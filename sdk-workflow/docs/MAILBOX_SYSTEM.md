# Mailbox System - Inter-Orchestrator Communication
## Overview
The mailbox system provides lightweight, token-efficient IPC (Inter-Process Communication) for orchestrators using file-based message passing. It enables Claude Code to communicate with running orchestrators, orchestrators to communicate with each other, and status monitoring without complex network protocols.
## Key Features
- **Token Efficient**: Uses compact JSON format with short field names (avg 100 tokens per message)
- **File-Based**: Simple, reliable persistence using JSON files
- **Priority System**: 0=low, 1=normal, 2=high, 3=urgent
- **Auto-Cleanup**: TTL-based message expiration
- **Broadcast Support**: Send messages to all orchestrators
- **Type Safety**: Enum-based message types
## Architecture
### Directory Structure
```
~/.claude/sdk-workflow/mailbox/
├── claude-code/              # Claude Code's mailbox
│   ├── inbox/               # Incoming messages
│   └── outbox/              # Sent messages (tracking)
├── orchestrator-abc123/     # Per-session orchestrator mailbox
│   ├── inbox/
│   └── outbox/
├── orchestrator-xyz789/
│   ├── inbox/
│   └── outbox/
└── broadcast/               # Broadcast messages (all read)
```
### Message Format
**File naming**: `{timestamp}_{msgid}.json`
**Compact JSON** (token-optimized):
```json
{
  "i": "abc12345",
  "s": "claude-code",
  "r": "orchestrator-123",
  "t": "cmd",
  "p": {"action": "pause"},
  "ts": 1234567890.123,
  "pr": 2,
  "ttl": 3600
}
```
**Field mapping**:
- `i` → id (message UUID)
- `s` → sender
- `r` → recipient
- `t` → type (cmd, qry, rsp, sts, sig)
- `p` → payload
- `ts` → timestamp
- `pr` → priority
- `ttl` → ttl_seconds
- `rto` → reply_to (optional)
## Message Types
```python
class MessageType(Enum):
    COMMAND = 'cmd'      # Execute action
    QUERY = 'qry'        # Request information
    RESPONSE = 'rsp'     # Reply to query
    STATUS = 'sts'       # Progress update
    SIGNAL = 'sig'       # Control signal (PAUSE, RESUME, ABORT)
```
## Usage
### Basic Usage
```python
from sdk_workflow.core.mailbox import Mailbox, MessageType
# Create mailbox for orchestrator
mailbox = Mailbox(owner_id="orchestrator-123")
# Send command
msg_id = mailbox.send(
    recipient="claude-code",
    msg_type=MessageType.STATUS,
    payload={
        'phase': 'implementation',
        'progress': 0.75,
        'summary': 'Implementing features'
    }
)
# Receive messages
messages = mailbox.receive(limit=10)
for msg in messages:
    print(f"From {msg.sender}: {msg.payload}")
# Check for control signals
signals = mailbox.receive(msg_type=MessageType.SIGNAL, limit=1)
if signals:
    signal = signals[0].payload.get('signal')
    if signal == 'PAUSE':
        # Handle pause
        pass
```
### Orchestrator Integration
```python
from sdk_workflow.core.mailbox_integration import OrchestratorMailboxMixin
class MyOrchestrator(OrchestratorMailboxMixin):
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._init_mailbox()
    def execute_phase(self, phase: str):
        # Check for control signals
        signal = self.check_mailbox()
        if signal:
            self.handle_signal(signal)
        # Execute phase work
        # ...
        # Report progress
        self.report_status(
            phase=phase,
            progress=0.5,
            summary='Processing data'
        )
```
### Convenience Functions
```python
from sdk_workflow.core.mailbox import send_command, send_status, send_signal
# Send command from Claude Code to orchestrator
send_command(
    sender='claude-code',
    recipient='orchestrator-123',
    action='pause',
    params={'checkpoint': True}
)
# Send status from orchestrator to Claude Code
send_status(
    sender='orchestrator-123',
    recipient='claude-code',
    phase='testing',
    progress=0.9,
    summary='Running tests'
)
# Send control signal
send_signal(
    sender='claude-code',
    recipient='orchestrator-123',
    signal='RESUME'
)
```
## CLI Commands
### Check Mailbox
```bash
# Check Claude Code's mailbox
python -m sdk_workflow mailbox check
# Check specific orchestrator's mailbox
python -m sdk_workflow mailbox check --owner orchestrator-123
# Filter by message type
python -m sdk_workflow mailbox check --type signal
# Delete messages after reading
python -m sdk_workflow mailbox check --delete
```
### Send Message
```bash
# Send command to orchestrator
python -m sdk_workflow mailbox send \
  --to orchestrator-123 \
  --type command \
  --payload '{"action":"pause"}'
# Send with priority
python -m sdk_workflow mailbox send \
  --to orchestrator-123 \
  --type signal \
  --payload '{"signal":"ABORT"}' \
  --priority 3
```
### List Mailboxes
```bash
# List all active mailboxes
python -m sdk_workflow mailbox list
# Show message counts
python -m sdk_workflow mailbox list --show-counts
```
### Broadcast Message
```bash
# Broadcast to all orchestrators
python -m sdk_workflow mailbox broadcast \
  --type status \
  --payload '{"announcement":"System maintenance in 5 minutes"}'
```
### Cleanup
```bash
# Remove expired messages
python -m sdk_workflow mailbox cleanup --owner claude-code
# Clear all messages (requires confirmation)
python -m sdk_workflow mailbox clear --owner orchestrator-123 --confirm
```
## Common Patterns
### 1. Status Reporting (Orchestrator → Claude Code)
```python
# From orchestrator
mailbox = Mailbox("orchestrator-123")
# Report phase completion
mailbox.send(
    recipient="claude-code",
    msg_type=MessageType.STATUS,
    payload={
        'phase': 'planning',
        'progress': 1.0,
        'summary': 'Planning complete, starting implementation'
    },
    ttl=300  # Status expires in 5 minutes
)
```
### 2. Control Signals (Claude Code → Orchestrator)
```python
# From Claude Code
mailbox = Mailbox("claude-code")
# Pause orchestrator
mailbox.send(
    recipient="orchestrator-123",
    msg_type=MessageType.SIGNAL,
    payload={'signal': 'PAUSE'},
    priority=3,  # Urgent
    ttl=600
)
# From Orchestrator - check for signals
orchestrator_mailbox = Mailbox("orchestrator-123")
signals = orchestrator_mailbox.receive(msg_type=MessageType.SIGNAL, limit=1)
if signals and signals[0].payload.get('signal') == 'PAUSE':
    # Pause execution
    create_checkpoint()
    wait_for_resume()
```
### 3. Query-Response Pattern
```python
# Orchestrator sends query
orchestrator_mb = Mailbox("orchestrator-123")
msg_id = orchestrator_mb.send(
    recipient="orchestrator-456",
    msg_type=MessageType.QUERY,
    payload={'query': 'capabilities'}
)
# Other orchestrator receives and replies
other_mb = Mailbox("orchestrator-456")
queries = other_mb.receive(msg_type=MessageType.QUERY)
for query in queries:
    other_mb.reply(
        original_msg=query,
        payload={'capabilities': ['planning', 'implementation']}
    )
# Original orchestrator receives response
responses = orchestrator_mb.receive(msg_type=MessageType.RESPONSE)
```
### 4. Broadcast Announcements
```python
# Claude Code broadcasts system update
mailbox = Mailbox("claude-code")
mailbox.broadcast(
    msg_type=MessageType.STATUS,
    payload={
        'announcement': 'System maintenance in 10 minutes',
        'action_required': 'checkpoint'
    }
)
# All orchestrators can receive
orchestrator_mb = Mailbox("orchestrator-123")
broadcasts = orchestrator_mb.receive_broadcast()
for msg in broadcasts:
    if msg.payload.get('action_required') == 'checkpoint':
        create_checkpoint()
```
## Best Practices
### 1. Token Efficiency
- **Keep payloads minimal**: Only include essential data
- **Use short keys**: Custom payload keys should be brief
- **Round numbers**: `progress: 0.75` not `progress: 0.7532141`
- **Avoid nested objects**: Flatten when possible
```python
# Good - minimal payload
payload = {'phase': 'impl', 'prog': 0.75, 'err': 0}
# Bad - verbose payload
payload = {
    'current_phase': 'implementation',
    'progress_percentage': 0.753214159,
    'error_count': 0,
    'metadata': {'details': 'lots of nested data'}
}
```
### 2. TTL Selection
- **Status updates**: 300s (5 min) - short-lived
- **Commands**: 3600s (1 hour) - default
- **Signals**: 600s (10 min) - moderate urgency
- **Queries**: 1800s (30 min) - need response time
### 3. Priority Levels
- **0 (Low)**: Non-urgent notifications, FYI messages
- **1 (Normal)**: Regular status updates, queries
- **2 (High)**: Important commands, critical updates
- **3 (Urgent)**: Control signals (PAUSE, ABORT), errors
### 4. Cleanup
```python
# Periodic cleanup in orchestrator
class MyOrchestrator:
    def run(self):
        try:
            # Execute workflow
            pass
        finally:
            # Always cleanup on exit
            self.mailbox.cleanup_expired()
```
### 5. Error Handling
```python
# Robust message receiving
try:
    messages = mailbox.receive(msg_type=MessageType.SIGNAL)
    for msg in messages:
        try:
            handle_signal(msg)
        except Exception as e:
            logger.error(f"Error handling message {msg.id}: {e}")
            # Send error response
            mailbox.reply(
                original_msg=msg,
                payload={'error': str(e), 'status': 'failed'}
            )
except Exception as e:
    logger.error(f"Mailbox error: {e}")
```
## Performance Characteristics
### Message Size
- **Header overhead**: ~80 tokens
- **Typical payload**: 20-50 tokens
- **Average total**: 100-150 tokens per message
### File Operations
- **Send**: 1 write (recipient inbox) + 1 write (sender outbox)
- **Receive**: N reads + N deletes (if delete_after_read=True)
- **Cleanup**: N reads + M deletes (M expired)
### Scalability
- **Messages per mailbox**: Tested up to 1000 messages
- **Mailboxes**: Tested up to 100 concurrent mailboxes
- **Filesystem**: Standard filesystem (no special requirements)
## Troubleshooting
### Messages Not Received
1. **Check mailbox ID**: Ensure sender/recipient IDs match exactly
2. **Check expiry**: Messages may have expired (check TTL)
3. **Check filters**: Verify msg_type filter isn't excluding messages
4. **Check filesystem**: Ensure mailbox directories exist and are writable
```python
# Debug mailbox state
mailbox = Mailbox("orchestrator-123")
print(f"Inbox: {mailbox.inbox_dir}")
print(f"Pending: {mailbox.get_pending_count()}")
print(f"Files: {list(mailbox.inbox_dir.glob('*.json'))}")
```
### High Message Volume
```python
# Implement rate limiting
import time
class RateLimitedMailbox(Mailbox):
    def send(self, *args, **kwargs):
        time.sleep(0.1)  # 10 messages/second max
        return super().send(*args, **kwargs)
```
### Corrupt Messages
```python
# Cleanup will automatically remove corrupt files
count = mailbox.cleanup_expired()
# Also removes unreadable JSON files
```
## Security Considerations
1. **No Authentication**: Messages are not authenticated - trust the filesystem
2. **No Encryption**: Messages are plain JSON - don't send secrets
3. **Filesystem Permissions**: Mailbox security relies on OS filesystem permissions
4. **No Validation**: Payload contents are not validated - validate on receive
## Integration Examples
### With StreamingOrchestrator
```python
from sdk_workflow.core.mailbox_integration import StreamingOrchestratorExample
orchestrator = StreamingOrchestratorExample(session_id="abc123")
phases = ['planning', 'implementation', 'review', 'testing']
orchestrator.execute_workflow(phases)
# Claude Code can monitor
from sdk_workflow.core.mailbox_integration import get_orchestrator_progress
progress = get_orchestrator_progress('abc123')
print(f"Phase: {progress['phase']}, Progress: {progress['progress']}")
```
### Polling for Status
```python
from sdk_workflow.core.mailbox_integration import poll_orchestrator_status
# Poll orchestrator for status updates (blocks until timeout)
status_msg = poll_orchestrator_status('orchestrator-123', timeout=60)
if status_msg:
    print(f"Latest status: {status_msg.payload}")
```
### Sending Control Signals
```python
from sdk_workflow.core.mailbox_integration import send_control_signal
# Pause orchestrator
send_control_signal('orchestrator-123', 'PAUSE')
# Resume after user intervention
send_control_signal('orchestrator-123', 'RESUME')
# Abort on error
send_control_signal('orchestrator-123', 'ABORT')
```
## Future Enhancements
Potential improvements for future versions:
1. **Message Queues**: Priority queues for better message ordering
2. **Atomic Operations**: File locking for concurrent access
3. **Compression**: Optional gzip compression for large payloads
4. **Encryption**: Optional message encryption for sensitive data
5. **Message History**: Persistent message history with search
6. **Webhooks**: HTTP callbacks for message events
7. **Batch Operations**: Batch send/receive for efficiency
## API Reference
See the following modules for detailed API documentation:
- `core/mailbox.py` - Core mailbox implementation
- `core/mailbox_integration.py` - Integration helpers and mixins
- `cli/main.py` - CLI command handlers
## Testing
Run comprehensive tests:
```bash
# Run all mailbox tests
pytest tests/test_mailbox.py -v
# Run specific test
pytest tests/test_mailbox.py::TestMailbox::test_send_message -v
# Run with coverage
pytest tests/test_mailbox.py --cov=sdk_workflow.core.mailbox
```
## License
Part of the SDK Workflow project. See main LICENSE file.
