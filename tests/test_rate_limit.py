import time

import pytest

from src.core.rate_limit import RateLimiter, parse_rate_limit, rate_limiter


def test_parse_rate_limit_valid():
    assert parse_rate_limit("100/minute") == (100, 60)
    assert parse_rate_limit("5/second") == (5, 1)
    assert parse_rate_limit("2/hour") == (2, 3600)
    assert parse_rate_limit("10/day") == (10, 86400)
    assert parse_rate_limit("3/minutes") == (3, 60)


def test_parse_rate_limit_invalid():
    with pytest.raises(ValueError):
        parse_rate_limit("nope")
    with pytest.raises(ValueError):
        parse_rate_limit("10/lightyear")
    with pytest.raises(ValueError):
        parse_rate_limit("0/minute")
    with pytest.raises(ValueError):
        parse_rate_limit("100")


def test_limiter_enforces_budget_per_key():
    rl = RateLimiter(limit=2, window=10)
    assert rl.allow("a")
    assert rl.allow("a")
    assert not rl.allow("a")
    assert rl.allow("b")


def test_limiter_slides_after_window():
    rl = RateLimiter(limit=1, window=0.1)
    assert rl.allow("k")
    assert not rl.allow("k")
    time.sleep(0.15)
    assert rl.allow("k")


def test_process_limiter_disabled_by_default():
    assert rate_limiter is None
