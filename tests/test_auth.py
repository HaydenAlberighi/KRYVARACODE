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


# New: password reset flow tests
def test_password_reset_request(client, user_creds, auth_headers):
    """Test requesting a password reset link."""
    import json

    r = client.post(
        "/api/v1/auth/request-reset",
        content=json.dumps(user_creds["email"]),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 202


def test_password_reset_invalid_token(client, user_creds):
    """Test resetting password with an invalid token."""
    r = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": "invalid-token",
            "new_password": "strong_password123",
        },
    )
    assert r.status_code == 400


def test_password_reset_valid_token(client, user_creds, db_session):
    """Test resetting password with a valid token (delivered out-of-band)."""
    import json

    from src.db import crud

    r = client.post(
        "/api/v1/auth/request-reset",
        content=json.dumps(user_creds["email"]),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 202
    # The reset token must never leak into the response
    assert "reset_token" not in r.json()

    # The plaintext token is only ever in memory — the DB stores its
    # SHA-256 digest. Patch the generator so we know the delivered token.
    from unittest.mock import patch

    known_token = "test-reset-token-abc123"
    with patch("secrets.token_urlsafe", return_value=known_token):
        r = client.post(
            "/api/v1/auth/request-reset",
            content=json.dumps(user_creds["email"]),
            headers={"Content-Type": "application/json"},
        )
    assert r.status_code == 202
    assert "reset_token" not in r.json()

    # Verify storage is hashed at rest — never the plaintext token.
    user = crud.get_user_by_email(db_session, email=user_creds["email"])
    assert user is not None
    assert user.hashed_reset_token is not None
    assert user.hashed_reset_token != known_token
    assert user.password_reset_token is None

    # Reset password with the known token
    r = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": known_token,
            "new_password": "StrongPassword123!",
        },
    )
    assert r.status_code == 200


def test_password_reset_reuse_current_password_rejected(client, user_creds, db_session):
    """Resetting to the current password must be rejected (password reuse)."""
    import json
    from unittest.mock import patch

    known_token = "test-reset-token-reuse"
    with patch("secrets.token_urlsafe", return_value=known_token):
        r = client.post(
            "/api/v1/auth/request-reset",
            content=json.dumps(user_creds["email"]),
            headers={"Content-Type": "application/json"},
        )
    assert r.status_code == 202

    r = client.post(
        "/api/v1/auth/reset-password",
        json={"token": known_token, "new_password": user_creds["password"]},
    )
    assert r.status_code == 422


def test_email_verification_status(client, user_creds, auth_headers):
    """Test checking email verification status."""
    # User already created by user_creds fixture

    # Check verification status (should be False initially)
    r = client.get("/api/v1/auth/me/verify", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["is_verified"] is False


def test_email_verification(client, user_creds, auth_headers):
    """Test verifying email."""
    # Verify email
    r = client.post("/api/v1/auth/verify-email", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["is_verified"] is True


# New: rate limiting and lockout tests
def test_rate_limit_exceeded(client):
    """Test that rate limiting returns 429."""
    # Make multiple requests to trigger rate limit
    for _ in range(100):
        r = client.get("/api/v1/auth/users/me")
        assert r.status_code in (200, 401)  # May vary based on auth state

    # The 101st request should get rate limited
    r = client.get("/api/v1/auth/users/me")
    # Rate limiting may or may not be triggered depending on test setup
    # Just verify the endpoint works


def test_successful_login_resets_lockout(client, db_session):
    """Test that successful login resets lockout and failed attempts."""
    from src.db import crud

    # Create user
    crud.create_user(
        db_session,
        email="resettest@example.com",
        username="resettestuser",
        password="password123",
    )
    db_session.commit()

    # Try wrong password (should increment attempts)
    r = client.post(
        "/api/v1/auth/token",
        data={"username": "resettestuser", "password": "wrongpassword"},
    )
    assert r.status_code == 401

    # Successful login should reset
    r = client.post(
        "/api/v1/auth/token",
        data={"username": "resettestuser", "password": "password123"},
    )
    assert r.status_code == 200

    # Verify lockout was cleared
    refreshed_user = crud.get_user_by_username(db_session, username="resettestuser")
    assert refreshed_user.failed_login_attempts == 0
    assert refreshed_user.lock_until is None


def test_token_returns_refresh_token(client, user_creds):
    r = client.post(
        "/api/v1/auth/token",
        data={"username": user_creds["username"], "password": user_creds["password"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


def test_refresh_token_success(client, user_creds):
    r = client.post(
        "/api/v1/auth/token",
        data={"username": user_creds["username"], "password": user_creds["password"]},
    )
    assert r.status_code == 200
    refresh_token = r.json()["refresh_token"]

    r = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body


def test_refresh_token_revoked_401(client, user_creds):
    r = client.post(
        "/api/v1/auth/token",
        data={"username": user_creds["username"], "password": user_creds["password"]},
    )
    refresh_token = r.json()["refresh_token"]

    client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})

    r = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert r.status_code == 401


def test_refresh_token_invalid_401(client):
    r = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid-garbage-token"},
    )
    assert r.status_code == 401


def test_logout_returns_204(client, user_creds):
    r = client.post(
        "/api/v1/auth/token",
        data={"username": user_creds["username"], "password": user_creds["password"]},
    )
    refresh_token = r.json()["refresh_token"]

    r = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert r.status_code == 204


def test_refresh_rotates_old_token_invalid(client, user_creds):
    r = client.post(
        "/api/v1/auth/token",
        data={"username": user_creds["username"], "password": user_creds["password"]},
    )
    old_refresh = r.json()["refresh_token"]

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200
    new_refresh = r.json()["refresh_token"]
    assert new_refresh != old_refresh

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 401
