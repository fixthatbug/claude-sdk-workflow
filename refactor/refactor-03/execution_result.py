"""Execution result data structure.

@version 2.0.0 - Standalone module with bounded message storage
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

__all__ = ['ExecutionResult', 'ExecutionMetrics']


# =============================================================================
# Execution Metrics
# =============================================================================

@dataclass
class ExecutionMetrics:
    """Metrics for tracking execution performance and cost.
    
    Attributes:
        input_tokens: Total input tokens consumed
        output_tokens: Total output tokens generated
        cache_read_tokens: Tokens read from cache
        cache_write_tokens: Tokens written to cache
        total_cost_usd: Cumulative cost in USD
        turns: Number of conversation turns
        start_time: Execution start timestamp
        end_time: Execution end timestamp
    """
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_cost_usd: float = 0.0
    turns: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    def add_turn(self, input_tokens: int, output_tokens: int) -> None:
        """Add a turn's token usage."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.turns += 1

    def add_cache(self, read: int = 0, write: int = 0) -> None:
        """Add cache token usage."""
        self.cache_read_tokens += read
        self.cache_write_tokens += write

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)."""
        return self.input_tokens + self.output_tokens

    @property
    def duration_ms(self) -> Optional[int]:
        """Duration in milliseconds."""
        if self.start_time and self.end_time:
            return int((self.end_time - self.start_time).total_seconds() * 1000)
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_tokens': self.total_tokens,
            'cache_read_tokens': self.cache_read_tokens,
            'cache_write_tokens': self.cache_write_tokens,
            'total_cost_usd': self.total_cost_usd,
            'turns': self.turns,
            'duration_ms': self.duration_ms,
        }


# =============================================================================
# Execution Result
# =============================================================================

class ExecutionResult:
    """Result of a task execution.

    Features:
    - Bounded message storage (first 10 + last 40)
    - Tool use tracking with timestamps
    - Cost and metrics integration
    - Lifecycle state management

    Attributes:
        task_id: Unique identifier for this execution
        agent_name: Name of the agent used
        task: Original task description
        status: Execution status (pending, running, completed, failed)
        output: Final text output
        tool_uses: List of tools used during execution
        cost: Cost information dict
        duration_ms: Execution duration in milliseconds
        error: Error message if failed
        session_id: SDK session identifier
        metrics: ExecutionMetrics instance
    """

    __slots__ = (
        'task_id', 'agent_name', 'task', 'status',
        '_messages_head', '_messages_tail', '_total_message_count',
        'output', 'tool_uses', 'cost', 'duration_ms', 'error',
        '_start_time', 'session_id', 'metrics'
    )

    def __init__(
        self,
        task_id: str,
        agent_name: str,
        task: str,
    ):
        self.task_id = task_id
        self.agent_name = agent_name
        self.task = task
        self.status = "pending"
        self._messages_head: List[Any] = []  # First 10 messages
        self._messages_tail: deque = deque(maxlen=40)  # Last 40 messages
        self._total_message_count: int = 0
        self.output = ""
        self.tool_uses: List[Dict[str, Any]] = []
        self.cost: Optional[Dict[str, float]] = None
        self.duration_ms: Optional[int] = None
        self.error: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self.session_id: Optional[str] = None
        self.metrics: Optional[ExecutionMetrics] = None

    # -------------------------------------------------------------------------
    # Lifecycle Methods
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Mark execution as started."""
        self.status = "running"
        self._start_time = datetime.now()
        if self.metrics:
            self.metrics.start_time = self._start_time

    def complete(self, output: str = "") -> None:
        """Mark execution as completed."""
        self.status = "completed"
        self.output = output
        if self._start_time:
            self.duration_ms = int(
                (datetime.now() - self._start_time).total_seconds() * 1000
            )
        if self.metrics:
            self.metrics.end_time = datetime.now()

    def fail(self, error: str) -> None:
        """Mark execution as failed."""
        self.status = "failed"
        self.error = error
        if self._start_time:
            self.duration_ms = int(
                (datetime.now() - self._start_time).total_seconds() * 1000
            )
        if self.metrics:
            self.metrics.end_time = datetime.now()

    # -------------------------------------------------------------------------
    # Message Management (Bounded Storage)
    # -------------------------------------------------------------------------

    @property
    def messages(self) -> List[Any]:
        """Return bounded message list (first 10 + last 40)."""
        return self._messages_head + list(self._messages_tail)

    @property
    def message_count(self) -> int:
        """Total messages received (including dropped)."""
        return self._total_message_count

    def add_message(self, message: Any) -> None:
        """Add message with bounded storage."""
        self._total_message_count += 1
        if len(self._messages_head) < 10:
            self._messages_head.append(message)
        else:
            self._messages_tail.append(message)

    # -------------------------------------------------------------------------
    # Tool Tracking
    # -------------------------------------------------------------------------

    def add_tool_use(self, tool_name: str, tool_input: Dict[str, Any]) -> None:
        """Record a tool use."""
        self.tool_uses.append({
            "tool": tool_name,
            "input": tool_input,
            "timestamp": datetime.now().isoformat()
        })

    # -------------------------------------------------------------------------
    # Cost Management
    # -------------------------------------------------------------------------

    def set_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        total_cost_usd: float,
        cache_read: int = 0,
        cache_write: int = 0,
        model: str = "sonnet"
    ) -> None:
        """Set cost information.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            total_cost_usd: Total cost in USD
            cache_read: Cache read tokens
            cache_write: Cache write tokens
            model: Model used
        """
        self.cost = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read,
            "cache_write_tokens": cache_write,
            "model": model,
            "total_cost_usd": total_cost_usd
        }
        if self.metrics:
            self.metrics.input_tokens = input_tokens
            self.metrics.output_tokens = output_tokens
            self.metrics.cache_read_tokens = cache_read
            self.metrics.cache_write_tokens = cache_write
            self.metrics.total_cost_usd = total_cost_usd

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "task": self.task,
            "status": self.status,
            "output": self.output,
            "tool_uses": self.tool_uses,
            "cost": self.cost,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "message_count": self.message_count,
        }
        if self.metrics:
            result["metrics"] = self.metrics.to_dict()
        return result

    def __repr__(self) -> str:
        return f"ExecutionResult(task_id={self.task_id}, status={self.status})"
