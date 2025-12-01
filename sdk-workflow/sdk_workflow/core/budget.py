"""Budget management for SDK workflow API spending.
Provides daily budget tracking with tiered warning levels to prevent
unexpected costs while allowing flexibility for important work.
"""
import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from enum import Enum
from dataclasses import dataclass, asdict
import threading
class BudgetStatus(Enum):
    """Budget check result status levels."""
    OK = "OK" # Under 70% - proceed normally
    SOFT_WARNING = "SOFT_WARNING" # 70-90% - warn but allow
    HARD_LIMIT = "HARD_LIMIT" # 90-100% - require confirmation
    EMERGENCY = "EMERGENCY" # >100% - block unless override
@dataclass
class DailyBudget:
    """Daily budget tracking data."""
    date: str
    limit: float
    spent: float
    transactions: list
    def to_dict(self) -> dict:
        return asdict(self)
    @classmethod
    def from_dict(cls, data: dict) -> "DailyBudget":
        return cls(
            date=data["date"],
            limit=data["limit"],
            spent=data["spent"],
            transactions=data.get("transactions", [])
        )
class BudgetManager:
    """Manages daily API spending budget with tiered warnings.
    Tracks spending against a configurable daily limit and provides
    status checks before operations to prevent overspending.
    Status Levels:
        - OK (< 70%): Proceed normally
        - SOFT_WARNING (70-90%): Log warning, proceed
        - HARD_LIMIT (90-100%): Require explicit confirmation
        - EMERGENCY (> 100%): Block unless emergency override
    Usage:
        budget = BudgetManager(daily_limit=10.0)
        # Before operation
        allowed, status = budget.check(estimated_cost=0.50)
        if allowed:
            # Perform operation
            budget.record_spend(actual_cost=0.45)
        # Check utilization
        print(f"Used {budget.get_utilization():.1%} of daily budget")
    """
    # Threshold percentages for status levels
    SOFT_WARNING_THRESHOLD = 0.70 # 70%
    HARD_LIMIT_THRESHOLD = 0.90 # 90%
    EMERGENCY_THRESHOLD = 1.00 # 100%
    def __init__(
        self,
        daily_limit: float = 10.0,
        storage_dir: Optional[Path] = None
    ):
        """Initialize budget manager.
        Args:
            daily_limit: Maximum daily spend in USD.
            storage_dir: Directory for budget data. Defaults to
                        ~/.claude/sdk-workflow/budget/
        """
        self.daily_limit = daily_limit
        self.storage_dir = storage_dir or Path.home() / ".claude" / "sdk-workflow" / "budget"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._current_budget: Optional[DailyBudget] = None
        # Load or create today's budget
        self._ensure_current_budget()
    def _get_budget_file(self, for_date: Optional[date] = None) -> Path:
        """Get path to budget file for a specific date."""
        target_date = for_date or date.today()
        return self.storage_dir / f"budget_{target_date.isoformat()}.json"
    def _ensure_current_budget(self) -> DailyBudget:
        """Ensure we have a budget record for today."""
        today = date.today().isoformat()
        with self._lock:
            # Check if cached budget is still valid
            if self._current_budget and self._current_budget.date == today:
                return self._current_budget
            # Try to load from file
            budget_file = self._get_budget_file()
            if budget_file.exists():
                try:
                    with open(budget_file, "r") as f:
                        data = json.load(f)
                    self._current_budget = DailyBudget.from_dict(data)
                    return self._current_budget
                except (json.JSONDecodeError, KeyError):
                    pass # Create new if corrupted
            # Create new budget for today
            self._current_budget = DailyBudget(
                date=today,
                limit=self.daily_limit,
                spent=0.0,
                transactions=[]
            )
            self._save_budget()
            return self._current_budget
    def _save_budget(self) -> None:
        """Save current budget to disk."""
        if self._current_budget:
            budget_file = self._get_budget_file()
            with open(budget_file, "w") as f:
                json.dump(self._current_budget.to_dict(), f, indent=2)
    def check(
        self,
        estimated_cost: float,
        allow_emergency: bool = False
    ) -> tuple[bool, str]:
        """Check if an operation is within budget.
        Args:
            estimated_cost: Estimated cost of the operation in USD.
            allow_emergency: If True, allow operations even over limit.
        Returns:
            Tuple of (allowed: bool, status: str).
            Status is one of: OK, SOFT_WARNING, HARD_LIMIT, EMERGENCY
        """
        budget = self._ensure_current_budget()
        projected_spend = budget.spent + estimated_cost
        utilization = projected_spend / budget.limit
        if utilization < self.SOFT_WARNING_THRESHOLD:
            return True, BudgetStatus.OK.value
        elif utilization < self.HARD_LIMIT_THRESHOLD:
            return True, BudgetStatus.SOFT_WARNING.value
        elif utilization < self.EMERGENCY_THRESHOLD:
            # Hard limit - operation allowed but at risk
            return True, BudgetStatus.HARD_LIMIT.value
        else:
            # Over budget - only allow if emergency override
            return allow_emergency, BudgetStatus.EMERGENCY.value
    def record_spend(
        self,
        cost: float,
        operation: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> None:
        """Record an API spend transaction.
        Args:
            cost: Actual cost of the operation in USD.
            operation: Optional description of the operation.
            metadata: Optional additional data (tokens, model, etc).
        """
        budget = self._ensure_current_budget()
        with self._lock:
            budget.spent += cost
            budget.transactions.append({
                "timestamp": datetime.now().isoformat(),
                "cost": cost,
                "operation": operation,
                "metadata": metadata or {},
                "running_total": budget.spent
            })
            self._save_budget()
    def get_utilization(self) -> float:
        """Get current budget utilization as a ratio (0.0 to 1.0+).
        Returns:
            Utilization ratio. Values > 1.0 indicate over-budget.
        """
        budget = self._ensure_current_budget()
        return budget.spent / budget.limit if budget.limit > 0 else 0.0
    def get_remaining(self) -> float:
        """Get remaining budget in USD.
        Returns:
            Remaining budget. Negative if over-budget.
        """
        budget = self._ensure_current_budget()
        return budget.limit - budget.spent
    def get_status(self) -> dict:
        """Get complete budget status.
        Returns:
            Dict with limit, spent, remaining, utilization, and status.
        """
        budget = self._ensure_current_budget()
        utilization = self.get_utilization()
        if utilization < self.SOFT_WARNING_THRESHOLD:
            status = BudgetStatus.OK.value
        elif utilization < self.HARD_LIMIT_THRESHOLD:
            status = BudgetStatus.SOFT_WARNING.value
        elif utilization < self.EMERGENCY_THRESHOLD:
            status = BudgetStatus.HARD_LIMIT.value
        else:
            status = BudgetStatus.EMERGENCY.value
        return {
            "date": budget.date,
            "limit": budget.limit,
            "spent": round(budget.spent, 4),
            "remaining": round(self.get_remaining(), 4),
            "utilization": round(utilization, 4),
            "utilization_percent": f"{utilization:.1%}",
            "status": status,
            "transaction_count": len(budget.transactions)
        }
    def get_transactions(self, limit: Optional[int] = None) -> list:
        """Get transaction history for today.
        Args:
            limit: Optional max number of recent transactions.
        Returns:
            List of transaction records.
        """
        budget = self._ensure_current_budget()
        transactions = budget.transactions
        if limit:
            return transactions[-limit:]
        return transactions
    def set_daily_limit(self, new_limit: float) -> None:
        """Update the daily budget limit.
        Args:
            new_limit: New daily limit in USD.
        """
        self.daily_limit = new_limit
        budget = self._ensure_current_budget()
        with self._lock:
            budget.limit = new_limit
            self._save_budget()
    def reset_daily_spend(self) -> None:
        """Reset today's spending (use with caution).
        Warning:
            This clears all transaction history for today.
            Primarily useful for testing or error recovery.
        """
        with self._lock:
            self._current_budget = DailyBudget(
                date=date.today().isoformat(),
                limit=self.daily_limit,
                spent=0.0,
                transactions=[]
            )
            self._save_budget()
    @staticmethod
    def estimate_cost(
        input_tokens: int,
        output_tokens: int,
        model: str = "claude-sonnet-4-20250514",
        cached_tokens: int = 0
    ) -> float:
        """Estimate API cost based on token counts.
        Args:
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            model: Model name for pricing lookup.
            cached_tokens: Number of cached input tokens (90% discount).
        Returns:
            Estimated cost in USD.
        """
        # Pricing per 1M tokens (as of 2024)
        pricing = {
            "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
            "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
            "claude-haiku-3-5-20241022": {"input": 0.25, "output": 1.25},
            # Fallback for unknown models
            "default": {"input": 3.0, "output": 15.0}
        }
        rates = pricing.get(model, pricing["default"])
        # Calculate costs
        non_cached_input = input_tokens - cached_tokens
        cached_cost = (cached_tokens / 1_000_000) * rates["input"] * 0.1 # 90% discount
        input_cost = (non_cached_input / 1_000_000) * rates["input"]
        output_cost = (output_tokens / 1_000_000) * rates["output"]
        return cached_cost + input_cost + output_cost
