"""
E2B Sandbox client for secure shell command execution.

Provides isolated cloud sandbox environments via E2B API.
Falls back gracefully when E2B is unavailable.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# E2B SDK availability
_E2B_AVAILABLE = False
try:  # pragma: no cover
    from e2b import Sandbox as E2BSandboxClient  # type: ignore[import]

    _E2B_AVAILABLE = True
except ImportError:  # pragma: no cover
    _E2B_AVAILABLE = False
    E2BSandboxClient = Any  # type: ignore[assignment,misc]


@dataclass
class SandboxResult:
    """Result of a sandbox command execution."""

    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    timed_out: bool = False


class E2BSandbox:
    """E2B sandbox for secure shell command execution.

    Uses E2B cloud sandboxes for isolated command execution.
    Manages sandbox lifecycle and provides fallback when unavailable.
    """

    def __init__(
        self,
        api_key: str | None = None,
        template_id: str = "base",
        timeout_seconds: int = 60,
        cpu_limit: float = 1.0,
        memory_mb: int = 512,
    ) -> None:
        """Initialize E2B sandbox client.

        Parameters
        ----------
        api_key : str | None
            E2B API key. If None, reads from settings.
        template_id : str
            E2B template ID (default: "base" - includes Python, Node, common tools).
        timeout_seconds : int
            Default command timeout in seconds.
        cpu_limit : float
            CPU limit in cores (1.0 = 1 vCPU).
        memory_mb : int
            Memory limit in MB.
        """
        from src.core.config import settings

        self._api_key = api_key or settings.E2B_API_KEY
        self._template_id = template_id or settings.E2B_TEMPLATE_ID
        self._timeout_seconds = timeout_seconds or settings.E2B_TIMEOUT_SECONDS
        self._cpu_limit = cpu_limit or settings.E2B_CPU_LIMIT
        self._memory_mb = memory_mb or settings.E2B_MEMORY_LIMIT_MB

        self._sandbox: E2BSandboxClient | None = None
        self._sandbox_created = False

    def is_available(self) -> bool:
        """Check if E2B is configured and SDK is available."""
        if not _E2B_AVAILABLE:
            return False
        return bool(self._api_key)

    def _get_or_create_sandbox(self) -> E2BSandboxClient | None:
        """Get existing sandbox or create new one."""
        if not self.is_available():
            return None

        if self._sandbox is not None and self._sandbox_created:
            return self._sandbox

        try:
            logger.info("Creating E2B sandbox (template=%s)...", self._template_id)
            self._sandbox = E2BSandboxClient(
                api_key=self._api_key,
                template=self._template_id,
                timeout=self._timeout_seconds,
            )
            self._sandbox_created = True
            logger.info("E2B sandbox created successfully")
            return self._sandbox
        except Exception as e:
            logger.error("Failed to create E2B sandbox: %s", e)
            self._sandbox = None
            self._sandbox_created = False
            return None

    def run_command(
        self,
        command: str,
        cwd: str = "/home/user",
        env: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> SandboxResult:
        """Run a shell command in the E2B sandbox.

        Parameters
        ----------
        command : str
            Shell command to execute.
        cwd : str
            Working directory inside sandbox (default: /home/user).
        env : dict | None
            Environment variables to set.
        timeout_seconds : int | None
            Override default timeout.

        Returns
        -------
        SandboxResult
            Execution result with stdout, stderr, exit_code, timing.
        """
        if not self.is_available():
            raise RuntimeError("E2B sandbox not available (missing API key or SDK)")

        sandbox = self._get_or_create_sandbox()
        if sandbox is None:
            raise RuntimeError("Failed to initialize E2B sandbox")

        timeout = timeout_seconds or self._timeout_seconds
        start_time = time.perf_counter()

        try:
            # Prepare environment
            if env:
                # E2B doesn't directly support env in commands.run,
                # but we can export them in the command
                env_exports = " ".join(f"{k}={v}" for k, v in env.items())
                full_command = f"export {env_exports} && cd {cwd} && {command}"
            else:
                full_command = f"cd {cwd} && {command}"

            # Execute command
            logger.debug("Running command in E2B sandbox: %s", command)
            proc = sandbox.commands.run(full_command, timeout=timeout)

            execution_time = (time.perf_counter() - start_time) * 1000

            return SandboxResult(
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                exit_code=proc.exit_code,
                execution_time_ms=execution_time,
                timed_out=False,
            )

        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000
            error_msg = str(e)

            # Check if it's a timeout
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                return SandboxResult(
                    stdout="",
                    stderr=f"Command timed out after {timeout}s",
                    exit_code=-1,
                    execution_time_ms=execution_time,
                    timed_out=True,
                )

            logger.error("E2B sandbox command failed: %s", e)
            return SandboxResult(
                stdout="",
                stderr=error_msg,
                exit_code=-1,
                execution_time_ms=execution_time,
                timed_out=False,
            )

    def run_python(
        self,
        code: str,
        args: dict[str, Any] | None = None,
        timeout_seconds: int | None = None,
    ) -> SandboxResult:
        """Run Python code in the E2B sandbox.

        Alternative to SandboxExecutor for synthesized tools.

        Parameters
        ----------
        code : str
            Python code to execute.
        args : dict | None
            Arguments to pass to the code (available as `args` variable).
        timeout_seconds : int | None
            Override default timeout.

        Returns
        -------
        SandboxResult
            Execution result.
        """
        if not self.is_available():
            raise RuntimeError("E2B sandbox not available")

        sandbox = self._get_or_create_sandbox()
        if sandbox is None:
            raise RuntimeError("Failed to initialize E2B sandbox")

        timeout = timeout_seconds or self._timeout_seconds
        start_time = time.perf_counter()

        try:
            # Prepare code with args
            import base64
            import json

            args_b64 = base64.b64encode(json.dumps(args or {}).encode()).decode()
            wrapped_code = f"""
import json
import base64
import sys

# Deserialize args
args = json.loads(base64.b64decode("{args_b64}").decode())

{code}

# If there's a main function, call it
if 'main' in globals():
    result = main(**args)
    print(json.dumps(result, default=str))
"""

            logger.debug("Running Python code in E2B sandbox")
            exec_result = sandbox.run_code(wrapped_code, timeout=timeout)

            execution_time = (time.perf_counter() - start_time) * 1000

            stdout = ""
            stderr = ""
            if exec_result.logs:
                stdout = exec_result.logs.stdout if exec_result.logs.stdout else ""
                stderr = exec_result.logs.stderr if exec_result.logs.stderr else ""

            exit_code = 0 if exec_result.error is None else -1

            return SandboxResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                execution_time_ms=execution_time,
                timed_out=False,
            )

        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000
            error_msg = str(e)

            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                return SandboxResult(
                    stdout="",
                    stderr=f"Execution timed out after {timeout}s",
                    exit_code=-1,
                    execution_time_ms=execution_time,
                    timed_out=True,
                )

            logger.error("E2B sandbox Python execution failed: %s", e)
            return SandboxResult(
                stdout="",
                stderr=error_msg,
                exit_code=-1,
                execution_time_ms=execution_time,
                timed_out=False,
            )

    def write_file(self, path: str, content: str) -> bool:
        """Write a file to the sandbox filesystem."""
        if not self.is_available():
            return False

        sandbox = self._get_or_create_sandbox()
        if sandbox is None:
            return False

        try:
            sandbox.filesystem.write(path, content)
            return True
        except Exception as e:
            logger.error("Failed to write file to E2B sandbox: %s", e)
            return False

    def read_file(self, path: str) -> str | None:
        """Read a file from the sandbox filesystem."""
        if not self.is_available():
            return None

        sandbox = self._get_or_create_sandbox()
        if sandbox is None:
            return None

        try:
            return sandbox.filesystem.read(path)
        except Exception as e:
            logger.error("Failed to read file from E2B sandbox: %s", e)
            return None

    def list_files(self, path: str = "/home/user") -> list[str]:
        """List files in sandbox directory."""
        if not self.is_available():
            return []

        sandbox = self._get_or_create_sandbox()
        if sandbox is None:
            return []

        try:
            return sandbox.filesystem.list(path)
        except Exception as e:
            logger.error("Failed to list files in E2B sandbox: %s", e)
            return []

    def kill(self) -> None:
        """Terminate the sandbox."""
        if self._sandbox is not None and self._sandbox_created:
            try:
                self._sandbox.kill()
                logger.info("E2B sandbox terminated")
            except Exception as e:
                logger.error("Failed to kill E2B sandbox: %s", e)
            finally:
                self._sandbox = None
                self._sandbox_created = False

    def __enter__(self) -> "E2BSandbox":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - cleanup sandbox."""
        self.kill()


# Global singleton (lazy initialization)
_e2b_sandbox_instance: E2BSandbox | None = None


def get_e2b_sandbox() -> E2BSandbox:
    """Get or create global E2B sandbox instance."""
    global _e2b_sandbox_instance
    if _e2b_sandbox_instance is None:
        _e2b_sandbox_instance = E2BSandbox()
    return _e2b_sandbox_instance


def reset_e2b_sandbox() -> None:
    """Reset global E2B sandbox instance (for testing)."""
    global _e2b_sandbox_instance
    if _e2b_sandbox_instance is not None:
        _e2b_sandbox_instance.kill()
    _e2b_sandbox_instance = None
