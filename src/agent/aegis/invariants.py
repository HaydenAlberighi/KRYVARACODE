"""
Aegis Safety Invariants for KRYVARACODE.
Defines the boundaries of safe operation for autonomously synthesized tools.
"""

import re
from dataclasses import dataclass
from typing import List, Pattern, Optional, Dict
from enum import Enum


class RiskLevel(Enum):
    CRITICAL = 3
    HIGH = 2
    MEDIUM = 1
    LOW = 0


@dataclass
class SafetyInvariant:
    """A safety rule that code must not violate."""

    name: str
    pattern: Pattern
    risk_level: RiskLevel
    description: str
    allowed_prefixes: Optional[List[str]] = None


def check_violation(
    code: str, target_path: Optional[str] = None
) -> List[SafetyInvariant]:
    """
    Scans a block of code against the safety registry.
    Returns a list of violated invariants, considering context.
    """
    violations = []
    for invariant in FORBIDDEN_PATTERNS:
        if invariant.pattern.search(code):
            if (
                invariant.allowed_prefixes
                and target_path
                and isinstance(target_path, str)
            ):
                if any(
                    target_path.startswith(prefix)
                    for prefix in invariant.allowed_prefixes
                ):
                    continue
            violations.append(invariant)
    return violations


FORBIDDEN_PATTERNS = [
    # File System Destruction
    SafetyInvariant(
        name="Recursive Delete",
        pattern=re.compile(r"shutil\.rmtree\(|os\.system\(.*rm\s+-rf"),
        risk_level=RiskLevel.CRITICAL,
        description="Prohibits recursive directory deletion.",
        allowed_prefixes=["C:\\Users\\User\\KRYVARACODE\\temp\\", "/tmp/"],
    ),
    SafetyInvariant(
        name="System File Access",
        pattern=re.compile(r"C:\\Windows\\|/etc/passwd|/etc/shadow"),
        risk_level=RiskLevel.CRITICAL,
        description="Prohibits access to sensitive system directories.",
    ),
    # Unauthorized Network/Remote Execution
    SafetyInvariant(
        name="Arbitrary Remote Shell",
        pattern=re.compile(r"subprocess\.Popen\(.*shell=True.*|os\.popen\("),
        risk_level=RiskLevel.CRITICAL,
        description="Prohibits shell execution of arbitrary strings.",
    ),
    SafetyInvariant(
        name="Unauthorized Socket/Connection",
        pattern=re.compile(
            r"socket\.socket\(|requests\.(get|post)\(.*\b(internal|localhost|127\.0\.0\.1)\b"
        ),
        risk_level=RiskLevel.HIGH,
        description="Prevents unauthorized internal network probing.",
    ),
    # Memory/Process Manipulation
    SafetyInvariant(
        name="CTypes Memory Access",
        pattern=re.compile(r"import ctypes|ctypes\."),
        risk_level=RiskLevel.HIGH,
        description="Prohibits direct memory manipulation via ctypes.",
    ),
    SafetyInvariant(
        name="Process Termination",
        pattern=re.compile(r"os\._exit\(|sys\.exit\("),
        risk_level=RiskLevel.MEDIUM,
        description="Prevents tools from killing the host process.",
    ),
]


def get_all_invariants() -> List[SafetyInvariant]:
    """Returns the registry of all defined safety invariants."""
    return FORBIDDEN_PATTERNS
