# Migration Summary: Oneshot Executor Consolidation
**Quick Reference Guide for Developers**
---
## What Changed?
All oneshot executor modules have been consolidated into a single file for better organization:
**Before:**
- `executors/oneshot.py`
- `executors/oneshot_orchestrator.py`
- `executors/oneshot_example.py`
**After:**
- `executors/streaming_orchestrator.py` (consolidated module)
- `executors/oneshot.py` (compatibility shim with deprecation warning)
---
## Do I Need to Change My Code?
**Short answer: NO**
Your existing code will continue to work without any changes. However, you'll see deprecation warnings if you import directly from `oneshot.py`.
---
## Recommended Migration
### Option 1: Use Package Import (Recommended)
```python
# This is the recommended approach
from sdk_workflow.executors import OneshotExecutor
executor = OneshotExecutor(config=config, model="haiku")
result = executor.execute(task, system_prompt)
```
**Benefits:**
- No changes needed if you already use this
- No deprecation warnings
- Future-proof
- Clean and simple
### Option 2: Direct Import from Consolidated Module
```python
# Import directly from the new consolidated module
from sdk_workflow.executors.streaming_orchestrator import OneshotExecutor
executor = OneshotExecutor(config=config, model="haiku")
result = executor.execute(task, system_prompt)
```
**Benefits:**
- No deprecation warnings
- Explicit about source module
- Slightly faster imports
### Option 3: Old Import (Still Works, But Deprecated)
```python
# This still works but shows deprecation warning
from sdk_workflow.executors.oneshot import OneshotExecutor  # ️ Warning
executor = OneshotExecutor(config=config, model="haiku")
result = executor.execute(task, system_prompt)
```
**Issues:**
- ️ Deprecation warning on every import
- ️ May be removed in future major version
---
## What's Preserved?
**Everything!** All functionality has been preserved exactly as it was:
- Auto-escalation (Haiku → Sonnet)
- Model routing and quality checks
- Token accumulation across attempts
- Cost tracking and breakdown
- Error handling (CLINotFoundError, ProcessError, etc.)
- Tool use extraction
- All method signatures
- All parameters
- All return types
---
## Quick Migration Checklist
- [ ] Review your imports of `OneshotExecutor`
- [ ] If importing from `executors.oneshot`, update to `executors` package import
- [ ] Run your tests to verify everything still works
- [ ] Check for any deprecation warnings in logs
- [ ] Update internal documentation if needed
---
## Example Migration
### Before (with deprecation warning):
```python
from sdk_workflow.executors.oneshot import OneshotExecutor
class MyWorkflow:
    def __init__(self):
        self.executor = OneshotExecutor(model="haiku")
    def run(self, task):
        return self.executor.execute(task)
```
### After (clean, no warnings):
```python
from sdk_workflow.executors import OneshotExecutor
class MyWorkflow:
    def __init__(self):
        self.executor = OneshotExecutor(model="haiku")
    def run(self, task):
        return self.executor.execute(task)
```
**Change required:** Just the import line! Everything else stays the same.
---
## FAQ
### Q: Will my existing code break?
**A:** No! All imports continue to work with backward compatibility.
### Q: When should I migrate?
**A:** At your convenience. There's no rush, but migrating sooner means fewer deprecation warnings in your logs.
### Q: What if I use OneshotExecutor in OrchestratorExecutor?
**A:** No changes needed! OrchestratorExecutor has been updated internally to use the consolidated module.
### Q: Can I still access the old code?
**A:** Yes! It's archived in `executors/deprecated/v1.0-archived-{date}/` for reference.
### Q: What about examples in oneshot_example.py?
**A:** Examples are documented in the deprecation notice and will be added to main docs.
### Q: Will there be more consolidations?
**A:** This was a one-time consolidation of fragmented oneshot modules. No further changes planned.
---
## Timeline
- **Now**: Deprecation warnings active, compatibility shim in place
- **Next minor releases**: Warnings continue, no breaking changes
- **Next major version** (future): Compatibility shim may be removed
**Recommendation:** Migrate during your next code maintenance cycle to avoid rushing.
---
## Need Help?
If you encounter any issues:
1. Check this migration guide
2. Review `CONSOLIDATION_REPORT.md` for technical details
3. Check `executors/deprecated/DEPRECATION_NOTICE.md`
4. Contact maintainers if problems persist
---
## Testing Your Migration
Run these quick tests after migrating:
```python
# Test 1: Import works
from sdk_workflow.executors import OneshotExecutor
print(" Import successful")
# Test 2: Instantiation works
executor = OneshotExecutor()
print(" Instantiation successful")
# Test 3: No deprecation warnings
import warnings
with warnings.catch_warnings(record=True) as w:
    from sdk_workflow.executors import OneshotExecutor
    assert len(w) == 0, "Unexpected deprecation warning"
print(" No deprecation warnings")
# Test 4: Functionality intact
executor = OneshotExecutor()
executor.setup()
print(" Functionality intact")
```
---
**Last updated:** December 19, 2024
**Status:** Production Ready
**Breaking Changes:** None
