import socket
from unittest.mock import MagicMock

import pytest

from connection import ClientConnection
from pubsub import PubSub


@pytest.fixture
def pubsub() -> PubSub:
    return PubSub()


@pytest.fixture
def clients() -> tuple[ClientConnection, ClientConnection]:
    return (
        ClientConnection(MagicMock(spec=socket.socket)),
        ClientConnection(MagicMock(spec=socket.socket)),
    )


# SUBSCRIBE tests
def test_subscribe(
    pubsub: PubSub, clients: tuple[ClientConnection, ClientConnection]
) -> None:
    client_a, client_b = clients

    pubsub.subscribe(b"news", client_a)
    pubsub.subscribe(b"news", client_b)

    assert pubsub.get_subscribers(b"news") == {client_a, client_b}


def test_subscribe_duplicate(
    pubsub: PubSub, clients: tuple[ClientConnection, ClientConnection]
) -> None:
    client_a, _ = clients

    pubsub.subscribe(b"news", client_a)
    pubsub.subscribe(b"news", client_a)

    assert pubsub.get_subscribers(b"news") == {client_a}


def test_subscribe_multiple_channels(
    pubsub: PubSub, clients: tuple[ClientConnection, ClientConnection]
) -> None:
    client_a, _ = clients

    pubsub.subscribe(b"news", client_a)
    pubsub.subscribe(b"notification", client_a)

    assert pubsub.get_subscribers(b"news") == {client_a}
    assert pubsub.get_subscribers(b"notification") == {client_a}


def test_subscribe_channels_isolation(
    pubsub: PubSub, clients: tuple[ClientConnection, ClientConnection]
) -> None:
    client_a, client_b = clients

    pubsub.subscribe(b"news", client_a)
    pubsub.subscribe(b"notification", client_b)

    assert pubsub.get_subscribers(b"news") == {client_a}
    assert pubsub.get_subscribers(b"notification") == {client_b}


def test_unsubscribe(
    pubsub: PubSub, clients: tuple[ClientConnection, ClientConnection]
) -> None:
    client_a, client_b = clients

    pubsub.subscribe(b"news", client_a)
    pubsub.subscribe(b"news", client_b)

    pubsub.unsubscribe(b"news", client_a)

    assert pubsub.get_subscribers(b"news") == {client_b}


# UNSUBSCRIBE tests
def test_unsubscribe_last_client(
    pubsub: PubSub, clients: tuple[ClientConnection, ClientConnection]
) -> None:
    client_a, _ = clients

    pubsub.subscribe(b"news", client_a)
    pubsub.unsubscribe(b"news", client_a)

    assert pubsub.channels == {}


def test_unsubscribe_nonexistent(
    pubsub: PubSub, clients: tuple[ClientConnection, ClientConnection]
) -> None:
    client_a, _ = clients

    pubsub.unsubscribe(b"news", client_a)

    assert pubsub.channels == {}


def test_unsubscribe_client_not_subscribed(
    pubsub: PubSub, clients: tuple[ClientConnection, ClientConnection]
) -> None:
    client_a, client_b = clients

    pubsub.subscribe(b"news", client_a)

    pubsub.unsubscribe(b"news", client_b)

    assert pubsub.get_subscribers(b"news") == {client_a}


# GET SUBSCRIBERS tests
def test_get_subscribers_nonexistent(pubsub: PubSub) -> None:
    assert pubsub.get_subscribers(b"unknown") == set()


def test_get_subscribers_copy(
    pubsub: PubSub, clients: tuple[ClientConnection, ClientConnection]
) -> None:
    client_a, _ = clients

    pubsub.subscribe(b"news", client_a)

    subscribers = pubsub.get_subscribers(b"news")
    subscribers.clear()

    assert pubsub.get_subscribers(b"news") == {client_a}
