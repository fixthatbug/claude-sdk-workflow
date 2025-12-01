"""
Agent Client - Adapter layer for Claude Agent SDK.
Provides singleton management and compatibility with existing executor architecture.
"""
import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional
from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    query,
)
from .config import Config, get_config
from .types import CostBreakdown, Message, TokenUsage
@dataclass
class SDKUsage:
    """Extracted usage from SDK messages."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
def extract_usage_from_message(message) -> SDKUsage:
    """
    Extract token usage from a Claude Agent SDK message.
    Handles both AssistantMessage and ResultMessage types.
    ResultMessage has usage directly, AssistantMessage may have it nested.
    """
    usage = SDKUsage()
    # Check if this is a ResultMessage (has usage directly)
    if hasattr(message, 'usage') and message.usage:
        msg_usage = message.usage
        # ResultMessage.usage is typically a dict or object with these fields
        if isinstance(msg_usage, dict):
            usage.input_tokens = msg_usage.get('input_tokens', 0) or 0
            usage.output_tokens = msg_usage.get('output_tokens', 0) or 0
            usage.cache_read_tokens = msg_usage.get('cache_read_input_tokens', 0) or 0
            usage.cache_write_tokens = msg_usage.get('cache_creation_input_tokens', 0) or 0
        else:
            # Object with attributes
            if hasattr(msg_usage, 'input_tokens'):
                usage.input_tokens = getattr(msg_usage, 'input_tokens', 0) or 0
            if hasattr(msg_usage, 'output_tokens'):
                usage.output_tokens = getattr(msg_usage, 'output_tokens', 0) or 0
            if hasattr(msg_usage, 'cache_read_input_tokens'):
                usage.cache_read_tokens = getattr(msg_usage, 'cache_read_input_tokens', 0) or 0
            if hasattr(msg_usage, 'cache_creation_input_tokens'):
                usage.cache_write_tokens = getattr(msg_usage, 'cache_creation_input_tokens', 0) or 0
    return usage
def sdk_usage_to_token_usage(sdk_usage: SDKUsage) -> TokenUsage:
    """Convert SDKUsage to our TokenUsage type."""
    return TokenUsage(
        input_tokens=sdk_usage.input_tokens,
        output_tokens=sdk_usage.output_tokens,
        cache_read_tokens=sdk_usage.cache_read_tokens,
        cache_write_tokens=sdk_usage.cache_write_tokens,
    )
def extract_text_from_message(message: AssistantMessage) -> str:
    """Extract text content from an SDK message."""
    texts = []
    if hasattr(message, 'content') and message.content:
        for block in message.content:
            if isinstance(block, TextBlock):
                texts.append(block.text)
    return ''.join(texts)
def extract_tool_uses_from_message(message: AssistantMessage) -> List[Dict[str, Any]]:
    """Extract tool use blocks from an SDK message."""
    tool_uses = []
    if hasattr(message, 'content') and message.content:
        for block in message.content:
            if isinstance(block, ToolUseBlock):
                tool_uses.append({
                    'id': getattr(block, 'id', ''),
                    'name': getattr(block, 'name', ''),
                    'input': getattr(block, 'input', {}),
                })
    return tool_uses
def extract_session_id_from_message(message: AssistantMessage) -> Optional[str]:
    """
    Extract session ID from SDK init message.
    Args:
        message: AssistantMessage from SDK
    Returns:
        Session ID string if found in init message, None otherwise
    """
    # Check if this is an init message with session_id
    if hasattr(message, 'subtype') and message.subtype == 'init':
        if hasattr(message, 'data') and isinstance(message.data, dict):
            return message.data.get('session_id')
    # Also check for session_id directly on message
    if hasattr(message, 'session_id'):
        return getattr(message, 'session_id', None)
    return None
class AgentClientManager:
    """
    Singleton manager for Claude Agent SDK clients.
    Provides thread-safe access to SDK query function and session clients.
    Adapts SDK interface to match existing executor expectations.
    """
    _instance: Optional['AgentClientManager'] = None
    _lock: threading.Lock = threading.Lock()
    def __new__(cls) -> 'AgentClientManager':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    def __init__(self):
        if self._initialized:
            return
        self._config: Config = get_config()
        self._session_clients: Dict[str, ClaudeSDKClient] = {}
        self._current_session_id: Optional[str] = None
        self._initialized = True
    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to actual model ID."""
        if model in self._config.aliases:
            return self._config.aliases[model]
        return model
    def create_options(
        self,
        model: Optional[str] = None,
        system_prompt: str = "",
        max_turns: int = None, # None = unlimited, SDK auto-compacts
        # Tool control
        allowed_tools: Optional[List[str]] = None,
        disallowed_tools: Optional[List[str]] = None,
        # Agent delegation
        agents: Optional[Dict[str, AgentDefinition]] = None,
        # Hook system
        hooks: Optional[Dict[str, List]] = None,
        # MCP servers
        mcp_servers: Optional[Dict[str, Any]] = None,
        # Session management
        permission_mode: Optional[str] = None,
        resume: Optional[str] = None,
        fork_session: bool = False,
        # Structured output
        output_format: Optional[Dict[str, Any]] = None,
        # Extended thinking
        max_thinking_tokens: Optional[int] = None,
        # Working directory
        cwd: Optional[str] = None,
        **kwargs
    ) -> ClaudeAgentOptions:
        """
        Create ClaudeAgentOptions with full SDK support.
        Args:
            model: Model name or alias (resolved via config)
            system_prompt: System prompt for the agent
            max_turns: Maximum conversation turns
            allowed_tools: List of tool names to allow
            disallowed_tools: List of tool names to disallow
            agents: Dictionary of subagent definitions for delegation
            hooks: Dictionary of hook functions by event name
            mcp_servers: MCP server configurations
            permission_mode: Permission mode ("default", "acceptEdits", "plan", etc.)
            resume: Session ID to resume
            fork_session: Whether to fork the session
            output_format: Structured output schema
            max_thinking_tokens: Maximum tokens for extended thinking
            cwd: Working directory for agent execution
            **kwargs: Additional options
        Returns:
            Configured ClaudeAgentOptions instance
        """
        # Resolve model alias if needed
        resolved_model = self._resolve_model(model) if model else None
        options = ClaudeAgentOptions(
            # Basic options
            system_prompt=system_prompt if system_prompt else None,
            model=resolved_model,
            max_turns=max_turns,
            # Tool control
            allowed_tools=allowed_tools or [],
            disallowed_tools=disallowed_tools or [],
            # Agent delegation
            agents=agents,
            # Hook system
            hooks=hooks,
            # MCP servers
            mcp_servers=mcp_servers or {},
            # Session management
            resume=resume,
            fork_session=fork_session,
            # Permission control
            permission_mode=permission_mode,
            # Structured output
            output_format=output_format,
            # Extended thinking
            max_thinking_tokens=max_thinking_tokens,
            # Working directory
            cwd=cwd,
        )
        return options
    def create_subagent_definition(
        self,
        description: str,
        prompt: str,
        allowed_tools: List[str],
        model: str = "sonnet"
    ) -> AgentDefinition:
        """
        Create an AgentDefinition for subagent delegation.
        Args:
            description: Description of subagent's purpose
            prompt: System prompt for the subagent
            allowed_tools: List of allowed tool names
            model: Model to use (default: sonnet)
        Returns:
            AgentDefinition instance
        """
        return AgentDefinition(
            description=description,
            prompt=prompt,
            allowed_tools=allowed_tools,
            model=self._resolve_model(model),
        )
    def create_orchestrator_options(
        self,
        task: str,
        subagents: Dict[str, AgentDefinition],
        system_prompt: str,
        **kwargs
    ) -> ClaudeAgentOptions:
        """
        Create options specifically for orchestrator mode.
        Args:
            task: Main task description
            subagents: Dictionary of subagent definitions
            system_prompt: Orchestrator system prompt
            **kwargs: Additional options
        Returns:
            ClaudeAgentOptions configured for orchestration
        """
        return self.create_options(
            model="opus", # Use highest intelligence for orchestration
            system_prompt=system_prompt,
            agents=subagents,
            max_turns=50, # Allow multi-turn orchestration
            allowed_tools=["Task", "TodoWrite", "Read", "Grep", "Glob"],
            **kwargs
        )
    def capture_session_id(self, message: AssistantMessage) -> None:
        """
        Capture session ID from SDK message if present.
        Args:
            message: AssistantMessage that may contain session_id
        """
        session_id = extract_session_id_from_message(message)
        if session_id:
            self._current_session_id = session_id
    def get_current_session_id(self) -> Optional[str]:
        """
        Get the current SDK session ID.
        Returns:
            Current session ID or None
        """
        return self._current_session_id
    def clear_session_id(self) -> None:
        """Clear the current session ID."""
        self._current_session_id = None
    async def oneshot_query(
        self,
        prompt: str,
        options: Optional[ClaudeAgentOptions] = None,
    ) -> AsyncIterator[AssistantMessage]:
        """
        Execute a one-shot query using the SDK query function.
        Args:
            prompt: The user prompt
            options: Optional ClaudeAgentOptions
        Yields:
            AssistantMessage objects from the response
        """
        async for message in query(prompt=prompt, options=options):
            # Capture session ID from init messages
            self.capture_session_id(message)
            yield message
    def get_session_client(
        self,
        session_id: str,
        **kwargs
    ) -> ClaudeSDKClient:
        """
        Get or create a session client for multi-turn conversations.
        Args:
            session_id: Unique session identifier
            **kwargs: Additional client configuration
        Returns:
            ClaudeSDKClient instance for the session
        """
        if session_id not in self._session_clients:
            client = ClaudeSDKClient(**kwargs)
            self._session_clients[session_id] = client
        return self._session_clients[session_id]
    def close_session(self, session_id: str) -> None:
        """Close and remove a session client."""
        if session_id in self._session_clients:
            client = self._session_clients.pop(session_id)
            # SDK client cleanup if needed
            if hasattr(client, 'disconnect'):
                try:
                    asyncio.get_event_loop().run_until_complete(client.disconnect())
                except Exception:
                    pass
    def close_all_sessions(self) -> None:
        """Close all active session clients."""
        for session_id in list(self._session_clients.keys()):
            self.close_session(session_id)
# Module-level singleton accessor
_manager: Optional[AgentClientManager] = None
def get_agent_client() -> AgentClientManager:
    """Get the singleton AgentClientManager instance."""
    global _manager
    if _manager is None:
        _manager = AgentClientManager()
    return _manager
def reset_agent_client() -> None:
    """Reset the singleton (for testing)."""
    global _manager
    if _manager is not None:
        _manager.close_all_sessions()
        _manager = None
# Sync wrapper for oneshot query (for compatibility with sync executors)
def run_oneshot_sync(
    prompt: str,
    options: Optional[ClaudeAgentOptions] = None,
) -> List[AssistantMessage]:
    """
    Synchronous wrapper for oneshot query.
    Collects all messages and returns them as a list.
    """
    async def _collect():
        messages = []
        manager = get_agent_client()
        async for message in manager.oneshot_query(prompt, options):
            messages.append(message)
        return messages
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, use nest_asyncio or run in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _collect())
                return future.result()
        else:
            return loop.run_until_complete(_collect())
    except RuntimeError:
        # No event loop, create new one
        return asyncio.run(_collect())
