# Resources Module - Usage Examples
This document demonstrates practical usage patterns for the sdk-workflow resources module.
## Table of Contents
1. [Agent Management](#agent-management)
2. [Tool Configuration](#tool-configuration)
3. [Prompt Composition](#prompt-composition)
4. [Integration Examples](#integration-examples)
---
## Agent Management
### Using Pre-defined Agents
```python
from resources import get_agent, list_agents
# List all available agents
print(f"Available agents: {list_agents()}")
# Output: ['architect', 'implementer', 'reviewer', 'tester', 'researcher', 'debugger', 'documenter']
# Get a specific agent
architect = get_agent('architect')
print(f"Agent: {architect.name}")
print(f"Role: {architect.role}")
print(f"Model: {architect.model}")
print(f"Tools: {architect.tools}")
```
### Creating Custom Agents
```python
from resources import create_agent, AgentRegistry
# Create and register a custom agent
performance_agent = create_agent(
    name='performance_optimizer',
    role='Performance Engineer',
    system_prompt="""You are an expert Performance Engineer.
    Analyze code for performance bottlenecks and optimization opportunities.
    Focus on algorithmic efficiency, memory usage, and execution speed.""",
    model='claude-sonnet-4-20250514',
    tools=['read_file', 'search_files', 'bash'],
    register=True  # Automatically register
)
# Create without registering (for one-off use)
temp_agent = create_agent(
    name='temp_analyzer',
    role='Temporary Analyst',
    system_prompt='Quick analysis agent',
    register=False
)
```
### Modifying Agent Configurations
```python
from resources import get_agent
# Get an existing agent
base_agent = get_agent('implementer')
# Create variant with different model
fast_implementer = base_agent.with_model('claude-haiku-4-5-20251001')
# Create variant with different tools
limited_implementer = base_agent.with_tools(['read_file', 'write_file'])
```
---
## Tool Configuration
### Using Tool Sets
```python
from resources import ToolSets, ToolRegistry
# Get predefined tool sets
readonly_tools = ToolSets.get('readonly')
# ['read_file', 'search_files']
developer_tools = ToolSets.get('developer')
# ['read_file', 'write_file', 'edit_file', 'bash', 'search_files']
orchestrator_tools = ToolSets.get('orchestrator')
# ['read_file', 'search_files', 'delegate_task']
# Get tools in Anthropic API format
api_tools = ToolSets.get_tools('developer')
# Returns list of dicts with 'name', 'description', 'input_schema'
```
### Working with Individual Tools
```python
from resources import get_tool, validate_tool_input
# Get a specific tool
read_tool = get_tool('read_file')
print(f"Tool: {read_tool.name}")
print(f"Description: {read_tool.description}")
# Convert to API format
api_format = read_tool.to_api_format()
# {'name': 'read_file', 'description': '...', 'input_schema': {...}}
# Validate tool input
input_data = {
    'file_path': '/path/to/file.py',
    'offset': 10,
    'limit': 100
}
is_valid = validate_tool_input('read_file', input_data)
# Returns True if valid, raises ValueError with details if invalid
```
### Validating Tool Inputs
```python
from resources import ToolRegistry
# Parse and validate input (returns typed Pydantic model)
input_data = {'file_path': '/test.py', 'offset': 0}
parsed = ToolRegistry.parse_input('read_file', input_data)
print(f"File path: {parsed.file_path}")
print(f"Offset: {parsed.offset}")
print(f"Limit: {parsed.limit}")  # Uses default if not provided
# Validation catches errors
try:
    invalid_input = {'file_path': '', 'offset': -1}
    ToolRegistry.validate_input('read_file', invalid_input)
except ValueError as e:
    print(f"Validation failed: {e}")
```
---
## Prompt Composition
### Using Static Prompts
```python
from resources import PromptRegistry
# Access static prompts directly
orchestrator_prompt = PromptRegistry.ORCHESTRATOR
subagent_base = PromptRegistry.SUBAGENT_BASE
# Get task-specific prompts
implementation_prompt = PromptRegistry.get_task_prompt('implementation')
review_prompt = PromptRegistry.get_task_prompt('review')
testing_prompt = PromptRegistry.get_task_prompt('testing')
debug_prompt = PromptRegistry.get_task_prompt('debug')
research_prompt = PromptRegistry.get_task_prompt('research')
```
### Composing Dynamic Prompts
```python
from resources import compose_orchestrator_prompt, compose_subagent_prompt
# Compose orchestrator prompt with context
full_prompt = compose_orchestrator_prompt(
    task_context="Implement user authentication for REST API",
    available_agents=['architect', 'implementer', 'reviewer', 'tester'],
    constraints="""
    - Use JWT tokens
    - Support OAuth2
    - Include rate limiting
    - Write comprehensive tests
    """
)
# Compose subagent prompt with prior context
subagent_prompt = compose_subagent_prompt(
    specialty_prompt=get_agent('implementer').system_prompt,
    task_context="Implement JWT authentication endpoints",
    prior_context="Architecture designed by architect: [details...]"
)
```
### Creating Custom Dynamic Prompts
```python
from resources import create_dynamic_prompt
# Create a specialized agent prompt
security_prompt = create_dynamic_prompt(
    role='Security Auditor',
    expertise='Finding security vulnerabilities and implementing secure coding practices',
    task_description="""
    Review code for:
    - SQL injection vulnerabilities
    - XSS vulnerabilities
    - Authentication/authorization issues
    - Data exposure risks
    """,
    tools=['read_file', 'search_files'],
    output_format="""
    ## Security Assessment
    [Overall risk level]
    ## Critical Issues
    [List with file:line references]
    ## Recommendations
    [Specific fixes needed]
    """
)
```
### Adding Few-Shot Examples
```python
from resources import PromptRegistry
# Compose prompt with relevant example
prompt_with_example = PromptRegistry.compose_with_example(
    base_prompt=PromptRegistry.IMPLEMENTATION,
    example_type='implementation'
)
# Available example types: 'delegation', 'implementation', 'review'
review_with_example = PromptRegistry.compose_with_example(
    base_prompt=PromptRegistry.REVIEW,
    example_type='review'
)
```
---
## Integration Examples
### Example 1: Setting Up an Orchestrator
```python
from resources import (
    get_agent,
    compose_orchestrator_prompt,
    orchestrator_tools,
)
# Get orchestrator configuration
orchestrator_agent = get_agent('architect')  # Or create custom
# Compose system prompt
system_prompt = compose_orchestrator_prompt(
    task_context="Build a REST API with authentication",
    available_agents=['architect', 'implementer', 'reviewer', 'tester'],
)
# Get tools in API format
tools = orchestrator_tools()
# Use with Claude Agent SDK
from claude_agent_sdk import Anthropic
client = Anthropic()
response = client.messages.create(
    model=orchestrator_agent.model,
    system=system_prompt,
    tools=tools,
    messages=[
        {"role": "user", "content": "Plan the implementation"}
    ]
)
```
### Example 2: Creating a Specialized Workflow
```python
from resources import (
    create_agent,
    ToolSets,
    compose_subagent_prompt,
    get_agent,
)
# Create a security-focused workflow
security_reviewer = create_agent(
    name='security_reviewer',
    role='Security Specialist',
    system_prompt="""You are a Security Specialist.
    Focus exclusively on security vulnerabilities and secure coding practices.
    Treat every input as potentially malicious.""",
    model='claude-sonnet-4-20250514',
    tools=ToolSets.get('reviewer'),  # ['read_file', 'search_files', 'bash']
)
# Compose task prompt
task_prompt = compose_subagent_prompt(
    specialty_prompt=security_reviewer.system_prompt,
    task_context="Review authentication module for vulnerabilities",
    prior_context="Code implemented using JWT tokens and bcrypt hashing"
)
# Get tools for the agent
agent_tools = ToolSets.get_tools('reviewer')
```
### Example 3: Building a Multi-Agent Pipeline
```python
from resources import (
    get_agent,
    compose_subagent_prompt,
    ToolRegistry,
)
class AgentPipeline:
    """Sequential multi-agent workflow."""
    def __init__(self):
        self.stages = []
        self.context_history = []
    def add_stage(self, agent_name: str, task: str):
        """Add a stage to the pipeline."""
        agent = get_agent(agent_name)
        self.stages.append({
            'agent': agent,
            'task': task,
        })
    def get_stage_config(self, stage_index: int):
        """Get configuration for a specific stage."""
        stage = self.stages[stage_index]
        # Build prior context from all previous stages
        prior_context = "\n\n".join(
            f"Stage {i+1} ({self.stages[i]['agent'].role}): {ctx}"
            for i, ctx in enumerate(self.context_history)
        ) if self.context_history else None
        # Compose prompt
        prompt = compose_subagent_prompt(
            specialty_prompt=stage['agent'].system_prompt,
            task_context=stage['task'],
            prior_context=prior_context
        )
        # Get tools
        tools = ToolRegistry.get_tools(stage['agent'].tools)
        return {
            'model': stage['agent'].model,
            'system_prompt': prompt,
            'tools': tools,
        }
# Usage
pipeline = AgentPipeline()
pipeline.add_stage('architect', 'Design the authentication system')
pipeline.add_stage('implementer', 'Implement the authentication endpoints')
pipeline.add_stage('tester', 'Write comprehensive tests')
pipeline.add_stage('reviewer', 'Review for security issues')
# Execute each stage
for i in range(len(pipeline.stages)):
    config = pipeline.get_stage_config(i)
    # Execute with Anthropic SDK
    # result = execute_agent(config)
    # pipeline.context_history.append(result)
```
### Example 4: Dynamic Tool Selection
```python
from resources import ToolRegistry, ToolSets
def get_tools_for_task(task_type: str) -> list[dict]:
    """Dynamically select tools based on task type."""
    tool_mapping = {
        'read_only': ToolSets.get('readonly'),
        'implement': ToolSets.get('developer'),
        'review': ToolSets.get('reviewer'),
        'orchestrate': ToolSets.get('orchestrator'),
    }
    tool_names = tool_mapping.get(task_type, ToolSets.get('readonly'))
    return ToolRegistry.get_tools(tool_names)
# Usage
review_tools = get_tools_for_task('review')
implementation_tools = get_tools_for_task('implement')
```
### Example 5: Cost-Optimized Agent Selection
```python
from resources import get_agent
def select_agent_for_complexity(task_complexity: str, role: str):
    """Select appropriate agent based on task complexity."""
    agent = get_agent(role)
    # Use cheaper model for simple tasks
    if task_complexity == 'simple':
        agent = agent.with_model('claude-haiku-4-5-20251001')
    # Use most capable model for complex tasks
    elif task_complexity == 'complex':
        agent = agent.with_model('claude-sonnet-4-20250514')
    return agent
# Usage
simple_review = select_agent_for_complexity('simple', 'reviewer')
complex_implementation = select_agent_for_complexity('complex', 'implementer')
```
---
## Best Practices
### Prompt Caching Optimization
```python
#  GOOD: Static base + dynamic suffix
from resources import compose_orchestrator_prompt
# Static part (ORCHESTRATOR_PROMPT) is cached
prompt = compose_orchestrator_prompt(
    task_context="Dynamic task description here"
)
#  BAD: Fully dynamic prompts don't benefit from caching
custom_prompt = f"""You are a lead developer.
Task: {dynamic_task}  # This changes every time
Agents: {dynamic_agents}
"""
```
### Tool Validation
```python
#  GOOD: Validate before sending to API
from resources import validate_tool_input
user_input = get_user_input()
try:
    validate_tool_input('write_file', user_input)
    # Proceed with API call
except ValueError as e:
    # Handle validation error before wasting API credits
    print(f"Invalid input: {e}")
```
### Agent Reuse
```python
#  GOOD: Reuse agents with modifications
from resources import get_agent
base_implementer = get_agent('implementer')
fast_implementer = base_implementer.with_model('claude-haiku-4-5-20251001')
limited_implementer = base_implementer.with_tools(['read_file', 'write_file'])
#  BAD: Creating from scratch each time
# create_agent(...) every time instead of modifying existing
```
---
## Testing Examples
### Unit Test Example
```python
import pytest
from resources import (
    AgentRegistry,
    create_agent,
    get_agent,
    list_agents,
)
def test_agent_registration():
    """Test agent registration and retrieval."""
    initial_count = len(list_agents())
    # Create and register agent
    agent = create_agent(
        name='test_agent',
        role='Test Role',
        system_prompt='Test prompt',
        register=True
    )
    assert len(list_agents()) == initial_count + 1
    assert 'test_agent' in list_agents()
    # Retrieve and verify
    retrieved = get_agent('test_agent')
    assert retrieved.name == 'test_agent'
    assert retrieved.role == 'Test Role'
    # Cleanup
    AgentRegistry.unregister('test_agent')
def test_tool_validation():
    """Test tool input validation."""
    from resources import validate_tool_input
    # Valid input
    valid = {'file_path': '/test.py', 'offset': 0}
    assert validate_tool_input('read_file', valid) is True
    # Invalid input
    with pytest.raises(ValueError):
        invalid = {'file_path': '', 'offset': -1}
        validate_tool_input('read_file', invalid)
```
---
## Additional Resources
- **Module Source**: `C:\Users\Ray\.claude\sdk-workflow\resources\`
- **Agent Definitions**: `resources/agents.py`
- **Prompt Templates**: `resources/prompts.py`
- **Tool Schemas**: `resources/tools.py`
- **Registry API**: `resources/__init__.py`
