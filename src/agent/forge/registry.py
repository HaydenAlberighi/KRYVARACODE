"""
ToolRegistry for KRYVARACODE Omega-Prime.
Handles the dynamic registration, tracking, and retrieval of synthesized capabilities.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Metadata for a synthesized tool."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema of expected arguments
    implementation_path: str  # Path to the Python file containing the logic
    function_name: str  # Name of the function to call within the file
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    is_verified: bool = False


class ToolRegistry:
    """
    A thread-safe registry for managing dynamically synthesized tools.
    Allows the agent to expand its capabilities at runtime.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._registry_lock = threading.RLock()
        logger.info("ToolRegistry initialized for Omega-Prime.")

    def register_tool(self, definition: ToolDefinition):
        """Registers a new tool or updates an existing one."""
        with self._registry_lock:
            self._tools[definition.name] = definition
            logger.info(
                f"Tool '{definition.name}' (v{definition.version}) registered successfully."
            )

    def unregister_tool(self, tool_name: str):
        """Removes a tool from the registry."""
        with self._registry_lock:
            if tool_name in self._tools:
                del self._tools[tool_name]
                logger.info(f"Tool '{tool_name}' unregistered.")
            else:
                logger.warning(
                    f"Attempted to unregister non-existent tool '{tool_name}'."
                )

    def get_tool(self, tool_name: str) -> ToolDefinition | None:
        """Retrieves tool metadata by name."""
        with self._registry_lock:
            return self._tools.get(tool_name)

    def list_tools(self) -> list[str]:
        """Returns a list of all currently registered synthesized tools."""
        with self._registry_lock:
            return list(self._tools.keys())

    def get_all_definitions(self) -> dict[str, ToolDefinition]:
        """Returns all tool definitions for analysis by the Sovereign."""
        with self._registry_lock:
            return self._tools.copy()


# Global singleton for system-wide access
registry = ToolRegistry()
