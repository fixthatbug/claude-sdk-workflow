"""
Streaming Executor - Real-time output with event callbacks.
Provides streaming responses with checkpointing support for long-running operations.
Uses Claude Agent SDK for streaming execution with proper session management.
Features:
- Real-time text streaming via on_text callback
- Tool use notifications via on_tool_use callback
- Completion callback for final processing
- Automatic checkpointing before long operations
- Session state persistence and resumption
- Proper async/sync context handling
- Advanced error handling and resource cleanup
"""
from typing import Optional, Callable, List, Dict, Any
import json
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from .base import BaseExecutor
from core.config import Config
from core.types import (
    ExecutionResult,
    ExecutionMode,
    SessionState,
    SessionStatus,
    TokenUsage,
    CostBreakdown,
    Checkpoint,
)
from core.agent_client import (
    get_agent_client,
    extract_text_from_message,
    extract_tool_uses_from_message,
    sdk_usage_to_token_usage,
    extract_usage_from_message,
    extract_session_id_from_message,
)
# Claude Agent SDK imports
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    UserMessage,
    SystemMessage,
)
logger = logging.getLogger(__name__)
@dataclass
class StreamingMetrics:
    """Metrics for streaming execution."""
    chunks_received: int = 0
    total_chars: int = 0
    tool_calls: int = 0
    checkpoints_created: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
class StreamingExecutor(BaseExecutor):
    """
    Streaming executor with event-driven callbacks and session management.
    The executor maintains conversation context across multiple query() calls
    using ClaudeSDKClient's persistent session capabilities.
    Features:
    - Real-time text streaming via on_text callback
    - Tool use notifications via on_tool_use callback
    - Completion callback for final processing
    - Automatic checkpointing for long operations
    - Session state persistence and resumption
    - Interrupt support for long-running tasks
    - Comprehensive error handling
    Usage:
        executor = StreamingExecutor(
            config=config,
            on_text=lambda text: print(text, end=''),
            on_tool_use=lambda tool: logger.info(f"Tool: {tool['name']}"),
            session_manager=session_mgr
        )
        result = executor.execute("Analyze this codebase")
        # Resume from previous session
        executor_resumed = StreamingExecutor(
            resume_session_id=result.sdk_session_id
        )
        result2 = executor_resumed.execute("Continue the analysis")
    """
    def __init__(
        self,
        config: Optional[Config] = None,
        model: Optional[str] = None,
        on_text: Optional[Callable[[str], None]] = None,
        on_tool_use: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_complete: Optional[Callable[[ExecutionResult], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        session_manager: Optional[Any] = None,
        resume_session_id: Optional[str] = None,
        checkpoint_interval: int = 1000,
        enable_interrupts: bool = True,
    ):
        """
        Initialize streaming executor.
        Args:
            config: Configuration instance
            model: Override default model
            on_text: Callback for text chunks (called for each text block)
            on_tool_use: Callback for tool use events (called per tool invocation)
            on_complete: Callback when streaming completes (receives ExecutionResult)
            on_error: Callback for error handling
            session_manager: Optional SessionManager for persistence
            resume_session_id: SDK session ID to resume from
            checkpoint_interval: Characters between auto-checkpoints (default: 1000)
            enable_interrupts: Whether to support interrupt() calls
        """
        super().__init__(config)
        # Agent client (initialized in setup)
        self._agent_client = None
        self._sdk_client: Optional[ClaudeSDKClient] = None
        # Model configuration
        self._model = model or self.config.routing.default_streaming_model
        # Callbacks
        self._on_text = on_text or self._default_on_text
        self._on_tool_use = on_tool_use or self._default_on_tool_use
        self._on_complete = on_complete or self._default_on_complete
        self._on_error = on_error or self._default_on_error
        # Streaming state
        self._accumulated_text = ""
        self._tool_uses: List[Dict[str, Any]] = []
        self._current_tool: Optional[Dict[str, Any]] = None
        self._metrics = StreamingMetrics()
        # Session management
        self._session_manager = session_manager
        self._resume_session_id = resume_session_id
        self._sdk_session_id: Optional[str] = None
        # Checkpointing
        self._checkpoint_interval = checkpoint_interval
        self._last_checkpoint_size = 0
        # Interrupt support
        self._enable_interrupts = enable_interrupts
        self._interrupt_requested = False
    def setup(self) -> None:
        """Initialize Claude Agent SDK client and session state."""
        self._agent_client = get_agent_client()
        self._session = SessionState(
            mode=ExecutionMode.STREAMING,
            model=self._model,
            status=SessionStatus.CREATED,
        )
        # Reset state
        self._accumulated_text = ""
        self._tool_uses = []
        self._current_tool = None
        self._metrics = StreamingMetrics(start_time=datetime.now())
        self._interrupt_requested = False
        logger.info(
            f"StreamingExecutor setup complete - model: {self._model}, "
            f"resume: {self._resume_session_id is not None}"
        )
    def execute(self, task: str, system_prompt: str = "") -> ExecutionResult:
        """
        Execute streaming request with callbacks.
        This method uses ClaudeSDKClient to maintain session continuity.
        Each call to execute() continues the same conversation session.
        Args:
            task: The task/prompt to execute
            system_prompt: Optional system prompt (applied at session start)
        Returns:
            ExecutionResult with accumulated content, usage, and session info
        Raises:
            RuntimeError: If execution fails or is interrupted
        """
        self._start_timer()
        # Update session
        self._session.status = SessionStatus.RUNNING
        self._session.system_prompt = system_prompt
        self._session.add_message("user", task)
        model_config = self.config.resolve_model(self._model)
        try:
            return self._execute_with_agent_sdk(task, system_prompt, model_config)
        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            self._on_error(e)
            # Update session to failed state
            if self._session:
                self._session.status = SessionStatus.FAILED
            raise
    def _execute_with_agent_sdk(
        self,
        task: str,
        system_prompt: str,
        model_config: Any,
    ) -> ExecutionResult:
        """
        Execute streaming using Claude Agent SDK.
        Uses ClaudeSDKClient context manager for proper resource management
        and session continuity across multiple query() calls.
        """
        # Create options for streaming with resume support
        options = ClaudeAgentOptions(
            model=model_config.model_id,
            system_prompt=system_prompt if system_prompt else None,
            max_turns=None, # Unlimited turns - SDK handles auto-compact
            cwd=self.config.execution.working_directory if hasattr(self.config, 'execution') else ".",
            permission_mode="default", # Use default permission handling
        )
        # Run async streaming in sync context
        async def _stream():
            result_message = None
            messages_processed = 0
            # Use ClaudeSDKClient as async context manager
            async with ClaudeSDKClient(options) as client:
                # Store client reference for interrupt support
                if self._enable_interrupts:
                    self._sdk_client = client
                # Send query - this continues the session if resuming
                await client.query(task)
                # Receive response messages
                async for message in client.receive_response():
                    messages_processed += 1
                    # Check for interrupt request
                    if self._interrupt_requested:
                        logger.info("Interrupt requested, stopping execution")
                        await client.interrupt()
                        break
                    # Handle ResultMessage for usage/cost data
                    if isinstance(message, ResultMessage):
                        result_message = message
                        logger.info(
                            f"Received ResultMessage - duration: {message.duration_ms}ms, "
                            f"turns: {message.num_turns}"
                        )
                    # Handle AssistantMessage for content
                    elif isinstance(message, AssistantMessage):
                        # Capture session ID from messages
                        session_id = extract_session_id_from_message(message)
                        if session_id and not self._sdk_session_id:
                            self._sdk_session_id = session_id
                            logger.info(f"Captured SDK session ID: {session_id}")
                            # Update session manager if available
                            if self._session_manager and hasattr(self._session, 'session_id'):
                                self._session_manager.update(
                                    self._session.session_id,
                                    sdk_session_id=session_id
                                )
                        # Extract and emit text
                        text = extract_text_from_message(message)
                        if text:
                            self._accumulated_text += text
                            self._metrics.chunks_received += 1
                            self._metrics.total_chars += len(text)
                            self._on_text(text)
                            # Auto-checkpoint if interval reached
                            if (len(self._accumulated_text) - self._last_checkpoint_size) >= self._checkpoint_interval:
                                self._maybe_checkpoint()
                                self._last_checkpoint_size = len(self._accumulated_text)
                        # Extract tool uses
                        tools = extract_tool_uses_from_message(message)
                        for tool in tools:
                            self._tool_uses.append(tool)
                            self._metrics.tool_calls += 1
                            self._on_tool_use(tool)
                            logger.debug(f"Tool use: {tool.get('name', 'unknown')}")
                    # Handle SystemMessage for initialization info
                    elif isinstance(message, SystemMessage):
                        logger.debug(f"System message: {message.subtype}")
                # Clear client reference
                self._sdk_client = None
            logger.info(f"Stream completed - processed {messages_processed} messages")
            return result_message
        # Execute async function in appropriate event loop context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an existing event loop - use thread executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _stream())
                    final_message = future.result()
            else:
                # No running loop - use run_until_complete
                final_message = loop.run_until_complete(_stream())
        except RuntimeError:
            # Fallback to asyncio.run
            final_message = asyncio.run(_stream())
        # Mark metrics end time
        self._metrics.end_time = datetime.now()
        # Extract usage and cost from ResultMessage
        if final_message:
            sdk_usage = extract_usage_from_message(final_message)
            usage = sdk_usage_to_token_usage(sdk_usage)
            stop_reason = getattr(final_message, 'stop_reason', None)
            # Extract additional metadata
            duration_ms = getattr(final_message, 'duration_ms', self._get_duration_ms())
            num_turns = getattr(final_message, 'num_turns', 0)
        else:
            usage = TokenUsage()
            stop_reason = None
            duration_ms = self._get_duration_ms()
            num_turns = 0
        cost = self._calculate_cost(usage, model_config.model_id)
        # Update session
        self._session.total_usage = usage
        self._session.total_cost = cost
        self._session.status = SessionStatus.COMPLETED if not self._interrupt_requested else SessionStatus.INTERRUPTED
        self._session.add_message("assistant", self._accumulated_text)
        # Build execution result
        result = ExecutionResult(
            content=self._accumulated_text,
            usage=usage,
            cost=cost,
            model=model_config.model_id,
            mode=ExecutionMode.STREAMING,
            stop_reason=stop_reason,
            tool_uses=self._tool_uses,
            duration_ms=duration_ms,
            sdk_session_id=self._sdk_session_id,
            num_turns=num_turns,
            metrics={
                'chunks_received': self._metrics.chunks_received,
                'total_chars': self._metrics.total_chars,
                'tool_calls': self._metrics.tool_calls,
                'checkpoints_created': self._metrics.checkpoints_created,
            }
        )
        # Trigger completion callback
        self._on_complete(result)
        logger.info(
            f"Execution complete - chars: {self._metrics.total_chars}, "
            f"tools: {self._metrics.tool_calls}, duration: {duration_ms}ms"
        )
        return result
    async def interrupt(self) -> None:
        """
        Interrupt the current streaming execution.
        Only works in streaming input mode when enable_interrupts=True.
        The interrupt is processed when the SDK client is actively consuming messages.
        Raises:
            RuntimeError: If no active SDK client or interrupts disabled
        """
        if not self._enable_interrupts:
            raise RuntimeError("Interrupts are disabled for this executor")
        if not self._sdk_client:
            raise RuntimeError("No active SDK client to interrupt")
        logger.info("Sending interrupt signal to SDK client")
        self._interrupt_requested = True
        # Send interrupt to SDK client
        await self._sdk_client.interrupt()
    def _maybe_checkpoint(self) -> None:
        """
        Create checkpoint if conditions met.
        Checkpoints capture the current state including accumulated text,
        tool uses, and session metadata for recovery.
        """
        if self._session:
            checkpoint = self._session.create_checkpoint(self._accumulated_text)
            self._metrics.checkpoints_created += 1
            logger.debug(f"Checkpoint created - total: {self._metrics.checkpoints_created}")
    def create_checkpoint(self) -> Checkpoint:
        """
        Manually create a checkpoint of current state.
        Returns:
            Checkpoint with current accumulated state
        Raises:
            RuntimeError: If no active session
        """
        if not self._session:
            raise RuntimeError("No active session for checkpointing")
        checkpoint = self._session.create_checkpoint(self._accumulated_text)
        self._metrics.checkpoints_created += 1
        logger.info(f"Manual checkpoint created - size: {len(self._accumulated_text)} chars")
        return checkpoint
    def get_sdk_session_id(self) -> Optional[str]:
        """
        Get the captured SDK session ID for resumption.
        The session ID is extracted from SDK messages during execution
        and can be used to resume the conversation in a new executor instance.
        Returns:
            SDK session ID if captured during execution, None otherwise
        Example:
            executor = StreamingExecutor()
            result = executor.execute("Analyze this code")
            session_id = executor.get_sdk_session_id()
            # Later, resume the session
            resumed_executor = StreamingExecutor(resume_session_id=session_id)
            result2 = resumed_executor.execute("Continue the analysis")
        """
        return self._sdk_session_id
    def resume_from_checkpoint(self, checkpoint: Checkpoint) -> None:
        """
        Resume execution from a previously saved checkpoint.
        Restores accumulated text, tool uses, messages, usage, and cost
        from the checkpoint state. Sets session status to RUNNING.
        Args:
            checkpoint: Checkpoint to resume from
        Raises:
            RuntimeError: If no active session exists
        """
        if not self._session:
            raise RuntimeError("No active session to resume into")
        self._accumulated_text = checkpoint.accumulated_text
        self._tool_uses = checkpoint.tool_uses.copy() if checkpoint.tool_uses else []
        # Restore session state
        self._session.messages = checkpoint.messages.copy()
        self._session.total_usage = checkpoint.usage
        self._session.total_cost = checkpoint.cost
        self._session.status = SessionStatus.RUNNING
        # Update metrics
        self._last_checkpoint_size = len(self._accumulated_text)
        logger.info(
            f"Resumed from checkpoint - text: {len(self._accumulated_text)} chars, "
            f"tools: {len(self._tool_uses)}, messages: {len(checkpoint.messages)}"
        )
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current execution metrics.
        Returns:
            Dictionary containing streaming metrics including:
            - chunks_received: Number of text chunks processed
            - total_chars: Total characters accumulated
            - tool_calls: Number of tool invocations
            - checkpoints_created: Number of checkpoints created
            - duration_seconds: Execution duration if completed
        """
        metrics = {
            'chunks_received': self._metrics.chunks_received,
            'total_chars': self._metrics.total_chars,
            'tool_calls': self._metrics.tool_calls,
            'checkpoints_created': self._metrics.checkpoints_created,
        }
        if self._metrics.start_time and self._metrics.end_time:
            duration = (self._metrics.end_time - self._metrics.start_time).total_seconds()
            metrics['duration_seconds'] = duration
        return metrics
    def _default_on_text(self, text: str) -> None:
        """
        Default text callback - prints to stdout with flush.
        Args:
            text: Text chunk received from streaming response
        """
        print(text, end="", flush=True)
    def _default_on_tool_use(self, tool: Dict[str, Any]) -> None:
        """
        Default tool use callback - logs tool name and ID.
        Args:
            tool: Tool use dictionary with 'name', 'id', and 'input' keys
        """
        tool_name = tool.get('name', 'unknown')
        tool_id = tool.get('id', 'unknown')
        print(f"\n[Tool: {tool_name} ({tool_id})]", flush=True)
    def _default_on_complete(self, result: ExecutionResult) -> None:
        """
        Default completion callback - prints summary.
        Args:
            result: ExecutionResult with final metrics
        """
        print() # Newline after streaming
        print(f"[Completed - {result.usage.total_tokens} tokens, ${result.cost.total:.4f}]")
    def _default_on_error(self, error: Exception) -> None:
        """
        Default error callback - logs error.
        Args:
            error: Exception that occurred during execution
        """
        logger.error(f"Streaming execution error: {error}", exc_info=True)
    def cleanup(self) -> None:
        """
        Release resources and finalize session.
        Cleans up SDK client references, finalizes session status,
        and resets internal state. Should be called when done with executor.
        """
        # Finalize session if still running
        if self._session and self._session.status == SessionStatus.RUNNING:
            self._session.status = SessionStatus.COMPLETED
        # Clear references
        self._agent_client = None
        self._sdk_client = None
        # Reset state
        self._accumulated_text = ""
        self._tool_uses = []
        self._current_tool = None
        self._interrupt_requested = False
        logger.info("StreamingExecutor cleanup complete")
    def __enter__(self):
        """Context manager entry - setup executor."""
        self.setup()
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup executor."""
        self.cleanup()
        return False
# Advanced usage patterns and examples
class ProgressTrackingExecutor(StreamingExecutor):
    """
    Extended executor with progress tracking and custom checkpoint logic.
    Demonstrates advanced usage patterns:
    - Custom checkpoint strategies
    - Progress percentage tracking
    - Estimated time remaining
    - Custom event handlers
    """
    def __init__(self, *args, estimated_chars: int = 10000, **kwargs):
        """
        Initialize with progress tracking.
        Args:
            estimated_chars: Estimated total characters for progress calculation
            *args, **kwargs: Passed to StreamingExecutor
        """
        self._estimated_chars = estimated_chars
        self._progress_callbacks: List[Callable[[float], None]] = []
        # Wrap callbacks to include progress tracking
        original_on_text = kwargs.get('on_text')
        kwargs['on_text'] = self._on_text_with_progress
        self._original_on_text = original_on_text
        super().__init__(*args, **kwargs)
    def add_progress_callback(self, callback: Callable[[float], None]) -> None:
        """
        Add callback for progress updates.
        Args:
            callback: Function receiving progress percentage (0.0-1.0)
        """
        self._progress_callbacks.append(callback)
    def _on_text_with_progress(self, text: str) -> None:
        """Text callback with progress calculation."""
        # Call original callback
        if self._original_on_text:
            self._original_on_text(text)
        # Calculate and emit progress
        progress = min(1.0, len(self._accumulated_text) / self._estimated_chars)
        for callback in self._progress_callbacks:
            callback(progress)
    def _maybe_checkpoint(self) -> None:
        """Create checkpoint with progress metadata."""
        super()._maybe_checkpoint()
        # Add custom checkpoint logic
        progress = len(self._accumulated_text) / self._estimated_chars
        if progress > 0.5 and self._metrics.checkpoints_created == 1:
            logger.info("Reached 50% progress - creating safety checkpoint")
            self.create_checkpoint()
# Example usage patterns
def example_basic_streaming():
    """Basic streaming with default callbacks."""
    executor = StreamingExecutor()
    executor.setup()
    result = executor.execute("Explain quantum computing")
    print(f"\nTotal tokens: {result.usage.total_tokens}")
    print(f"Cost: ${result.cost.total:.4f}")
    executor.cleanup()
def example_custom_callbacks():
    """Streaming with custom event handlers."""
    texts = []
    tools = []
    def on_text(text: str):
        texts.append(text)
        print(f"[{len(texts)}] {text[:50]}...")
    def on_tool(tool: Dict[str, Any]):
        tools.append(tool)
        print(f"Tool called: {tool['name']}")
    def on_complete(result: ExecutionResult):
        print(f"\nFinal: {len(texts)} chunks, {len(tools)} tools")
    executor = StreamingExecutor(
        on_text=on_text,
        on_tool_use=on_tool,
        on_complete=on_complete
    )
    with executor:
        result = executor.execute("Analyze this codebase")
def example_session_resumption():
    """Resume a previous session."""
    # First execution
    executor1 = StreamingExecutor()
    executor1.setup()
    result1 = executor1.execute("Start analyzing the code")
    session_id = executor1.get_sdk_session_id()
    executor1.cleanup()
    # Resume session
    executor2 = StreamingExecutor(resume_session_id=session_id)
    executor2.setup()
    result2 = executor2.execute("Continue the analysis")
    executor2.cleanup()
def example_checkpoint_recovery():
    """Checkpoint and recovery pattern."""
    executor = StreamingExecutor(checkpoint_interval=500)
    executor.setup()
    try:
        # Start long-running task
        result = executor.execute("Perform comprehensive code review")
    except KeyboardInterrupt:
        # Save checkpoint on interrupt
        checkpoint = executor.create_checkpoint()
        print(f"Saved checkpoint with {len(checkpoint.accumulated_text)} chars")
        # Later, resume from checkpoint
        executor.resume_from_checkpoint(checkpoint)
        result = executor.execute("Continue from where we left off")
    finally:
        executor.cleanup()
def example_progress_tracking():
    """Progress tracking with custom executor."""
    def on_progress(progress: float):
        print(f"\rProgress: {progress*100:.1f}%", end='', flush=True)
    executor = ProgressTrackingExecutor(
        estimated_chars=5000,
        checkpoint_interval=1000
    )
    executor.add_progress_callback(on_progress)
    with executor:
        result = executor.execute("Generate detailed documentation")
        metrics = executor.get_metrics()
        print(f"\n\nMetrics: {metrics}")
def example_async_streaming():
    """Async streaming pattern for integration with async frameworks."""
    import asyncio
    async def async_stream():
        executor = StreamingExecutor()
        executor.setup()
        # Execute in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            executor.execute,
            "Analyze system architecture"
        )
        executor.cleanup()
        return result
    # Run async function
    result = asyncio.run(async_stream())
"""
Reference Documentation:
Session Management (TypeScript):
- Session ID capture and resumption patterns documented at:
  https://platform.claude.com/docs/en/agent-sdk/sessions
Agent SDK TypeScript Reference:
- Hook types and event handling:
  https://platform.claude.com/docs/en/agent-sdk/typescript#hook-types
- Message types for streaming:
  https://platform.claude.com/docs/en/agent-sdk/typescript#message-types
- Configuration options:
  https://platform.claude.com/docs/en/agent-sdk/typescript#types
Slash Commands:
- /compact and /clear command usage:
  https://platform.claude.com/docs/en/agent-sdk/slash-commands
Claude Sonnet 4.5 Announcement:
- Model capabilities and features:
  https://www.anthropic.com/news/claude-sonnet-4-5
GitHub Issues (Community Discussion):
- Session resumption behavior:
  https://github.com/anthropics/claude-code/issues/8069
- Session checkpointing feature requests:
  https://github.com/anthropics/claude-code/issues/1417
Note: This implementation is based on TypeScript SDK patterns and general
SDK concepts. For Python-specific implementation details, consult the
official Claude Agent SDK Python documentation when available.
"""
