"""NVIDIA Multi-Agent Warehouse Blueprint — Shared State.

Thread-safe key-value store with versioned entries, TTL-based expiry,
change notifications, and atomic operations for inter-agent coordination.

Part of the KRYVARACODE Omega-Prime coordination layer.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# ── Data Models ──────────────────────────────────────────────────────────────


@dataclass
class StateEntry:
    """Versioned key-value entry with optional TTL."""

    key: str
    value: Any
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    ttl_seconds: float | None = None
    created_by: str = "system"


class StateChangeType(StrEnum):
    """Type of state change event."""

    SET = "set"
    DELETE = "delete"
    EXPIRED = "expired"


@dataclass
class StateChangeEvent:
    """Record of a mutation to shared state."""

    change_type: StateChangeType
    key: str
    value: Any | None
    old_value: Any | None
    version: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    source: str = ""


# ── Shared State ─────────────────────────────────────────────────────────────


class SharedState:
    """Thread-safe key-value store with change notifications and TTL.

    Uses :class:`threading.Lock` for synchronous safety, and exposes
    ``async`` methods for integration with the asyncio event loop.

    Example::

        state = SharedState()


        async def on_change(evt: StateChangeEvent) -> None:
            print(f"Changed: {evt.key}")


        state.observe(on_change)
        await state.set("agent.heartbeat", {"ts": 1}, source="sovereign")
    """

    def __init__(self) -> None:
        self._store: dict[str, StateEntry] = {}
        self._lock = threading.Lock()
        self._change_log: deque[StateChangeEvent] = deque(maxlen=1000)
        self._observers: list[Callable[[StateChangeEvent], Awaitable[None]]] = []
        self._cleanup_task: asyncio.Task[None] | None = None

    # ── Core CRUD ────────────────────────────────────────────────────────

    async def set(
        self,
        key: str,
        value: Any,
        source: str = "system",
        ttl_seconds: float | None = None,
    ) -> StateEntry:
        """Set or update *key* with *value*.

        Existing entries are version-incremented.  New entries start at
        version 1.  Observers are notified of the change.
        """
        with self._lock:
            old_value: Any = None
            now = datetime.now(tz=UTC)

            if key in self._store:
                entry = self._store[key]
                old_value = entry.value
                entry.value = value
                entry.version += 1
                entry.updated_at = now
                if ttl_seconds is not None:
                    entry.ttl_seconds = ttl_seconds
                entry.created_by = source
            else:
                entry = StateEntry(
                    key=key,
                    value=value,
                    created_at=now,
                    updated_at=now,
                    ttl_seconds=ttl_seconds,
                    created_by=source,
                )
                self._store[key] = entry

            version = entry.version

        event = StateChangeEvent(
            change_type=StateChangeType.SET,
            key=key,
            value=value,
            old_value=old_value,
            version=version,
            source=source,
        )
        self._change_log.append(event)
        await self._notify_observers(event)
        logger.debug("set(%s) v%d by %s", key, version, source)
        return entry

    async def get(self, key: str) -> Any | None:
        """Return the value for *key*, or ``None`` if missing / expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if self._is_expired(entry):
                self._delete_unlocked(key)
                return None
            return entry.value

    async def get_entry(self, key: str) -> StateEntry | None:
        """Return the full :class:`StateEntry` or ``None``."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if self._is_expired(entry):
                self._delete_unlocked(key)
                return None
            return entry

    async def delete(self, key: str, source: str = "system") -> bool:
        """Remove *key*.  Returns ``True`` if it existed."""
        with self._lock:
            old_value = None
            version = 0
            if key in self._store:
                old_value = self._store[key].value
                version = self._store[key].version
                self._delete_unlocked(key)
            else:
                return False

        event = StateChangeEvent(
            change_type=StateChangeType.DELETE,
            key=key,
            value=None,
            old_value=old_value,
            version=version,
            source=source,
        )
        self._change_log.append(event)
        await self._notify_observers(event)
        logger.debug("delete(%s) by %s", key, source)
        return True

    async def exists(self, key: str) -> bool:
        """Return ``True`` if *key* exists and is not expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            if self._is_expired(entry):
                self._delete_unlocked(key)
                return False
            return True

    async def keys(self) -> list[str]:
        """Return all non-expired keys."""
        with self._lock:
            self._sweep_expired_unlocked()
            return list(self._store.keys())

    async def items(self) -> dict[str, Any]:
        """Return all non-expired key-value pairs."""
        with self._lock:
            self._sweep_expired_unlocked()
            return {k: e.value for k, e in self._store.items()}

    async def clear(self, source: str = "system") -> int:
        """Clear all entries.  Returns the count removed."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
        if count > 0:
            logger.debug("clear(%s) removed %d entries", source, count)
        return count

    # ── Atomic Operations ────────────────────────────────────────────────

    async def atomic_update(
        self,
        key: str,
        updater_fn: Callable[[Any], Any],
        source: str = "system",
    ) -> Any | None:
        """Atomically get-modify-set under the lock.

        *updater_fn* receives the current value and returns the new value.
        Returns the new value or ``None`` if the key is missing.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if self._is_expired(entry):
                self._delete_unlocked(key)
                return None
            old_value = entry.value
            new_value = updater_fn(entry.value)
            entry.value = new_value
            entry.version += 1
            entry.updated_at = datetime.now(tz=UTC)
            entry.created_by = source
            version = entry.version

        event = StateChangeEvent(
            change_type=StateChangeType.SET,
            key=key,
            value=new_value,
            old_value=old_value,
            version=version,
            source=source,
        )
        self._change_log.append(event)
        await self._notify_observers(event)
        return new_value

    async def compare_and_set(
        self,
        key: str,
        expected: Any,
        new_value: Any,
        source: str = "system",
    ) -> bool:
        """Compare-and-swap: set *new_value* only if current value equals *expected*."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            if self._is_expired(entry):
                self._delete_unlocked(key)
                return False
            if entry.value != expected:
                return False
            old_value = entry.value
            entry.value = new_value
            entry.version += 1
            entry.updated_at = datetime.now(tz=UTC)
            entry.created_by = source
            version = entry.version

        event = StateChangeEvent(
            change_type=StateChangeType.SET,
            key=key,
            value=new_value,
            old_value=old_value,
            version=version,
            source=source,
        )
        self._change_log.append(event)
        await self._notify_observers(event)
        return True

    # ── Observer Pattern ─────────────────────────────────────────────────

    def observe(self, callback: Callable[[StateChangeEvent], Awaitable[None]]) -> None:
        """Register an async callback for state changes."""
        self._observers.append(callback)

    def unobserve(self, callback: Callable[[StateChangeEvent], Awaitable[None]]) -> None:
        """Remove a previously registered callback."""
        self._observers = [o for o in self._observers if o is not callback]

    async def _notify_observers(self, event: StateChangeEvent) -> None:
        """Fan-out *event* to all registered observers."""
        for obs in self._observers:
            try:
                await obs(event)
            except Exception:
                logger.exception("Observer error for key=%s", event.key)

    # ── History & Stats ──────────────────────────────────────────────────

    def get_change_history(self, limit: int = 50) -> list[StateChangeEvent]:
        """Return up to *limit* most recent state changes."""
        return list(self._change_log)[-limit:]

    def get_stats(self) -> dict[str, int]:
        """Summary statistics about the store."""
        with self._lock:
            expired = sum(1 for e in self._store.values() if self._is_expired(e))
            return {
                "total_keys": len(self._store),
                "expired_pending": expired,
                "total_changes": len(self._change_log),
                "observer_count": len(self._observers),
            }

    # ── TTL Management ───────────────────────────────────────────────────

    def _is_expired(self, entry: StateEntry) -> bool:
        """Check if *entry* has exceeded its TTL."""
        if entry.ttl_seconds is None:
            return False
        elapsed = (datetime.now(tz=UTC) - entry.updated_at).total_seconds()
        return elapsed > entry.ttl_seconds

    def _delete_unlocked(self, key: str) -> None:
        """Remove a key under an already-held lock (no notification)."""
        self._store.pop(key, None)

    def _sweep_expired_unlocked(self) -> None:
        """Remove all expired entries under an already-held lock."""
        expired_keys = [k for k, e in self._store.items() if self._is_expired(e)]
        for k in expired_keys:
            self._store.pop(k, None)

    async def _cleanup_expired(self) -> None:
        """Sweep expired entries and notify observers."""
        with self._lock:
            expired_entries = [(k, e) for k, e in self._store.items() if self._is_expired(e)]
            for k, _e in expired_entries:
                self._store.pop(k, None)

        for _key, entry in expired_entries:
            event = StateChangeEvent(
                change_type=StateChangeType.EXPIRED,
                key=entry.key,
                value=None,
                old_value=entry.value,
                version=entry.version,
                source="ttl_cleanup",
            )
            self._change_log.append(event)
            await self._notify_observers(event)

        if expired_entries:
            logger.debug("cleanup_expired: removed %d entries", len(expired_entries))

    async def start_ttl_cleanup(self, interval: float = 30.0) -> None:
        """Start a background task that periodically sweeps expired entries."""
        if self._cleanup_task is not None:
            return

        async def _loop() -> None:
            while True:
                await asyncio.sleep(interval)
                await self._cleanup_expired()

        self._cleanup_task = asyncio.create_task(_loop())
        logger.info("TTL cleanup started (interval=%.1fs)", interval)

    def stop_ttl_cleanup(self) -> None:
        """Stop the background TTL cleanup task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            self._cleanup_task = None
            logger.info("TTL cleanup stopped")


# ── Module Singleton ─────────────────────────────────────────────────────────

shared_state = SharedState()
