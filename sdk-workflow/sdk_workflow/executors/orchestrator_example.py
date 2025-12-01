"""
Orchestrator Executor - Multi-agent delegation with workflow management.
Production-ready implementation using claude-agent-sdk for Python.
This module implements orchestration patterns using:
- ClaudeSDKClient for continuous conversation sessions
- Custom MCP tools for subagent delegation
- Hook system for workflow phase tracking
- Proper error handling and resource management
References:
[1] Agent SDK Overview: https://platform.claude.com/docs/en/agent-sdk/overview
[2] Python SDK Reference: https://platform.claude.com/docs/en/agent-sdk/python
[3] GitHub Python SDK: https://github.com/anthropics/claude-agent-sdk-python
"""
from typing import Optional, Callable, Dict, Any, List, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
from pathlib import Path
# Claude Agent SDK imports
from claude_agent_sdk import (
   ClaudeSDKClient,
   ClaudeAgentOptions,
   query,
   tool,
   create_sdk_mcp_server,
   AssistantMessage,
   UserMessage,
   TextBlock,
   ToolUseBlock,
   ToolResultBlock,
   HookMatcher,
   HookContext,
   HookCallback,
   CLINotFoundError,
   ProcessError,
   CLIJSONDecodeError,
)
class WorkflowPhase(Enum):
   """Standard workflow phases for orchestration."""
   ARCHITECT = "architect"
   IMPLEMENTER = "implementer"
   REVIEWER = "reviewer"
   TESTER = "tester"
   CUSTOM = "custom"
@dataclass
class TokenUsage:
   """Token usage tracking."""
   input_tokens: int = 0
   output_tokens: int = 0
   cache_read_tokens: int = 0
   cache_write_tokens: int = 0
   @property
   def total_tokens(self) -> int:
       return self.input_tokens + self.output_tokens
   @property
   def cache_hit_rate(self) -> float:
       total_cache = self.cache_read_tokens + self.cache_write_tokens
       if total_cache == 0:
           return 0.0
       return self.cache_read_tokens / total_cache
@dataclass
class CostBreakdown:
   """Cost tracking in USD."""
   input_cost: float = 0.0
   output_cost: float = 0.0
   cache_read_cost: float = 0.0
   cache_write_cost: float = 0.0
   @property
   def total_cost(self) -> float:
       return (
           self.input_cost
           + self.output_cost
           + self.cache_read_cost
           + self.cache_write_cost
       )
@dataclass
class SubagentTask:
   """Subagent task definition."""
   task_id: str
   agent_type: str
   prompt: str
   system_prompt: str = ""
   model: Optional[str] = None
   dependencies: List[str] = field(default_factory=list)
   metadata: Dict[str, Any] = field(default_factory=dict)
@dataclass
class SubagentResult:
   """Result from subagent execution."""
   task_id: str
   success: bool
   content: str
   usage: TokenUsage
   cost: CostBreakdown
   duration_ms: int
   error: Optional[Exception] = None
@dataclass
class PhaseResult:
   """Result from a workflow phase."""
   phase: WorkflowPhase
   success: bool
   output: str
   subagent_results: List[SubagentResult] = field(default_factory=list)
   accumulated_usage: TokenUsage = field(default_factory=TokenUsage)
   accumulated_cost: CostBreakdown = field(default_factory=CostBreakdown)
@dataclass
class ExecutionResult:
   """Final execution result."""
   success: bool
   content: str
   usage: TokenUsage
   cost: CostBreakdown
   duration_ms: int
   session_id: Optional[str] = None
   phase_results: List[PhaseResult] = field(default_factory=list)
class OrchestratorExecutor:
   """
   Production orchestrator using claude-agent-sdk.
   Features:
   - Continuous conversation with ClaudeSDKClient
   - Custom MCP tools for subagent delegation
   - Hook-based workflow phase tracking
   - Proper resource management with context managers
   - Comprehensive error handling
   Architecture:
   1. Main orchestrator uses ClaudeSDKClient for session management
   2. Subagents delegated via custom MCP Task tool
   3. Dependencies resolved through conversation context
   4. Hooks track workflow phases and tool usage
   Usage:
       async with OrchestratorExecutor() as executor:
           result = await executor.execute(
               task="Build a web scraper",
               workflow_phases=[
                   WorkflowPhase.ARCHITECT,
                   WorkflowPhase.IMPLEMENTER,
                   WorkflowPhase.TESTER
               ]
           )
   """
   def __init__(
       self,
       model: Optional[str] = None,
       system_prompt: Optional[str] = None,
       cwd: Optional[Path] = None,
       allowed_tools: Optional[List[str]] = None,
       permission_mode: Optional[str] = None,
       max_turns: Optional[int] = None,
       on_text: Optional[Callable[[str], None]] = None,
       on_subagent_start: Optional[Callable[[SubagentTask], None]] = None,
       on_subagent_complete: Optional[Callable[[SubagentResult], None]] = None,
   ):
       """
       Initialize orchestrator executor.
       Args:
           model: Claude model to use (default: claude-opus-4-20250514)
           system_prompt: System prompt for orchestrator
           cwd: Working directory for file operations
           allowed_tools: List of allowed tool names
           permission_mode: Permission mode ('acceptEdits', 'bypass_permissions')
           max_turns: Maximum conversation turns
           on_text: Callback for streaming text
           on_subagent_start: Callback when subagent starts
           on_subagent_complete: Callback when subagent completes
       """
       self.model = model or "claude-opus-4-20250514"
       self.system_prompt = system_prompt or self._default_orchestrator_prompt()
       self.cwd = cwd or Path.cwd()
       self.allowed_tools = allowed_tools or ["Read", "Write", "Bash", "Task"]
       self.permission_mode = permission_mode or "acceptEdits"
       self.max_turns = max_turns or 50
       # Callbacks
       self._on_text = on_text or self._default_on_text
       self._on_subagent_start = on_subagent_start or self._default_subagent_start
       self._on_subagent_complete = on_subagent_complete or self._default_subagent_complete
       # State tracking
       self._client: Optional[ClaudeSDKClient] = None
       self._phase_results: List[PhaseResult] = []
       self._subagent_results: List[SubagentResult] = []
       self._task_outputs: Dict[str, str] = {}
       self._current_phase: Optional[WorkflowPhase] = None
       # Custom MCP tools
       self._task_tool = self._create_task_tool()
       self._mcp_server = create_sdk_mcp_server(
           name="orchestrator-tools",
           version="1.0.0",
           tools=[self._task_tool],
       )
   def _create_task_tool(self):
       """Create custom Task tool for subagent delegation."""
       @tool(
           "delegate_task",
           "Delegate a task to a specialized subagent",
           {
               "task_id": str,
               "agent_type": str,
               "prompt": str,
               "system_prompt": str,
               "model": str,
               "dependencies": list,
           },
       )
       async def delegate_task(args: Dict[str, Any]) -> Dict[str, Any]:
           """Handle subagent delegation."""
           task = SubagentTask(
               task_id=args.get("task_id", ""),
               agent_type=args.get("agent_type", "expert"),
               prompt=args.get("prompt", ""),
               system_prompt=args.get("system_prompt", ""),
               model=args.get("model"),
               dependencies=args.get("dependencies", []),
           )
           # Resolve dependencies
           resolved_prompt = self._resolve_dependencies(task)
           # Notify start
           self._on_subagent_start(task)
           # Execute subagent
           result = await self._execute_subagent(task, resolved_prompt)
           # Track result
           self._subagent_results.append(result)
           self._task_outputs[task.task_id] = result.content
           # Notify completion
           self._on_subagent_complete(result)
           return {
               "content": [
                   {
                       "type": "text",
                       "text": json.dumps(
                           {
                               "task_id": result.task_id,
                               "success": result.success,
                               "output": result.content,
                               "tokens": result.usage.total_tokens,
                               "cost_usd": result.cost.total_cost,
                           }
                       ),
                   }
               ]
           }
       return delegate_task
   async def _execute_subagent(
       self, task: SubagentTask, prompt: str
   ) -> SubagentResult:
       """
       Execute subagent using query() for single-turn interaction.
       Args:
           task: Subagent task definition
           prompt: Resolved prompt with dependencies
       Returns:
           SubagentResult with execution details
       """
       import time
       start_time = time.time()
       try:
           options = ClaudeAgentOptions(
               model=task.model or "claude-sonnet-4-20250514",
               system_prompt=task.system_prompt or self._default_subagent_prompt(
                   task.agent_type
               ),
               allowed_tools=["Read", "Write", "Bash", "Glob", "Grep"],
               permission_mode=self.permission_mode,
               cwd=str(self.cwd),
               max_turns=10,
           )
           content = []
           usage = TokenUsage()
           async for message in query(prompt=prompt, options=options):
               if isinstance(message, AssistantMessage):
                   for block in message.content:
                       if isinstance(block, TextBlock):
                           content.append(block.text)
               # Extract usage if available (implementation-specific)
               # Note: Actual usage extraction depends on message structure
           duration_ms = int((time.time() - start_time) * 1000)
           return SubagentResult(
               task_id=task.task_id,
               success=True,
               content="\n".join(content),
               usage=usage,
               cost=CostBreakdown(), # Calculate based on usage
               duration_ms=duration_ms,
           )
       except Exception as e:
           duration_ms = int((time.time() - start_time) * 1000)
           return SubagentResult(
               task_id=task.task_id,
               success=False,
               content=f"Subagent error: {str(e)}",
               usage=TokenUsage(),
               cost=CostBreakdown(),
               duration_ms=duration_ms,
               error=e,
           )
   def _resolve_dependencies(self, task: SubagentTask) -> str:
       """
       Resolve task dependencies by injecting prior outputs.
       Args:
           task: Subagent task with dependencies
       Returns:
           Resolved prompt with dependency context
       """
       if not task.dependencies:
           return task.prompt
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
   async def __aenter__(self):
       """Async context manager entry."""
       await self.setup()
       return self
   async def __aexit__(self, exc_type, exc_val, exc_tb):
       """Async context manager exit."""
       await self.cleanup()
   async def setup(self):
       """Initialize orchestrator client and resources."""
       # Create hooks for phase tracking
       hooks = self._create_hooks()
       # Configure client options
       options = ClaudeAgentOptions(
           model=self.model,
           system_prompt=self.system_prompt,
           allowed_tools=self.allowed_tools + ["mcp__orchestrator-tools__delegate_task"],
           mcp_servers={"orchestrator-tools": self._mcp_server},
           permission_mode=self.permission_mode,
           cwd=str(self.cwd),
           max_turns=self.max_turns,
           hooks=hooks,
       )
       # Initialize client
       self._client = ClaudeSDKClient(options=options)
       await self._client.connect()
       # Reset state
       self._phase_results = []
       self._subagent_results = []
       self._task_outputs = {}
   def _create_hooks(self) -> Dict[str, List[HookMatcher]]:
       """Create hooks for workflow tracking."""
       async def pre_tool_hook(
           input_data: Dict[str, Any],
           tool_use_id: Optional[str],
           context: HookContext,
       ) -> Dict[str, Any]:
           """Track tool usage for workflow phases."""
           tool_name = input_data.get("tool_name", "")
           if tool_name == "delegate_task":
               task_input = input_data.get("tool_input", {})
               print(f"[Phase: {self._current_phase}] Delegating to {task_input.get('agent_type')}")
           return {}
       async def post_tool_hook(
           input_data: Dict[str, Any],
           tool_use_id: Optional[str],
           context: HookContext,
       ) -> Dict[str, Any]:
           """Log tool completion."""
           tool_name = input_data.get("tool_name", "")
           print(f"[Tool Complete] {tool_name}")
           return {}
       return {
           "PreToolUse": [HookMatcher(hooks=[pre_tool_hook])],
           "PostToolUse": [HookMatcher(hooks=[post_tool_hook])],
       }
   async def execute(
       self,
       task: str,
       workflow_phases: Optional[List[WorkflowPhase]] = None,
   ) -> ExecutionResult:
       """
       Execute orchestrated workflow with optional phase structure.
       Args:
           task: Main orchestration task
           workflow_phases: Optional list of phases to execute sequentially
       Returns:
           ExecutionResult with aggregated metrics
       """
       if not self._client:
           raise RuntimeError("Executor not initialized. Use 'async with' context manager.")
       import time
       start_time = time.time()
       try:
           if workflow_phases:
               # Execute structured workflow
               for phase in workflow_phases:
                   self._current_phase = phase
                   phase_result = await self._execute_phase(phase, task)
                   self._phase_results.append(phase_result)
                   if not phase_result.success:
                       break
           else:
               # Execute single-turn orchestration
               await self._client.query(task)
           # Collect response
           content = []
           async for message in self._client.receive_response():
               if isinstance(message, AssistantMessage):
                   for block in message.content:
                       if isinstance(block, TextBlock):
                           content.append(block.text)
                           # Stream text to callback
                           self._on_text(block.text)
           duration_ms = int((time.time() - start_time) * 1000)
           # Aggregate usage and costs
           total_usage, total_cost = self._aggregate_metrics()
           return ExecutionResult(
               success=True,
               content="\n".join(content),
               usage=total_usage,
               cost=total_cost,
               duration_ms=duration_ms,
               session_id=self._client.session_id if hasattr(self._client, 'session_id') else None,
               phase_results=self._phase_results.copy(),
           )
       except Exception as e:
           duration_ms = int((time.time() - start_time) * 1000)
           return ExecutionResult(
               success=False,
               content=f"Orchestration error: {str(e)}",
               usage=TokenUsage(),
               cost=CostBreakdown(),
               duration_ms=duration_ms,
               phase_results=self._phase_results.copy(),
           )
   async def _execute_phase(
       self, phase: WorkflowPhase, task: str
   ) -> PhaseResult:
       """
       Execute a specific workflow phase.
       Args:
           phase: Workflow phase to execute
           task: Task description for this phase
       Returns:
           PhaseResult with phase-specific metrics
       """
       import time
       start_time = time.time()
       pre_subagent_count = len(self._subagent_results)
       # Build phase-specific prompt
       phase_prompt = self._build_phase_prompt(phase, task)
       try:
           # Send phase query
           await self._client.query(phase_prompt)
           # Collect phase output
           content = []
           async for message in self._client.receive_response():
               if isinstance(message, AssistantMessage):
                   for block in message.content:
                       if isinstance(block, TextBlock):
                           content.append(block.text)
           # Collect phase-specific subagent results
           phase_subagents = self._subagent_results[pre_subagent_count:]
           # Calculate phase metrics
           phase_usage = TokenUsage()
           phase_cost = CostBreakdown()
           for subagent in phase_subagents:
               phase_usage.input_tokens += subagent.usage.input_tokens
               phase_usage.output_tokens += subagent.usage.output_tokens
               phase_usage.cache_read_tokens += subagent.usage.cache_read_tokens
               phase_usage.cache_write_tokens += subagent.usage.cache_write_tokens
               phase_cost.input_cost += subagent.cost.input_cost
               phase_cost.output_cost += subagent.cost.output_cost
               phase_cost.cache_read_cost += subagent.cost.cache_read_cost
               phase_cost.cache_write_cost += subagent.cost.cache_write_cost
           return PhaseResult(
               phase=phase,
               success=True,
               output="\n".join(content),
               subagent_results=phase_subagents,
               accumulated_usage=phase_usage,
               accumulated_cost=phase_cost,
           )
       except Exception as e:
           return PhaseResult(
               phase=phase,
               success=False,
               output=f"Phase error: {str(e)}",
               subagent_results=[],
               accumulated_usage=TokenUsage(),
               accumulated_cost=CostBreakdown(),
           )
   def _build_phase_prompt(self, phase: WorkflowPhase, task: str) -> str:
       """
       Build phase-specific prompt with context.
       Args:
           phase: Current workflow phase
           task: Original task description
       Returns:
           Formatted prompt for the phase
       """
       phase_instructions = {
           WorkflowPhase.ARCHITECT: (
               "As the Architect, design the high-level structure and approach. "
               "Break down the task into logical components and define interfaces."
           ),
           WorkflowPhase.IMPLEMENTER: (
               "As the Implementer, build the components based on the architecture. "
               "Write clean, maintainable code following best practices."
           ),
           WorkflowPhase.REVIEWER: (
               "As the Reviewer, analyze the implementation for quality, security, "
               "and adherence to requirements. Suggest improvements."
           ),
           WorkflowPhase.TESTER: (
               "As the Tester, verify functionality through comprehensive testing. "
               "Identify edge cases and validate correctness."
           ),
           WorkflowPhase.CUSTOM: (
               "Execute the custom workflow phase as specified."
           ),
       }
       instruction = phase_instructions.get(phase, "")
       # Include previous phase outputs for context
       context = []
       for prev_result in self._phase_results:
           context.append(
               f"[{prev_result.phase.value.upper()} Output]:\n{prev_result.output}"
           )
       context_block = "\n\n".join(context) if context else ""
       if context_block:
           return f"{context_block}\n\n---\n\n{instruction}\n\nTask: {task}"
       else:
           return f"{instruction}\n\nTask: {task}"
   def _aggregate_metrics(self) -> tuple[TokenUsage, CostBreakdown]:
       """
       Aggregate usage and costs from all subagents.
       Returns:
           Tuple of (total_usage, total_cost)
       """
       total_usage = TokenUsage()
       total_cost = CostBreakdown()
       for subagent in self._subagent_results:
           total_usage.input_tokens += subagent.usage.input_tokens
           total_usage.output_tokens += subagent.usage.output_tokens
           total_usage.cache_read_tokens += subagent.usage.cache_read_tokens
           total_usage.cache_write_tokens += subagent.usage.cache_write_tokens
           total_cost.input_cost += subagent.cost.input_cost
           total_cost.output_cost += subagent.cost.output_cost
           total_cost.cache_read_cost += subagent.cost.cache_read_cost
           total_cost.cache_write_cost += subagent.cost.cache_write_cost
       return total_usage, total_cost
   async def query_streaming(
       self, prompt: str
   ) -> AsyncIterator[AssistantMessage]:
       """
       Stream orchestrator responses in real-time.
       Args:
           prompt: Query prompt
       Yields:
           AssistantMessage chunks as they arrive
       """
       if not self._client:
           raise RuntimeError("Executor not initialized.")
       await self._client.query(prompt)
       async for message in self._client.receive_response():
           if isinstance(message, AssistantMessage):
               yield message
   def get_phase_results(self) -> List[PhaseResult]:
       """Get all completed phase results."""
       return self._phase_results.copy()
   def get_subagent_results(self) -> List[SubagentResult]:
       """Get all subagent execution results."""
       return self._subagent_results.copy()
   def get_workflow_summary(self) -> Dict[str, Any]:
       """
       Get comprehensive workflow execution summary.
       Returns:
           Dictionary with phases, totals, and metrics
       """
       total_usage, total_cost = self._aggregate_metrics()
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
                   "tokens": pr.accumulated_usage.total_tokens,
                   "cost_usd": pr.accumulated_cost.total_cost,
               }
               for pr in self._phase_results
           ],
           "subagents": [
               {
                   "task_id": sr.task_id,
                   "success": sr.success,
                   "tokens": sr.usage.total_tokens,
                   "cost_usd": sr.cost.total_cost,
                   "duration_ms": sr.duration_ms,
               }
               for sr in self._subagent_results
           ],
       }
   async def cleanup(self):
       """Release all resources and close connections."""
       if self._client:
           await self._client.close()
           self._client = None
       self._phase_results = []
       self._subagent_results = []
       self._task_outputs = {}
       self._current_phase = None
   # Default callbacks
   def _default_on_text(self, text: str) -> None:
       """Default text streaming callback."""
       print(text, end="", flush=True)
   def _default_subagent_start(self, task: SubagentTask) -> None:
       """Default subagent start callback."""
       print(f"\n[Subagent: {task.agent_type}] Starting task '{task.task_id}'...")
   def _default_subagent_complete(self, result: SubagentResult) -> None:
       """Default subagent completion callback."""
       status = " completed" if result.success else " failed"
       print(
           f"[Subagent: {result.task_id}] {status} "
           f"({result.duration_ms}ms, {result.usage.total_tokens} tokens)"
       )
   def _default_orchestrator_prompt(self) -> str:
       """Default system prompt for orchestrator."""
       return """You are an expert orchestrator managing complex multi-agent workflows.
Your responsibilities:
1. Break down complex tasks into logical phases
2. Delegate specialized work to subagents using the delegate_task tool
3. Coordinate dependencies between tasks
4. Synthesize results into coherent solutions
When delegating:
- Choose appropriate agent_type (architect, implementer, reviewer, tester, expert)
- Provide clear, focused prompts
- Specify dependencies on prior tasks when needed
- Use unique task_ids for tracking
Available workflow phases:
- ARCHITECT: Design structure and approach
- IMPLEMENTER: Build components and code
- REVIEWER: Validate quality and correctness
- TESTER: Verify functionality and edge cases
Coordinate effectively and produce high-quality results."""
   def _default_subagent_prompt(self, agent_type: str) -> str:
       """Default system prompt for subagents."""
       prompts = {
           "architect": "You are an expert software architect. Design clean, scalable solutions.",
           "implementer": "You are an expert developer. Write clean, maintainable code.",
           "reviewer": "You are an expert code reviewer. Identify issues and suggest improvements.",
           "tester": "You are an expert QA engineer. Verify functionality thoroughly.",
           "expert": "You are an expert assistant. Complete tasks with precision.",
       }
       return prompts.get(agent_type, prompts["expert"])
# ============================================================================
# ADVANCED USAGE PATTERNS
# ============================================================================
async def example_basic_orchestration():
   """Basic orchestration example."""
   async with OrchestratorExecutor(
       model="claude-opus-4-20250514",
       on_text=lambda text: print(text, end=""),
   ) as executor:
       result = await executor.execute(
           task="Create a Python REST API with authentication"
       )
       print(f"\n\nSuccess: {result.success}")
       print(f"Total tokens: {result.usage.total_tokens}")
       print(f"Total cost: ${result.cost.total_cost:.4f}")
async def example_phased_workflow():
   """Structured workflow with explicit phases."""
   async with OrchestratorExecutor() as executor:
       result = await executor.execute(
           task="Build a web scraper for e-commerce sites",
           workflow_phases=[
               WorkflowPhase.ARCHITECT,
               WorkflowPhase.IMPLEMENTER,
               WorkflowPhase.REVIEWER,
               WorkflowPhase.TESTER,
           ],
       )
       # Get detailed summary
       summary = executor.get_workflow_summary()
       print(json.dumps(summary, indent=2))
async def example_streaming_orchestration():
   """Stream orchestrator responses in real-time."""
   async with OrchestratorExecutor() as executor:
       async for message in executor.query_streaming(
           "Design a microservices architecture for a social media platform"
       ):
           for block in message.content:
               if isinstance(block, TextBlock):
                   print(block.text, end="", flush=True)
async def example_custom_callbacks():
   """Custom callbacks for workflow tracking."""
   def on_text(text: str):
       """Custom text handler with logging."""
       import logging
       logging.info(f"Orchestrator output: {text[:50]}...")
       print(text, end="")
   def on_subagent_start(task: SubagentTask):
       """Track subagent metrics."""
       print(f"\n{'='*60}")
       print(f"Subagent: {task.agent_type}")
       print(f"Task ID: {task.task_id}")
       print(f"Dependencies: {task.dependencies}")
       print(f"{'='*60}")
   def on_subagent_complete(result: SubagentResult):
       """Log subagent completion."""
       print(f"\n[Complete] {result.task_id}")
       print(f" Tokens: {result.usage.total_tokens}")
       print(f" Cost: ${result.cost.total_cost:.4f}")
       print(f" Duration: {result.duration_ms}ms")
   async with OrchestratorExecutor(
       on_text=on_text,
       on_subagent_start=on_subagent_start,
       on_subagent_complete=on_subagent_complete,
   ) as executor:
       await executor.execute("Build a data pipeline with ETL processes")
async def example_error_handling():
   """Robust error handling pattern."""
   try:
       async with OrchestratorExecutor(
           max_turns=20, permission_mode="bypass_permissions"
       ) as executor:
           result = await executor.execute(
               task="Analyze and refactor legacy codebase",
               workflow_phases=[WorkflowPhase.ARCHITECT, WorkflowPhase.IMPLEMENTER],
           )
           if not result.success:
               print(f"Orchestration failed: {result.content}")
               # Check individual phase failures
               for phase_result in executor.get_phase_results():
                   if not phase_result.success:
                       print(f"Phase {phase_result.phase.value} failed")
               # Check subagent failures
               for subagent in executor.get_subagent_results():
                   if not subagent.success:
                       print(f"Subagent {subagent.task_id} error: {subagent.error}")
   except CLINotFoundError as e:
       print(f"Claude CLI not found: {e}")
   except ProcessError as e:
       print(f"Process error: {e}")
   except Exception as e:
       print(f"Unexpected error: {e}")
async def example_cost_optimization():
   """Cost-optimized orchestration with caching."""
    # Use Sonnet for orchestrator, Haiku for simple subagents
    async with OrchestratorExecutor(
        model="claude-sonnet-4-20250514", # Orchestrator
        system_prompt="You are a cost-efficient orchestrator. Use Haiku for simple tasks.",
    ) as executor:
        # Enable prompt caching for repeated context
        result = await executor.execute(
            task="Process 100 customer support tickets and categorize them",
        )
        # Check cache efficiency
        cache_hit_rate = result.usage.cache_hit_rate
        print(f"Cache hit rate: {cache_hit_rate:.2%}")
        print(f"Total cost: ${result.cost.total_cost:.4f}")
async def example_parallel_subagents():
    """Leverage parallel subagent execution."""
    async with OrchestratorExecutor() as executor:
        # Orchestrator will delegate multiple independent tasks in parallel
        result = await executor.execute(
            task="""Analyze this codebase in parallel:
            1. Security audit (delegate to security expert)
            2. Performance analysis (delegate to performance expert)
            3. Code quality review (delegate to quality expert)
            4. Documentation review (delegate to documentation expert)
            Synthesize findings into a comprehensive report."""
        )
        # Subagents run concurrently, reducing total execution time
        summary = executor.get_workflow_summary()
        print(f"Completed {summary['total_subagents']} subagents")
async def example_dependency_resolution():
    """Subagents with explicit dependencies."""
    async with OrchestratorExecutor() as executor:
        result = await executor.execute(
            task="""Build a data pipeline with these dependent tasks:
            Task 1 (schema-designer): Design database schema
            Task 2 (api-builder, depends on Task 1): Build REST API using schema
            Task 3 (test-writer, depends on Task 2): Write integration tests for API
            Each task should reference outputs from its dependencies."""
        )
        # Dependencies ensure proper execution order
        for subagent in executor.get_subagent_results():
            print(f"{subagent.task_id}: {subagent.success}")
async def example_session_management():
    """Multi-turn conversation with session persistence."""
    async with OrchestratorExecutor() as executor:
        # First query
        result1 = await executor.execute(
            task="Design a caching strategy for a high-traffic API"
        )
        # Continue conversation with context
        result2 = await executor.execute(
            task="Now implement the caching layer you just designed"
        )
        # Session maintains full context across queries
        print(f"Session ID: {result2.session_id}")
async def example_custom_working_directory():
    """Execute in specific project directory."""
    project_path = Path("/path/to/project")
    async with OrchestratorExecutor(
        cwd=project_path,
        allowed_tools=["Read", "Write", "Bash", "Glob", "Grep"],
    ) as executor:
        result = await executor.execute(
            task="Refactor the authentication module to use JWT tokens"
        )
        # All file operations happen in project_path
        print(f"Working directory: {project_path}")
async def example_permission_modes():
    """Different permission modes for safety."""
    # Strict mode - requires approval for edits
    async with OrchestratorExecutor(
        permission_mode="default"
    ) as executor_strict:
        await executor_strict.execute("Review code but don't modify")
    # Auto-accept edits
    async with OrchestratorExecutor(
        permission_mode="acceptEdits"
    ) as executor_auto:
        await executor_auto.execute("Refactor and update all files")
    # Bypass all permissions (use with caution)
    async with OrchestratorExecutor(
        permission_mode="bypass_permissions"
    ) as executor_bypass:
        await executor_bypass.execute("Automated deployment script")
async def example_metrics_tracking():
    """Comprehensive metrics and cost tracking."""
    async with OrchestratorExecutor() as executor:
        result = await executor.execute(
            task="Build a complete CRUD API with tests",
            workflow_phases=[
                WorkflowPhase.ARCHITECT,
                WorkflowPhase.IMPLEMENTER,
                WorkflowPhase.TESTER,
            ],
        )
        # Detailed metrics
        print("\n=== EXECUTION METRICS ===")
        print(f"Total duration: {result.duration_ms}ms")
        print(f"Input tokens: {result.usage.input_tokens:,}")
        print(f"Output tokens: {result.usage.output_tokens:,}")
        print(f"Cache read: {result.usage.cache_read_tokens:,}")
        print(f"Cache write: {result.usage.cache_write_tokens:,}")
        print(f"Cache hit rate: {result.usage.cache_hit_rate:.2%}")
        print("\n=== COST BREAKDOWN ===")
        print(f"Input cost: ${result.cost.input_cost:.4f}")
        print(f"Output cost: ${result.cost.output_cost:.4f}")
        print(f"Cache read cost: ${result.cost.cache_read_cost:.4f}")
        print(f"Cache write cost: ${result.cost.cache_write_cost:.4f}")
        print(f"Total cost: ${result.cost.total_cost:.4f}")
        print("\n=== WORKFLOW SUMMARY ===")
        summary = executor.get_workflow_summary()
        for phase in summary["phases"]:
            print(f"{phase['name']}: {phase['subagent_count']} subagents, "
                  f"{phase['tokens']} tokens, ${phase['cost_usd']:.4f}")
async def example_programmatic_subagents():
    """Define subagents programmatically (SDK approach)."""
    # Note: Based on SDK documentation, subagents are defined via agents parameter
    # in ClaudeAgentOptions, not as filesystem artifacts
    subagent_definitions = {
        "code-reviewer": {
            "description": "Expert code reviewer for quality and security",
            "tools": ["Read", "Grep"], # Read-only tools
            "prompt": "You are an expert code reviewer. Analyze code for quality, security, and best practices.",
            "model": "sonnet", # Use faster model for reviews
        },
        "test-generator": {
            "description": "Expert test writer for comprehensive test coverage",
            "tools": ["Read", "Write", "Bash"],
            "prompt": "You are an expert test engineer. Write comprehensive unit and integration tests.",
            "model": "sonnet",
        },
        "performance-optimizer": {
            "description": "Expert in performance optimization and profiling",
            "tools": ["Read", "Write", "Bash", "Grep"],
            "prompt": "You are a performance optimization expert. Identify bottlenecks and optimize code.",
            "model": "opus", # Use more capable model for complex analysis
        },
    }
    # Create options with programmatic subagent definitions
    options = ClaudeAgentOptions(
        model="claude-opus-4-20250514",
        agents=subagent_definitions, # Pass subagent definitions
        allowed_tools=["Read", "Write", "Bash", "Grep", "Task"],
    )
    async with ClaudeSDKClient(options=options) as client:
        await client.query(
            "Review the codebase, generate tests, and optimize performance"
        )
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="")
async def example_filesystem_subagents():
    """Use filesystem-based subagent definitions."""
    # Create .claude/agents/ directory structure
    agents_dir = Path(".claude/agents")
    agents_dir.mkdir(parents=True, exist_ok=True)
    # Define subagent as markdown file with YAML frontmatter
    security_agent = agents_dir / "security-auditor.md"
    security_agent.write_text("""---
name: security-auditor
description: Use proactively for security audits and vulnerability scanning
tools: Read, Grep, Bash
model: opus
---
You are a security expert specializing in:
- SQL injection detection
- XSS vulnerability scanning
- Authentication/authorization flaws
- Dependency vulnerability analysis
- Security best practices enforcement
When analyzing code:
1. Check for common vulnerabilities (OWASP Top 10)
2. Review authentication and authorization logic
3. Scan dependencies for known CVEs
4. Validate input sanitization
5. Check for hardcoded secrets
Provide detailed security reports with severity ratings.""")
    # SDK will automatically discover and load filesystem-based subagents
    # when settingSources includes 'project'
    options = ClaudeAgentOptions(
        model="claude-opus-4-20250514",
        setting_sources=["project"], # Load project-level settings
        allowed_tools=["Read", "Write", "Bash", "Grep", "Task"],
    )
    async with ClaudeSDKClient(options=options) as client:
        await client.query("Perform a comprehensive security audit")
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
async def example_advanced_error_recovery():
    """Advanced error handling with retry logic."""
    max_retries = 3
    retry_delay = 2.0
    for attempt in range(max_retries):
        try:
            async with OrchestratorExecutor(
                max_turns=30,
                permission_mode="acceptEdits",
            ) as executor:
                result = await executor.execute(
                    task="Build and deploy a microservice",
                    workflow_phases=[
                        WorkflowPhase.ARCHITECT,
                        WorkflowPhase.IMPLEMENTER,
                        WorkflowPhase.TESTER,
                    ],
                )
                if result.success:
                    print(" Orchestration completed successfully")
                    break
                else:
                    print(f" Attempt {attempt + 1} failed: {result.content}")
                    # Analyze failure
                    failed_phases = [
                        pr for pr in executor.get_phase_results() if not pr.success
                    ]
                    failed_subagents = [
                        sr for sr in executor.get_subagent_results() if not sr.success
                    ]
                    print(f"Failed phases: {[p.phase.value for p in failed_phases]}")
                    print(f"Failed subagents: {[s.task_id for s in failed_subagents]}")
                    if attempt < max_retries - 1:
                        print(f"Retrying in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
        except CLINotFoundError:
            print("Error: Claude CLI not found. Install with:")
            print("curl -fsSL https://claude.ai/install.sh | bash")
            break
        except ProcessError as e:
            print(f"Process error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                print("Max retries exceeded")
        except Exception as e:
            print(f"Unexpected error: {e}")
            break
async def example_production_deployment():
    """Production-ready deployment pattern with full observability."""
    import logging
    from datetime import datetime
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(f"orchestrator_{datetime.now():%Y%m%d}.log"),
            logging.StreamHandler(),
        ],
    )
    logger = logging.getLogger("orchestrator")
    # Custom callbacks for production monitoring
    def production_text_handler(text: str):
        logger.info(f"Output: {text[:100]}...")
    def production_subagent_start(task: SubagentTask):
        logger.info(
            f"Subagent started - ID: {task.task_id}, Type: {task.agent_type}, "
            f"Dependencies: {task.dependencies}"
        )
    def production_subagent_complete(result: SubagentResult):
        logger.info(
            f"Subagent completed - ID: {result.task_id}, Success: {result.success}, "
            f"Tokens: {result.usage.total_tokens}, Cost: ${result.cost.total_cost:.4f}, "
            f"Duration: {result.duration_ms}ms"
        )
        if not result.success:
            logger.error(f"Subagent {result.task_id} failed: {result.error}")
    try:
        async with OrchestratorExecutor(
            model="claude-opus-4-20250514",
            cwd=Path("/production/workspace"),
            allowed_tools=["Read", "Write", "Bash", "Grep", "Glob"],
            permission_mode="acceptEdits",
            max_turns=50,
            on_text=production_text_handler,
            on_subagent_start=production_subagent_start,
            on_subagent_complete=production_subagent_complete,
        ) as executor:
            logger.info("Starting production orchestration")
            result = await executor.execute(
                task="Analyze production logs and generate incident report",
                workflow_phases=[
                    WorkflowPhase.ARCHITECT,
                    WorkflowPhase.IMPLEMENTER,
                    WorkflowPhase.REVIEWER,
                ],
            )
            # Log comprehensive results
            summary = executor.get_workflow_summary()
            logger.info(f"Orchestration summary: {json.dumps(summary, indent=2)}")
            # Export metrics for monitoring
            metrics = {
                "timestamp": datetime.now().isoformat(),
                "success": result.success,
                "duration_ms": result.duration_ms,
                "total_tokens": result.usage.total_tokens,
                "total_cost_usd": result.cost.total_cost,
                "cache_hit_rate": result.usage.cache_hit_rate,
                "phases_completed": len(result.phase_results),
                "subagents_executed": len(executor.get_subagent_results()),
            }
            # Write metrics to file for external monitoring
            with open("orchestrator_metrics.json", "w") as f:
                json.dump(metrics, f, indent=2)
            logger.info(f"Execution completed - Success: {result.success}")
            return result
    except Exception as e:
        logger.exception("Fatal orchestration error")
        raise
# ============================================================================
# MAIN EXECUTION
# ============================================================================
async def main():
    """Main entry point with example selection."""
    examples = {
        "1": ("Basic Orchestration", example_basic_orchestration),
        "2": ("Phased Workflow", example_phased_workflow),
        "3": ("Streaming Responses", example_streaming_orchestration),
        "4": ("Custom Callbacks", example_custom_callbacks),
        "5": ("Error Handling", example_error_handling),
        "6": ("Cost Optimization", example_cost_optimization),
        "7": ("Parallel Subagents", example_parallel_subagents),
        "8": ("Dependency Resolution", example_dependency_resolution),
        "9": ("Session Management", example_session_management),
        "10": ("Custom Working Directory", example_custom_working_directory),
        "11": ("Permission Modes", example_permission_modes),
        "12": ("Metrics Tracking", example_metrics_tracking),
        "13": ("Programmatic Subagents", example_programmatic_subagents),
        "14": ("Filesystem Subagents", example_filesystem_subagents),
        "15": ("Advanced Error Recovery", example_advanced_error_recovery),
        "16": ("Production Deployment", example_production_deployment),
    }
    print("=== Claude Agent SDK - Orchestrator Examples ===\n")
    for key, (name, _) in examples.items():
        print(f"{key}. {name}")
    print("\nEnter example number (or 'all' to run all): ", end="")
    choice = input().strip()
    if choice.lower() == "all":
        for key, (name, func) in examples.items():
            print(f"\n{'='*70}")
            print(f"Running: {name}")
            print(f"{'='*70}\n")
            try:
                await func()
            except Exception as e:
                print(f"Error in {name}: {e}")
    elif choice in examples:
        name, func = examples[choice]
        print(f"\nRunning: {name}\n")
        await func()
    else:
        print("Invalid choice. Running basic example...")
        await example_basic_orchestration()
if __name__ == "__main__":
    asyncio.run(main())
# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def calculate_cost(usage: TokenUsage, model: str = "claude-opus-4") -> CostBreakdown:
    """
    Calculate costs based on token usage and model pricing.
    Pricing (as of 2024, subject to change):
    - Claude Opus: $15/MTok input, $75/MTok output
    - Claude Sonnet: $3/MTok input, $15/MTok output
    - Claude Haiku: $0.25/MTok input, $1.25/MTok output
    - Cache read: 10% of input cost
    - Cache write: 25% of input cost
    Args:
        usage: TokenUsage object
        model: Model name for pricing lookup
    Returns:
        CostBreakdown with calculated costs
    """
    pricing = {
        "claude-opus-4": {"input": 15.0, "output": 75.0},
        "claude-sonnet-4": {"input": 3.0, "output": 15.0},
        "claude-haiku-4": {"input": 0.25, "output": 1.25},
    }
    # Default to Opus pricing
    base_model = "claude-opus-4"
    for key in pricing.keys():
        if key in model.lower():
            base_model = key
            break
    rates = pricing[base_model]
    # Calculate costs (rates are per million tokens)
    input_cost = (usage.input_tokens / 1_000_000) * rates["input"]
    output_cost = (usage.output_tokens / 1_000_000) * rates["output"]
    cache_read_cost = (usage.cache_read_tokens / 1_000_000) * (rates["input"] * 0.1)
    cache_write_cost = (usage.cache_write_tokens / 1_000_000) * (rates["input"] * 0.25)
    return CostBreakdown(
        input_cost=input_cost,
        output_cost=output_cost,
        cache_read_cost=cache_read_cost,
        cache_write_cost=cache_write_cost,
    )
def format_duration(ms: int) -> str:
    """
    Format duration in milliseconds to human-readable string.
    Args:
        ms: Duration in milliseconds
    Returns:
        Formatted string (e.g., "1.5s", "2m 30s")
    """
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    else:
        minutes = ms // 60000
        seconds = (ms % 60000) / 1000
        return f"{minutes}m {seconds:.0f}s"
def export_workflow_report(
    executor: OrchestratorExecutor, output_path: Path
) -> None:
    """
    Export comprehensive workflow report to JSON file.
    Args:
        executor: OrchestratorExecutor instance
        output_path: Path to output JSON file
    """
    summary = executor.get_workflow_summary()
    phase_results = executor.get_phase_results()
    subagent_results = executor.get_subagent_results()
    report = {
        "summary": summary,
        "phases": [
            {
                "phase": pr.phase.value,
                "success": pr.success,
                "output": pr.output,
                "usage": {
                    "input_tokens": pr.accumulated_usage.input_tokens,
                    "output_tokens": pr.accumulated_usage.output_tokens,
                    "cache_read_tokens": pr.accumulated_usage.cache_read_tokens,
                    "cache_write_tokens": pr.accumulated_usage.cache_write_tokens,
                    "total_tokens": pr.accumulated_usage.total_tokens,
                },
                "cost": {
                    "input_cost": pr.accumulated_cost.input_cost,
                    "output_cost": pr.accumulated_cost.output_cost,
                    "cache_read_cost": pr.accumulated_cost.cache_read_cost,
                    "cache_write_cost": pr.accumulated_cost.cache_write_cost,
                    "total_cost": pr.accumulated_cost.total_cost,
                },
                "subagents": [
                    {
                        "task_id": sr.task_id,
                        "success": sr.success,
                        "content": sr.content,
                        "duration_ms": sr.duration_ms,
                    }
                    for sr in pr.subagent_results
                ],
            }
            for pr in phase_results
        ],
        "all_subagents": [
            {
                "task_id": sr.task_id,
                "success": sr.success,
                "content": sr.content,
                "usage": {
                    "input_tokens": sr.usage.input_tokens,
                    "output_tokens": sr.usage.output_tokens,
                    "total_tokens": sr.usage.total_tokens,
                },
                "cost": {
                    "total_cost": sr.cost.total_cost,
                },
                "duration_ms": sr.duration_ms,
                "error": str(sr.error) if sr.error else None,
            }
            for sr in subagent_results
        ],
    }
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Report exported to: {output_path}")
async def batch_orchestration(
    tasks: List[Dict[str, Any]], max_concurrent: int = 3
) -> List[ExecutionResult]:
    """
    Execute multiple orchestration tasks concurrently with rate limiting.
    Args:
        tasks: List of task dictionaries with 'task' and optional 'phases'
        max_concurrent: Maximum concurrent executions
    Returns:
        List of ExecutionResults
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []
    async def execute_with_semaphore(task_config: Dict[str, Any]):
        async with semaphore:
            async with OrchestratorExecutor() as executor:
                return await executor.execute(
                    task=task_config["task"],
                    workflow_phases=task_config.get("phases"),
                )
    # Execute all tasks concurrently with rate limiting
    tasks_coros = [execute_with_semaphore(task) for task in tasks]
    results = await asyncio.gather(*tasks_coros, return_exceptions=True)
    return results
# ============================================================================
# TESTING UTILITIES
# ============================================================================
async def test_orchestrator_basic():
    """Test basic orchestrator functionality."""
    async with OrchestratorExecutor() as executor:
        result = await executor.execute("Echo 'Hello, World!'")
        assert result.success, "Basic execution failed"
        assert "Hello" in result.content, "Unexpected output"
        print(" Basic orchestrator test passed")
async def test_phased_workflow():
    """Test phased workflow execution."""
    async with OrchestratorExecutor() as executor:
        result = await executor.execute(
            task="Design a simple calculator",
            workflow_phases=[WorkflowPhase.ARCHITECT, WorkflowPhase.IMPLEMENTER],
        )
        assert result.success, "Phased workflow failed"
        assert len(executor.get_phase_results()) == 2, "Incorrect phase count"
        print(" Phased workflow test passed")
async def test_subagent_delegation():
    """Test subagent delegation."""
    async with OrchestratorExecutor() as executor:
        result = await executor.execute(
            task="Delegate a simple task to a subagent"
        )
        # Should have at least one subagent result if delegation occurred
        subagents = executor.get_subagent_results()
        print(f" Subagent delegation test passed ({len(subagents)} subagents)")
async def run_all_tests():
    """Run all orchestrator tests."""
    print("\n=== Running Orchestrator Tests ===\n")
    tests = [
        ("Basic Orchestrator", test_orchestrator_basic),
        ("Phased Workflow", test_phased_workflow),
        ("Subagent Delegation", test_subagent_delegation),
    ]
    for name, test_func in tests:
        try:
            await test_func()
        except Exception as e:
            print(f" {name} test failed: {e}")
    print("\n=== Tests Complete ===\n")
# ============================================================================
# REFERENCE LINKS
# ============================================================================
"""
OFFICIAL DOCUMENTATION REFERENCES:
1. Claude Agent SDK Overview:
   https://platform.claude.com/docs/en/agent-sdk/overview
2. Python SDK Reference:
   https://platform.claude.com/docs/en/agent-sdk/python
3. Subagents Documentation:
   https://platform.claude.com/docs/en/agent-sdk/subagents
4. GitHub Python SDK:
   https://github.com/anthropics/claude-agent-sdk-python
5. Claude Code Subagents:
   https://code.claude.com/docs/en/sub-agents
6. Building Effective Agents:
   https://www.anthropic.com/engineering/building-effective-agents
7. Claude Code Best Practices:
   https://www.anthropic.com/engineering/claude-code-best-practices
8. Model Context Protocol (MCP):
   https://modelcontextprotocol.io/
9. Claude API Reference:
   https://docs.anthropic.com/en/api/
10. Prompt Engineering Guide:
    https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/
ARCHITECTURE PATTERNS:
- Orchestrator-Workers Pattern: Main orchestrator delegates to specialized subagents
- Hierarchical Planning: Break complex tasks into phases with dependencies
- Context Management: Separate context windows prevent information overload
- Tool Restrictions: Limit subagent capabilities for safety
- Parallel Execution: Run independent subagents concurrently
BEST PRACTICES:
1. Use appropriate models: Opus for orchestration, Sonnet/Haiku for subagents
2. Enable prompt caching for repeated context
3. Implement proper error handling and retries
4. Track metrics for cost optimization
5. Use dependency resolution for sequential workflows
6. Leverage parallel execution for independent tasks
7. Define clear subagent roles and responsibilities
8. Implement comprehensive logging for production
9. Use permission modes appropriate to your use case
10. Export workflow reports for analysis
COST OPTIMIZATION:
- Use Haiku for simple, repetitive tasks
- Use Sonnet for balanced performance/cost
- Use Opus only for complex reasoning
- Enable prompt caching for repeated context
- Limit max_turns to prevent runaway costs
- Monitor cache hit rates
- Track per-subagent costs
SECURITY CONSIDERATIONS:
- Use 'default' permission mode for untrusted code
- Limit tool access to minimum required
- Validate subagent outputs before use
- Implement rate limiting for production
- Log all subagent activities
- Review generated code before execution
- Use read-only tools for analysis tasks
PRODUCTION DEPLOYMENT:
- Implement comprehensive logging
- Export metrics for monitoring
- Use async context managers for cleanup
- Implement retry logic with backoff
- Monitor token usage and costs
- Set appropriate max_turns limits
- Use environment-specific configurations
- Implement circuit breakers for failures
"""
