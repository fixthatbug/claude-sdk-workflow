"""
Type definitions for SDK Workflow.
Contains: ExecutionResult, SessionState, Message, and related types.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import uuid
class ExecutionMode(Enum):
    """Execution mode for the SDK workflow."""
    ONESHOT = "oneshot"
    STREAMING = "streaming"
    ORCHESTRATOR = "orchestrator"
class SessionStatus(Enum):
    """Session lifecycle status."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    CHECKPOINTED = "checkpointed"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"
    TERMINATED = "terminated"
class ErrorSeverity(Enum):
    """Error severity levels."""
    RECOVERABLE = "recoverable"
    DEGRADABLE = "degradable"
    BLOCKING = "blocking"
    CRITICAL = "critical"
class ErrorCategory(Enum):
    """Error category for routing recovery strategies."""
    TRANSIENT = "transient" # Network timeout, rate limit
    RESOURCE = "resource" # Out of memory, quota exceeded
    LOGIC = "logic" # Code error, invalid input
    PERMISSION = "permission" # Auth failure, access denied
    EXTERNAL = "external" # Third-party API failure
@dataclass
class TokenUsage:
    """Token usage tracking."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_input = self.input_tokens + self.cache_read_tokens
        if total_input == 0:
            return 0.0
        return self.cache_read_tokens / total_input
@dataclass
class CostBreakdown:
    """Cost breakdown for a request."""
    input_cost: float = 0.0
    output_cost: float = 0.0
    cache_read_cost: float = 0.0
    cache_write_cost: float = 0.0
    @property
    def total_cost(self) -> float:
        return self.input_cost + self.output_cost + self.cache_read_cost + self.cache_write_cost
@dataclass
class Message:
    """Conversation message."""
    role: str # "user", "assistant", "system"
    content: Union[str, List[Dict[str, Any]]]
    timestamp: datetime = field(default_factory=datetime.now)
    def to_dict(self) -> Dict[str, Any]:
        """Convert to API-compatible dict."""
        return {"role": self.role, "content": self.content}
@dataclass
class ExecutionResult:
    """Result from an executor."""
    content: str
    usage: TokenUsage
    cost: CostBreakdown
    model: str
    mode: ExecutionMode
    stop_reason: Optional[str] = None
    tool_uses: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list) # File paths created
    duration_ms: float = 0.0
    escalated: bool = False # Whether model was escalated during execution
    @property
    def success(self) -> bool:
        return self.stop_reason in ("end_turn", "stop_sequence", None)
@dataclass
class ExecutionError:
    """Structured error information."""
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    attempt: int = 0
    original_exception: Optional[Exception] = None
    context: Dict[str, Any] = field(default_factory=dict)
    def should_retry(self) -> bool:
        """Determine if error is retryable."""
        return (
            self.category == ErrorCategory.TRANSIENT and
            self.severity in (ErrorSeverity.RECOVERABLE, ErrorSeverity.DEGRADABLE)
        )
@dataclass
class Checkpoint:
    """Session checkpoint for resume."""
    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.now)
    messages: List[Message] = field(default_factory=list)
    accumulated_text: str = ""
    tool_uses: List[Dict[str, Any]] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost: CostBreakdown = field(default_factory=CostBreakdown)
    metadata: Dict[str, Any] = field(default_factory=dict)
@dataclass
class SessionState:
    """State for a running or paused session."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    workflow_id: Optional[str] = None # Group related sessions
    status: SessionStatus = SessionStatus.CREATED
    mode: ExecutionMode = ExecutionMode.ONESHOT
    model: str = "haiku"
    system_prompt: str = ""
    messages: List[Message] = field(default_factory=list)
    checkpoints: List[Checkpoint] = field(default_factory=list)
    total_usage: TokenUsage = field(default_factory=TokenUsage)
    total_cost: CostBreakdown = field(default_factory=CostBreakdown)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    def add_message(self, role: str, content: Union[str, List]) -> None:
        """Add message to conversation."""
        self.messages.append(Message(role=role, content=content))
        self.updated_at = datetime.now()
    def create_checkpoint(self, accumulated_text: str = "") -> Checkpoint:
        """Create a checkpoint of current state."""
        checkpoint = Checkpoint(
            messages=self.messages.copy(),
            accumulated_text=accumulated_text,
            usage=self.total_usage,
            cost=self.total_cost,
        )
        self.checkpoints.append(checkpoint)
        self.status = SessionStatus.CHECKPOINTED
        return checkpoint
    def to_dict(self) -> Dict[str, Any]:
        """Serialize session state."""
        return {
            "session_id": self.session_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "mode": self.mode.value,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "messages": [m.to_dict() for m in self.messages],
            "total_usage": {
                "input_tokens": self.total_usage.input_tokens,
                "output_tokens": self.total_usage.output_tokens,
                "cache_read_tokens": self.total_usage.cache_read_tokens,
                "cache_write_tokens": self.total_usage.cache_write_tokens,
            },
            "total_cost": {
                "input_cost": self.total_cost.input_cost,
                "output_cost": self.total_cost.output_cost,
                "cache_read_cost": self.total_cost.cache_read_cost,
                "cache_write_cost": self.total_cost.cache_write_cost,
            },
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionState":
        """Deserialize session state."""
        state = cls(
            session_id=data["session_id"],
            workflow_id=data.get("workflow_id"),
            status=SessionStatus(data["status"]),
            mode=ExecutionMode(data["mode"]),
            model=data["model"],
            system_prompt=data["system_prompt"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
        )
        # Restore messages
        for msg_data in data.get("messages", []):
            state.messages.append(Message(
                role=msg_data["role"],
                content=msg_data["content"],
            ))
        # Restore usage
        usage_data = data.get("total_usage", {})
        state.total_usage = TokenUsage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            cache_read_tokens=usage_data.get("cache_read_tokens", 0),
            cache_write_tokens=usage_data.get("cache_write_tokens", 0),
        )
        # Restore cost
        cost_data = data.get("total_cost", {})
        state.total_cost = CostBreakdown(
            input_cost=cost_data.get("input_cost", 0.0),
            output_cost=cost_data.get("output_cost", 0.0),
            cache_read_cost=cost_data.get("cache_read_cost", 0.0),
            cache_write_cost=cost_data.get("cache_write_cost", 0.0),
        )
        return state
@dataclass
class SubagentTask:
    """Task definition for subagent delegation."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_type: str = "expert-clone"
    prompt: str = ""
    system_prompt: str = ""
    model: Optional[str] = None # Override default
    dependencies: List[str] = field(default_factory=list) # Task IDs this depends on
    timeout: float = 300.0 # 5 minutes default
    metadata: Dict[str, Any] = field(default_factory=dict)
@dataclass
class SubagentResult:
    """Result from subagent execution."""
    task_id: str
    success: bool
    content: str
    usage: TokenUsage
    cost: CostBreakdown
    duration_ms: float
    error: Optional[ExecutionError] = None
