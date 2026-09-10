"""
The Dream: World State Simulation for Omega-Prime.
Predicts the 'blast radius' and potential systemic impact of an action
before it is committed to the real environment.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Tuple

from src.agent.aegis.invariants import FORBIDDEN_PATTERNS as SAFETY_INVARIANTS

logger = logging.getLogger(__name__)


@dataclass
class SimulationResult:
    """The outcome of a world-state simulation."""

    risk_score: float  # 0.0 (Safe) to 1.0 (Catastrophic)
    predicted_impacts: List[str]
    blast_radius: str  # 'local', 'systemic', 'global'
    suggested_mitigations: List[str]
    is_reversible: bool
    timestamp: datetime = field(default_factory=datetime.now)


class WorldSimulator:
    """
    Simulates the execution of a proposed action in a virtual 'shadow' state
    to evaluate systemic risk.
    """

    def __init__(self):
        self.risk_weights = {
            "filesystem_write": 0.4,
            "network_request": 0.3,
            "process_termination": 0.6,
            "registry_change": 0.7,
            "user_input_simulation": 0.2,
        }

    def _calculate_base_risk(self, action_code: str) -> float:
        """
        Heuristic analysis of the code to determine base risk.
        """
        score = 0.0
        # Check against Aegis invariants for immediate high risk
        for invariant in SAFETY_INVARIANTS:
            if invariant.pattern in action_code:
                score += 0.5  # Base jump for any safety violation

        # Check for high-risk keywords
        risk_keywords = {
            "rm -rf": 0.8,
            "os.remove": 0.4,
            "shutil.rmtree": 0.7,
            "subprocess.Popen": 0.3,
            "socket.connect": 0.2,
            "requests.post": 0.2,
            "set_env": 0.1,
        }

        for keyword, weight in risk_keywords.items():
            if keyword in action_code:
                score += weight

        return min(score, 1.0)

    def _estimate_blast_radius(
        self, base_risk: float, context: Dict[str, Any]
    ) -> Tuple[str, List[str]]:
        """
        Estimates how far the impact of the action spreads.
        """
        impacts = []
        if base_risk < 0.3:
            return "local", ["Minimal change to local state"]

        if 0.3 <= base_risk < 0.7:
            impacts.append("Potential modification of application configuration")
            impacts.append("Temporary service interruption")
            return "systemic", impacts

        impacts.append("Permanent data loss in target directory")
        impacts.append("System-wide stability degradation")
        impacts.append("Security perimeter breach")
        return "global", impacts

    async def simulate(
        self, action_code: str, context: Dict[str, Any]
    ) -> SimulationResult:
        """
        Perform a 'Dream' simulation of the proposed action.
        """
        logger.info("The Dream: Simulating proposed action blast radius...")

        # Simulate processing time
        await asyncio.sleep(0.2)

        base_risk = self._calculate_base_risk(action_code)
        radius, impacts = self._estimate_blast_radius(base_risk, context)

        # Determine reversibility
        is_reversible = True
        if "rm " in action_code or "delete" in action_code.lower():
            is_reversible = False

        mitigations = []
        if base_risk > 0.5:
            mitigations.append("Create a full system snapshot before execution")
            mitigations.append("Run in a restricted container with no network access")
        if not is_reversible:
            mitigations.append("Verify existence of off-site backups")

        return SimulationResult(
            risk_score=base_risk,
            predicted_impacts=impacts,
            blast_radius=radius,
            suggested_mitigations=mitigations,
            is_reversible=is_reversible,
        )


# Global singleton
world_simulator = WorldSimulator()
