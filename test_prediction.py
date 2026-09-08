#!/usr/bin/env python3
"""
Test script to verify prediction module imports work correctly
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_prediction_imports():
    """Test that we can import the prediction modules"""
    try:
        # Test prediction service import
        from src.api.prediction.service import PredictionService, prediction_service

        print("[OK] Successfully imported prediction service")

        # Test prediction router import
        from src.api.prediction import router as prediction_router

        print("[OK] Successfully imported prediction router")

        # Test that API routes can be imported (this will show if there are circular import issues)
        from src.api.routes import api_router

        print("[OK] Successfully imported main API router with prediction included")

        print("\n[SUCCESS] All prediction imports successful!")
        return True

    except Exception as e:
        print(f"[ERROR] Import failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_prediction_imports()
    sys.exit(0 if success else 1)
