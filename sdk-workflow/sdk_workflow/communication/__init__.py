"""
Communication module for sdk-workflow.
Handles inter-process and inter-session communication:
- MessageBus: Event-driven pub/sub messaging
- ProgressTracker: Real-time progress streaming
- SessionTracker: Concurrent session management
- SessionBridge: Communication between orchestrator and subagents
- MessageQueue: Async message passing
- EventBus: Event-driven notifications
Components:
- message_bus: Event-driven pub/sub system
- progress: Progress tracking and streaming
- session_tracker: Session lifecycle management
- bridge: Session-to-session communication
- queue: Message queue implementation
- events: Event publishing and subscription
"""
from .message_bus import (
    MessageBus,
    EventType,
    Event,
    Subscription,
    get_default_bus,
    reset_default_bus,
)
from .progress import (
    ProgressTracker,
    ProgressStatus,
    ProgressSnapshot,
    ProgressPhase,
    ProgressBar,
)
from .session_tracker import (
    SessionTracker,
    SessionState,
    SessionInfo,
    get_default_tracker,
    reset_default_tracker,
)
__all__ = [
    # Message Bus
    "MessageBus",
    "EventType",
    "Event",
    "Subscription",
    "get_default_bus",
    "reset_default_bus",
    # Progress Tracking
    "ProgressTracker",
    "ProgressStatus",
    "ProgressSnapshot",
    "ProgressPhase",
    "ProgressBar",
    # Session Tracking
    "SessionTracker",
    "SessionState",
    "SessionInfo",
    "get_default_tracker",
    "reset_default_tracker",
    # Legacy exports (backward compatibility)
    "SessionBridge",
    "MessageQueue",
    "EventBus",
    "send_message",
    "receive_message",
]
def send_message(session_id: str, message: str, **kwargs) -> bool:
    """
    Send a message to a running session.
    Args:
        session_id: Target session identifier.
        message: Message content to send.
        **kwargs: Additional message metadata.
    Returns:
        True if message was sent successfully.
    """
    # Try new SessionTracker first
    tracker = get_default_tracker()
    if tracker.get(session_id):
        return tracker.send_message(session_id, message)
    # Fall back to legacy bridge
    try:
        from .bridge import SessionBridge
        bridge = SessionBridge()
        return bridge.send(session_id, message, **kwargs)
    except ImportError:
        return False
def receive_message(session_id: str, timeout: float = None):
    """
    Receive a message from a session's output queue.
    Args:
        session_id: Source session identifier.
        timeout: Maximum time to wait (None for non-blocking).
    Returns:
        Message content or None if no message available.
    """
    try:
        from .bridge import SessionBridge
        bridge = SessionBridge()
        return bridge.receive(session_id, timeout=timeout)
    except ImportError:
        return None
# Lazy imports for legacy modules
def __getattr__(name: str):
    if name == "SessionBridge":
        try:
            from .bridge import SessionBridge
            return SessionBridge
        except ImportError:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    elif name == "MessageQueue":
        try:
            from .queue import MessageQueue
            return MessageQueue
        except ImportError:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    elif name == "EventBus":
        try:
            from .events import EventBus
            return EventBus
        except ImportError:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
