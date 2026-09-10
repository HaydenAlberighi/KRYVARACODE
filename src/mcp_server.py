"""MCP server exposing the KRYVARACODE tool registry over stdio.

Built on the MCP Python SDK 2.x in-SDK server (``mcp.server.MCPServer``):
``mcp.server.fastmcp`` no longer exists in SDK 2.x, so the native API is used
directly. Every registry tool in ``src.agent.tools`` becomes one MCP tool;
each call runs with a fresh DB session and no authenticated user.

Run with::

    python -m src.mcp_server
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

from mcp.server import MCPServer

from src.agent.tools import TOOLS, Tool
from src.db.database import SessionLocal

server = MCPServer(name="kryvaracode")


def _register(tool: Tool) -> None:
    fields = tool.parameters.model_fields
    params = []
    for fname, finfo in fields.items():
        annotation = finfo.annotation if finfo.annotation is not None else Any
        default = inspect.Parameter.empty if finfo.is_required() else finfo.default
        params.append(
            inspect.Parameter(
                fname,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=default,
                annotation=annotation,
            )
        )

    async def _handler(**kwargs: Any) -> dict[str, Any]:
        db = SessionLocal()
        try:
            parsed = tool.parameters(**kwargs)
            return tool.handler(parsed, db, None)
        finally:
            db.close()

    _handler.__name__ = tool.name
    # inspect.Signature forbids non-default params after default ones.
    ordered = sorted(params, key=lambda p: p.default is not inspect.Parameter.empty)
    _handler.__signature__ = inspect.Signature(ordered)  # type: ignore[attr-defined]
    server.tool(name=tool.name, description=tool.description)(_handler)


for _tool in TOOLS:
    _register(_tool)


async def _serve() -> None:
    await server.run_stdio_async()


def main() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
