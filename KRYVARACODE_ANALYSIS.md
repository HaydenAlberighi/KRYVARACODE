# KRYVARACODE Codebase Analysis

**Date**: 2026-09-10  
**Analyst**: Sisyphus  
**Status**: Complete

---

## Architecture Overview

| Layer | Component | Status |
|-------|-----------|--------|
| **API** | FastAPI + JWT auth + rate limiting + lifespan mgmt | ✅ Production-ready |
| **MCP Server** | 30+ tools via stdio (MCP SDK 2.x) | ✅ Functional |
| **Tool Registry** | Generic `Tool[ArgsT]` with Pydantic schemas, JSON Schema gen | ✅ Well-designed |
| **Forge** | Template-based tool synthesis (Registry/Synthesizer/Verifier) | ✅ Working |
| **RAG** | Embedder (ST/TF-IDF) + Chunker + In-memory Retriever | ⚠️ **Limited** |
| **Sovereign** | Manager + Memory Graph + Judge + Evolver loop | ✅ Novel architecture |
| **Aegis** | Verifier (invariants) + Gatekeeper (HITL) | ✅ Safety-first |

---

## Dependencies

**Base**: FastAPI, SQLAlchemy 2.x, Redis/Celery, Pydantic 2, python-jose, bcrypt, prometheus-client, loguru, mcp>=2.0.0  
**ML**: torch (CPU), tensorflow-cpu, mlflow, boto3, minio  
**Dev**: pytest, black, ruff, mypy, pre-commit, mkdocs-material

---

## Key Patterns

- Pydantic models for all tool parameters with JSON Schema generation
- Generic `Tool[ArgsT]` dataclass with handler: `(ArgsT, Session, User?) -> dict`
- MCP registration via `inspect.Signature` manipulation
- In-memory rate limiter (sliding window), disabled by default
- Global singletons for registry, verifier, gatekeeper
- Thread-safe `ToolRegistry` with `RLock`

---

## Critical Gaps & Enhancement Priority Matrix

| Priority | Area | Gap | Recommended Solution |
|----------|------|-----|---------------------|
| **P0** | RAG Persistence | In-memory cosine only | Add **Qdrant/Weaviate/Pinecone** + hybrid search (BM25 + dense) |
| **P0** | Sandboxing | Raw shell execution | **Firecracker/gVisor** microVMs or **E2B/Daytona** sandbox API |
| **P1** | Observability | Prometheus only | **Langfuse/LangSmith** for LLM tracing + **RAGAS/DeepEval** for eval |
| **P1** | MCP Transport | stdio only | Add **HTTP/SSE** transport + **MCP Gateway** for community servers |
| **P2** | Auth | JWT only | **OAuth2/OIDC** (Auth0/Clerk/Keycloak) + **API keys** with scopes |
| **P2** | Scheduling | In-process Celery | **Temporal** or **Airflow** for distributed workflows |
| **P2** | Multi-agent | Custom sovereign only | **LangGraph** integration for complex graphs |
| **P3** | Tool Synthesis | Template-only | **LLM-driven synthesis** (function calling → code gen → verify) |
| **P3** | Embeddings | ST/TF-IDF only | **Rerankers** (Cohere/Jina/BGE) + **ColBERTv2** late interaction |

---

## Immediate Action Items (This Week)

```bash
# 1. Add vector DB to RAG (highest ROI)
pip install qdrant-client sentence-transformers

# 2. Add sandboxing for shell tool
pip install e2b  # or Daytona SDK

# 3. Add LLM observability
pip install langfuse  # or langsmith

# 4. Enable HTTP MCP transport
# Modify src/mcp_server.py to support StreamableHTTP transport
```

---

## Architectural Decisions to Make

| Decision | Options | Recommendation |
|----------|---------|----------------|
| **Vector DB** | Qdrant (self-hosted), Weaviate, Pinecone, Chroma | **Qdrant** — Rust, fast, filters, self-hostable |
| **Sandbox** | Firecracker, gVisor, E2B, Daytona, Modal | **E2B** — simplest API, built for code execution |
| **Orchestration** | Custom → LangGraph, Temporal, Airflow | **LangGraph** for agent graphs; **Temporal** for durable workflows |
| **Eval Framework** | RAGAS, DeepEval, Patronus, Custom | **RAGAS** for RAG; **DeepEval** for agent benchmarks |

---

## Codebase Health: 8/10

**Strengths**: Clean separation, Pydantic-first, thread-safe registry, safety layer (Aegis), novel sovereign architecture

**Technical Debt**: 
- Global singletons hinder testing (consider DI container)
- No integration tests for MCP tools
- Rate limiter disabled by default — enable in production
- TF-IDF fallback is weak; consider **BM25** (rank-bm25) as baseline

---

## Next Steps

1. **Implement Qdrant-backed Retriever** with hybrid search
2. **Add E2B sandbox** for the shell tool
3. **Integrate Langfuse** for LLM tracing
4. **Build HTTP/SSE MCP transport**
5. **Create a work plan** for any of the above