from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict
from threading import RLock
from typing import Any, Awaitable, Callable, DefaultDict, List


# Common event names used by the Quantum Life AI engine pipeline.
TASK_RECEIVED = "TASK_RECEIVED"
CONTEXT_READY = "CONTEXT_READY"
PREDICTIONS_READY = "PREDICTIONS_READY"
DECISION_READY = "DECISION_READY"
SCHEDULE_READY = "SCHEDULE_READY"

EventCallback = Callable[[dict[str, Any]], Any]


class EventBus:
    """Thread-safe asynchronous event bus for engine-to-engine communication.

    The bus keeps a registry of callbacks per event name. Callbacks may be
    synchronous functions or async coroutines. Published events are dispatched
    concurrently using asyncio.
    """

    def __init__(self) -> None:
        # A re-entrant lock protects listener registration and removal across threads.
        self._lock = RLock()

        # Each event name maps to a list of callbacks interested in that event.
        self._listeners: DefaultDict[str, List[EventCallback]] = defaultdict(list)

        # Use the module logger so applications can control logging centrally.
        self._logger = logging.getLogger(__name__)

    def register_listener(self, event_name: str, callback: EventCallback) -> None:
        """Register a listener callback for an event."""
        with self._lock:
            if callback not in self._listeners[event_name]:
                self._listeners[event_name].append(callback)
                self._logger.debug(
                    "Registered listener for event '%s': %s",
                    event_name,
                    self._describe_callback(callback),
                )

    def remove_listener(self, event_name: str, callback: EventCallback) -> None:
        """Remove a previously registered listener for an event."""
        with self._lock:
            listeners = self._listeners.get(event_name, [])
            if callback in listeners:
                listeners.remove(callback)
                self._logger.debug(
                    "Removed listener for event '%s': %s",
                    event_name,
                    self._describe_callback(callback),
                )

            if not listeners and event_name in self._listeners:
                self._listeners.pop(event_name, None)

    async def publish_event(self, event_name: str, data: dict[str, Any]) -> None:
        """Publish an event and asynchronously notify all listeners.

        Every registered listener receives the same event data payload.
        Async listeners are awaited directly. Sync listeners run in the default
        thread executor so they do not block the event loop.
        """
        listeners = self._snapshot_listeners(event_name)
        self._logger.info(
            "Publishing event '%s' to %d listener(s)",
            event_name,
            len(listeners),
        )

        if not listeners:
            return

        tasks = [
            self._dispatch_listener(event_name=event_name, callback=callback, data=data)
            for callback in listeners
        ]
        await asyncio.gather(*tasks)

    def _snapshot_listeners(self, event_name: str) -> List[EventCallback]:
        """Take a stable copy of listeners so dispatch is safe during mutation."""
        with self._lock:
            return list(self._listeners.get(event_name, []))

    async def _dispatch_listener(
        self,
        *,
        event_name: str,
        callback: EventCallback,
        data: dict[str, Any],
    ) -> None:
        """Dispatch one callback and log success or failure."""
        callback_name = self._describe_callback(callback)
        self._logger.debug("Dispatching event '%s' to %s", event_name, callback_name)

        try:
            if inspect.iscoroutinefunction(callback):
                await callback(data)
            else:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, callback, data)

            self._logger.debug("Listener completed for event '%s': %s", event_name, callback_name)
        except Exception:
            self._logger.exception(
                "Listener failed while handling event '%s': %s",
                event_name,
                callback_name,
            )
            raise

    def _describe_callback(self, callback: EventCallback) -> str:
        """Return a readable callback name for logs."""
        return getattr(callback, "__qualname__", repr(callback))
