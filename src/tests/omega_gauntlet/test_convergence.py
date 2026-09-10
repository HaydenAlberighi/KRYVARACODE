"""
The Omega Gauntlet: Convergence Test Suite.
These tests verify the end-to-end autonomous loops of the Omega-Prime architecture.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.agent.eye.manager import EyeManager
from src.agent.eye.os_interface import os_interface
from src.agent.forge.manager import ToolForgeManager
from src.agent.forge.network_discovery import APIExplorer
from src.agent.forge.protocol_bridge import protocol_bridge
from src.agent.sovereign.manager import SovereignManager
from src.agent.sovereign.memory_graph import SovereignMemory


class TestOmegaConvergence(unittest.TestCase):
    def setUp(self):
        # Setup a temporary workspace for the Gauntlet to prevent actual system damage
        self.test_dir = tempfile.mkdtemp(prefix="omega_gauntlet_")
        self.workspace = Path(self.test_dir)

        # Initialize the Omega-Prime core components
        self.memory = SovereignMemory()
        self.forge = ToolForgeManager()
        self.eye = EyeManager()
        self.sovereign = SovereignManager(memory=self.memory, forge=self.forge, eye=self.eye)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_self_healing_cycle(self):
        """
        Test: The Self-Healing Cycle
        Goal: System must detect a failure, synthesize a repair tool,
              verify it via Aegis, and fix the state autonomously.
        """
        # 1. Sabotage: Create a "corrupted" config file
        config_path = self.workspace / "system_config.txt"
        config_path.write_text("STATUS=OPERATIONAL\nVERSION=1.0\n")

        # Corrupt it
        config_path.write_text("STATUS=CORRUPTED\nVERSION=1.0\n")

        # 2. Detection & Goal Generation
        goal = {
            "id": "gauntlet_01",
            "description": f"Repair the corrupted config at {config_path}",
            "success_criteria": "STATUS=OPERATIONAL in system_config.txt",
        }

        # 3. Execution Loop
        result = self.sovereign.execute_goal(goal)

        # 4. Verification
        self.assertTrue(
            result["success"],
            f"Sovereign failed to heal the system: {result.get('error')}",
        )
        self.assertEqual(config_path.read_text().strip(), "STATUS=OPERATIONAL\nVERSION=1.0")

        lessons = self.memory.query_patterns("config repair")
        self.assertTrue(len(lessons) > 0, "System failed to commit a lesson to Semantic Memory")


def test_convergence_flow_discovery_to_action():
    """
    Integration test: Discover an API endpoint, infer its use, and perform a corresponding UI action.
    """
    mock_explorer = APIExplorer(base_url="http://mock-service")
    mock_explorer.discovered_endpoints = {
        "/api/status": MagicMock(
            url="http://mock-service/api/status",
            method="GET",
            inferred_schema={"status": "str"},
            response_sample={"status": "Critical_Error"},
            status_code=200,
            content_type="application/json",
        )
    }
    api_map = mock_explorer.get_api_map()
    assert "/api/status" in api_map
    status = api_map["/api/status"]["response_sample"]["status"]

    if status == "Critical_Error":
        with patch("src.agent.eye.os_interface.OSInterface.click") as mock_click:
            success = os_interface.semantic_click("Repair")
            assert success is True
            mock_click.assert_called()


def test_protocol_bridge_unified_interface():
    """
    Verify that the ProtocolBridge correctly abstracts different transports.
    """

    async def mock_grpc_handler(dest, payload, **kwargs):
        return {"result": "success"}, "OK", {"grpc_code": 0}

    protocol_bridge.register_handler("grpc", mock_grpc_handler)
    import asyncio

    async def run_test():
        resp = await protocol_bridge.send("grpc", "localhost:50051", {"cmd": "ping"})
        assert resp.protocol == "grpc"
        assert resp.status == "OK"
        assert resp.payload["result"] == "success"

    asyncio.run(run_test())


def test_drift_detection_integration():
    """
    Verify that the drift utility can be used by the Sovereign to trigger retraining.
    """
    from src.ml.monitoring import compute_drift

    ref = [1.0, 1.1, 0.9, 1.0, 1.0]
    curr = [2.0, 2.1, 1.9, 2.0, 2.0]
    p_val, drifted = compute_drift(ref, curr)
    assert drifted is True
    assert p_val < 0.05


if __name__ == "__main__":
    # Run the unittest class
    suite = unittest.TestLoader().loadTestsFromTestCase(TestOmegaConvergence)
    unittest.TextTestRunner().run(suite)
    # Also run the pytest functions
    pytest.main([__file__])
