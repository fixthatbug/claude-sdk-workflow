# Mailbox System - Quick Start Guide
## What is the Mailbox System?
A lightweight, file-based messaging system for communication between Claude Code and orchestrators. Think of it as a simple mailbox where orchestrators and Claude Code can send and receive messages to coordinate work.
## Installation
The mailbox system is included in the SDK workflow. No additional installation required.
```python
from sdk_workflow.core.mailbox import Mailbox, MessageType
```
## 5-Minute Quick Start
### 1. Basic Message Exchange
```python
from sdk_workflow.core.mailbox import Mailbox, MessageType
# Create mailboxes
alice = Mailbox(owner_id="alice")
bob = Mailbox(owner_id="bob")
# Alice sends message to Bob
alice.send(
    recipient="bob",
    msg_type=MessageType.COMMAND,
    payload={"action": "process", "data": "hello"}
)
# Bob receives message
messages = bob.receive()
print(messages[0].payload)  # {'action': 'process', 'data': 'hello'}
```
### 2. Orchestrator Status Updates
```python
from sdk_workflow.core.mailbox import send_status
# Orchestrator sends status to Claude Code
send_status(
    sender="orchestrator-123",
    recipient="claude-code",
    phase="implementation",
    progress=0.75,
    summary="Implementing user authentication"
)
```
### 3. Control Signals
```python
from sdk_workflow.core.mailbox import send_signal, Mailbox, MessageType
# Claude Code sends pause signal to orchestrator
send_signal(
    sender="claude-code",
    recipient="orchestrator-123",
    signal="PAUSE"
)
# Orchestrator checks for signals
orchestrator = Mailbox("orchestrator-123")
signals = orchestrator.receive(msg_type=MessageType.SIGNAL)
if signals:
    signal = signals[0].payload.get('signal')
    if signal == 'PAUSE':
        # Pause execution
        pass
```
### 4. Using with Orchestrators
```python
from sdk_workflow.core.mailbox_integration import OrchestratorMailboxMixin
class MyOrchestrator(OrchestratorMailboxMixin):
    def __init__(self, session_id):
        self.session_id = session_id
        self._init_mailbox()
    def run(self):
        # Check for control signals
        signal = self.check_mailbox()
        if signal:
            self.handle_signal(signal)
        # Report progress
        self.report_status(
            phase="planning",
            progress=0.5,
            summary="Creating execution plan"
        )
```
## CLI Commands
### Check Your Mailbox
```bash
python -m sdk_workflow mailbox check
```
### Send a Message
```bash
python -m sdk_workflow mailbox send \
  --to orchestrator-123 \
  --type command \
  --payload '{"action":"pause"}'
```
### List All Mailboxes
```bash
python -m sdk_workflow mailbox list --show-counts
```
### Cleanup Old Messages
```bash
python -m sdk_workflow mailbox cleanup
```
## Common Use Cases
### Use Case 1: Monitor Orchestrator Progress
**From Orchestrator:**
```python
# Report progress during execution
self.report_status(
    phase="testing",
    progress=0.9,
    summary="Running unit tests"
)
```
**From Claude Code:**
```bash
# Check status via CLI
python -m sdk_workflow mailbox check --type status
```
### Use Case 2: Pause/Resume Orchestrator
**From Claude Code:**
```bash
# Pause orchestrator
python -m sdk_workflow mailbox send \
  --to orchestrator-123 \
  --type signal \
  --payload '{"signal":"PAUSE"}' \
  --priority 3
# Resume orchestrator
python -m sdk_workflow mailbox send \
  --to orchestrator-123 \
  --type signal \
  --payload '{"signal":"RESUME"}' \
  --priority 3
```
**From Orchestrator:**
```python
# Check for signals between phases
signal = self.check_mailbox(msg_type=MessageType.SIGNAL)
if signal:
    self.handle_signal(signal)  # Automatically handles PAUSE/RESUME
```
### Use Case 3: Broadcast System Announcements
```python
# Claude Code broadcasts to all orchestrators
mailbox = Mailbox("claude-code")
mailbox.broadcast(
    msg_type=MessageType.STATUS,
    payload={"announcement": "System maintenance in 5 minutes"}
)
```
## Message Types Explained
| Type | Code | Purpose | Example |
|------|------|---------|---------|
| COMMAND | `cmd` | Execute an action | `{"action": "pause"}` |
| QUERY | `qry` | Request information | `{"query": "status"}` |
| RESPONSE | `rsp` | Reply to query | `{"status": "running"}` |
| STATUS | `sts` | Progress update | `{"phase": "testing", "progress": 0.8}` |
| SIGNAL | `sig` | Control signal | `{"signal": "PAUSE"}` |
## Priority Levels
- **0 (Low)**: FYI messages, non-urgent notifications
- **1 (Normal)**: Regular status updates (default)
- **2 (High)**: Important commands
- **3 (Urgent)**: Critical signals (PAUSE, ABORT)
## Where Are Messages Stored?
```
~/.claude/sdk-workflow/mailbox/
├── claude-code/
│   ├── inbox/     # Messages received by Claude Code
│   └── outbox/    # Messages sent by Claude Code
├── orchestrator-{session}/
│   ├── inbox/     # Messages for this orchestrator
│   └── outbox/    # Messages from this orchestrator
└── broadcast/     # Broadcast messages (all can read)
```
## Tips for Token Efficiency
1. **Keep payloads minimal** - only essential data
2. **Use short keys** - `prog` instead of `progress_percentage`
3. **Round numbers** - `0.75` instead of `0.753214159`
4. **Set appropriate TTL** - status updates expire quickly (300s)
```python
# Good - minimal payload (50 tokens)
payload = {"phase": "impl", "prog": 0.75, "ok": True}
# Bad - verbose payload (150 tokens)
payload = {
    "current_phase": "implementation",
    "progress_percentage": 0.753214159,
    "is_successful": True,
    "detailed_status": "Currently implementing authentication module"
}
```
## Running Examples
```bash
# Run all examples
python examples/mailbox_example.py
# Run tests
pytest tests/test_mailbox.py -v
```
## Troubleshooting
### Messages Not Appearing?
```python
# Check if messages exist
mailbox = Mailbox("claude-code")
count = mailbox.get_pending_count()
print(f"Pending messages: {count}")
# List inbox files
print(f"Inbox: {mailbox.inbox_dir}")
print(f"Files: {list(mailbox.inbox_dir.glob('*.json'))}")
```
### Clean Up Everything
```bash
# Clear all messages
python -m sdk_workflow mailbox clear --owner claude-code --confirm
```
### Debug Message Content
```python
# Peek at messages without deleting
messages = mailbox.peek(limit=10)
for msg in messages:
    print(f"ID: {msg.id}")
    print(f"From: {msg.sender}")
    print(f"Type: {msg.type}")
    print(f"Payload: {msg.payload}")
    print(f"Expired: {msg.is_expired()}")
    print("---")
```
## Next Steps
- **Full Documentation**: See [MAILBOX_SYSTEM.md](docs/MAILBOX_SYSTEM.md)
- **Integration Guide**: See `core/mailbox_integration.py`
- **API Reference**: See `core/mailbox.py`
- **Examples**: See `examples/mailbox_example.py`
- **Tests**: See `tests/test_mailbox.py`
## Support
For issues or questions:
1. Check the full documentation in `docs/MAILBOX_SYSTEM.md`
2. Review examples in `examples/mailbox_example.py`
3. Run tests to verify setup: `pytest tests/test_mailbox.py -v`
---
**Remember**: The mailbox system is designed for simplicity and token efficiency. Keep messages small, clean up regularly, and use appropriate TTLs!
