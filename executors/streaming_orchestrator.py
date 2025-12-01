"""
Streaming Orchestrator - Phase-by-phase workflow with real-time progress.
CONSOLIDATED MODULE - Contains all executor functionalities:
- OneshotExecutor: Single-shot execution with auto-escalation (merged from oneshot.py)
- StreamingOrchestrator: Phase-by-phase workflow with real-time progress
Extends StreamingExecutor to provide orchestrated multi-phase execution with:
- Silent subagent delegation using phase presets
- Real-time progress reporting for user visibility
- Structured output management per phase
- Phase dependency resolution
- Comprehensive error handling and recovery
- Auto-escalation from Haiku to Sonnet for quality assurance
- Token accumulation across escalation attempts
- Model routing and quality checks
Migration Note: This module consolidates functionality from:
- executors/oneshot.py (OneshotExecutor)
- executors/oneshot_orchestrator.py (deprecated OneshotOrchestrator)
- executors/oneshot_example.py (example patterns)
"""
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
import json
import asyncio
import logging
import time
from datetime import datetime
from dataclasses import dataclass, field
from .streaming import StreamingExecutor
from .base import BaseExecutor
from config.presets import PhaseType, get_phase_prompt
from core.config import Config
from core.types import (
    ExecutionResult,
    ExecutionMode,
    TokenUsage,
    CostBreakdown,
    SubagentTask,
    SubagentResult,
)
from core.agent_client import get_agent_client
from claude_agent_sdk import (
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ThinkingBlock,
    ToolResultBlock,
    UserMessage,
    SystemMessage,
    query,
    CLINotFoundError,
    ProcessError,
    CLIJSONDecodeError,
    ClaudeSDKError,
)
logger = logging.getLogger(__name__)
# ============================================================================
# ONESHOT EXECUTOR - Consolidated from oneshot.py
# ============================================================================
class OneshotExecutor(BaseExecutor):
    """
    Single-shot executor with intelligent model routing.
    Strategy:
    1. Start with Haiku (cost-effective)
    2. Check response quality
    3. Auto-escalate to Sonnet if quality fails
    Quality Checks:
    - Response contains escalation markers ("I cannot", etc.)
    - Response is too short (< min_quality_length)
    - Response indicates uncertainty
    Implementation based on Claude Agent SDK Python reference.
    Consolidated from executors/oneshot.py into streaming_orchestrator.py
    """
    def __init__(
        self,
        config: Optional[Config] = None,
        model: Optional[str] = None,
        cwd: Optional[str] = None,
        permission_mode: Optional[str] = None,
    ):
        """
        Initialize oneshot executor.
        Args:
            config: Configuration instance
            model: Override default model (skips auto-routing)
            cwd: Working directory for agent execution
            permission_mode: Permission mode for agent execution
        """
        super().__init__(config)
        self._model_override = model
        self._cwd = cwd
        self._permission_mode = permission_mode
        self._escalated = False
        # Accumulated usage across escalation attempts
        self._total_usage = TokenUsage()
        self._total_cost = CostBreakdown()
        # Timing
        self._start_time: Optional[float] = None
    def setup(self) -> None:
        """Initialize executor state."""
        self._escalated = False
        self._total_usage = TokenUsage()
        self._total_cost = CostBreakdown()
        self._start_time = None
    def execute(
        self,
        task: str,
        system_prompt: str = ""
    ) -> ExecutionResult:
        """
        Execute single-shot request with auto-escalation.
        Args:
            task: The task/prompt to execute
            system_prompt: Optional system prompt
        Returns:
            ExecutionResult from best attempt
        Raises:
            CLINotFoundError: If Claude Code CLI not installed
            ProcessError: If CLI process fails
            CLIJSONDecodeError: If response parsing fails
        """
        self._start_timer()
        # Determine starting model
        if self._model_override:
            model = self._model_override
        else:
            model = self.config.routing.default_oneshot_model
        try:
            # First attempt with initial model
            result = self._execute_with_model(task, system_prompt, model)
            # Check if escalation needed (only if started with haiku)
            if (
                not self._model_override
                and model == "haiku"
                and self._needs_escalation(result.content)
            ):
                # Escalate to Sonnet
                self._escalated = True
                escalated_result = self._execute_with_model(
                    task,
                    system_prompt,
                    self.config.routing.default_streaming_model,
                )
                escalated_result.escalated = True
                return escalated_result
            return result
        except CLINotFoundError as e:
            raise CLINotFoundError(
                "Claude Code not found. Install: npm install -g @anthropic-ai/claude-code",
                cli_path=getattr(e, 'cli_path', None)
            )
        except ProcessError as e:
            raise ProcessError(
                f"CLI process failed: {e}",
                exit_code=getattr(e, 'exit_code', None),
                stderr=getattr(e, 'stderr', None)
            )
        except CLIJSONDecodeError as e:
            raise CLIJSONDecodeError(
                line=getattr(e, 'line', ''),
                original_error=getattr(e, 'original_error', e)
            )
    def _execute_with_model(
        self,
        task: str,
        system_prompt: str,
        model: str
    ) -> ExecutionResult:
        """
        Execute request with specific model using Claude Agent SDK.
        Args:
            task: The task to execute
            system_prompt: System prompt
            model: Model alias or ID
        Returns:
            ExecutionResult from this attempt
        """
        model_config = self.config.resolve_model(model)
        return self._execute_with_agent_sdk(
            task,
            system_prompt,
            model_config
        )
    def _execute_with_agent_sdk(
        self,
        task: str,
        system_prompt: str,
        model_config
    ) -> ExecutionResult:
        """
        Execute using Claude Agent SDK with proper message handling.
        Implementation follows the pattern from SDK documentation for
        basic file operations and message type checking.
        """
        # Create options for the query
        options = ClaudeAgentOptions(
            model=model_config.model_id,
            system_prompt=system_prompt if system_prompt else None,
            max_turns=1,
            cwd=self._cwd,
            permission_mode=self._permission_mode or "default",
            allowed_tools=self.config.allowed_tools if hasattr(self.config, 'allowed_tools') else None,
        )
        # Run the query and collect messages
        messages = self._run_query_sync(prompt=task, options=options)
        # Extract information from messages
        content = ""
        tool_uses = []
        usage_data: Optional[Dict[str, Any]] = None
        stop_reason = None
        result_message: Optional[ResultMessage] = None
        for message in messages:
            if isinstance(message, AssistantMessage):
                # Extract text content
                for block in message.content:
                    if isinstance(block, TextBlock):
                        content += block.text
                    elif isinstance(block, ToolUseBlock):
                        tool_uses.append({
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                # Get model from message
                if hasattr(message, 'model'):
                    model_config.model_id = message.model
            elif isinstance(message, ResultMessage):
                result_message = message
                if hasattr(message, 'usage') and message.usage:
                    usage_data = message.usage
                if hasattr(message, 'subtype'):
                    stop_reason = message.subtype
        # Convert usage data to TokenUsage
        usage = self._convert_usage(usage_data)
        # Calculate cost
        cost = self._calculate_cost(usage, model_config.model_id)
        # Accumulate totals
        self._accumulate_usage(usage, cost)
        return ExecutionResult(
            content=content,
            usage=self._total_usage,
            cost=self._total_cost,
            model=model_config.model_id,
            mode=ExecutionMode.ONESHOT,
            stop_reason=stop_reason,
            tool_uses=tool_uses,
            duration_ms=self._get_duration_ms(),
            escalated=self._escalated,
        )
    def _run_query_sync(
        self,
        prompt: str,
        options: ClaudeAgentOptions
    ) -> List[Any]:
        """
        Run query synchronously and collect all messages.
        Args:
            prompt: User prompt
            options: Claude Agent options
        Returns:
            List of all messages from the query
        """
        messages = []
        # Use asyncio to run the async generator
        async def collect_messages():
            async for message in query(prompt=prompt, options=options):
                messages.append(message)
        # Run in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(collect_messages())
        return messages
    def _convert_usage(
        self,
        usage_data: Optional[Dict[str, Any]]
    ) -> TokenUsage:
        """
        Convert SDK usage data to TokenUsage.
        Args:
            usage_data: Raw usage dictionary from ResultMessage
        Returns:
            TokenUsage instance
        """
        if not usage_data:
            return TokenUsage()
        return TokenUsage(
            input_tokens=usage_data.get('input_tokens', 0),
            output_tokens=usage_data.get('output_tokens', 0),
            cache_read_tokens=usage_data.get('cache_read_input_tokens', 0),
            cache_write_tokens=usage_data.get('cache_creation_input_tokens', 0),
        )
    def _needs_escalation(self, response: str) -> bool:
        """
        Check if response indicates need for model escalation.
        Escalation triggers:
        - Response contains uncertainty markers
        - Response is suspiciously short
        - Response admits inability
        Args:
            response: The model's response text
        Returns:
            True if escalation is recommended
        """
        # Check for escalation markers
        response_lower = response.lower()
        for marker in self.config.routing.escalation_markers:
            if marker.lower() in response_lower:
                return True
        # Check for minimum quality length
        if len(response.strip()) < self.config.routing.min_quality_length:
            return True
        return False
    def _accumulate_usage(
        self,
        usage: TokenUsage,
        cost: CostBreakdown
    ) -> None:
        """Accumulate usage and cost across attempts."""
        self._total_usage.input_tokens += usage.input_tokens
        self._total_usage.output_tokens += usage.output_tokens
        self._total_usage.cache_read_tokens += usage.cache_read_tokens
        self._total_usage.cache_write_tokens += usage.cache_write_tokens
        self._total_cost.input_cost += cost.input_cost
        self._total_cost.output_cost += cost.output_cost
        self._total_cost.cache_read_cost += cost.cache_read_cost
        self._total_cost.cache_write_cost += cost.cache_write_cost
    def _start_timer(self) -> None:
        """Start execution timer."""
        self._start_time = time.time()
    def _get_duration_ms(self) -> int:
        """Get execution duration in milliseconds."""
        if self._start_time is None:
            return 0
        return int((time.time() - self._start_time) * 1000)
    def cleanup(self) -> None:
        """Release resources."""
        self._escalated = False
        self._start_time = None
# ============================================================================
# ORCHESTRATOR CLASSES AND UTILITIES
# ============================================================================
@dataclass
class PhaseProgress:
    """Progress tracking for a workflow phase."""
    phase: PhaseType
    status: str # "pending", "running", "completed", "failed"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    summary: str = ""
    output_path: Optional[Path] = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost: CostBreakdown = field(default_factory=CostBreakdown)
    error: Optional[str] = None
@dataclass
class WorkflowMetrics:
    """Aggregate metrics for entire workflow."""
    phases_completed: int = 0
    phases_failed: int = 0
    total_duration_ms: float = 0.0
    total_usage: TokenUsage = field(default_factory=TokenUsage)
    total_cost: CostBreakdown = field(default_factory=CostBreakdown)
    subagents_executed: int = 0
class OutputManager:
    """Manages phase output storage."""
    def __init__(self, base_path: Path):
        """
        Initialize output manager.
        Args:
            base_path: Base directory for outputs (e.g., outputs/{session_id})
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    def save_phase_output(
        self,
        phase: PhaseType,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Save phase output to file.
        Args:
            phase: Phase type
            content: Phase output content
            metadata: Optional metadata to save alongside
        Returns:
            Path to saved output file
        """
        phase_dir = self.base_path / phase.value
        phase_dir.mkdir(parents=True, exist_ok=True)
        # Save content
        output_file = phase_dir / "output.txt"
        output_file.write_text(content, encoding="utf-8")
        # Save metadata if provided
        if metadata:
            metadata_file = phase_dir / "metadata.json"
            metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        logger.info(f"Saved {phase.value} output to {output_file}")
        return output_file
    def load_phase_output(self, phase: PhaseType) -> Optional[str]:
        """
        Load phase output from file.
        Args:
            phase: Phase type
        Returns:
            Phase output content or None if not found
        """
        output_file = self.base_path / phase.value / "output.txt"
        if output_file.exists():
            return output_file.read_text(encoding="utf-8")
        return None
    def get_workflow_summary(self) -> Dict[str, Any]:
        """
        Get summary of all phase outputs.
        Returns:
            Dictionary with phase summaries
        """
        summary = {}
        for phase_dir in self.base_path.iterdir():
            if phase_dir.is_dir():
                output_file = phase_dir / "output.txt"
                metadata_file = phase_dir / "metadata.json"
                summary[phase_dir.name] = {
                    "has_output": output_file.exists(),
                    "output_size": output_file.stat().st_size if output_file.exists() else 0,
                    "has_metadata": metadata_file.exists(),
                }
        return summary
class StreamingOrchestrator(StreamingExecutor):
    """
    Streaming orchestrator with phase-by-phase execution.
    Features:
    - Extends StreamingExecutor for real-time streaming capabilities
    - Phase-based workflow execution using presets from config.presets
    - Silent subagent delegation (only orchestrator reports progress)
    - Structured output storage per phase
    - Automatic phase dependency resolution
    - Resume capability from checkpoints
    - Comprehensive error handling
    Usage:
        orchestrator = StreamingOrchestrator(
            session_id="workflow-123",
            on_progress=lambda p, s, msg: print(f"[{p.value}] {s}: {msg}")
        )
        result = orchestrator.execute_workflow(
            task="Build a REST API",
            phases=[PhaseType.PLANNING, PhaseType.IMPLEMENTATION, PhaseType.TESTING]
        )
    """
    def __init__(
        self,
        config: Optional[Config] = None,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
        output_base_dir: Optional[Path] = None,
        on_progress: Optional[Callable[[PhaseType, str, str], None]] = None,
        on_phase_complete: Optional[Callable[[PhaseProgress], None]] = None,
        **kwargs
    ):
        """
        Initialize streaming orchestrator.
        Args:
            config: Configuration instance
            model: Override default model
            session_id: Session ID for output organization
            output_base_dir: Base directory for outputs (default: ./outputs)
            on_progress: Callback for progress updates (phase, status, message)
            on_phase_complete: Callback when phase completes
            **kwargs: Additional arguments passed to StreamingExecutor
        """
        super().__init__(config=config, model=model, **kwargs)
        # Session management
        self._session_id = session_id or f"workflow-{datetime.now():%Y%m%d-%H%M%S}"
        # Output management
        base_dir = output_base_dir or Path("outputs")
        self._output_manager = OutputManager(base_dir / self._session_id)
        # Progress tracking
        self._phase_progress: Dict[PhaseType, PhaseProgress] = {}
        self._current_phase: Optional[PhaseType] = None
        self._workflow_metrics = WorkflowMetrics()
        # Callbacks
        self._on_progress = on_progress or self._default_on_progress
        self._on_phase_complete = on_phase_complete or self._default_on_phase_complete
        # Subagent results
        self._subagent_results: List[SubagentResult] = []
    def execute_workflow(
        self,
        task: str,
        phases: List[PhaseType],
        system_prompt: str = ""
    ) -> ExecutionResult:
        """
        Execute multi-phase orchestrated workflow.
        Each phase:
        1. Uses silent system prompt from config.presets
        2. Executes with streaming for real-time updates
        3. Saves output to outputs/{session_id}/{phase}/
        4. Reports progress only from orchestrator
        Args:
            task: Main task description
            phases: List of phases to execute sequentially
            system_prompt: Optional additional system context
        Returns:
            ExecutionResult with aggregated metrics
        """
        self._start_timer()
        workflow_start = datetime.now()
        logger.info(f"Starting workflow {self._session_id} with {len(phases)} phases")
        self.report_progress(None, "workflow_started", f"Executing {len(phases)} phases")
        # Initialize phase tracking
        for phase in phases:
            self._phase_progress[phase] = PhaseProgress(
                phase=phase,
                status="pending"
            )
        all_outputs = []
        final_result = None
        try:
            # Execute phases sequentially
            for phase in phases:
                phase_result = self._execute_phase(task, phase, system_prompt)
                all_outputs.append(f"=== {phase.value.upper()} ===\n{phase_result.content}")
                # Update metrics
                self._workflow_metrics.phases_completed += 1
                self._accumulate_metrics(phase_result.usage, phase_result.cost)
                # Store final result for return
                final_result = phase_result
                # Check for phase failure
                if not phase_result.success:
                    self._phase_progress[phase].status = "failed"
                    self._phase_progress[phase].error = phase_result.stop_reason
                    self._workflow_metrics.phases_failed += 1
                    logger.warning(f"Phase {phase.value} failed: {phase_result.stop_reason}")
                    self.report_progress(phase, "failed", f"Phase failed: {phase_result.stop_reason}")
                    # Stop workflow on failure
                    break
            # Calculate total duration
            workflow_end = datetime.now()
            self._workflow_metrics.total_duration_ms = (workflow_end - workflow_start).total_seconds() * 1000
            # Build final result
            combined_output = "\n\n".join(all_outputs)
            # Save workflow summary
            self._save_workflow_summary()
            # Report completion
            success_count = self._workflow_metrics.phases_completed - self._workflow_metrics.phases_failed
            self.report_progress(
                None,
                "workflow_completed",
                f"Completed {success_count}/{len(phases)} phases successfully"
            )
            return ExecutionResult(
                content=combined_output,
                usage=self._workflow_metrics.total_usage,
                cost=self._workflow_metrics.total_cost,
                model=self._model,
                mode=ExecutionMode.ORCHESTRATOR,
                duration_ms=self._workflow_metrics.total_duration_ms,
                artifacts=[str(self._output_manager.base_path)],
            )
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            self.report_progress(None, "workflow_failed", f"Error: {str(e)}")
            raise
    def _execute_phase(
        self,
        task: str,
        phase: PhaseType,
        base_system_prompt: str = ""
    ) -> ExecutionResult:
        """
        Execute a single workflow phase with silent subagent delegation.
        Args:
            task: Task description
            phase: Phase to execute
            base_system_prompt: Additional system context
        Returns:
            ExecutionResult for this phase
        """
        self._current_phase = phase
        progress = self._phase_progress[phase]
        progress.status = "running"
        progress.started_at = datetime.now()
        logger.info(f"Executing phase: {phase.value}")
        self.report_progress(phase, "started", f"Starting {phase.value} phase")
        try:
            # Get silent system prompt from presets
            phase_prompt = get_phase_prompt(phase)
            # Combine with base system prompt if provided
            if base_system_prompt:
                combined_prompt = f"{base_system_prompt}\n\n{phase_prompt}"
            else:
                combined_prompt = phase_prompt
            # Build phase-specific task with context
            phase_task = self._build_phase_task(task, phase)
            # Execute phase using subagent (silent execution)
            phase_result = self._execute_phase_subagent(phase_task, combined_prompt)
            # Save phase output
            output_path = self._output_manager.save_phase_output(
                phase=phase,
                content=phase_result.content,
                metadata={
                    "phase": phase.value,
                    "started_at": progress.started_at.isoformat(),
                    "completed_at": datetime.now().isoformat(),
                    "tokens": phase_result.usage.total_tokens,
                    "cost": phase_result.cost.total_cost,
                    "model": phase_result.model,
                }
            )
            # Update progress
            progress.status = "completed"
            progress.completed_at = datetime.now()
            progress.summary = self._generate_phase_summary(phase_result.content)
            progress.output_path = output_path
            progress.usage = phase_result.usage
            progress.cost = phase_result.cost
            # Report completion
            duration_s = (progress.completed_at - progress.started_at).total_seconds()
            self.report_progress(
                phase,
                "completed",
                f"Completed in {duration_s:.1f}s - {phase_result.usage.total_tokens} tokens, ${phase_result.cost.total_cost:.4f}"
            )
            # Trigger callback
            self._on_phase_complete(progress)
            return phase_result
        except Exception as e:
            progress.status = "failed"
            progress.completed_at = datetime.now()
            progress.error = str(e)
            logger.error(f"Phase {phase.value} failed: {e}", exc_info=True)
            self.report_progress(phase, "failed", f"Error: {str(e)}")
            raise
    def _execute_phase_subagent(
        self,
        task: str,
        system_prompt: str
    ) -> ExecutionResult:
        """
        Execute phase using silent subagent delegation.
        Uses Claude Agent SDK query() for single-phase execution
        with silent system prompts from config.presets.
        Args:
            task: Phase-specific task
            system_prompt: Silent system prompt from presets
        Returns:
            ExecutionResult from subagent execution
        """
        model_config = self.config.resolve_model(self._model)
        # Create options for silent subagent execution
        options = ClaudeAgentOptions(
            model=model_config.model_id,
            system_prompt=system_prompt,
            max_turns=10, # Allow multiple turns for complex phases
            cwd=str(Path.cwd()),
            permission_mode="default",
        )
        # Execute using query() for silent delegation
        messages = []
        async def collect_phase_messages():
            async for message in query(prompt=task, options=options):
                messages.append(message)
        # Run async collection
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, collect_phase_messages())
                    future.result()
            else:
                loop.run_until_complete(collect_phase_messages())
        except RuntimeError:
            asyncio.run(collect_phase_messages())
        # Extract result from messages
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
        # Track subagent execution
        self._workflow_metrics.subagents_executed += 1
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
        # Get previous phase outputs
        context_parts = []
        for prev_phase in PhaseType:
            if prev_phase == phase:
                break # Don't include current phase
            prev_output = self._output_manager.load_phase_output(prev_phase)
            if prev_output:
                context_parts.append(f"=== {prev_phase.value.upper()} OUTPUT ===\n{prev_output}")
        # Build task with context
        if context_parts:
            context = "\n\n".join(context_parts)
            return f"{context}\n\n=== CURRENT TASK ===\n{original_task}"
        else:
            return original_task
    def _generate_phase_summary(self, content: str, max_length: int = 200) -> str:
        """
        Generate brief summary of phase output.
        Args:
            content: Phase output content
            max_length: Maximum summary length
        Returns:
            Brief summary string
        """
        # Try to extract JSON summary if available
        try:
            data = json.loads(content)
            if "phase" in data:
                phase_name = data.get("phase", "unknown")
                return f"Phase {phase_name} completed successfully"
        except json.JSONDecodeError:
            pass
        # Fallback to truncated text
        summary = content.strip()[:max_length]
        if len(content) > max_length:
            summary += "..."
        return summary
    def _accumulate_metrics(self, usage: TokenUsage, cost: CostBreakdown) -> None:
        """Accumulate usage and cost metrics."""
        self._workflow_metrics.total_usage.input_tokens += usage.input_tokens
        self._workflow_metrics.total_usage.output_tokens += usage.output_tokens
        self._workflow_metrics.total_usage.cache_read_tokens += usage.cache_read_tokens
        self._workflow_metrics.total_usage.cache_write_tokens += usage.cache_write_tokens
        self._workflow_metrics.total_cost.input_cost += cost.input_cost
        self._workflow_metrics.total_cost.output_cost += cost.output_cost
        self._workflow_metrics.total_cost.cache_read_cost += cost.cache_read_cost
        self._workflow_metrics.total_cost.cache_write_cost += cost.cache_write_cost
    def _save_workflow_summary(self) -> None:
        """Save comprehensive workflow summary."""
        summary = {
            "session_id": self._session_id,
            "completed_at": datetime.now().isoformat(),
            "metrics": {
                "phases_completed": self._workflow_metrics.phases_completed,
                "phases_failed": self._workflow_metrics.phases_failed,
                "total_duration_ms": self._workflow_metrics.total_duration_ms,
                "subagents_executed": self._workflow_metrics.subagents_executed,
                "total_tokens": self._workflow_metrics.total_usage.total_tokens,
                "total_cost": self._workflow_metrics.total_cost.total_cost,
            },
            "phases": {
                phase.value: {
                    "status": progress.status,
                    "started_at": progress.started_at.isoformat() if progress.started_at else None,
                    "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
                    "summary": progress.summary,
                    "tokens": progress.usage.total_tokens,
                    "cost": progress.cost.total_cost,
                    "error": progress.error,
                }
                for phase, progress in self._phase_progress.items()
            }
        }
        summary_file = self._output_manager.base_path / "workflow_summary.json"
        summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        logger.info(f"Saved workflow summary to {summary_file}")
    def report_progress(
        self,
        phase: Optional[PhaseType],
        status: str,
        message: str
    ) -> None:
        """
        Report progress to user (only orchestrator emits progress).
        Args:
            phase: Current phase (None for workflow-level messages)
            status: Status indicator
            message: Progress message
        """
        if phase:
            prefix = f"[{phase.value.upper()}]"
        else:
            prefix = "[WORKFLOW]"
        formatted_message = f"{prefix} {status}: {message}"
        print(formatted_message, flush=True)
        logger.info(formatted_message)
        # Trigger callback
        self._on_progress(phase, status, message)
    def get_phase_progress(self, phase: PhaseType) -> Optional[PhaseProgress]:
        """Get progress for specific phase."""
        return self._phase_progress.get(phase)
    def get_workflow_metrics(self) -> WorkflowMetrics:
        """Get aggregate workflow metrics."""
        return self._workflow_metrics
    def _default_on_progress(
        self,
        phase: Optional[PhaseType],
        status: str,
        message: str
    ) -> None:
        """Default progress callback (logging only)."""
        # Progress already logged in report_progress()
        pass
    def _default_on_phase_complete(self, progress: PhaseProgress) -> None:
        """Default phase completion callback."""
        logger.info(
            f"Phase {progress.phase.value} complete - "
            f"tokens: {progress.usage.total_tokens}, "
            f"cost: ${progress.cost.total_cost:.4f}"
        )
# ============================================================================
# USAGE EXAMPLES
# ============================================================================
def example_basic_workflow():
    """Basic streaming orchestration workflow."""
    orchestrator = StreamingOrchestrator(
        session_id="example-workflow-001",
    )
    result = orchestrator.execute_workflow(
        task="Create a simple Python REST API with authentication",
        phases=[
            PhaseType.PLANNING,
            PhaseType.IMPLEMENTATION,
            PhaseType.TESTING,
        ]
    )
    print(f"\nWorkflow completed!")
    print(f"Total tokens: {result.usage.total_tokens}")
    print(f"Total cost: ${result.cost.total_cost:.4f}")
    print(f"Duration: {result.duration_ms/1000:.1f}s")
    print(f"Outputs saved to: {result.artifacts[0]}")
def example_custom_callbacks():
    """Workflow with custom progress tracking."""
    progress_log = []
    def track_progress(phase, status, message):
        progress_log.append({
            "timestamp": datetime.now().isoformat(),
            "phase": phase.value if phase else "workflow",
            "status": status,
            "message": message,
        })
    def on_phase_done(progress):
        print(f"\n {progress.phase.value} finished: {progress.summary}")
    orchestrator = StreamingOrchestrator(
        session_id="tracked-workflow",
        on_progress=track_progress,
        on_phase_complete=on_phase_done,
    )
    result = orchestrator.execute_workflow(
        task="Build a data processing pipeline",
        phases=[PhaseType.PLANNING, PhaseType.IMPLEMENTATION]
    )
    # Export progress log
    log_file = Path("outputs") / "tracked-workflow" / "progress.json"
    log_file.write_text(json.dumps(progress_log, indent=2))
    print(f"\nProgress log saved to: {log_file}")
def example_resume_from_checkpoint():
    """Resume workflow from saved checkpoint."""
    # First execution (may fail mid-workflow)
    orchestrator1 = StreamingOrchestrator(session_id="resumable-001")
    try:
        orchestrator1.execute_workflow(
            task="Complex multi-phase task",
            phases=[
                PhaseType.PLANNING,
                PhaseType.IMPLEMENTATION,
                PhaseType.REVIEW,
                PhaseType.TESTING,
            ]
        )
    except Exception as e:
        print(f"Workflow interrupted: {e}")
        # Checkpoint is automatically saved per phase
    # Resume from checkpoint (load previous outputs)
    orchestrator2 = StreamingOrchestrator(
        session_id="resumable-001", # Same session ID
    )
    # Load previous progress
    output_manager = OutputManager(Path("outputs") / "resumable-001")
    completed_phases = []
    for phase in PhaseType:
        if output_manager.load_phase_output(phase):
            completed_phases.append(phase)
    # Resume from next phase
    remaining_phases = [p for p in PhaseType if p not in completed_phases]
    if remaining_phases:
        print(f"Resuming from phase: {remaining_phases[0].value}")
        orchestrator2.execute_workflow(
            task="Continue complex task",
            phases=remaining_phases
        )
if __name__ == "__main__":
    # Run basic example
    example_basic_workflow()
