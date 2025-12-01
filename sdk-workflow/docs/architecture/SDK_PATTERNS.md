# Claude Agent SDK Usage Patterns
## Reference Guide for Agent SDK Integration
### Pattern 1: SDK Detection (Use in ALL executors)
```python
# At top of executor file, after imports
USE_AGENT_SDK = False
try:
    from core.agent_client import (
        get_agent_client,
        run_oneshot_sync,
        extract_text_from_message,
        extract_tool_uses_from_message,
        sdk_usage_to_token_usage,
        extract_usage_from_message,
    )
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage
    USE_AGENT_SDK = True
except ImportError:
    USE_AGENT_SDK = False
    from core.client import get_client
```
**Critical**: Must initialize `USE_AGENT_SDK = False` BEFORE try block.
### Pattern 2: Dual Client Setup
```python
def setup(self) -> None:
    """Initialize client (Agent SDK or legacy)."""
    if USE_AGENT_SDK:
        self._agent_client = get_agent_client()
        self._client = None
    else:
        self._client = get_client()
        self._agent_client = None
```
### Pattern 3: One-Shot Query (Sync Executor)
```python
def _execute_with_agent_sdk(self, task: str, system_prompt: str, model_config) -> ExecutionResult:
    """Execute using Claude Agent SDK."""
    # 1. Create options
    options = self._agent_client.create_options(
        model=model_config.model_id,
        system_prompt=system_prompt,
        max_turns=1,
    )
    # 2. Run query synchronously
    messages = run_oneshot_sync(prompt=task, options=options)
    # 3. Extract from messages
    content = ""
    tool_uses = []
    usage = TokenUsage()
    stop_reason = None
    for message in messages:
        if isinstance(message, AssistantMessage):
            content += extract_text_from_message(message)
            tool_uses.extend(extract_tool_uses_from_message(message))
            sdk_usage = extract_usage_from_message(message)
            usage = sdk_usage_to_token_usage(sdk_usage)
            stop_reason = getattr(message, 'stop_reason', None)
    # 4. Calculate cost
    cost = self._calculate_cost(usage, model_config.model_id)
    # 5. Return result
    return ExecutionResult(
        content=content,
        usage=usage,
        cost=cost,
        model=model_config.model_id,
        mode=ExecutionMode.ONESHOT,
        stop_reason=stop_reason,
        tool_uses=tool_uses,
        duration_ms=self._get_duration_ms(),
    )
```
### Pattern 4: Bidirectional Streaming (Sync Executor)
```python
def _execute_with_agent_sdk(self, task: str, system_prompt: str, model_config) -> ExecutionResult:
    """Execute streaming using Claude Agent SDK."""
    # 1. Create options
    options = self._agent_client.create_options(
        model=model_config.model_id,
        system_prompt=system_prompt,
        max_turns=1,
    )
    # 2. Define async streaming function
    async def _stream():
        async with ClaudeSDKClient(options) as client:
            # Send query
            await client.query(task)
            # Receive responses
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    # Extract and emit text
                    text = extract_text_from_message(message)
                    if text:
                        self._accumulated_text += text
                        self._on_text(text)  # Real-time callback
                    # Extract tool uses
                    tools = extract_tool_uses_from_message(message)
                    for tool in tools:
                        self._tool_uses.append(tool)
                        self._on_tool_use(tool)  # Real-time callback
            # Return final message for usage
            return message if isinstance(message, AssistantMessage) else None
    # 3. Run async in sync context
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Event loop already running, use thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _stream())
                final_message = future.result()
        else:
            # Event loop exists but not running
            final_message = loop.run_until_complete(_stream())
    except RuntimeError:
        # No event loop, create new one
        final_message = asyncio.run(_stream())
    # 4. Extract usage from final message
    if final_message:
        sdk_usage = extract_usage_from_message(final_message)
        usage = sdk_usage_to_token_usage(sdk_usage)
        stop_reason = getattr(final_message, 'stop_reason', None)
    else:
        usage = TokenUsage()
        stop_reason = None
    # 5. Calculate cost
    cost = self._calculate_cost(usage, model_config.model_id)
    # 6. Return result
    return ExecutionResult(
        content=self._accumulated_text,
        usage=usage,
        cost=cost,
        model=model_config.model_id,
        mode=ExecutionMode.STREAMING,
        stop_reason=stop_reason,
        tool_uses=self._tool_uses,
        duration_ms=self._get_duration_ms(),
    )
```
### Pattern 5: Native Async Executor (Future)
```python
async def _execute_with_agent_sdk(self, task: str, system_prompt: str, model_config) -> ExecutionResult:
    """Execute using Claude Agent SDK (native async)."""
    options = self._agent_client.create_options(
        model=model_config.model_id,
        system_prompt=system_prompt,
        max_turns=1,
    )
    async with ClaudeSDKClient(options) as client:
        await client.query(task)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                text = extract_text_from_message(message)
                self._accumulated_text += text
                await self._on_text(text)  # Async callback
                tools = extract_tool_uses_from_message(message)
                for tool in tools:
                    await self._on_tool_use(tool)  # Async callback
    # Extract usage and return
    sdk_usage = extract_usage_from_message(message)
    usage = sdk_usage_to_token_usage(sdk_usage)
    cost = self._calculate_cost(usage, model_config.model_id)
    return ExecutionResult(
        content=self._accumulated_text,
        usage=usage,
        cost=cost,
        model=model_config.model_id,
        mode=ExecutionMode.STREAMING,
        stop_reason=getattr(message, 'stop_reason', None),
        tool_uses=self._tool_uses,
        duration_ms=self._get_duration_ms(),
    )
```
### Pattern 6: Creating Options
```python
# Minimal options
options = agent_client.create_options(
    model="claude-sonnet-4-20250514",
    system_prompt="You are a helpful assistant.",
    max_turns=1,
)
# With tools (future)
from claude_agent_sdk import tool
@tool
def search_codebase(query: str) -> List[str]:
    """Search codebase for query."""
    return grep(query)
options = agent_client.create_options(
    model="claude-sonnet-4-20250514",
    system_prompt="You are a code analysis expert.",
    max_turns=5,
    tools=[search_codebase],
)
# With all parameters
options = agent_client.create_options(
    model=model_config.model_id,
    system_prompt=system_prompt,
    max_tokens=8192,
    tools=None,
    max_turns=1,
)
```
### Pattern 7: Extraction Utilities
```python
# Extract text
text = extract_text_from_message(message)
# Returns: "Here is the response text..."
# Extract tool uses
tools = extract_tool_uses_from_message(message)
# Returns: [
#     {"id": "tool_123", "name": "search_codebase", "input": {"query": "auth"}},
#     {"id": "tool_124", "name": "read_file", "input": {"path": "auth.py"}}
# ]
# Extract usage
sdk_usage = extract_usage_from_message(message)
# Returns: SDKUsage(input_tokens=100, output_tokens=50, ...)
# Convert to internal type
usage = sdk_usage_to_token_usage(sdk_usage)
# Returns: TokenUsage(input_tokens=100, output_tokens=50, ...)
```
### Pattern 8: Cleanup
```python
def cleanup(self) -> None:
    """Release resources."""
    self._client = None
    self._agent_client = None
    # ... other cleanup
```
## Complete Executor Template
```python
from typing import Optional
from .base import BaseExecutor
from core.config import Config
from core.types import ExecutionResult, ExecutionMode, TokenUsage
# SDK Detection
USE_AGENT_SDK = False
try:
    from core.agent_client import (
        get_agent_client,
        run_oneshot_sync,
        extract_text_from_message,
        extract_tool_uses_from_message,
        sdk_usage_to_token_usage,
        extract_usage_from_message,
    )
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage
    USE_AGENT_SDK = True
except ImportError:
    USE_AGENT_SDK = False
    from core.client import get_client
class MyExecutor(BaseExecutor):
    def __init__(self, config: Optional[Config] = None):
        super().__init__(config)
        self._client = None
        self._agent_client = None
    def setup(self) -> None:
        """Initialize client."""
        if USE_AGENT_SDK:
            self._agent_client = get_agent_client()
            self._client = None
        else:
            self._client = get_client()
            self._agent_client = None
    def execute(self, task: str, system_prompt: str = "") -> ExecutionResult:
        """Execute task."""
        self._start_timer()
        model_config = self.config.resolve_model(self._model)
        if USE_AGENT_SDK:
            return self._execute_with_agent_sdk(task, system_prompt, model_config)
        else:
            return self._execute_with_legacy_client(task, system_prompt, model_config)
    def _execute_with_agent_sdk(self, task, system_prompt, model_config):
        """Execute using Agent SDK."""
        options = self._agent_client.create_options(
            model=model_config.model_id,
            system_prompt=system_prompt,
            max_turns=1,
        )
        messages = run_oneshot_sync(prompt=task, options=options)
        content = ""
        usage = TokenUsage()
        for message in messages:
            if isinstance(message, AssistantMessage):
                content += extract_text_from_message(message)
                sdk_usage = extract_usage_from_message(message)
                usage = sdk_usage_to_token_usage(sdk_usage)
        cost = self._calculate_cost(usage, model_config.model_id)
        return ExecutionResult(
            content=content,
            usage=usage,
            cost=cost,
            model=model_config.model_id,
            mode=ExecutionMode.ONESHOT,
            duration_ms=self._get_duration_ms(),
        )
    def _execute_with_legacy_client(self, task, system_prompt, model_config):
        """Execute using legacy SDK."""
        # Legacy implementation
        pass
    def cleanup(self) -> None:
        """Release resources."""
        self._client = None
        self._agent_client = None
```
## Common Pitfalls
### Wrong: Setting USE_AGENT_SDK=True before try
```python
USE_AGENT_SDK = True  #  Will stay True even if import fails!
try:
    from claude_agent_sdk import ...
except ImportError:
    from core.client import get_client
```
### Correct: Setting USE_AGENT_SDK=False before try
```python
USE_AGENT_SDK = False  #  Correct default
try:
    from claude_agent_sdk import ...
    USE_AGENT_SDK = True  #  Only True on success
except ImportError:
    from core.client import get_client
```
### Wrong: Using query() in sync context without wrapper
```python
# This won't work - query() is async generator
messages = query(prompt=task, options=options)  #  SyntaxError
```
### Correct: Using sync wrapper
```python
messages = run_oneshot_sync(prompt=task, options=options)  #
```
### Wrong: Not checking message type
```python
for message in messages:
    text = extract_text_from_message(message)  #  May fail on non-Assistant messages
```
### Correct: Type checking
```python
for message in messages:
    if isinstance(message, AssistantMessage):
        text = extract_text_from_message(message)  #
```
## Testing Patterns
```python
import pytest
from unittest.mock import patch, MagicMock
def test_agent_sdk_mode():
    """Test executor with Agent SDK."""
    from executors.myexecutor import MyExecutor, USE_AGENT_SDK
    if not USE_AGENT_SDK:
        pytest.skip("Agent SDK not available")
    executor = MyExecutor()
    result = executor.execute("Test task")
    assert result.content
    assert result.usage.input_tokens > 0
def test_legacy_mode():
    """Test executor with legacy SDK."""
    with patch('executors.myexecutor.USE_AGENT_SDK', False):
        executor = MyExecutor()
        result = executor.execute("Test task")
        assert result.content
        assert result.usage.input_tokens > 0
def test_fallback_on_import_error():
    """Test that import error triggers fallback."""
    import sys
    # Remove SDK from modules
    original = sys.modules.pop('claude_agent_sdk', None)
    try:
        # Re-import executor
        import importlib
        from executors import myexecutor
        importlib.reload(myexecutor)
        assert not myexecutor.USE_AGENT_SDK
    finally:
        # Restore
        if original:
            sys.modules['claude_agent_sdk'] = original
```
## Summary
Key patterns to remember:
1. **Always** initialize `USE_AGENT_SDK = False` before try block
2. **Always** use `run_oneshot_sync()` for sync executors
3. **Always** check `isinstance(message, AssistantMessage)` before extraction
4. **Always** handle async/sync bridge with ThreadPoolExecutor fallback
5. **Always** set both `_client` and `_agent_client` to None in cleanup
