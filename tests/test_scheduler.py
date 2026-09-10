"""Tests for the scheduled-job tools and runner."""

import uuid


def _invoke(client, headers, name, arguments):
    return client.post(
        f"/api/v1/agent/tools/{name}/invoke",
        json={"arguments": arguments},
        headers=headers,
    )


def _unique(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _job_id_by_name(client, auth_headers, name):
    r = _invoke(client, auth_headers, "list_scheduled_jobs", {})
    assert r.status_code == 200, r.text
    body = r.json()
    jobs = body.get("items", body.get("jobs", body if isinstance(body, list) else []))
    for job in jobs:
        if isinstance(job, dict) and job.get("name") == name:
            return job.get("id")
    return None


def test_scheduler_requires_auth(client):
    r = client.post(
        "/api/v1/agent/tools/create_scheduled_job/invoke",
        json={"arguments": {"name": "x", "tool_name": "system_info"}},
    )
    assert r.status_code == 401


def test_scheduled_job_lifecycle(client, auth_headers):
    name = _unique("schedtest")
    r = _invoke(
        client,
        auth_headers,
        "create_scheduled_job",
        {
            "name": name,
            "tool_name": "system_info",
            "arguments": {},
            "interval_seconds": 3600,
        },
    )
    assert r.status_code == 200, r.text

    job_id = _job_id_by_name(client, auth_headers, name)
    assert job_id is not None

    r = _invoke(client, auth_headers, "run_scheduled_jobs", {})
    assert r.status_code == 200, r.text

    r = _invoke(client, auth_headers, "delete_scheduled_job", {"job_id": job_id})
    assert r.status_code == 200, r.text
    assert _job_id_by_name(client, auth_headers, name) is None


def test_create_job_unknown_tool_fails(client, auth_headers):
    r = _invoke(
        client,
        auth_headers,
        "create_scheduled_job",
        {"name": _unique("schedtest"), "tool_name": "no_such_tool"},
    )
    assert r.status_code != 200
