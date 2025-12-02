"""Session Management - Unified session handling for SDK workflows.

Consolidates SessionData, SessionUtilities, and ConversationSession from
previously duplicated implementations.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class SessionData:
    """Unified session data container.
    
    Consolidates duplicate SessionData from session_extractor.py and session_viewer.py
    """
    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    costs: Dict[str, float] = field(default_factory=dict)
    status: str = "active"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "messages": self.messages,
            "tool_calls": self.tool_calls,
            "costs": self.costs,
            "status": self.status,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
            metadata=data.get("metadata", {}),
            messages=data.get("messages", []),
            tool_calls=data.get("tool_calls", []),
            costs=data.get("costs", {}),
            status=data.get("status", "active"),
        )
    
    def add_message(self, role: str, content: str, **kwargs) -> None:
        """Add a message to the session."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        })
        self.updated_at = datetime.now()
    
    def add_tool_call(self, tool_name: str, input_data: Dict, output_data: Any = None) -> None:
        """Record a tool call."""
        self.tool_calls.append({
            "tool": tool_name,
            "input": input_data,
            "output": output_data,
            "timestamp": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now()


class SessionUtilities:
    """Session utility functions for session management workflows.
    
    Consolidates duplicate implementations from sdk_workflow_enhancements.py
    """
    
    def __init__(self, sessions_dir: Optional[Path] = None):
        self.sessions_dir = sessions_dir or Path.home() / ".claude" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._active_sessions: Dict[str, SessionData] = {}
    
    def create_session(self, session_id: Optional[str] = None, **metadata) -> SessionData:
        """Create a new session."""
        import uuid
        sid = session_id or str(uuid.uuid4())[:8]
        session = SessionData(session_id=sid, metadata=metadata)
        self._active_sessions[sid] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Retrieve session by ID."""
        if session_id in self._active_sessions:
            return self._active_sessions[session_id]
        
        # Try loading from disk
        session_file = self.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            with open(session_file) as f:
                data = json.load(f)
            session = SessionData.from_dict(data)
            self._active_sessions[session_id] = session
            return session
        return None
    
    def save_session(self, session: SessionData) -> Path:
        """Persist session to disk."""
        session_file = self.sessions_dir / f"{session.session_id}.json"
        with open(session_file, "w") as f:
            json.dump(session.to_dict(), f, indent=2)
        return session_file
    
    def list_sessions(self) -> List[str]:
        """List all session IDs."""
        sessions = list(self._active_sessions.keys())
        for f in self.sessions_dir.glob("*.json"):
            sid = f.stem
            if sid not in sessions:
                sessions.append(sid)
        return sessions
    
    def close_session(self, session_id: str) -> bool:
        """Close and archive a session."""
        session = self.get_session(session_id)
        if session:
            session.status = "closed"
            self.save_session(session)
            self._active_sessions.pop(session_id, None)
            return True
        return False


class ConversationSession:
    """High-level conversation session manager.
    
    Provides conversation-oriented interface for SDK interactions.
    """
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        system_prompt: Optional[str] = None,
        max_turns: int = 100,
    ):
        self.utilities = SessionUtilities()
        self.session = self.utilities.create_session(session_id)
        self.model = model
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.turn_count = 0
        self._hooks: Dict[str, List[Callable]] = {}
    
    @property
    def session_id(self) -> str:
        return self.session.session_id
    
    def add_hook(self, event: str, callback: Callable) -> None:
        """Register an event hook."""
        self._hooks.setdefault(event, []).append(callback)
    
    def _trigger_hooks(self, event: str, data: Any) -> None:
        """Trigger all hooks for an event."""
        for hook in self._hooks.get(event, []):
            try:
                hook(data)
            except Exception as e:
                logger.warning(f"Hook error for {event}: {e}")
    
    async def send_message(self, content: str, **kwargs) -> Dict[str, Any]:
        """Send a message and get response."""
        self.session.add_message("user", content, **kwargs)
        self.turn_count += 1
        self._trigger_hooks("pre_send", {"content": content, "turn": self.turn_count})
        
        # This would integrate with actual SDK client
        response = {
            "role": "assistant",
            "content": f"[Response to: {content[:50]}...]",
            "turn": self.turn_count,
        }
        
        self.session.add_message("assistant", response["content"])
        self._trigger_hooks("post_response", response)
        
        return response
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get conversation history."""
        messages = self.session.messages
        if limit:
            messages = messages[-limit:]
        return messages
    
    def save(self) -> Path:
        """Persist the session."""
        return self.utilities.save_session(self.session)
    
    def close(self) -> None:
        """Close the session."""
        self.utilities.close_session(self.session_id)


# Utility functions
def get_project_sessions_dir(project_name: str = "default") -> Path:
    """Get project-specific sessions directory.
    
    Consolidates duplicate implementations from session_extractor.py and session_viewer.py
    """
    base_dir = Path.home() / ".claude" / "projects" / project_name / "sessions"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


__all__ = [
    'SessionData',
    'SessionUtilities', 
    'ConversationSession',
    'get_project_sessions_dir',
]
