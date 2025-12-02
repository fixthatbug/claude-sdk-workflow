#!/usr/bin/env python3
"""Checkpoint persistence for session resume capability."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class CheckpointManager:
    """Manages checkpoint persistence for resuming sessions."""

    def __init__(self, output_dir: Optional[Path] = None):
        if output_dir is None:
            output_dir = Path.cwd() / ".claude" / "outputs"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(
        self,
        session_id: str,
        turn: int,
        total_input_tokens: int,
        total_output_tokens: int,
        context_used_pct: float,
        result: Optional[Any] = None,
        **extra_data: Any
    ) -> Path:
        checkpoint = {
            "session_id": session_id,
            "turn": turn,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "context_used_pct": context_used_pct,
            "timestamp": datetime.now().isoformat(),
            **extra_data
        }

        if result is not None:
            checkpoint["result"] = result.to_dict() if hasattr(result, "to_dict") else str(result)

        checkpoint_path = self.output_dir / f"checkpoint_{session_id}.json"
        checkpoint_path.write_text(json.dumps(checkpoint, indent=2, default=str), encoding="utf-8")
        return checkpoint_path

    def load_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        checkpoint_path = self.output_dir / f"checkpoint_{session_id}.json"
        if not checkpoint_path.exists():
            return None
        try:
            return json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def checkpoint_exists(self, session_id: str) -> bool:
        return (self.output_dir / f"checkpoint_{session_id}.json").exists()

    def delete_checkpoint(self, session_id: str) -> bool:
        checkpoint_path = self.output_dir / f"checkpoint_{session_id}.json"
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            return True
        return False

    def list_checkpoints(self) -> List[Tuple[str, Path, str]]:
        checkpoints = []
        for cp in self.output_dir.glob("checkpoint_*.json"):
            try:
                data = json.loads(cp.read_text(encoding="utf-8"))
                checkpoints.append((data.get("session_id", "unknown"), cp, data.get("timestamp", "")))
            except Exception:
                continue
        checkpoints.sort(key=lambda x: x[2], reverse=True)
        return checkpoints

    def get_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        checkpoints = self.list_checkpoints()
        if not checkpoints:
            return None
        try:
            return json.loads(checkpoints[0][1].read_text(encoding="utf-8"))
        except Exception:
            return None

    def cleanup_old_checkpoints(self, keep_recent: int = 10) -> int:
        checkpoints = self.list_checkpoints()
        if len(checkpoints) <= keep_recent:
            return 0
        deleted = 0
        for _, cp, _ in checkpoints[keep_recent:]:
            try:
                cp.unlink()
                deleted += 1
            except Exception:
                continue
        return deleted
