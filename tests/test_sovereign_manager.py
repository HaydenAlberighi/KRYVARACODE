"""
Unit tests for src/agent/sovereign/manager.py - SovereignManager
"""

from typing import cast
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.agent.sovereign.manager import SovereignManager
from src.agent.sovereign.pulse import AutonomousGoal


class TestSovereignManager:
    """Tests for SovereignManager class."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock all global dependencies used by SovereignManager."""
        with (
            patch("src.agent.sovereign.manager.swarm_engine") as mock_engine,
            patch("src.agent.sovereign.manager.judge") as mock_judge,
            patch("src.agent.sovereign.manager.sovereign_memory") as mock_memory,
            patch("src.agent.sovereign.manager.ToolForgeManager") as mock_forge_class,
            patch("src.agent.sovereign.manager.EyeManager") as mock_eye_class,
            patch("src.agent.sovereign.manager.metabolic_governor") as mock_governor,
            patch("src.agent.sovereign.manager.aegis_verifier") as mock_verifier,
            patch("src.agent.sovereign.manager.aegis_gatekeeper") as mock_gatekeeper,
            patch("src.agent.sovereign.manager.IntentGenerator") as mock_pulse_class,
        ):
            mock_engine.run_loop.return_value = {
                "final_implementation": {
                    "code": "print('hello')",
                    "evidence": "test passed",
                },
                "final_critique": {"is_flawed": False, "issues": []},
                "blueprint": "test_blueprint",
                "iterations": 1,
            }
            mock_judge.evaluate.return_value = (True, "Approved: Goal achieved")
            mock_memory.query_patterns.return_value = []
            mock_memory.commit_lesson.return_value = "mem_123"
            mock_governor.check_vitals.return_value = (True, "Vitals healthy")
            mock_governor.throttle = Mock()
            mock_verifier.verify_code.return_value = (True, None)
            mock_gatekeeper.request_approval.return_value = True
            mock_pulse = cast(MagicMock, mock_pulse_class.return_value)
            mock_pulse.pulse.return_value = []

            mock_forge = Mock()
            mock_forge_class.return_value = mock_forge
            mock_eye = Mock()
            mock_eye_class.return_value = mock_eye

            yield {
                "engine": mock_engine,
                "judge": mock_judge,
                "memory": mock_memory,
                "forge": mock_forge,
                "eye": mock_eye,
                "governor": mock_governor,
                "verifier": mock_verifier,
                "gatekeeper": mock_gatekeeper,
                "pulse": mock_pulse,
                "pulse_class": mock_pulse_class,
            }

    def test_init_with_defaults(self, mock_dependencies):
        """Test SovereignManager initialization with defaults."""
        manager = SovereignManager(db_session_factory=Mock())

        assert manager.engine is mock_dependencies["engine"]
        assert manager.judge is mock_dependencies["judge"]
        assert manager.memory is mock_dependencies["memory"]
        assert manager.forge is mock_dependencies["forge"]
        assert manager.eye is mock_dependencies["eye"]
        assert manager.pulse is mock_dependencies["pulse"]
        mock_dependencies["pulse_class"].assert_called_once()

    def test_init_with_custom_dependencies(self, mock_dependencies):
        """Test SovereignManager initialization with custom dependencies."""
        custom_memory = Mock()
        custom_forge = Mock()
        custom_eye = Mock()
        custom_db_factory = Mock()

        manager = SovereignManager(
            db_session_factory=custom_db_factory,
            memory=custom_memory,
            forge=custom_forge,
            eye=custom_eye,
        )

        assert manager.memory is custom_memory
        assert manager.forge is custom_forge
        assert manager.eye is custom_eye
        assert manager.pulse is mock_dependencies["pulse"]

    def test_init_without_db_factory(self, mock_dependencies):
        """Test SovereignManager initialization without db_session_factory."""
        mock_dependencies["pulse_class"].reset_mock()

        manager = SovereignManager(db_session_factory=None)

        assert manager.pulse is None
        mock_dependencies["pulse_class"].assert_not_called()

    def test_execute_omega_task_success(self, mock_dependencies):
        """Test successful execution of omega task."""
        manager = SovereignManager(db_session_factory=Mock())

        result = manager.execute_omega_task(goal="Test goal", context={"test": "context"})

        assert result["status"] == "completed"
        assert result["verdict"] == "Approved: Goal achieved"
        assert result["result"] == {"code": "print('hello')", "evidence": "test passed"}

        mock_dependencies["engine"].run_loop.assert_called_once_with("Test goal")
        mock_dependencies["judge"].evaluate.assert_called_once()
        mock_dependencies["memory"].commit_lesson.assert_called_once()

    def test_execute_omega_task_metabolic_unhealthy(self, mock_dependencies):
        """Test execution when metabolic governor reports unhealthy (advisory only)."""
        mock_dependencies["governor"].check_vitals.return_value = (
            False,
            "CPU too high",
        )
        mock_dependencies["engine"].run_loop.return_value = {
            "final_implementation": {"code": "test"},
            "final_critique": {"is_flawed": False},
            "blueprint": "test",
            "iterations": 1,
        }
        manager = SovereignManager(db_session_factory=Mock())

        result = manager.execute_omega_task(goal="Test goal", context={})

        assert result["status"] == "completed"
        mock_dependencies["governor"].throttle.assert_called_once()

    def test_execute_omega_task_memory_patterns_found(self, mock_dependencies):
        """Test execution when memory returns failure patterns."""
        mock_pattern = Mock()
        mock_dependencies["memory"].query_patterns.return_value = [mock_pattern]
        manager = SovereignManager(db_session_factory=Mock())

        result = manager.execute_omega_task(goal="Test goal", context={"test": "context"})

        assert result["status"] == "completed"
        mock_dependencies["memory"].query_patterns.assert_called_once_with(
            {"test": "context"}, tags=["failure_pattern"]
        )

    def test_execute_omega_task_aegis_critical_violation_blocked(self, mock_dependencies):
        """Test execution blocked by Aegis critical violation."""
        mock_violation = Mock()
        mock_violation.risk_level = "CRITICAL"
        mock_violation.name = "dangerous_pattern"

        mock_dependencies["verifier"].verify_code.return_value = (
            False,
            [mock_violation],
        )
        mock_dependencies["gatekeeper"].request_approval.return_value = False
        manager = SovereignManager(db_session_factory=Mock())

        result = manager.execute_omega_task(goal="Test goal", context={})

        assert result["status"] == "blocked"
        assert "Human operator rejected" in result["reason"]
        assert result["violations"] == [mock_violation]
        mock_dependencies["gatekeeper"].request_approval.assert_called_once()

    def test_execute_omega_task_aegis_critical_violation_approved(self, mock_dependencies):
        """Test execution with critical violation but human approves."""
        mock_violation = Mock()
        mock_violation.risk_level = "CRITICAL"
        mock_violation.name = "dangerous_pattern"

        mock_dependencies["verifier"].verify_code.return_value = (
            False,
            [mock_violation],
        )
        mock_dependencies["gatekeeper"].request_approval.return_value = True
        manager = SovereignManager(db_session_factory=Mock())

        result = manager.execute_omega_task(goal="Test goal", context={})

        assert result["status"] == "completed"
        mock_dependencies["gatekeeper"].request_approval.assert_called_once()

    def test_execute_omega_task_aegis_non_critical_violation(self, mock_dependencies):
        """Test execution with non-critical violations goes to judge."""
        mock_violation = Mock()
        mock_violation.risk_level = "HIGH"
        mock_violation.name = "minor_issue"

        mock_dependencies["verifier"].verify_code.return_value = (
            False,
            [mock_violation],
        )
        manager = SovereignManager(db_session_factory=Mock())

        result = manager.execute_omega_task(goal="Test goal", context={})

        assert result["status"] == "completed"
        mock_dependencies["judge"].evaluate.assert_called_once()

    def test_execute_omega_task_judge_rejects(self, mock_dependencies):
        """Test execution when judge rejects the result."""
        mock_dependencies["judge"].evaluate.return_value = (
            False,
            "Evidence insufficient",
        )
        manager = SovereignManager(db_session_factory=Mock())

        result = manager.execute_omega_task(goal="Test goal", context={})

        assert result["status"] == "rejected"
        assert result["reason"] == "Evidence insufficient"
        assert "details" in result

    def test_execute_omega_task_implementation_as_string(self, mock_dependencies):
        """Test handling when implementation is a string instead of dict."""
        mock_dependencies["engine"].run_loop.return_value = {
            "final_implementation": "simple string implementation",
            "final_critique": {"is_flawed": False},
            "blueprint": "test",
            "iterations": 1,
        }
        manager = SovereignManager(db_session_factory=Mock())

        result = manager.execute_omega_task(goal="Test goal", context={})

        assert result["status"] == "completed"

    def test_execute_omega_task_aegis_aggregate_risk_high(self, mock_dependencies):
        """Test execution with high aggregate risk - goes to judge since no CRITICAL."""
        mock_violation1 = Mock()
        mock_violation1.risk_level = "HIGH"
        mock_violation1.name = "issue1"

        mock_violation2 = Mock()
        mock_violation2.risk_level = "HIGH"
        mock_violation2.name = "issue2"

        mock_dependencies["verifier"].verify_code.return_value = (
            False,
            [mock_violation1, mock_violation2],
        )
        mock_dependencies["gatekeeper"].request_approval.return_value = False
        manager = SovereignManager(db_session_factory=Mock())

        result = manager.execute_omega_task(goal="Test goal", context={})

        assert result["status"] == "completed"
        mock_dependencies["judge"].evaluate.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_autonomous_cycle_no_pulse(self):
        """Test autonomous cycle when pulse is not configured."""
        with (
            patch("src.agent.sovereign.manager.swarm_engine", Mock()),
            patch("src.agent.sovereign.manager.judge", Mock()),
            patch("src.agent.sovereign.manager.sovereign_memory", Mock()),
            patch("src.agent.sovereign.manager.ToolForgeManager", Mock()),
            patch("src.agent.sovereign.manager.EyeManager", Mock()),
            patch("src.agent.sovereign.manager.metabolic_governor", Mock()),
            patch("src.agent.sovereign.manager.aegis_verifier", Mock()),
            patch("src.agent.sovereign.manager.aegis_gatekeeper", Mock()),
            patch("src.agent.sovereign.manager.IntentGenerator", Mock()),
        ):
            manager = SovereignManager(db_session_factory=None)
            assert manager.pulse is None

            await manager.run_autonomous_cycle()

    @pytest.mark.asyncio
    async def test_run_autonomous_cycle_with_goals(self, mock_dependencies):
        """Test autonomous cycle with generated goals."""
        goal1 = AutonomousGoal(
            goal_id="goal_1",
            description="Fix tool X",
            priority="high",
            trigger_source="failure_cluster",
            context={"tool": "X"},
        )
        goal2 = AutonomousGoal(
            goal_id="goal_2",
            description="Optimize latency",
            priority="medium",
            trigger_source="latency_spike",
            context={"tools": ["Y"]},
        )
        mock_dependencies["pulse"].pulse.return_value = [goal1, goal2]

        manager = SovereignManager(db_session_factory=Mock())
        manager.execute_omega_task = Mock(return_value={"status": "completed"})

        await manager.run_autonomous_cycle()

        assert mock_dependencies["pulse"].pulse.call_count == 1
        assert manager.execute_omega_task.call_count == 2

    def test_execute_goal_facade(self, mock_dependencies):
        """Test execute_goal facade method."""
        manager = SovereignManager(db_session_factory=Mock())

        goal_dict = {
            "id": "goal_123",
            "description": "Test goal from dict",
            "success_criteria": "Must pass all tests",
        }

        result = manager.execute_goal(goal_dict)

        assert result["status"] == "completed"

    def test_execute_goal_minimal_dict(self, mock_dependencies):
        """Test execute_goal with minimal goal dict."""
        manager = SovereignManager(db_session_factory=Mock())

        goal_dict = {"id": "goal_minimal"}

        result = manager.execute_goal(goal_dict)

        assert result["status"] == "completed"


class TestSovereignManagerEdgeCases:
    """Edge case tests for SovereignManager."""

    @pytest.fixture
    def manager(self):
        """Create SovereignManager with basic mocks."""
        with (
            patch("src.agent.sovereign.manager.swarm_engine") as mock_engine,
            patch("src.agent.sovereign.manager.judge") as mock_judge,
            patch("src.agent.sovereign.manager.sovereign_memory") as mock_memory,
            patch("src.agent.sovereign.manager.ToolForgeManager") as mock_forge_class,
            patch("src.agent.sovereign.manager.EyeManager") as mock_eye_class,
            patch("src.agent.sovereign.manager.metabolic_governor") as mock_governor,
            patch("src.agent.sovereign.manager.aegis_verifier") as mock_verifier,
            patch("src.agent.sovereign.manager.aegis_gatekeeper") as mock_gatekeeper,
            patch("src.agent.sovereign.manager.IntentGenerator") as mock_pulse_class,
        ):
            mock_engine.run_loop.return_value = {
                "final_implementation": {
                    "code": "print('hello')",
                    "evidence": "test passed",
                },
                "final_critique": {"is_flawed": False, "issues": []},
                "blueprint": "test_blueprint",
                "iterations": 1,
            }
            mock_judge.evaluate.return_value = (True, "Approved: Goal achieved")
            mock_memory.query_patterns.return_value = []
            mock_memory.commit_lesson.return_value = "mem_123"
            mock_governor.check_vitals.return_value = (True, "Vitals healthy")
            mock_governor.throttle = Mock()
            mock_verifier.verify_code.return_value = (True, None)
            mock_gatekeeper.request_approval.return_value = True
            mock_pulse = cast(MagicMock, mock_pulse_class.return_value)
            mock_pulse.pulse.return_value = []

            mock_forge = Mock()
            mock_forge_class.return_value = mock_forge
            mock_eye = Mock()
            mock_eye_class.return_value = mock_eye

            yield (
                SovereignManager(db_session_factory=Mock()),
                {
                    "engine": mock_engine,
                    "judge": mock_judge,
                    "memory": mock_memory,
                    "governor": mock_governor,
                    "verifier": mock_verifier,
                    "gatekeeper": mock_gatekeeper,
                },
            )

    def test_execute_omega_task_swarm_exception(self, manager):
        """Test that swarm engine exception propagates."""
        mgr, mocks = manager
        mocks["engine"].run_loop.side_effect = Exception("Swarm failed")

        with pytest.raises(Exception, match="Swarm failed"):
            mgr.execute_omega_task("Test goal", {})

    def test_execute_omega_task_judge_exception(self, manager):
        """Test that judge exception propagates."""
        mgr, mocks = manager
        mocks["judge"].evaluate.side_effect = Exception("Judge failed")

        with pytest.raises(Exception, match="Judge failed"):
            mgr.execute_omega_task("Test goal", {})
