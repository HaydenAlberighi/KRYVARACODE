"""NVIDIA Multi-Agent Warehouse Blueprint — Message Bus.

Async pub/sub message bus for inter-agent communication with topic-based
routing, wildcard subscriptions, message history, and sync/async publishing.

Part of the KRYVARACODE Omega-Prime coordination layer.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# ── Data Models ─────────────────────────────────────────────────────────────


class MessageType(StrEnum):
    """Category of inter-agent message."""

    AGENT_MSG = "agent_msg"
    TASK_REQUEST = "task_request"
    TASK_RESULT = "task_result"
    STATE_UPDATE = "state_update"
    HEARTBEAT = "heartbeat"
    SYSTEM = "system"


@dataclass
class Message:
    """Envelope for inter-agent communication."""

    topic: str
    sender: str
    payload: dict[str, Any]
    msg_type: MessageType = MessageType.SYSTEM
    message_id: str = field(default_factory=lambda: uuid4().hex)
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    priority: int = 0
    reply_to: str | None = None


@dataclass
class Subscription:
    """Registered interest in a topic pattern."""

    subscriber_id: str
    topic_pattern: str
    callback: Callable[[Message], Awaitable[None]]
    filter_fn: Callable[[Message], bool] | None = None


# ── Message Bus ──────────────────────────────────────────────────────────────


class MessageBus:
    """Async pub/sub message bus with topic routing and wildcard support.

    Agents subscribe to topic patterns (exact match or ``*`` wildcard) and
    receive :class:`Message` objects through async callbacks.  Messages are
    dispatched from an internal queue via :meth:`start`.

    Example::

        bus = MessageBus()

        async def handler(msg: Message) -> None:
            print(f"Got {msg.topic}: {msg.payload}")

        bus.subscribe("agent_1", "agent.sovereign.*", handler)
        await bus.start()
        await bus.publish(Message(topic="agent.sovereign.task_complete", sender="sovereign", payload={}))
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Subscription]] = {}
        self._queue: asyncio.Queue[Message] = asyncio.Queue()
        self._running: bool = False
        self._dispatch_task: asyncio.Task[None] | None = None
        self._history: deque[Message] = deque(maxlen=1000)

    # ── Subscription Management ──────────────────────────────────────────

    def subscribe(
        self,
        subscriber_id: str,
        topic_pattern: str,
        callback: Callable[[Message], Awaitable[None]],
        filter_fn: Callable[[Message], bool] | None = None,
    ) -> Subscription:
        """Register a callback for messages matching *topic_pattern*.

        The pattern ``"*"`` matches every topic.  An optional *filter_fn*
        further qualifies delivery.

        Returns the :class:`Subscription` handle (pass to :meth:`unsubscribe`).
        """
        sub = Subscription(
            subscriber_id=subscriber_id,
            topic_pattern=topic_pattern,
            callback=callback,
            filter_fn=filter_fn,
        )
        self._subscribers.setdefault(topic_pattern, []).append(sub)
        logger.info("subscribe(%s -> %s)", subscriber_id, topic_pattern)
        return sub

    def unsubscribe(self, subscription: Subscription) -> None:
        """Remove a previously registered *subscription*."""
        subs = self._subscribers.get(subscription.topic_pattern, [])
        self._subscribers[subscription.topic_pattern] = [
            s for s in subs if s is not subscription
        ]
        if not self._subscribers[subscription.topic_pattern]:
            del self._subscribers[subscription.topic_pattern]
        logger.info("unsubscribe(%s)", subscription.subscriber_id)

    # ── Publishing ───────────────────────────────────────────────────────

    async def publish(self, message: Message) -> None:
        """Enqueue *message* for asynchronous dispatch."""
        await self._queue.put(message)
        logger.debug("publish(%s) -> %s", message.topic, message.message_id)

    def publish_sync(self, message: Message) -> None:
        """Thread-safe publish from non-async contexts."""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(self._queue.put_nowait, message)
        else:
            loop.run_until_complete(self._queue.put(message))
        logger.debug("publish_sync(%s) -> %s", message.topic, message.message_id)

    # ── Dispatch Loop ────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the background dispatch loop."""
        if self._running:
            return
        self._running = True
        self._dispatch_task = asyncio.create_task(self._dispatch_loop())
        logger.info("MessageBus started")

    async def stop(self) -> None:
        """Stop the dispatch loop and wait for the task to finish."""
        self._running = False
        if self._dispatch_task is not None:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
            self._dispatch_task = None
        logger.info("MessageBus stopped")

    async def _dispatch_loop(self) -> None:
        """Pull messages from the queue and fan-out to matching subscribers."""
        while self._running:
            try:
                message = await self._queue.get()
            except asyncio.CancelledError:
                break

            self._history.append(message)

            for pattern, subs in list(self._subscribers.items()):
                for sub in subs:
                    if not self._topic_matches(message.topic, pattern):
                        continue
                    if sub.filter_fn is not None and not sub.filter_fn(message):
                        continue
                    try:
                        result = sub.callback(message)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        logger.exception(
                            "Subscriber %s failed on topic %s",
                            sub.subscriber_id,
                            message.topic,
                        )

    # ── History & Stats ──────────────────────────────────────────────────

    def get_history(self, topic: str | None = None, limit: int = 50) -> list[Message]:
        """Return recent messages, optionally filtered by *topic*."""
        msgs = list(self._history)
        if topic is not None:
            msgs = [m for m in msgs if m.topic == topic]
        return msgs[-limit:]

    @property
    def pending_count(self) -> int:
        """Number of messages waiting in the dispatch queue."""
        return self._queue.qsize()

    @property
    def subscriber_count(self) -> int:
        """Total number of active subscriptions."""
        return sum(len(subs) for subs in self._subscribers.values())

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _topic_matches(topic: str, pattern: str) -> bool:
        """Check whether *topic* matches a subscription *pattern*.

        ``"*"`` matches everything.  A pattern like ``"agent.*"`` matches
        ``"agent.sovereign"`` but not ``"agent.sovereign.task"``.  Full
        prefix matching with ``"agent.**"`` would match both (future).
        """
        if pattern == "*":
            return True
        if "**" in pattern:
            prefix = pattern.replace("**", "").rstrip(".")
            return topic.startswith(prefix)
        return topic == pattern


# ── Module Singleton ─────────────────────────────────────────────────────────

message_bus = MessageBus()
