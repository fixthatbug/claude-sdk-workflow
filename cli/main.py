"""
CLI entry point for SDK workflow execution.
Routes tasks to appropriate executors based on mode and configuration.
"""
import sys
import json
import io
# Fix Windows console encoding for Unicode output
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
from typing import Any, Optional, Dict
from pathlib import Path
# Add parent directory to path for imports
_sdk_root = Path(__file__).parent.parent.absolute()
if str(_sdk_root) not in sys.path:
    sys.path.insert(0, str(_sdk_root))
# Import using direct module names (relative to sdk-workflow root)
import cli.arguments as arguments_module
import lib.utils as utils_module
import lib.error_handling as error_module
import lib.system_prompt_loader as prompt_loader_module
import core.config as config_module
import core.types as types_module
import executors as executors_module
# Unpack needed items
parse_arguments = arguments_module.parse_arguments
build_config_from_args = arguments_module.build_config_from_args
validate_task = arguments_module.validate_task
ensure_dirs = utils_module.ensure_dirs
format_cost = utils_module.format_cost
format_tokens = utils_module.format_tokens
format_duration = utils_module.format_duration
get_session_file = utils_module.get_session_file
generate_session_id = utils_module.generate_session_id
ErrorHandler = error_module.ErrorHandler
EscalationReport = error_module.EscalationReport
load_system_prompt = prompt_loader_module.load_system_prompt
Config = config_module.Config
ExecutionResult = types_module.ExecutionResult
BaseExecutor = executors_module.BaseExecutor
SDKOneshotExecutor = executors_module.OneshotExecutor
SDKStreamingExecutor = executors_module.StreamingExecutor
SDKOrchestratorExecutor = executors_module.OrchestratorExecutor
# Export executor classes for compatibility
OneshotExecutor = SDKOneshotExecutor
StreamingExecutor = SDKStreamingExecutor
OrchestratorExecutor = SDKOrchestratorExecutor
ExecutorBase = BaseExecutor
# Static Orchestrator System Prompt with /compact Protocol Enforcement
ORCHESTRATOR_SYSTEM_PROMPT = """# SDK Orchestrator - Distributed Development Coordination
## Role Definition
Lead orchestrator coordinating specialized subagents to achieve cohesive project goals. You are NOT implementing—you are delegating, coordinating, and synthesizing.
## MANDATORY /compact Protocol
After EVERY cycle completion:
1. Update {session_id}-TODO.md with cycle results
2. Execute `/compact` to optimize session state
3. Wait for completion confirmation
4. Then proceed with next delegation
NO EXCEPTIONS—this is enforced by SDK hooks.
## Execution Framework
### Phase 1: Strategic Discovery (Deploy 5-8 subagents)
Objectives: Map codebase, identify opportunities, discover dependencies
- Subagent 1: Architecture analysis (components, patterns, flows)
- Subagent 2: Documentation audit (gaps, outdated content, structure)
- Subagent 3: Dependency mapping (integration points, circular refs)
- Subagent 4: Convention analysis (coding styles, patterns, decisions)
- Subagent 5+: Domain-specific investigation
Your Job: Collect findings, create comprehensive todo list via TodoWrite
BEFORE SIGNOFF: Create `{session_id}-TODO.md` with discovery findings
### Phase 2: Strategic Planning
Objectives: Create implementation roadmap, resolve conflicts, optimize execution order
- Consolidate all discovery outputs
- Identify blocking tasks vs parallelizable work
- Flag contradictions, decide resolution
- Create detailed TodoWrite with clear success criteria
Your Job: Synthesize complexity into clear execution plan
BEFORE SIGNOFF: Update `{session_id}-TODO.md` with prioritized roadmap
### Phase 3: Coordinated Implementation (Deploy 3-20 subagents)
Objectives: Execute tasks in dependency order, maintain consistency, resolve issues
Your Job:
- Deploy subagents based on dependency chain
- Monitor progress and detect failures
- Update TodoWrite continuously
- Maintain cross-subagent consistency
- ON EACH ITERATION: Update `{session_id}-TODO.md` with current progress
- BEFORE SIGNOFF/PAUSE: Finalize TODO with next immediate action for resume
### Phase 4: Quality Assurance & Optimization
Objectives: Eliminate redundancies, verify consistency, optimize performance
## Session TODO Persistence
BEFORE ANY SIGNOFF OR RESUME:
1. Create/update `{session_id}-TODO.md` in `$CLAUDE_PROJECT_DIR`
2. Capture complete task state with YAML frontmatter
3. This file becomes the single source of truth for session continuation
## Critical Rules
1. **Never directly implement**—delegate to subagents
2. **Synthesize findings**—don't conduct primary research
3. **No abstract summaries**—only actionable next steps
4. **TodoWrite is living document**—update after each phase
5. **Session TODO is state persistence**—update before every signoff/resume
6. **Dependency order is law**—block-first, then parallelize
7. **Consistency over speed**—validate before declaring success
8. **Single source of truth**—eliminate all redundancy
9. **{session_id}-TODO.md MUST be created/updated before any signoff**
10. **{session_id}-TODO.md MUST be loaded first on any resume**
11. **MANDATORY /compact PROTOCOL**: After EVERY cycle:
    - Update {session_id}-TODO.md with cycle results
    - Execute `/compact` to optimize session state
    - Wait for completion confirmation
    - Then proceed with next delegation
    - NO EXCEPTIONS—this is enforced by SDK hooks
12. **Hook Enforcement**: SDK hooks automatically validate /compact protocol:
    - **Stop hook**: Blocks agent stop unless /compact executed
    - **SubagentStop hook**: Validates subagent completion + compaction
    - **UserPromptSubmit hook**: Reminds of /compact before new delegation
    - **PreCompact hook**: Validates TODO state before compacting
    - **SessionStart hook**: Loads compact protocol enforcement
## Success Indicators
- All discovery subagents complete with non-overlapping findings
- TodoWrite list reflects all tasks with clear dependencies
- `{session_id}-TODO.md` saved with accurate task state
- Implementation subagents execute in optimal order
- Zero import/dependency errors in final validation
- All documentation synchronized with implementation
- Agentic workflow patterns fully established
- Session TODO properly maintained for session continuity
"""
def get_executor(mode: str, config: dict) -> BaseExecutor:
    """Get the appropriate executor for the specified mode.
    Args:
        mode: Execution mode (oneshot, streaming, orchestrator)
        config: Configuration dictionary
    Returns:
        Executor instance
    """
    # Convert dict config to Config object
    cfg = _dict_to_config(config)
    executors = {
        "oneshot": SDKOneshotExecutor,
        "streaming": SDKStreamingExecutor,
        "orchestrator": SDKOrchestratorExecutor,
    }
    executor_class = executors.get(mode, SDKOneshotExecutor)
    # Extract cwd from config dict for executor
    cwd = config.get("cwd")
    permission_mode = config.get("permission_mode", "bypassPermissions")
    return executor_class(cfg, cwd=cwd, permission_mode=permission_mode)
def _dict_to_config(config_dict: dict) -> Config:
    """Convert CLI config dictionary to Config object.
    Args:
        config_dict: Dictionary from build_config_from_args
    Returns:
        Config object for executor initialization
    """
    # Create a Config object with appropriate settings
    cfg = Config()
    # Map config dict to Config attributes
    if "model" in config_dict:
        cfg.default_model = config_dict["model"]
    if "timeout" in config_dict:
        cfg.timeout = config_dict["timeout"]
    if "max_tokens" in config_dict:
        cfg.max_tokens = config_dict["max_tokens"]
    if "verbose" in config_dict:
        cfg.verbose = config_dict["verbose"]
    # Store full config dict for executor access
    cfg._cli_config = config_dict
    return cfg
def _execution_result_to_dict(result: ExecutionResult, mode: str, config: dict) -> dict:
    """Convert ExecutionResult to CLI output dictionary.
    Args:
        result: ExecutionResult from executor
        mode: Execution mode
        config: Config dictionary
    Returns:
        Dictionary compatible with CLI output format
    """
    return {
        "status": "success" if result.success else "error",
        "mode": mode,
        "model": result.model,
        "session_id": config.get("session_id"),
        "task": config.get("_task", ""),
        "response": result.content,
        "metrics": {
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "cost": result.cost.total_cost,
            "duration": result.duration_ms / 1000.0, # Convert to seconds
        },
        "error": result.stop_reason if not result.success else None,
    }
def format_output(result: dict, output_format: str) -> str:
    """Format execution result for display.
    Args:
        result: Execution result dictionary
        output_format: Desired format (json, text, markdown)
    Returns:
        Formatted output string
    """
    if output_format == "json":
        return json.dumps(result, indent=2)
    elif output_format == "markdown":
        lines = [
            f"# Execution Result",
            "",
            f"**Status:** {result.get('status', 'unknown')}",
            f"**Mode:** {result.get('mode', 'unknown')}",
            f"**Model:** {result.get('model', 'unknown')}",
            "",
        ]
        if result.get("session_id"):
            lines.append(f"**Session ID:** `{result['session_id']}`")
            lines.append("")
        lines.extend([
            "## Response",
            "",
            result.get("response", "No response"),
            "",
        ])
        metrics = result.get("metrics", {})
        if metrics:
            lines.extend([
                "## Metrics",
                "",
                f"- **Input Tokens:** {format_tokens(metrics.get('input_tokens', 0))}",
                f"- **Output Tokens:** {format_tokens(metrics.get('output_tokens', 0))}",
                f"- **Cost:** {format_cost(metrics.get('cost', 0.0))}",
                f"- **Duration:** {format_duration(metrics.get('duration', 0.0))}",
            ])
        if result.get("error"):
            lines.extend([
                "",
                "## Error",
                "",
                result["error"],
            ])
        return "\n".join(lines)
    else: # text
        lines = [
            f"Status: {result.get('status', 'unknown')}",
            f"Mode: {result.get('mode', 'unknown')}",
            f"Model: {result.get('model', 'unknown')}",
        ]
        if result.get("session_id"):
            lines.append(f"Session ID: {result['session_id']}")
        lines.extend([
            "",
            "Response:",
            result.get("response", "No response"),
        ])
        metrics = result.get("metrics", {})
        if metrics:
            lines.extend([
                "",
                "Metrics:",
                f" Input Tokens: {format_tokens(metrics.get('input_tokens', 0))}",
                f" Output Tokens: {format_tokens(metrics.get('output_tokens', 0))}",
                f" Cost: {format_cost(metrics.get('cost', 0.0))}",
                f" Duration: {format_duration(metrics.get('duration', 0.0))}",
            ])
        if result.get("error"):
            lines.extend([
                "",
                "Error:",
                result["error"],
            ])
        return "\n".join(lines)
def handle_mailbox_command(args) -> int:
    """Handle mailbox management subcommands.
    DEPRECATED: Mailbox system has been archived. Use TodoWrite for progress tracking.
    Args:
        args: Parsed arguments namespace
    Returns:
        Exit code (0 for success)
    """
    print("=" * 80)
    print("DEPRECATION NOTICE")
    print("=" * 80)
    print("The mailbox system has been deprecated and archived.")
    print("It has been replaced with TodoWrite-based progress tracking.")
    print()
    print("Migration:")
    print(" - Use TodoWrite tool for progress tracking")
    print(" - See: sdk_workflow/DEPRECATION.md for migration guide")
    print(" - See: docs/TODOWRITE_BEST_PRACTICES.md for usage")
    print()
    print("The mailbox command is no longer functional.")
    print("=" * 80)
    return 1
    # Original implementation archived - keeping stub for reference
    import json
    from core.mailbox import Mailbox, MessageType
    # Map string types to MessageType enum
    type_map = {
        'command': MessageType.COMMAND,
        'query': MessageType.QUERY,
        'response': MessageType.RESPONSE,
        'status': MessageType.STATUS,
        'signal': MessageType.SIGNAL
    }
    if args.mailbox_action == "check":
        # Check mailbox for messages
        mailbox = Mailbox(args.owner)
        msg_type = None if args.type == "all" else type_map.get(args.type)
        messages = mailbox.receive(
            msg_type=msg_type,
            limit=args.limit,
            delete_after_read=args.delete
        )
        if not messages:
            print(f"No messages in {args.owner} mailbox")
            return 0
        print(f"{'ID':<10} {'From':<20} {'Type':<10} {'Priority':<8} {'Payload':<50}")
        print("-" * 98)
        for msg in messages:
            payload_str = json.dumps(msg.payload)[:47]
            if len(json.dumps(msg.payload)) > 47:
                payload_str += "..."
            print(f"{msg.id:<10} {msg.sender:<20} {msg.type.value:<10} {msg.priority:<8} {payload_str:<50}")
        print(f"\n{len(messages)} message(s) retrieved" + (" and deleted" if args.delete else ""))
        return 0
    elif args.mailbox_action == "send":
        # Send message to orchestrator
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON payload: {e}")
            return 1
        mailbox = Mailbox(args.sender)
        msg_type = type_map.get(args.type)
        msg_id = mailbox.send(
            recipient=args.recipient,
            msg_type=msg_type,
            payload=payload,
            priority=args.priority,
            ttl=args.ttl
        )
        print(f"Message sent: {msg_id}")
        print(f"From: {args.sender}")
        print(f"To: {args.recipient}")
        print(f"Type: {args.type}")
        print(f"Priority: {args.priority}")
        return 0
    elif args.mailbox_action == "list":
        # List all active mailboxes
        mailboxes = Mailbox.list_mailboxes()
        if not mailboxes:
            print("No active mailboxes found")
            return 0
        print(f"{'Mailbox ID':<30} {'Messages':<10}")
        print("-" * 40)
        for mb_id in mailboxes:
            if args.show_counts:
                mb = Mailbox(mb_id)
                count = mb.get_pending_count()
                print(f"{mb_id:<30} {count:<10}")
            else:
                print(mb_id)
        return 0
    elif args.mailbox_action == "cleanup":
        # Remove expired messages
        mailbox = Mailbox(args.owner)
        count = mailbox.cleanup_expired()
        print(f"Removed {count} expired message(s) from {args.owner} mailbox")
        return 0
    elif args.mailbox_action == "clear":
        # Clear all messages
        if not args.confirm:
            print("Warning: This will delete all messages from the mailbox.")
            print("Use --confirm to proceed.")
            return 1
        mailbox = Mailbox(args.owner)
        count = mailbox.clear_all()
        print(f"Cleared {count} message(s) from {args.owner} mailbox")
        return 0
    elif args.mailbox_action == "broadcast":
        # Broadcast message
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON payload: {e}")
            return 1
        mailbox = Mailbox(args.sender)
        msg_type = type_map.get(args.type)
        msg_id = mailbox.broadcast(
            msg_type=msg_type,
            payload=payload
        )
        print(f"Broadcast message sent: {msg_id}")
        print(f"From: {args.sender}")
        print(f"Type: {args.type}")
        return 0
    elif args.mailbox_action == "watch":
        # Watch mailbox in real-time
        import time
        import os
        from datetime import datetime
        mailbox = Mailbox(args.owner)
        print(f"Watching {args.owner} mailbox (Press Ctrl+C to stop)...")
        print(f"Refreshing every {args.interval} seconds")
        print("=" * 80)
        try:
            while True:
                # Clear screen (platform-independent)
                os.system('cls' if os.name == 'nt' else 'clear')
                # Header
                print(f"=== {args.owner} Mailbox - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
                print()
                # Get recent messages (peek without deleting)
                messages = mailbox.peek(limit=args.limit)
                if not messages:
                    print("No messages in mailbox")
                else:
                    # Display messages
                    print(f"{'Time':<20} {'From':<20} {'Type':<10} {'Payload':<40}")
                    print("-" * 90)
                    for msg in messages:
                        timestamp = datetime.fromtimestamp(msg.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                        payload_str = json.dumps(msg.payload)[:37]
                        if len(json.dumps(msg.payload)) > 37:
                            payload_str += "..."
                        print(f"{timestamp:<20} {msg.sender:<20} {msg.type.value:<10} {payload_str:<40}")
                    print()
                    print(f"{len(messages)} message(s) | Pending: {mailbox.get_pending_count()}")
                # Wait for next refresh
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n\nStopped watching.")
            return 0
    elif args.mailbox_action == "stats":
        # Show mailbox statistics
        from datetime import datetime
        mailbox = Mailbox(args.owner)
        print(f"=== Mailbox Statistics: {args.owner} ===")
        print()
        # Count messages by type
        type_counts = {}
        total_messages = 0
        oldest_timestamp = None
        newest_timestamp = None
        # Check inbox
        if mailbox.inbox_dir.exists():
            for msg_file in mailbox.inbox_dir.glob('*.json'):
                try:
                    with open(msg_file, 'r') as f:
                        data = json.load(f)
                    msg_type = data.get('t', 'unknown')
                    timestamp = data.get('ts', 0)
                    type_counts[msg_type] = type_counts.get(msg_type, 0) + 1
                    total_messages += 1
                    if oldest_timestamp is None or timestamp < oldest_timestamp:
                        oldest_timestamp = timestamp
                    if newest_timestamp is None or timestamp > newest_timestamp:
                        newest_timestamp = timestamp
                except Exception:
                    pass
        # Display stats
        print(f"Total Messages: {total_messages}")
        print()
        if total_messages > 0:
            print("Messages by Type:")
            for msg_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
                # Map compact type to full name
                type_names = {'cmd': 'COMMAND', 'qry': 'QUERY', 'rsp': 'RESPONSE',
                             'sts': 'STATUS', 'sig': 'SIGNAL'}
                type_name = type_names.get(msg_type, msg_type.upper())
                print(f" {type_name:<15} {count:>5}")
            print()
            print(f"Oldest Message: {datetime.fromtimestamp(oldest_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Newest Message: {datetime.fromtimestamp(newest_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("No messages found")
        # Check for expired messages
        expired_count = 0
        if mailbox.inbox_dir.exists():
            for msg_file in mailbox.inbox_dir.glob('*.json'):
                try:
                    with open(msg_file, 'r') as f:
                        data = json.load(f)
                    from core.mailbox import Message
                    msg = Message.from_compact_dict(data)
                    if msg.is_expired():
                        expired_count += 1
                except Exception:
                    pass
        if expired_count > 0:
            print()
            print(f" Warning: {expired_count} expired message(s) - run 'cleanup' to remove")
        return 0
    else:
        print("Unknown mailbox action. Use: check, send, list, cleanup, clear, broadcast, watch, stats")
        return 1
def handle_sessions_command(args) -> int:
    """Handle session management subcommands.
    Args:
        args: Parsed arguments namespace
    Returns:
        Exit code (0 for success)
    """
    sessions_dir = utils_module.get_sessions_dir()
    if args.session_action == "list":
        # List sessions
        session_files = list(sessions_dir.glob("*.json"))
        if not session_files:
            print("No sessions found.")
            return 0
        print(f"{'ID':<10} {'Status':<12} {'Task':<50}")
        print("-" * 72)
        for sf in sorted(session_files, key=lambda p: p.stat().st_mtime, reverse=True)[:args.limit]:
            try:
                with open(sf) as f:
                    data = json.load(f)
                    task = data.get("task", "")[:47]
                    if len(data.get("task", "")) > 47:
                        task += "..."
                    print(f"{data.get('id', 'unknown'):<10} {data.get('status', 'unknown'):<12} {task:<50}")
            except Exception as e:
                print(f"Error reading {sf}: {e}")
        return 0
    elif args.session_action == "status":
        session_file = get_session_file(args.session_id)
        if not session_file.exists():
            print(f"Session not found: {args.session_id}")
            return 1
        with open(session_file) as f:
            data = json.load(f)
        if args.detailed:
            print(json.dumps(data, indent=2))
        else:
            print(f"Session: {data.get('id')}")
            print(f"Status: {data.get('status')}")
            print(f"Task: {data.get('task')}")
        return 0
    elif args.session_action == "send":
        session_file = get_session_file(args.session_id)
        if not session_file.exists():
            print(f"Session not found: {args.session_id}")
            return 1
        # In production, this would send message to running session
        print(f"Message sent to session {args.session_id}: {args.message}")
        return 0
    elif args.session_action == "resume":
        session_file = get_session_file(args.session_id)
        if not session_file.exists():
            print(f"Session not found: {args.session_id}")
            return 1
        print(f"Resuming session: {args.session_id}")
        # In production, this would resume the session
        return 0
    elif args.session_action == "kill":
        session_file = get_session_file(args.session_id)
        if not session_file.exists():
            print(f"Session not found: {args.session_id}")
            return 1
        # Update session status
        with open(session_file) as f:
            data = json.load(f)
        data["status"] = "terminated"
        with open(session_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Session terminated: {args.session_id}")
        return 0
    else:
        print("Unknown session action. Use: list, status, send, resume, kill")
        return 1
def main() -> int:
    """Main entry point for the CLI.
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Ensure directories exist
    ensure_dirs()
    # Parse arguments
    try:
        args = parse_arguments()
    except SystemExit as e:
        return e.code if e.code else 1
    # Handle sessions subcommand
    if args.subcommand == "sessions":
        return handle_sessions_command(args)
    # Handle mailbox subcommand
    if args.subcommand == "mailbox":
        return handle_mailbox_command(args)
    # Validate task
    if args.task and not validate_task(args.task):
        print("Error: Invalid task description", file=sys.stderr)
        return 1
    # Build configuration
    config = build_config_from_args(args)
    config["_task"] = args.task # Store task for later reference
    # Get executor
    try:
        executor = get_executor(args.mode, config)
    except Exception as e:
        print(f"Error creating executor: {e}", file=sys.stderr)
        if hasattr(e, '__traceback__'):
            import traceback
            traceback.print_exc()
        return 1
    # Setup executor
    try:
        executor.setup()
    except Exception as e:
        print(f"Error setting up executor: {e}", file=sys.stderr)
        if hasattr(e, '__traceback__'):
            import traceback
            traceback.print_exc()
        return 1
    # Execute task
    try:
        # Use static orchestrator prompt if in orchestrator mode and no custom prompt provided
        if args.mode == "orchestrator" and not args.system_prompt:
            system_prompt = ORCHESTRATOR_SYSTEM_PROMPT
        else:
            # Use provided prompt or loader for other modes
            system_prompt = load_system_prompt(args.mode, args.system_prompt)
        result = executor.execute(args.task, system_prompt)
        # Convert ExecutionResult to dict
        result_dict = _execution_result_to_dict(result, args.mode, config)
    except Exception as e:
        error_handler = ErrorHandler()
        action, data = error_handler.handle(e, 3) # Force escalation
        if isinstance(data, EscalationReport):
            print(f"Error: {data.error_message}", file=sys.stderr)
            print(f"Type: {data.error_type}", file=sys.stderr)
            print(f"Recommendations:", file=sys.stderr)
            for rec in data.recommendations:
                print(f" - {rec}", file=sys.stderr)
        else:
            print(f"Error: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        return 1
    finally:
        # Cleanup executor
        try:
            executor.cleanup()
        except Exception as e:
            print(f"Warning: Error during cleanup: {e}", file=sys.stderr)
    # Format and print output
    output = format_output(result_dict, args.output_format)
    print(output)
    # Return appropriate exit code
    if result_dict.get("status") in ("success", "started"):
        return 0
    else:
        return 1
if __name__ == "__main__":
    sys.exit(main())
