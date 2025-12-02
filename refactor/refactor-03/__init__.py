"""Core execution components.

@version 2.0.0 - Refactored for SDK integration
"""

# Core types (always available)
from .execution_result import ExecutionResult, ExecutionMetrics
from .base_executor import BaseExecutor, ExecutorConfig, SDK_AVAILABLE

# Helpers
from .executor_helpers import (
    MCP_SERVERS,
    build_sdk_options,
    validate_sdk_options,
    discover_plugins,
)

# Lazy imports for components with external dependencies
def __getattr__(name: str):
    """Lazy import for components with complex dependencies."""
    if name == "UserscopeExecutor":
        from .userscope_executor import UserscopeExecutor
        return UserscopeExecutor
    elif name == "SimulatedExecutor":
        from .simulated_executor import SimulatedExecutor
        return SimulatedExecutor
    elif name == "execute_task":
        from .simulated_executor import execute_task
        return execute_task
    elif name == "execute_task_sync":
        from .simulated_executor import execute_task_sync
        return execute_task_sync
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Core types
    "ExecutionResult",
    "ExecutionMetrics",
    "BaseExecutor",
    "ExecutorConfig",
    "SDK_AVAILABLE",
    # Helpers
    "MCP_SERVERS",
    "build_sdk_options",
    "validate_sdk_options",
    "discover_plugins",
    # Executors (lazy loaded)
    "UserscopeExecutor",
    "SimulatedExecutor",
    "execute_task",
    "execute_task_sync",
]
