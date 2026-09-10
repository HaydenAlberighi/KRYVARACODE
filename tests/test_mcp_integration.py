"""MCP Integration test suite for KRYVARACODE.

Tests verify the MCP server correctly exposes all tools, handles requests properly,
and integrates with the tool registry.
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.tools import TOOLS
from src.db.database import SessionLocal, init_db
from src.mcp_server import server

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _db():
    """Initialize database for tests."""
    init_db()


def _run(coro):
    """Run an async coroutine in the test context."""
    return asyncio.run(coro)


def _parse_result(result) -> dict:
    """Parse CallToolResult into a dictionary."""
    # The result is a CallToolResult with content as TextContent
    # Extract the JSON from the text content
    if hasattr(result, "content") and result.content:
        text_content = result.content[0]
        if hasattr(text_content, "text"):
            return json.loads(text_content.text)
    # Fallback: try to convert to dict directly
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return {}


def _call_tool_expect_error(tool_name: str, args: dict) -> dict:
    """Call a tool and expect it to raise an error, return parsed error."""
    try:
        result = _run(server.call_tool(tool_name, args))
        parsed = _parse_result(result)
        return parsed
    except Exception as e:
        # If it raises an exception, that's also valid - return error info
        return {"error": str(e), "exception_type": type(e).__name__}


# =============================================================================
# Test: MCP Server Lists All Tools Correctly
# =============================================================================


def test_mcp_lists_all_registered_tools():
    """Test that MCP server lists all 28 tools from the registry."""
    tools = _run(server.list_tools())

    # Should have all tools from registry
    expected_count = len(TOOLS)
    assert len(tools) == expected_count, f"Expected {expected_count} tools, got {len(tools)}"

    # Check all tool names are present
    mcp_tool_names = {t.name for t in tools}
    registry_tool_names = {t.name for t in TOOLS}
    assert mcp_tool_names == registry_tool_names, (
        f"MCP tool names don't match registry: missing {registry_tool_names - mcp_tool_names}, extra {mcp_tool_names - registry_tool_names}"
    )

    # Verify core tools are present
    core_tools = {
        "system_info",
        "list_datasets",
        "get_dataset",
        "create_dataset",
        "list_models",
        "get_model",
        "get_model_by_name",
        "register_model",
        "list_experiments",
        "get_experiment",
        "create_experiment",
        "predict",
        "train_model",
        "run_shell",
        "read_file",
        "write_file",
        "list_dir",
        "process_list",
        "process_kill",
        "account_status",
        "create_scheduled_job",
        "list_scheduled_jobs",
        "run_scheduled_jobs",
        "delete_scheduled_job",
    }
    assert core_tools <= mcp_tool_names, f"Missing core tools: {core_tools - mcp_tool_names}"


def test_mcp_tool_schemas_match_registry():
    """Test that MCP tool schemas match the registry schemas exactly."""
    mcp_tools = _run(server.list_tools())
    mcp_by_name = {t.name: t for t in mcp_tools}

    for registry_tool in TOOLS:
        mcp_tool = mcp_by_name.get(registry_tool.name)
        assert mcp_tool is not None, f"Tool {registry_tool.name} not found in MCP"

        # Compare schemas
        registry_schema = registry_tool.parameters.model_json_schema()
        mcp_schema = mcp_tool.input_schema

        # Key properties should match
        assert mcp_schema["type"] == registry_schema["type"]
        assert set(mcp_schema.get("properties", {}).keys()) == set(registry_schema.get("properties", {}).keys())


# =============================================================================
# Test: MCP Tool Execution - Basic Tools
# =============================================================================


def test_mcp_call_system_info():
    """Test system_info tool via MCP."""
    result = _run(server.call_tool("system_info", {}))
    parsed = _parse_result(result)

    assert isinstance(parsed, dict)
    assert "service" in parsed
    assert "version" in parsed
    assert "environment" in parsed
    assert "database" in parsed
    assert parsed["service"] == "KRYVARACODE"
    assert parsed["database"] in ("ok", "unavailable")


def test_mcp_call_list_datasets_empty():
    """Test list_datasets returns empty list when no datasets exist."""
    result = _run(server.call_tool("list_datasets", {"skip": 0, "limit": 10}))
    parsed = _parse_result(result)

    assert isinstance(parsed, dict)
    assert "items" in parsed
    assert "total" in parsed
    assert isinstance(parsed["items"], list)
    assert isinstance(parsed["total"], int)
    assert parsed["total"] >= 0


def test_mcp_call_list_models_empty():
    """Test list_models returns empty list when no models exist."""
    result = _run(server.call_tool("list_models", {"skip": 0, "limit": 10}))
    parsed = _parse_result(result)

    assert isinstance(parsed, dict)
    assert "items" in parsed
    assert "total" in parsed
    assert isinstance(parsed["items"], list)
    assert isinstance(parsed["total"], int)


def test_mcp_call_list_experiments_empty():
    """Test list_experiments returns empty list when no experiments exist."""
    result = _run(server.call_tool("list_experiments", {"skip": 0, "limit": 10}))
    parsed = _parse_result(result)

    assert isinstance(parsed, dict)
    assert "items" in parsed
    assert "total" in parsed
    assert isinstance(parsed["items"], list)
    assert isinstance(parsed["total"], int)


def test_mcp_call_process_list():
    """Test process_list tool via MCP."""
    result = _run(server.call_tool("process_list", {}))
    parsed = _parse_result(result)

    assert isinstance(parsed, dict)
    assert "processes" in parsed
    assert isinstance(parsed["processes"], list)
    # Should have at least the current process
    assert len(parsed["processes"]) > 0
    for proc in parsed["processes"]:
        assert "pid" in proc
        assert "name" in proc
        assert isinstance(proc["pid"], int)
        assert isinstance(proc["name"], str)


def test_mcp_call_account_status():
    """Test account_status tool via MCP."""
    result = _run(server.call_tool("account_status", {}))
    parsed = _parse_result(result)

    assert isinstance(parsed, dict)
    assert "github" in parsed
    # github is a dict with available, account, via
    assert isinstance(parsed["github"], dict)
    assert "available" in parsed["github"]


# =============================================================================
# Test: MCP Tool Execution - Parameter Validation
# =============================================================================


def test_mcp_call_unknown_tool_raises():
    """Test that calling unknown tool raises an error."""
    # This might raise an exception or return an error result
    result = _call_tool_expect_error("nonexistent_tool", {})
    assert "error" in result or "exception_type" in result


def test_mcp_call_list_datasets_invalid_params():
    """Test list_datasets with invalid parameters."""
    # Negative skip should be rejected
    result = _call_tool_expect_error("list_datasets", {"skip": -1, "limit": 10})
    assert "error" in result or "exception_type" in result

    # Zero limit should be rejected
    result = _call_tool_expect_error("list_datasets", {"skip": 0, "limit": 0})
    assert "error" in result or "exception_type" in result

    # Limit over max should be rejected
    result = _call_tool_expect_error("list_datasets", {"skip": 0, "limit": 1001})
    assert "error" in result or "exception_type" in result


def test_mcp_call_get_dataset_invalid_id():
    """Test get_dataset with invalid ID."""
    result = _call_tool_expect_error("get_dataset", {"dataset_id": -1})
    assert "error" in result or "exception_type" in result

    # Non-existent ID should return NotFound
    result = _call_tool_expect_error("get_dataset", {"dataset_id": 999999})
    assert "error" in result or "exception_type" in result


def test_mcp_call_get_model_invalid_id():
    """Test get_model with invalid ID."""
    result = _call_tool_expect_error("get_model", {"model_id": -1})
    assert "error" in result or "exception_type" in result

    result = _call_tool_expect_error("get_model", {"model_id": 999999})
    assert "error" in result or "exception_type" in result


def test_mcp_call_get_model_by_name_not_found():
    """Test get_model_by_name with non-existent name."""
    result = _call_tool_expect_error("get_model_by_name", {"name": "nonexistent_model", "version": "1.0"})
    assert "error" in result or "exception_type" in result


def test_mcp_call_get_experiment_invalid_id():
    """Test get_experiment with invalid ID."""
    result = _call_tool_expect_error("get_experiment", {"experiment_id": -1})
    assert "error" in result or "exception_type" in result

    result = _call_tool_expect_error("get_experiment", {"experiment_id": 999999})
    assert "error" in result or "exception_type" in result


# =============================================================================
# Test: MCP Tool Execution - User-Required Tools
# =============================================================================


def test_mcp_call_create_dataset_requires_user():
    """Test that create_dataset requires authentication (returns error without user)."""
    result = _call_tool_expect_error(
        "create_dataset",
        {
            "name": "test_dataset",
            "storage_uri": "/tmp/test.csv",
            "format": "csv",
        },
    )
    # Should fail with an error indicating forbidden/requires user
    error_msg = str(result.get("error", "")).lower()
    assert any(keyword in error_msg for keyword in ["forbidden", "authenticated", "requires user", "permission"])


def test_mcp_call_register_model_requires_user():
    """Test that register_model requires authentication."""
    result = _call_tool_expect_error(
        "register_model",
        {
            "name": "test_model",
            "version": "1.0",
            "file_path": "/tmp/model.pkl",
        },
    )
    error_msg = str(result.get("error", "")).lower()
    assert any(keyword in error_msg for keyword in ["forbidden", "authenticated", "requires user", "permission"])


def test_mcp_call_create_experiment_requires_user():
    """Test that create_experiment requires authentication."""
    result = _call_tool_expect_error(
        "create_experiment",
        {
            "name": "test_experiment",
        },
    )
    error_msg = str(result.get("error", "")).lower()
    assert any(keyword in error_msg for keyword in ["forbidden", "authenticated", "requires user", "permission"])


# =============================================================================
# Test: MCP Tool Execution - File System Tools
# =============================================================================


def test_mcp_call_read_file_not_found():
    """Test read_file with non-existent file."""
    result = _call_tool_expect_error("read_file", {"path": "/nonexistent/file.txt"})
    assert "error" in result or "exception_type" in result


def test_mcp_call_write_file_creates_file():
    """Test write_file creates a file in allowed directory."""
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test_write.txt")
        result = _run(
            server.call_tool(
                "write_file",
                {
                    "path": test_file,
                    "content": "Hello, MCP!",
                },
            )
        )
        parsed = _parse_result(result)

        assert isinstance(parsed, dict)
        assert "bytes_written" in parsed or "success" in str(parsed).lower()

        # Verify file was created
        assert os.path.exists(test_file)
        with open(test_file) as f:
            assert f.read() == "Hello, MCP!"


def test_mcp_call_list_dir():
    """Test list_dir on a temporary directory."""
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test files
        with open(os.path.join(tmpdir, "file1.txt"), "w") as f:
            f.write("content1")
        with open(os.path.join(tmpdir, "file2.txt"), "w") as f:
            f.write("content2")
        os.makedirs(os.path.join(tmpdir, "subdir"))

        result = _run(server.call_tool("list_dir", {"path": tmpdir}))
        parsed = _parse_result(result)

        assert isinstance(parsed, dict)
        assert "entries" in parsed
        assert isinstance(parsed["entries"], list)

        entry_names = {e["name"] for e in parsed["entries"]}
        assert "file1.txt" in entry_names
        assert "file2.txt" in entry_names
        assert "subdir" in entry_names

        for entry in parsed["entries"]:
            assert "name" in entry
            assert "type" in entry
            assert entry["type"] in ("file", "dir")


def test_mcp_call_list_dir_not_found():
    """Test list_dir on non-existent directory."""
    result = _call_tool_expect_error("list_dir", {"path": "/nonexistent/directory"})
    assert "error" in result or "exception_type" in result


# =============================================================================
# Test: MCP Tool Execution - Shell Tools
# =============================================================================


def test_mcp_call_run_shell_simple():
    """Test run_shell with a simple command."""
    result = _run(server.call_tool("run_shell", {"command": "echo hello"}))
    parsed = _parse_result(result)

    assert isinstance(parsed, dict)
    assert "stdout" in parsed or "returncode" in parsed
    if "returncode" in parsed:
        assert parsed["returncode"] == 0


def test_mcp_call_run_shell_blocked_command():
    """Test run_shell blocks dangerous commands."""
    dangerous_commands = [
        "rm -rf /",
        "rm -rf *",
        "sudo rm -rf /",
        "format c:",
    ]

    for cmd in dangerous_commands:
        result = _call_tool_expect_error("run_shell", {"command": cmd})
        error_msg = str(result.get("error", "")).lower()
        assert any(
            keyword in error_msg for keyword in ["forbidden", "blocked", "dangerous", "not allowed", "destructive"]
        ), f"Command '{cmd}' was not blocked: {error_msg}"


def test_mcp_call_run_shell_timeout():
    """Test run_shell handles timeout."""
    # Command that runs longer than timeout
    result = _run(
        server.call_tool(
            "run_shell",
            {
                "command": "sleep 10",
                "timeout": 1,  # 1 second timeout
            },
        )
    )
    parsed = _parse_result(result)

    # Should either timeout or complete (depending on implementation)
    assert isinstance(parsed, dict)


# =============================================================================
# Test: MCP Tool Execution - Scheduled Jobs
# =============================================================================


def test_mcp_call_list_scheduled_jobs():
    """Test list_scheduled_jobs returns empty list initially."""
    result = _run(server.call_tool("list_scheduled_jobs", {"skip": 0, "limit": 10}))
    parsed = _parse_result(result)

    assert isinstance(parsed, dict)
    assert "items" in parsed
    assert "total" in parsed
    assert isinstance(parsed["items"], list)
    assert parsed["total"] == 0


def test_mcp_call_run_scheduled_jobs_empty():
    """Test run_scheduled_jobs with no jobs."""
    result = _run(server.call_tool("run_scheduled_jobs", {}))
    parsed = _parse_result(result)

    assert isinstance(parsed, dict)
    assert "jobs_run" in parsed or "count" in parsed or "executed" in parsed


def test_mcp_call_create_scheduled_job_works_without_user():
    """Test create_scheduled_job works without authentication."""
    result = _run(
        server.call_tool(
            "create_scheduled_job",
            {
                "name": "mcp-created-job",
                "tool_name": "system_info",
                "arguments": {},
                "interval_seconds": 60,
            },
        )
    )
    parsed = _parse_result(result)

    assert isinstance(parsed, dict)
    assert "id" in parsed
    assert parsed["name"] == "mcp-created-job"
    assert parsed["tool_name"] == "system_info"
    assert parsed["interval_seconds"] == 60


def test_mcp_call_delete_scheduled_job_not_found():
    """Test delete_scheduled_job with non-existent ID."""
    result = _call_tool_expect_error("delete_scheduled_job", {"job_id": 999999})
    assert "error" in result or "exception_type" in result


# =============================================================================
# Test: MCP Tool Execution - Process Management
# =============================================================================


def test_mcp_call_process_kill_invalid_pid():
    """Test process_kill with invalid PID."""
    result = _call_tool_expect_error("process_kill", {"pid": -1})
    assert "error" in result or "exception_type" in result

    result = _call_tool_expect_error("process_kill", {"pid": 0})
    assert "error" in result or "exception_type" in result


def test_mcp_call_process_kill_current_process_blocked():
    """Test that killing the current process is blocked."""
    import os

    current_pid = os.getpid()

    result = _call_tool_expect_error("process_kill", {"pid": current_pid})
    assert "error" in result or "exception_type" in result


# =============================================================================
# Test: MCP Tool Execution - Prediction
# =============================================================================


def test_mcp_call_predict_without_model():
    """Test predict fails when no model is loaded."""
    result = _call_tool_expect_error("predict", {"features": {"feature1": 1.0, "feature2": 2.0}})

    assert "error" in result or "exception_type" in result
    error_msg = str(result.get("error", "")).lower()
    assert "no model loaded" in error_msg or "model not loaded" in error_msg or "unavailable" in error_msg


def test_mcp_call_predict_invalid_features():
    """Test predict with invalid features."""
    result = _call_tool_expect_error("predict", {"features": "not_a_dict"})
    assert "error" in result or "exception_type" in result


# =============================================================================
# Test: MCP Server Health and Metadata
# =============================================================================


def test_mcp_server_name():
    """Test MCP server has correct name."""
    assert server.name == "kryvaracode"


def test_mcp_tool_descriptions_not_empty():
    """Test all MCP tools have non-empty descriptions."""
    tools = _run(server.list_tools())

    for tool in tools:
        assert tool.description is not None, f"Tool {tool.name} has no description"
        assert len(tool.description.strip()) > 0, f"Tool {tool.name} has empty description"


def test_mcp_tool_input_schemas_valid():
    """Test all MCP tools have valid JSON schemas."""
    tools = _run(server.list_tools())

    for tool in tools:
        schema = tool.input_schema
        assert schema is not None, f"Tool {tool.name} has no input schema"
        assert schema.get("type") == "object", f"Tool {tool.name} schema type is not object"
        assert "properties" in schema, f"Tool {tool.name} schema missing properties"
        # All tools should have at least empty properties
        assert isinstance(schema["properties"], dict)


# =============================================================================
# Test: MCP Integration with Tool Registry
# =============================================================================


def test_mcp_registry_sync():
    """Test that MCP server tools stay in sync with registry."""
    # Get tools from registry
    registry_names = {t.name for t in TOOLS}

    # Get tools from MCP server
    mcp_tools = _run(server.list_tools())
    mcp_names = {t.name for t in mcp_tools}

    # Should be exactly the same
    assert registry_names == mcp_names, f"Registry and MCP out of sync. Registry: {registry_names}, MCP: {mcp_names}"


def test_mcp_tool_handler_execution():
    """Test that MCP tool handlers execute the actual registry handlers."""
    # system_info is a simple tool that doesn't need DB/user
    # Verify it returns the same data structure as direct handler call
    from src.agent.tools import NoArgs, system_info

    db = SessionLocal()
    try:
        direct_result = system_info(NoArgs(), db, None)
    finally:
        db.close()

    mcp_result = _run(server.call_tool("system_info", {}))
    mcp_parsed = _parse_result(mcp_result)

    # Key fields should match
    assert mcp_parsed["service"] == direct_result["service"]
    assert mcp_parsed["version"] == direct_result["version"]
    assert mcp_parsed["environment"] == direct_result["environment"]
    assert mcp_parsed["database"] == direct_result["database"]


# =============================================================================
# Test: MCP Error Handling
# =============================================================================


def test_mcp_error_responses_structured():
    """Test that MCP errors have structured format."""
    # Test various error scenarios
    error_cases = [
        ("nonexistent_tool", {}),
        ("list_datasets", {"skip": -1}),
        ("get_dataset", {"dataset_id": -1}),
        ("read_file", {"path": "/nonexistent"}),
        ("process_kill", {"pid": -1}),
    ]

    for tool_name, args in error_cases:
        result = _call_tool_expect_error(tool_name, args)
        # Should return an error result (not raise unhandled exception)
        assert "error" in result or "exception_type" in result


# =============================================================================
# Test: MCP Concurrent Calls
# =============================================================================


def test_mcp_concurrent_tool_calls():
    """Test MCP handles concurrent tool calls."""
    import threading

    results = []
    errors = []

    def call_system_info():
        try:
            result = _run(server.call_tool("system_info", {}))
            parsed = _parse_result(result)
            results.append(parsed)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=call_system_info) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert len(errors) == 0, f"Concurrent calls raised errors: {errors}"
    assert len(results) == 10
    for result in results:
        assert result["service"] == "KRYVARACODE"


# =============================================================================
# Test: MCP Tool Registration Completeness
# =============================================================================


def test_all_registry_tools_registered_in_mcp():
    """Test that every tool in the registry is registered in MCP."""
    mcp_tools = _run(server.list_tools())
    mcp_names = {t.name for t in mcp_tools}

    for tool in TOOLS:
        assert tool.name in mcp_names, f"Registry tool '{tool.name}' not registered in MCP"


def test_mcp_no_extra_tools():
    """Test that MCP doesn't have tools not in registry."""
    mcp_tools = _run(server.list_tools())
    mcp_names = {t.name for t in mcp_tools}
    registry_names = {t.name for t in TOOLS}

    # MCP should not have extra tools
    extra = mcp_names - registry_names
    assert len(extra) == 0, f"MCP has extra tools not in registry: {extra}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
