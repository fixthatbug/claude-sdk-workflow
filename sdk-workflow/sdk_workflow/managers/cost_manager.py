"""Cost management with advanced tracking, analytics, and budget alerts."""
import csv
import json
import logging
import threading
import time
from collections import deque, OrderedDict
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple
logger = logging.getLogger(__name__)
# Model pricing per million tokens (MTok)
MODEL_PRICING = {
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_write": 18.75},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75},
    "claude-haiku-3-5-20241022": {"input": 0.25, "output": 1.25, "cache_read": 0.025, "cache_write": 0.3125},
}
class CostManagerException(Exception):
    """Base exception for CostManager errors."""
    pass
class BudgetExceeded(CostManagerException):
    """Raised when budget limit is exceeded."""
    pass
class CostManager:
    """
    Manages cost tracking with advanced analytics and budget monitoring.
    This class provides comprehensive cost management including:
    - Cost calculation with prompt caching support
    - Budget alerts with soft/hard/emergency thresholds
    - Cost projection based on usage patterns
    - Cost breakdown by operation type
    - Cache efficiency reporting (90% savings tracking)
    - Multi-session cost aggregation
    - Export functionality (JSON/CSV)
    - Thread-safe operations
    - MetricsEngine integration
    Attributes:
        total_cost (float): Total cost accumulated across all operations
        cost_by_model (Dict[str, float]): Cost breakdown by model
        soft_limit_threshold (float): Percentage for soft budget warnings (default: 70%)
        hard_limit_threshold (float): Percentage for hard budget warnings (default: 90%)
        emergency_threshold (float): Percentage for emergency warnings (default: 100%)
    Example:
        >>> manager = CostManager()
        >>> cost = manager.calculate_cost(input_tokens=1000, output_tokens=500)
        >>> status = manager.check_budget_status(budget_limit=10.0)
        >>> print(f"Budget usage: {status['usage_pct']:.1f}%")
    """
    def __init__(
        self,
        history_size: int = 100,
        soft_limit_threshold: float = 70.0,
        hard_limit_threshold: float = 90.0,
        emergency_threshold: float = 100.0,
        metrics_engine: Optional[Any] = None
    ):
        """
        Initialize CostManager with configurable limits and options.
        Args:
            history_size: Maximum number of historical records to maintain
            soft_limit_threshold: Percentage for soft budget warnings (0-100)
            hard_limit_threshold: Percentage for hard budget warnings (0-100)
            emergency_threshold: Percentage for emergency warnings (0-100)
            metrics_engine: Optional MetricsEngine instance for integration
        Raises:
            ValueError: If thresholds are not in valid range or not in ascending order
        """
        # Validate thresholds
        if not 0 <= soft_limit_threshold <= 100:
            raise ValueError("soft_limit_threshold must be between 0 and 100")
        if not 0 <= hard_limit_threshold <= 100:
            raise ValueError("hard_limit_threshold must be between 0 and 100")
        if not 0 <= emergency_threshold <= 100:
            raise ValueError("emergency_threshold must be between 0 and 100")
        if not (soft_limit_threshold <= hard_limit_threshold <= emergency_threshold):
            raise ValueError("Thresholds must be in ascending order: soft <= hard <= emergency")
        # Basic cost tracking
        self.total_cost = 0.0
        self._max_models = 100
        self.cost_by_model: OrderedDict[str, float] = OrderedDict()
        # Budget thresholds
        self.soft_limit_threshold = soft_limit_threshold
        self.hard_limit_threshold = hard_limit_threshold
        self.emergency_threshold = emergency_threshold
        # Advanced features
        self.history_size = history_size
        self.metrics_engine = metrics_engine
        # Thread safety - using RLock to prevent deadlock on reentrant calls
        self._lock = threading.RLock()
        # Cost history tracking - stores dicts with timestamp and cost details
        self._cost_history: deque = deque(maxlen=history_size)
        # Operation type tracking
        self._cost_by_operation: Dict[str, float] = {
            'input': 0.0,
            'output': 0.0,
            'cache_read': 0.0,
            'cache_write': 0.0
        }
        # Token tracking for cost breakdown
        self._tokens_by_operation: Dict[str, int] = {
            'input': 0,
            'output': 0,
            'cache_read': 0,
            'cache_write': 0
        }
        # Cache efficiency tracking
        self._total_cache_savings = 0.0
        self._cache_read_tokens = 0
        self._total_input_tokens = 0 # For efficiency calculation
        # Statistics
        self._operation_count = 0
        self._start_time = time.time()
        self._last_warning_time = 0.0
        self._warning_cooldown = 60.0 # Seconds between duplicate warnings
        self._peak_cost = 0.0
        # Multi-session tracking
        self._max_sessions = 1000
        self._session_costs: OrderedDict[str, Dict] = OrderedDict()
    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read: int = 0,
        cache_write: int = 0,
        model: str = "claude-sonnet-4-20250514",
        session_id: Optional[str] = None
    ) -> float:
        """
        Calculate cost for a single API call with comprehensive tracking.
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cache_read: Number of cache read tokens (90% discount)
            cache_write: Number of cache write tokens
            model: Model identifier for pricing lookup
            session_id: Optional session identifier for multi-session tracking
        Returns:
            float: Total cost for this operation in USD
        Raises:
            ValueError: If any token count is negative
        Example:
            >>> manager = CostManager()
            >>> cost = manager.calculate_cost(
            ... input_tokens=1000,
            ... output_tokens=500,
            ... cache_read=200,
            ... model="claude-sonnet-4-20250514"
            ... )
            >>> print(f"Cost: ${cost:.6f}")
        """
        # Input validation
        if input_tokens < 0:
            raise ValueError(f"input_tokens must be non-negative, got {input_tokens}")
        if output_tokens < 0:
            raise ValueError(f"output_tokens must be non-negative, got {output_tokens}")
        if cache_read < 0:
            raise ValueError(f"cache_read must be non-negative, got {cache_read}")
        if cache_write < 0:
            raise ValueError(f"cache_write must be non-negative, got {cache_write}")
        with self._lock:
            # Get pricing for model (fallback to default)
            pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-sonnet-4-20250514"])
            # Calculate costs per operation type
            input_cost = (input_tokens / 1_000_000) * pricing["input"]
            output_cost = (output_tokens / 1_000_000) * pricing["output"]
            cache_read_cost = (cache_read / 1_000_000) * pricing["cache_read"]
            cache_write_cost = (cache_write / 1_000_000) * pricing["cache_write"]
            total = input_cost + output_cost + cache_read_cost + cache_write_cost
            # Update total cost
            self.total_cost += total
            # Update cost by model with FIFO eviction
            if model not in self.cost_by_model:
                if len(self.cost_by_model) >= self._max_models:
                    self.cost_by_model.popitem(last=False) # Remove oldest
            self.cost_by_model[model] = self.cost_by_model.get(model, 0.0) + total
            # Update operation type costs
            self._cost_by_operation['input'] += input_cost
            self._cost_by_operation['output'] += output_cost
            self._cost_by_operation['cache_read'] += cache_read_cost
            self._cost_by_operation['cache_write'] += cache_write_cost
            # Update token counts by operation
            self._tokens_by_operation['input'] += input_tokens
            self._tokens_by_operation['output'] += output_tokens
            self._tokens_by_operation['cache_read'] += cache_read
            self._tokens_by_operation['cache_write'] += cache_write
            # Update cache efficiency tracking
            if cache_read > 0:
                savings = self.get_cache_savings(cache_read, model)
                self._total_cache_savings += savings
                self._cache_read_tokens += cache_read
            self._total_input_tokens += input_tokens
            # Update session costs if session_id provided with FIFO eviction
            if session_id:
                if session_id not in self._session_costs:
                    if len(self._session_costs) >= self._max_sessions:
                        self._session_costs.popitem(last=False) # Remove oldest
                self._session_costs[session_id] = self._session_costs.get(session_id, 0.0) + total
            # Update statistics
            self._operation_count += 1
            if self.total_cost > self._peak_cost:
                self._peak_cost = self.total_cost
            # Record in history
            history_entry = {
                'timestamp': time.time(),
                'datetime': datetime.now().isoformat(),
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cache_read_tokens': cache_read,
                'cache_write_tokens': cache_write,
                'input_cost': round(input_cost, 8),
                'output_cost': round(output_cost, 8),
                'cache_read_cost': round(cache_read_cost, 8),
                'cache_write_cost': round(cache_write_cost, 8),
                'total_cost': round(total, 8),
                'cumulative_cost': round(self.total_cost, 8),
                'model': model,
                'session_id': session_id
            }
            self._cost_history.append(history_entry)
            # Integrate with MetricsEngine if available
            if self.metrics_engine:
                try:
                    self.metrics_engine.record_cost(
                        cost=total,
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cache_read=cache_read,
                        cache_write=cache_write
                    )
                except Exception as e:
                    logger.debug(f"Failed to record cost in MetricsEngine: {e}")
            return total
    def get_cache_savings(self, cache_read: int, model: str) -> float:
        """
        Calculate savings from cache hits (90% discount).
        Args:
            cache_read: Number of cache read tokens
            model: Model identifier for pricing lookup
        Returns:
            float: Amount saved in USD by using cache
        Example:
            >>> manager = CostManager()
            >>> savings = manager.get_cache_savings(1000, "claude-sonnet-4-20250514")
            >>> print(f"Saved: ${savings:.6f}")
        """
        with self._lock:
            pricing = MODEL_PRICING.get(model, MODEL_PRICING["claude-sonnet-4-20250514"])
            full_price = (cache_read / 1_000_000) * pricing["input"]
            cached_price = (cache_read / 1_000_000) * pricing["cache_read"]
            return full_price - cached_price
    def check_budget_status(self, budget_limit: float) -> Dict[str, Any]:
        """
        Check budget status with soft/hard/emergency threshold warnings.
        Args:
            budget_limit: Budget limit in USD to check against
        Returns:
            Dict[str, Any]: Budget status containing:
                - current_cost: Current total cost
                - budget_limit: The budget limit being checked
                - remaining: Amount remaining in budget
                - usage_pct: Percentage of budget used
                - status: Status string ("ok", "soft_warning", "hard_warning", "emergency")
                - exceeded: Boolean indicating if budget is exceeded
                - message: Human-readable status message
        Raises:
            ValueError: If budget_limit is not positive
        Example:
            >>> manager = CostManager()
            >>> manager.calculate_cost(input_tokens=1000, output_tokens=500)
            >>> status = manager.check_budget_status(budget_limit=10.0)
            >>> if status['status'] != 'ok':
            ... print(f"Warning: {status['message']}")
        """
        if budget_limit <= 0:
            raise ValueError(f"budget_limit must be positive, got {budget_limit}")
        with self._lock:
            usage_pct = (self.total_cost / budget_limit) * 100
            remaining = budget_limit - self.total_cost
            exceeded = self.total_cost >= budget_limit
            # Determine status level
            if usage_pct >= self.emergency_threshold:
                status = "emergency"
                message = f"EMERGENCY: Budget at {usage_pct:.1f}% (${self.total_cost:.4f}/${budget_limit:.2f})"
            elif usage_pct >= self.hard_limit_threshold:
                status = "hard_warning"
                message = f"HARD WARNING: Budget at {usage_pct:.1f}% (${self.total_cost:.4f}/${budget_limit:.2f})"
            elif usage_pct >= self.soft_limit_threshold:
                status = "soft_warning"
                message = f"Soft Warning: Budget at {usage_pct:.1f}% (${self.total_cost:.4f}/${budget_limit:.2f})"
            else:
                status = "ok"
                message = f"Budget OK: {usage_pct:.1f}% used (${self.total_cost:.4f}/${budget_limit:.2f})"
            # Log warnings with cooldown
            if status != "ok":
                current_time = time.time()
                if current_time - self._last_warning_time > self._warning_cooldown:
                    if status == "emergency":
                        logger.error(message)
                    elif status == "hard_warning":
                        logger.warning(message)
                    else:
                        logger.info(message)
                    self._last_warning_time = current_time
            return {
                'current_cost': round(self.total_cost, 6),
                'budget_limit': budget_limit,
                'remaining': round(remaining, 6),
                'usage_pct': round(usage_pct, 2),
                'status': status,
                'exceeded': exceeded,
                'message': message,
                'soft_threshold': self.soft_limit_threshold,
                'hard_threshold': self.hard_limit_threshold,
                'emergency_threshold': self.emergency_threshold
            }
    def project_session_cost(self, estimated_turns: int, avg_input: int = 1000, avg_output: int = 500) -> float:
        """
        Predict future costs based on usage patterns.
        Args:
            estimated_turns: Number of conversation turns to project
            avg_input: Average input tokens per turn (default: 1000)
            avg_output: Average output tokens per turn (default: 500)
        Returns:
            float: Projected cost in USD for estimated turns
        Raises:
            ValueError: If estimated_turns is not positive or token counts are negative
        Example:
            >>> manager = CostManager()
            >>> # Estimate cost for 50 more conversation turns
            >>> projected = manager.project_session_cost(estimated_turns=50)
            >>> print(f"Projected cost: ${projected:.4f}")
        """
        if estimated_turns <= 0:
            raise ValueError(f"estimated_turns must be positive, got {estimated_turns}")
        if avg_input < 0:
            raise ValueError(f"avg_input must be non-negative, got {avg_input}")
        if avg_output < 0:
            raise ValueError(f"avg_output must be non-negative, got {avg_output}")
        with self._lock:
            # If we have history, use actual averages
            if len(self._cost_history) > 0:
                history_list = list(self._cost_history)
                avg_cost_per_turn = sum(entry['total_cost'] for entry in history_list) / len(history_list)
                projected_cost = avg_cost_per_turn * estimated_turns
            else:
                # Use provided averages with default model pricing
                pricing = MODEL_PRICING["claude-sonnet-4-20250514"]
                cost_per_turn = (
                    (avg_input / 1_000_000) * pricing["input"] +
                    (avg_output / 1_000_000) * pricing["output"]
                )
                projected_cost = cost_per_turn * estimated_turns
            return round(projected_cost, 6)
    def get_cost_breakdown(self) -> Dict[str, float]:
        """
        Get cost breakdown by operation type.
        Returns:
            Dict[str, float]: Cost breakdown containing:
                - input: Cost from input tokens
                - output: Cost from output tokens
                - cache_read: Cost from cache read tokens
                - cache_write: Cost from cache write tokens
                - total: Total cost
                - input_pct: Percentage of total from input
                - output_pct: Percentage of total from output
                - cache_read_pct: Percentage of total from cache reads
                - cache_write_pct: Percentage of total from cache writes
        Example:
            >>> manager = CostManager()
            >>> manager.calculate_cost(input_tokens=1000, output_tokens=500)
            >>> breakdown = manager.get_cost_breakdown()
            >>> print(f"Input cost: ${breakdown['input']:.6f} ({breakdown['input_pct']:.1f}%)")
        """
        with self._lock:
            total = self.total_cost if self.total_cost > 0 else 1.0 # Avoid division by zero
            breakdown = {
                'input': round(self._cost_by_operation['input'], 6),
                'output': round(self._cost_by_operation['output'], 6),
                'cache_read': round(self._cost_by_operation['cache_read'], 6),
                'cache_write': round(self._cost_by_operation['cache_write'], 6),
                'total': round(self.total_cost, 6),
                'input_pct': round((self._cost_by_operation['input'] / total) * 100, 2),
                'output_pct': round((self._cost_by_operation['output'] / total) * 100, 2),
                'cache_read_pct': round((self._cost_by_operation['cache_read'] / total) * 100, 2),
                'cache_write_pct': round((self._cost_by_operation['cache_write'] / total) * 100, 2)
            }
            return breakdown
    def calculate_cache_efficiency(self) -> Dict[str, Any]:
        """
        Calculate cache efficiency metrics with 90% savings tracking.
        Returns:
            Dict[str, Any]: Cache efficiency metrics containing:
                - total_cache_savings: Total amount saved from cache usage
                - cache_read_tokens: Total tokens read from cache
                - total_input_tokens: Total input tokens processed
                - cache_hit_rate: Percentage of input tokens served from cache
                - efficiency_score: Overall cache efficiency (0-100)
                - savings_rate: Savings rate (90% for cache hits)
                - message: Human-readable efficiency summary
        Example:
            >>> manager = CostManager()
            >>> manager.calculate_cost(input_tokens=1000, output_tokens=500, cache_read=800)
            >>> efficiency = manager.calculate_cache_efficiency()
            >>> print(f"Cache efficiency: {efficiency['efficiency_score']:.1f}%")
        """
        with self._lock:
            total_input_plus_cache = self._total_input_tokens + self._cache_read_tokens
            if total_input_plus_cache == 0:
                cache_hit_rate = 0.0
                efficiency_score = 0.0
            else:
                cache_hit_rate = (self._cache_read_tokens / total_input_plus_cache) * 100
                # Efficiency score: cache hit rate weighted by savings (90%)
                efficiency_score = cache_hit_rate * 0.9
            message = (
                f"Cache saved ${self._total_cache_savings:.4f} "
                f"({cache_hit_rate:.1f}% hit rate, {efficiency_score:.1f}% efficiency)"
            )
            return {
                'total_cache_savings': round(self._total_cache_savings, 6),
                'cache_read_tokens': self._cache_read_tokens,
                'total_input_tokens': self._total_input_tokens,
                'cache_hit_rate': round(cache_hit_rate, 2),
                'efficiency_score': round(efficiency_score, 2),
                'savings_rate': 90.0, # Cache provides 90% discount
                'message': message
            }
    def aggregate_costs(self, session_ids: List[str]) -> Dict[str, Any]:
        """
        Aggregate costs across multiple sessions.
        Args:
            session_ids: List of session identifiers to aggregate
        Returns:
            Dict[str, Any]: Aggregated cost data containing:
                - session_costs: Dict mapping session_id to cost
                - total_cost: Sum of costs across all sessions
                - avg_cost_per_session: Average cost per session
                - session_count: Number of sessions
                - min_cost: Minimum session cost
                - max_cost: Maximum session cost
        Raises:
            ValueError: If session_ids is empty
        Example:
            >>> manager = CostManager()
            >>> manager.calculate_cost(input_tokens=1000, output_tokens=500, session_id="session_1")
            >>> manager.calculate_cost(input_tokens=1200, output_tokens=600, session_id="session_2")
            >>> aggregated = manager.aggregate_costs(["session_1", "session_2"])
            >>> print(f"Total: ${aggregated['total_cost']:.4f}")
        """
        if not session_ids:
            raise ValueError("session_ids cannot be empty")
        with self._lock:
            session_costs = {}
            for session_id in session_ids:
                session_costs[session_id] = self._session_costs.get(session_id, 0.0)
            costs = list(session_costs.values())
            total = sum(costs)
            count = len(session_ids)
            return {
                'session_costs': {k: round(v, 6) for k, v in session_costs.items()},
                'total_cost': round(total, 6),
                'avg_cost_per_session': round(total / count, 6) if count > 0 else 0.0,
                'session_count': count,
                'min_cost': round(min(costs), 6) if costs else 0.0,
                'max_cost': round(max(costs), 6) if costs else 0.0
            }
    def export_cost_report(self, export_format: str = "json", include_history: bool = True) -> str:
        """
        Export comprehensive cost report in specified format.
        Args:
            export_format: Export format - "json" or "csv"
            include_history: Whether to include detailed history (default: True)
        Returns:
            str: Formatted cost report
        Raises:
            ValueError: If export_format is not supported
        Example:
            >>> manager = CostManager()
            >>> manager.calculate_cost(input_tokens=1000, output_tokens=500)
            >>> json_report = manager.export_cost_report(export_format="json")
            >>> csv_report = manager.export_cost_report(export_format="csv")
        """
        format_lower = export_format.lower()
        if format_lower not in ("json", "csv"):
            raise ValueError(f"Unsupported export format: {export_format}. Use 'json' or 'csv'.")
        with self._lock:
            # Gather all cost data
            breakdown = self.get_cost_breakdown()
            cache_efficiency = self.calculate_cache_efficiency()
            analytics = self._get_analytics()
            report_data = {
                'summary': {
                    'total_cost': round(self.total_cost, 6),
                    'operation_count': self._operation_count,
                    'peak_cost': round(self._peak_cost, 6),
                    'export_timestamp': datetime.now().isoformat(),
                    'uptime_seconds': round(time.time() - self._start_time, 2)
                },
                'cost_breakdown': breakdown,
                'cache_efficiency': cache_efficiency,
                'analytics': analytics,
                'cost_by_model': {k: round(v, 6) for k, v in self.cost_by_model.items()},
                'session_costs': {k: round(v, 6) for k, v in self._session_costs.items()}
            }
            if include_history:
                report_data['history'] = list(self._cost_history)
            if format_lower == "json":
                return json.dumps(report_data, indent=2)
            else: # csv
                output = StringIO()
                writer = csv.writer(output)
                # Write summary section
                writer.writerow(['=== Cost Manager Report ==='])
                writer.writerow(['Metric', 'Value'])
                for key, value in report_data['summary'].items():
                    writer.writerow([key, value])
                # Write cost breakdown
                writer.writerow([])
                writer.writerow(['=== Cost Breakdown ==='])
                writer.writerow(['Operation', 'Cost', 'Percentage'])
                for key in ['input', 'output', 'cache_read', 'cache_write']:
                    writer.writerow([
                        key,
                        f"${breakdown[key]:.6f}",
                        f"{breakdown[key + '_pct']:.2f}%"
                    ])
                # Write cache efficiency
                writer.writerow([])
                writer.writerow(['=== Cache Efficiency ==='])
                writer.writerow(['Metric', 'Value'])
                for key, value in cache_efficiency.items():
                    if key != 'message':
                        writer.writerow([key, value])
                # Write cost by model
                writer.writerow([])
                writer.writerow(['=== Cost by Model ==='])
                writer.writerow(['Model', 'Cost'])
                for model, cost in report_data['cost_by_model'].items():
                    writer.writerow([model, f"${cost:.6f}"])
                # Write history if included
                if include_history and self._cost_history:
                    writer.writerow([])
                    writer.writerow(['=== Cost History ==='])
                    history_list = list(self._cost_history)
                    headers = list(history_list[0].keys())
                    writer.writerow(headers)
                    for entry in history_list:
                        writer.writerow([entry.get(h, '') for h in headers])
                return output.getvalue()
    def _get_analytics(self) -> Dict[str, Any]:
        """
        Calculate comprehensive cost analytics and statistics.
        Returns:
            Dict[str, Any]: Analytics dictionary with various metrics
        """
        uptime = time.time() - self._start_time
        # Calculate averages
        avg_cost = self.total_cost / self._operation_count if self._operation_count > 0 else 0
        cost_per_minute = (self.total_cost / uptime) * 60 if uptime > 0 else 0
        operations_per_minute = (self._operation_count / uptime) * 60 if uptime > 0 else 0
        # Calculate trend
        trend = "stable"
        if len(self._cost_history) >= 6:
            history_list = list(self._cost_history)
            recent_avg = sum(e['total_cost'] for e in history_list[-3:]) / 3
            older_avg = sum(e['total_cost'] for e in history_list[-6:-3]) / 3
            if older_avg > 0:
                if recent_avg > older_avg * 1.2: # 20% increase
                    trend = "increasing"
                elif recent_avg < older_avg * 0.8: # 20% decrease
                    trend = "decreasing"
        return {
            'total_operations': self._operation_count,
            'avg_cost_per_operation': round(avg_cost, 6),
            'cost_per_minute': round(cost_per_minute, 6),
            'operations_per_minute': round(operations_per_minute, 2),
            'uptime_seconds': round(uptime, 2),
            'peak_cost': round(self._peak_cost, 6),
            'trend': trend,
            'current_history_size': len(self._cost_history),
            'max_history_size': self.history_size
        }
    def get_cost_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent cost history.
        Args:
            limit: Maximum number of historical records to return (most recent first)
        Returns:
            List[Dict[str, Any]]: List of cost records
        Raises:
            ValueError: If limit is not positive
        Example:
            >>> manager = CostManager()
            >>> manager.calculate_cost(input_tokens=1000, output_tokens=500)
            >>> history = manager.get_cost_history(limit=5)
            >>> print(f"Last operation cost: ${history[0]['total_cost']:.6f}")
        """
        if limit <= 0:
            raise ValueError(f"limit must be positive, got {limit}")
        with self._lock:
            history_list = list(self._cost_history)
            return history_list[-limit:][::-1] if history_list else []
    def reset(self) -> None:
        """
        Reset all counters and history.
        This method clears:
        - All cost counters
        - Cost by model tracking
        - Operation type costs
        - Token counts
        - Cache efficiency data
        - Session costs
        - Cost history
        - Statistics
        Example:
            >>> manager = CostManager()
            >>> manager.calculate_cost(input_tokens=1000, output_tokens=500)
            >>> manager.reset()
            >>> manager.total_cost
            0.0
        """
        with self._lock:
            self.total_cost = 0.0
            self.cost_by_model.clear()
            self._cost_by_operation = {
                'input': 0.0,
                'output': 0.0,
                'cache_read': 0.0,
                'cache_write': 0.0
            }
            self._tokens_by_operation = {
                'input': 0,
                'output': 0,
                'cache_read': 0,
                'cache_write': 0
            }
            self._total_cache_savings = 0.0
            self._cache_read_tokens = 0
            self._total_input_tokens = 0
            self._session_costs.clear()
            self._cost_history.clear()
            self._operation_count = 0
            self._start_time = time.time()
            self._last_warning_time = 0.0
            self._peak_cost = 0.0
            logger.info("CostManager reset completed")
    def get_summary(self) -> str:
        """
        Get a human-readable summary of current cost status.
        Returns:
            str: Formatted summary string
        Example:
            >>> manager = CostManager()
            >>> manager.calculate_cost(input_tokens=1000, output_tokens=500)
            >>> print(manager.get_summary())
        """
        with self._lock:
            analytics = self._get_analytics()
            breakdown = self.get_cost_breakdown()
            cache_efficiency = self.calculate_cache_efficiency()
            summary_lines = [
                "=== Cost Manager Summary ===",
                f"Total Cost: ${self.total_cost:.6f}",
                f"Total Operations: {self._operation_count}",
                f"Avg Cost/Operation: ${analytics['avg_cost_per_operation']:.6f}",
                f"Peak Cost: ${self._peak_cost:.6f}",
                f"Trend: {analytics['trend'].capitalize()}",
                "",
                "Cost Breakdown:",
                f" Input: ${breakdown['input']:.6f} ({breakdown['input_pct']:.1f}%)",
                f" Output: ${breakdown['output']:.6f} ({breakdown['output_pct']:.1f}%)",
                f" Cache Read: ${breakdown['cache_read']:.6f} ({breakdown['cache_read_pct']:.1f}%)",
                f" Cache Write: ${breakdown['cache_write']:.6f} ({breakdown['cache_write_pct']:.1f}%)",
                "",
                f"Cache Efficiency: {cache_efficiency['efficiency_score']:.1f}%",
                f"Total Savings: ${cache_efficiency['total_cache_savings']:.6f}",
                f"Uptime: {analytics['uptime_seconds']:.0f}s"
            ]
            return "\n".join(summary_lines)
    def __repr__(self) -> str:
        """Return string representation of CostManager."""
        return (
            f"CostManager(operations={self._operation_count}, "
            f"total_cost=${self.total_cost:.6f}, "
            f"models={len(self.cost_by_model)})"
        )
