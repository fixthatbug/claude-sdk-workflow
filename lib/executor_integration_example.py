"""
Example integration of async error handling with executors.
This file demonstrates how to integrate ThreeStrikeHandler into
executor classes for robust error handling.
"""
import asyncio
import logging
from typing import Optional
from lib.error_handling import (
    ThreeStrikeHandler,
    ErrorInfo,
    retry_with_backoff,
)
logger = logging.getLogger(__name__)
class ErrorHandlingMixin:
    """
    Mixin class to add error handling capabilities to executors.
    Usage:
        class MyExecutor(ErrorHandlingMixin, BaseExecutor):
            async def execute_async(self, task, system_prompt):
                return await self._with_error_handling(
                    lambda: self._do_execute(task, system_prompt),
                    context={"task": task}
                )
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._error_handler = ThreeStrikeHandler(
            max_retries=3,
            on_escalate=self._handle_escalation
        )
    async def _with_error_handling(self, func, context=None):
        """
        Execute function with 3-strike error handling.
        Args:
            func: Async function to execute
            context: Context passed to escalation handler
        Returns:
            Result from successful execution
        """
        return await self._error_handler.execute_with_retry(func, context)
    async def _handle_escalation(self, error_info: ErrorInfo, context):
        """
        Handle escalated errors (Strike 3).
        This is called when all retries are exhausted.
        Override in subclass for custom behavior.
        Args:
            error_info: Categorized error information
            context: Execution context
        """
        logger.error(
            f"Task failed after all retries:\n"
            f" Category: {error_info.category.value}\n"
            f" Severity: {error_info.severity.value}\n"
            f" Message: {error_info.message}\n"
            f" Context: {context}"
        )
# Example: Async Oneshot Executor with Error Handling
class OneshotExecutorAsync:
    """
    Example async oneshot executor with integrated error handling.
    This demonstrates the pattern for adding error handling to executors.
    """
    def __init__(self, max_retries: int = 3):
        self._error_handler = ThreeStrikeHandler(
            max_retries=max_retries,
            on_escalate=self._log_escalation
        )
    async def execute(self, task: str, system_prompt: str = ""):
        """Execute task with error handling."""
        return await self._error_handler.execute_with_retry(
            lambda: self._do_execute(task, system_prompt),
            context={"task": task, "system_prompt": system_prompt}
        )
    async def _do_execute(self, task: str, system_prompt: str):
        """Actual execution logic (wrapped by error handler)."""
        # This is where you'd call the actual SDK/API
        # For demonstration, we'll simulate an API call
        await asyncio.sleep(0.1)
        # Simulate potential errors based on task
        if "fail" in task.lower():
            raise Exception("Simulated failure")
        return {
            "content": f"Executed: {task}",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }
    async def _log_escalation(self, error_info: ErrorInfo, context):
        """Log escalated errors."""
        logger.error(
            f"ESCALATED ERROR:\n"
            f" Task: {context.get('task', 'unknown')}\n"
            f" Category: {error_info.category.value}\n"
            f" Message: {error_info.message}"
        )
# Example: Streaming Executor with Error Handling
class StreamingExecutorAsync:
    """
    Example async streaming executor with error handling.
    Demonstrates error handling for streaming operations.
    """
    def __init__(self, max_retries: int = 3):
        self._error_handler = ThreeStrikeHandler(
            max_retries=max_retries,
            on_escalate=self._log_escalation
        )
    async def execute_stream(self, task: str, on_chunk=None):
        """Execute streaming task with error handling."""
        return await self._error_handler.execute_with_retry(
            lambda: self._do_execute_stream(task, on_chunk),
            context={"task": task}
        )
    async def _do_execute_stream(self, task: str, on_chunk=None):
        """Actual streaming execution logic."""
        # Simulate streaming chunks
        chunks = [f"Chunk {i}" for i in range(5)]
        for chunk in chunks:
            if on_chunk:
                on_chunk(chunk)
            await asyncio.sleep(0.1)
        return {"chunks": chunks, "complete": True}
    async def _log_escalation(self, error_info: ErrorInfo, context):
        """Log escalated errors."""
        logger.error(
            f"Stream failed after retries:\n"
            f" Task: {context.get('task')}\n"
            f" Error: {error_info.message}"
        )
# ============================================================================
# INTEGRATION PATTERNS
# ============================================================================
async def pattern_1_simple_retry():
    """
    Pattern 1: Simple retry with backoff
    Use when you just need basic retry logic.
    """
    async def api_call():
        # Your API call here
        return "result"
    result = await retry_with_backoff(api_call, max_retries=3)
    return result
async def pattern_2_custom_escalation():
    """
    Pattern 2: Custom escalation handling
    Use when you need specific error handling logic.
    """
    escalation_log = []
    async def on_escalate(error_info, context):
        escalation_log.append({
            "error": error_info.message,
            "category": error_info.category.value,
            "context": context
        })
    handler = ThreeStrikeHandler(
        max_retries=3,
        on_escalate=on_escalate
    )
    async def risky_operation():
        # Your risky operation here
        raise Exception("Something went wrong")
    try:
        await handler.execute_with_retry(
            risky_operation,
            context={"operation": "critical_task"}
        )
    except Exception as e:
        # Handle after escalation
        print(f"Failed after escalation: {e}")
        print(f"Escalation log: {escalation_log}")
async def pattern_3_executor_integration():
    """
    Pattern 3: Full executor integration
    Use for production executor classes.
    """
    executor = OneshotExecutorAsync(max_retries=3)
    # Normal execution
    result1 = await executor.execute("Hello world")
    print(f"Success: {result1}")
    # Failed execution (will retry and escalate)
    try:
        result2 = await executor.execute("This will fail")
    except Exception as e:
        print(f"Failed after retries: {e}")
# ============================================================================
# USAGE EXAMPLE
# ============================================================================
async def main():
    """Demonstrate integration patterns."""
    logging.basicConfig(level=logging.INFO)
    print("=== Pattern 1: Simple Retry ===")
    result = await pattern_1_simple_retry()
    print(f"Result: {result}\n")
    print("=== Pattern 2: Custom Escalation ===")
    await pattern_2_custom_escalation()
    print()
    print("=== Pattern 3: Executor Integration ===")
    await pattern_3_executor_integration()
if __name__ == "__main__":
    asyncio.run(main())
