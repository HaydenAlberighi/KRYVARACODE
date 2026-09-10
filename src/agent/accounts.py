"""Account integrations for agent tools.

Live backends are availability-gated at registry build time: ``tools.py``
only registers GitHub tools when the ``gh`` CLI is installed and
authenticated. Gmail has no credentials on this host, so no Gmail tools are
registered — ``account_status`` reports the gap and the setup path instead
of advertising dead tools.
"""

from __future__ import annotations

import functools
import json
import shutil
import subprocess
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.exceptions import ServiceUnavailableError
from src.db import models

if TYPE_CHECKING:  # import-time cycle with tools.py; types only
    from src.agent.tools import ListArgs

_GH_TIMEOUT = 30


@functools.lru_cache(maxsize=1)
def github_available() -> bool:
    """True when the ``gh`` CLI exists and holds a valid login."""
    if shutil.which("gh") is None:
        return False
    try:
        proc = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def _gh(*cli_args: str) -> Any:
    """Run ``gh`` with JSON output, raising a 503 on any failure."""
    try:
        proc = subprocess.run(
            ["gh", *cli_args],
            capture_output=True,
            text=True,
            timeout=_GH_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ServiceUnavailableError(f"GitHub CLI failed: {exc}") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()[:500]
        raise ServiceUnavailableError(f"GitHub CLI error: {detail}")
    try:
        return json.loads(proc.stdout or "null")
    except json.JSONDecodeError as exc:
        raise ServiceUnavailableError("GitHub CLI returned non-JSON output") from exc


def _github_login() -> Optional[str]:
    try:
        proc = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def account_status(
    _args: object, _db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    """Report which account integrations are live and how to enable the rest."""
    return {
        "github": {
            "available": github_available(),
            "account": _github_login() if github_available() else None,
            "via": "gh CLI",
        },
        "gmail": {
            "available": False,
            "via": "Google OAuth",
            "setup": (
                "Place Google OAuth client credentials at credentials.json, "
                "run the OAuth flow to mint token.json, then enable the "
                "gmail_* tools."
            ),
        },
    }


def github_repo_list(
    args: "ListArgs", _db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    """List GitHub repositories visible to the authenticated user."""
    repos = _gh(
        "repo",
        "list",
        "--limit",
        str(args.limit),
        "--json",
        "nameWithOwner,description,url,isPrivate",
    )
    items = repos if isinstance(repos, list) else []
    return {"items": items, "total": len(items)}


class GitHubIssueListArgs(BaseModel):
    repo: str = Field(..., min_length=1, description="owner/name repository")
    state: str = Field("open", pattern="^(open|closed|all)$")
    limit: int = Field(20, ge=1, le=100)


def github_issue_list(
    args: GitHubIssueListArgs, _db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    """List issues for a repository."""
    issues = _gh(
        "issue",
        "list",
        "--repo",
        args.repo,
        "--state",
        args.state,
        "--limit",
        str(args.limit),
        "--json",
        "number,title,author,url",
    )
    items = issues if isinstance(issues, list) else []
    return {"items": items, "total": len(items)}


class GitHubIssueCreateArgs(BaseModel):
    repo: str = Field(..., min_length=1, description="owner/name repository")
    title: str = Field(..., min_length=1, max_length=256)
    body: Optional[str] = Field(None, max_length=10000)


def github_issue_create(
    args: GitHubIssueCreateArgs, _db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    """Create a GitHub issue in a repository."""
    cli_args: List[str] = [
        "issue",
        "create",
        "--repo",
        args.repo,
        "--title",
        args.title,
    ]
    if args.body:
        cli_args += ["--body", args.body]
    cli_args += ["--json", "number,url"]
    created = _gh(*cli_args)
    return {"number": created.get("number"), "url": created.get("url")}


class GitHubPrListArgs(BaseModel):
    repo: str = Field(..., min_length=1, description="owner/name repository")
    state: str = Field("open", pattern="^(open|closed|merged|all)$")
    limit: int = Field(20, ge=1, le=100)


def github_pr_list(
    args: GitHubPrListArgs, _db: Session, _user: Optional[models.User]
) -> Dict[str, Any]:
    """List pull requests for a repository."""
    prs = _gh(
        "pr",
        "list",
        "--repo",
        args.repo,
        "--state",
        args.state,
        "--limit",
        str(args.limit),
        "--json",
        "number,title,author,url",
    )
    items = prs if isinstance(prs, list) else []
    return {"items": items, "total": len(items)}
