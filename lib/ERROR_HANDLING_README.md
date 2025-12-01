# Async Error Handling with 3-Strike Protocol
## Overview
This module provides robust error handling for SDK workflow operations using an intelligent 3-strike protocol with fibonacci backoff, error categorization, and circuit breaker protection.
## Features
### Core Components
1. **ThreeStrikeHandler** - Main async error handling class
2. **AsyncCircuitBreaker** - Prevents cascading failures
3. **Error Categorization** - Intelligent error classification
4. **Fibonacci Backoff** - Progressive delay strategy
5. **SDK Integration** - Native support for Claude Agent SDK exceptions
### 3-Strike Protocol
#### Strike 1: Auto-Retry
- **Transient errors** (network, timeout): Immediate retry with fibonacci backoff
- **Rate limits**: Longer backoff (60s default)
- **Fatal errors** (auth, validation): Escalate immediately
#### Strike 2: Intelligent Recovery
- **Rate limits**: Extended backoff with retry
- **Network/API**: Wait for recovery, retry
- **Auth/Validation**: Cannot auto-recover, escalate
#### Strike 3: Escalation
- Call custom escalation callback
- Log detailed error report
- Re-raise exception for caller handling
## API Reference
### Quick Start
```python
from lib.error_handling import retry_with_backoff
async def fetch_data():
    # Your async operation
    return await api.get("/data")
# Simple retry with backoff
result = await retry_with_backoff(fetch_data, max_retries=3)
```
### Advanced Usage
```python
from lib.error_handling import ThreeStrikeHandler, ErrorInfo
async def on_escalate(error_info: ErrorInfo, context):
    logger.error(f"Failed: {error_info.message}")
    # Send alert, update metrics, etc.
handler = ThreeStrikeHandler(
    max_retries=3,
    on_escalate=on_escalate
)
result = await handler.execute_with_retry(
    lambda: my_async_operation(),
    context={"task_id": "12345"}
)
```
### Error Categorization
```python
from lib.error_handling import categorize_error
try:
    await risky_operation()
except Exception as e:
    info = categorize_error(e)
    print(f"Category: {info.category.value}")
    print(f"Severity: {info.severity.value}")
    print(f"Message: {info.message}")
```
## Error Categories
| Category | Examples | Default Severity |
|----------|----------|------------------|
| `NETWORK` | Connection errors, DNS failures | LOW |
| `TIMEOUT` | Operation timeouts | LOW |
| `RATE_LIMIT` | API rate limiting, 429 errors | LOW |
| `AUTH` | Authentication failures, 401/403 | HIGH |
| `VALIDATION` | Invalid input, malformed data | MEDIUM |
| `API` | Server errors, 500/502/503 | MEDIUM |
| `RESOURCE` | File not found, disk errors | MEDIUM |
| `UNKNOWN` | Unclassified errors | MEDIUM |
## SDK-Specific Exceptions
The module automatically handles Claude Agent SDK exceptions:
| SDK Exception | Category | Severity |
|---------------|----------|----------|
| `CLINotFoundError` | VALIDATION | HIGH |
| `ProcessError` (rate limit) | RATE_LIMIT | LOW |
| `ProcessError` (auth) | AUTH | HIGH |
| `ProcessError` (other) | API | MEDIUM |
| `CLIJSONDecodeError` | VALIDATION | MEDIUM |
## Fibonacci Backoff Sequence
| Attempt | Delay |
|---------|-------|
| 1 | 1.0s |
| 2 | 1.0s |
| 3 | 2.0s |
| 4 | 3.0s |
| 5 | 5.0s |
| 6 | 8.0s |
| 7+ | Capped at 30.0s |
## Circuit Breaker
The circuit breaker prevents cascading failures:
- **Threshold**: 5 consecutive failures (configurable)
- **Cooldown**: 60 seconds (configurable)
- **States**: Closed → Open → Half-Open → Closed
```python
handler = ThreeStrikeHandler()
# Circuit breaker automatically managed
for i in range(10):
    try:
        await handler.execute_with_retry(operation)
    except RuntimeError as e:
        if "Circuit breaker is open" in str(e):
            print("Too many failures, waiting for cooldown...")
            break
```
## Integration with Executors
### Pattern 1: Simple Retry
```python
from lib.error_handling import retry_with_backoff
class MyExecutor:
    async def execute(self, task):
        return await retry_with_backoff(
            lambda: self._do_execute(task),
            max_retries=3
        )
```
### Pattern 2: Custom Escalation
```python
from lib.error_handling import ThreeStrikeHandler
class MyExecutor:
    def __init__(self):
        self._error_handler = ThreeStrikeHandler(
            max_retries=3,
            on_escalate=self._handle_escalation
        )
    async def execute(self, task):
        return await self._error_handler.execute_with_retry(
            lambda: self._do_execute(task),
            context={"task": task}
        )
    async def _handle_escalation(self, error_info, context):
        logger.error(f"Task failed: {error_info.message}")
        # Custom handling
```
### Pattern 3: Mixin Class
```python
from lib.executor_integration_example import ErrorHandlingMixin
from .base import BaseExecutor
class OneshotExecutor(ErrorHandlingMixin, BaseExecutor):
    async def execute_async(self, task, system_prompt):
        return await self._with_error_handling(
            lambda: self._do_execute(task, system_prompt),
            context={"task": task}
        )
```
## Testing
Run the test suite to verify functionality:
```bash
cd C:\Users\Ray\.claude\sdk-workflow
python test_error_handling.py
```
Expected output:
```
============================================================
Testing Async Error Handling with 3-Strike Protocol
============================================================
=== Fibonacci Backoff Sequence ===
Attempt 1: 1.0s
...
PASS: Fibonacci sequence correct
=== Transient Error Recovery ===
  Attempt 1...
  Attempt 2...
  Attempt 3...
PASS: Recovered after 3 attempts
...
ALL TESTS PASSED (8.08s)
============================================================
```
## Backward Compatibility
The module maintains full backward compatibility with the existing synchronous `ErrorHandler` class:
```python
from lib.error_handling import with_error_handling
# Synchronous decorator still works
@with_error_handling(max_retries=3)
def sync_operation():
    # Your sync code
    pass
```
## Best Practices
### 1. Choose Appropriate Retry Counts
- **Transient operations**: 3-5 retries
- **Critical operations**: 5-10 retries
- **Non-critical operations**: 1-3 retries
### 2. Use Context for Debugging
```python
await handler.execute_with_retry(
    operation,
    context={
        "task_id": task_id,
        "user_id": user_id,
        "attempt_timestamp": datetime.now()
    }
)
```
### 3. Log Escalations Properly
```python
async def on_escalate(error_info, context):
    logger.error(
        "Operation failed after retries",
        extra={
            "error_category": error_info.category.value,
            "error_severity": error_info.severity.value,
            "context": context,
            "stack_trace": traceback.format_exc()
        }
    )
```
### 4. Monitor Circuit Breaker Status
```python
if handler.circuit_breaker.is_open:
    # Alert, fallback logic, etc.
    await send_alert("Circuit breaker open")
```
## Performance Considerations
### Caching
- Error handlers are lightweight and can be reused
- Circuit breaker state persists across calls
- Create one handler per executor instance
### Async Efficiency
- Uses `asyncio.sleep()` for non-blocking backoff
- Supports concurrent error handling across multiple tasks
- No thread overhead
### Memory
- Error history not retained (stateless)
- Circuit breaker maintains minimal state
- No memory leaks from retry logic
## Troubleshooting
### Circuit Breaker Opens Unexpectedly
- Check failure threshold configuration
- Review error logs for root cause
- Consider if errors are truly transient
### Retries Not Working
- Verify error severity classification
- Check if errors are fatal (HIGH severity)
- Ensure async/await syntax is correct
### Escalation Not Called
- Verify callback is async function
- Check exception is not caught elsewhere
- Ensure handler completes all retries
## Future Enhancements
- [ ] Metrics collection (success/failure rates)
- [ ] Adaptive backoff based on error patterns
- [ ] Distributed circuit breaker (shared state)
- [ ] Telemetry integration
- [ ] Custom retry strategies per error category
## Examples
See `lib/executor_integration_example.py` for complete integration examples.
## License
Part of sdk-workflow package.
