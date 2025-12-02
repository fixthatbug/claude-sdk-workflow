"""
Subagent Base Prompt Configuration

Core data structures and constraints for all subagent prompts.
Integrates with SDK ToolPreset system for consistent tooling.

@version 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "SubagentPrompt",
    "BASE_CONSTRAINTS",
    "THINKING_BUDGETS",
]


# =============================================================================
# Thinking Budget Configuration
# =============================================================================

THINKING_BUDGETS: Dict[str, int] = {
    "haiku": 8000,
    "sonnet": 16000,
    "opus": 32000,
}


# =============================================================================
# Base Constraints (Applied to ALL subagents)
# =============================================================================

BASE_CONSTRAINTS = """
<default_to_action>
Take action immediately. Execute assigned task without waiting for permission.
Use tools to gather context, then implement solution. Exit when task complete.
</default_to_action>

<post_tool_reflection>
After each tool execution, reflect briefly:
- What does this result tell me about next steps?
- Are there unexpected patterns or issues?
- What additional context is needed?
- Can I proceed or am I blocked?
</post_tool_reflection>

<prevent_over_engineering>
Implement only what is assigned:
- NO speculative features beyond task scope
- NO unnecessary abstractions
- Keep solutions minimal and focused
- Prefer simple, direct implementations
</prevent_over_engineering>

<investigate_before_answering>
Before making claims:
1. Use Read/Grep/Glob to verify file contents
2. Cite specific file paths and line numbers
3. Mark uncertainty explicitly
NEVER fabricate file paths, signatures, or results.
</investigate_before_answering>

## STRICT CONSTRAINTS
- Exit IMMEDIATELY after completing assigned task
- NO reporting back, NO summaries, NO status updates
- Output ONLY deliverables - implementation guides, code, or key findings
- Action over discussion - minimize communication
- If blocked, document blocker and exit

## OUTPUT FORMAT
- Concise, key information only
- Code must be deployment-ready
- No placeholder/TODO code
- No explanations unless essential for understanding
"""


# =============================================================================
# SubagentPrompt Data Class
# =============================================================================

@dataclass
class SubagentPrompt:
    """A subagent system prompt configuration.
    
    Attributes:
        name: Unique identifier for the subagent
        role: Human-readable role description
        model: Model tier (haiku, sonnet, opus)
        tools: List of tool names or preset references
        prompt: Full system prompt text
        exit_condition: Condition that triggers agent exit
        preset: Optional ToolPreset name to use
        thinking_budget: Override default thinking budget
    """
    name: str
    role: str
    model: str
    tools: List[str]
    prompt: str
    exit_condition: str
    preset: Optional[str] = None
    thinking_budget: Optional[int] = None

    def get_thinking_budget(self) -> int:
        """Get thinking budget for this agent's model tier."""
        if self.thinking_budget:
            return self.thinking_budget
        return THINKING_BUDGETS.get(self.model, 16000)

    def to_sdk_definition(self) -> Dict[str, Any]:
        """Convert to SDK-compatible agent definition.
        
        Returns dict suitable for SDK agents parameter.
        """
        return {
            "description": f"{self.role} - {self.exit_condition}",
            "prompt": self.prompt,
            "tools": self.tools,
            "model": self.model,
            "thinking_budget": self.get_thinking_budget(),
        }

    def to_options_dict(self) -> Dict[str, Any]:
        """Convert to ClaudeAgentOptions-compatible dict."""
        return {
            "model": self._get_full_model_name(),
            "system_prompt": self.prompt,
            "allowed_tools": self.tools,
            "max_thinking_tokens": self.get_thinking_budget(),
            "metadata": {
                "agent_name": self.name,
                "role": self.role,
                "exit_condition": self.exit_condition,
            },
        }

    def _get_full_model_name(self) -> str:
        """Convert model tier to full model name."""
        model_map = {
            "haiku": "claude-haiku-4-5-20251001",
            "sonnet": "claude-sonnet-4-5-20250929",
            "opus": "claude-opus-4-5-20251101",
        }
        return model_map.get(self.model, self.model)


# =============================================================================
# Prompt Template Helpers
# =============================================================================

def create_agent_prompt(
    role_description: str,
    responsibilities: List[str],
    output_format: str,
    additional_constraints: str = "",
) -> str:
    """Create a standardized agent prompt.
    
    Args:
        role_description: What the agent does
        responsibilities: List of key responsibilities
        output_format: Expected output format
        additional_constraints: Extra constraints specific to this agent
    
    Returns:
        Complete prompt string with BASE_CONSTRAINTS included
    """
    responsibilities_text = "\n".join(f"- {r}" for r in responsibilities)
    
    return f"""You are a {role_description}.

## PRIME DIRECTIVE
{responsibilities[0] if responsibilities else 'Complete assigned tasks efficiently.'}

## RESPONSIBILITIES
{responsibilities_text}

## OUTPUT FORMAT
{output_format}

{additional_constraints}

{BASE_CONSTRAINTS}
"""
