"""Session-based output directory management for SDK workflow orchestrator.
Provides structured output management with session isolation and phase-based
organization. Supports metadata tracking and manifest generation.
"""
import json
import shutil
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
@dataclass
class SessionManifest:
    """Metadata manifest for a session's outputs."""
    session_id: str
    created_at: str
    updated_at: str
    phases: List[str] = field(default_factory=list)
    files: Dict[str, List[str]] = field(default_factory=dict) # phase -> file paths
    metadata: Dict[str, Any] = field(default_factory=dict)
    total_files: int = 0
    total_size_bytes: int = 0
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionManifest":
        """Create instance from dictionary."""
        return cls(**data)
class OutputManager:
    """Manages session-based output directories with phase organization.
    Directory structure:
        outputs/
            {session_id}/
                manifest.json
                {phase_1}/
                    output_1.json
                    output_2.txt
                {phase_2}/
                    output_3.json
                ...
    Usage:
        # Create manager with default or custom output directory
        manager = OutputManager()
        # Create session directory
        session_dir = manager.create_session_dir("sess_abc123")
        # Write phase output
        manager.write_phase_output(
            session_id="sess_abc123",
            phase="planning",
            filename="plan.json",
            content={"tasks": [...]}
        )
        # Read phase output
        data = manager.read_phase_output(
            session_id="sess_abc123",
            phase="planning",
            filename="plan.json"
        )
        # Get session manifest
        manifest = manager.get_manifest("sess_abc123")
    """
    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize output manager.
        Args:
            base_dir: Base directory for outputs. Defaults to
                     ~/.claude/sdk-workflow/outputs/
        """
        self.base_dir = base_dir or Path.home() / ".claude" / "sdk-workflow" / "outputs"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
    def _get_session_dir(self, session_id: str) -> Path:
        """Get path to session output directory."""
        return self.base_dir / session_id
    def _get_phase_dir(self, session_id: str, phase: str) -> Path:
        """Get path to phase directory within session."""
        return self._get_session_dir(session_id) / phase
    def _get_manifest_path(self, session_id: str) -> Path:
        """Get path to session manifest file."""
        return self._get_session_dir(session_id) / "manifest.json"
    def create_session_dir(self, session_id: str, metadata: Optional[Dict[str, Any]] = None) -> Path:
        """Create output directory for a new session.
        Args:
            session_id: Unique session identifier.
            metadata: Optional metadata to store in manifest.
        Returns:
            Path to created session directory.
        """
        session_dir = self._get_session_dir(session_id)
        with self._lock:
            session_dir.mkdir(parents=True, exist_ok=True)
            # Create initial manifest
            now = datetime.now().isoformat()
            manifest = SessionManifest(
                session_id=session_id,
                created_at=now,
                updated_at=now,
                metadata=metadata or {}
            )
            # Write manifest
            manifest_path = self._get_manifest_path(session_id)
            with open(manifest_path, 'w') as f:
                json.dump(manifest.to_dict(), f, indent=2)
        return session_dir
    def write_phase_output(
        self,
        session_id: str,
        phase: str,
        filename: str,
        content: Any,
        is_json: bool = True
    ) -> Path:
        """Write output file for a specific phase.
        Args:
            session_id: Session identifier.
            phase: Phase name (e.g., "planning", "implementation").
            filename: Name of output file.
            content: Content to write (dict/list for JSON, str for text).
            is_json: If True, serialize content as JSON.
        Returns:
            Path to written file.
        """
        phase_dir = self._get_phase_dir(session_id, phase)
        with self._lock:
            # Create phase directory if needed
            phase_dir.mkdir(parents=True, exist_ok=True)
            # Write content
            output_path = phase_dir / filename
            if is_json:
                with open(output_path, 'w') as f:
                    json.dump(content, f, indent=2, default=str)
            else:
                with open(output_path, 'w') as f:
                    f.write(str(content))
            # Update manifest
            self._update_manifest(session_id, phase, filename, output_path)
        return output_path
    def read_phase_output(
        self,
        session_id: str,
        phase: str,
        filename: str,
        is_json: bool = True
    ) -> Optional[Any]:
        """Read output file from a specific phase.
        Args:
            session_id: Session identifier.
            phase: Phase name.
            filename: Name of file to read.
            is_json: If True, parse as JSON.
        Returns:
            File content (parsed JSON or text), or None if not found.
        """
        output_path = self._get_phase_dir(session_id, phase) / filename
        if not output_path.exists():
            return None
        try:
            if is_json:
                with open(output_path, 'r') as f:
                    return json.load(f)
            else:
                with open(output_path, 'r') as f:
                    return f.read()
        except (json.JSONDecodeError, IOError):
            return None
    def list_phase_outputs(self, session_id: str, phase: str) -> List[Path]:
        """List all output files in a phase directory.
        Args:
            session_id: Session identifier.
            phase: Phase name.
        Returns:
            List of file paths in the phase directory.
        """
        phase_dir = self._get_phase_dir(session_id, phase)
        if not phase_dir.exists():
            return []
        return [f for f in phase_dir.iterdir() if f.is_file()]
    def get_manifest(self, session_id: str) -> Optional[SessionManifest]:
        """Get session manifest with metadata.
        Args:
            session_id: Session identifier.
        Returns:
            SessionManifest object or None if not found.
        """
        manifest_path = self._get_manifest_path(session_id)
        if not manifest_path.exists():
            return None
        try:
            with open(manifest_path, 'r') as f:
                data = json.load(f)
            return SessionManifest.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None
    def _update_manifest(self, session_id: str, phase: str, filename: str, file_path: Path) -> None:
        """Update manifest with new file information.
        Args:
            session_id: Session identifier.
            phase: Phase name.
            filename: File name.
            file_path: Full path to file.
        """
        manifest = self.get_manifest(session_id)
        if manifest is None:
            # Create new manifest if it doesn't exist
            manifest = SessionManifest(
                session_id=session_id,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
        # Add phase if new
        if phase not in manifest.phases:
            manifest.phases.append(phase)
        # Add file to phase
        if phase not in manifest.files:
            manifest.files[phase] = []
        # Use relative path from session directory
        session_dir = self._get_session_dir(session_id)
        relative_path = str(file_path.relative_to(session_dir))
        if relative_path not in manifest.files[phase]:
            manifest.files[phase].append(relative_path)
        # Update metadata
        manifest.updated_at = datetime.now().isoformat()
        manifest.total_files = sum(len(files) for files in manifest.files.values())
        # Calculate total size
        total_size = 0
        for phase_files in manifest.files.values():
            for rel_path in phase_files:
                full_path = session_dir / rel_path
                if full_path.exists():
                    total_size += full_path.stat().st_size
        manifest.total_size_bytes = total_size
        # Write updated manifest
        manifest_path = self._get_manifest_path(session_id)
        with open(manifest_path, 'w') as f:
            json.dump(manifest.to_dict(), f, indent=2)
    def delete_session(self, session_id: str) -> bool:
        """Delete entire session directory.
        Args:
            session_id: Session identifier.
        Returns:
            True if deleted, False if not found.
        """
        session_dir = self._get_session_dir(session_id)
        if not session_dir.exists():
            return False
        with self._lock:
            shutil.rmtree(session_dir)
        return True
    def list_sessions(self) -> List[str]:
        """List all session IDs with output directories.
        Returns:
            List of session IDs.
        """
        if not self.base_dir.exists():
            return []
        return [d.name for d in self.base_dir.iterdir() if d.is_dir()]
    def cleanup_old_sessions(self, days: int = 7) -> int:
        """Remove session directories older than specified days.
        Args:
            days: Age threshold in days.
        Returns:
            Number of sessions removed.
        """
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0
        for session_id in self.list_sessions():
            manifest = self.get_manifest(session_id)
            if manifest is None:
                continue
            try:
                updated = datetime.fromisoformat(manifest.updated_at)
                if updated < cutoff:
                    if self.delete_session(session_id):
                        removed += 1
            except ValueError:
                continue
        return removed
