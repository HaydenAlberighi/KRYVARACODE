"""Tests for computer-control agent tools (shell, files, processes)."""

import os
import tempfile


def _invoke(client, headers, name, arguments):
    return client.post(
        f"/api/v1/agent/tools/{name}/invoke",
        json={"arguments": arguments},
        headers=headers,
    )


def test_computer_tools_require_auth(client):
    r = client.post(
        "/api/v1/agent/tools/run_shell/invoke",
        json={"arguments": {"command": "echo hi"}},
    )
    assert r.status_code == 401


def test_agent_tool_list_includes_computer_tools(client, auth_headers):
    r = client.get("/api/v1/agent/tools", headers=auth_headers)
    assert r.status_code == 200
    names = {t["name"] for t in r.json()}
    for expected in (
        "run_shell",
        "read_file",
        "write_file",
        "list_dir",
        "process_list",
        "process_kill",
    ):
        assert expected in names


def test_run_shell_echo(client, auth_headers):
    r = _invoke(client, auth_headers, "run_shell", {"command": "echo hello"})
    assert r.status_code == 200, r.text
    assert "hello" in r.text


def test_run_shell_blocked_command_refused(client, auth_headers):
    r = _invoke(client, auth_headers, "run_shell", {"command": "rm -rf /"})
    assert r.status_code != 200


def test_write_and_read_file_roundtrip(client, auth_headers):
    path = os.path.join(tempfile.gettempdir(), "kryvara_tooltest_roundtrip.txt")
    try:
        r = _invoke(
            client,
            auth_headers,
            "write_file",
            {"path": path, "content": "tool-test-content"},
        )
        assert r.status_code == 200, r.text
        assert os.path.exists(path)

        r = _invoke(client, auth_headers, "read_file", {"path": path})
        assert r.status_code == 200, r.text
        assert "tool-test-content" in r.text
    finally:
        if os.path.exists(path):
            os.remove(path)


def test_read_missing_file_fails(client, auth_headers):
    missing = os.path.join(tempfile.gettempdir(), "kryvara_tooltest_missing.txt")
    if os.path.exists(missing):
        os.remove(missing)
    r = _invoke(client, auth_headers, "read_file", {"path": missing})
    assert r.status_code != 200


def test_list_dir(client, auth_headers):
    r = _invoke(client, auth_headers, "list_dir", {"path": tempfile.gettempdir()})
    assert r.status_code == 200, r.text


def test_process_list(client, auth_headers):
    r = _invoke(client, auth_headers, "process_list", {})
    assert r.status_code == 200, r.text


def test_process_kill_refuses_system_pid(client, auth_headers):
    r = _invoke(client, auth_headers, "process_kill", {"pid": 1})
    assert r.status_code != 200
