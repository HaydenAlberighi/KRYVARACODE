"""
ToolVerifier for KRYVARACODE Omega-Prime.
Generates and executes test cases to ensure synthesized tools are safe and correct.
"""

import logging
from typing import Any, Dict, List, Tuple

from src.agent.forge.sandbox import executor

logger = logging.getLogger(__name__)


class ToolVerifier:
    """
    Verifies synthesized tools by running them in the sandbox against
    expected inputs and outcomes.
    """

    def verify(
        self, code: str, test_cases: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str]]:
        """
        Runs a set of test cases against the provided code.

        Args:
            code: The synthesized Python source code.
            test_cases: A list of test cases, where each is a dict containing:
                        - 'args': The arguments to pass to the tool
                        - 'expected': The expected result (or a predicate function)

        Returns:
            (is_verified, logs): Boolean indicating if all tests passed, and a list of logs.
        """
        logs = []
        all_passed = True

        for i, test in enumerate(test_cases):
            args = test.get("args", {})
            expected = test.get("expected")

            logger.info(f"Running test case {i + 1}/{len(test_cases)}...")

            result, error = executor.execute(code, args)

            if error:
                logs.append(f"Test {i + 1} failed with runtime error: {error}")
                all_passed = False
                continue

            # Basic equality check for the prototype.
            # In a full implementation, this would support regex or semantic matching.
            if expected is not None:
                if str(result) != str(expected):
                    logs.append(
                        f"Test {i + 1} failed: Expected {expected}, got {result}"
                    )
                    all_passed = False
                else:
                    logs.append(f"Test {i + 1} passed.")
            else:
                logs.append(
                    f"Test {i + 1} executed successfully (no expected value provided)."
                )

        return all_passed, logs

    def generate_test_cases(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generates basic test cases based on the tool specification.
        In Omega-Prime, this is driven by an LLM that thinks of edge cases.
        """
        # Prototype: generate one simple 'happy path' test case based on params
        params = spec.get("parameters", {})
        test_args = {}
        for p_name, p_info in params.items():
            p_type = p_info.get("type", "str")
            if p_type == "int":
                test_args[p_name] = 1
            elif p_type == "float":
                test_args[p_name] = 1.0
            elif p_type == "bool":
                test_args[p_name] = True
            else:
                test_args[p_name] = "test_value"

        return [
            {
                "args": test_args,
                "expected": None,  # Let the first run define the expected value for the prototype
            }
        ]


# Global singleton
verifier = ToolVerifier()
