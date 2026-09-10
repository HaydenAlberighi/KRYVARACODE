"""
SandboxExecutor for KRYVARACODE Omega-Prime.
Executes synthesized code in an isolated process to prevent system corruption.
"""

import logging
import os
import subprocess
import sys
import tempfile
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SandboxError(Exception):
    """Custom exception for sandbox execution failures."""

    pass


class SandboxExecutor:
    """
    Executes Python code in an isolated subprocess.
    Future versions will upgrade to Docker/Podman for hard isolation.
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def execute(
        self, code: str, args: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[Any], Optional[str]]:
        """
        Executes the provided code in a separate process.

        Args:
            code: The Python source code to execute.
            args: Arguments to pass to the synthesized function.

        Returns:
            A tuple of (result, error_message).
        """
        # Create a temporary file for the code
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
            # We wrap the code to handle argument passing and result capturing
            wrapped_code = self._wrap_code(code, args)
            tmp.write(wrapped_code.encode("utf-8"))
            tmp_path = tmp.name

        try:
            # Run the code using the current Python interpreter
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode != 0:
                logger.error(f"Sandbox execution failed: {result.stderr}")
                return None, result.stderr

            # The result is expected to be printed to stdout as a representation
            # In a real implementation, we'd use a structured format like JSON
            return result.stdout.strip(), None

        except subprocess.TimeoutExpired:
            logger.error("Sandbox execution timed out.")
            return None, "Timeout expired"
        except Exception as e:
            logger.error(f"Unexpected sandbox error: {e}")
            return None, str(e)
        finally:
            # Cleanup temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _wrap_code(self, code: str, args: Optional[Dict[str, Any]]) -> str:
        """
        Wraps the synthesized code to call the target function with provided args
        and print the result to stdout.
        """
        # We assume the synthesizer provides a function named 'run' or uses a convention
        # For the prototype, we'll assume the function is called 'execute'

        import_block = "import json\nimport sys\n"

        # Simplified wrapper for prototype:
        # 1. Include the synthesized code
        # 2. Attempt to call a function named 'main' or 'execute'
        # 3. Print result

        wrapper = f"""
{import_block}
{code}

if __name__ == "__main__":
    try:
        # Try to find the main execution function
        # In production, the synthesizer would provide the exact function name
        import inspect
        curr_module = sys.modules['__main__']
        funcs = [name for name, obj in inspect.getmembers(curr_module) if inspect.isfunction(obj)]
        
        target_func = None
        for name in ['execute', 'main', 'run']:
            if name in funcs:
                target_func = getattr(curr_module, name)
                break
        
        if target_func is None and funcs:
            target_func = getattr(curr_module, funcs[0])
            
        if target_func:
            # Pass args if provided, otherwise call without args
            args_val = {args if args else "{}"}
            result = target_func(**args_val)
            print(result)
        else:
            print("Error: No executable function found in synthesized code.")
            sys.exit(1)
    except Exception as e:
        print(f"Runtime Error: {{e}}")
        sys.exit(1)
"""
        return wrapper


# Global singleton
executor = SandboxExecutor()
