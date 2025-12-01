"""
DEPRECATED MODULE - This module has been consolidated into streaming_orchestrator.py
This module is deprecated and will be removed in a future version.
All functionality has been migrated to:
    sdk_workflow.executors.streaming_orchestrator.OneshotExecutor
Migration Guide:
    OLD: from sdk_workflow.executors.oneshot import OneshotExecutor
    NEW: from sdk_workflow.executors.streaming_orchestrator import OneshotExecutor
    OR use the executors package (recommended):
    from sdk_workflow.executors import OneshotExecutor
Archive Location:
    sdk_workflow/executors/deprecated/v1.0-archived-{date}/oneshot.py.deprecated
Consolidation Date: {date}
Reason: Consolidate all executor functionalities into streaming_orchestrator.py
        to reduce module fragmentation and improve maintainability.
All OneshotExecutor functionality including:
- Auto-escalation from Haiku to Sonnet
- Model routing and quality checks
- Token accumulation across attempts
- Cost tracking and reporting
Has been fully preserved and consolidated into streaming_orchestrator.py
"""
import warnings
from typing import Optional
class OneshotExecutor:
    """
    DEPRECATED: Use OneshotExecutor from streaming_orchestrator instead.
    This class is a compatibility shim that redirects to the consolidated module.
    """
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "OneshotExecutor from oneshot.py is deprecated. "
            "Import from streaming_orchestrator instead: "
            "from sdk_workflow.executors.streaming_orchestrator import OneshotExecutor",
            DeprecationWarning,
            stacklevel=2
        )
        # Import and delegate to consolidated module
        from .streaming_orchestrator import OneshotExecutor as ConsolidatedOneshotExecutor
        self._executor = ConsolidatedOneshotExecutor(*args, **kwargs)
    def __getattr__(self, name):
        """Delegate all attributes to consolidated executor."""
        return getattr(self._executor, name)
# Re-export for backward compatibility
__all__ = ['OneshotExecutor']
