"""
Subagent Prompts Module

Provides all subagent prompt configurations for multi-agent teams.

Teams:
- research: Lead, domain, data, trend, validation researchers
- discussion: Moderator, architect, pragmatist, critic, optimizer
- cicd: Pipeline architect, build/test/security/deploy/monitor specialists
- discovery: Analyzer, scanner, mapper
- execution: Implementer, integrator
- verification: Tester, reviewer, validator

Usage:
    from prompts import get_subagent_prompt, get_team_prompts
    
    # Get single agent
    prompt = get_subagent_prompt("implementer")
    options = prompt.to_sdk_definition()
    
    # Get full team
    team = get_team_prompts("research")
    
    # Get SDK-ready definitions
    agents = get_sdk_agent_definitions("cicd")

@version 1.0.0
"""

from .base import (
    SubagentPrompt,
    BASE_CONSTRAINTS,
    THINKING_BUDGETS,
    create_agent_prompt,
)

from .teams import (
    RESEARCH_TEAM_PROMPTS,
    DISCUSSION_PANEL_PROMPTS,
    CICD_TEAM_PROMPTS,
    DISCOVERY_PROMPTS,
    EXECUTION_PROMPTS,
    VERIFICATION_PROMPTS,
)

from .registry import (
    SUBAGENT_PROMPTS,
    TEAM_REGISTRY,
    get_subagent_prompt,
    get_team_prompts,
    get_sdk_agent_definitions,
    list_agents,
    list_teams,
    get_agents_by_model,
)

__all__ = [
    # Base
    "SubagentPrompt",
    "BASE_CONSTRAINTS",
    "THINKING_BUDGETS",
    "create_agent_prompt",
    
    # Team prompts
    "RESEARCH_TEAM_PROMPTS",
    "DISCUSSION_PANEL_PROMPTS",
    "CICD_TEAM_PROMPTS",
    "DISCOVERY_PROMPTS",
    "EXECUTION_PROMPTS",
    "VERIFICATION_PROMPTS",
    
    # Registry
    "SUBAGENT_PROMPTS",
    "TEAM_REGISTRY",
    "get_subagent_prompt",
    "get_team_prompts",
    "get_sdk_agent_definitions",
    "list_agents",
    "list_teams",
    "get_agents_by_model",
]
