"""
Unit tests for the mailbox system.
Tests message sending, receiving, expiry, and cleanup.
"""
import json
import time
import tempfile
from pathlib import Path
import pytest
from sdk_workflow.core.mailbox import (
    Mailbox,
    Message,
    MessageType,
    send_command,
    send_status,
    send_signal
)
@pytest.fixture
def temp_mailbox_dir(tmp_path):
    """Create temporary mailbox directory for testing."""
    return tmp_path / "test_mailbox"
@pytest.fixture
def mailbox_alice(temp_mailbox_dir):
    """Create mailbox for Alice."""
    return Mailbox(owner_id="alice", base_path=temp_mailbox_dir)
@pytest.fixture
def mailbox_bob(temp_mailbox_dir):
    """Create mailbox for Bob."""
    return Mailbox(owner_id="bob", base_path=temp_mailbox_dir)
class TestMessage:
    """Tests for Message class."""
    def test_message_creation(self):
        """Test creating a message."""
        msg = Message(
            id="test123",
            sender="alice",
            recipient="bob",
            type=MessageType.COMMAND,
            payload={"action": "test"},
            timestamp=time.time(),
            priority=1,
            ttl_seconds=3600
        )
        assert msg.id == "test123"
        assert msg.sender == "alice"
        assert msg.recipient == "bob"
        assert msg.type == MessageType.COMMAND
        assert msg.payload == {"action": "test"}
    def test_message_to_compact_dict(self):
        """Test message serialization to compact dict."""
        msg = Message(
            id="test123",
            sender="alice",
            recipient="bob",
            type=MessageType.COMMAND,
            payload={"action": "test"},
            timestamp=1234567890.0,
            priority=2,
            ttl_seconds=3600
        )
        compact = msg.to_compact_dict()
        assert compact['i'] == "test123"
        assert compact['s'] == "alice"
        assert compact['r'] == "bob"
        assert compact['t'] == "cmd"
        assert compact['p'] == {"action": "test"}
        assert compact['ts'] == 1234567890.0
        assert compact['pr'] == 2
        assert compact['ttl'] == 3600
    def test_message_from_compact_dict(self):
        """Test message deserialization from compact dict."""
        compact = {
            'i': "test123",
            's': "alice",
            'r': "bob",
            't': "cmd",
            'p': {"action": "test"},
            'ts': 1234567890.0,
            'pr': 2,
            'ttl': 3600
        }
        msg = Message.from_compact_dict(compact)
        assert msg.id == "test123"
        assert msg.sender == "alice"
        assert msg.recipient == "bob"
        assert msg.type == MessageType.COMMAND
        assert msg.payload == {"action": "test"}
        assert msg.timestamp == 1234567890.0
        assert msg.priority == 2
        assert msg.ttl_seconds == 3600
    def test_message_expiry(self):
        """Test message expiry detection."""
        # Not expired
        msg = Message(
            id="test123",
            sender="alice",
            recipient="bob",
            type=MessageType.COMMAND,
            payload={},
            timestamp=time.time(),
            ttl_seconds=3600
        )
        assert not msg.is_expired()
        # Expired
        msg_expired = Message(
            id="test456",
            sender="alice",
            recipient="bob",
            type=MessageType.COMMAND,
            payload={},
            timestamp=time.time() - 7200, # 2 hours ago
            ttl_seconds=3600 # 1 hour TTL
        )
        assert msg_expired.is_expired()
class TestMailbox:
    """Tests for Mailbox class."""
    def test_mailbox_initialization(self, temp_mailbox_dir):
        """Test mailbox initialization creates directories."""
        mailbox = Mailbox(owner_id="test_user", base_path=temp_mailbox_dir)
        assert mailbox.owner_id == "test_user"
        assert mailbox.inbox_dir.exists()
        assert mailbox.outbox_dir.exists()
        assert mailbox.broadcast_dir.exists()
    def test_send_message(self, mailbox_alice, mailbox_bob):
        """Test sending a message."""
        msg_id = mailbox_alice.send(
            recipient="bob",
            msg_type=MessageType.COMMAND,
            payload={"action": "test"},
            priority=1,
            ttl=3600
        )
        assert msg_id is not None
        assert len(msg_id) == 8 # Short ID
        # Check message exists in Bob's inbox
        inbox_files = list(mailbox_bob.inbox_dir.glob("*.json"))
        assert len(inbox_files) == 1
        # Verify message content
        with open(inbox_files[0], 'r') as f:
            data = json.load(f)
        assert data['s'] == "alice"
        assert data['r'] == "bob"
        assert data['t'] == "cmd"
        assert data['p'] == {"action": "test"}
    def test_receive_message(self, mailbox_alice, mailbox_bob):
        """Test receiving messages."""
        # Alice sends to Bob
        mailbox_alice.send(
            recipient="bob",
            msg_type=MessageType.COMMAND,
            payload={"action": "test1"},
            priority=1
        )
        mailbox_alice.send(
            recipient="bob",
            msg_type=MessageType.QUERY,
            payload={"query": "test2"},
            priority=2
        )
        # Bob receives messages
        messages = mailbox_bob.receive(limit=10)
        assert len(messages) == 2
        # Should be sorted by priority (descending)
        assert messages[0].type == MessageType.QUERY # priority 2
        assert messages[1].type == MessageType.COMMAND # priority 1
    def test_receive_with_filter(self, mailbox_alice, mailbox_bob):
        """Test receiving messages with type filter."""
        # Send different types
        mailbox_alice.send(
            recipient="bob",
            msg_type=MessageType.COMMAND,
            payload={"action": "test"}
        )
        mailbox_alice.send(
            recipient="bob",
            msg_type=MessageType.STATUS,
            payload={"status": "running"}
        )
        # Receive only STATUS messages
        messages = mailbox_bob.receive(msg_type=MessageType.STATUS)
        assert len(messages) == 1
        assert messages[0].type == MessageType.STATUS
    def test_receive_deletes_messages(self, mailbox_alice, mailbox_bob):
        """Test that receive deletes messages by default."""
        mailbox_alice.send(
            recipient="bob",
            msg_type=MessageType.COMMAND,
            payload={"action": "test"}
        )
        # First receive - should get message
        messages = mailbox_bob.receive(delete_after_read=True)
        assert len(messages) == 1
        # Second receive - should be empty
        messages = mailbox_bob.receive()
        assert len(messages) == 0
    def test_peek_doesnt_delete(self, mailbox_alice, mailbox_bob):
        """Test that peek doesn't delete messages."""
        mailbox_alice.send(
            recipient="bob",
            msg_type=MessageType.COMMAND,
            payload={"action": "test"}
        )
        # Peek at messages
        messages = mailbox_bob.peek()
        assert len(messages) == 1
        # Peek again - should still be there
        messages = mailbox_bob.peek()
        assert len(messages) == 1
    def test_reply_to_message(self, mailbox_alice, mailbox_bob):
        """Test replying to a message."""
        # Alice sends query to Bob
        mailbox_alice.send(
            recipient="bob",
            msg_type=MessageType.QUERY,
            payload={"query": "status"}
        )
        # Bob receives and replies
        messages = mailbox_bob.receive()
        original_msg = messages[0]
        mailbox_bob.reply(
            original_msg=original_msg,
            payload={"status": "running"}
        )
        # Alice receives reply
        replies = mailbox_alice.receive()
        assert len(replies) == 1
        assert replies[0].type == MessageType.RESPONSE
        assert replies[0].sender == "bob"
    def test_broadcast_message(self, mailbox_alice, mailbox_bob):
        """Test broadcasting a message."""
        msg_id = mailbox_alice.broadcast(
            msg_type=MessageType.STATUS,
            payload={"announcement": "system update"}
        )
        assert msg_id is not None
        # Bob should be able to read broadcast
        broadcasts = mailbox_bob.receive_broadcast()
        assert len(broadcasts) == 1
        assert broadcasts[0].payload["announcement"] == "system update"
    def test_receive_broadcast_excludes_own_messages(self, mailbox_alice):
        """Test that receive_broadcast excludes sender's own messages."""
        # Alice broadcasts
        mailbox_alice.broadcast(
            msg_type=MessageType.STATUS,
            payload={"test": "broadcast"}
        )
        # Alice shouldn't see her own broadcast
        broadcasts = mailbox_alice.receive_broadcast()
        assert len(broadcasts) == 0
    def test_cleanup_expired_messages(self, mailbox_alice, mailbox_bob):
        """Test cleanup of expired messages."""
        # Send message with short TTL
        mailbox_alice.send(
            recipient="bob",
            msg_type=MessageType.COMMAND,
            payload={"action": "test"},
            ttl=1 # 1 second TTL
        )
        # Wait for expiry
        time.sleep(2)
        # Cleanup should remove it
        count = mailbox_bob.cleanup_expired()
        assert count == 1
        # Verify inbox is empty
        messages = mailbox_bob.receive()
        assert len(messages) == 0
    def test_get_pending_count(self, mailbox_alice, mailbox_bob):
        """Test getting count of pending messages."""
        # Initially empty
        assert mailbox_bob.get_pending_count() == 0
        # Send some messages
        mailbox_alice.send("bob", MessageType.COMMAND, {"action": "test1"})
        mailbox_alice.send("bob", MessageType.STATUS, {"status": "ok"})
        # Count should be 2
        assert mailbox_bob.get_pending_count() == 2
        # Count with filter
        assert mailbox_bob.get_pending_count(msg_type=MessageType.COMMAND) == 1
    def test_clear_all_messages(self, mailbox_alice, mailbox_bob):
        """Test clearing all messages."""
        # Send some messages
        mailbox_alice.send("bob", MessageType.COMMAND, {"action": "test1"})
        mailbox_alice.send("bob", MessageType.COMMAND, {"action": "test2"})
        # Clear Bob's mailbox
        count = mailbox_bob.clear_all()
        assert count == 2
        # Verify empty
        assert mailbox_bob.get_pending_count() == 0
    def test_list_mailboxes(self, temp_mailbox_dir):
        """Test listing all active mailboxes."""
        # Create several mailboxes
        Mailbox("alice", base_path=temp_mailbox_dir)
        Mailbox("bob", base_path=temp_mailbox_dir)
        Mailbox("charlie", base_path=temp_mailbox_dir)
        # List should show all
        mailboxes = Mailbox.list_mailboxes(base_path=temp_mailbox_dir)
        assert len(mailboxes) == 3
        assert "alice" in mailboxes
        assert "bob" in mailboxes
        assert "charlie" in mailboxes
class TestConvenienceFunctions:
    """Tests for convenience functions."""
    def test_send_command(self, temp_mailbox_dir):
        """Test send_command convenience function."""
        # Create mailboxes with custom base path
        sender_mb = Mailbox("alice", base_path=temp_mailbox_dir)
        recipient_mb = Mailbox("bob", base_path=temp_mailbox_dir)
        # Use convenience function (need to patch or use base_path)
        from sdk_workflow.core.mailbox import Mailbox as MB
        original_init = MB.__init__
        def patched_init(self, owner_id, base_path=None):
            original_init(self, owner_id, base_path=temp_mailbox_dir)
        MB.__init__ = patched_init
        msg_id = send_command(
            sender="alice",
            recipient="bob",
            action="pause",
            params={"delay": 10}
        )
        assert msg_id is not None
        # Verify message
        messages = recipient_mb.receive()
        assert len(messages) == 1
        assert messages[0].type == MessageType.COMMAND
        assert messages[0].payload["action"] == "pause"
        assert messages[0].payload["params"]["delay"] == 10
        MB.__init__ = original_init
    def test_send_status(self, temp_mailbox_dir):
        """Test send_status convenience function."""
        sender_mb = Mailbox("orchestrator-123", base_path=temp_mailbox_dir)
        recipient_mb = Mailbox("claude-code", base_path=temp_mailbox_dir)
        from sdk_workflow.core.mailbox import Mailbox as MB
        original_init = MB.__init__
        def patched_init(self, owner_id, base_path=None):
            original_init(self, owner_id, base_path=temp_mailbox_dir)
        MB.__init__ = patched_init
        msg_id = send_status(
            sender="orchestrator-123",
            recipient="claude-code",
            phase="implementation",
            progress=0.75,
            summary="Implementing features"
        )
        assert msg_id is not None
        # Verify message
        messages = recipient_mb.receive()
        assert len(messages) == 1
        assert messages[0].type == MessageType.STATUS
        assert messages[0].payload["phase"] == "implementation"
        assert messages[0].payload["progress"] == 0.75
        MB.__init__ = original_init
    def test_send_signal(self, temp_mailbox_dir):
        """Test send_signal convenience function."""
        sender_mb = Mailbox("claude-code", base_path=temp_mailbox_dir)
        recipient_mb = Mailbox("orchestrator-123", base_path=temp_mailbox_dir)
        from sdk_workflow.core.mailbox import Mailbox as MB
        original_init = MB.__init__
        def patched_init(self, owner_id, base_path=None):
            original_init(self, owner_id, base_path=temp_mailbox_dir)
        MB.__init__ = patched_init
        msg_id = send_signal(
            sender="claude-code",
            recipient="orchestrator-123",
            signal="PAUSE"
        )
        assert msg_id is not None
        # Verify message
        messages = recipient_mb.receive()
        assert len(messages) == 1
        assert messages[0].type == MessageType.SIGNAL
        assert messages[0].payload["signal"] == "PAUSE"
        assert messages[0].priority == 3 # Urgent
        MB.__init__ = original_init
class TestMessageSerialization:
    """Tests for message serialization efficiency."""
    def test_compact_json_format(self, mailbox_alice, mailbox_bob):
        """Test that messages use compact JSON format."""
        mailbox_alice.send(
            recipient="bob",
            msg_type=MessageType.COMMAND,
            payload={"action": "test", "value": 123},
            priority=2,
            ttl=3600
        )
        # Read raw JSON file
        inbox_files = list(mailbox_bob.inbox_dir.glob("*.json"))
        with open(inbox_files[0], 'r') as f:
            raw_content = f.read()
        # Verify compact format (no spaces after separators)
        assert ',' in raw_content
        assert ': ' not in raw_content # Should use ':' not ': '
    def test_short_field_names(self, mailbox_alice, mailbox_bob):
        """Test that serialized messages use short field names."""
        mailbox_alice.send(
            recipient="bob",
            msg_type=MessageType.COMMAND,
            payload={"action": "test"}
        )
        # Read raw JSON
        inbox_files = list(mailbox_bob.inbox_dir.glob("*.json"))
        with open(inbox_files[0], 'r') as f:
            data = json.load(f)
        # Verify short keys
        assert 'i' in data # id
        assert 's' in data # sender
        assert 'r' in data # recipient
        assert 't' in data # type
        assert 'p' in data # payload
        assert 'ts' in data # timestamp
        assert 'pr' in data # priority
        assert 'ttl' in data # ttl_seconds
        # Verify no long keys
        assert 'id' not in data
        assert 'sender' not in data
        assert 'recipient' not in data
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
