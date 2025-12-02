# SDK Execution Core

Refactored execution module with standardized lifecycle management and SDK integration.

## Files

| File | LOC | Purpose |
|------|-----|---------|
| `base_executor.py` | 285 | Abstract base class with lifecycle management |
| `execution_result.py` | 220 | Result dataclass with bounded message storage |
| `executor_helpers.py` | 135 | MCP config, SDK validation, plugin discovery |
| `userscope_executor.py` | 340 | Main SDK executor (extends BaseExecutor) |
| `simulated_executor.py` | 110 | Testing executor (no SDK required) |
| `__init__.py` | 45 | Lazy-loading module exports |

**Total: ~1,135 LOC** (vs original ~1,500 LOC = **24% reduction**)

## Changes from Original

### ❌ Deleted (Duplicate)
- `streaming_engine.py` - Replaced by project `/mnt/project/streaming.py`

### ✅ Integrated
- `BaseExecutor` - New abstract base with lifecycle: `setup() → _execute() → cleanup()`
- `ExecutorConfig` - Memory-efficient config with `__slots__`
- `ExecutionMetrics` - Separate from `ExecutionResult` for reuse
- `CostTracker` - Inlined to avoid external dependency

### ⚠️ Refactored
- `UserscopeExecutor` - Now extends `BaseExecutor`
- Imports fixed (removed broken `agents.` paths)
- Uses project streaming module via `StreamingDecisionEngine`

## Usage

```python
from core import UserscopeExecutor, ExecutionResult

# Streaming execution
executor = UserscopeExecutor(cwd="/project")
async for message in executor.run("dev-feature", "implement auth"):
    print(message)

# Execute with result
result = await executor.execute("dev-bugfix", "fix login")
print(f"Status: {result.status}, Cost: ${result.cost['total_cost_usd']:.4f}")

# Auto-select agent
result = await executor.execute_auto("add dark mode feature")

# Simulated mode (no SDK)
from core import SimulatedExecutor
sim = SimulatedExecutor()
result = await sim.execute("test", "demo task")
```

## Integration with Project

These files replace the uploaded executor module. Use with existing:
- `/mnt/project/streaming.py` - StreamingHandler, StreamingDecisionEngine
- `/mnt/project/session.py` - Session management
- `/mnt/project/workflow.py` - BatchProcessor, WorkflowResult
