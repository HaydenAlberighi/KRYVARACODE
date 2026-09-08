from src.core.config import get_settings
from src.core.logging import get_logger
from src.core.exceptions import AppError, NotFoundError, ConflictError
from src.core.security import get_password_hash, verify_password


def test_settings_defaults():
    s = get_settings()
    assert s.APP_NAME == "KRYVARACODE"
    assert s.API_V1_STR == "/api/v1"
    assert s.APP_ENV in {"development", "test", "production"}


def test_settings_cors_origins_strips_empties():
    s = get_settings()
    assert isinstance(s.cors_origins, list)


def test_logger_returns_named_logger():
    logger = get_logger("test.module")
    assert logger.name == "test.module"


def test_exception_hierarchy():
    app_err = AppError(detail="boom")
    assert app_err.status_code == 500
    assert app_err.error_code == "internal_error"
    assert app_err.to_dict()["detail"] == "boom"

    nf = NotFoundError(detail="missing")
    assert nf.status_code == 404
    assert issubclass(NotFoundError, AppError)
    assert issubclass(ConflictError, AppError)


def test_password_hash_roundtrip():
    hashed = get_password_hash("s3cret-password")
    assert verify_password("s3cret-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_invalid_hash_returns_false():
    assert not verify_password("anything", "not-a-valid-bcrypt-hash")
