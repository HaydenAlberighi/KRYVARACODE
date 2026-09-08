import uuid


def _name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def test_experiments_require_auth(client):
    r = client.post("/api/v1/experiments", json={"name": _name("exp")})
    assert r.status_code == 401


def test_experiment_lifecycle(client, auth_headers):
    name = _name("exp")
    r = client.post(
        "/api/v1/experiments",
        json={"name": name, "parameters": {"lr": 0.01}},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == name
    assert body["status"] == "created"
    assert isinstance(body["created_by"], int)
    assert body["parameters"] == {"lr": 0.01}
    eid = body["id"]

    r = client.patch(
        f"/api/v1/experiments/{eid}",
        json={"status": "running", "metrics": {"accuracy": 0.9}},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "running"
    assert r.json()["metrics"] == {"accuracy": 0.9}

    r = client.get("/api/v1/experiments", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    r = client.get(f"/api/v1/experiments/{eid}", headers=auth_headers)
    assert r.status_code == 200

    r = client.delete(f"/api/v1/experiments/{eid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["detail"] == "Experiment deleted"

    r = client.get(f"/api/v1/experiments/{eid}", headers=auth_headers)
    assert r.status_code == 404


def test_experiment_invalid_status(client, auth_headers):
    r = client.post(
        "/api/v1/experiments",
        json={"name": _name("exp"), "status": "paused"},
        headers=auth_headers,
    )
    assert r.status_code == 422
