"""Progress Monitoring - Real-time execution progress tracking."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProgressUpdate:
    """A progress update event."""
    phase: str
    step: int
    total_steps: int
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def percentage(self) -> float:
        return (self.step / self.total_steps * 100) if self.total_steps > 0 else 0


class ProgressMonitor:
    """Monitor and report execution progress."""
    
    def __init__(self, callback: Optional[Callable[[ProgressUpdate], None]] = None):
        self._callback = callback
        self._updates: List[ProgressUpdate] = []
        self._current_phase: Optional[str] = None
        self._phases: Dict[str, Dict] = {}
        self._start_time: Optional[datetime] = None
    
    def start(self, phases: Optional[List[str]] = None) -> None:
        """Start progress monitoring."""
        self._start_time = datetime.now()
        self._updates.clear()
        
        if phases:
            for i, phase in enumerate(phases):
                self._phases[phase] = {
                    "index": i,
                    "total": len(phases),
                    "started": False,
                    "completed": False
                }
    
    def begin_phase(self, phase: str, total_steps: int = 1) -> None:
        """Begin a new phase."""
        self._current_phase = phase
        if phase in self._phases:
            self._phases[phase]["started"] = True
            self._phases[phase]["total_steps"] = total_steps
        
        self._emit(ProgressUpdate(
            phase=phase,
            step=0,
            total_steps=total_steps,
            message=f"Starting {phase}"
        ))
    
    def update(self, step: int, message: str, **metadata) -> None:
        """Update current phase progress."""
        if not self._current_phase:
            return
        
        total = self._phases.get(self._current_phase, {}).get("total_steps", 1)
        self._emit(ProgressUpdate(
            phase=self._current_phase,
            step=step,
            total_steps=total,
            message=message,
            metadata=metadata
        ))
    
    def complete_phase(self, phase: Optional[str] = None) -> None:
        """Mark a phase as completed."""
        phase = phase or self._current_phase
        if phase and phase in self._phases:
            self._phases[phase]["completed"] = True
        
        total = self._phases.get(phase, {}).get("total_steps", 1)
        self._emit(ProgressUpdate(
            phase=phase or "unknown",
            step=total,
            total_steps=total,
            message=f"Completed {phase}"
        ))
    
    def _emit(self, update: ProgressUpdate) -> None:
        """Emit a progress update."""
        self._updates.append(update)
        if self._callback:
            try:
                self._callback(update)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
    
    def get_overall_progress(self) -> float:
        """Get overall progress as percentage."""
        if not self._phases:
            return 0
        
        completed = sum(1 for p in self._phases.values() if p["completed"])
        return (completed / len(self._phases)) * 100
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        if not self._start_time:
            return 0
        return (datetime.now() - self._start_time).total_seconds()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get progress summary."""
        return {
            "elapsed_seconds": self.get_elapsed_time(),
            "overall_progress": self.get_overall_progress(),
            "phases_completed": sum(1 for p in self._phases.values() if p["completed"]),
            "total_phases": len(self._phases),
            "current_phase": self._current_phase,
            "updates_count": len(self._updates),
        }


__all__ = ['ProgressUpdate', 'ProgressMonitor']
