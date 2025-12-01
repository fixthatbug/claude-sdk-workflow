"""
Executors module for sdk-workflow.
Provides the three execution modes:
    - OneshotExecutor: Single message, single response (consolidated into streaming_orchestrator)
    - StreamingExecutor: Real-time output with conversation
    - OrchestratorExecutor: Multi-agent delegation
Each executor implements the BaseExecutor interface.
Migration Note:
    - OneshotExecutor has been consolidated into streaming_orchestrator.py
    - All oneshot functionality is now available from streaming_orchestrator module
    - Deprecated oneshot.py, oneshot_orchestrator.py, oneshot_example.py modules archived
"""
from typing import TYPE_CHECKING
__all__ = [
    "BaseExecutor",
    "OneshotExecutor",
    "StreamingExecutor",
    "OrchestratorExecutor",
    "StreamingOrchestrator",
    "get_executor",
]
def get_executor(mode: str):
    """
    Factory function to get the appropriate executor for a mode.
    Args:
        mode: Execution mode ("oneshot", "streaming", "orchestrator").
    Returns:
        Executor class for the specified mode.
    Raises:
        ValueError: If mode is not recognized.
    """
    executors = {
        "oneshot": "OneshotExecutor",
        "streaming": "StreamingExecutor",
        "orchestrator": "OrchestratorExecutor",
    }
    if mode not in executors:
        raise ValueError(
            f"Unknown mode: {mode}. "
            f"Valid modes: {', '.join(executors.keys())}"
        )
    executor_name = executors[mode]
    return __getattr__(executor_name)
# Lazy imports to avoid circular dependencies and speed up import
def __getattr__(name: str):
    if name == "BaseExecutor":
        from .base import BaseExecutor
        return BaseExecutor
    elif name == "OneshotExecutor":
        # UPDATED: Import from consolidated streaming_orchestrator module
        from .streaming_orchestrator import OneshotExecutor
        return OneshotExecutor
    elif name == "StreamingExecutor":
        from .streaming import StreamingExecutor
        return StreamingExecutor
    elif name == "OrchestratorExecutor":
        from .orchestrator import OrchestratorExecutor
        return OrchestratorExecutor
    elif name == "StreamingOrchestrator":
        from .streaming_orchestrator import StreamingOrchestrator
        return StreamingOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
