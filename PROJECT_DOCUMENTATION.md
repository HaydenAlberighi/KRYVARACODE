# KRYVARACODE Project Documentation

> Consolidated documentation for the KRYVARACODE AI System Stack

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [ML Pipeline](#ml-pipeline)
3. [Code Review & Issues](#code-review--issues)
4. [Test Infrastructure](#test-infrastructure)
5. [Roadmap](#roadmap)

---

## Project Overview

KRYVARACODE is a comprehensive AI system stack built on FastAPI with SQLAlchemy ORM, MLflow integration, and an agent tool system. It provides a production-ready foundation for building sophisticated AI applications with proper MLOps practices, security, and scalability.

### Core Structure

- **Modular Architecture**: Clean separation between API, core ML, data processing, and utilities
- **Production-Ready Design**: Follows best practices for scalability, maintainability, and security
- **Environment Configuration**: Pydantic-based settings management with environment variable support
- **Database Layer**: SQLAlchemy ORM with models for Users, Items, Model Metadata, and Experiments
- **Authentication System**: JWT-based auth with secure password hashing

### Key Components

#### API Layer (`src/api/`)
- **Main Entry Point** (`src/api/main.py`): FastAPI application with CORS, health checks, and routing
- **Authentication Module** (`src/api/auth/`):
  - JWT token generation and validation
  - Password hashing with bcrypt
  - Login/logout endpoints
  - Current user dependency
- **Model Management** (`src/api/models/`):
  - CRUD operations for model metadata
  - Model versioning and tracking
  - Integration with MLflow (in training module)
- **Data Processing** (`src/api/data/`):
  - Data ingestion and processing endpoints
  - Dataset management
  - Placeholder for ETL pipeline integration

#### Core Libraries (`src/core/`)
- **Configuration** (`src/core/config.py`): 
  - Pydantic Settings with environment variable support
  - Database URLs, API keys, service configurations
  - Development/production environment switching

#### Machine Learning (`src/ml/`)
- **Training Utilities** (`src/ml/training.py`):
  - MLflow integration for experiment tracking
  - Model training with scikit-learn (extensible to other frameworks)
  - Model loading and prediction utilities

#### Data Processing (`src/data/`)
- **Processor** (`src/data/processor.py`):
  - Data loading (CSV, Parquet, JSON)
  - Data cleaning and missing value handling
  - Feature engineering pipeline
  - Train/test split utilities

#### Utilities (`src/utils/`)
- **Helpers** (`src/utils/helpers.py`):
  - Directory creation utilities
  - JSON/YAML serialization
  - File size formatting
  - Common helper functions

#### Database (`src/db/`)
- **Models** (`src/db/models.py`):
  - User authentication and authorization
  - Item ownership and relationships
  - Model metadata tracking (name, version, file path, metrics)
  - Experiment tracking (status, metrics, parameters)
- **CRUD Operations** (`src/db/crud.py`):
  - Create, read, update, delete operations for all entities
  - Authentication helpers (password verification)
  - Database session management
- **Database Connection** (`src/db/database.py`):
  - SQLAlchemy engine and session factory
  - Dependency injection for FastAPI routes

### Agent System

The system is built around five interconnected agents:

```
┌─────────────────────────────────────────────────────┐
│                   SOVEREIGN                         │
│         Goal Pursuit & Swarm Intelligence           │
│   (Strategist → Executor → Critic adversarial loop) │
├────────────┬────────────┬──────────┬────────────────┤
│   FORGE    │    EYE     │  AEGIS   │     NERVE      │
│  Tool      │  Visual    │  Safety  │   Event Bus    │
│  Synthesis │  Perception│  Guard   │   & Dispatch   │
└────────────┴────────────┴──────────┴────────────────┘
```

| Agent | Role | Description |
|-------|------|-------------|
| **Sovereign** | Goal pursuit | Orchestrates autonomous task execution through an adversarial swarm loop |
| **Forge** | Tool synthesis | Builds new capabilities on demand through a 5-stage pipeline |
| **Eye** | Perception | Captures screenshots, monitors running processes, bridges environmental data |
| **Aegis** | Safety | Enforces behavioral invariants with pattern-matching over all agent outputs |
| **Nerve** | Event bus | Async event dispatch system with file system watching and subscriber-based routing |

### Key Features Implemented

#### Security
- Password hashing with bcrypt
- JWT-based authentication
- Environment-based configuration (secrets in .env)
- CORS middleware
- Non-root user in Docker containers

#### Scalability
- Modular architecture enabling horizontal scaling
- Database connection pooling
- Redis caching layer
- Docker containerization
- Kubernetes-ready deployment configs

#### MLOps Ready
- MLflow integration for experiment tracking
- Model versioning and registry
- Experiment tracking (status, metrics, parameters)
- Object storage for models and datasets
- Monitoring stack (Prometheus/Grafana)

#### Developer Experience
- Automatic API documentation (Swagger UI)
- Environment variable management
- Comprehensive error handling
- Test structure in place
- Code formatting and linting configurations
- Setup script for easy onboarding

---

## ML Pipeline

### Feature Store (`src/features/processor.py`)

The FeatureStore ensures consistent feature transformation between training and inference, eliminating one of the most common sources of ML bugs in production.

#### FeatureProcessor Class

A scikit-learn compatible transformer that ensures consistent feature transformation:

- **Automatic pipeline creation** based on data types (numeric vs categorical)
- **Missing value imputation**, scaling, and encoding
- **Save/load functionality** for persistence
- **Integration with MLflow** for experiment tracking
- **Custom transformers** for feature selection and polynomial features

#### Usage

```python
from src.features.processor import FeatureProcessor

# Initialize processor
processor = FeatureProcessor()

# Fit on training data
processor.fit(X_train)

# Transform training and test data
X_train_processed = processor.transform(X_train)
X_test_processed = processor.transform(X_test)

# Save for later use
processor.save("feature_processor.pkl")

# Load from file
processor = FeatureProcessor.load("feature_processor.pkl")
```

### Prediction Service (`src/api/prediction/`)

The PredictionService handles loading models from MLflow and making predictions with proper feature processing.

#### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/predict/` | POST | Make predictions with feature data |
| `/api/v1/predict/model-info` | GET | Get info about currently loaded model |
| `/api/v1/predict/reload-model` | POST | Reload model from MLflow |

#### Features

- Automatic loading of latest production model from MLflow
- Fallback to latest version if no production model exists
- Real-time prediction endpoint with feature input
- Probability output for classifiers (when available)
- Model info endpoint to check loaded model status
- Model reload capability (useful after promoting new models)
- Proper error handling and logging
- Singleton pattern for efficient model loading

#### Usage

```python
# Make a prediction
curl -X POST "http://localhost:8000/api/v1/predict/" \
  -H "Content-Type: application/json" \
  -d '{"feature1": 1.2, "feature2": -0.5, "feature3": 3.1, "feature4": 0.8}'

# Check model information
curl -X GET "http://localhost:8000/api/v1/predict/model-info"

# Reload model after new training
curl -X POST "http://localhost:8000/api/v1/predict/reload-model"
```

### Complete MLOps Lifecycle

1. **Data Processing** → `src/data/processor.py` (basic cleaning)
2. **Feature Store** → `src/features/processor.py` (centralized feature transformation logic)
3. **Model Training** → `src/ml/training.py` (creates, fits, and logs feature processors)
4. **Model Tracking** → MLflow server (experiments, models, AND feature processors)
5. **Model Serving** → `src/api/prediction/` (applies consistent feature transformations)
6. **API Access** → REST endpoints for predictions (with proper feature processing)
7. **Model Management** → `src/api/models/` (metadata tracking)
8. **Monitoring** → Available via existing docker-compose (Prometheus/Grafana)

---

## Code Review & Issues

> **Last Audit: 2026-09-10** — All 5 critical and 5 quality issues verified as **FIXED** in current source.

### Critical Security Issues 🔴 — ALL FIXED ✅

| ID | Issue | File | Status |
|----|-------|------|--------|
| CRIT-01 | Password reset token leaked in response | `src/api/auth/router.py:124` | ✅ Fixed |
| CRIT-02 | Deprecated `datetime.utcnow()` usage | `src/db/crud.py:114,121` | ✅ Fixed |
| CRIT-03 | Shell injection risk in agent tools | `src/agent/computer.py:89,97,125` | ✅ Fixed |
| CRIT-04 | Symlink path traversal | `src/agent/computer.py:54-68` | ✅ Fixed |
| CRIT-05 | Missing auth endpoint rate limiting | `src/api/auth/router.py:33-43` | ✅ Fixed |

#### CRIT-01: Password Reset Token Leaked in Response ✅

`request_password_reset` (router.py:124) now returns only `{"message": "If the email exists, a reset link has been sent"}`. The token is stored on the user record but never included in the response body.

#### CRIT-02: Deprecated `datetime.utcnow()` Usage ✅

All datetime calls now use `datetime.now(timezone.utc)`:
- `src/db/crud.py:114,121` — `datetime.now(timezone.utc)`
- `src/api/auth/router.py:116,140` — `datetime.now(timezone.utc)`

#### CRIT-03: Shell Injection Risk ✅

`run_shell` (computer.py:117-147) now uses `shell=False`, `shlex.split()`, and rejects metacharacters (`|`, `&`, `;`, `<`, `>`, backticks, `$`, `()`) via `_SHELL_METACHARS_RE`.

#### CRIT-04: Symlink Path Traversal ✅

`_resolve_scoped` (computer.py:48-69) checks every path component for symlinks and rejects them, then validates the resolved path stays within allowed roots.

#### CRIT-05: Missing Auth Endpoint Rate Limiting ✅

Rate limiting implemented via `_enforce_auth_rate_limit()` applied to `/token`, `/users/`, `/request-reset`, `/reset-password`. `RateLimiter` sliding-window class in `src/core/rate_limit.py`. `RateLimitMiddleware` for global API rate limiting. Configurable via `RATE_LIMIT_ENABLED` and `RATE_LIMIT_DEFAULT`.

---

### Code Quality Issues 🟡 — ALL FIXED ✅

| ID | Issue | File | Status |
|----|-------|------|--------|
| QUAL-01 | Inconsistent CRUD return types | `src/db/crud.py` | ✅ Fixed |
| QUAL-02 | f-strings in logging | `src/agent/orchestrator.py:32,53,57` | ✅ Fixed |
| QUAL-03 | Wrong pagination total count | `src/agent/tools.py:156,186,227` | ✅ Fixed |
| QUAL-04 | Missing database indexes | `src/db/models.py` | ✅ Fixed |
| QUAL-05 | Missing N+1 query prevention | `src/db/crud.py:28-35` | ✅ Fixed |

#### QUAL-01: Inconsistent CRUD Return Types ✅

All CRUD functions now have consistent `Optional[Model]` or `List[Model]` return types with explicit annotations.

#### QUAL-02: f-strings in Logging ✅

`orchestrator.py` logging calls now use lazy `%s` formatting (lines 32, 53, 57). No f-strings in logging calls.

#### QUAL-03: Wrong Pagination Total Count ✅

All list handlers in `tools.py` compute `total` with a separate `COUNT` query (lines 156, 186, 227).

#### QUAL-04: Missing Database Indexes ✅

All frequently queried columns now have `index=True` in models.py:
- **User:** id, email, username
- **Item:** id, title
- **ModelMetadata:** id, name
- **Experiment:** id, name, status
- **AuditLog:** id, tool_name
- **PredictionLog:** id, model_version, created_at
- **ScheduledJob:** id, name, tool_name
- **Dataset:** id, name, status

#### QUAL-05: Missing N+1 Query Prevention ✅

`get_user_with_items()` (crud.py:28-35) uses `joinedload(models.User.items)` to eagerly load related items.

---

### Technical Debt (from ISSUES.md) — 6 items OPEN ⏳

| # | Issue | Location | Status |
|---|-------|----------|--------|
| 1 | `ToolSynthesizer` uses templated prototype approach | `src/agent/forge/synthesizer.py` | ⏳ Open |
| 2 | Shell command blocklist is static/reactive | `src/agent/computer.py` | ⏳ Open |
| 3 | MCP Server passes `None` for authenticated user | `src/mcp_server.py:46` | ⏳ Open |
| 4 | No deep integration tests for MCP server lifecycle | `tests/test_mcp_server.py` | ⏳ Open |
| 5 | No tests for `analyze_screen` | `src/agent/eye/vision_bridge.py` | ⏳ Open |
| 6 | No fuzz testing for path resolution | `src/agent/computer.py` | ⏳ Open |
| 7 | Synthesized tool signatures need strict typing | `src/agent/forge/` | ⏳ Open |
| 8 | Forge documentation incomplete | `src/agent/forge/` | ⏳ Open |
| 9 | LSP warnings in `src/agent/` | Various | ⏳ Open |

---

## Test Infrastructure

> **Last Updated: 2026-09-10** — system_info fix verified, invariants.py removed.

### Test Files

| File | Description | Tests | Coverage |
|------|-------------|-------|----------|
| `tests/conftest.py` | Enhanced with async DB fixtures | N/A | N/A |
| `tests/test_sovereign_manager.py` | SovereignManager unit tests | 18 | 100% |
| `tests/test_aegis_verifier.py` | Aegis Verifier & Invariants tests | 44 (43 pass, 1 xfail) | 100% |
| `tests/test_forge.py` | ToolForge Manager & Synthesizer tests | 38 | 100% |
| `tests/test_prediction_service.py` | PredictionService unit tests | 23 | 88% |
| `tests/test_tools_integration.py` | Tools registry integration tests | 37 (29 pass, 8 error) | N/A |
| `tests/test_async_fixtures.py` | Async fixtures verification | 3 | N/A |

### Test Results Summary

| Test Suite | Pass | Fail | Error | Coverage |
|------------|------|------|-------|----------|
| `test_sovereign_manager.py` | 18 | 0 | 0 | 100% |
| `test_aegis_verifier.py` | 43 | 0 | 0 | 100% (1 xfail) |
| `test_forge.py` | 38 | 0 | 0 | 100% |
| `test_prediction_service.py` | 23 | 0 | 0 | 88% |
| `test_tools_integration.py` | 29 | 0 | 8 | N/A |
| `test_async_fixtures.py` | 3 | 0 | 0 | N/A |
| `test_auth.py` | 14 | 0 | 0 | N/A |
| `test_config.py` | 6 | 0 | 0 | N/A |
| `test_health.py` | 4 | 0 | 0 | N/A |
| `test_items.py` | 4 | 0 | 0 | N/A |

**Total**: 178 tests passing, 8 errors (all in REST integration tests)

### Remaining Test Issues

| # | Issue | Location | Status |
|---|-------|----------|--------|
| 1 | `system_info` handler used `engine.connect()` directly | `src/agent/tools.py:138` | ✅ Fixed — now uses `db: Session` and `db.execute()` |
| 2 | `invariants.py:41` — non-string `target_path` caused `AttributeError` | `src/agent/aegis/invariants.py:41` | ⚠️ Stale — `invariants.py` no longer exists as a separate file |
| 3 | Async fixtures conflict with sync tests | `tests/conftest.py` | ⏳ Open — in-memory SQLite creates separate DBs |

---

## Roadmap

### Priority 1 — Documentation Site (highest value)

The `mkdocs.yml` is configured but broken and empty:

- **Placeholder URLs** — `yourusername/KRYVARACODE`, `twitter.com/yourusername`, etc.
- **Typos that would crash the build:**
  - `inlinehightlight` → `inlinehighlight`
  - Duplicate `pymdownx.superfloats` entry
  - `tilde: true` indented at the wrong level
- **Nav references ~20 doc files that don't exist** — no `docs/` directory

**Tasks:**
1. Fix `mkdocs.yml` (real URLs, remove duplicates, fix typos)
2. Create `docs/` with real content seeded from summary files
3. Move loose root `.md` files into `docs/`

### Priority 2 — GitHub Pages Deployment

- New GitHub Action: build docs with mkdocs + publish to GitHub Pages
- README badge for the live docs site

### Priority 3 — Packaging (`pyproject.toml`)

Project is **not pip-installable** — no `pyproject.toml` exists.

**Tasks:**
- Add `pyproject.toml` with project metadata
- Dependencies from `requirements/base.txt`
- Build system configuration (hatchling or setuptools)
- Consolidate Ruff + mypy + pytest tool config

### Priority 4 — CHANGELOG.md

- Create `CHANGELOG.md` following Keep a Changelog format
- Entry for 0.1.0 — summarize history from git log

### Priority 5 — Release Automation

- GitHub Actions workflow triggered on tagged commits (`v*.*.*`)
- Auto-generate GitHub Release notes from CHANGELOG
- Build + publish Docker images tagged with the version

---

## Commands for Development

```bash
# Run all tests
pytest tests/ -v --cov=src --cov-report=term-missing

# Run specific test suite
pytest tests/test_sovereign_manager.py -v
pytest tests/test_aegis_verifier.py -v
pytest tests/test_forge.py -v
pytest tests/test_prediction_service.py -v
pytest tests/test_tools_integration.py -v

# Run with coverage gate
pytest tests/ --cov=src --cov-fail-under=80

# Run linters
ruff check src/ tests/
mypy src/
bandit -r src/

# Start API server
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Docker
docker compose up -d
docker compose --profile ml up -d
```

*Last Updated: 2026-09-10 — All 10 CRIT+QUAL issues verified fixed; 6 tech debt items open; test infra partially resolved*
