import uuid
from pathlib import Path


def test_upload_requires_auth(client):
    r = client.post(
        "/api/v1/data/datasets/upload",
        files={"file": ("no_auth.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert r.status_code == 401


def test_upload_lifecycle(client, auth_headers):
    name = f"uploaded_{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/api/v1/data/datasets/upload",
        headers=auth_headers,
        files={"file": ("payload.csv", b"a,b\n1,2\n", "text/csv")},
        data={"name": name},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == name
    assert body["format"] == "csv"
    assert body["status"] == "registered"
    assert body["storage_uri"].endswith(".csv")
    ds_id = body["id"]

    dup = client.post(
        "/api/v1/data/datasets/upload",
        headers=auth_headers,
        files={"file": ("payload.csv", b"a,b\n3,4\n", "text/csv")},
        data={"name": name},
    )
    assert dup.status_code == 409

    bad = client.post(
        "/api/v1/data/datasets/upload",
        headers=auth_headers,
        files={"file": ("payload.xlsx", b"x", "application/vnd.ms-excel")},
    )
    assert bad.status_code == 422

    got = client.get(f"/api/v1/data/datasets/{ds_id}", headers=auth_headers)
    assert got.status_code == 200

    deleted = client.delete(f"/api/v1/data/datasets/{ds_id}", headers=auth_headers)
    assert deleted.status_code == 200

    stored = Path(body["storage_uri"])
    if stored.exists():
        stored.unlink()

    gone = client.get(f"/api/v1/data/datasets/{ds_id}", headers=auth_headers)
    assert gone.status_code == 404


def test_upload_stem_becomes_name(client, auth_headers):
    stem_name = f"stem_{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/api/v1/data/datasets/upload",
        headers=auth_headers,
        files={"file": (f"{stem_name}.json", b'{"a": 1}', "application/json")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == stem_name
    assert body["format"] == "json"
    ds_id = body["id"]

    deleted = client.delete(f"/api/v1/data/datasets/{ds_id}", headers=auth_headers)
    assert deleted.status_code == 200
    stored = Path(body["storage_uri"])
    if stored.exists():
        stored.unlink()
