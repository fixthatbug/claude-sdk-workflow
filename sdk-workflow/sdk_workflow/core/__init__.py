"""
Core module for sdk-workflow.
Contains the central routing logic, configuration, and shared utilities.
Components:
    - router: Task routing decision logic
    - config: Configuration management
    - session: Session state management
    - metrics: Token and cost tracking
    - types: Core type definitions
"""
__all__ = [
    # Router
    "route_task",
    # Config
    "Config",
    "ModelConfig",
    "ModelTier",
    "BetaHeaders",
    "RoutingConfig",
    "BudgetConfig",
    "TimeoutConfig",
    "RetryConfig",
    "CacheConfig",
    "MODELS",
    "MODEL_ALIASES",
    "get_config",
    # Agent Client (Claude Agent SDK)
    "AgentClientManager",
    "get_agent_client",
    "reset_agent_client",
    # Cache
    "PromptCacheOptimizer",
    # Budget
    "BudgetManager",
    "BudgetStatus",
    "DailyBudget",
    # State
    "SessionManager",
    "CheckpointManager",
    # Session (legacy)
    "Session",
    # Types
    "ExecutionMode",
    "SessionStatus",
    "ErrorSeverity",
    "ErrorCategory",
    "TokenUsage",
    "CostBreakdown",
    "Message",
    "ExecutionResult",
    "ExecutionError",
    "Checkpoint",
    "SessionState",
    "SubagentTask",
    "SubagentResult",
    # Metrics
    "MetricsEngine",
    "BudgetExceededError",
    "RequestMetrics",
    # Mailbox (DEPRECATED - archived in sdk_workflow/archive/mailbox_system/)
    # Use TodoWrite for progress tracking instead
]
def route_task(task: str, mode: str, **kwargs):
    """
    Route a task to the appropriate executor.
    Args:
        task: Task description.
        mode: Execution mode ("oneshot", "streaming", "orchestrator").
        **kwargs: Mode-specific arguments.
    Returns:
        Execution result dictionary.
    """
    from .router import route_task as _route
    return _route(task, mode, **kwargs)
# Lazy imports for heavy modules
def __getattr__(name: str):
    # Config exports
    if name == "Config":
        from .config import Config
        return Config
    elif name == "ModelConfig":
        from .config import ModelConfig
        return ModelConfig
    elif name == "ModelTier":
        from .config import ModelTier
        return ModelTier
    elif name == "BetaHeaders":
        from .config import BetaHeaders
        return BetaHeaders
    elif name == "RoutingConfig":
        from .config import RoutingConfig
        return RoutingConfig
    elif name == "BudgetConfig":
        from .config import BudgetConfig
        return BudgetConfig
    elif name == "TimeoutConfig":
        from .config import TimeoutConfig
        return TimeoutConfig
    elif name == "RetryConfig":
        from .config import RetryConfig
        return RetryConfig
    elif name == "CacheConfig":
        from .config import CacheConfig
        return CacheConfig
    elif name == "MODELS":
        from .config import MODELS
        return MODELS
    elif name == "MODEL_ALIASES":
        from .config import MODEL_ALIASES
        return MODEL_ALIASES
    elif name == "get_config":
        from .config import get_config
        return get_config
    # Agent Client exports (Claude Agent SDK)
    elif name == "AgentClientManager":
        from .agent_client import AgentClientManager
        return AgentClientManager
    elif name == "get_agent_client":
        from .agent_client import get_agent_client
        return get_agent_client
    elif name == "reset_agent_client":
        from .agent_client import reset_agent_client
        return reset_agent_client
    # Cache exports
    elif name == "PromptCacheOptimizer":
        from .cache import PromptCacheOptimizer
        return PromptCacheOptimizer
    # Budget exports
    elif name == "BudgetManager":
        from .budget import BudgetManager
        return BudgetManager
    elif name == "BudgetStatus":
        from .budget import BudgetStatus
        return BudgetStatus
    elif name == "DailyBudget":
        from .budget import DailyBudget
        return DailyBudget
    # State exports
    elif name == "SessionManager":
        from .state import SessionManager
        return SessionManager
    elif name == "CheckpointManager":
        from .state import CheckpointManager
        return CheckpointManager
    # Session exports
    elif name == "Session":
        from .session import Session
        return Session
    # Types exports
    elif name == "ExecutionMode":
        from .types import ExecutionMode
        return ExecutionMode
    elif name == "SessionStatus":
        from .types import SessionStatus
        return SessionStatus
    elif name == "ErrorSeverity":
        from .types import ErrorSeverity
        return ErrorSeverity
    elif name == "ErrorCategory":
        from .types import ErrorCategory
        return ErrorCategory
    elif name == "TokenUsage":
        from .types import TokenUsage
        return TokenUsage
    elif name == "CostBreakdown":
        from .types import CostBreakdown
        return CostBreakdown
    elif name == "Message":
        from .types import Message
        return Message
    elif name == "ExecutionResult":
        from .types import ExecutionResult
        return ExecutionResult
    elif name == "ExecutionError":
        from .types import ExecutionError
        return ExecutionError
    elif name == "Checkpoint":
        from .types import Checkpoint
        return Checkpoint
    elif name == "SessionState":
        from .types import SessionState
        return SessionState
    elif name == "SubagentTask":
        from .types import SubagentTask
        return SubagentTask
    elif name == "SubagentResult":
        from .types import SubagentResult
        return SubagentResult
    # Metrics exports
    elif name == "MetricsEngine":
        from .metrics import MetricsEngine
        return MetricsEngine
    elif name == "BudgetExceededError":
        from .metrics import BudgetExceededError
        return BudgetExceededError
    elif name == "RequestMetrics":
        from .metrics import RequestMetrics
        return RequestMetrics
    # Mailbox exports - DEPRECATED (archived in sdk_workflow/archive/mailbox_system/)
    elif name in ("Mailbox", "MessageType", "send_command", "send_status", "send_signal", "OrchestratorMailboxMixin"):
        raise AttributeError(
            f"Mailbox system is deprecated. '{name}' has been archived. "
            f"Use TodoWrite for progress tracking instead. "
            f"See sdk_workflow/DEPRECATION.md for migration guide."
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
