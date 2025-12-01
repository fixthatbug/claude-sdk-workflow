"""
Concurrent session management for SDK workflow.
Tracks active sessions, enables inter-session communication,
and provides session lifecycle management.
"""
from __future__ import annotations
import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, Protocol, TypeVar
from .message_bus import Event, EventType, MessageBus, get_default_bus
from .progress import ProgressStatus, ProgressTracker
logger = logging.getLogger(__name__)
T = TypeVar("T")
class SessionState(str, Enum):
    """States for session lifecycle."""
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"
class ExecutorProtocol(Protocol):
    """Protocol for session executors."""
    def send_message(self, message: str) -> None:
        """Send a message to the executor."""
        ...
    def terminate(self) -> None:
        """Terminate the executor."""
        ...
    def get_status(self) -> dict:
        """Get executor status."""
        ...
@dataclass
class SessionInfo:
    """Information about a tracked session."""
    session_id: str
    state: SessionState
    executor: Optional[Any]
    progress: Optional[ProgressTracker]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)
    message_queue: list[str] = field(default_factory=list)
    result: Any = None
    error: Optional[str] = None
    parent_session_id: Optional[str] = None
    child_session_ids: list[str] = field(default_factory=list)
    @property
    def is_active(self) -> bool:
        """Check if session is in an active state."""
        return self.state in (
            SessionState.CREATED,
            SessionState.STARTING,
            SessionState.RUNNING,
            SessionState.PAUSED,
        )
    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time."""
        if self.started_at is None:
            return 0.0
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()
class SessionTracker:
    """
    Thread-safe concurrent session management.
    Tracks multiple SDK workflow sessions, enabling:
    - Session registration and lookup
    - Inter-session messaging
    - Lifecycle management
    - Parent-child session relationships
    - Session state transitions
    Example:
        tracker = SessionTracker()
        # Register a new session
        session_id = tracker.register("my-session", executor)
        # Send message to session
        tracker.send_message(session_id, "Focus on error handling")
        # Check active sessions
        active = tracker.list_active()
        # Terminate session
        tracker.terminate(session_id)
    """
    def __init__(self, message_bus: Optional[MessageBus] = None):
        """
        Initialize session tracker.
        Args:
            message_bus: MessageBus for session events (uses default if None).
        """
        self._sessions: dict[str, SessionInfo] = {}
        self._lock = threading.RLock()
        self._bus = message_bus or get_default_bus()
        # Session lookup indices
        self._active_sessions: set[str] = set()
        self._sessions_by_state: dict[SessionState, set[str]] = {
            state: set() for state in SessionState
        }
        # Callbacks
        self._on_state_change: list[Callable[[str, SessionState, SessionState], None]] = []
    def register(
        self,
        session_id: Optional[str] = None,
        executor: Optional[Any] = None,
        metadata: Optional[dict] = None,
        parent_session_id: Optional[str] = None,
        auto_progress: bool = True,
    ) -> str:
        """
        Register a new session.
        Args:
            session_id: Session ID (generated if None).
            executor: Optional executor instance.
            metadata: Optional session metadata.
            parent_session_id: Optional parent session for hierarchies.
            auto_progress: Create ProgressTracker automatically.
        Returns:
            The session ID.
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        progress = ProgressTracker(session_id, self._bus) if auto_progress else None
        session = SessionInfo(
            session_id=session_id,
            state=SessionState.CREATED,
            executor=executor,
            progress=progress,
            created_at=datetime.now(),
            metadata=metadata or {},
            parent_session_id=parent_session_id,
        )
        with self._lock:
            if session_id in self._sessions:
                raise ValueError(f"Session '{session_id}' already exists")
            self._sessions[session_id] = session
            self._sessions_by_state[SessionState.CREATED].add(session_id)
            # Link to parent
            if parent_session_id and parent_session_id in self._sessions:
                self._sessions[parent_session_id].child_session_ids.append(session_id)
        self._publish_event(EventType.SESSION_START, session_id, {
            "state": SessionState.CREATED.value,
            "metadata": metadata,
        })
        logger.info(f"Registered session: {session_id}")
        return session_id
    def get(self, session_id: str) -> Optional[SessionInfo]:
        """
        Get session information.
        Args:
            session_id: The session ID.
        Returns:
            SessionInfo or None if not found.
        """
        with self._lock:
            return self._sessions.get(session_id)
    def get_executor(self, session_id: str) -> Optional[Any]:
        """Get the executor for a session."""
        session = self.get(session_id)
        return session.executor if session else None
    def get_progress(self, session_id: str) -> Optional[ProgressTracker]:
        """Get the progress tracker for a session."""
        session = self.get(session_id)
        return session.progress if session else None
    def set_executor(self, session_id: str, executor: Any) -> bool:
        """
        Set or update the executor for a session.
        Returns:
            True if successful, False if session not found.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            session.executor = executor
            return True
    def list_active(self) -> list[str]:
        """
        List all active session IDs.
        Returns:
            List of session IDs in active states.
        """
        with self._lock:
            return [
                sid for sid, session in self._sessions.items()
                if session.is_active
            ]
    def list_all(self) -> list[str]:
        """List all session IDs."""
        with self._lock:
            return list(self._sessions.keys())
    def list_by_state(self, state: SessionState) -> list[str]:
        """List sessions in a specific state."""
        with self._lock:
            return list(self._sessions_by_state.get(state, set()))
    def get_all_info(self) -> dict[str, dict]:
        """Get information about all sessions."""
        with self._lock:
            return {
                sid: self._session_to_dict(session)
                for sid, session in self._sessions.items()
            }
    def send_message(self, session_id: str, message: str) -> bool:
        """
        Send a message to a session.
        Args:
            session_id: Target session ID.
            message: Message to send.
        Returns:
            True if message was sent/queued, False if session not found.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                logger.warning(f"Cannot send message to unknown session: {session_id}")
                return False
            # Queue message
            session.message_queue.append(message)
            # Try to send via executor
            if session.executor and hasattr(session.executor, "send_message"):
                try:
                    session.executor.send_message(message)
                    logger.debug(f"Sent message to session {session_id}")
                except Exception as e:
                    logger.error(f"Error sending message to session {session_id}: {e}")
        self._publish_event(EventType.MESSAGE_RECEIVED, session_id, {
            "message": message,
        })
        return True
    def broadcast(self, message: str, state_filter: Optional[SessionState] = None) -> int:
        """
        Broadcast message to multiple sessions.
        Args:
            message: Message to broadcast.
            state_filter: Only send to sessions in this state.
        Returns:
            Number of sessions messaged.
        """
        count = 0
        with self._lock:
            for sid, session in self._sessions.items():
                if state_filter and session.state != state_filter:
                    continue
                if session.is_active:
                    self.send_message(sid, message)
                    count += 1
        return count
    def update_state(
        self,
        session_id: str,
        new_state: SessionState,
        error: Optional[str] = None,
        result: Any = None,
    ) -> bool:
        """
        Update session state.
        Args:
            session_id: Session ID.
            new_state: New state to transition to.
            error: Error message (for FAILED state).
            result: Result (for COMPLETED state).
        Returns:
            True if state was updated.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            old_state = session.state
            # Update state indices
            self._sessions_by_state[old_state].discard(session_id)
            self._sessions_by_state[new_state].add(session_id)
            # Update session
            session.state = new_state
            if new_state == SessionState.STARTING:
                session.started_at = datetime.now()
            elif new_state in (SessionState.COMPLETED, SessionState.FAILED, SessionState.TERMINATED):
                session.completed_at = datetime.now()
            if error:
                session.error = error
            if result is not None:
                session.result = result
        # Notify callbacks
        for callback in self._on_state_change:
            try:
                callback(session_id, old_state, new_state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")
        self._publish_event(EventType.STATE_CHANGE, session_id, {
            "old_state": old_state.value,
            "new_state": new_state.value,
            "error": error,
        })
        return True
    def start(self, session_id: str) -> bool:
        """Mark session as starting."""
        return self.update_state(session_id, SessionState.STARTING)
    def running(self, session_id: str) -> bool:
        """Mark session as running."""
        return self.update_state(session_id, SessionState.RUNNING)
    def complete(self, session_id: str, result: Any = None) -> bool:
        """Mark session as completed."""
        return self.update_state(session_id, SessionState.COMPLETED, result=result)
    def fail(self, session_id: str, error: str) -> bool:
        """Mark session as failed."""
        return self.update_state(session_id, SessionState.FAILED, error=error)
    def terminate(self, session_id: str, cascade: bool = True) -> bool:
        """
        Terminate a session.
        Args:
            session_id: Session to terminate.
            cascade: Also terminate child sessions.
        Returns:
            True if terminated successfully.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                logger.warning(f"Cannot terminate unknown session: {session_id}")
                return False
            # Terminate executor
            if session.executor and hasattr(session.executor, "terminate"):
                try:
                    session.executor.terminate()
                except Exception as e:
                    logger.error(f"Error terminating executor for {session_id}: {e}")
            # Cascade to children
            if cascade:
                for child_id in session.child_session_ids:
                    self.terminate(child_id, cascade=True)
        self.update_state(session_id, SessionState.TERMINATED)
        self._publish_event(EventType.SESSION_END, session_id, {
            "reason": "terminated",
        })
        logger.info(f"Terminated session: {session_id}")
        return True
    def terminate_all(self) -> int:
        """Terminate all active sessions."""
        count = 0
        for session_id in self.list_active():
            if self.terminate(session_id, cascade=False):
                count += 1
        return count
    def remove(self, session_id: str) -> bool:
        """
        Remove a session from tracking.
        Only removes completed/failed/terminated sessions.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            if session.is_active:
                logger.warning(f"Cannot remove active session: {session_id}")
                return False
            # Remove from indices
            self._sessions_by_state[session.state].discard(session_id)
            # Remove from parent
            if session.parent_session_id:
                parent = self._sessions.get(session.parent_session_id)
                if parent:
                    parent.child_session_ids = [
                        cid for cid in parent.child_session_ids if cid != session_id
                    ]
            del self._sessions[session_id]
        logger.debug(f"Removed session: {session_id}")
        return True
    def cleanup_completed(self, max_age_seconds: float = 3600) -> int:
        """
        Remove old completed sessions.
        Args:
            max_age_seconds: Remove sessions completed more than this many seconds ago.
        Returns:
            Number of sessions removed.
        """
        now = datetime.now()
        to_remove = []
        with self._lock:
            for sid, session in self._sessions.items():
                if not session.is_active and session.completed_at:
                    age = (now - session.completed_at).total_seconds()
                    if age > max_age_seconds:
                        to_remove.append(sid)
        for sid in to_remove:
            self.remove(sid)
        return len(to_remove)
    def get_children(self, session_id: str) -> list[SessionInfo]:
        """Get child sessions."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return []
            return [
                self._sessions[cid]
                for cid in session.child_session_ids
                if cid in self._sessions
            ]
    def get_parent(self, session_id: str) -> Optional[SessionInfo]:
        """Get parent session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.parent_session_id is None:
                return None
            return self._sessions.get(session.parent_session_id)
    def add_state_change_callback(
        self,
        callback: Callable[[str, SessionState, SessionState], None],
    ) -> None:
        """Register callback for state changes."""
        self._on_state_change.append(callback)
    def _session_to_dict(self, session: SessionInfo) -> dict:
        """Convert SessionInfo to dictionary."""
        return {
            "session_id": session.session_id,
            "state": session.state.value,
            "created_at": session.created_at.isoformat(),
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "elapsed_seconds": session.elapsed_seconds,
            "is_active": session.is_active,
            "metadata": session.metadata,
            "message_queue_length": len(session.message_queue),
            "error": session.error,
            "parent_session_id": session.parent_session_id,
            "child_session_ids": session.child_session_ids,
        }
    def _publish_event(self, event_type: EventType, session_id: str, data: dict) -> None:
        """Publish session event to message bus."""
        self._bus.publish(
            event_type,
            {"session_id": session_id, **data},
            source=session_id,
        )
    # Context manager for session lifecycle
    def session_context(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        """
        Context manager for automatic session lifecycle.
        Example:
            with tracker.session_context() as session_id:
                # Session is RUNNING
                do_work()
            # Session is COMPLETED (or FAILED if exception)
        """
        return _SessionContext(self, session_id, metadata)
class _SessionContext:
    """Context manager for session lifecycle."""
    def __init__(
        self,
        tracker: SessionTracker,
        session_id: Optional[str],
        metadata: Optional[dict],
    ):
        self._tracker = tracker
        self._session_id = session_id
        self._metadata = metadata
    def __enter__(self) -> str:
        self._session_id = self._tracker.register(
            self._session_id,
            metadata=self._metadata,
        )
        self._tracker.start(self._session_id)
        self._tracker.running(self._session_id)
        return self._session_id
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self._tracker.fail(self._session_id, str(exc_val))
        else:
            self._tracker.complete(self._session_id)
# Global default tracker instance
_default_tracker: Optional[SessionTracker] = None
def get_default_tracker() -> SessionTracker:
    """Get or create the default global session tracker."""
    global _default_tracker
    if _default_tracker is None:
        _default_tracker = SessionTracker()
    return _default_tracker
def reset_default_tracker() -> None:
    """Reset the default global session tracker."""
    global _default_tracker
    if _default_tracker is not None:
        _default_tracker.terminate_all()
    _default_tracker = None
