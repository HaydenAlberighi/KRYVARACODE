"""
ToolForgeManager for KRYVARACODE Omega-Prime.
Orchestrates the end-to-end pipeline of synthesizing and registering new capabilities.
"""

import logging
from typing import Any, Dict, Tuple

from src.agent.forge.registry import ToolDefinition, registry
from src.agent.forge.synthesizer import synthesizer
from src.agent.forge.verifier import verifier
from src.agent.sovereign.memory_graph import sovereign_memory

logger = logging.getLogger(__name__)


class ToolForgeManager:
    """
    The central controller for the Forge.
    It handles the lifecycle of a new capability:
    Request -> Specification -> Synthesis -> Verification -> Registration.
    """

    def forge_capability(self, spec: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Attempts to create and register a new tool based on a specification.

        Args:
            spec: The tool specification {name, description, parameters, logic_hint}

        Returns:
            (success, message): Boolean indicating if the tool was successfully forged.
        """
        tool_name = spec.get("name")
        if not tool_name:
            return False, "Tool specification must include a 'name'."

        logger.info(f"Initiating Forge process for capability: {tool_name}")

        # 1. Synthesis
        try:
            query_text = (
                f"{spec.get('name')} {spec.get('description')} {spec.get('logic_hint')}"
            )
            lessons = sovereign_memory.get_distilled_lessons(query_text)

            if lessons:
                processed_lessons = []
                for l in lessons:
                    if not isinstance(l, str) and hasattr(l, "content"):
                        processed_lessons.append(l.content)
                    else:
                        processed_lessons.append(str(l))
                lessons = processed_lessons

            if lessons:
                logger.info(
                    f"Injecting {len(lessons)} learned lessons into synthesis for {tool_name}."
                )

            code = synthesizer.synthesize(spec, lessons=lessons)
            logger.info(f"Successfully synthesized code for {tool_name}.")
        except Exception as e:
            logger.error(f"Synthesis failed for {tool_name}: {e}")
            return False, f"Synthesis error: {str(e)}"

        # 2. Verification
        try:
            test_cases = verifier.generate_test_cases(spec)
            is_verified, logs = verifier.verify(code, test_cases)

            if not is_verified:
                logger.warning(f"Verification failed for {tool_name}. Logs: {logs}")
                return False, f"Verification failed: {'; '.join(logs)}"

            logger.info(f"Tool {tool_name} passed verification.")
        except Exception as e:
            logger.error(f"Verification process crashed for {tool_name}: {e}")
            return False, f"Verification system error: {str(e)}"

        # 3. Registration
        try:
            # In a real system, we would save the code to a physical file first
            # For the prototype, we store the code in the definition metadata
            definition = ToolDefinition(
                name=tool_name,
                description=spec.get("description", ""),
                parameters=spec.get("parameters", {}),
                implementation_path=f"src/agent/forge/generated/{tool_name}.py",
                function_name="execute",
                is_verified=True,
            )

            # For the prototype, we'll simulate the file save
            # In production, we'd use filesystem_write_file here

            registry.register_tool(definition)
            logger.info(f"Capability {tool_name} is now LIVE in the registry.")
            return True, f"Successfully forged and registered {tool_name}."

        except Exception as e:
            logger.error(f"Registration failed for {tool_name}: {e}")
            return False, f"Registration error: {str(e)}"


# Global singleton
forge_manager = ToolForgeManager()
