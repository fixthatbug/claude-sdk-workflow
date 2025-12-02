"""Execution Mode - Mode selection and complexity assessment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class ExecutionMode(Enum):
    """Available execution modes."""
    STANDARD = "standard"
    EXTENDED_THINKING = "extended_thinking"
    AGENTIC = "agentic"
    BATCH = "batch"
    STREAMING = "streaming"


class ComplexityLevel(Enum):
    """Task complexity levels."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EXPERT = "expert"


@dataclass
class ModeConfig:
    """Configuration for an execution mode."""
    mode: ExecutionMode
    thinking_budget: int = 8000
    max_tokens: int = 4096
    streaming: bool = True
    parallel: bool = False


class ModeSelector:
    """Select optimal execution mode based on task characteristics."""
    
    COMPLEXITY_THRESHOLDS = {
        "token_simple": 500,
        "token_moderate": 2000,
        "token_complex": 5000,
    }
    
    MODE_CONFIGS = {
        ExecutionMode.STANDARD: ModeConfig(
            mode=ExecutionMode.STANDARD,
            thinking_budget=4000,
            max_tokens=4096
        ),
        ExecutionMode.EXTENDED_THINKING: ModeConfig(
            mode=ExecutionMode.EXTENDED_THINKING,
            thinking_budget=16000,
            max_tokens=8192
        ),
        ExecutionMode.AGENTIC: ModeConfig(
            mode=ExecutionMode.AGENTIC,
            thinking_budget=8000,
            max_tokens=4096,
            parallel=True
        ),
        ExecutionMode.BATCH: ModeConfig(
            mode=ExecutionMode.BATCH,
            streaming=False,
            parallel=True
        ),
    }
    
    def __init__(self):
        self._task_history: list = []
    
    def assess_complexity(self, task: str) -> ComplexityLevel:
        """Assess task complexity."""
        indicators = {
            "complex_keywords": len([w for w in ["analyze", "compare", "design", "implement", "optimize"] 
                                    if w in task.lower()]),
            "length": len(task),
            "questions": task.count("?"),
            "steps": sum(1 for w in ["then", "after", "next", "finally"] if w in task.lower()),
        }
        
        score = (
            indicators["complex_keywords"] * 2 +
            (indicators["length"] // 200) +
            indicators["questions"] +
            indicators["steps"]
        )
        
        if score >= 6:
            return ComplexityLevel.EXPERT
        elif score >= 4:
            return ComplexityLevel.COMPLEX
        elif score >= 2:
            return ComplexityLevel.MODERATE
        return ComplexityLevel.SIMPLE
    
    def select_mode(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ModeConfig:
        """Select optimal mode for task."""
        complexity = self.assess_complexity(task)
        context = context or {}
        
        # Check for explicit mode request
        if "mode" in context:
            explicit = context["mode"]
            try:
                mode = ExecutionMode(explicit)
                return self.MODE_CONFIGS.get(mode, self.MODE_CONFIGS[ExecutionMode.STANDARD])
            except ValueError:
                pass
        
        # Select based on complexity
        if complexity == ComplexityLevel.EXPERT:
            return self.MODE_CONFIGS[ExecutionMode.EXTENDED_THINKING]
        elif complexity == ComplexityLevel.COMPLEX:
            return self.MODE_CONFIGS[ExecutionMode.AGENTIC]
        elif "batch" in task.lower() or context.get("batch"):
            return self.MODE_CONFIGS[ExecutionMode.BATCH]
        
        return self.MODE_CONFIGS[ExecutionMode.STANDARD]
    
    def get_thinking_budget(self, complexity: ComplexityLevel) -> int:
        """Get appropriate thinking budget for complexity."""
        budgets = {
            ComplexityLevel.SIMPLE: 4000,
            ComplexityLevel.MODERATE: 8000,
            ComplexityLevel.COMPLEX: 12000,
            ComplexityLevel.EXPERT: 16000,
        }
        return budgets.get(complexity, 8000)


__all__ = [
    'ExecutionMode',
    'ComplexityLevel',
    'ModeConfig',
    'ModeSelector',
]
