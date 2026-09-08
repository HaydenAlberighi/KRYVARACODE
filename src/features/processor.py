"""
Feature processing module for KRYVARACODE AI System Stack
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Union, Optional, Callable
import pickle
import os
from abc import ABC, abstractmethod
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    StandardScaler,
    MinMaxScaler,
    OneHotEncoder,
    LabelEncoder,
)
from sklearn.impute import SimpleImputer
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)


class FeatureProcessor:
    """
    A feature processing pipeline that ensures consistent feature transformation
    between training and inference.
    """

    def __init__(self, steps: Optional[List] = None):
        self.pipeline = Pipeline(steps) if steps else None
        self.feature_names_in_ = None
        self.feature_names_out_ = None

    def fit(self, X: pd.DataFrame, y=None):
        """Fit the feature processor on training on training data"""
        if self.pipeline is None:
            # Create a default pipeline if none provided
            self._create_default_pipeline(X)

        self.pipeline.fit(X, y)
        self.feature_names_in_ = list(X.columns)
        # Get output feature names (this is approximate for complex pipelines)
        try:
            self.feature_names_out_ = [
                f"feature_{i}" for i in range(len(self.pipeline.transform(X.iloc[:1])))
            ]
        except:
            self.feature_names_out_ = None
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Transform data using the fitted pipeline"""
        if self.pipeline is None:
            raise ValueError("Feature processor has not been fitted yet")

        transformed = self.pipeline.transform(X)

        # Convert back to DataFrame with appropriate column names
        if hasattr(transformed, "toarray"):
            transformed = transformed.toarray()

        if isinstance(transformed, np.ndarray):
            if (
                self.feature_names_out_
                and len(self.feature_names_out_) == transformed.shape[1]
            ):
                return pd.DataFrame(
                    transformed, columns=self.feature_names_out_, index=X.index
                )
            else:
                # Generate generic column names
                col_names = [f"feature_{i}" for i in range(transformed.shape[1])]
                return pd.DataFrame(transformed, columns=col_names, index=X.index)
        else:
            return pd.DataFrame(transformed, index=X.index)

    def fit_transform(self, X: pd.DataFrame, y=None) -> pd.DataFrame:
        """Fit and transform in one step"""
        return self.fit(X, y).transform(X)

    def _create_default_pipeline(self, X: pd.DataFrame):
        """Create a default processing pipeline based on data types"""
        from sklearn.compose import ColumnTransformer

        # Identify column types
        numeric_features = X.select_dtypes(include=[np.number]).columns.tolist()
        categorical_features = X.select_dtypes(
            include=["object", "bool"]
        ).columns.tolist()

        # Create transformers for each type
        numeric_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )

        categorical_transformer = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
                ("onehot", OneHotEncoder(handle_unknown="ignore")),
            ]
        )

        # Combine transformers
        preprocessor = ColumnTransformer(
            transformers=[
                ("num", numeric_transformer, numeric_features),
                ("cat", categorical_transformer, categorical_features),
            ]
        )

        self.pipeline = Pipeline(steps=[("preprocessor", preprocessor)])

    def save(self, filepath: str):
        """Save the feature processor to disk"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            pickle.dump(self, f)
        logger.info(f"Feature processor saved to {filepath}")

    @classmethod
    def load(cls, filepath: str):
        """Load a feature processor from disk"""
        with open(filepath, "rb") as f:
            processor = pickle.load(f)
        logger.info(f"Feature processor loaded from {filepath}")
        return processor


def create_feature_processor_from_config(config: Dict) -> FeatureProcessor:
    """
    Create a feature processor from a configuration dictionary.

    Args:
        config: Dictionary defining the feature processing steps

    Returns:
        Configured FeatureProcessor instance
    """
    # This would be expanded based on specific needs
    # For now, return a default processor
    return FeatureProcessor()


# Example feature transformers (can be expanded)
class FeatureSelector(BaseEstimator, TransformerMixin):
    """Select specific features from a DataFrame"""

    def __init__(self, features: List[str]):
        self.features = features

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        if isinstance(X, pd.DataFrame):
            return X[self.features]
        else:
            # Assume X is already in correct order if not DataFrame
            return X


class PolynomialFeaturesTransformer(BaseEstimator, TransformerMixin):
    """Generate polynomial features"""

    def __init__(self, degree: int = 2, include_bias: bool = False):
        self.degree = degree
        self.include_bias = include_bias
        from sklearn.preprocessing import PolynomialFeatures

        self.poly = PolynomialFeatures(degree=degree, include_bias=include_bias)

    def fit(self, X, y=None):
        self.poly.fit(X)
        return self

    def transform(self, X):
        return self.poly.transform(X)


# Convenience functions for common operations
def scale_features(X: pd.DataFrame, method: str = "standard") -> pd.DataFrame:
    """Scale features using specified method"""
    from sklearn.preprocessing import StandardScaler, MinMaxScaler

    if method == "standard":
        scaler = StandardScaler()
    elif method == "minmax":
        scaler = MinMaxScaler()
    else:
        raise ValueError(f"Unknown scaling method: {method}")

    scaled_data = scaler.fit_transform(X)
    return pd.DataFrame(scaled_data, columns=X.columns, index=X.index)


def encode_categorical(X: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Encode categorical variables using one-hot encoding"""
    return pd.get_dummies(X, columns=columns, drop_first=True)
