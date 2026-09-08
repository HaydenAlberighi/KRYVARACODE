#!/usr/bin/env python3
"""
Test script to verify imports work correctly
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_imports():
    """Test that we can import the main modules"""
    try:
        # Test config import
        from src.core.config import settings

        print("✓ Successfully imported settings")
        print(f"  APP_NAME: {settings.APP_NAME}")

        # Test API routes import
        from src.api.routes import api_router

        print("✓ Successfully imported api_router")

        # Test main app import
        from src.api.main import app

        print("✓ Successfully imported FastAPI app")

        # Test auth imports
        from src.api.auth.auth import authenticate_user, create_access_token
        from src.api.auth.router import router as auth_router

        print("✓ Successfully imported auth modules")

        # Test db imports
        from src.db import models, crud
        from src.db.database import Base, engine, SessionLocal, get_db

        print("✓ Successfully imported database modules")

        print("\n🎉 All imports successful!")
        return True

    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
