"""
SDK Workflow Enhancements Module - Backward Compatibility Layer

This module provides backward compatibility by re-exporting from the
new modular SDK architecture. For new code, import directly from the
sdk package instead.

@version 2.0.0 (modularized)
@deprecated Import from sdk package instead: `from sdk import *`
"""

# Re-export everything from the modular SDK for backward compatibility
from sdk import (
    # Core
    SDK_AVAILABLE,
    ConversationSession,
    SessionUtilities,
    SessionData,
    StreamingHandler,
    StreamingConfig,
    EvaluationFramework,
    HallucinationGuard,
    ConsistencyEnforcer,
    
    # Managers
    CostTracker,
    TokenUsageCalculator,
    ExecutionMetrics,
    ContextCacheManager,
    CacheMonitor,
    ContextEditingManager,
    ProgressMonitor,
    ContainerManager,
    
    # Tools
    ToolResponseParser,
    ToolResult,
    MemoryToolValidator,
    ToolPreset,
    get_tool_preset,
    TOOL_PRESETS,
    
    # Execution
    ExecutionMode,
    ComplexityLevel,
    ModeSelector,
    WorkflowModeIntegrator,
    BatchProcessor,
    LatencyOptimizer,
    ExtendedThinkingBudget,
    
    # Utils
    MCPServerRegistry,
    SDK_VERSION,
    DEFAULT_MODEL,
    DEFAULT_THINKING_BUDGET,
    DEFAULT_MAX_TOKENS,
)

# Additional re-exports from core streaming
from sdk.core.streaming import (
    StreamingMode,
    StreamChunk,
    StreamingDecisionEngine,
    create_streaming_handler,
)

# Additional re-exports from managers
from sdk.managers.cost import (
    TokenUsage,
    MODEL_PRICING,
)

from sdk.managers.cache import CacheEntry
from sdk.managers.container import ContainerState, ContainerConfig, Container
from sdk.managers.progress import ProgressUpdate

# Additional re-exports from execution
from sdk.execution.mode import ModeConfig
from sdk.execution.workflow import WorkflowStep, WorkflowResult, BatchItem
from sdk.execution.optimization import LatencyMetrics, ThinkingBudgetConfig

# Additional re-exports from utils
from sdk.utils.constants import (
    MODELS,
    TOOL_CATEGORIES,
    CONTAINER_CONFIG,
    COMPUTER_USE_ACTIONS,
    RATE_LIMITS,
)

from sdk.utils.registry import MCPServer

# Re-export evaluation types
from sdk.core.evaluation import EvaluationResult, EvaluationReport

# Convenience function aliases (for legacy code)
def create_validation_hooks():
    """Create validation hooks - use EvaluationFramework instead."""
    return EvaluationFramework(strict_mode=True)

def create_logging_hooks():
    """Create logging hooks - use ProgressMonitor instead."""
    return ProgressMonitor()

# Constants for backward compatibility
TOOL_RESPONSE_TYPES = {
    "web_search": "search_results",
    "web_fetch": "page_content",
    "code_execution": "execution_result",
}

PROGRAMMATIC_TOOL_CONFIG = {
    "enabled": True,
    "types": list(TOOL_RESPONSE_TYPES.keys()),
}

__all__ = [
    # Version
    'SDK_VERSION',
    
    # Core
    'SDK_AVAILABLE',
    'ConversationSession',
    'SessionUtilities',
    'SessionData',
    'StreamingHandler',
    'StreamingConfig',
    'StreamingMode',
    'StreamChunk',
    'StreamingDecisionEngine',
    'create_streaming_handler',
    'EvaluationFramework',
    'EvaluationResult',
    'EvaluationReport',
    'HallucinationGuard',
    'ConsistencyEnforcer',
    
    # Managers
    'CostTracker',
    'TokenUsageCalculator',
    'TokenUsage',
    'ExecutionMetrics',
    'MODEL_PRICING',
    'ContextCacheManager',
    'CacheMonitor',
    'CacheEntry',
    'ContextEditingManager',
    'ProgressMonitor',
    'ProgressUpdate',
    'ContainerManager',
    'ContainerState',
    'ContainerConfig',
    'Container',
    
    # Tools
    'ToolResponseParser',
    'ToolResult',
    'MemoryToolValidator',
    'ToolPreset',
    'get_tool_preset',
    'TOOL_PRESETS',
    
    # Execution
    'ExecutionMode',
    'ComplexityLevel',
    'ModeConfig',
    'ModeSelector',
    'WorkflowModeIntegrator',
    'WorkflowStep',
    'WorkflowResult',
    'BatchProcessor',
    'BatchItem',
    'LatencyOptimizer',
    'LatencyMetrics',
    'ExtendedThinkingBudget',
    'ThinkingBudgetConfig',
    
    # Utils
    'MCPServerRegistry',
    'MCPServer',
    'DEFAULT_MODEL',
    'DEFAULT_THINKING_BUDGET',
    'DEFAULT_MAX_TOKENS',
    'MODELS',
    'TOOL_CATEGORIES',
    'CONTAINER_CONFIG',
    'COMPUTER_USE_ACTIONS',
    'RATE_LIMITS',
    
    # Legacy compatibility
    'TOOL_RESPONSE_TYPES',
    'PROGRAMMATIC_TOOL_CONFIG',
    'create_validation_hooks',
    'create_logging_hooks',
]
