# KRYVARACODE — Parallel Task Board

> **Purpose**: Each task below is fully self-contained. Open a separate OpenCode chat, paste the task, and let it run independently.
>
> **Rules**:
> - Do NOT touch files outside your task's scope
> - Do NOT modify existing test files — create new ones if needed
> - Every change must pass `ruff check` and `pytest` on your changed files
> - Reference `PROJECT_DOCUMENTATION.md` for project context
>
> **Status Key**: ⬜ Not started | 🔄 In progress | ✅ Done

---

## Task 1: CRIT-6 — Fix SQL Injection Patterns 🔴

**Status**: ⬜
**Priority**: CRITICAL
**Estimated Effort**: 30 min
**Files to modify**:
- `src/agent/tools.py` (line 138)
- `src/api/main.py` (line 155)
- `src/cli/main.py` (line 192)

**Problem**: Three locations use raw SQL strings via `db.execute(sql_text("SELECT 1"))`. While these specific queries are benign, the pattern is dangerous — future changes could introduce injection vectors.

**What to do**:

1. **`src/agent/tools.py:138`** — The `system_info` tool uses `db.execute(sql_text("SELECT 1"))` for connection health check.
   - Replace with `db.execute(text("SELECT 1"))` (SQLAlchemy 2.0 style)
   - Better: use `db.connection()` or `db.get_bind().connect()` for health checks

2. **`src/api/main.py:155`** — Health check endpoint uses raw SQL.
   - Replace with `db.execute(text("SELECT 1"))` or use `db.get_bind().connect().execute(text("SELECT 1"))`
   - Wrap in try/except for proper health status

3. **`src/cli/main.py:192`** — CLI database check uses raw SQL.
   - Same fix as above

4. **Create a helper** in `src/db/database.py`:
   ```python
   def check_db_connection(db: Session) -> bool:
       """Safe database connection health check."""
       try:
           db.execute(text("SELECT 1"))
           return True
       except Exception:
           return False
   ```

5. **Replace all three** call sites with `check_db_connection(db)`

**MUST NOT**:
- Change any other functionality in these files
- Modify the tool handler logic in tools.py beyond the health check
- Touch auth, prediction, or any other module

**Success criteria**:
- `ruff check src/agent/tools.py src/api/main.py src/cli/main.py src/db/database.py` — zero errors
- `pytest tests/test_tools_integration.py -k system_info` — passes
- No raw `sql_text(` or `text(` calls outside of the helper function

---

## Task 2: CRIT-7 — Harden Sandbox Code Execution 🔴

**Status**: ⬜
**Priority**: CRITICAL
**Estimated Effort**: 45 min
**Files to modify**:
- `src/agent/sandbox.py` (line 117)

**Problem**: `sandbox.py:117` uses f-string interpolation to inject `args` dict into generated wrapper code. The sandbox uses subprocess isolation only (no Docker/Podman), so a malicious tool could escape.

**What to do**:

1. **Read `src/agent/sandbox.py`** — understand the full sandbox architecture

2. **Fix the code injection at line 117**:
   - The f-string pattern `f"...{args}..."` is vulnerable because `args` values are attacker-controlled
   - Replace with `json.dumps(args)` for serialization, never string interpolation
   - Use `ast.literal_eval()` for deserialization on the other side

3. **Add input sanitization** to the wrapper code generator:
   - Validate that generated Python code doesn't contain `__import__`, `exec`, `eval`, `compile`, `getattr`, `setattr`, `delattr`, `globals`, `locals`, `dir`, `vars`
   - Add an allowlist of safe builtins for the sandboxed environment

4. **Document the sandbox security model** in a docstring:
   - What it protects against
   - Known limitations (subprocess-only, no container isolation)
   - Recommendations for production (add Docker/Podman)

**MUST NOT**:
- Add Docker/Podman dependencies (out of scope)
- Modify the tool registry or any other agent module
- Change the sandbox's public API (keep `run_sandboxed` signature)

**Success criteria**:
- `ruff check src/agent/sandbox.py` — zero errors
- `pytest tests/test_forge.py -v` — all pass (synthesizer tests exercise sandbox)
- `grep -n "f\".*{args" src/agent/sandbox.py` — no matches (no f-string injection)

---

## Task 3: Security Headers + CORS Hardening + CSRF + Request Limits 🟡

**Status**: ⬜
**Priority**: HIGH
**Estimated Effort**: 40 min
**Files to modify**:
- `src/api/main.py` (lines 116-186 only)

**Problem**: The FastAPI app is missing security headers, has overly permissive CORS, no CSRF protection, no request size limits, and exposes `/metrics` without auth.

**What to do**:

1. **Add security headers middleware** (after CORS middleware, line ~138):
   ```python
   @app.middleware("http")
   async def security_headers(request, call_next):
       response = await call_next(request)
       response.headers["X-Content-Type-Options"] = "nosniff"
       response.headers["X-Frame-Options"] = "DENY"
       response.headers["X-XSS-Protection"] = "1; mode=block"
       response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
       response.headers["Content-Security-Policy"] = "default-src 'self'"
       response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
       return response
   ```

2. **Restrict CORS** (line 129-135):
   - Change `allow_methods=["*"]` → `allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"]`
   - Change `allow_headers=["*"]` → `allow_headers=["Authorization", "Content-Type"]`
   - Add `max_age=600`

3. **Add request size limits middleware**:
   - Add middleware that rejects requests > 10MB body
   - Return 413 Payload Too Large

4. **Protect `/metrics` endpoint** (line 173-186):
   - Add authentication dependency (require valid JWT)
   - Or move to a separate port/path that's only accessible internally

5. **Add CORS origins from environment**:
   - Read allowed origins from `CORS_ORIGINS` env var (comma-separated)
   - Default to `["http://localhost:3000"]` in development

**MUST NOT**:
- Change any endpoint logic, route handlers, or business logic
- Modify database models or CRUD operations
- Touch authentication module (auth/router.py, security.py)
- Remove any existing endpoints

**Success criteria**:
- `ruff check src/api/main.py` — zero errors
- `curl -I http://localhost:8000/health` — shows security headers
- `pytest tests/test_health.py -v` — passes
- `pytest tests/test_auth.py -v` — passes (CORS doesn't break auth)

---

## Task 4: JWT Overhaul — RS256 + Refresh Tokens 🟡

**Status**: ⬜
**Priority**: HIGH
**Estimated Effort**: 60 min
**Files to modify**:
- `src/core/security.py` (lines 102-130)
- `src/core/config.py` (lines 49-50)
- `src/api/auth/router.py` (lines 94-124)

**Problem**: JWT uses HS256 (symmetric/shared secret) instead of RS256 (asymmetric/private key). No refresh token implementation — users must re-authenticate when access token expires.

**What to do**:

1. **Generate RSA key pair**:
   - Add `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY` to config (can be loaded from env or file)
   - Generate keys with `openssl genrsa -out private.pem 2048` and `openssl rsa -in private.pem -pubout -out public.pem`
   - For dev: auto-generate and cache keys in `.secrets/`

2. **Update `src/core/config.py`**:
   - Add `JWT_PRIVATE_KEY_PATH: str = ".secrets/private.pem"`
   - Add `JWT_PUBLIC_KEY_PATH: str = ".secrets/public.pem"`
   - Add `JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15`
   - Add `JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7`

3. **Update `src/core/security.py`**:
   - Change `create_access_token()` to use RS256 with private key
   - Add `create_refresh_token()` function
   - Add `verify_refresh_token()` function
   - Change `decode_access_token()` to use public key

4. **Update `src/api/auth/router.py`**:
   - Add `/refresh` endpoint that accepts refresh token, returns new access token
   - Store refresh tokens in DB (add `refresh_token` column to User model or separate table)
   - Add `/logout` endpoint that invalidates refresh token

5. **Add migration** for refresh token storage:
   - Create `alembic/versions/xxxx_add_refresh_tokens.py` (or document the migration)

**MUST NOT**:
- Remove existing `/token` endpoint behavior
- Change password hashing (bcrypt is fine)
- Modify CORS or security headers (Task 3 handles that)
- Touch any non-auth files

**Success criteria**:
- `ruff check src/core/security.py src/core/config.py src/api/auth/router.py` — zero errors
- `pytest tests/test_auth.py -v` — all pass
- `grep -n "HS256" src/core/security.py` — no matches
- `grep -n "RS256" src/core/security.py` — at least one match
- New `/refresh` endpoint documented in OpenAPI

---

## Task 5: SSRF Blocklist + File Upload + Password Security 🟡

**Status**: ⬜
**Priority**: HIGH
**Estimated Effort**: 40 min
**Files to modify**:
- `src/agent/aegis/invariants.py` (lines 78-82)
- `src/api/data/router.py` (lines 89-102)
- `src/db/models.py` (lines 35, 44-46)
- `src/db/crud.py` (lines 150-152)

**Problem**: SSRF blocklist is incomplete (only blocks localhost), file upload filenames are untrusted, password reset tokens are stored in plaintext, and there's no password reuse prevention.

**What to do**:

1. **Expand SSRF blocklist** (`src/agent/aegis/invariants.py:78-82`):
   ```python
   BLOCKED_IP_RANGES = [
       "127.0.0.0/8",      # Loopback
       "10.0.0.0/8",        # RFC1918
       "172.16.0.0/12",     # RFC1918
       "192.168.0.0/16",    # RFC1918
       "169.254.0.0/16",    # AWS metadata, link-local
       "::1/128",           # IPv6 loopback
       "fc00::/7",          # IPv6 ULA
       "fe80::/10",         # IPv6 link-local
   ]
   ```
   - Use `ipaddress.ip_address()` and `ipaddress.ip_network()` for proper CIDR matching

2. **Sanitize file upload filenames** (`src/api/data/router.py:89-102`):
   ```python
   import uuid
   from werkzeug.utils import secure_filename

   safe_name = secure_filename(upload.filename)
   unique_name = f"{uuid.uuid4().hex}_{safe_name}"
   ```
   - Or use UUID-only naming: `f"{uuid.uuid4()}{Path(upload.filename).suffix}"`

3. **Encrypt password reset tokens** (`src/db/models.py:44-46`):
   - Add `hashed_reset_token` column (store SHA-256 hash, not plaintext)
   - Keep original token only in memory during the request
   - Add migration to drop old `reset_token` column and add `hashed_reset_token`

4. **Add password reuse prevention** (`src/db/crud.py:150-152`):
   - When changing password, check that new password hash doesn't match any of the last N hashes
   - Add `password_history` table or add `previous_password_hash` column to User model
   - Minimum: check against current `password_hash` (prevent reusing same password)

**MUST NOT**:
- Change the User model's public API (keep existing columns)
- Modify authentication flow (login, token generation)
- Touch any agent files (tools.py, computer.py, orchestrator.py)

**Success criteria**:
- `ruff check src/agent/aegis/invariants.py src/api/data/router.py src/db/models.py src/db/crud.py` — zero errors
- `pytest tests/test_aegis_verifier.py -v` — all pass
- `pytest tests/test_tools_integration.py -v` — no new failures
- SSRF blocklist covers all RFC1918 + link-local ranges

---

## Task 6: Code Quality Cleanup — Imports, Exceptions, Type Hints 🟡

**Status**: ⬜
**Priority**: MEDIUM
**Estimated Effort**: 45 min
**Files to modify**:
- `src/features/processor.py` (line 73)
- `src/agent/tools.py` (line 512)
- `src/api/prediction/service.py` (lines 84, 196)
- `src/cli/main.py` (line 193)
- 8 files with unused imports (see list below)

**Problem**: Bare `except:` clauses, silent exception swallowing, unused imports across the codebase.

**What to do**:

1. **Fix bare `except:`** in `src/features/processor.py:73`:
   - Change to `except Exception as e:` and add logging
   - If the exception is expected, document why it's caught

2. **Fix silent pass** in `src/agent/tools.py:512`:
   - The audit logging swallows exceptions silently
   - Add `logger.warning("Audit logging failed: %s", e)` or similar

3. **Fix silent exceptions** in `src/api/prediction/service.py:84,196`:
   - Add logging for caught exceptions
   - At minimum: `logger.debug("Prediction fallback: %s", e)`

4. **Remove unused imports** (run `ruff check --fix src/` first, then verify manually):
   - `src/agent/tools.py:71` — `src.db.database.engine`
   - `src/agent/aegis/gatekeeper.py:10` — `typing.List`
   - `src/agent/aegis/invariants.py:8` — `typing.Dict`
   - `src/agent/sovereign/judge.py:4` — `src.agent.orchestrator.event_evaluator`
   - `src/agent/sovereign/memory_graph.py:11` — `datetime.timezone`
   - `src/api/deps.py:19` — `typing.AsyncGenerator`
   - `src/tasks/prediction.py:6` — `src.schemas.model.ModelCreate`

5. **Verify** no F401 (unused import) errors remain: `ruff check src/ --select F401`

**MUST NOT**:
- Change function signatures or return types
- Modify business logic in any handler
- Touch config, auth, or database models
- Split god modules (tools.py, crud.py) — that's a separate task

**Success criteria**:
- `ruff check src/ --select F401` — zero errors (or only F401 suppressions with comments)
- `ruff check src/features/processor.py src/agent/tools.py src/api/prediction/service.py` — zero errors
- `grep -rn "except:" src/ --include="*.py"` — no bare excepts remain
- `grep -rn "except Exception:" src/ --include="*.py"` — only ones with logging

---

## Task 7: Data Protection — Audit Logging + Input Validation + datetime Regression 🟡

**Status**: ⬜
**Priority**: MEDIUM
**Estimated Effort**: 40 min
**Files to modify**:
- `src/db/models.py` (lines 138-140 — AuditLog model)
- `src/agent/tools.py` (line 500 — audit log write)
- `src/api/data/router.py` (lines 82-111 — missing validation)
- `src/api/auth/router.py` (lines 94-124 — missing validation)
- `src/tasks/lifecycle.py` (lines 30, 53 — datetime.utcnow() regression)

**Problem**: Audit log stores tool arguments in plaintext (potential data leak), API endpoints lack input validation, and `datetime.utcnow()` was reintroduced in lifecycle.py.

**What to do**:

1. **Sanitize audit log arguments** (`src/agent/tools.py:500`):
   - Before storing `args` in AuditLog, redact sensitive fields:
     ```python
     SENSITIVE_KEYS = {"password", "token", "secret", "api_key", "authorization"}
     sanitized = {k: "***" if k.lower() in SENSITIVE_KEYS else v for k, v in args.items()}
     ```
   - Or encrypt the args field using Fernet symmetric encryption

2. **Add input validation** to API endpoints:
   - `src/api/data/router.py:82-111` — validate file type, size, required fields
   - `src/api/auth/router.py:94-124` — validate email format, password strength, username length
   - Use Pydantic models for request validation (create schemas in `src/schemas/`)

3. **Fix datetime.utcnow() regression** (`src/tasks/lifecycle.py:30,53`):
   - Replace `datetime.utcnow()` → `datetime.now(timezone.utc)`
   - Add `from datetime import timezone` import
   - Search entire codebase: `grep -rn "utcnow()" src/`

4. **Add API versioning** (optional enhancement):
   - Add `/api/v1/` prefix to all endpoints if not present
   - Add deprecation headers for old endpoints

**MUST NOT**:
- Change the AuditLog table schema (columns, types) — only change what's stored in the args field
- Modify authentication flow (login, token generation)
- Touch security.py, config.py, or main.py (other tasks handle those)

**Success criteria**:
- `ruff check src/db/models.py src/agent/tools.py src/api/data/router.py src/api/auth/router.py src/tasks/lifecycle.py` — zero errors
- `grep -rn "utcnow()" src/` — zero matches
- `pytest tests/test_tools_integration.py -v` — passes
- Audit log args field no longer contains plaintext secrets

---

## Task 8: NVIDIA Blueprint — Enterprise RAG Pipeline Integration 🟢

**Status**: ⬜
**Priority**: FEATURE (Medium value)
**Estimated Effort**: 90 min
**Reference**: https://github.com/NVIDIA-AI-Blueprints/rag (757 stars)
**Files to create/modify**:
- Create `src/features/rag/` (new module)
- Modify `src/api/prediction/service.py` (add RAG context)

**Problem**: The prediction service has no retrieval-augmented generation capability. Adding RAG would let predictions incorporate relevant context from a knowledge base.

**What to do**:

1. **Study the NVIDIA RAG blueprint**:
   - Clone or fetch: `https://github.com/NVIDIA-AI-Blueprints/rag`
   - Study the chunking, embedding, and retrieval patterns
   - Focus on: NeMo Retriever integration, chunking strategies, vector store setup

2. **Create RAG module** (`src/features/rag/`):
   ```
   src/features/rag/
   ├── __init__.py
   ├── chunker.py      # Text chunking (fixed-size, semantic, recursive)
   ├── embedder.py     # Embedding generation (sentence-transformers or API)
   ├── retriever.py    # Vector similarity search
   └── augmenter.py    # Context injection into prompts
   ```

3. **Implement chunker.py**:
   - Support fixed-size, sentence-based, and recursive chunking
   - Configurable chunk_size and chunk_overlap
   - Metadata preservation (source, page, section)

4. **Implement retriever.py**:
   - Use FAISS or ChromaDB for local vector storage
   - Support similarity search with configurable top_k
   - Add MMR (Maximal Marginal Relevance) for diversity

5. **Integrate with prediction service**:
   - Add optional `context` parameter to prediction requests
   - When context is provided, retrieve relevant chunks and inject into prediction
   - Keep backward compatibility (existing predictions work without context)

6. **Add tests**:
   - `tests/test_rag_chunker.py` — test chunking strategies
   - `tests/test_rag_retriever.py` — test retrieval accuracy

**MUST NOT**:
- Break existing prediction API (backward compatible)
- Add heavy dependencies (keep under 100MB additional)
- Modify database models or auth system
- Touch the agent system (sovereign, forge, eye, aegis, nerve)

**Success criteria**:
- `ruff check src/features/rag/` — zero errors
- `pytest tests/test_rag_*.py -v` — all pass
- `pytest tests/test_prediction_service.py -v` — existing tests still pass
- RAG module can chunk text, embed it, and retrieve similar chunks

---

## Task 9: NVIDIA Blueprint — Multi-Agent Orchestration Upgrade 🟢

**Status**: ⬜
**Priority**: FEATURE (Medium value)
**Estimated Effort**: 90 min
**Reference**: https://github.com/NVIDIA-AI-Blueprints/Multi-Agent-Intelligent-Warehouse (125 stars)
**Files to modify**:
- `src/agent/orchestrator.py` (currently 61 lines)
- Create `src/agent/coordination/` (new module)

**Problem**: The orchestrator is minimal (61 lines). The NVIDIA Multi-Agent Warehouse blueprint has proper agent-to-agent communication, task delegation, shared state, and MCP integration patterns.

**What to do**:

1. **Study the NVIDIA Multi-Agent Warehouse blueprint**:
   - Clone or fetch: `https://github.com/NVIDIA-AI-Blueprints/Multi-Agent-Intelligent-Warehouse`
   - Focus on: agent coordination patterns, shared state management, task queuing

2. **Create coordination module** (`src/agent/coordination/`):
   ```
   src/agent/coordination/
   ├── __init__.py
   ├── message_bus.py    # Inter-agent message passing
   ├── task_queue.py     # Priority task queue with dependencies
   ├── shared_state.py   # Thread-safe shared state container
   └── coordinator.py    # Agent lifecycle management
   ```

3. **Implement message_bus.py**:
   - Publish/subscribe pattern for agent communication
   - Support broadcast and targeted messages
   - Message history for debugging

4. **Implement task_queue.py**:
   - Priority queue with dependency resolution
   - Task status tracking (pending, running, completed, failed)
   - Timeout and retry support

5. **Implement shared_state.py**:
   - Thread-safe key-value store
   - Support for nested state (agent-specific sub-states)
   - Change notifications for reactive agents

6. **Upgrade orchestrator.py**:
   - Replace current minimal implementation with coordinator-based approach
   - Add agent lifecycle management (start, stop, health check)
   - Add task distribution and result aggregation
   - Keep backward compatibility with existing tool handlers

7. **Add tests**:
   - `tests/test_coordination.py` — test message bus, task queue, shared state

**MUST NOT**:
- Change the tool handler API (tools.py must remain compatible)
- Modify the agent subsystems (forge, eye, aegis, nerve) directly
- Add external dependencies (use stdlib threading/asyncio)
- Touch the API layer or database models

**Success criteria**:
- `ruff check src/agent/orchestrator.py src/agent/coordination/` — zero errors
- `pytest tests/test_coordination.py -v` — all pass
- `pytest tests/test_sovereign_manager.py -v` — existing tests still pass
- Orchestrator supports agent communication and task delegation

---

## Task 10: Security Test Suite + Fuzz Testing 🟢

**Status**: ⬜
**Priority**: TESTING (Medium value)
**Estimated Effort**: 60 min
**Files to create**:
- `tests/test_security.py` (new)
- `tests/test_fuzz.py` (new)
- `tests/test_mcp_integration.py` (new)

**Problem**: No security-specific tests, no fuzz testing for path resolution, no MCP integration tests.

**What to do**:

1. **Create `tests/test_security.py`**:
   ```python
   # Test cases to implement:
   - test_sql_injection_prevention()  # Try SQL injection in all endpoints
   - test_path_traversal_prevention()  # Try ../ attacks on file operations
   - test_symlink_escape_prevention()  # Try symlink attacks
   - test_ssrf_prevention()  # Try internal network access
   - test_xss_prevention()  # Try script injection in responses
   - test_cors_headers()  # Verify CORS is restrictive
   - test_security_headers()  # Verify all security headers present
   - test_rate_limiting()  # Verify rate limits work
   - test_jwt_validation()  # Try invalid tokens
   - test_password_policy()  # Verify password strength requirements
   ```

2. **Create `tests/test_fuzz.py`**:
   ```python
   # Fuzz testing for:
   - fuzz_path_resolution()  # Random paths, symlinks, unicode, null bytes
   - fuzz_shell_commands()  # Random command strings
   - fuzz_file_uploads()  # Random filenames, sizes, content
   - fuzz_json_inputs()  # Random JSON payloads to API
   - fuzz_jwt_tokens()  # Random/forged tokens
   ```
   - Use `hypothesis` library for property-based testing if available
   - Or use manual random generation with fixed seeds for reproducibility

3. **Create `tests/test_mcp_integration.py`**:
   ```python
   # MCP server lifecycle tests:
   - test_mcp_server_startup()  # Server starts without errors
   - test_mcp_tool_listing()  # All tools are listed correctly
   - test_mcp_tool_execution()  # Tools can be called
   - test_mcp_authentication()  # Auth works (or fails gracefully when None)
   - test_mcp_error_handling()  # Errors return proper responses
   ```

4. **Run full test suite** after creation:
   ```bash
   pytest tests/test_security.py tests/test_fuzz.py tests/test_mcp_integration.py -v
   ```

**MUST NOT**:
- Modify existing test files
- Add external dependencies (use stdlib random, string, etc.)
- Touch source code (tests only)
- Create destructive tests (no actual exploitation)

**Success criteria**:
- `ruff check tests/test_security.py tests/test_fuzz.py tests/test_mcp_integration.py` — zero errors
- `pytest tests/test_security.py -v` — all pass
- `pytest tests/test_fuzz.py -v` — all pass (or xfail with known issues documented)
- `pytest tests/test_mcp_integration.py -v` — all pass
- Total test count increases by 20+

---

## Task 11: datetime.utcnow() Full Codebase Sweep 🟡

**Status**: ⬜
**Priority**: MEDIUM
**Estimated Effort**: 15 min
**Files to modify**: Any file with `datetime.utcnow()`

**Problem**: `datetime.utcnow()` was fixed in some locations but reintroduced in `tasks/lifecycle.py`. Need a full sweep.

**What to do**:

1. **Find all instances**:
   ```bash
   grep -rn "utcnow()" src/ --include="*.py"
   ```

2. **Replace each** with `datetime.now(timezone.utc)`

3. **Add imports** where needed:
   ```python
   from datetime import datetime, timezone
   ```

4. **Verify no regressions**:
   ```bash
   pytest tests/ -v
   ```

**MUST NOT**:
- Change any logic beyond the datetime call
- Modify function signatures

**Success criteria**:
- `grep -rn "utcnow()" src/` — zero matches
- `pytest tests/ -v` — no new failures

---

## Task 12: God Module Refactoring — tools.py + crud.py 🟢

**Status**: ⬜
**Priority**: LOW (code organization)
**Estimated Effort**: 120 min
**Files to modify**:
- `src/agent/tools.py` (576 lines → split into ~4 files)
- `src/db/crud.py` (436 lines → split into ~8 files)

**Problem**: Two god modules with too many responsibilities. `tools.py` handles tool registry + 24 handlers + audit logic. `crud.py` handles all CRUD for 8 models.

**What to do**:

1. **Split `src/agent/tools.py`**:
   ```
   src/agent/tools/
   ├── __init__.py          # Re-export all public APIs
   ├── registry.py          # ToolRegistry class
   ├── handlers/
   │   ├── __init__.py
   │   ├── dataset.py       # Dataset-related handlers
   │   ├── model.py         # Model-related handlers
   │   ├── system.py        # System info, health checks
   │   └── experiment.py    # Experiment handlers
   └── audit.py             # Audit logging logic
   ```
   - Keep backward compatibility by re-exporting from `__init__.py`

2. **Split `src/db/crud.py`**:
   ```
   src/db/crud/
   ├── __init__.py          # Re-export all CRUD functions
   ├── user.py              # User CRUD
   ├── item.py              # Item CRUD
   ├── model_metadata.py    # ModelMetadata CRUD
   ├── experiment.py        # Experiment CRUD
   ├── audit_log.py         # AuditLog CRUD
   ├── prediction_log.py    # PredictionLog CRUD
   ├── scheduled_job.py     # ScheduledJob CRUD
   └── dataset.py           # Dataset CRUD
   ```
   - Keep backward compatibility by re-exporting from `__init__.py`

3. **Update imports** in all files that import from these modules:
   - Use `from src.db.crud import get_user` (should still work via `__init__.py`)
   - Or update to `from src.db.crud.user import get_user`

4. **Run full test suite** to verify nothing breaks

**MUST NOT**:
- Change any function signatures or return types
- Modify business logic
- Break backward compatibility (re-exports must work)
- Touch any files outside the two modules being split

**Success criteria**:
- `ruff check src/agent/tools/ src/db/crud/` — zero errors
- `pytest tests/ -v` — all existing tests pass
- `from src.agent.tools import ToolRegistry` — works
- `from src.db.crud import get_user` — works
- No file exceeds 200 lines

---

## Execution Guide

### How to Use This File

1. **Open 8-10 OpenCode chats** (one per task)
2. **Paste the task description** into each chat
3. **Each AI works independently** — tasks are designed to not conflict
4. **After completion**, run the full test suite to verify:
   ```bash
   pytest tests/ -v --tb=short
   ```
5. **Check for conflicts** if two tasks modified the same file

### Task Dependencies

```
Task 1  (SQL Injection)       — Independent
Task 2  (Sandbox Hardening)   — Independent
Task 3  (Security Headers)    — Independent
Task 4  (JWT RS256)           — Independent
Task 5  (SSRF + File Upload)  — Independent
Task 6  (Code Quality)        — Independent
Task 7  (Data Protection)     — Independent
Task 8  (RAG Pipeline)        — Independent
Task 9  (Multi-Agent)         — Independent
Task 10 (Security Tests)      — Depends on Tasks 1-7 being done (tests validate fixes)
Task 11 (datetime Sweep)      — Independent (quick win)
Task 12 (God Modules)         — Independent (but do last — largest refactor)
```

### Recommended Order

**Wave 1** (8 parallel chats):
- Tasks 1, 2, 3, 4, 5, 6, 7, 11

**Wave 2** (4 parallel chats):
- Tasks 8, 9, 10, 12

**Wave 3** (verification):
- Run full test suite
- Update PROJECT_DOCUMENTATION.md with results

---

*Generated: 2026-09-10 | Source: Security audit + Code quality audit + NVIDIA Blueprints research*
