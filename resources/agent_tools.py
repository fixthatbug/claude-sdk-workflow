"""
Agent Tools - Claude Agent SDK @tool decorated functions.
Provides tool implementations compatible with the SDK's MCP tool system.
The @tool decorator requires:
- name: Tool identifier
- description: What the tool does
- input_schema: Dict mapping param names to types
Functions must be async and return {"content": [...]}
"""
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from claude_agent_sdk import tool
# Dangerous patterns for bash command safety
DANGEROUS_PATTERNS = [
    r'rm\s+-rf\s+/',
    r'rm\s+-rf\s+~',
    r'rm\s+-rf\s+\*',
    r'mkfs\.',
    r'dd\s+if=',
    r'>\s*/dev/sd',
    r'chmod\s+-R\s+777\s+/',
    r'curl.*\|\s*sh',
    r'wget.*\|\s*sh',
]
def is_dangerous_command(command: str) -> bool:
    """Check if a bash command matches dangerous patterns."""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False
def _text_response(text: str, is_error: bool = False) -> Dict[str, Any]:
    """Create a standard text response for tools."""
    response = {"content": [{"type": "text", "text": text}]}
    if is_error:
        response["is_error"] = True
    return response
@tool("read_file", "Read contents of a file with optional line offset and limit", {
    "file_path": str,
    "offset": int,
    "limit": int,
})
async def read_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """Read contents of a file."""
    file_path = args.get("file_path", "")
    offset = args.get("offset", 0) or 0
    limit = args.get("limit", 2000) or 2000
    try:
        path = Path(file_path)
        if not path.exists():
            return _text_response(f"Error: File not found: {file_path}", is_error=True)
        if not path.is_file():
            return _text_response(f"Error: Not a file: {file_path}", is_error=True)
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        # Apply offset and limit
        selected = lines[offset:offset + limit]
        # Format with line numbers
        result = []
        for i, line in enumerate(selected, start=offset + 1):
            result.append(f"{i:>6}\t{line.rstrip()}")
        return _text_response('\n'.join(result))
    except PermissionError:
        return _text_response(f"Error: Permission denied: {file_path}", is_error=True)
    except Exception as e:
        return _text_response(f"Error reading file: {e}", is_error=True)
@tool("write_file", "Write content to a file, creating directories if needed", {
    "file_path": str,
    "content": str,
    "create_directories": bool,
})
async def write_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """Write content to a file."""
    file_path = args.get("file_path", "")
    content = args.get("content", "")
    create_directories = args.get("create_directories", True)
    try:
        path = Path(file_path)
        if create_directories:
            path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return _text_response(f"Successfully wrote {len(content)} bytes to {file_path}")
    except PermissionError:
        return _text_response(f"Error: Permission denied: {file_path}", is_error=True)
    except Exception as e:
        return _text_response(f"Error writing file: {e}", is_error=True)
@tool("edit_file", "Edit a file by replacing old_string with new_string", {
    "file_path": str,
    "old_string": str,
    "new_string": str,
    "replace_all": bool,
})
async def edit_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """Edit a file by replacing text."""
    file_path = args.get("file_path", "")
    old_string = args.get("old_string", "")
    new_string = args.get("new_string", "")
    replace_all = args.get("replace_all", False)
    try:
        path = Path(file_path)
        if not path.exists():
            return _text_response(f"Error: File not found: {file_path}", is_error=True)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Check for matches
        count = content.count(old_string)
        if count == 0:
            return _text_response(
                f"Error: String not found in file: {old_string[:50]}...",
                is_error=True
            )
        if count > 1 and not replace_all:
            return _text_response(
                f"Error: String found {count} times. Use replace_all=true or provide more context.",
                is_error=True
            )
        # Perform replacement
        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        replaced = count if replace_all else 1
        return _text_response(f"Successfully replaced {replaced} occurrence(s) in {file_path}")
    except PermissionError:
        return _text_response(f"Error: Permission denied: {file_path}", is_error=True)
    except Exception as e:
        return _text_response(f"Error editing file: {e}", is_error=True)
@tool("bash", "Execute a bash/shell command with timeout", {
    "command": str,
    "timeout": int,
    "working_directory": str,
})
async def bash(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a bash command."""
    command = args.get("command", "")
    timeout = args.get("timeout", 120) or 120
    working_directory = args.get("working_directory")
    # Safety check
    if is_dangerous_command(command):
        return _text_response(f"Error: Dangerous command blocked: {command}", is_error=True)
    # Limit timeout
    timeout = min(timeout, 600)
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_directory,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        # Truncate if too long
        if len(output) > 30000:
            output = output[:30000] + "\n... (output truncated)"
        return _text_response(output)
    except subprocess.TimeoutExpired:
        return _text_response(f"Error: Command timed out after {timeout} seconds", is_error=True)
    except Exception as e:
        return _text_response(f"Error executing command: {e}", is_error=True)
@tool("search_files", "Search for regex pattern in files under a directory", {
    "pattern": str,
    "path": str,
    "file_pattern": str,
    "max_results": int,
})
async def search_files(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search for text pattern in files."""
    pattern = args.get("pattern", "")
    path = args.get("path", ".") or "."
    file_pattern = args.get("file_pattern")
    max_results = args.get("max_results", 100) or 100
    try:
        search_path = Path(path)
        if not search_path.exists():
            return _text_response(f"Error: Path not found: {path}", is_error=True)
        # Compile regex
        try:
            regex = re.compile(pattern)
        except re.error as e:
            return _text_response(f"Error: Invalid regex pattern: {e}", is_error=True)
        results = []
        files_searched = 0
        # Determine files to search
        if file_pattern:
            files = list(search_path.rglob(file_pattern))
        else:
            files = [f for f in search_path.rglob("*") if f.is_file()]
        for file_path in files:
            if len(results) >= max_results:
                break
            # Skip binary files
            if file_path.suffix.lower() in ['.exe', '.dll', '.so', '.bin', '.pyc', '.jpg', '.png', '.gif']:
                continue
            files_searched += 1
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append(f"{file_path}:{line_num}: {line.rstrip()}")
                            if len(results) >= max_results:
                                break
            except (PermissionError, OSError):
                continue
        output = f"Searched {files_searched} files\n"
        if results:
            output += '\n'.join(results)
        else:
            output += "No matches found"
        if len(results) >= max_results:
            output += f"\n... (limited to {max_results} results)"
        return _text_response(output)
    except Exception as e:
        return _text_response(f"Error searching: {e}", is_error=True)
@tool("glob_files", "Find files matching a glob pattern", {
    "pattern": str,
    "path": str,
    "max_results": int,
})
async def glob_files(args: Dict[str, Any]) -> Dict[str, Any]:
    """Find files matching a glob pattern."""
    pattern = args.get("pattern", "")
    path = args.get("path", ".") or "."
    max_results = args.get("max_results", 100) or 100
    try:
        search_path = Path(path)
        if not search_path.exists():
            return _text_response(f"Error: Path not found: {path}", is_error=True)
        matches = list(search_path.glob(pattern))[:max_results]
        if not matches:
            return _text_response(f"No files match pattern: {pattern}")
        result = [str(m) for m in sorted(matches)]
        if len(matches) >= max_results:
            result.append(f"... (limited to {max_results} results)")
        return _text_response('\n'.join(result))
    except Exception as e:
        return _text_response(f"Error globbing: {e}", is_error=True)
# Tool registry - stores the SdkMcpTool instances
AGENT_TOOLS = {
    'read_file': read_file,
    'write_file': write_file,
    'edit_file': edit_file,
    'bash': bash,
    'search_files': search_files,
    'glob_files': glob_files,
}
def get_agent_tools(tool_names: Optional[List[str]] = None) -> List:
    """
    Get a list of @tool decorated functions.
    Args:
        tool_names: List of tool names to include, or None for all
    Returns:
        List of SdkMcpTool instances
    """
    if tool_names is None:
        return list(AGENT_TOOLS.values())
    tools = []
    for name in tool_names:
        if name in AGENT_TOOLS:
            tools.append(AGENT_TOOLS[name])
    return tools
def get_available_tools() -> List[str]:
    """Get list of available tool names."""
    return list(AGENT_TOOLS.keys())
