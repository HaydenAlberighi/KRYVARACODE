"""
Data processing utilities for KRYVARACODE AI System Stack
"""


import numpy as np
import pandas as pd


def load_data(file_path: str) -> pd.DataFrame:
    """
    Load data from various file formats

    Args:
        file_path: Path to the data file

    Returns:
        Loaded DataFrame
    """
    if file_path.endswith(".csv"):
        return pd.read_csv(file_path)
    elif file_path.endswith(".parquet"):
        return pd.read_parquet(file_path)
    elif file_path.endswith(".json"):
        return pd.read_json(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_path}")


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the data by handling missing values and removing duplicates

    Args:
        df: Input DataFrame

    Returns:
        Cleaned DataFrame
    """
    # Make a copy to avoid modifying the original
    df_clean = df.copy()

    # Remove duplicates
    df_clean = df_clean.drop_duplicates()

    # Handle missing values (simple strategy - can be customized)
    # For numeric columns, fill with median
    numeric_cols = df_clean.select_dtypes(include=[np.number]).columns
    df_clean[numeric_cols] = df_clean[numeric_cols].fillna(
        df_clean[numeric_cols].median()
    )

    # For categorical columns, fill with mode
    categorical_cols = df_clean.select_dtypes(include=["object"]).columns
    for col in categorical_cols:
        df_clean[col] = df_clean[col].fillna(
            df_clean[col].mode()[0] if not df_clean[col].mode().empty else ""
        )

    return df_clean


def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """
    Perform feature engineering on the data

    Args:
        df: Input DataFrame

    Returns:
        DataFrame with engineered features
    """
    # Make a copy to avoid modifying the original
    df_fe = df.copy()

    # Example feature engineering (can be customized based on data)
    # This is just a placeholder - real feature engineering would be domain-specific

    return df_fe


def split_features_target(
    df: pd.DataFrame, target_column: str
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Split DataFrame into features and target

    Args:
        df: Input DataFrame
        target_column: Name of the target column

    Returns:
        Tuple of (features DataFrame, target Series)
    """
    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' not found in DataFrame")

    X = df.drop(columns=[target_column])
    y = df[target_column]
    return X, y


def save_data(df: pd.DataFrame, file_path: str) -> None:
    """
    Save DataFrame to file

    Args:
        df: DataFrame to save
        file_path: Path to save the file
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    if file_path.endswith(".csv"):
        df.to_csv(file_path, index=False)
    elif file_path.endswith(".parquet"):
        df.to_parquet(file_path, index=False)
    elif file_path.endswith(".json"):
        df.to_json(file_path, indent=2)
    else:
        raise ValueError(f"Unsupported file format: {file_path}")


# Import os at the top to avoid issues
import os
