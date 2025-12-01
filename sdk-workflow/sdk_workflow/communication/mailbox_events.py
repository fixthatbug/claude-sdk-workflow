"""
MailboxEventPublisher - Bridges mailbox operations to MessageBus.
Enables optional event streaming for mailbox IPC operations.
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
    from sdk_workflow.core.mailbox import Message
from .message_bus import MessageBus, EventType, get_default_bus
logger = logging.getLogger(__name__)
class MailboxEventPublisher:
    """
    Bridges mailbox operations to MessageBus for unified event streaming.
    This class provides optional integration between the file-based mailbox
    system and the in-memory MessageBus, allowing mailbox operations to be
    published as events that can be subscribed to.
    Example:
        bus = get_default_bus()
        publisher = MailboxEventPublisher(bus, auto_publish=True)
        # When mailbox sends a message:
        publisher.on_message_sent(message)
        # Subscribers to MESSAGE_SENT events will receive notification
    """
    def __init__(
        self,
        message_bus: Optional[MessageBus] = None,
        auto_publish: bool = True
    ):
        """
        Initialize the mailbox event publisher.
        Args:
            message_bus: MessageBus instance (uses default if None)
            auto_publish: Whether to automatically publish events (default: True)
        """
        self._bus = message_bus or get_default_bus()
        self._auto_publish = auto_publish
    def on_message_sent(self, message: 'Message') -> None:
        """
        Publish MESSAGE_SENT event when a message is sent.
        Args:
            message: The message that was sent
        """
        if not self._auto_publish:
            return
        try:
            self._bus.publish(
                EventType.MESSAGE_SENT,
                self._message_to_event_data(message),
                source=message.sender,
                metadata={'recipient': message.recipient, 'priority': message.priority}
            )
            logger.debug(f"Published MESSAGE_SENT event for {message.id}")
        except Exception as e:
            logger.error(f"Error publishing MESSAGE_SENT event: {e}")
    def on_message_received(self, message: 'Message', recipient: str) -> None:
        """
        Publish MESSAGE_RECEIVED event when a message is received.
        Args:
            message: The message that was received
            recipient: The recipient who received the message
        """
        if not self._auto_publish:
            return
        try:
            self._bus.publish(
                EventType.MESSAGE_RECEIVED,
                self._message_to_event_data(message),
                source=recipient,
                metadata={'sender': message.sender, 'priority': message.priority}
            )
            logger.debug(f"Published MESSAGE_RECEIVED event for {message.id}")
        except Exception as e:
            logger.error(f"Error publishing MESSAGE_RECEIVED event: {e}")
    def on_signal_received(self, message: 'Message', recipient: str) -> None:
        """
        Publish SIGNAL_RECEIVED event for high-priority control signals.
        Args:
            message: The signal message that was received
            recipient: The recipient who received the signal
        """
        if not self._auto_publish:
            return
        try:
            self._bus.publish(
                EventType.SIGNAL_RECEIVED,
                self._message_to_event_data(message),
                source=recipient,
                metadata={
                    'sender': message.sender,
                    'signal': message.payload.get('signal', 'unknown'),
                    'priority': message.priority
                }
            )
            logger.debug(f"Published SIGNAL_RECEIVED event for {message.id}")
        except Exception as e:
            logger.error(f"Error publishing SIGNAL_RECEIVED event: {e}")
    def on_broadcast_sent(self, message: 'Message') -> None:
        """
        Publish BROADCAST_SENT event when a broadcast is sent.
        Args:
            message: The broadcast message that was sent
        """
        if not self._auto_publish:
            return
        try:
            self._bus.publish(
                EventType.BROADCAST_SENT,
                self._message_to_event_data(message),
                source=message.sender,
                metadata={'priority': message.priority}
            )
            logger.debug(f"Published BROADCAST_SENT event for {message.id}")
        except Exception as e:
            logger.error(f"Error publishing BROADCAST_SENT event: {e}")
    def on_mailbox_cleared(self, owner_id: str, count: int) -> None:
        """
        Publish MAILBOX_CLEARED event when a mailbox is cleared.
        Args:
            owner_id: The owner of the cleared mailbox
            count: Number of messages that were cleared
        """
        if not self._auto_publish:
            return
        try:
            self._bus.publish(
                EventType.MAILBOX_CLEARED,
                {'owner_id': owner_id, 'messages_cleared': count},
                source=owner_id
            )
            logger.debug(f"Published MAILBOX_CLEARED event for {owner_id}")
        except Exception as e:
            logger.error(f"Error publishing MAILBOX_CLEARED event: {e}")
    def _message_to_event_data(self, message: 'Message') -> dict:
        """
        Convert a Message object to event data for MessageBus.
        Args:
            message: The message to convert
        Returns:
            Dictionary containing essential message data
        """
        return {
            'message_id': message.id,
            'sender': message.sender,
            'recipient': message.recipient,
            'type': message.type.value,
            'payload': message.payload,
            'timestamp': message.timestamp,
            'priority': message.priority,
            'ttl': message.ttl_seconds
        }
    def enable(self) -> None:
        """Enable automatic event publishing."""
        self._auto_publish = True
        logger.debug("MailboxEventPublisher enabled")
    def disable(self) -> None:
        """Disable automatic event publishing."""
        self._auto_publish = False
        logger.debug("MailboxEventPublisher disabled")
    def is_enabled(self) -> bool:
        """Check if auto-publishing is enabled."""
        return self._auto_publish
