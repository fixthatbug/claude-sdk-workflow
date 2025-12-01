"""
Agent Client - Production-grade adapter layer for Claude Agent SDK.
Provides singleton management, session lifecycle control, and compatibility
with existing executor architecture. Implements advanced patterns including:
- Multi-turn conversation management via ClaudeSDKClient
- Hook system for deterministic processing
- Subagent delegation and orchestration
- Structured output validation
- Comprehensive usage tracking
- Thread-safe session management
Based on Claude Agent SDK documentation and examples.
"""
import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union
from claude_agent_sdk import (
   AgentDefinition,
   AssistantMessage,
   ClaudeAgentOptions,
   ClaudeSDKClient,
   ResultMessage,
   SystemMessage,
   TextBlock,
   ToolResultBlock,
   ToolUseBlock,
   UserMessage,
   query,
)
from .config import Config, get_config
from .types import CostBreakdown, Message, TokenUsage
# Configure logging
logger = logging.getLogger(__name__)
@dataclass
class SDKUsage:
   """
   Token usage extracted from SDK messages.
   Tracks input/output tokens and cache usage for cost calculation.
   """
   input_tokens: int = 0
   output_tokens: int = 0
   cache_read_tokens: int = 0
   cache_write_tokens: int = 0
   total_cost_usd: float = 0.0
def extract_usage_from_message(message: Any) -> SDKUsage:
   """
   Extract token usage from Claude Agent SDK message.
   ResultMessage contains usage and cost information. AssistantMessage
   may contain partial usage during streaming.
   Args:
       message: SDK message (ResultMessage, AssistantMessage, etc.)
   Returns:
       SDKUsage with extracted token counts and cost
   References:
       - ResultMessage has total_cost_usd field
       - Usage tracking in examples
   """
   usage = SDKUsage()
   # ResultMessage contains final cost information
   if isinstance(message, ResultMessage):
       if hasattr(message, 'total_cost_usd') and message.total_cost_usd:
           usage.total_cost_usd = message.total_cost_usd
   # Check for usage attribute (may be dict or object)
   if hasattr(message, 'usage') and message.usage:
       msg_usage = message.usage
       if isinstance(msg_usage, dict):
           usage.input_tokens = msg_usage.get('input_tokens', 0) or 0
           usage.output_tokens = msg_usage.get('output_tokens', 0) or 0
           usage.cache_read_tokens = msg_usage.get('cache_read_input_tokens', 0) or 0
           usage.cache_write_tokens = msg_usage.get('cache_creation_input_tokens', 0) or 0
       else:
           # Object with attributes
           usage.input_tokens = getattr(msg_usage, 'input_tokens', 0) or 0
           usage.output_tokens = getattr(msg_usage, 'output_tokens', 0) or 0
           usage.cache_read_tokens = getattr(msg_usage, 'cache_read_input_tokens', 0) or 0
           usage.cache_write_tokens = getattr(msg_usage, 'cache_creation_input_tokens', 0) or 0
   return usage
def sdk_usage_to_token_usage(sdk_usage: SDKUsage) -> TokenUsage:
   """
   Convert SDKUsage to application TokenUsage type.
   Args:
       sdk_usage: SDK usage data
   Returns:
       TokenUsage instance for application use
   """
   return TokenUsage(
       input_tokens=sdk_usage.input_tokens,
       output_tokens=sdk_usage.output_tokens,
       cache_read_tokens=sdk_usage.cache_read_tokens,
       cache_write_tokens=sdk_usage.cache_write_tokens,
   )
def extract_text_from_message(message: AssistantMessage) -> str:
   """
   Extract text content from SDK AssistantMessage.
   Args:
       message: AssistantMessage containing TextBlock content
   Returns:
       Concatenated text from all TextBlock elements
   References:
       - AssistantMessage structure
       - TextBlock extraction pattern
   """
   texts = []
   if hasattr(message, 'content') and message.content:
       for block in message.content:
           if isinstance(block, TextBlock):
               texts.append(block.text)
   return ''.join(texts)
def extract_tool_uses_from_message(message: AssistantMessage) -> List[Dict[str, Any]]:
   """
   Extract tool use blocks from SDK AssistantMessage.
   Args:
       message: AssistantMessage containing ToolUseBlock elements
   Returns:
       List of tool use dictionaries with id, name, and input
   References:
       - ToolUseBlock structure
       - Tool extraction examples
   """
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
def display_message(message: Any) -> None:
   """
   Display SDK message in human-readable format.
   Standardized display function for debugging and logging.
   Args:
       message: Any SDK message type
   References:
       - Message display pattern
   """
   if isinstance(message, UserMessage):
       for block in message.content:
           if isinstance(block, TextBlock):
               logger.info(f"User: {block.text}")
   elif isinstance(message, AssistantMessage):
       for block in message.content:
           if isinstance(block, TextBlock):
               logger.info(f"Claude: {block.text}")
   elif isinstance(message, ResultMessage):
       logger.info("Result ended")
       if hasattr(message, 'total_cost_usd') and message.total_cost_usd:
           logger.info(f"Cost: ${message.total_cost_usd:.4f}")
class AgentClientManager:
   """
   Production singleton manager for Claude Agent SDK clients.
   Provides thread-safe access to SDK query function and session clients.
   Implements advanced patterns:
   - Multi-turn conversations via ClaudeSDKClient
   - Hook system for deterministic processing
   - Subagent delegation
   - Session lifecycle management
   Usage:
       manager = get_agent_client()
       # One-shot query
       async for msg in manager.oneshot_query("Hello"):
           print(msg)
       # Multi-turn session
       async with manager.create_session("session-1") as client:
           await client.query("First question")
           async for msg in client.receive_response():
               print(msg)
           await client.query("Follow-up")
           async for msg in client.receive_response():
               print(msg)
   References:
       - ClaudeSDKClient usage
       - Session management patterns
       - Hook system
   """
   _instance: Optional['AgentClientManager'] = None
   _lock: threading.Lock = threading.Lock()
   def __new__(cls) -> 'AgentClientManager':
       """Thread-safe singleton instantiation."""
       if cls._instance is None:
           with cls._lock:
               if cls._instance is None:
                   cls._instance = super().__new__(cls)
                   cls._instance._initialized = False
       return cls._instance
   def __init__(self):
       """Initialize manager with config and session tracking."""
       if getattr(self, '_initialized', False):
           return
       self._config: Config = get_config()
       self._session_clients: Dict[str, ClaudeSDKClient] = {}
       self._session_locks: Dict[str, asyncio.Lock] = {}
       self._initialized = True
       logger.info("AgentClientManager initialized")
   def _resolve_model(self, model: Optional[str]) -> Optional[str]:
       """
       Resolve model alias to actual model ID.
       Args:
           model: Model name or alias
       Returns:
           Resolved model ID or original if no alias found
       """
       if not model:
           return None
       if hasattr(self._config, 'aliases') and model in self._config.aliases:
           return self._config.aliases[model]
       return model
   def create_options(
       self,
       model: Optional[str] = None,
       system_prompt: Optional[Union[str, Dict[str, Any]]] = None,
       max_turns: Optional[int] = None,
       # Tool control
       allowed_tools: Optional[List[str]] = None,
       disallowed_tools: Optional[List[str]] = None,
       # Agent delegation
       agents: Optional[Dict[str, AgentDefinition]] = None,
       # Hook system
       hooks: Optional[Dict[str, List[Any]]] = None,
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
       # Settings sources
       setting_sources: Optional[List[str]] = None,
       # Additional options
       **kwargs
   ) -> ClaudeAgentOptions:
       """
       Create ClaudeAgentOptions with full SDK support.
       Args:
           model: Model name or alias (resolved via config)
           system_prompt: System prompt string or preset dict
           max_turns: Maximum conversation turns (None = unlimited)
           allowed_tools: List of tool names to allow
           disallowed_tools: List of tool names to disallow
           agents: Dictionary of subagent definitions
           hooks: Dictionary of hook functions by event name
           mcp_servers: MCP server configurations
           permission_mode: "default", "acceptEdits", "plan", "bypassPermissions"
           resume: Session ID to resume
           fork_session: Fork session instead of continuing
           output_format: JSON schema for structured output
           max_thinking_tokens: Maximum tokens for extended thinking
           cwd: Working directory for agent execution
           setting_sources: Filesystem settings to load
           **kwargs: Additional SDK options
       Returns:
           Configured ClaudeAgentOptions instance
       References:
           - ClaudeAgentOptions structure
           - System prompt presets
           - Setting sources
       """
       # Resolve model alias
       resolved_model = self._resolve_model(model)
       # Build options dict
       options_dict = {
           'model': resolved_model,
           'max_turns': max_turns,
           'allowed_tools': allowed_tools or [],
           'disallowed_tools': disallowed_tools or [],
           'agents': agents,
           'hooks': hooks,
           'mcp_servers': mcp_servers or {},
           'resume': resume,
           'fork_session': fork_session,
           'permission_mode': permission_mode,
           'output_format': output_format,
           'max_thinking_tokens': max_thinking_tokens,
           'cwd': cwd,
           'setting_sources': setting_sources,
       }
       # Handle system_prompt (can be string or preset dict)
       if system_prompt:
           options_dict['system_prompt'] = system_prompt
       # Add any additional kwargs
       options_dict.update(kwargs)
       # Remove None values to use SDK defaults
       options_dict = {k: v for k, v in options_dict.items() if v is not None}
       return ClaudeAgentOptions(**options_dict)
   def create_subagent_definition(
       self,
       description: str,
       prompt: str,
       tools: Optional[List[str]] = None,
       model: str = "sonnet"
   ) -> AgentDefinition:
       """
       Create AgentDefinition for subagent delegation.
       Args:
           description: Natural language description of when to use agent
           prompt: System prompt for the subagent
           tools: List of allowed tool names (None = inherit all)
           model: Model to use ("sonnet", "opus", "haiku", "inherit")
       Returns:
           AgentDefinition instance
       References:
           - AgentDefinition structure
           - Subagent examples
       """
       return AgentDefinition(
           description=description,
           prompt=prompt,
           tools=tools,
           model=self._resolve_model(model) if model != "inherit" else model,
       )
   def create_orchestrator_options(
       self,
       orchestrator_prompt: str,
       subagents: Dict[str, AgentDefinition],
       model: str = "opus",
       max_turns: int = 50,
       allowed_tools: Optional[List[str]] = None,
       **kwargs
   ) -> ClaudeAgentOptions:
       """
       Create options for orchestrator pattern with subagents.
       Orchestrator delegates tasks to specialized subagents.
       Args:
           orchestrator_prompt: System prompt for orchestrator
           subagents: Dictionary of subagent definitions
           model: Orchestrator model (default: opus for highest intelligence)
           max_turns: Maximum orchestration turns
           allowed_tools: Tools available to orchestrator
           **kwargs: Additional options
       Returns:
           ClaudeAgentOptions configured for orchestration
       References:
           - Subagent delegation
           - Orchestration examples
       """
       if allowed_tools is None:
           allowed_tools = ["Task", "TodoWrite", "Read", "Grep", "Glob"]
       return self.create_options(
           model=model,
           system_prompt=orchestrator_prompt,
           agents=subagents,
           max_turns=max_turns,
           allowed_tools=allowed_tools,
           **kwargs
       )
   async def oneshot_query(
       self,
       prompt: str,
       options: Optional[ClaudeAgentOptions] = None,
   ) -> AsyncIterator[Any]:
       """
       Execute one-shot query using SDK query function.
       Each call creates a new session with no memory of previous interactions.
       Args:
           prompt: User prompt string
           options: Optional ClaudeAgentOptions
       Yields:
           SDK messages (AssistantMessage, ResultMessage, etc.)
       References:
           - query() function
           - One-shot pattern
       """
       async for message in query(prompt=prompt, options=options):
           yield message
   @asynccontextmanager
   async def create_session(
       self,
       session_id: str,
       options: Optional[ClaudeAgentOptions] = None,
   ) -> AsyncIterator[ClaudeSDKClient]:
       """
       Create managed multi-turn conversation session.
       Context manager ensures proper cleanup of session resources.
       Args:
           session_id: Unique session identifier
           options: Optional ClaudeAgentOptions for session configuration
       Yields:
           ClaudeSDKClient instance for multi-turn conversation
       Example:
           async with manager.create_session("session-1") as client:
               await client.query("First question")
               async for msg in client.receive_response():
                   print(msg)
               await client.query("Follow-up question")
               async for msg in client.receive_response():
                   print(msg)
       References:
           - ClaudeSDKClient context manager
           - Multi-turn conversation pattern
       """
       # Get or create async lock for this session
       if session_id not in self._session_locks:
           self._session_locks[session_id] = asyncio.Lock()
       async with self._session_locks[session_id]:
           # Create new client if doesn't exist
           if session_id not in self._session_clients:
               client = ClaudeSDKClient(options=options)
               self._session_clients[session_id] = client
               logger.info(f"Created new session client: {session_id}")
           client = self._session_clients[session_id]
           try:
               # Connect if not already connected
               if not hasattr(client, '_connected') or not client._connected:
                   await client.connect()
                   client._connected = True
               yield client
           finally:
               # Cleanup handled by close_session or close_all_sessions
               pass
   async def close_session(self, session_id: str) -> None:
       """
       Close and cleanup a session client.
       Args:
           session_id: Session identifier to close
       References:
           - ClaudeSDKClient disconnect
       """
       if session_id in self._session_clients:
           client = self._session_clients.pop(session_id)
           try:
               if hasattr(client, 'disconnect'):
                   await client.disconnect()
               logger.info(f"Closed session: {session_id}")
           except Exception as e:
               logger.error(f"Error closing session {session_id}: {e}")
           # Remove lock
           if session_id in self._session_locks:
               del self._session_locks[session_id]
   async def close_all_sessions(self) -> None:
       """Close all active session clients."""
       session_ids = list(self._session_clients.keys())
       for session_id in session_ids:
           await self.close_session(session_id)
       logger.info("Closed all sessions")
   def get_active_sessions(self) -> List[str]:
       """
       Get list of active session IDs.
       Returns:
           List of active session identifiers
       """
       return list(self._session_clients.keys())
class ConversationSession:
   """
   High-level conversation session manager.
   Maintains a single conversation session with Claude, tracking turn count
   and providing convenient interface for multi-turn interactions.
   Usage:
       session = ConversationSession(options)
       await session.start()
       # Interactive loop
       while True:
           user_input = input("You: ")
           if user_input == 'exit':
               break
           response = await session.send_message(user_input)
           print(f"Claude: {response}")
       await session.end()
   References:
       - Conversation session pattern
   """
   def __init__(self, options: Optional[ClaudeAgentOptions] = None):
       """
       Initialize conversation session.
       Args:
           options: Optional ClaudeAgentOptions for configuration
       """
       self.client = ClaudeSDKClient(options)
       self.turn_count = 0
       self.options = options
       self._connected = False
   async def start(self) -> None:
       """
       Start the conversation session.
       References:
           - ClaudeSDKClient.connect()
       """
       await self.client.connect()
       self._connected = True
       logger.info("Conversation session started")
   async def send_message(self, user_input: str) -> str:
       """
       Send message and receive response.
       Args:
           user_input: User message text
       Returns:
           Complete response text from Claude
       References:
           - ClaudeSDKClient.query()
           - receive_response() helper
       """
       if not self._connected:
           raise RuntimeError("Session not started. Call start() first.")
       await self.client.query(user_input)
       self.turn_count += 1
       response_text = []
       async for message in self.client.receive_response():
           if isinstance(message, AssistantMessage):
               for block in message.content:
                   if isinstance(block, TextBlock):
                       response_text.append(block.text)
       return ''.join(response_text)
   async def interrupt(self) -> None:
       """
       Send interrupt signal to stop current task.
       Only works in streaming mode.
       References:
           - ClaudeSDKClient.interrupt()
       """
       if not self._connected:
           raise RuntimeError("Session not started. Call start() first.")
       await self.client.interrupt()
       logger.info("Interrupt signal sent")
   async def end(self) -> None:
       """
       End the conversation session.
       References:
           - ClaudeSDKClient.disconnect()
       """
       if self._connected:
           await self.client.disconnect()
           self._connected = False
           logger.info(f"Conversation session ended after {self.turn_count} turns")
# Module-level singleton accessor
_manager: Optional[AgentClientManager] = None
_manager_lock: threading.Lock = threading.Lock()
def get_agent_client() -> AgentClientManager:
   """
   Get singleton AgentClientManager instance.
   Thread-safe singleton accessor.
   Returns:
       Shared AgentClientManager instance
   """
   global _manager
   if _manager is None:
       with _manager_lock:
           if _manager is None:
               _manager = AgentClientManager()
   return _manager
def reset_agent_client() -> None:
   """
   Reset singleton instance.
   Useful for testing and cleanup. Closes all active sessions.
   """
   global _manager
   if _manager is not None:
       with _manager_lock:
           if _manager is not None:
               # Close sessions synchronously
               loop = None
               try:
                   loop = asyncio.get_event_loop()
               except RuntimeError:
                   loop = asyncio.new_event_loop()
                   asyncio.set_event_loop(loop)
               loop.run_until_complete(_manager.close_all_sessions())
               _manager = None
               logger.info("AgentClientManager reset")
# Synchronous wrapper for oneshot query
def run_oneshot_sync(
   prompt: str,
   options: Optional[ClaudeAgentOptions] = None,
) -> List[Any]:
   """
   Synchronous wrapper for oneshot query.
   Collects all messages and returns them as a list.
   Handles event loop management for sync contexts.
   Args:
       prompt: User prompt string
       options: Optional ClaudeAgentOptions
   Returns:
       List of all messages from the response
   References:
       - query() function
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
           # Already in async context - run in thread pool
           import concurrent.futures
           with concurrent.futures.ThreadPoolExecutor() as executor:
               future = executor.submit(asyncio.run, _collect())
               return future.result()
       else:
           return loop.run_until_complete(_collect())
   except RuntimeError:
       # No event loop - create new one
       return asyncio.run(_collect())
# Advanced usage helper functions
def create_hook_matcher(
   matcher: str,
   hooks: List[Callable]
) -> Dict[str, Any]:
   """
   Create hook matcher for SDK hook system.
   Args:
       matcher: Tool name or pattern to match
       hooks: List of hook functions to invoke
   Returns:
       Hook matcher dictionary
   References:
       - Hook system
       - HookMatcher structure
   """
   return {
       'matcher': matcher,
       'hooks': hooks
   }
async def streaming_query_with_display(
   prompt: str,
   options: Optional[ClaudeAgentOptions] = None,
) -> SDKUsage:
   """
   Execute query with real-time message display.
   Streams messages to console and returns usage statistics.
   Args:
       prompt: User prompt
       options: Optional ClaudeAgentOptions
   Returns:
       SDKUsage with accumulated token counts and cost
   References:
       - Streaming examples
   """
   total_usage = SDKUsage()
   manager = get_agent_client()
   async for message in manager.oneshot_query(prompt, options):
       display_message(message)
       # Accumulate usage
       msg_usage = extract_usage_from_message(message)
       total_usage.input_tokens += msg_usage.input_tokens
       total_usage.output_tokens += msg_usage.output_tokens
       total_usage.cache_read_tokens += msg_usage.cache_read_tokens
       total_usage.cache_write_tokens += msg_usage.cache_write_tokens
       total_usage.total_cost_usd += msg_usage.total_cost_usd
   return total_usage
async def multi_turn_conversation_example():
   """
   Example of multi-turn conversation using ClaudeSDKClient.
   Demonstrates context retention across multiple queries.
   References:
       - Multi-turn pattern
       - ClaudeSDKClient usage
   """
   manager = get_agent_client()
   async with manager.create_session("example-session") as client:
       # First turn
       print("User: What's the capital of France?")
       await client.query("What's the capital of France?")
       async for message in client.receive_response():
           if isinstance(message, AssistantMessage):
               for block in message.content:
                   if isinstance(block, TextBlock):
                       print(f"Claude: {block.text}")
       # Second turn - Claude remembers context
       print("\nUser: What's the population of that city?")
       await client.query("What's the population of that city?")
       async for message in client.receive_response():
           if isinstance(message, AssistantMessage):
               for block in message.content:
                   if isinstance(block, TextBlock):
                       print(f"Claude: {block.text}")
async def orchestrator_example():
   """
   Example of orchestrator pattern with subagents.
   Demonstrates task delegation to specialized subagents.
   References:
       - Subagent delegation
       - Agent examples
   """
   manager = get_agent_client()
   # Define specialized subagents
   subagents = {
       "code-reviewer": manager.create_subagent_definition(
           description="Reviews code for best practices and potential issues",
           prompt="You are a code reviewer. Analyze code for bugs, performance issues, "
                  "security vulnerabilities, and adherence to best practices.",
           tools=["Read", "Grep"],
           model="sonnet"
       ),
       "doc-writer": manager.create_subagent_definition(
           description="Writes comprehensive documentation",
           prompt="You are a technical documentation expert. Write clear, comprehensive "
                  "documentation with examples.",
           tools=["Read", "Write", "Edit"],
           model="sonnet"
       ),
   }
   # Create orchestrator options
   options = manager.create_orchestrator_options(
       orchestrator_prompt="You are a project manager. Delegate tasks to specialized agents.",
       subagents=subagents,
       model="opus"
   )
   # Execute orchestrated task
   async for message in manager.oneshot_query(
       "Review the code in src/ and update the documentation",
       options=options
   ):
       display_message(message)
async def hook_system_example():
   """
   Example of using hooks for deterministic processing.
   Demonstrates PreToolUse hook to block dangerous commands.
   References:
       - Hook system
       - Hook examples
   """
   async def check_bash_command(input_data, tool_use_id, context):
       """Hook to validate bash commands before execution."""
       tool_name = input_data.get("tool_name")
       tool_input = input_data.get("tool_input", {})
       if tool_name != "Bash":
           return {}
       command = tool_input.get("command", "")
       dangerous_patterns = ["rm -rf", "sudo", "chmod 777"]
       for pattern in dangerous_patterns:
           if pattern in command:
               return {
                   "hookSpecificOutput": {
                       "hookEventName": "PreToolUse",
                       "permissionDecision": "deny",
                       "permissionDecisionReason": f"Command contains dangerous pattern: {pattern}",
                   }
               }
       return {}
   manager = get_agent_client()
   options = manager.create_options(
       allowed_tools=["Bash"],
       hooks={
           "PreToolUse": [
               create_hook_matcher("Bash", [check_bash_command])
           ],
       }
   )
   # Test with dangerous command
   async for message in manager.oneshot_query(
       "Run this bash command: rm -rf /",
       options=options
   ):
       display_message(message)
          # Test with dangerous command
   async for message in manager.oneshot_query(
       "Run this bash command: rm -rf /",
       options=options
   ):
       display_message(message)
async def structured_output_example():
   """
   Example of using structured output validation.
   Demonstrates JSON schema validation for agent responses.
   References:
       - OutputFormat type
       - Structured output examples
   """
   manager = get_agent_client()
   # Define JSON schema for structured output
   output_schema = {
       "type": "object",
       "properties": {
           "summary": {"type": "string"},
           "key_points": {
               "type": "array",
               "items": {"type": "string"}
           },
           "confidence": {
               "type": "number",
               "minimum": 0,
               "maximum": 1
           }
       },
       "required": ["summary", "key_points", "confidence"]
   }
   options = manager.create_options(
       model="sonnet",
       output_format={
           "type": "json_schema",
           "schema": output_schema
       }
   )
   async for message in manager.oneshot_query(
       "Analyze the current state of AI development",
       options=options
   ):
       display_message(message)
async def extended_thinking_example():
   """
   Example of using extended thinking mode.
   Demonstrates max_thinking_tokens for complex reasoning tasks.
   References:
       - Extended thinking parameter
       - ClaudeAgentOptions
   """
   manager = get_agent_client()
   options = manager.create_options(
       model="opus",
       max_thinking_tokens=10000, # Allow extended reasoning
       system_prompt="Think deeply about complex problems before answering."
   )
   async for message in manager.oneshot_query(
       "Design a distributed system architecture for a global e-commerce platform",
       options=options
   ):
       display_message(message)
async def mcp_server_example():
   """
   Example of using MCP servers for custom tools.
   Demonstrates integration with Model Context Protocol servers.
   References:
       - MCP servers configuration
       - MCP examples
   """
   manager = get_agent_client()
   # Configure MCP servers
   mcp_config = {
       "calculator": {
           "command": "python",
           "args": ["-m", "mcp_calculator_server"],
           "env": {}
       }
   }
   options = manager.create_options(
       mcp_servers=mcp_config,
       allowed_tools=["add", "subtract", "multiply", "divide"]
   )
   async for message in manager.oneshot_query(
       "Calculate (15 + 27) * 3 - 8",
       options=options
   ):
       display_message(message)
async def session_resume_example():
   """
   Example of resuming a previous session.
   Demonstrates session continuity across application restarts.
   References:
       - Session resume
       - ClaudeAgentOptions resume parameter
   """
   manager = get_agent_client()
   # First session
   print("=== Initial Session ===")
   session_id = None
   async for message in manager.oneshot_query(
       "Remember that my favorite color is blue",
       options=None
   ):
       display_message(message)
       # Extract session_id from init message if available
       if isinstance(message, SystemMessage):
           if hasattr(message, 'session_id'):
               session_id = message.session_id
   # Resume session (if session_id was captured)
   if session_id:
       print("\n=== Resumed Session ===")
       options = manager.create_options(resume=session_id)
       async for message in manager.oneshot_query(
           "What's my favorite color?",
           options=options
       ):
           display_message(message)
async def permission_mode_example():
   """
   Example of different permission modes.
   Demonstrates acceptEdits, plan, and bypassPermissions modes.
   References:
       - PermissionMode type
       - Permission modes
   """
   manager = get_agent_client()
   # Auto-accept edits mode
   options_accept = manager.create_options(
       permission_mode="acceptEdits",
       allowed_tools=["Write", "Edit"]
   )
   print("=== Auto-Accept Edits Mode ===")
   async for message in manager.oneshot_query(
       "Create a file called test.txt with 'Hello World'",
       options=options_accept
   ):
       display_message(message)
   # Plan mode - show what would be done
   options_plan = manager.create_options(
       permission_mode="plan",
       allowed_tools=["Write", "Edit"]
   )
   print("\n=== Plan Mode ===")
   async for message in manager.oneshot_query(
       "Create a file called test.txt with 'Hello World'",
       options=options_plan
   ):
       display_message(message)
async def setting_sources_example():
   """
   Example of loading filesystem settings.
   Demonstrates user, project, and local setting sources.
   References:
       - SettingSource type
       - Setting sources behavior
   """
   manager = get_agent_client()
   # Load all settings (user, project, local)
   options_all = manager.create_options(
       setting_sources=["user", "project", "local"]
   )
   # Load only project settings (for CI/testing)
   options_project = manager.create_options(
       setting_sources=["project"]
   )
   # No settings (default - isolated SDK application)
   options_none = manager.create_options()
   print("Settings sources configured:")
   print(f" All settings: {options_all.setting_sources}")
   print(f" Project only: {options_project.setting_sources}")
   print(f" None (default): {options_none.setting_sources}")
async def fork_session_example():
   """
   Example of forking a session.
   Demonstrates creating a new branch from an existing session.
   References:
       - fork_session parameter
       - Session forking
   """
   manager = get_agent_client()
   # Original session
   print("=== Original Session ===")
   session_id = "original-session"
   async with manager.create_session(session_id) as client:
       await client.query("Let's discuss Python programming")
       async for message in client.receive_response():
           display_message(message)
   # Fork the session to explore different path
   print("\n=== Forked Session ===")
   options_fork = manager.create_options(
       resume=session_id,
       fork_session=True # Create new session ID instead of continuing
   )
   async for message in manager.oneshot_query(
       "Now let's talk about JavaScript instead",
       options=options_fork
   ):
       display_message(message)
async def tool_permission_callback_example():
   """
   Example of using can_use_tool callback for dynamic permissions.
   Demonstrates runtime permission control.
   References:
       - can_use_tool callback
       - CanUseTool type
       - Permission examples
   """
   from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny
   async def permission_callback(tool_name: str, input_data: dict, context):
       """Dynamic permission control for tool usage."""
       # Always allow read operations
       if tool_name in ["Read", "Glob", "Grep"]:
           return PermissionResultAllow()
       # Block writes to system directories
       if tool_name in ["Write", "Edit"]:
           file_path = input_data.get("file_path", "")
           if file_path.startswith("/etc/") or file_path.startswith("/usr/"):
               return PermissionResultDeny(
                   message=f"Cannot write to system directory: {file_path}"
               )
           # Redirect to safe directory
           if not file_path.startswith("./safe/"):
               safe_path = f"./safe/{file_path.split('/')[-1]}"
               modified_input = input_data.copy()
               modified_input["file_path"] = safe_path
               return PermissionResultAllow(updated_input=modified_input)
       return PermissionResultAllow()
   manager = get_agent_client()
   # Note: can_use_tool is passed to ClaudeAgentOptions
   # This requires SDK support for the parameter
   options = ClaudeAgentOptions(
       allowed_tools=["Read", "Write", "Edit"],
       # can_use_tool=permission_callback # If supported by SDK
   )
async def include_partial_messages_example():
   """
   Example of streaming partial messages.
   Demonstrates real-time streaming of message generation.
   References:
       - include_partial_messages option
       - Streaming examples
   """
   manager = get_agent_client()
   options = manager.create_options(
       include_partial_messages=True # Stream partial updates
   )
   print("Streaming partial messages:")
   async for message in manager.oneshot_query(
       "Write a detailed explanation of quantum computing",
       options=options
   ):
       # Partial messages will be streamed as they're generated
       if isinstance(message, AssistantMessage):
           for block in message.content:
               if isinstance(block, TextBlock):
                   print(block.text, end='', flush=True)
async def comprehensive_usage_tracking():
   """
   Comprehensive example of usage tracking across multiple queries.
   Demonstrates cost calculation and token tracking.
   References:
       - Usage extraction
       - ResultMessage cost field
   """
   manager = get_agent_client()
   total_usage = SDKUsage()
   queries = [
       "Explain machine learning",
       "What are neural networks?",
       "Describe deep learning"
   ]
   for query in queries:
       print(f"\n=== Query: {query} ===")
       async for message in manager.oneshot_query(query):
           display_message(message)
           # Track usage
           msg_usage = extract_usage_from_message(message)
           total_usage.input_tokens += msg_usage.input_tokens
           total_usage.output_tokens += msg_usage.output_tokens
           total_usage.cache_read_tokens += msg_usage.cache_read_tokens
           total_usage.cache_write_tokens += msg_usage.cache_write_tokens
           total_usage.total_cost_usd += msg_usage.total_cost_usd
   print("\n=== Total Usage ===")
   print(f"Input tokens: {total_usage.input_tokens}")
   print(f"Output tokens: {total_usage.output_tokens}")
   print(f"Cache read tokens: {total_usage.cache_read_tokens}")
   print(f"Cache write tokens: {total_usage.cache_write_tokens}")
   print(f"Total cost: ${total_usage.total_cost_usd:.4f}")
async def interrupt_example():
   """
   Example of interrupting long-running tasks.
   Demonstrates interrupt functionality in streaming mode.
   References:
       - ClaudeSDKClient.interrupt()
       - Interrupt support
   """
   manager = get_agent_client()
   async with manager.create_session("interrupt-demo") as client:
       # Start long-running task
       await client.query("Generate 1000 lines of code")
       # Simulate interrupt after short delay
       async def interrupt_after_delay():
           await asyncio.sleep(2)
           await client.interrupt()
           print("\n[Interrupted!]")
       # Run interrupt task concurrently
       interrupt_task = asyncio.create_task(interrupt_after_delay())
       try:
           async for message in client.receive_response():
               display_message(message)
       except Exception as e:
           logger.error(f"Interrupted: {e}")
       await interrupt_task
# Main execution examples
async def main():
   """
   Main function demonstrating various SDK patterns.
   Run individual examples to see different features in action.
   """
   print("Claude Agent SDK - Production Implementation Examples\n")
   print("=" * 60)
   # Uncomment to run specific examples:
   # await multi_turn_conversation_example()
   # await orchestrator_example()
   # await hook_system_example()
   # await structured_output_example()
   # await extended_thinking_example()
   # await mcp_server_example()
   # await session_resume_example()
   # await permission_mode_example()
   # await setting_sources_example()
   # await fork_session_example()
   # await include_partial_messages_example()
   # await comprehensive_usage_tracking()
   # await interrupt_example()
   print("\nExamples complete!")
if __name__ == "__main__":
   """
   Entry point for running examples.
   Usage:
       python agent_client.py
   """
   try:
       asyncio.run(main())
   except KeyboardInterrupt:
       print("\n\nInterrupted by user")
   finally:
       reset_agent_client()
# ============================================================================
# REFERENCE LINKS
# ============================================================================
#
# This implementation is based on the official Claude Agent SDK documentation
# and examples. All code patterns follow documented SDK behavior.
#
# Primary References:
# : https://platform.claude.com/docs/en/agent-sdk/python#classes
# - ClaudeSDKClient class and methods
# - Message types (AssistantMessage, ResultMessage, etc.)
# - Session management with connect(), disconnect(), query()
#
# [(5)](https://platform.claude.com/docs/en/agent-sdk/python#example-usage): https://platform.claude.com/docs/en/agent-sdk/python#example-usage
# - Basic usage patterns
# - File operations examples
# - Error handling patterns
#
# [(6)](https://platform.claude.com/docs/en/agent-sdk/python): https://platform.claude.com/docs/en/agent-sdk/python
# - SDK overview and installation
# - Choosing between query() and ClaudeSDKClient
#
# [(7)](https://platform.claude.com/docs/en/agent-sdk/python#functions): https://platform.claude.com/docs/en/agent-sdk/python#functions
# - query() function signature and usage
# - tool() decorator for custom tools
# - create_sdk_mcp_server() for MCP integration
#
# : https://platform.claude.com/docs/en/agent-sdk/python#advanced-features-with-claude-sdk-client
# - Multi-turn conversation patterns
# - Session lifecycle management
# - Interrupt functionality
#
# : https://platform.claude.com/docs/en/agent-sdk/python#types
# - ClaudeAgentOptions complete specification
# - AgentDefinition for subagents
# - SettingSource types
# - OutputFormat for structured output
# - All type definitions
#
# [(8)](https://platform.claude.com/docs/en/agent-sdk/migration-guide#breaking-changes): https://platform.claude.com/docs/en/agent-sdk/migration-guide#breaking-changes
# - Migration from claude-code-sdk to claude-agent-sdk
# - Breaking changes in v0.1.0
# - System prompt changes
#
# [(9)](https://platform.claude.com/docs/en/agent-sdk/typescript#types): https://platform.claude.com/docs/en/agent-sdk/typescript#types
# - TypeScript SDK reference (for comparison)
#
# [(10)](https://platform.claude.com/docs/en/agent-sdk/migration-guide): https://platform.claude.com/docs/en/agent-sdk/migration-guide
# - Complete migration guide
# - Package name changes
#
# : https://github.com/anthropics/claude-agent
