# Contributing to KRYVARACODE

Thank you for considering contributing to KRYVARACODE. This document covers the process for contributing to this project.

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Git
- Docker and Docker Compose (optional, for containerized development)

### Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/KRYVARACODE.git
   cd KRYVARACODE
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements/base.txt
   pip install -r requirements/ml.txt  # Only if working on ML components
   ```

4. Install pre-commit hooks:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

5. Copy environment configuration:
   ```bash
   cp .env.example .env
   # Edit .env with your local configuration
   ```

6. Run the test suite:
   ```bash
   pytest
   ```

## How to Contribute

### Reporting Issues

- Use the GitHub issue tracker
- Check existing issues before creating a new one
- Include steps to reproduce for bugs
- Include your OS, Python version, and KRYVARACODE version

### Pull Requests

1. Create a branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the coding standards below

3. Add tests for new functionality

4. Run the full test suite:
   ```bash
   pytest
   ruff check src/ tests/
   mypy src/
   ```

5. Commit with a clear message and push:
   ```bash
   git commit -m "feat: add new feature description"
   git push origin feature/your-feature-name
   ```

6. Open a Pull Request against `main`

## Coding Standards

### Python

- Follow PEP 8 style (enforced by `ruff`)
- Use type hints on all function signatures
- Write docstrings for all public modules, classes, and functions
- Keep functions focused and under 50 lines where possible
- Use Pydantic v2 models for data validation
- Prefer `async`/`await` for I/O-bound operations

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation changes
- `refactor:` — Code refactoring without behavior change
- `test:` — Adding or updating tests
- `ci:` — CI/CD changes
- `chore:` — Maintenance tasks

Examples:
```
feat: add batch prediction endpoint
fix: resolve race condition in event bus
docs: update API reference for auth endpoints
test: add integration tests for Forge pipeline
```

### Code Quality

The project enforces quality through:

- **ruff** — Linting and formatting
- **mypy** — Static type checking
- **bandit** — Security analysis
- **pytest** with 80% coverage threshold

Run all checks before submitting:
```bash
ruff check src/ tests/
mypy src/
bandit -r src/
pytest --cov=src --cov-report=term-missing
```

## Project Structure

```
src/
├── agent/          # Autonomous agent system (Sovereign, Forge, Eye, Aegis, Nerve)
├── api/            # FastAPI application and routes
├── core/           # Configuration, exceptions, logging
├── db/             # SQLAlchemy models and CRUD operations
├── ml/             # Machine learning training pipeline
└── schemas/        # Pydantic v2 validation models
```

When adding new functionality:

- **Agent code** goes in `src/agent/` under the appropriate subsystem
- **API endpoints** go in `src/api/` with a new router file
- **Database models** go in `src/db/models.py`
- **Pydantic schemas** go in `src/schemas/`
- **Tests** go in `tests/` with a descriptive filename

## Aegis Safety

If your change affects agent behavior, tool execution, or system operations:

- Ensure Aegis invariants still pass
- Add test cases for new safety-relevant code
- Document any changes to the safety model in your PR description

## Getting Help

- Check existing documentation and code comments
- Look at similar contributions for patterns
- Open an issue for questions about approach before starting large changes

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
