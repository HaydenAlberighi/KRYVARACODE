# KRYVARACODE Technical Debt & Issues Tracker

This document tracks known issues, architectural gaps, and technical debt within the KRYVARACODE AI System Stack.

## [CRITICAL] Security & Stability
- **Tool Synthesis Logic**: The `ToolSynthesizer` currently uses a templated prototype approach. Production-grade logic generation (via LLM chains) is required to ensure generated tools are functional and safe.
- **Shell Command Blocklist**: While `_BLOCKED_PATTERNS` exists, it is a reactive blocklist. Consider moving toward a more restrictive "allow-list" or a highly sandboxed execution environment for synthesized tools.
- **MCP Server User Context**: The `_handler` in `src/mcp_server.py` currently passes `None` for the authenticated user. This means MCP tools run without user identity, which may be a security risk if tools are expanded to touch user-specific data.

## [IMPORTANT] Testing & Coverage
- **MCP Server Integration**: While `tests/test_mcp_server.py` exists, deep integration tests verifying the full lifecycle of tool registration and execution via stdio are needed.
- **Vision Bridge Gaps**: `src/agent/eye/vision_bridge.py` (`analyze_screen`) and related perception loops currently have no covering tests.
- **Edge Case Fuzzing**: The `_resolve_scoped` path resolution and `_BLOCKED_PATTERNS` regexes should be subjected to fuzz testing to prevent path traversal or command injection bypasses.

## [MINOR] Quality & Maintenance
- **Type Safety**: Ensure all synthesised tool signatures are strictly typed and validated against the `ToolDefinition` schema.
- **Documentation**: Expand documentation for the "Forge" system to explain the synthesis lifecycle to new contributors.
- **LSP Diagnostics**: Resolve remaining minor linting warnings in `src/agent/` to maintain a clean build.

---
*Last Updated: 2026-09-10*
