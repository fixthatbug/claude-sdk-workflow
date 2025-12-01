"""
Test script for async error handling with 3-strike protocol.
Demonstrates fibonacci backoff and error categorization.
"""
import asyncio
import time
from lib.error_handling import (
    ThreeStrikeHandler,
    retry_with_backoff,
    categorize_error,
    ErrorCategory,
    ErrorSeverity,
    fibonacci_delay,
)
async def test_fibonacci_backoff():
    """Test fibonacci delay sequence."""
    print("\n=== Fibonacci Backoff Sequence ===")
    for attempt in range(1, 9):
        delay = fibonacci_delay(attempt)
        print(f"Attempt {attempt}: {delay:.1f}s")
    assert fibonacci_delay(1) == 1.0
    assert fibonacci_delay(3) == 2.0
    assert fibonacci_delay(5) == 5.0
    print("PASS: Fibonacci sequence correct")
async def test_transient_error_recovery():
    """Test recovery from transient errors."""
    print("\n=== Transient Error Recovery ===")
    attempt_count = 0
    async def flaky_operation():
        nonlocal attempt_count
        attempt_count += 1
        print(f" Attempt {attempt_count}...")
        if attempt_count < 3:
            raise asyncio.TimeoutError("Simulated timeout")
        return "Success!"
    result = await retry_with_backoff(flaky_operation, max_retries=3)
    assert result == "Success!"
    assert attempt_count == 3
    print(f"PASS: Recovered after {attempt_count} attempts")
async def test_error_categorization():
    """Test error categorization logic."""
    print("\n=== Error Categorization ===")
    # Test different error types
    test_cases = [
        (asyncio.TimeoutError("Connection timed out"), ErrorCategory.TIMEOUT, ErrorSeverity.LOW),
        (Exception("Rate limit exceeded"), ErrorCategory.RATE_LIMIT, ErrorSeverity.LOW),
        (Exception("Authentication failed"), ErrorCategory.AUTH, ErrorSeverity.HIGH),
        (Exception("Invalid JSON"), ErrorCategory.VALIDATION, ErrorSeverity.MEDIUM),
    ]
    for error, expected_category, expected_severity in test_cases:
        info = categorize_error(error)
        assert info.category == expected_category, f"Expected {expected_category}, got {info.category}"
        assert info.severity == expected_severity, f"Expected {expected_severity}, got {info.severity}"
        print(f" {type(error).__name__}: {info.category.value} (severity: {info.severity.value})")
    print("PASS: All errors categorized correctly")
async def test_escalation_callback():
    """Test escalation callback on Strike 3."""
    print("\n=== Escalation Callback ===")
    escalation_called = False
    escalation_info = None
    async def on_escalate(error_info, context):
        nonlocal escalation_called, escalation_info
        escalation_called = True
        escalation_info = error_info
        print(f" ESCALATED: {error_info.message}")
        print(f" Category: {error_info.category.value}")
        print(f" Severity: {error_info.severity.value}")
    handler = ThreeStrikeHandler(max_retries=3, on_escalate=on_escalate)
    async def failing_operation():
        raise Exception("Persistent failure")
    try:
        await handler.execute_with_retry(failing_operation, context={"task": "test"})
    except Exception as e:
        pass # Expected to fail
    assert escalation_called, "Escalation callback should have been called"
    assert escalation_info is not None
    print("PASS: Escalation callback triggered correctly")
async def test_circuit_breaker():
    """Test circuit breaker functionality."""
    print("\n=== Circuit Breaker ===")
    handler = ThreeStrikeHandler(max_retries=3)
    # Modify circuit breaker threshold for testing
    handler.circuit_breaker.failure_threshold = 2
    async def always_fails():
        raise Exception("Simulated failure")
    # First failure
    try:
        await handler.execute_with_retry(always_fails)
    except:
        pass
    print(f" Failures: {handler.circuit_breaker.failures}")
    # Second failure (should open circuit)
    handler_2 = ThreeStrikeHandler(max_retries=3)
    handler_2.circuit_breaker.failure_threshold = 2
    handler_2.circuit_breaker.failures = 1 # Simulate previous failure
    try:
        await handler_2.execute_with_retry(always_fails)
    except:
        pass
    print(f" Circuit open: {handler_2.circuit_breaker.is_open}")
    assert handler_2.circuit_breaker.is_open
    print("PASS: Circuit breaker opens after threshold")
async def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Async Error Handling with 3-Strike Protocol")
    print("=" * 60)
    start = time.time()
    try:
        await test_fibonacci_backoff()
        await test_transient_error_recovery()
        await test_error_categorization()
        await test_escalation_callback()
        await test_circuit_breaker()
        elapsed = time.time() - start
        print("\n" + "=" * 60)
        print(f"ALL TESTS PASSED ({elapsed:.2f}s)")
        print("=" * 60)
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        raise
if __name__ == "__main__":
    asyncio.run(main())
