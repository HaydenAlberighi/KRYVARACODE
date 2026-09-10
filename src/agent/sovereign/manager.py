"""
SovereignManager for KRYVARACODE Omega-Prime.
The entry point that orchestrates the transition from standard single-agent
orchestration to the Adversarial Swarm mode.
"""

import logging
from typing import Any

from src.agent.aegis.gatekeeper import aegis_gatekeeper
from src.agent.aegis.governor import metabolic_governor
from src.agent.aegis.verifier import aegis_verifier
from src.agent.eye.manager import EyeManager
from src.agent.forge.manager import ToolForgeManager
from src.agent.sovereign.judge import judge
from src.agent.sovereign.memory_graph import sovereign_memory
from src.agent.sovereign.pulse import IntentGenerator
from src.agent.sovereign.swarm_engine import swarm_engine

logger = logging.getLogger(__name__)


class SovereignManager:
    """
    High-level manager that handles goal routing and swarm coordination.
    Now integrated with The Pulse for proactive autonomous goal pursuit.
    """

    def __init__(self, db_session_factory=None, memory=None, forge=None, eye=None):
        self.engine = swarm_engine
        self.judge = judge
        self.memory = memory or sovereign_memory
        self.forge = forge or ToolForgeManager()
        self.eye = eye or EyeManager()
        self.pulse = IntentGenerator(db_session_factory) if db_session_factory else None

    async def run_autonomous_cycle(self):
        """
        The background heartbeat. Scans for intrinsic needs and triggers
        Sovereign sessions without user input.
        """
        if not self.pulse:
            return

        logger.info("SovereignManager: Initiating autonomous pulse check...")
        goals = self.pulse.pulse()

        for goal in goals:
            logger.info(f"Pulse triggered autonomous goal: {goal.description}")
            result = self.execute_omega_task(
                goal=goal.description,
                context={"trigger": goal.trigger_source, "goal_id": goal.goal_id},
            )
            logger.info(f"Autonomous goal {goal.goal_id} result: {result['status']}")

    def execute_omega_task(self, goal: str, context: dict[str, Any]) -> dict[str, Any]:
        """
        The primary loop for Omega-Prime tasks with integrated Aegis safety checks.
        """
        logger.info(f"SovereignManager taking control for goal: {goal}")

        # 1. Metabolic Check
        is_healthy, reason = metabolic_governor.check_vitals()
        if not is_healthy:
            logger.warning(f"Sovereign paused by Metabolic Governor: {reason}")
            metabolic_governor.throttle()

        # 2. Memory lookup
        patterns = self.memory.query_patterns(context, tags=["failure_pattern"])
        if patterns:
            logger.info(f"Retrieved {len(patterns)} relevant failure patterns from recursive memory.")

        # 3. Swarm execution
        swarm_result = self.engine.run_loop(goal)

        # 4. Safety verification
        implementation_code = (
            swarm_result["final_implementation"].get("code", "")
            if isinstance(swarm_result["final_implementation"], dict)
            else str(swarm_result["final_implementation"])
        )
        is_safe, violations = aegis_verifier.verify_code(implementation_code, {"tool_name": "Sovereign_Result"})

        if not is_safe:
            critical = [v for v in (violations or []) if v.risk_level == "CRITICAL"]
            if critical:
                approved = aegis_gatekeeper.request_approval(
                    action_id="omega_execution",
                    description=f"Sovereign proposes code with CRITICAL violations: {[v.name for v in critical] if critical else 'None'}",
                    risk_level="CRITICAL",
                )
                if not approved:
                    logger.error("SovereignManager: Execution BLOCKED by Aegis Gatekeeper (Human Rejected).")
                    return {
                        "status": "blocked",
                        "reason": "Human operator rejected safety violations.",
                        "violations": violations,
                    }
            else:
                logger.warning("Aegis detected non-critical violations. Passing to Judge for final verdict.")

        # 5. Final adjudication by the Judge
        verdict, reason = self.judge.evaluate(
            goal=goal,
            implementation=swarm_result["final_implementation"],
            critique=swarm_result["final_critique"],
        )

        if not verdict:
            logger.error(f"Sovereign Judge rejected result: {reason}")
            # This would trigger a high-level retry or a human-in-the-loop escalation
            return {"status": "rejected", "reason": reason, "details": swarm_result}

        # 6. Commit successful strategy to memory
        self.memory.commit_lesson(
            category="strategic_pivot",
            content=f"Successfully achieved {goal} using blueprint: {swarm_result['blueprint']}",
            context={"iterations": swarm_result["iterations"]},
            tags=["success", "omega_prime"],
        )

        logger.info("SovereignManager: Goal achieved and lessons committed to memory.")
        return {
            "status": "completed",
            "verdict": reason,
            "result": swarm_result["final_implementation"],
        }

    def execute_goal(self, goal: dict[str, Any]) -> dict[str, Any]:
        """
        Facade method for the Gauntlet and other high-level autonomous goal callers.
        """
        goal_id = goal.get("id", "unknown")
        description = goal.get("description", "no description")

        logger.info(f"Sovereign executing goal {goal_id}: {description}")

        # Convert the Goal object/dict into a lapped Omega task
        return self.execute_omega_task(
            goal=description,
            context={
                "goal_id": goal_id,
                "success_criteria": goal.get("success_criteria"),
            },
        )


# Global singleton
sovereign_manager = SovereignManager()
