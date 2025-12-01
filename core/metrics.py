"""
MetricsEngine - Cost tracking and usage analytics for SDK Workflow.
Provides real-time cost calculation, budget enforcement, and usage summaries.
Integrates with the existing Config and ModelConfig architecture.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from .config import get_config, Config
@dataclass
class RequestMetrics:
    """Metrics for a single request."""
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    cost: float
    timestamp: datetime = field(default_factory=datetime.now)
class BudgetExceededError(Exception):
    """Raised when budget hard limit is exceeded."""
    def __init__(self, current_cost: float, limit: float):
        self.current_cost = current_cost
        self.limit = limit
        super().__init__(f"Budget exceeded: ${current_cost:.4f} > ${limit:.4f}")
class MetricsEngine:
    """
    Tracks API usage and costs across requests.
    Features:
    - Per-request cost calculation with cache pricing
    - Budget enforcement (soft/hard limits)
    - Usage summaries by model
    - Session-level aggregation
    Integrates with Config for pricing and budget thresholds.
    """
    def __init__(
        self,
        config: Optional[Config] = None,
        daily_budget: Optional[float] = None,
    ):
        """
        Initialize MetricsEngine.
        Args:
            config: Optional Config instance (uses global if not provided)
            daily_budget: Override daily budget (uses config default if not provided)
        """
        self._config = config or get_config()
        self._daily_budget = daily_budget or self._config.budget.daily_budget_usd
        self._requests: list[RequestMetrics] = []
        self._total_cost: float = 0.0
        self._started_at: Optional[datetime] = None
        self._model_usage: dict[str, dict] = {}
    @property
    def soft_limit(self) -> float:
        """Soft budget limit (warning threshold)."""
        return self._daily_budget * self._config.budget.soft_limit_percent
    @property
    def hard_limit(self) -> float:
        """Hard budget limit (blocking threshold)."""
        return self._daily_budget * self._config.budget.hard_limit_percent
    @property
    def emergency_limit(self) -> float:
        """Emergency budget limit (block all)."""
        return self._daily_budget * self._config.budget.emergency_limit_percent
    def _calculate_cost(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int,
        cache_write_tokens: int,
    ) -> float:
        """Calculate cost for a request using ModelConfig pricing."""
        model_config = self._config.models.get(model_id)
        if model_config is None:
            raise ValueError(f"Unknown model: {model_id}")
        # Calculate cost components (pricing is per 1M tokens)
        input_cost = (input_tokens / 1_000_000) * model_config.input_price_per_mtok
        output_cost = (output_tokens / 1_000_000) * model_config.output_price_per_mtok
        cache_read_cost = (cached_tokens / 1_000_000) * model_config.cache_read_price
        cache_write_cost = (cache_write_tokens / 1_000_000) * model_config.cache_write_price
        return input_cost + output_cost + cache_read_cost + cache_write_cost
    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to full model ID."""
        return self._config.aliases.get(model, model)
    def track_request(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> float:
        """
        Track a request and calculate its cost.
        Args:
            model: Model ID or alias
            input_tokens: Number of input tokens (non-cached)
            output_tokens: Number of output tokens
            cached_tokens: Number of tokens read from cache
            cache_write_tokens: Number of tokens written to cache
        Returns:
            Cost of this request in dollars
        Raises:
            BudgetExceededError: If hard limit would be exceeded
        """
        if self._started_at is None:
            self._started_at = datetime.now()
        resolved_model = self._resolve_model(model)
        total_request_cost = self._calculate_cost(
            resolved_model,
            input_tokens,
            output_tokens,
            cached_tokens,
            cache_write_tokens,
        )
        # Check budget before recording
        projected_total = self._total_cost + total_request_cost
        if projected_total > self.hard_limit:
            raise BudgetExceededError(projected_total, self.hard_limit)
        # Record the request
        metrics = RequestMetrics(
            model=resolved_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            cache_write_tokens=cache_write_tokens,
            cost=total_request_cost,
        )
        self._requests.append(metrics)
        self._total_cost += total_request_cost
        # Update per-model tracking
        if resolved_model not in self._model_usage:
            self._model_usage[resolved_model] = {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "cache_write_tokens": 0,
                "cost": 0.0,
            }
        usage = self._model_usage[resolved_model]
        usage["requests"] += 1
        usage["input_tokens"] += input_tokens
        usage["output_tokens"] += output_tokens
        usage["cached_tokens"] += cached_tokens
        usage["cache_write_tokens"] += cache_write_tokens
        usage["cost"] += total_request_cost
        return total_request_cost
    def get_cost(self) -> float:
        """Get total cost so far."""
        return self._total_cost
    def is_over_soft_limit(self) -> bool:
        """Check if soft budget limit has been exceeded."""
        return self._total_cost >= self.soft_limit
    def is_over_hard_limit(self) -> bool:
        """Check if hard budget limit has been exceeded."""
        return self._total_cost >= self.hard_limit
    def is_over_emergency_limit(self) -> bool:
        """Check if emergency budget limit has been exceeded."""
        return self._total_cost >= self.emergency_limit
    def remaining_budget(self) -> float:
        """Get remaining budget before hard limit."""
        return max(0.0, self.hard_limit - self._total_cost)
    def get_summary(self) -> dict:
        """
        Get comprehensive usage summary.
        Returns:
            Dictionary with:
            - total_cost: Total cost in dollars
            - total_requests: Number of requests
            - total_tokens: Total tokens used
            - by_model: Per-model breakdown
            - budget: Budget status
            - duration: Time elapsed
        """
        total_input = sum(r.input_tokens for r in self._requests)
        total_output = sum(r.output_tokens for r in self._requests)
        total_cached = sum(r.cached_tokens for r in self._requests)
        total_cache_write = sum(r.cache_write_tokens for r in self._requests)
        duration = None
        if self._started_at:
            duration = (datetime.now() - self._started_at).total_seconds()
        # Calculate cache savings
        cache_savings = 0.0
        for r in self._requests:
            if r.cached_tokens > 0:
                model_config = self._config.models.get(r.model)
                if model_config:
                    # Savings = what we would have paid vs what we paid
                    full_price = (r.cached_tokens / 1_000_000) * model_config.input_price_per_mtok
                    cache_price = (r.cached_tokens / 1_000_000) * model_config.cache_read_price
                    cache_savings += full_price - cache_price
        return {
            "total_cost": round(self._total_cost, 6),
            "total_requests": len(self._requests),
            "total_tokens": {
                "input": total_input,
                "output": total_output,
                "cached_read": total_cached,
                "cached_write": total_cache_write,
                "total": total_input + total_output + total_cached,
            },
            "cache_savings": round(cache_savings, 6),
            "by_model": {
                model: {
                    "requests": data["requests"],
                    "input_tokens": data["input_tokens"],
                    "output_tokens": data["output_tokens"],
                    "cached_tokens": data["cached_tokens"],
                    "cost": round(data["cost"], 6),
                }
                for model, data in self._model_usage.items()
            },
            "budget": {
                "daily_budget": self._daily_budget,
                "soft_limit": round(self.soft_limit, 2),
                "hard_limit": round(self.hard_limit, 2),
                "emergency_limit": round(self.emergency_limit, 2),
                "remaining": round(self.remaining_budget(), 6),
                "over_soft": self.is_over_soft_limit(),
                "over_hard": self.is_over_hard_limit(),
                "over_emergency": self.is_over_emergency_limit(),
                "utilization": round(self._total_cost / self.hard_limit * 100, 2) if self.hard_limit > 0 else 0,
            },
            "duration_seconds": duration,
            "started_at": self._started_at.isoformat() if self._started_at else None,
        }
    def reset(self) -> dict:
        """
        Reset all metrics and return final summary.
        Returns:
            Final summary before reset
        """
        final_summary = self.get_summary()
        self._requests = []
        self._total_cost = 0.0
        self._started_at = None
        self._model_usage = {}
        return final_summary
    def get_request_history(self) -> list[dict]:
        """Get list of all tracked requests."""
        return [
            {
                "model": r.model,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cached_tokens": r.cached_tokens,
                "cache_write_tokens": r.cache_write_tokens,
                "cost": round(r.cost, 6),
                "timestamp": r.timestamp.isoformat(),
            }
            for r in self._requests
        ]
    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
    ) -> float:
        """
        Estimate cost for a hypothetical request without tracking it.
        Useful for pre-flight budget checks.
        """
        resolved_model = self._resolve_model(model)
        model_config = self._config.models.get(resolved_model)
        if model_config is None:
            raise ValueError(f"Unknown model: {model}")
        input_cost = (input_tokens / 1_000_000) * model_config.input_price_per_mtok
        output_cost = (output_tokens / 1_000_000) * model_config.output_price_per_mtok
        cache_read_cost = (cached_tokens / 1_000_000) * model_config.cache_read_price
        return input_cost + output_cost + cache_read_cost
    def can_afford(
        self,
        model: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> bool:
        """
        Check if a request can be afforded within budget.
        Args:
            model: Model ID or alias
            estimated_input_tokens: Estimated input tokens
            estimated_output_tokens: Estimated output tokens
        Returns:
            True if request is within budget
        """
        estimated_cost = self.estimate_cost(model, estimated_input_tokens, estimated_output_tokens)
        return (self._total_cost + estimated_cost) <= self.hard_limit
