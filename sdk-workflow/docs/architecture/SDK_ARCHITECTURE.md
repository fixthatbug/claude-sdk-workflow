# SDK Architecture: Unified Claude Agent SDK Integration
## Overview
The sdk-workflow system supports **both** legacy Anthropic SDK and modern Claude Agent SDK, with automatic fallback when Agent SDK is unavailable.
## SDK Mode Detection
All executors use this pattern:
```python
USE_AGENT_SDK = False
try:
    from core.agent_client import get_agent_client, ...
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    USE_AGENT_SDK = True
except ImportError:
    USE_AGENT_SDK = False
    from core.client import get_client
```
**Critical**: `USE_AGENT_SDK` MUST be `False` before try block to correctly capture import failures.
## Executor SDK Usage
### oneshot.py - Single Request Execution
**Agent SDK Mode** (Primary):
- Uses `query()` function from claude_agent_sdk
- Pattern: `async for msg in query(prompt, options):`
- Synchronous wrapper: `run_oneshot_sync(prompt, options)`
- Returns list of `AssistantMessage` objects
**Legacy SDK Mode** (Fallback):
- Uses `client.messages.create(**kwargs)`
- Direct single request/response
**Flow**:
```
setup() → get_agent_client() or get_client()
   ↓
execute() → _execute_with_model()
   ↓
   ├─ USE_AGENT_SDK=True → _execute_with_agent_sdk()
   │   └─ run_oneshot_sync(query())
   │
   └─ USE_AGENT_SDK=False → _execute_with_legacy_client()
       └─ client.messages.create()
```
### streaming.py - Real-time Streaming Execution
**Agent SDK Mode** (Primary):
- Uses `ClaudeSDKClient` for bidirectional streaming
- Pattern:
  ```python
  async with ClaudeSDKClient(options) as client:
      await client.query(task)
      async for message in client.receive_response():
          process(message)
  ```
- Real-time text and tool callbacks
- Async executed in sync context via `asyncio.run()` or `ThreadPoolExecutor`
**Legacy SDK Mode** (Fallback):
- Uses `client.messages.stream(**kwargs)` context manager
- Pattern:
  ```python
  with client.messages.stream(**kwargs) as stream:
      for event in stream:
          handle_event(event)
  ```
**Flow**:
```
setup() → get_agent_client() or get_client()
   ↓
execute() → model_config.resolve_model()
   ↓
   ├─ USE_AGENT_SDK=True → _execute_with_agent_sdk()
   │   └─ async with ClaudeSDKClient() → receive_response()
   │
   └─ USE_AGENT_SDK=False → _execute_with_legacy_client()
       └─ with client.messages.stream() → _process_stream()
```
## agent_client.py - Adapter Layer
### Core Components
**AgentClientManager** (Singleton):
- Thread-safe singleton for SDK client management
- Creates `ClaudeAgentOptions` from config
- Manages session clients for multi-turn conversations
- Provides sync wrappers for async SDK functions
### Key Functions
**create_options()**:
```python
def create_options(
    model: str,
    system_prompt: str,
    max_tokens: int = 8192,
    tools: List[Callable] = None,
    max_turns: int = 1,
) -> ClaudeAgentOptions
```
Returns properly configured `ClaudeAgentOptions` for SDK usage.
**run_oneshot_sync()**:
```python
def run_oneshot_sync(
    prompt: str,
    options: ClaudeAgentOptions,
) -> List[AssistantMessage]
```
Synchronous wrapper that collects async query results. Handles event loop management:
- If loop running → use ThreadPoolExecutor
- If loop exists but not running → run_until_complete
- No loop → asyncio.run()
### Extraction Utilities
**extract_text_from_message(message: AssistantMessage)**:
- Extracts text from TextBlock content
- Returns concatenated string
**extract_tool_uses_from_message(message: AssistantMessage)**:
- Extracts tool use blocks
- Returns list of dicts: `[{id, name, input}, ...]`
**extract_usage_from_message(message: AssistantMessage)**:
- Extracts token usage from message
- Returns `SDKUsage` dataclass
**sdk_usage_to_token_usage(sdk_usage: SDKUsage)**:
- Converts SDK usage to internal `TokenUsage` type
- Maps cache fields correctly
## SDK Comparison
| Feature | Legacy SDK | Agent SDK |
|---------|-----------|-----------|
| Import | `anthropic.Anthropic` | `claude_agent_sdk` |
| One-shot | `client.messages.create()` | `query()` async generator |
| Streaming | `client.messages.stream()` context manager | `ClaudeSDKClient` async context |
| Response | Single `Message` object | Stream of `AssistantMessage` |
| Tools | Dict format in kwargs | `@tool` decorated functions |
| Multi-turn | Manual message list management | Built-in via `max_turns` |
| Async | Synchronous | Fully async (bridged to sync) |
## Migration Path
### Current State
- **oneshot.py**: Agent SDK integrated, legacy fallback functional
- **streaming.py**: Agent SDK integrated, legacy fallback functional
- **agent_client.py**: Complete adapter layer with utilities
### Agent SDK Benefits
1. **Simplified API**: `query()` vs manual message construction
2. **Built-in streaming**: `receive_response()` async iterator
3. **Tool integration**: `@tool` decorator pattern
4. **Multi-turn**: Managed conversation state
5. **Type safety**: Proper message types
### Legacy SDK Use Cases
- Environments without Agent SDK installed
- Testing/development isolation
- Gradual migration periods
- Compatibility requirements
## Configuration Integration
Both modes use same config resolution:
```python
model_config = self.config.resolve_model(model_alias)
# Returns ModelConfig with:
#   - model_id: Full model identifier
#   - max_tokens: Token limit
#   - aliases: Alternative names
```
Agent SDK options are created via:
```python
options = agent_client.create_options(
    model=model_config.model_id,
    system_prompt=system_prompt,
    max_turns=1,
)
```
## Error Handling
Both modes use same error patterns:
- Import failures → fallback to legacy
- Runtime errors → propagate to executor base class
- Usage extraction failures → return empty TokenUsage
- Event loop conflicts → ThreadPoolExecutor bridge
## Testing Strategy
Test both modes:
```python
# Force legacy mode
with mock.patch('executors.oneshot.USE_AGENT_SDK', False):
    executor = OneshotExecutor()
    result = executor.execute("task")
# Force agent SDK mode
with mock.patch('executors.oneshot.USE_AGENT_SDK', True):
    executor = OneshotExecutor()
    result = executor.execute("task")
```
## Future Enhancements
When Agent SDK fully stable:
1. Remove legacy client code paths
2. Simplify executor logic (single code path)
3. Add native tool support (@tool decorators)
4. Leverage advanced SDK features (sessions, checkpointing)
5. Remove sync wrappers (make executors async)
## Summary
The unified architecture provides:
- **Flexibility**: Works with or without Agent SDK
- **Consistency**: Same interface for both modes
- **Performance**: Agent SDK when available, legacy fallback
- **Maintainability**: Clear separation via adapter layer
- **Future-proof**: Easy to deprecate legacy when ready
