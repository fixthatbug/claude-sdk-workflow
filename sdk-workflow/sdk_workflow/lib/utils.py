"""
Utility functions for SDK workflow operations.
Provides path handling, directory management, and formatting helpers
used across the sdk-workflow package.
"""
from pathlib import Path
from typing import Optional
import os
import json
import hashlib
def get_workflow_dir() -> Path:
    """Get the root sdk-workflow directory path.
    Returns:
        Path to ~/.claude/sdk-workflow
    """
    return Path.home() / ".claude" / "sdk-workflow"
def get_sessions_dir() -> Path:
    """Get the sessions storage directory path.
    Returns:
        Path to ~/.claude/sdk-workflow/sessions
    """
    return get_workflow_dir() / "sessions"
def get_logs_dir() -> Path:
    """Get the logs directory path.
    Returns:
        Path to ~/.claude/sdk-workflow/logs
    """
    return get_workflow_dir() / "logs"
def get_cache_dir() -> Path:
    """Get the cache directory path.
    Returns:
        Path to ~/.claude/sdk-workflow/cache
    """
    return get_workflow_dir() / "cache"
def get_resources_dir() -> Path:
    """Get the resources directory path.
    Returns:
        Path to ~/.claude/sdk-workflow/resources
    """
    return get_workflow_dir() / "resources"
def ensure_dirs() -> None:
    """Create all required directories if they don't exist.
    Creates:
        - ~/.claude/sdk-workflow/
        - ~/.claude/sdk-workflow/sessions/
        - ~/.claude/sdk-workflow/logs/
        - ~/.claude/sdk-workflow/cache/
        - ~/.claude/sdk-workflow/resources/
        - ~/.claude/sdk-workflow/lib/
        - ~/.claude/sdk-workflow/cli/
    """
    directories = [
        get_workflow_dir(),
        get_sessions_dir(),
        get_logs_dir(),
        get_cache_dir(),
        get_resources_dir(),
        get_workflow_dir() / "lib",
        get_workflow_dir() / "cli",
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
def format_cost(cost: float) -> str:
    """Format a cost value as a currency string.
    Args:
        cost: Cost in dollars (float)
    Returns:
        Formatted string like "$0.0042" or "$1.23"
    """
    if cost < 0.01:
        return f"${cost:.4f}"
    elif cost < 1.0:
        return f"${cost:.3f}"
    else:
        return f"${cost:.2f}"
def format_tokens(tokens: int) -> str:
    """Format token count with appropriate suffix.
    Args:
        tokens: Number of tokens
    Returns:
        Formatted string like "1.5K" or "2.3M" or "500"
    """
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    elif tokens >= 1_000:
        return f"{tokens / 1_000:.1f}K"
    else:
        return str(tokens)
def truncate_text(text: str, max_len: int, suffix: str = "...") -> str:
    """Truncate text to maximum length with suffix.
    Args:
        text: Text to truncate
        max_len: Maximum length including suffix
        suffix: String to append when truncated (default: "...")
    Returns:
        Truncated text with suffix if it exceeded max_len
    """
    if len(text) <= max_len:
        return text
    truncate_at = max_len - len(suffix)
    if truncate_at <= 0:
        return suffix[:max_len]
    return text[:truncate_at] + suffix
def safe_path(path_str: str) -> Path:
    """Convert string to Path, expanding user and resolving.
    Args:
        path_str: Path string, may contain ~ or relative components
    Returns:
        Resolved absolute Path object
    """
    return Path(path_str).expanduser().resolve()
def get_session_file(session_id: str) -> Path:
    """Get the path to a session's state file.
    Args:
        session_id: Unique session identifier
    Returns:
        Path to the session JSON file
    """
    return get_sessions_dir() / f"{session_id}.json"
def generate_session_id() -> str:
    """Generate a unique session identifier.
    Returns:
        UUID-based session ID string
    """
    import uuid
    return str(uuid.uuid4())[:8]
def get_env_or_default(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get environment variable with optional default.
    Args:
        key: Environment variable name
        default: Default value if not set
    Returns:
        Environment variable value or default
    """
    return os.environ.get(key, default)
def format_duration(seconds: float) -> str:
    """Format duration in human-readable form.
    Args:
        seconds: Duration in seconds
    Returns:
        Formatted string like "1.2s" or "2m 30s" or "1h 5m"
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename.
    Args:
        name: Original string
    Returns:
        Sanitized string safe for filenames
    """
    import re
    # Replace invalid characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Collapse multiple underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    # Trim to reasonable length
    return sanitized[:100].strip('_')
def get_sdk_workflow_path() -> Path:
    """Get the root path to sdk-workflow directory.
    Returns:
        Path to ~/.claude/sdk-workflow
    Note:
        This is an alias for get_workflow_dir() for consistency with naming.
    """
    return get_workflow_dir()
def ensure_directory(path: Path) -> None:
    """Create directory if it doesn't exist.
    Args:
        path: Path to directory to create
    Creates parent directories as needed.
    """
    Path(path).mkdir(parents=True, exist_ok=True)
def safe_json_loads(text: str) -> Optional[dict]:
    """Parse JSON with error handling.
    Args:
        text: JSON string to parse
    Returns:
        Parsed dict if successful, None if parsing fails
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
def hash_content(content: str) -> str:
    """Generate SHA256 hash of content for caching keys.
    Args:
        content: String content to hash
    Returns:
        Hexadecimal hash string (64 characters)
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
def parse_model_name(name: str) -> str:
    """Normalize model names to full API identifiers.
    Args:
        name: Short model name (e.g., "haiku", "sonnet", "opus")
    Returns:
        Full model identifier for API calls
    Examples:
        >>> parse_model_name("haiku")
        'claude-haiku-4-5-20251001'
        >>> parse_model_name("sonnet")
        'claude-sonnet-4-5-20250929'
        >>> parse_model_name("opus")
        'claude-opus-4-5-20251101'
        >>> parse_model_name("claude-sonnet-4-5-20250929")
        'claude-sonnet-4-5-20250929'
    """
    # Model name mapping - Claude 4.5 models only
    model_map = {
        "haiku": "claude-haiku-4-5-20251001",
        "sonnet": "claude-sonnet-4-5-20250929",
        "opus": "claude-opus-4-5-20251101",
        "4.5-haiku": "claude-haiku-4-5-20251001",
        "4.5-sonnet": "claude-sonnet-4-5-20250929",
        "4.5-opus": "claude-opus-4-5-20251101",
    }
    # Normalize input
    name_lower = name.lower().strip()
    # If already a full model name, return it
    if name_lower.startswith("claude-"):
        return name
    # Map short name to full name
    return model_map.get(name_lower, name)
