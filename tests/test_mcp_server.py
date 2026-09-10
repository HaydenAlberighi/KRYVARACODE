import asyncio
import json

import pytest

mcp = pytest.importorskip("mcp")

from src.db.database import init_db
from src.mcp_server import server


@pytest.fixture(autouse=True)
def _db():
    init_db()


def _run(coro):
    return asyncio.run(coro)


def test_mcp_lists_all_tools():
    tools = _run(server.list_tools())
    assert len(tools) == 28
    names = {t.name for t in tools}
    assert {"system_info", "list_datasets", "predict", "train_model"} <= names
    assert {"run_shell", "read_file", "account_status", "create_scheduled_job"} <= names


def test_mcp_tool_schema_has_args():
    tools = _run(server.list_tools())
    by_name = {t.name: t for t in tools}
    schema = by_name["list_datasets"].input_schema
    assert "skip" in schema["properties"]
    assert "limit" in schema["properties"]


def test_mcp_call_list_datasets():
    res = _run(server.call_tool("list_datasets", {}))
    assert "items" in json.dumps(res, default=str)


def test_mcp_call_system_info():
    res = _run(server.call_tool("system_info", {}))
    assert "kryvaracode" in json.dumps(res, default=str).lower()


def test_mcp_call_unknown_tool_raises():
    with pytest.raises(Exception):
        _run(server.call_tool("nope", {}))


def test_mcp_call_predict_without_model_raises():
    with pytest.raises(Exception, match="No model loaded"):
        _run(server.call_tool("predict", {"features": {}}))
