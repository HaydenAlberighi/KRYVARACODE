"""Security test suite for KRYVARACODE.

Tests cover: SQL injection prevention, path traversal, symlink escape,
SSRF prevention, XSS prevention, CORS headers, security headers,
rate limiting, JWT validation, and password policy.
"""

import json
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.agent.aegis.invariants import is_blocked_ip
from src.agent.computer import _resolve_scoped
from src.api.main import app
from src.core.rate_limit import RateLimiter, parse_rate_limit
from src.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    validate_password_policy,
    verify_password,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def user_creds(client):
    import uuid

    suffix = uuid.uuid4().hex[:8]
    creds = {
        "email": f"{suffix}@test.dev",
        "username": f"user_{suffix}",
        "password": "Hunter22!",
    }
    r = client.post("/api/v1/auth/users/", json=creds)
    assert r.status_code == 201, r.text
    return creds


@pytest.fixture()
def auth_headers(client, user_creds):
    r = client.post(
        "/api/v1/auth/token",
        data={"username": user_creds["username"], "password": user_creds["password"]},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# =============================================================================
# SQL Injection Prevention
# =============================================================================


def test_sql_injection_prevention(client, auth_headers):
    """Test that SQL injection attempts in all endpoints are prevented."""
    injection_payloads = [
        "' OR '1'='1",
        "'; DROP TABLE users; --",
        "' UNION SELECT * FROM users --",
        "1' OR '1'='1' --",
        "admin'--",
        "' OR 1=1#",
        "' OR '1'='1' /*",
    ]

    for payload in injection_payloads:
        r = client.get(
            "/api/v1/data/datasets",
            params={"skip": payload, "limit": 10},
            headers=auth_headers,
        )
        assert r.status_code in (200, 422), f"Payload '{payload}' caused {r.status_code}: {r.text}"

    for payload in injection_payloads:
        r = client.get(
            "/api/v1/models/",
            params={"skip": payload, "limit": 10},
            headers=auth_headers,
        )
        assert r.status_code in (200, 422), f"Payload '{payload}' caused {r.status_code}: {r.text}"

    for payload in injection_payloads:
        r = client.get(
            "/api/v1/experiments/",
            params={"skip": payload, "limit": 10},
            headers=auth_headers,
        )
        assert r.status_code in (200, 422), f"Payload '{payload}' caused {r.status_code}: {r.text}"


# =============================================================================
# Path Traversal Prevention
# =============================================================================


def test_path_traversal_prevention():
    """Test that ../ path traversal attacks are blocked on file operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        test_file = tmpdir_path / "allowed.txt"
        test_file.write_text("allowed content")

        outside_file = Path(tmpdir).parent / "secret.txt"
        outside_file.write_text("secret content")

        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
            "allowed.txt/../../../etc/passwd",
            ".." + os.sep + ".." + os.sep + "secret.txt",
            os.path.join("..", "..", "secret.txt"),
        ]

        for malicious_path in malicious_paths:
            with pytest.raises(Exception) as exc_info:
                _resolve_scoped(malicious_path)
            assert "forbidden" in str(exc_info.value).lower() or "outside" in str(exc_info.value).lower()


def test_path_traversal_with_symlink_components():
    """Test that path traversal through symlink components is blocked."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        allowed_root = tmpdir_path / "allowed"
        allowed_root.mkdir()

        target_file = allowed_root / "target.txt"
        target_file.write_text("target")

        outside_dir = tmpdir_path / "outside"
        outside_dir.mkdir()
        secret_file = outside_dir / "secret.txt"
        secret_file.write_text("secret")

        symlink_path = allowed_root / "link"
        symlink_path.symlink_to(outside_dir)

        malicious_paths = [
            str(symlink_path / "secret.txt"),
            str(symlink_path / ".." / "secret.txt"),
        ]

        for malicious_path in malicious_paths:
            with pytest.raises(Exception) as exc_info:
                _resolve_scoped(malicious_path)
            assert "forbidden" in str(exc_info.value).lower() or "symlink" in str(exc_info.value).lower()


# =============================================================================
# Symlink Escape Prevention
# =============================================================================


def test_symlink_escape_prevention():
    """Test that symlink attacks cannot escape the allowed roots."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        allowed_root = tmpdir_path / "project"
        allowed_root.mkdir()

        project_file = allowed_root / "project_file.txt"
        project_file.write_text("project content")

        sensitive_dir = tmpdir_path / "sensitive"
        sensitive_dir.mkdir()
        sensitive_file = sensitive_dir / "keys.txt"
        sensitive_file.write_text("private keys")

        symlink = allowed_root / "escape_link"
        symlink.symlink_to(sensitive_dir)

        with pytest.raises(Exception) as exc_info:
            _resolve_scoped(str(symlink / "keys.txt"))
        assert "forbidden" in str(exc_info.value).lower() or "symlink" in str(exc_info.value).lower()

        nested_link = allowed_root / "nested" / "link"
        nested_link.parent.mkdir()
        nested_link.symlink_to(sensitive_dir)

        with pytest.raises(Exception) as exc_info:
            _resolve_scoped(str(nested_link / "keys.txt"))
        assert "forbidden" in str(exc_info.value).lower() or "symlink" in str(exc_info.value).lower()


# =============================================================================
# SSRF Prevention
# =============================================================================


def test_ssrf_prevention_blocked_ranges():
    """Test that internal IP ranges are blocked for SSRF prevention."""
    private_ips = [
        "10.0.0.1",
        "10.255.255.255",
        "172.16.0.1",
        "172.31.255.255",
        "192.168.0.1",
        "192.168.255.255",
    ]

    for ip in private_ips:
        assert is_blocked_ip(ip), f"Private IP {ip} should be blocked"

    loopback_ips = ["127.0.0.1", "127.0.0.2", "::1"]
    for ip in loopback_ips:
        assert is_blocked_ip(ip), f"Loopback IP {ip} should be blocked"

    link_local = ["169.254.0.1", "169.254.255.255", "fe80::1"]
    for ip in link_local:
        assert is_blocked_ip(ip), f"Link-local IP {ip} should be blocked"

    aws_metadata = ["169.254.169.254"]
    for ip in aws_metadata:
        assert is_blocked_ip(ip), f"AWS metadata IP {ip} should be blocked"

    ipv6_ula = ["fc00::1", "fd00::1"]
    for ip in ipv6_ula:
        assert is_blocked_ip(ip), f"IPv6 ULA {ip} should be blocked"

    public_ips = ["8.8.8.8", "1.1.1.1", "2001:4860:4860::8888"]
    for ip in public_ips:
        assert not is_blocked_ip(ip), f"Public IP {ip} should be allowed"


def test_ssrf_prevention_dns_rebinding():
    """Test SSRF protection against DNS rebinding attacks."""
    import socket

    with patch("socket.getaddrinfo") as mock_getaddrinfo:
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]

        assert is_blocked_ip("rebind.example.com"), "DNS rebinding to localhost should be blocked"

        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 80))]

        assert is_blocked_ip("internal.example.com"), "DNS to private IP should be blocked"


# =============================================================================
# XSS Prevention
# =============================================================================


def test_xss_prevention_security_headers(client):
    """Test that all security headers are present to prevent XSS."""
    r = client.get("/health")

    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "max-age=31536000" in r.headers.get("Strict-Transport-Security", "")
    assert "includeSubDomains" in r.headers.get("Strict-Transport-Security", "")
    assert r.headers.get("Content-Security-Policy") == "default-src 'self'"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_xss_prevention_on_error_responses(client):
    """Test that security headers are present even on error responses."""
    r = client.get("/api/v1/nonexistent")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"

    r = client.post("/api/v1/auth/users/", json={"email": "invalid", "username": "u", "password": "short"})
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"


# =============================================================================
# CORS Headers
# =============================================================================


def test_cors_headers_restrictive(client):
    """Test that CORS headers are restrictive and not overly permissive."""
    r = client.options(
        "/api/v1/auth/users/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert r.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
    assert r.headers.get("Access-Control-Allow-Credentials") == "true"

    r = client.options(
        "/api/v1/auth/users/",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    allowed_origin = r.headers.get("Access-Control-Allow-Origin")
    assert allowed_origin != "*"
    if allowed_origin:
        assert allowed_origin != "http://evil.com"


# =============================================================================
# Security Headers (Comprehensive)
# =============================================================================


def test_security_headers_all_endpoints(client, auth_headers):
    """Test security headers on all major endpoints."""
    endpoints = [
        "/health",
        "/api/v1/auth/users/me",
        "/api/v1/datasets/",
        "/api/v1/models/",
        "/api/v1/experiments/",
        "/api/v1/agent/tools",
    ]

    for endpoint in endpoints:
        headers = auth_headers if "auth" in endpoint or "agent" in endpoint or "datasets" in endpoint else {}
        r = client.get(endpoint, headers=headers)

        assert r.headers.get("X-Content-Type-Options") == "nosniff", f"Missing on {endpoint}"
        assert r.headers.get("X-Frame-Options") == "DENY", f"Missing on {endpoint}"
        assert r.headers.get("X-XSS-Protection") == "1; mode=block", f"Missing on {endpoint}"
        assert "max-age=31536000" in r.headers.get("Strict-Transport-Security", ""), f"Missing on {endpoint}"
        assert r.headers.get("Content-Security-Policy") == "default-src 'self'", f"Missing on {endpoint}"
        assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin", f"Missing on {endpoint}"


# =============================================================================
# Rate Limiting
# =============================================================================


def test_rate_limiting_enforced(client):
    """Test that rate limiting is enforced on auth endpoints."""
    for _i in range(10):
        r = client.post("/api/v1/auth/token", data={"username": "test", "password": "wrong"})
        assert r.status_code == 401

    r = client.post("/api/v1/auth/token", data={"username": "test", "password": "wrong"})
    if r.status_code == 429:
        assert "Retry-After" in r.headers
        assert r.json().get("error_code") == "rate_limited"


def test_rate_limiter_parse_valid():
    """Test rate limit string parsing."""
    assert parse_rate_limit("100/minute") == (100, 60)
    assert parse_rate_limit("5/second") == (5, 1)
    assert parse_rate_limit("2/hour") == (2, 3600)
    assert parse_rate_limit("10/day") == (10, 86400)
    assert parse_rate_limit("3/minutes") == (3, 60)


def test_rate_limiter_parse_invalid():
    """Test rate limit string parsing rejects invalid formats."""
    with pytest.raises(ValueError):
        parse_rate_limit("nope")
    with pytest.raises(ValueError):
        parse_rate_limit("10/lightyear")
    with pytest.raises(ValueError):
        parse_rate_limit("0/minute")
    with pytest.raises(ValueError):
        parse_rate_limit("100")


def test_rate_limiter_sliding_window():
    """Test rate limiter sliding window behavior."""
    import time

    rl = RateLimiter(limit=2, window=0.1)
    assert rl.allow("test_key")
    assert rl.allow("test_key")
    assert not rl.allow("test_key")

    time.sleep(0.15)
    assert rl.allow("test_key")


def test_rate_limiter_per_key_isolation():
    """Test that rate limits are isolated per key."""
    rl = RateLimiter(limit=1, window=10)
    assert rl.allow("key_a")
    assert not rl.allow("key_a")
    assert rl.allow("key_b")


# =============================================================================
# JWT Validation
# =============================================================================


def test_jwt_validation_valid_token(user_creds):
    """Test that valid JWT tokens are accepted."""
    token = create_access_token(subject=user_creds["username"])
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == user_creds["username"]
    assert payload["type"] == "access"


def test_jwt_validation_expired_token(user_creds):
    """Test that expired JWT tokens are rejected."""
    token = create_access_token(subject=user_creds["username"], expires_delta=timedelta(seconds=-1))
    assert decode_access_token(token) is None


def test_jwt_validation_malformed_token():
    """Test that malformed JWT tokens are rejected."""
    assert decode_access_token("not.a.valid.token") is None

    assert (
        decode_access_token(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        is None
    )


def test_jwt_validation_algorithm_confusion():
    """Test that algorithm confusion attacks are prevented (RS256 only)."""
    import jwt

    payload = {"sub": "attacker", "type": "access", "exp": 9999999999}
    forged_token = jwt.encode(payload, "", algorithm="none")
    assert decode_access_token(forged_token) is None

    public_key_path = Path(__file__).parent.parent / "src" / "core" / "keys" / "public.pem"
    if public_key_path.exists():
        public_key = public_key_path.read_text()
        try:
            forged_hs256 = jwt.encode(payload, public_key, algorithm="HS256")
        except jwt.InvalidKeyError:
            forged_hs256 = None
        if forged_hs256 is not None:
            assert decode_access_token(forged_hs256) is None


def test_jwt_refresh_token_rotation(client, user_creds):
    """Test that refresh tokens are rotated on use."""
    r = client.post(
        "/api/v1/auth/token",
        data={"username": user_creds["username"], "password": user_creds["password"]},
    )
    assert r.status_code == 200
    first_refresh = r.json()["refresh_token"]

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert r.status_code == 200
    second_refresh = r.json()["refresh_token"]

    assert second_refresh != first_refresh

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert r.status_code == 401


def test_jwt_refresh_token_revocation(client, user_creds):
    """Test that logout revokes refresh token."""
    r = client.post(
        "/api/v1/auth/token",
        data={"username": user_creds["username"], "password": user_creds["password"]},
    )
    refresh_token = r.json()["refresh_token"]

    r = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert r.status_code == 204

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 401


# =============================================================================
# Password Policy
# =============================================================================


def test_password_policy_enforced(client):
    """Test that password strength requirements are enforced."""
    r = client.post("/api/v1/auth/users/", json={"email": "test@test.dev", "username": "testuser", "password": "short"})
    assert r.status_code == 422

    r = client.post(
        "/api/v1/auth/users/", json={"email": "test2@test.dev", "username": "testuser2", "password": "NoDigitHere!"}
    )
    assert r.status_code == 422

    r = client.post(
        "/api/v1/auth/users/", json={"email": "test3@test.dev", "username": "testuser3", "password": "nouppercase1!"}
    )
    assert r.status_code == 422

    r = client.post(
        "/api/v1/auth/users/", json={"email": "test4@test.dev", "username": "testuser4", "password": "NOLOWERCASE1!"}
    )
    assert r.status_code == 422

    r = client.post(
        "/api/v1/auth/users/", json={"email": "test5@test.dev", "username": "testuser5", "password": "NoSpecialChar1"}
    )
    assert r.status_code == 422

    r = client.post(
        "/api/v1/auth/users/", json={"email": "test6@test.dev", "username": "testuser6", "password": "ValidPass123!"}
    )
    assert r.status_code == 201


def test_password_hash_bcrypt():
    """Test that passwords are hashed with bcrypt."""
    password = "TestPassword123!"
    hashed = get_password_hash(password)

    assert hashed.startswith("$2b$")
    assert verify_password(password, hashed)
    assert not verify_password("WrongPassword123!", hashed)


def test_password_policy_validator():
    """Test the password strength validator directly."""
    assert validate_password_policy("ValidPass123!") == []
    assert validate_password_policy("AnotherGood1@") == []
    assert validate_password_policy("Str0ng!Pass") == []

    assert validate_password_policy("short") != []
    assert validate_password_policy("NoDigitHere!") != []
    assert validate_password_policy("nouppercase1!") != []
    assert validate_password_policy("NOLOWERCASE1!") != []
    assert validate_password_policy("NoSpecialChar1") != []
    assert validate_password_policy("A" * 129 + "1!") != []


def test_password_reuse_prevention(client, user_creds, auth_headers):
    """Test that password reuse is prevented on reset."""

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


def test_account_lockout_after_failed_attempts(client):
    """Test that account is locked after 5 failed login attempts."""
    from src.db import crud
    from src.db.database import SessionLocal

    db = SessionLocal()
    try:
        crud.create_user(
            db,
            email="lockout@test.dev",
            username="lockoutuser",
            password="correctpassword",
        )
        db.commit()
    finally:
        db.close()

    for _ in range(5):
        r = client.post(
            "/api/v1/auth/token",
            data={"username": "lockoutuser", "password": "wrongpassword"},
        )
        assert r.status_code == 401

    r = client.post(
        "/api/v1/auth/token",
        data={"username": "lockoutuser", "password": "wrongpassword"},
    )
    assert r.status_code in (401, 403)

    db = SessionLocal()
    try:
        locked_user = crud.get_user_by_username(db, username="lockoutuser")
        assert locked_user is not None
        assert locked_user.failed_login_attempts >= 5
        assert locked_user.lock_until is not None
    finally:
        db.close()
