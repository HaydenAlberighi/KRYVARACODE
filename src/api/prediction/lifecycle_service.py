"""
Service for managing the ML model lifecycle: promotion and versioning.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.models import ModelMetadata

logger = logging.getLogger(__name__)

# MLflow is optional at import time - guard like service.py
mlflow: Any = None
_MLFLOW_AVAILABLE = False
try:
    import mlflow  # type: ignore[import]

    _MLFLOW_AVAILABLE = True
except ImportError:
    _MLFLOW_AVAILABLE = False


class ModelLifecycleService:
    def __init__(self):
        if _MLFLOW_AVAILABLE:
            mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        else:
            logger.warning(
                "MLflow not available - lifecycle service will raise RuntimeError on use"
            )

    def promote_model(self, db: Session, version_to_promote: str) -> tuple[bool, str]:
        """
        Promotes a model version to 'Production' if its metrics are superior
        to the current production model.
        """
        if not _MLFLOW_AVAILABLE:
            raise RuntimeError("MLflow not installed - model promotion unavailable")

        try:
            # 1. Get current production model version from DB
            current_prod = (
                db.query(ModelMetadata)
                .filter(
                    ModelMetadata.name == settings.MODEL_NAME,
                    # In a real system we'd have a 'stage' column in ModelMetadata,
                    # for now we track the 'Production' tag in MLflow
                )
                .first()
            )

            # 2. Fetch metrics for both versions from MLflow
            # We use the version (run_id) to fetch the run metrics
            new_run = mlflow.get_run(version_to_promote)
            new_accuracy = new_run.data.metrics.get("accuracy", 0.0)

            if current_prod:
                prod_run = mlflow.get_run(current_prod.version)
                prod_accuracy = prod_run.data.metrics.get("accuracy", 0.0)

                if new_accuracy <= prod_accuracy:
                    return (
                        False,
                        f"New model accuracy ({new_accuracy:.4f}) is not better than production ({prod_accuracy:.4f})",
                    )

            # 3. Update MLflow stage to 'Production'
            client = mlflow.tracking.MlflowClient()

            # Find the version number for the given run_id
            model_versions = client.get_latest_versions(settings.MODEL_NAME)
            version_num = None
            for mv in model_versions:
                if mv.run_id == version_to_promote:
                    version_num = mv.version
                    break

            if not version_num:
                return (
                    False,
                    f"Could not find model version number for run {version_to_promote}",
                )

            client.transition_model_version_stage(
                name=settings.MODEL_NAME,
                version=version_num,
                stage="Production",
                archive_existing_versions=True,
            )

            # 4. Update ModelMetadata in DB
            if current_prod:
                # This is a simplification: we just update the metadata of the 'active' record
                # or create a new one and mark the old as archived.
                # For this implementation, we'll update the record for the new version.
                pass

            # Ensure the promoted version is registered as the primary metadata entry
            meta = (
                db.query(ModelMetadata)
                .filter(ModelMetadata.version == version_to_promote)
                .first()
            )
            if not meta:
                meta = ModelMetadata(
                    name=settings.MODEL_NAME,
                    version=version_to_promote,
                    description="Promoted to Production via LifecycleService",
                    file_path=f"mlruns/{version_to_promote}/artifacts/model",
                    created_by=1,
                )
                db.add(meta)

            db.commit()

            return True, f"Model {version_to_promote} promoted to Production."

        except Exception as e:
            logger.error(f"Promotion failed: {e}")
            db.rollback()
            return False, str(e)


lifecycle_service = ModelLifecycleService()
