"""
Status protocol for token-efficient mailbox messages.
Provides compact field codes (ph, pg, st, sm, tk, cs) for status updates.
"""
from __future__ import annotations
# =============================================================================
# DEPRECATION WARNING
# =============================================================================
# This module is DEPRECATED and will be removed in a future version.
#
# The mailbox system has been replaced with TodoWrite-based progress tracking.
# This module is archived and should not be used for new development.
#
# Migration: Use TodoWrite tool for progress tracking instead.
# See: sdk_workflow/DEPRECATION.md for migration guide.
# =============================================================================
import warnings
warnings.warn(
    f"{__name__} is deprecated and will be removed. Use TodoWrite for progress tracking.",
    DeprecationWarning,
    stacklevel=2
)
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any
import logging
logger = logging.getLogger(__name__)
class StateCode(str, Enum):
    """Compact state codes for status protocol."""
    RUNNING = "run" # Currently executing
    PAUSED = "pau" # Paused/suspended
    COMPLETED = "ok" # Successfully completed
    ERROR = "err" # Error occurred
    WAITING = "wai" # Waiting for input/resource
    PENDING = "pen" # Pending/queued
    CANCELLED = "can" # Cancelled/aborted
@dataclass
class StatusProtocol:
    """
    Compact status protocol for token-efficient progress updates.
    Field Codes:
    - ph: phase (current phase name, max 4 chars recommended)
    - pg: progress (0.0-1.0)
    - st: state (StateCode: run/pau/ok/err/wai/pen/can)
    - sm: summary (brief message, max 50 chars recommended)
    - tk: tokens (optional token usage count)
    - cs: cost (optional cost in USD)
    Example:
        status = StatusProtocol(
            ph="impl",
            pg=0.75,
            st=StateCode.RUNNING,
            sm="Writing tests",
            tk=1234,
            cs=0.05
        )
        payload = status.to_payload()
        # {"ph":"impl","pg":0.75,"st":"run","sm":"Writing tests","tk":1234,"cs":0.05}
    """
    ph: str # phase
    pg: float # progress (0.0-1.0)
    st: StateCode # state code
    sm: str # summary message
    tk: Optional[int] = None # tokens used
    cs: Optional[float] = None # cost in USD
    def to_payload(self) -> Dict[str, Any]:
        """
        Convert to compact payload dictionary for message transmission.
        Returns:
            Dictionary with compact field names and optimized values
        """
        payload = {
            'ph': self.ph[:4] if len(self.ph) > 4 else self.ph, # Truncate phase to 4 chars
            'pg': round(self.pg, 2), # Round progress to 2 decimals
            'st': self.st.value if isinstance(self.st, StateCode) else self.st,
            'sm': self.sm[:50] if len(self.sm) > 50 else self.sm # Truncate summary
        }
        # Only include optional fields if they have values
        if self.tk is not None:
            payload['tk'] = self.tk
        if self.cs is not None:
            payload['cs'] = round(self.cs, 4) # Round cost to 4 decimals
        return payload
    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> 'StatusProtocol':
        """
        Reconstruct StatusProtocol from compact payload.
        Args:
            payload: Dictionary with compact field names
        Returns:
            StatusProtocol instance
        """
        # Convert state string to StateCode enum
        state_str = payload['st']
        state = StateCode(state_str) if isinstance(state_str, str) else state_str
        return cls(
            ph=payload['ph'],
            pg=payload['pg'],
            st=state,
            sm=payload['sm'],
            tk=payload.get('tk'),
            cs=payload.get('cs')
        )
    def to_verbose_dict(self) -> Dict[str, Any]:
        """
        Convert to verbose dictionary with full field names.
        Useful for logging and debugging.
        Returns:
            Dictionary with descriptive field names
        """
        result = {
            'phase': self.ph,
            'progress': self.pg,
            'state': self.st.value if isinstance(self.st, StateCode) else self.st,
            'summary': self.sm
        }
        if self.tk is not None:
            result['tokens'] = self.tk
        if self.cs is not None:
            result['cost_usd'] = self.cs
        return result
    def __str__(self) -> str:
        """Human-readable string representation."""
        parts = [
            f"[{self.st.value.upper()}]",
            f"{self.ph}",
            f"({self.pg:.0%})",
            f"- {self.sm}"
        ]
        if self.tk is not None:
            parts.append(f"| {self.tk} tokens")
        if self.cs is not None:
            parts.append(f"| ${self.cs:.4f}")
        return " ".join(parts)
def create_status(
    phase: str,
    progress: float,
    state: StateCode | str,
    summary: str,
    tokens: Optional[int] = None,
    cost: Optional[float] = None
) -> StatusProtocol:
    """
    Convenience function to create a StatusProtocol instance.
    Args:
        phase: Current phase name (will be truncated to 4 chars)
        progress: Progress as float 0.0-1.0
        state: State code (StateCode enum or string)
        summary: Brief status summary (will be truncated to 50 chars)
        tokens: Optional token usage count
        cost: Optional cost in USD
    Returns:
        StatusProtocol instance
    """
    # Convert string state to StateCode if needed
    if isinstance(state, str):
        try:
            state = StateCode(state)
        except ValueError:
            logger.warning(f"Unknown state code '{state}', using RUNNING")
            state = StateCode.RUNNING
    return StatusProtocol(
        ph=phase,
        pg=progress,
        st=state,
        sm=summary,
        tk=tokens,
        cs=cost
    )
def parse_status(payload: Dict[str, Any]) -> StatusProtocol:
    """
    Parse a status payload into a StatusProtocol instance.
    Alias for StatusProtocol.from_payload() for convenience.
    Args:
        payload: Dictionary with compact or verbose field names
    Returns:
        StatusProtocol instance
    """
    # Handle both compact and verbose formats
    if 'ph' in payload:
        # Compact format
        return StatusProtocol.from_payload(payload)
    elif 'phase' in payload:
        # Verbose format - convert to compact
        compact = {
            'ph': payload['phase'],
            'pg': payload['progress'],
            'st': payload['state'],
            'sm': payload['summary'],
        }
        if 'tokens' in payload:
            compact['tk'] = payload['tokens']
        if 'cost_usd' in payload or 'cost' in payload:
            compact['cs'] = payload.get('cost_usd') or payload.get('cost')
        return StatusProtocol.from_payload(compact)
    else:
        raise ValueError(f"Invalid status payload format: {payload}")
