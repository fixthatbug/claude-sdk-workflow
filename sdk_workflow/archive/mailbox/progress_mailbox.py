"""
ProgressMailbox Bridge - Connects ProgressTracker to Mailbox IPC.
Automatically forwards progress updates to mailbox for cross-process communication.
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
import logging
from typing import Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from sdk_workflow.core.mailbox import Mailbox
    from sdk_workflow.communication.progress import ProgressTracker, ProgressSnapshot
from .progress import ProgressStatus
logger = logging.getLogger(__name__)
class ProgressMailboxBridge:
    """
    Bridges ProgressTracker to Mailbox for automatic status updates.
    This class subscribes to ProgressTracker callbacks and forwards progress
    updates to a mailbox using the compact status protocol.
    Example:
        tracker = ProgressTracker("session-123")
        mailbox = Mailbox("session-123")
        bridge = ProgressMailboxBridge(tracker, mailbox)
        # Now all progress updates are automatically sent via mailbox
        tracker.start()
        tracker.update("impl", 1, 10, "Implementing feature")
        # → Mailbox message sent to 'claude-code'
    """
    def __init__(
        self,
        tracker: 'ProgressTracker',
        mailbox: 'Mailbox',
        recipient: str = 'claude-code',
        use_compact_protocol: bool = True
    ):
        """
        Initialize the progress-to-mailbox bridge.
        Args:
            tracker: ProgressTracker instance to monitor
            mailbox: Mailbox instance for sending updates
            recipient: Recipient ID for status messages (default: 'claude-code')
            use_compact_protocol: Use compact protocol (ph,pg,st,sm) (default: True)
        """
        self._tracker = tracker
        self._mailbox = mailbox
        self._recipient = recipient
        self._use_compact = use_compact_protocol
        # Subscribe to progress tracker callbacks
        tracker.add_update_callback(self._on_progress_update)
        tracker.add_complete_callback(self._on_complete)
        tracker.add_error_callback(self._on_error)
        logger.info(f"ProgressMailboxBridge initialized for {tracker.session_id}")
    def _on_progress_update(self, snapshot: 'ProgressSnapshot') -> None:
        """
        Handle progress updates from ProgressTracker.
        Args:
            snapshot: Current progress snapshot
        """
        try:
            from sdk_workflow.core.mailbox import MessageType
            # Map ProgressStatus to state code
            state_map = {
                ProgressStatus.PENDING: 'pen',
                ProgressStatus.RUNNING: 'run',
                ProgressStatus.PAUSED: 'pau',
                ProgressStatus.COMPLETED: 'ok',
                ProgressStatus.FAILED: 'err',
                ProgressStatus.CANCELLED: 'can'
            }
            state = state_map.get(snapshot.status, 'run')
            if self._use_compact:
                # Use compact protocol
                from sdk_workflow.core.mailbox_protocol import StatusProtocol, StateCode
                # Convert state string to StateCode
                try:
                    state_code = StateCode(state)
                except ValueError:
                    state_code = StateCode.RUNNING
                status = StatusProtocol(
                    ph=snapshot.current_phase or 'init',
                    pg=snapshot.overall_progress_pct / 100, # Convert 0-100 to 0.0-1.0
                    st=state_code,
                    sm=snapshot.message[:50] # Truncate to 50 chars
                )
                payload = status.to_payload()
            else:
                # Use verbose format
                payload = {
                    'phase': snapshot.current_phase or 'init',
                    'progress': round(snapshot.overall_progress_pct / 100, 2),
                    'status': snapshot.status.value,
                    'message': snapshot.message,
                    'elapsed_seconds': snapshot.elapsed_seconds
                }
            self._mailbox.send(
                recipient=self._recipient,
                msg_type=MessageType.STATUS,
                payload=payload,
                priority=1,
                ttl=300 # 5 minute TTL for status updates
            )
            logger.debug(
                f"Forwarded progress update: {snapshot.current_phase} "
                f"({snapshot.overall_progress_pct:.1f}%)"
            )
        except Exception as e:
            logger.error(f"Error forwarding progress update: {e}", exc_info=True)
    def _on_complete(self, result: any) -> None:
        """
        Handle completion from ProgressTracker.
        Args:
            result: The completion result
        """
        try:
            from sdk_workflow.core.mailbox import MessageType
            if self._use_compact:
                from sdk_workflow.core.mailbox_protocol import StatusProtocol, StateCode
                status = StatusProtocol(
                    ph='done',
                    pg=1.0,
                    st=StateCode.COMPLETED,
                    sm='Completed successfully'
                )
                payload = status.to_payload()
            else:
                payload = {
                    'phase': 'completed',
                    'progress': 1.0,
                    'status': 'completed',
                    'message': 'Task completed successfully'
                }
            self._mailbox.send(
                recipient=self._recipient,
                msg_type=MessageType.STATUS,
                payload=payload,
                priority=1,
                ttl=600 # Keep completion status longer
            )
            logger.info("Forwarded completion status")
        except Exception as e:
            logger.error(f"Error forwarding completion: {e}", exc_info=True)
    def _on_error(self, error: str) -> None:
        """
        Handle error from ProgressTracker.
        Args:
            error: Error message
        """
        try:
            from sdk_workflow.core.mailbox import MessageType
            if self._use_compact:
                from sdk_workflow.core.mailbox_protocol import StatusProtocol, StateCode
                status = StatusProtocol(
                    ph='err',
                    pg=0.0,
                    st=StateCode.ERROR,
                    sm=error[:50] # Truncate error message
                )
                payload = status.to_payload()
            else:
                payload = {
                    'phase': 'error',
                    'progress': 0.0,
                    'status': 'failed',
                    'message': error
                }
            self._mailbox.send(
                recipient=self._recipient,
                msg_type=MessageType.STATUS,
                payload=payload,
                priority=2, # Higher priority for errors
                ttl=600 # Keep error status longer
            )
            logger.warning(f"Forwarded error status: {error}")
        except Exception as e:
            logger.error(f"Error forwarding error status: {e}", exc_info=True)
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
        Change the recipient for status messages.
        Args:
            recipient: New recipient ID
        """
        self._recipient = recipient
        logger.debug(f"Changed recipient to {recipient}")
