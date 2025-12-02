"""
Team Prompt Modules

Exports all team-specific prompt configurations.

@version 1.0.0
"""

from .research import RESEARCH_TEAM_PROMPTS
from .discussion import DISCUSSION_PANEL_PROMPTS
from .cicd import CICD_TEAM_PROMPTS
from .workflow import (
    DISCOVERY_PROMPTS,
    EXECUTION_PROMPTS,
    VERIFICATION_PROMPTS,
)

__all__ = [
    "RESEARCH_TEAM_PROMPTS",
    "DISCUSSION_PANEL_PROMPTS",
    "CICD_TEAM_PROMPTS",
    "DISCOVERY_PROMPTS",
    "EXECUTION_PROMPTS",
    "VERIFICATION_PROMPTS",
]
