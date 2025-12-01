"""
Tool Definitions with Pydantic Validation.
This module provides type-safe tool definitions for SDK workflow agents.
Tools are defined with JSON schemas and validated using Pydantic models.
DESIGN PRINCIPLES:
- Each tool has a clear, single purpose
- Input schemas are strict (validate early, fail fast)
- Descriptions are LLM-friendly (clear, with examples)
- Tools mirror Claude Code capabilities where applicable
"""
from __future__ import annotations
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Literal
from pydantic import BaseModel, Field, field_validator
# =============================================================================
# Tool Definition Model
# =============================================================================
class ToolDefinition(BaseModel):
    """
    Definition of a tool available to agents.
    Attributes:
        name: Unique identifier for the tool.
        description: LLM-friendly description of what the tool does.
        input_schema: JSON Schema defining expected input parameters.
    """
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=10, max_length=1024)
    input_schema: dict[str, Any]
    def to_api_format(self) -> dict[str, Any]:
        """Convert to Claude API tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
# =============================================================================
# Input Validation Models
# =============================================================================
class ReadFileInput(BaseModel):
    """Input schema for read_file tool."""
    file_path: str = Field(
        ...,
        description="Absolute path to the file to read",
    )
    offset: int | None = Field(
        default=None,
        ge=0,
        description="Line number to start reading from (0-indexed)",
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=10000,
        description="Maximum number of lines to read",
    )
    @field_validator("file_path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("file_path cannot be empty")
        return v
class WriteFileInput(BaseModel):
    """Input schema for write_file tool."""
    file_path: str = Field(
        ...,
        description="Absolute path to the file to write",
    )
    content: str = Field(
        ...,
        description="Content to write to the file",
    )
    create_directories: bool = Field(
        default=True,
        description="Create parent directories if they don't exist",
    )
class EditFileInput(BaseModel):
    """Input schema for edit_file tool."""
    file_path: str = Field(
        ...,
        description="Absolute path to the file to edit",
    )
    old_string: str = Field(
        ...,
        min_length=1,
        description="Exact string to find and replace",
    )
    new_string: str = Field(
        ...,
        description="Replacement string (can be empty to delete)",
    )
    replace_all: bool = Field(
        default=False,
        description="Replace all occurrences (default: first only)",
    )
    @field_validator("old_string")
    @classmethod
    def old_must_differ_from_new(cls, v: str, info) -> str:
        # This runs before new_string is available, so we validate in model_validator
        return v
class BashInput(BaseModel):
    """Input schema for bash tool."""
    command: str = Field(
        ...,
        min_length=1,
        description="Shell command to execute",
    )
    timeout: int = Field(
        default=120000,
        ge=1000,
        le=600000,
        description="Timeout in milliseconds (default: 2 minutes, max: 10 minutes)",
    )
    working_directory: str | None = Field(
        default=None,
        description="Directory to run command in (default: current)",
    )
    @field_validator("command")
    @classmethod
    def validate_command(cls, v: str) -> str:
        # Basic safety check - block obviously dangerous patterns
        dangerous_patterns = [
            "rm -rf /",
            "rm -rf /*",
            ":(){:|:&};:", # Fork bomb
            "mkfs.",
            "dd if=",
            "> /dev/sd",
        ]
        for pattern in dangerous_patterns:
            if pattern in v:
                raise ValueError(f"Command contains dangerous pattern: {pattern}")
        return v
class SearchFilesInput(BaseModel):
    """Input schema for search_files tool."""
    pattern: str = Field(
        ...,
        min_length=1,
        description="Regex pattern to search for in file contents",
    )
    path: str | None = Field(
        default=None,
        description="Directory to search in (default: current working directory)",
    )
    glob: str | None = Field(
        default=None,
        description="Glob pattern to filter files (e.g., '*.py', '**/*.ts')",
    )
    case_insensitive: bool = Field(
        default=False,
        description="Perform case-insensitive search",
    )
    max_results: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of results to return",
    )
class DelegateTaskInput(BaseModel):
    """Input schema for delegate_task tool."""
    agent: str = Field(
        ...,
        description="Name of the agent to delegate to",
    )
    task: str = Field(
        ...,
        min_length=10,
        description="Description of the task to perform",
    )
    context: str | None = Field(
        default=None,
        description="Additional context from previous steps",
    )
    expected_output: str | None = Field(
        default=None,
        description="Description of expected output format",
    )
# =============================================================================
# Tool Definitions
# =============================================================================
READ_FILE_TOOL = ToolDefinition(
    name="read_file",
    description="""Read contents of a file from the filesystem.
Use this to:
- Examine source code files
- Read configuration files
- Review documentation
- Check file contents before editing
The file_path must be an absolute path. Use offset and limit for large files.""",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to read",
            },
            "offset": {
                "type": "integer",
                "minimum": 0,
                "description": "Line number to start reading from (0-indexed)",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10000,
                "description": "Maximum number of lines to read",
            },
        },
        "required": ["file_path"],
    },
)
WRITE_FILE_TOOL = ToolDefinition(
    name="write_file",
    description="""Write content to a file, creating it if it doesn't exist.
Use this to:
- Create new source files
- Write configuration files
- Generate documentation
- Save output data
WARNING: This overwrites existing files completely. For partial updates, use edit_file.""",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
            "create_directories": {
                "type": "boolean",
                "default": True,
                "description": "Create parent directories if they don't exist",
            },
        },
        "required": ["file_path", "content"],
    },
)
EDIT_FILE_TOOL = ToolDefinition(
    name="edit_file",
    description="""Edit a file by replacing specific text.
Use this to:
- Fix bugs in code
- Update function implementations
- Modify configuration values
- Refactor specific sections
The old_string must match exactly (including whitespace). Use replace_all=true to replace all occurrences.""",
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to edit",
            },
            "old_string": {
                "type": "string",
                "minLength": 1,
                "description": "Exact string to find and replace",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement string (can be empty to delete)",
            },
            "replace_all": {
                "type": "boolean",
                "default": False,
                "description": "Replace all occurrences (default: first only)",
            },
        },
        "required": ["file_path", "old_string", "new_string"],
    },
)
BASH_TOOL = ToolDefinition(
    name="bash",
    description="""Execute a shell command and return the output.
Use this to:
- Run tests (pytest, npm test, etc.)
- Execute build commands
- Run linters and formatters
- Check git status
- Install dependencies
Commands run in a bash shell. Use && to chain commands. Avoid interactive commands.""",
    input_schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "minLength": 1,
                "description": "Shell command to execute",
            },
            "timeout": {
                "type": "integer",
                "minimum": 1000,
                "maximum": 600000,
                "default": 120000,
                "description": "Timeout in milliseconds",
            },
            "working_directory": {
                "type": "string",
                "description": "Directory to run command in",
            },
        },
        "required": ["command"],
    },
)
SEARCH_FILES_TOOL = ToolDefinition(
    name="search_files",
    description="""Search for patterns in files using regex.
Use this to:
- Find function definitions
- Locate usage of variables/functions
- Search for TODO comments
- Find files containing specific patterns
Returns matching file paths and line numbers. Use glob to filter by file type.""",
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "minLength": 1,
                "description": "Regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in",
            },
            "glob": {
                "type": "string",
                "description": "Glob pattern to filter files (e.g., '*.py')",
            },
            "case_insensitive": {
                "type": "boolean",
                "default": False,
                "description": "Case-insensitive search",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000,
                "default": 100,
                "description": "Maximum results to return",
            },
        },
        "required": ["pattern"],
    },
)
DELEGATE_TASK_TOOL = ToolDefinition(
    name="delegate_task",
    description="""Delegate a task to another specialized agent.
Use this to:
- Hand off work to a specialist (architect, implementer, reviewer, etc.)
- Break down complex tasks
- Get expert input on specific areas
The orchestrator uses this to coordinate work across agents.""",
    input_schema={
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "description": "Name of the agent to delegate to",
            },
            "task": {
                "type": "string",
                "minLength": 10,
                "description": "Description of the task to perform",
            },
            "context": {
                "type": "string",
                "description": "Additional context from previous steps",
            },
            "expected_output": {
                "type": "string",
                "description": "Description of expected output format",
            },
        },
        "required": ["agent", "task"],
    },
)
# =============================================================================
# Tool Registry
# =============================================================================
class ToolRegistry:
    """
    Central registry for tool definitions.
    Provides access to tools by name and validation utilities.
    """
    # All available tools
    _tools: ClassVar[dict[str, ToolDefinition]] = {
        "read_file": READ_FILE_TOOL,
        "write_file": WRITE_FILE_TOOL,
        "edit_file": EDIT_FILE_TOOL,
        "bash": BASH_TOOL,
        "search_files": SEARCH_FILES_TOOL,
        "delegate_task": DELEGATE_TASK_TOOL,
    }
    # Validation models
    _validators: ClassVar[dict[str, type[BaseModel]]] = {
        "read_file": ReadFileInput,
        "write_file": WriteFileInput,
        "edit_file": EditFileInput,
        "bash": BashInput,
        "search_files": SearchFilesInput,
        "delegate_task": DelegateTaskInput,
    }
    @classmethod
    def get(cls, name: str) -> ToolDefinition:
        """
        Get a tool definition by name.
        Args:
            name: The tool name.
        Returns:
            The ToolDefinition.
        Raises:
            KeyError: If tool not found.
        """
        if name not in cls._tools:
            raise KeyError(
                f"Tool '{name}' not found. Available: {list(cls._tools.keys())}"
            )
        return cls._tools[name]
    @classmethod
    def get_tools(cls, tool_names: list[str]) -> list[dict[str, Any]]:
        """
        Get multiple tools in API format.
        Args:
            tool_names: List of tool names to retrieve.
        Returns:
            List of tool definitions in Claude API format.
        Raises:
            KeyError: If any tool not found.
        """
        return [cls.get(name).to_api_format() for name in tool_names]
    @classmethod
    def get_all(cls) -> list[dict[str, Any]]:
        """Get all tools in API format."""
        return [tool.to_api_format() for tool in cls._tools.values()]
    @classmethod
    def list_names(cls) -> list[str]:
        """List all available tool names."""
        return list(cls._tools.keys())
    @classmethod
    def validate_input(cls, tool_name: str, input_data: dict[str, Any]) -> bool:
        """
        Validate input data against a tool's schema.
        Args:
            tool_name: The tool to validate against.
            input_data: The input data to validate.
        Returns:
            True if valid.
        Raises:
            KeyError: If tool not found.
            ValueError: If validation fails (with details).
        """
        if tool_name not in cls._validators:
            raise KeyError(f"No validator for tool '{tool_name}'")
        validator = cls._validators[tool_name]
        try:
            validator.model_validate(input_data)
            return True
        except Exception as e:
            raise ValueError(f"Validation failed for {tool_name}: {e}") from e
    @classmethod
    def parse_input(cls, tool_name: str, input_data: dict[str, Any]) -> BaseModel:
        """
        Parse and validate input, returning typed model.
        Args:
            tool_name: The tool name.
            input_data: Raw input data.
        Returns:
            Validated Pydantic model instance.
        Raises:
            KeyError: If tool not found.
            ValidationError: If input invalid.
        """
        if tool_name not in cls._validators:
            raise KeyError(f"No validator for tool '{tool_name}'")
        validator = cls._validators[tool_name]
        return validator.model_validate(input_data)
    @classmethod
    def register(
        cls,
        tool: ToolDefinition,
        validator: type[BaseModel] | None = None,
    ) -> None:
        """
        Register a new tool.
        Args:
            tool: The ToolDefinition to register.
            validator: Optional Pydantic model for input validation.
        """
        cls._tools[tool.name] = tool
        if validator:
            cls._validators[tool.name] = validator
# =============================================================================
# Tool Sets for Common Workflows
# =============================================================================
class ToolSets:
    """Pre-defined tool sets for different agent types."""
    # Read-only tools for analysis
    READONLY: ClassVar[list[str]] = ["read_file", "search_files"]
    # Full file system access
    FILESYSTEM: ClassVar[list[str]] = ["read_file", "write_file", "edit_file", "search_files"]
    # Execution tools
    EXECUTION: ClassVar[list[str]] = ["bash"]
    # Full development toolset
    DEVELOPER: ClassVar[list[str]] = [
        "read_file",
        "write_file",
        "edit_file",
        "bash",
        "search_files",
    ]
    # Orchestrator tools
    ORCHESTRATOR: ClassVar[list[str]] = [
        "read_file",
        "search_files",
        "delegate_task",
    ]
    # Reviewer tools (read + execute tests)
    REVIEWER: ClassVar[list[str]] = [
        "read_file",
        "search_files",
        "bash",
    ]
    @classmethod
    def get(cls, set_name: str) -> list[str]:
        """
        Get a predefined tool set by name.
        Args:
            set_name: Name of the tool set.
        Returns:
            List of tool names.
        """
        sets = {
            "readonly": cls.READONLY,
            "filesystem": cls.FILESYSTEM,
            "execution": cls.EXECUTION,
            "developer": cls.DEVELOPER,
            "orchestrator": cls.ORCHESTRATOR,
            "reviewer": cls.REVIEWER,
        }
        if set_name not in sets:
            raise KeyError(
                f"Tool set '{set_name}' not found. Available: {list(sets.keys())}"
            )
        return sets[set_name]
    @classmethod
    def get_tools(cls, set_name: str) -> list[dict[str, Any]]:
        """Get tool definitions for a tool set."""
        return ToolRegistry.get_tools(cls.get(set_name))
# =============================================================================
# Convenience Functions
# =============================================================================
def get_tool(name: str) -> ToolDefinition:
    """Shorthand for ToolRegistry.get()."""
    return ToolRegistry.get(name)
def get_tools(names: list[str]) -> list[dict[str, Any]]:
    """Shorthand for ToolRegistry.get_tools()."""
    return ToolRegistry.get_tools(names)
def validate_tool_input(tool_name: str, input_data: dict[str, Any]) -> bool:
    """Shorthand for ToolRegistry.validate_input()."""
    return ToolRegistry.validate_input(tool_name, input_data)
def developer_tools() -> list[dict[str, Any]]:
    """Get the standard developer tool set."""
    return ToolSets.get_tools("developer")
def orchestrator_tools() -> list[dict[str, Any]]:
    """Get the orchestrator tool set."""
    return ToolSets.get_tools("orchestrator")
