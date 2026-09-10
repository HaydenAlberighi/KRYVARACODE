from src.api.prediction.service import PredictionService
from src.core.config import settings
from src.db import crud
from src.db.database import SessionLocal
from src.ml.training import train_model
from src.tasks import celery_app

# Logging with optional loguru fallback
try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

# Initialize the service to handle model loading
# In a real production env, this might be handled by a worker's warm-up
prediction_service = PredictionService()


@celery_app.task(name="tasks.predict", bind=True)
def predict_task(self, features: dict):
    """
    Async task to perform model prediction.
    Wraps the synchronous PredictionService.predict() method.
    """
    try:
        # Call the synchronous prediction logic
        result = prediction_service.predict(features)
        return result
    except Exception as e:
        # Log error and fail task
        self.update_state(state="FAILURE", meta={"exc": str(e)})
        raise e


@celery_app.task(name="tasks.train", bind=True)
def train_task(self, dataset_id: int, target: str, experiment: str, user_id: int):
    """
    Async task to train a model using a registered dataset.
    Wraps the training pipeline with MLflow tracking and experiment recording.
    """
    db = SessionLocal()
    try:
        # Get the dataset info
        dataset = crud.get_dataset(db, dataset_id=dataset_id)
        if dataset is None:
            raise ValueError(f"Dataset {dataset_id} not found")

        # Read the dataset file
        import os

        data_path = dataset.storage_uri
        if not os.path.exists(data_path):
            raise ValueError(f"Dataset file not found at {data_path}")

        # Load data with pandas/numpy (may fail if ML deps not installed)
        try:
            import pandas as pd

            df = pd.read_csv(data_path)
        except Exception:
            raise RuntimeError(
                "Training requires pandas, which is not installed. Install ML dependencies to use training."
            ) from None

        X = df.drop(columns=[target], errors="ignore")
        y = df[target] if target in df.columns else df.iloc[:, -1]

        # Execute training pipeline
        _model, _processor, run_id = train_model(X, y, experiment_name=experiment)

        # Register the new model in ModelMetadata
        model_data = {
            "name": settings.MODEL_NAME,
            "version": str(run_id),
            "description": f"Training experiment: {experiment}, dataset: {dataset_id}",
            "file_path": f"mlruns/{run_id}/artifacts/model",
        }
        new_model = crud.create_model_metadata(db, model_data, user_id)

        return {
            "status": "success",
            "model_version": str(run_id),
            "dataset_id": dataset_id,
            "experiment": experiment,
            "model_id": new_model.id,
        }

    except Exception as e:
        logger.error(f"Training task failed: {e}")
        raise e
    finally:
        db.close()


__all__ = ["predict_task", "train_task"]
