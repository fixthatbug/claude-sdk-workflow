"""Comprehensive test suite for SessionManager.
Tests cover:
- Initialization and configuration
- Session lifecycle (start, end, get)
- Persistence (save, load)
- Search and filter capabilities
- Tagging functionality
- Analytics and statistics
- Archival operations
- Cleanup policies
- LRU eviction
- Thread safety
- Input validation
- Export functionality
- Performance benchmarks
"""
import json
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from sdk_workflow.managers.session_manager import (
    SessionManager,
    SessionManagerException,
    SessionNotFoundError,
)
class TestSessionManagerInitialization:
    """Test SessionManager initialization and configuration."""
    def test_default_initialization(self):
        """Test initialization with default parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            assert manager.max_sessions == 1000
            assert manager.persistence_enabled is True
            assert manager.history_size == 100
            assert isinstance(manager.active_sessions, dict)
    def test_custom_initialization(self):
        """Test initialization with custom parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(
                max_sessions=500,
                persistence_dir=Path(tmpdir),
                persistence_enabled=False,
                history_size=50
            )
            assert manager.max_sessions == 500
            assert manager.persistence_enabled is False
            assert manager.history_size == 50
    def test_invalid_max_sessions(self):
        """Test initialization with invalid max_sessions."""
        with pytest.raises(ValueError, match="max_sessions must be positive"):
            SessionManager(max_sessions=0)
        with pytest.raises(ValueError, match="max_sessions must be positive"):
            SessionManager(max_sessions=-1)
    def test_persistence_directory_creation(self):
        """Test that persistence directory is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence_dir = Path(tmpdir) / "sessions" / "nested"
            manager = SessionManager(
                persistence_dir=persistence_dir,
                persistence_enabled=True
            )
            assert persistence_dir.exists()
            assert persistence_dir.is_dir()
    def test_persistence_disabled_no_directory_creation(self):
        """Test that directory is not created when persistence disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence_dir = Path(tmpdir) / "sessions"
            manager = SessionManager(
                persistence_dir=persistence_dir,
                persistence_enabled=False
            )
            # Directory should not be created
            assert not persistence_dir.exists()
    def test_rlock_usage(self):
        """Test that RLock (not Lock) is used for thread safety."""
        manager = SessionManager(persistence_enabled=False)
        # Check that it's an RLock (not a regular Lock)
        assert type(manager._lock).__name__ == 'RLock'
        # Test reentrant locking
        with manager._lock:
            with manager._lock: # Should not deadlock
                pass
class TestSessionLifecycle:
    """Test session lifecycle operations."""
    def test_generate_session_id(self):
        """Test session ID generation."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.generate_session_id()
        assert session_id is not None
        assert session_id.startswith("sdk-")
        assert len(session_id) > 4
        # Should be unique
        session_id2 = manager.generate_session_id()
        assert session_id != session_id2
    def test_start_session_basic(self):
        """Test basic session start."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(
            task="Test task",
            agent_name="TestAgent"
        )
        assert session_id is not None
        assert session_id in manager.active_sessions
        assert manager.active_sessions[session_id]["task"] == "Test task"
        assert manager.active_sessions[session_id]["agent_name"] == "TestAgent"
        assert manager.active_sessions[session_id]["status"] == "running"
    def test_start_session_with_custom_id(self):
        """Test starting session with custom ID."""
        manager = SessionManager(persistence_enabled=False)
        custom_id = "custom_session_123"
        session_id = manager.start_session(session_id=custom_id)
        assert session_id == custom_id
        assert custom_id in manager.active_sessions
    def test_start_session_with_metadata(self):
        """Test starting session with additional metadata."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(
            task="Test",
            agent_name="TestAgent",
            priority="high",
            custom_field="value"
        )
        session = manager.active_sessions[session_id]
        assert session["priority"] == "high"
        assert session["custom_field"] == "value"
    def test_end_session_basic(self):
        """Test basic session end."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(task="Test")
        time.sleep(0.1) # Small delay to measure duration
        manager.end_session(session_id, status="completed")
        session = manager.active_sessions[session_id]
        assert session["status"] == "completed"
        assert "ended_at" in session
        assert "duration_seconds" in session
        assert session["duration_seconds"] > 0
    def test_end_session_nonexistent(self):
        """Test ending non-existent session."""
        manager = SessionManager(persistence_enabled=False)
        with pytest.raises(SessionNotFoundError, match="Session not found"):
            manager.end_session("nonexistent_session")
    def test_end_session_with_persistence(self):
        """Test ending session loads from persistence if not in memory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            # Start and persist session
            session_id = manager.start_session(task="Test")
            # Remove from active memory
            del manager.active_sessions[session_id]
            # End session (should load from persistence)
            manager.end_session(session_id, status="completed")
            # Should be back in active sessions
            assert session_id in manager.active_sessions
            assert manager.active_sessions[session_id]["status"] == "completed"
    def test_get_session_existing(self):
        """Test getting existing session."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(task="Test task")
        session = manager.get_session(session_id)
        assert session is not None
        assert session["session_id"] == session_id
        assert session["task"] == "Test task"
    def test_get_session_nonexistent(self):
        """Test getting non-existent session."""
        manager = SessionManager(persistence_enabled=False)
        session = manager.get_session("nonexistent")
        assert session is None
    def test_get_session_lru_update(self):
        """Test that get_session updates LRU order."""
        manager = SessionManager(max_sessions=3, persistence_enabled=False)
        # Create sessions
        id1 = manager.start_session(task="Task 1")
        id2 = manager.start_session(task="Task 2")
        id3 = manager.start_session(task="Task 3")
        # Access id1 (should move to end)
        manager.get_session(id1)
        # Create new session (should evict id2, not id1)
        id4 = manager.start_session(task="Task 4")
        # id2 should be evicted, id1 should still be there
        assert id1 in manager.active_sessions
        assert id2 not in manager.active_sessions
    def test_list_active_sessions(self):
        """Test listing active sessions."""
        manager = SessionManager(persistence_enabled=False)
        # Create running sessions
        id1 = manager.start_session(task="Task 1")
        id2 = manager.start_session(task="Task 2")
        # End one
        manager.end_session(id2, status="completed")
        active = manager.list_active_sessions()
        # Only id1 should be active (status="running")
        assert len(active) == 1
        assert id1 in active
        assert id2 not in active
class TestSessionPersistence:
    """Test session persistence functionality."""
    def test_persist_session(self):
        """Test persisting session to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            session_id = manager.start_session(task="Test task")
            path = manager.persist_session(session_id)
            assert path.exists()
            assert path.name == f"session_{session_id}.json"
            # Verify content
            data = json.loads(path.read_text())
            assert data["session_id"] == session_id
            assert data["task"] == "Test task"
    def test_persist_session_nonexistent(self):
        """Test persisting non-existent session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            with pytest.raises(SessionNotFoundError, match="Session not found"):
                manager.persist_session("nonexistent")
    def test_persist_session_disabled(self):
        """Test persist_session when persistence is disabled."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(task="Test")
        with pytest.raises(SessionManagerException, match="Persistence is not enabled"):
            manager.persist_session(session_id)
    def test_load_persisted_session(self):
        """Test loading persisted session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            # Create and persist
            session_id = manager.start_session(task="Test task")
            manager.persist_session(session_id)
            # Remove from memory
            del manager.active_sessions[session_id]
            # Load
            session = manager.load_persisted_session(session_id)
            assert session is not None
            assert session["session_id"] == session_id
            assert session["task"] == "Test task"
    def test_load_persisted_session_nonexistent(self):
        """Test loading non-existent persisted session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            session = manager.load_persisted_session("nonexistent")
            assert session is None
    def test_auto_persistence_on_start(self):
        """Test that sessions are automatically persisted on start."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            session_id = manager.start_session(task="Test task")
            # Check file exists
            session_file = Path(tmpdir) / f"session_{session_id}.json"
            assert session_file.exists()
    def test_auto_persistence_on_end(self):
        """Test that sessions are persisted on end."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            session_id = manager.start_session(task="Test")
            manager.end_session(session_id, status="completed")
            # Load and verify status was persisted
            session = manager.load_persisted_session(session_id)
            assert session["status"] == "completed"
class TestSessionSearch:
    """Test session search and filter functionality."""
    def test_search_sessions_by_status(self):
        """Test searching sessions by status."""
        manager = SessionManager(persistence_enabled=False)
        id1 = manager.start_session(task="Task 1")
        id2 = manager.start_session(task="Task 2")
        manager.end_session(id1, status="completed")
        # Search for running sessions
        results = manager.search_sessions({"status": "running"})
        assert len(results) == 1
        assert results[0]["session_id"] == id2
        # Search for completed sessions
        results = manager.search_sessions({"status": "completed"})
        assert len(results) == 1
        assert results[0]["session_id"] == id1
    def test_search_sessions_by_task(self):
        """Test searching sessions by task substring."""
        manager = SessionManager(persistence_enabled=False)
        manager.start_session(task="Process documents")
        manager.start_session(task="Generate report")
        manager.start_session(task="Process images")
        # Search for "Process"
        results = manager.search_sessions({"task": "Process"})
        assert len(results) == 2
        # Case insensitive
        results = manager.search_sessions({"task": "process"})
        assert len(results) == 2
    def test_search_sessions_by_agent_name(self):
        """Test searching sessions by agent name."""
        manager = SessionManager(persistence_enabled=False)
        manager.start_session(task="Task 1", agent_name="AgentA")
        manager.start_session(task="Task 2", agent_name="AgentB")
        manager.start_session(task="Task 3", agent_name="AgentA")
        results = manager.search_sessions({"agent_name": "AgentA"})
        assert len(results) == 2
    def test_search_sessions_by_tags(self):
        """Test searching sessions by tags."""
        manager = SessionManager(persistence_enabled=False)
        id1 = manager.start_session(task="Task 1")
        id2 = manager.start_session(task="Task 2")
        id3 = manager.start_session(task="Task 3")
        manager.tag_session(id1, ["important", "urgent"])
        manager.tag_session(id2, ["important"])
        manager.tag_session(id3, ["routine"])
        # Search for important tag
        results = manager.search_sessions({"tags": ["important"]})
        assert len(results) == 2
        # Search for urgent tag
        results = manager.search_sessions({"tags": ["urgent"]})
        assert len(results) == 1
    def test_search_sessions_by_date_range(self):
        """Test searching sessions by date range."""
        manager = SessionManager(persistence_enabled=False)
        # Create session with old timestamp
        now = datetime.now()
        past = now - timedelta(days=5)
        id1 = manager.start_session(task="Old task")
        # Manually set old timestamp
        manager.active_sessions[id1]["started_at"] = past.isoformat()
        id2 = manager.start_session(task="Recent task")
        # Search for sessions started after 3 days ago
        cutoff = (now - timedelta(days=3)).isoformat()
        results = manager.search_sessions({"started_after": cutoff})
        assert len(results) == 1
        assert results[0]["session_id"] == id2
        # Search for sessions started before 3 days ago
        results = manager.search_sessions({"started_before": cutoff})
        assert len(results) == 1
        assert results[0]["session_id"] == id1
    def test_search_sessions_multiple_filters(self):
        """Test searching with multiple filters."""
        manager = SessionManager(persistence_enabled=False)
        id1 = manager.start_session(task="Process documents", agent_name="AgentA")
        id2 = manager.start_session(task="Process images", agent_name="AgentB")
        id3 = manager.start_session(task="Generate report", agent_name="AgentA")
        manager.tag_session(id1, ["important"])
        manager.end_session(id1, status="completed")
        # Multiple filters
        results = manager.search_sessions({
            "status": "completed",
            "agent_name": "AgentA",
            "task": "Process"
        })
        assert len(results) == 1
        assert results[0]["session_id"] == id1
    def test_search_sessions_includes_persisted(self):
        """Test that search includes persisted sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(
                max_sessions=2,
                persistence_dir=Path(tmpdir)
            )
            # Create sessions (more than max_sessions)
            id1 = manager.start_session(task="Task 1")
            id2 = manager.start_session(task="Task 2")
            id3 = manager.start_session(task="Task 3") # Should evict id1
            # Search should find all 3
            results = manager.search_sessions({"task": "Task"})
            assert len(results) == 3
    def test_search_sessions_invalid_filters(self):
        """Test search with invalid filters parameter."""
        manager = SessionManager(persistence_enabled=False)
        with pytest.raises(ValueError, match="filters must be a dictionary"):
            manager.search_sessions("invalid")
class TestSessionTagging:
    """Test session tagging functionality."""
    def test_tag_session_basic(self):
        """Test basic session tagging."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(task="Test")
        manager.tag_session(session_id, ["important", "urgent"])
        assert session_id in manager._session_tags
        assert "important" in manager._session_tags[session_id]
        assert "urgent" in manager._session_tags[session_id]
    def test_tag_session_incremental(self):
        """Test adding tags incrementally."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(task="Test")
        manager.tag_session(session_id, ["tag1"])
        manager.tag_session(session_id, ["tag2", "tag3"])
        tags = manager._session_tags[session_id]
        assert len(tags) == 3
        assert "tag1" in tags
        assert "tag2" in tags
        assert "tag3" in tags
    def test_tag_session_duplicates(self):
        """Test that duplicate tags are handled."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(task="Test")
        manager.tag_session(session_id, ["tag1", "tag2"])
        manager.tag_session(session_id, ["tag2", "tag3"]) # tag2 is duplicate
        tags = manager._session_tags[session_id]
        assert len(tags) == 3 # No duplicate
    def test_tag_session_nonexistent(self):
        """Test tagging non-existent session."""
        manager = SessionManager(persistence_enabled=False)
        with pytest.raises(SessionNotFoundError, match="Session not found"):
            manager.tag_session("nonexistent", ["tag1"])
    def test_tag_session_with_persistence(self):
        """Test that tags are persisted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            session_id = manager.start_session(task="Test")
            manager.tag_session(session_id, ["tag1", "tag2"])
            # Load persisted session
            session = manager.load_persisted_session(session_id)
            assert "tags" in session
            assert set(session["tags"]) == {"tag1", "tag2"}
    def test_tag_session_invalid_parameters(self):
        """Test tagging with invalid parameters."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(task="Test")
        with pytest.raises(ValueError, match="session_id must be a non-empty string"):
            manager.tag_session("", ["tag1"])
        with pytest.raises(ValueError, match="tags must be a list"):
            manager.tag_session(session_id, "not_a_list")
    def test_tag_cleanup_on_archive(self):
        """Test that tags are cleaned up when session is archived."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            session_id = manager.start_session(task="Test")
            manager.tag_session(session_id, ["tag1", "tag2"])
            assert session_id in manager._session_tags
            manager.archive_session(session_id)
            # Tags should be cleaned up
            assert session_id not in manager._session_tags
class TestSessionAnalytics:
    """Test session analytics functionality."""
    def test_get_session_analytics_initial(self):
        """Test analytics with no sessions."""
        manager = SessionManager(persistence_enabled=False)
        analytics = manager.get_session_analytics()
        assert analytics["total_sessions_created"] == 0
        assert analytics["total_sessions_ended"] == 0
        assert analytics["total_sessions_archived"] == 0
        assert analytics["active_sessions_count"] == 0
    def test_get_session_analytics_after_operations(self):
        """Test analytics after session operations."""
        manager = SessionManager(persistence_enabled=False)
        id1 = manager.start_session(task="Task 1", agent_name="AgentA")
        id2 = manager.start_session(task="Task 2", agent_name="AgentB")
        id3 = manager.start_session(task="Task 3", agent_name="AgentA")
        manager.end_session(id1, status="completed")
        analytics = manager.get_session_analytics()
        assert analytics["total_sessions_created"] == 3
        assert analytics["total_sessions_ended"] == 1
        assert analytics["active_sessions_count"] == 3
        assert analytics["running_sessions_count"] == 2
    def test_analytics_sessions_by_status(self):
        """Test sessions_by_status analytics."""
        manager = SessionManager(persistence_enabled=False)
        id1 = manager.start_session(task="Task 1")
        id2 = manager.start_session(task="Task 2")
        id3 = manager.start_session(task="Task 3")
        manager.end_session(id1, status="completed")
        manager.end_session(id2, status="failed")
        analytics = manager.get_session_analytics()
        assert analytics["sessions_by_status"]["running"] == 1
        assert analytics["sessions_by_status"]["completed"] == 1
        assert analytics["sessions_by_status"]["failed"] == 1
    def test_analytics_sessions_by_agent(self):
        """Test sessions_by_agent analytics."""
        manager = SessionManager(persistence_enabled=False)
        manager.start_session(task="Task 1", agent_name="AgentA")
        manager.start_session(task="Task 2", agent_name="AgentA")
        manager.start_session(task="Task 3", agent_name="AgentB")
        analytics = manager.get_session_analytics()
        assert analytics["sessions_by_agent"]["AgentA"] == 2
        assert analytics["sessions_by_agent"]["AgentB"] == 1
    def test_analytics_avg_duration(self):
        """Test average session duration calculation."""
        manager = SessionManager(persistence_enabled=False)
        id1 = manager.start_session(task="Task 1")
        time.sleep(0.1)
        manager.end_session(id1)
        id2 = manager.start_session(task="Task 2")
        time.sleep(0.1)
        manager.end_session(id2)
        analytics = manager.get_session_analytics()
        assert analytics["avg_session_duration"] > 0
    def test_analytics_top_tags(self):
        """Test top tags analytics."""
        manager = SessionManager(persistence_enabled=False)
        id1 = manager.start_session(task="Task 1")
        id2 = manager.start_session(task="Task 2")
        id3 = manager.start_session(task="Task 3")
        manager.tag_session(id1, ["important", "urgent"])
        manager.tag_session(id2, ["important"])
        manager.tag_session(id3, ["routine"])
        analytics = manager.get_session_analytics()
        assert len(analytics["top_tags"]) == 3
        assert analytics["top_tags"][0]["tag"] == "important"
        assert analytics["top_tags"][0]["count"] == 2
    def test_analytics_sessions_per_hour(self):
        """Test sessions per hour calculation."""
        manager = SessionManager(persistence_enabled=False)
        for i in range(10):
            manager.start_session(task=f"Task {i}")
        analytics = manager.get_session_analytics()
        assert analytics["sessions_per_hour"] > 0
class TestSessionArchival:
    """Test session archival functionality."""
    def test_archive_session_basic(self):
        """Test basic session archival."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            session_id = manager.start_session(task="Test")
            manager.end_session(session_id)
            archive_path = manager.archive_session(session_id)
            assert archive_path.exists()
            assert session_id not in manager.active_sessions
    def test_archive_session_without_persistence(self):
        """Test archival when persistence is disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(
                persistence_dir=Path(tmpdir),
                persistence_enabled=False
            )
            session_id = manager.start_session(task="Test")
            archive_path = manager.archive_session(session_id)
            # Should create archive directory
            assert archive_path.exists()
            assert "archived" in str(archive_path)
    def test_archive_session_nonexistent(self):
        """Test archiving non-existent session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            with pytest.raises(SessionNotFoundError, match="Session not found"):
                manager.archive_session("nonexistent")
    def test_archive_session_increments_counter(self):
        """Test that archival increments counter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            session_id = manager.start_session(task="Test")
            initial_count = manager._total_sessions_archived
            manager.archive_session(session_id)
            assert manager._total_sessions_archived == initial_count + 1
class TestSessionCleanup:
    """Test session cleanup functionality."""
    def test_cleanup_sessions_by_age(self):
        """Test cleanup of old sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            # Create old session
            old_id = manager.start_session(task="Old task")
            old_time = time.time() - (31 * 24 * 60 * 60) # 31 days ago
            manager.active_sessions[old_id]["created_unix_time"] = old_time
            # Create recent session
            recent_id = manager.start_session(task="Recent task")
            # Cleanup sessions older than 30 days
            deleted = manager.cleanup_sessions(older_than_days=30)
            assert deleted >= 1
            assert old_id not in manager.active_sessions
            assert recent_id in manager.active_sessions
    def test_cleanup_sessions_persisted_files(self):
        """Test cleanup of persisted session files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            # Create and persist session
            session_id = manager.start_session(task="Test")
            session_file = manager.persistence_dir / f"session_{session_id}.json"
            # Make file old
            old_time = time.time() - (31 * 24 * 60 * 60)
            import os
            os.utime(session_file, (old_time, old_time))
            # Cleanup
            deleted = manager.cleanup_sessions(older_than_days=30)
            assert deleted >= 1
            assert not session_file.exists()
    def test_cleanup_invalid_age(self):
        """Test cleanup with invalid age parameter."""
        manager = SessionManager(persistence_enabled=False)
        with pytest.raises(ValueError, match="older_than_days must be positive"):
            manager.cleanup_sessions(older_than_days=0)
        with pytest.raises(ValueError, match="older_than_days must be positive"):
            manager.cleanup_sessions(older_than_days=-1)
    def test_cleanup_with_tags(self):
        """Test that cleanup also removes tags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            # Create old session with tags
            session_id = manager.start_session(task="Old task")
            manager.tag_session(session_id, ["tag1", "tag2"])
            old_time = time.time() - (31 * 24 * 60 * 60)
            manager.active_sessions[session_id]["created_unix_time"] = old_time
            assert session_id in manager._session_tags
            # Cleanup
            manager.cleanup_sessions(older_than_days=30)
            # Tags should be removed
            assert session_id not in manager._session_tags
class TestLRUEviction:
    """Test LRU eviction functionality."""
    def test_lru_eviction_on_max_sessions(self):
        """Test that oldest session is evicted when reaching max_sessions."""
        manager = SessionManager(max_sessions=3, persistence_enabled=False)
        id1 = manager.start_session(task="Task 1")
        id2 = manager.start_session(task="Task 2")
        id3 = manager.start_session(task="Task 3")
        # All should be in memory
        assert len(manager.active_sessions) == 3
        # Add one more (should evict id1)
        id4 = manager.start_session(task="Task 4")
        assert len(manager.active_sessions) == 3
        assert id1 not in manager.active_sessions
        assert id2 in manager.active_sessions
        assert id3 in manager.active_sessions
        assert id4 in manager.active_sessions
    def test_lru_eviction_with_persistence(self):
        """Test that evicted sessions are persisted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(
                max_sessions=2,
                persistence_dir=Path(tmpdir)
            )
            id1 = manager.start_session(task="Task 1")
            id2 = manager.start_session(task="Task 2")
            # Create one more (should evict and persist id1)
            id3 = manager.start_session(task="Task 3")
            # id1 should be persisted
            session_file = Path(tmpdir) / f"session_{id1}.json"
            assert session_file.exists()
            # Should be able to load it
            session = manager.load_persisted_session(id1)
            assert session is not None
    def test_lru_order_maintained(self):
        """Test that LRU order is maintained correctly."""
        manager = SessionManager(max_sessions=3, persistence_enabled=False)
        id1 = manager.start_session(task="Task 1")
        id2 = manager.start_session(task="Task 2")
        id3 = manager.start_session(task="Task 3")
        # Access id1 (moves to end)
        manager.get_session(id1)
        # Add new session (should evict id2, not id1)
        id4 = manager.start_session(task="Task 4")
        assert id1 in manager.active_sessions
        assert id2 not in manager.active_sessions
        assert id3 in manager.active_sessions
        assert id4 in manager.active_sessions
class TestThreadSafety:
    """Test thread safety of SessionManager."""
    def test_concurrent_session_starts(self):
        """Test concurrent session starts."""
        manager = SessionManager(persistence_enabled=False)
        def start_sessions(count: int):
            for i in range(count):
                manager.start_session(task=f"Task {i}")
        threads = []
        for i in range(5):
            thread = threading.Thread(target=start_sessions, args=(10,))
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        # Should have 50 sessions
        assert len(manager.active_sessions) == 50
    def test_concurrent_start_end(self):
        """Test concurrent start and end operations."""
        manager = SessionManager(persistence_enabled=False)
        session_ids = []
        lock = threading.Lock()
        def start_and_end():
            session_id = manager.start_session(task="Test")
            with lock:
                session_ids.append(session_id)
            time.sleep(0.01)
            manager.end_session(session_id, status="completed")
        threads = []
        for _ in range(20):
            thread = threading.Thread(target=start_and_end)
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        # All sessions should be completed
        assert len(session_ids) == 20
        for session_id in session_ids:
            assert manager.active_sessions[session_id]["status"] == "completed"
    def test_concurrent_tagging(self):
        """Test concurrent tagging operations."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(task="Test")
        def add_tags(tag_prefix: str):
            for i in range(10):
                manager.tag_session(session_id, [f"{tag_prefix}_{i}"])
        threads = []
        for i in range(5):
            thread = threading.Thread(target=add_tags, args=(f"tag{i}",))
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        # Should have 50 tags
        assert len(manager._session_tags[session_id]) == 50
    def test_concurrent_search(self):
        """Test concurrent search operations."""
        manager = SessionManager(persistence_enabled=False)
        # Pre-populate sessions
        for i in range(20):
            manager.start_session(task=f"Task {i}", agent_name="TestAgent")
        results_list = []
        lock = threading.Lock()
        def search():
            results = manager.search_sessions({"agent_name": "TestAgent"})
            with lock:
                results_list.append(len(results))
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=search)
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        # All searches should return same count
        assert all(count == 20 for count in results_list)
    def test_reentrant_locking(self):
        """Test that RLock allows reentrant calls."""
        manager = SessionManager(persistence_enabled=False)
        # This should not deadlock
        with manager._lock:
            with manager._lock:
                manager.start_session(task="Test")
        # Verify success
        assert len(manager.active_sessions) == 1
class TestInputValidation:
    """Test input validation and error handling."""
    def test_end_session_invalid_session_id(self):
        """Test end_session with invalid session_id."""
        manager = SessionManager(persistence_enabled=False)
        with pytest.raises(ValueError, match="session_id must be a non-empty string"):
            manager.end_session("", status="completed")
    def test_persist_session_invalid_session_id(self):
        """Test persist_session with invalid session_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            with pytest.raises(ValueError, match="session_id must be a non-empty string"):
                manager.persist_session("")
    def test_archive_session_invalid_session_id(self):
        """Test archive_session with invalid session_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(persistence_dir=Path(tmpdir))
            with pytest.raises(ValueError, match="session_id must be a non-empty string"):
                manager.archive_session("")
    def test_get_session_invalid_input(self):
        """Test get_session with invalid input."""
        manager = SessionManager(persistence_enabled=False)
        assert manager.get_session("") is None
        assert manager.get_session(None) is None
class TestExport:
    """Test export functionality."""
    def test_export_sessions_json(self):
        """Test exporting sessions in JSON format."""
        manager = SessionManager(persistence_enabled=False)
        manager.start_session(task="Task 1")
        manager.start_session(task="Task 2")
        json_data = manager.export_sessions(export_format="json")
        assert json_data is not None
        data = json.loads(json_data)
        assert "analytics" in data
        assert "sessions" in data
        assert len(data["sessions"]) == 2
    def test_export_sessions_csv(self):
        """Test exporting sessions in CSV format."""
        manager = SessionManager(persistence_enabled=False)
        manager.start_session(task="Task 1")
        manager.start_session(task="Task 2")
        csv_data = manager.export_sessions(export_format="csv")
        assert csv_data is not None
        assert "Session Manager Analytics" in csv_data
        assert "Sessions" in csv_data
    def test_export_sessions_with_tags(self):
        """Test that export includes tags."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(task="Task 1")
        manager.tag_session(session_id, ["tag1", "tag2"])
        json_data = manager.export_sessions(export_format="json")
        data = json.loads(json_data)
        # Find the session
        session = next(s for s in data["sessions"] if s["session_id"] == session_id)
        assert "tags" in session
        assert set(session["tags"]) == {"tag1", "tag2"}
    def test_export_invalid_format(self):
        """Test export with invalid format."""
        manager = SessionManager(persistence_enabled=False)
        with pytest.raises(ValueError, match="Unsupported export format"):
            manager.export_sessions(export_format="xml")
    def test_get_summary(self):
        """Test getting human-readable summary."""
        manager = SessionManager(persistence_enabled=False)
        id1 = manager.start_session(task="Task 1")
        manager.start_session(task="Task 2")
        manager.end_session(id1, status="completed")
        summary = manager.get_summary()
        assert "Session Manager Summary" in summary
        assert "Total Sessions Created" in summary
        assert "Active Sessions" in summary
        assert "Running Sessions" in summary
class TestPerformance:
    """Performance benchmark tests."""
    def test_start_session_performance(self):
        """Test session start performance."""
        manager = SessionManager(max_sessions=1000, persistence_enabled=False)
        start = time.time()
        for i in range(100):
            manager.start_session(task=f"Task {i}")
        elapsed = time.time() - start
        # Should be fast
        assert elapsed < 1.0 # Less than 1 second for 100 starts
        avg_time = elapsed / 100
        assert avg_time < 0.01 # Less than 10ms per start
    def test_search_performance(self):
        """Test search performance with many sessions."""
        manager = SessionManager(persistence_enabled=False)
        # Create many sessions
        for i in range(500):
            manager.start_session(
                task=f"Task {i}",
                agent_name=f"Agent{i % 10}"
            )
        start = time.time()
        results = manager.search_sessions({"agent_name": "Agent5"})
        elapsed = time.time() - start
        # Should be fast
        assert elapsed < 0.5 # Less than 500ms
        assert len(results) == 50 # Should find 50 matches
    def test_tag_performance(self):
        """Test tagging performance."""
        manager = SessionManager(persistence_enabled=False)
        session_ids = []
        for i in range(100):
            session_id = manager.start_session(task=f"Task {i}")
            session_ids.append(session_id)
        start = time.time()
        for session_id in session_ids:
            manager.tag_session(session_id, ["tag1", "tag2", "tag3"])
        elapsed = time.time() - start
        # Should be fast
        assert elapsed < 1.0 # Less than 1 second for 100 tagging operations
    def test_concurrent_performance(self):
        """Test performance under concurrent load."""
        manager = SessionManager(max_sessions=500, persistence_enabled=False)
        def worker(worker_id: int):
            for i in range(20):
                session_id = manager.start_session(
                    task=f"Task {worker_id}_{i}",
                    agent_name=f"Agent{worker_id}"
                )
                manager.tag_session(session_id, [f"tag{i}"])
                if i % 2 == 0:
                    manager.end_session(session_id)
        start = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            for future in as_completed(futures):
                future.result()
        elapsed = time.time() - start
        # 10 workers x 20 sessions = 200 sessions
        assert elapsed < 5.0 # Should complete in reasonable time
    def test_memory_bounded(self):
        """Test that memory usage is bounded."""
        manager = SessionManager(max_sessions=100, persistence_enabled=False)
        # Create many more sessions than max
        for i in range(500):
            manager.start_session(task=f"Task {i}")
        # Active sessions should be bounded
        assert len(manager.active_sessions) == 100
    def test_lru_eviction_performance(self):
        """Test LRU eviction doesn't significantly impact performance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(
                max_sessions=50,
                persistence_dir=Path(tmpdir)
            )
            start = time.time()
            for i in range(200):
                manager.start_session(task=f"Task {i}")
            elapsed = time.time() - start
            # Even with eviction and persistence, should be reasonable
            assert elapsed < 5.0
class TestEdgeCases:
    """Test edge cases and corner scenarios."""
    def test_session_with_none_metadata(self):
        """Test session with None metadata values."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(
            task=None,
            agent_name=None,
            custom_field=None
        )
        session = manager.get_session(session_id)
        assert session["task"] is None
        assert session["agent_name"] is None
        assert session["custom_field"] is None
    def test_unicode_in_session_data(self):
        """Test handling of unicode in session data."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(
            task="Process 世界 documents ",
            agent_name="Agent™"
        )
        session = manager.get_session(session_id)
        assert session["task"] == "Process 世界 documents "
        assert session["agent_name"] == "Agent™"
    def test_very_long_task_description(self):
        """Test handling of very long task descriptions."""
        manager = SessionManager(persistence_enabled=False)
        long_task = "Task " * 10000 # Very long string
        session_id = manager.start_session(task=long_task)
        session = manager.get_session(session_id)
        assert session["task"] == long_task
    def test_many_tags_on_session(self):
        """Test session with many tags."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(task="Test")
        # Add many tags
        tags = [f"tag_{i}" for i in range(1000)]
        manager.tag_session(session_id, tags)
        assert len(manager._session_tags[session_id]) == 1000
    def test_special_characters_in_tags(self):
        """Test tags with special characters."""
        manager = SessionManager(persistence_enabled=False)
        session_id = manager.start_session(task="Test")
        manager.tag_session(session_id, ["tag-1", "tag_2", "tag.3", "tag@4"])
        tags = manager._session_tags[session_id]
        assert len(tags) == 4
    def test_search_with_empty_filters(self):
        """Test search with empty filters dictionary."""
        manager = SessionManager(persistence_enabled=False)
        manager.start_session(task="Task 1")
        manager.start_session(task="Task 2")
        # Empty filters should return all sessions
        results = manager.search_sessions({})
        assert len(results) == 2
    def test_repr(self):
        """Test __repr__ method."""
        manager = SessionManager(persistence_enabled=False)
        manager.start_session(task="Task 1")
        manager.start_session(task="Task 2")
        repr_str = repr(manager)
        assert "SessionManager" in repr_str
        assert "active=" in repr_str
        assert "total_created=" in repr_str
    def test_operation_history_bounded(self):
        """Test that operation history is bounded."""
        manager = SessionManager(
            persistence_enabled=False,
            history_size=10
        )
        # Perform many operations
        for i in range(20):
            manager.start_session(task=f"Task {i}")
        # History should be bounded
        assert len(manager._operation_history) == 10
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
