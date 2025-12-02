"""Optimization - Latency and thinking budget optimization."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LatencyMetrics:
    """Latency measurements."""
    ttft_ms: float = 0  # Time to first token
    total_ms: float = 0
    tokens_per_second: float = 0


class LatencyOptimizer:
    """Optimize latency through various strategies."""
    
    def __init__(self, target_ttft_ms: float = 500):
        self.target_ttft = target_ttft_ms
        self._samples: List[LatencyMetrics] = []
        self._strategies: Dict[str, bool] = {
            "streaming": True,
            "cache_priming": True,
            "batch_tokens": True,
            "connection_pooling": True,
        }
    
    def record(self, metrics: LatencyMetrics) -> None:
        """Record latency sample."""
        self._samples.append(metrics)
        if len(self._samples) > 100:
            self._samples.pop(0)
    
    def get_average_latency(self) -> LatencyMetrics:
        """Get average latency from samples."""
        if not self._samples:
            return LatencyMetrics()
        
        return LatencyMetrics(
            ttft_ms=sum(s.ttft_ms for s in self._samples) / len(self._samples),
            total_ms=sum(s.total_ms for s in self._samples) / len(self._samples),
            tokens_per_second=sum(s.tokens_per_second for s in self._samples) / len(self._samples)
        )
    
    def suggest_optimizations(self) -> List[str]:
        """Suggest optimizations based on metrics."""
        suggestions = []
        avg = self.get_average_latency()
        
        if avg.ttft_ms > self.target_ttft:
            if not self._strategies["streaming"]:
                suggestions.append("Enable streaming for faster first token")
            if not self._strategies["cache_priming"]:
                suggestions.append("Enable cache priming for repeated contexts")
        
        if avg.tokens_per_second < 20:
            suggestions.append("Consider reducing prompt complexity")
        
        return suggestions
    
    def enable_strategy(self, strategy: str) -> bool:
        """Enable an optimization strategy."""
        if strategy in self._strategies:
            self._strategies[strategy] = True
            return True
        return False
    
    def disable_strategy(self, strategy: str) -> bool:
        """Disable an optimization strategy."""
        if strategy in self._strategies:
            self._strategies[strategy] = False
            return True
        return False


@dataclass 
class ThinkingBudgetConfig:
    """Configuration for thinking budget."""
    min_budget: int = 1024
    max_budget: int = 128000
    default_budget: int = 8000


class ExtendedThinkingBudget:
    """Manage extended thinking token budgets."""
    
    def __init__(self, config: Optional[ThinkingBudgetConfig] = None):
        self.config = config or ThinkingBudgetConfig()
        self._usage_history: List[Dict] = []
    
    def calculate_budget(
        self,
        task_complexity: str,
        expected_output_tokens: int = 4000
    ) -> int:
        """Calculate appropriate thinking budget."""
        complexity_multipliers = {
            "simple": 0.5,
            "moderate": 1.0,
            "complex": 2.0,
            "expert": 4.0,
        }
        
        multiplier = complexity_multipliers.get(task_complexity.lower(), 1.0)
        budget = int(self.config.default_budget * multiplier)
        
        # Ensure within bounds
        budget = max(self.config.min_budget, min(budget, self.config.max_budget))
        
        return budget
    
    def record_usage(self, budget: int, actual_used: int) -> None:
        """Record thinking budget usage."""
        self._usage_history.append({
            "budget": budget,
            "used": actual_used,
            "efficiency": actual_used / budget if budget > 0 else 0,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_efficiency(self) -> float:
        """Get average budget efficiency."""
        if not self._usage_history:
            return 0.0
        return sum(u["efficiency"] for u in self._usage_history) / len(self._usage_history)
    
    def suggest_budget(self) -> int:
        """Suggest budget based on history."""
        if not self._usage_history:
            return self.config.default_budget
        
        avg_used = sum(u["used"] for u in self._usage_history[-10:]) / min(10, len(self._usage_history))
        return int(avg_used * 1.2)  # 20% buffer


__all__ = [
    'LatencyMetrics',
    'LatencyOptimizer',
    'ThinkingBudgetConfig',
    'ExtendedThinkingBudget',
]
