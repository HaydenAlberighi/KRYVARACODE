"""
OSInterface for KRYVARACODE Omega-Prime.
Provides low-level control and semantic UI automation via the Accessibility Tree.
"""

import logging
from typing import Any

# ML and UI dependencies are handled with a lazy import pattern
pyautogui: Any = None
pywinauto: Any = None
_PYAUTOGUI_AVAILABLE = False
_PYWINAUTO_AVAILABLE = False

try:
    import pyautogui

    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    _PYAUTOGUI_AVAILABLE = False

try:
    from pywinauto import Application

    _PYWINAUTO_AVAILABLE = True
except ImportError:
    _PYWINAUTO_AVAILABLE = False

logger = logging.getLogger(__name__)


class OSInterface:
    """
    Interacts with the Operating System to simulate human input.
    Supports both coordinate-based actions and semantic Accessibility Tree targeting.
    """

    def __init__(self):
        if _PYAUTOGUI_AVAILABLE:
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.1
        else:
            logger.warning("PyAutoGUI not installed. OSInterface will run in SIMULATION MODE.")

    def find_element_by_text(self, text: str) -> tuple[int, int] | None:
        """
        Upgraded: Uses the Accessibility Tree (via pywinauto) to find an element's
        coordinates based on semantic text rather than fixed pixels.
        """
        if not _PYWINAUTO_AVAILABLE:
            logger.warning("pywinauto not available. Cannot perform semantic lookup. Falling back to simulation.")
            return (100, 100)  # Simulation fallback

        try:
            # Connect to the active window
            app = Application().connect(active_window=True)
            window = app.top_window()

            # Search for element by text (simplified implementation)
            element = window.child_window(title=text, control_type="Button")  # Example: focus on buttons
            if element.exists():
                rect = element.rectangle()
                # Return center of the element
                return (rect.left + rect.width() // 2, rect.top + rect.height() // 2)
        except Exception as e:
            logger.error(f"Accessibility Tree lookup failed for '{text}': {e}")

        return None

    def semantic_click(self, text: str) -> bool:
        """
        High-level action: Finds a UI element by its semantic text and clicks it.
        """
        logger.info(f"Attempting semantic click on element: {text}")
        coords = self.find_element_by_text(text)
        if coords:
            return self.click(coords[0], coords[1])

        logger.error(f"Could not find element with text '{text}' in accessibility tree.")
        return False

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> bool:
        """Simulates a mouse click at the specified coordinates."""
        logger.info(f"Clicking {button} button at ({x}, {y})")
        if not _PYAUTOGUI_AVAILABLE:
            return True

        try:
            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            return True
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False

    def type_text(self, text: str, interval: float = 0.1) -> bool:
        """Simulates keyboard typing."""
        logger.info(f"Typing text: {text[:20]}...")
        if not _PYAUTOGUI_AVAILABLE:
            return True

        try:
            pyautogui.write(text, interval=interval)
            return True
        except Exception as e:
            logger.error(f"Typing failed: {e}")
            return False

    def press_key(self, key: str) -> bool:
        """Simulates a single key press."""
        logger.info(f"Pressing key: {key}")
        if not _PYAUTOGUI_AVAILABLE:
            return True

        try:
            pyautogui.press(key)
            return True
        except Exception as e:
            logger.error(f"Key press failed: {e}")
            return False

    def hotkey(self, *keys: str) -> bool:
        """Simulates a keyboard shortcut."""
        logger.info(f"Executing hotkey: {'+'.join(keys)}")
        if not _PYAUTOGUI_AVAILABLE:
            return True

        try:
            pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            logger.error(f"Hotkey failed: {e}")
            return False

    def move_to(self, x: int, y: int, duration: float = 0.2) -> bool:
        """Moves the cursor to specific coordinates."""
        logger.info(f"Moving cursor to ({x}, {y})")
        if not _PYAUTOGUI_AVAILABLE:
            return True

        try:
            pyautogui.moveTo(x, y, duration=duration)
            return True
        except Exception as e:
            logger.error(f"Move to failed: {e}")
            return False

    def get_screen_size(self) -> tuple[int, int]:
        """Returns the current screen resolution."""
        if not _PYAUTOGUI_AVAILABLE:
            return (1920, 1080)
        return pyautogui.size()


# Global singleton
os_interface = OSInterface()
