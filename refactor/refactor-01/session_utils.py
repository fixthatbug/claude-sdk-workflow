#!/usr/bin/env python3
"""
Session utilities for Claude Agent SDK.

Consolidated from duplicate SessionUtilities classes in sdk_workflow_enhancements.py.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class SessionUtilities:
    """Session management utilities for workflow orchestration.

    Provides:
    - Unique session ID generation with timestamps
    - Checkpoint save/load for session persistence
    - Progress tracking utilities
    """

    @staticmethod
    def generate_session_id(prefix: str = "session") -> str:
        """Generate unique session ID with timestamp and UUID.

        Args:
            prefix: Session ID prefix

        Returns:
            Unique session ID: prefix-YYYYMMDD-HHMMSS-uuid[:8]
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        short_id = str(uuid.uuid4())[:8]
        return f"{prefix}-{timestamp}-{short_id}"

    @staticmethod
    def save_checkpoint(
        checkpoint_dir: str,
        session_id: str,
        state: Dict[str, Any]
    ) -> str:
        """Save session checkpoint to disk.

        Args:
            checkpoint_dir: Directory for checkpoint files
            session_id: Unique session identifier
            state: Session state dictionary

        Returns:
            Path to saved checkpoint file
        """
        Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
        checkpoint_path = Path(checkpoint_dir) / f"{session_id}.json"

        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)

        return str(checkpoint_path)

    @staticmethod
    def load_checkpoint(checkpoint_path: str) -> Dict[str, Any]:
        """Load session checkpoint from disk.

        Args:
            checkpoint_path: Path to checkpoint file

        Returns:
            Session state dictionary

        Raises:
            FileNotFoundError: If checkpoint doesn't exist
            json.JSONDecodeError: If checkpoint is invalid
        """
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def track_progress(current: int, total: int) -> Dict[str, Any]:
        """Track execution progress.

        Args:
            current: Current item number
            total: Total items

        Returns:
            Progress tracking dict with percentage
        """
        return {
            "current": current,
            "total": total,
            "percentage": round((current / total * 100), 1) if total > 0 else 0,
            "remaining": total - current,
            "completed": current >= total,
        }

    @staticmethod
    def get_checkpoint_path(checkpoint_dir: str, session_id: str) -> Path:
        """Get the checkpoint file path for a session.

        Args:
            checkpoint_dir: Base directory for checkpoints
            session_id: Session identifier

        Returns:
            Path object for checkpoint file
        """
        return Path(checkpoint_dir) / f"{session_id}.json"

    @staticmethod
    def checkpoint_exists(checkpoint_dir: str, session_id: str) -> bool:
        """Check if a checkpoint exists for a session.

        Args:
            checkpoint_dir: Base directory for checkpoints
            session_id: Session identifier

        Returns:
            True if checkpoint exists
        """
        return SessionUtilities.get_checkpoint_path(checkpoint_dir, session_id).exists()

    @staticmethod
    def list_checkpoints(checkpoint_dir: str) -> list[str]:
        """List all checkpoint session IDs in a directory.

        Args:
            checkpoint_dir: Directory to scan

        Returns:
            List of session IDs with checkpoints
        """
        path = Path(checkpoint_dir)
        if not path.exists():
            return []
        return [f.stem for f in path.glob("*.json")]

    @staticmethod
    def delete_checkpoint(checkpoint_dir: str, session_id: str) -> bool:
        """Delete a checkpoint file.

        Args:
            checkpoint_dir: Base directory for checkpoints
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        path = SessionUtilities.get_checkpoint_path(checkpoint_dir, session_id)
        if path.exists():
            path.unlink()
            return True
        return False
