"""
Real-time progress tracking for SDK workflow sessions.
Provides progress updates, status tracking, and completion handling
with message bus integration for streaming updates.
"""
from __future__ import annotations
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
from .message_bus import EventType, MessageBus, get_default_bus
logger = logging.getLogger(__name__)
class ProgressStatus(str, Enum):
    """Status states for progress tracking."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
@dataclass
class ProgressPhase:
    """Represents a phase within the progress tracker."""
    name: str
    total_steps: int
    current_step: int = 0
    status: ProgressStatus = ProgressStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    message: str = ""
    metadata: dict = field(default_factory=dict)
    @property
    def progress_pct(self) -> float:
        """Calculate progress percentage."""
        if self.total_steps == 0:
            return 100.0 if self.status == ProgressStatus.COMPLETED else 0.0
        return (self.current_step / self.total_steps) * 100
    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time in seconds."""
        if self.started_at is None:
            return 0.0
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()
@dataclass
class ProgressSnapshot:
    """Immutable snapshot of progress state."""
    session_id: str
    status: ProgressStatus
    current_phase: Optional[str]
    phases: dict[str, dict]
    overall_progress_pct: float
    elapsed_seconds: float
    message: str
    result: Any
    error: Optional[str]
    timestamp: datetime = field(default_factory=datetime.now)
class ProgressTracker:
    """
    Real-time progress tracking with streaming updates.
    Tracks multi-phase progress with step-level granularity.
    Integrates with MessageBus for real-time progress streaming.
    Example:
        tracker = ProgressTracker("session-123")
        tracker.start()
        tracker.update("parsing", 1, 10, "Parsing file 1 of 10")
        tracker.update("parsing", 2, 10, "Parsing file 2 of 10")
        ...
        tracker.update("parsing", 10, 10, "Parsing complete")
        tracker.update("analysis", 1, 5, "Analyzing patterns")
        ...
        tracker.on_complete({"findings": [...]})
    """
    def __init__(
        self,
        session_id: str,
        message_bus: Optional[MessageBus] = None,
        auto_publish: bool = True,
    ):
        """
        Initialize progress tracker.
        Args:
            session_id: Unique session identifier.
            message_bus: MessageBus for publishing updates (uses default if None).
            auto_publish: Automatically publish progress updates to bus.
        """
        self.session_id = session_id
        self._bus = message_bus or get_default_bus()
        self._auto_publish = auto_publish
        self._lock = threading.RLock()
        self._status = ProgressStatus.PENDING
        self._phases: dict[str, ProgressPhase] = {}
        self._phase_order: list[str] = []
        self._current_phase: Optional[str] = None
        self._started_at: Optional[datetime] = None
        self._completed_at: Optional[datetime] = None
        self._result: Any = None
        self._error: Optional[str] = None
        self._message: str = ""
        # Callbacks
        self._on_update_callbacks: list[Callable[[ProgressSnapshot], None]] = []
        self._on_complete_callbacks: list[Callable[[Any], None]] = []
        self._on_error_callbacks: list[Callable[[str], None]] = []
    def start(self, message: str = "Starting...") -> None:
        """Start progress tracking."""
        with self._lock:
            self._status = ProgressStatus.RUNNING
            self._started_at = datetime.now()
            self._message = message
        self._publish_update()
        logger.info(f"Progress started for session {self.session_id}")
    def add_phase(
        self,
        phase: str,
        total_steps: int,
        position: Optional[int] = None,
    ) -> None:
        """
        Pre-register a phase with known total steps.
        Args:
            phase: Phase name.
            total_steps: Total steps in this phase.
            position: Position in phase order (appends if None).
        """
        with self._lock:
            self._phases[phase] = ProgressPhase(name=phase, total_steps=total_steps)
            if phase not in self._phase_order:
                if position is not None:
                    self._phase_order.insert(position, phase)
                else:
                    self._phase_order.append(phase)
    def update(
        self,
        phase: str,
        step: int,
        total: int,
        message: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Update progress for a specific phase.
        Args:
            phase: Phase name.
            step: Current step (1-indexed).
            total: Total steps in phase.
            message: Human-readable progress message.
            metadata: Optional additional data.
        """
        with self._lock:
            # Create phase if not exists
            if phase not in self._phases:
                self._phases[phase] = ProgressPhase(name=phase, total_steps=total)
                self._phase_order.append(phase)
            phase_obj = self._phases[phase]
            # Start phase if first update
            if phase_obj.status == ProgressStatus.PENDING:
                phase_obj.status = ProgressStatus.RUNNING
                phase_obj.started_at = datetime.now()
            phase_obj.current_step = step
            phase_obj.total_steps = total
            phase_obj.message = message
            if metadata:
                phase_obj.metadata.update(metadata)
            # Complete phase if at total
            if step >= total:
                phase_obj.status = ProgressStatus.COMPLETED
                phase_obj.completed_at = datetime.now()
            self._current_phase = phase
            self._message = message
        self._publish_update()
        self._notify_callbacks()
    def increment(
        self,
        phase: str,
        message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Increment progress by one step.
        Args:
            phase: Phase name.
            message: Optional updated message.
            metadata: Optional additional data.
        """
        with self._lock:
            if phase not in self._phases:
                raise ValueError(f"Phase '{phase}' not found. Call add_phase or update first.")
            phase_obj = self._phases[phase]
            new_step = phase_obj.current_step + 1
            new_message = message or phase_obj.message
        self.update(phase, new_step, phase_obj.total_steps, new_message, metadata)
    def set_phase_status(
        self,
        phase: str,
        status: ProgressStatus,
        message: Optional[str] = None,
    ) -> None:
        """Manually set phase status."""
        with self._lock:
            if phase in self._phases:
                phase_obj = self._phases[phase]
                phase_obj.status = status
                if message:
                    phase_obj.message = message
                if status == ProgressStatus.COMPLETED:
                    phase_obj.completed_at = datetime.now()
        self._publish_update()
    def pause(self, message: str = "Paused") -> None:
        """Pause progress tracking."""
        with self._lock:
            self._status = ProgressStatus.PAUSED
            self._message = message
        self._publish_update()
    def resume(self, message: str = "Resumed") -> None:
        """Resume progress tracking."""
        with self._lock:
            self._status = ProgressStatus.RUNNING
            self._message = message
        self._publish_update()
    def on_complete(self, result: Any) -> None:
        """
        Mark progress as complete with result.
        Args:
            result: The final result of the tracked operation.
        """
        with self._lock:
            self._status = ProgressStatus.COMPLETED
            self._completed_at = datetime.now()
            self._result = result
            self._message = "Completed"
            # Complete any running phases
            for phase_obj in self._phases.values():
                if phase_obj.status == ProgressStatus.RUNNING:
                    phase_obj.status = ProgressStatus.COMPLETED
                    phase_obj.completed_at = datetime.now()
        self._publish_complete(result)
        self._notify_complete_callbacks(result)
        logger.info(f"Progress completed for session {self.session_id}")
    def on_error(self, error: str, exception: Optional[Exception] = None) -> None:
        """
        Mark progress as failed with error.
        Args:
            error: Error message.
            exception: Optional exception object.
        """
        with self._lock:
            self._status = ProgressStatus.FAILED
            self._completed_at = datetime.now()
            self._error = error
            self._message = f"Failed: {error}"
        self._publish_error(error, exception)
        self._notify_error_callbacks(error)
        logger.error(f"Progress failed for session {self.session_id}: {error}")
    def cancel(self, reason: str = "Cancelled by user") -> None:
        """Cancel the tracked operation."""
        with self._lock:
            self._status = ProgressStatus.CANCELLED
            self._completed_at = datetime.now()
            self._message = reason
        self._publish_update()
    def get_status(self) -> dict:
        """
        Get current progress status as dictionary.
        Returns:
            Dictionary with full progress state.
        """
        snapshot = self.get_snapshot()
        return {
            "session_id": snapshot.session_id,
            "status": snapshot.status.value,
            "current_phase": snapshot.current_phase,
            "phases": snapshot.phases,
            "overall_progress_pct": snapshot.overall_progress_pct,
            "elapsed_seconds": snapshot.elapsed_seconds,
            "message": snapshot.message,
            "result": snapshot.result,
            "error": snapshot.error,
            "timestamp": snapshot.timestamp.isoformat(),
        }
    def get_snapshot(self) -> ProgressSnapshot:
        """Get immutable snapshot of current progress state."""
        with self._lock:
            phases_dict = {}
            for name, phase in self._phases.items():
                phases_dict[name] = {
                    "current_step": phase.current_step,
                    "total_steps": phase.total_steps,
                    "progress_pct": phase.progress_pct,
                    "status": phase.status.value,
                    "message": phase.message,
                    "elapsed_seconds": phase.elapsed_seconds,
                    "metadata": phase.metadata,
                }
            return ProgressSnapshot(
                session_id=self.session_id,
                status=self._status,
                current_phase=self._current_phase,
                phases=phases_dict,
                overall_progress_pct=self._calculate_overall_progress(),
                elapsed_seconds=self._calculate_elapsed(),
                message=self._message,
                result=self._result,
                error=self._error,
            )
    def _calculate_overall_progress(self) -> float:
        """Calculate overall progress across all phases."""
        if not self._phases:
            if self._status == ProgressStatus.COMPLETED:
                return 100.0
            return 0.0
        total_steps = sum(p.total_steps for p in self._phases.values())
        completed_steps = sum(p.current_step for p in self._phases.values())
        if total_steps == 0:
            return 100.0 if self._status == ProgressStatus.COMPLETED else 0.0
        return (completed_steps / total_steps) * 100
    def _calculate_elapsed(self) -> float:
        """Calculate total elapsed time."""
        if self._started_at is None:
            return 0.0
        end = self._completed_at or datetime.now()
        return (end - self._started_at).total_seconds()
    def _publish_update(self) -> None:
        """Publish progress update to message bus."""
        if not self._auto_publish:
            return
        self._bus.publish(
            EventType.PROGRESS_UPDATE,
            self.get_status(),
            source=self.session_id,
        )
    def _publish_complete(self, result: Any) -> None:
        """Publish completion event."""
        if not self._auto_publish:
            return
        self._bus.publish(
            EventType.TASK_COMPLETE,
            {
                "session_id": self.session_id,
                "result": result,
                "elapsed_seconds": self._calculate_elapsed(),
            },
            source=self.session_id,
        )
    def _publish_error(self, error: str, exception: Optional[Exception]) -> None:
        """Publish error event."""
        if not self._auto_publish:
            return
        self._bus.publish(
            EventType.ERROR,
            {
                "session_id": self.session_id,
                "error": error,
                "error_type": type(exception).__name__ if exception else "Error",
                "elapsed_seconds": self._calculate_elapsed(),
            },
            source=self.session_id,
        )
    # Callback registration
    def add_update_callback(self, callback: Callable[[ProgressSnapshot], None]) -> None:
        """Register callback for progress updates."""
        self._on_update_callbacks.append(callback)
    def add_complete_callback(self, callback: Callable[[Any], None]) -> None:
        """Register callback for completion."""
        self._on_complete_callbacks.append(callback)
    def add_error_callback(self, callback: Callable[[str], None]) -> None:
        """Register callback for errors."""
        self._on_error_callbacks.append(callback)
    def _notify_callbacks(self) -> None:
        """Notify registered update callbacks."""
        snapshot = self.get_snapshot()
        for callback in self._on_update_callbacks:
            try:
                callback(snapshot)
            except Exception as e:
                logger.error(f"Error in update callback: {e}")
    def _notify_complete_callbacks(self, result: Any) -> None:
        """Notify registered completion callbacks."""
        for callback in self._on_complete_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Error in complete callback: {e}")
    def _notify_error_callbacks(self, error: str) -> None:
        """Notify registered error callbacks."""
        for callback in self._on_error_callbacks:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
    # Context manager support
    def __enter__(self) -> "ProgressTracker":
        """Start tracking on context entry."""
        self.start()
        return self
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Complete or fail tracking on context exit."""
        if exc_type is not None:
            self.on_error(str(exc_val), exc_val)
        elif self._status == ProgressStatus.RUNNING:
            self.on_complete(None)
class ProgressBar:
    """
    Simple progress bar for console output.
    Example:
        bar = ProgressBar(total=100, prefix="Processing")
        for i in range(100):
            bar.update(i + 1)
        bar.finish()
    """
    def __init__(
        self,
        total: int,
        prefix: str = "",
        width: int = 40,
        fill: str = "=",
        empty: str = "-",
    ):
        self.total = total
        self.prefix = prefix
        self.width = width
        self.fill = fill
        self.empty = empty
        self.current = 0
        self._start_time = time.time()
    def update(self, current: int, message: str = "") -> str:
        """Update progress bar and return formatted string."""
        self.current = current
        pct = (current / self.total) * 100 if self.total > 0 else 100
        filled = int(self.width * current / self.total) if self.total > 0 else self.width
        bar = self.fill * filled + self.empty * (self.width - filled)
        elapsed = time.time() - self._start_time
        line = f"\r{self.prefix} [{bar}] {pct:5.1f}% ({current}/{self.total})"
        if message:
            line += f" - {message}"
        return line
    def finish(self, message: str = "Done") -> str:
        """Complete the progress bar."""
        return self.update(self.total, message)
