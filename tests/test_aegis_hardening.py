from src.agent.aegis.gatekeeper import aegis_gatekeeper
from src.agent.aegis.invariants import RiskLevel
from src.agent.aegis.verifier import aegis_verifier


def test_gatekeeper_structured_protocol():
    """Verify the gatekeeper uses the new request/response protocol."""
    action_id = "test_action_123"
    description = "Safe action"

    # Should be approved
    result = aegis_gatekeeper.request_approval(action_id=action_id, description=description, risk_level="HIGH")
    assert result is True

    # Should be rejected (Critical + DELETE)
    result_rejected = aegis_gatekeeper.request_approval(
        action_id="test_action_456",
        description="DELETE ALL SYSTEM FILES",
        risk_level="CRITICAL",
    )
    assert result_rejected is False


def test_verifier_context_awareness():
    """Verify that allowed_prefixes bypass certain invariants."""
    # Code that triggers "Recursive Delete"
    code = "import shutil; shutil.rmtree('C:\\Users\\User\\KRYVARACODE\\temp\\test_dir')"

    # Test 1: No target path provided (should reject)
    is_safe, _, _ = aegis_verifier.verify_code(code, {"tool_name": "test_tool"})
    assert is_safe is False

    # Test 2: Target path in allowed prefix (should approve)
    is_safe_allowed, _, _ = aegis_verifier.verify_code(
        code,
        {
            "tool_name": "test_tool",
            "target_path": "C:\\Users\\User\\KRYVARACODE\\temp\\test_dir",
        },
    )
    assert is_safe_allowed is True


def test_verifier_aggregate_risk():
    """Verify that multiple medium risks trigger a rejection via aggregate score."""
    # Code that triggers multiple MEDIUM/HIGH risks (e.g., Process Termination + CTypes)
    # CTypes (HIGH=2) + Process Termination (MEDIUM=1) = 3 (Threshold)
    code = "import ctypes; import os; os._exit(0)"

    is_safe, violations, score = aegis_verifier.verify_code(code, {"tool_name": "risky_tool"})

    assert is_safe is False
    assert score >= 3
    assert violations is not None and len(violations) >= 2


def test_verifier_critical_immediate_reject():
    """Verify that any CRITICAL violation causes immediate rejection regardless of score."""
    code = "open('/etc/shadow', 'r')"  # System File Access = CRITICAL

    is_safe, _, score = aegis_verifier.verify_code(code, {"tool_name": "critical_tool"})

    assert is_safe is False
    assert score >= RiskLevel.CRITICAL.value
