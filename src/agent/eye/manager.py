"""
EyeManager for KRYVARACODE Omega-Prime.
The high-level API that coordinates vision and OS control into a seamless 'See-Act' loop.
"""

import logging
from typing import Any

from src.agent.eye.os_interface import os_interface
from src.agent.eye.perception_loop import perception_loop
from src.agent.eye.vision_bridge import vision_bridge

logger = logging.getLogger(__name__)


class EyeManager:
    """
    The sovereign interface for environmental interaction.
    Translates high-level intent ("Click the Submit button") into
    coordinated Vision and OS actions.
    """

    def __init__(self):
        self.vision = vision_bridge
        self.os = os_interface
        self.perception = perception_loop

    def observe(self, target_label: str | None = None) -> dict[str, Any]:
        """
        Captures the current state of the world.
        If target_label is provided, it focuses the analysis on that specific element.
        """
        logger.info(f"Observing environment... Target: {target_label or 'General'}")

        screenshot = self.vision.capture_screenshot()
        ui_map = self.vision.analyze_screen(
            screenshot, f"Focus on {target_label}" if target_label else "General scan"
        )

        # Sync with process state
        system_state = self.perception.sync_environment()

        return {"ui_map": [vars(el) for el in ui_map], "system_state": system_state}

    def act_on_element(
        self, label: str, action: str = "click", value: str | None = None
    ) -> bool:
        """
        The core 'See-Act' primitive.
        1. Perceives current UI.
        2. Resolves semantic label to coordinates.
        3. Executes OS-level input.
        """
        logger.info(f"Attempting to {action} element: {label}")

        # 1. See
        screenshot = self.vision.capture_screenshot()
        ui_map = self.vision.analyze_screen(screenshot, f"Find the {label} element")
        coords = self.vision.resolve_element_coordinates(label, ui_map)

        if not coords:
            logger.error(f"Could not resolve coordinates for {label}. Action aborted.")
            return False

        x, y = coords

        # 2. Act
        if action == "click":
            return self.os.click(x, y)
        elif action == "type":
            if value is None:
                logger.error("Action 'type' requires a 'value' argument.")
                return False
            self.os.move_to(x, y)
            self.os.click(x, y)
            return self.os.type_text(value)
        elif action == "right_click":
            return self.os.click(x, y, button="right")
        else:
            logger.warning(f"Unknown action '{action}' requested.")
            return False

    def perform_workflow(self, steps: list[dict[str, Any]]) -> bool:
        """
        Executes a sequence of visual actions.
        Example step: {"label": "search_bar", "action": "type", "value": "Omega-Prime"}
        """
        for i, step in enumerate(steps):
            logger.info(f"Executing workflow step {i + 1}/{len(steps)}")
            success = self.act_on_element(
                step["label"], step.get("action", "click"), step.get("value")
            )
            if not success:
                logger.error(f"Workflow failed at step {i + 1}: {step['label']}")
                return False
        return True


# Global singleton
eye_manager = EyeManager()
