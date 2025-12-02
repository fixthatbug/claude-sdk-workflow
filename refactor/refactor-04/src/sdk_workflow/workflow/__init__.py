"""
Workflow Module - Workflow orchestration and processing.

Contains:
- processor.py: WorkflowModeIntegrator, BatchProcessor
- evaluation.py: EvaluationFramework, HallucinationGuard
- streaming.py: StreamingHandler, StreamingDecisionEngine
"""

from .processor import (
    WorkflowStep,
    WorkflowResult,
    WorkflowModeIntegrator,
    BatchItem,
    BatchProcessor,
)

from .evaluation import (
    EvaluationResult,
    EvaluationReport,
    EvaluationFramework,
    HallucinationGuard,
    ConsistencyEnforcer,
)

from .streaming import (
    StreamingMode,
    StreamingConfig,
    StreamChunk,
    StreamingHandler,
    StreamingDecisionEngine,
    create_streaming_handler,
)

__all__ = [
    # Processor
    "WorkflowStep",
    "WorkflowResult",
    "WorkflowModeIntegrator",
    "BatchItem",
    "BatchProcessor",
    
    # Evaluation
    "EvaluationResult",
    "EvaluationReport",
    "EvaluationFramework",
    "HallucinationGuard",
    "ConsistencyEnforcer",
    
    # Streaming
    "StreamingMode",
    "StreamingConfig",
    "StreamChunk",
    "StreamingHandler",
    "StreamingDecisionEngine",
    "create_streaming_handler",
]
