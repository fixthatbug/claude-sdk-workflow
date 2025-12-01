"""
Event-driven pub/sub message bus for SDK workflow communication.
Provides decoupled communication between components via event subscription
and publishing patterns.
"""
from __future__ import annotations
import asyncio
import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, Union
from weakref import WeakMethod, ref
logger = logging.getLogger(__name__)
class EventType(str, Enum):
    """Standard event types for SDK workflow communication."""
    TEXT_DELTA = "text_delta"
    TOOL_USE = "tool_use"
    TASK_COMPLETE = "task_complete"
    ERROR = "error"
    CHECKPOINT = "checkpoint"
    # Extended event types
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    PROGRESS_UPDATE = "progress_update"
    SUBAGENT_SPAWN = "subagent_spawn"
    SUBAGENT_COMPLETE = "subagent_complete"
    MESSAGE_RECEIVED = "message_received"
    STATE_CHANGE = "state_change"
    # Mailbox event types
    MESSAGE_SENT = "message_sent"
    SIGNAL_RECEIVED = "signal_received"
    MAILBOX_CLEARED = "mailbox_cleared"
    BROADCAST_SENT = "broadcast_sent"
@dataclass
class Event:
    """Represents an event in the message bus."""
    event_type: str
    data: Any
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: Optional[str] = None
    metadata: dict = field(default_factory=dict)
@dataclass
class Subscription:
    """Represents a subscription to an event type."""
    subscription_id: str
    event_type: str
    callback: Callable
    filter_fn: Optional[Callable[[Event], bool]] = None
    priority: int = 0
    is_async: bool = False
    weak_ref: bool = False
class MessageBus:
    """
    Thread-safe event-driven pub/sub message bus.
    Supports both synchronous and asynchronous callbacks, event filtering,
    priority-based delivery, and weak references for automatic cleanup.
    Example:
        bus = MessageBus()
        def on_progress(event):
            print(f"Progress: {event.data}")
        bus.subscribe("progress_update", on_progress)
        bus.publish("progress_update", {"step": 1, "total": 10})
    """
    def __init__(self, max_history: int = 100):
        """
        Initialize the message bus.
        Args:
            max_history: Maximum number of events to retain in history.
        """
        self._subscribers: dict[str, list[Subscription]] = defaultdict(list)
        self._lock = threading.RLock()
        self._async_lock: Optional[asyncio.Lock] = None
        self._history: list[Event] = []
        self._max_history = max_history
        self._paused = False
        self._pending_events: list[Event] = []
    def _get_async_lock(self) -> asyncio.Lock:
        """Get or create async lock for coroutine safety."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock
    def subscribe(
        self,
        event_type: Union[str, EventType],
        callback: Callable,
        filter_fn: Optional[Callable[[Event], bool]] = None,
        priority: int = 0,
        weak: bool = False,
    ) -> str:
        """
        Subscribe to an event type.
        Args:
            event_type: The event type to subscribe to.
            callback: Function to call when event is published.
            filter_fn: Optional filter to apply before calling callback.
            priority: Higher priority callbacks are called first.
            weak: Use weak reference (auto-unsubscribe when callback owner is GC'd).
        Returns:
            Subscription ID for later unsubscription.
        """
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
        subscription_id = str(uuid.uuid4())
        # Determine if callback is async
        is_async = asyncio.iscoroutinefunction(callback)
        # Handle weak references
        if weak:
            if hasattr(callback, "__self__"):
                # Bound method
                callback = WeakMethod(callback)
            else:
                callback = ref(callback)
        subscription = Subscription(
            subscription_id=subscription_id,
            event_type=event_type_str,
            callback=callback,
            filter_fn=filter_fn,
            priority=priority,
            is_async=is_async,
            weak_ref=weak,
        )
        with self._lock:
            subscribers = self._subscribers[event_type_str]
            subscribers.append(subscription)
            # Sort by priority (higher first)
            subscribers.sort(key=lambda s: s.priority, reverse=True)
        logger.debug(f"Subscribed to '{event_type_str}' with ID {subscription_id}")
        return subscription_id
    def unsubscribe(
        self,
        event_type: Union[str, EventType],
        callback_or_id: Union[Callable, str],
    ) -> bool:
        """
        Unsubscribe from an event type.
        Args:
            event_type: The event type to unsubscribe from.
            callback_or_id: Either the callback function or subscription ID.
        Returns:
            True if unsubscribed successfully, False if not found.
        """
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
        with self._lock:
            subscribers = self._subscribers.get(event_type_str, [])
            for i, sub in enumerate(subscribers):
                if isinstance(callback_or_id, str):
                    # Match by subscription ID
                    if sub.subscription_id == callback_or_id:
                        subscribers.pop(i)
                        logger.debug(f"Unsubscribed ID {callback_or_id} from '{event_type_str}'")
                        return True
                else:
                    # Match by callback
                    actual_callback = sub.callback() if sub.weak_ref else sub.callback
                    if actual_callback == callback_or_id:
                        subscribers.pop(i)
                        logger.debug(f"Unsubscribed callback from '{event_type_str}'")
                        return True
        return False
    def unsubscribe_all(self, event_type: Optional[Union[str, EventType]] = None) -> int:
        """
        Unsubscribe all callbacks from an event type or all types.
        Args:
            event_type: Specific event type, or None for all.
        Returns:
            Number of subscriptions removed.
        """
        with self._lock:
            if event_type is None:
                count = sum(len(subs) for subs in self._subscribers.values())
                self._subscribers.clear()
                return count
            event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
            count = len(self._subscribers.get(event_type_str, []))
            self._subscribers[event_type_str] = []
            return count
    def publish(
        self,
        event_type: Union[str, EventType],
        data: Any,
        source: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Event:
        """
        Publish an event to all subscribers.
        Args:
            event_type: The event type to publish.
            data: Event payload data.
            source: Optional source identifier.
            metadata: Optional additional metadata.
        Returns:
            The created Event object.
        """
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
        event = Event(
            event_type=event_type_str,
            data=data,
            source=source,
            metadata=metadata or {},
        )
        if self._paused:
            self._pending_events.append(event)
            return event
        self._dispatch_event(event)
        return event
    async def publish_async(
        self,
        event_type: Union[str, EventType],
        data: Any,
        source: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Event:
        """
        Asynchronously publish an event to all subscribers.
        Properly awaits async callbacks.
        """
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
        event = Event(
            event_type=event_type_str,
            data=data,
            source=source,
            metadata=metadata or {},
        )
        if self._paused:
            self._pending_events.append(event)
            return event
        await self._dispatch_event_async(event)
        return event
    def _dispatch_event(self, event: Event) -> None:
        """Dispatch event to synchronous subscribers."""
        self._add_to_history(event)
        with self._lock:
            subscribers = list(self._subscribers.get(event.event_type, []))
            # Also notify wildcard subscribers
            subscribers.extend(self._subscribers.get("*", []))
        dead_subscriptions = []
        for sub in subscribers:
            try:
                # Handle weak references
                callback = sub.callback() if sub.weak_ref else sub.callback
                if callback is None:
                    dead_subscriptions.append(sub)
                    continue
                # Apply filter
                if sub.filter_fn and not sub.filter_fn(event):
                    continue
                # Call the callback
                if sub.is_async:
                    # Schedule async callback
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.ensure_future(callback(event))
                        else:
                            loop.run_until_complete(callback(event))
                    except RuntimeError:
                        # No event loop, create one
                        asyncio.run(callback(event))
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Error in subscriber callback: {e}", exc_info=True)
                # Publish error event (avoiding recursion)
                if event.event_type != EventType.ERROR.value:
                    self._dispatch_error(e, event)
        # Clean up dead weak references
        self._cleanup_dead_subscriptions(dead_subscriptions)
    async def _dispatch_event_async(self, event: Event) -> None:
        """Dispatch event to subscribers, awaiting async callbacks."""
        self._add_to_history(event)
        async with self._get_async_lock():
            subscribers = list(self._subscribers.get(event.event_type, []))
            subscribers.extend(self._subscribers.get("*", []))
        dead_subscriptions = []
        tasks = []
        for sub in subscribers:
            try:
                callback = sub.callback() if sub.weak_ref else sub.callback
                if callback is None:
                    dead_subscriptions.append(sub)
                    continue
                if sub.filter_fn and not sub.filter_fn(event):
                    continue
                if sub.is_async:
                    tasks.append(callback(event))
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Error in subscriber callback: {e}", exc_info=True)
        # Await all async callbacks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._cleanup_dead_subscriptions(dead_subscriptions)
    def _dispatch_error(self, error: Exception, source_event: Event) -> None:
        """Dispatch an error event."""
        error_event = Event(
            event_type=EventType.ERROR.value,
            data={
                "error": str(error),
                "error_type": type(error).__name__,
                "source_event": source_event.event_id,
            },
            source=source_event.source,
        )
        self._dispatch_event(error_event)
    def _add_to_history(self, event: Event) -> None:
        """Add event to history, maintaining max size."""
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
    def _cleanup_dead_subscriptions(self, dead: list[Subscription]) -> None:
        """Remove dead weak reference subscriptions."""
        if not dead:
            return
        with self._lock:
            for sub in dead:
                subscribers = self._subscribers.get(sub.event_type, [])
                if sub in subscribers:
                    subscribers.remove(sub)
    def pause(self) -> None:
        """Pause event delivery. Events are queued until resumed."""
        self._paused = True
    def resume(self) -> None:
        """Resume event delivery and dispatch pending events."""
        self._paused = False
        pending = self._pending_events
        self._pending_events = []
        for event in pending:
            self._dispatch_event(event)
    def get_history(
        self,
        event_type: Optional[Union[str, EventType]] = None,
        limit: Optional[int] = None,
    ) -> list[Event]:
        """
        Get event history.
        Args:
            event_type: Filter by event type.
            limit: Maximum number of events to return.
        Returns:
            List of events, most recent last.
        """
        with self._lock:
            history = self._history.copy()
        if event_type:
            event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
            history = [e for e in history if e.event_type == event_type_str]
        if limit:
            history = history[-limit:]
        return history
    def subscriber_count(self, event_type: Optional[Union[str, EventType]] = None) -> int:
        """Get number of subscribers for an event type or total."""
        with self._lock:
            if event_type is None:
                return sum(len(subs) for subs in self._subscribers.values())
            event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
            return len(self._subscribers.get(event_type_str, []))
# Global default message bus instance
_default_bus: Optional[MessageBus] = None
def get_default_bus() -> MessageBus:
    """Get or create the default global message bus."""
    global _default_bus
    if _default_bus is None:
        _default_bus = MessageBus()
    return _default_bus
def reset_default_bus() -> None:
    """Reset the default global message bus."""
    global _default_bus
    _default_bus = None
