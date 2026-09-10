"""Host computer control tools: shell, filesystem, processes.

Safety policy (skeleton grade, enforced here, not just documented):

- Filesystem access is scoped to allowed roots: the project tree, the OS
  temp directory, plus any extra roots in the ``AGENT_FILE_ROOTS``
  environment variable (``os.pathsep``-separated).
- ``run_shell`` rejects a blocklist of destructive command patterns.
- ``process_kill`` refuses system PIDs and the agent's own PID.
- Stdout/stderr are truncated; every call is audit-logged by ``invoke_tool``.
"""

from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.exceptions import ForbiddenError, ServiceUnavailableError
from src.db import models

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MAX_OUTPUT_CHARS = 8000
MAX_TIMEOUT_SECONDS = 300


def _file_roots() -> List[Path]:
    roots = [PROJECT_ROOT, Path(tempfile.gettempdir()).resolve()]
    extra = os.environ.get("AGENT_FILE_ROOTS", "")
    for part in re.split(r"[\n" + re.escape(os.pathsep) + r"]+", extra):
        part = part.strip()
        if part:
            roots.append(Path(part).resolve())
    return roots


def _resolve_scoped(path_str: str) -> Path:
    raw = Path(path_str)
    path = (PROJECT_ROOT / raw).resolve() if not raw.is_absolute() else raw.resolve()
    if not any(path == root or path.is_relative_to(root) for root in _file_roots()):
        raise ForbiddenError(f"Path outside allowed file roots: {path_str}")
    return path


_BLOCKED_PATTERNS = (
    r"rm\s+[^|;&]*-[a-z]*r",
    r"\bmkfs\b",
    r"\bdd\s+[^|;&]*of=/dev/",
    r":\(\)\s*\{\s*:\s*\|\s*:",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bhalt\b",
    r"\bpoweroff\b",
    r"\bformat\s+[a-z]:",
    r"del\s+/s[^|;&]*\\\\windows",
    r"rd\s+/s[^|;&]*\\\\windows",
    r"\breg\s+delete\s+HKLM",
)


def _check_command(command: str) -> None:
    lowered = command.strip().lower()
    for pattern in _BLOCKED_PATTERNS:
        if re.search(pattern, lowered):
            raise ForbiddenError("Command blocked by destructive-pattern policy")


def _truncate(text: str) -> Dict[str, Any]:
    if len(text) > MAX_OUTPUT_CHARS:
        return {"text": text[-MAX_OUTPUT_CHARS:], "truncated": True}
    return {"text": text, "truncated": False}


class RunShellArgs(BaseModel):
    command: str = Field(..., min_length=1, max_length=8000)
    workdir: Optional[str] = Field(
        None, description="Working directory, scoped to allowed file roots"
    )
    timeout_seconds: int = Field(60, ge=1, le=MAX_TIMEOUT_SECONDS)


def run_shell(
    args: RunShellArgs, _db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    """Execute a shell command on the host and return its output."""
    _check_command(args.command)
    cwd = str(_resolve_scoped(args.workdir)) if args.workdir else str(PROJECT_ROOT)
    try:
        proc = subprocess.run(
            args.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=args.timeout_seconds,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return {
            "timed_out": True,
            "timeout_seconds": args.timeout_seconds,
            "returncode": None,
        }
    stdout = _truncate(proc.stdout or "")
    stderr = _truncate(proc.stderr or "")
    return {
        "timed_out": False,
        "returncode": proc.returncode,
        "stdout": stdout["text"],
        "stdout_truncated": stdout["truncated"],
        "stderr": stderr["text"],
        "stderr_truncated": stderr["truncated"],
    }


class ReadFileArgs(BaseModel):
    path: str = Field(..., min_length=1, description="Scoped file path to read")
    max_bytes: int = Field(65536, ge=1, le=1048576)


def read_file(
    args: ReadFileArgs, _db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    """Read a text file inside the allowed roots."""
    path = _resolve_scoped(args.path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        from src.core.exceptions import NotFoundError

        raise NotFoundError(f"File not found: {args.path}") from None
    except OSError as exc:
        raise ServiceUnavailableError(f"Cannot read file: {exc}") from exc
    chunk = raw[: args.max_bytes]
    return {
        "path": str(path),
        "size_bytes": len(raw),
        "content": chunk.decode("utf-8", errors="replace"),
        "truncated": len(raw) > args.max_bytes,
    }


class WriteFileArgs(BaseModel):
    path: str = Field(..., min_length=1, description="Scoped file path to write")
    content: str = Field(..., max_length=1048576)
    create_dirs: bool = Field(True)


def write_file(
    args: WriteFileArgs, _db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    """Write text to a file inside the allowed roots."""
    path = _resolve_scoped(args.path)
    try:
        if args.create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)
        data = args.content.encode("utf-8")
        path.write_bytes(data)
    except OSError as exc:
        raise ServiceUnavailableError(f"Cannot write file: {exc}") from exc
    return {"path": str(path), "bytes_written": len(data)}


class ListDirArgs(BaseModel):
    path: str = Field(".", description="Scoped directory to list")
    recursive: bool = Field(False)


def list_dir(
    args: ListDirArgs, _db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    """List directory entries inside the allowed roots."""
    root = _resolve_scoped(args.path)
    if not root.is_dir():
        from src.core.exceptions import NotFoundError

        raise NotFoundError(f"Directory not found: {args.path}") from None
    entries: List[Dict[str, Any]] = []
    iterator = root.rglob("*") if args.recursive else root.iterdir()
    for child in iterator:
        if len(entries) >= 500:
            break
        try:
            is_dir = child.is_dir()
            entries.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "type": "dir" if is_dir else "file",
                    "size_bytes": None if is_dir else child.stat().st_size,
                }
            )
        except OSError:
            continue
    return {"path": str(root), "entries": entries, "total": len(entries)}


def process_list(
    _args: object, _db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    """List running host processes (pid + name, capped)."""
    processes: List[Dict[str, Any]] = []
    try:
        if sys.platform == "win32":
            proc = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            reader = csv.reader(io.StringIO(proc.stdout))
            for row in reader:
                if len(row) >= 2 and row[1].strip().isdigit():
                    processes.append({"name": row[0].strip('"'), "pid": int(row[1])})
        else:
            proc = subprocess.run(
                ["ps", "-eo", "pid,comm"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            for line in proc.stdout.splitlines()[1:]:
                parts = line.split(None, 1)
                if len(parts) == 2 and parts[0].isdigit():
                    processes.append({"pid": int(parts[0]), "name": parts[1]})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ServiceUnavailableError(f"Cannot list processes: {exc}") from exc
    processes = processes[:500]
    return {"processes": processes, "total": len(processes)}


class ProcessKillArgs(BaseModel):
    pid: int = Field(..., ge=1, description="Process id to terminate")


def process_kill(
    args: ProcessKillArgs, _db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    """Force-terminate a process by pid (never system PIDs or self)."""
    if args.pid <= 4 or args.pid == os.getpid():
        raise ForbiddenError(f"Refusing to kill protected pid {args.pid}")
    try:
        if sys.platform == "win32":
            cmd = ["taskkill", "/PID", str(args.pid), "/F"]
        else:
            cmd = ["kill", "-9", str(args.pid)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ServiceUnavailableError(f"Cannot kill process: {exc}") from exc
    if proc.returncode != 0:
        raise ServiceUnavailableError(
            f"Kill failed for pid {args.pid}: {(proc.stderr or proc.stdout).strip()[:500]}"
        )
    return {"killed": True, "pid": args.pid}
