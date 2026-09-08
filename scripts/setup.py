#!/usr/bin/env python3
"""
Setup script for KRYVARACODE AI System Stack
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(command, description):
    """Run a command and handle errors"""
    print(f"\n{description}...")
    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        print(f"✓ {description} completed successfully")
        return result
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed:")
        print(f"  Error: {e.stderr}")
        return None


def main():
    """Main setup function"""
    print("🚀 Setting up KRYVARACODE AI System Stack")
    print("=" * 50)

    # Check if we're in the right directory
    if not Path("KRYVARACODE").exists() and not Path(".gitignore").exists():
        print("❌ Please run this script from the KRYVARACODE root directory")
        sys.exit(1)

    # Create virtual environment
    if not Path("venv").exists():
        run_command(f"{sys.executable} -m venv venv", "Creating virtual environment")

    # Determine activation script based on OS
    if os.name == "nt":  # Windows
        activate_script = "venv\\Scripts\\activate"
        pip_path = "venv\\Scripts\\pip"
    else:  # Unix/Linux/MacOS
        activate_script = "source venv/bin/activate"
        pip_path = "venv/bin/pip"

    # Install dependencies
    run_command(f"{pip_path} install --upgrade pip", "Upgrading pip")

    run_command(
        f"{pip_path} install -r requirements/base.txt", "Installing base dependencies"
    )

    run_command(
        f"{pip_path} install -r requirements/dev.txt",
        "Installing development dependencies",
    )

    # Install pre-commit hooks
    run_command(f"{pip_path} install pre-commit", "Installing pre-commit")

    run_command(f"{pip_path} run pre-commit install", "Installing pre-commit hooks")

    # Create .env file from example if it doesn't exist
    if not Path(".env").exists():
        if Path(".env.example").exists():
            run_command("cp .env.example .env", "Creating .env file from example")
            print("⚠️  Please edit .env file with your configuration")
        else:
            print("⚠️  No .env.example found, please create .env file manually")

    # Create necessary directories
    directories = ["data", "models", "logs", "experiments", "deployments/prometheus"]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directory: {directory}")

    print("\n" + "=" * 50)
    print("🎉 Setup completed successfully!")
    print("\nNext steps:")
    print("1. Activate the virtual environment:")
    print(f"   {activate_script}")
    print("2. Edit .env file with your configuration")
    print("3. Run the application:")
    print("   uvicorn src.api.main:app --reload")
    print("4. Visit http://localhost:8000 for the API")
    print("5. Visit http://localhost:8000/docs for API documentation")


if __name__ == "__main__":
    main()
