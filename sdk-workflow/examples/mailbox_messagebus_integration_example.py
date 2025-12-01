"""
Comprehensive example demonstrating mailbox-MessageBus integration features.
Shows all new features: MessageBus events, compact protocol, bridges, etc.
"""
import sys
from pathlib import Path
# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
import time
from sdk_workflow.communication.message_bus import MessageBus, EventType, get_default_bus
from sdk_workflow.communication.progress import ProgressTracker, ProgressStatus
from sdk_workflow.communication.session_tracker import SessionTracker, SessionState
from sdk_workflow.communication.progress_mailbox import ProgressMailboxBridge
from sdk_workflow.communication.session_mailbox import SessionMailboxBridge
from sdk_workflow.core.mailbox import Mailbox, MessageType, send_status_compact
from sdk_workflow.core.mailbox_protocol import StatusProtocol, StateCode
from sdk_workflow.core.mailbox_integration import OrchestratorMailboxMixin
def example_1_messagebus_integration():
    """Example 1: MessageBus Integration - Events are published when mailbox operations occur."""
    print("=" * 80)
    print("Example 1: MessageBus Integration")
    print("=" * 80)
    # Create MessageBus
    bus = MessageBus()
    # Subscribe to mailbox events
    events_captured = []
    def on_mailbox_event(event):
        events_captured.append(event)
        print(f" Event: {event.event_type} | From: {event.data.get('sender', 'N/A')} → To: {event.data.get('recipient', 'N/A')}")
    bus.subscribe(EventType.MESSAGE_SENT, on_mailbox_event)
    bus.subscribe(EventType.MESSAGE_RECEIVED, on_mailbox_event)
    bus.subscribe(EventType.SIGNAL_RECEIVED, on_mailbox_event)
    # Create mailboxes WITH MessageBus integration
    alice = Mailbox(owner_id="alice", message_bus=bus, publish_events=True)
    bob = Mailbox(owner_id="bob", message_bus=bus, publish_events=True)
    print("\nAlice sends command to Bob...")
    alice.send(
        recipient="bob",
        msg_type=MessageType.COMMAND,
        payload={"action": "process_data"}
    )
    print("\nBob receives message...")
    messages = bob.receive()
    print("\nBob sends signal to Alice...")
    bob.send(
        recipient="alice",
        msg_type=MessageType.SIGNAL,
        payload={"signal": "DONE"}
    )
    print("\nAlice receives signal...")
    messages = alice.receive()
    print(f"\n Total events captured: {len(events_captured)}")
    print(f" MESSAGE_SENT events: {sum(1 for e in events_captured if e.event_type == 'message_sent')}")
    print(f" MESSAGE_RECEIVED events: {sum(1 for e in events_captured if e.event_type == 'message_received')}")
    print(f" SIGNAL_RECEIVED events: {sum(1 for e in events_captured if e.event_type == 'signal_received')}")
    # Cleanup
    alice.clear_all()
    bob.clear_all()
    print("\n Example 1 complete!\n")
def example_2_compact_status_protocol():
    """Example 2: Compact Status Protocol - Token-efficient messaging."""
    print("=" * 80)
    print("Example 2: Compact Status Protocol")
    print("=" * 80)
    # Create status using StatusProtocol class
    status = StatusProtocol(
        ph="impl",
        pg=0.75,
        st=StateCode.RUNNING,
        sm="Writing unit tests for auth module",
        tk=1234,
        cs=0.0523
    )
    print("\nStatusProtocol object:")
    print(f" {status}")
    # Convert to compact payload
    compact_payload = status.to_payload()
    print(f"\nCompact payload ({len(str(compact_payload))} chars):")
    print(f" {compact_payload}")
    # Compare with verbose format
    verbose_payload = {
        "phase": "implementation",
        "progress": 0.75,
        "state": "running",
        "summary": "Writing unit tests for auth module",
        "tokens": 1234,
        "cost_usd": 0.0523
    }
    print(f"\nVerbose payload ({len(str(verbose_payload))} chars):")
    print(f" {verbose_payload}")
    savings = ((len(str(verbose_payload)) - len(str(compact_payload))) / len(str(verbose_payload))) * 100
    print(f"\n Token savings: {savings:.1f}%")
    # Send compact status via mailbox
    print("\nSending compact status via mailbox...")
    msg_id = send_status_compact(
        sender="orchestrator-123",
        recipient="claude-code",
        phase="implementation",
        progress=0.75,
        state="run",
        summary="Writing unit tests for auth module",
        tokens=1234,
        cost=0.0523
    )
    print(f" Message sent: {msg_id}")
    # Cleanup
    mailbox = Mailbox("orchestrator-123")
    mailbox.clear_all()
    mailbox = Mailbox("claude-code")
    mailbox.clear_all()
    print("\n Example 2 complete!\n")
def example_3_progress_mailbox_bridge():
    """Example 3: ProgressMailboxBridge - Automatic progress forwarding."""
    print("=" * 80)
    print("Example 3: ProgressMailboxBridge")
    print("=" * 80)
    # Setup
    tracker = ProgressTracker("session-abc123")
    mailbox = Mailbox("session-abc123")
    bridge = ProgressMailboxBridge(
        tracker,
        mailbox,
        recipient='claude-code',
        use_compact_protocol=True
    )
    print("\nStarting progress tracking with automatic mailbox forwarding...")
    # Start tracking - automatically sent via mailbox
    tracker.start("Starting workflow")
    print(" Started (message sent automatically)")
    # Update progress - automatically sent via mailbox
    tracker.update("planning", 1, 3, "Analyzing requirements")
    print(" Planning 1/3 (message sent automatically)")
    tracker.update("planning", 2, 3, "Creating execution plan")
    print(" Planning 2/3 (message sent automatically)")
    tracker.update("planning", 3, 3, "Plan complete")
    print(" Planning 3/3 (message sent automatically)")
    tracker.update("implementation", 1, 5, "Setting up environment")
    print(" Implementation 1/5 (message sent automatically)")
    # Complete - automatically sent via mailbox
    tracker.on_complete({"result": "success"})
    print(" Completed (message sent automatically)")
    # Check messages that were sent
    print("\nChecking Claude Code's mailbox...")
    claude_mailbox = Mailbox("claude-code")
    messages = claude_mailbox.receive()
    print(f" Received {len(messages)} automatic progress updates")
    for i, msg in enumerate(messages[:3], 1): # Show first 3
        print(f" {i}. {msg.payload}")
    # Cleanup
    mailbox.clear_all()
    claude_mailbox.clear_all()
    print("\n Example 3 complete!\n")
def example_4_session_mailbox_bridge():
    """Example 4: SessionMailboxBridge - Automatic session state forwarding."""
    print("=" * 80)
    print("Example 4: SessionMailboxBridge")
    print("=" * 80)
    # Setup
    tracker = SessionTracker()
    bridge = SessionMailboxBridge(tracker, recipient='claude-code', use_compact_protocol=True)
    print("\nRegistering session with automatic state change forwarding...")
    # Register session - state: CREATED
    session_id = tracker.register("my-workflow-session")
    print(f" Session registered: {session_id}")
    # Start session - state: STARTING → RUNNING
    tracker.start(session_id)
    print(" Session started (state change sent)")
    tracker.running(session_id)
    print(" Session running (state change sent)")
    # Complete session - state: COMPLETED
    tracker.complete(session_id, result={"success": True})
    print(" Session completed (state change sent)")
    # Check messages
    print("\nChecking Claude Code's mailbox...")
    claude_mailbox = Mailbox("claude-code")
    messages = claude_mailbox.receive()
    print(f" Received {len(messages)} automatic state change updates")
    for i, msg in enumerate(messages, 1):
        print(f" {i}. {msg.payload}")
    # Cleanup
    claude_mailbox.clear_all()
    print("\n Example 4 complete!\n")
def example_5_orchestrator_with_all_features():
    """Example 5: Complete Orchestrator using all new features."""
    print("=" * 80)
    print("Example 5: Complete Orchestrator with All Features")
    print("=" * 80)
    class DemoOrchestrator(OrchestratorMailboxMixin):
        """Orchestrator using all new features."""
        def __init__(self, session_id):
            self.session_id = session_id
            self.bus = MessageBus()
            # Initialize mailbox
            self._init_mailbox()
            # Enable MessageBus integration (manually for demo)
            from sdk_workflow.communication.mailbox_events import MailboxEventPublisher
            self.mailbox._event_publisher = MailboxEventPublisher(self.bus, auto_publish=True)
            # Setup progress tracking with bridge
            self.tracker = ProgressTracker(session_id, message_bus=self.bus)
            self.progress_bridge = ProgressMailboxBridge(
                self.tracker,
                self.mailbox,
                use_compact_protocol=True
            )
            # Subscribe to MessageBus events
            self.bus.subscribe(EventType.MESSAGE_SENT, self._on_bus_event)
            self.bus.subscribe(EventType.PROGRESS_UPDATE, self._on_bus_event)
            self.events = []
        def _on_bus_event(self, event):
            self.events.append(event)
        def execute(self):
            print("\n Starting orchestrator...")
            # Start tracking (triggers ProgressTracker → ProgressMailboxBridge → Mailbox)
            self.tracker.start("Initializing")
            # Check for signals
            signal = self.check_mailbox()
            if signal:
                print(f" Received signal: {signal.payload}")
            # Report status using compact protocol
            self.report_status_compact(
                phase="plan",
                progress=0.2,
                state="run",
                summary="Planning execution",
                tokens=150,
                cost=0.001
            )
            print(" Sent compact status update")
            # Update progress (automatically forwarded via bridge)
            self.tracker.update("impl", 1, 2, "Implementing features")
            print(" Progress update (auto-forwarded)")
            self.tracker.update("impl", 2, 2, "Features complete")
            print(" Progress update (auto-forwarded)")
            # Complete
            self.tracker.on_complete({"success": True})
            print(" Completed")
            # Show stats
            print(f"\n MessageBus events captured: {len(self.events)}")
            print(f" PROGRESS_UPDATE: {sum(1 for e in self.events if e.event_type == 'progress_update')}")
            print(f" MESSAGE_SENT: {sum(1 for e in self.events if e.event_type == 'message_sent')}")
    # Run orchestrator
    orch = DemoOrchestrator("demo-session-xyz")
    orch.execute()
    # Cleanup
    orch.cleanup_mailbox()
    claude_mailbox = Mailbox("claude-code")
    claude_mailbox.clear_all()
    print("\n Example 5 complete!\n")
def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("MAILBOX-MESSAGEBUS INTEGRATION - COMPREHENSIVE EXAMPLES")
    print("=" * 80 + "\n")
    examples = [
        ("MessageBus Integration", example_1_messagebus_integration),
        ("Compact Status Protocol", example_2_compact_status_protocol),
        ("ProgressMailboxBridge", example_3_progress_mailbox_bridge),
        ("SessionMailboxBridge", example_4_session_mailbox_bridge),
        ("Complete Orchestrator", example_5_orchestrator_with_all_features),
    ]
    for i, (name, func) in enumerate(examples, 1):
        try:
            func()
            time.sleep(0.5) # Brief pause between examples
        except Exception as e:
            print(f"\n Example {i} ({name}) failed: {e}\n")
            import traceback
            traceback.print_exc()
    print("=" * 80)
    print("All examples completed!")
    print("=" * 80)
    print("\n Key Features Demonstrated:")
    print(" 1. MessageBus event publishing for mailbox operations")
    print(" 2. Compact status protocol (40-50% token savings)")
    print(" 3. Automatic ProgressTracker → Mailbox forwarding")
    print(" 4. Automatic SessionTracker → Mailbox forwarding")
    print(" 5. Complete orchestrator integration with all features")
    print("\n See MAILBOX_MESSAGEBUS_INTEGRATION.md for full documentation")
    print()
if __name__ == "__main__":
    main()
