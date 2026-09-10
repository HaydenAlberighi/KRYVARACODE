"""
Unit tests for src/agent/forge/manager.py and src/agent/forge/synthesizer.py
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List, Optional

from src.agent.forge.manager import ToolForgeManager
from src.agent.forge.synthesizer import ToolSynthesizer
from src.agent.forge.registry import ToolDefinition, ToolRegistry


class TestToolSynthesizer:
    """Tests for ToolSynthesizer class."""

    @pytest.fixture
    def synthesizer(self):
        """Create a ToolSynthesizer instance."""
        return ToolSynthesizer()

    def test_synthesize_basic(self, synthesizer):
        """Test basic tool synthesis."""
        spec = {
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {"param1": {"type": "str"}, "param2": {"type": "int"}},
            "logic_hint": "simple logic",
        }

        code = synthesizer.synthesize(spec)

        assert "def execute(param1: str, param2: int) -> Any:" in code
        assert "A test tool" in code
        assert "import os" in code
        assert "import sys" in code
        assert "import json" in code
        assert "from typing import Any, Dict, List" in code

    def test_synthesize_with_http_hint(self, synthesizer):
        """Test synthesis with HTTP logic hint."""
        spec = {
            "name": "http_tool",
            "description": "Makes HTTP requests",
            "parameters": {},
            "logic_hint": "http request to api",
        }

        code = synthesizer.synthesize(spec)

        assert "import requests" in code

    def test_synthesize_with_file_hint(self, synthesizer):
        """Test synthesis with file logic hint."""
        spec = {
            "name": "file_tool",
            "description": "Processes files",
            "parameters": {},
            "logic_hint": "file operations",
        }

        code = synthesizer.synthesize(spec)

        assert "import pathlib" in code

    def test_synthesize_with_data_hint(self, synthesizer):
        """Test synthesis with data processing hint."""
        spec = {
            "name": "data_tool",
            "description": "Processes data",
            "parameters": {},
            "logic_hint": "data analysis with pandas",
        }

        code = synthesizer.synthesize(spec)

        assert "import pandas as pd" in code

    def test_synthesize_with_math_hint(self, synthesizer):
        """Test synthesis with math hint."""
        spec = {
            "name": "math_tool",
            "description": "Math operations",
            "parameters": {},
            "logic_hint": "math and numpy",
        }

        code = synthesizer.synthesize(spec)

        assert "import numpy as np" in code

    def test_synthesize_with_system_hint(self, synthesizer):
        """Test synthesis with system hint."""
        spec = {
            "name": "system_tool",
            "description": "System operations",
            "parameters": {},
            "logic_hint": "system monitoring psutil",
        }

        code = synthesizer.synthesize(spec)

        assert "import psutil" in code

    def test_synthesize_with_shell_hint(self, synthesizer):
        """Test synthesis with shell hint."""
        spec = {
            "name": "shell_tool",
            "description": "Shell commands",
            "parameters": {},
            "logic_hint": "shell subprocess",
        }

        code = synthesizer.synthesize(spec)

        assert "import subprocess" in code

    def test_synthesize_with_multiple_hints(self, synthesizer):
        """Test synthesis with multiple logic hints."""
        spec = {
            "name": "multi_tool",
            "description": "Multi-purpose tool",
            "parameters": {"input": {"type": "str"}},
            "logic_hint": "http file data math system shell",
        }

        code = synthesizer.synthesize(spec)

        assert "import requests" in code
        assert "import pathlib" in code
        assert "import pandas as pd" in code
        assert "import numpy as np" in code
        assert "import psutil" in code
        assert "import subprocess" in code

    def test_synthesize_with_lessons(self, synthesizer):
        """Test synthesis incorporates lessons."""
        spec = {
            "name": "lesson_tool",
            "description": "Tool with lessons",
            "parameters": {},
            "logic_hint": "",
        }
        lessons = ["Lesson 1: Avoid X", "Lesson 2: Prefer Y"]

        code = synthesizer.synthesize(spec, lessons=lessons)

        assert "LEARNED CONSTRAINTS:" in code
        assert "Lesson 1: Avoid X" in code
        assert "Lesson 2: Prefer Y" in code

    def test_synthesize_empty_lessons(self, synthesizer):
        """Test synthesis with empty lessons list."""
        spec = {
            "name": "no_lesson_tool",
            "description": "No lessons",
            "parameters": {},
            "logic_hint": "",
        }

        code = synthesizer.synthesize(spec, lessons=[])

        assert "LEARNED CONSTRAINTS:" not in code

    def test_synthesize_none_lessons(self, synthesizer):
        """Test synthesis with None lessons."""
        spec = {
            "name": "none_lesson_tool",
            "description": "No lessons",
            "parameters": {},
            "logic_hint": "",
        }

        code = synthesizer.synthesize(spec, lessons=None)

        assert "LEARNED CONSTRAINTS:" not in code

    def test_synthesize_complex_parameters(self, synthesizer):
        """Test synthesis with complex parameter types."""
        spec = {
            "name": "complex_tool",
            "description": "Complex parameters",
            "parameters": {
                "items": {"type": "List[str]"},
                "config": {"type": "Dict[str, Any]"},
                "count": {"type": "int"},
                "enabled": {"type": "bool"},
            },
            "logic_hint": "",
        }

        code = synthesizer.synthesize(spec)

        assert "items: List[str]" in code
        assert "config: Dict[str, Any]" in code
        assert "count: int" in code
        assert "enabled: bool" in code

    def test_synthesize_param_without_type(self, synthesizer):
        """Test synthesis with parameters missing type."""
        spec = {
            "name": "no_type_tool",
            "description": "No type params",
            "parameters": {
                "param1": {},  # No type
                "param2": "not_a_dict",  # String instead of dict
            },
            "logic_hint": "",
        }

        code = synthesizer.synthesize(spec)

        assert "param1: Any" in code
        assert "param2: Any" in code

    def test_synthesize_body_generation(self, synthesizer):
        """Test logic body generation."""
        params = {"param1": {"type": "str"}, "param2": {"type": "int"}}
        logic_hint = "process data"

        body = synthesizer._generate_logic_body(logic_hint, params)

        assert "Logic synthesized from hint: process data" in body
        assert "result = {'status': 'success', 'data': {}}" in body
        assert "Processing param1..." in body
        assert "result['data']['param1']" in body
        assert "Processing param2..." in body
        assert "result['data']['param2']" in body
        assert "return result" in body

    def test_synthesize_empty_params(self, synthesizer):
        """Test synthesis with no parameters."""
        spec = {
            "name": "no_param_tool",
            "description": "No parameters",
            "parameters": {},
            "logic_hint": "simple",
        }

        code = synthesizer.synthesize(spec)

        assert "def execute() -> Any:" in code

    def test_global_singleton(self):
        """Test that global singleton exists."""
        from src.agent.forge.synthesizer import synthesizer

        assert isinstance(synthesizer, ToolSynthesizer)


class TestToolForgeManager:
    """Tests for ToolForgeManager class."""

    @pytest.fixture
    def mock_sovereign_memory(self):
        """Mock sovereign memory."""
        memory = Mock()
        memory.get_distilled_lessons = Mock(return_value=[])
        return memory

    @pytest.fixture
    def mock_synthesizer(self):
        """Mock synthesizer."""
        synth = Mock()
        synth.synthesize = Mock(
            return_value="def execute() -> Any:\n    return {'status': 'ok'}"
        )
        return synth

    @pytest.fixture
    def mock_verifier(self):
        """Mock verifier."""
        ver = Mock()
        ver.generate_test_cases = Mock(return_value=[{"args": {}, "expected": None}])
        ver.verify = Mock(return_value=(True, ["Test passed"]))
        return ver

    @pytest.fixture
    def mock_registry(self):
        """Mock registry."""
        reg = Mock()
        reg.register_tool = Mock()
        return reg

    @pytest.fixture
    def forge_manager(
        self, mock_sovereign_memory, mock_synthesizer, mock_verifier, mock_registry
    ):
        """Create ToolForgeManager with mocked dependencies."""
        with (
            patch("src.agent.forge.manager.sovereign_memory", mock_sovereign_memory),
            patch("src.agent.forge.manager.synthesizer", mock_synthesizer),
            patch("src.agent.forge.manager.verifier", mock_verifier),
            patch("src.agent.forge.manager.registry", mock_registry),
        ):
            manager = ToolForgeManager()
            yield (
                manager,
                {
                    "memory": mock_sovereign_memory,
                    "synthesizer": mock_synthesizer,
                    "verifier": mock_verifier,
                    "registry": mock_registry,
                },
            )

    def test_forge_capability_success(self, forge_manager):
        """Test successful capability forging."""
        manager, mocks = forge_manager

        spec = {
            "name": "new_tool",
            "description": "A new tool",
            "parameters": {"input": {"type": "str"}},
            "logic_hint": "simple processing",
        }

        success, message = manager.forge_capability(spec)

        assert success is True
        assert "Successfully forged and registered new_tool" in message

        mocks["synthesizer"].synthesize.assert_called_once()
        mocks["verifier"].generate_test_cases.assert_called_once_with(spec)
        mocks["verifier"].verify.assert_called_once()
        mocks["registry"].register_tool.assert_called_once()

    def test_forge_capability_missing_name(self, forge_manager):
        """Test forging with missing tool name."""
        manager, mocks = forge_manager

        spec = {"description": "No name", "parameters": {}}

        success, message = manager.forge_capability(spec)

        assert success is False
        assert "must include a 'name'" in message
        mocks["synthesizer"].synthesize.assert_not_called()

    def test_forge_capability_synthesis_failure(self, forge_manager):
        """Test handling of synthesis failure."""
        manager, mocks = forge_manager
        mocks["synthesizer"].synthesize.side_effect = Exception("Synthesis error")

        spec = {"name": "fail_tool", "description": "Fails", "parameters": {}}

        success, message = manager.forge_capability(spec)

        assert success is False
        assert "Synthesis error" in message

    def test_forge_capability_verification_failure(self, forge_manager):
        """Test handling of verification failure."""
        manager, mocks = forge_manager
        mocks["verifier"].verify.return_value = (
            False,
            ["Test failed: expected X, got Y"],
        )

        spec = {
            "name": "unverified_tool",
            "description": "Fails verification",
            "parameters": {},
        }

        success, message = manager.forge_capability(spec)

        assert success is False
        assert "Verification failed" in message
        assert "expected X, got Y" in message
        mocks["registry"].register_tool.assert_not_called()

    def test_forge_capability_verification_exception(self, forge_manager):
        """Test handling of verification exception."""
        manager, mocks = forge_manager
        mocks["verifier"].generate_test_cases.side_effect = Exception(
            "Verifier crashed"
        )

        spec = {"name": "crash_tool", "description": "Crashes", "parameters": {}}

        success, message = manager.forge_capability(spec)

        assert success is False
        assert "Verification system error" in message

    def test_forge_capability_registration_failure(self, forge_manager):
        """Test handling of registration failure."""
        manager, mocks = forge_manager
        mocks["registry"].register_tool.side_effect = Exception("Registry error")

        spec = {
            "name": "reg_fail_tool",
            "description": "Registration fails",
            "parameters": {},
        }

        success, message = manager.forge_capability(spec)

        assert success is False
        assert "Registration error" in message

    def test_forge_capability_injects_lessons(self, forge_manager):
        """Test that lessons from memory are injected into synthesis."""
        manager, mocks = forge_manager
        mocks["memory"].get_distilled_lessons.return_value = ["Lesson 1", "Lesson 2"]

        spec = {"name": "lesson_tool", "description": "With lessons", "parameters": {}}

        manager.forge_capability(spec)

        call_args = mocks["synthesizer"].synthesize.call_args
        assert call_args is not None
        args, kwargs = call_args
        assert "lessons" in kwargs
        assert kwargs["lessons"] == ["Lesson 1", "Lesson 2"]

    def test_forge_capability_no_lessons(self, forge_manager):
        """Test forging when memory returns no lessons."""
        manager, mocks = forge_manager
        mocks["memory"].get_distilled_lessons.return_value = []

        spec = {"name": "no_lesson_tool", "description": "No lessons", "parameters": {}}

        success, message = manager.forge_capability(spec)

        assert success is True
        call_args = mocks["synthesizer"].synthesize.call_args
        args, kwargs = call_args
        assert kwargs.get("lessons") == []


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh ToolRegistry instance."""
        ToolRegistry._instance = None
        return ToolRegistry()

    def test_singleton(self):
        """Test that ToolRegistry is a singleton."""
        ToolRegistry._instance = None
        r1 = ToolRegistry()
        r2 = ToolRegistry()
        assert r1 is r2

    def test_register_tool(self, registry):
        """Test registering a tool."""
        definition = ToolDefinition(
            name="test_tool",
            description="Test tool",
            parameters={"input": "str"},
            implementation_path="/path/to/tool.py",
            function_name="execute",
        )

        registry.register_tool(definition)

        retrieved = registry.get_tool("test_tool")
        assert retrieved is definition
        assert retrieved.name == "test_tool"

    def test_unregister_tool(self, registry):
        """Test unregistering a tool."""
        definition = ToolDefinition(
            name="removable_tool",
            description="Removable",
            parameters={},
            implementation_path="/path.py",
            function_name="exec",
        )
        registry.register_tool(definition)

        registry.unregister_tool("removable_tool")

        assert registry.get_tool("removable_tool") is None

    def test_unregister_nonexistent(self, registry):
        """Test unregistering non-existent tool."""
        registry.unregister_tool("nonexistent")

    def test_get_tool(self, registry):
        """Test getting a tool by name."""
        definition = ToolDefinition(
            name="get_tool",
            description="Get me",
            parameters={},
            implementation_path="/path.py",
            function_name="exec",
        )
        registry.register_tool(definition)

        retrieved = registry.get_tool("get_tool")

        assert retrieved is definition

    def test_get_nonexistent_tool(self, registry):
        """Test getting non-existent tool returns None."""
        result = registry.get_tool("nonexistent")
        assert result is None

    def test_list_tools(self, registry):
        """Test listing all tools."""
        registry.register_tool(
            ToolDefinition(
                name="tool1",
                description="",
                parameters={},
                implementation_path="",
                function_name="",
            )
        )
        registry.register_tool(
            ToolDefinition(
                name="tool2",
                description="",
                parameters={},
                implementation_path="",
                function_name="",
            )
        )

        tools = registry.list_tools()

        assert "tool1" in tools
        assert "tool2" in tools
        assert len(tools) == 2

    def test_get_all_definitions(self, registry):
        """Test getting all tool definitions."""
        def1 = ToolDefinition(
            name="t1",
            description="",
            parameters={},
            implementation_path="",
            function_name="",
        )
        def2 = ToolDefinition(
            name="t2",
            description="",
            parameters={},
            implementation_path="",
            function_name="",
        )
        registry.register_tool(def1)
        registry.register_tool(def2)

        all_defs = registry.get_all_definitions()

        assert "t1" in all_defs
        assert "t2" in all_defs
        assert all_defs["t1"] is def1
        assert all_defs["t2"] is def2

    def test_global_singleton(self):
        """Test global singleton exists."""
        from src.agent.forge.registry import registry

        assert isinstance(registry, ToolRegistry)


class TestToolDefinition:
    """Tests for ToolDefinition dataclass."""

    def test_tool_definition_creation(self):
        """Test creating a ToolDefinition."""
        definition = ToolDefinition(
            name="my_tool",
            description="A tool",
            parameters={"param": "str"},
            implementation_path="/path/to/tool.py",
            function_name="execute",
            version="2.0.0",
            is_verified=True,
        )

        assert definition.name == "my_tool"
        assert definition.description == "A tool"
        assert definition.parameters == {"param": "str"}
        assert definition.implementation_path == "/path/to/tool.py"
        assert definition.function_name == "execute"
        assert definition.version == "2.0.0"
        assert definition.is_verified is True
        assert definition.created_at is not None

    def test_tool_definition_defaults(self):
        """Test ToolDefinition with default values."""
        definition = ToolDefinition(
            name="default_tool",
            description="Defaults",
            parameters={},
            implementation_path="",
            function_name="",
        )

        assert definition.version == "1.0.0"
        assert definition.is_verified is False
        assert definition.created_at is not None


class TestForgeEdgeCases:
    """Edge case tests for Forge components."""

    def test_synthesizer_deterministic_imports(self):
        """Test that import determination is deterministic."""
        synth = ToolSynthesizer()

        imports1 = synth._determine_imports("http file")
        imports2 = synth._determine_imports("http file")

        assert imports1 == imports2

    def test_synthesizer_case_insensitive_hints(self):
        """Test that logic hints are case insensitive."""
        synth = ToolSynthesizer()

        imports_http = synth._determine_imports("HTTP REQUEST")
        imports_file = synth._determine_imports("FILE operations")

        assert "import requests" in imports_http
        assert "import pathlib" in imports_file

    def test_forge_manager_thread_safety(self):
        """Test that registry is thread-safe."""
        import threading
        import time

        ToolRegistry._instance = None
        registry = ToolRegistry()

        results = []

        def register_tools(start):
            for i in range(10):
                name = f"tool_{start}_{i}"
                defn = ToolDefinition(
                    name=name,
                    description="",
                    parameters={},
                    implementation_path="",
                    function_name="",
                )
                registry.register_tool(defn)
                time.sleep(0.001)
                results.append(registry.get_tool(name) is not None)

        threads = [
            threading.Thread(target=register_tools, args=(i * 10,)) for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(results)
        assert len(registry.list_tools()) == 50
