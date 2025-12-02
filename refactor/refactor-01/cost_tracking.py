#!/usr/bin/env python3
"""
Cost tracking for Claude Agent SDK.

Provides execution metrics and cost tracking with budget alerts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionMetrics:
    """Metrics from a single execution."""
    session_id: str
    turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_cost_usd: float = 0.0
    duration_ms: int = 0
    tools_used: List[Dict[str, Any]] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    model: str = "sonnet"

    def add_turn(self, input_toks: int = 0, output_toks: int = 0) -> None:
        self.turns += 1
        self.input_tokens += input_toks
        self.output_tokens += output_toks

    def add_tool_use(self, tool_name: str, tool_input: Dict[str, Any]) -> None:
        self.tools_used.append({
            "tool": tool_name,
            "input_summary": str(tool_input)[:200],
            "timestamp": datetime.now().isoformat(),
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "turns": self.turns,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "total_cost_usd": self.total_cost_usd,
            "duration_ms": self.duration_ms,
            "tools_used_count": len(self.tools_used),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "model": self.model,
        }


class CostTracker:
    """Tracks costs across multiple executions."""

    PRICING = {
        "opus": {"input": 15.0, "output": 75.0, "cache_write": 18.75, "cache_read": 1.50},
        "sonnet": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.30},
        "haiku": {"input": 0.80, "output": 4.0, "cache_write": 1.0, "cache_read": 0.08},
    }

    def __init__(
        self,
        budget_usd: Optional[float] = None,
        on_budget_alert: Optional[Callable[[float, float], None]] = None,
    ):
        self.budget_usd = budget_usd
        self.on_budget_alert = on_budget_alert
        self.executions: Dict[str, ExecutionMetrics] = {}
        self.total_cost = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self._charged_message_ids: set = set()

    def start_execution(self, session_id: str, model: str = "sonnet") -> ExecutionMetrics:
        metrics = ExecutionMetrics(session_id=session_id, started_at=datetime.now(), model=model)
        self.executions[session_id] = metrics
        return metrics

    def update_execution(
        self,
        session_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read: int = 0,
        cache_write: int = 0,
    ) -> None:
        if session_id not in self.executions:
            return

        metrics = self.executions[session_id]
        metrics.add_turn(input_tokens, output_tokens)
        metrics.cache_read_tokens += cache_read
        metrics.cache_write_tokens += cache_write

        cost = self.calculate_cost(input_tokens, output_tokens, cache_read, cache_write, metrics.model)
        metrics.total_cost_usd += cost
        self.total_cost += cost
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        self._check_budget()

    def complete_execution(self, session_id: str, result_message: Any = None) -> Optional[ExecutionMetrics]:
        if session_id not in self.executions:
            return None

        if result_message and hasattr(result_message, 'id'):
            if result_message.id in self._charged_message_ids:
                return self.executions[session_id]
            self._charged_message_ids.add(result_message.id)

        metrics = self.executions[session_id]
        metrics.completed_at = datetime.now()

        if metrics.started_at:
            metrics.duration_ms = int((metrics.completed_at - metrics.started_at).total_seconds() * 1000)

        return metrics

    @classmethod
    def calculate_cost(
        cls,
        input_tokens: int,
        output_tokens: int,
        cache_read: int = 0,
        cache_write: int = 0,
        model: str = "sonnet",
    ) -> float:
        pricing = cls.PRICING.get(model, cls.PRICING["sonnet"])
        return (
            (input_tokens * pricing["input"] / 1_000_000) +
            (output_tokens * pricing["output"] / 1_000_000) +
            (cache_read * pricing["cache_read"] / 1_000_000) +
            (cache_write * pricing["cache_write"] / 1_000_000)
        )

    def _check_budget(self) -> None:
        if not self.budget_usd:
            return

        if self.total_cost >= self.budget_usd * 0.8:
            if self.on_budget_alert:
                self.on_budget_alert(self.total_cost, self.budget_usd)
            elif self.total_cost >= self.budget_usd:
                logger.warning(f"Budget exceeded: ${self.total_cost:.4f} / ${self.budget_usd:.2f}")
            else:
                logger.warning(f"Approaching budget: ${self.total_cost:.4f} / ${self.budget_usd:.2f}")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_cost_usd": self.total_cost,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "execution_count": len(self.executions),
            "budget_usd": self.budget_usd,
            "budget_remaining": (self.budget_usd - self.total_cost) if self.budget_usd else None,
            "executions": {sid: m.to_dict() for sid, m in self.executions.items()},
        }
