"""
Task routing logic for sdk-workflow.
Routes tasks to the appropriate executor based on mode and task analysis.
"""
from typing import Any, Dict, Optional
def route_task(
    task: str,
    mode: str,
    *,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    background: bool = False,
    session_id: Optional[str] = None,
    agents: Optional[list] = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Route a task to the appropriate executor.
    Args:
        task: Task description to execute.
        mode: Execution mode - "oneshot", "streaming", or "orchestrator".
        model: Model override (default depends on mode).
        system_prompt: Custom system prompt.
        background: Run in background (orchestrator only).
        session_id: Resume existing session.
        agents: Subagent configurations (orchestrator only).
        **kwargs: Additional executor-specific arguments.
    Returns:
        Dict with:
            - result: Execution output
            - session_id: Session identifier
            - status: "completed", "running", "failed"
            - metrics: Token/cost tracking
    Raises:
        ValueError: If mode is invalid.
    """
    from .config import get_config
    from ..executors import get_executor
    from ..lib.utils import generate_session_id
    # Validate mode
    valid_modes = {"oneshot", "streaming", "orchestrator"}
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode '{mode}'. Must be one of: {valid_modes}")
    # Get configuration
    config = get_config()
    # Override model if specified
    if model:
        config = config.with_model(model)
    # Generate or use existing session ID
    sid = session_id or generate_session_id()
    # Get the appropriate executor class and instantiate
    ExecutorClass = get_executor(mode)
    executor = ExecutorClass(config)
    # Build execution context
    context = {
        "session_id": sid,
        "background": background,
        "agents": agents or [],
        **kwargs
    }
    # Determine system prompt
    prompt = system_prompt or _get_default_prompt(mode)
    try:
        # Setup executor
        executor.setup()
        # Execute task
        if background and mode == "orchestrator":
            # Background execution returns immediately
            result = executor.execute_background(task, prompt, context)
            return {
                "result": None,
                "session_id": sid,
                "status": "running",
                "metrics": None
            }
        else:
            # Foreground execution
            result = executor.execute(task, prompt)
            return {
                "result": result.content if hasattr(result, 'content') else str(result),
                "session_id": sid,
                "status": "completed",
                "metrics": _extract_metrics(result)
            }
    except Exception as e:
        return {
            "result": None,
            "session_id": sid,
            "status": "failed",
            "error": str(e),
            "metrics": None
        }
    finally:
        executor.cleanup()
def _get_default_prompt(mode: str) -> str:
    """Get default system prompt for the mode."""
    from ..resources.prompts import (
        ORCHESTRATOR_PROMPT,
        SUBAGENT_BASE_PROMPT
    )
    prompts = {
        "oneshot": "You are a helpful assistant. Be concise and accurate.",
        "streaming": "You are a skilled developer. Think step by step.",
        "orchestrator": ORCHESTRATOR_PROMPT
    }
    return prompts.get(mode, prompts["oneshot"])
def _extract_metrics(result: Any) -> Optional[Dict[str, Any]]:
    """Extract metrics from execution result."""
    if not result:
        return None
    metrics = {}
    if hasattr(result, 'usage'):
        usage = result.usage
        metrics["input_tokens"] = getattr(usage, 'input_tokens', 0)
        metrics["output_tokens"] = getattr(usage, 'output_tokens', 0)
        metrics["cached_tokens"] = getattr(usage, 'cached_tokens', 0)
    if hasattr(result, 'cost'):
        metrics["cost"] = result.cost
    if hasattr(result, 'model'):
        metrics["model"] = result.model
    return metrics if metrics else None
def analyze_task_complexity(task: str) -> str:
    """
    Analyze task complexity to suggest appropriate mode.
    Args:
        task: Task description.
    Returns:
        Suggested mode: "oneshot", "streaming", or "orchestrator".
    """
    task_lower = task.lower()
    # Orchestrator indicators
    orchestrator_keywords = [
        "implement", "build", "create", "develop",
        "refactor", "migrate", "redesign",
        "multi-file", "feature", "system"
    ]
    if any(kw in task_lower for kw in orchestrator_keywords):
        return "orchestrator"
    # Streaming indicators
    streaming_keywords = [
        "explain", "analyze", "review", "investigate",
        "research", "explore", "debug"
    ]
    if any(kw in task_lower for kw in streaming_keywords):
        return "streaming"
    # Default to oneshot for simple tasks
    return "oneshot"
