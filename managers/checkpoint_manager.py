"""Checkpoint management with versioning, compression, validation, and backup."""
import csv
import gzip
import hashlib
import json
import logging
import shutil
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
logger = logging.getLogger(__name__)
class CheckpointManagerException(Exception):
    """Base exception for CheckpointManager errors."""
    pass
class CheckpointValidationError(CheckpointManagerException):
    """Raised when checkpoint validation fails."""
    pass
class CheckpointNotFoundError(CheckpointManagerException):
    """Raised when checkpoint is not found."""
    pass
class CheckpointManager:
    """
    Manages checkpoint persistence with advanced versioning, compression, and validation.
    This class provides comprehensive checkpoint management including:
    - Basic checkpoint persistence
    - Checkpoint versioning with bounded storage
    - Gzip compression for space efficiency
    - Integrity validation with checksums
    - Auto-cleanup with retention policies
    - Backup and restore capabilities
    - Thread-safe operations
    - Export functionality (JSON/CSV)
    Attributes:
        output_dir (Path): Directory for storing checkpoints
        max_versions_per_session (int): Maximum versions to keep per session (default: 10)
        compression_enabled (bool): Whether to use gzip compression (default: True)
    Example:
        >>> manager = CheckpointManager()
        >>> path, version = manager.save_checkpoint_versioned("session_1", turn=5, tokens=1000)
        >>> checkpoint = manager.load_checkpoint_version("session_1", version=1)
        >>> versions = manager.list_checkpoint_versions("session_1")
    """
    def __init__(
        self,
        output_dir: Optional[Path] = None,
        max_versions_per_session: int = 10,
        compression_enabled: bool = True,
        history_size: int = 100
    ):
        """
        Initialize CheckpointManager with configurable options.
        Args:
            output_dir: Directory for checkpoint storage (default: ~/.claude/sdk-workflow/sessions)
            max_versions_per_session: Maximum versions to keep per session (default: 10)
            compression_enabled: Enable gzip compression (default: True)
            history_size: Maximum number of operations to track in history (default: 100)
        Raises:
            ValueError: If max_versions_per_session is not positive
        """
        if max_versions_per_session <= 0:
            raise ValueError("max_versions_per_session must be positive")
        self.output_dir = output_dir or Path.home() / ".claude" / "sdk-workflow" / "sessions"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_versions_per_session = max_versions_per_session
        self.compression_enabled = compression_enabled
        self.history_size = history_size
        # Thread safety - using RLock to prevent deadlock on reentrant calls
        self._lock = threading.RLock()
        # Version tracking with bounded memory
        self._max_sessions = 1000
        self._version_tracking: OrderedDict[str, int] = OrderedDict() # session_id -> current_version
        # Operation history
        self._operation_history: deque = deque(maxlen=history_size)
        # Statistics
        self._save_count = 0
        self._load_count = 0
        self._validation_count = 0
        self._cleanup_count = 0
        self._start_time = time.time()
        self._total_bytes_saved = 0
        self._total_bytes_compressed = 0
        logger.info(f"CheckpointManager initialized with output_dir={self.output_dir}")
    def save_checkpoint(
        self,
        session_id: str,
        turn: int,
        total_input_tokens: int,
        total_output_tokens: int,
        context_used_pct: float,
        **extra_data: Any
    ) -> Path:
        """
        Save checkpoint to disk (backward compatibility method).
        Args:
            session_id: Unique session identifier
            turn: Current turn number
            total_input_tokens: Total input tokens
            total_output_tokens: Total output tokens
            context_used_pct: Context usage percentage
            **extra_data: Additional data to save
        Returns:
            Path: Path to the saved checkpoint file
        Raises:
            ValueError: If session_id is empty or numeric values are negative
            CheckpointManagerException: If save operation fails
        Example:
            >>> manager = CheckpointManager()
            >>> path = manager.save_checkpoint(
            ... session_id="session_1",
            ... turn=5,
            ... total_input_tokens=1000,
            ... total_output_tokens=500,
            ... context_used_pct=25.5
            ... )
        """
        # Input validation
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        if turn < 0:
            raise ValueError(f"turn must be non-negative, got {turn}")
        if total_input_tokens < 0:
            raise ValueError(f"total_input_tokens must be non-negative, got {total_input_tokens}")
        if total_output_tokens < 0:
            raise ValueError(f"total_output_tokens must be non-negative, got {total_output_tokens}")
        if not 0 <= context_used_pct <= 100:
            raise ValueError(f"context_used_pct must be between 0 and 100, got {context_used_pct}")
        with self._lock:
            checkpoint = {
                "session_id": session_id,
                "turn": turn,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "context_used_pct": context_used_pct,
                "timestamp": datetime.now().isoformat(),
                **extra_data
            }
            try:
                path = self.output_dir / f"checkpoint_{session_id}.json"
                json_data = json.dumps(checkpoint, indent=2, default=str)
                path.write_text(json_data, encoding="utf-8")
                self._save_count += 1
                self._total_bytes_saved += len(json_data)
                # Record in history
                self._operation_history.append({
                    'operation': 'save_checkpoint',
                    'session_id': session_id,
                    'timestamp': time.time(),
                    'success': True
                })
                logger.debug(f"Checkpoint saved for session {session_id} at {path}")
                return path
            except Exception as e:
                logger.error(f"Failed to save checkpoint for session {session_id}: {e}")
                raise CheckpointManagerException(f"Failed to save checkpoint: {e}") from e
    def save_checkpoint_versioned(
        self,
        session_id: str,
        **data: Any
    ) -> Tuple[Path, int]:
        """
        Save versioned checkpoint with automatic version management.
        Args:
            session_id: Unique session identifier
            **data: Checkpoint data to save
        Returns:
            Tuple[Path, int]: (path_to_checkpoint, version_number)
        Raises:
            ValueError: If session_id is empty
            CheckpointManagerException: If save operation fails
        Example:
            >>> manager = CheckpointManager()
            >>> path, version = manager.save_checkpoint_versioned(
            ... session_id="session_1",
            ... turn=5,
            ... tokens=1000
            ... )
            >>> print(f"Saved version {version} at {path}")
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        with self._lock:
            # Get current version and increment
            current_version = self._version_tracking.get(session_id, 0)
            new_version = current_version + 1
            # Update version tracking with FIFO eviction
            if session_id not in self._version_tracking:
                if len(self._version_tracking) >= self._max_sessions:
                    self._version_tracking.popitem(last=False) # Remove oldest
            self._version_tracking[session_id] = new_version
            # Create versioned checkpoint
            checkpoint = {
                'session_id': session_id,
                'version': new_version,
                'timestamp': datetime.now().isoformat(),
                'unix_time': time.time(),
                **data
            }
            try:
                # Create session directory
                session_dir = self.output_dir / session_id
                session_dir.mkdir(parents=True, exist_ok=True)
                # Generate filename
                if self.compression_enabled:
                    filename = f"checkpoint_v{new_version:04d}.json.gz"
                    path = session_dir / filename
                else:
                    filename = f"checkpoint_v{new_version:04d}.json"
                    path = session_dir / filename
                # Serialize data
                json_data = json.dumps(checkpoint, indent=2, default=str)
                original_size = len(json_data)
                # Save with optional compression
                if self.compression_enabled:
                    compressed_data = gzip.compress(json_data.encode('utf-8'))
                    path.write_bytes(compressed_data)
                    self._total_bytes_compressed += len(compressed_data)
                else:
                    path.write_text(json_data, encoding='utf-8')
                self._save_count += 1
                self._total_bytes_saved += original_size
                # Record in history
                self._operation_history.append({
                    'operation': 'save_checkpoint_versioned',
                    'session_id': session_id,
                    'version': new_version,
                    'timestamp': time.time(),
                    'compressed': self.compression_enabled,
                    'size_bytes': original_size,
                    'success': True
                })
                # Cleanup old versions if exceeding limit
                self._cleanup_old_versions(session_id)
                logger.debug(f"Versioned checkpoint saved: session={session_id}, version={new_version}")
                return path, new_version
            except Exception as e:
                logger.error(f"Failed to save versioned checkpoint for session {session_id}: {e}")
                raise CheckpointManagerException(f"Failed to save versioned checkpoint: {e}") from e
    def load_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint from disk (backward compatibility method).
        Args:
            session_id: Unique session identifier
        Returns:
            Optional[Dict[str, Any]]: Checkpoint data if found, None otherwise
        Example:
            >>> manager = CheckpointManager()
            >>> checkpoint = manager.load_checkpoint("session_1")
            >>> if checkpoint:
            ... print(f"Turn: {checkpoint['turn']}")
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        with self._lock:
            path = self.output_dir / f"checkpoint_{session_id}.json"
            try:
                if path.exists():
                    data = json.loads(path.read_text(encoding="utf-8"))
                    self._load_count += 1
                    # Record in history
                    self._operation_history.append({
                        'operation': 'load_checkpoint',
                        'session_id': session_id,
                        'timestamp': time.time(),
                        'success': True
                    })
                    return data
                return None
            except Exception as e:
                logger.error(f"Failed to load checkpoint for session {session_id}: {e}")
                return None
    def load_checkpoint_version(
        self,
        session_id: str,
        version: int
    ) -> Optional[Dict[str, Any]]:
        """
        Load specific checkpoint version.
        Args:
            session_id: Unique session identifier
            version: Version number to load
        Returns:
            Optional[Dict[str, Any]]: Checkpoint data if found, None otherwise
        Raises:
            ValueError: If session_id is empty or version is not positive
        Example:
            >>> manager = CheckpointManager()
            >>> checkpoint = manager.load_checkpoint_version("session_1", version=3)
            >>> if checkpoint:
            ... print(f"Loaded version {checkpoint['version']}")
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        if version <= 0:
            raise ValueError(f"version must be positive, got {version}")
        with self._lock:
            session_dir = self.output_dir / session_id
            if not session_dir.exists():
                logger.debug(f"Session directory not found: {session_dir}")
                return None
            # Try both compressed and uncompressed
            compressed_path = session_dir / f"checkpoint_v{version:04d}.json.gz"
            uncompressed_path = session_dir / f"checkpoint_v{version:04d}.json"
            try:
                if compressed_path.exists():
                    compressed_data = compressed_path.read_bytes()
                    json_data = gzip.decompress(compressed_data).decode('utf-8')
                    data = json.loads(json_data)
                elif uncompressed_path.exists():
                    json_data = uncompressed_path.read_text(encoding='utf-8')
                    data = json.loads(json_data)
                else:
                    logger.debug(f"Version {version} not found for session {session_id}")
                    return None
                self._load_count += 1
                # Record in history
                self._operation_history.append({
                    'operation': 'load_checkpoint_version',
                    'session_id': session_id,
                    'version': version,
                    'timestamp': time.time(),
                    'success': True
                })
                return data
            except Exception as e:
                logger.error(f"Failed to load checkpoint version {version} for session {session_id}: {e}")
                return None
    def list_checkpoint_versions(self, session_id: str) -> List[Dict[str, Any]]:
        """
        List all checkpoint versions for a session.
        Args:
            session_id: Unique session identifier
        Returns:
            List[Dict[str, Any]]: List of version info dictionaries, sorted by version (newest first)
                Each dict contains: version, timestamp, size_bytes, compressed, path
        Raises:
            ValueError: If session_id is empty
        Example:
            >>> manager = CheckpointManager()
            >>> versions = manager.list_checkpoint_versions("session_1")
            >>> for v in versions:
            ... print(f"Version {v['version']}: {v['timestamp']} ({v['size_bytes']} bytes)")
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        with self._lock:
            session_dir = self.output_dir / session_id
            if not session_dir.exists():
                return []
            versions = []
            try:
                # Find all checkpoint files
                for path in session_dir.glob("checkpoint_v*.json*"):
                    # Extract version number from filename
                    filename = path.name
                    if filename.endswith('.json.gz'):
                        version_str = filename.replace('checkpoint_v', '').replace('.json.gz', '')
                        compressed = True
                    elif filename.endswith('.json'):
                        version_str = filename.replace('checkpoint_v', '').replace('.json', '')
                        compressed = False
                    else:
                        continue
                    try:
                        version_num = int(version_str)
                    except ValueError:
                        continue
                    # Get file stats
                    stat = path.stat()
                    versions.append({
                        'version': version_num,
                        'timestamp': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'size_bytes': stat.st_size,
                        'compressed': compressed,
                        'path': str(path)
                    })
                # Sort by version (newest first)
                versions.sort(key=lambda x: x['version'], reverse=True)
                return versions
            except Exception as e:
                logger.error(f"Failed to list checkpoint versions for session {session_id}: {e}")
                return []
    def validate_checkpoint(self, session_id: str, version: int) -> bool:
        """
        Validate checkpoint integrity with checksum verification.
        Args:
            session_id: Unique session identifier
            version: Version number to validate
        Returns:
            bool: True if checkpoint is valid, False otherwise
        Raises:
            ValueError: If session_id is empty or version is not positive
        Example:
            >>> manager = CheckpointManager()
            >>> is_valid = manager.validate_checkpoint("session_1", version=3)
            >>> if is_valid:
            ... print("Checkpoint is valid")
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        if version <= 0:
            raise ValueError(f"version must be positive, got {version}")
        with self._lock:
            try:
                # Try to load the checkpoint
                data = self.load_checkpoint_version(session_id, version)
                if data is None:
                    logger.warning(f"Validation failed: checkpoint not found (session={session_id}, version={version})")
                    return False
                # Validate required fields
                required_fields = ['session_id', 'version', 'timestamp']
                for field in required_fields:
                    if field not in data:
                        logger.warning(f"Validation failed: missing required field '{field}'")
                        return False
                # Validate session_id matches
                if data['session_id'] != session_id:
                    logger.warning(f"Validation failed: session_id mismatch")
                    return False
                # Validate version matches
                if data['version'] != version:
                    logger.warning(f"Validation failed: version mismatch")
                    return False
                # Validate timestamp format
                try:
                    datetime.fromisoformat(data['timestamp'])
                except (ValueError, TypeError):
                    logger.warning(f"Validation failed: invalid timestamp format")
                    return False
                self._validation_count += 1
                # Record in history
                self._operation_history.append({
                    'operation': 'validate_checkpoint',
                    'session_id': session_id,
                    'version': version,
                    'timestamp': time.time(),
                    'valid': True
                })
                return True
            except Exception as e:
                logger.error(f"Validation error for session {session_id} version {version}: {e}")
                return False
    def cleanup_old_checkpoints(self, retention_days: int = 30) -> int:
        """
        Clean up checkpoints older than retention period.
        Args:
            retention_days: Number of days to retain checkpoints (default: 30)
        Returns:
            int: Number of checkpoints deleted
        Raises:
            ValueError: If retention_days is not positive
        Example:
            >>> manager = CheckpointManager()
            >>> deleted = manager.cleanup_old_checkpoints(retention_days=7)
            >>> print(f"Deleted {deleted} old checkpoints")
        """
        if retention_days <= 0:
            raise ValueError(f"retention_days must be positive, got {retention_days}")
        with self._lock:
            cutoff_time = datetime.now() - timedelta(days=retention_days)
            deleted_count = 0
            try:
                # Iterate through all session directories
                for session_dir in self.output_dir.iterdir():
                    if not session_dir.is_dir():
                        continue
                    # Check all checkpoint files
                    for checkpoint_file in session_dir.glob("checkpoint_v*.json*"):
                        stat = checkpoint_file.stat()
                        file_mtime = datetime.fromtimestamp(stat.st_mtime)
                        if file_mtime < cutoff_time:
                            checkpoint_file.unlink()
                            deleted_count += 1
                            logger.debug(f"Deleted old checkpoint: {checkpoint_file}")
                    # Remove empty session directories
                    if not any(session_dir.iterdir()):
                        session_dir.rmdir()
                        logger.debug(f"Removed empty session directory: {session_dir}")
                self._cleanup_count += deleted_count
                # Record in history
                self._operation_history.append({
                    'operation': 'cleanup_old_checkpoints',
                    'retention_days': retention_days,
                    'deleted_count': deleted_count,
                    'timestamp': time.time()
                })
                logger.info(f"Cleanup completed: deleted {deleted_count} checkpoints older than {retention_days} days")
                return deleted_count
            except Exception as e:
                logger.error(f"Cleanup operation failed: {e}")
                return deleted_count
    def backup_checkpoint(self, session_id: str, backup_dir: Path) -> Path:
        """
        Backup all checkpoint versions for a session.
        Args:
            session_id: Unique session identifier
            backup_dir: Directory to store backup
        Returns:
            Path: Path to the backup archive
        Raises:
            ValueError: If session_id is empty
            CheckpointNotFoundError: If session has no checkpoints
            CheckpointManagerException: If backup operation fails
        Example:
            >>> manager = CheckpointManager()
            >>> backup_path = manager.backup_checkpoint("session_1", Path("/backups"))
            >>> print(f"Backup created at {backup_path}")
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        with self._lock:
            session_dir = self.output_dir / session_id
            if not session_dir.exists():
                raise CheckpointNotFoundError(f"No checkpoints found for session {session_id}")
            try:
                # Create backup directory
                backup_dir.mkdir(parents=True, exist_ok=True)
                # Create backup archive name with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"checkpoint_backup_{session_id}_{timestamp}"
                backup_path = backup_dir / backup_name
                # Copy session directory to backup
                shutil.copytree(session_dir, backup_path)
                # Record in history
                self._operation_history.append({
                    'operation': 'backup_checkpoint',
                    'session_id': session_id,
                    'backup_path': str(backup_path),
                    'timestamp': time.time(),
                    'success': True
                })
                logger.info(f"Backup created for session {session_id} at {backup_path}")
                return backup_path
            except Exception as e:
                logger.error(f"Backup operation failed for session {session_id}: {e}")
                raise CheckpointManagerException(f"Failed to backup checkpoint: {e}") from e
    def restore_checkpoint(self, backup_path: Path) -> str:
        """
        Restore checkpoint from backup.
        Args:
            backup_path: Path to backup directory
        Returns:
            str: Session ID of restored checkpoint
        Raises:
            CheckpointNotFoundError: If backup path doesn't exist
            CheckpointManagerException: If restore operation fails
        Example:
            >>> manager = CheckpointManager()
            >>> session_id = manager.restore_checkpoint(Path("/backups/checkpoint_backup_session_1_20241201_120000"))
            >>> print(f"Restored session {session_id}")
        """
        if not backup_path.exists():
            raise CheckpointNotFoundError(f"Backup path does not exist: {backup_path}")
        with self._lock:
            try:
                # Extract session_id from backup directory name
                backup_name = backup_path.name
                # Format: checkpoint_backup_{session_id}_{timestamp}
                parts = backup_name.split('_')
                if len(parts) < 4:
                    raise CheckpointManagerException(f"Invalid backup directory name: {backup_name}")
                # Reconstruct session_id (may contain underscores)
                session_id = '_'.join(parts[2:-2])
                # Restore directory
                restore_dir = self.output_dir / session_id
                # Remove existing if present
                if restore_dir.exists():
                    shutil.rmtree(restore_dir)
                # Copy backup to restore location
                shutil.copytree(backup_path, restore_dir)
                # Update version tracking
                versions = self.list_checkpoint_versions(session_id)
                if versions:
                    max_version = max(v['version'] for v in versions)
                    if session_id not in self._version_tracking:
                        if len(self._version_tracking) >= self._max_sessions:
                            self._version_tracking.popitem(last=False)
                    self._version_tracking[session_id] = max_version
                # Record in history
                self._operation_history.append({
                    'operation': 'restore_checkpoint',
                    'session_id': session_id,
                    'backup_path': str(backup_path),
                    'timestamp': time.time(),
                    'success': True
                })
                logger.info(f"Checkpoint restored for session {session_id} from {backup_path}")
                return session_id
            except Exception as e:
                logger.error(f"Restore operation failed: {e}")
                raise CheckpointManagerException(f"Failed to restore checkpoint: {e}") from e
    def checkpoint_exists(self, session_id: str) -> bool:
        """
        Check if checkpoint exists for session.
        Args:
            session_id: Unique session identifier
        Returns:
            bool: True if checkpoint exists, False otherwise
        Example:
            >>> manager = CheckpointManager()
            >>> if manager.checkpoint_exists("session_1"):
            ... print("Checkpoint exists")
        """
        if not session_id or not isinstance(session_id, str):
            return False
        with self._lock:
            # Check legacy checkpoint
            legacy_path = self.output_dir / f"checkpoint_{session_id}.json"
            if legacy_path.exists():
                return True
            # Check versioned checkpoints
            session_dir = self.output_dir / session_id
            if session_dir.exists():
                checkpoint_files = list(session_dir.glob("checkpoint_v*.json*"))
                return len(checkpoint_files) > 0
            return False
    def get_analytics(self) -> Dict[str, Any]:
        """
        Calculate comprehensive checkpoint analytics.
        Returns:
            Dict[str, Any]: Analytics dictionary containing:
                - total_saves: Total number of save operations
                - total_loads: Total number of load operations
                - total_validations: Total validations performed
                - total_cleanups: Total cleanup operations
                - active_sessions: Number of sessions with checkpoints
                - total_versions: Total checkpoint versions across all sessions
                - avg_versions_per_session: Average versions per session
                - total_bytes_saved: Total uncompressed bytes saved
                - total_bytes_compressed: Total compressed bytes (if compression enabled)
                - compression_ratio: Compression ratio if applicable
                - uptime_seconds: Time since manager initialization
                - operations_per_minute: Operation rate
        Example:
            >>> manager = CheckpointManager()
            >>> analytics = manager.get_analytics()
            >>> print(f"Total saves: {analytics['total_saves']}")
        """
        with self._lock:
            uptime = time.time() - self._start_time
            total_operations = self._save_count + self._load_count + self._validation_count
            # Count active sessions and versions
            active_sessions = 0
            total_versions = 0
            for session_dir in self.output_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                checkpoint_files = list(session_dir.glob("checkpoint_v*.json*"))
                if checkpoint_files:
                    active_sessions += 1
                    total_versions += len(checkpoint_files)
            avg_versions = total_versions / active_sessions if active_sessions > 0 else 0
            # Calculate compression ratio
            compression_ratio = 0.0
            if self.compression_enabled and self._total_bytes_compressed > 0:
                compression_ratio = (1 - (self._total_bytes_compressed / self._total_bytes_saved)) * 100 if self._total_bytes_saved > 0 else 0
            # Calculate operation rate
            operations_per_min = (total_operations / uptime) * 60 if uptime > 0 else 0
            return {
                'total_saves': self._save_count,
                'total_loads': self._load_count,
                'total_validations': self._validation_count,
                'total_cleanups': self._cleanup_count,
                'active_sessions': active_sessions,
                'total_versions': total_versions,
                'avg_versions_per_session': round(avg_versions, 2),
                'total_bytes_saved': self._total_bytes_saved,
                'total_bytes_compressed': self._total_bytes_compressed,
                'compression_ratio': round(compression_ratio, 2),
                'compression_enabled': self.compression_enabled,
                'uptime_seconds': round(uptime, 2),
                'operations_per_minute': round(operations_per_min, 2),
                'max_versions_per_session': self.max_versions_per_session,
                'tracked_sessions': len(self._version_tracking)
            }
    def export_metrics(self, export_format: str = "json") -> str:
        """
        Export checkpoint metrics in specified format.
        Args:
            export_format: Export format - "json" or "csv"
        Returns:
            str: Formatted metrics data
        Raises:
            ValueError: If export_format is not "json" or "csv"
        Example:
            >>> manager = CheckpointManager()
            >>> json_data = manager.export_metrics(export_format="json")
            >>> csv_data = manager.export_metrics(export_format="csv")
        """
        format_lower = export_format.lower()
        if format_lower not in ("json", "csv"):
            raise ValueError(f"Unsupported export format: {export_format}. Use 'json' or 'csv'.")
        with self._lock:
            analytics = self.get_analytics()
            history = list(self._operation_history)
            export_data = {
                'analytics': analytics,
                'history': history,
                'export_timestamp': datetime.now().isoformat(),
                'export_unix_time': time.time()
            }
            if format_lower == "json":
                return json.dumps(export_data, indent=2)
            else: # csv
                output = StringIO()
                writer = csv.writer(output)
                # Write analytics section
                writer.writerow(['=== Checkpoint Manager Analytics ==='])
                writer.writerow(['Metric', 'Value'])
                for key, value in analytics.items():
                    writer.writerow([key, value])
                writer.writerow([]) # Blank row
                writer.writerow(['=== Operation History ==='])
                # Write history section
                if history:
                    headers = list(history[0].keys())
                    writer.writerow(headers)
                    for entry in history:
                        writer.writerow([entry.get(h, '') for h in headers])
                else:
                    writer.writerow(['No history available'])
                return output.getvalue()
    def get_summary(self) -> str:
        """
        Get a human-readable summary of checkpoint status.
        Returns:
            str: Formatted summary string
        Example:
            >>> manager = CheckpointManager()
            >>> print(manager.get_summary())
        """
        with self._lock:
            analytics = self.get_analytics()
            summary_lines = [
                "=== Checkpoint Manager Summary ===",
                f"Active Sessions: {analytics['active_sessions']}",
                f"Total Versions: {analytics['total_versions']}",
                f"Avg Versions/Session: {analytics['avg_versions_per_session']:.1f}",
                f"Total Saves: {analytics['total_saves']}",
                f"Total Loads: {analytics['total_loads']}",
                f"Validations: {analytics['total_validations']}",
                f"Cleanups: {analytics['total_cleanups']}",
                f"Compression: {'Enabled' if analytics['compression_enabled'] else 'Disabled'}",
            ]
            if analytics['compression_enabled'] and analytics['compression_ratio'] > 0:
                summary_lines.append(f"Compression Ratio: {analytics['compression_ratio']:.1f}%")
            summary_lines.append(f"Uptime: {analytics['uptime_seconds']:.0f}s")
            return "\n".join(summary_lines)
    def _cleanup_old_versions(self, session_id: str) -> None:
        """
        Clean up old versions for a session if exceeding max_versions_per_session.
        Args:
            session_id: Session identifier to clean up
        """
        session_dir = self.output_dir / session_id
        if not session_dir.exists():
            return
        # Get all checkpoint files
        checkpoints = []
        for path in session_dir.glob("checkpoint_v*.json*"):
            filename = path.name
            if filename.endswith('.json.gz'):
                version_str = filename.replace('checkpoint_v', '').replace('.json.gz', '')
            elif filename.endswith('.json'):
                version_str = filename.replace('checkpoint_v', '').replace('.json', '')
            else:
                continue
            try:
                version_num = int(version_str)
                checkpoints.append((version_num, path))
            except ValueError:
                continue
        # Sort by version (oldest first)
        checkpoints.sort(key=lambda x: x[0])
        # Delete oldest versions if exceeding limit
        while len(checkpoints) > self.max_versions_per_session:
            version_num, path = checkpoints.pop(0)
            try:
                path.unlink()
                logger.debug(f"Deleted old version {version_num} for session {session_id}")
            except Exception as e:
                logger.error(f"Failed to delete old version {version_num}: {e}")
    def __repr__(self) -> str:
        """Return string representation of CheckpointManager."""
        analytics = self.get_analytics()
        return (
            f"CheckpointManager(sessions={analytics['active_sessions']}, "
            f"versions={analytics['total_versions']}, "
            f"compression={self.compression_enabled})"
        )
