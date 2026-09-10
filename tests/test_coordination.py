"""
Unit tests for src/agent/coordination/* and src/agent/orchestrator.py.
"""

import asyncio
from unittest.mock import Mock, patch

import pytest

from src.agent.coordination.coordinator import AgentCoordinator, AgentStatus
from src.agent.coordination.message_bus import Message, MessageBus
from src.agent.coordination.shared_state import (
    SharedState,
    StateChangeType,
    StateEntry,
)
from src.agent.coordination.task_queue import (
    QueueTask,
    RetryPolicy,
    TaskQueue,
    TaskStatus,
)


class TestMessageBus:
    """Tests for MessageBus pub/sub."""

    @pytest.fixture
    def bus(self):
        return MessageBus()

    def test_subscribe_returns_subscription(self, bus):
        sub = bus.subscribe("agent-1", "agent.*", lambda m: None)
        assert sub.subscriber_id == "agent-1"
        assert sub.topic_pattern == "agent.*"
        assert bus.subscriber_count == 1

    def test_unsubscribe_removes_subscription(self, bus):
        sub = bus.subscribe("agent-1", "agent.*", lambda m: None)
        bus.unsubscribe(sub)
        assert bus.subscriber_count == 0

    def test_topic_matches_exact(self, bus):
        assert bus._topic_matches("agent.hello", "agent.hello")
        assert not bus._topic_matches("agent.hello", "agent.world")

    def test_topic_matches_wildcard_all(self, bus):
        assert bus._topic_matches("anything.at.all", "*")

    def test_topic_matches_segment_wildcard(self, bus):
        assert bus._topic_matches("agent.hello", "agent.*")
        assert not bus._topic_matches("agent.hello.world", "agent.*")
        assert not bus._topic_matches("system.hello", "agent.*")

    def test_topic_matches_prefix(self, bus):
        assert bus._topic_matches("agent.hello.world", "agent.**")
        assert bus._topic_matches("agent.hello", "agent.**")
        assert not bus._topic_matches("other.hello", "agent.**")

    @pytest.mark.asyncio
    async def test_publish_dispatches_to_subscriber(self, bus):
        received = []
        bus.subscribe("agent-1", "agent.*", lambda m: received.append(m))
        await bus.start()
        try:
            await bus.publish(Message(topic="agent.hello", sender="test", payload={"x": 1}))
            for _ in range(10):
                if received:
                    break
                await asyncio.sleep(0.01)
            assert len(received) == 1
            assert received[0].payload == {"x": 1}
        finally:
            await bus.stop()

    @pytest.mark.asyncio
    async def test_publish_skips_non_matching(self, bus):
        received = []
        bus.subscribe("agent-1", "agent.*", lambda m: received.append(m))
        await bus.start()
        try:
            await bus.publish(Message(topic="system.boot", sender="test", payload={}))
            await asyncio.sleep(0.05)
            assert received == []
        finally:
            await bus.stop()

    @pytest.mark.asyncio
    async def test_publish_uses_filter_fn(self, bus):
        received = []

        def only_high(m: Message) -> bool:
            return m.priority >= 5

        bus.subscribe("agent-1", "*", lambda m: received.append(m), filter_fn=only_high)
        await bus.start()
        try:
            await bus.publish(Message(topic="t", sender="s", payload={}, priority=1))
            await bus.publish(Message(topic="t", sender="s", payload={"high": True}, priority=9))
            for _ in range(10):
                if len(received) >= 1:
                    break
                await asyncio.sleep(0.01)
            assert len(received) == 1
            assert received[0].payload == {"high": True}
        finally:
            await bus.stop()

    @pytest.mark.asyncio
    async def test_history_after_dispatch(self, bus):
        await bus.start()
        try:
            await bus.publish(Message(topic="agent.hello", sender="s", payload={}))
            for _ in range(10):
                if bus.pending_count == 0:
                    break
                await asyncio.sleep(0.01)
            assert bus.pending_count == 0
            history = bus.get_history("agent.hello", limit=5)
            assert len(history) == 1
            assert history[0].topic == "agent.hello"
        finally:
            await bus.stop()

    @pytest.mark.asyncio
    async def test_publish_sync_from_other_thread(self, bus):
        bus.publish_sync(Message(topic="agent.hello", sender="s", payload={}))
        await asyncio.sleep(0.05)
        assert bus.pending_count == 1


class TestTaskQueue:
    """Tests for TaskQueue scheduling."""

    @pytest.fixture
    def queue(self):
        return TaskQueue()

    def test_add_task_pending(self, queue):
        task = QueueTask(name="t1", handler=Mock())
        task_id = queue.add_task(task)
        assert task.status == TaskStatus.PENDING
        assert task.task_id == task_id

    def test_add_task_with_unmet_dependencies(self, queue):
        dep = QueueTask(name="dep", handler=Mock())
        dep_id = queue.add_task(dep)
        task = QueueTask(name="t2", handler=Mock(), dependencies=[dep_id])
        queue.add_task(task)
        assert task.status == TaskStatus.WAITING_DEPS
        assert queue.get_ready_tasks() == [dep]

    def test_ready_tasks_priority_order(self, queue):
        low = QueueTask(name="low", handler=Mock(), priority=1)
        high = QueueTask(name="high", handler=Mock(), priority=10)
        queue.add_task(low)
        queue.add_task(high)
        ready = queue.get_ready_tasks()
        assert ready == [high, low]

    def test_mark_running_and_completed(self, queue):
        task = QueueTask(name="t1", handler=Mock())
        queue.add_task(task)
        queue.mark_running(task.task_id)
        assert task.status == TaskStatus.RUNNING
        queue.mark_completed(task.task_id, result=42)
        assert task.status == TaskStatus.COMPLETED
        assert task.result == 42

    def test_completion_unblocks_dependents(self, queue):
        dep = QueueTask(name="dep", handler=Mock())
        dep_id = queue.add_task(dep)
        task = QueueTask(name="t2", handler=Mock(), dependencies=[dep_id])
        queue.add_task(task)
        assert task.status == TaskStatus.WAITING_DEPS
        queue.mark_running(dep_id)
        queue.mark_completed(dep_id)
        assert task.status == TaskStatus.PENDING

    def test_cancel_pending_task(self, queue):
        task = QueueTask(name="t1", handler=Mock())
        queue.add_task(task)
        assert queue.cancel_task(task.task_id) is True
        assert task.status == TaskStatus.CANCELLED

    def test_cannot_cancel_running_task(self, queue):
        task = QueueTask(name="t1", handler=Mock())
        queue.add_task(task)
        queue.mark_running(task.task_id)
        assert queue.cancel_task(task.task_id) is False
        assert task.status == TaskStatus.RUNNING

    @pytest.mark.asyncio
    async def test_failed_task_is_retried(self, queue):
        policy = RetryPolicy(max_retries=2, base_delay=0.0)
        task = QueueTask(name="t1", handler=Mock(), retry_policy=policy)
        queue.add_task(task)
        queue.mark_running(task.task_id)
        queue.mark_failed(task.task_id, "boom")
        assert task.status == TaskStatus.PENDING
        assert task.retries_used == 1

    @pytest.mark.asyncio
    async def test_failed_task_goes_to_dead_letter_after_max(self, queue):
        policy = RetryPolicy(max_retries=1, base_delay=0.0)
        task = QueueTask(name="t1", handler=Mock(), retry_policy=policy)
        queue.add_task(task)
        for _ in range(2):
            queue.mark_running(task.task_id)
            queue.mark_failed(task.task_id, "boom")
        assert task.status == TaskStatus.DEAD_LETTER
        assert queue.dead_letter_count == 1

    def test_clear_dead_letters(self, queue):
        policy = RetryPolicy(max_retries=0, base_delay=0.0)
        task = QueueTask(name="t1", handler=Mock(), retry_policy=policy)
        queue.add_task(task)
        queue.mark_running(task.task_id)
        queue.mark_failed(task.task_id, "boom")
        assert queue.dead_letter_count == 1
        assert queue.clear_dead_letters() == 1
        assert queue.dead_letter_count == 0

    def test_stats_counts(self, queue):
        task = QueueTask(name="t1", handler=Mock())
        queue.add_task(task)
        stats = queue.stats()
        assert stats[TaskStatus.PENDING.value] == 1
        assert stats[TaskStatus.COMPLETED.value] == 0

    def test_len(self, queue):
        queue.add_task(QueueTask(name="t1", handler=Mock()))
        assert len(queue) == 1


class TestSharedState:
    """Tests for SharedState store."""

    @pytest.fixture
    def state(self):
        return SharedState()

    @pytest.mark.asyncio
    async def test_set_and_get(self, state):
        await state.set("k", 42, source="test")
        assert await state.get("k") == 42

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, state):
        assert await state.get("missing") is None

    @pytest.mark.asyncio
    async def test_delete(self, state):
        await state.set("k", 1, source="test")
        assert await state.delete("k", source="test") is True
        assert not await state.exists("k")

    @pytest.mark.asyncio
    async def test_delete_missing_returns_false(self, state):
        assert await state.delete("missing", source="test") is False

    @pytest.mark.asyncio
    async def test_exists_and_keys(self, state):
        await state.set("a", 1, source="test")
        await state.set("b", 2, source="test")
        assert await state.exists("a")
        assert set(await state.keys()) == {"a", "b"}

    def test_is_expired_with_past_timestamp(self, state):
        import datetime

        entry = state._store.setdefault(
            "k",
            StateEntry(
                key="k",
                value="v",
                created_at=datetime.datetime.now(datetime.UTC),
            ),
        )
        entry.updated_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=10)
        entry.ttl_seconds = 5
        assert state._is_expired(entry) is True

    def test_not_expired_within_ttl(self, state):
        import datetime

        entry = state._store.setdefault(
            "k",
            StateEntry(
                key="k",
                value="v",
                created_at=datetime.datetime.now(datetime.UTC),
            ),
        )
        entry.ttl_seconds = 60
        assert state._is_expired(entry) is False

    @pytest.mark.asyncio
    async def test_sweep_expired_removes_entries(self, state):
        import datetime

        await state.set("fresh", 1, source="test", ttl_seconds=60)
        entry = state._store.setdefault(
            "stale",
            StateEntry(
                key="stale",
                value="old",
                created_at=datetime.datetime.now(datetime.UTC),
            ),
        )
        entry.updated_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=30)
        entry.ttl_seconds = 5

        with state._lock:
            state._sweep_expired_unlocked()

        assert not await state.exists("stale")
        assert await state.exists("fresh")

    @pytest.mark.asyncio
    async def test_atomic_update(self, state):
        await state.set("counter", 0, source="test")

        def increment(current):
            return (current or 0) + 1

        await state.atomic_update("counter", increment, source="test")
        assert await state.get("counter") == 1

    @pytest.mark.asyncio
    async def test_compare_and_set_success(self, state):
        await state.set("k", 1, source="test")
        assert await state.compare_and_set("k", 1, 2, source="test") is True
        assert await state.get("k") == 2

    @pytest.mark.asyncio
    async def test_compare_and_set_failure(self, state):
        await state.set("k", 1, source="test")
        assert await state.compare_and_set("k", 99, 2, source="test") is False
        assert await state.get("k") == 1

    @pytest.mark.asyncio
    async def test_change_history_records_events(self, state):
        await state.set("k", "v1", source="test")
        await state.set("k", "v2", source="test")
        history = state.get_change_history(limit=10)
        assert len(history) == 2
        assert history[0].change_type == StateChangeType.SET
        assert history[0].old_value is None
        assert history[1].old_value == "v1"

    @pytest.mark.asyncio
    async def test_observers_notified_on_set_and_delete(self, state):
        seen = []

        async def observer(event):
            seen.append(event)

        state.observe(observer)
        await state.set("k", "v", source="test")
        assert len(seen) == 1
        assert seen[0].key == "k"
        assert seen[0].value == "v"

        await state.delete("k", source="test")
        assert len(seen) == 2
        assert seen[1].change_type == StateChangeType.DELETE

        state.unobserve(observer)
        await state.set("k2", "v2", source="test")
        assert len(seen) == 2

    def test_stats_counts(self, state):
        stats = state.get_stats()
        assert stats["total_keys"] == 0
        assert stats["observer_count"] == 0


class TestAgentCoordinator:
    """Tests for AgentCoordinator lifecycle."""

    @pytest.fixture
    def coordinator(self):
        return AgentCoordinator(
            bus=MessageBus(),
            state=SharedState(),
            queue=TaskQueue(),
        )

    @pytest.mark.asyncio
    async def test_register_deregister_agent(self, coordinator):
        await coordinator.start()
        try:
            await coordinator.register_agent("forge")
            assert "forge" in coordinator._agents
            assert coordinator._agents["forge"].status == AgentStatus.REGISTERED
            assert await coordinator.deregister_agent("forge") is True
            assert "forge" not in coordinator._agents
        finally:
            await coordinator.stop()

    @pytest.mark.asyncio
    async def test_heartbeat_activates_agent(self, coordinator):
        await coordinator.start()
        try:
            await coordinator.register_agent("forge")
            await coordinator.heartbeat("forge")
            assert coordinator._agents["forge"].status == AgentStatus.ACTIVE
        finally:
            await coordinator.stop()

    @pytest.mark.asyncio
    async def test_heartbeat_unknown_agent_logs(self, coordinator):
        await coordinator.start()
        try:
            # Should not raise
            await coordinator.heartbeat("ghost")
        finally:
            await coordinator.stop()

    @pytest.mark.asyncio
    async def test_submit_task_returns_id(self, coordinator):
        await coordinator.start()
        try:
            task = QueueTask(name="build", handler=Mock())
            task_id = await coordinator.submit_task(task)
            assert task_id == task.task_id
            assert task.task_id in coordinator._queue._tasks
        finally:
            await coordinator.stop()

    @pytest.mark.asyncio
    async def test_submit_task_to_unknown_agent_raises(self, coordinator):
        await coordinator.start()
        try:
            task = QueueTask(name="build", handler=Mock())
            with pytest.raises(ValueError):
                await coordinator.submit_task(task, target_agent="ghost")
        finally:
            await coordinator.stop()

    @pytest.mark.asyncio
    async def test_complete_task_broadcasts(self, coordinator):
        await coordinator.start()
        try:
            task = QueueTask(name="build", handler=Mock())
            task_id = await coordinator.submit_task(task)
            coordinator._queue.mark_running(task_id)
            await coordinator.complete_task(task_id, result="done")
            assert task.status == TaskStatus.COMPLETED
        finally:
            await coordinator.stop()

    def test_stats_without_agents(self, coordinator):
        stats = coordinator.stats()
        assert stats["agents"] == 0
        assert stats["dead_letters"] == 0


class TestEventEvaluator:
    """Tests for the preserved EventEvaluator."""

    def test_no_condition_returns_false(self):
        from src.agent.orchestrator import EventEvaluator

        evaluator = EventEvaluator()
        job = Mock()
        job.trigger_condition = None
        assert evaluator.evaluate(db=Mock(), job=job) is False

    def test_invalid_format_returns_false(self):
        from src.agent.orchestrator import EventEvaluator

        evaluator = EventEvaluator()
        job = Mock()
        job.trigger_condition = "not_a_condition"
        assert evaluator.evaluate(db=Mock(), job=job) is False

    def test_unsupported_metric_returns_false(self):
        from src.agent.orchestrator import EventEvaluator

        evaluator = EventEvaluator()
        job = Mock()
        job.trigger_condition = "mystery_metric:5"
        assert evaluator.evaluate(db=Mock(), job=job) is False

    @patch("src.agent.orchestrator.AuditLog")
    @patch("src.agent.orchestrator.func")
    def test_tool_fail_count_metric(self, mock_func, mock_auditlog):
        from src.agent.orchestrator import EventEvaluator

        evaluator = EventEvaluator()
        job = Mock()
        job.trigger_condition = "tool_fail_count:3"
        job.tool_name = "web_search"

        # A mock query chain returning count 5
        mock_count = Mock()
        mock_count.filter.return_value.scalar.return_value = 5
        mock_func.count.return_value = Mock()
        mock_db = Mock()
        mock_db.query.return_value = mock_count

        with patch("src.agent.orchestrator.func.count") as mock_count_func:
            mock_count_func.return_value = "COUNT_EXPR"
            assert evaluator.evaluate(db=mock_db, job=job) is True

    @patch("src.agent.orchestrator.func.count")
    def test_tool_fail_count_below_threshold(self, mock_count):
        from src.agent.orchestrator import EventEvaluator

        evaluator = EventEvaluator()
        job = Mock()
        job.trigger_condition = "tool_fail_count:5"
        job.tool_name = "web_search"

        mock_count.return_value = "COUNT_EXPR"
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.scalar.return_value = 2
        assert evaluator.evaluate(db=mock_db, job=job) is False


class TestOmegaOrchestrator:
    """Tests for the coordinator-based OmegaOrchestrator."""

    @pytest.fixture
    def orchestrator(self):
        from unittest.mock import AsyncMock

        from src.agent.orchestrator import OmegaOrchestrator

        coordinator = Mock()
        coordinator.stats.return_value = {"agents": 1}
        coordinator.start = AsyncMock()
        coordinator.stop = AsyncMock()
        coordinator.submit_task = AsyncMock(return_value="task-1")
        bus = Mock()
        bus.start = AsyncMock()
        bus.stop = AsyncMock()
        queue = Mock()
        queue.stats.return_value = {"pending": 2}
        state = Mock()
        state.get_stats.return_value = {"entries": 3}
        return OmegaOrchestrator(
            coordinator=coordinator,
            message_bus=bus,
            task_queue=queue,
            shared_state=state,
        )

    @pytest.mark.asyncio
    async def test_start_starts_coordinator_and_bus(self, orchestrator):
        await orchestrator.start()
        orchestrator.coordinator.start.assert_awaited_once()
        orchestrator.bus.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_stops_coordinator_and_bus(self, orchestrator):
        await orchestrator.stop()
        orchestrator.coordinator.stop.assert_awaited_once()
        orchestrator.bus.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_submit_task_builds_queue_task(self, orchestrator):
        handler = Mock()
        task_id = await orchestrator.submit_task("build", handler, priority=5, kwargs={"opt": True})
        assert task_id == orchestrator.coordinator.submit_task.return_value
        submitted = orchestrator.coordinator.submit_task.await_args.args[0]
        assert submitted.name == "build"
        assert submitted.handler is handler
        assert submitted.priority == 5
        assert submitted.kwargs == {"opt": True}

    def test_health_report_aggregates(self, orchestrator):
        report = orchestrator.health_report()
        assert report["coordinator"] == {"agents": 1}
        assert report["queue"] == {"pending": 2}
        assert report["state"] == {"entries": 3}
