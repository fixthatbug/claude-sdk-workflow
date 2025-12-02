"""
Core Module - Foundation layer for SDK Workflow.

Contains:
- types.py: Data structures (TokenUsage, CostBreakdown, SessionState, etc.)
- config.py: Configuration management with model pricing
- router.py: Task routing with complexity analysis
- agent_client.py: Claude Agent SDK adapter
"""

from .types import (
    ExecutionMode,
    SessionStatus,
    ErrorSeverity,
    ErrorCategory,
    TokenUsage,
    CostBreakdown,
    Message,
    ExecutionResult,
    ExecutionError,
    Checkpoint,
    SessionState,
    SubagentTask,
    SubagentResult,
)

from .config import (
    Config,
    ModelConfig,
    ModelTier,
    BetaHeaders,
    RoutingConfig,
    BudgetConfig,
    TimeoutConfig,
    RetryConfig,
    CacheConfig,
    get_config,
    MODELS,
    MODEL_ALIASES,
)

from .router import (
    route_task,
    analyze_task_complexity,
)

from .agent_client import (
    AgentClientManager,
    get_agent_client,
    reset_agent_client,
    run_oneshot_sync,
    extract_text_from_message,
    extract_tool_uses_from_message,
    extract_usage_from_message,
    sdk_usage_to_token_usage,
)

__all__ = [
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
    "get_config",
    "MODELS",
    "MODEL_ALIASES",
    
    # Router
    "route_task",
    "analyze_task_complexity",
    
    # Agent Client
    "AgentClientManager",
    "get_agent_client",
    "reset_agent_client",
    "run_oneshot_sync",
    "extract_text_from_message",
    "extract_tool_uses_from_message",
    "extract_usage_from_message",
    "sdk_usage_to_token_usage",
]
