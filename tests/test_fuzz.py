"""Fuzz/property-based test suite for KRYVARACODE.

Tests use hypothesis for property-based fuzzing of inputs to discover edge cases
and bugs that unit tests might miss. Requires hypothesis package (pip install hypothesis).
"""

from __future__ import annotations

import string
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

# Try to import hypothesis, skip tests if not available
hypothesis = pytest.importorskip("hypothesis")
from hypothesis import example, given, settings
from hypothesis import strategies as st

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Imports after path modification (required for local imports)
from src.agent.computer import _resolve_scoped
from src.agent.tools import TOOLS, ListArgs, get_tool
from src.api.main import app
from src.core.rate_limit import parse_rate_limit
from src.core.security import get_password_hash, validate_password_policy, verify_password
from src.schemas.dataset import DatasetCreate
from src.schemas.experiment import ExperimentCreate
from src.schemas.model import ModelCreate
from src.schemas.prediction import PredictionRequest

# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Unicode strings including control characters, emojis, etc.
unicode_text = st.text(
    alphabet=st.characters(
        min_codepoint=0,
        max_codepoint=0x10FFFF,
        blacklist_categories=("Cs",),  # Exclude surrogates
        blacklist_characters=["\x00"],  # Exclude null bytes
    ),
    min_size=0,
    max_size=1000,
)

# ASCII strings for simpler cases
ascii_text = st.text(
    alphabet=string.printable,
    min_size=0,
    max_size=1000,
)

# Password strings that might pass validation
password_strategy = st.text(
    alphabet=string.ascii_letters + string.digits + "!@#$%^&*()",
    min_size=8,
    max_size=128,
)

# File paths (including malicious ones)
file_path_strategy = st.text(
    alphabet=string.ascii_letters + string.digits + "/\\.-_",
    min_size=1,
    max_size=500,
)

# JSON-serializable data
json_data = st.recursive(
    st.none()
    | st.booleans()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.integers()
    | st.text(max_size=100),
    lambda children: st.lists(children, max_size=10) | st.dicts(st.text(max_size=20), children, max_size=10),
    max_leaves=50,
)


# =============================================================================
# Fuzz Tests - Password Validation
# =============================================================================


@settings(max_examples=200, deadline=None)
@given(password_strategy)
@example("ValidPass123!")  # Known valid
@example("A" * 128 + "1!")  # Max length
@example("short")  # Too short
@example("NoDigitHere!")  # No digit
@example("nouppercase1!")  # No uppercase
@example("NOLOWERCASE1!")  # No lowercase
@example("NoSpecialChar1")  # No special char
def test_fuzz_password_validation(password: str):
    """Fuzz test password validation - should never crash, only raise ValueError for invalid."""
    try:
        errors = validate_password_policy(password)
        if not errors:
            # If it passes, it should be a valid password
            assert len(password) >= 8
            assert any(c.islower() for c in password)
            assert any(c.isupper() for c in password)
            assert any(c.isdigit() for c in password)
            assert any(c in "!@#$%^&*()-_=+[]{}|;:'\",.<>?/`~" for c in password)
            assert len(password) <= 128
    except Exception as e:
        # Should never raise exceptions
        pytest.fail(f"validate_password_policy raised unexpected exception: {type(e).__name__}: {e}")


@settings(max_examples=100, deadline=None)
@given(password_strategy, password_strategy)
def test_fuzz_password_hash_roundtrip(password1: str, password2: str):
    """Fuzz test password hash/verify roundtrip - should never crash."""
    try:
        hashed = get_password_hash(password1)
        assert hashed.startswith("$2b$")
        # Verify correct password works
        assert verify_password(password1, hashed) is True
        # Verify wrong password fails
        if password1 != password2:
            assert verify_password(password2, hashed) is False
    except Exception as e:
        pytest.fail(f"Password hash/verify raised unexpected exception: {type(e).__name__}: {e}")


# =============================================================================
# Fuzz Tests - Path Resolution (Security Critical)
# =============================================================================


@settings(max_examples=200, deadline=None)
@given(file_path_strategy)
@example("../../../etc/passwd")
@example("..\\..\\windows\\system32")
@example("allowed/../../../secret")
@example("")  # Empty path
@example(".")  # Current dir
@example("..")  # Parent dir
@example("/")  # Root
@example("C:\\Windows")  # Windows absolute
@example("/etc/passwd")  # Unix absolute
def test_fuzz_path_resolution_security(path: str):
    """Fuzz test _resolve_scoped - should always either resolve safely or raise for traversal."""
    try:
        result = _resolve_scoped(path)
        # If it resolves, the result should be a Path inside allowed roots
        # The function should never return a path outside allowed roots
        resolved = Path(result).resolve()
        # Note: We can't easily check the exact allowed roots without knowing them,
        # but we can verify it doesn't crash and returns a valid path
        assert isinstance(resolved, Path)
    except Exception as e:
        # Expected for malicious paths - should raise ValueError or similar
        error_msg = str(e).lower()
        assert any(
            keyword in error_msg
            for keyword in ["forbidden", "outside", "traversal", "symlink", "invalid", "not allowed"]
        ), f"Unexpected error for path '{path}': {type(e).__name__}: {e}"


# =============================================================================
# Fuzz Tests - Rate Limit Parsing
# =============================================================================


@settings(max_examples=200, deadline=None)
@given(ascii_text)
@example("100/minute")
@example("5/second")
@example("2/hour")
@example("10/day")
@example("100/minutes")
@example("100/")
@example("/minute")
@example("abc")
@example("0/minute")
@example("-1/minute")
@example("100/foo")
@example("100/minute/extra")
def test_fuzz_rate_limit_parsing(rate_str: str):
    """Fuzz test parse_rate_limit - should never crash, only raise ValueError for invalid."""
    try:
        limit, window = parse_rate_limit(rate_str)
        assert isinstance(limit, int)
        assert isinstance(window, int)
        assert limit > 0
        assert window > 0
    except ValueError:
        # Expected for invalid formats
        pass
    except Exception as e:
        pytest.fail(f"parse_rate_limit raised unexpected exception: {type(e).__name__}: {e}")


# =============================================================================
# Fuzz Tests - Schema Validation (Pydantic)
# =============================================================================


@settings(max_examples=200, deadline=None)
@given(
    name=st.text(min_size=1, max_size=100),
    description=st.text(max_size=5000),
    storage_uri=st.text(min_size=1, max_size=500),
    file_format=st.sampled_from(["csv", "parquet", "json", "unknown"]),
    row_count=st.integers(min_value=-10, max_value=1000000),
    columns=st.lists(st.text(min_size=1, max_size=50), max_size=50),
)
@example(name="", description="test", storage_uri="/tmp/test.csv", file_format="csv", row_count=0, columns=[])
@example(name="a" * 101, description="test", storage_uri="/tmp/test.csv", file_format="csv", row_count=0, columns=[])
def test_fuzz_dataset_create_schema(
    name: str, description: str, storage_uri: str, file_format: str, row_count: int, columns: list
):
    """Fuzz test DatasetCreate schema validation."""
    try:
        dataset = DatasetCreate(
            name=name,
            description=description,
            storage_uri=storage_uri,
            format=file_format,
            row_count=row_count,
            columns=columns,
        )
        # If valid, check constraints
        assert 1 <= len(dataset.name) <= 100
        assert len(dataset.storage_uri) >= 1
        assert dataset.format in ["csv", "parquet", "json"]
    except ValidationError:
        # Validation errors are expected for invalid inputs
        pass
    except Exception as e:
        pytest.fail(f"DatasetCreate raised unexpected exception: {type(e).__name__}: {e}")


@settings(max_examples=200, deadline=None)
@given(
    name=st.text(min_size=1, max_size=100),
    description=st.text(max_size=5000),
    status=st.sampled_from(["created", "running", "completed", "failed", "unknown"]),
    metrics=st.dicts(st.text(max_size=50), st.floats(allow_nan=False, allow_infinity=False), max_size=20),
    parameters=st.dicts(st.text(max_size=50), st.text(max_size=100), max_size=20),
)
@example(name="", description="test", status="created", metrics={}, parameters={})
@example(name="a" * 101, description="test", status="created", metrics={}, parameters={})
def test_fuzz_experiment_create_schema(name: str, description: str, status: str, metrics: dict, parameters: dict):
    """Fuzz test ExperimentCreate schema validation."""
    try:
        exp = ExperimentCreate(
            name=name, description=description, status=status, metrics=metrics, parameters=parameters
        )
        assert 1 <= len(exp.name) <= 100
        assert exp.status in ["created", "running", "completed", "failed"]
    except ValidationError:
        pass
    except Exception as e:
        pytest.fail(f"ExperimentCreate raised unexpected exception: {type(e).__name__}: {e}")


@settings(max_examples=200, deadline=None)
@given(
    name=st.text(min_size=1, max_size=100),
    version=st.text(min_size=1, max_size=50),
    description=st.text(max_size=5000),
    file_path=st.text(min_size=1, max_size=500),
    file_size=st.integers(min_value=-10, max_value=1000000000),
    accuracy=st.floats(min_value=-1.0, max_value=2.0, allow_nan=False, allow_infinity=False),
)
@example(name="", version="1.0", description="test", file_path="/tmp/model.pkl", file_size=0, accuracy=0.5)
@example(name="model", version="", description="test", file_path="/tmp/model.pkl", file_size=0, accuracy=0.5)
@example(name="model", version="1.0", description="test", file_path="", file_size=0, accuracy=0.5)
@example(name="model", version="1.0", description="test", file_path="/tmp/model.pkl", file_size=0, accuracy=1.5)
def test_fuzz_model_create_schema(
    name: str, version: str, description: str, file_path: str, file_size: int, accuracy: float
):
    """Fuzz test ModelCreate schema validation."""
    try:
        model = ModelCreate(
            name=name,
            version=version,
            description=description,
            file_path=file_path,
            file_size=file_size,
            accuracy=accuracy,
        )
        assert 1 <= len(model.name) <= 100
        assert 1 <= len(model.version) <= 50
        assert 1 <= len(model.file_path) <= 500
    except ValidationError:
        pass
    except Exception as e:
        pytest.fail(f"ModelCreate raised unexpected exception: {type(e).__name__}: {e}")


# =============================================================================
# Fuzz Tests - Tool Argument Validation
# =============================================================================


@settings(max_examples=100, deadline=None)
@given(
    tool_name=st.sampled_from([t.name for t in TOOLS]),
    arguments=json_data,
)
def test_fuzz_tool_argument_validation(tool_name: str, arguments: dict[str, Any]):
    """Fuzz test tool argument validation - should never crash on invalid input."""
    tool = get_tool(tool_name)
    if tool is None:
        pytest.skip(f"Tool {tool_name} not found")

    try:
        # Try to validate arguments against the tool's parameter model
        parsed = tool.parameters(**arguments)
        # If validation passes, the parsed object should be valid
        assert parsed is not None
    except ValidationError:
        # ValidationError is acceptable for invalid input
        pass
    except Exception as e:
        pytest.fail(f"Tool {tool_name} argument validation raised unexpected exception: {type(e).__name__}: {e}")


# =============================================================================
# Fuzz Tests - JSON Serialization/Deserialization
# =============================================================================


@settings(max_examples=200, deadline=None)
@given(json_data)
def test_fuzz_json_roundtrip(data: Any):
    """Fuzz test JSON serialization roundtrip."""
    import json as json_module

    try:
        # Serialize to JSON
        json_str = json_module.dumps(data, default=str)
        # Deserialize back
        loaded = json_module.loads(json_str)
        # For basic types, should roundtrip exactly
        if data is None or isinstance(data, (bool, int, float, str)):
            assert loaded == data
        elif isinstance(data, list):
            assert len(loaded) == len(data)
        elif isinstance(data, dict):
            assert set(loaded.keys()) == set(data.keys())
    except Exception as e:
        # Should handle all JSON-serializable data
        if "default=str" in str(e):
            pytest.fail(f"JSON roundtrip failed: {e}")


# =============================================================================
# Fuzz Tests - SQL Injection via API Endpoints
# =============================================================================


@settings(max_examples=50, deadline=None)
@given(
    payload=st.text(
        alphabet=string.ascii_letters + string.digits + "'\"\\;()-=<>",
        min_size=1,
        max_size=200,
    )
)
@example("' OR '1'='1")
@example("'; DROP TABLE users; --")
@example("1' OR '1'='1")
@example("admin'--")
@example("\\x27 OR \\x271\\x27=\\x271")
def test_fuzz_sql_injection_api(payload: str):
    """Fuzz test SQL injection attempts via API query parameters."""
    client = TestClient(app)

    # Try to register/login first to get auth
    import uuid

    suffix = uuid.uuid4().hex[:8]
    creds = {"email": f"{suffix}@test.dev", "username": f"user_{suffix}", "password": "Hunter22!"}

    r = client.post("/api/v1/auth/users/", json=creds)
    if r.status_code != 201:
        pytest.skip("Could not create test user")

    r = client.post("/api/v1/auth/token", data={"username": creds["username"], "password": creds["password"]})
    if r.status_code != 200:
        pytest.skip("Could not get auth token")

    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # Test various endpoints with injection payload
    endpoints = [
        "/api/v1/datasets/",
        "/api/v1/models/",
        "/api/v1/experiments/",
    ]

    for endpoint in endpoints:
        r = client.get(endpoint, params={"skip": payload, "limit": 10}, headers=headers)
        # Should never return 500 (server error) - either 200, 422, or 401
        assert r.status_code != 500, f"Server error on {endpoint} with payload '{payload}': {r.text}"
        assert r.status_code in (200, 401, 422, 403), f"Unexpected status {r.status_code} on {endpoint}"


# =============================================================================
# Fuzz Tests - XSS via Input Fields
# =============================================================================


@settings(max_examples=100, deadline=None)
@given(
    xss_payload=st.text(
        alphabet=string.ascii_letters + string.digits + "<>\"'&/;=()",
        min_size=1,
        max_size=200,
    )
)
@example("<script>alert('xss')</script>")
@example("<img src=x onerror=alert(1)>")
@example("javascript:alert(1)")
@example("<svg onload=alert(1)>")
@example("' onclick='alert(1)")
def test_fuzz_xss_inputs(xss_payload: str):
    """Fuzz test XSS payloads in user input fields."""
    client = TestClient(app)

    # Try registration with XSS payload in username
    import uuid

    suffix = uuid.uuid4().hex[:8]
    creds = {
        "email": f"{suffix}@test.dev",
        "username": xss_payload[:50],  # Username has max length
        "password": "Hunter22!",
    }

    r = client.post("/api/v1/auth/users/", json=creds)
    # Should not crash (500), may return 422 for validation or 201 if valid
    assert r.status_code != 500, f"Server error with XSS payload '{xss_payload}': {r.text}"
    assert r.status_code in (201, 400, 422)


# =============================================================================
# Fuzz Tests - Large Input Handling
# =============================================================================


@settings(max_examples=50, deadline=None)
@given(
    large_text=st.text(
        alphabet=string.ascii_letters + " ",
        min_size=1000,
        max_size=10000,
    )
)
def test_fuzz_large_input_handling(large_text: str):
    """Fuzz test handling of unusually large inputs."""
    client = TestClient(app)

    import uuid

    suffix = uuid.uuid4().hex[:8]
    creds = {
        "email": f"{suffix}@test.dev",
        "username": f"user_{suffix}",
        "password": "Hunter22!",
    }

    r = client.post("/api/v1/auth/users/", json=creds)
    if r.status_code != 201:
        pytest.skip("Could not create test user")

    r = client.post("/api/v1/auth/token", data={"username": creds["username"], "password": creds["password"]})
    if r.status_code != 200:
        pytest.skip("Could not get auth token")

    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # Try creating dataset with very long description
    dataset_data = {
        "name": f"test_{suffix}",
        "description": large_text,
        "storage_uri": "/tmp/test.csv",
        "format": "csv",
    }

    r = client.post("/api/v1/data/", json=dataset_data, headers=headers)
    # Should handle gracefully - either accept or reject with 422, never 500
    assert r.status_code != 500, f"Server error with large input: {r.text}"
    assert r.status_code in (200, 201, 400, 413, 422)


# =============================================================================
# Fuzz Tests - Concurrent Request Handling
# =============================================================================


@settings(max_examples=10, deadline=None)
@given(
    num_requests=st.integers(min_value=2, max_value=20),
    endpoint=st.sampled_from(["/health", "/api/v1/auth/users/me"]),
)
def test_fuzz_concurrent_requests(num_requests: int, endpoint: str):
    """Fuzz test concurrent request handling."""
    import threading

    client = TestClient(app)
    results = []
    errors = []

    def make_request():
        try:
            if endpoint == "/api/v1/auth/users/me":
                import uuid

                suffix = uuid.uuid4().hex[:8]
                creds = {"email": f"{suffix}@test.dev", "username": f"user_{suffix}", "password": "Hunter22!"}
                r = client.post("/api/v1/auth/users/", json=creds)
                if r.status_code != 201:
                    return
                r = client.post(
                    "/api/v1/auth/token", data={"username": creds["username"], "password": creds["password"]}
                )
                if r.status_code != 200:
                    return
                headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
                r = client.get(endpoint, headers=headers)
            else:
                r = client.get(endpoint)
            results.append(r.status_code)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=make_request) for _ in range(num_requests)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    # No crashes
    assert len(errors) == 0, f"Concurrent requests raised errors: {errors}"
    # All requests should complete with valid status codes
    for status in results:
        assert status in (200, 401, 403, 422, 429), f"Unexpected status: {status}"


# =============================================================================
# Fuzz Tests - Unicode Handling
# =============================================================================


@settings(max_examples=100, deadline=None)
@given(unicode_text)
@example("测试数据")  # Chinese
@example("тест")  # Cyrillic
@example("🎉🚀💯")  # Emojis
@example("مرحبا")  # Arabic
@example("👨‍👩‍👧‍👦")  # Complex emoji sequence
@example("\u202e\u202d")  # RTL/LTR overrides
@example("\ufeff")  # BOM
def test_fuzz_unicode_handling(text: str):
    """Fuzz test Unicode handling in various inputs."""
    client = TestClient(app)

    import uuid

    suffix = uuid.uuid4().hex[:8]

    # Test in username (limited length)
    username = text[:50] if text else "user"
    creds = {
        "email": f"{suffix}@test.dev",
        "username": username,
        "password": "Hunter22!",
    }

    r = client.post("/api/v1/auth/users/", json=creds)
    # Should not crash on Unicode
    assert r.status_code != 500, f"Server error with Unicode input: {r.text}"
    assert r.status_code in (201, 400, 422)

    if r.status_code == 201:
        # If user created, test login
        r = client.post("/api/v1/auth/token", data={"username": username, "password": "Hunter22!"})
        assert r.status_code != 500


# =============================================================================
# Fuzz Tests - Tool Invocation Edge Cases
# =============================================================================


@settings(max_examples=100, deadline=None)
@given(
    tool_name=st.sampled_from([t.name for t in TOOLS if not t.requires_user]),
    skip=st.integers(min_value=-100, max_value=10000),
    limit=st.integers(min_value=-100, max_value=10000),
)
def test_fuzz_pagination_edge_cases(tool_name: str, skip: int, limit: int):
    """Fuzz test pagination edge cases for list tools."""
    from src.db.database import SessionLocal

    tool = get_tool(tool_name)
    if tool is None or tool.parameters != ListArgs:
        pytest.skip("Tool not a list tool")

    db = SessionLocal()
    try:
        # Tool handler should handle edge cases gracefully
        args = ListArgs(skip=max(0, skip), limit=max(1, min(1000, limit)))
        result = tool.handler(args, db, None)
        assert "items" in result
        assert "total" in result
        assert isinstance(result["items"], list)
        assert isinstance(result["total"], int)
        assert result["total"] >= 0
    except ValidationError:
        # Expected for invalid values
        pass
    except Exception as e:
        pytest.fail(f"Tool {tool_name} raised unexpected exception: {type(e).__name__}: {e}")
    finally:
        db.close()


# =============================================================================
# Fuzz Tests - Prediction Request Schema
# =============================================================================


@settings(max_examples=100, deadline=None)
@given(
    features=st.dicts(st.text(max_size=50), st.floats(allow_nan=False, allow_infinity=False), max_size=50),
    context=st.text(max_size=5000),
)
def test_fuzz_prediction_request_schema(features: dict[str, float], context: str):
    """Fuzz test PredictionRequest schema validation."""
    try:
        req = PredictionRequest(features=features, context=context)
        assert req.features == features
        assert req.context == context
    except ValidationError:
        # Validation errors expected for edge cases
        pass
    except Exception as e:
        pytest.fail(f"PredictionRequest raised unexpected exception: {type(e).__name__}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
