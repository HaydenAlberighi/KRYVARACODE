"""
Helper utilities for KRYVARACODE AI System Stack
"""

import json
import os
from typing import Any

import yaml


def ensure_dir(directory: str) -> None:
    """
    Ensure a directory exists, creating it if necessary

    Args:
        directory: Path to the directory
    """
    os.makedirs(directory, exist_ok=True)


def load_json(file_path: str) -> dict[str, Any]:
    """
    Load data from a JSON file

    Args:
        file_path: Path to the JSON file

    Returns:
        Dictionary with the loaded data
    """
    with open(file_path) as f:
        return json.load(f)


def save_json(data: dict[str, Any], file_path: str) -> None:
    """
    Save data to a JSON file

    Args:
        data: Dictionary to save
        file_path: Path to save the JSON file
    """
    ensure_dir(os.path.dirname(file_path))
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)


def load_yaml(file_path: str) -> dict[str, Any]:
    """
    Load data from a YAML file

    Args:
        file_path: Path to the YAML file

    Returns:
        Dictionary with the loaded data
    """
    with open(file_path) as f:
        return yaml.safe_load(f)


def save_yaml(data: dict[str, Any], file_path: str) -> None:
    """
    Save data to a YAML file

    Args:
        data: Dictionary to save
        file_path: Path to save the YAML file
    """
    ensure_dir(os.path.dirname(file_path))
    with open(file_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)


def get_file_size(file_path: str) -> int:
    """
    Get the size of a file in bytes

    Args:
        file_path: Path to the file

    Returns:
        Size of the file in bytes
    """
    return os.path.getsize(file_path)


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes into a human-readable string

    Args:
        bytes_value: Number of bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"
