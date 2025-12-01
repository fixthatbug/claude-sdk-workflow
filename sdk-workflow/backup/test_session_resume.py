"""
Test script for session ID capture and resume functionality.
"""
import sys
import io
from pathlib import Path
from core.state import Session, SessionManager, SessionStatus
from core.agent_client import (
    get_agent_client,
    extract_session_id_from_message,
)
# Fix Windows encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
def test_session_persistence():
    """Test Session save/load with sdk_session_id."""
    print("Testing Session persistence...")
    # Create a session with SDK session ID
    session = Session(
        id="sess_test123",
        mode="streaming",
        task="Test task",
        status=SessionStatus.CREATED.value,
        model="claude-sonnet-4-20250514",
        created_at="2025-01-01T00:00:00",
        updated_at="2025-01-01T00:00:00",
        sdk_session_id="sdk_session_abc123"
    )
    # Save to file
    test_file = Path("test_session.json")
    session.save_to_file(test_file)
    print(f" Saved session to {test_file}")
    # Load from file
    loaded_session = Session.load_from_file(test_file)
    print(f" Loaded session from {test_file}")
    # Verify
    assert loaded_session.sdk_session_id == "sdk_session_abc123", "SDK session ID mismatch"
    assert loaded_session.id == "sess_test123", "Session ID mismatch"
    print(" Session data matches")
    # Cleanup
    test_file.unlink()
    print(" Test file cleaned up")
    print("\n Session persistence test PASSED\n")
def test_session_manager():
    """Test SessionManager with sdk_session_id."""
    print("Testing SessionManager...")
    # Create temporary storage
    storage_dir = Path("test_sessions")
    manager = SessionManager(storage_dir=storage_dir)
    # Create session with SDK session ID
    session = manager.create(
        mode="streaming",
        task="Test with SDK session",
        model="claude-sonnet-4-20250514",
        sdk_session_id="sdk_abc123"
    )
    print(f" Created session {session.id}")
    # Retrieve and verify
    retrieved = manager.get(session.id)
    assert retrieved is not None, "Session not found"
    assert retrieved.sdk_session_id == "sdk_abc123", "SDK session ID not stored"
    print(" SDK session ID stored correctly")
    # Update SDK session ID
    updated = manager.update(
        session.id,
        sdk_session_id="sdk_xyz789"
    )
    assert updated.sdk_session_id == "sdk_xyz789", "SDK session ID not updated"
    print(" SDK session ID updated correctly")
    # Cleanup
    manager.delete(session.id)
    storage_dir.rmdir()
    print(" Test storage cleaned up")
    print("\n SessionManager test PASSED\n")
def test_agent_client_session_capture():
    """Test AgentClientManager session ID capture."""
    print("Testing AgentClientManager session capture...")
    client = get_agent_client()
    # Verify initial state
    assert client.get_current_session_id() is None, "Should start with no session ID"
    print(" Initial state correct")
    # Test session ID clearing
    client._current_session_id = "test_session"
    client.clear_session_id()
    assert client.get_current_session_id() is None, "Session ID should be cleared"
    print(" Session ID clearing works")
    # Test create_options with resume parameter
    options = client.create_options(
        model="sonnet",
        resume="sdk_session_123"
    )
    assert options.resume == "sdk_session_123", "Resume parameter not set"
    print(" create_options accepts resume parameter")
    print("\n AgentClientManager test PASSED\n")
if __name__ == "__main__":
    print("=" * 60)
    print("Session ID Capture and Resume - Test Suite")
    print("=" * 60)
    print()
    try:
        test_session_persistence()
        test_session_manager()
        test_agent_client_session_capture()
        print("=" * 60)
        print("ALL TESTS PASSED ")
        print("=" * 60)
    except Exception as e:
        print(f"\n TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
