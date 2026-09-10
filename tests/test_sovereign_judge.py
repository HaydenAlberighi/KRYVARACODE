import pytest
from src.agent.sovereign.judge import judge


def test_judge_approves_when_no_flaws():
    """Test that the judge approves when the critic finds no flaws (fallback path)."""
    goal = "Implement a simple API"
    implementation = {"evidence": "API is running on port 8080"}
    critique = {"is_flawed": False, "reason": "No issues found"}

    is_approved, verdict = judge.evaluate(goal, implementation, critique)

    assert is_approved is True
    assert "Approved via fallback" in verdict


def test_judge_rejects_when_flawed_and_no_llm():
    """Test that the judge rejects when flaws exist and LLM is unavailable (fallback path)."""
    goal = "Implement a simple API"
    implementation = {"evidence": "API is running on port 8080"}
    critique = {"is_flawed": True, "reason": "Missing authentication"}

    is_approved, verdict = judge.evaluate(goal, implementation, critique)

    assert is_approved is False
    assert "Rejected via fallback" in verdict


def test_judge_handles_empty_evidence():
    """Test that the judge handles missing evidence gracefully."""
    goal = "Implement a simple API"
    implementation = {}  # No evidence key
    critique = {"is_flawed": True, "reason": "Critical bug"}

    is_approved, verdict = judge.evaluate(goal, implementation, critique)

    assert is_approved is False
    assert "Rejected via fallback" in verdict
