"""
The Nerve: Real-time Event Stream for Omega-Prime.
Provides asynchronous monitoring of the operating system environment to trigger
immediate Sovereign reactions to external changes.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Watchdog is the industry standard for cross-platform file system monitoring
try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler

    _WATCHDOG_AVAILABLE = True
except ImportError:
    _WATCHDOG_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class SystemEvent:
    """A standardized event emitted by The Nerve."""

    event_type: (
        str  # 'file_modified', 'process_started', 'network_change', 'resource_spike'
    )
    source: str  # Path to file, Process ID, or Interface name
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    priority: str = "medium"


class EventBus:
    """
    The central nervous system of Omega-Prime.
    Collects raw OS events and emits them to registered subscribers (like SovereignManager).
    """

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._running = False

    def subscribe(self, event_type: str, callback: Callable[[SystemEvent], Any]):
        """Register a callback for a specific type of system event."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug(
            f"Subscribed to {event_type}. Total subscribers: {len(self._subscribers[event_type])}"
        )

    async def emit(self, event: SystemEvent):
        """Push an event into the bus for asynchronous distribution."""
        await self._event_queue.put(event)

    async def start_dispatch_loop(self):
        """The main distribution loop that drains the queue and notifies subscribers."""
        self._running = True
        logger.info("The Nerve: Event dispatch loop started.")
        try:
            while self._running:
                event = await self._event_queue.get()

                # Notify specific subscribers
                if event.event_type in self._subscribers:
                    for callback in self._subscribers[event.event_type]:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(event)
                            else:
                                callback(event)
                        except Exception as e:
                            logger.error(
                                f"Error in event subscriber for {event.event_type}: {e}"
                            )

                # Notify universal subscribers (wildcard '*')
                if "*" in self._subscribers:
                    for callback in self._subscribers["*"]:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(event)
                            else:
                                callback(event)
                        except Exception as e:
                            logger.error(f"Error in universal event subscriber: {e}")

                self._event_queue.task_done()
        except asyncio.CancelledError:
            self._running = False
            logger.info("The Nerve: Dispatch loop shutting down.")

    def stop(self):
        self._running = False


class OSWatcher(FileSystemEventHandler):
    """
    Bridge between OS-level file system events and the EventBus.
    """

    def __init__(self, bus: EventBus, watch_paths: list[str]):
        self.bus = bus
        self.watch_paths = watch_paths

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return

        # We use asyncio.create_task because watchdog callbacks are synchronous
        # but our bus is asynchronous.
        asyncio.create_task(
            self.bus.emit(
                SystemEvent(
                    event_type="file_modified",
                    source=event.src_path,
                    payload={
                        "action": "modified",
                        "timestamp": datetime.now().isoformat(),
                    },
                )
            )
        )

    def on_created(self, event: FileSystemEvent):
        asyncio.create_task(
            self.bus.emit(
                SystemEvent(
                    event_type="file_created",
                    source=event.src_path,
                    payload={"action": "created"},
                )
            )
        )


class NerveManager:
    """
    Coordinates the EventBus and the OS-level watchers.
    """

    def __init__(self, watch_paths: list[str] | None = None):
        self.bus = EventBus()
        self.watch_paths = watch_paths or []
        self.observer: Any | None = None

    async def initialize(self):
        """Starts the event bus and the OS observers."""
        # 1. Start the dispatch loop in the background
        asyncio.create_task(self.bus.start_dispatch_loop())

        # 2. Setup File System Watchers if watchdog is installed
        if _WATCHDOG_AVAILABLE and self.watch_paths:
            from watchdog.observers import Observer

            self.observer = Observer()
            handler = OSWatcher(self.bus, self.watch_paths)

            for path in self.watch_paths:
                p = Path(path)
                if p.exists():
                    self.observer.schedule(handler, str(p), recursive=True)
                    logger.info(f"The Nerve: Now watching {path}")

            self.observer.start()
        elif not _WATCHDOG_AVAILABLE:
            logger.warning(
                "The Nerve: watchdog library not found. File system monitoring disabled."
            )

    def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.bus.stop()


# Global singleton
nerve_manager = NerveManager(watch_paths=["C:\\Users\\User\\KRYVARACODE\\src"])
