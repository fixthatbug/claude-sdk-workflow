"""
CLI module for sdk-workflow.
Provides command-line interface for running tasks and managing sessions.
Usage:
    python -m sdk_workflow --mode oneshot --task "Your task"
    python -m sdk_workflow sessions list
    python -m sdk_workflow sessions send <id> "message"
"""
from typing import Optional
# Import from arguments module
from .arguments import (
    create_parser,
    parse_arguments,
    get_mode_defaults,
    validate_task,
    build_config_from_args,
)
# Import from main module
from .main import (
    main as cli_main,
    get_executor,
    format_output,
    handle_sessions_command,
    ExecutorBase,
    OneshotExecutor,
    StreamingExecutor,
    OrchestratorExecutor,
)
__all__ = [
    # Entry points
    "main",
    "parse_args",
    "cli_main",
    # Arguments
    "create_parser",
    "parse_arguments",
    "get_mode_defaults",
    "validate_task",
    "build_config_from_args",
    # Main functions
    "get_executor",
    "format_output",
    "handle_sessions_command",
    # Executors (re-exported from executors package)
    "ExecutorBase",
    "OneshotExecutor",
    "StreamingExecutor",
    "OrchestratorExecutor",
]
def main(args: Optional[list] = None) -> int:
    """
    Main CLI entry point.
    Args:
        args: Command line arguments (defaults to sys.argv).
    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    return cli_main()
def parse_args(args: Optional[list] = None):
    """Parse command line arguments.
    Args:
        args: Command line arguments (defaults to sys.argv).
    Returns:
        Parsed arguments namespace.
    """
    return parse_arguments(args)
