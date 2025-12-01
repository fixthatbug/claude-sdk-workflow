"""
DEPRECATED: This module is deprecated and will be removed in a future version.
Use OrchestratorExecutor from sdk_workflow.executors.orchestrator instead.
OrchestratorExecutor provides better streaming support, real-time feedback,
and improved subagent delegation capabilities.
Migration Guide:
- Replace OneshotOrchestrator with OrchestratorExecutor
- Use streaming execution instead of batch oneshot
- Leverage real-time progress tracking and callbacks
- Use the enhanced phase prompts from config.presets
- Utilize agent_prompts for specialized subagent roles
Legacy Documentation (DEPRECATED):
Oneshot Orchestrator - Batch execution with checkpoint-based resume.
Extends BaseExecutor to provide orchestrated multi-phase execution with:
- Checkpoint after each phase for resume capability
- Silent subagent delegation using phase presets
- State persistence for workflow resumption
- Batch execution optimized for cost-effectiveness
- Comprehensive error recovery
"""
import warnings
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass, field
from .base import BaseExecutor
from config.presets import PhaseType, get_phase_prompt
from core.config import Config
from core.types import (
    ExecutionResult,
    ExecutionMode,
    SessionState,
    SessionStatus,
    TokenUsage,
    CostBreakdown,
    Checkpoint,
    Message,
)
from claude_agent_sdk import (
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)
logger = logging.getLogger(__name__)
@dataclass
class OrchestratedSession:
    """
    Session state for orchestrated workflow with checkpointing.
    Extends SessionState with orchestration-specific features:
    - Phase tracking
    - Checkpoint management
    - Resume capability
    """
    session_id: str
    task: str
    phases: List[PhaseType]
    current_phase_index: int = 0
    phase_outputs: Dict[str, str] = field(default_factory=dict)
    phase_checkpoints: Dict[str, Checkpoint] = field(default_factory=dict)
    total_usage: TokenUsage = field(default_factory=TokenUsage)
    total_cost: CostBreakdown = field(default_factory=CostBreakdown)
    status: SessionStatus = SessionStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    @property
    def current_phase(self) -> Optional[PhaseType]:
        """Get current phase being executed."""
        if 0 <= self.current_phase_index < len(self.phases):
            return self.phases[self.current_phase_index]
        return None
    @property
    def is_complete(self) -> bool:
        """Check if all phases are complete."""
        return self.current_phase_index >= len(self.phases)
    @property
    def completed_phases(self) -> List[PhaseType]:
        """Get list of completed phases."""
        return self.phases[:self.current_phase_index]
    @property
    def remaining_phases(self) -> List[PhaseType]:
        """Get list of remaining phases."""
        return self.phases[self.current_phase_index:]
    def to_dict(self) -> Dict[str, Any]:
        """Serialize session state for persistence."""
        return {
            "session_id": self.session_id,
            "task": self.task,
            "phases": [p.value for p in self.phases],
            "current_phase_index": self.current_phase_index,
            "phase_outputs": self.phase_outputs,
            "total_usage": {
                "input_tokens": self.total_usage.input_tokens,
                "output_tokens": self.total_usage.output_tokens,
                "cache_read_tokens": self.total_usage.cache_read_tokens,
                "cache_write_tokens": self.total_usage.cache_write_tokens,
            },
            "total_cost": {
                "input_cost": self.total_cost.input_cost,
                "output_cost": self.total_cost.output_cost,
                "cache_read_cost": self.total_cost.cache_read_cost,
                "cache_write_cost": self.total_cost.cache_write_cost,
            },
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrchestratedSession":
        """Deserialize session state from dict."""
        phases = [PhaseType(p) for p in data["phases"]]
        usage_data = data.get("total_usage", {})
        usage = TokenUsage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            cache_read_tokens=usage_data.get("cache_read_tokens", 0),
            cache_write_tokens=usage_data.get("cache_write_tokens", 0),
        )
        cost_data = data.get("total_cost", {})
        cost = CostBreakdown(
            input_cost=cost_data.get("input_cost", 0.0),
            output_cost=cost_data.get("output_cost", 0.0),
            cache_read_cost=cost_data.get("cache_read_cost", 0.0),
            cache_write_cost=cost_data.get("cache_write_cost", 0.0),
        )
        return cls(
            session_id=data["session_id"],
            task=data["task"],
            phases=phases,
            current_phase_index=data.get("current_phase_index", 0),
            phase_outputs=data.get("phase_outputs", {}),
            total_usage=usage,
            total_cost=cost,
            status=SessionStatus(data.get("status", "created")),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
        )
class OneshotOrchestrator(BaseExecutor):
    """
    Oneshot orchestrator with checkpoint-based resume capability.
    Features:
    - Extends BaseExecutor for batch execution
    - Checkpoint after each phase for recovery
    - Silent subagent delegation using presets
    - Session persistence for workflow resumption
    - Optimized for cost with batch execution
    - Comprehensive error handling
    Usage:
        # New workflow
        orchestrator = OneshotOrchestrator()
        result = orchestrator.execute(
            task="Build a REST API",
            phases=[PhaseType.PLANNING, PhaseType.IMPLEMENTATION]
        )
        # Resume from checkpoint
        orchestrator2 = OneshotOrchestrator()
        result2 = orchestrator2.resume(session_id="workflow-123")
    """
    def __init__(
        self,
        config: Optional[Config] = None,
        model: Optional[str] = None,
        checkpoint_dir: Optional[Path] = None,
    ):
        """
        Initialize oneshot orchestrator.
        DEPRECATED: OneshotOrchestrator is deprecated. Use OrchestratorExecutor instead.
        Args:
            config: Configuration instance
            model: Override default model
            checkpoint_dir: Directory for checkpoint storage (default: ./checkpoints)
        """
        warnings.warn(
            "OneshotOrchestrator is deprecated and will be removed in a future version. "
            "Use OrchestratorExecutor from sdk_workflow.executors.orchestrator instead. "
            "See module docstring for migration guide.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(config)
        # Model configuration
        self._model = model or self.config.routing.default_oneshot_model
        # Checkpoint management
        self._checkpoint_dir = checkpoint_dir or Path("checkpoints")
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        # Session state
        self._session: Optional[OrchestratedSession] = None
        # Output management
        self._output_dir = Path("outputs")
        self._output_dir.mkdir(parents=True, exist_ok=True)
    def setup(self) -> None:
        """Initialize executor resources."""
        logger.info(f"OneshotOrchestrator setup - model: {self._model}")
    def execute(
        self,
        task: str,
        phases: List[PhaseType],
        system_prompt: str = "",
        session_id: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute multi-phase orchestrated workflow with checkpointing.
        Each phase:
        1. Uses silent system prompt from config.presets
        2. Executes with oneshot query
        3. Checkpoints state for resume
        4. Saves output to outputs/{session_id}/{phase}/
        Args:
            task: Main task description
            phases: List of phases to execute sequentially
            system_prompt: Optional additional system context
            session_id: Optional session ID (generated if not provided)
        Returns:
            ExecutionResult with aggregated metrics
        """
        self._start_timer()
        # Create or resume session
        if session_id:
            self._session = self._load_session(session_id)
            if not self._session:
                raise ValueError(f"Session {session_id} not found")
        else:
            session_id = f"workflow-{datetime.now():%Y%m%d-%H%M%S}"
            self._session = OrchestratedSession(
                session_id=session_id,
                task=task,
                phases=phases,
            )
        self._session.status = SessionStatus.RUNNING
        logger.info(f"Starting workflow {session_id} - {len(phases)} phases")
        try:
            # Execute remaining phases
            all_outputs = []
            for phase in self._session.remaining_phases:
                logger.info(f"Executing phase: {phase.value}")
                # Execute phase
                phase_result = self._execute_phase(task, phase, system_prompt)
                all_outputs.append(f"=== {phase.value.upper()} ===\n{phase_result.content}")
                # Store phase output
                self._session.phase_outputs[phase.value] = phase_result.content
                # Accumulate metrics
                self._accumulate_metrics(phase_result.usage, phase_result.cost)
                # Create checkpoint
                self.checkpoint()
                # Move to next phase
                self._session.current_phase_index += 1
            # Mark completion
            self._session.status = SessionStatus.COMPLETED
            self._session.updated_at = datetime.now()
            self._save_session()
            logger.info(f"Workflow {session_id} completed successfully")
            # Build final result
            combined_output = "\n\n".join(all_outputs)
            return ExecutionResult(
                content=combined_output,
                usage=self._session.total_usage,
                cost=self._session.total_cost,
                model=self._model,
                mode=ExecutionMode.ORCHESTRATOR,
                duration_ms=self._get_duration_ms(),
                artifacts=[str(self._output_dir / session_id)],
            )
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            self._session.status = SessionStatus.FAILED
            self._session.updated_at = datetime.now()
            self._save_session()
            raise
    def resume(self, session_id: str) -> ExecutionResult:
        """
        Resume workflow from last checkpoint.
        Loads session state and continues execution from the last
        successfully completed phase.
        Args:
            session_id: Session ID to resume
        Returns:
            ExecutionResult from resumed execution
        Raises:
            ValueError: If session not found or cannot be resumed
        """
        logger.info(f"Resuming workflow {session_id}")
        # Load session
        session = self._load_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        if session.is_complete:
            raise ValueError(f"Session {session_id} is already complete")
        # Resume execution
        return self.execute(
            task=session.task,
            phases=session.phases,
            session_id=session_id,
        )
    def checkpoint(self) -> Checkpoint:
        """
        Create checkpoint of current workflow state.
        Saves session state to disk for recovery and resumption.
        Returns:
            Checkpoint with current state
        Raises:
            RuntimeError: If no active session
        """
        if not self._session:
            raise RuntimeError("No active session to checkpoint")
        # Create checkpoint
        checkpoint = Checkpoint(
            timestamp=datetime.now(),
            accumulated_text="\n".join(self._session.phase_outputs.values()),
            usage=self._session.total_usage,
            cost=self._session.total_cost,
            metadata={
                "session_id": self._session.session_id,
                "current_phase_index": self._session.current_phase_index,
                "completed_phases": [p.value for p in self._session.completed_phases],
            }
        )
        # Store checkpoint in session
        if self._session.current_phase:
            self._session.phase_checkpoints[self._session.current_phase.value] = checkpoint
        # Save session state
        self._session.status = SessionStatus.CHECKPOINTED
        self._session.updated_at = datetime.now()
        self._save_session()
        logger.info(
            f"Checkpoint created for phase {self._session.current_phase.value if self._session.current_phase else 'unknown'} "
            f"- {checkpoint.checkpoint_id}"
        )
        return checkpoint
    def _execute_phase(
        self,
        task: str,
        phase: PhaseType,
        base_system_prompt: str = ""
    ) -> ExecutionResult:
        """
        Execute single phase with silent subagent delegation.
        Args:
            task: Task description
            phase: Phase to execute
            base_system_prompt: Additional system context
        Returns:
            ExecutionResult for this phase
        """
        # Get silent system prompt from presets
        phase_prompt = get_phase_prompt(phase)
        # Combine with base system prompt if provided
        if base_system_prompt:
            combined_prompt = f"{base_system_prompt}\n\n{phase_prompt}"
        else:
            combined_prompt = phase_prompt
        # Build phase-specific task with context
        phase_task = self._build_phase_task(task, phase)
        # Execute using oneshot query
        model_config = self.config.resolve_model(self._model)
        options = ClaudeAgentOptions(
            model=model_config.model_id,
            system_prompt=combined_prompt,
            max_turns=1, # Oneshot execution
            cwd=str(Path.cwd()),
            permission_mode="bypassPermissions",
        )
        # Execute query
        messages = []
        async def collect_messages():
            async for message in query(prompt=phase_task, options=options):
                messages.append(message)
        # Run async collection
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(collect_messages())
        # Extract result
        content = []
        tool_uses = []
        usage = TokenUsage()
        stop_reason = None
        for message in messages:
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        content.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        tool_uses.append({
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
            elif isinstance(message, ResultMessage):
                if hasattr(message, 'usage') and message.usage:
                    usage = TokenUsage(
                        input_tokens=message.usage.get('input_tokens', 0),
                        output_tokens=message.usage.get('output_tokens', 0),
                        cache_read_tokens=message.usage.get('cache_read_input_tokens', 0),
                        cache_write_tokens=message.usage.get('cache_creation_input_tokens', 0),
                    )
                if hasattr(message, 'stop_reason'):
                    stop_reason = message.stop_reason
        # Calculate cost
        cost = self._calculate_cost(usage, model_config.model_id)
        # Save phase output
        self._save_phase_output(phase, "\n".join(content))
        return ExecutionResult(
            content="\n".join(content),
            usage=usage,
            cost=cost,
            model=model_config.model_id,
            mode=ExecutionMode.ORCHESTRATOR,
            stop_reason=stop_reason,
            tool_uses=tool_uses,
        )
    def _build_phase_task(self, original_task: str, phase: PhaseType) -> str:
        """
        Build phase-specific task with context from previous phases.
        Args:
            original_task: Original task description
            phase: Current phase
        Returns:
            Task with previous phase context injected
        """
        if not self._session:
            return original_task
        # Get previous phase outputs
        context_parts = []
        for prev_phase in self._session.completed_phases:
            output = self._session.phase_outputs.get(prev_phase.value)
            if output:
                context_parts.append(f"=== {prev_phase.value.upper()} OUTPUT ===\n{output}")
        # Build task with context
        if context_parts:
            context = "\n\n".join(context_parts)
            return f"{context}\n\n=== CURRENT TASK ===\n{original_task}"
        else:
            return original_task
    def _accumulate_metrics(self, usage: TokenUsage, cost: CostBreakdown) -> None:
        """Accumulate usage and cost metrics in session."""
        if not self._session:
            return
        self._session.total_usage.input_tokens += usage.input_tokens
        self._session.total_usage.output_tokens += usage.output_tokens
        self._session.total_usage.cache_read_tokens += usage.cache_read_tokens
        self._session.total_usage.cache_write_tokens += usage.cache_write_tokens
        self._session.total_cost.input_cost += cost.input_cost
        self._session.total_cost.output_cost += cost.output_cost
        self._session.total_cost.cache_read_cost += cost.cache_read_cost
        self._session.total_cost.cache_write_cost += cost.cache_write_cost
    def _save_session(self) -> None:
        """Save session state to checkpoint file."""
        if not self._session:
            return
        checkpoint_file = self._checkpoint_dir / f"{self._session.session_id}.json"
        checkpoint_file.write_text(
            json.dumps(self._session.to_dict(), indent=2),
            encoding="utf-8"
        )
        logger.debug(f"Session saved to {checkpoint_file}")
    def _load_session(self, session_id: str) -> Optional[OrchestratedSession]:
        """
        Load session state from checkpoint file.
        Args:
            session_id: Session ID to load
        Returns:
            OrchestratedSession or None if not found
        """
        checkpoint_file = self._checkpoint_dir / f"{session_id}.json"
        if not checkpoint_file.exists():
            return None
        try:
            data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            session = OrchestratedSession.from_dict(data)
            logger.info(f"Loaded session {session_id} - phase {session.current_phase_index}/{len(session.phases)}")
            return session
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}", exc_info=True)
            return None
    def _save_phase_output(self, phase: PhaseType, content: str) -> None:
        """Save phase output to file."""
        if not self._session:
            return
        phase_dir = self._output_dir / self._session.session_id / phase.value
        phase_dir.mkdir(parents=True, exist_ok=True)
        output_file = phase_dir / "output.txt"
        output_file.write_text(content, encoding="utf-8")
        logger.debug(f"Saved {phase.value} output to {output_file}")
    def cleanup(self) -> None:
        """Release resources and finalize session."""
        if self._session and self._session.status == SessionStatus.RUNNING:
            self._session.status = SessionStatus.COMPLETED
            self._save_session()
        self._session = None
        logger.info("OneshotOrchestrator cleanup complete")
    def get_session(self) -> Optional[OrchestratedSession]:
        """Get current session state."""
        return self._session
    def list_sessions(self) -> List[str]:
        """
        List all available session IDs.
        Returns:
            List of session IDs
        """
        sessions = []
        for checkpoint_file in self._checkpoint_dir.glob("*.json"):
            sessions.append(checkpoint_file.stem)
        return sorted(sessions)
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session information without loading full state.
        Args:
            session_id: Session ID
        Returns:
            Dictionary with session info or None if not found
        """
        checkpoint_file = self._checkpoint_dir / f"{session_id}.json"
        if not checkpoint_file.exists():
            return None
        try:
            data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            return {
                "session_id": data["session_id"],
                "task": data["task"],
                "phases": data["phases"],
                "current_phase_index": data.get("current_phase_index", 0),
                "status": data.get("status", "unknown"),
                "created_at": data["created_at"],
                "updated_at": data["updated_at"],
            }
        except Exception as e:
            logger.error(f"Failed to get session info for {session_id}: {e}")
            return None
# ============================================================================
# USAGE EXAMPLES
# ============================================================================
def example_basic_workflow():
    """Basic oneshot orchestration workflow."""
    orchestrator = OneshotOrchestrator()
    orchestrator.setup()
    result = orchestrator.execute(
        task="Create a simple Python REST API with authentication",
        phases=[
            PhaseType.PLANNING,
            PhaseType.IMPLEMENTATION,
            PhaseType.TESTING,
        ]
    )
    print(f"\nWorkflow completed!")
    print(f"Session ID: {orchestrator.get_session().session_id}")
    print(f"Total tokens: {result.usage.total_tokens}")
    print(f"Total cost: ${result.cost.total_cost:.4f}")
    print(f"Duration: {result.duration_ms/1000:.1f}s")
    orchestrator.cleanup()
def example_resume_workflow():
    """Resume workflow from checkpoint."""
    # First execution (simulate interruption)
    orchestrator1 = OneshotOrchestrator()
    orchestrator1.setup()
    try:
        # Start workflow
        result1 = orchestrator1.execute(
            task="Build a data processing pipeline",
            phases=[
                PhaseType.PLANNING,
                PhaseType.IMPLEMENTATION,
                PhaseType.REVIEW,
                PhaseType.TESTING,
            ]
        )
    except KeyboardInterrupt:
        print("\nWorkflow interrupted!")
        session = orchestrator1.get_session()
        print(f"Checkpoint saved at phase {session.current_phase_index}/{len(session.phases)}")
        session_id = session.session_id
        orchestrator1.cleanup()
        # Resume later
        print(f"\nResuming workflow {session_id}...")
        orchestrator2 = OneshotOrchestrator()
        orchestrator2.setup()
        result2 = orchestrator2.resume(session_id=session_id)
        print(f"Workflow resumed and completed!")
        print(f"Total cost: ${result2.cost.total_cost:.4f}")
        orchestrator2.cleanup()
def example_list_sessions():
    """List and inspect available sessions."""
    orchestrator = OneshotOrchestrator()
    # List all sessions
    sessions = orchestrator.list_sessions()
    print(f"\nFound {len(sessions)} sessions:")
    for session_id in sessions:
        info = orchestrator.get_session_info(session_id)
        if info:
            print(f"\n Session: {session_id}")
            print(f" Task: {info['task'][:60]}...")
            print(f" Status: {info['status']}")
            print(f" Progress: {info['current_phase_index']}/{len(info['phases'])} phases")
            print(f" Updated: {info['updated_at']}")
def example_batch_execution():
    """Execute multiple workflows in batch."""
    orchestrator = OneshotOrchestrator()
    orchestrator.setup()
    tasks = [
        {
            "task": "Create REST API for user management",
            "phases": [PhaseType.PLANNING, PhaseType.IMPLEMENTATION],
        },
        {
            "task": "Build data validation library",
            "phases": [PhaseType.PLANNING, PhaseType.IMPLEMENTATION, PhaseType.TESTING],
        },
        {
            "task": "Design authentication system",
            "phases": [PhaseType.PLANNING, PhaseType.REVIEW],
        },
    ]
    results = []
    for i, task_config in enumerate(tasks, 1):
        print(f"\n{'='*60}")
        print(f"Executing task {i}/{len(tasks)}")
        print(f"{'='*60}")
        result = orchestrator.execute(
            task=task_config["task"],
            phases=task_config["phases"]
        )
        results.append(result)
        print(f" Completed - {result.usage.total_tokens} tokens, ${result.cost.total_cost:.4f}")
    # Summary
    print(f"\n{'='*60}")
    print("BATCH EXECUTION SUMMARY")
    print(f"{'='*60}")
    total_tokens = sum(r.usage.total_tokens for r in results)
    total_cost = sum(r.cost.total_cost for r in results)
    print(f"Tasks completed: {len(results)}")
    print(f"Total tokens: {total_tokens:,}")
    print(f"Total cost: ${total_cost:.4f}")
    orchestrator.cleanup()
def example_checkpoint_recovery():
    """Demonstrate checkpoint-based error recovery."""
    orchestrator = OneshotOrchestrator()
    orchestrator.setup()
    session_id = None
    try:
        result = orchestrator.execute(
            task="Complex multi-phase workflow",
            phases=[
                PhaseType.PLANNING,
                PhaseType.IMPLEMENTATION,
                PhaseType.REVIEW,
                PhaseType.TESTING,
            ]
        )
    except Exception as e:
        print(f"\nError occurred: {e}")
        session = orchestrator.get_session()
        if session:
            session_id = session.session_id
            print(f"Session checkpointed: {session_id}")
            print(f"Completed phases: {[p.value for p in session.completed_phases]}")
            print(f"Remaining phases: {[p.value for p in session.remaining_phases]}")
    finally:
        orchestrator.cleanup()
    # Retry from checkpoint
    if session_id:
        print(f"\nRetrying from checkpoint {session_id}...")
        orchestrator2 = OneshotOrchestrator()
        orchestrator2.setup()
        try:
            result2 = orchestrator2.resume(session_id=session_id)
            print("Workflow completed successfully after recovery!")
        except Exception as e2:
            print(f"Recovery failed: {e2}")
        finally:
            orchestrator2.cleanup()
if __name__ == "__main__":
    # Run basic example
    example_basic_workflow()
