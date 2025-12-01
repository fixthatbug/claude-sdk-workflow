"""Token management with advanced tracking, analytics, and rate limiting."""
import csv
import json
import logging
import threading
import time
from collections import deque
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional, Set, Tuple
logger = logging.getLogger(__name__)
class TokenManagerException(Exception):
    """Base exception for TokenManager errors."""
    pass
class RateLimitExceeded(TokenManagerException):
    """Raised when rate limit is exceeded."""
    pass
class TokenManager:
    """
    Manages token tracking with deduplication, analytics, and rate limiting.
    This class provides comprehensive token management including:
    - Basic token tracking with deduplication
    - Context window overflow detection
    - Token usage history tracking
    - Rate limiting per time window
    - Usage analytics and statistics
    - Export functionality (JSON/CSV)
    - Thread-safe operations
    Attributes:
        context_window_limit (int): Maximum context window size in tokens
        input_tokens (int): Total input tokens processed
        output_tokens (int): Total output tokens generated
        cache_read_tokens (int): Total cache read tokens
        cache_write_tokens (int): Total cache write tokens
        overflow_warning_threshold (float): Percentage threshold for warnings (default: 80%)
    Example:
        >>> manager = TokenManager(context_window_limit=200000)
        >>> manager.update_tokens(input_tokens=100, output_tokens=50)
        >>> analytics = manager.get_analytics()
        >>> print(f"Average tokens per request: {analytics['avg_total_per_request']}")
    """
    def __init__(
        self,
        context_window_limit: int = 200000,
        history_size: int = 100,
        overflow_warning_threshold: float = 80.0,
        metrics_engine: Optional[Any] = None
    ):
        """
        Initialize TokenManager with configurable limits and options.
        Args:
            context_window_limit: Maximum context window size in tokens
            history_size: Maximum number of historical records to maintain
            overflow_warning_threshold: Percentage threshold for overflow warnings (0-100)
            metrics_engine: Optional MetricsEngine instance for integration
        Raises:
            ValueError: If context_window_limit <= 0 or overflow_warning_threshold not in 0-100
        """
        if context_window_limit <= 0:
            raise ValueError("context_window_limit must be positive")
        if not 0 <= overflow_warning_threshold <= 100:
            raise ValueError("overflow_warning_threshold must be between 0 and 100")
        # Basic token counters
        self.context_window_limit = context_window_limit
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read_tokens = 0
        self.cache_write_tokens = 0
        self.processed_message_ids: Set[str] = set()
        # Advanced features
        self.overflow_warning_threshold = overflow_warning_threshold
        self.history_size = history_size
        self.metrics_engine = metrics_engine
        # Thread safety - using RLock to prevent deadlock on reentrant calls
        self._lock = threading.RLock()
        # Usage history tracking - stores dicts with timestamp and token counts
        self._usage_history: deque = deque(maxlen=history_size)
        # Message ID deduplication with bounded memory
        self._max_message_ids = 10000
        self._message_id_deque: deque = deque(maxlen=self._max_message_ids)
        # Statistics
        self._request_count = 0
        self._start_time = time.time()
        self._last_warning_time = 0.0
        self._warning_cooldown = 60.0 # Seconds between duplicate warnings
        self._peak_usage_pct = 0.0 # Track peak context usage
    def update_tokens(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read: int = 0,
        cache_write: int = 0,
        message_id: Optional[str] = None
    ) -> bool:
        """
        Update token counts with deduplication and overflow detection.
        Args:
            input_tokens: Number of input tokens to add
            output_tokens: Number of output tokens to add
            cache_read: Number of cache read tokens to add
            cache_write: Number of cache write tokens to add
            message_id: Optional unique message identifier for deduplication
        Returns:
            bool: True if tokens were updated, False if message was already processed
        Raises:
            ValueError: If any token count is negative
        Example:
            >>> manager = TokenManager()
            >>> manager.update_tokens(input_tokens=100, output_tokens=50, message_id="msg_123")
            True
            >>> manager.update_tokens(input_tokens=100, output_tokens=50, message_id="msg_123")
            False
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
            # Deduplication check
            if message_id and message_id in self.processed_message_ids:
                return False
            if message_id:
                # Bounded message ID tracking to prevent unbounded memory growth
                if len(self.processed_message_ids) >= self._max_message_ids:
                    oldest_id = self._message_id_deque[0]
                    self.processed_message_ids.discard(oldest_id)
                self.processed_message_ids.add(message_id)
                self._message_id_deque.append(message_id)
            # Update counters
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.cache_read_tokens += cache_read
            self.cache_write_tokens += cache_write
            self._request_count += 1
            # Record in history with all token types included in total
            history_entry = {
                'timestamp': time.time(),
                'datetime': datetime.now().isoformat(),
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cache_read_tokens': cache_read,
                'cache_write_tokens': cache_write,
                'total_tokens': input_tokens + output_tokens + cache_read + cache_write,
                'message_id': message_id,
                'cumulative_input': self.input_tokens,
                'cumulative_output': self.output_tokens,
                'context_usage_pct': self.get_context_usage_pct()
            }
            self._usage_history.append(history_entry)
            # Check for overflow warnings and update peak usage
            usage_pct = self.get_context_usage_pct()
            if usage_pct > self._peak_usage_pct:
                self._peak_usage_pct = usage_pct
            if usage_pct >= self.overflow_warning_threshold:
                current_time = time.time()
                if current_time - self._last_warning_time > self._warning_cooldown:
                    logger.warning(
                        f"Context window usage at {usage_pct:.1f}% "
                        f"({self.input_tokens + self.output_tokens}/{self.context_window_limit} tokens). "
                        f"Approaching limit!"
                    )
                    self._last_warning_time = current_time
            # Integrate with MetricsEngine if available
            if self.metrics_engine:
                try:
                    self.metrics_engine.record_token_usage(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cache_read=cache_read,
                        cache_write=cache_write
                    )
                except Exception as e:
                    logger.debug(f"Failed to record tokens in MetricsEngine: {e}")
            return True
    def get_context_usage_pct(self) -> float:
        """
        Get context window usage percentage.
        Returns:
            float: Percentage of context window used (0-100+)
        Example:
            >>> manager = TokenManager(context_window_limit=1000)
            >>> manager.update_tokens(input_tokens=300, output_tokens=200)
            >>> manager.get_context_usage_pct()
            50.0
        """
        with self._lock:
            total = self.input_tokens + self.output_tokens
            return (total / self.context_window_limit) * 100
    def predict_overflow(self, estimated_tokens: int) -> Tuple[bool, float]:
        """
        Predict if adding estimated tokens would cause overflow.
        Args:
            estimated_tokens: Number of tokens expected to be added
        Returns:
            Tuple[bool, float]: (will_overflow, resulting_usage_pct)
                - will_overflow: True if adding tokens would exceed limit
                - resulting_usage_pct: Predicted usage percentage after addition
        Raises:
            ValueError: If estimated_tokens is negative
        Example:
            >>> manager = TokenManager(context_window_limit=1000)
            >>> manager.update_tokens(input_tokens=900)
            >>> will_overflow, pct = manager.predict_overflow(200)
            >>> print(f"Overflow: {will_overflow}, Usage: {pct:.1f}%")
            Overflow: True, Usage: 110.0%
        """
        if estimated_tokens < 0:
            raise ValueError(f"estimated_tokens must be non-negative, got {estimated_tokens}")
        with self._lock:
            current_total = self.input_tokens + self.output_tokens
            predicted_total = current_total + estimated_tokens
            predicted_pct = (predicted_total / self.context_window_limit) * 100
            will_overflow = predicted_total > self.context_window_limit
            return will_overflow, predicted_pct
    def get_usage_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent token usage history.
        Args:
            limit: Maximum number of historical records to return (most recent first)
        Returns:
            List[Dict[str, Any]]: List of usage records, each containing:
                - timestamp: Unix timestamp
                - datetime: ISO format datetime string
                - input_tokens: Input tokens for this request
                - output_tokens: Output tokens for this request
                - cache_read_tokens: Cache read tokens
                - cache_write_tokens: Cache write tokens
                - total_tokens: Total tokens for this request
                - message_id: Message identifier if available
                - cumulative_input: Total input tokens at this point
                - cumulative_output: Total output tokens at this point
                - context_usage_pct: Context usage percentage at this point
        Raises:
            ValueError: If limit is not positive
        Example:
            >>> manager = TokenManager()
            >>> manager.update_tokens(input_tokens=100, output_tokens=50)
            >>> history = manager.get_usage_history(limit=5)
            >>> print(f"Last request used {history[0]['total_tokens']} tokens")
        """
        if limit <= 0:
            raise ValueError(f"limit must be positive, got {limit}")
        with self._lock:
            # Return most recent entries first
            history_list = list(self._usage_history)
            return history_list[-limit:][::-1] if history_list else []
    def check_rate_limit(self, window_seconds: int, max_tokens: int) -> bool:
        """
        Check if token usage exceeds rate limit within time window.
        Args:
            window_seconds: Time window in seconds to check
            max_tokens: Maximum tokens allowed in the time window
        Returns:
            bool: True if within rate limit, False if limit exceeded
        Raises:
            ValueError: If window_seconds or max_tokens are not positive
        Example:
            >>> manager = TokenManager()
            >>> manager.update_tokens(input_tokens=100, output_tokens=50)
            >>> # Check if we've used more than 1000 tokens in last 60 seconds
            >>> within_limit = manager.check_rate_limit(window_seconds=60, max_tokens=1000)
            >>> if not within_limit:
            ... print("Rate limit exceeded!")
        """
        if window_seconds <= 0:
            raise ValueError(f"window_seconds must be positive, got {window_seconds}")
        if max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {max_tokens}")
        with self._lock:
            current_time = time.time()
            cutoff_time = current_time - window_seconds
            # Sum tokens from requests within the time window
            tokens_in_window = 0
            for entry in self._usage_history:
                if entry['timestamp'] >= cutoff_time:
                    tokens_in_window += entry['total_tokens']
            within_limit = tokens_in_window <= max_tokens
            if not within_limit:
                logger.warning(
                    f"Rate limit check: {tokens_in_window} tokens used in last "
                    f"{window_seconds}s (limit: {max_tokens})"
                )
            return within_limit
    def get_analytics(self) -> Dict[str, Any]:
        """
        Calculate comprehensive usage analytics and statistics.
        Returns:
            Dict[str, Any]: Analytics dictionary containing:
                - total_requests: Total number of requests processed
                - total_input_tokens: Total input tokens
                - total_output_tokens: Total output tokens
                - total_cache_read_tokens: Total cache read tokens
                - total_cache_write_tokens: Total cache write tokens
                - total_tokens: Sum of input and output tokens
                - avg_input_per_request: Average input tokens per request
                - avg_output_per_request: Average output tokens per request
                - avg_total_per_request: Average total tokens per request
                - context_usage_pct: Current context window usage percentage
                - uptime_seconds: Time since manager initialization
                - requests_per_minute: Request rate
                - tokens_per_minute: Token processing rate
                - peak_usage_pct: Highest context usage reached
                - current_history_size: Number of entries in history
                - trend: Usage trend ("increasing", "decreasing", "stable")
        Example:
            >>> manager = TokenManager()
            >>> manager.update_tokens(input_tokens=100, output_tokens=50)
            >>> analytics = manager.get_analytics()
            >>> print(f"Total tokens: {analytics['total_tokens']}")
            >>> print(f"Avg per request: {analytics['avg_total_per_request']:.1f}")
        """
        with self._lock:
            total_tokens = self.input_tokens + self.output_tokens
            uptime = time.time() - self._start_time
            # Calculate averages
            avg_input = self.input_tokens / self._request_count if self._request_count > 0 else 0
            avg_output = self.output_tokens / self._request_count if self._request_count > 0 else 0
            avg_total = total_tokens / self._request_count if self._request_count > 0 else 0
            # Calculate rates
            requests_per_min = (self._request_count / uptime) * 60 if uptime > 0 else 0
            tokens_per_min = (total_tokens / uptime) * 60 if uptime > 0 else 0
            # Use dedicated peak usage tracker
            peak_usage = self._peak_usage_pct
            # Calculate trend (compare recent vs older history)
            trend = "stable"
            if len(self._usage_history) >= 6:
                history_list = list(self._usage_history)
                recent_avg = sum(e['total_tokens'] for e in history_list[-3:]) / 3
                older_avg = sum(e['total_tokens'] for e in history_list[-6:-3]) / 3
                if recent_avg > older_avg * 1.2: # 20% increase
                    trend = "increasing"
                elif recent_avg < older_avg * 0.8: # 20% decrease
                    trend = "decreasing"
            analytics = {
                'total_requests': self._request_count,
                'total_input_tokens': self.input_tokens,
                'total_output_tokens': self.output_tokens,
                'total_cache_read_tokens': self.cache_read_tokens,
                'total_cache_write_tokens': self.cache_write_tokens,
                'total_tokens': total_tokens,
                'avg_input_per_request': round(avg_input, 2),
                'avg_output_per_request': round(avg_output, 2),
                'avg_total_per_request': round(avg_total, 2),
                'context_usage_pct': round(self.get_context_usage_pct(), 2),
                'context_window_limit': self.context_window_limit,
                'uptime_seconds': round(uptime, 2),
                'requests_per_minute': round(requests_per_min, 2),
                'tokens_per_minute': round(tokens_per_min, 2),
                'peak_usage_pct': round(peak_usage, 2),
                'current_history_size': len(self._usage_history),
                'max_history_size': self.history_size,
                'trend': trend,
                'overflow_warning_threshold': self.overflow_warning_threshold
            }
            return analytics
    def export_metrics(self, export_format: str = "json") -> str:
        """
        Export token metrics in specified format.
        Args:
            export_format: Export format - "json" or "csv"
        Returns:
            str: Formatted metrics data
        Raises:
            ValueError: If export_format is not "json" or "csv"
        Example:
            >>> manager = TokenManager()
            >>> manager.update_tokens(input_tokens=100, output_tokens=50)
            >>> json_data = manager.export_metrics(export_format="json")
            >>> csv_data = manager.export_metrics(export_format="csv")
        """
        format_lower = export_format.lower()
        if format_lower not in ("json", "csv"):
            raise ValueError(f"Unsupported export format: {export_format}. Use 'json' or 'csv'.")
        with self._lock:
            analytics = self.get_analytics()
            history = list(self._usage_history)
            export_data = {
                'analytics': analytics,
                'history': history,
                'export_timestamp': datetime.now().isoformat(),
                'export_unix_time': time.time()
            }
            if format_lower == "json":
                return json.dumps(export_data, indent=2)
            else: # csv
                output = StringIO()
                # Write analytics section
                writer = csv.writer(output)
                writer.writerow(['=== Token Manager Analytics ==='])
                writer.writerow(['Metric', 'Value'])
                for key, value in analytics.items():
                    writer.writerow([key, value])
                writer.writerow([]) # Blank row
                writer.writerow(['=== Usage History ==='])
                # Write history section
                if history:
                    headers = list(history[0].keys())
                    writer.writerow(headers)
                    for entry in history:
                        writer.writerow([entry.get(h, '') for h in headers])
                else:
                    writer.writerow(['No history available'])
                return output.getvalue()
    def reset(self) -> None:
        """
        Reset all counters and history.
        This method clears:
        - All token counters (input, output, cache)
        - Processed message IDs
        - Usage history
        - Request count and statistics
        - Peak usage tracking
        Example:
            >>> manager = TokenManager()
            >>> manager.update_tokens(input_tokens=100)
            >>> manager.reset()
            >>> manager.input_tokens
            0
        """
        with self._lock:
            self.input_tokens = 0
            self.output_tokens = 0
            self.cache_read_tokens = 0
            self.cache_write_tokens = 0
            self.processed_message_ids.clear()
            self._message_id_deque.clear()
            self._usage_history.clear()
            self._request_count = 0
            self._start_time = time.time()
            self._last_warning_time = 0.0
            self._peak_usage_pct = 0.0
            logger.info("TokenManager reset completed")
    def get_summary(self) -> str:
        """
        Get a human-readable summary of current token usage.
        Returns:
            str: Formatted summary string
        Example:
            >>> manager = TokenManager()
            >>> manager.update_tokens(input_tokens=100, output_tokens=50)
            >>> print(manager.get_summary())
        """
        with self._lock:
            analytics = self.get_analytics()
            summary_lines = [
                "=== Token Manager Summary ===",
                f"Total Requests: {analytics['total_requests']}",
                f"Input Tokens: {analytics['total_input_tokens']:,}",
                f"Output Tokens: {analytics['total_output_tokens']:,}",
                f"Total Tokens: {analytics['total_tokens']:,}",
                f"Context Usage: {analytics['context_usage_pct']:.1f}%",
                f"Avg Tokens/Request: {analytics['avg_total_per_request']:.1f}",
                f"Trend: {analytics['trend'].capitalize()}",
                f"Uptime: {analytics['uptime_seconds']:.0f}s"
            ]
            return "\n".join(summary_lines)
    def __repr__(self) -> str:
        """Return string representation of TokenManager."""
        return (
            f"TokenManager(requests={self._request_count}, "
            f"tokens={self.input_tokens + self.output_tokens}, "
            f"usage={self.get_context_usage_pct():.1f}%)"
        )
