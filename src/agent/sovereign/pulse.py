"""
The Pulse: Proactive Intent Generation for Omega-Prime.
Moves the system from a reactive tool to a proactive digital organism.
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.db.models import AuditLog

logger = logging.getLogger(__name__)


@dataclass
class AutonomousGoal:
    goal_id: str
    description: str
    priority: str  # high, medium, low
    trigger_source: str  # e.g., 'latency_spike', 'failure_cluster', 'curiosity'
    context: dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)


class IntentGenerator:
    """
    Analyzes system logs and environmental state to generate intrinsic goals.
    """

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        self.curiosity_threshold = 0.1  # Probability of spawning a 'curiosity' goal

    def scan_for_inefficiencies(self) -> list[AutonomousGoal]:
        """
        Scans the AuditLog for patterns that suggest a need for autonomous improvement.
        """
        goals = []
        with self.db_session_factory() as db:
            # 1. Detect Failure Clusters (e.g., same tool failing repeatedly)
            failure_cluster = db.query(AuditLog).filter(not AuditLog.success).limit(50).all()
            if failure_cluster:
                tool_counts = {}
                for log in failure_cluster:
                    tool_counts[log.tool_name] = tool_counts.get(log.tool_name, 0) + 1

                for tool, count in tool_counts.items():
                    if count > 3:
                        goals.append(
                            AutonomousGoal(
                                goal_id=f"goal_fix_{tool}_{int(datetime.now().timestamp())}",
                                description=f"Optimize and repair tool '{tool}' which has failed {count} times recently.",
                                priority="high",
                                trigger_source="failure_cluster",
                                context={"tool": tool, "failure_count": count},
                            )
                        )

            # 2. Detect Latency Spikes
            slow_logs = db.query(AuditLog).filter(AuditLog.duration_ms > 2000).limit(20).all()
            if slow_logs:
                slow_tools = list({log.tool_name for log in slow_logs})
                if slow_tools:
                    goals.append(
                        AutonomousGoal(
                            goal_id=f"goal_opt_{int(datetime.now().timestamp())}",
                            description=f"Reduce latency for tools: {', '.join(slow_tools)}.",
                            priority="medium",
                            trigger_source="latency_spike",
                            context={"slow_tools": slow_tools},
                        )
                    )

        return goals

    def generate_curiosity_goal(self) -> AutonomousGoal | None:
        """
        Occasionally spawns a goal to explore the environment or test a new hypothesis.
        """
        if random.random() < self.curiosity_threshold:
            hypotheses = [
                "Explore unknown network endpoints for new capabilities.",
                "Test the limits of the current OSInterface semantic targeting.",
                "Attempt to synthesize a tool that optimizes memory retrieval speed.",
                "Analyze the current system architecture for redundant logic.",
            ]
            return AutonomousGoal(
                goal_id=f"goal_curious_{int(datetime.now().timestamp())}",
                description=random.choice(hypotheses),
                priority="low",
                trigger_source="curiosity",
                context={},
            )
        return None

    def pulse(self) -> list[AutonomousGoal]:
        """
        The main heartbeat of the organism: scan for needs and generate intent.
        """
        logger.info("Omega-Prime Pulse: Scanning for intrinsic needs...")

        all_goals = self.scan_for_inefficiencies()
        curiosity = self.generate_curiosity_goal()
        if curiosity:
            all_goals.append(curiosity)

        if all_goals:
            logger.info(f"Pulse generated {len(all_goals)} autonomous goals.")

        return all_goals
