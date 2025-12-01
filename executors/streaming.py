"""
Streaming Executor - Real-time output with event callbacks.
Provides streaming responses with checkpointing support for
long-running operations.
Uses Claude Agent SDK for streaming execution.
"""
from typing import Optional, Callable, List, Dict, Any
import json
import asyncio
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
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, ResultMessage
class StreamingExecutor(BaseExecutor):
    """
    Streaming executor with event-driven callbacks.
    Features:
    - Real-time text streaming via on_text callback
    - Tool use notifications via on_tool_use callback
    - Completion callback for final processing
    - Automatic checkpointing before long operations
    - Session state persistence
    """
    def __init__(
        self,
        config: Optional[Config] = None,
        model: Optional[str] = None,
        on_text: Optional[Callable[[str], None]] = None,
        on_tool_use: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_complete: Optional[Callable[[ExecutionResult], None]] = None,
        session_manager: Optional[Any] = None,
        resume_session_id: Optional[str] = None,
        cwd: Optional[str] = None,
        permission_mode: Optional[str] = None,
    ):
        """
        Initialize streaming executor.
        Args:
            config: Configuration instance
            model: Override default model
            on_text: Callback for text chunks
            on_tool_use: Callback for tool use events
            on_complete: Callback when streaming completes
            session_manager: Optional SessionManager for persistence
            resume_session_id: SDK session ID to resume from
            cwd: Working directory for agent execution
            permission_mode: SDK permission mode ("default", "acceptEdits", "bypassPermissions")
        """
        super().__init__(config)
        self._agent_client = None
        self._model = model or self.config.routing.default_streaming_model
        self._cwd = cwd
        self._permission_mode = permission_mode
        # Callbacks
        self._on_text = on_text or self._default_on_text
        self._on_tool_use = on_tool_use or self._default_on_tool_use
        self._on_complete = on_complete or self._default_on_complete
        # Streaming state
        self._accumulated_text = ""
        self._tool_uses: List[Dict[str, Any]] = []
        self._current_tool: Optional[Dict[str, Any]] = None
        # Session management
        self._session_manager = session_manager
        self._resume_session_id = resume_session_id
        self._sdk_session_id: Optional[str] = None
    def setup(self) -> None:
        """Initialize Claude Agent SDK client and session state."""
        self._agent_client = get_agent_client()
        self._session = SessionState(
            mode=ExecutionMode.STREAMING,
            model=self._model,
            status=SessionStatus.CREATED,
        )
        self._accumulated_text = ""
        self._tool_uses = []
    def execute(self, task: str, system_prompt: str = "") -> ExecutionResult:
        """
        Execute streaming request with callbacks.
        Args:
            task: The task/prompt to execute
            system_prompt: Optional system prompt
        Returns:
            ExecutionResult with accumulated content
        """
        self._start_timer()
        # Update session
        self._session.status = SessionStatus.RUNNING
        self._session.system_prompt = system_prompt
        self._session.add_message("user", task)
        model_config = self.config.resolve_model(self._model)
        return self._execute_with_agent_sdk(task, system_prompt, model_config)
    def _execute_with_agent_sdk(
        self,
        task: str,
        system_prompt: str,
        model_config
    ) -> ExecutionResult:
        """Execute streaming using Claude Agent SDK."""
        # Create options for streaming with resume support
        options = self._agent_client.create_options(
            model=model_config.model_id,
            system_prompt=system_prompt,
            max_turns=None, # Unlimited turns - SDK handles auto-compact
            resume=self._resume_session_id, # Pass session ID for resume
            cwd=self._cwd, # Working directory for agent execution
            permission_mode=self._permission_mode, # Permission mode for auto-accept
        )
        # Run async streaming in sync context
        async def _stream():
            result_message = None
            async with ClaudeSDKClient(options) as client:
                await client.query(task)
                async for message in client.receive_response():
                    # Capture ResultMessage for usage/cost data
                    if isinstance(message, ResultMessage):
                        result_message = message
                    elif isinstance(message, AssistantMessage):
                        # Capture session ID from init messages
                        session_id = extract_session_id_from_message(message)
                        if session_id:
                            self._sdk_session_id = session_id
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
                            self._on_text(text)
                        # Extract tool uses
                        tools = extract_tool_uses_from_message(message)
                        for tool in tools:
                            self._tool_uses.append(tool)
                            self._on_tool_use(tool)
                        # Checkpoint periodically
                        if len(self._accumulated_text) % 1000 < len(text):
                            self._maybe_checkpoint()
                # Return ResultMessage for usage extraction
                return result_message
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _stream())
                    final_message = future.result()
            else:
                final_message = loop.run_until_complete(_stream())
        except RuntimeError:
            final_message = asyncio.run(_stream())
        # Extract usage
        if final_message:
            sdk_usage = extract_usage_from_message(final_message)
            usage = sdk_usage_to_token_usage(sdk_usage)
            stop_reason = getattr(final_message, 'stop_reason', None)
        else:
            usage = TokenUsage()
            stop_reason = None
        cost = self._calculate_cost(usage, model_config.model_id)
        # Update session
        self._session.total_usage = usage
        self._session.total_cost = cost
        self._session.status = SessionStatus.COMPLETED
        self._session.add_message("assistant", self._accumulated_text)
        result = ExecutionResult(
            content=self._accumulated_text,
            usage=usage,
            cost=cost,
            model=model_config.model_id,
            mode=ExecutionMode.STREAMING,
            stop_reason=stop_reason,
            tool_uses=self._tool_uses,
            duration_ms=self._get_duration_ms(),
        )
        self._on_complete(result)
        return result
    def _maybe_checkpoint(self) -> None:
        """Create checkpoint if conditions met."""
        if self._session:
            self._session.create_checkpoint(self._accumulated_text)
    def create_checkpoint(self) -> Checkpoint:
        """
        Manually create a checkpoint of current state.
        Returns:
            Checkpoint with current accumulated state
        """
        if not self._session:
            raise RuntimeError("No active session for checkpointing")
        return self._session.create_checkpoint(self._accumulated_text)
    def get_sdk_session_id(self) -> Optional[str]:
        """
        Get the captured SDK session ID.
        Returns:
            SDK session ID if captured, None otherwise
        """
        return self._sdk_session_id
    def resume_from_checkpoint(self, checkpoint: Checkpoint) -> None:
        """
        Resume execution from a checkpoint.
        Args:
            checkpoint: Checkpoint to resume from
        """
        self._accumulated_text = checkpoint.accumulated_text
        self._tool_uses = checkpoint.tool_uses.copy()
        if self._session:
            self._session.messages = checkpoint.messages.copy()
            self._session.total_usage = checkpoint.usage
            self._session.total_cost = checkpoint.cost
            self._session.status = SessionStatus.RUNNING
    def _default_on_text(self, text: str) -> None:
        """Default text callback - prints to stdout."""
        print(text, end="", flush=True)
    def _default_on_tool_use(self, tool: Dict[str, Any]) -> None:
        """Default tool use callback - logs tool name."""
        print(f"\n[Tool: {tool['name']}]", flush=True)
    def _default_on_complete(self, result: ExecutionResult) -> None:
        """Default completion callback - prints newline."""
        print() # Newline after streaming
    def cleanup(self) -> None:
        """Release resources and finalize session."""
        if self._session and self._session.status == SessionStatus.RUNNING:
            self._session.status = SessionStatus.COMPLETED
        self._agent_client = None
        self._accumulated_text = ""
        self._tool_uses = []
