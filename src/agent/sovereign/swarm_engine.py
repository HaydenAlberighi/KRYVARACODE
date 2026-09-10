"""
SwarmEngine for KRYVARACODE Omega-Prime.
Coordinates the adversarial loop between the Strategist, Executor, and Critic.
"""

import logging
from typing import Any, Dict

from src.agent.sovereign.roles import SwarmRole, get_persona

logger = logging.getLogger(__name__)


class SwarmEngine:
    """
    Manages the execution flow of the Adversarial Loop.
    Logic:
    1. Strategist designs blueprint.
    2. Executor implements blueprint.
    3. Critic analyzes implementation.
    4. If Critic finds flaws, loop back to Executor (or Strategist if architectural).
    5. Final output goes to the Judge.
    """

    def __init__(self):
        self.current_context = {}
        self.iteration_count = 0
        self.max_iterations = 5

    def run_loop(self, goal: str) -> Dict[str, Any]:
        """
        Executes the adversarial cycle until the Judge approves or max iterations reached.
        """
        logger.info(f"Initializing Sovereign Swarm for goal: {goal}")

        # Step 1: The Blueprint (Strategist)
        blueprint = self._invoke_role(SwarmRole.STRATEGIST, {"goal": goal})
        self.current_context["blueprint"] = blueprint

        while self.iteration_count < self.max_iterations:
            self.iteration_count += 1
            logger.info(f"Swarm Iteration {self.iteration_count} starting...")

            # Step 2: Implementation (Executor)
            implementation = self._invoke_role(
                SwarmRole.EXECUTOR,
                {"blueprint": blueprint, "context": self.current_context},
            )
            self.current_context["last_implementation"] = implementation

            # Step 3: Adversarial Review (Critic)
            critique = self._invoke_role(
                SwarmRole.CRITIC,
                {"implementation": implementation, "blueprint": blueprint},
            )

            if not critique.get("is_flawed", False):
                logger.info("Critic approved the implementation. Proceeding to Judge.")
                break

            logger.warning(
                f"Critic found flaws: {critique.get('reason')}. Looping back..."
            )
            # Update context with critique for the next Executor attempt
            self.current_context["last_critique"] = critique

        return {
            "final_implementation": self.current_context.get("last_implementation"),
            "final_critique": self.current_context.get("last_critique"),
            "blueprint": blueprint,
            "iterations": self.iteration_count,
        }

    def _invoke_role(
        self, role: SwarmRole, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Simulates the invocation of a specific role.
        In production, this triggers a separate LLM session with the role's persona.
        """
        persona = get_persona(role)
        logger.info(f"Invoking {role.value}... Objective: {persona.objective}")

        # PROTOTYPE: Returns simulated role-specific responses.
        # In real use, this calls the LLM API with the persona's system prompt.
        if role == SwarmRole.STRATEGIST:
            return {
                "plan": "1. Use Forge to create API-wrapper. 2. Use Eye to verify UI. 3. Push to DB.",
                "metrics": "Latency < 200ms",
            }
        elif role == SwarmRole.EXECUTOR:
            return {
                "status": "implemented",
                "evidence": "logs.txt",
                "result": "Task complete",
            }
        elif role == SwarmRole.CRITIC:
            # Simulate a flaw in the first iteration, approval in the second
            if self.iteration_count < 2:
                return {
                    "is_flawed": True,
                    "reason": "Edge case: network timeout not handled.",
                }
            return {"is_flawed": False, "reason": "Implementation is robust."}

        return {}


# Global singleton
swarm_engine = SwarmEngine()
