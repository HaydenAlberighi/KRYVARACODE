"""KRYVARACODE Omega-Prime — Coordination Layer.

Multi-agent orchestration modules based on the NVIDIA Multi-Agent Intelligent
Warehouse blueprint.  Provides inter-agent messaging, priority task scheduling,
and shared state management.

Modules:
    message_bus  — async pub/sub with topic routing
    task_queue   — priority queue with deps, retry, dead-letter
    shared_state — versioned key-value store with TTL & observers
    coordinator  — agent lifecycle and health management
"""

from __future__ import annotations

from src.agent.coordination.coordinator import AgentCoordinator, coordinator
from src.agent.coordination.message_bus import (
    Message,
    MessageBus,
    MessageType,
    Subscription,
    message_bus,
)
from src.agent.coordination.shared_state import (
    SharedState,
    StateChangeType,
    StateEntry,
    shared_state,
)
from src.agent.coordination.task_queue import (
    QueueTask,
    RetryPolicy,
    TaskQueue,
    TaskStatus,
    task_queue,
)

__all__ = [
    # message_bus
    "MessageBus",
    "Message",
    "MessageType",
    "Subscription",
    "message_bus",
    # task_queue
    "TaskQueue",
    "QueueTask",
    "RetryPolicy",
    "TaskStatus",
    "task_queue",
    # shared_state
    "SharedState",
    "StateEntry",
    "StateChangeType",
    "shared_state",
    # coordinator
    "AgentCoordinator",
    "coordinator",
]
