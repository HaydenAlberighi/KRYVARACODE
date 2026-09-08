def test_datasets_require_auth(client):
    assert client.get("/api/v1/data/datasets").status_code == 401


def test_dataset_lifecycle(client, auth_headers):
    payload = {
        "name": "iris_data",
        "storage_uri": "s3://kryvara-data/iris.csv",
        "format": "csv",
        "columns": ["sepal_length", "sepal_width"],
    }
    r = client.post("/api/v1/data/datasets", json=payload, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "registered"
    ds_id = body["id"]

    r = client.post("/api/v1/data/datasets", json=payload, headers=auth_headers)
    assert r.status_code == 409

    r = client.get(f"/api/v1/data/datasets/{ds_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["format"] == "csv"

    r = client.patch(
        f"/api/v1/data/datasets/{ds_id}", json={"status": "ready"}, headers=auth_headers
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ready"

    r = client.delete(f"/api/v1/data/datasets/{ds_id}", headers=auth_headers)
    assert r.status_code == 200

    r = client.get(f"/api/v1/data/datasets/{ds_id}", headers=auth_headers)
    assert r.status_code == 404


def test_dataset_invalid_format_422(client, auth_headers):
    r = client.post(
        "/api/v1/data/datasets",
        json={"name": "bad_fmt", "storage_uri": "s3://x", "format": "xls"},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_process_stub_requires_auth(client):
    assert client.post("/api/v1/data/process", json={}).status_code == 401


def test_process_stub_queues_job(client, auth_headers):
    r = client.post(
        "/api/v1/data/process",
        json={"payload": {"x": 1}, "options": {"normalize": True}},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "queued"
