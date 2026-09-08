"""
Logging configuration for KRYVARACODE.

Provides a single ``setup_logging`` entry point that configures the standard
:mod:`logging` module with:

- a colored console handler (human-readable in dev)
- a rotating file handler under ``logs/``
- consistent structured format: timestamp | level | logger | message

Importable as ``from src.core.logging import get_logger``.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from src.core.config import settings
from src.utils.helpers import ensure_dir

_LOGGING_CONFIGURED = False

CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
FILE_FORMAT = CONSOLE_FORMAT


def _level_from_settings() -> int:
    level = (settings.LOG_LEVEL or "INFO").upper()
    return getattr(logging, level, logging.INFO)


def _console_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    return handler


def _file_handler(log_dir: Optional[Path] = None) -> logging.Handler:
    directory = log_dir or Path("logs")
    ensure_dir(str(directory))
    handler = RotatingFileHandler(
        directory / "kryvaracode.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(FILE_FORMAT))
    return handler


def setup_logging(
    level: Optional[str] = None,
    log_dir: Optional[Path] = None,
    force: bool = False,
) -> None:
    """Configure the root logger once.

    Args:
        level: Optional override, e.g. "DEBUG". Defaults to settings.LOG_LEVEL.
        log_dir: Optional directory for the rotating file handler.
        force: Reconfigure even if already configured (mainly for tests).
    """
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED and not force:
        return

    effective_level = _level_from_settings()
    if level:
        effective_level = getattr(logging, level.upper(), effective_level)

    root = logging.getLogger()
    root.setLevel(effective_level)

    # Remove any pre-existing handlers (idempotent setup).
    for handler in list(root.handlers):
        root.removeHandler(handler)

    root.addHandler(_console_handler())
    root.addHandler(_file_handler(log_dir=log_dir))

    # Friendlier uvicorn access logs inherit the root config.
    logging.getLogger("uvicorn").handlers.clear()
    logging.getLogger("uvicorn.error").handlers.clear()
    logging.getLogger("uvicorn.access").handlers.clear()

    # Quiet noisy third-party loggers by default.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    _LOGGING_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a child logger for the given module name."""
    return logging.getLogger(name)
