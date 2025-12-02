"""Tool Response Parser - Parse SDK tool results."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Parsed tool result."""
    tool_name: str
    success: bool
    content: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw: Optional[Any] = None


class ToolResponseParser:
    """Parse responses from various SDK tools."""
    
    # Known tool response types
    TOOL_TYPES = {
        "web_search": "search_results",
        "web_fetch": "page_content",
        "code_execution": "execution_result",
        "file_read": "file_content",
        "file_write": "write_result",
        "bash": "command_output",
        "computer_use": "action_result",
        "mcp": "mcp_response",
    }
    
    def __init__(self):
        self._parsers = {
            "web_search": self._parse_search,
            "web_fetch": self._parse_fetch,
            "code_execution": self._parse_execution,
            "bash": self._parse_bash,
            "file_read": self._parse_file,
        }
    
    def parse(self, tool_name: str, result: Any) -> ToolResult:
        """Parse a tool result based on tool type."""
        parser = self._parsers.get(tool_name, self._parse_generic)
        try:
            return parser(tool_name, result)
        except Exception as e:
            logger.warning(f"Parse error for {tool_name}: {e}")
            return ToolResult(
                tool_name=tool_name,
                success=False,
                content=None,
                error=str(e),
                raw=result
            )
    
    def _parse_generic(self, tool_name: str, result: Any) -> ToolResult:
        """Generic parser for unknown tools."""
        if isinstance(result, dict):
            success = not result.get("error")
            content = result.get("content", result.get("result", result))
            error = result.get("error")
        elif isinstance(result, str):
            success = True
            content = result
            error = None
        else:
            success = result is not None
            content = result
            error = None
        
        return ToolResult(
            tool_name=tool_name,
            success=success,
            content=content,
            error=error,
            raw=result
        )
    
    def _parse_search(self, tool_name: str, result: Any) -> ToolResult:
        """Parse web search results."""
        if isinstance(result, dict):
            results = result.get("results", [])
            return ToolResult(
                tool_name=tool_name,
                success=len(results) > 0,
                content=results,
                metadata={"result_count": len(results)},
                raw=result
            )
        return self._parse_generic(tool_name, result)
    
    def _parse_fetch(self, tool_name: str, result: Any) -> ToolResult:
        """Parse web fetch results."""
        if isinstance(result, dict):
            content = result.get("content", result.get("text", ""))
            return ToolResult(
                tool_name=tool_name,
                success=bool(content),
                content=content,
                metadata={
                    "url": result.get("url"),
                    "status": result.get("status"),
                },
                raw=result
            )
        return self._parse_generic(tool_name, result)
    
    def _parse_execution(self, tool_name: str, result: Any) -> ToolResult:
        """Parse code execution results."""
        if isinstance(result, dict):
            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            return_code = result.get("return_code", result.get("returncode", 0))
            
            return ToolResult(
                tool_name=tool_name,
                success=return_code == 0,
                content=stdout,
                error=stderr if return_code != 0 else None,
                metadata={
                    "return_code": return_code,
                    "has_stderr": bool(stderr),
                },
                raw=result
            )
        return self._parse_generic(tool_name, result)
    
    def _parse_bash(self, tool_name: str, result: Any) -> ToolResult:
        """Parse bash command results."""
        return self._parse_execution(tool_name, result)
    
    def _parse_file(self, tool_name: str, result: Any) -> ToolResult:
        """Parse file read results."""
        if isinstance(result, str):
            return ToolResult(
                tool_name=tool_name,
                success=True,
                content=result,
                metadata={"length": len(result)},
                raw=result
            )
        return self._parse_generic(tool_name, result)
    
    def extract_text(self, result: ToolResult) -> str:
        """Extract text content from parsed result."""
        if isinstance(result.content, str):
            return result.content
        elif isinstance(result.content, list):
            return "\n".join(str(item) for item in result.content)
        elif isinstance(result.content, dict):
            return json.dumps(result.content, indent=2)
        return str(result.content)


__all__ = ['ToolResult', 'ToolResponseParser']
