"""
Model training utilities for KRYVARACODE AI System Stack
"""

import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import pandas as pd
import numpy as np
import os
import pickle
from src.core.config import settings
from src.features.processor import FeatureProcessor


def train_model(X, y, experiment_name="default"):
    """
    Train a model with MLflow tracking

    Args:
        X: Features
        y: Target variable
        experiment_name: Name of the MLflow experiment

    Returns:
        Trained model, feature processor, and run ID
    """
    # Set up MLflow
    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(experiment_name)

    # Start MLflow run
    with mlflow.start_run() as run:
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Create and fit feature processor
        feature_processor = FeatureProcessor()
        X_train_processed = feature_processor.fit_transform(X_train)
        X_test_processed = feature_processor.transform(X_test)

        # Train model
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train_processed, y_train)

        # Make predictions
        y_pred = model.predict(X_test_processed)
        accuracy = accuracy_score(y_test, y_pred)

        # Log parameters
        mlflow.log_param("model_type", "RandomForestClassifier")
        mlflow.log_param("n_estimators", 100)
        mlflow.log_param("random_state", 42)

        # Log metrics
        mlflow.log_metric("accuracy", accuracy)

        # Log model
        mlflow.sklearn.log_model(model, "model")

        # Save and log feature processor
        os.makedirs("tmp", exist_ok=True)
        feature_processor_path = "tmp/feature_processor.pkl"
        feature_processor.save(feature_processor_path)
        mlflow.log_artifact(feature_processor_path, "feature_processor")

        return model, feature_processor, run.info.run_id


def load_model(model_uri):
    """
    Load a model from MLflow

    Args:
        model_uri: URI of the model in MLflow

    Returns:
        Loaded model
    """
    return mlflow.sklearn.load_model(model_uri)


def load_feature_processor(run_id, artifact_path="feature_processor"):
    """
    Load a feature processor from MLflow run artifacts

    Args:
        run_id: MLflow run ID
        artifact_path: Path to the feature processor artifact within the run

    Returns:
        Loaded feature processor
    """
    import mlflow.artifacts

    # Download the feature processor artifact
    local_path = mlflow.artifacts.download_artifacts(
        run_id=run_id, artifact_path=f"{artifact_path}/feature_processor.pkl"
    )

    # Load the feature processor
    return FeatureProcessor.load(local_path)


def predict(model, feature_processor, X):
    """
    Make predictions using a trained model and feature processor

    Args:
        model: Trained model
        feature_processor: Fitted feature processor
        X: Features to predict on

    Returns:
        Predictions
    """
    # Process features using the feature processor
    X_processed = feature_processor.transform(X)
    return model.predict(X_processed)


def predict_proba(model, feature_processor, X):
    """
    Make probability predictions using a trained model and feature processor

    Args:
        model: Trained model
        feature_processor: Fitted feature processor
        X: Features to predict on

    Returns:
        Prediction probabilities
    """
    # Process features using the feature processor
    X_processed = feature_processor.transform(X)
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X_processed)
    else:
        raise AttributeError("Model does not have predict_proba method")
