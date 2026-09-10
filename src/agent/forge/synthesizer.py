"""
ToolSynthesizer for KRYVARACODE Omega-Prime.
Generates executable Python code for new tools based on high-level specifications.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ToolSynthesizer:
    """
    Responsible for turning a Tool Specification into valid, executable Python code.
    In a full Omega-Prime implementation, this would be a specialized LLM chain.
    For the prototype, it uses a templated approach with an internal logic generator.
    """

    def synthesize(
        self, spec: dict[str, Any], lessons: list[str] | None = None
    ) -> str:
        """
        Generates Python source code for a tool, incorporating learned lessons.

        Args:
            spec: The tool specification containing:
                - name: Tool name
                - description: What the tool does
                - parameters: Expected input types/descriptions
                - logic_hint: Hints about the required logic/libraries
            lessons: A list of distilled lessons/rules to avoid past mistakes.

        Returns:
            The complete Python source code for the tool.
        """
        name = spec.get("name", "synthesized_tool")
        params = spec.get("parameters", {})
        logic_hint = spec.get("logic_hint", "")

        logger.info(f"Synthesizing code for tool: {name}")

        # 1. Build imports based on logic_hint (Simplified for prototype)
        imports = self._determine_imports(logic_hint)

        # 2. Generate the function signature
        # We use 'execute' as the standard entry point for the SandboxExecutor
        args_list = []
        for param_name, param_info in params.items():
            if isinstance(param_info, dict):
                param_type = param_info.get("type", "Any")
            else:
                param_type = "Any"
            args_list.append(f"{param_name}: {param_type}")

        args_str = ", ".join(args_list)

        # 3. Generate the function body
        # In the real Omega-Prime, this is where the LLM generates the logic.
        # For the prototype, we generate a generic "Smart Implementation" based on the hint.
        body = self._generate_logic_body(logic_hint, params)

        # 4. Assemble the final code
        lesson_block = ""
        if lessons:
            lesson_block = (
                "    # LEARNED CONSTRAINTS:\n"
                + "\n".join([f"    # - {l}" for l in lessons])
                + "\n"
            )

        # Ensure body is indented. Split and strip to avoid double-indenting empty lines.
        indented_body = "\n".join(
            [f"    {line}" if line.strip() else line for line in body.split("\n")]
        )
        indented_lessons = (
            "\n".join(
                [
                    f"    {line}" if line.strip() else line
                    for line in lesson_block.split("\n")
                ]
            )
            if lesson_block
            else ""
        )

        code = f"""{imports}

def execute({args_str}) -> Any:
    \"\"\"
    {spec.get("description", "Synthesized tool implementation.")}
    \"\"\"
    try:
{indented_lessons}{indented_body}
    except Exception as e:
        return f"Execution Error: {{str(e)}}"
"""
        return code

    def _determine_imports(self, logic_hint: str) -> str:
        """Determines required imports based on the logic hint."""
        imports = [
            "import os",
            "import sys",
            "import json",
            "from typing import Any, Dict, List",
        ]

        # Simple keyword-based import mapping
        mapping = {
            "http": "import requests",
            "file": "import pathlib",
            "data": "import pandas as pd",
            "math": "import numpy as np",
            "system": "import psutil",
            "shell": "import subprocess",
        }

        for keyword, imp in mapping.items():
            if keyword in logic_hint.lower():
                imports.append(imp)

        return "\n".join(imports)

    def _generate_logic_body(self, logic_hint: str, params: dict[str, Any]) -> str:
        """
        Generates the internal logic of the tool.
        In production, this is an LLM call. Here, we provide a structured
        placeholder that mimics a functional tool.
        """
        lines = []
        lines.append(f"# Logic synthesized from hint: {logic_hint}")
        lines.append("result = {'status': 'success', 'data': {}}")

        for param in params:
            lines.append(f"# Processing {param}...")
            lines.append(f"result['data'][{param!r}] = f'Processed {{ {param} }}'")

        lines.append("return result")

        return "\n".join(lines)


# Global singleton
synthesizer = ToolSynthesizer()
