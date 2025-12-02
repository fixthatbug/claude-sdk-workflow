#!/usr/bin/env python3
"""
Base types, enums, and constants for Claude Agent SDK.

Consolidated from sdk_workflow_enhancements.py to eliminate duplication.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# SDK Availability Check
# =============================================================================

SDK_AVAILABLE = True
try:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        AssistantMessage,
        TextBlock,
        ToolUseBlock,
        ToolResultBlock,
        ResultMessage,
        HookMatcher,
        HookContext,
        tool,
        create_sdk_mcp_server,
    )
    from claude_agent_sdk.types import AgentDefinition
except ImportError:
    SDK_AVAILABLE = False
    ClaudeSDKClient = None
    ClaudeAgentOptions = None
    AssistantMessage = None
    TextBlock = None
    ToolUseBlock = None
    ToolResultBlock = None
    ResultMessage = None
    HookMatcher = None
    HookContext = None
    tool = None
    AgentDefinition = None
    create_sdk_mcp_server = None


# =============================================================================
# Enums
# =============================================================================

class SkillType(Enum):
    """Skill source types for API requests."""
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


class ExecutionMode(Enum):
    """Execution modes for SDK operations."""
    STREAMING = "streaming"
    BATCH = "batch"
    INTERACTIVE = "interactive"


class ComplexityLevel(Enum):
    """Task complexity levels for mode selection."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


# =============================================================================
# Beta Headers
# =============================================================================

SKILLS_BETA_HEADERS = {
    "code_execution": "code-execution-2025-08-25",
    "skills": "skills-2025-10-02",
    "files_api": "files-api-2025-04-14",
    "prompt_caching": "prompt-caching-2024-07-31",
}


# =============================================================================
# Tool Response Types
# =============================================================================

TOOL_RESPONSE_TYPES = {
    "web_search": {
        "response_format": "search_result_list",
        "fields": ["title", "url", "snippet", "citations"],
    },
    "web_fetch": {
        "response_format": "page_content",
        "fields": ["url", "content", "content_type"],
    },
    "code_execution": {
        "response_format": "execution_result",
        "fields": ["stdout", "stderr", "exit_code", "container_id"],
    },
}


# =============================================================================
# Container Configuration
# =============================================================================

CONTAINER_CONFIG = {
    "memory_gib": 5,
    "expiry_days": 30,
    "free_hours_daily": 50,
    "hourly_rate_cents": 4,
}


# =============================================================================
# Computer Use Actions
# =============================================================================

COMPUTER_USE_ACTIONS = {
    "basic": ["screenshot", "click", "type", "scroll", "key"],
    "enhanced_20250124": ["screenshot", "click", "type", "scroll", "key", "hold_key", "wait", "triple_click"],
    "opus_20251124": ["screenshot", "click", "type", "scroll", "key", "hold_key", "wait", "triple_click", "mouse_move"],
}


# =============================================================================
# Programmatic Tool Configuration
# =============================================================================

PROGRAMMATIC_TOOL_CONFIG = {
    "text_editor_20250429": {"requires": "computer_use_20250429"},
    "bash_20250124": {"max_output": 2**20},
    "mcp_20251120": {"transports": ["sse", "streamable_http"]},
}


# =============================================================================
# MCP Server Configuration
# =============================================================================

MCP_SERVER_CONFIG = {
    "supported_transports": ["sse", "streamable_http"],
    "required_headers": {
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "mcp-client-2025-11-20",
    },
    "constraints": {
        "https_only": True,
        "single_toolset_per_server": True,
        "tools_only": True,
    },
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_skills_beta_headers(include_files_api: bool = False) -> List[str]:
    """Get required beta headers for skills API."""
    headers = [
        SKILLS_BETA_HEADERS["code_execution"],
        SKILLS_BETA_HEADERS["skills"],
    ]
    if include_files_api:
        headers.append(SKILLS_BETA_HEADERS["files_api"])
    return headers


def create_skill_config(
    skill_type: str,
    skill_id: str,
    version: str = "latest"
) -> Dict[str, Any]:
    """Create a skill configuration for API requests."""
    return {
        "type": skill_type,
        "skill_id": skill_id,
        "version": version,
    }


def create_container_config(
    skills: List[Dict[str, Any]],
    container_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a container configuration with skills."""
    config = {"skills": skills}
    if container_id:
        config["id"] = container_id
    return config
