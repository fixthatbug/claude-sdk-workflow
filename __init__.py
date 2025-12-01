"""
SDK Workflow - Claude Code execution framework.
Provides three execution modes:
- oneshot: Single message, single response (simple, deterministic)
- streaming: Real-time output with conversation support
- orchestrator: Multi-agent delegation with background execution
Usage:
    from sdk_workflow import run_task
    # Simple oneshot
    result = run_task("Extract function names from auth.py", mode="oneshot")
    # Streaming with custom prompt
    result = run_task(
        "Refactor auth module",
        mode="streaming",
        system_prompt="You are a senior backend developer."
    )
    # Orchestrator with background execution
    result = run_task(
        "Implement dashboard feature",
        mode="orchestrator",
        background=True
    )
"""
__version__ = "0.1.0"
__author__ = "Claude Code"
from typing import Any, Optional, Dict
def run_task(
    task: str,
    mode: str = "oneshot",
    *,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    background: bool = False,
    session_id: Optional[str] = None,
    agents: Optional[list] = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Execute a task using the specified execution mode.
    Args:
        task: The task description or prompt to execute.
        mode: Execution mode - "oneshot", "streaming", or "orchestrator".
        model: Model to use (default: haiku for oneshot, sonnet for others).
        system_prompt: Custom system prompt for the executor.
        background: Run in background (orchestrator mode only).
        session_id: Resume or interact with existing session.
        agents: List of subagent configurations (orchestrator mode only).
        **kwargs: Additional mode-specific arguments.
    Returns:
        Dict containing:
            - result: The execution result or output
            - session_id: Session identifier (for streaming/orchestrator)
            - status: Execution status
            - metrics: Token/cost metrics if available
    Raises:
        ValueError: If mode is invalid.
        RuntimeError: If execution fails.
    Example:
        >>> from sdk_workflow import run_task
        >>> result = run_task("List all Python files", mode="oneshot")
        >>> print(result["result"])
    """
    from .core.router import route_task
    return route_task(
        task=task,
        mode=mode,
        model=model,
        system_prompt=system_prompt,
        background=background,
        session_id=session_id,
        agents=agents,
        **kwargs
    )
# Convenience exports
__all__ = [
    "run_task",
    "__version__",
]
