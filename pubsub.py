"""Manage Redis Pub/Sub channel subscriptions."""

import logging
import threading

from connection import ClientConnection

logger = logging.getLogger(__name__)


class PubSub:
    """
    Manage Redis Pub/Sub channels and their subscribers.

    Provide operations for subscribing, unsubscribing
    and retrieving subscribers.

    Attributes:
        channels (dict[bytes, set[ClientConnection]]):
            Map channel names to sets of subscribed client connections.
    """

    def __init__(self) -> None:
        self.channels: dict[bytes, set[ClientConnection]] = {}
        self.lock: threading.Lock = threading.Lock()

    def subscribe(self, channel_name: bytes, client: ClientConnection) -> None:
        """Subscribe a client to a channel, creating it if necessary."""
        with self.lock:
            subscribers = self.channels.setdefault(channel_name, set())
            subscribers.add(client)
            logger.debug(
                "Client subscribed to channel %r (%d subscribers)",
                channel_name,
                len(subscribers),
            )

    def unsubscribe(self, channel_name: bytes, client: ClientConnection) -> None:
        """Remove a client from a channel if subscribed."""
        with self.lock:
            subscribers = self.channels.get(channel_name)

            if subscribers is None:
                return

            subscribers.discard(client)

            logger.debug(
                "Client unsubscribed from channel %r (%d subscribers remaining)",
                channel_name,
                len(subscribers),
            )

            if not subscribers:
                del self.channels[channel_name]
                logger.debug("Removed empty channel %r", channel_name)

    def get_subscribers(self, channel_name: bytes) -> set[ClientConnection]:
        """Return a copy of the channel's subscribers."""
        with self.lock:
            return self.channels.get(channel_name, set()).copy()
