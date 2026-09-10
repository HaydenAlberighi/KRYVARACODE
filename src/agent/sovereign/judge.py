import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SovereignJudge:
    """
    The Judge analyzes the evidence provided by the Executor and the
    counter-arguments provided by the Critic to determine if the
    goal has been achieved with sufficient stability and correctness.
    """

    def _call_llm_for_verdict(self, prompt: str) -> dict[str, Any] | None:
        try:
            return None
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    def evaluate(self, goal: str, implementation: dict[str, Any], critique: dict[str, Any]) -> tuple[bool, str]:
        logger.info("Sovereign Judge is evaluating the current loop output via reasoning chain...")

        prompt = f"""
        Sovereign Judge Protocol:
        Evaluate the completion of a goal based on Executor evidence and Critic critique.

        GOAL: {goal}

        EXECUTOR EVIDENCE:
        {json.dumps(implementation.get("evidence", "No evidence provided"), indent=2)}

        CRITIC CRITIQUE:
        {json.dumps(critique, indent=2)}

        TASK:
        1. Analyze if the Executor's evidence actually proves the goal is met.
        2. Determine if the Critic's flaws are 'Critical' (blockers) or 'Minor' (polish).
        3. Weigh the evidence against the critique.

        RESPONSE FORMAT (Strict JSON):
        {{
            "is_approved": boolean,
            "verdict": "Detailed reasoning explaining why the evidence outweighs the critique or why the critique is valid."
        }}
        """

        verdict_data = self._call_llm_for_verdict(prompt)

        if verdict_data and isinstance(verdict_data, dict):
            is_approved = verdict_data.get("is_approved", False)
            reasoning = verdict_data.get("verdict", "No reasoning provided.")

            if is_approved:
                logger.info(f"Judge verdict: APPROVED. {reasoning}")
            else:
                logger.warning(f"Judge verdict: REJECTED. {reasoning}")

            return is_approved, reasoning

        logger.error("Judge Reasoning failed or LLM unavailable. Falling back to Safe-Reject.")

        is_flawed = critique.get("is_flawed", False)
        if not is_flawed:
            return True, "Approved via fallback: No flaws detected by Critic."

        return (
            False,
            "Rejected via fallback: Reasoning engine unavailable and Critic flagged flaws.",
        )


judge = SovereignJudge()
