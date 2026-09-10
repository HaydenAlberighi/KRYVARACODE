"""
Aegis Safety Invariants for KRYVARACODE.
Defines the boundaries of safe operation for autonomously synthesized tools.
"""

import ipaddress
import re
import socket
from dataclasses import dataclass
from enum import Enum
from re import Pattern


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
    allowed_prefixes: list[str] | None = None


# CIDR ranges that must never be contacted (SSRF protection)
BLOCKED_IP_RANGES: list[str] = [
    "127.0.0.0/8",  # Loopback (IPv4)
    "10.0.0.0/8",  # RFC1918 private
    "172.16.0.0/12",  # RFC1918 private
    "192.168.0.0/16",  # RFC1918 private
    "169.254.0.0/16",  # AWS metadata, link-local
    "::1/128",  # IPv6 loopback
    "fc00::/7",  # IPv6 ULA (unique local addresses)
    "fe80::/10",  # IPv6 link-local
]

# Pre-compute network objects for efficient checking
_BLOCKED_NETWORKS = [ipaddress.ip_network(cidr, strict=False) for cidr in BLOCKED_IP_RANGES]


def is_blocked_ip(ip_str: str) -> bool:
    """Check if an IP address or hostname is in a blocked CIDR range.

    IP literals are checked directly. Hostnames are resolved via DNS and
    every resolved address is checked, closing DNS-rebinding bypasses.
    Returns True if the address is in any of the BLOCKED_IP_RANGES,
    or False if it is safe to connect to.
    """
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return _hostname_is_blocked(ip_str)
    return any(addr in network for network in _BLOCKED_NETWORKS)


def _hostname_is_blocked(hostname: str) -> bool:
    infos = socket.getaddrinfo(hostname, None)
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip = sockaddr[0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if any(addr in network for network in _BLOCKED_NETWORKS):
            return True
    return False


def check_violation(code: str, target_path: str | None = None) -> list[SafetyInvariant]:
    """
    Scans a block of code against the safety registry.
    Returns a list of violated invariants, considering context.
    """
    violations = []
    for invariant in FORBIDDEN_PATTERNS:
        if invariant.pattern.search(code):
            if (invariant.allowed_prefixes and target_path and isinstance(target_path, str)) and any(
                target_path.startswith(prefix) for prefix in invariant.allowed_prefixes
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
            r"socket\.socket\(|requests\.(get|post)\(.*\b("
            r"internal|localhost|127\.0\.0\.1|"
            r"10\.\d+\.\d+\.\d+|"
            r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|"
            r"192\.168\.\d+\.\d+|"
            r"169\.254\.\d+\.\d+"
            r")\b"
        ),
        risk_level=RiskLevel.HIGH,
        description="Prevents unauthorized internal network probing (RFC1918, link-local).",
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


def get_all_invariants() -> list[SafetyInvariant]:
    """Returns the registry of all defined safety invariants."""
    return FORBIDDEN_PATTERNS
