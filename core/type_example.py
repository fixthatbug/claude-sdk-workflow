"""
Production-grade Type Definitions for Claude Agent SDK Workflow.
This module provides comprehensive type definitions for building robust
agent workflows using the Claude Agent SDK for Python. It includes:
- Execution modes and session management
- Error handling with retry strategies
- Token usage and cost tracking
- Message and checkpoint structures
- Subagent task delegation
Based on Claude Agent SDK official documentation and best practices.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, AsyncIterator
import uuid
# ============================================================================
# EXECUTION MODES
# ============================================================================
class ExecutionMode(Enum):
   """
   Execution mode for SDK workflows.
   - QUERY: Single query-response using query() function
   - CLIENT: Continuous conversation using ClaudeSDKClient
   - ORCHESTRATOR: Multi-agent orchestration with subagents
   """
   QUERY = "query" # Aligned with SDK query() function
   CLIENT = "client" # Aligned with ClaudeSDKClient
   ORCHESTRATOR = "orchestrator"
# ============================================================================
# SESSION MANAGEMENT
# ============================================================================
class SessionStatus(Enum):
   """
   Session lifecycle status tracking.
   Maps to Claude Code session states for resume/fork functionality.
   """
   CREATED = "created"
   RUNNING = "running"
   PAUSED = "paused"
   CHECKPOINTED = "checkpointed"
   COMPLETED = "completed"
   FAILED = "failed"
   ESCALATED = "escalated"
   TERMINATED = "terminated"
# ============================================================================
# ERROR HANDLING
# ============================================================================
class ErrorSeverity(Enum):
   """Error severity levels for recovery strategies."""
   RECOVERABLE = "recoverable" # Retry with same config
   DEGRADABLE = "degradable" # Retry with reduced capabilities
   BLOCKING = "blocking" # Requires intervention
   CRITICAL = "critical" # Immediate escalation
class ErrorCategory(Enum):
   """
   Error categories for routing recovery strategies.
   Aligned with common SDK error patterns.
   """
   TRANSIENT = "transient" # Network timeout, rate limit
   RESOURCE = "resource" # Out of memory, quota exceeded
   LOGIC = "logic" # Code error, invalid input
   PERMISSION = "permission" # Auth failure, access denied
   EXTERNAL = "external" # Third-party API/MCP failure
@dataclass
class ExecutionError:
   """
   Structured error information with retry logic.
   Provides context for error handling and recovery strategies.
   """
   message: str
   category: ErrorCategory
   severity: ErrorSeverity
   attempt: int = 0
   original_exception: Optional[Exception] = None
   context: Dict[str, Any] = field(default_factory=dict)
   timestamp: datetime = field(default_factory=datetime.now)
   def should_retry(self) -> bool:
       """
       Determine if error warrants retry.
       Returns:
           True if error is transient and recoverable/degradable.
       """
       return (
           self.category == ErrorCategory.TRANSIENT and
           self.severity in (ErrorSeverity.RECOVERABLE, ErrorSeverity.DEGRADABLE)
       )
   def get_retry_delay(self, base_delay: float = 1.0) -> float:
       """
       Calculate exponential backoff delay.
       Args:
           base_delay: Base delay in seconds
       Returns:
           Delay in seconds for next retry attempt
       """
       return min(base_delay * (2 ** self.attempt), 60.0)
# ============================================================================
# TOKEN USAGE AND COST TRACKING
# ============================================================================
@dataclass
class TokenUsage:
   """
   Token usage tracking for Claude API requests.
   Tracks input, output, and cached token usage for cost optimization.
   """
   input_tokens: int = 0
   output_tokens: int = 0
   cache_read_tokens: int = 0
   cache_write_tokens: int = 0
   @property
   def total_tokens(self) -> int:
       """Total tokens consumed (excluding cache reads)."""
       return self.input_tokens + self.output_tokens
   @property
   def cache_hit_rate(self) -> float:
       """
       Calculate cache hit rate for optimization analysis.
       Returns:
           Ratio of cache reads to total input tokens (0.0 to 1.0)
       """
       total_input = self.input_tokens + self.cache_read_tokens
       if total_input == 0:
           return 0.0
       return self.cache_read_tokens / total_input
   def add(self, other: 'TokenUsage') -> None:
       """Accumulate token usage from another request."""
       self.input_tokens += other.input_tokens
       self.output_tokens += other.output_tokens
       self.cache_read_tokens += other.cache_read_tokens
       self.cache_write_tokens += other.cache_write_tokens
@dataclass
class CostBreakdown:
   """
   Cost breakdown for Claude API usage.
   Tracks costs per token type for budget management.
   """
   input_cost: float = 0.0
   output_cost: float = 0.0
   cache_read_cost: float = 0.0
   cache_write_cost: float = 0.0
   @property
   def total_cost(self) -> float:
       """Total cost in USD."""
       return (
           self.input_cost +
           self.output_cost +
           self.cache_read_cost +
           self.cache_write_cost
       )
   def add(self, other: 'CostBreakdown') -> None:
       """Accumulate costs from another request."""
       self.input_cost += other.input_cost
       self.output_cost += other.output_cost
       self.cache_read_cost += other.cache_read_cost
       self.cache_write_cost += other.cache_write_cost
# ============================================================================
# MESSAGE TYPES
# ============================================================================
@dataclass
class Message:
   """
   Conversation message compatible with Claude SDK.
   Supports both text and structured content blocks as per SDK spec.
   """
   role: str # "user", "assistant", "system"
   content: Union[str, List[Dict[str, Any]]]
   timestamp: datetime = field(default_factory=datetime.now)
   message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
   def to_dict(self) -> Dict[str, Any]:
       """
       Convert to Claude API-compatible dictionary.
       Returns:
           Dict with 'role' and 'content' keys for SDK consumption
       """
       return {
           "role": self.role,
           "content": self.content
       }
   @classmethod
   def from_sdk_message(cls, sdk_msg: Any) -> 'Message':
       """
       Create Message from SDK AssistantMessage or UserMessage.
       Args:
           sdk_msg: Message object from claude_agent_sdk
       Returns:
           Message instance
       """
       # Extract content from SDK message blocks
       content_parts = []
       if hasattr(sdk_msg, 'content'):
           for block in sdk_msg.content:
               if hasattr(block, 'text'):
                   content_parts.append(block.text)
       return cls(
           role=getattr(sdk_msg, 'role', 'assistant'),
           content=' '.join(content_parts) if content_parts else str(sdk_msg)
       )
# ============================================================================
# EXECUTION RESULTS
# ============================================================================
@dataclass
class ExecutionResult:
   """
   Result from Claude SDK query() or ClaudeSDKClient execution.
   Captures response content, usage metrics, and execution metadata.
   """
   content: str
   usage: TokenUsage
   cost: CostBreakdown
   model: str
   mode: ExecutionMode
   stop_reason: Optional[str] = None
   tool_uses: List[Dict[str, Any]] = field(default_factory=list)
   artifacts: List[str] = field(default_factory=list) # File paths created
   duration_ms: float = 0.0
   escalated: bool = False # Model escalation occurred
   session_id: Optional[str] = None # For ClaudeSDKClient sessions
   @property
   def success(self) -> bool:
       """
       Check if execution completed successfully.
       Returns:
           True if stop_reason indicates normal completion
       """
       return self.stop_reason in ("end_turn", "stop_sequence", None)
   @property
   def used_tools(self) -> bool:
       """Check if any tools were invoked during execution."""
       return len(self.tool_uses) > 0
   def get_tool_names(self) -> List[str]:
       """Extract names of all tools used."""
       return [tool.get('name', 'unknown') for tool in self.tool_uses]
# ============================================================================
# CHECKPOINTING
# ============================================================================
@dataclass
class Checkpoint:
   """
   Session checkpoint for pause/resume functionality.
   Enables saving conversation state for later continuation.
   """
   checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
   timestamp: datetime = field(default_factory=datetime.now)
   messages: List[Message] = field(default_factory=list)
   accumulated_text: str = ""
   tool_uses: List[Dict[str, Any]] = field(default_factory=list)
   usage: TokenUsage = field(default_factory=TokenUsage)
   cost: CostBreakdown = field(default_factory=CostBreakdown)
   metadata: Dict[str, Any] = field(default_factory=dict)
   def to_dict(self) -> Dict[str, Any]:
       """Serialize checkpoint for storage."""
       return {
           "checkpoint_id": self.checkpoint_id,
           "timestamp": self.timestamp.isoformat(),
           "messages": [m.to_dict() for m in self.messages],
           "accumulated_text": self.accumulated_text,
           "tool_uses": self.tool_uses,
           "usage": {
               "input_tokens": self.usage.input_tokens,
               "output_tokens": self.usage.output_tokens,
               "cache_read_tokens": self.usage.cache_read_tokens,
               "cache_write_tokens": self.usage.cache_write_tokens,
           },
           "cost": {
               "input_cost": self.cost.input_cost,
               "output_cost": self.cost.output_cost,
               "cache_read_cost": self.cost.cache_read_cost,
               "cache_write_cost": self.cost.cache_write_cost,
           },
           "metadata": self.metadata,
       }
# ============================================================================
# SESSION STATE
# ============================================================================
@dataclass
class SessionState:
   """
   State management for Claude SDK sessions.
   Supports both query() and ClaudeSDKClient execution modes with
   full checkpoint/resume capabilities.
   """
   session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
   workflow_id: Optional[str] = None # Group related sessions
   status: SessionStatus = SessionStatus.CREATED
   mode: ExecutionMode = ExecutionMode.QUERY
   model: str = "claude-sonnet-4-5" # Default model
   system_prompt: str = ""
   messages: List[Message] = field(default_factory=list)
   checkpoints: List[Checkpoint] = field(default_factory=list)
   total_usage: TokenUsage = field(default_factory=TokenUsage)
   total_cost: CostBreakdown = field(default_factory=CostBreakdown)
   created_at: datetime = field(default_factory=datetime.now)
   updated_at: datetime = field(default_factory=datetime.now)
   metadata: Dict[str, Any] = field(default_factory=dict)
   # SDK-specific fields
   resume_session_id: Optional[str] = None # For resume option
   fork_session: bool = False # For fork_session option
   def add_message(self, role: str, content: Union[str, List]) -> None:
       """
       Add message to conversation history.
       Args:
           role: Message role ("user", "assistant", "system")
           content: Message content (text or structured blocks)
       """
       self.messages.append(Message(role=role, content=content))
       self.updated_at = datetime.now()
   def create_checkpoint(self, accumulated_text: str = "") -> Checkpoint:
       """
       Create checkpoint of current state for pause/resume.
       Args:
           accumulated_text: Accumulated response text so far
       Returns:
           Checkpoint object with current state snapshot
       """
       checkpoint = Checkpoint(
           messages=self.messages.copy(),
           accumulated_text=accumulated_text,
           usage=self.total_usage,
           cost=self.total_cost,
           metadata=self.metadata.copy(),
       )
       self.checkpoints.append(checkpoint)
       self.status = SessionStatus.CHECKPOINTED
       self.updated_at = datetime.now()
       return checkpoint
   def update_usage(self, usage: TokenUsage, cost: CostBreakdown) -> None:
       """
       Update cumulative usage and cost metrics.
       Args:
           usage: Token usage from latest request
           cost: Cost breakdown from latest request
       """
       self.total_usage.add(usage)
       self.total_cost.add(cost)
       self.updated_at = datetime.now()
   def to_dict(self) -> Dict[str, Any]:
       """
       Serialize session state for persistence.
       Returns:
           Dictionary representation suitable for JSON storage
       """
       return {
           "session_id": self.session_id,
           "workflow_id": self.workflow_id,
           "status": self.status.value,
           "mode": self.mode.value,
           "model": self.model,
           "system_prompt": self.system_prompt,
           "messages": [m.to_dict() for m in self.messages],
           "checkpoints": [cp.to_dict() for cp in self.checkpoints],
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
           "resume_session_id": self.resume_session_id,
           "fork_session": self.fork_session,
       }
   @classmethod
   def from_dict(cls, data: Dict[str, Any]) -> "SessionState":
       """
       Deserialize session state from storage.
       Args:
           data: Dictionary representation from to_dict()
       Returns:
           Reconstructed SessionState instance
       """
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
            resume_session_id=data.get("resume_session_id"),
            fork_session=data.get("fork_session", False),
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
    def get_api_messages(self) -> List[Dict[str, Any]]:
        """
        Convert messages to Claude API format.
        Returns:
            List of message dicts compatible with Claude Messages API
        """
        return [m.to_dict() for m in self.messages]
# ============================================================================
# SUBAGENT DELEGATION
# ============================================================================
@dataclass
class SubagentTask:
    """
    Task definition for subagent delegation.
    Note: Based on TypeScript SDK patterns. Python SDK subagent support
    may differ. Refer to official documentation for current implementation.
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_type: str = "expert-clone"
    prompt: str = ""
    system_prompt: str = ""
    model: Optional[str] = None # Override default model
    dependencies: List[str] = field(default_factory=list) # Task IDs
    timeout: float = 300.0 # 5 minutes default
    metadata: Dict[str, Any] = field(default_factory=dict)
    max_retries: int = 3
    def to_dict(self) -> Dict[str, Any]:
        """Serialize task for delegation."""
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "prompt": self.prompt,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "dependencies": self.dependencies,
            "timeout": self.timeout,
            "metadata": self.metadata,
            "max_retries": self.max_retries,
        }
@dataclass
class SubagentResult:
    """
    Result from subagent execution.
    Captures outcome, metrics, and any errors from delegated tasks.
    """
    task_id: str
    success: bool
    content: str
    usage: TokenUsage
    cost: CostBreakdown
    duration_ms: float
    error: Optional[ExecutionError] = None
    artifacts: List[str] = field(default_factory=list)
    def to_dict(self) -> Dict[str, Any]:
        """Serialize result for aggregation."""
        return {
            "task_id": self.task_id,
            "success": self.success,
            "content": self.content,
            "usage": {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
                "cache_read_tokens": self.usage.cache_read_tokens,
                "cache_write_tokens": self.usage.cache_write_tokens,
            },
            "cost": {
                "total_cost": self.cost.total_cost,
            },
            "duration_ms": self.duration_ms,
            "error": self.error.message if self.error else None,
            "artifacts": self.artifacts,
        }
# ============================================================================
# ADVANCED USAGE PATTERNS
# ============================================================================
class WorkflowBuilder:
    """
    Builder pattern for constructing complex multi-step workflows.
    Example:
        workflow = (WorkflowBuilder()
            .with_model("claude-sonnet-4-5")
            .with_system_prompt("You are a coding assistant")
            .add_step("analyze", "Analyze the codebase")
            .add_step("refactor", "Refactor based on analysis")
            .build())
    """
    def __init__(self):
        self.workflow_id = str(uuid.uuid4())[:8]
        self.model = "claude-sonnet-4-5"
        self.system_prompt = ""
        self.steps: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
    def with_model(self, model: str) -> 'WorkflowBuilder':
        """Set the model for all steps."""
        self.model = model
        return self
    def with_system_prompt(self, prompt: str) -> 'WorkflowBuilder':
        """Set system prompt for workflow."""
        self.system_prompt = prompt
        return self
    def add_step(self, name: str, prompt: str, **kwargs) -> 'WorkflowBuilder':
        """Add a workflow step."""
        self.steps.append({
            "name": name,
            "prompt": prompt,
            **kwargs
        })
        return self
    def with_metadata(self, **metadata) -> 'WorkflowBuilder':
        """Add workflow metadata."""
        self.metadata.update(metadata)
        return self
    def build(self) -> Dict[str, Any]:
        """Build the workflow configuration."""
        return {
            "workflow_id": self.workflow_id,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "steps": self.steps,
            "metadata": self.metadata,
        }
# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def calculate_cost(usage: TokenUsage, model: str) -> CostBreakdown:
    """
    Calculate cost breakdown based on token usage and model.
    Args:
        usage: Token usage metrics
        model: Model identifier
    Returns:
        Cost breakdown in USD
    Note: Pricing based on Claude API pricing as of documentation date.
    Refer to official pricing page for current rates.
    """
    # Pricing per million tokens (approximate, verify current rates)
    pricing = {
        "claude-opus-4-5": {
            "input": 15.00,
            "output": 75.00,
            "cache_write": 18.75,
            "cache_read": 1.50,
        },
        "claude-sonnet-4-5": {
            "input": 3.00,
            "output": 15.00,
            "cache_write": 3.75,
            "cache_read": 0.30,
        },
        "claude-haiku-4-5": {
            "input": 0.80,
            "output": 4.00,
            "cache_write": 1.00,
            "cache_read": 0.08,
        },
    }
    # Default to Sonnet pricing if model not found
    rates = pricing.get(model, pricing["claude-sonnet-4-5"])
    return CostBreakdown(
        input_cost=(usage.input_tokens / 1_000_000) * rates["input"],
        output_cost=(usage.output_tokens / 1_000_000) * rates["output"],
        cache_write_cost=(usage.cache_write_tokens / 1_000_000) * rates["cache_write"],
        cache_read_cost=(usage.cache_read_tokens / 1_000_000) * rates["cache_read"],
    )
def create_session_from_checkpoint(checkpoint: Checkpoint) -> SessionState:
    """
    Create new session state from checkpoint for resume/fork.
    Args:
        checkpoint: Checkpoint to resume from
    Returns:
        New SessionState initialized from checkpoint
    """
    state = SessionState()
    state.messages = checkpoint.messages.copy()
    state.total_usage = checkpoint.usage
    state.total_cost = checkpoint.cost
    state.metadata = checkpoint.metadata.copy()
    state.status = SessionStatus.RUNNING
    return state
# ============================================================================
# # EXAMPLE USAGE PATTERNS
# ============================================================================
## EXAMPLE 1: Basic Query Pattern with Claude Messages API
from anthropic import Anthropic
client = Anthropic(api_key="your-api-key")
# Create session state
session = SessionState(
    model="claude-sonnet-4-5",
    system_prompt="You are a helpful coding assistant"
)
# Add user message
session.add_message("user", "Explain async/await in Python")
# Make API call (based on Messages API documentation)
response = client.messages.create(
    model=session.model,
    max_tokens=1024,
    messages=session.get_api_messages()
)
# Process response and update session
usage = TokenUsage(
    input_tokens=response.usage.input_tokens,
    output_tokens=response.usage.output_tokens
)
cost = calculate_cost(usage, session.model)
session.update_usage(usage, cost)
# Store assistant response
session.add_message("assistant", response.content[0].text)
# EXAMPLE 2: Streaming with Checkpoints
--
import asyncio
from anthropic import AsyncAnthropic
async def streaming_with_checkpoints():
    client = AsyncAnthropic(api_key="your-api-key")
    session = SessionState(model="claude-sonnet-4-5")
    session.add_message("user", "Write a Python function for binary search")
    accumulated = ""
    async with client.messages.stream(
        model=session.model,
        max_tokens=2048,
        messages=session.get_api_messages()
    ) as stream:
        async for text in stream.text_stream:
            accumulated += text
            print(text, end="", flush=True)
            # Create checkpoint every 100 chars
            if len(accumulated) % 100 == 0:
                session.create_checkpoint(accumulated)
    # Final update
    final_message = await stream.get_final_message()
    session.add_message("assistant", accumulated)
    usage = TokenUsage(
        input_tokens=final_message.usage.input_tokens,
        output_tokens=final_message.usage.output_tokens
    )
    session.update_usage(usage, calculate_cost(usage, session.model))
# EXAMPLE 3: Multi-Step Workflow with Error Handling
def execute_workflow_with_retry(workflow_config: Dict[str, Any]):
    client = Anthropic(api_key="your-api-key")
    session = SessionState(
        workflow_id=workflow_config["workflow_id"],
        model=workflow_config["model"],
        system_prompt=workflow_config["system_prompt"]
    )
    results = []
    for step in workflow_config["steps"]:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                session.add_message("user", step["prompt"])
                response = client.messages.create(
                    model=session.model,
                    max_tokens=2048,
                    messages=session.get_api_messages()
                )
                # Success - process and continue
                content = response.content[0].text
                session.add_message("assistant", content)
                usage = TokenUsage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens
                )
                session.update_usage(usage, calculate_cost(usage, session.model))
                results.append({
                    "step": step["name"],
                    "success": True,
                    "content": content
                })
                break
            except Exception as e:
                error = ExecutionError(
                    message=str(e),
                    category=ErrorCategory.TRANSIENT,
                    severity=ErrorSeverity.RECOVERABLE,
                    attempt=attempt
                )
                if not error.should_retry() or attempt == max_retries - 1:
                    results.append({
                        "step": step["name"],
                        "success": False,
                        "error": error.message
                    })
                    break
                # Wait before retry
                import time
                time.sleep(error.get_retry_delay())
    return results, session
# EXAMPLE 4: Subagent Task Delegation Pattern
class SubagentOrchestrator:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.tasks: Dict[str, SubagentTask] = {}
        self.results: Dict[str, SubagentResult] = {}
    def add_task(self, task: SubagentTask) -> None:
        self.tasks[task.task_id] = task
    def execute_task(self, task: SubagentTask) -> SubagentResult:
        start_time = datetime.now()
        try:
            # Create isolated session for subagent
            session = SessionState(
                model=task.model or "claude-sonnet-4-5",
                system_prompt=task.system_prompt
            )
            session.add_message("user", task.prompt)
            response = self.client.messages.create(
                model=session.model,
                max_tokens=4096,
                messages=session.get_api_messages()
            )
            duration = (datetime.now() - start_time).total_seconds() * 1000
            content = response.content[0].text
            usage = TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens
            )
            cost = calculate_cost(usage, session.model)
            return SubagentResult(
                task_id=task.task_id,
                success=True,
                content=content,
                usage=usage,
                cost=cost,
                duration_ms=duration
            )
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            return SubagentResult(
                task_id=task.task_id,
                success=False,
                content="",
                usage=TokenUsage(),
                cost=CostBreakdown(),
                duration_ms=duration,
                error=ExecutionError(
                    message=str(e),
                    category=ErrorCategory.EXTERNAL,
                    severity=ErrorSeverity.BLOCKING
                )
            )
    def execute_all(self) -> Dict[str, SubagentResult]:
        # Execute tasks respecting dependencies
        executed = set()
        while len(executed) < len(self.tasks):
            for task_id, task in self.tasks.items():
                if task_id in executed:
                    continue
                # Check if all dependencies are satisfied
                deps_satisfied = all(
                    dep_id in executed for dep_id in task.dependencies
                )
                if deps_satisfied:
                    result = self.execute_task(task)
                    self.results[task_id] = result
                    executed.add(task_id)
        return self.results
# EXAMPLE 5: Token Counting Before Execution
# Based on Messages API count_tokens endpoint from Python documentation
from anthropic import Anthropic
def estimate_request_cost(messages: List[Message], model: str) -> Dict[str, Any]:
    '''
    Estimate token usage and cost before making actual API call.
    Uses the count_tokens endpoint to preview resource consumption.
    '''
    client = Anthropic(api_key="your-api-key")
    # Convert messages to API format
    api_messages = [m.to_dict() for m in messages]
    # Count tokens using the Messages API count_tokens endpoint
    # Note: This is based on the Python beta.messages.count_tokens documentation
    token_count = client.beta.messages.count_tokens(
        model=model,
        messages=api_messages
    )
    # Create usage object from count
    usage = TokenUsage(
        input_tokens=token_count.input_tokens
    )
    # Calculate estimated cost
    cost = calculate_cost(usage, model)
    return {
        "estimated_input_tokens": usage.input_tokens,
        "estimated_cost": cost.total_cost,
        "model": model
    }
# EXAMPLE 6: Session Persistence and Resume
--
import json
from pathlib import Path
class SessionManager:
    '''
    Manage session persistence for pause/resume workflows.
    Enables saving and loading conversation state across executions.
    '''
    def __init__(self, storage_dir: str = "./sessions"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
    def save_session(self, session: SessionState) -> str:
        '''Save session to disk and return file path.'''
        filepath = self.storage_dir / f"{session.session_id}.json"
        with open(filepath, 'w') as f:
            json.dump(session.to_dict(), f, indent=2)
        return str(filepath)
    def load_session(self, session_id: str) -> SessionState:
        '''Load session from disk.'''
        filepath = self.storage_dir / f"{session_id}.json"
        if not filepath.exists():
            raise FileNotFoundError(f"Session {session_id} not found")
        with open(filepath, 'r') as f:
            data = json.load(f)
        return SessionState.from_dict(data)
    def resume_session(
        self,
        session_id: str,
        new_message: str
    ) -> SessionState:
        '''Resume a saved session with a new message.'''
        session = self.load_session(session_id)
        session.status = SessionStatus.RUNNING
        session.add_message("user", new_message)
        return session
    def fork_session(
        self,
        session_id: str,
        fork_from_checkpoint: Optional[int] = None
    ) -> SessionState:
        '''
        Create a new session forked from an existing one.
        Optionally fork from a specific checkpoint.
        '''
        original = self.load_session(session_id)
        # Create new session with copied state
        forked = SessionState(
            workflow_id=original.workflow_id,
            model=original.model,
            system_prompt=original.system_prompt,
            fork_session=True
        )
        if fork_from_checkpoint is not None:
            # Fork from specific checkpoint
            checkpoint = original.checkpoints[fork_from_checkpoint]
            forked.messages = checkpoint.messages.copy()
            forked.total_usage = checkpoint.usage
            forked.total_cost = checkpoint.cost
        else:
            # Fork from current state
            forked.messages = original.messages.copy()
            forked.total_usage = original.total_usage
            forked.total_cost = original.total_cost
        return forked
# EXAMPLE 7: Advanced Error Recovery with Exponential Backoff
import asyncio
from typing import Callable, TypeVar
T = TypeVar('T')
async def execute_with_retry(
    func: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    error_handler: Optional[Callable[[ExecutionError], None]] = None
) -> T:
    '''
    Execute function with exponential backoff retry logic.
    Args:
        func: Async function to execute
        max_retries: Maximum retry attempts
        base_delay: Base delay in seconds for exponential backoff
        error_handler: Optional callback for error logging
    Returns:
        Result from successful function execution
    Raises:
        Last exception if all retries exhausted
    '''
    last_error = None
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            # Classify error
            if "rate_limit" in str(e).lower():
                category = ErrorCategory.TRANSIENT
                severity = ErrorSeverity.RECOVERABLE
            elif "timeout" in str(e).lower():
                category = ErrorCategory.TRANSIENT
                severity = ErrorSeverity.RECOVERABLE
            elif "auth" in str(e).lower():
                category = ErrorCategory.PERMISSION
                severity = ErrorSeverity.BLOCKING
            else:
                category = ErrorCategory.EXTERNAL
                severity = ErrorSeverity.DEGRADABLE
            error = ExecutionError(
                message=str(e),
                category=category,
                severity=severity,
                attempt=attempt,
                original_exception=e
            )
            last_error = error
            # Call error handler if provided
            if error_handler:
                error_handler(error)
            # Check if should retry
            if not error.should_retry() or attempt == max_retries - 1:
                break
            # Exponential backoff
            delay = error.get_retry_delay(base_delay)
            await asyncio.sleep(delay)
    # All retries exhausted
    if last_error and last_error.original_exception:
        raise last_error.original_exception
    raise Exception("Execution failed after all retries")
# EXAMPLE 8: Batch Processing with Progress Tracking
from typing import Iterator
import time
class BatchProcessor:
    '''
    Process multiple prompts in batch with progress tracking.
    Useful for bulk operations with cost and usage monitoring.
    '''
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5"):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.total_usage = TokenUsage()
        self.total_cost = CostBreakdown()
    def process_batch(
        self,
        prompts: List[str],
        system_prompt: str = "",
        max_tokens: int = 1024,
        delay_between_requests: float = 0.5
    ) -> Iterator[Dict[str, Any]]:
        '''
        Process prompts in batch with progress tracking.
        Args:
            prompts: List of user prompts to process
            system_prompt: System prompt for all requests
            max_tokens: Max tokens per response
            delay_between_requests: Delay in seconds between requests
        Yields:
            Dict with result, usage, and progress information
        '''
        total = len(prompts)
        for idx, prompt in enumerate(prompts, 1):
            start_time = time.time()
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_prompt if system_prompt else None,
                    messages=[{"role": "user", "content": prompt}]
                )
                # Extract usage
                usage = TokenUsage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens
                )
                cost = calculate_cost(usage, self.model)
                # Accumulate totals
                self.total_usage.add(usage)
                self.total_cost.add(cost)
                duration = time.time() - start_time
                yield {
                    "index": idx,
                    "total": total,
                    "progress": idx / total,
                    "prompt": prompt,
                    "response": response.content[0].text,
                    "usage": usage,
                    "cost": cost,
                    "duration_seconds": duration,
                    "cumulative_cost": self.total_cost.total_cost,
                    "success": True
                }
            except Exception as e:
                yield {
                    "index": idx,
                    "total": total,
                    "progress": idx / total,
                    "prompt": prompt,
                    "error": str(e),
                    "success": False
                }
            # Rate limiting delay
            if idx < total:
                time.sleep(delay_between_requests)
# EXAMPLE 9: Context Window Management with Caching
--
class ContextManager:
    '''
    Manage conversation context with prompt caching support.
    Automatically handles context window limits and cache optimization.
    '''
    def __init__(
        self,
        model: str = "claude-sonnet-4-5",
        max_context_tokens: int = 180000
    ):
        self.model = model
        self.max_context_tokens = max_context_tokens
        self.session = SessionState(model=model)
    def add_cacheable_context(
        self,
        content: str,
        cache_type: str = "ephemeral"
    ) -> None:
        '''
        Add content with cache control for prompt caching.
        Note: Prompt caching details based on general Claude API patterns.
        Refer to official documentation for current implementation.
        '''
        # Add system message with cache control
        self.session.system_prompt = content
    def add_message_with_context_check(
        self,
        role: str,
        content: str,
        client: Anthropic
    ) -> bool:
        '''
        Add message with automatic context window management.
        Returns:
            True if message added successfully, False if context limit reached
        '''
        # Estimate current context size
        test_messages = self.session.get_api_messages() + [
            {"role": role, "content": content}
        ]
        try:
            # Use count_tokens to check if we're within limits
            token_count = client.beta.messages.count_tokens(
                model=self.model,
                messages=test_messages
            )
            if token_count.input_tokens > self.max_context_tokens:
                # Context limit reached - need to truncate
                self._truncate_context()
                return False
            # Safe to add message
            self.session.add_message(role, content)
            return True
        except Exception as e:
            print(f"Error checking context: {e}")
            return False
    def _truncate_context(self, keep_recent: int = 10) -> None:
        '''Keep only the most recent messages to stay within limits.'''
        if len(self.session.messages) > keep_recent:
            self.session.messages = self.session.messages[-keep_recent:]
# EXAMPLE 10: Comprehensive Workflow Execution
-
class WorkflowExecutor:
    '''
    Complete workflow executor with all advanced features:
    - Error recovery
    - Checkpointing
    - Cost tracking
    - Progress monitoring
    '''
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.session_manager = SessionManager()
    async def execute_workflow(
        self,
        workflow_config: Dict[str, Any],
        checkpoint_interval: int = 3,
        save_checkpoints: bool = True
    ) -> Dict[str, Any]:
        '''
        Execute complete workflow with advanced features.
        Args:
            workflow_config: Configuration from WorkflowBuilder
            checkpoint_interval: Save checkpoint every N steps
            save_checkpoints: Whether to persist checkpoints to disk
        Returns:
            Workflow execution summary with results and metrics
        '''
        session = SessionState(
            workflow_id=workflow_config["workflow_id"],
            model=workflow_config["model"],
            system_prompt=workflow_config["system_prompt"],
            metadata=workflow_config["metadata"]
        )
        results = []
        step_count = len(workflow_config["steps"])
        for idx, step in enumerate(workflow_config["steps"], 1):
            print(f"Executing step {idx}/{step_count}: {step['name']}")
            # Add user message
            session.add_message("user", step["prompt"])
            # Execute with retry logic
            async def execute_step():
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=session.model,
                    max_tokens=step.get("max_tokens", 2048),
                    messages=session.get_api_messages()
                )
                return response
            try:
                response = await execute_with_retry(
                    execute_step,
                    max_retries=3,
                    error_handler=lambda e: print(f"Retry after error: {e.message}")
                )
                # Process response
                content = response.content[0].text
                session.add_message("assistant", content)
                usage = TokenUsage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens
                )
                cost = calculate_cost(usage, session.model)
                session.update_usage(usage, cost)
                results.append({
                    "step": step["name"],
                    "success": True,
                    "content": content,
                    "tokens": usage.total_tokens,
                    "cost": cost.total_cost
                })
                # Create checkpoint if needed
                if idx % checkpoint_interval == 0 and save_checkpoints:
                    checkpoint = session.create_checkpoint(content)
                    self.session_manager.save_session(session)
                    print(f"Checkpoint saved: {checkpoint.checkpoint_id}")
            except Exception as e:
                results.append({
                    "step": step["name"],
                    "success": False,
                    "error": str(e)
                })
                session.status = SessionStatus.FAILED
                break
        # Final save
        if save_checkpoints:
            self.session_manager.save_session(session)
        return {
            "workflow_id": session.workflow_id,
            "session_id": session.session_id,
            "status": session.status.value,
            "steps_completed": len([r for r in results if r["success"]]),
            "total_steps": step_count,
            "results": results,
            "total_tokens": session.total_usage.total_tokens,
            "total_cost": session.total_cost.total_cost,
            "cache_hit_rate": session.total_usage.cache_hit_rate
        }
