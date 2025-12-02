#!/usr/bin/env python3
"""
Session data structures for Claude Agent SDK.

Consolidates SessionData from session_extractor.py and session_viewer.py.
Provides unified data model for session parsing and viewing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MessageData:
    """Individual message in a session."""
    role: str
    content: str
    timestamp: Optional[str] = None
    model: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class ToolCall:
    """Tool call record."""
    name: str
    input: Dict[str, Any] = field(default_factory=dict)
    output: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class ConversationTurn:
    """A single conversation turn (user + assistant)."""
    user_message: Optional[str] = None
    assistant_message: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    thinking: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class SessionData:
    """Unified session data structure.

    Supports both extraction (parsing JSONL) and viewing (rich display) use cases.
    """
    session_id: str
    filepath: Optional[Path] = None
    project_path: Optional[str] = None

    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Messages (simple list)
    messages: List[MessageData] = field(default_factory=list)

    # Conversation (structured turns)
    turns: List[ConversationTurn] = field(default_factory=list)
    user_messages: int = 0
    assistant_messages: int = 0

    # Subagents
    subagent_ids: List[str] = field(default_factory=list)
    agent_ids: List[str] = field(default_factory=list)

    # Token usage
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_creation: int = 0
    total_cache_read: int = 0
    cache_read_tokens: int = 0
    cache_create_tokens: int = 0

    # Tool usage
    tool_calls: List[ToolCall] = field(default_factory=list)
    tools_used: Dict[str, int] = field(default_factory=dict)
    tools_summary: Dict[str, int] = field(default_factory=dict)
    errors: int = 0

    # Metadata
    models_used: List[str] = field(default_factory=list)
    cwd: Optional[str] = None
    version: Optional[str] = None

    # Generated content
    summary: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate session duration in seconds."""
        if not self.start_time or not self.end_time:
            return None
        return (self.end_time - self.start_time).total_seconds()

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.total_input_tokens + self.total_output_tokens

    @property
    def message_count(self) -> int:
        """Total message count."""
        return len(self.messages) or (self.user_messages + self.assistant_messages)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        if self.filepath:
            data["filepath"] = str(self.filepath)
        if self.start_time:
            data["start_time"] = self.start_time.isoformat()
        if self.end_time:
            data["end_time"] = self.end_time.isoformat()
        data["duration_seconds"] = self.duration_seconds
        data["total_tokens"] = self.total_tokens
        return data

    def get_tokens_dict(self) -> Dict[str, int]:
        """Get token usage as dictionary."""
        return {
            "input": self.total_input_tokens,
            "output": self.total_output_tokens,
            "cache_creation": self.total_cache_creation or self.cache_create_tokens,
            "cache_read": self.total_cache_read or self.cache_read_tokens,
            "total": self.total_tokens,
        }

    def get_summary_filename(self) -> str:
        """Generate filename with session ID and summary."""
        safe_summary = ""
        if self.summary:
            safe_summary = "_" + self.summary[:50].replace(" ", "_").replace("/", "-")
        return f"{self.session_id}{safe_summary}"

    def merge_subagent_ids(self) -> List[str]:
        """Get all agent IDs (combining subagent_ids and agent_ids)."""
        return list(set(self.subagent_ids + self.agent_ids))

    def get_tools_summary(self) -> Dict[str, int]:
        """Get unified tools summary (combining tools_used and tools_summary)."""
        combined = dict(self.tools_used)
        for tool, count in self.tools_summary.items():
            combined[tool] = combined.get(tool, 0) + count
        return combined

    @classmethod
    def from_extractor_format(
        cls,
        session_id: str,
        project_path: str,
        **kwargs
    ) -> "SessionData":
        """Create from session_extractor format."""
        start_time = kwargs.get("start_time")
        end_time = kwargs.get("end_time")
        
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

        return cls(
            session_id=session_id,
            project_path=project_path,
            start_time=start_time,
            end_time=end_time,
            messages=kwargs.get("messages", []),
            subagent_ids=kwargs.get("subagent_ids", []),
            total_input_tokens=kwargs.get("total_input_tokens", 0),
            total_output_tokens=kwargs.get("total_output_tokens", 0),
            total_cache_creation=kwargs.get("total_cache_creation", 0),
            total_cache_read=kwargs.get("total_cache_read", 0),
            models_used=kwargs.get("models_used", []),
            tools_used=kwargs.get("tools_used", {}),
        )

    @classmethod
    def from_viewer_format(
        cls,
        session_id: str,
        filepath: Path,
        **kwargs
    ) -> "SessionData":
        """Create from session_viewer format."""
        return cls(
            session_id=session_id,
            filepath=filepath,
            start_time=kwargs.get("start_time"),
            end_time=kwargs.get("end_time"),
            turns=kwargs.get("turns", []),
            user_messages=kwargs.get("user_messages", 0),
            assistant_messages=kwargs.get("assistant_messages", 0),
            tool_calls=kwargs.get("tool_calls", []),
            tools_summary=kwargs.get("tools_summary", {}),
            errors=kwargs.get("errors", 0),
            total_input_tokens=kwargs.get("total_input_tokens", 0),
            total_output_tokens=kwargs.get("total_output_tokens", 0),
            cache_read_tokens=kwargs.get("cache_read_tokens", 0),
            cache_create_tokens=kwargs.get("cache_create_tokens", 0),
            models_used=kwargs.get("models_used", []),
            agent_ids=kwargs.get("agent_ids", []),
            cwd=kwargs.get("cwd"),
            version=kwargs.get("version"),
            summary=kwargs.get("summary"),
            tags=kwargs.get("tags", []),
        )
