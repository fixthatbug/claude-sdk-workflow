"""
Resources module for sdk-workflow.
Contains static resources that benefit from prompt caching:
    - agents: Agent definitions and registry
    - prompts: System prompts and templates
    - schemas: JSON schemas for structured output
    - tools: Tool definitions with Pydantic validation
Prompt caching provides ~90% cost reduction on repeated prompts.
"""
from __future__ import annotations
__all__ = [
    # Agent exports
    "AgentDefinition",
    "AgentRegistry",
    "get_agent",
    "list_agents",
    "create_agent",
    "ARCHITECT",
    "IMPLEMENTER",
    "REVIEWER",
    "TESTER",
    "RESEARCHER",
    "DEBUGGER",
    "DOCUMENTER",
    # Prompt exports
    "PromptRegistry",
    "compose_orchestrator_prompt",
    "compose_subagent_prompt",
    "create_dynamic_prompt",
    "ORCHESTRATOR_PROMPT",
    "SUBAGENT_BASE_PROMPT",
    # Tool exports
    "ToolDefinition",
    "ToolRegistry",
    "ToolSets",
    "get_tool",
    "get_tools",
    "validate_tool_input",
    "developer_tools",
    "orchestrator_tools",
    # Legacy exports (backward compatibility)
    "get_prompt",
    "get_schema",
    "get_tool_definitions",
]
# =============================================================================
# Agent Imports
# =============================================================================
from .agents import (
    AgentDefinition,
    AgentRegistry,
    get_agent,
    list_agents,
    create_agent,
    ARCHITECT,
    IMPLEMENTER,
    REVIEWER,
    TESTER,
    RESEARCHER,
    DEBUGGER,
    DOCUMENTER,
)
# =============================================================================
# Prompt Imports
# =============================================================================
from .prompts import (
    PromptRegistry,
    compose_orchestrator_prompt,
    compose_subagent_prompt,
    create_dynamic_prompt,
    ORCHESTRATOR_PROMPT,
    SUBAGENT_BASE_PROMPT,
)
# =============================================================================
# Tool Imports
# =============================================================================
from .tools import (
    ToolDefinition,
    ToolRegistry,
    ToolSets,
    get_tool,
    get_tools,
    validate_tool_input,
    developer_tools,
    orchestrator_tools,
)
# =============================================================================
# Legacy Functions (Backward Compatibility)
# =============================================================================
def get_prompt(name: str, **variables) -> str:
    """
    Get a system prompt by name with variable substitution.
    DEPRECATED: Use PromptRegistry.get_task_prompt() or compose_* functions.
    Args:
        name: Prompt identifier (e.g., "implementation", "review").
        **variables: Variables to substitute in the prompt.
    Returns:
        Formatted prompt string.
    Raises:
        KeyError: If prompt name not found.
    """
    prompt = PromptRegistry.get_task_prompt(name)
    if variables:
        prompt = prompt.format(**variables)
    return prompt
def get_schema(name: str) -> dict:
    """
    Get a JSON schema by name for structured output.
    Args:
        name: Schema identifier.
    Returns:
        JSON schema dictionary.
    """
    # Lazy import to avoid circular dependency
    try:
        from .schemas import SCHEMAS
        if name not in SCHEMAS:
            raise KeyError(f"Unknown schema: {name}. Available: {list(SCHEMAS.keys())}")
        return SCHEMAS[name]
    except ImportError:
        raise KeyError(f"Schemas module not available. Schema '{name}' not found.")
def get_tool_definitions(tool_set: str | list[str] | None = None) -> list[dict]:
    """
    Get tool definitions for agents.
    Args:
        tool_set: Either a tool set name ('developer', 'orchestrator', etc.),
                  a list of tool names, or None for all tools.
    Returns:
        List of tool definition dictionaries in API format.
    """
    if tool_set is None:
        return ToolRegistry.get_all()
    elif isinstance(tool_set, str):
        return ToolSets.get_tools(tool_set)
    else:
        return ToolRegistry.get_tools(tool_set)
