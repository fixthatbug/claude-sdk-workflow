"""Session and checkpoint management for SDK workflow.
Provides persistent state management for long-running workflows,
enabling session tracking, checkpointing, and recovery.
"""
import json
import uuid
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
class SessionStatus(Enum):
    """Session lifecycle states."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
@dataclass
class Session:
    """Represents an SDK workflow session."""
    id: str
    mode: str # oneshot, streaming, orchestrator
    task: str
    status: str
    model: str
    created_at: str
    updated_at: str
    system_prompt: Optional[str] = None
    messages: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None
    result: Optional[Any] = None
    sdk_session_id: Optional[str] = None # Claude SDK session ID for resume
    def to_dict(self) -> dict:
        return asdict(self)
    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        return cls(**data)
    def save_to_file(self, file_path: Path) -> None:
        """
        Save session to a JSON file.
        Args:
            file_path: Path to save the session file
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    @classmethod
    def load_from_file(cls, file_path: Path) -> "Session":
        """
        Load session from a JSON file.
        Args:
            file_path: Path to the session file
        Returns:
            Session instance
        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
        """
        with open(file_path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
@dataclass
class Checkpoint:
    """Represents a session checkpoint for recovery."""
    id: str
    session_id: str
    created_at: str
    state: dict
    messages: list
    metadata: dict = field(default_factory=dict)
    def to_dict(self) -> dict:
        return asdict(self)
    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(**data)
class SessionManager:
    """Manages SDK workflow sessions.
    Provides CRUD operations for sessions with file-based persistence.
    Sessions are stored as JSON files in the sessions directory.
    Usage:
        manager = SessionManager()
        # Create new session
        session = manager.create(
            mode="orchestrator",
            task="Implement user dashboard",
            model="claude-sonnet-4-20250514"
        )
        # Update status
        manager.update(session.id, status="running")
        # List active sessions
        for s in manager.list_active():
            print(f"{s.id}: {s.task} ({s.status})")
    """
    def __init__(self, storage_dir: Optional[Path] = None):
        """Initialize session manager.
        Args:
            storage_dir: Directory for session files. Defaults to
                        ~/.claude/sdk-workflow/sessions/
        """
        self.storage_dir = storage_dir or Path.home() / ".claude" / "sdk-workflow" / "sessions"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
    def _get_session_file(self, session_id: str) -> Path:
        """Get path to session file."""
        return self.storage_dir / f"{session_id}.json"
    def _generate_id(self) -> str:
        """Generate unique session ID."""
        return f"sess_{uuid.uuid4().hex[:12]}"
    def create(
        self,
        mode: str,
        task: str,
        model: str = "claude-sonnet-4-20250514",
        system_prompt: Optional[str] = None,
        metadata: Optional[dict] = None,
        sdk_session_id: Optional[str] = None
    ) -> Session:
        """Create a new session.
        Args:
            mode: Execution mode (oneshot, streaming, orchestrator).
            task: Task description.
            model: Model to use.
            system_prompt: Optional system prompt.
            metadata: Optional additional metadata.
            sdk_session_id: Claude SDK session ID for resume capability.
        Returns:
            Newly created Session object.
        """
        now = datetime.now().isoformat()
        session = Session(
            id=self._generate_id(),
            mode=mode,
            task=task,
            status=SessionStatus.CREATED.value,
            model=model,
            created_at=now,
            updated_at=now,
            system_prompt=system_prompt,
            messages=[],
            metadata=metadata or {},
            sdk_session_id=sdk_session_id
        )
        with self._lock:
            session_file = self._get_session_file(session.id)
            with open(session_file, "w") as f:
                json.dump(session.to_dict(), f, indent=2)
        return session
    def get(self, session_id: str) -> Optional[Session]:
        """Retrieve a session by ID.
        Args:
            session_id: Session identifier.
        Returns:
            Session object or None if not found.
        """
        session_file = self._get_session_file(session_id)
        if not session_file.exists():
            return None
        try:
            with open(session_file, "r") as f:
                data = json.load(f)
            return Session.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None
    def update(
        self,
        session_id: str,
        status: Optional[str] = None,
        messages: Optional[list] = None,
        append_message: Optional[dict] = None,
        metadata: Optional[dict] = None,
        error: Optional[str] = None,
        result: Optional[Any] = None,
        sdk_session_id: Optional[str] = None
    ) -> Optional[Session]:
        """Update an existing session.
        Args:
            session_id: Session identifier.
            status: New status value.
            messages: Replace entire message list.
            append_message: Append single message to history.
            metadata: Update metadata (merges with existing).
            error: Set error message.
            result: Set final result.
            sdk_session_id: Update Claude SDK session ID.
        Returns:
            Updated Session object or None if not found.
        """
        session = self.get(session_id)
        if not session:
            return None
        with self._lock:
            if status is not None:
                session.status = status
            if messages is not None:
                session.messages = messages
            if append_message is not None:
                session.messages.append(append_message)
            if metadata is not None:
                session.metadata.update(metadata)
            if error is not None:
                session.error = error
            if result is not None:
                session.result = result
            if sdk_session_id is not None:
                session.sdk_session_id = sdk_session_id
            session.updated_at = datetime.now().isoformat()
            session_file = self._get_session_file(session_id)
            with open(session_file, "w") as f:
                json.dump(session.to_dict(), f, indent=2)
        return session
    def delete(self, session_id: str) -> bool:
        """Delete a session.
        Args:
            session_id: Session identifier.
        Returns:
            True if deleted, False if not found.
        """
        session_file = self._get_session_file(session_id)
        if session_file.exists():
            with self._lock:
                session_file.unlink()
            return True
        return False
    def list_active(self) -> list[Session]:
        """List all active (non-terminal) sessions.
        Returns:
            List of sessions with status in (created, running, paused).
        """
        active_statuses = {
            SessionStatus.CREATED.value,
            SessionStatus.RUNNING.value,
            SessionStatus.PAUSED.value
        }
        sessions = []
        for file in self.storage_dir.glob("sess_*.json"):
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                session = Session.from_dict(data)
                if session.status in active_statuses:
                    sessions.append(session)
            except (json.JSONDecodeError, KeyError):
                continue
        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions
    def list_all(
        self,
        status_filter: Optional[str] = None,
        mode_filter: Optional[str] = None,
        limit: Optional[int] = None
    ) -> list[Session]:
        """List sessions with optional filters.
        Args:
            status_filter: Filter by status value.
            mode_filter: Filter by mode value.
            limit: Maximum number of sessions to return.
        Returns:
            List of matching sessions.
        """
        sessions = []
        for file in self.storage_dir.glob("sess_*.json"):
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                session = Session.from_dict(data)
                if status_filter and session.status != status_filter:
                    continue
                if mode_filter and session.mode != mode_filter:
                    continue
                sessions.append(session)
            except (json.JSONDecodeError, KeyError):
                continue
        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        if limit:
            return sessions[:limit]
        return sessions
    def cleanup_old(self, days: int = 7) -> int:
        """Remove sessions older than specified days.
        Args:
            days: Age threshold in days.
        Returns:
            Number of sessions removed.
        """
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0
        for file in self.storage_dir.glob("sess_*.json"):
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                updated = datetime.fromisoformat(data["updated_at"])
                if updated < cutoff:
                    with self._lock:
                        file.unlink()
                    removed += 1
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return removed
class CheckpointManager:
    """Manages session checkpoints for recovery.
    Checkpoints capture session state at specific points, enabling
    recovery from failures or resumption of paused work.
    Usage:
        checkpoints = CheckpointManager()
        # Save checkpoint during long operation
        cp = checkpoints.save(
            session_id="sess_abc123",
            state={"phase": 2, "completed_tasks": ["a", "b"]},
            messages=conversation_history
        )
        # Later, recover from checkpoint
        restored = checkpoints.load(cp.id)
        # Resume from restored.state
    """
    def __init__(self, storage_dir: Optional[Path] = None):
        """Initialize checkpoint manager.
        Args:
            storage_dir: Directory for checkpoint files. Defaults to
                        ~/.claude/sdk-workflow/sessions/checkpoints/
        """
        self.storage_dir = (
            storage_dir or
            Path.home() / ".claude" / "sdk-workflow" / "sessions" / "checkpoints"
        )
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
    def _get_checkpoint_file(self, checkpoint_id: str) -> Path:
        """Get path to checkpoint file."""
        return self.storage_dir / f"{checkpoint_id}.json"
    def _generate_id(self) -> str:
        """Generate unique checkpoint ID."""
        return f"cp_{uuid.uuid4().hex[:12]}"
    def save(
        self,
        session_id: str,
        state: dict,
        messages: list,
        metadata: Optional[dict] = None
    ) -> Checkpoint:
        """Create a new checkpoint.
        Args:
            session_id: Associated session ID.
            state: Current workflow state to save.
            messages: Current message history.
            metadata: Optional additional metadata.
        Returns:
            Newly created Checkpoint object.
        """
        checkpoint = Checkpoint(
            id=self._generate_id(),
            session_id=session_id,
            created_at=datetime.now().isoformat(),
            state=state,
            messages=messages,
            metadata=metadata or {}
        )
        with self._lock:
            cp_file = self._get_checkpoint_file(checkpoint.id)
            with open(cp_file, "w") as f:
                json.dump(checkpoint.to_dict(), f, indent=2)
        return checkpoint
    def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Load a checkpoint by ID.
        Args:
            checkpoint_id: Checkpoint identifier.
        Returns:
            Checkpoint object or None if not found.
        """
        cp_file = self._get_checkpoint_file(checkpoint_id)
        if not cp_file.exists():
            return None
        try:
            with open(cp_file, "r") as f:
                data = json.load(f)
            return Checkpoint.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None
    def list(
        self,
        session_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> list[Checkpoint]:
        """List checkpoints with optional session filter.
        Args:
            session_id: Filter by session ID.
            limit: Maximum number to return.
        Returns:
            List of matching checkpoints.
        """
        checkpoints = []
        for file in self.storage_dir.glob("cp_*.json"):
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                checkpoint = Checkpoint.from_dict(data)
                if session_id and checkpoint.session_id != session_id:
                    continue
                checkpoints.append(checkpoint)
            except (json.JSONDecodeError, KeyError):
                continue
        # Sort by created_at descending
        checkpoints.sort(key=lambda c: c.created_at, reverse=True)
        if limit:
            return checkpoints[:limit]
        return checkpoints
    def get_latest(self, session_id: str) -> Optional[Checkpoint]:
        """Get the most recent checkpoint for a session.
        Args:
            session_id: Session identifier.
        Returns:
            Latest checkpoint or None if none exist.
        """
        checkpoints = self.list(session_id=session_id, limit=1)
        return checkpoints[0] if checkpoints else None
    def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.
        Args:
            checkpoint_id: Checkpoint identifier.
        Returns:
            True if deleted, False if not found.
        """
        cp_file = self._get_checkpoint_file(checkpoint_id)
        if cp_file.exists():
            with self._lock:
                cp_file.unlink()
            return True
        return False
    def delete_for_session(self, session_id: str) -> int:
        """Delete all checkpoints for a session.
        Args:
            session_id: Session identifier.
        Returns:
            Number of checkpoints deleted.
        """
        deleted = 0
        for cp in self.list(session_id=session_id):
            if self.delete(cp.id):
                deleted += 1
        return deleted
    def cleanup_old(self, days: int = 3) -> int:
        """Remove checkpoints older than specified days.
        Args:
            days: Age threshold in days.
        Returns:
            Number of checkpoints removed.
        """
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0
        for file in self.storage_dir.glob("cp_*.json"):
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                created = datetime.fromisoformat(data["created_at"])
                if created < cutoff:
                    with self._lock:
                        file.unlink()
                    removed += 1
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return removed
