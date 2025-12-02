"""Tool Presets - Predefined tool configurations for agent types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class ToolPreset:
    """A preset tool configuration."""
    name: str
    tools: List[str]
    description: str
    permissions: Dict[str, bool] = field(default_factory=dict)


# Standard tool presets
TOOL_PRESETS: Dict[str, ToolPreset] = {
    "core": ToolPreset(
        name="core",
        tools=["Read", "Glob", "Grep"],
        description="Basic read-only tools for all agents",
        permissions={"file_read": True, "file_write": False}
    ),
    "web": ToolPreset(
        name="web",
        tools=["WebSearch", "WebFetch"],
        description="Web access tools for research",
        permissions={"web_access": True}
    ),
    "file": ToolPreset(
        name="file",
        tools=["Read", "Write", "Edit", "Glob"],
        description="File manipulation tools",
        permissions={"file_read": True, "file_write": True}
    ),
    "execution": ToolPreset(
        name="execution",
        tools=["Bash", "CodeExecution"],
        description="Code execution tools",
        permissions={"bash_execute": True, "code_execute": True}
    ),
    "orchestration": ToolPreset(
        name="orchestration",
        tools=["Task", "TodoRead", "TodoWrite"],
        description="Orchestration tools for coordinators",
        permissions={"delegate": True}
    ),
    "full": ToolPreset(
        name="full",
        tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash", 
               "WebSearch", "WebFetch", "Task"],
        description="Full tool access",
        permissions={
            "file_read": True, "file_write": True,
            "bash_execute": True, "web_access": True, "delegate": True
        }
    ),
    "research": ToolPreset(
        name="research",
        tools=["Read", "Glob", "Grep", "WebSearch", "WebFetch"],
        description="Research-focused tools",
        permissions={"file_read": True, "web_access": True}
    ),
    "development": ToolPreset(
        name="development",
        tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
        description="Development tools",
        permissions={
            "file_read": True, "file_write": True, "bash_execute": True
        }
    ),
}


def get_tool_preset(name: str) -> Optional[ToolPreset]:
    """Get a tool preset by name."""
    return TOOL_PRESETS.get(name.lower())


def combine_presets(*preset_names: str) -> ToolPreset:
    """Combine multiple presets into one."""
    tools: Set[str] = set()
    permissions: Dict[str, bool] = {}
    
    for name in preset_names:
        preset = get_tool_preset(name)
        if preset:
            tools.update(preset.tools)
            permissions.update(preset.permissions)
    
    return ToolPreset(
        name="+".join(preset_names),
        tools=list(tools),
        description=f"Combined preset: {', '.join(preset_names)}",
        permissions=permissions
    )


__all__ = ['ToolPreset', 'TOOL_PRESETS', 'get_tool_preset', 'combine_presets']
