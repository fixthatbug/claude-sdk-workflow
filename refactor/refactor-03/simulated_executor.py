"""Simulated Executor - Testing without SDK.

@version 2.0.0
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .execution_result import ExecutionResult

__all__ = ['SimulatedExecutor', 'execute_task', 'execute_task_sync']


class SimulatedExecutor:
    """Simulated executor for testing without Claude Agent SDK.

    Provides the same interface as UserscopeExecutor but returns
    simulated responses for testing and demonstration.
    """

    def __init__(self, cwd: Optional[str] = None, **kwargs):
        self.cwd = cwd or str(Path.cwd())
        self._factory = None

    @property
    def factory(self):
        """Lazy load factory."""
        if self._factory is None:
            try:
                from agents.factory import create_userscope_factory
                self._factory = create_userscope_factory(cwd=self.cwd)
            except ImportError:
                pass
        return self._factory

    def _generate_task_id(self) -> str:
        content = f"{datetime.now().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    async def execute(
        self,
        agent_name: str,
        task: str,
        **kwargs,
    ) -> ExecutionResult:
        """Simulate task execution."""
        task_id = self._generate_task_id()
        result = ExecutionResult(task_id=task_id, agent_name=agent_name, task=task)
        result.start()

        # Get agent info if available
        agent_info = {}
        if self.factory:
            agent_info = self.factory.get_agent_info(agent_name)

        # Simulate work
        time.sleep(0.3)

        # Generate simulated output
        output = f"""[SIMULATION MODE - Claude Agent SDK not installed]

Task: {task[:200]}...
Agent: {agent_name}
Category: {agent_info.get('category', 'unknown')}
Model: {agent_info.get('model', 'simulated')}

This is a simulated response. To execute real tasks:
1. Install Claude Agent SDK: pip install claude-agent-sdk
2. Set up API credentials
3. Run again
"""

        result.complete(output.strip())
        result.set_cost(
            input_tokens=1000,
            output_tokens=500,
            total_cost_usd=0.015,
        )

        return result

    async def execute_auto(self, task: str, **kwargs) -> ExecutionResult:
        """Simulate auto-selected execution."""
        agent_name = "dev-feature"
        if self.factory:
            self.factory.create_for_task(task)
            metadata = self.factory.get_current_metadata()
            agent_name = metadata.get("agent_name", "dev-feature")
        return await self.execute(agent_name, task, **kwargs)


# =============================================================================
# Convenience Functions
# =============================================================================

async def execute_task(
    task: str,
    agent: Optional[str] = None,
    auto_select: bool = True,
    cwd: Optional[str] = None,
    **kwargs: Any,
) -> ExecutionResult:
    """Execute task with userscope agent (convenience function).

    Args:
        task: Task description
        agent: Agent name (if None, auto-selects)
        auto_select: Auto-select agent if not specified
        cwd: Working directory
        **kwargs: Additional options

    Returns:
        ExecutionResult
    """
    try:
        from .userscope_executor import UserscopeExecutor
        executor = UserscopeExecutor(cwd=cwd)
    except ImportError:
        executor = SimulatedExecutor(cwd=cwd)

    if agent:
        return await executor.execute(agent, task, **kwargs)
    elif auto_select:
        return await executor.execute_auto(task, **kwargs)
    else:
        raise ValueError("Either 'agent' or 'auto_select=True' required")


def execute_task_sync(
    task: str,
    agent: Optional[str] = None,
    auto_select: bool = True,
    cwd: Optional[str] = None,
    **kwargs: Any,
) -> ExecutionResult:
    """Synchronous wrapper for execute_task."""
    import asyncio
    return asyncio.run(execute_task(task, agent, auto_select, cwd, **kwargs))
