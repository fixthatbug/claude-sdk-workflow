"""
Practical examples demonstrating the mailbox system.
Shows real-world usage patterns for inter-orchestrator communication.
"""
import time
import sys
from pathlib import Path
# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from sdk_workflow.core.mailbox import (
    Mailbox,
    MessageType,
    send_command,
    send_status,
    send_signal
)
from sdk_workflow.core.mailbox_integration import (
    OrchestratorMailboxMixin,
    send_control_signal,
    get_orchestrator_progress
)
def example_basic_messaging():
    """Example 1: Basic message sending and receiving."""
    print("=" * 60)
    print("Example 1: Basic Messaging")
    print("=" * 60)
    # Create mailboxes for Alice and Bob
    alice = Mailbox(owner_id="alice")
    bob = Mailbox(owner_id="bob")
    # Alice sends a command to Bob
    print("\nAlice sends command to Bob...")
    msg_id = alice.send(
        recipient="bob",
        msg_type=MessageType.COMMAND,
        payload={"action": "process_data", "dataset": "customers"},
        priority=2
    )
    print(f" Sent message: {msg_id}")
    # Bob receives the message
    print("\nBob receives messages...")
    messages = bob.receive(limit=10)
    for msg in messages:
        print(f" From: {msg.sender}")
        print(f" Type: {msg.type.value}")
        print(f" Payload: {msg.payload}")
        print(f" Priority: {msg.priority}")
        # Bob replies
        print("\nBob sends response...")
        bob.reply(
            original_msg=msg,
            payload={"status": "completed", "records_processed": 1234}
        )
    # Alice receives the response
    print("\nAlice receives response...")
    responses = alice.receive(msg_type=MessageType.RESPONSE)
    for resp in responses:
        print(f" Response from {resp.sender}: {resp.payload}")
    # Cleanup
    alice.clear_all()
    bob.clear_all()
    print("\n Example 1 complete\n")
def example_status_reporting():
    """Example 2: Orchestrator status reporting to Claude Code."""
    print("=" * 60)
    print("Example 2: Status Reporting")
    print("=" * 60)
    # Orchestrator mailbox
    orchestrator = Mailbox(owner_id="orchestrator-abc123")
    # Claude Code mailbox
    claude_code = Mailbox(owner_id="claude-code")
    # Simulate workflow execution with status updates
    phases = [
        ("planning", "Analyzing requirements"),
        ("implementation", "Writing code"),
        ("review", "Code review in progress"),
        ("testing", "Running tests"),
        ("completed", "Workflow complete")
    ]
    print("\nOrchestrator executing workflow with status updates...")
    for i, (phase, summary) in enumerate(phases):
        progress = (i + 1) / len(phases)
        # Send status update
        orchestrator.send(
            recipient="claude-code",
            msg_type=MessageType.STATUS,
            payload={
                'phase': phase,
                'progress': round(progress, 2),
                'summary': summary
            },
            ttl=300 # 5 minute TTL for status
        )
        print(f" [{progress:.0%}] {phase}: {summary}")
        time.sleep(0.5) # Simulate work
    # Claude Code checks status
    print("\nClaude Code checking status updates...")
    statuses = claude_code.receive(msg_type=MessageType.STATUS, limit=10)
    for status in statuses:
        payload = status.payload
        print(f" {status.sender}: {payload['phase']} ({payload['progress']:.0%}) - {payload['summary']}")
    # Cleanup
    orchestrator.clear_all()
    claude_code.clear_all()
    print("\n Example 2 complete\n")
def example_control_signals():
    """Example 3: Control signals for orchestrator management."""
    print("=" * 60)
    print("Example 3: Control Signals")
    print("=" * 60)
    claude_code = Mailbox(owner_id="claude-code")
    orchestrator = Mailbox(owner_id="orchestrator-xyz789")
    # Claude Code sends pause signal
    print("\nClaude Code sends PAUSE signal...")
    claude_code.send(
        recipient="orchestrator-xyz789",
        msg_type=MessageType.SIGNAL,
        payload={'signal': 'PAUSE'},
        priority=3, # Urgent
        ttl=600
    )
    # Orchestrator checks for signals
    print("Orchestrator checks mailbox for signals...")
    signals = orchestrator.receive(msg_type=MessageType.SIGNAL)
    for sig in signals:
        signal_type = sig.payload.get('signal')
        print(f" Received signal: {signal_type} (priority: {sig.priority})")
        if signal_type == 'PAUSE':
            print(" → Pausing execution and creating checkpoint...")
            # Simulate checkpoint
            time.sleep(0.5)
            # Send acknowledgment
            orchestrator.send(
                recipient="claude-code",
                msg_type=MessageType.STATUS,
                payload={'status': 'paused', 'checkpoint_id': 'cp_001'}
            )
    # Claude Code receives acknowledgment
    print("\nClaude Code checks for acknowledgment...")
    statuses = claude_code.receive(msg_type=MessageType.STATUS)
    for status in statuses:
        print(f" Orchestrator status: {status.payload}")
    # Later, send resume signal
    print("\nClaude Code sends RESUME signal...")
    claude_code.send(
        recipient="orchestrator-xyz789",
        msg_type=MessageType.SIGNAL,
        payload={'signal': 'RESUME'},
        priority=3
    )
    signals = orchestrator.receive(msg_type=MessageType.SIGNAL)
    for sig in signals:
        print(f" Received signal: {sig.payload.get('signal')}")
        print(" → Resuming execution from checkpoint...")
    # Cleanup
    claude_code.clear_all()
    orchestrator.clear_all()
    print("\n Example 3 complete\n")
def example_broadcast():
    """Example 4: Broadcasting messages to multiple orchestrators."""
    print("=" * 60)
    print("Example 4: Broadcasting")
    print("=" * 60)
    # Create multiple orchestrators
    claude_code = Mailbox(owner_id="claude-code")
    orch1 = Mailbox(owner_id="orchestrator-001")
    orch2 = Mailbox(owner_id="orchestrator-002")
    orch3 = Mailbox(owner_id="orchestrator-003")
    # Broadcast system announcement
    print("\nClaude Code broadcasts system announcement...")
    claude_code.broadcast(
        msg_type=MessageType.STATUS,
        payload={
            'announcement': 'System maintenance in 10 minutes',
            'action_required': 'checkpoint'
        },
        priority=2
    )
    # All orchestrators receive broadcast
    print("\nOrchestrators receive broadcast:")
    for i, orch in enumerate([orch1, orch2, orch3], 1):
        broadcasts = orch.receive_broadcast(limit=10)
        for msg in broadcasts:
            print(f" Orchestrator-{i:03d} received: {msg.payload['announcement']}")
            if msg.payload.get('action_required') == 'checkpoint':
                print(f" → Creating checkpoint...")
    # Cleanup
    claude_code.clear_all()
    orch1.clear_all()
    orch2.clear_all()
    orch3.clear_all()
    print("\n Example 4 complete\n")
def example_orchestrator_integration():
    """Example 5: Orchestrator with mailbox integration."""
    print("=" * 60)
    print("Example 5: Orchestrator Integration")
    print("=" * 60)
    class DemoOrchestrator(OrchestratorMailboxMixin):
        """Demo orchestrator with mailbox support."""
        def __init__(self, session_id: str):
            self.session_id = session_id
            self.paused = False
            self._init_mailbox()
        def execute_task(self, task_name: str):
            """Execute a task with signal checking and status reporting."""
            print(f"\n Executing task: {task_name}")
            # Check for control signals
            signal = self.check_mailbox(msg_type=MessageType.SIGNAL)
            if signal:
                self.handle_signal(signal)
            # Simulate work
            for i in range(5):
                progress = (i + 1) / 5
                # Check for pause
                if self.paused:
                    print(" [Paused] Waiting for resume...")
                    while self.paused:
                        sig = self.check_mailbox(msg_type=MessageType.SIGNAL)
                        if sig:
                            self.handle_signal(sig)
                        time.sleep(0.2)
                # Report progress
                self.report_status(
                    phase=task_name,
                    progress=progress,
                    summary=f"Step {i+1}/5"
                )
                print(f" [{progress:.0%}] Step {i+1}/5")
                time.sleep(0.3)
        def _pause(self):
            self.paused = True
            print(" → Orchestrator PAUSED")
        def _resume(self):
            self.paused = False
            print(" → Orchestrator RESUMED")
    # Create orchestrator
    print("\nCreating orchestrator...")
    orch = DemoOrchestrator(session_id="demo-001")
    # Start task in background (simulated with threading)
    import threading
    def run_task():
        orch.execute_task("data_processing")
    task_thread = threading.Thread(target=run_task, daemon=True)
    task_thread.start()
    # Wait a bit then send pause signal
    time.sleep(1)
    print("\n[Claude Code] Sending PAUSE signal...")
    send_control_signal("demo-001", "PAUSE")
    # Wait then resume
    time.sleep(1)
    print("\n[Claude Code] Sending RESUME signal...")
    send_control_signal("demo-001", "RESUME")
    # Wait for completion
    task_thread.join(timeout=5)
    # Check final progress
    progress = get_orchestrator_progress("demo-001")
    if progress:
        print(f"\n[Claude Code] Final status: {progress}")
    # Cleanup
    orch.cleanup_mailbox()
    print("\n Example 5 complete\n")
def example_convenience_functions():
    """Example 6: Using convenience functions."""
    print("=" * 60)
    print("Example 6: Convenience Functions")
    print("=" * 60)
    # Setup mailboxes
    claude_code = Mailbox(owner_id="claude-code")
    orchestrator = Mailbox(owner_id="orchestrator-123")
    # Send command using convenience function
    print("\nSending command via convenience function...")
    msg_id = send_command(
        sender="claude-code",
        recipient="orchestrator-123",
        action="execute",
        params={"task": "data_analysis", "timeout": 300}
    )
    print(f" Sent command: {msg_id}")
    # Receive and process
    messages = orchestrator.receive()
    for msg in messages:
        print(f" Received: {msg.payload}")
    # Send status using convenience function
    print("\nSending status via convenience function...")
    send_status(
        sender="orchestrator-123",
        recipient="claude-code",
        phase="analysis",
        progress=0.65,
        summary="Analyzing customer data"
    )
    statuses = claude_code.receive(msg_type=MessageType.STATUS)
    for status in statuses:
        print(f" Status: {status.payload}")
    # Send signal using convenience function
    print("\nSending signal via convenience function...")
    send_signal(
        sender="claude-code",
        recipient="orchestrator-123",
        signal="CHECKPOINT"
    )
    signals = orchestrator.receive(msg_type=MessageType.SIGNAL)
    for sig in signals:
        print(f" Signal: {sig.payload['signal']}")
    # Cleanup
    claude_code.clear_all()
    orchestrator.clear_all()
    print("\n Example 6 complete\n")
def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("MAILBOX SYSTEM - USAGE EXAMPLES")
    print("=" * 60 + "\n")
    examples = [
        ("Basic Messaging", example_basic_messaging),
        ("Status Reporting", example_status_reporting),
        ("Control Signals", example_control_signals),
        ("Broadcasting", example_broadcast),
        ("Orchestrator Integration", example_orchestrator_integration),
        ("Convenience Functions", example_convenience_functions),
    ]
    for i, (name, func) in enumerate(examples, 1):
        try:
            func()
        except Exception as e:
            print(f"\n Example {i} ({name}) failed: {e}\n")
            import traceback
            traceback.print_exc()
    print("=" * 60)
    print("All examples complete!")
    print("=" * 60 + "\n")
if __name__ == "__main__":
    main()
