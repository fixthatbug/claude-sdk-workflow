"""
Integration examples for mailbox system with orchestrators.
Demonstrates how to use the mailbox for inter-orchestrator communication.
"""
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
from typing import Optional
import logging
from pathlib import Path
from .mailbox import Mailbox, Message, MessageType, send_status, send_signal
logger = logging.getLogger(__name__)
class OrchestratorMailboxMixin:
    """Mixin class to add mailbox capabilities to orchestrators.
    Add this to your StreamingOrchestrator or other orchestrator classes to enable
    mailbox-based IPC.
    Example:
        class MyOrchestrator(OrchestratorMailboxMixin):
            def __init__(self, session_id: str):
                self.session_id = session_id
                self._init_mailbox()
            def run(self):
                # Check mailbox between phases
                signal = self.check_mailbox()
                if signal:
                    self.handle_signal(signal)
                # Report progress
                self.report_status('implementation', 0.5, 'Implementing features')
    """
    def _init_mailbox(self, owner_id: Optional[str] = None) -> None:
        """Initialize mailbox for this orchestrator.
        Args:
            owner_id: Optional owner ID override (defaults to self.session_id)
        """
        mailbox_id = owner_id or getattr(self, 'session_id', 'default')
        self.mailbox = Mailbox(owner_id=mailbox_id)
        logger.info(f"Initialized mailbox for {mailbox_id}")
    def check_mailbox(self, msg_type: Optional[MessageType] = None) -> Optional[Message]:
        """Check for messages during execution.
        Should be called periodically (e.g., between phases) to check for control signals.
        Args:
            msg_type: Optional filter by message type (default: SIGNAL for control messages)
        Returns:
            First high-priority message if available, None otherwise
        """
        if not hasattr(self, 'mailbox'):
            logger.warning("Mailbox not initialized, skipping check")
            return None
        # Default to checking for signals (control messages)
        check_type = msg_type or MessageType.SIGNAL
        messages = self.mailbox.receive(msg_type=check_type, limit=1, delete_after_read=True)
        if messages:
            msg = messages[0]
            logger.info(f"Received {msg.type.value} message: {msg.payload}")
            return msg
        return None
    def handle_signal(self, message: Message) -> bool:
        """Handle control signal messages.
        Args:
            message: Signal message to handle
        Returns:
            True if signal was handled, False otherwise
        """
        if message.type != MessageType.SIGNAL:
            logger.warning(f"Expected SIGNAL message, got {message.type.value}")
            return False
        signal = message.payload.get('signal', '').upper()
        if signal == 'PAUSE':
            logger.info("Received PAUSE signal")
            # Implement pause logic
            if hasattr(self, '_pause'):
                self._pause()
            return True
        elif signal == 'RESUME':
            logger.info("Received RESUME signal")
            # Implement resume logic
            if hasattr(self, '_resume'):
                self._resume()
            return True
        elif signal == 'ABORT':
            logger.info("Received ABORT signal")
            # Implement abort logic
            if hasattr(self, '_abort'):
                self._abort()
            return True
        elif signal == 'CHECKPOINT':
            logger.info("Received CHECKPOINT signal")
            # Implement checkpoint logic
            if hasattr(self, '_create_checkpoint'):
                self._create_checkpoint()
            return True
        else:
            logger.warning(f"Unknown signal: {signal}")
            return False
    def report_status(
        self,
        phase: str,
        progress: float,
        summary: str,
        recipient: str = 'claude-code'
    ) -> None:
        """Send status update to Claude Code or another orchestrator.
        Args:
            phase: Current phase name (e.g., 'planning', 'implementation')
            progress: Progress as float 0.0-1.0
            summary: Brief status summary
            recipient: Recipient ID (default: 'claude-code')
        """
        if not hasattr(self, 'mailbox'):
            logger.warning("Mailbox not initialized, cannot send status")
            return
        self.mailbox.send(
            recipient=recipient,
            msg_type=MessageType.STATUS,
            payload={
                'phase': phase,
                'progress': round(progress, 2),
                'summary': summary
            },
            priority=1,
            ttl=300 # Status updates expire quickly (5 min)
        )
        logger.debug(f"Sent status update: {phase} ({progress:.0%}) - {summary}")
    def report_status_compact(
        self,
        phase: str,
        progress: float,
        state: str,
        summary: str,
        tokens: Optional[int] = None,
        cost: Optional[float] = None,
        recipient: str = 'claude-code'
    ) -> None:
        """Send compact status update using protocol (ph, pg, st, sm, tk, cs).
        This method uses the compact StatusProtocol for token-efficient messaging.
        Args:
            phase: Current phase name (will be truncated to 4 chars)
            progress: Progress as float 0.0-1.0
            state: State code ('run', 'pau', 'ok', 'err', 'wai', 'pen', 'can')
            summary: Brief status summary (will be truncated to 50 chars)
            tokens: Optional token usage count
            cost: Optional cost in USD
            recipient: Recipient ID (default: 'claude-code')
        Example:
            self.report_status_compact(
                phase="impl",
                progress=0.75,
                state="run",
                summary="Writing tests",
                tokens=1234,
                cost=0.05
            )
        """
        if not hasattr(self, 'mailbox'):
            logger.warning("Mailbox not initialized, cannot send status")
            return
        from .mailbox_protocol import StatusProtocol, StateCode
        # Convert state string to StateCode
        try:
            state_code = StateCode(state) if isinstance(state, str) else state
        except ValueError:
            logger.warning(f"Unknown state code '{state}', using RUNNING")
            state_code = StateCode.RUNNING
        status = StatusProtocol(
            ph=phase,
            pg=progress,
            st=state_code,
            sm=summary,
            tk=tokens,
            cs=cost
        )
        self.mailbox.send(
            recipient=recipient,
            msg_type=MessageType.STATUS,
            payload=status.to_payload(),
            priority=1,
            ttl=300
        )
        logger.debug(f"Sent compact status: {status}")
    def send_command(
        self,
        recipient: str,
        action: str,
        params: Optional[dict] = None,
        priority: int = 2
    ) -> str:
        """Send command to another orchestrator.
        Args:
            recipient: Target orchestrator ID
            action: Command action (e.g., 'execute', 'delegate')
            params: Optional command parameters
            priority: Message priority (default: high)
        Returns:
            Message ID
        """
        if not hasattr(self, 'mailbox'):
            logger.error("Mailbox not initialized")
            raise RuntimeError("Mailbox not initialized")
        payload = {'action': action}
        if params:
            payload['params'] = params
        msg_id = self.mailbox.send(
            recipient=recipient,
            msg_type=MessageType.COMMAND,
            payload=payload,
            priority=priority
        )
        logger.info(f"Sent command '{action}' to {recipient}: {msg_id}")
        return msg_id
    def query_orchestrator(
        self,
        recipient: str,
        query: str,
        params: Optional[dict] = None
    ) -> str:
        """Send query to another orchestrator and expect response.
        Args:
            recipient: Target orchestrator ID
            query: Query type (e.g., 'status', 'capabilities')
            params: Optional query parameters
        Returns:
            Message ID (can be used to track responses via reply_to)
        """
        if not hasattr(self, 'mailbox'):
            logger.error("Mailbox not initialized")
            raise RuntimeError("Mailbox not initialized")
        payload = {'query': query}
        if params:
            payload['params'] = params
        msg_id = self.mailbox.send(
            recipient=recipient,
            msg_type=MessageType.QUERY,
            payload=payload,
            priority=1
        )
        logger.info(f"Sent query '{query}' to {recipient}: {msg_id}")
        return msg_id
    def cleanup_mailbox(self) -> None:
        """Clean up expired messages from mailbox.
        Should be called periodically or during shutdown.
        """
        if not hasattr(self, 'mailbox'):
            return
        count = self.mailbox.cleanup_expired()
        if count > 0:
            logger.debug(f"Cleaned up {count} expired messages")
# Example StreamingOrchestrator integration
class StreamingOrchestratorExample(OrchestratorMailboxMixin):
    """Example showing mailbox integration with a streaming orchestrator."""
    def __init__(self, session_id: str):
        """Initialize orchestrator with mailbox support."""
        self.session_id = session_id
        self._init_mailbox()
        self.paused = False
    def execute_workflow(self, phases: list):
        """Execute workflow with mailbox checks between phases.
        Args:
            phases: List of workflow phases to execute
        """
        total_phases = len(phases)
        for i, phase in enumerate(phases):
            # Check for control signals before each phase
            signal = self.check_mailbox(msg_type=MessageType.SIGNAL)
            if signal:
                if self.handle_signal(signal):
                    # Signal was handled, may need to pause or abort
                    if self.paused:
                        logger.info("Workflow paused, waiting for resume signal")
                        while self.paused:
                            resume_signal = self.check_mailbox(msg_type=MessageType.SIGNAL)
                            if resume_signal and resume_signal.payload.get('signal') == 'RESUME':
                                self.paused = False
                                self.handle_signal(resume_signal)
            # Execute phase
            logger.info(f"Executing phase: {phase}")
            progress = (i + 1) / total_phases
            # Report status to Claude Code
            self.report_status(
                phase=phase,
                progress=progress,
                summary=f"Executing {phase}"
            )
            # Simulate phase execution
            # ... actual phase logic here ...
        # Final status report
        self.report_status(
            phase='completed',
            progress=1.0,
            summary='Workflow completed successfully'
        )
        # Cleanup
        self.cleanup_mailbox()
    def _pause(self):
        """Pause workflow execution."""
        self.paused = True
        logger.info("Workflow paused")
    def _resume(self):
        """Resume workflow execution."""
        self.paused = False
        logger.info("Workflow resumed")
    def _abort(self):
        """Abort workflow execution."""
        logger.info("Workflow aborted")
        raise RuntimeError("Workflow aborted by signal")
# Convenience functions for Claude Code integration
def poll_orchestrator_status(
    orchestrator_id: str,
    timeout: int = 300
) -> Optional[Message]:
    """Poll orchestrator for status updates.
    Args:
        orchestrator_id: Orchestrator session ID to monitor
        timeout: Timeout in seconds (default: 5 minutes)
    Returns:
        Latest status message or None
    """
    mailbox = Mailbox('claude-code')
    import time
    start_time = time.time()
    while (time.time() - start_time) < timeout:
        messages = mailbox.receive(msg_type=MessageType.STATUS, limit=1, delete_after_read=False)
        if messages:
            # Filter for messages from target orchestrator
            for msg in messages:
                if msg.sender == orchestrator_id:
                    return msg
        time.sleep(1) # Poll every second
    return None
def send_control_signal(
    orchestrator_id: str,
    signal: str,
    sender: str = 'claude-code'
) -> str:
    """Send control signal to orchestrator.
    Args:
        orchestrator_id: Target orchestrator session ID
        signal: Signal type ('PAUSE', 'RESUME', 'ABORT', 'CHECKPOINT')
        sender: Sender ID (default: 'claude-code')
    Returns:
        Message ID
    """
    return send_signal(
        sender=sender,
        recipient=orchestrator_id,
        signal=signal
    )
def get_orchestrator_progress(orchestrator_id: str) -> Optional[dict]:
    """Get current progress from orchestrator.
    Args:
        orchestrator_id: Orchestrator session ID
    Returns:
        Progress dict with phase, progress, summary or None
    """
    mailbox = Mailbox('claude-code')
    messages = mailbox.peek(msg_type=MessageType.STATUS, limit=10)
    # Find latest status from target orchestrator
    for msg in reversed(messages):
        if msg.sender == orchestrator_id:
            return msg.payload
    return None
