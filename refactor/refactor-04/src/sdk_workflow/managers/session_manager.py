"""Session Manager - Consolidated session lifecycle management.

Consolidates session.py, session_data.py, session_utils.py into single module.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionMetrics:
    """Metrics for a session."""
    total_turns: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    cache_hit_rate: float = 0.0
    avg_response_time_ms: float = 0.0


@dataclass 
class SessionData:
    """Session state and history."""
    session_id: str
    workflow_id: Optional[str] = None
    status: str = "created"
    model: str = "sonnet"
    system_prompt: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)
    metrics: SessionMetrics = field(default_factory=SessionMetrics)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """Manage session lifecycle, persistence, and state.
    
    Consolidates:
    - Session creation and management
    - Session data persistence
    - Session utilities and helpers
    """
    
    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path.home() / ".claude" / "sessions"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: Dict[str, SessionData] = {}
        self._active_session: Optional[str] = None
    
    def create(
        self,
        model: str = "sonnet",
        system_prompt: str = "",
        workflow_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> SessionData:
        """Create a new session."""
        session_id = str(uuid.uuid4())[:8]
        
        session = SessionData(
            session_id=session_id,
            workflow_id=workflow_id,
            model=model,
            system_prompt=system_prompt,
            metadata=metadata or {},
        )
        
        self._sessions[session_id] = session
        self._active_session = session_id
        
        logger.debug(f"Created session: {session_id}")
        return session
    
    def get(self, session_id: str) -> Optional[SessionData]:
        """Get session by ID."""
        if session_id in self._sessions:
            return self._sessions[session_id]
        
        # Try loading from disk
        return self._load(session_id)
    
    def get_active(self) -> Optional[SessionData]:
        """Get currently active session."""
        if self._active_session:
            return self.get(self._active_session)
        return None
    
    def update(
        self,
        session_id: str,
        status: Optional[str] = None,
        add_message: Optional[Dict] = None,
        metrics_update: Optional[Dict] = None,
    ) -> Optional[SessionData]:
        """Update session state."""
        session = self.get(session_id)
        if not session:
            return None
        
        if status:
            session.status = status
        
        if add_message:
            session.messages.append(add_message)
            session.metrics.total_turns += 1
        
        if metrics_update:
            for key, value in metrics_update.items():
                if hasattr(session.metrics, key):
                    setattr(session.metrics, key, value)
        
        session.updated_at = datetime.now().isoformat()
        return session
    
    def checkpoint(self, session_id: str, label: str = "") -> Optional[Dict]:
        """Create checkpoint of current state."""
        session = self.get(session_id)
        if not session:
            return None
        
        checkpoint = {
            "checkpoint_id": str(uuid.uuid4())[:8],
            "label": label,
            "timestamp": datetime.now().isoformat(),
            "message_count": len(session.messages),
            "metrics_snapshot": asdict(session.metrics),
        }
        
        session.checkpoints.append(checkpoint)
        session.status = "checkpointed"
        
        return checkpoint
    
    def save(self, session_id: str) -> bool:
        """Persist session to disk."""
        session = self.get(session_id)
        if not session:
            return False
        
        path = self.storage_dir / f"{session_id}.json"
        try:
            data = asdict(session)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")
            return False
    
    def _load(self, session_id: str) -> Optional[SessionData]:
        """Load session from disk."""
        path = self.storage_dir / f"{session_id}.json"
        if not path.exists():
            return None
        
        try:
            with open(path) as f:
                data = json.load(f)
            
            metrics = SessionMetrics(**data.pop("metrics", {}))
            session = SessionData(**data, metrics=metrics)
            self._sessions[session_id] = session
            return session
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None
    
    def list_sessions(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[SessionData]:
        """List sessions with optional filters."""
        # Load all from disk
        for path in self.storage_dir.glob("*.json"):
            session_id = path.stem
            if session_id not in self._sessions:
                self._load(session_id)
        
        sessions = list(self._sessions.values())
        
        if workflow_id:
            sessions = [s for s in sessions if s.workflow_id == workflow_id]
        if status:
            sessions = [s for s in sessions if s.status == status]
        
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)
    
    def close(self, session_id: str, save: bool = True) -> bool:
        """Close and optionally save session."""
        session = self.get(session_id)
        if not session:
            return False
        
        session.status = "completed"
        session.updated_at = datetime.now().isoformat()
        
        if save:
            self.save(session_id)
        
        if self._active_session == session_id:
            self._active_session = None
        
        return True
    
    def resume(self, session_id: str) -> Optional[SessionData]:
        """Resume a saved session."""
        session = self.get(session_id)
        if not session:
            return None
        
        session.status = "running"
        session.updated_at = datetime.now().isoformat()
        self._active_session = session_id
        
        return session


# Utility functions

def generate_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())[:8]


def generate_workflow_id() -> str:
    """Generate a workflow ID for grouping sessions."""
    return f"wf-{str(uuid.uuid4())[:6]}"


__all__ = [
    "SessionMetrics",
    "SessionData",
    "SessionManager",
    "generate_session_id",
    "generate_workflow_id",
]
