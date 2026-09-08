def test_models_require_auth(client):
    assert client.get("/api/v1/models").status_code == 401


def test_model_create_and_get(client, auth_headers):
    payload = {
        "name": "demo_model",
        "version": "1.0.0",
        "file_path": "mlflow:///models/demo_model/1",
        "accuracy": 0.95,
    }
    r = client.post("/api/v1/models/", json=payload, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "demo_model"
    assert body["version"] == "1.0.0"
    model_id = body["id"]

    r = client.get(f"/api/v1/models/{model_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["accuracy"] == 0.95


def test_model_list(client, auth_headers):
    r = client.get("/api/v1/models/", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_model_get_by_name_version(client, auth_headers):
    payload = {
        "name": "named_model",
        "version": "2.1.0",
        "file_path": "mlflow:///models/named_model/2",
    }
    r = client.post("/api/v1/models/", json=payload, headers=auth_headers)
    assert r.status_code == 201

    r = client.get("/api/v1/models/named_model/2.1.0", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["version"] == "2.1.0"


def test_model_not_found_404(client, auth_headers):
    r = client.get("/api/v1/models/999999", headers=auth_headers)
    assert r.status_code == 404
