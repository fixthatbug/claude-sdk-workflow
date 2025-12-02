"""Cost Tracking - Token usage and execution cost management."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Pricing per 1M tokens (as of knowledge cutoff)
MODEL_PRICING = {
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-20250514": {"input": 0.25, "output": 1.25},
    # Aliases
    "opus": {"input": 15.0, "output": 75.0},
    "sonnet": {"input": 3.0, "output": 15.0},
    "haiku": {"input": 0.25, "output": 1.25},
}


@dataclass
class TokenUsage:
    """Token usage record."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ExecutionMetrics:
    """Metrics from a single execution."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    tokens: TokenUsage = field(default_factory=TokenUsage)
    tool_calls: int = 0
    model: str = "sonnet"
    cost_usd: float = 0.0
    
    @property
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


class TokenUsageCalculator:
    """Calculate token usage and costs."""
    
    def __init__(self, model: str = "sonnet"):
        self.model = model
        self._usage_history: List[TokenUsage] = []
    
    def calculate_cost(self, usage: TokenUsage) -> float:
        """Calculate cost in USD for token usage."""
        pricing = MODEL_PRICING.get(self.model, MODEL_PRICING["sonnet"])
        
        input_cost = (usage.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (usage.output_tokens / 1_000_000) * pricing["output"]
        
        # Cache reads are 90% cheaper
        cache_read_cost = (usage.cache_read_tokens / 1_000_000) * pricing["input"] * 0.1
        # Cache writes have a small premium
        cache_write_cost = (usage.cache_write_tokens / 1_000_000) * pricing["input"] * 1.25
        
        return input_cost + output_cost + cache_read_cost + cache_write_cost
    
    def record(self, usage: TokenUsage) -> float:
        """Record usage and return cost."""
        self._usage_history.append(usage)
        return self.calculate_cost(usage)
    
    def get_totals(self) -> TokenUsage:
        """Get total usage across all records."""
        total = TokenUsage()
        for u in self._usage_history:
            total.input_tokens += u.input_tokens
            total.output_tokens += u.output_tokens
            total.cache_read_tokens += u.cache_read_tokens
            total.cache_write_tokens += u.cache_write_tokens
        return total
    
    def get_total_cost(self) -> float:
        """Get total cost across all records."""
        return self.calculate_cost(self.get_totals())


class CostTracker:
    """Track costs across multiple sessions and models."""
    
    def __init__(self, budget_usd: Optional[float] = None):
        self.budget_usd = budget_usd
        self._sessions: Dict[str, ExecutionMetrics] = {}
        self._calculators: Dict[str, TokenUsageCalculator] = {}
    
    def start_session(self, session_id: str, model: str = "sonnet") -> ExecutionMetrics:
        """Start tracking a new session."""
        metrics = ExecutionMetrics(
            session_id=session_id,
            start_time=datetime.now(),
            model=model
        )
        self._sessions[session_id] = metrics
        
        if model not in self._calculators:
            self._calculators[model] = TokenUsageCalculator(model)
        
        return metrics
    
    def record_usage(
        self,
        session_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> float:
        """Record token usage for a session. Returns cost."""
        if session_id not in self._sessions:
            logger.warning(f"Unknown session: {session_id}")
            return 0.0
        
        metrics = self._sessions[session_id]
        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write
        )
        
        metrics.tokens.input_tokens += input_tokens
        metrics.tokens.output_tokens += output_tokens
        metrics.tokens.cache_read_tokens += cache_read
        metrics.tokens.cache_write_tokens += cache_write
        
        calc = self._calculators.get(metrics.model, TokenUsageCalculator(metrics.model))
        cost = calc.calculate_cost(usage)
        metrics.cost_usd += cost
        
        return cost
    
    def record_tool_call(self, session_id: str) -> None:
        """Record a tool call for a session."""
        if session_id in self._sessions:
            self._sessions[session_id].tool_calls += 1
    
    def end_session(self, session_id: str) -> Optional[ExecutionMetrics]:
        """End tracking for a session."""
        if session_id in self._sessions:
            self._sessions[session_id].end_time = datetime.now()
            return self._sessions[session_id]
        return None
    
    def get_session_metrics(self, session_id: str) -> Optional[ExecutionMetrics]:
        """Get metrics for a specific session."""
        return self._sessions.get(session_id)
    
    def get_total_cost(self) -> float:
        """Get total cost across all sessions."""
        return sum(m.cost_usd for m in self._sessions.values())
    
    def is_over_budget(self) -> bool:
        """Check if total cost exceeds budget."""
        if self.budget_usd is None:
            return False
        return self.get_total_cost() > self.budget_usd
    
    def remaining_budget(self) -> Optional[float]:
        """Get remaining budget, if set."""
        if self.budget_usd is None:
            return None
        return max(0, self.budget_usd - self.get_total_cost())
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all tracking."""
        return {
            "total_sessions": len(self._sessions),
            "total_cost_usd": self.get_total_cost(),
            "budget_usd": self.budget_usd,
            "remaining_budget": self.remaining_budget(),
            "total_tokens": sum(m.tokens.total_tokens for m in self._sessions.values()),
            "total_tool_calls": sum(m.tool_calls for m in self._sessions.values()),
        }


__all__ = [
    'TokenUsage',
    'ExecutionMetrics',
    'TokenUsageCalculator',
    'CostTracker',
    'MODEL_PRICING',
]
