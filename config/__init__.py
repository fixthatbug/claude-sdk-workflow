"""Configuration package for SDK workflow orchestrator.
Exports phase presets, agent prompts, and configuration utilities for workflow automation.
"""
from .presets import PhaseType, PHASE_PROMPTS, get_phase_prompt, list_available_phases
from .agent_prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    SUBAGENT_ARCHITECT_PROMPT,
    SUBAGENT_IMPLEMENTER_PROMPT,
    SUBAGENT_REVIEWER_PROMPT,
    SUBAGENT_TESTER_PROMPT,
    SUBAGENT_EXPERT_CLONE_PROMPT,
    get_orchestrator_prompt,
    get_subagent_prompt,
    list_available_agent_types,
)
__all__ = [
    # Phase presets
    "PhaseType",
    "PHASE_PROMPTS",
    "get_phase_prompt",
    "list_available_phases",
    # Agent prompts
    "ORCHESTRATOR_SYSTEM_PROMPT",
    "SUBAGENT_ARCHITECT_PROMPT",
    "SUBAGENT_IMPLEMENTER_PROMPT",
    "SUBAGENT_REVIEWER_PROMPT",
    "SUBAGENT_TESTER_PROMPT",
    "SUBAGENT_EXPERT_CLONE_PROMPT",
    "get_orchestrator_prompt",
    "get_subagent_prompt",
    "list_available_agent_types",
]
