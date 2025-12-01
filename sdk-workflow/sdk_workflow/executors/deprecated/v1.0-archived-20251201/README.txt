DEPRECATED ONESHOT EXECUTOR MODULES ARCHIVE
==========================================
Archive Date: December 1, 2024 (Consolidation Date: December 19, 2024)
Archive Version: v1.0-archived-20251201
CONTENTS
--------
This directory contains archived versions of deprecated oneshot executor modules
that have been consolidated into streaming_orchestrator.py:
1. oneshot.py.deprecated
   - Original OneshotExecutor implementation
   - Auto-escalation logic (Haiku → Sonnet)
   - Model routing and quality checks
   - Token accumulation and cost tracking
2. oneshot_orchestrator.py.deprecated
   - OneshotOrchestrator implementation (already deprecated)
   - Checkpoint-based workflow execution
   - Session management and recovery
3. oneshot_example.py.deprecated
   - Advanced usage examples
   - AdvancedOneshotExecutor with hooks
   - Integration patterns
REASON FOR DEPRECATION
---------------------
These modules were consolidated to:
- Reduce module fragmentation
- Improve code organization
- Simplify maintenance
- Preserve all functionality in a single location
NEW LOCATION
-----------
All functionality now available in:
  sdk_workflow/executors/streaming_orchestrator.py
MIGRATION
---------
See the following files for migration guidance:
- ../../DEPRECATION_NOTICE.md
- ../../../CONSOLIDATION_REPORT.md
- ../../../MIGRATION_SUMMARY.md
BACKWARD COMPATIBILITY
---------------------
A compatibility shim exists in oneshot.py that:
- Issues deprecation warnings
- Redirects to consolidated module
- Maintains backward compatibility
RESTORATION
-----------
If restoration is needed:
1. Copy .deprecated files to parent directory
2. Remove .deprecated extension
3. Revert import changes in __init__.py and orchestrator.py
DO NOT MODIFY THESE FILES
-------------------------
These files are archived for reference only.
Modifications will not affect the running system.
For questions or issues, see CONSOLIDATION_REPORT.md
