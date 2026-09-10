# KRYVARACODE

**An autonomous AI system stack with self-synthesizing tools, adversarial swarm intelligence, and built-in safety enforcement.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.1.0-green.svg)](https://github.com/HaydenAlberighi/KRYVARACODE)

---

KRYVARACODE is not another ML framework wrapper. It is a 5-agent autonomous system that pursues goals through adversarial debate, synthesizes its own tools at runtime, and enforces safety invariants against every action it takes. The system observes its environment, reasons about objectives, and executes — all while a dedicated safety layer blocks destructive operations before they happen.

## Architecture

The system is built around five interconnected agents, each with a distinct responsibility:

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
| **Sovereign** | Goal pursuit | Orchestrates autonomous task execution through an adversarial swarm loop. A Strategist proposes plans, an Executor implements them, and a Critic evaluates the result — iterating up to 5 rounds until a final Judge renders a verdict. A Pulse engine triggers goals autonomously based on system state. |
| **Forge** | Tool synthesis | Builds new capabilities on demand through a 5-stage pipeline: Request, Specification, Synthesis, Verification, Registration. Synthesized tools are validated against safety invariants before registration. |
| **Eye** | Perception | Captures screenshots, monitors running processes via `psutil`, and bridges environmental data into the event system for other agents to consume. |
| **Aegis** | Safety | Enforces behavioral invariants with pattern-matching over all agent outputs. Blocks recursive deletes, system file access, arbitrary shell commands, and unauthorized network operations. A Metabolic Governor throttles CPU, RAM, and API cost. CRITICAL violations require human approval via the Gatekeeper. |
| **Nerve** | Event bus | Async event dispatch system with file system watching (via `watchdog`) and subscriber-based routing. Connects all agents through a shared event stream. |

## Features

- **Adversarial Swarm Intelligence** — Tasks are solved through structured debate between three specialized roles, not single-pass generation
- **Autonomous Tool Synthesis** — The Forge agent creates, verifies, and registers new tools at runtime based on task requirements
- **Safety-First Design** — Aegis scans all agent outputs against forbidden patterns with risk-level classification (CRITICAL/HIGH/MEDIUM/LOW)
- **Metabolic Governance** — Real-time CPU, memory, and API cost monitoring with automatic throttling
- **MCP Protocol Support** — All 24+ tools are exposed over the Model Context Protocol for LLM integration
- **Multi-Surface API** — Same tool registry serves HTTP API, MCP server, and CLI interfaces
- **Recursive Memory** — Sovereign's memory graph commits lessons from completed tasks for future reference
- **Observability Stack** — Prometheus metrics, Grafana dashboards, structured logging with Loguru

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Web Framework | FastAPI + Uvicorn |
| Validation | Pydantic v2 |
| ORM | SQLAlchemy 2.0 (Mapped style) |
| Database | PostgreSQL 16, Redis 7 |
| Object Storage | MinIO (S3-compatible) |
| Experiment Tracking | MLflow v2.19 |
| ML Frameworks | scikit-learn, PyTorch, TensorFlow |
| Task Queue | Celery |
| Monitoring | Prometheus + Grafana |
| Authentication | JWT (python-jose + bcrypt) |
| Protocol | MCP SDK 2.x |
| Containerization | Docker, Docker Compose |
| Orchestration | Kubernetes |
| Async | asyncio, asyncpg, aiosqlite |

## Getting Started

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 16
- Redis 7
- Docker and Docker Compose (for containerized deployment)

### Installation

```bash
git clone https://github.com/HaydenAlberighi/KRYVARACODE.git
cd KRYVARACODE

python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements/base.txt
```

### Configuration

```bash
cp .env.example .env
```

Edit `.env` with your configuration. Key variables:

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:password@localhost:5432/kryvaracode` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | Application secret | Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_SECRET_KEY` | JWT signing key | Generate similarly |
| `MLFLOW_TRACKING_URI` | MLflow server | `http://localhost:5000` |
| `MINIO_ENDPOINT` | MinIO object storage | `localhost:9000` |

### Launch with Docker Compose

```bash
docker compose up -d
```

This starts 7 services:

| Service | Port | Description |
|---------|------|-------------|
| API | 8000 | FastAPI application server |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Caching and task queue |
| MLflow | 5000 | Experiment tracking UI |
| MinIO | 9000/9001 | Object storage (models, data) |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3000 | Metrics visualization |

For the ML worker (training tasks):

```bash
docker compose --profile ml up -d
```

### Launch without Docker

```bash
# Start the API server
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Reference

The API is versioned under `/api/v1` and includes:

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Health check with database round-trip |
| `POST /api/v1/auth/register` | User registration |
| `POST /api/v1/auth/login` | JWT token issuance |
| `GET /api/v1/models` | List registered ML models |
| `POST /api/v1/predict` | Run model predictions |
| `POST /api/v1/data` | Dataset management |
| `POST /api/v1/experiments` | Experiment tracking |
| `GET /api/v1/agent` | Agent tool execution |
| `GET /api/v1/metrics` | Prometheus metrics |

Full API documentation is available at `/docs` when the server is running (Swagger UI).

## Agent Tools

The system exposes 24+ tools through a unified registry. Each tool has Pydantic validation, audit logging, and timed execution.

| Category | Tools |
|----------|-------|
| Data | `list_datasets`, `get_dataset`, `create_dataset` |
| Models | `list_models`, `get_model`, `get_model_by_name`, `register_model` |
| Experiments | `list_experiments`, `get_experiment`, `create_experiment` |
| Prediction | `predict` |
| ML Training | `train_model` |
| System | `system_info`, `process_list`, `process_kill` |
| File System | `read_file`, `write_file`, `list_dir`, `run_shell` |
| Scheduling | `create_scheduled_job`, `list_scheduled_jobs`, `run_scheduled_job`, `delete_scheduled_job` |
| GitHub | `github_repo_list`, `github_issue_list`, `github_issue_create`, `github_pr_list` |
| Account | `account_status` |

## Testing

```bash
# Run the full test suite
pytest

# Run with verbose output
pytest -v

# Run specific test categories
pytest tests/test_aegis_hardening.py    # Safety system tests
pytest tests/test_sovereign_manager.py  # Agent orchestration tests
pytest tests/test_forge.py              # Tool synthesis tests
```

The test suite covers agent behavior, API endpoints, database operations, tool execution, safety invariants, and integration scenarios.

## Project Structure

```
KRYVARACODE/
├── src/
│   ├── agent/                  # Autonomous agent system
│   │   ├── sovereign/          # Goal pursuit & swarm engine
│   │   ├── forge/              # Tool synthesis pipeline
│   │   ├── eye/                # Visual perception
│   │   ├── aegis/              # Safety enforcement
│   │   ├── nerve/              # Event bus
│   │   ├── tools.py            # Unified tool registry (24+ tools)
│   │   ├── accounts.py         # GitHub/account integrations
│   │   ├── computer.py         # System-level operations
│   │   └── scheduler.py        # Scheduled job management
│   ├── api/                    # FastAPI application
│   │   ├── auth/               # JWT authentication
│   │   ├── models/             # Model management endpoints
│   │   ├── data/               # Dataset endpoints
│   │   ├── prediction/         # Prediction service
│   │   ├── experiments/        # Experiment tracking
│   │   └── agent/              # Agent tool execution
│   ├── core/                   # Configuration, exceptions, logging
│   ├── db/                     # SQLAlchemy models & CRUD
│   ├── ml/                     # Training pipeline & monitoring
│   ├── schemas/                # Pydantic v2 models
│   └── mcp_server.py           # MCP protocol server
├── deployments/
│   ├── docker/                 # Dockerfiles (API, ML worker)
│   ├── k8s/                    # Kubernetes manifests
│   └── prometheus/             # Prometheus configuration
├── requirements/
│   ├── base.txt                # API service dependencies
│   └── ml.txt                  # ML training dependencies
├── tests/                      # Test suite (26 test files)
├── docker-compose.yml          # 7-service stack
├── pytest.ini                  # Test configuration
├── mkdocs.yml                  # Documentation site config
└── .env.example                # Environment variable template
```

## Deployment

### Docker

```bash
docker compose up -d --build
```

### Kubernetes

```bash
kubectl apply -f deployments/k8s/configmap.yaml
kubectl apply -f deployments/k8s/secret.yaml
kubectl apply -f deployments/k8s/deployment.yaml
kubectl apply -f deployments/k8s/service.yaml
```

### ML Training Worker

The ML worker runs as a separate container with GPU/CPU-optimized dependencies:

```bash
docker compose --profile ml up -d ml-worker
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

All contributions should include tests for new functionality and follow the existing code patterns.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
