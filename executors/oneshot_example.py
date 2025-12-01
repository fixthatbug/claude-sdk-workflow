"""
Oneshot Executor - Single message execution with auto-escalation.
Implements Haiku-first strategy with automatic escalation to Sonnet
when quality checks fail.
Uses Claude Agent SDK for execution.
Advanced Implementation Features:
- Proper async/sync client usage
- Comprehensive error handling
- Message type checking with dataclass patterns
- Token usage accumulation
- Cost tracking across escalation attempts
- Tool use extraction and reporting
- Duration tracking
- Quality-based escalation logic
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import asyncio
import time
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    UserMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    ToolResultBlock,
    CLINotFoundError,
    ProcessError,
    CLIJSONDecodeError,
    ClaudeSDKError,
)
from .base import BaseExecutor
from core.config import Config
from core.types import (
    ExecutionResult,
    ExecutionMode,
    TokenUsage,
    CostBreakdown,
)
class OneshotExecutor(BaseExecutor):
    """
    Single-shot executor with intelligent model routing.
    Strategy:
    1. Start with Haiku (cost-effective)
    2. Check response quality
    3. Auto-escalate to Sonnet if quality fails
    Quality Checks:
    - Response contains escalation markers ("I cannot", etc.)
    - Response is too short (< min_quality_length)
    - Response indicates uncertainty
    Implementation based on Claude Agent SDK Python reference.
    """
    def __init__(
        self,
        config: Optional[Config] = None,
        model: Optional[str] = None
    ):
        """
        Initialize oneshot executor.
        Args:
            config: Configuration instance
            model: Override default model (skips auto-routing)
        """
        super().__init__(config)
        self._model_override = model
        self._escalated = False
        # Accumulated usage across escalation attempts
        self._total_usage = TokenUsage()
        self._total_cost = CostBreakdown()
        # Timing
        self._start_time: Optional[float] = None
    def setup(self) -> None:
        """Initialize executor state."""
        self._escalated = False
        self._total_usage = TokenUsage()
        self._total_cost = CostBreakdown()
        self._start_time = None
    def execute(
        self,
        task: str,
        system_prompt: str = ""
    ) -> ExecutionResult:
        """
        Execute single-shot request with auto-escalation.
        Args:
            task: The task/prompt to execute
            system_prompt: Optional system prompt
        Returns:
            ExecutionResult from best attempt
        Raises:
            CLINotFoundError: If Claude Code CLI not installed
            ProcessError: If CLI process fails
            CLIJSONDecodeError: If response parsing fails
        """
        self._start_timer()
        # Determine starting model
        if self._model_override:
            model = self._model_override
        else:
            model = self.config.routing.default_oneshot_model
        try:
            # First attempt with initial model
            result = self._execute_with_model(task, system_prompt, model)
            # Check if escalation needed (only if started with haiku)
            if (
                not self._model_override
                and model == "haiku"
                and self._needs_escalation(result.content)
            ):
                # Escalate to Sonnet
                self._escalated = True
                escalated_result = self._execute_with_model(
                    task,
                    system_prompt,
                    self.config.routing.default_streaming_model,
                )
                escalated_result.escalated = True
                return escalated_result
            return result
        except CLINotFoundError as e:
            raise CLINotFoundError(
                "Claude Code not found. Install: npm install -g @anthropic-ai/claude-code",
                cli_path=getattr(e, 'cli_path', None)
            )
        except ProcessError as e:
            raise ProcessError(
                f"CLI process failed: {e}",
                exit_code=getattr(e, 'exit_code', None),
                stderr=getattr(e, 'stderr', None)
            )
        except CLIJSONDecodeError as e:
            raise CLIJSONDecodeError(
                line=getattr(e, 'line', ''),
                original_error=getattr(e, 'original_error', e)
            )
    def _execute_with_model(
        self,
        task: str,
        system_prompt: str,
        model: str
    ) -> ExecutionResult:
        """
        Execute request with specific model using Claude Agent SDK.
        Args:
            task: The task to execute
            system_prompt: System prompt
            model: Model alias or ID
        Returns:
            ExecutionResult from this attempt
        """
        model_config = self.config.resolve_model(model)
        return self._execute_with_agent_sdk(
            task,
            system_prompt,
            model_config
        )
    def _execute_with_agent_sdk(
        self,
        task: str,
        system_prompt: str,
        model_config
    ) -> ExecutionResult:
        """
        Execute using Claude Agent SDK with proper message handling.
        Implementation follows the pattern from SDK documentation for
        basic file operations and message type checking.
        """
        # Create options for the query
        options = ClaudeAgentOptions(
            model=model_config.model_id,
            system_prompt=system_prompt if system_prompt else None,
            max_turns=1,
            permission_mode="bypassPermissions",
            allowed_tools=self.config.allowed_tools if hasattr(self.config, 'allowed_tools') else None,
        )
        # Run the query and collect messages
        messages = self._run_query_sync(prompt=task, options=options)
        # Extract information from messages
        content = ""
        tool_uses = []
        usage_data: Optional[Dict[str, Any]] = None
        stop_reason = None
        result_message: Optional[ResultMessage] = None
        for message in messages:
            if isinstance(message, AssistantMessage):
                # Extract text content
                for block in message.content:
                    if isinstance(block, TextBlock):
                        content += block.text
                    elif isinstance(block, ToolUseBlock):
                        tool_uses.append({
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                # Get model from message
                if hasattr(message, 'model'):
                    model_config.model_id = message.model
            elif isinstance(message, ResultMessage):
                result_message = message
                if hasattr(message, 'usage') and message.usage:
                    usage_data = message.usage
                if hasattr(message, 'subtype'):
                    stop_reason = message.subtype
        # Convert usage data to TokenUsage
        usage = self._convert_usage(usage_data)
        # Calculate cost
        cost = self._calculate_cost(usage, model_config.model_id)
        # Accumulate totals
        self._accumulate_usage(usage, cost)
        return ExecutionResult(
            content=content,
            usage=self._total_usage,
            cost=self._total_cost,
            model=model_config.model_id,
            mode=ExecutionMode.ONESHOT,
            stop_reason=stop_reason,
            tool_uses=tool_uses,
            duration_ms=self._get_duration_ms(),
            escalated=self._escalated,
        )
    def _run_query_sync(
        self,
        prompt: str,
        options: ClaudeAgentOptions
    ) -> List[Any]:
        """
        Run query synchronously and collect all messages.
        Args:
            prompt: User prompt
            options: Claude Agent options
        Returns:
            List of all messages from the query
        """
        messages = []
        # Use asyncio to run the async generator
        async def collect_messages():
            async for message in query(prompt=prompt, options=options):
                messages.append(message)
        # Run in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(collect_messages())
        return messages
    def _convert_usage(
        self,
        usage_data: Optional[Dict[str, Any]]
    ) -> TokenUsage:
        """
        Convert SDK usage data to TokenUsage.
        Args:
            usage_data: Raw usage dictionary from ResultMessage
        Returns:
            TokenUsage instance
        """
        if not usage_data:
            return TokenUsage()
        return TokenUsage(
            input_tokens=usage_data.get('input_tokens', 0),
            output_tokens=usage_data.get('output_tokens', 0),
            cache_read_tokens=usage_data.get('cache_read_input_tokens', 0),
            cache_write_tokens=usage_data.get('cache_creation_input_tokens', 0),
        )
    def _needs_escalation(self, response: str) -> bool:
        """
        Check if response indicates need for model escalation.
        Escalation triggers:
        - Response contains uncertainty markers
        - Response is suspiciously short
        - Response admits inability
        Args:
            response: The model's response text
        Returns:
            True if escalation is recommended
        """
        # Check for escalation markers
        response_lower = response.lower()
        for marker in self.config.routing.escalation_markers:
            if marker.lower() in response_lower:
                return True
        # Check for minimum quality length
        if len(response.strip()) < self.config.routing.min_quality_length:
            return True
        return False
    def _accumulate_usage(
        self,
        usage: TokenUsage,
        cost: CostBreakdown
    ) -> None:
        """Accumulate usage and cost across attempts."""
        self._total_usage.input_tokens += usage.input_tokens
        self._total_usage.output_tokens += usage.output_tokens
        self._total_usage.cache_read_tokens += usage.cache_read_tokens
        self._total_usage.cache_write_tokens += usage.cache_write_tokens
        self._total_cost.input_cost += cost.input_cost
        self._total_cost.output_cost += cost.output_cost
        self._total_cost.cache_read_cost += cost.cache_read_cost
        self._total_cost.cache_write_cost += cost.cache_write_cost
    def _start_timer(self) -> None:
        """Start execution timer."""
        self._start_time = time.time()
    def _get_duration_ms(self) -> int:
        """Get execution duration in milliseconds."""
        if self._start_time is None:
            return 0
        return int((time.time() - self._start_time) * 1000)
    def cleanup(self) -> None:
        """Release resources."""
        self._escalated = False
        self._start_time = None
# ============================================================================
# ADVANCED USAGE PATTERNS
# ============================================================================
class AdvancedOneshotExecutor(OneshotExecutor):
    """
    Advanced oneshot executor with additional features:
    - Custom tool definitions
    - Hook-based monitoring
    - Streaming support
    - Error recovery
    """
    def __init__(
        self,
        config: Optional[Config] = None,
        model: Optional[str] = None,
        enable_hooks: bool = False,
    ):
        super().__init__(config, model)
        self.enable_hooks = enable_hooks
        self.tool_call_log: List[Dict[str, Any]] = []
    def execute_with_hooks(
        self,
        task: str,
        system_prompt: str = "",
        pre_tool_callback=None,
        post_tool_callback=None,
    ) -> ExecutionResult:
        """
        Execute with hook-based monitoring.
        Hooks allow you to intercept and modify tool execution.
        """
        from claude_agent_sdk import HookMatcher, HookContext
        async def pre_tool_logger(
            input_data: Dict[str, Any],
            tool_use_id: Optional[str],
            context: HookContext,
        ) -> Dict[str, Any]:
            """Log all tool usage before execution."""
            tool_name = input_data.get("tool_name", "unknown")
            self.tool_call_log.append({
                "phase": "pre",
                "tool": tool_name,
                "input": input_data.get("tool_input", {}),
            })
            if pre_tool_callback:
                return pre_tool_callback(input_data, tool_use_id, context)
            return {}
        async def post_tool_logger(
            input_data: Dict[str, Any],
            tool_use_id: Optional[str],
            context: HookContext,
        ) -> Dict[str, Any]:
            """Log results after tool execution."""
            tool_name = input_data.get("tool_name", "unknown")
            self.tool_call_log.append({
                "phase": "post",
                "tool": tool_name,
            })
            if post_tool_callback:
                return post_tool_callback(input_data, tool_use_id, context)
            return {}
        # Create options with hooks
        model_config = self.config.resolve_model(
            self._model_override or self.config.routing.default_oneshot_model
        )
        options = ClaudeAgentOptions(
            model=model_config.model_id,
            system_prompt=system_prompt if system_prompt else None,
            max_turns=1,
            hooks={
                "PreToolUse": [HookMatcher(hooks=[pre_tool_logger])],
                "PostToolUse": [HookMatcher(hooks=[post_tool_logger])],
            },
        )
        self._start_timer()
        messages = self._run_query_sync(prompt=task, options=options)
        # Process messages (same as base implementation)
        content = ""
        tool_uses = []
        usage_data = None
        for message in messages:
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        content += block.text
                    elif isinstance(block, ToolUseBlock):
                        tool_uses.append({
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
            elif isinstance(message, ResultMessage):
                if hasattr(message, "usage"):
                    usage_data = message.usage
        usage = self._convert_usage(usage_data)
        cost = self._calculate_cost(usage, model_config.model_id)
        return ExecutionResult(
            content=content,
            usage=usage,
            cost=cost,
            model=model_config.model_id,
            mode=ExecutionMode.ONESHOT,
            tool_uses=tool_uses,
            duration_ms=self._get_duration_ms(),
            escalated=False,
        )
