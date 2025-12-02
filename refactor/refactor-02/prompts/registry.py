"""
Subagent Prompt Registry

Consolidated registry of all subagent prompts with access functions.

@version 1.0.0
"""

from typing import Any, Dict, List, Optional

from .base import SubagentPrompt
from .teams import (
    RESEARCH_TEAM_PROMPTS,
    DISCUSSION_PANEL_PROMPTS,
    CICD_TEAM_PROMPTS,
    DISCOVERY_PROMPTS,
    EXECUTION_PROMPTS,
    VERIFICATION_PROMPTS,
)

__all__ = [
    "SUBAGENT_PROMPTS",
    "TEAM_REGISTRY",
    "get_subagent_prompt",
    "get_team_prompts",
    "get_sdk_agent_definitions",
    "list_agents",
    "list_teams",
]


# =============================================================================
# Team Registry
# =============================================================================

TEAM_REGISTRY: Dict[str, Dict[str, SubagentPrompt]] = {
    "research": RESEARCH_TEAM_PROMPTS,
    "discussion": DISCUSSION_PANEL_PROMPTS,
    "cicd": CICD_TEAM_PROMPTS,
    "discovery": DISCOVERY_PROMPTS,
    "execution": EXECUTION_PROMPTS,
    "verification": VERIFICATION_PROMPTS,
}


# =============================================================================
# Consolidated Prompts Dictionary
# =============================================================================

SUBAGENT_PROMPTS: Dict[str, SubagentPrompt] = {
    **RESEARCH_TEAM_PROMPTS,
    **DISCUSSION_PANEL_PROMPTS,
    **CICD_TEAM_PROMPTS,
    **DISCOVERY_PROMPTS,
    **EXECUTION_PROMPTS,
    **VERIFICATION_PROMPTS,
}


# =============================================================================
# Access Functions
# =============================================================================

def get_subagent_prompt(name: str) -> SubagentPrompt:
    """Get a subagent prompt by name.

    Args:
        name: Subagent name

    Returns:
        SubagentPrompt instance

    Raises:
        KeyError: If subagent not found
    """
    if name not in SUBAGENT_PROMPTS:
        available = ", ".join(sorted(SUBAGENT_PROMPTS.keys()))
        raise KeyError(f"Subagent '{name}' not found. Available: {available}")
    return SUBAGENT_PROMPTS[name]


def get_team_prompts(team: str) -> Dict[str, SubagentPrompt]:
    """Get all prompts for a team.

    Args:
        team: Team name (research, discussion, cicd, discovery, execution, verification)

    Returns:
        Dict of team member prompts
    """
    return TEAM_REGISTRY.get(team, {})


def get_sdk_agent_definitions(team: str) -> Dict[str, Dict[str, Any]]:
    """Get SDK-compatible agent definitions for a team.

    Args:
        team: Team name

    Returns:
        Dict suitable for SDK 'agents' parameter
    """
    prompts = get_team_prompts(team)
    return {
        name: prompt.to_sdk_definition()
        for name, prompt in prompts.items()
    }


def list_agents(team: Optional[str] = None) -> List[str]:
    """List available agent names.

    Args:
        team: Optional team filter

    Returns:
        List of agent names
    """
    if team:
        return list(get_team_prompts(team).keys())
    return list(SUBAGENT_PROMPTS.keys())


def list_teams() -> List[str]:
    """List available team names."""
    return list(TEAM_REGISTRY.keys())


def get_agents_by_model(model: str) -> Dict[str, SubagentPrompt]:
    """Get all agents that use a specific model tier.

    Args:
        model: Model tier (haiku, sonnet, opus)

    Returns:
        Dict of matching agents
    """
    return {
        name: prompt
        for name, prompt in SUBAGENT_PROMPTS.items()
        if prompt.model == model
    }
