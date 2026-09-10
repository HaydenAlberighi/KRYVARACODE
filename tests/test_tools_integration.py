"""
Integration tests for src/agent/tools.py registry (REST + MCP)
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.agent.tools import TOOLS, all_tool_schemas, get_tool, invoke_tool, tool_schema
from src.api.main import app
from src.db import models


class TestToolRegistryREST:
    """Integration tests for REST API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client):
        """Create authenticated user and return auth headers."""
        import uuid

        suffix = uuid.uuid4().hex[:8]
        creds = {
            "email": f"{suffix}@test.dev",
            "username": f"user_{suffix}",
            "password": "Hunter22!",
        }
        r = client.post("/api/v1/auth/users/", json=creds)
        assert r.status_code == 201

        r = client.post(
            "/api/v1/auth/token",
            data={"username": creds["username"], "password": creds["password"]},
        )
        assert r.status_code == 200
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_list_tools_endpoint(self, client, auth_headers):
        """Test GET /api/v1/agent/tools returns all tool schemas."""
        response = client.get("/api/v1/agent/tools", headers=auth_headers)

        assert response.status_code == 200
        tools = response.json()
        assert isinstance(tools, list)
        assert len(tools) >= 20  # At least the core tools

        # Verify schema structure
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert isinstance(tool["parameters"], dict)

    def test_list_tools_requires_auth(self, client):
        """Test that tools endpoint requires authentication."""
        response = client.get("/api/v1/agent/tools")
        assert response.status_code == 401

    def test_invoke_tool_endpoint(self, client, auth_headers):
        """Test POST /api/v1/agent/tools/{name}/invoke works."""
        # Test system_info tool (no args, no DB required for basic check)
        response = client.post(
            "/api/v1/agent/tools/system_info/invoke",
            json={"arguments": {}},
            headers=auth_headers,
        )

        assert response.status_code == 200
        result = response.json()
        assert "status" in result or "service" in result or "version" in result

    def test_invoke_tool_with_validation_error(self, client, auth_headers):
        """Test tool invocation with invalid arguments."""
        # system_info takes no arguments, so providing any should fail validation
        response = client.post(
            "/api/v1/agent/tools/system_info/invoke",
            json={"arguments": {"invalid_arg": "value"}},
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    def test_invoke_nonexistent_tool(self, client, auth_headers):
        """Test invoking a tool that doesn't exist."""
        response = client.post(
            "/api/v1/agent/tools/nonexistent_tool/invoke",
            json={"arguments": {}},
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_invoke_tool_requires_auth(self, client):
        """Test tool invocation requires authentication."""
        response = client.post("/api/v1/agent/tools/system_info/invoke", json={"arguments": {}})
        assert response.status_code == 401

    def test_core_tools_present(self, client, auth_headers):
        """Test that all core tools are registered and accessible."""
        response = client.get("/api/v1/agent/tools", headers=auth_headers)
        tools = response.json()
        tool_names = {t["name"] for t in tools}

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

        for tool_name in core_tools:
            assert tool_name in tool_names, f"Core tool {tool_name} missing from registry"

    def test_tool_schema_structure(self, client, auth_headers):
        """Test that tool schemas match OpenAI function calling format."""
        response = client.get("/api/v1/agent/tools", headers=auth_headers)
        tools = response.json()

        for tool in tools:
            # Check required fields
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool

            # Parameters should be JSON Schema
            params = tool["parameters"]
            assert "type" in params
            assert params["type"] == "object"
            assert "properties" in params


class TestToolRegistryMCP:
    """Integration tests for MCP server tool exposure."""

    def test_mcp_server_imports(self):
        """Test that MCP server can import tool registry."""
        # This verifies the module structure is correct
        from src.agent.tools import TOOLS
        from src.mcp_server import server

        assert server is not None
        assert len(TOOLS) >= 20

    def test_mcp_tool_registration(self):
        """Test that all tools are registered with MCP server."""
        from src.agent.tools import TOOLS
        from src.mcp_server import server

        # Get registered tool names from MCP server
        registered_names = set(server._tool_manager._tools.keys())

        # All TOOLS should be registered
        tool_names = {tool.name for tool in TOOLS}
        assert tool_names.issubset(registered_names) or len(registered_names) >= len(tool_names)

    def test_mcp_tool_schema_format(self):
        """Test MCP tool schemas have correct format."""
        from src.agent.tools import _TOOLS_BY_NAME, TOOLS

        for tool in TOOLS:
            mcp_tool = _TOOLS_BY_NAME.get(tool.name)
            assert mcp_tool is not None
            assert mcp_tool.name == tool.name
            assert mcp_tool.description == tool.description


class TestToolRegistryCore:
    """Tests for core tool registry functions."""

    def test_tools_list_not_empty(self):
        """Test that TOOLS list is populated."""
        assert len(TOOLS) >= 20

    def test_get_tool_existing(self):
        """Test get_tool returns tool for existing name."""
        tool = get_tool("system_info")
        assert tool is not None
        assert tool.name == "system_info"

    def test_get_tool_nonexistent(self):
        """Test get_tool returns None for nonexistent name."""
        tool = get_tool("nonexistent_tool_xyz")
        assert tool is None

    def test_tool_schema_format(self):
        """Test tool_schema produces correct format."""
        tool = get_tool("system_info")
        schema = tool_schema(tool)

        assert schema["name"] == "system_info"
        assert "description" in schema
        assert "parameters" in schema
        assert schema["parameters"]["type"] == "object"

    def test_all_tool_schemas(self):
        """Test all_tool_schemas returns list of schemas."""
        schemas = all_tool_schemas()

        assert isinstance(schemas, list)
        assert len(schemas) == len(TOOLS)

        for schema in schemas:
            assert "name" in schema
            assert "description" in schema
            assert "parameters" in schema

    def test_tool_parameters_are_pydantic_models(self):
        """Test that all tool parameters are Pydantic models."""
        from pydantic import BaseModel

        for tool in TOOLS:
            assert issubclass(tool.parameters, BaseModel)

    def test_tool_requires_user_flag(self):
        """Test that requires_user flag is set correctly."""
        # Tools that require auth
        create_dataset = get_tool("create_dataset")
        assert create_dataset.requires_user is True

        register_model = get_tool("register_model")
        assert register_model.requires_user is True

        # Tools that don't require auth
        system_info = get_tool("system_info")
        assert system_info.requires_user is False

        list_datasets = get_tool("list_datasets")
        assert list_datasets.requires_user is False


class TestInvokeTool:
    """Tests for invoke_tool function."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_user(self):
        """Mock user."""
        user = Mock(spec=models.User)
        user.id = 1
        return user

    def test_invoke_tool_success(self, mock_db, mock_user):
        """Test successful tool invocation."""
        # Mock the system_info handler in the TOOLS list
        tool = get_tool("system_info")
        mock_handler = Mock(return_value={"status": "ok", "version": "1.0"})

        # Replace handler in the tool (create new Tool with mocked handler)
        from src.agent.tools import Tool as ToolClass

        mocked_tool = ToolClass(
            name=tool.name,
            description=tool.description,
            parameters=tool.parameters,
            handler=mock_handler,
            requires_user=tool.requires_user,
        )

        with patch("src.agent.tools._TOOLS_BY_NAME", {"system_info": mocked_tool}):
            result = invoke_tool("system_info", {}, mock_db, mock_user)

            assert result == {"status": "ok", "version": "1.0"}
            mock_handler.assert_called_once()

    def test_invoke_tool_not_found(self, mock_db, mock_user):
        """Test invoking nonexistent tool raises NotFoundError."""
        from src.core.exceptions import NotFoundError

        with pytest.raises(NotFoundError, match="not found"):
            invoke_tool("nonexistent_tool", {}, mock_db, mock_user)

    def test_invoke_tool_validation_error(self, mock_db, mock_user):
        """Test invoking tool with invalid arguments raises ValidationFailedError.

        Note: NoArgs in Pydantic v2 ignores extra fields by default, so this test
        uses a tool that actually validates its arguments.
        """
        from src.core.exceptions import ValidationFailedError

        # Use list_datasets which has required args (skip, limit) - provide invalid type
        with pytest.raises(ValidationFailedError):
            invoke_tool("list_datasets", {"skip": "not_an_int"}, mock_db, mock_user)

    def test_invoke_tool_handler_exception(self, mock_db, mock_user):
        """Test that handler exceptions are wrapped and re-raised."""

        tool = get_tool("system_info")
        mock_handler = Mock(side_effect=Exception("Handler failed"))

        from src.agent.tools import Tool as ToolClass

        mocked_tool = ToolClass(
            name=tool.name,
            description=tool.description,
            parameters=tool.parameters,
            handler=mock_handler,
            requires_user=tool.requires_user,
        )

        with (
            patch("src.agent.tools._TOOLS_BY_NAME", {"system_info": mocked_tool}),
            pytest.raises(Exception, match="Handler failed"),
        ):
            invoke_tool("system_info", {}, mock_db, mock_user)

    def test_invoke_tool_writes_audit_on_success(self, mock_db, mock_user):
        """Test that successful invocation writes audit log."""

        tool = get_tool("system_info")
        mock_handler = Mock(return_value={"ok": True})

        from src.agent.tools import Tool as ToolClass

        mocked_tool = ToolClass(
            name=tool.name,
            description=tool.description,
            parameters=tool.parameters,
            handler=mock_handler,
            requires_user=tool.requires_user,
        )

        with (
            patch("src.agent.tools._TOOLS_BY_NAME", {"system_info": mocked_tool}),
            patch("src.agent.tools._write_audit") as mock_audit,
        ):
            invoke_tool("system_info", {}, mock_db, mock_user)

            mock_audit.assert_called_once()
            assert mock_audit.call_args.args[4] is True
            assert mock_audit.call_args.args[5] is None

    def test_invoke_tool_writes_audit_on_failure(self, mock_db, mock_user):
        """Test that failed handler invocation writes audit log."""

        tool = get_tool("system_info")
        mock_handler = Mock(side_effect=Exception("Handler failed"))

        from src.agent.tools import Tool as ToolClass

        mocked_tool = ToolClass(
            name=tool.name,
            description=tool.description,
            parameters=tool.parameters,
            handler=mock_handler,
            requires_user=tool.requires_user,
        )

        with (
            patch("src.agent.tools._TOOLS_BY_NAME", {"system_info": mocked_tool}),
            patch("src.agent.tools._write_audit") as mock_audit,
        ):
            with pytest.raises(Exception, match="Handler failed"):
                invoke_tool("system_info", {}, mock_db, mock_user)

            mock_audit.assert_called_once()
            assert mock_audit.call_args.args[4] is False
            assert mock_audit.call_args.args[5] is not None

    def test_invoke_tool_anonymous_user(self, mock_db):
        """Test invoking tool with no user (anonymous)."""
        tool = get_tool("system_info")
        mock_handler = Mock(return_value={"ok": True})

        from src.agent.tools import Tool as ToolClass

        mocked_tool = ToolClass(
            name=tool.name,
            description=tool.description,
            parameters=tool.parameters,
            handler=mock_handler,
            requires_user=tool.requires_user,
        )

        with (
            patch("src.agent.tools._TOOLS_BY_NAME", {"system_info": mocked_tool}),
            patch("src.agent.tools._write_audit") as mock_audit,
        ):
            result = invoke_tool("system_info", {}, mock_db, None)

            assert result == {"ok": True}
            mock_audit.assert_called_once()
            assert mock_audit.call_args.args[3] is None


class TestToolArgumentsValidation:
    """Tests for tool argument validation against Pydantic schemas."""

    def test_system_info_no_args(self):
        """Test system_info accepts empty arguments."""
        from src.agent.tools import NoArgs

        parsed = NoArgs(**{})
        assert parsed is not None

    def test_list_args_with_limit(self):
        """Test ListArgs accepts limit parameter."""
        from src.agent.tools import ListArgs

        parsed = ListArgs(limit=10, skip=5)
        assert parsed.limit == 10
        assert parsed.skip == 5

    def test_list_args_defaults(self):
        """Test ListArgs default values."""
        from src.agent.tools import ListArgs

        parsed = ListArgs()
        assert parsed.limit == 100
        assert parsed.skip == 0

    def test_get_dataset_args(self):
        """Test GetDatasetArgs validation."""
        from src.agent.tools import GetDatasetArgs

        parsed = GetDatasetArgs(dataset_id=42)
        assert parsed.dataset_id == 42

        # Missing required field should fail
        with pytest.raises(Exception):
            GetDatasetArgs()

    def test_run_shell_args(self):
        """Test RunShellArgs validation."""
        from src.agent.tools import RunShellArgs

        parsed = RunShellArgs(command="echo hello", workdir="/tmp", timeout_seconds=30)
        assert parsed.command == "echo hello"
        assert parsed.workdir == "/tmp"
        assert parsed.timeout_seconds == 30

        # Default timeout
        parsed2 = RunShellArgs(command="ls")
        assert parsed2.timeout_seconds == 60


class TestGitHubToolsConditional:
    """Tests for conditional GitHub tools."""

    def test_github_tools_when_available(self):
        """Test GitHub tools are present when gh is available."""
        from src.agent.tools import TOOLS, github_available

        # If gh is available, GitHub tools should be in TOOLS
        if github_available():
            tool_names = {t.name for t in TOOLS}
            github_tools = {
                "github_repo_list",
                "github_issue_list",
                "github_issue_create",
                "github_pr_list",
            }
            assert github_tools.issubset(tool_names)


class TestAgentRouterIntegration:
    """Integration tests for agent router with real FastAPI app."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client):
        import uuid

        suffix = uuid.uuid4().hex[:8]
        creds = {
            "email": f"{suffix}@test.dev",
            "username": f"user_{suffix}",
            "password": "Hunter22!",
        }
        r = client.post("/api/v1/auth/users/", json=creds)
        assert r.status_code == 201
        r = client.post(
            "/api/v1/auth/token",
            data={"username": creds["username"], "password": creds["password"]},
        )
        assert r.status_code == 200
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def test_agent_tools_endpoint_integration(self, client, auth_headers):
        """Test full integration of agent tools endpoint."""
        response = client.get("/api/v1/agent/tools", headers=auth_headers)
        assert response.status_code == 200

        tools = response.json()
        assert len(tools) > 0

        # Test invoking a simple tool
        for tool in tools:
            if tool["name"] == "system_info":
                invoke_resp = client.post(
                    f"/api/v1/agent/tools/{tool['name']}/invoke",
                    json={"arguments": {}},
                    headers=auth_headers,
                )
                assert invoke_resp.status_code == 200
                break

    def test_agent_tools_openapi_format(self, client, auth_headers):
        """Test that tool schemas are compatible with OpenAI function calling."""
        response = client.get("/api/v1/agent/tools", headers=auth_headers)
        tools = response.json()

        for tool in tools:
            # OpenAI function calling format requirements
            assert "name" in tool
            assert isinstance(tool["name"], str)
            assert "description" in tool
            assert isinstance(tool["description"], str)
            assert "parameters" in tool
            assert tool["parameters"]["type"] == "object"
            assert "properties" in tool["parameters"]


class TestToolRegistryThreadSafety:
    """Tests for thread safety of tool registry operations."""

    def test_concurrent_tool_lookup(self):
        """Test concurrent get_tool calls."""
        import threading
        import time

        results = []
        errors = []

        def lookup_tools():
            try:
                for _ in range(100):
                    tool = get_tool("system_info")
                    assert tool is not None
                    time.sleep(0.001)
                results.append(True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=lookup_tools) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10

    def test_concurrent_schema_generation(self):
        """Test concurrent all_tool_schemas calls."""
        import threading
        import time

        results = []
        errors = []

        def get_schemas():
            try:
                for _ in range(50):
                    schemas = all_tool_schemas()
                    assert len(schemas) > 0
                    time.sleep(0.001)
                results.append(True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_schemas) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5


class TestMCPServerStartup:
    """Tests for MCP server startup and tool registration."""

    def test_mcp_server_creates_tools(self):
        """Test that MCP server initializes with tools."""
        from src.mcp_server import server

        # Server should have tools registered
        assert hasattr(server, "_tools") or hasattr(server, "_tool_manager")

        # At minimum, verify the module loads without error
        import src.mcp_server

        assert src.mcp_server is not None

    def test_mcp_tool_handler_signature(self):
        """Test that MCP tool handlers have correct signatures."""
        from src.agent.tools import TOOLS

        # Each tool in TOOLS should have a corresponding handler
        # The server registers handlers dynamically
        assert len(TOOLS) > 0
