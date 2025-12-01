"""
Command-line argument definitions for SDK workflow.
Provides argparse configuration for all CLI modes and subcommands.
"""
import argparse
import os
from typing import Optional, List
import sys
def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with all subcommands.
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="sdk_workflow",
        description="SDK Workflow - Intelligent task execution with Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simple oneshot task
  python -m sdk_workflow --mode oneshot --task "Extract function names from auth.py"
  # Streaming with custom prompt
  python -m sdk_workflow --mode streaming --task "Refactor auth module" \\
    --system-prompt "You are a senior developer"
  # Background orchestrator
  python -m sdk_workflow --mode orchestrator --task "Implement dashboard" \\
    --background
  # Session management
  python -m sdk_workflow sessions list
  python -m sdk_workflow sessions status abc123
  python -m sdk_workflow sessions send abc123 "Focus on error handling"
  # Mailbox management
  python -m sdk_workflow mailbox check
  python -m sdk_workflow mailbox send --to session-123 --type command --payload '{"action":"pause"}'
  python -m sdk_workflow mailbox list
"""
    )
    # Create subparsers for main commands vs sessions
    subparsers = parser.add_subparsers(dest="subcommand", help="Available commands")
    # Add main execution arguments to the parser itself
    _add_execution_args(parser)
    # Add sessions subcommand
    sessions_parser = subparsers.add_parser(
        "sessions",
        help="Manage workflow sessions",
        description="List, monitor, and interact with workflow sessions"
    )
    _add_sessions_subcommands(sessions_parser)
    # Add mailbox subcommand
    mailbox_parser = subparsers.add_parser(
        "mailbox",
        help="Manage mailbox for inter-orchestrator communication",
        description="Send, receive, and manage messages between orchestrators"
    )
    _add_mailbox_subcommands(mailbox_parser)
    return parser
def _add_execution_args(parser: argparse.ArgumentParser) -> None:
    """Add execution-related arguments to the parser."""
    # Mode selection
    parser.add_argument(
        "--mode", "-m",
        choices=["oneshot", "streaming", "orchestrator"],
        default="oneshot",
        help="Execution mode (default: oneshot)"
    )
    # Task description
    parser.add_argument(
        "--task", "-t",
        type=str,
        help="Task description (required for execution)"
    )
    # System prompt
    parser.add_argument(
        "--system-prompt", "-s",
        type=str,
        default=None,
        help="Custom system prompt for the executor"
    )
    # Model override
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        choices=["haiku", "sonnet", "opus"],
        help="Model override (default: mode-dependent)"
    )
    # Background execution
    parser.add_argument(
        "--background", "-b",
        action="store_true",
        help="Run in background (orchestrator mode)"
    )
    # Session management
    parser.add_argument(
        "--session",
        type=str,
        default=None,
        help="Session ID to resume"
    )
    parser.add_argument(
        "--continue", "-c",
        dest="continue_session",
        action="store_true",
        help="Continue an existing session"
    )
    # Output formatting
    parser.add_argument(
        "--output-format", "-o",
        choices=["json", "text", "markdown"],
        default="text",
        help="Output format (default: text)"
    )
    # Additional options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress non-essential output"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout in seconds (default: 300)"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Maximum tokens for response"
    )
    # Orchestrator-specific
    parser.add_argument(
        "--agents",
        type=str,
        nargs="+",
        default=None,
        help="Subagents for orchestrator mode"
    )
    parser.add_argument(
        "--workflow",
        type=str,
        default=None,
        help="Workflow definition file"
    )
    # Working directory - defaults to user's current directory (project folder)
    parser.add_argument(
        "--cwd",
        type=str,
        default=None,
        help="Working directory for agent execution (default: current directory)"
    )
    # Permission mode for SDK agents
    parser.add_argument(
        "--permission-mode",
        type=str,
        default="bypassPermissions",
        choices=["default", "acceptEdits", "bypassPermissions"],
        help="Permission mode for SDK agents (default: bypassPermissions for auto-accept)"
    )
def _add_sessions_subcommands(parser: argparse.ArgumentParser) -> None:
    """Add session management subcommands."""
    subparsers = parser.add_subparsers(dest="session_action", help="Session actions")
    # List sessions
    list_parser = subparsers.add_parser(
        "list",
        help="List all sessions"
    )
    list_parser.add_argument(
        "--status",
        choices=["all", "running", "completed", "failed"],
        default="all",
        help="Filter by status"
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum sessions to show"
    )
    # Session status
    status_parser = subparsers.add_parser(
        "status",
        help="Get session status"
    )
    status_parser.add_argument(
        "session_id",
        type=str,
        help="Session ID to check"
    )
    status_parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed status"
    )
    # Send message to session
    send_parser = subparsers.add_parser(
        "send",
        help="Send message to running session"
    )
    send_parser.add_argument(
        "session_id",
        type=str,
        help="Session ID to send to"
    )
    send_parser.add_argument(
        "message",
        type=str,
        help="Message to send"
    )
    # Resume session
    resume_parser = subparsers.add_parser(
        "resume",
        help="Resume a paused session"
    )
    resume_parser.add_argument(
        "session_id",
        type=str,
        help="Session ID to resume"
    )
    resume_parser.add_argument(
        "--from-checkpoint",
        type=str,
        default=None,
        help="Checkpoint to resume from"
    )
    # Kill session
    kill_parser = subparsers.add_parser(
        "kill",
        help="Terminate a running session"
    )
    kill_parser.add_argument(
        "session_id",
        type=str,
        help="Session ID to terminate"
    )
    kill_parser.add_argument(
        "--force",
        action="store_true",
        help="Force termination"
    )
def _add_mailbox_subcommands(parser: argparse.ArgumentParser) -> None:
    """Add mailbox management subcommands."""
    subparsers = parser.add_subparsers(dest="mailbox_action", help="Mailbox actions")
    # Check mailbox
    check_parser = subparsers.add_parser(
        "check",
        help="Check mailbox for messages"
    )
    check_parser.add_argument(
        "--owner",
        type=str,
        default="claude-code",
        help="Mailbox owner ID (default: claude-code)"
    )
    check_parser.add_argument(
        "--type",
        type=str,
        choices=["command", "query", "response", "status", "signal", "all"],
        default="all",
        help="Filter by message type"
    )
    check_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum messages to show"
    )
    check_parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete messages after reading"
    )
    # Send message
    send_parser = subparsers.add_parser(
        "send",
        help="Send message to orchestrator"
    )
    send_parser.add_argument(
        "--from",
        dest="sender",
        type=str,
        default="claude-code",
        help="Sender ID (default: claude-code)"
    )
    send_parser.add_argument(
        "--to",
        dest="recipient",
        type=str,
        required=True,
        help="Recipient orchestrator ID"
    )
    send_parser.add_argument(
        "--type",
        type=str,
        choices=["command", "query", "response", "status", "signal"],
        required=True,
        help="Message type"
    )
    send_parser.add_argument(
        "--payload",
        type=str,
        required=True,
        help="Message payload as JSON string"
    )
    send_parser.add_argument(
        "--priority",
        type=int,
        default=1,
        choices=[0, 1, 2, 3],
        help="Message priority (0=low, 1=normal, 2=high, 3=urgent)"
    )
    send_parser.add_argument(
        "--ttl",
        type=int,
        default=3600,
        help="Time-to-live in seconds (default: 3600)"
    )
    # List mailboxes
    list_parser = subparsers.add_parser(
        "list",
        help="List all active mailboxes"
    )
    list_parser.add_argument(
        "--show-counts",
        action="store_true",
        help="Show message counts for each mailbox"
    )
    # Cleanup mailbox
    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="Remove expired messages"
    )
    cleanup_parser.add_argument(
        "--owner",
        type=str,
        default="claude-code",
        help="Mailbox owner ID (default: claude-code)"
    )
    # Clear mailbox
    clear_parser = subparsers.add_parser(
        "clear",
        help="Clear all messages from mailbox"
    )
    clear_parser.add_argument(
        "--owner",
        type=str,
        default="claude-code",
        help="Mailbox owner ID (default: claude-code)"
    )
    clear_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm deletion"
    )
    # Broadcast message
    broadcast_parser = subparsers.add_parser(
        "broadcast",
        help="Send broadcast message to all orchestrators"
    )
    broadcast_parser.add_argument(
        "--from",
        dest="sender",
        type=str,
        default="claude-code",
        help="Sender ID (default: claude-code)"
    )
    broadcast_parser.add_argument(
        "--type",
        type=str,
        choices=["command", "query", "status", "signal"],
        required=True,
        help="Message type"
    )
    broadcast_parser.add_argument(
        "--payload",
        type=str,
        required=True,
        help="Message payload as JSON string"
    )
    # Watch mailbox
    watch_parser = subparsers.add_parser(
        "watch",
        help="Watch mailbox for real-time updates"
    )
    watch_parser.add_argument(
        "--owner",
        type=str,
        default="claude-code",
        help="Mailbox owner ID to watch (default: claude-code)"
    )
    watch_parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Refresh interval in seconds (default: 2)"
    )
    watch_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum messages to display (default: 5)"
    )
    # Mailbox stats
    stats_parser = subparsers.add_parser(
        "stats",
        help="Show mailbox statistics"
    )
    stats_parser.add_argument(
        "--owner",
        type=str,
        default="claude-code",
        help="Mailbox owner ID (default: claude-code)"
    )
def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.
    Args:
        args: Arguments to parse (default: sys.argv[1:])
    Returns:
        Parsed arguments namespace
    """
    parser = create_parser()
    parsed = parser.parse_args(args)
    # Validation
    if parsed.subcommand is None:
        # Main execution mode - task is required
        if parsed.task is None and not parsed.continue_session:
            parser.error("--task is required for execution (or use --continue with --session)")
    return parsed
def get_mode_defaults(mode: str) -> dict:
    """Get default settings for a given execution mode.
    Args:
        mode: Execution mode (oneshot, streaming, orchestrator)
    Returns:
        Dictionary of default settings
    """
    defaults = {
        "oneshot": {
            "model": "haiku",
            "timeout": 60,
            "max_tokens": 4096,
            "streaming": False,
        },
        "streaming": {
            "model": "sonnet",
            "timeout": 300,
            "max_tokens": 8192,
            "streaming": True,
        },
        "orchestrator": {
            "model": "sonnet",
            "timeout": 600,
            "max_tokens": 16384,
            "streaming": True,
            "background": True,
        },
    }
    return defaults.get(mode, defaults["oneshot"])
def validate_task(task: str) -> bool:
    """Validate a task description.
    Args:
        task: Task description string
    Returns:
        True if valid, False otherwise
    """
    if not task or not task.strip():
        return False
    # Minimum reasonable length
    if len(task.strip()) < 5:
        return False
    return True
def build_config_from_args(args: argparse.Namespace) -> dict:
    """Build configuration dictionary from parsed arguments.
    Args:
        args: Parsed arguments namespace
    Returns:
        Configuration dictionary for executor
    """
    # Start with mode defaults
    config = get_mode_defaults(args.mode)
    # Override with explicit arguments
    if args.model:
        config["model"] = args.model
    if args.timeout:
        config["timeout"] = args.timeout
    if args.max_tokens:
        config["max_tokens"] = args.max_tokens
    if args.background:
        config["background"] = True
    if args.system_prompt:
        config["system_prompt"] = args.system_prompt
    if args.session:
        config["session_id"] = args.session
    if args.agents:
        config["agents"] = args.agents
    if args.workflow:
        config["workflow"] = args.workflow
    # Working directory - default to user's current directory (project folder)
    # This captures the directory where the command was invoked, not sdk-workflow dir
    config["cwd"] = args.cwd if args.cwd else os.getcwd()
    # Flags
    config["verbose"] = args.verbose
    config["quiet"] = args.quiet
    config["permission_mode"] = getattr(args, "permission_mode", "bypassPermissions")
    return config
