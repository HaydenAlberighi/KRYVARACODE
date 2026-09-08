def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "KRYVARACODE"
    assert body["database"] == "ok"


def test_health_version_present(client):
    body = client.get("/health").json()
    assert isinstance(body["version"], str)


def test_root_welcome(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "KRYVARACODE" in r.json()["message"]


def test_unknown_route_404_with_request_id(client):
    r = client.get("/definitely-not-a-route")
    assert r.status_code == 404
    assert "x-request-id" in r.headers
