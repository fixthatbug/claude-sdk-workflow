"""SDK Constants - Shared constants and configuration values."""

# SDK Version
SDK_VERSION = "2.0.0"

# Model defaults
DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_THINKING_BUDGET = 8000
DEFAULT_MAX_TOKENS = 4096

# Available models
MODELS = {
    "opus": "claude-opus-4-20250514",
    "sonnet": "claude-sonnet-4-20250514", 
    "haiku": "claude-haiku-4-20250514",
}

# Tool categories
TOOL_CATEGORIES = {
    "file": ["Read", "Write", "Edit", "Glob", "Grep"],
    "web": ["WebSearch", "WebFetch"],
    "execution": ["Bash", "CodeExecution"],
    "orchestration": ["Task", "TodoRead", "TodoWrite"],
}

# Container configuration
CONTAINER_CONFIG = {
    "memory_gib": 5.0,
    "max_lifetime_days": 30,
    "free_hours_daily": 50.0,
    "hourly_rate_usd": 0.03,
}

# Computer use actions
COMPUTER_USE_ACTIONS = {
    "basic": ["screenshot", "click", "type", "scroll"],
    "enhanced": ["screenshot", "click", "type", "scroll", "key", "wait", "drag"],
    "opus": ["screenshot", "click", "type", "scroll", "key", "wait", "drag", "move", "double_click"],
}

# Rate limits (per minute)
RATE_LIMITS = {
    "opus": {"requests": 40, "tokens": 80000},
    "sonnet": {"requests": 50, "tokens": 100000},
    "haiku": {"requests": 100, "tokens": 200000},
}

__all__ = [
    'SDK_VERSION',
    'DEFAULT_MODEL',
    'DEFAULT_THINKING_BUDGET',
    'DEFAULT_MAX_TOKENS',
    'MODELS',
    'TOOL_CATEGORIES',
    'CONTAINER_CONFIG',
    'COMPUTER_USE_ACTIONS',
    'RATE_LIMITS',
]
