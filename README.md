<p align="center">
  <img src=".github/social-preview.png" alt="KRYVARACODE" width="640">
</p>

<p align="center">
  <strong>KRYVARACODE — AI prediction engine</strong><br>
  An autonomous AI system stack with self-synthesizing tools, adversarial swarm intelligence, and built-in safety enforcement.
</p>

<p align="center">
  <a href="https://github.com/HaydenAlberighi/KRYVARACODE/actions"><img alt="CI" src="https://github.com/HaydenAlberighi/KRYVARACODE/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-blue">
  <img alt="Version" src="https://img.shields.io/badge/version-1.0.0-brightgreen">
</p>

---

## Overview

KRYVARACODE is a self-evolving **autonomous AI system stack**. Instead of a single
agent answering questions, it runs a **swarm of specialized agents** — a Sovereign
that plans, a Forge that builds, an Eye that observes, an Aegis that enforces
safety, and a Nerve that keeps the whole system alive. Agents coordinate through
shared state, an event bus, and a task queue; they expose their capabilities over
a FastAPI backend, a CLI, and an **MCP (Model Context Protocol) server** so any
MCP-compatible client can drive the stack.

The system is designed to be adversarial by construction: the Sovereign's swarm
loop generates and critiques its own solutions, the Judge gates approvals, the
Forge sandboxes every execution, and the Aegis verifies code before it is ever
applied. **Self-evolution is recursive** — the SelfEvolver (`The Mirror`) analyzes
operational bottlenecks and proposes refactors that are themselves verified before
being applied.

## Architecture

```
                          ┌──────────────────────────────────────────────┐
                          │                 SOVEREIGN                   │
                          │   plan → swarm loop → judge → evolve        │
                          └───────┬──────────────┬──────────────┬───────┘
                                  │              │              │
                          ┌───────▼───────┐ ┌────▼─────┐ ┌──────▼────────┐
                          │     FORGE     │ │   EYE    │ │     AEGIS     │
                          │  build tools  │ │ observe  │ │  safety + QA  │
                          └───────┬───────┘ └────┬─────┘ └──────┬────────┘
                                  │              │              │
                          ┌───────▼──────────────▼──────────────▼───────┐
                          │                   NERVE                     │
                          │   coordination · event bus · task queue     │
                          └─────────────────────────────────────────────┘
```

| Agent | Role | Responsibilities |
|---|---|---|
| **Sovereign** | Planner | Runs the **adversarial swarm loop** — a Strategist designs a blueprint, an Executor implements it, a Critic analyzes the result and the loop repeats (up to 5 iterations) until it survives critique. The **SovereignJudge** then approves or rejects the outcome with a reasoning chain. The **SelfEvolver** monitors the audit log and proposes verified self-refactors. Backed by a recursive **memory graph**, a goal **pulse**, and an environment **simulator**. |
| **Forge** | Builder | A 5-stage tool factory — *Request → Spec → Synthesis → Verification → Registration*. Sandboxes every execution, maintains a capability registry, and performs network/protocol discovery. |
| **Eye** | Observer | Perception loop over the host via `psutil` (processes, system state) and OS interfaces, feeding observations back to the Sovereign. |
| **Aegis** | Safety | Enforces invariants, includes an **AegisVerifier** that statically verifies generated code before execution, a **Metabolic Governor** that throttles CPU/RAM/API cost, and a **Gatekeeper** that requires human approval for critical actions. |
| **Nerve** | Nervous system | Watchdog + event bus for agent-to-agent messaging, shared state, task queues, and global system health. |

The stack layers three coordination primitives under Nerve: a **message bus**
(async pub/sub), **shared state**, and a **task queue** (`src/agent/coordination/`),
driven by `orchestrator.py` and `optimizer.py`.

## Features

- **Adversarial swarm intelligence** — Strategist/Executor/Critic loop with judge-gated approvals
- **Recursive self-evolution** — the system proposes, verifies, and applies its own refactors
- **MCP server (SDK 2.x)** — every agent tool is automatically exposed as an MCP tool over stdio
- **RAG pipeline** — chunking, embedding, retrieval, and context augmentation (`src/features/rag/`)
- **Secure tool execution sandbox** — shell/filesystem tools restricted to allowed roots with destructive-pattern rejection
- **Full user auth** — JWT access + rotating refresh tokens, email verification, password reset, per-IP rate limiting
- **Async ML serving** — Celery task queue for training and prediction, MLflow model registry with promotion + drift checks
- **Observability by default** — Prometheus metrics, structured logging, request IDs, audit log, request-size limits, security headers (CSP/HSTS)
- **CLI + REST + MCP, one engine** — the same tool registry drives all three interfaces
- **Battle-tested CI** — ruff, mypy, bandit, 80% coverage gate, alembic migration verification, Python 3.12/3.13 matrix

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI · Pydantic v2 · Uvicorn |
| Data | SQLAlchemy 2.0 · Alembic · PostgreSQL 16 · Redis 7 |
| ML | scikit-learn · (optional) PyTorch / TensorFlow · MLflow · MinIO (S3) |
| Async | Celery + Redis broker |
| Agents | MCP Python SDK 2.x (`mcp>=2.0.0`) |
| Observability | Prometheus · Grafana · loguru |
| Tooling | Ruff · mypy · bandit · pre-commit · pytest · uv |

## Getting Started

### Prerequisites

- **Python 3.11+**
- **PostgreSQL 16** and **Redis 7** (or use Docker Compose)
- **Docker** with the Compose plugin (recommended for the full stack)

### Quick start (full stack with Docker)

```bash
# 1. Clone and enter the project
git clone https://github.com/HaydenAlberighi/KRYVARACODE.git
cd KRYVARACODE

# 2. Create the environment file with your secrets
cp .env.example .env
#   ...then edit .env: SECRET_KEY, JWT_SECRET_KEY, DATABASE_URL, REDIS_URL, ...

# 3. Start the 7-service stack (API, PostgreSQL, Redis, MLflow, MinIO, Prometheus, Grafana)
docker compose up -d

# 4. Optional: also start the ML worker (training/prediction jobs)
docker compose --profile ml up -d

# 5. Open the docs
#    Swagger UI:      http://localhost:8000/docs
#    Health check:    http://localhost:8000/health
#    MLflow:          http://localhost:5000
#    MinIO console:   http://localhost:9001
#    Grafana:         http://localhost:3000
```

### Run from source

```bash
# 2. (Python 3.11+)
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\Activate.ps1

# 3. Install dependencies (base = API runtime)
pip install -r requirements/base.txt

# 4. Environment
cp .env.example .env

# 5. Create the schema (SQLite/development convenience; production uses Alembic)
python -m src.cli init-db

# 6. Start the API
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
#    ...or via the CLI:
python -m src.cli serve --reload
```

> **Using uv?** The repo ships a `uv.lock` — `uv sync` will install the entire
> lockfile-managed environment for you.

### Configuration

All configuration is environment-driven via `.env`. The essential variables:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://user:password@localhost:5432/kryvaracode` | SQLAlchemy database URL (SQLite works for dev) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis/Celery broker URL |
| `SECRET_KEY` | — | App secret; use `secrets.token_urlsafe(48)` |
| `JWT_SECRET_KEY` | — | JWT signing secret (generate separately) |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `11520` | Access-token lifetime (days for user sessions) |
| `MLFLOW_TRACKING_URI` | `http://localhost:5000` | MLflow tracking server |
| `MINIO_ENDPOINT` | `localhost:9000` | S3-compatible object storage |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | `minioadmin` | MinIO credentials |
| `MINIO_BUCKET_MODELS` | `kryvara-models` | Model artifact bucket |
| `MINIO_BUCKET_DATA` | `kryvara-data` | Dataset bucket |
| `APP_ENV` | `development` | App environment (`development`/`test`/`production`) |
| `APP_DEBUG` | `true` | Enable uvicorn auto-reload in dev |
| `RATE_LIMIT_ENABLED` | `false` | Per-IP rate limiting |
| `RATE_LIMIT_DEFAULT` | `100/minute` | Default rate limit |
| `OPENAI_API_KEY` / `HUGGINGFACE_API_KEY` | — | Optional LLM/embedding providers |

Runtime versioning note: the app reports `PROJECT_VERSION` (default `0.1.0` in
`src/core/config.py`); the package version published in `pyproject.toml` is
**1.0.0**. Keep the two in sync if you expose the version via the API.

## Running the Stack

### 1 — The API (`:8000`)

```bash
uvicorn src.api.main:app --reload
# Swagger UI → http://localhost:8000/docs
```

Interactive docs are auto-generated from the OpenAPI schema, which is served at
`/api/v1/openapi.json`.

### 2 — The CLI

The full stack is scriptable from a terminal via `python -m src.cli`:

| Command | Description |
|---|---|
| `init-db` | Create all tables (dev convenience; prod uses Alembic) and print the schema |
| `create-user --email E --username U --password P` | Create a user (`--full-name`, `--superuser` optional) |
| `list-users [--limit N]` | List registered users |
| `upload-dataset --file F.csv [--name N] [--username U]` | Register a `.csv`/`.parquet`/`.json` file as a dataset |
| `list-datasets [--limit N]` | List registered datasets |
| `train --dataset-id N --target COL [--experiment NAME]` | Queue a Celery training job |
| `status` | Show version, environment, DB health, and row counts |
| `serve [--host H] [--port P] [--reload]` | Start the API server |
| `agent-tools` | List every registered agent tool |
| `agent-invoke NAME [--args-json '{"...": ...}']` | Invoke an agent tool directly |

### 3 — The MCP server

Every tool in the agent registry is exposed as an **MCP tool** via a stdio
server built on the MCP Python SDK 2.x:

```bash
python -m src.mcp_server
```

Point any MCP client (e.g. `claude mcp add`, or your client of choice) at this
stdio server to drive the KRYVARACODE agent directly — system info, datasets,
models, experiments, predictions, shell/filesystem access, scheduling, and
GitHub integration, all in OpenAI-function-calling-compatible schemas.

## API Reference

All endpoints are served under the `/api/v1` prefix (except `/` and `/health`).
Authenticated endpoints expect `Authorization: Bearer <access_token>` — obtain
one via `POST /api/v1/auth/token`.

| Method | Path | Description | Auth |
|---|---|---|---|
| `GET` | `/` | Welcome payload (message, version, docs link) | — |
| `GET` | `/health` | Service + database liveness (real DB round-trip; `503` if degraded) | — |
| `GET` | `/api/v1/metrics` | Prometheus metrics exposition | ✔ |

**Auth** (`/api/v1/auth`, per-IP rate limited):

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/token` | OAuth2 password flow → `{access_token, refresh_token}` |
| `POST` | `/auth/refresh` | Rotate a refresh token (old token revoked, new pair issued) |
| `POST` | `/auth/logout` | Revoke the current refresh token |
| `GET` | `/auth/users/me` | Current user profile |
| `POST` | `/auth/users/` | Register a new user |
| `POST` | `/auth/request-reset` | Request password reset (generic response regardless of existence) |
| `POST` | `/auth/reset-password` | Reset password with emailed token (reuse rejected) |
| `GET` | `/auth/me/verify` | Email verification status |
| `POST` | `/auth/verify-email` | Confirm an email address |

**Agent** (`/api/v1/agent`):

| Method | Path | Description |
|---|---|---|
| `GET` | `/agent/tools` | List agent tools in function-calling format (name/description/parameters) |
| `POST` | `/agent/tools/{name}/invoke` | Invoke a tool with `{arguments: {...}}` (Pydantic-validated) |

**Models** (`/api/v1/models`):

| Method | Path | Description |
|---|---|---|
| `POST` | `/models/` | Register model metadata |
| `GET` | `/models/` | List models (pagination) |
| `GET` | `/models/{model_id}` · `DELETE /models/{model_id}` | Fetch / remove a model |
| `GET` | `/models/{name}/{version}` | Fetch model by name + version |
| `GET` | `/models/{model_id}/download` | Download stub (serves from MinIO/S3 in production) |

**Prediction** (`/api/v1/predict`, Celery-backed):

| Method | Path | Description |
|---|---|---|
| `POST` | `/predict/` | Submit features → `{task_id, status:"pending"}` (async) |
| `GET` | `/predict/{task_id}` | Poll task result (prediction + probabilities) |
| `GET` | `/predict/model-info` | Currently deployed model metadata |
| `POST` | `/predict/reload-model` | Reload the deployed model from MLflow |
| `POST` | `/predict/train` | Queue a training job from a dataset |
| `POST` | `/predict/promote?version=` | Promote a model version to Production (rejected if metrics are inferior) |
| `GET` | `/predict/drift` | Feature-drift check against reference data |

**Data** (`/api/v1/data`):

| Method | Path | Description |
|---|---|---|
| `POST` | `/data/process` | Data-processing pipeline (currently a stub — returns queued) |
| `POST` | `/data/datasets` | Register a dataset (metadata) |
| `POST` | `/data/datasets/upload` | Upload `.csv`/`.parquet`/`.json` (max 50 MB, stored in `data/uploads/`) |
| `GET` | `/data/datasets` · `GET /data/datasets/{id}` | List / fetch datasets |
| `PATCH` | `/data/datasets/{id}` · `DELETE /data/datasets/{id}` | Update / remove a dataset |
| `GET` | `/data/datasets/{id}/download` | Storage-URI stub (S3-backed in production) |

**Experiments** (`/api/v1/experiments`): `POST` (create), `GET` (list),
`GET /{id}`, `PATCH /{id}` (status/metrics/parameters), `DELETE /{id}`.

**Items** (`/api/v1/items`): example user-owned CRUD resource — `POST` (create),
`GET` (list), `GET /{id}`, `DELETE /{id}`.

## Agent Tool Registry

The registry (`src/agent/tools.py`) is the single source of truth for agent
capabilities. It currently ships **24 core tools**, plus **4 GitHub tools** when
the `gh` CLI is authenticated, for **up to 28 tools** — all auto-exposed via
`POST /api/v1/agent/tools/{name}/invoke` and the MCP server:

| Category | Tools |
|---|---|
| System | `system_info`, `run_shell`, `process_list`, `process_kill` |
| Filesystem | `read_file`, `write_file`, `list_dir` |
| Datasets | `list_datasets`, `get_dataset`, `create_dataset` |
| Models | `list_models`, `get_model`, `get_model_by_name`, `register_model` |
| Experiments | `list_experiments`, `get_experiment`, `create_experiment` |
| Prediction / ML | `predict`, `train_model` |
| Scheduling | `create_scheduled_job`, `list_scheduled_jobs`, `run_scheduled_jobs`, `delete_scheduled_job` |
| Accounts | `account_status` |
| GitHub (if `gh` authed) | `github_repo_list`, `github_issue_list`, `github_issue_create`, `github_pr_list` |

Security model: shell and filesystem tools are constrained to allowed roots,
reject destructive patterns, refuse killing system/agent PIDs, and cap output;
filesystem writes stay inside the tool.

## RAG Pipeline

`src/features/rag/` provides a retrieval-augmented generation stack: a chunker
(splits source documents), an embedder, a retriever (vector search over chunks),
and an augmenter (builds context for LLM prompts). Covered by
`tests/test_rag_chunker.py` and `tests/test_rag_retriever.py`.

## Testing

**37 test files** cover the API, auth, agents, the swarm loop, the judge, the
Aegis verifier, the forge sandbox, RAG, coordination, MCP, scheduling, rate
limiting, security, metrics, and the convergence gauntlet.

```bash
# Lightweight suite (what CI runs — no torch/tensorflow/mlflow needed)
pip install -r requirements/test.txt
pytest

# Verbose, with coverage gate
pytest -v --cov=src --cov-report=term-missing
```

Every push and PR is gated by the CI pipeline on Python 3.12 and 3.13:

```
python -m compileall -q src tests   # syntax check
ruff check src/ tests/              # lint
mypy src/                           # type checks
bandit -r src/                      # security scan
pytest --cov-fail-under=80          # tests + ≥80% coverage
alembic upgrade head                # migrations must apply cleanly
```

### Migrations

Alembic manages the schema in `alembic/versions/` (initial schema, refresh
tokens, audit log + scheduled jobs). CI verifies `alembic upgrade head` against
a fresh database on every run.

## Security

- **`SECURITY.md`** — how to report vulnerabilities (disclosure policy)
- JWT auth with rotating refresh tokens; reset tokens stored only as SHA-256 digests
- Request-size limits (10 MB API, 50 MB uploads), per-IP rate limiting, security headers (CSP, HSTS, nosniff, frame denial)
- Sandboxed tool execution, static code verification before self-modification, human gatekeeper for critical actions
- `bandit` and Dependabot in CI; vulnerability alerts enabled on the repository

## Project Structure

```
KRYVARACODE/
├── src/
│   ├── agent/                  # Agent subsystem
│   │   ├── sovereign/          #   Swarm engine, judge, evolver, memory graph, pulse, simulator
│   │   ├── forge/              #   5-stage tool factory + sandbox + registry
│   │   ├── eye/                #   Perception loop, OS interface, vision bridge
│   │   ├── aegis/              #   Verifier, invariants, governor, gatekeeper
│   │   ├── nerve/              #   Event bus
│   │   ├── coordination/       #   Coordinator, message bus, shared state, task queue
│   │   └── tools.py            #   Tool registry (28 tools, all interfaces)
│   ├── api/                    # FastAPI app
│   │   ├── auth/               #   JWT auth, refresh rotation, password reset
│   │   ├── agent/              #   /agent tools endpoints
│   │   ├── models/             #   /models registry
│   │   ├── prediction/         #   /predict Celery tasks + lifecycle + monitoring
│   │   ├── data/               #   /data datasets + upload + processing
│   │   ├── experiments/        #   /experiments CRUD
│   │   └── items/              #   /items example CRUD
│   ├── cli/                    # `python -m src.cli` — 10 commands
│   ├── core/                   # Config, security, exceptions, logging, metrics, rate limiting
│   ├── db/                     # SQLAlchemy models, CRUD, session
│   ├── features/               # Processor + RAG (chunker, embedder, retriever, augmenter)
│   ├── ml/                     # Training + monitoring
│   ├── schemas/                # Pydantic v2 schemas
│   ├── tasks/                  # Celery tasks (prediction, lifecycle)
│   ├── utils/                  # Helpers
│   └── mcp_server.py           # MCP (SDK 2.x) stdio server
├── tests/                      # 37 test files (incl. src/tests/omega_gauntlet/)
├── deployments/
│   ├── docker/                 #   Dockerfile.api, Dockerfile.ml-worker
│   ├── k8s/                    #   ConfigMap, Secret, Deployment, Service
│   └── prometheus/             #   Scrape config
├── alembic/                    # Migrations (initial, refresh tokens, audit+scheduled jobs)
├── requirements/               # base, dev, ml, test
├── .github/workflows/ci.yml    # Test matrix (3.12/3.13) + Docker build/push
└── pyproject.toml              # v1.0.0 · ruff/mypy config
```

## Deployment

### Docker Compose (recommended)

Seven services orchestrated by `docker-compose.yml` + an optional ML worker:

| Service | Image | Port(s) |
|---|---|---|
| API | local build (`Dockerfile.api`) | `8000` |
| PostgreSQL | `postgres:16-alpine` | `5432` |
| Redis | `redis:7-alpine` | `6379` |
| MLflow | `ghcr.io/mlflow/mlflow:v2.19.0` | `5000` |
| MinIO | `minio/minio:latest` | `9000` / `9001` (console) |
| Prometheus | `prom/prometheus:v2.54.1` | `9090` |
| Grafana | `grafana/grafana:11.1.4` | `3000` |
| **ML worker** *(profile `ml`)* | local build (`Dockerfile.ml-worker`) | — |

The API container mounts `./data`, `./models`, and `./logs`; persistent volumes
exist for Postgres, MinIO, Prometheus, and Grafana. The ML worker is optional —
start it with `docker compose --profile ml up -d`.

### Kubernetes

Apply the manifests in order:

```bash
kubectl apply -f deployments/k8s/
# 00-configmap.yaml → 01-secret.example.yaml (fill your secrets) → 02-deployment.yaml → 03-service.yaml
```

Copy `01-secret.example.yaml` to a real secret manifest and populate it from your
`.env` before deploying.

### CI/CD

`ci.yml` runs the full quality gate on every push/PR (`develop` and `main`,
Python 3.12 + 3.13 matrix). On pushes to `main` it also builds and pushes the
API image to `ghcr.io/HaydenAlberighi/KRYVARACODE`.

## Contributing

Contributions are welcome. Please read:

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — workflow, branch guidance, and tooling
- **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** — community standards
- **[SECURITY.md](SECURITY.md)** — vulnerability reporting

Every contribution is verified by the CI gate described above (lint, types,
security, ≥80% coverage, migrations). Feature ideas can also be pitched in the
[discussions](https://github.com/HaydenAlberighi/KRYVARACODE/discussions) using
the Ideas category.

## License

Released under the [MIT License](LICENSE).