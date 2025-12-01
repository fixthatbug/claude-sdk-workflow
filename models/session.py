"""Orchestrated session models with checkpoint and resume capabilities.
Extends the base SessionState with orchestration-specific features including
phase execution tracking, named checkpoints, and structured phase results.
"""
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from sdk_workflow.core.types import (
    SessionState,
    SessionStatus,
    ExecutionMode,
    TokenUsage,
    CostBreakdown,
    Message,
)
from sdk_workflow.core.config import Config, get_config
@dataclass
class PhaseResult:
    """Result from executing a workflow phase.
    Captures the outcome, metrics, and artifacts from a single phase
    of orchestrated execution (e.g., planning, implementation, review).
    """
    phase_name: str
    status: str # "success", "failed", "partial"
    started_at: str
    completed_at: str
    duration_ms: float
    output: Any # Phase-specific output (plan, code changes, test results, etc.)
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost: CostBreakdown = field(default_factory=CostBreakdown)
    messages: List[Message] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list) # File paths created/modified
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    @property
    def success(self) -> bool:
        """Check if phase completed successfully."""
        return self.status == "success"
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        data = asdict(self)
        # Convert Message objects to dicts
        data["messages"] = [
            m.to_dict() if hasattr(m, "to_dict") else m
            for m in self.messages
        ]
        return data
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhaseResult":
        """Deserialize from dictionary."""
        # Convert dicts back to Message objects
        messages_data = data.get("messages", [])
        messages = [
            Message(role=m["role"], content=m["content"])
            if isinstance(m, dict)
            else m
            for m in messages_data
        ]
        # Convert usage dict to TokenUsage
        usage_data = data.get("usage", {})
        if isinstance(usage_data, dict):
            usage = TokenUsage(**usage_data)
        else:
            usage = usage_data
        # Convert cost dict to CostBreakdown
        cost_data = data.get("cost", {})
        if isinstance(cost_data, dict):
            cost = CostBreakdown(**cost_data)
        else:
            cost = cost_data
        return cls(
            phase_name=data["phase_name"],
            status=data["status"],
            started_at=data["started_at"],
            completed_at=data["completed_at"],
            duration_ms=data["duration_ms"],
            output=data.get("output"),
            usage=usage,
            cost=cost,
            messages=messages,
            artifacts=data.get("artifacts", []),
            errors=data.get("errors", []),
            metadata=data.get("metadata", {}),
        )
class OrchestratedSession(SessionState):
    """Extended session for orchestrated multi-phase workflows.
    Adds orchestration-specific features:
    - Phase execution tracking with results
    - Named checkpoints for recovery points
    - Enhanced persistence with phase history
    - Config injection for model/budget management
    Usage:
        # Create new session
        session = OrchestratedSession.create(
            mode=ExecutionMode.ORCHESTRATOR,
            task="Implement user dashboard",
            config=get_config()
        )
        # Execute phases and track results
        planning_result = execute_planning_phase()
        session.add_phase_result(planning_result)
        session.create_checkpoint("post-planning")
        # Save session state
        session.save()
        # Later: Resume from checkpoint
        resumed = OrchestratedSession.load(session.session_id)
        resumed.resume_from_checkpoint("post-planning")
    """
    def __init__(
        self,
        session_id: str = None,
        workflow_id: Optional[str] = None,
        status: SessionStatus = SessionStatus.CREATED,
        mode: ExecutionMode = ExecutionMode.ORCHESTRATOR,
        model: str = "sonnet",
        system_prompt: str = "",
        messages: List[Message] = None,
        total_usage: TokenUsage = None,
        total_cost: CostBreakdown = None,
        created_at: datetime = None,
        updated_at: datetime = None,
        metadata: Dict[str, Any] = None,
        config: Optional[Config] = None,
    ):
        """Initialize orchestrated session.
        Args:
            session_id: Unique session identifier. Auto-generated if None.
            workflow_id: Optional workflow group identifier.
            status: Initial session status.
            mode: Execution mode.
            model: Model to use (alias or full ID).
            system_prompt: System prompt for the session.
            messages: Initial messages.
            total_usage: Initial token usage.
            total_cost: Initial cost breakdown.
            created_at: Creation timestamp.
            updated_at: Last update timestamp.
            metadata: Additional metadata.
            config: Config instance for settings injection.
        """
        super().__init__(
            session_id=session_id or f"orch_{uuid.uuid4().hex[:12]}",
            workflow_id=workflow_id,
            status=status,
            mode=mode,
            model=model,
            system_prompt=system_prompt,
            messages=messages or [],
            total_usage=total_usage or TokenUsage(),
            total_cost=total_cost or CostBreakdown(),
            created_at=created_at or datetime.now(),
            updated_at=updated_at or datetime.now(),
            metadata=metadata or {},
        )
        # Orchestration-specific attributes
        self.config = config or get_config()
        self.phase_results: List[PhaseResult] = []
        self.named_checkpoints: Dict[str, Dict[str, Any]] = {}
        self.current_phase: Optional[str] = None
    @classmethod
    def create(
        cls,
        mode: ExecutionMode = ExecutionMode.ORCHESTRATOR,
        task: str = "",
        model: str = "sonnet",
        system_prompt: str = "",
        workflow_id: Optional[str] = None,
        config: Optional[Config] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "OrchestratedSession":
        """Factory method to create a new orchestrated session.
        Args:
            mode: Execution mode.
            task: Task description.
            model: Model to use.
            system_prompt: System prompt.
            workflow_id: Optional workflow group ID.
            config: Config instance.
            metadata: Additional metadata.
        Returns:
            New OrchestratedSession instance.
        """
        session_metadata = metadata or {}
        session_metadata["task"] = task
        session = cls(
            mode=mode,
            model=model,
            system_prompt=system_prompt,
            workflow_id=workflow_id,
            metadata=session_metadata,
            config=config,
        )
        # Add initial user message with task
        if task:
            session.add_message("user", task)
        return session
    def add_phase_result(self, result: PhaseResult) -> None:
        """Add a completed phase result to history.
        Args:
            result: PhaseResult from completed phase.
        """
        self.phase_results.append(result)
        # Accumulate usage and cost
        self.total_usage.input_tokens += result.usage.input_tokens
        self.total_usage.output_tokens += result.usage.output_tokens
        self.total_usage.cache_read_tokens += result.usage.cache_read_tokens
        self.total_usage.cache_write_tokens += result.usage.cache_write_tokens
        self.total_cost.input_cost += result.cost.input_cost
        self.total_cost.output_cost += result.cost.output_cost
        self.total_cost.cache_read_cost += result.cost.cache_read_cost
        self.total_cost.cache_write_cost += result.cost.cache_write_cost
        # Extend messages
        self.messages.extend(result.messages)
        # Update metadata
        self.updated_at = datetime.now()
        self.current_phase = None
    def create_checkpoint(
        self,
        name: str,
        description: str = "",
        include_phase_results: bool = True,
    ) -> str:
        """Create a named checkpoint for session recovery.
        Args:
            name: Checkpoint name (e.g., "post-planning", "pre-testing").
            description: Optional checkpoint description.
            include_phase_results: Whether to include phase results in checkpoint.
        Returns:
            Checkpoint identifier (name).
        """
        checkpoint_data = {
            "name": name,
            "description": description,
            "timestamp": datetime.now().isoformat(),
            "status": self.status.value,
            "current_phase": self.current_phase,
            "messages": [m.to_dict() for m in self.messages],
            "total_usage": asdict(self.total_usage),
            "total_cost": asdict(self.total_cost),
            "metadata": self.metadata.copy(),
        }
        if include_phase_results:
            checkpoint_data["phase_results"] = [
                r.to_dict() for r in self.phase_results
            ]
        self.named_checkpoints[name] = checkpoint_data
        self.status = SessionStatus.CHECKPOINTED
        self.updated_at = datetime.now()
        return name
    def resume_from_checkpoint(self, name: str) -> bool:
        """Resume session from a named checkpoint.
        Args:
            name: Checkpoint name to resume from.
        Returns:
            True if successfully resumed, False if checkpoint not found.
        """
        if name not in self.named_checkpoints:
            return False
        checkpoint = self.named_checkpoints[name]
        # Restore session state from checkpoint
        self.status = SessionStatus(checkpoint["status"])
        self.current_phase = checkpoint.get("current_phase")
        # Restore messages
        self.messages = [
            Message(role=m["role"], content=m["content"])
            for m in checkpoint["messages"]
        ]
        # Restore usage
        usage_data = checkpoint["total_usage"]
        self.total_usage = TokenUsage(**usage_data)
        # Restore cost
        cost_data = checkpoint["total_cost"]
        self.total_cost = CostBreakdown(**cost_data)
        # Restore metadata
        self.metadata = checkpoint["metadata"].copy()
        # Restore phase results if present
        if "phase_results" in checkpoint:
            self.phase_results = [
                PhaseResult.from_dict(r) for r in checkpoint["phase_results"]
            ]
        self.updated_at = datetime.now()
        return True
    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all named checkpoints with metadata.
        Returns:
            List of checkpoint info dicts.
        """
        return [
            {
                "name": name,
                "description": cp.get("description", ""),
                "timestamp": cp["timestamp"],
                "phase": cp.get("current_phase"),
            }
            for name, cp in self.named_checkpoints.items()
        ]
    def get_latest_phase_result(self, phase_name: Optional[str] = None) -> Optional[PhaseResult]:
        """Get the most recent phase result.
        Args:
            phase_name: Optional phase name filter.
        Returns:
            Latest PhaseResult or None if no results exist.
        """
        if not self.phase_results:
            return None
        if phase_name:
            filtered = [r for r in self.phase_results if r.phase_name == phase_name]
            return filtered[-1] if filtered else None
        return self.phase_results[-1]
    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dictionary.
        Returns:
            Dictionary representation including orchestration data.
        """
        # Get base session data
        data = super().to_dict()
        # Add orchestration-specific data
        data.update(
            {
                "phase_results": [r.to_dict() for r in self.phase_results],
                "named_checkpoints": self.named_checkpoints,
                "current_phase": self.current_phase,
            }
        )
        return data
    @classmethod
    def from_dict(cls, data: Dict[str, Any], config: Optional[Config] = None) -> "OrchestratedSession":
        """Deserialize session from dictionary.
        Args:
            data: Dictionary representation.
            config: Optional Config instance.
        Returns:
            OrchestratedSession instance.
        """
        # Create base session
        session = cls(
            session_id=data["session_id"],
            workflow_id=data.get("workflow_id"),
            status=SessionStatus(data["status"]),
            mode=ExecutionMode(data["mode"]),
            model=data["model"],
            system_prompt=data["system_prompt"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
            config=config,
        )
        # Restore messages
        session.messages = [
            Message(role=m["role"], content=m["content"])
            for m in data.get("messages", [])
        ]
        # Restore usage
        usage_data = data.get("total_usage", {})
        session.total_usage = TokenUsage(**usage_data)
        # Restore cost
        cost_data = data.get("total_cost", {})
        session.total_cost = CostBreakdown(**cost_data)
        # Restore orchestration data
        session.phase_results = [
            PhaseResult.from_dict(r) for r in data.get("phase_results", [])
        ]
        session.named_checkpoints = data.get("named_checkpoints", {})
        session.current_phase = data.get("current_phase")
        return session
    def save(self, storage_dir: Optional[Path] = None) -> Path:
        """Save session to disk.
        Args:
            storage_dir: Directory to save session. Defaults to
                        ~/.claude/sdk-workflow/sessions/orchestrated/
        Returns:
            Path to saved session file.
        """
        if storage_dir is None:
            storage_dir = (
                Path.home() / ".claude" / "sdk-workflow" / "sessions" / "orchestrated"
            )
        storage_dir.mkdir(parents=True, exist_ok=True)
        file_path = storage_dir / f"{self.session_id}.json"
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)
        return file_path
    @classmethod
    def load(
        cls, session_id: str, storage_dir: Optional[Path] = None, config: Optional[Config] = None
    ) -> Optional["OrchestratedSession"]:
        """Load session from disk.
        Args:
            session_id: Session identifier.
            storage_dir: Directory containing session files. Defaults to
                        ~/.claude/sdk-workflow/sessions/orchestrated/
            config: Optional Config instance.
        Returns:
            OrchestratedSession instance or None if not found.
        """
        if storage_dir is None:
            storage_dir = (
                Path.home() / ".claude" / "sdk-workflow" / "sessions" / "orchestrated"
            )
        file_path = storage_dir / f"{session_id}.json"
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            return cls.from_dict(data, config=config)
        except (json.JSONDecodeError, KeyError):
            return None
