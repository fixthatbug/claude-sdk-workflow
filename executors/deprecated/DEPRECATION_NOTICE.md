# Deprecation Notice - Oneshot Executor Modules
## Summary
The following modules have been **deprecated** and consolidated into `streaming_orchestrator.py`:
- `oneshot.py` → Consolidated into `streaming_orchestrator.py`
- `oneshot_orchestrator.py` → Already deprecated, archived
- `oneshot_example.py` → Examples moved to documentation, archived
## Migration Date
Date: 2024-12-19
## Reason for Consolidation
1. **Reduce Module Fragmentation**: Having multiple oneshot-related modules made the codebase harder to navigate
2. **Improve Maintainability**: Centralizing executor logic in fewer files
3. **Preserve All Functionality**: All features have been fully preserved
4. **Better Organization**: Streaming orchestrator is the natural home for all execution modes
## What Was Consolidated
### From `oneshot.py`:
- `OneshotExecutor` class with full auto-escalation logic
- Model routing (Haiku → Sonnet escalation)
- Quality checks and escalation markers
- Token accumulation across attempts
- Cost tracking and breakdown
- Claude Agent SDK integration
- Error handling (CLINotFoundError, ProcessError, etc.)
### From `oneshot_orchestrator.py`:
- Already deprecated (see module docstring)
- Archived for reference only
### From `oneshot_example.py`:
- Advanced usage patterns documented
- Examples moved to documentation
- Archived for reference
## Migration Guide
### For Developers
**Before (Deprecated):**
```python
from sdk_workflow.executors.oneshot import OneshotExecutor
executor = OneshotExecutor(config=config, model="haiku")
result = executor.execute(task="Your task", system_prompt="...")
```
**After (Recommended):**
```python
from sdk_workflow.executors import OneshotExecutor
executor = OneshotExecutor(config=config, model="haiku")
result = executor.execute(task="Your task", system_prompt="...")
```
**OR directly from consolidated module:**
```python
from sdk_workflow.executors.streaming_orchestrator import OneshotExecutor
executor = OneshotExecutor(config=config, model="haiku")
result = executor.execute(task="Your task", system_prompt="...")
```
### No Breaking Changes
- **Imports through `executors` package still work** - The `__init__.py` has been updated to import from the consolidated module
- **All method signatures preserved** - No API changes
- **All functionality intact** - Auto-escalation, model routing, token tracking all work identically
### Compatibility Shim
The deprecated `oneshot.py` file now contains a compatibility shim that:
1. Issues a deprecation warning
2. Automatically redirects to the consolidated module
3. Delegates all method calls transparently
This ensures existing code continues to work while encouraging migration.
## Archive Location
Deprecated modules archived at:
```
sdk_workflow/executors/deprecated/v1.0-archived-{date}/
├── oneshot.py.deprecated
├── oneshot_orchestrator.py.deprecated
├── oneshot_example.py.deprecated
└── DEPRECATION_NOTICE.md (this file)
```
## Consolidated Module
All functionality now available in:
```
sdk_workflow/executors/streaming_orchestrator.py
```
This module now contains:
- **OneshotExecutor**: Single-shot execution with auto-escalation
- **StreamingOrchestrator**: Phase-by-phase workflow execution
- All supporting utilities and helpers
## Timeline
- **Now**: Deprecation warnings issued, compatibility shim active
- **Next Minor Release**: Warnings continue
- **Next Major Release**: Deprecated files may be removed
## Questions or Issues?
If you encounter any issues during migration:
1. Check that imports are updated to use `executors` package
2. Verify all functionality works identically
3. Review this deprecation notice for guidance
4. Contact the maintainers if problems persist
## Verification
To verify successful consolidation:
```bash
# All imports should resolve correctly
python -c "from sdk_workflow.executors import OneshotExecutor; print(' Import successful')"
# Functionality should work identically
python -c "from sdk_workflow.executors import OneshotExecutor; e = OneshotExecutor(); e.setup(); print(' Functionality intact')"
```
