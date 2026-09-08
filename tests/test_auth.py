def test_signup_and_duplicate_conflict(client, user_creds):
    r = client.post("/api/v1/auth/users/", json=user_creds)
    assert r.status_code == 409
    assert r.json()["error_code"] == "conflict"


def test_signup_invalid_email_422(client):
    r = client.post(
        "/api/v1/auth/users/",
        json={
            "email": "not-an-email",
            "username": "valid_user",
            "password": "hunter22",
        },
    )
    assert r.status_code == 422


def test_signup_short_password_422(client):
    r = client.post(
        "/api/v1/auth/users/",
        json={"email": "x@test.dev", "username": "user_val", "password": "short"},
    )
    assert r.status_code == 422


def test_token_success_and_me(client, user_creds, auth_headers):
    r = client.get("/api/v1/auth/users/me", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == user_creds["username"]
    assert body["email"] == user_creds["email"]
    assert body["is_active"] is True


def test_token_wrong_password_401(client, user_creds):
    r = client.post(
        "/api/v1/auth/token",
        data={"username": user_creds["username"], "password": "wrong-password"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Incorrect username or password"


def test_me_without_token_401(client):
    r = client.get("/api/v1/auth/users/me")
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"


def test_me_with_garbage_token_401(client):
    r = client.get("/api/v1/auth/users/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
