"""
Library module for sdk-workflow.
Contains utility functions and shared components:
    - logging: Structured logging configuration
    - errors: Custom exception classes
    - utils: Helper functions and path handling
    - error_handling: 3-strike error protocol
    - validators: Input validation utilities
These are internal utilities used across the package.
"""
# Import from utils module
from .utils import (
    get_workflow_dir,
    get_sessions_dir,
    get_logs_dir,
    get_cache_dir,
    get_resources_dir,
    ensure_dirs,
    format_cost,
    format_tokens,
    format_duration,
    truncate_text,
    safe_path,
    get_session_file,
    generate_session_id,
    get_env_or_default,
    sanitize_filename,
    get_sdk_workflow_path,
    ensure_directory,
    safe_json_loads,
    hash_content,
    parse_model_name,
)
# Import from error_handling module
from .error_handling import (
    ErrorHandler,
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
    RecoveryStrategy,
    EscalationReport,
    CircuitBreaker,
    fibonacci_delay,
    with_error_handling,
)
__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    # Exceptions
    "SDKWorkflowError",
    "ExecutionError",
    "SessionError",
    "ValidationError",
    # Utils
    "get_workflow_dir",
    "get_sessions_dir",
    "get_logs_dir",
    "get_cache_dir",
    "get_resources_dir",
    "ensure_dirs",
    "format_cost",
    "format_tokens",
    "format_duration",
    "truncate_text",
    "safe_path",
    "get_session_file",
    "generate_session_id",
    "get_env_or_default",
    "sanitize_filename",
    "get_sdk_workflow_path",
    "ensure_directory",
    "safe_json_loads",
    "hash_content",
    "parse_model_name",
    # Error handling
    "ErrorHandler",
    "ErrorSeverity",
    "ErrorCategory",
    "ErrorContext",
    "RecoveryStrategy",
    "EscalationReport",
    "CircuitBreaker",
    "fibonacci_delay",
    "with_error_handling",
]
def setup_logging(level: str = "INFO", format: str = None):
    """
    Configure logging for sdk-workflow.
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        format: Custom log format string.
    """
    from .logging import setup_logging as _setup
    _setup(level=level, format=format)
def get_logger(name: str = None):
    """
    Get a logger instance.
    Args:
        name: Logger name (defaults to sdk_workflow).
    Returns:
        Configured logger instance.
    """
    from .logging import get_logger as _get
    return _get(name)
# Exception classes - import directly for isinstance checks
class SDKWorkflowError(Exception):
    """Base exception for sdk-workflow errors."""
    pass
class ExecutionError(SDKWorkflowError):
    """Error during task execution."""
    pass
class SessionError(SDKWorkflowError):
    """Error with session management."""
    pass
class ValidationError(SDKWorkflowError):
    """Input validation error."""
    pass
