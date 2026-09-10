"""
Sovereign Metabolic Governor for KRYVARACODE.
Prevents the recursive swarm from consuming excessive system resources
or blowing through API budgets.
"""

import logging
import time

import psutil

logger = logging.getLogger(__name__)


class MetabolicGovernor:
    """
    Monitors system 'vital signs' (CPU, RAM, API Costs) and
    enforces throttling or termination of the recursive loop.
    """

    def __init__(
        self,
        cpu_threshold: float = 80.0,
        ram_threshold: float = 85.0,
        max_api_cost_per_session: float = 10.0,
    ):
        self.cpu_threshold = cpu_threshold
        self.ram_threshold = ram_threshold
        self.max_api_cost_per_session = max_api_cost_per_session
        self.session_cost = 0.0

    def check_vitals(self) -> tuple[bool, str]:
        """
        Checks current system resources.
        Returns (is_healthy, reason).
        """
        cpu_usage = psutil.cpu_percent(interval=0.1)
        ram_usage = psutil.virtual_memory().percent

        if cpu_usage > self.cpu_threshold:
            return (
                False,
                f"CPU usage too high: {cpu_usage}% (Threshold: {self.cpu_threshold}%)",
            )

        if ram_usage > self.ram_threshold:
            return (
                False,
                f"RAM usage too high: {ram_usage}% (Threshold: {self.ram_threshold}%)",
            )

        if self.session_cost > self.max_api_cost_per_session:
            return (
                False,
                f"API cost limit exceeded: ${self.session_cost} (Limit: ${self.max_api_cost_per_session})",
            )

        return True, "Vitals healthy."

    def record_cost(self, cost: float):
        """Accumulates API costs for the current session."""
        self.session_cost += cost
        if self.session_cost > self.max_api_cost_per_session:
            logger.warning(f"Metabolic limit reached! Session cost: ${self.session_cost}")

    def throttle(self, duration_seconds: float = 5.0):
        """Forces the agent to pause to let system resources recover."""
        logger.info(f"Governor enforcing metabolic pause for {duration_seconds}s...")
        time.sleep(duration_seconds)


# Global singleton
metabolic_governor = MetabolicGovernor()
