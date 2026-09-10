"""
Protocol Bridge module for Omega-Prime.
Provides a unified interface for interacting with diverse network protocols.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ProtocolResponse:
    payload: Any
    status: str
    protocol: str
    metadata: dict[str, Any]


class ProtocolBridge:
    """
    Unified wrapper for different communication protocols.
    Allows the Forge to send requests without worrying about the underlying transport.
    """

    def __init__(self):
        self._handlers: dict[str, Callable] = {}

    def register_handler(self, protocol: str, handler: Callable):
        """Register a handler for a specific protocol (e.g., 'grpc', 'websocket', 'http')."""
        self._handlers[protocol] = handler
        logger.info(f"Registered protocol handler: {protocol}")

    async def send(self, protocol: str, destination: str, payload: Any, **kwargs) -> ProtocolResponse:
        """
        Send a request via the specified protocol.
        """
        if protocol not in self._handlers:
            raise NotImplementedError(f"Protocol {protocol} is not supported by the Bridge.")

        try:
            handler = self._handlers[protocol]
            # The handler is expected to be an async function returning (payload, status, metadata)
            result, status, metadata = await handler(destination, payload, **kwargs)

            return ProtocolResponse(payload=result, status=status, protocol=protocol, metadata=metadata)
        except Exception as e:
            logger.error(f"Protocol error on {protocol} to {destination}: {e}")
            return ProtocolResponse(
                payload=None,
                status="error",
                protocol=protocol,
                metadata={"error": str(e)},
            )


# Singleton instance for the Forge
protocol_bridge = ProtocolBridge()


# Mock HTTP handler for initial setup
async def http_mock_handler(dest, payload, **kwargs):
    return (
        {"status": "ok", "data": "mock_http_response"},
        "success",
        {"latency": "10ms"},
    )


protocol_bridge.register_handler("http", http_mock_handler)
