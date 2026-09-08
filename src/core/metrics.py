"""Prometheus metrics helpers (guarded imports).

``prometheus-client`` is a declared runtime dependency, but the module is
import-safe without it: when the library is missing, all helpers degrade to
no-ops and ``/api/v1/metrics`` reports 503.  This keeps core imports working
in minimal test/CI environments.
"""

from __future__ import annotations

from typing import Any

# Type: Any so method calls stay valid regardless of availability.
Counter: Any = None
Histogram: Any = None
generate_latest: Any = None
CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

_PROMETHEUS_AVAILABLE = False
try:
    from prometheus_client import (  # type: ignore[import]
        CONTENT_TYPE_LATEST,
        Counter,
        Histogram,
        generate_latest,
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only on minimal installs
    _PROMETHEUS_AVAILABLE = False

REQUEST_COUNT: Any = None
REQUEST_DURATION: Any = None

if _PROMETHEUS_AVAILABLE:
    REQUEST_COUNT = Counter(
        "kryvaracode_requests_total",
        "Total number of HTTP requests served",
        ["method", "path", "status"],
    )
    REQUEST_DURATION = Histogram(
        "kryvaracode_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "path"],
    )


def register_request(method: str, path: str, status: int, duration_ms: float) -> None:
    """Record one completed request.  No-op when prometheus-client is absent."""
    if not _PROMETHEUS_AVAILABLE:
        return
    REQUEST_COUNT.labels(method, path, str(status)).inc()
    REQUEST_DURATION.labels(method, path).observe(duration_ms / 1000.0)


def render_metrics() -> bytes | None:
    """Return the Prometheus exposition text, or None when unavailable."""
    if not _PROMETHEUS_AVAILABLE:
        return None
    return generate_latest()
