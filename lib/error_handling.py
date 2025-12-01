"""
Error handling with 3-strike protocol for SDK workflow operations.
Implements intelligent retry, recovery, and escalation strategies
for robust error management in automated workflows.
Supports both synchronous and asynchronous execution patterns.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, Tuple, List, Dict, TypeVar, Awaitable
import traceback
import time
import asyncio
# SDK-specific exceptions for better error categorization
try:
    from claude_agent_sdk import CLINotFoundError, ProcessError, CLIJSONDecodeError
    SDK_EXCEPTIONS_AVAILABLE = True
except ImportError:
    # Fallback if SDK not installed
    SDK_EXCEPTIONS_AVAILABLE = False
    CLINotFoundError = type('CLINotFoundError', (Exception,), {})
    ProcessError = type('ProcessError', (Exception,), {})
    CLIJSONDecodeError = type('CLIJSONDecodeError', (Exception,), {})
T = TypeVar("T")
def fibonacci_delay(attempt: int) -> float:
    """Calculate fibonacci-based delay for retries.
    Args:
        attempt: Current attempt number (1-indexed)
    Returns:
        Delay in seconds following fibonacci sequence: 1, 1, 2, 3, 5, 8, 13...
    Examples:
        >>> fibonacci_delay(1)
        1.0
        >>> fibonacci_delay(2)
        1.0
        >>> fibonacci_delay(3)
        2.0
        >>> fibonacci_delay(4)
        3.0
        >>> fibonacci_delay(5)
        5.0
        >>> fibonacci_delay(6)
        8.0
    """
    # Fibonacci: 1, 1, 2, 3, 5, 8, 13...
    if attempt <= 1:
        return 1.0
    elif attempt == 2:
        return 1.0
    a, b = 1.0, 1.0
    for _ in range(attempt - 2):
        a, b = b, a + b
    # Cap at 30 seconds to prevent excessive delays
    return min(b, 30.0)
class ErrorSeverity(Enum):
    """Classification of error severity levels."""
    LOW = "low" # Transient, likely recoverable
    MEDIUM = "medium" # May need intervention
    HIGH = "high" # Critical, needs escalation
    CRITICAL = "critical" # System-level failure
class ErrorCategory(Enum):
    """Classification of error types for routing recovery strategies."""
    NETWORK = "network" # Connection, timeout errors
    RATE_LIMIT = "rate_limit" # API rate limiting
    AUTH = "auth" # Authentication/authorization
    VALIDATION = "validation" # Input/output validation
    RESOURCE = "resource" # File, memory, disk errors
    API = "api" # API-specific errors
    TIMEOUT = "timeout" # Operation timeout
    UNKNOWN = "unknown" # Unclassified errors
@dataclass
class ErrorContext:
    """Context information for error analysis."""
    error: Exception
    attempt: int
    category: ErrorCategory
    severity: ErrorSeverity
    timestamp: datetime = field(default_factory=datetime.now)
    stack_trace: str = ""
    additional_info: Dict[str, Any] = field(default_factory=dict)
@dataclass
class RecoveryStrategy:
    """Strategy for recovering from an error."""
    action: str # "retry", "recover", "escalate"
    delay: float = 0.0
    modified_params: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
@dataclass
class EscalationReport:
    """Detailed report for escalated errors."""
    error_type: str
    error_message: str
    category: ErrorCategory
    severity: ErrorSeverity
    attempts_made: int
    recovery_attempts: List[str]
    stack_trace: str
    timestamp: datetime
    recommendations: List[str]
    context: Dict[str, Any]
class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    Opens circuit after consecutive failures, preventing further attempts
    until cooldown period expires.
    """
    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 60.0):
        """Initialize the circuit breaker.
        Args:
            failure_threshold: Number of consecutive failures before opening circuit
            cooldown_seconds: Time to wait before attempting to close circuit
        """
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.successes = 0
        self.is_open = False
        self.opened_at: Optional[datetime] = None
        self.last_failure: Optional[Exception] = None
    def record_success(self) -> None:
        """Record a successful operation."""
        self.successes += 1
        self.failures = 0
        self.is_open = False
        self.opened_at = None
        self.last_failure = None
    def record_failure(self, error: Optional[Exception] = None) -> None:
        """Record a failed operation.
        Args:
            error: The exception that caused the failure
        """
        self.failures += 1
        self.last_failure = error
        if self.failures >= self.failure_threshold:
            self.is_open = True
            self.opened_at = datetime.now()
    def can_proceed(self) -> bool:
        """Check if operations can proceed.
        Returns:
            True if circuit is closed and operations can proceed,
            False if circuit is open
        """
        if not self.is_open:
            return True
        # Check if cooldown period has elapsed
        if self.opened_at:
            elapsed = (datetime.now() - self.opened_at).total_seconds()
            if elapsed >= self.cooldown_seconds:
                # Half-open state: allow one attempt
                self.is_open = False
                return True
        return False
    def reset(self) -> None:
        """Reset the circuit breaker to initial state."""
        self.failures = 0
        self.successes = 0
        self.is_open = False
        self.opened_at = None
        self.last_failure = None
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the circuit breaker.
        Returns:
            Dictionary with status information
        """
        status = {
            "is_open": self.is_open,
            "failures": self.failures,
            "successes": self.successes,
            "threshold": self.failure_threshold,
        }
        if self.is_open and self.opened_at:
            elapsed = (datetime.now() - self.opened_at).total_seconds()
            remaining = max(0, self.cooldown_seconds - elapsed)
            status["cooldown_remaining"] = remaining
        if self.last_failure:
            status["last_failure"] = str(self.last_failure)
        return status
class ErrorHandler:
    """
    Implements the 3-strike error handling protocol.
    Strike 1: Auto-correct with automated tools
    Strike 2: Analyze and apply targeted fix
    Strike 3: Escalate with detailed report
    """
    def __init__(self, max_retries: int = 3):
        """Initialize the error handler.
        Args:
            max_retries: Maximum number of retry attempts (default: 3)
        """
        self.max_retries = max_retries
        self.error_history: List[ErrorContext] = []
        self.recovery_attempts: List[str] = []
    def handle(self, error: Exception, attempt: int) -> Tuple[str, Any]:
        """
        Handle an error according to the 3-strike protocol.
        Args:
            error: The exception that occurred
            attempt: Current attempt number (1-indexed)
        Returns:
            Tuple of (action, data) where action is one of:
            - ("retry", delay_seconds)
            - ("recover", RecoveryStrategy)
            - ("escalate", EscalationReport)
        """
        # Classify the error
        category = self._categorize_error(error)
        severity = self._assess_severity(error, category, attempt)
        # Build context
        context = ErrorContext(
            error=error,
            attempt=attempt,
            category=category,
            severity=severity,
            stack_trace=traceback.format_exc(),
        )
        self.error_history.append(context)
        # Apply 3-strike protocol
        if attempt == 1:
            # Strike 1: Auto-correct attempt
            return self._strike_one(context)
        elif attempt == 2:
            # Strike 2: Intelligent recovery
            return self._strike_two(context)
        else:
            # Strike 3: Escalate
            return self._strike_three(context)
    def _strike_one(self, context: ErrorContext) -> Tuple[str, Any]:
        """Strike 1: Attempt automatic correction with simple retry."""
        delay = fibonacci_delay(1)
        # For transient errors, simple retry often works
        if context.category in (ErrorCategory.NETWORK, ErrorCategory.TIMEOUT):
            self.recovery_attempts.append("Simple retry after transient error")
            return ("retry", delay)
        # For rate limits, wait longer
        if context.category == ErrorCategory.RATE_LIMIT:
            delay = max(delay, 5.0) # Minimum 5 second wait for rate limits
            self.recovery_attempts.append("Rate limit backoff")
            return ("retry", delay)
        # For other errors, still try once
        self.recovery_attempts.append("Initial retry attempt")
        return ("retry", delay)
    def _strike_two(self, context: ErrorContext) -> Tuple[str, Any]:
        """Strike 2: Analyze error and apply intelligent recovery."""
        strategy = self._intelligent_recovery(context)
        if strategy.action == "retry":
            self.recovery_attempts.append(f"Intelligent recovery: {strategy.message}")
            return ("retry", strategy)
        elif strategy.action == "recover":
            self.recovery_attempts.append(f"Recovery strategy: {strategy.message}")
            return ("recover", strategy)
        else:
            # Even on strike 2, some errors should escalate immediately
            return self._strike_three(context)
    def _strike_three(self, context: ErrorContext) -> Tuple[str, Any]:
        """Strike 3: Escalate with detailed report."""
        report = self._build_escalation_report(context)
        return ("escalate", report)
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize an error based on its type and message."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        # SDK-specific exceptions (if available)
        if SDK_EXCEPTIONS_AVAILABLE:
            if isinstance(error, CLINotFoundError):
                return ErrorCategory.VALIDATION
            if isinstance(error, ProcessError):
                if 'rate limit' in error_str:
                    return ErrorCategory.RATE_LIMIT
                if 'auth' in error_str or 'unauthorized' in error_str:
                    return ErrorCategory.AUTH
                return ErrorCategory.API
            if isinstance(error, CLIJSONDecodeError):
                return ErrorCategory.VALIDATION
        # Network errors
        if any(term in error_str for term in ['connection', 'network', 'unreachable', 'dns']):
            return ErrorCategory.NETWORK
        if 'timeout' in error_str or 'timed out' in error_str:
            return ErrorCategory.TIMEOUT
        # Rate limiting
        if any(term in error_str for term in ['rate limit', 'too many requests', '429']):
            return ErrorCategory.RATE_LIMIT
        # Authentication
        if any(term in error_str for term in ['auth', 'unauthorized', '401', '403', 'permission']):
            return ErrorCategory.AUTH
        # Validation
        if any(term in error_str for term in ['validation', 'invalid', 'malformed', 'schema']):
            return ErrorCategory.VALIDATION
        # Resource errors
        if any(term in error_str for term in ['file not found', 'no such file', 'memory', 'disk']):
            return ErrorCategory.RESOURCE
        # API errors
        if any(term in error_str for term in ['api', '500', '502', '503', 'server error']):
            return ErrorCategory.API
        return ErrorCategory.UNKNOWN
    def _assess_severity(self, error: Exception, category: ErrorCategory, attempt: int) -> ErrorSeverity:
        """Assess the severity of an error."""
        # Critical categories
        if category == ErrorCategory.AUTH:
            return ErrorSeverity.HIGH
        # Escalate severity with attempts
        if attempt >= self.max_retries:
            return ErrorSeverity.HIGH
        # Transient errors start low
        if category in (ErrorCategory.NETWORK, ErrorCategory.TIMEOUT, ErrorCategory.RATE_LIMIT):
            return ErrorSeverity.LOW if attempt == 1 else ErrorSeverity.MEDIUM
        # Validation errors are medium
        if category == ErrorCategory.VALIDATION:
            return ErrorSeverity.MEDIUM
        # Unknown errors are concerning
        if category == ErrorCategory.UNKNOWN:
            return ErrorSeverity.MEDIUM if attempt == 1 else ErrorSeverity.HIGH
        return ErrorSeverity.MEDIUM
    def _intelligent_recovery(self, context: ErrorContext) -> RecoveryStrategy:
        """Apply intelligent recovery based on error analysis."""
        category = context.category
        error_str = str(context.error).lower()
        # Rate limit: exponential backoff
        if category == ErrorCategory.RATE_LIMIT:
            delay = fibonacci_delay(context.attempt) * 2
            return RecoveryStrategy(
                action="retry",
                delay=delay,
                message=f"Rate limit detected, backing off {delay:.1f}s"
            )
        # Network/timeout: retry with longer timeout
        if category in (ErrorCategory.NETWORK, ErrorCategory.TIMEOUT):
            return RecoveryStrategy(
                action="retry",
                delay=fibonacci_delay(context.attempt),
                modified_params={"timeout": 60},
                message="Network issue, retrying with extended timeout"
            )
        # API server errors: wait and retry
        if category == ErrorCategory.API:
            return RecoveryStrategy(
                action="retry",
                delay=fibonacci_delay(context.attempt) * 1.5,
                message="API server error, waiting for recovery"
            )
        # Validation: cannot auto-recover
        if category == ErrorCategory.VALIDATION:
            return RecoveryStrategy(
                action="escalate",
                message="Validation error requires manual intervention"
            )
        # Auth: cannot auto-recover
        if category == ErrorCategory.AUTH:
            return RecoveryStrategy(
                action="escalate",
                message="Authentication error requires credential update"
            )
        # Default: standard retry
        return RecoveryStrategy(
            action="retry",
            delay=fibonacci_delay(context.attempt),
            message="Attempting standard retry"
        )
    def _build_escalation_report(self, context: ErrorContext) -> EscalationReport:
        """Build a detailed escalation report."""
        recommendations = self._generate_recommendations(context)
        return EscalationReport(
            error_type=type(context.error).__name__,
            error_message=str(context.error),
            category=context.category,
            severity=context.severity,
            attempts_made=context.attempt,
            recovery_attempts=self.recovery_attempts.copy(),
            stack_trace=context.stack_trace,
            timestamp=context.timestamp,
            recommendations=recommendations,
            context={
                "error_history_count": len(self.error_history),
                "last_errors": [str(e.error) for e in self.error_history[-3:]],
            }
        )
    def _generate_recommendations(self, context: ErrorContext) -> List[str]:
        """Generate actionable recommendations for the error."""
        recommendations = []
        if context.category == ErrorCategory.AUTH:
            recommendations.extend([
                "Verify API key or credentials are valid",
                "Check if credentials have expired",
                "Ensure proper permissions are granted"
            ])
        elif context.category == ErrorCategory.RATE_LIMIT:
            recommendations.extend([
                "Implement request queuing with rate limiting",
                "Consider upgrading API tier for higher limits",
                "Add caching to reduce API calls"
            ])
        elif context.category == ErrorCategory.NETWORK:
            recommendations.extend([
                "Check network connectivity",
                "Verify DNS resolution",
                "Check if target service is accessible"
            ])
        elif context.category == ErrorCategory.VALIDATION:
            recommendations.extend([
                "Review input data format",
                "Check API documentation for schema changes",
                "Validate data before sending"
            ])
        elif context.category == ErrorCategory.RESOURCE:
            recommendations.extend([
                "Verify file paths exist",
                "Check disk space availability",
                "Review file permissions"
            ])
        else:
            recommendations.extend([
                "Review the stack trace for root cause",
                "Check recent code changes",
                "Consult documentation or support"
            ])
        return recommendations
    def reset(self) -> None:
        """Reset error history for a new operation."""
        self.error_history.clear()
        self.recovery_attempts.clear()
def with_error_handling(
    func: Optional[Callable] = None,
    max_retries: int = 3,
    on_escalate: Optional[Callable[[EscalationReport], Any]] = None
) -> Callable:
    """Decorator to wrap a function with error handling.
    Can be used with or without parameters:
        @with_error_handling
        def my_func():
            ...
        @with_error_handling(max_retries=5)
        def my_func():
            ...
    Args:
        func: Function to wrap (when used without parentheses)
        max_retries: Maximum retry attempts
        on_escalate: Callback when error is escalated
    Returns:
        Wrapped function with error handling
    """
    def decorator(f: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            import inspect
            handler = ErrorHandler(max_retries=max_retries)
            attempt = 0
            # Get function signature to check what params it accepts
            sig = inspect.signature(f)
            while attempt < max_retries:
                attempt += 1
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    action, data = handler.handle(e, attempt)
                    if action == "retry":
                        # Data can be either a float (strike 1) or RecoveryStrategy (strike 2)
                        delay = data if isinstance(data, (int, float)) else data.delay
                        time.sleep(delay)
                        # Apply modified params if available and function accepts them
                        if hasattr(data, 'modified_params') and data.modified_params:
                            for param, value in data.modified_params.items():
                                if param in sig.parameters:
                                    kwargs[param] = value
                        continue
                    elif action == "recover":
                        # Data is RecoveryStrategy
                        if data.modified_params:
                            for param, value in data.modified_params.items():
                                if param in sig.parameters:
                                    kwargs[param] = value
                        time.sleep(data.delay)
                        continue
                    else: # escalate
                        if on_escalate:
                            return on_escalate(data)
                        raise
            # Should not reach here, but just in case
            raise RuntimeError(f"Exhausted all {max_retries} retry attempts")
        return wrapper
    # Support both @with_error_handling and @with_error_handling(...)
    if func is not None:
        return decorator(func)
    return decorator
# ============================================================================
# ASYNC ERROR HANDLING
# ============================================================================
class AsyncCircuitBreaker:
    """
    Async-aware circuit breaker pattern to prevent cascading failures.
    Opens circuit after consecutive failures, preventing further attempts
    until cooldown period expires.
    """
    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 60.0):
        """Initialize the async circuit breaker.
        Args:
            failure_threshold: Number of consecutive failures before opening circuit
            cooldown_seconds: Time to wait before attempting to close circuit
        """
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.successes = 0
        self.is_open = False
        self.opened_at: Optional[datetime] = None
        self.last_failure: Optional[Exception] = None
    def record_success(self) -> None:
        """Record a successful operation."""
        self.successes += 1
        self.failures = 0
        self.is_open = False
        self.opened_at = None
        self.last_failure = None
    def record_failure(self, error: Optional[Exception] = None) -> None:
        """Record a failed operation.
        Args:
            error: The exception that caused the failure
        """
        self.failures += 1
        self.last_failure = error
        if self.failures >= self.failure_threshold:
            self.is_open = True
            self.opened_at = datetime.now()
    def can_proceed(self) -> bool:
        """Check if operations can proceed.
        Returns:
            True if circuit is closed and operations can proceed,
            False if circuit is open
        """
        if not self.is_open:
            return True
        # Check if cooldown period has elapsed
        if self.opened_at:
            elapsed = (datetime.now() - self.opened_at).total_seconds()
            if elapsed >= self.cooldown_seconds:
                # Half-open state: allow one attempt
                self.is_open = False
                return True
        return False
    def reset(self) -> None:
        """Reset the circuit breaker to initial state."""
        self.failures = 0
        self.successes = 0
        self.is_open = False
        self.opened_at = None
        self.last_failure = None
@dataclass
class ErrorInfo:
    """Information about a categorized error."""
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    original_error: Optional[Exception] = None
    retry_after: Optional[float] = None
def categorize_error(error: Exception) -> ErrorInfo:
    """Categorize an error for appropriate handling (async-compatible version).
    Args:
        error: The exception to categorize
    Returns:
        ErrorInfo with category, severity, and handling guidance
    """
    # SDK-specific exceptions
    if SDK_EXCEPTIONS_AVAILABLE:
        if isinstance(error, CLINotFoundError):
            return ErrorInfo(
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.HIGH,
                message="Claude CLI not found. Please install Claude Code.",
                original_error=error
            )
        if isinstance(error, ProcessError):
            if "rate limit" in str(error).lower():
                return ErrorInfo(
                    category=ErrorCategory.RATE_LIMIT,
                    severity=ErrorSeverity.LOW,
                    message="Rate limit hit. Will retry with backoff.",
                    original_error=error,
                    retry_after=60.0
                )
            if "authentication" in str(error).lower() or "unauthorized" in str(error).lower():
                return ErrorInfo(
                    category=ErrorCategory.AUTH,
                    severity=ErrorSeverity.HIGH,
                    message="Authentication failed. Check API key.",
                    original_error=error
                )
            return ErrorInfo(
                category=ErrorCategory.API,
                severity=ErrorSeverity.MEDIUM,
                message=f"Process error: {error}",
                original_error=error
            )
        if isinstance(error, CLIJSONDecodeError):
            return ErrorInfo(
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.MEDIUM,
                message="Invalid JSON response from CLI.",
                original_error=error
            )
    # Standard exceptions
    error_str = str(error).lower()
    if isinstance(error, asyncio.TimeoutError) or 'timeout' in error_str:
        return ErrorInfo(
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.LOW,
            message="Request timed out.",
            original_error=error
        )
    if any(term in error_str for term in ['connection', 'network', 'unreachable']):
        return ErrorInfo(
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.LOW,
            message="Network error occurred.",
            original_error=error
        )
    if any(term in error_str for term in ['rate limit', 'too many requests', '429']):
        return ErrorInfo(
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.LOW,
            message="Rate limit exceeded.",
            original_error=error,
            retry_after=60.0
        )
    if any(term in error_str for term in ['auth', 'unauthorized', '401', '403']):
        return ErrorInfo(
            category=ErrorCategory.AUTH,
            severity=ErrorSeverity.HIGH,
            message="Authentication error.",
            original_error=error
        )
    if any(term in error_str for term in ['validation', 'invalid', 'malformed']):
        return ErrorInfo(
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message="Validation error.",
            original_error=error
        )
    # Default unknown error
    return ErrorInfo(
        category=ErrorCategory.UNKNOWN,
        severity=ErrorSeverity.MEDIUM,
        message=str(error),
        original_error=error
    )
class ThreeStrikeHandler:
    """
    Async 3-Strike Error Protocol implementation.
    Strike 1: Auto-retry with fibonacci backoff (transient errors)
    Strike 2: Intelligent recovery based on error type
    Strike 3: Escalate to user/caller with detailed report
    """
    def __init__(
        self,
        max_retries: int = 3,
        on_escalate: Optional[Callable[[ErrorInfo, Any], Awaitable[None]]] = None
    ):
        """Initialize the three-strike handler.
        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            on_escalate: Async callback when error is escalated (Strike 3)
        """
        self.max_retries = max_retries
        self.on_escalate = on_escalate
        self.circuit_breaker = AsyncCircuitBreaker()
    async def execute_with_retry(
        self,
        func: Callable[[], Awaitable[T]],
        context: Any = None
    ) -> T:
        """Execute async function with 3-strike retry protocol.
        Args:
            func: Async function to execute
            context: Optional context passed to escalation callback
        Returns:
            Result from successful execution
        Raises:
            RuntimeError: If circuit breaker is open
            Exception: Re-raises exception after all retries exhausted
        """
        if not self.circuit_breaker.can_proceed():
            raise RuntimeError("Circuit breaker is open. Too many recent failures.")
        last_error_info: Optional[ErrorInfo] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = await func()
                self.circuit_breaker.record_success()
                return result
            except Exception as e:
                error_info = categorize_error(e)
                last_error_info = error_info
                # Strike 1: Auto-retry with backoff (transient errors)
                if attempt == 1:
                    if error_info.severity == ErrorSeverity.LOW:
                        delay = error_info.retry_after or fibonacci_delay(attempt)
                        await asyncio.sleep(delay)
                        continue
                    elif error_info.severity == ErrorSeverity.HIGH:
                        # Fatal errors don't retry
                        self.circuit_breaker.record_failure(e)
                        if self.on_escalate:
                            await self.on_escalate(error_info, context)
                        raise
                # Strike 2: Intelligent recovery
                if attempt == 2:
                    recovery_success = await self._attempt_recovery(error_info, context)
                    if recovery_success:
                        continue
                    elif error_info.severity == ErrorSeverity.HIGH:
                        # Don't continue with fatal errors
                        self.circuit_breaker.record_failure(e)
                        if self.on_escalate:
                            await self.on_escalate(error_info, context)
                        raise
                # Strike 3: Escalate
                if attempt == 3:
                    self.circuit_breaker.record_failure(e)
                    if self.on_escalate:
                        await self.on_escalate(error_info, context)
                    raise
                # Standard backoff between attempts
                delay = fibonacci_delay(attempt)
                await asyncio.sleep(delay)
        # Should not reach here, but just in case
        if last_error_info and last_error_info.original_error:
            raise last_error_info.original_error
        raise RuntimeError(f"All {self.max_retries} attempts failed")
    async def _attempt_recovery(
        self,
        error_info: ErrorInfo,
        context: Any
    ) -> bool:
        """Attempt intelligent recovery based on error type.
        Args:
            error_info: Categorized error information
            context: Execution context
        Returns:
            True if recovery may have succeeded, False otherwise
        """
        if error_info.category == ErrorCategory.RATE_LIMIT:
            # Wait longer for rate limits
            delay = error_info.retry_after or 60.0
            await asyncio.sleep(delay)
            return True
        if error_info.category == ErrorCategory.TIMEOUT:
            # For timeouts, waiting may help server recover
            await asyncio.sleep(fibonacci_delay(2))
            return True
        if error_info.category in (ErrorCategory.NETWORK, ErrorCategory.API):
            # Network/API issues may be transient
            await asyncio.sleep(fibonacci_delay(2))
            return True
        # Cannot auto-recover from validation/auth errors
        return False
async def retry_with_backoff(
    func: Callable[[], Awaitable[T]],
    max_retries: int = 3
) -> T:
    """Simple async retry with fibonacci backoff.
    Convenience function for basic retry logic without custom escalation.
    Args:
        func: Async function to execute
        max_retries: Maximum retry attempts
    Returns:
        Result from successful execution
    Example:
        >>> async def fetch_data():
        ... return await api.get("/data")
        >>> result = await retry_with_backoff(fetch_data, max_retries=5)
    """
    handler = ThreeStrikeHandler(max_retries=max_retries)
    return await handler.execute_with_retry(func)
