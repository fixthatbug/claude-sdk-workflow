# SDK-Workflow Resources Module
**Location**: `C:\Users\Ray\.claude\sdk-workflow\resources\`
Production-ready module providing agents, prompts, and tools for the SDK workflow orchestration system. Designed for optimal prompt caching with static base prompts and dynamic composition.
## Quick Start
```python
from resources import (
    # Agents
    get_agent, list_agents, create_agent,
    ARCHITECT, IMPLEMENTER, REVIEWER, TESTER,
    # Tools
    get_tool, developer_tools, orchestrator_tools,
    validate_tool_input,
    # Prompts
    compose_orchestrator_prompt, compose_subagent_prompt,
    PromptRegistry,
)
# Get a pre-configured agent
architect = get_agent('architect')
print(f"Agent: {architect.role}, Model: {architect.model}")
# Get tools for an agent
tools = developer_tools()  # Returns list of tool definitions in API format
# Compose a prompt with caching optimization
prompt = compose_orchestrator_prompt(
    task_context="Build a REST API with authentication",
    available_agents=['architect', 'implementer', 'tester']
)
```
## Module Structure
### 1. **agents.py** - Agent Registry (384 lines)
**Purpose**: Dynamic agent registration and management
**Key Classes**:
- `AgentDefinition`: Immutable agent configuration with name, role, system_prompt, model, tools
- `AgentRegistry`: Central registry for agents with class-level storage
**Default Agents** (7 total):
| Agent | Role | Model | Tools |
|-------|------|-------|-------|
| `architect` | System Architect | sonnet-4 | read_file, search_files |
| `implementer` | Software Developer | sonnet-4 | read_file, write_file, edit_file, bash, search_files |
| `reviewer` | Code Reviewer | haiku | read_file, search_files |
| `tester` | QA Engineer | haiku | read_file, write_file, bash, search_files |
| `researcher` | Technical Researcher | haiku | read_file, search_files |
| `debugger` | Debug Specialist | sonnet-4 | read_file, edit_file, bash, search_files |
| `documenter` | Technical Writer | haiku | read_file, write_file, search_files |
**Functions**:
```python
# Retrieve agents
get_agent(name: str) -> AgentDefinition
list_agents() -> list[str]
# Create custom agents
create_agent(
    name: str,
    role: str,
    system_prompt: str,
    model: str = "claude-haiku-4-5-20251001",
    tools: list[str] | None = None,
    register: bool = True
) -> AgentDefinition
# Registry methods
AgentRegistry.register(agent)
AgentRegistry.get(name)
AgentRegistry.list_all()
AgentRegistry.list_by_role(role)
AgentRegistry.unregister(name)
```
**Example**:
```python
# Use existing agent
implementer = get_agent('implementer')
# Create variant with different model
fast_implementer = implementer.with_model('claude-haiku-4-5-20251001')
# Create custom agent
perf_agent = create_agent(
    name='performance_optimizer',
    role='Performance Engineer',
    system_prompt='Optimize code for performance...',
    model='claude-sonnet-4-20250514',
    tools=['read_file', 'search_files', 'bash']
)
```
---
### 2. **prompts.py** - Static Cacheable Prompts (477 lines)
**Purpose**: System prompts optimized for 90% cache reuse
**Design Pattern**: Static base + dynamic suffix for optimal caching
**Core Prompts**:
- `ORCHESTRATOR_PROMPT` (1573 chars): Lead developer coordinating agents
- `SUBAGENT_BASE_PROMPT` (703 chars): Base prompt for all subagents
**Task-Specific Prompts**:
- `IMPLEMENTATION_TASK_PROMPT`: For code implementation tasks
- `REVIEW_TASK_PROMPT`: For code review tasks
- `TESTING_TASK_PROMPT`: For test writing
- `DEBUG_TASK_PROMPT`: For debugging
- `RESEARCH_TASK_PROMPT`: For research tasks
**Few-Shot Examples**:
- `DELEGATION_EXAMPLE`: Shows orchestrator delegation workflow
- `CODE_IMPLEMENTATION_EXAMPLE`: Shows implementation best practices
- `CODE_REVIEW_EXAMPLE`: Shows review output format
**Key Functions**:
```python
# Compose prompts with dynamic context
compose_orchestrator_prompt(
    task_context: str,
    available_agents: list[str] | None = None,
    constraints: str | None = None
) -> str
compose_subagent_prompt(
    specialty_prompt: str,
    task_context: str,
    prior_context: str | None = None
) -> str
# Create dynamic prompts
create_dynamic_prompt(
    role: str,
    expertise: str,
    task_description: str,
    tools: list[str],
    output_format: str
) -> str
# Prompt registry access
PromptRegistry.get_task_prompt(task_type: str) -> str
PromptRegistry.compose_with_example(base_prompt: str, example_type: str) -> str
```
**Example**:
```python
# Compose orchestrator prompt (static base is cached)
prompt = compose_orchestrator_prompt(
    task_context="Implement user authentication",
    available_agents=['architect', 'implementer', 'tester'],
    constraints="Use JWT tokens, include rate limiting"
)
# Get task-specific prompt
implementation_prompt = PromptRegistry.get_task_prompt('implementation')
# Add example
prompt_with_example = PromptRegistry.compose_with_example(
    base_prompt=implementation_prompt,
    example_type='implementation'
)
```
---
### 3. **tools.py** - Type-Safe Tool Definitions (570 lines)
**Purpose**: Tool definitions with Pydantic validation
**Key Classes**:
- `ToolDefinition`: Tool with name, description, input_schema
- `ToolRegistry`: Central tool registry with validation
- `ToolSets`: Pre-defined tool sets for common workflows
**Input Validation Models** (Pydantic):
- `ReadFileInput`: file_path, offset?, limit?
- `WriteFileInput`: file_path, content, create_directories?
- `EditFileInput`: file_path, old_string, new_string, replace_all?
- `BashInput`: command, timeout?, working_directory? (includes safety checks)
- `SearchFilesInput`: pattern, path?, glob?, case_insensitive?, max_results?
- `DelegateTaskInput`: agent, task, context?, expected_output?
**Available Tools** (6 total):
1. `read_file`: Read file contents (supports offset/limit for large files)
2. `write_file`: Create/overwrite files (auto-creates directories)
3. `edit_file`: Replace specific text (exact match, supports replace_all)
4. `bash`: Execute shell commands (includes dangerous pattern detection)
5. `search_files`: Regex search across files (supports glob filtering)
6. `delegate_task`: Delegate to another agent (orchestrator use)
**Tool Sets**:
```python
ToolSets.READONLY       # ['read_file', 'search_files']
ToolSets.FILESYSTEM     # ['read_file', 'write_file', 'edit_file', 'search_files']
ToolSets.EXECUTION      # ['bash']
ToolSets.DEVELOPER      # ['read_file', 'write_file', 'edit_file', 'bash', 'search_files']
ToolSets.ORCHESTRATOR   # ['read_file', 'search_files', 'delegate_task']
ToolSets.REVIEWER       # ['read_file', 'search_files', 'bash']
```
**Functions**:
```python
# Get tools
get_tool(name: str) -> ToolDefinition
get_tools(names: list[str]) -> list[dict]  # API format
developer_tools() -> list[dict]  # Shorthand for DEVELOPER set
orchestrator_tools() -> list[dict]  # Shorthand for ORCHESTRATOR set
# Validate input
validate_tool_input(tool_name: str, input_data: dict) -> bool
ToolRegistry.parse_input(tool_name: str, input_data: dict) -> BaseModel
# Registry operations
ToolRegistry.get(name: str)
ToolRegistry.get_tools(names: list[str])
ToolRegistry.get_all()
ToolRegistry.list_names()
ToolRegistry.validate_input(tool_name, input_data)
ToolRegistry.register(tool, validator?)
# Tool sets
ToolSets.get(set_name: str) -> list[str]
ToolSets.get_tools(set_name: str) -> list[dict]
```
**Example**:
```python
# Get tools for agent
tools = developer_tools()  # All developer tools in API format
# Validate before use
input_data = {'file_path': '/test.py', 'offset': 0}
if validate_tool_input('read_file', input_data):
    # Safe to use with API
    pass
# Get custom tool set
review_tools = ToolRegistry.get_tools(['read_file', 'search_files', 'bash'])
# Parse and validate (returns typed Pydantic model)
parsed = ToolRegistry.parse_input('bash', {
    'command': 'pytest tests/',
    'timeout': 60000
})
print(f"Command: {parsed.command}, Timeout: {parsed.timeout}ms")
```
---
### 4. **__init__.py** - Module Exports (136 lines)
**Purpose**: Centralized exports and legacy compatibility
**Total Exports**: 29
**Categories**:
- **Agents** (12): AgentDefinition, AgentRegistry, get_agent, list_agents, create_agent, + 7 default agents
- **Prompts** (6): PromptRegistry, compose functions, static prompts
- **Tools** (8): ToolDefinition, ToolRegistry, ToolSets, utility functions
- **Legacy** (3): get_prompt, get_schema, get_tool_definitions
**Import Patterns**:
```python
# Import everything
from resources import *
# Import specific items
from resources import (
    get_agent, create_agent,
    developer_tools, orchestrator_tools,
    compose_orchestrator_prompt,
)
# Import default agents
from resources import ARCHITECT, IMPLEMENTER, REVIEWER
# Legacy compatibility
from resources import get_prompt, get_tool_definitions
```
---
## Usage Patterns
### Pattern 1: Simple Agent Execution
```python
from resources import get_agent, developer_tools
# Get agent configuration
agent = get_agent('implementer')
# Use with Claude Agent SDK
from claude_agent_sdk import Anthropic
client = Anthropic()
response = client.messages.create(
    model=agent.model,
    system=agent.system_prompt,
    tools=developer_tools(),
    messages=[{"role": "user", "content": "Implement feature X"}]
)
```
### Pattern 2: Orchestrated Workflow
```python
from resources import (
    compose_orchestrator_prompt,
    orchestrator_tools,
    get_agent,
)
# Build orchestrator configuration
system_prompt = compose_orchestrator_prompt(
    task_context="Build REST API with auth",
    available_agents=['architect', 'implementer', 'tester']
)
# Execute orchestrator
response = client.messages.create(
    model='claude-sonnet-4-20250514',
    system=system_prompt,
    tools=orchestrator_tools(),
    messages=[{"role": "user", "content": "Start implementation"}]
)
```
### Pattern 3: Multi-Stage Pipeline
```python
from resources import (
    get_agent,
    compose_subagent_prompt,
    ToolRegistry,
)
# Stage 1: Architecture
architect = get_agent('architect')
arch_prompt = compose_subagent_prompt(
    specialty_prompt=architect.system_prompt,
    task_context="Design auth system"
)
# Execute stage 1
arch_result = execute_with_sdk(architect.model, arch_prompt, architect.tools)
# Stage 2: Implementation (with context from stage 1)
implementer = get_agent('implementer')
impl_prompt = compose_subagent_prompt(
    specialty_prompt=implementer.system_prompt,
    task_context="Implement auth endpoints",
    prior_context=arch_result
)
# Execute stage 2
impl_result = execute_with_sdk(implementer.model, impl_prompt, implementer.tools)
```
### Pattern 4: Cost Optimization
```python
from resources import get_agent
# Use cheaper model for simple tasks
def get_optimized_agent(role: str, complexity: str):
    agent = get_agent(role)
    if complexity == 'simple':
        return agent.with_model('claude-haiku-4-5-20251001')
    elif complexity == 'complex':
        return agent.with_model('claude-sonnet-4-20250514')
    return agent
# Usage
simple_review = get_optimized_agent('reviewer', 'simple')
complex_impl = get_optimized_agent('implementer', 'complex')
```
---
## Testing
All components include type hints and Pydantic validation. Test suite included in module.
```python
# Run tests
cd C:\Users\Ray\.claude\sdk-workflow
python -m pytest resources/
# Validate installation
python -c "from resources import *; print('OK')"
# Check exports
python -c "from resources import __all__; print(len(__all__), 'exports')"
```
---
## Key Features
1. **Prompt Caching Optimization**: Static base prompts cached at 90% discount, dynamic content appended
2. **Type Safety**: Full Pydantic validation for tool inputs
3. **Flexible Agent System**: 7 default agents, easy custom agent creation
4. **Tool Sets**: Pre-configured tool sets for common workflows
5. **Production Ready**: Complete type hints, docstrings, error handling
6. **Backward Compatible**: Legacy functions for gradual migration
---
## Files
| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 136 | Module exports and legacy compatibility |
| `agents.py` | 384 | Agent registry and default agents |
| `prompts.py` | 477 | Static cacheable system prompts |
| `tools.py` | 570 | Tool definitions with validation |
| `USAGE_EXAMPLES.md` | 529 | Comprehensive usage documentation |
| `README.md` | - | This file |
---
## Next Steps
1. **Integrate with Executors**: Use in `executors/orchestrator.py` and `executors/streaming.py`
2. **Add Custom Agents**: Create domain-specific agents for your workflow
3. **Extend Tools**: Add custom tools via `ToolRegistry.register()`
4. **Monitor Caching**: Track cache hit rates with Anthropic API metrics
---
## References
- **Module Location**: `C:\Users\Ray\.claude\sdk-workflow\resources\`
- **Usage Examples**: `USAGE_EXAMPLES.md`
- **Anthropic API Docs**: https://docs.anthropic.com/
- **Prompt Caching**: https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
---
**Version**: 1.0.0
**Last Updated**: 2025-11-30
**Status**: Production Ready
