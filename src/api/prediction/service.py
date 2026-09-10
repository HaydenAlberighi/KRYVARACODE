"""
Model prediction service for KRYVARACODE AI System Stack
"""

import logging
import time
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models import PredictionLog

# ML dependencies are optional at import time: the API must be able to boot
# even when the ML layer (mlflow / sklearn / pandas) is not provisioned.
# Callers that hit an unavailable dependency get a clear RuntimeError instead
# of a ModuleNotFoundError at app startup.
mlflow: Any = None
mlflow_artifacts: Any = None
_MLFLOW_AVAILABLE = False
try:  # pragma: no cover - exercised only on machines without ML deps
    import mlflow  # type: ignore[import]
    import mlflow.sklearn  # type: ignore[import]

    mlflow = mlflow
    _MLFLOW_AVAILABLE = True
except ImportError:  # pragma: no cover
    _MLFLOW_AVAILABLE = False

np: Any = None
pd: Any = None
_PANDAS_AVAILABLE = False
try:  # pragma: no cover
    import pandas as pd  # type: ignore[import]

    _PANDAS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PANDAS_AVAILABLE = False

FeatureProcessor: Any = None
_FEATURE_PROCESSOR_AVAILABLE = False
try:  # pragma: no cover
    from src.features.processor import FeatureProcessor

    _FEATURE_PROCESSOR_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FEATURE_PROCESSOR_AVAILABLE = False

logger = logging.getLogger(__name__)


class PredictionService:
    def __init__(self):
        self.model = None
        self.feature_processor = None
        self.model_uri = None
        self.feature_processor_uri = None
        self.model_name = getattr(settings, "MODEL_NAME", "kryvara_model")
        self._load_model_from_mlflow(settings.MLFLOW_TRACKING_URI)

    def _load_model_from_mlflow(self, tracking_uri: str):
        """Load the latest production model and feature processor from MLflow"""
        if not _MLFLOW_AVAILABLE:
            logger.warning("MLflow not available — skipping model load")
            self.model = None
            self.feature_processor = None
            return
        try:
            mlflow.set_tracking_uri(tracking_uri)

            # Try to load production model
            try:
                model_uri = f"models:/{self.model_name}/Production"
                self.model = mlflow.sklearn.load_model(model_uri)
                self.model_uri = model_uri
                logger.info(f"Loaded model from {model_uri}")

                # Try to load the associated feature processor
                # We need to get the run ID from the model URI to fetch artifacts
                # For simplicity, we'll look for a feature processor in the same model version
                self._load_associated_feature_processor(model_uri)

            except Exception:
                # Fallback to latest version if no production model exists
                try:
                    model_uri = f"models:/{self.model_name}/latest"
                    self.model = mlflow.sklearn.load_model(model_uri)
                    self.model_uri = model_uri
                    logger.info(f"Loaded latest model from {model_uri}")

                    # Try to load the associated feature processor
                    self._load_associated_feature_processor(model_uri)

                except Exception as e:
                    logger.warning(f"Could not load model from MLflow: {e}")
                    self.model = None
                    self.feature_processor = None

        except Exception as e:
            logger.error(f"Error setting up MLflow connection: {e}")
            self.model = None
            self.feature_processor = None

    def _load_associated_feature_processor(self, model_uri: str):
        """Load the feature processor strictly associated with a specific model version"""
        try:
            # To ensure strict binding and prevent training-serving skew,
            # we must load the processor that was saved during the same MLflow run.

            # 1. Extract run_id from the model_uri (e.g., 'models:/name/version' or 'runs:/<run_id>/model')
            # For simplicity, we'll assume the URI contains the run_id or we can resolve it via MLflow client
            client = mlflow.tracking.MlflowClient()

            # In a production system, we would resolve the model_uri to its run_id.
            # Here, we resolve the latest version of the model name to get the current run_id.
            model_versions = client.get_latest_versions(self.model_name)
            if not model_versions:
                raise RuntimeError("No model versions found in registry")

            # We take the production model's run_id
            run_id = model_versions[0].run_id

            # 2. Download the specific feature_processor artifact from that run
            import mlflow.artifacts

            local_path = mlflow.artifacts.download_artifacts(
                run_id=run_id, artifact_path="feature_processor/feature_processor.pkl"
            )

            self.feature_processor = FeatureProcessor.load(local_path)
            logger.info(f"Strictly bound feature processor loaded from run {run_id}")

        except Exception as e:
            logger.error(f"CRITICAL: Could not load bound feature processor: {e}")
            # We raise an error instead of falling back to a default processor to prevent
            # silent failures and incorrect predictions (Training-Serving Skew)
            raise RuntimeError(f"Feature processor binding failed: {e}")

    def predict(
        self,
        features: Dict[str, Any],
        db: Optional[Session] = None,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Make a prediction using the loaded model and feature processor"""
        if self.model is None:
            raise RuntimeError(
                "No model loaded. Please check MLflow connection and model registration."
            )

        if not _PANDAS_AVAILABLE:
            raise RuntimeError(
                "Prediction requires pandas/numpy, which are not installed."
            )

        start_time = time.perf_counter()
        try:
            # Convert features to DataFrame (assuming tabular data)
            df = pd.DataFrame([features])

            # Process features using the feature processor if available
            if self.feature_processor is not None:
                try:
                    # Check if the feature processor is fitted
                    if hasattr(self.feature_processor, "feature_names_in_"):
                        X_processed = self.feature_processor.transform(df)
                    else:
                        # Feature processor not fitted, use raw features
                        # In production, you would want to handle this case properly
                        logger.warning(
                            "Feature processor not fitted, using raw features"
                        )
                        X_processed = df
                except Exception as e:
                    logger.warning(
                        f"Error processing features: {e}, using raw features"
                    )
                    X_processed = df
            else:
                # No feature processor available, use raw features
                X_processed = df

            # Make prediction
            prediction = self.model.predict(X_processed)

            # Get prediction probabilities if available (for classifiers)
            result = {
                "prediction": (
                    prediction.tolist() if hasattr(prediction, "tolist") else prediction
                )
            }

            if hasattr(self.model, "predict_proba"):
                try:
                    proba = self.model.predict_proba(X_processed)
                    result["probabilities"] = proba.tolist()
                except Exception:
                    pass  # Probabilities not available or failed

            latency_ms = (time.perf_counter() - start_time) * 1000

            if db is not None:
                try:
                    log = PredictionLog(
                        model_version=self.model_uri or "unknown",
                        features=features,
                        prediction=result["prediction"],
                        probabilities=result.get("probabilities"),
                        latency_ms=latency_ms,
                        user_id=user_id,
                    )
                    db.add(log)
                    db.commit()
                except Exception as e:
                    logger.error(f"Failed to log prediction: {e}")
                    db.rollback()

            return result

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            raise RuntimeError(f"Prediction failed: {str(e)}")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the currently loaded model"""
        if self.model is None:
            return {"status": "no_model_loaded"}

        return {
            "status": "model_loaded",
            "model_uri": self.model_uri,
            "model_type": type(self.model).__name__,
            "has_feature_processor": self.feature_processor is not None,
            "feature_processor_fitted": (
                hasattr(self.feature_processor, "feature_names_in_")
                if self.feature_processor is not None
                else False
            ),
        }

    def reload_model(self):
        """Force reload of the model and feature processor from MLflow"""
        self._load_model_from_mlflow(settings.MLFLOW_TRACKING_URI)
        return self.get_model_info()


# Create singleton instance
prediction_service = PredictionService()
