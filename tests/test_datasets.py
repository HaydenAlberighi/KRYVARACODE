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

    # Test download endpoint
    r = client.get(f"/api/v1/data/datasets/{ds_id}/download", headers=auth_headers)
    assert r.status_code == 200

    r = client.delete(f"/api/v1/data/datasets/{ds_id}", headers=auth_headers)
    assert r.status_code == 200

    r = client.get(f"/api/v1/data/datasets/{ds_id}", headers=auth_headers)
    assert r.status_code == 404


def test_model_lifecycle(client, auth_headers):
    """Test model metadata CRUD operations."""
    # Create model metadata
    payload = {
        "name": "test_model",
        "version": "0.1.0",
        "description": "Test model",
        "file_path": "/path/to/model.pkl",
    }
    r = client.post("/api/v1/models/", json=payload, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "test_model"
    model_id = body["id"]

    # Read model metadata
    r = client.get(f"/api/v1/models/{model_id}", headers=auth_headers)
    assert r.status_code == 200

    # Test download endpoint
    r = client.get(f"/api/v1/models/{model_id}/download", headers=auth_headers)
    assert r.status_code == 200

    # Delete model metadata
    r = client.delete(f"/api/v1/models/{model_id}", headers=auth_headers)
    assert r.status_code == 200

    # Verify deletion
    r = client.get(f"/api/v1/models/{model_id}", headers=auth_headers)
    assert r.status_code == 404
