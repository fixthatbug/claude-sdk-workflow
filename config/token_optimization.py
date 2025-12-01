"""Token optimization configuration for SDK workflow.
Minimizes token usage across all communications without affecting output quality.
"""
from dataclasses import dataclass
from typing import Dict, Any
@dataclass
class TokenLimits:
    """Token limits per model tier."""
    haiku_max: int = 4096
    sonnet_max: int = 8192
    opus_max: int = 16384
    context_reserve: float = 0.1 # Reserve 10% for response
    def get_effective_limit(self, model: str) -> int:
        """Get effective token limit after reserving space for response."""
        limits = {
            'haiku': self.haiku_max,
            'sonnet': self.sonnet_max,
            'opus': self.opus_max,
        }
        base = limits.get(model, self.sonnet_max)
        return int(base * (1 - self.context_reserve))
COMPRESSION_THRESHOLDS = {
    'context_ratio': 0.7, # Compress when context > 70% of limit
    'message_count': 20, # Compress after 20 messages
    'phase_boundary': True, # Always compress between phases
}
# Short keys for JSON compression - minimizes token usage in IPC
SHORT_KEYS: Dict[str, str] = {
    # Message fields
    'id': 'i',
    'sender': 's',
    'recipient': 'r',
    'type': 't',
    'payload': 'p',
    'timestamp': 'ts',
    'priority': 'pr',
    'ttl': 'ttl',
    'reply_to': 'rt',
    # Status fields
    'phase': 'ph',
    'progress': 'pg',
    'status': 'st',
    'summary': 'sm',
    'tokens': 'tk',
    'cost': 'cs',
    # Session fields
    'session_id': 'sid',
    'message': 'msg',
    'content': 'ct',
    'model': 'md',
    'duration': 'dur',
    # Error fields
    'error': 'err',
    'category': 'cat',
    'severity': 'sev',
}
# Inverse mapping for expansion
FULL_KEYS: Dict[str, str] = {v: k for k, v in SHORT_KEYS.items()}
def compress_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert full keys to short keys for token efficiency.
    Args:
        data: Dictionary with full key names
    Returns:
        Dictionary with shortened keys
    """
    if not isinstance(data, dict):
        return data
    return {
        SHORT_KEYS.get(k, k): compress_keys(v) if isinstance(v, dict) else v
        for k, v in data.items()
    }
def expand_keys(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert short keys back to full keys.
    Args:
        data: Dictionary with short key names
    Returns:
        Dictionary with full keys
    """
    if not isinstance(data, dict):
        return data
    return {
        FULL_KEYS.get(k, k): expand_keys(v) if isinstance(v, dict) else v
        for k, v in data.items()
    }
def estimate_tokens(text: str) -> int:
    """Rough token estimate (4 chars per token average).
    Args:
        text: Text to estimate
    Returns:
        Approximate token count
    """
    return len(text) // 4 + 1
def should_compress_context(
    current_tokens: int,
    model: str,
    message_count: int = 0
) -> bool:
    """Determine if context should be compressed.
    Args:
        current_tokens: Current context size in tokens
        model: Model being used
        message_count: Number of messages in context
    Returns:
        True if compression recommended
    """
    limits = TokenLimits()
    effective_limit = limits.get_effective_limit(model)
    # Check ratio threshold
    if current_tokens > effective_limit * COMPRESSION_THRESHOLDS['context_ratio']:
        return True
    # Check message count threshold
    if message_count >= COMPRESSION_THRESHOLDS['message_count']:
        return True
    return False
# Default instance for convenience
DEFAULT_LIMITS = TokenLimits()
