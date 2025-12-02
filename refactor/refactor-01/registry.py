"""MCP Server Registry - Manage MCP server connections."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPServer:
    """An MCP server configuration."""
    name: str
    transport: str  # stdio, sse, http
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    url: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    tools: List[str] = field(default_factory=list)
    enabled: bool = True


class MCPServerRegistry:
    """Registry for MCP server configurations."""
    
    def __init__(self):
        self._servers: Dict[str, MCPServer] = {}
    
    def register(self, server: MCPServer) -> None:
        """Register an MCP server."""
        self._servers[server.name] = server
        logger.info(f"Registered MCP server: {server.name}")
    
    def unregister(self, name: str) -> bool:
        """Unregister an MCP server."""
        if name in self._servers:
            del self._servers[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[MCPServer]:
        """Get a server by name."""
        return self._servers.get(name)
    
    def list_servers(self) -> List[str]:
        """List all registered server names."""
        return list(self._servers.keys())
    
    def get_enabled(self) -> List[MCPServer]:
        """Get all enabled servers."""
        return [s for s in self._servers.values() if s.enabled]
    
    def enable(self, name: str) -> bool:
        """Enable a server."""
        server = self._servers.get(name)
        if server:
            server.enabled = True
            return True
        return False
    
    def disable(self, name: str) -> bool:
        """Disable a server."""
        server = self._servers.get(name)
        if server:
            server.enabled = False
            return True
        return False


__all__ = ['MCPServer', 'MCPServerRegistry']
