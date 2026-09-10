"""NVIDIA Multi-Agent Warehouse Blueprint — Coordinator.

Agent lifecycle management: registration, health monitoring, graceful
shutdown, and task routing built on top of the message bus, task queue,
and shared state primitives.

Part of the KRYVARACODE Omega-Prime coordination layer.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from src.agent.coordination.message_bus import Message, MessageType, message_bus
from src.agent.coordination.shared_state import SharedState, shared_state
from src.agent.coordination.task_queue import QueueTask, task_queue

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

HEARTBEAT_INTERVAL: float = 15.0
HEARTBEAT_TIMEOUT: float = 45.0


# ── Agent Registry ───────────────────────────────────────────────────────────


class AgentStatus(StrEnum):
    """Lifecycle status for a registered agent."""

    REGISTERED = "registered"
    STARTING = "starting"
    ACTIVE = "active"
    IDLE = "idle"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class AgentInfo:
    """Metadata for a single registered agent."""

    name: str
    status: AgentStatus = AgentStatus.REGISTERED
    capabilities: list[str] = field(default_factory=list)
    registered_at: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    last_heartbeat: datetime = field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    tasks_completed: int = 0
    tasks_failed: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Coordinator ──────────────────────────────────────────────────────────────


class AgentCoordinator:
    """Manages agent lifecycle: registration, health, and task routing.

    Built on the three coordination primitives:

    * **MessageBus** — heartbeats and status broadcasts.
    * **SharedState** — agent registry and configuration.
    * **TaskQueue** — work dispatch and completion tracking.

    Example::

        coord = AgentCoordinator()
        await coord.start()
        await coord.register_agent("sovereign", capabilities=["goal", "reason"])
        # ... later ...
        await coord.stop()
    """

    def __init__(
        self,
        bus: Any | None = None,
        state: SharedState | None = None,
        queue: Any | None = None,
    ) -> None:
        self._bus = bus or message_bus
        self._state = state or shared_state
        self._queue = queue or task_queue
        self._agents: dict[str, AgentInfo] = {}
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._running: bool = False

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the coordinator (message bus + heartbeat monitor)."""
        if self._running:
            return
        self._running = True
        await self._bus.start()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("AgentCoordinator started")

    async def stop(self) -> None:
        """Gracefully shut down all agents and the coordinator."""
        self._running = False
        for name in list(self._agents):
            await self.deregister_agent(name)
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        await self._bus.stop()
        logger.info("AgentCoordinator stopped")

    # ── Agent Management ─────────────────────────────────────────────────

    async def register_agent(
        self,
        name: str,
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentInfo:
        """Register a new agent with the coordinator."""
        info = AgentInfo(
            name=name,
            capabilities=capabilities or [],
            metadata=metadata or {},
        )
        self._agents[name] = info
        await self._state.set(
            f"agent.{name}.status",
            AgentStatus.REGISTERED.value,
            source="coordinator",
        )
        await self._state.set(
            f"agent.{name}.capabilities",
            info.capabilities,
            source="coordinator",
        )
        await self._bus.publish(
            Message(
                topic="coordinator.agent.registered",
                sender="coordinator",
                payload={"agent": name, "capabilities": info.capabilities},
                msg_type=MessageType.AGENT_MSG,
            )
        )
        logger.info("register_agent(%s) caps=%s", name, info.capabilities)
        return info

    async def deregister_agent(self, name: str) -> bool:
        """Remove an agent from the coordinator.  Returns ``True`` if found."""
        if name not in self._agents:
            return False
        info = self._agents[name]
        info.status = AgentStatus.STOPPING
        await self._state.set(
            f"agent.{name}.status",
            AgentStatus.STOPPED.value,
            source="coordinator",
        )
        await self._bus.publish(
            Message(
                topic="coordinator.agent.deregistered",
                sender="coordinator",
                payload={"agent": name},
                msg_type=MessageType.AGENT_MSG,
            )
        )
        del self._agents[name]
        logger.info("deregister_agent(%s)", name)
        return True

    def get_agent(self, name: str) -> AgentInfo | None:
        """Look up an agent by name."""
        return self._agents.get(name)

    def list_agents(self) -> list[AgentInfo]:
        """Return metadata for all registered agents."""
        return list(self._agents.values())

    # ── Heartbeats ───────────────────────────────────────────────────────

    async def heartbeat(self, agent_name: str) -> None:
        """Called by agents to signal liveness."""
        info = self._agents.get(agent_name)
        if info is None:
            logger.warning("heartbeat from unknown agent %s", agent_name)
            return
        info.last_heartbeat = datetime.now(tz=timezone.utc)
        if info.status in (AgentStatus.REGISTERED, AgentStatus.DEGRADED):
            info.status = AgentStatus.ACTIVE
        await self._state.set(
            f"agent.{agent_name}.heartbeat",
            info.last_heartbeat.timestamp(),
            source=agent_name,
        )

    async def _heartbeat_loop(self) -> None:
        """Periodically check for stale agents."""
        while self._running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            now = time.time()
            for info in self._agents.values():
                elapsed = now - info.last_heartbeat.timestamp()
                if elapsed > HEARTBEAT_TIMEOUT:
                    if info.status != AgentStatus.DEGRADED:
                        info.status = AgentStatus.DEGRADED
                        logger.warning(
                            "Agent %s degraded (no heartbeat for %.0fs)",
                            info.name,
                            elapsed,
                        )

    # ── Task Routing ─────────────────────────────────────────────────────

    async def submit_task(
        self,
        task: QueueTask,
        target_agent: str | None = None,
    ) -> str:
        """Submit a *task* to the queue, optionally targeting a specific agent."""
        if target_agent and target_agent not in self._agents:
            raise ValueError(f"Unknown agent: {target_agent}")
        task_id = self._queue.add_task(task)
        await self._bus.publish(
            Message(
                topic="coordinator.task.submitted",
                sender="coordinator",
                payload={"task_id": task_id, "target": target_agent},
                msg_type=MessageType.TASK_REQUEST,
            )
        )
        return task_id

    async def complete_task(self, task_id: str, result: Any = None) -> None:
        """Mark a task as completed and broadcast the result."""
        self._queue.mark_completed(task_id, result)
        await self._bus.publish(
            Message(
                topic="coordinator.task.completed",
                sender="coordinator",
                payload={"task_id": task_id, "result": result},
                msg_type=MessageType.TASK_RESULT,
            )
        )

    async def fail_task(self, task_id: str, error: str) -> None:
        """Mark a task as failed (with retry logic) and broadcast."""
        self._queue.mark_failed(task_id, error)
        await self._bus.publish(
            Message(
                topic="coordinator.task.failed",
                sender="coordinator",
                payload={"task_id": task_id, "error": error},
                msg_type=MessageType.TASK_RESULT,
            )
        )

    # ── Stats ────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Coordinator and queue statistics."""
        return {
            "agents": len(self._agents),
            "active_agents": sum(
                1 for a in self._agents.values() if a.status == AgentStatus.ACTIVE
            ),
            "task_queue": self._queue.stats(),
            "dead_letters": self._queue.dead_letter_count,
        }


# ── Module Singleton ─────────────────────────────────────────────────────────

coordinator = AgentCoordinator()
