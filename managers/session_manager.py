"""Session management with persistence, search, analytics, and archival."""
import csv
import json
import logging
import threading
import time
import uuid
from collections import OrderedDict, deque
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
logger = logging.getLogger(__name__)
class SessionManagerException(Exception):
    """Base exception for SessionManager errors."""
    pass
class SessionNotFoundError(SessionManagerException):
    """Raised when session is not found."""
    pass
class SessionManager:
    """
    Manages session lifecycle with advanced persistence, search, and analytics.
    This class provides comprehensive session management including:
    - Basic session lifecycle (create, start, end)
    - Session persistence to disk
    - Search and filter capabilities
    - Session analytics and statistics
    - Tagging for categorization
    - Session archival
    - Auto-cleanup with age-based removal
    - Thread-safe operations
    - Bounded memory with LRU eviction
    - Export functionality (JSON/CSV)
    Attributes:
        active_sessions (OrderedDict): Currently active sessions
        max_sessions (int): Maximum sessions to keep in memory (default: 1000)
        persistence_enabled (bool): Whether to persist sessions to disk (default: True)
    Example:
        >>> manager = SessionManager()
        >>> session_id = manager.start_session(task="Test task", agent_name="TestAgent")
        >>> manager.tag_session(session_id, ["important", "testing"])
        >>> sessions = manager.search_sessions({"tags": ["important"]})
        >>> analytics = manager.get_session_analytics()
    """
    def __init__(
        self,
        max_sessions: int = 1000,
        persistence_dir: Optional[Path] = None,
        persistence_enabled: bool = True,
        history_size: int = 100
    ):
        """
        Initialize SessionManager with configurable options.
        Args:
            max_sessions: Maximum sessions to keep in memory (default: 1000)
            persistence_dir: Directory for session persistence (default: ~/.claude/sdk-workflow/sessions)
            persistence_enabled: Enable session persistence (default: True)
            history_size: Maximum number of operations to track in history (default: 100)
        Raises:
            ValueError: If max_sessions is not positive
        """
        if max_sessions <= 0:
            raise ValueError("max_sessions must be positive")
        self.max_sessions = max_sessions
        self.persistence_enabled = persistence_enabled
        self.history_size = history_size
        # Persistence directory
        self.persistence_dir = persistence_dir or Path.home() / ".claude" / "sdk-workflow" / "sessions"
        if self.persistence_enabled:
            self.persistence_dir.mkdir(parents=True, exist_ok=True)
        # Thread safety - using RLock to prevent deadlock on reentrant calls
        self._lock = threading.RLock()
        # Active sessions with bounded memory (LRU using OrderedDict)
        self.active_sessions: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        # Session tagging
        self._session_tags: Dict[str, Set[str]] = {}
        # Operation history
        self._operation_history: deque = deque(maxlen=history_size)
        # Statistics
        self._total_sessions_created = 0
        self._total_sessions_ended = 0
        self._total_sessions_archived = 0
        self._start_time = time.time()
        logger.info(f"SessionManager initialized with max_sessions={max_sessions}, persistence={persistence_enabled}")
    def generate_session_id(self) -> str:
        """
        Generate unique session ID.
        Returns:
            str: Unique session identifier
        Example:
            >>> manager = SessionManager()
            >>> session_id = manager.generate_session_id()
            >>> print(session_id) # e.g., "sdk-a1b2c3d4e5f6"
        """
        return f"sdk-{uuid.uuid4().hex[:12]}"
    def start_session(
        self,
        session_id: Optional[str] = None,
        task: Optional[str] = None,
        agent_name: Optional[str] = None,
        **metadata: Any
    ) -> str:
        """
        Start a new session with optional metadata.
        Args:
            session_id: Optional session identifier (generated if not provided)
            task: Optional task description
            agent_name: Optional agent name
            **metadata: Additional metadata to attach to session
        Returns:
            str: Session identifier
        Raises:
            SessionManagerException: If session creation fails
        Example:
            >>> manager = SessionManager()
            >>> session_id = manager.start_session(
            ... task="Process documents",
            ... agent_name="DocumentAgent",
            ... priority="high"
            ... )
        """
        with self._lock:
            try:
                if session_id is None:
                    session_id = self.generate_session_id()
                # Check if we need to evict oldest session (LRU)
                if len(self.active_sessions) >= self.max_sessions:
                    oldest_id, oldest_session = self.active_sessions.popitem(last=False)
                    logger.debug(f"Evicted oldest session from memory: {oldest_id}")
                    # Persist evicted session if enabled
                    if self.persistence_enabled:
                        try:
                            self.persist_session(oldest_id)
                        except Exception as e:
                            logger.warning(f"Failed to persist evicted session {oldest_id}: {e}")
                # Create session
                session_data = {
                    "session_id": session_id,
                    "task": task,
                    "agent_name": agent_name,
                    "status": "running",
                    "started_at": datetime.now().isoformat(),
                    "created_unix_time": time.time(),
                    **metadata
                }
                self.active_sessions[session_id] = session_data
                self._total_sessions_created += 1
                # Record in history
                self._operation_history.append({
                    'operation': 'start_session',
                    'session_id': session_id,
                    'timestamp': time.time(),
                    'task': task,
                    'agent_name': agent_name
                })
                # Persist if enabled
                if self.persistence_enabled:
                    try:
                        self.persist_session(session_id)
                    except Exception as e:
                        logger.warning(f"Failed to persist new session {session_id}: {e}")
                logger.debug(f"Started session: {session_id}")
                return session_id
            except Exception as e:
                logger.error(f"Failed to start session: {e}")
                raise SessionManagerException(f"Failed to start session: {e}") from e
    def end_session(self, session_id: str, status: str = "completed") -> None:
        """
        End a session with specified status.
        Args:
            session_id: Session identifier
            status: Final status (default: "completed")
        Raises:
            ValueError: If session_id is empty
            SessionNotFoundError: If session is not found
        Example:
            >>> manager = SessionManager()
            >>> session_id = manager.start_session(task="Test")
            >>> manager.end_session(session_id, status="completed")
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        with self._lock:
            if session_id not in self.active_sessions:
                # Try to load from persistence
                if self.persistence_enabled:
                    loaded_session = self.load_persisted_session(session_id)
                    if loaded_session:
                        self.active_sessions[session_id] = loaded_session
                    else:
                        raise SessionNotFoundError(f"Session not found: {session_id}")
                else:
                    raise SessionNotFoundError(f"Session not found: {session_id}")
            self.active_sessions[session_id]["status"] = status
            self.active_sessions[session_id]["ended_at"] = datetime.now().isoformat()
            self.active_sessions[session_id]["ended_unix_time"] = time.time()
            # Calculate duration
            started_at = self.active_sessions[session_id].get("created_unix_time")
            if started_at:
                duration = time.time() - started_at
                self.active_sessions[session_id]["duration_seconds"] = round(duration, 2)
            self._total_sessions_ended += 1
            # Record in history
            self._operation_history.append({
                'operation': 'end_session',
                'session_id': session_id,
                'timestamp': time.time(),
                'status': status
            })
            # Persist updated session
            if self.persistence_enabled:
                try:
                    self.persist_session(session_id)
                except Exception as e:
                    logger.warning(f"Failed to persist ended session {session_id}: {e}")
            logger.debug(f"Ended session {session_id} with status: {status}")
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session metadata.
        Args:
            session_id: Session identifier
        Returns:
            Optional[Dict[str, Any]]: Session data if found, None otherwise
        Example:
            >>> manager = SessionManager()
            >>> session = manager.get_session("sdk-123abc")
            >>> if session:
            ... print(f"Task: {session['task']}")
        """
        if not session_id or not isinstance(session_id, str):
            return None
        with self._lock:
            # Check active sessions first
            if session_id in self.active_sessions:
                # Move to end (LRU)
                self.active_sessions.move_to_end(session_id)
                return dict(self.active_sessions[session_id])
            # Try to load from persistence
            if self.persistence_enabled:
                return self.load_persisted_session(session_id)
            return None
    def list_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        List all active sessions.
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of active sessions
        Example:
            >>> manager = SessionManager()
            >>> active = manager.list_active_sessions()
            >>> print(f"Active sessions: {len(active)}")
        """
        with self._lock:
            return {
                k: dict(v) for k, v in self.active_sessions.items()
                if v.get("status") == "running"
            }
    def persist_session(self, session_id: str) -> Path:
        """
        Persist session to disk.
        Args:
            session_id: Session identifier
        Returns:
            Path: Path to persisted session file
        Raises:
            ValueError: If session_id is empty
            SessionNotFoundError: If session is not found
            SessionManagerException: If persistence fails
        Example:
            >>> manager = SessionManager()
            >>> session_id = manager.start_session(task="Test")
            >>> path = manager.persist_session(session_id)
            >>> print(f"Persisted to {path}")
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        if not self.persistence_enabled:
            raise SessionManagerException("Persistence is not enabled")
        with self._lock:
            if session_id not in self.active_sessions:
                raise SessionNotFoundError(f"Session not found: {session_id}")
            try:
                session_data = self.active_sessions[session_id]
                # Include tags if present
                if session_id in self._session_tags:
                    session_data['tags'] = list(self._session_tags[session_id])
                # Create session file
                session_file = self.persistence_dir / f"session_{session_id}.json"
                json_data = json.dumps(session_data, indent=2, default=str)
                session_file.write_text(json_data, encoding='utf-8')
                logger.debug(f"Persisted session {session_id} to {session_file}")
                return session_file
            except Exception as e:
                logger.error(f"Failed to persist session {session_id}: {e}")
                raise SessionManagerException(f"Failed to persist session: {e}") from e
    def load_persisted_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load persisted session from disk.
        Args:
            session_id: Session identifier
        Returns:
            Optional[Dict[str, Any]]: Session data if found, None otherwise
        Example:
            >>> manager = SessionManager()
            >>> session = manager.load_persisted_session("sdk-123abc")
            >>> if session:
            ... print(f"Loaded session: {session['task']}")
        """
        if not session_id or not isinstance(session_id, str):
            return None
        if not self.persistence_enabled:
            return None
        with self._lock:
            try:
                session_file = self.persistence_dir / f"session_{session_id}.json"
                if not session_file.exists():
                    return None
                json_data = session_file.read_text(encoding='utf-8')
                session_data = json.loads(json_data)
                # Load tags if present
                if 'tags' in session_data:
                    self._session_tags[session_id] = set(session_data['tags'])
                logger.debug(f"Loaded persisted session {session_id}")
                return session_data
            except Exception as e:
                logger.error(f"Failed to load persisted session {session_id}: {e}")
                return None
    def search_sessions(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Search sessions with filter criteria.
        Args:
            filters: Dictionary of filter criteria. Supported filters:
                - status: Filter by session status
                - task: Filter by task (substring match)
                - agent_name: Filter by agent name (substring match)
                - tags: Filter by tags (list of tags, matches any)
                - started_after: Filter by start time (ISO format datetime)
                - started_before: Filter by start time (ISO format datetime)
        Returns:
            List[Dict[str, Any]]: List of matching sessions
        Raises:
            ValueError: If filters is not a dictionary
        Example:
            >>> manager = SessionManager()
            >>> results = manager.search_sessions({
            ... "status": "completed",
            ... "tags": ["important"],
            ... "agent_name": "TestAgent"
            ... })
            >>> for session in results:
            ... print(f"Found: {session['session_id']}")
        """
        if not isinstance(filters, dict):
            raise ValueError("filters must be a dictionary")
        with self._lock:
            results = []
            # Search in active sessions
            for session_id, session_data in self.active_sessions.items():
                if self._matches_filters(session_id, session_data, filters):
                    results.append(dict(session_data))
            # Search in persisted sessions if enabled
            if self.persistence_enabled:
                try:
                    for session_file in self.persistence_dir.glob("session_*.json"):
                        session_id = session_file.stem.replace("session_", "")
                        # Skip if already in active sessions
                        if session_id in self.active_sessions:
                            continue
                        session_data = self.load_persisted_session(session_id)
                        if session_data and self._matches_filters(session_id, session_data, filters):
                            results.append(session_data)
                except Exception as e:
                    logger.warning(f"Error searching persisted sessions: {e}")
            logger.debug(f"Search found {len(results)} sessions matching filters")
            return results
    def get_session_analytics(self) -> Dict[str, Any]:
        """
        Calculate comprehensive session analytics.
        Returns:
            Dict[str, Any]: Analytics dictionary containing:
                - total_sessions_created: Total sessions created since start
                - total_sessions_ended: Total sessions ended
                - total_sessions_archived: Total sessions archived
                - active_sessions_count: Currently active sessions
                - avg_session_duration: Average session duration in seconds
                - sessions_by_status: Count of sessions by status
                - sessions_by_agent: Count of sessions by agent name
                - top_tags: Most used tags with counts
                - uptime_seconds: Time since manager initialization
                - sessions_per_hour: Session creation rate
        Example:
            >>> manager = SessionManager()
            >>> analytics = manager.get_session_analytics()
            >>> print(f"Total sessions: {analytics['total_sessions_created']}")
            >>> print(f"Active: {analytics['active_sessions_count']}")
        """
        with self._lock:
            uptime = time.time() - self._start_time
            # Count sessions by status
            sessions_by_status = {}
            sessions_by_agent = {}
            durations = []
            for session_data in self.active_sessions.values():
                # Count by status
                status = session_data.get('status', 'unknown')
                sessions_by_status[status] = sessions_by_status.get(status, 0) + 1
                # Count by agent
                agent = session_data.get('agent_name', 'unknown')
                sessions_by_agent[agent] = sessions_by_agent.get(agent, 0) + 1
                # Collect durations
                if 'duration_seconds' in session_data:
                    durations.append(session_data['duration_seconds'])
            # Calculate average duration
            avg_duration = sum(durations) / len(durations) if durations else 0
            # Count tags
            tag_counts = {}
            for tags in self._session_tags.values():
                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            # Sort tags by count
            top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            # Calculate session rate
            sessions_per_hour = (self._total_sessions_created / uptime) * 3600 if uptime > 0 else 0
            return {
                'total_sessions_created': self._total_sessions_created,
                'total_sessions_ended': self._total_sessions_ended,
                'total_sessions_archived': self._total_sessions_archived,
                'active_sessions_count': len(self.active_sessions),
                'running_sessions_count': len(self.list_active_sessions()),
                'avg_session_duration': round(avg_duration, 2),
                'sessions_by_status': sessions_by_status,
                'sessions_by_agent': sessions_by_agent,
                'top_tags': [{'tag': tag, 'count': count} for tag, count in top_tags],
                'unique_tags_count': len(tag_counts),
                'uptime_seconds': round(uptime, 2),
                'sessions_per_hour': round(sessions_per_hour, 2),
                'max_sessions': self.max_sessions,
                'persistence_enabled': self.persistence_enabled
            }
    def tag_session(self, session_id: str, tags: List[str]) -> None:
        """
        Add tags to a session for categorization.
        Args:
            session_id: Session identifier
            tags: List of tags to add
        Raises:
            ValueError: If session_id is empty or tags is not a list
            SessionNotFoundError: If session is not found
        Example:
            >>> manager = SessionManager()
            >>> session_id = manager.start_session(task="Test")
            >>> manager.tag_session(session_id, ["important", "testing", "v1.0"])
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        if not isinstance(tags, list):
            raise ValueError("tags must be a list")
        with self._lock:
            # Ensure session exists
            if session_id not in self.active_sessions:
                if self.persistence_enabled:
                    loaded_session = self.load_persisted_session(session_id)
                    if not loaded_session:
                        raise SessionNotFoundError(f"Session not found: {session_id}")
                else:
                    raise SessionNotFoundError(f"Session not found: {session_id}")
            # Initialize tag set if not exists
            if session_id not in self._session_tags:
                self._session_tags[session_id] = set()
            # Add tags
            for tag in tags:
                if tag and isinstance(tag, str):
                    self._session_tags[session_id].add(tag)
            # Record in history
            self._operation_history.append({
                'operation': 'tag_session',
                'session_id': session_id,
                'tags': tags,
                'timestamp': time.time()
            })
            # Persist updated session
            if self.persistence_enabled and session_id in self.active_sessions:
                try:
                    self.persist_session(session_id)
                except Exception as e:
                    logger.warning(f"Failed to persist tagged session {session_id}: {e}")
            logger.debug(f"Tagged session {session_id} with {len(tags)} tags")
    def archive_session(self, session_id: str) -> Path:
        """
        Archive a session to disk and remove from active memory.
        Args:
            session_id: Session identifier
        Returns:
            Path: Path to archived session
        Raises:
            ValueError: If session_id is empty
            SessionNotFoundError: If session is not found
            SessionManagerException: If archive operation fails
        Example:
            >>> manager = SessionManager()
            >>> session_id = manager.start_session(task="Test")
            >>> manager.end_session(session_id)
            >>> archive_path = manager.archive_session(session_id)
            >>> print(f"Archived to {archive_path}")
        """
        if not session_id or not isinstance(session_id, str):
            raise ValueError("session_id must be a non-empty string")
        with self._lock:
            if session_id not in self.active_sessions:
                raise SessionNotFoundError(f"Session not found: {session_id}")
            try:
                # Persist before archiving
                if self.persistence_enabled:
                    persist_path = self.persist_session(session_id)
                else:
                    # Create archive directory if not exists
                    archive_dir = self.persistence_dir / "archived"
                    archive_dir.mkdir(parents=True, exist_ok=True)
                    # Save to archive
                    session_data = self.active_sessions[session_id]
                    if session_id in self._session_tags:
                        session_data['tags'] = list(self._session_tags[session_id])
                    archive_file = archive_dir / f"session_{session_id}.json"
                    json_data = json.dumps(session_data, indent=2, default=str)
                    archive_file.write_text(json_data, encoding='utf-8')
                    persist_path = archive_file
                # Remove from active sessions
                del self.active_sessions[session_id]
                # Clean up tags
                if session_id in self._session_tags:
                    del self._session_tags[session_id]
                self._total_sessions_archived += 1
                # Record in history
                self._operation_history.append({
                    'operation': 'archive_session',
                    'session_id': session_id,
                    'timestamp': time.time()
                })
                logger.debug(f"Archived session {session_id}")
                return persist_path
            except Exception as e:
                logger.error(f"Failed to archive session {session_id}: {e}")
                raise SessionManagerException(f"Failed to archive session: {e}") from e
    def cleanup_sessions(self, older_than_days: int) -> int:
        """
        Clean up sessions older than specified days.
        Args:
            older_than_days: Remove sessions older than this many days
        Returns:
            int: Number of sessions cleaned up
        Raises:
            ValueError: If older_than_days is not positive
        Example:
            >>> manager = SessionManager()
            >>> deleted = manager.cleanup_sessions(older_than_days=30)
            >>> print(f"Cleaned up {deleted} old sessions")
        """
        if older_than_days <= 0:
            raise ValueError(f"older_than_days must be positive, got {older_than_days}")
        with self._lock:
            cutoff_time = datetime.now() - timedelta(days=older_than_days)
            cutoff_unix = cutoff_time.timestamp()
            cleanup_count = 0
            try:
                # Cleanup from active sessions
                sessions_to_remove = []
                for session_id, session_data in self.active_sessions.items():
                    created_time = session_data.get('created_unix_time', 0)
                    if created_time < cutoff_unix:
                        sessions_to_remove.append(session_id)
                for session_id in sessions_to_remove:
                    # Archive before removal if possible
                    try:
                        if self.persistence_enabled:
                            self.persist_session(session_id)
                    except Exception as e:
                        logger.warning(f"Failed to persist session {session_id} during cleanup: {e}")
                    del self.active_sessions[session_id]
                    if session_id in self._session_tags:
                        del self._session_tags[session_id]
                    cleanup_count += 1
                # Cleanup from persisted sessions if enabled
                if self.persistence_enabled:
                    for session_file in self.persistence_dir.glob("session_*.json"):
                        try:
                            stat = session_file.stat()
                            file_mtime = datetime.fromtimestamp(stat.st_mtime)
                            if file_mtime < cutoff_time:
                                session_file.unlink()
                                cleanup_count += 1
                                logger.debug(f"Deleted old session file: {session_file}")
                        except Exception as e:
                            logger.warning(f"Error processing {session_file}: {e}")
                # Record in history
                self._operation_history.append({
                    'operation': 'cleanup_sessions',
                    'older_than_days': older_than_days,
                    'cleanup_count': cleanup_count,
                    'timestamp': time.time()
                })
                logger.info(f"Cleanup completed: removed {cleanup_count} sessions older than {older_than_days} days")
                return cleanup_count
            except Exception as e:
                logger.error(f"Cleanup operation failed: {e}")
                return cleanup_count
    def export_sessions(self, export_format: str = "json", include_archived: bool = False) -> str:
        """
        Export session data in specified format.
        Args:
            export_format: Export format - "json" or "csv"
            include_archived: Include archived sessions (default: False)
        Returns:
            str: Formatted session data
        Raises:
            ValueError: If export_format is not "json" or "csv"
        Example:
            >>> manager = SessionManager()
            >>> json_data = manager.export_sessions(export_format="json")
            >>> csv_data = manager.export_sessions(export_format="csv")
        """
        format_lower = export_format.lower()
        if format_lower not in ("json", "csv"):
            raise ValueError(f"Unsupported export format: {export_format}. Use 'json' or 'csv'.")
        with self._lock:
            analytics = self.get_session_analytics()
            sessions = [dict(s) for s in self.active_sessions.values()]
            # Add tags to sessions
            for session in sessions:
                session_id = session.get('session_id')
                if session_id and session_id in self._session_tags:
                    session['tags'] = list(self._session_tags[session_id])
            export_data = {
                'analytics': analytics,
                'sessions': sessions,
                'export_timestamp': datetime.now().isoformat(),
                'export_unix_time': time.time(),
                'include_archived': include_archived
            }
            if format_lower == "json":
                return json.dumps(export_data, indent=2, default=str)
            else: # csv
                output = StringIO()
                writer = csv.writer(output)
                # Write analytics section
                writer.writerow(['=== Session Manager Analytics ==='])
                writer.writerow(['Metric', 'Value'])
                for key, value in analytics.items():
                    if not isinstance(value, (dict, list)):
                        writer.writerow([key, value])
                writer.writerow([]) # Blank row
                writer.writerow(['=== Sessions ==='])
                # Write sessions section
                if sessions:
                    # Get all possible fields
                    all_fields = set()
                    for session in sessions:
                        all_fields.update(session.keys())
                    headers = sorted(all_fields)
                    writer.writerow(headers)
                    for session in sessions:
                        writer.writerow([str(session.get(h, '')) for h in headers])
                else:
                    writer.writerow(['No sessions available'])
                return output.getvalue()
    def get_summary(self) -> str:
        """
        Get a human-readable summary of session status.
        Returns:
            str: Formatted summary string
        Example:
            >>> manager = SessionManager()
            >>> print(manager.get_summary())
        """
        with self._lock:
            analytics = self.get_session_analytics()
            summary_lines = [
                "=== Session Manager Summary ===",
                f"Total Sessions Created: {analytics['total_sessions_created']}",
                f"Active Sessions: {analytics['active_sessions_count']}",
                f"Running Sessions: {analytics['running_sessions_count']}",
                f"Ended Sessions: {analytics['total_sessions_ended']}",
                f"Archived Sessions: {analytics['total_sessions_archived']}",
                f"Avg Duration: {analytics['avg_session_duration']:.1f}s",
                f"Unique Tags: {analytics['unique_tags_count']}",
                f"Sessions/Hour: {analytics['sessions_per_hour']:.1f}",
                f"Persistence: {'Enabled' if analytics['persistence_enabled'] else 'Disabled'}",
                f"Uptime: {analytics['uptime_seconds']:.0f}s"
            ]
            return "\n".join(summary_lines)
    def _matches_filters(
        self,
        session_id: str,
        session_data: Dict[str, Any],
        filters: Dict[str, Any]
    ) -> bool:
        """
        Check if session matches filter criteria.
        Args:
            session_id: Session identifier
            session_data: Session data dictionary
            filters: Filter criteria
        Returns:
            bool: True if session matches all filters
        """
        # Filter by status
        if 'status' in filters:
            if session_data.get('status') != filters['status']:
                return False
        # Filter by task (substring match)
        if 'task' in filters:
            task = session_data.get('task', '')
            if not task or filters['task'].lower() not in task.lower():
                return False
        # Filter by agent_name (substring match)
        if 'agent_name' in filters:
            agent = session_data.get('agent_name', '')
            if not agent or filters['agent_name'].lower() not in agent.lower():
                return False
        # Filter by tags (matches any)
        if 'tags' in filters:
            session_tags = self._session_tags.get(session_id, set())
            filter_tags = set(filters['tags'])
            if not filter_tags.intersection(session_tags):
                return False
        # Filter by started_after
        if 'started_after' in filters:
            try:
                started_at = session_data.get('started_at')
                if not started_at:
                    return False
                started_dt = datetime.fromisoformat(started_at)
                filter_dt = datetime.fromisoformat(filters['started_after'])
                if started_dt < filter_dt:
                    return False
            except (ValueError, TypeError):
                return False
        # Filter by started_before
        if 'started_before' in filters:
            try:
                started_at = session_data.get('started_at')
                if not started_at:
                    return False
                started_dt = datetime.fromisoformat(started_at)
                filter_dt = datetime.fromisoformat(filters['started_before'])
                if started_dt > filter_dt:
                    return False
            except (ValueError, TypeError):
                return False
        return True
    def __repr__(self) -> str:
        """Return string representation of SessionManager."""
        return (
            f"SessionManager(active={len(self.active_sessions)}, "
            f"total_created={self._total_sessions_created}, "
            f"persistence={self.persistence_enabled})"
        )
