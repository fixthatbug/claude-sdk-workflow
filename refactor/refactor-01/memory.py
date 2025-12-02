"""Memory Tool Validator - Secure memory path validation."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MemoryToolValidator:
    """Validate and sanitize memory tool operations."""
    
    ALLOWED_BASE_PATHS = [
        "/memories",
        "/mnt/user-data",
        ".claude/memory",
    ]
    
    FORBIDDEN_PATTERNS = [
        r"\.\./",           # Path traversal
        r"~",               # Home expansion
        r"\$\{",            # Variable expansion
        r";",               # Command injection
        r"\|",              # Pipe
        r"`",               # Backtick execution
        r"\x00",            # Null byte
    ]
    
    ALLOWED_COMMANDS = ["create", "read", "update", "delete", "list"]
    
    def __init__(self, custom_base_paths: Optional[List[str]] = None):
        self.base_paths = custom_base_paths or self.ALLOWED_BASE_PATHS
    
    def validate_path(self, path: str) -> bool:
        """Validate a memory path is safe."""
        # Check for forbidden patterns
        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, path):
                logger.warning(f"Forbidden pattern in path: {pattern}")
                return False
        
        # Check path is under allowed base
        normalized = str(Path(path).resolve()) if not path.startswith("/") else path
        is_allowed = any(
            normalized.startswith(base) or path.startswith(base)
            for base in self.base_paths
        )
        
        if not is_allowed:
            logger.warning(f"Path not under allowed base: {path}")
        
        return is_allowed
    
    def sanitize_path(self, path: str) -> str:
        """Sanitize a path for safe use."""
        # Remove dangerous characters
        sanitized = path
        for pattern in self.FORBIDDEN_PATTERNS:
            sanitized = re.sub(pattern, "", sanitized)
        
        # Normalize
        sanitized = sanitized.strip().replace("//", "/")
        
        return sanitized
    
    def validate_command(
        self,
        command: str,
        path: str,
        content: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate a complete memory command.
        
        Returns (is_valid, error_message).
        """
        # Check command
        if command.lower() not in self.ALLOWED_COMMANDS:
            return False, f"Unknown command: {command}"
        
        # Check path
        if not self.validate_path(path):
            return False, f"Invalid path: {path}"
        
        # Check content for dangerous patterns
        if content:
            for pattern in self.FORBIDDEN_PATTERNS:
                if re.search(pattern, content):
                    return False, f"Content contains forbidden pattern"
        
        return True, None
    
    def validate_content_size(
        self,
        content: str,
        max_size_bytes: int = 1_000_000  # 1MB default
    ) -> bool:
        """Validate content is within size limits."""
        return len(content.encode('utf-8')) <= max_size_bytes


__all__ = ['MemoryToolValidator']
