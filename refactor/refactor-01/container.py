"""Container Management - Code execution container lifecycle."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ContainerState(Enum):
    """Container lifecycle states."""
    CREATING = "creating"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    EXPIRED = "expired"


@dataclass
class ContainerConfig:
    """Container configuration."""
    memory_gib: float = 5.0
    cpu_cores: int = 2
    timeout_hours: float = 1.0
    max_lifetime_days: int = 30
    free_hours_daily: float = 50.0


@dataclass
class Container:
    """A code execution container instance."""
    container_id: str
    created_at: datetime = field(default_factory=datetime.now)
    state: ContainerState = ContainerState.CREATING
    config: ContainerConfig = field(default_factory=ContainerConfig)
    hours_used: float = 0.0
    last_active: datetime = field(default_factory=datetime.now)
    
    @property
    def is_expired(self) -> bool:
        age = datetime.now() - self.created_at
        return age > timedelta(days=self.config.max_lifetime_days)


class ContainerManager:
    """Manage code execution containers."""
    
    HOURLY_RATE_USD = 0.03  # After free tier
    
    def __init__(self, config: Optional[ContainerConfig] = None):
        self.config = config or ContainerConfig()
        self._containers: Dict[str, Container] = {}
        self._daily_usage: float = 0.0
        self._last_reset: datetime = datetime.now()
    
    def create_container(self, container_id: Optional[str] = None) -> Container:
        """Create a new container."""
        import uuid
        cid = container_id or str(uuid.uuid4())[:12]
        
        container = Container(
            container_id=cid,
            config=self.config,
            state=ContainerState.RUNNING
        )
        self._containers[cid] = container
        return container
    
    def get_container(self, container_id: str) -> Optional[Container]:
        """Get container by ID."""
        return self._containers.get(container_id)
    
    def record_usage(self, container_id: str, hours: float) -> float:
        """Record usage hours. Returns cost incurred."""
        container = self._containers.get(container_id)
        if not container:
            return 0.0
        
        container.hours_used += hours
        container.last_active = datetime.now()
        
        # Reset daily usage if new day
        if datetime.now().date() > self._last_reset.date():
            self._daily_usage = 0.0
            self._last_reset = datetime.now()
        
        self._daily_usage += hours
        return self.calculate_cost(hours)
    
    def calculate_cost(self, hours: float) -> float:
        """Calculate cost for hours, considering free tier."""
        free_remaining = max(0, self.config.free_hours_daily - self._daily_usage)
        billable = max(0, hours - free_remaining)
        return billable * self.HOURLY_RATE_USD
    
    def stop_container(self, container_id: str) -> bool:
        """Stop a container."""
        container = self._containers.get(container_id)
        if container:
            container.state = ContainerState.STOPPED
            return True
        return False
    
    def cleanup_expired(self) -> int:
        """Remove expired containers. Returns count removed."""
        expired = [cid for cid, c in self._containers.items() if c.is_expired]
        for cid in expired:
            del self._containers[cid]
        return len(expired)
    
    def get_usage_summary(self) -> Dict[str, Any]:
        """Get usage summary."""
        return {
            "active_containers": sum(1 for c in self._containers.values() 
                                    if c.state == ContainerState.RUNNING),
            "total_containers": len(self._containers),
            "daily_hours_used": self._daily_usage,
            "free_hours_remaining": max(0, self.config.free_hours_daily - self._daily_usage),
            "total_hours_used": sum(c.hours_used for c in self._containers.values()),
        }


__all__ = [
    'ContainerState',
    'ContainerConfig',
    'Container',
    'ContainerManager',
]
