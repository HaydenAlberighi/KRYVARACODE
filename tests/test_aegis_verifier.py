"""
Unit tests for src/agent/aegis/verifier.py and src/agent/aegis/invariants.py
"""

import pytest

from src.agent.aegis.invariants import (
    FORBIDDEN_PATTERNS,
    RiskLevel,
    SafetyInvariant,
    check_violation,
    get_all_invariants,
)
from src.agent.aegis.verifier import AegisVerifier


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_risk_level_values(self):
        """Test that RiskLevel enum has correct values."""
        assert RiskLevel.CRITICAL.value == 3
        assert RiskLevel.HIGH.value == 2
        assert RiskLevel.MEDIUM.value == 1
        assert RiskLevel.LOW.value == 0

    def test_risk_level_ordering(self):
        """Test that risk levels can be compared."""
        assert RiskLevel.CRITICAL.value > RiskLevel.HIGH.value
        assert RiskLevel.HIGH.value > RiskLevel.MEDIUM.value
        assert RiskLevel.MEDIUM.value > RiskLevel.LOW.value


class TestSafetyInvariant:
    """Tests for SafetyInvariant dataclass."""

    def test_safety_invariant_creation(self):
        """Test creating a SafetyInvariant."""
        import re

        pattern = re.compile(r"test")
        invariant = SafetyInvariant(
            name="Test Invariant",
            pattern=pattern,
            risk_level=RiskLevel.HIGH,
            description="Test description",
            allowed_prefixes=["/safe/"],
        )

        assert invariant.name == "Test Invariant"
        assert invariant.pattern is pattern
        assert invariant.risk_level == RiskLevel.HIGH
        assert invariant.description == "Test description"
        assert invariant.allowed_prefixes == ["/safe/"]

    def test_safety_invariant_without_allowed_prefixes(self):
        """Test SafetyInvariant without allowed_prefixes."""
        import re

        invariant = SafetyInvariant(
            name="No Prefix",
            pattern=re.compile(r"bad"),
            risk_level=RiskLevel.CRITICAL,
            description="No allowed prefixes",
        )

        assert invariant.allowed_prefixes is None


class TestCheckViolation:
    """Tests for check_violation function."""

    def test_no_violations(self):
        """Test code with no violations."""
        safe_code = "print('hello world')\nx = 1 + 2"
        violations = check_violation(safe_code)
        assert violations == []

    def test_recursive_delete_violation(self):
        """Test detection of recursive delete."""
        code = "import shutil\nshutil.rmtree('/some/path')"
        violations = check_violation(code)

        assert len(violations) == 1
        assert violations[0].name == "Recursive Delete"
        assert violations[0].risk_level == RiskLevel.CRITICAL

    def test_recursive_delete_with_os_system(self):
        """Test detection of rm -rf via os.system."""
        code = "import os\nos.system('rm -rf /tmp/test')"
        violations = check_violation(code)

        assert len(violations) == 1
        assert violations[0].name == "Recursive Delete"

    def test_recursive_delete_allowed_prefix(self):
        """Test that allowed prefixes bypass recursive delete check."""
        code = "import shutil\nshutil.rmtree('C:\\\\Users\\\\User\\\\KRYVARACODE\\\\temp\\\\test')"
        violations = check_violation(code, target_path="C:\\Users\\User\\KRYVARACODE\\temp\\test")

        assert violations == []

    def test_system_file_access_violation(self):
        """Test detection of system file access."""
        code = "with open('/etc/passwd') as f:\n    data = f.read()"
        violations = check_violation(code)

        assert len(violations) == 1
        assert violations[0].name == "System File Access"
        assert violations[0].risk_level == RiskLevel.CRITICAL

    def test_windows_system_file_access(self):
        """Test detection of Windows system file access."""
        code = "with open('C:\\Windows\\System32\\config\\SAM') as f:\n    pass"
        violations = check_violation(code)

        assert len(violations) == 1
        assert violations[0].name == "System File Access"
        assert violations[0].risk_level == RiskLevel.CRITICAL

    def test_arbitrary_remote_shell_violation(self):
        """Test detection of arbitrary shell execution."""
        code = "import subprocess\nsubprocess.Popen('ls', shell=True)"
        violations = check_violation(code)

        assert len(violations) == 1
        assert violations[0].name == "Arbitrary Remote Shell"
        assert violations[0].risk_level == RiskLevel.CRITICAL

    def test_os_popen_violation(self):
        """Test detection of os.popen."""
        code = "import os\nos.popen('ls').read()"
        violations = check_violation(code)

        assert len(violations) == 1
        assert violations[0].name == "Arbitrary Remote Shell"

    def test_unauthorized_socket_violation(self):
        """Test detection of unauthorized socket/connection."""
        code = "import socket\ns = socket.socket()"
        violations = check_violation(code)

        assert len(violations) == 1
        assert violations[0].name == "Unauthorized Socket/Connection"
        assert violations[0].risk_level == RiskLevel.HIGH

    def test_requests_to_localhost_violation(self):
        """Test detection of requests to localhost."""
        code = "import requests\nrequests.get('http://127.0.0.1:8080/api')"
        violations = check_violation(code)

        assert len(violations) == 1
        assert violations[0].name == "Unauthorized Socket/Connection"

    def test_requests_to_internal_violation(self):
        """Test detection of requests to internal host."""
        code = "import requests\nrequests.post('http://internal.service/api')"
        violations = check_violation(code)

        assert len(violations) == 1
        assert violations[0].name == "Unauthorized Socket/Connection"

    def test_ctypes_memory_access_violation(self):
        """Test detection of ctypes memory access."""
        code = "import ctypes\nctypes.memmove(...)"
        violations = check_violation(code)

        assert len(violations) == 1
        assert violations[0].name == "CTypes Memory Access"
        assert violations[0].risk_level == RiskLevel.HIGH

    def test_process_termination_violation(self):
        """Test detection of process termination."""
        code = "import sys\nsys.exit(1)"
        violations = check_violation(code)

        assert len(violations) == 1
        assert violations[0].name == "Process Termination"
        assert violations[0].risk_level == RiskLevel.MEDIUM

    def test_os_exit_violation(self):
        """Test detection of os._exit."""
        code = "import os\nos._exit(0)"
        violations = check_violation(code)

        assert len(violations) == 1
        assert violations[0].name == "Process Termination"

    def test_multiple_violations(self):
        """Test detection of multiple violations."""
        code = """
import shutil
import os
shutil.rmtree('/tmp/test')
os.system('rm -rf /etc/passwd')
"""
        violations = check_violation(code)

        assert len(violations) == 2
        names = {v.name for v in violations}
        assert "Recursive Delete" in names
        assert "System File Access" in names

    def test_violation_order_preserved(self):
        """Test that violations are returned in pattern order."""
        code = "import ctypes\nimport shutil\nshutil.rmtree('/tmp')"
        violations = check_violation(code)

        # Recursive Delete comes before CTypes in FORBIDDEN_PATTERNS
        assert violations[0].name == "Recursive Delete"
        assert violations[1].name == "CTypes Memory Access"


class TestAegisVerifier:
    """Tests for AegisVerifier class."""

    @pytest.fixture
    def verifier(self):
        """Create an AegisVerifier instance."""
        return AegisVerifier()

    def test_verify_code_safe(self, verifier):
        """Test verifying safe code."""
        code = "def hello():\n    return 'world'"
        metadata = {"tool_name": "test_tool", "target_path": "/tmp/test.py"}

        is_safe, violations, risk_score = verifier.verify_code(code, metadata)

        assert is_safe is True
        assert violations is None
        assert risk_score == 0

    def test_verify_code_critical_violation(self, verifier):
        """Test verifying code with critical violation."""
        code = "import shutil\nshutil.rmtree('/home/user/test')"
        metadata = {"tool_name": "test_tool", "target_path": "/home/user/test.py"}

        is_safe, violations, risk_score = verifier.verify_code(code, metadata)

        assert is_safe is False
        assert violations is not None
        assert len(violations) == 1
        assert violations[0].name == "Recursive Delete"
        assert violations[0].risk_level == RiskLevel.CRITICAL
        assert risk_score == 3  # CRITICAL = 3

    def test_verify_code_high_violation(self, verifier):
        """Test verifying code with high violation."""
        code = "import socket\ns = socket.socket()"
        metadata = {"tool_name": "test_tool", "target_path": "/tmp/test.py"}

        is_safe, violations, risk_score = verifier.verify_code(code, metadata)

        assert is_safe is False
        assert violations is not None
        assert len(violations) == 1
        assert violations[0].risk_level == RiskLevel.HIGH
        assert risk_score == 2  # HIGH = 2

    def test_verify_code_multiple_violations(self, verifier):
        """Test verifying code with multiple violations."""
        code = """
import shutil
import socket
shutil.rmtree('/home/user/test')
s = socket.socket()
"""
        metadata = {"tool_name": "test_tool", "target_path": "/home/user/test.py"}

        is_safe, violations, risk_score = verifier.verify_code(code, metadata)

        assert is_safe is False
        assert violations is not None
        assert len(violations) == 2
        # CRITICAL (3) + HIGH (2) = 5
        assert risk_score == 5

    def test_verify_code_aggregate_risk_exceeds_threshold(self, verifier):
        """Test that aggregate risk >= 3 rejects even without CRITICAL."""
        code = """
import socket
import ctypes
s = socket.socket()
ctypes.memmove(0, 0, 0)
"""
        metadata = {"tool_name": "test_tool", "target_path": "/tmp/test.py"}

        is_safe, _violations, risk_score = verifier.verify_code(code, metadata)

        assert is_safe is False
        assert risk_score >= 3  # 2 + 2 = 4

    def test_verify_code_allowed_prefix_bypass(self, verifier):
        """Test that allowed prefix bypasses recursive delete check."""
        code = "import shutil\nshutil.rmtree('C:\\\\Users\\\\User\\\\KRYVARACODE\\\\temp\\\\test')"
        metadata = {
            "tool_name": "test_tool",
            "target_path": "C:\\Users\\User\\KRYVARACODE\\temp\\test",
        }

        is_safe, violations, _risk_score = verifier.verify_code(code, metadata)

        assert is_safe is True
        assert violations is None

    def test_verify_code_logs_safe(self, verifier, caplog):
        """Test that safe code logs SAFE verdict."""
        code = "print('hello')"
        metadata = {"tool_name": "test_tool"}

        with caplog.at_level("INFO"):
            verifier.verify_code(code, metadata)

        assert "Code passed safety scan. Verdict: SAFE." in caplog.text

    def test_verify_code_logs_critical(self, verifier, caplog):
        """Test that critical violation logs error."""
        code = "import shutil\nshutil.rmtree('/tmp/test')"
        metadata = {"tool_name": "test_tool"}

        with caplog.at_level("ERROR"):
            verifier.verify_code(code, metadata)

        assert "CRITICAL safety violation detected" in caplog.text

    def test_verify_code_logs_aggregate_risk(self, verifier, caplog):
        """Test that aggregate risk >= 3 logs warning."""
        code = "import socket\nimport ctypes\ns = socket.socket()\nctypes.memmove(0,0,0)"
        metadata = {"tool_name": "test_tool"}

        with caplog.at_level("WARNING"):
            verifier.verify_code(code, metadata)

        assert "Aggregate risk score" in caplog.text
        assert "exceeds threshold (3)" in caplog.text

    def test_scan_tool_definition_safe(self, verifier):
        """Test scan_tool_definition with safe code."""
        tool_def = {
            "name": "safe_tool",
            "code": "def run():\n    return 'ok'",
            "target_path": "/tmp/safe.py",
        }

        result = verifier.scan_tool_definition(tool_def)

        assert result is True

    def test_scan_tool_definition_unsafe(self, verifier):
        """Test scan_tool_definition with unsafe code."""
        tool_def = {
            "name": "unsafe_tool",
            "code": "import shutil\nshutil.rmtree('/home/user/temp')",
            "target_path": "/home/user/unsafe.py",
        }

        result = verifier.scan_tool_definition(tool_def)

        assert result is False

    def test_scan_tool_definition_missing_code(self, verifier):
        """Test scan_tool_definition with missing code field."""
        tool_def = {"name": "no_code_tool"}

        result = verifier.scan_tool_definition(tool_def)

        assert result is True  # Empty code is safe

    def test_global_singleton(self):
        """Test that global singleton exists."""
        from src.agent.aegis.verifier import aegis_verifier

        assert isinstance(aegis_verifier, AegisVerifier)


class TestGetAllInvariants:
    """Tests for get_all_invariants function."""

    def test_returns_all_patterns(self):
        """Test that get_all_invariants returns all forbidden patterns."""
        invariants = get_all_invariants()

        assert len(invariants) == len(FORBIDDEN_PATTERNS)
        assert all(isinstance(inv, SafetyInvariant) for inv in invariants)

    def test_invariant_names_unique(self):
        """Test that all invariant names are unique."""
        invariants = get_all_invariants()
        names = [inv.name for inv in invariants]

        assert len(names) == len(set(names))

    def test_all_invariants_have_required_fields(self):
        """Test that all invariants have required fields."""
        invariants = get_all_invariants()

        for inv in invariants:
            assert inv.name
            assert inv.pattern
            assert inv.risk_level in RiskLevel
            assert inv.description


class TestInvariantEdgeCases:
    """Edge case tests for invariants."""

    def test_case_insensitive_patterns(self):
        """Test that patterns match case-insensitively where appropriate."""
        # The patterns use re.search which is case-sensitive by default
        # but the patterns themselves may be written to be case-insensitive
        code = "SHUTIL.RMTREE('/tmp')"
        violations = check_violation(code)

        # Pattern is "shutil\.rmtree" - case sensitive
        # So this should NOT match
        assert len(violations) == 0

    def test_pattern_with_special_chars(self):
        """Test patterns with special regex characters."""
        code = "import os\nos._exit(0)"
        violations = check_violation(code)

        assert len(violations) == 1
        assert violations[0].name == "Process Termination"

    def test_empty_code(self):
        """Test empty code string."""
        violations = check_violation("")
        assert violations == []

    def test_none_target_path(self):
        """Test with None target_path."""
        code = "import shutil\nshutil.rmtree('/tmp/test')"
        violations = check_violation(code, target_path=None)

        assert len(violations) == 1
        assert violations[0].name == "Recursive Delete"

    @pytest.mark.xfail(reason="Source code bug: non-string target_path causes AttributeError")
    def test_target_path_not_string(self):
        """Test with non-string target_path (exposes source code bug)."""
        code = "import shutil\nshutil.rmtree('/tmp/test')"
        violations = check_violation(code, target_path=123)

        assert len(violations) == 1


class TestVerifierEdgeCases:
    """Edge case tests for AegisVerifier."""

    @pytest.fixture
    def verifier(self):
        return AegisVerifier()

    def test_verify_code_empty_metadata(self, verifier):
        """Test verify_code with empty metadata."""
        code = "print('hello')"
        metadata = {}

        is_safe, _violations, _risk_score = verifier.verify_code(code, metadata)

        assert is_safe is True

    def test_verify_code_none_target_path_in_metadata(self, verifier):
        """Test verify_code with None target_path in metadata."""
        code = "import shutil\nshutil.rmtree('/tmp/test')"
        metadata = {"tool_name": "test", "target_path": None}

        is_safe, _violations, _risk_score = verifier.verify_code(code, metadata)

        assert is_safe is False

    def test_scan_tool_definition_empty_dict(self, verifier):
        """Test scan_tool_definition with empty dict."""
        tool_def = {}

        result = verifier.scan_tool_definition(tool_def)

        assert result is True
