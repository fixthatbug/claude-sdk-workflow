"""Comprehensive test suite for CheckpointManager.
Tests cover:
- Initialization and configuration
- Versioned checkpoint save/load
- Version listing and tracking
- Compression functionality
- Validation and integrity
- Cleanup and retention policies
- Backup and restore operations
- Thread safety
- Input validation
- Analytics and metrics
- Export functionality
- Performance benchmarks
"""
import gzip
import json
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from sdk_workflow.managers.checkpoint_manager import (
    CheckpointManager,
    CheckpointManagerException,
    CheckpointNotFoundError,
    CheckpointValidationError,
)
class TestCheckpointManagerInitialization:
    """Test CheckpointManager initialization and configuration."""
    def test_default_initialization(self):
        """Test initialization with default parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            assert manager.output_dir == Path(tmpdir)
            assert manager.max_versions_per_session == 10
            assert manager.compression_enabled is True
            assert manager.history_size == 100
            assert manager._max_sessions == 1000
    def test_custom_initialization(self):
        """Test initialization with custom parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                output_dir=Path(tmpdir),
                max_versions_per_session=5,
                compression_enabled=False,
                history_size=50
            )
            assert manager.max_versions_per_session == 5
            assert manager.compression_enabled is False
            assert manager.history_size == 50
    def test_invalid_max_versions(self):
        """Test initialization with invalid max_versions_per_session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="max_versions_per_session must be positive"):
                CheckpointManager(output_dir=Path(tmpdir), max_versions_per_session=0)
            with pytest.raises(ValueError, match="max_versions_per_session must be positive"):
                CheckpointManager(output_dir=Path(tmpdir), max_versions_per_session=-1)
    def test_output_directory_creation(self):
        """Test that output directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "checkpoints" / "nested"
            manager = CheckpointManager(output_dir=output_dir)
            assert output_dir.exists()
            assert output_dir.is_dir()
    def test_rlock_usage(self):
        """Test that RLock (not Lock) is used for thread safety."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Check that it's an RLock (not a regular Lock)
            assert type(manager._lock).__name__ == 'RLock'
            # Test reentrant locking
            with manager._lock:
                with manager._lock: # Should not deadlock
                    pass
class TestCheckpointSaveLoad:
    """Test basic checkpoint save and load operations."""
    def test_save_checkpoint_basic(self):
        """Test basic checkpoint save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            path = manager.save_checkpoint(
                session_id="test_session",
                turn=5,
                total_input_tokens=1000,
                total_output_tokens=500,
                context_used_pct=25.5
            )
            assert path.exists()
            assert path.name == "checkpoint_test_session.json"
            # Verify content
            data = json.loads(path.read_text())
            assert data["session_id"] == "test_session"
            assert data["turn"] == 5
            assert data["total_input_tokens"] == 1000
            assert data["total_output_tokens"] == 500
            assert data["context_used_pct"] == 25.5
    def test_save_checkpoint_with_extra_data(self):
        """Test checkpoint save with extra metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            path = manager.save_checkpoint(
                session_id="test_session",
                turn=1,
                total_input_tokens=100,
                total_output_tokens=50,
                context_used_pct=10.0,
                custom_field="custom_value",
                nested_data={"key": "value"}
            )
            data = json.loads(path.read_text())
            assert data["custom_field"] == "custom_value"
            assert data["nested_data"]["key"] == "value"
    def test_load_checkpoint_existing(self):
        """Test loading an existing checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Save first
            manager.save_checkpoint(
                session_id="test_session",
                turn=5,
                total_input_tokens=1000,
                total_output_tokens=500,
                context_used_pct=25.5
            )
            # Load
            checkpoint = manager.load_checkpoint("test_session")
            assert checkpoint is not None
            assert checkpoint["session_id"] == "test_session"
            assert checkpoint["turn"] == 5
    def test_load_checkpoint_nonexistent(self):
        """Test loading a non-existent checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            checkpoint = manager.load_checkpoint("nonexistent")
            assert checkpoint is None
    def test_checkpoint_exists(self):
        """Test checkpoint existence check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            assert not manager.checkpoint_exists("test_session")
            manager.save_checkpoint(
                session_id="test_session",
                turn=1,
                total_input_tokens=100,
                total_output_tokens=50,
                context_used_pct=10.0
            )
            assert manager.checkpoint_exists("test_session")
class TestVersionedCheckpoints:
    """Test versioned checkpoint functionality."""
    def test_save_checkpoint_versioned_basic(self):
        """Test basic versioned checkpoint save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            path, version = manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=1,
                tokens=100
            )
            assert version == 1
            assert path.exists()
            assert "checkpoint_v0001" in path.name
    def test_save_checkpoint_versioned_increments(self):
        """Test that versions increment correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Save multiple versions
            path1, version1 = manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=1
            )
            path2, version2 = manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=2
            )
            path3, version3 = manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=3
            )
            assert version1 == 1
            assert version2 == 2
            assert version3 == 3
    def test_load_checkpoint_version_existing(self):
        """Test loading a specific checkpoint version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Save versions
            manager.save_checkpoint_versioned(session_id="test_session", turn=1)
            manager.save_checkpoint_versioned(session_id="test_session", turn=2)
            manager.save_checkpoint_versioned(session_id="test_session", turn=3)
            # Load version 2
            checkpoint = manager.load_checkpoint_version("test_session", 2)
            assert checkpoint is not None
            assert checkpoint["version"] == 2
            assert checkpoint["turn"] == 2
    def test_load_checkpoint_version_nonexistent(self):
        """Test loading a non-existent checkpoint version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            checkpoint = manager.load_checkpoint_version("test_session", 99)
            assert checkpoint is None
    def test_list_checkpoint_versions(self):
        """Test listing all checkpoint versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Save multiple versions
            for i in range(1, 6):
                manager.save_checkpoint_versioned(session_id="test_session", turn=i)
            versions = manager.list_checkpoint_versions("test_session")
            assert len(versions) == 5
            # Should be sorted newest first
            assert versions[0]["version"] > versions[-1]["version"]
            # Check version info structure
            for v in versions:
                assert "version" in v
                assert "timestamp" in v
                assert "size_bytes" in v
                assert "compressed" in v
                assert "path" in v
    def test_list_checkpoint_versions_empty(self):
        """Test listing versions for session with no checkpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            versions = manager.list_checkpoint_versions("nonexistent")
            assert versions == []
    def test_version_tracking_bounded_memory(self):
        """Test that version tracking is bounded to _max_sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            manager._max_sessions = 3 # Set small limit for testing
            # Create more sessions than the limit
            for i in range(5):
                manager.save_checkpoint_versioned(
                    session_id=f"session_{i}",
                    turn=1
                )
            # Version tracking should only have 3 sessions (most recent)
            assert len(manager._version_tracking) == 3
class TestCompression:
    """Test compression functionality."""
    def test_compression_enabled(self):
        """Test that compression creates .gz files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                output_dir=Path(tmpdir),
                compression_enabled=True
            )
            path, version = manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=1,
                large_data="x" * 10000 # Large data to compress
            )
            assert path.suffix == ".gz"
            assert path.exists()
    def test_compression_disabled(self):
        """Test that uncompressed creates .json files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                output_dir=Path(tmpdir),
                compression_enabled=False
            )
            path, version = manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=1
            )
            assert path.suffix == ".json"
            assert path.exists()
    def test_compression_reduces_size(self):
        """Test that compression actually reduces file size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Compressed
            manager_compressed = CheckpointManager(
                output_dir=Path(tmpdir) / "compressed",
                compression_enabled=True
            )
            path_compressed, _ = manager_compressed.save_checkpoint_versioned(
                session_id="test_session",
                turn=1,
                large_data="This is repeated data. " * 1000
            )
            compressed_size = path_compressed.stat().st_size
            # Uncompressed
            manager_uncompressed = CheckpointManager(
                output_dir=Path(tmpdir) / "uncompressed",
                compression_enabled=False
            )
            path_uncompressed, _ = manager_uncompressed.save_checkpoint_versioned(
                session_id="test_session",
                turn=1,
                large_data="This is repeated data. " * 1000
            )
            uncompressed_size = path_uncompressed.stat().st_size
            assert compressed_size < uncompressed_size
    def test_load_compressed_checkpoint(self):
        """Test loading a compressed checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                output_dir=Path(tmpdir),
                compression_enabled=True
            )
            # Save
            manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=1,
                data="test_data"
            )
            # Load
            checkpoint = manager.load_checkpoint_version("test_session", 1)
            assert checkpoint is not None
            assert checkpoint["data"] == "test_data"
    def test_load_uncompressed_checkpoint(self):
        """Test loading an uncompressed checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                output_dir=Path(tmpdir),
                compression_enabled=False
            )
            # Save
            manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=1,
                data="test_data"
            )
            # Load
            checkpoint = manager.load_checkpoint_version("test_session", 1)
            assert checkpoint is not None
            assert checkpoint["data"] == "test_data"
class TestValidation:
    """Test checkpoint validation functionality."""
    def test_validate_checkpoint_valid(self):
        """Test validation of a valid checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Save checkpoint
            manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=1
            )
            # Validate
            is_valid = manager.validate_checkpoint("test_session", 1)
            assert is_valid is True
    def test_validate_checkpoint_nonexistent(self):
        """Test validation of non-existent checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            is_valid = manager.validate_checkpoint("nonexistent", 1)
            assert is_valid is False
    def test_validate_checkpoint_corrupted(self):
        """Test validation of corrupted checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Save checkpoint
            path, _ = manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=1
            )
            # Corrupt the file
            path.write_bytes(b"corrupted data")
            # Validate
            is_valid = manager.validate_checkpoint("test_session", 1)
            assert is_valid is False
    def test_validate_checkpoint_missing_fields(self):
        """Test validation with missing required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                output_dir=Path(tmpdir),
                compression_enabled=False
            )
            # Create checkpoint directory
            session_dir = Path(tmpdir) / "test_session"
            session_dir.mkdir(parents=True, exist_ok=True)
            # Create invalid checkpoint (missing required fields)
            invalid_checkpoint = {"data": "test"}
            checkpoint_file = session_dir / "checkpoint_v0001.json"
            checkpoint_file.write_text(json.dumps(invalid_checkpoint))
            # Validate
            is_valid = manager.validate_checkpoint("test_session", 1)
            assert is_valid is False
    def test_validation_increments_counter(self):
        """Test that validation increments the validation counter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            manager.save_checkpoint_versioned(session_id="test_session", turn=1)
            initial_count = manager._validation_count
            manager.validate_checkpoint("test_session", 1)
            assert manager._validation_count == initial_count + 1
class TestCleanup:
    """Test cleanup and retention policies."""
    def test_cleanup_old_versions(self):
        """Test that old versions are cleaned up when exceeding limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                output_dir=Path(tmpdir),
                max_versions_per_session=3
            )
            # Save 5 versions (exceeds limit of 3)
            for i in range(1, 6):
                manager.save_checkpoint_versioned(
                    session_id="test_session",
                    turn=i
                )
            # Check that only 3 versions remain
            versions = manager.list_checkpoint_versions("test_session")
            assert len(versions) == 3
            # Check that newest versions are kept
            version_numbers = [v["version"] for v in versions]
            assert 3 in version_numbers
            assert 4 in version_numbers
            assert 5 in version_numbers
            assert 1 not in version_numbers
            assert 2 not in version_numbers
    def test_cleanup_old_checkpoints_by_date(self):
        """Test cleanup of checkpoints older than retention period."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Create old checkpoint
            old_session_dir = Path(tmpdir) / "old_session"
            old_session_dir.mkdir(parents=True, exist_ok=True)
            old_checkpoint = old_session_dir / "checkpoint_v0001.json"
            old_checkpoint.write_text(json.dumps({
                "session_id": "old_session",
                "version": 1,
                "timestamp": datetime.now().isoformat()
            }))
            # Make it old (modify mtime)
            old_time = time.time() - (31 * 24 * 60 * 60) # 31 days ago
            import os
            os.utime(old_checkpoint, (old_time, old_time))
            # Create recent checkpoint
            manager.save_checkpoint_versioned(
                session_id="recent_session",
                turn=1
            )
            # Cleanup with 30 day retention
            deleted = manager.cleanup_old_checkpoints(retention_days=30)
            assert deleted == 1
            assert not old_checkpoint.exists()
    def test_cleanup_removes_empty_directories(self):
        """Test that cleanup removes empty session directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Create old checkpoint
            old_session_dir = Path(tmpdir) / "old_session"
            old_session_dir.mkdir(parents=True, exist_ok=True)
            old_checkpoint = old_session_dir / "checkpoint_v0001.json"
            old_checkpoint.write_text(json.dumps({
                "session_id": "old_session",
                "version": 1,
                "timestamp": datetime.now().isoformat()
            }))
            # Make it old
            old_time = time.time() - (31 * 24 * 60 * 60)
            import os
            os.utime(old_checkpoint, (old_time, old_time))
            # Cleanup
            manager.cleanup_old_checkpoints(retention_days=30)
            # Session directory should be removed
            assert not old_session_dir.exists()
    def test_cleanup_invalid_retention_days(self):
        """Test cleanup with invalid retention_days parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            with pytest.raises(ValueError, match="retention_days must be positive"):
                manager.cleanup_old_checkpoints(retention_days=0)
            with pytest.raises(ValueError, match="retention_days must be positive"):
                manager.cleanup_old_checkpoints(retention_days=-1)
class TestBackupRestore:
    """Test backup and restore functionality."""
    def test_backup_checkpoint(self):
        """Test backing up checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir) / "checkpoints")
            backup_dir = Path(tmpdir) / "backups"
            # Create checkpoints
            for i in range(1, 4):
                manager.save_checkpoint_versioned(
                    session_id="test_session",
                    turn=i
                )
            # Backup
            backup_path = manager.backup_checkpoint("test_session", backup_dir)
            assert backup_path.exists()
            assert backup_path.is_dir()
            assert "checkpoint_backup_test_session_" in backup_path.name
            # Verify backup contains all versions
            backup_files = list(backup_path.glob("checkpoint_v*.json*"))
            assert len(backup_files) == 3
    def test_backup_nonexistent_session(self):
        """Test backup of non-existent session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            backup_dir = Path(tmpdir) / "backups"
            with pytest.raises(CheckpointNotFoundError, match="No checkpoints found"):
                manager.backup_checkpoint("nonexistent", backup_dir)
    def test_restore_checkpoint(self):
        """Test restoring checkpoint from backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir) / "checkpoints")
            backup_dir = Path(tmpdir) / "backups"
            # Create and backup
            for i in range(1, 4):
                manager.save_checkpoint_versioned(
                    session_id="test_session",
                    turn=i
                )
            backup_path = manager.backup_checkpoint("test_session", backup_dir)
            # Delete original
            session_dir = manager.output_dir / "test_session"
            shutil.rmtree(session_dir)
            # Restore
            session_id = manager.restore_checkpoint(backup_path)
            assert session_id == "test_session"
            assert session_dir.exists()
            # Verify all versions restored
            versions = manager.list_checkpoint_versions("test_session")
            assert len(versions) == 3
    def test_restore_nonexistent_backup(self):
        """Test restore from non-existent backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            with pytest.raises(CheckpointNotFoundError, match="Backup path does not exist"):
                manager.restore_checkpoint(Path(tmpdir) / "nonexistent")
    def test_backup_restore_preserves_data(self):
        """Test that backup and restore preserves all data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir) / "checkpoints")
            backup_dir = Path(tmpdir) / "backups"
            # Create checkpoint with specific data
            manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=5,
                custom_field="custom_value"
            )
            # Backup and delete
            backup_path = manager.backup_checkpoint("test_session", backup_dir)
            session_dir = manager.output_dir / "test_session"
            shutil.rmtree(session_dir)
            # Restore
            manager.restore_checkpoint(backup_path)
            # Verify data
            checkpoint = manager.load_checkpoint_version("test_session", 1)
            assert checkpoint["turn"] == 5
            assert checkpoint["custom_field"] == "custom_value"
class TestThreadSafety:
    """Test thread safety of CheckpointManager."""
    def test_concurrent_saves(self):
        """Test concurrent checkpoint saves."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            def save_checkpoint(session_id: str, num_saves: int):
                for i in range(num_saves):
                    manager.save_checkpoint_versioned(
                        session_id=session_id,
                        turn=i
                    )
            # Run concurrent saves
            threads = []
            for i in range(5):
                thread = threading.Thread(
                    target=save_checkpoint,
                    args=(f"session_{i}", 10)
                )
                threads.append(thread)
                thread.start()
            # Wait for all threads
            for thread in threads:
                thread.join()
            # Verify all sessions have correct version count
            for i in range(5):
                versions = manager.list_checkpoint_versions(f"session_{i}")
                assert len(versions) == 10
    def test_concurrent_save_load(self):
        """Test concurrent save and load operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                output_dir=Path(tmpdir),
                max_versions_per_session=20 # Increase limit to avoid cleanup during test
            )
            # Pre-populate some checkpoints
            for i in range(5):
                manager.save_checkpoint_versioned(
                    session_id="shared_session",
                    turn=i
                )
            results = {"saves": 0, "loads": 0, "errors": 0}
            lock = threading.Lock()
            def save_operation():
                try:
                    manager.save_checkpoint_versioned(
                        session_id=f"session_{threading.current_thread().ident}",
                        turn=10
                    )
                    with lock:
                        results["saves"] += 1
                except Exception as e:
                    with lock:
                        results["errors"] += 1
            def load_operation():
                try:
                    # Load from the pre-populated session
                    checkpoint = manager.load_checkpoint_version("shared_session", 3)
                    if checkpoint is not None:
                        with lock:
                            results["loads"] += 1
                except Exception as e:
                    with lock:
                        results["errors"] += 1
            # Run mixed operations
            threads = []
            for _ in range(10):
                threads.append(threading.Thread(target=save_operation))
                threads.append(threading.Thread(target=load_operation))
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            assert results["saves"] == 10
            assert results["loads"] == 10
            assert results["errors"] == 0
    def test_concurrent_cleanup(self):
        """Test concurrent cleanup operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                output_dir=Path(tmpdir),
                max_versions_per_session=3
            )
            # Create many versions
            for i in range(20):
                manager.save_checkpoint_versioned(
                    session_id="test_session",
                    turn=i
                )
            # Concurrent cleanup (should be safe)
            threads = []
            for _ in range(5):
                thread = threading.Thread(
                    target=manager.cleanup_old_checkpoints,
                    args=(1,)
                )
                threads.append(thread)
                thread.start()
            for thread in threads:
                thread.join()
            # No crashes means success
    def test_reentrant_locking(self):
        """Test that RLock allows reentrant calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # This should not deadlock
            with manager._lock:
                with manager._lock:
                    manager.save_checkpoint_versioned(
                        session_id="test_session",
                        turn=1
                    )
            # Verify save succeeded
            assert manager.checkpoint_exists("test_session")
class TestInputValidation:
    """Test input validation and error handling."""
    def test_save_checkpoint_invalid_session_id(self):
        """Test save_checkpoint with invalid session_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            with pytest.raises(ValueError, match="session_id must be a non-empty string"):
                manager.save_checkpoint(
                    session_id="",
                    turn=1,
                    total_input_tokens=100,
                    total_output_tokens=50,
                    context_used_pct=10.0
                )
    def test_save_checkpoint_negative_turn(self):
        """Test save_checkpoint with negative turn."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            with pytest.raises(ValueError, match="turn must be non-negative"):
                manager.save_checkpoint(
                    session_id="test",
                    turn=-1,
                    total_input_tokens=100,
                    total_output_tokens=50,
                    context_used_pct=10.0
                )
    def test_save_checkpoint_negative_tokens(self):
        """Test save_checkpoint with negative tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            with pytest.raises(ValueError, match="total_input_tokens must be non-negative"):
                manager.save_checkpoint(
                    session_id="test",
                    turn=1,
                    total_input_tokens=-100,
                    total_output_tokens=50,
                    context_used_pct=10.0
                )
    def test_save_checkpoint_invalid_context_pct(self):
        """Test save_checkpoint with invalid context_used_pct."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            with pytest.raises(ValueError, match="context_used_pct must be between 0 and 100"):
                manager.save_checkpoint(
                    session_id="test",
                    turn=1,
                    total_input_tokens=100,
                    total_output_tokens=50,
                    context_used_pct=150.0
                )
    def test_save_checkpoint_versioned_invalid_session_id(self):
        """Test save_checkpoint_versioned with invalid session_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            with pytest.raises(ValueError, match="session_id must be a non-empty string"):
                manager.save_checkpoint_versioned(session_id="", turn=1)
    def test_load_checkpoint_invalid_session_id(self):
        """Test load_checkpoint with invalid session_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            with pytest.raises(ValueError, match="session_id must be a non-empty string"):
                manager.load_checkpoint("")
    def test_load_checkpoint_version_invalid_params(self):
        """Test load_checkpoint_version with invalid parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            with pytest.raises(ValueError, match="session_id must be a non-empty string"):
                manager.load_checkpoint_version("", 1)
            with pytest.raises(ValueError, match="version must be positive"):
                manager.load_checkpoint_version("test", 0)
    def test_validate_checkpoint_invalid_params(self):
        """Test validate_checkpoint with invalid parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            with pytest.raises(ValueError, match="session_id must be a non-empty string"):
                manager.validate_checkpoint("", 1)
            with pytest.raises(ValueError, match="version must be positive"):
                manager.validate_checkpoint("test", -1)
    def test_backup_checkpoint_invalid_session_id(self):
        """Test backup_checkpoint with invalid session_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            backup_dir = Path(tmpdir) / "backups"
            with pytest.raises(ValueError, match="session_id must be a non-empty string"):
                manager.backup_checkpoint("", backup_dir)
class TestAnalytics:
    """Test analytics and statistics functionality."""
    def test_get_analytics_initial(self):
        """Test analytics with no operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            analytics = manager.get_analytics()
            assert analytics["total_saves"] == 0
            assert analytics["total_loads"] == 0
            assert analytics["total_validations"] == 0
            assert analytics["total_cleanups"] == 0
            assert analytics["active_sessions"] == 0
            assert analytics["total_versions"] == 0
    def test_get_analytics_after_operations(self):
        """Test analytics after various operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Perform operations
            manager.save_checkpoint_versioned(session_id="session_1", turn=1)
            manager.save_checkpoint_versioned(session_id="session_1", turn=2)
            manager.save_checkpoint_versioned(session_id="session_2", turn=1)
            initial_load_count = manager._load_count
            manager.load_checkpoint_version("session_1", 1)
            manager.load_checkpoint_version("session_1", 2)
            manager.validate_checkpoint("session_1", 1)
            analytics = manager.get_analytics()
            assert analytics["total_saves"] == 3
            # validate_checkpoint also calls load_checkpoint_version internally
            assert analytics["total_loads"] >= 2
            assert analytics["total_validations"] == 1
            assert analytics["active_sessions"] == 2
            assert analytics["total_versions"] == 3
    def test_compression_ratio_tracking(self):
        """Test compression ratio calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                output_dir=Path(tmpdir),
                compression_enabled=True
            )
            # Save with compressible data
            manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=1,
                large_data="Repeated data. " * 1000
            )
            analytics = manager.get_analytics()
            assert analytics["compression_enabled"] is True
            assert analytics["compression_ratio"] > 0
    def test_operations_per_minute(self):
        """Test operations per minute calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Perform some operations
            for i in range(10):
                manager.save_checkpoint_versioned(session_id=f"session_{i}", turn=1)
            analytics = manager.get_analytics()
            # Should have non-zero operation rate
            assert analytics["operations_per_minute"] > 0
    def test_operation_history(self):
        """Test that operation history is tracked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir), history_size=10)
            # Perform operations
            manager.save_checkpoint_versioned(session_id="test_session", turn=1)
            manager.load_checkpoint_version("test_session", 1)
            # Check history
            assert len(manager._operation_history) == 2
            assert manager._operation_history[0]["operation"] == "save_checkpoint_versioned"
            assert manager._operation_history[1]["operation"] == "load_checkpoint_version"
    def test_operation_history_bounded(self):
        """Test that operation history respects maxlen."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir), history_size=5)
            # Perform more operations than history size
            for i in range(10):
                manager.save_checkpoint_versioned(session_id=f"session_{i}", turn=1)
            # History should be bounded to 5
            assert len(manager._operation_history) == 5
class TestExport:
    """Test export functionality."""
    def test_export_metrics_json(self):
        """Test exporting metrics in JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Perform some operations
            manager.save_checkpoint_versioned(session_id="test_session", turn=1)
            # Export
            json_data = manager.export_metrics(export_format="json")
            assert json_data is not None
            data = json.loads(json_data)
            assert "analytics" in data
            assert "history" in data
            assert "export_timestamp" in data
    def test_export_metrics_csv(self):
        """Test exporting metrics in CSV format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Perform some operations
            manager.save_checkpoint_versioned(session_id="test_session", turn=1)
            # Export
            csv_data = manager.export_metrics(export_format="csv")
            assert csv_data is not None
            assert "Checkpoint Manager Analytics" in csv_data
            assert "Operation History" in csv_data
    def test_export_invalid_format(self):
        """Test export with invalid format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            with pytest.raises(ValueError, match="Unsupported export format"):
                manager.export_metrics(export_format="xml")
    def test_get_summary(self):
        """Test getting human-readable summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Perform operations
            manager.save_checkpoint_versioned(session_id="test_session", turn=1)
            manager.save_checkpoint_versioned(session_id="test_session", turn=2)
            summary = manager.get_summary()
            assert "Checkpoint Manager Summary" in summary
            assert "Active Sessions" in summary
            assert "Total Versions" in summary
            assert "Compression" in summary
class TestPerformance:
    """Performance benchmark tests."""
    def test_save_performance(self):
        """Test that save operations are fast."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            start = time.time()
            for i in range(100):
                manager.save_checkpoint_versioned(
                    session_id=f"session_{i % 10}",
                    turn=i
                )
            elapsed = time.time() - start
            # Should complete 100 saves in reasonable time
            assert elapsed < 5.0 # 5 seconds for 100 saves
            # Average time per save
            avg_time = elapsed / 100
            assert avg_time < 0.05 # Less than 50ms per save
    def test_load_performance(self):
        """Test that load operations are fast."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Pre-populate
            for i in range(10):
                manager.save_checkpoint_versioned(
                    session_id=f"session_{i}",
                    turn=1
                )
            start = time.time()
            for i in range(100):
                manager.load_checkpoint_version(f"session_{i % 10}", 1)
            elapsed = time.time() - start
            # Should complete 100 loads quickly
            assert elapsed < 2.0 # 2 seconds for 100 loads
            avg_time = elapsed / 100
            assert avg_time < 0.02 # Less than 20ms per load
    def test_list_versions_performance(self):
        """Test performance of listing versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Create many versions
            for i in range(100):
                manager.save_checkpoint_versioned(
                    session_id="test_session",
                    turn=i
                )
            start = time.time()
            versions = manager.list_checkpoint_versions("test_session")
            elapsed = time.time() - start
            # Should list 100 versions quickly
            assert elapsed < 1.0 # Less than 1 second
            # Note: Cleanup will keep only max_versions_per_session
            assert len(versions) == min(100, manager.max_versions_per_session)
    def test_concurrent_performance(self):
        """Test performance under concurrent load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            def worker(worker_id: int):
                for i in range(20):
                    manager.save_checkpoint_versioned(
                        session_id=f"session_{worker_id}",
                        turn=i
                    )
            start = time.time()
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(worker, i) for i in range(10)]
                for future in as_completed(futures):
                    future.result()
            elapsed = time.time() - start
            # 10 workers x 20 saves = 200 saves
            assert elapsed < 10.0 # Should complete in reasonable time
    def test_memory_efficiency(self):
        """Test that memory usage is bounded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            manager._max_sessions = 100 # Set limit
            # Create many sessions (more than limit)
            for i in range(200):
                manager.save_checkpoint_versioned(
                    session_id=f"session_{i}",
                    turn=1
                )
            # Version tracking should be bounded
            assert len(manager._version_tracking) <= 100
class TestEdgeCases:
    """Test edge cases and corner scenarios."""
    def test_empty_session_id(self):
        """Test handling of empty session ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            with pytest.raises(ValueError):
                manager.save_checkpoint_versioned(session_id="", turn=1)
    def test_very_large_checkpoint(self):
        """Test saving very large checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Create large data
            large_data = {"data": "x" * 1000000} # 1MB of data
            path, version = manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=1,
                **large_data
            )
            assert path.exists()
            # Should be able to load it back
            checkpoint = manager.load_checkpoint_version("test_session", 1)
            assert checkpoint is not None
    def test_special_characters_in_session_id(self):
        """Test handling of special characters in session ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            # Some special characters (but valid for filesystem)
            session_id = "test_session-123"
            path, version = manager.save_checkpoint_versioned(
                session_id=session_id,
                turn=1
            )
            assert path.exists()
            checkpoint = manager.load_checkpoint_version(session_id, 1)
            assert checkpoint is not None
    def test_unicode_in_checkpoint_data(self):
        """Test handling of unicode data in checkpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            unicode_data = {
                "message": "Hello 世界 ",
                "emoji": ""
            }
            path, version = manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=1,
                **unicode_data
            )
            checkpoint = manager.load_checkpoint_version("test_session", 1)
            assert checkpoint["message"] == "Hello 世界 "
            assert checkpoint["emoji"] == ""
    def test_checkpoint_with_none_values(self):
        """Test checkpoint with None values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            path, version = manager.save_checkpoint_versioned(
                session_id="test_session",
                turn=1,
                optional_field=None
            )
            checkpoint = manager.load_checkpoint_version("test_session", 1)
            assert checkpoint["optional_field"] is None
    def test_repr(self):
        """Test __repr__ method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            manager.save_checkpoint_versioned(session_id="test_session", turn=1)
            repr_str = repr(manager)
            assert "CheckpointManager" in repr_str
            assert "sessions=" in repr_str
            assert "versions=" in repr_str
    def test_checkpoint_exists_with_invalid_input(self):
        """Test checkpoint_exists with invalid input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(output_dir=Path(tmpdir))
            assert manager.checkpoint_exists("") is False
            assert manager.checkpoint_exists(None) is False
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
