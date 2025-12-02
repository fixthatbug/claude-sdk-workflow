"""Executor helper functions.

SDK option validation, MCP configuration, and plugin discovery.

@version 2.0.0
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

__all__ = [
    'MCP_SERVERS',
    'build_sdk_options',
    'validate_sdk_options',
    'discover_plugins',
]

logger = logging.getLogger(__name__)


# =============================================================================
# MCP Server Configurations
# =============================================================================

MCP_SERVERS: Dict[str, Dict[str, Any]] = {
    "user-memory": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-memory"]
    },
    "sequential-thinking": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@anthropic/mcp-sequential-thinking"]
    },
}


# =============================================================================
# SDK Options Builder
# =============================================================================

# Valid SDK option keys (from official docs)
VALID_SDK_KEYS = {
    "allowed_tools",
    "system_prompt",
    "mcp_servers",
    "permission_mode",
    "continue_conversation",
    "resume",
    "max_turns",
    "disallowed_tools",
    "model",
    "output_format",
    "permission_prompt_tool_name",
    "cwd",
    "settings",
    "add_dirs",
    "env",
    "extra_args",
    "max_buffer_size",
    "stderr",
    "can_use_tool",
    "hooks",
    "user",
    "include_partial_messages",
    "fork_session",
    "agents",
    "setting_sources",
    "max_thinking_tokens",
    "plugins",
}


def build_sdk_options(
    factory_options: Dict[str, Any],
    cwd: str,
    include_mcp: bool = True,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build SDK-compatible options from factory configuration.

    Args:
        factory_options: Options from agent factory
        cwd: Working directory
        include_mcp: Whether to include MCP servers
        overrides: Additional overrides

    Returns:
        SDK-compatible options dictionary
    """
    overrides = overrides or {}
    
    options: Dict[str, Any] = {
        "model": factory_options.get("model"),
        "cwd": factory_options.get("cwd", cwd),
        "system_prompt": factory_options.get("system_prompt"),
        "allowed_tools": factory_options.get("tools", []),
        "setting_sources": ["user", "project"],
    }

    if include_mcp:
        options["mcp_servers"] = MCP_SERVERS

    # Handle thinking budget
    thinking = factory_options.get("thinking")
    if isinstance(thinking, dict):
        if thinking.get("type") == "enabled" and thinking.get("budget_tokens"):
            options["max_thinking_tokens"] = int(thinking["budget_tokens"])
    elif isinstance(thinking, int):
        options["max_thinking_tokens"] = thinking

    # Apply overrides
    if "agents" in overrides:
        options["agents"] = overrides["agents"]

    return options


def validate_sdk_options(options: Dict[str, Any]) -> None:
    """Validate that options are SDK-compliant.

    Args:
        options: Options dictionary to validate

    Raises:
        ValueError: If options contain invalid values
    """
    # Warn about invalid keys
    invalid_keys = set(options.keys()) - VALID_SDK_KEYS
    if invalid_keys:
        logger.warning(f"Non-SDK keys (ignored): {invalid_keys}")

    # Type validations
    if "allowed_tools" in options and not isinstance(options["allowed_tools"], list):
        raise ValueError(f"allowed_tools must be list, got {type(options['allowed_tools'])}")

    if "setting_sources" in options and not isinstance(options["setting_sources"], list):
        raise ValueError(f"setting_sources must be list")

    if "max_thinking_tokens" in options and not isinstance(options["max_thinking_tokens"], int):
        raise ValueError(f"max_thinking_tokens must be int")

    if "agents" in options and not isinstance(options["agents"], dict):
        raise ValueError(f"agents must be dict")

    logger.debug(f"Options validation passed: {len(options)} keys")


# =============================================================================
# Plugin Discovery
# =============================================================================

def discover_plugins(search_paths: Optional[List[Path]] = None) -> Dict[str, Any]:
    """Discover plugins from standard locations.

    Args:
        search_paths: Additional paths to search

    Returns:
        Dict mapping plugin names to manifest data
    """
    plugins = {}
    plugin_dirs = [
        Path(".claude-plugin"),
        Path.home() / ".claude" / "plugins"
    ]
    
    if search_paths:
        plugin_dirs.extend(search_paths)

    for plugin_dir in plugin_dirs:
        manifest = plugin_dir / "plugin.json"
        if manifest.exists():
            try:
                with open(manifest) as f:
                    plugins[plugin_dir.name] = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load plugin {plugin_dir}: {e}")

    return plugins
