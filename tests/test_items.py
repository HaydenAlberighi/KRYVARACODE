import uuid


def _name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def test_items_require_auth(client):
    r = client.post("/api/v1/items", json={"title": _name("item")})
    assert r.status_code == 401


def test_item_lifecycle(client, auth_headers, user_creds):
    title = _name("item")
    r = client.post("/api/v1/items", json={"title": title}, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == title
    assert isinstance(body["owner_id"], int)
    item_id = body["id"]

    r = client.get("/api/v1/items", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    r = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert r.status_code == 200

    r = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["detail"] == "Item deleted"

    r = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert r.status_code == 404


def test_item_missing_description_ok(client, auth_headers):
    r = client.post(
        "/api/v1/items",
        json={"title": _name("item"), "description": "desc"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["description"] == "desc"


def test_item_empty_title_rejected(client, auth_headers):
    r = client.post("/api/v1/items", json={"title": ""}, headers=auth_headers)
    assert r.status_code == 422
