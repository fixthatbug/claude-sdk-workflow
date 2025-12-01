"""
Orchestrator Executor - Multi-agent delegation with workflow management.
Extends StreamingExecutor with subagent delegation capabilities
for complex multi-phase workflows.
Migration Note:
    - OneshotExecutor imported from consolidated streaming_orchestrator module
    - Deprecated oneshot.py module archived
"""
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import json
from .streaming import StreamingExecutor
from .streaming_orchestrator import OneshotExecutor # UPDATED: Import from consolidated module
from core.config import Config
from config.agent_prompts import get_orchestrator_prompt, get_subagent_prompt
from core.types import (
    ExecutionResult,
    ExecutionMode,
    SessionStatus,
    SubagentTask,
    SubagentResult,
    TokenUsage,
    CostBreakdown,
    ExecutionError,
    ErrorCategory,
    ErrorSeverity,
)
class WorkflowPhase(Enum):
    """Standard workflow phases for orchestration."""
    ARCHITECT = "architect"
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"
    TESTER = "tester"
    CUSTOM = "custom"
@dataclass
class PhaseResult:
    """Result from a workflow phase."""
    phase: WorkflowPhase
    success: bool
    output: str
    subagent_results: List[SubagentResult] = field(default_factory=list)
    accumulated_usage: TokenUsage = field(default_factory=TokenUsage)
    accumulated_cost: CostBreakdown = field(default_factory=CostBreakdown)
class OrchestratorExecutor(StreamingExecutor):
    """
    Orchestrator executor for multi-agent workflows.
    Extends StreamingExecutor with:
    - Subagent delegation via Task tool
    - Workflow phase management
    - Result aggregation across agents
    - Dependency resolution between tasks
    Workflow Pattern:
    1. Architect designs structure
    2. Implementer builds components
    3. Reviewer validates quality
    4. Tester verifies functionality
    """
    def __init__(
        self,
        config: Optional[Config] = None,
        model: Optional[str] = None,
        on_text: Optional[Callable[[str], None]] = None,
        on_tool_use: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_complete: Optional[Callable[[ExecutionResult], None]] = None,
        on_subagent_start: Optional[Callable[[SubagentTask], None]] = None,
        on_subagent_complete: Optional[Callable[[SubagentResult], None]] = None,
        cwd: Optional[str] = None,
        permission_mode: Optional[str] = None,
    ):
        """
        Initialize orchestrator executor.
        Args:
            config: Configuration instance
            model: Override default model
            on_text: Callback for text chunks
            on_tool_use: Callback for tool use events
            on_complete: Callback when orchestration completes
            on_subagent_start: Callback when subagent starts
            on_subagent_complete: Callback when subagent completes
            cwd: Working directory for agent execution
        """
        super().__init__(config, model, on_text, on_tool_use, on_complete, cwd=cwd, permission_mode=permission_mode)
        # Override default model for orchestrator
        self._model = model or self.config.routing.default_orchestrator_model
        # Subagent callbacks
        self._on_subagent_start = on_subagent_start or self._default_subagent_start
        self._on_subagent_complete = on_subagent_complete or self._default_subagent_complete
        # Subagent executor (reused for all delegations)
        self._subagent_executor: Optional[OneshotExecutor] = None
        # Workflow state
        self._phase_results: List[PhaseResult] = []
        self._subagent_results: List[SubagentResult] = []
        self._task_outputs: Dict[str, str] = {} # task_id -> output
    def setup(self) -> None:
        """Initialize orchestrator and subagent executor."""
        super().setup()
        # Initialize subagent executor with default subagent model
        self._subagent_executor = OneshotExecutor(
            config=self.config,
            model=self.config.routing.default_subagent_model,
        )
        self._subagent_executor.setup()
        self._phase_results = []
        self._subagent_results = []
        self._task_outputs = {}
    def execute(self, task: str, system_prompt: str = "") -> ExecutionResult:
        """
        Execute orchestrated workflow.
        Intercepts tool use for Task tool calls and delegates
        to subagent executor.
        Args:
            task: The orchestration task
            system_prompt: System prompt with workflow definition (defaults to enhanced orchestrator prompt)
        Returns:
            ExecutionResult with aggregated outputs
        """
        # Use enhanced orchestrator prompt if none provided
        if not system_prompt:
            system_prompt = get_orchestrator_prompt()
        # Override tool use handler to intercept Task tool
        original_on_tool_use = self._on_tool_use
        self._on_tool_use = self._intercept_tool_use
        try:
            result = super().execute(task, system_prompt)
            # Aggregate subagent usage into result
            result = self._aggregate_subagent_results(result)
            return result
        finally:
            self._on_tool_use = original_on_tool_use
    def _intercept_tool_use(self, tool: Dict[str, Any]) -> None:
        """
        Intercept tool use events to handle Task delegations.
        Args:
            tool: Tool use dictionary with name and input
        """
        if tool.get("name") == "Task":
            # Handle Task tool delegation
            task_input = tool.get("input", {})
            result = self.handle_task_tool(task_input)
            # Store result for context
            task_id = task_input.get("task_id", tool.get("id", "unknown"))
            self._task_outputs[task_id] = result
        # Call original handler
        self._default_on_tool_use(tool)
    def handle_task_tool(self, task_request: Dict[str, Any]) -> str:
        """
        Handle Task tool call by delegating to subagent.
        Args:
            task_request: Task tool input with:
                - agent_type: Type of agent (default: expert-clone)
                - prompt: Task prompt
                - system_prompt: Optional system prompt override
                - model: Optional model override
                - dependencies: Optional list of task IDs to wait for
        Returns:
            Subagent response content
        """
        # Build subagent task
        subagent_task = SubagentTask(
            task_id=task_request.get("task_id", ""),
            agent_type=task_request.get("agent_type", "expert-clone"),
            prompt=task_request.get("prompt", ""),
            system_prompt=task_request.get("system_prompt", ""),
            model=task_request.get("model"),
            dependencies=task_request.get("dependencies", []),
        )
        # Resolve dependencies - inject outputs from previous tasks
        resolved_prompt = self._resolve_dependencies(subagent_task)
        # Get enhanced subagent prompt if none provided
        if not subagent_task.system_prompt:
            try:
                subagent_task.system_prompt = get_subagent_prompt(subagent_task.agent_type)
            except ValueError:
                # If agent_type not recognized, use expert-clone as fallback
                subagent_task.system_prompt = get_subagent_prompt("expert-clone")
        # Notify subagent start
        self._on_subagent_start(subagent_task)
        # Execute with subagent executor
        try:
            # Override model if specified
            if subagent_task.model:
                self._subagent_executor._model_override = subagent_task.model
            result = self._subagent_executor.execute(
                resolved_prompt,
                subagent_task.system_prompt,
            )
            # Build subagent result
            subagent_result = SubagentResult(
                task_id=subagent_task.task_id,
                success=result.success,
                content=result.content,
                usage=result.usage,
                cost=result.cost,
                duration_ms=result.duration_ms,
            )
        except Exception as e:
            # Handle subagent failure
            subagent_result = SubagentResult(
                task_id=subagent_task.task_id,
                success=False,
                content=f"Subagent error: {str(e)}",
                usage=TokenUsage(),
                cost=CostBreakdown(),
                duration_ms=0,
                error=ExecutionError(
                    message=str(e),
                    category=ErrorCategory.EXTERNAL,
                    severity=ErrorSeverity.RECOVERABLE,
                    original_exception=e,
                ),
            )
        # Reset model override
        self._subagent_executor._model_override = None
        # Track result
        self._subagent_results.append(subagent_result)
        # Notify completion
        self._on_subagent_complete(subagent_result)
        return subagent_result.content
    def _resolve_dependencies(self, task: SubagentTask) -> str:
        """
        Resolve task dependencies by injecting prior outputs.
        Args:
            task: Subagent task with potential dependencies
        Returns:
            Resolved prompt with dependency outputs injected
        """
        if not task.dependencies:
            return task.prompt
        # Build context from dependencies
        dependency_context = []
        for dep_id in task.dependencies:
            if dep_id in self._task_outputs:
                dependency_context.append(
                    f"[Output from {dep_id}]:\n{self._task_outputs[dep_id]}"
                )
        if dependency_context:
            context_block = "\n\n".join(dependency_context)
            return f"{context_block}\n\n---\n\n{task.prompt}"
        return task.prompt
    def _aggregate_subagent_results(self, result: ExecutionResult) -> ExecutionResult:
        """
        Aggregate subagent usage and costs into main result.
        Args:
            result: Main execution result
        Returns:
            Result with aggregated totals
        """
        for subagent_result in self._subagent_results:
            # Accumulate usage
            result.usage.input_tokens += subagent_result.usage.input_tokens
            result.usage.output_tokens += subagent_result.usage.output_tokens
            result.usage.cache_read_tokens += subagent_result.usage.cache_read_tokens
            result.usage.cache_write_tokens += subagent_result.usage.cache_write_tokens
            # Accumulate cost
            result.cost.input_cost += subagent_result.cost.input_cost
            result.cost.output_cost += subagent_result.cost.output_cost
            result.cost.cache_read_cost += subagent_result.cost.cache_read_cost
            result.cost.cache_write_cost += subagent_result.cost.cache_write_cost
        # Update mode to reflect orchestration
        result.mode = ExecutionMode.ORCHESTRATOR
        return result
    def execute_phase(
        self,
        phase: WorkflowPhase,
        task: str,
        system_prompt: str = ""
    ) -> PhaseResult:
        """
        Execute a specific workflow phase.
        Convenience method for structured workflow execution.
        Args:
            phase: The workflow phase
            task: Task for this phase
            system_prompt: Phase-specific system prompt
        Returns:
            PhaseResult with phase output and metrics
        """
        # Track pre-execution state
        pre_subagent_count = len(self._subagent_results)
        # Execute phase
        result = self.execute(task, system_prompt)
        # Collect phase-specific subagent results
        phase_subagents = self._subagent_results[pre_subagent_count:]
        # Build phase result
        phase_result = PhaseResult(
            phase=phase,
            success=result.success,
            output=result.content,
            subagent_results=phase_subagents,
            accumulated_usage=result.usage,
            accumulated_cost=result.cost,
        )
        self._phase_results.append(phase_result)
        return phase_result
    def get_phase_results(self) -> List[PhaseResult]:
        """Get all completed phase results."""
        return self._phase_results.copy()
    def get_workflow_summary(self) -> Dict[str, Any]:
        """
        Get summary of entire workflow execution.
        Returns:
            Dictionary with phases, totals, and status
        """
        total_usage = TokenUsage()
        total_cost = CostBreakdown()
        for phase_result in self._phase_results:
            total_usage.input_tokens += phase_result.accumulated_usage.input_tokens
            total_usage.output_tokens += phase_result.accumulated_usage.output_tokens
            total_usage.cache_read_tokens += phase_result.accumulated_usage.cache_read_tokens
            total_usage.cache_write_tokens += phase_result.accumulated_usage.cache_write_tokens
            total_cost.input_cost += phase_result.accumulated_cost.input_cost
            total_cost.output_cost += phase_result.accumulated_cost.output_cost
            total_cost.cache_read_cost += phase_result.accumulated_cost.cache_read_cost
            total_cost.cache_write_cost += phase_result.accumulated_cost.cache_write_cost
        return {
            "phases_completed": len(self._phase_results),
            "all_succeeded": all(pr.success for pr in self._phase_results),
            "total_subagents": len(self._subagent_results),
            "total_tokens": total_usage.total_tokens,
            "total_cost_usd": total_cost.total_cost,
            "cache_hit_rate": total_usage.cache_hit_rate,
            "phases": [
                {
                    "name": pr.phase.value,
                    "success": pr.success,
                    "subagent_count": len(pr.subagent_results),
                }
                for pr in self._phase_results
            ],
        }
    def _default_subagent_start(self, task: SubagentTask) -> None:
        """Default subagent start callback."""
        print(f"\n[Subagent: {task.agent_type}] Starting task {task.task_id}...")
    def _default_subagent_complete(self, result: SubagentResult) -> None:
        """Default subagent complete callback."""
        status = "completed" if result.success else "failed"
        print(f"[Subagent: {result.task_id}] {status} ({result.duration_ms:.0f}ms)")
    def cleanup(self) -> None:
        """Release orchestrator and subagent resources."""
        super().cleanup()
        if self._subagent_executor:
            self._subagent_executor.cleanup()
            self._subagent_executor = None
        self._phase_results = []
        self._subagent_results = []
        self._task_outputs = {}
