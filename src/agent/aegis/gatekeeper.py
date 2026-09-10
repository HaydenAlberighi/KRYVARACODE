"""
Sovereign Aegis Gatekeeper for KRYVARACODE.
Implements the Human-in-the-Loop (HITL) mechanism for high-risk autonomous actions
using a formalized request/response protocol.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class ApprovalRequest:
    """A formalized request for human intervention."""

    request_id: str
    action_id: str
    description: str
    risk_level: str  # "HIGH", "CRITICAL"
    timestamp: datetime = field(default_factory=datetime.now)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalResponse:
    """A formalized response from a human operator."""

    request_id: str
    status: ApprovalStatus
    operator_id: str
    reason: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


class AegisGatekeeper:
    """
    The Gatekeeper intercepts high-risk actions and manages the
    synchronous approval lifecycle between the Agent and the Operator.
    """

    def __init__(self):
        self._pending_requests: dict[str, ApprovalRequest] = {}
        self._approval_history: dict[str, ApprovalResponse] = {}

    def request_approval(
        self,
        action_id: str,
        description: str,
        risk_level: str,
        context: dict | None = None,
    ) -> bool:
        """
        Initiates a formal approval request.

        Returns:
            Boolean indicating if the action is permitted.
        """
        request_id = f"req_{int(datetime.now().timestamp())}_{action_id}"
        request = ApprovalRequest(
            request_id=request_id,
            action_id=action_id,
            description=description,
            risk_level=risk_level,
            context=context or {},
        )

        self._pending_requests[request_id] = request

        logger.info(f"--- HITL GATE TRIGGERED [{risk_level}] ---")
        logger.info(f"Request ID: {request_id}")
        logger.info(f"Action: {action_id}")
        logger.info(f"Description: {description}")

        response = self._simulate_operator_response(request)

        self._process_response(response)
        return response.status == ApprovalStatus.APPROVED

    def _simulate_operator_response(self, request: ApprovalRequest) -> ApprovalResponse:
        """
        Simulates an operator's decision.
        In production, this blocks until an external signal is received.
        """
        status = ApprovalStatus.APPROVED
        reason = "Action within safety parameters."

        if "DELETE" in request.description.upper() and request.risk_level == "CRITICAL":
            status = ApprovalStatus.REJECTED
            reason = "Destructive action rejected by operator."

        return ApprovalResponse(
            request_id=request.request_id,
            status=status,
            operator_id="simulated_operator_01",
            reason=reason,
        )

    def _process_response(self, response: ApprovalResponse):
        """Logs the outcome and cleans up pending requests."""
        self._approval_history[response.request_id] = response
        if response.request_id in self._pending_requests:
            del self._pending_requests[response.request_id]

        if response.status == ApprovalStatus.APPROVED:
            logger.info(
                f"Sovereign Gatekeeper: Request {response.request_id} APPROVED."
            )
        else:
            logger.warning(
                f"Sovereign Gatekeeper: Request {response.request_id} REJECTED. Reason: {response.reason}"
            )

    def verify_action_permit(self, request_id: str) -> bool:
        """Check if a specific request was approved."""
        response = self._approval_history.get(request_id)
        return response is not None and response.status == ApprovalStatus.APPROVED


# Global singleton
aegis_gatekeeper = AegisGatekeeper()
