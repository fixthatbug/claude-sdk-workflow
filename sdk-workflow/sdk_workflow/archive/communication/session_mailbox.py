"""
SessionMailbox Bridge - Connects SessionTracker to Mailbox IPC.
Automatically forwards session state changes to mailbox for cross-process communication.
.. deprecated:: 1.0.0
   SessionMailboxBridge is deprecated and will be removed in version 2.0.0.
   Use MessageBus integration with SessionTracker instead.
   See DEPRECATION.md for migration guide.
"""
from __future__ import annotations
import logging
import warnings
from typing import Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from sdk_workflow.communication.session_tracker import SessionTracker, SessionState
logger = logging.getLogger(__name__)
class SessionMailboxBridge:
    """
    Bridges SessionTracker to Mailbox for automatic session state updates.
    This class subscribes to SessionTracker state change callbacks and forwards
    state transitions to mailbox.
    Example:
        tracker = SessionTracker()
        bridge = SessionMailboxBridge(tracker)
        # Register a session
        session_id = tracker.register("my-session")
        # State changes are automatically sent via mailbox
        tracker.start(session_id) # → Mailbox message sent
        tracker.complete(session_id) # → Mailbox message sent
    """
    def __init__(
        self,
        tracker: 'SessionTracker',
        recipient: str = 'claude-code',
        use_compact_protocol: bool = True
    ):
        """
        Initialize the session-to-mailbox bridge.
        .. deprecated:: 1.0.0
           SessionMailboxBridge is deprecated. Use MessageBus integration instead.
        Args:
            tracker: SessionTracker instance to monitor
            recipient: Recipient ID for state change messages (default: 'claude-code')
            use_compact_protocol: Use compact protocol (default: True)
        """
        warnings.warn(
            "SessionMailboxBridge is deprecated and will be removed in version 2.0.0. "
            "Use MessageBus integration with SessionTracker instead. "
            "See DEPRECATION.md for migration guide.",
            DeprecationWarning,
            stacklevel=2
        )
        self._tracker = tracker
        self._recipient = recipient
        self._use_compact = use_compact_protocol
        # Subscribe to session state changes
        tracker.add_state_change_callback(self._on_state_change)
        logger.info("SessionMailboxBridge initialized")
    def _on_state_change(
        self,
        session_id: str,
        old_state: 'SessionState',
        new_state: 'SessionState'
    ) -> None:
        """
        Handle session state changes from SessionTracker.
        Args:
            session_id: ID of the session that changed
            old_state: Previous state
            new_state: New state
        """
        try:
            from sdk_workflow.core.mailbox import Mailbox, MessageType
            # Create mailbox for this session
            mailbox = Mailbox(session_id)
            # Map SessionState to progress state codes
            state_map = {
                'created': 'pen',
                'starting': 'run',
                'running': 'run',
                'paused': 'pau',
                'completing': 'run',
                'completed': 'ok',
                'failed': 'err',
                'terminated': 'can'
            }
            if self._use_compact:
                # Use compact protocol
                from sdk_workflow.core.mailbox_protocol import StatusProtocol, StateCode
                # Get state code
                state_str = state_map.get(new_state.value, 'run')
                try:
                    state_code = StateCode(state_str)
                except ValueError:
                    state_code = StateCode.RUNNING
                # Determine phase based on state
                phase_map = {
                    'created': 'init',
                    'starting': 'star',
                    'running': 'run',
                    'paused': 'paus',
                    'completing': 'comp',
                    'completed': 'done',
                    'failed': 'fail',
                    'terminated': 'term'
                }
                phase = phase_map.get(new_state.value, 'unkn')
                # Estimate progress based on state
                progress_map = {
                    'created': 0.0,
                    'starting': 0.1,
                    'running': 0.5,
                    'paused': 0.5,
                    'completing': 0.9,
                    'completed': 1.0,
                    'failed': 0.0,
                    'terminated': 0.0
                }
                progress = progress_map.get(new_state.value, 0.0)
                status = StatusProtocol(
                    ph=phase,
                    pg=progress,
                    st=state_code,
                    sm=f"State: {old_state.value} → {new_state.value}"
                )
                payload = status.to_payload()
            else:
                # Use verbose format
                payload = {
                    'event': 'state_change',
                    'session_id': session_id,
                    'from': old_state.value,
                    'to': new_state.value,
                    'timestamp': datetime.now().isoformat()
                }
            mailbox.send(
                recipient=self._recipient,
                msg_type=MessageType.STATUS,
                payload=payload,
                priority=1,
                ttl=300
            )
            logger.debug(f"Forwarded state change for {session_id}: {old_state.value} → {new_state.value}")
        except Exception as e:
            logger.error(f"Error forwarding session state change: {e}", exc_info=True)
    def enable_compact_protocol(self) -> None:
        """Enable compact protocol (ph, pg, st, sm)."""
        self._use_compact = True
        logger.debug("Enabled compact protocol")
    def disable_compact_protocol(self) -> None:
        """Disable compact protocol (use verbose format)."""
        self._use_compact = False
        logger.debug("Disabled compact protocol")
    def set_recipient(self, recipient: str) -> None:
        """
        Change the recipient for state change messages.
        Args:
            recipient: New recipient ID
        """
        self._recipient = recipient
        logger.debug(f"Changed recipient to {recipient}")
# Import datetime for timestamp
from datetime import datetime
