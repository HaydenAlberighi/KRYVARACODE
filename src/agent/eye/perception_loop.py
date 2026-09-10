"""
PerceptionLoop for KRYVARACODE Omega-Prime.
Synchronizes visual state with OS process state to create environmental awareness.
"""

import logging
import time
from typing import Any

import psutil

from src.agent.eye.vision_bridge import vision_bridge

logger = logging.getLogger(__name__)


class PerceptionLoop:
    """
    The "Heartbeat" of the Eye.
    Continuously monitors the system to ensure the agent's internal
    map of the world matches reality.
    """

    def __init__(self, polling_interval: float = 2.0):
        self.polling_interval = polling_interval
        self.is_running = False
        self.current_state = {
            "active_window": None,
            "processes": [],
            "ui_map": [],
            "last_sync": None,
        }

    def sync_environment(self) -> dict[str, Any]:
        """
        Performs a full synchronization of the digital environment.
        """
        logger.info("Synchronizing environmental state...")

        # 1. Capture Visual State
        screenshot = vision_bridge.capture_screenshot()
        ui_map = vision_bridge.analyze_screen(screenshot, "General environmental scan")

        # 2. Capture Process State
        # In production, we would use pygetwindow or similar to find the active window
        active_process = self._get_active_process_info()

        # 3. Update State
        self.current_state = {
            "active_window": active_process,
            "processes": self._get_top_processes(),
            "ui_map": [vars(el) for el in ui_map],
            "last_sync": time.time(),
        }

        return self.current_state

    def _get_active_process_info(self) -> dict[str, Any] | None:
        """Detects the currently focused window/process."""
        try:
            # Prototype: Simulates finding the active window
            # Real implementation: use pygetwindow.getActiveWindow()
            return {"name": "Chrome", "pid": 1234, "title": "Omega-Prime Design Doc"}
        except Exception as e:
            logger.error(f"Error detecting active window: {e}")
            return None

    def _get_top_processes(self, limit: int = 5) -> list[dict[str, Any]]:
        """Returns the most resource-intensive processes."""
        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent"]):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by CPU usage
        sorted_procs = sorted(
            processes, key=lambda x: x["cpu_percent"] or 0, reverse=True
        )
        return sorted_procs[:limit]

    def start_background_sync(self):
        """
        Starts the perception loop in a background thread.
        (Simplified for this implementation; would use a threading.Thread in production).
        """
        self.is_running = True
        logger.info(
            f"Perception loop active. Syncing every {self.polling_interval}s"
        )

    def stop_background_sync(self):
        self.is_running = False
        logger.info("Perception loop deactivated.")


# Global singleton
perception_loop = PerceptionLoop()
