"""Tests for account tools (status + GitHub adapters)."""

import pytest

from src.agent.accounts import github_available

needs_gh = pytest.mark.skipif(not github_available(), reason="gh CLI not authenticated here")


def _invoke(client, headers, name, arguments):
    return client.post(
        f"/api/v1/agent/tools/{name}/invoke",
        json={"arguments": arguments},
        headers=headers,
    )


def test_account_status_shape(client, auth_headers):
    r = _invoke(client, auth_headers, "account_status", {})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "github" in body
    assert "gmail" in body
    assert isinstance(body["github"].get("available"), bool)
    assert body["gmail"].get("available") is False


def test_account_status_requires_auth(client):
    r = client.post("/api/v1/agent/tools/account_status/invoke", json={"arguments": {}})
    assert r.status_code == 401


@needs_gh
def test_github_repo_list(client, auth_headers):
    r = _invoke(client, auth_headers, "github_repo_list", {"limit": 5})
    assert r.status_code == 200, r.text


@needs_gh
def test_github_issue_list_known_repo(client, auth_headers):
    r = _invoke(
        client,
        auth_headers,
        "github_issue_list",
        {"repo": "HaydenAlberighi/KRYVARACODE", "limit": 5},
    )
    assert r.status_code == 200, r.text
