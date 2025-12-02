"""
SDK Workflow - Unified Claude Agent SDK Integration

Production-ready SDK workflow with:
- Core types and configuration
- Production managers (Token, Cost, Session, Cache)
- Execution strategies (Base, Streaming, Orchestrator)
- Workflow orchestration and batch processing
- Team prompts and subagent definitions
- Quality evaluation and hallucination detection

@version 2.0.0 (refactor-04)
"""

from .core import (
    # Types
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
    # Config
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
    # Router
    route_task,
    analyze_task_complexity,
    # Agent Client
    get_agent_client,
    AgentClientManager,
)

from .managers import (
    TokenManager,
    CostManager,
    SessionManager,
    CacheManager,
)

from .executors import (
    BaseExecutor,
)

from .workflow import (
    WorkflowStep,
    WorkflowResult,
    WorkflowModeIntegrator,
    BatchItem,
    BatchProcessor,
    EvaluationResult,
    EvaluationReport,
    EvaluationFramework,
    HallucinationGuard,
    ConsistencyEnforcer,
    StreamingMode,
    StreamingConfig,
    StreamChunk,
    StreamingHandler,
    StreamingDecisionEngine,
    create_streaming_handler,
)

from .prompts import (
    SubagentPrompt,
    BASE_CONSTRAINTS,
    THINKING_BUDGETS,
    get_subagent_prompt,
    get_team_prompts,
    get_sdk_agent_definitions,
    list_agents,
    list_teams,
)

__version__ = "2.0.0"

__all__ = [
    # Version
    "__version__",
    
    # Core Types
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
    
    # Router
    "route_task",
    "analyze_task_complexity",
    
    # Agent Client
    "get_agent_client",
    "AgentClientManager",
    
    # Managers
    "TokenManager",
    "CostManager",
    "SessionManager",
    "CacheManager",
    
    # Executors
    "BaseExecutor",
    
    # Workflow
    "WorkflowStep",
    "WorkflowResult",
    "WorkflowModeIntegrator",
    "BatchItem",
    "BatchProcessor",
    "EvaluationResult",
    "EvaluationReport",
    "EvaluationFramework",
    "HallucinationGuard",
    "ConsistencyEnforcer",
    
    # Streaming
    "StreamingMode",
    "StreamingConfig",
    "StreamChunk",
    "StreamingHandler",
    "StreamingDecisionEngine",
    "create_streaming_handler",
    
    # Prompts
    "SubagentPrompt",
    "BASE_CONSTRAINTS",
    "THINKING_BUDGETS",
    "get_subagent_prompt",
    "get_team_prompts",
    "get_sdk_agent_definitions",
    "list_agents",
    "list_teams",
]
