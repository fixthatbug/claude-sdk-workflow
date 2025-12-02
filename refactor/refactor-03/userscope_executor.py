"""Userscope Executor - SDK execution engine.

Refactored to use project streaming module and extend BaseExecutor.

@version 2.0.0
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, TYPE_CHECKING

from .base_executor import BaseExecutor, ExecutorConfig, SDK_AVAILABLE
from .execution_result import ExecutionResult, ExecutionMetrics
from .executor_helpers import (
    build_sdk_options,
    validate_sdk_options,
    discover_plugins,
    MCP_SERVERS,
)

if TYPE_CHECKING:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        AssistantMessage,
        TextBlock,
        ToolUseBlock,
        ResultMessage,
    )

__all__ = ['UserscopeExecutor']

logger = logging.getLogger(__name__)


# Conditional SDK imports
if SDK_AVAILABLE:
    try:
        from claude_agent_sdk import (
            ClaudeSDKClient,
            AssistantMessage,
            TextBlock,
            ToolUseBlock,
            ResultMessage,
        )
    except ImportError:
        ClaudeSDKClient = None
        AssistantMessage = None
        TextBlock = None
        ToolUseBlock = None
        ResultMessage = None
else:
    ClaudeSDKClient = None
    AssistantMessage = None
    TextBlock = None
    ToolUseBlock = None
    ResultMessage = None


# =============================================================================
# Cost Tracker (Inline - avoids external dependency)
# =============================================================================

class CostTracker:
    """Simple cost tracking for executions."""

    # Pricing per 1M tokens (approximate)
    PRICING = {
        "sonnet": {"input": 3.0, "output": 15.0},
        "haiku": {"input": 0.25, "output": 1.25},
        "opus": {"input": 15.0, "output": 75.0},
    }

    def __init__(self, budget_usd: Optional[float] = None):
        self.budget_usd = budget_usd
        self._executions: Dict[str, ExecutionMetrics] = {}

    def start_execution(self, task_id: str, model: str = "sonnet") -> ExecutionMetrics:
        """Start tracking an execution."""
        metrics = ExecutionMetrics(start_time=datetime.now())
        self._executions[task_id] = metrics
        return metrics

    def update_execution(
        self,
        task_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read: int = 0,
        cache_write: int = 0,
        message_id: Optional[str] = None,
    ) -> bool:
        """Update execution metrics."""
        if task_id not in self._executions:
            return False
        metrics = self._executions[task_id]
        metrics.input_tokens += input_tokens
        metrics.output_tokens += output_tokens
        metrics.cache_read_tokens += cache_read
        metrics.cache_write_tokens += cache_write
        return True

    def complete_execution(self, task_id: str, model: str = "sonnet") -> Optional[ExecutionMetrics]:
        """Complete and calculate final cost."""
        if task_id not in self._executions:
            return None
        metrics = self._executions[task_id]
        metrics.end_time = datetime.now()
        
        # Calculate cost
        pricing = self.PRICING.get(model, self.PRICING["sonnet"])
        metrics.total_cost_usd = (
            (metrics.input_tokens / 1_000_000) * pricing["input"] +
            (metrics.output_tokens / 1_000_000) * pricing["output"]
        )
        return metrics

    def get_execution_metrics(self, task_id: str) -> Optional[ExecutionMetrics]:
        """Get metrics for an execution."""
        return self._executions.get(task_id)


# =============================================================================
# Userscope Executor
# =============================================================================

class UserscopeExecutor(BaseExecutor):
    """Executor for running userscope workflow agents via Claude Agent SDK.

    Extends BaseExecutor with:
    - Streaming execution with real-time output
    - Cost tracking and monitoring
    - MCP server integration
    - Plugin discovery

    Example:
        >>> executor = UserscopeExecutor()
        >>> async for message in executor.run("dev-bugfix", "fix auth bug"):
        ...     print(message.content)
        >>> result = await executor.execute("dev-feature", "add dark mode")
        >>> print(f"Status: {result.status}, Cost: ${result.cost['total_cost_usd']:.4f}")
    """

    def __init__(
        self,
        cwd: Optional[str] = None,
        include_mcp: bool = True,
        track_memory: bool = False,
        verbose: bool = False,
        **kwargs: Any,
    ):
        """Initialize executor.

        Args:
            cwd: Working directory
            include_mcp: Include MCP servers
            track_memory: Track in memory (requires memory manager)
            verbose: Enable verbose logging
            **kwargs: Additional options (cost_budget, etc.)
        """
        super().__init__(cwd=cwd, verbose=verbose, **kwargs)
        
        self.include_mcp = include_mcp
        self.track_memory = track_memory
        
        # Cost tracker
        self.cost_tracker = CostTracker(budget_usd=kwargs.get('cost_budget'))
        
        # Plugin discovery
        self._plugins = discover_plugins()
        
        # Agent factory (lazy loaded)
        self._factory = None

    @property
    def factory(self):
        """Lazy load agent factory."""
        if self._factory is None:
            try:
                from agents.factory import create_userscope_factory
                self._factory = create_userscope_factory(cwd=self.config.cwd)
            except ImportError:
                logger.warning("Agent factory not available")
        return self._factory

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _generate_task_id(self) -> str:
        """Generate unique task ID."""
        content = f"{datetime.now().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def _has_image_content(self, task: str) -> bool:
        """Check if task involves images."""
        image_indicators = ['image', 'picture', 'photo', 'screenshot', 'diagram']
        task_lower = task.lower()
        return any(ind in task_lower for ind in image_indicators)

    def _build_options(self, agent_name: str, **overrides: Any) -> Dict[str, Any]:
        """Build SDK options for agent execution."""
        if not self.factory:
            return {"model": "claude-sonnet-4-20250514", "cwd": self.config.cwd}
        
        factory_options = self.factory.create(agent_name)
        options = build_sdk_options(
            factory_options,
            cwd=self.config.cwd,
            include_mcp=self.include_mcp,
            overrides=overrides,
        )
        validate_sdk_options(options)
        return options

    def _print_execution_status(
        self,
        metrics: ExecutionMetrics,
        model: str,
        turn: int,
    ) -> None:
        """Print real-time execution status."""
        print(
            f"\r[Turn {turn}] "
            f"In: {metrics.input_tokens:,} | "
            f"Out: {metrics.output_tokens:,} | "
            f"Cache: {metrics.cache_read_tokens:,}R/{metrics.cache_write_tokens:,}W",
            end="",
            flush=True,
        )

    # -------------------------------------------------------------------------
    # Streaming Execution
    # -------------------------------------------------------------------------

    async def run(
        self,
        agent_name: str,
        task: str,
        on_tool_use: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        **overrides: Any,
    ) -> AsyncIterator[Any]:
        """Stream execution with real-time message delivery.

        Args:
            agent_name: Name of the userscope agent
            task: Task description
            on_tool_use: Optional callback for tool use events
            **overrides: Configuration overrides

        Yields:
            SDK messages (AssistantMessage, ResultMessage, etc.)
        """
        self._check_sdk()
        
        task_id = self._generate_task_id()
        options_dict = self._build_options(agent_name, **overrides)
        model = options_dict.get('model', 'sonnet')
        
        self.cost_tracker.start_execution(task_id, model=model)
        processed_ids: set = set()
        turn_num = 0

        try:
            async with ClaudeSDKClient(options_dict) as client:
                await client.query(task)

                async for message in client.receive_messages():
                    turn_num += 1

                    # Track tokens (deduplicated)
                    if SDK_AVAILABLE and isinstance(message, AssistantMessage):
                        msg_id = getattr(message, 'id', None)
                        if msg_id and msg_id not in processed_ids:
                            processed_ids.add(msg_id)
                            usage = getattr(message, 'usage', None)
                            if usage:
                                self.cost_tracker.update_execution(
                                    task_id,
                                    input_tokens=getattr(usage, 'input_tokens', 0),
                                    output_tokens=getattr(usage, 'output_tokens', 0),
                                    cache_read=getattr(usage, 'cache_read_input_tokens', 0),
                                    cache_write=getattr(usage, 'cache_creation_input_tokens', 0),
                                )

                        # Tool use callback
                        if on_tool_use:
                            for block in message.content:
                                if isinstance(block, ToolUseBlock):
                                    on_tool_use(block.name, block.input)

                        # Print status
                        metrics = self.cost_tracker.get_execution_metrics(task_id)
                        if metrics:
                            self._print_execution_status(metrics, model, turn_num)

                    yield message

                    if isinstance(message, ResultMessage):
                        break

            print()  # Newline after status
            logger.info(f"Task completed: {task_id}")

        except Exception as e:
            print()
            logger.error(f"Task failed: {e}")
            raise

    # -------------------------------------------------------------------------
    # Execute (BaseExecutor Implementation)
    # -------------------------------------------------------------------------

    async def _execute(self, task: str, **kwargs: Any) -> ExecutionResult:
        """Core execution implementation.

        Args:
            task: Task description
            **kwargs: Must include 'agent_name'

        Returns:
            ExecutionResult
        """
        agent_name = kwargs.pop('agent_name', 'dev-feature')
        return await self.execute(agent_name, task, **kwargs)

    async def execute(
        self,
        agent_name: str,
        task: str,
        collect_output: bool = True,
        **overrides: Any,
    ) -> ExecutionResult:
        """Execute task and return structured result.

        Args:
            agent_name: Agent name
            task: Task description
            collect_output: Collect text output
            **overrides: Configuration overrides

        Returns:
            ExecutionResult with status, output, cost
        """
        self._check_sdk()

        task_id = self._generate_task_id()
        result = ExecutionResult(task_id=task_id, agent_name=agent_name, task=task)
        result.session_id = task_id
        result.start()

        options_dict = self._build_options(agent_name, **overrides)
        model = options_dict.get('model', 'sonnet')

        metrics = self.cost_tracker.start_execution(task_id, model=model)
        result.metrics = metrics
        
        processed_ids: set = set()
        output_parts: List[str] = []

        try:
            async for message in self.run(agent_name, task, **overrides):
                result.add_message(message)

                if SDK_AVAILABLE and isinstance(message, AssistantMessage):
                    msg_id = getattr(message, 'id', None)
                    if msg_id and msg_id not in processed_ids:
                        processed_ids.add(msg_id)
                        usage = getattr(message, 'usage', None)
                        if usage:
                            self.cost_tracker.update_execution(
                                task_id,
                                input_tokens=getattr(usage, 'input_tokens', 0),
                                output_tokens=getattr(usage, 'output_tokens', 0),
                                cache_read=getattr(usage, 'cache_read_input_tokens', 0),
                                cache_write=getattr(usage, 'cache_creation_input_tokens', 0),
                            )

                if collect_output and SDK_AVAILABLE:
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                output_parts.append(block.text)
                            elif isinstance(block, ToolUseBlock):
                                result.add_tool_use(block.name, block.input)

                    elif isinstance(message, ResultMessage):
                        if hasattr(message, 'input_tokens'):
                            result.set_cost(
                                input_tokens=getattr(message, 'input_tokens', 0),
                                output_tokens=getattr(message, 'output_tokens', 0),
                                total_cost_usd=getattr(message, 'total_cost_usd', 0.0),
                            )

            result.complete(output="".join(output_parts))
            
            final_metrics = self.cost_tracker.complete_execution(task_id, model)
            if final_metrics:
                result.metrics = final_metrics
                self._print_final_summary(final_metrics)

        except Exception as e:
            result.fail(str(e))
            raise

        return result

    def _print_final_summary(self, metrics: ExecutionMetrics) -> None:
        """Print final token breakdown."""
        print(f"\n{'='*60}")
        print("TOKEN BREAKDOWN")
        print(f"{'='*60}")
        print(f"  Input:  {metrics.input_tokens:,}")
        print(f"  Output: {metrics.output_tokens:,}")
        print(f"  Cache:  {metrics.cache_read_tokens:,}R / {metrics.cache_write_tokens:,}W")
        print(f"  Cost:   ${metrics.total_cost_usd:.4f}")
        print(f"{'='*60}\n")

    # -------------------------------------------------------------------------
    # Auto-Select Execution
    # -------------------------------------------------------------------------

    async def execute_auto(self, task: str, **overrides: Any) -> ExecutionResult:
        """Execute with auto-selected agent.

        Args:
            task: Task description
            **overrides: Configuration overrides

        Returns:
            ExecutionResult
        """
        if not self.factory:
            return await self.execute("dev-feature", task, **overrides)
        
        self.factory.create_for_task(task)
        metadata = self.factory.get_current_metadata()
        agent_name = metadata.get("agent_name", "dev-feature")
        
        logger.info(f"Auto-selected agent: {agent_name}")
        return await self.execute(agent_name, task, **overrides)
