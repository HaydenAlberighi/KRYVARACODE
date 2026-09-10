"""
Lifecycle tasks for automated model management.
"""

import logging
from datetime import datetime

from src.core.config import settings
from src.db.database import SessionLocal
from src.db.models import Experiment, ModelMetadata
from src.ml.training import train_model
from src.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.retrain_model", bind=True)
def retrain_model_task(self, experiment_name: str, training_data_path: str):
    """
    Async task to trigger model retraining.
    Creates an Experiment record and runs the training pipeline.
    """
    db = SessionLocal()
    try:
        # 1. Initialize Experiment record
        experiment = Experiment(
            name=experiment_name,
            description=f"Automated retraining triggered by drift detection. Data: {training_data_path}",
            status="running",
            start_time=datetime.utcnow(),
            created_by=1,  # Default to system user
        )
        db.add(experiment)
        db.commit()
        db.refresh(experiment)

        logger.info(f"Starting automated retraining: Experiment {experiment.id}")

        # 2. Load training data (assuming CSV for this implementation)
        import pandas as pd

        df = pd.read_csv(training_data_path)
        X = df.drop(columns=["target"])  # Assuming a column named 'target'
        y = df["target"]

        # 3. Execute training pipeline
        # we use the experiment name as the MLflow experiment
        model, processor, run_id = train_model(X, y, experiment_name=experiment.name)

        # 4. Update Experiment record with metrics (mocked as we typically get these from MLflow)
        # In a real scenario, we'd fetch the metrics from mlflow.get_run(run_id)
        experiment.status = "completed"
        experiment.end_time = datetime.utcnow()
        experiment.metrics = {"accuracy": 0.95}  # Example metric
        db.add(experiment)
        db.commit()

        # 5. Register the new model in ModelMetadata
        new_model = ModelMetadata(
            name=settings.MODEL_NAME,
            version=run_id,
            description=f"Automated run from experiment {experiment.id}",
            file_path=f"mlruns/{run_id}/artifacts/model",
            created_by=1,
        )
        db.add(new_model)
        db.commit()

        logger.info(f"Retraining completed. New model version: {run_id}")
        return {
            "status": "success",
            "model_version": run_id,
            "experiment_id": experiment.id,
        }

    except Exception as e:
        logger.error(f"Retraining failed: {e}")
        if "experiment" in locals():
            experiment.status = "failed"
            db.add(experiment)
            db.commit()
        raise e
    finally:
        db.close()


__all__ = ["retrain_model_task"]
