"""
File-based mailbox system for inter-orchestrator communication.
Provides lightweight, token-efficient IPC using JSON files.
.. deprecated:: 1.0.0
   The mailbox module is deprecated and will be removed in version 2.0.0.
   Please use the MessageBus system from sdk_workflow.communication.message_bus instead.
   See DEPRECATION.md for migration guide.
"""
# =============================================================================
# DEPRECATION WARNING
# =============================================================================
# This module is DEPRECATED and will be removed in a future version.
#
# The mailbox system has been replaced with TodoWrite-based progress tracking.
# This module is archived and should not be used for new development.
#
# Migration: Use TodoWrite tool for progress tracking instead.
# See: sdk_workflow/DEPRECATION.md for migration guide.
# =============================================================================
import warnings
warnings.warn(
    f"{__name__} is deprecated and will be removed. Use TodoWrite for progress tracking.",
    DeprecationWarning,
    stacklevel=2
)
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging
logger = logging.getLogger(__name__)
class MessageType(Enum):
    """Message types for IPC communication."""
    COMMAND = 'cmd' # Execute action
    QUERY = 'qry' # Request info
    RESPONSE = 'rsp' # Reply to query
    STATUS = 'sts' # Progress update
    SIGNAL = 'sig' # Control signal (PAUSE, RESUME, ABORT)
@dataclass
class Message:
    """Lightweight message for inter-orchestrator communication.
    Uses short field names to minimize token usage when serialized.
    """
    id: str # UUID
    sender: str # Orchestrator ID or 'claude-code'
    recipient: str # Target orchestrator ID or 'broadcast'
    type: MessageType # Message type
    payload: dict # Minimal structured data
    timestamp: float # Unix timestamp
    priority: int = 1 # 0=low, 1=normal, 2=high, 3=urgent
    ttl_seconds: int = 3600 # Time-to-live, auto-cleanup
    reply_to: Optional[str] = None # For response threading
    def to_compact_dict(self) -> Dict[str, Any]:
        """Convert to compact dictionary with short keys for token efficiency."""
        return {
            'i': self.id,
            's': self.sender,
            'r': self.recipient,
            't': self.type.value,
            'p': self.payload,
            'ts': self.timestamp,
            'pr': self.priority,
            'ttl': self.ttl_seconds,
            'rto': self.reply_to
        }
    @classmethod
    def from_compact_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Reconstruct message from compact dictionary."""
        msg_type = MessageType(data['t'])
        return cls(
            id=data['i'],
            sender=data['s'],
            recipient=data['r'],
            type=msg_type,
            payload=data['p'],
            timestamp=data['ts'],
            priority=data.get('pr', 1),
            ttl_seconds=data.get('ttl', 3600),
            reply_to=data.get('rto')
        )
    def is_expired(self) -> bool:
        """Check if message has exceeded its TTL."""
        return (time.time() - self.timestamp) > self.ttl_seconds
class Mailbox:
    """File-based mailbox for orchestrator IPC.
    Provides lightweight, token-efficient message passing using JSON files.
    Each orchestrator has inbox/outbox directories for messages.
    Directory structure:
        ~/.claude/sdk-workflow/mailbox/
        ├── claude-code/
        │ ├── inbox/
        │ └── outbox/
        ├── orchestrator-{session}/
        │ ├── inbox/
        │ └── outbox/
        └── broadcast/
    Message file format (token-optimized):
        {timestamp}_{msgid}.json
        {"i":"uuid","s":"sender","r":"recipient","t":"cmd","p":{},"ts":1234567890,"pr":1,"ttl":3600}
    """
    def __init__(
        self,
        owner_id: str,
        base_path: Optional[Path] = None,
        message_bus: Optional[Any] = None,
        publish_events: bool = False
    ):
        """Initialize mailbox for an orchestrator.
        .. deprecated:: 1.0.0
           Mailbox class is deprecated. Use MessageBus from sdk_workflow.communication.message_bus instead.
        Args:
            owner_id: Unique identifier for this mailbox owner (e.g., session ID)
            base_path: Optional custom base path for mailbox storage
            message_bus: Optional MessageBus for event publishing
            publish_events: Whether to publish mailbox operations to MessageBus (default: False)
        """
        warnings.warn(
            "Mailbox is deprecated and will be removed in version 2.0.0. "
            "Use MessageBus from sdk_workflow.communication.message_bus instead. "
            "See DEPRECATION.md for migration guide.",
            DeprecationWarning,
            stacklevel=2
        )
        self.owner_id = owner_id
        self.base_path = base_path or Path.home() / '.claude' / 'sdk-workflow' / 'mailbox'
        # Create mailbox directories
        self.owner_dir = self.base_path / owner_id
        self.inbox_dir = self.owner_dir / 'inbox'
        self.outbox_dir = self.owner_dir / 'outbox'
        self.broadcast_dir = self.base_path / 'broadcast'
        # Ensure directories exist
        self._ensure_directories()
        # Optional MessageBus integration
        self._event_publisher = None
        if publish_events:
            try:
                # Lazy import to avoid circular dependencies
                from sdk_workflow.communication.mailbox_events import MailboxEventPublisher
                self._event_publisher = MailboxEventPublisher(message_bus, auto_publish=True)
                logger.debug(f"Enabled MessageBus integration for {owner_id}")
            except ImportError:
                logger.warning(f"Could not import MailboxEventPublisher, events disabled")
        logger.debug(f"Initialized mailbox for {owner_id} at {self.owner_dir}")
    def _ensure_directories(self) -> None:
        """Create mailbox directory structure if it doesn't exist."""
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        self.broadcast_dir.mkdir(parents=True, exist_ok=True)
    def send(
        self,
        recipient: str,
        msg_type: MessageType,
        payload: dict,
        priority: int = 1,
        ttl: int = 3600
    ) -> str:
        """Send message to recipient's inbox.
        Args:
            recipient: Target orchestrator ID (e.g., 'claude-code', 'orchestrator-abc123')
            msg_type: Type of message
            payload: Message payload data (keep minimal for token efficiency)
            priority: Message priority (0=low, 1=normal, 2=high, 3=urgent)
            ttl: Time-to-live in seconds (default: 1 hour)
        Returns:
            Message ID
        """
        msg_id = str(uuid.uuid4())[:8] # Short ID for efficiency
        message = Message(
            id=msg_id,
            sender=self.owner_id,
            recipient=recipient,
            type=msg_type,
            payload=payload,
            timestamp=time.time(),
            priority=priority,
            ttl_seconds=ttl
        )
        # Write to recipient's inbox
        recipient_inbox = self.base_path / recipient / 'inbox'
        recipient_inbox.mkdir(parents=True, exist_ok=True)
        filename = f"{int(message.timestamp)}_{msg_id}.json"
        filepath = recipient_inbox / filename
        with open(filepath, 'w') as f:
            json.dump(message.to_compact_dict(), f, separators=(',', ':'))
        # Also track in outbox for sender
        outbox_file = self.outbox_dir / filename
        with open(outbox_file, 'w') as f:
            json.dump(message.to_compact_dict(), f, separators=(',', ':'))
        logger.debug(f"Sent {msg_type.value} message {msg_id} from {self.owner_id} to {recipient}")
        # Publish event to MessageBus if enabled
        if self._event_publisher:
            self._event_publisher.on_message_sent(message)
        return msg_id
    def receive(
        self,
        msg_type: Optional[MessageType] = None,
        limit: int = 10,
        delete_after_read: bool = True
    ) -> List[Message]:
        """Get messages from own inbox.
        Args:
            msg_type: Optional filter by message type
            limit: Maximum number of messages to retrieve
            delete_after_read: Whether to delete messages after reading (default: True)
        Returns:
            List of messages, sorted by priority (highest first) then timestamp
        """
        messages = []
        # Read from inbox
        if not self.inbox_dir.exists():
            return messages
        # Get all message files
        msg_files = sorted(self.inbox_dir.glob('*.json'), key=lambda p: p.stat().st_mtime)
        for msg_file in msg_files:
            try:
                with open(msg_file, 'r') as f:
                    data = json.load(f)
                msg = Message.from_compact_dict(data)
                # Skip expired messages
                if msg.is_expired():
                    msg_file.unlink() # Clean up expired
                    continue
                # Apply type filter
                if msg_type and msg.type != msg_type:
                    continue
                messages.append(msg)
                # Delete if requested
                if delete_after_read:
                    msg_file.unlink()
            except Exception as e:
                logger.error(f"Error reading message {msg_file}: {e}")
                # Clean up corrupted file
                msg_file.unlink(missing_ok=True)
        # Sort by priority (descending) then timestamp (ascending)
        messages.sort(key=lambda m: (-m.priority, m.timestamp))
        # Apply limit
        limited_messages = messages[:limit]
        # Publish events to MessageBus if enabled
        if self._event_publisher:
            for msg in limited_messages:
                # Publish received event
                self._event_publisher.on_message_received(msg, self.owner_id)
                # Also publish signal event for SIGNAL type messages
                if msg.type == MessageType.SIGNAL:
                    self._event_publisher.on_signal_received(msg, self.owner_id)
        return limited_messages
    def reply(self, original_msg: Message, payload: dict, ttl: int = 3600) -> str:
        """Reply to a message, threading via reply_to.
        Args:
            original_msg: The message being replied to
            payload: Reply payload data
            ttl: Time-to-live in seconds
        Returns:
            Message ID of the reply
        """
        return self.send(
            recipient=original_msg.sender,
            msg_type=MessageType.RESPONSE,
            payload=payload,
            priority=original_msg.priority, # Match original priority
            ttl=ttl
        )
    def broadcast(
        self,
        msg_type: MessageType,
        payload: dict,
        priority: int = 1,
        ttl: int = 3600
    ) -> str:
        """Send message to all orchestrators via broadcast directory.
        Args:
            msg_type: Type of message
            payload: Message payload data
            priority: Message priority
            ttl: Time-to-live in seconds
        Returns:
            Message ID
        """
        msg_id = str(uuid.uuid4())[:8]
        message = Message(
            id=msg_id,
            sender=self.owner_id,
            recipient='broadcast',
            type=msg_type,
            payload=payload,
            timestamp=time.time(),
            priority=priority,
            ttl_seconds=ttl
        )
        # Write to broadcast directory
        filename = f"{int(message.timestamp)}_{msg_id}.json"
        filepath = self.broadcast_dir / filename
        with open(filepath, 'w') as f:
            json.dump(message.to_compact_dict(), f, separators=(',', ':'))
        logger.debug(f"Broadcast {msg_type.value} message {msg_id} from {self.owner_id}")
        # Publish event to MessageBus if enabled
        if self._event_publisher:
            self._event_publisher.on_broadcast_sent(message)
        return msg_id
    def receive_broadcast(
        self,
        msg_type: Optional[MessageType] = None,
        limit: int = 10
    ) -> List[Message]:
        """Read broadcast messages without deleting them.
        Args:
            msg_type: Optional filter by message type
            limit: Maximum number of messages to retrieve
        Returns:
            List of broadcast messages
        """
        messages = []
        if not self.broadcast_dir.exists():
            return messages
        # Read broadcast messages (don't delete)
        msg_files = sorted(self.broadcast_dir.glob('*.json'), key=lambda p: p.stat().st_mtime)
        for msg_file in msg_files:
            try:
                with open(msg_file, 'r') as f:
                    data = json.load(f)
                msg = Message.from_compact_dict(data)
                # Skip expired messages
                if msg.is_expired():
                    msg_file.unlink() # Clean up expired
                    continue
                # Skip own messages
                if msg.sender == self.owner_id:
                    continue
                # Apply type filter
                if msg_type and msg.type != msg_type:
                    continue
                messages.append(msg)
            except Exception as e:
                logger.error(f"Error reading broadcast message {msg_file}: {e}")
        # Sort by priority then timestamp
        messages.sort(key=lambda m: (-m.priority, m.timestamp))
        return messages[:limit]
    def cleanup_expired(self) -> int:
        """Remove messages past their TTL from all directories.
        Returns:
            Count of messages removed
        """
        count = 0
        # Clean inbox
        if self.inbox_dir.exists():
            count += self._cleanup_directory(self.inbox_dir)
        # Clean outbox
        if self.outbox_dir.exists():
            count += self._cleanup_directory(self.outbox_dir)
        # Clean broadcast (only if owner is claude-code or admin)
        if self.owner_id in ('claude-code', 'admin') and self.broadcast_dir.exists():
            count += self._cleanup_directory(self.broadcast_dir)
        if count > 0:
            logger.debug(f"Cleaned up {count} expired messages")
        return count
    def _cleanup_directory(self, directory: Path) -> int:
        """Clean up expired messages from a directory.
        Args:
            directory: Directory to clean
        Returns:
            Count of files removed
        """
        count = 0
        for msg_file in directory.glob('*.json'):
            try:
                with open(msg_file, 'r') as f:
                    data = json.load(f)
                msg = Message.from_compact_dict(data)
                if msg.is_expired():
                    msg_file.unlink()
                    count += 1
            except Exception as e:
                logger.error(f"Error checking expiry for {msg_file}: {e}")
                # Remove corrupted files
                msg_file.unlink(missing_ok=True)
                count += 1
        return count
    def get_pending_count(self, msg_type: Optional[MessageType] = None) -> int:
        """Count of unread messages in inbox.
        Args:
            msg_type: Optional filter by message type
        Returns:
            Number of pending messages
        """
        if not self.inbox_dir.exists():
            return 0
        count = 0
        for msg_file in self.inbox_dir.glob('*.json'):
            try:
                with open(msg_file, 'r') as f:
                    data = json.load(f)
                msg = Message.from_compact_dict(data)
                # Skip expired
                if msg.is_expired():
                    continue
                # Apply type filter
                if msg_type and msg.type != msg_type:
                    continue
                count += 1
            except Exception:
                continue
        return count
    def peek(
        self,
        msg_type: Optional[MessageType] = None,
        limit: int = 10
    ) -> List[Message]:
        """Read messages without deleting them.
        Args:
            msg_type: Optional filter by message type
            limit: Maximum number of messages to retrieve
        Returns:
            List of messages (not deleted)
        """
        return self.receive(msg_type=msg_type, limit=limit, delete_after_read=False)
    def clear_all(self) -> int:
        """Delete all messages from inbox and outbox.
        Returns:
            Total count of messages deleted
        """
        count = 0
        # Clear inbox
        if self.inbox_dir.exists():
            for msg_file in self.inbox_dir.glob('*.json'):
                msg_file.unlink()
                count += 1
        # Clear outbox
        if self.outbox_dir.exists():
            for msg_file in self.outbox_dir.glob('*.json'):
                msg_file.unlink()
                count += 1
        logger.debug(f"Cleared {count} messages from {self.owner_id} mailbox")
        # Publish event to MessageBus if enabled
        if self._event_publisher:
            self._event_publisher.on_mailbox_cleared(self.owner_id, count)
        return count
    @staticmethod
    def list_mailboxes(base_path: Optional[Path] = None) -> List[str]:
        """List all active mailboxes.
        Args:
            base_path: Optional custom base path
        Returns:
            List of mailbox owner IDs
        """
        base = base_path or Path.home() / '.claude' / 'sdk-workflow' / 'mailbox'
        if not base.exists():
            return []
        mailboxes = []
        for item in base.iterdir():
            if item.is_dir() and item.name != 'broadcast':
                mailboxes.append(item.name)
        return sorted(mailboxes)
# Convenience functions for common patterns
def send_command(
    sender: str,
    recipient: str,
    action: str,
    params: Optional[Dict[str, Any]] = None,
    priority: int = 2
) -> str:
    """Send a command message.
    Args:
        sender: Sender ID
        recipient: Recipient ID
        action: Command action (e.g., 'pause', 'resume', 'abort')
        params: Optional command parameters
        priority: Message priority (default: high)
    Returns:
        Message ID
    """
    mailbox = Mailbox(sender)
    payload = {'action': action}
    if params:
        payload['params'] = params
    return mailbox.send(
        recipient=recipient,
        msg_type=MessageType.COMMAND,
        payload=payload,
        priority=priority
    )
def send_status(
    sender: str,
    recipient: str,
    phase: str,
    progress: float,
    summary: str
) -> str:
    """Send a status update message.
    Args:
        sender: Sender ID
        recipient: Recipient ID (typically 'claude-code')
        phase: Current phase name
        progress: Progress as float 0.0-1.0
        summary: Brief status summary
    Returns:
        Message ID
    """
    mailbox = Mailbox(sender)
    return mailbox.send(
        recipient=recipient,
        msg_type=MessageType.STATUS,
        payload={
            'phase': phase,
            'progress': round(progress, 2), # Limit precision for token efficiency
            'summary': summary
        },
        priority=1,
        ttl=300 # Status updates expire quickly (5 min)
    )
def send_status_compact(
    sender: str,
    recipient: str,
    phase: str,
    progress: float,
    state: str,
    summary: str,
    tokens: Optional[int] = None,
    cost: Optional[float] = None,
    priority: int = 1,
    ttl: int = 300
) -> str:
    """Send a status update using compact protocol (ph, pg, st, sm, tk, cs).
    This function uses the compact StatusProtocol for token-efficient messaging.
    Args:
        sender: Sender ID
        recipient: Recipient ID (typically 'claude-code')
        phase: Current phase name (will be truncated to 4 chars)
        progress: Progress as float 0.0-1.0
        state: State code ('run', 'pau', 'ok', 'err', 'wai', 'pen', 'can')
        summary: Brief status summary (will be truncated to 50 chars)
        tokens: Optional token usage count
        cost: Optional cost in USD
        priority: Message priority (default: normal)
        ttl: Time-to-live in seconds (default: 300)
    Returns:
        Message ID
    Example:
        send_status_compact(
            sender="orchestrator-123",
            recipient="claude-code",
            phase="impl",
            progress=0.75,
            state="run",
            summary="Writing tests",
            tokens=1234,
            cost=0.05
        )
    """
    from .mailbox_protocol import StatusProtocol, StateCode
    # Convert state string to StateCode
    try:
        state_code = StateCode(state) if isinstance(state, str) else state
    except ValueError:
        logger.warning(f"Unknown state code '{state}', using RUNNING")
        state_code = StateCode.RUNNING
    status = StatusProtocol(
        ph=phase,
        pg=progress,
        st=state_code,
        sm=summary,
        tk=tokens,
        cs=cost
    )
    mailbox = Mailbox(sender)
    return mailbox.send(
        recipient=recipient,
        msg_type=MessageType.STATUS,
        payload=status.to_payload(),
        priority=priority,
        ttl=ttl
    )
def send_signal(
    sender: str,
    recipient: str,
    signal: str,
    priority: int = 3
) -> str:
    """Send a control signal.
    Args:
        sender: Sender ID
        recipient: Recipient ID
        signal: Signal type ('PAUSE', 'RESUME', 'ABORT', etc.)
        priority: Message priority (default: urgent)
    Returns:
        Message ID
    """
    mailbox = Mailbox(sender)
    return mailbox.send(
        recipient=recipient,
        msg_type=MessageType.SIGNAL,
        payload={'signal': signal.upper()},
        priority=priority,
        ttl=600 # Signals valid for 10 minutes
    )
