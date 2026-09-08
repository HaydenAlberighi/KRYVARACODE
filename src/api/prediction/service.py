"""
Model prediction service for KRYVARACODE AI System Stack
"""

import logging
import os
import pickle
from typing import Any, Dict, Optional, Union

from src.core.config import settings

# ML dependencies are optional at import time: the API must be able to boot
# even when the ML layer (mlflow / sklearn / pandas) is not provisioned.
# Callers that hit an unavailable dependency get a clear RuntimeError instead
# of a ModuleNotFoundError at app startup.
mlflow: Any = None
_MLFLOW_AVAILABLE = False
try:  # pragma: no cover - exercised only on machines without ML deps
    import mlflow  # type: ignore[import]
    import mlflow.sklearn  # type: ignore[import]

    _MLFLOW_AVAILABLE = True
except ImportError:  # pragma: no cover
    _MLFLOW_AVAILABLE = False

np: Any = None
pd: Any = None
_PANDAS_AVAILABLE = False
try:  # pragma: no cover
    import numpy as np  # type: ignore[import]
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
        """Load the feature processor associated with a model"""
        try:
            # In a real implementation, we would store the run ID with the model
            # For this example, we'll try to download the feature processor artifact
            # associated with the latest version of the model

            # Get model version info
            client = mlflow.tracking.MlflowClient()
            model_version_infos = client.get_latest_versions(
                self.model_name, stages=["None"]
            )

            # For simplicity in this example, we'll create a default feature processor
            # In production, you would properly link the model to its feature processor
            logger.info(
                "Using default feature processor (in production, this would be properly linked)"
            )
            self.feature_processor = FeatureProcessor()
            # Note: This feature processor is not fitted, so it would need to be fitted
            # or loaded from a proper artifact location

        except Exception as e:
            logger.warning(f"Could not load associated feature processor: {e}")
            self.feature_processor = None

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Make a prediction using the loaded model and feature processor"""
        if self.model is None:
            raise RuntimeError(
                "No model loaded. Please check MLflow connection and model registration."
            )

        if not _PANDAS_AVAILABLE:
            raise RuntimeError(
                "Prediction requires pandas/numpy, which are not installed."
            )

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
                "prediction": prediction.tolist()
                if hasattr(prediction, "tolist")
                else prediction
            }

            if hasattr(self.model, "predict_proba"):
                try:
                    proba = self.model.predict_proba(X_processed)
                    result["probabilities"] = proba.tolist()
                except Exception:
                    pass  # Probabilities not available or failed

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
            "feature_processor_fitted": hasattr(
                self.feature_processor, "feature_names_in_"
            )
            if self.feature_processor is not None
            else False,
        }

    def reload_model(self):
        """Force reload of the model and feature processor from MLflow"""
        self._load_model_from_mlflow(settings.MLFLOW_TRACKING_URI)
        return self.get_model_info()


# Create singleton instance
prediction_service = PredictionService()
