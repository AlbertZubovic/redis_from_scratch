import socket
import threading
from unittest.mock import MagicMock

import pytest

from connection import ClientConnection


@pytest.fixture
def mock_client_connection() -> tuple[MagicMock, ClientConnection]:
    mock_socket = MagicMock(spec=socket.socket)
    connection = ClientConnection(mock_socket)

    return mock_socket, connection


def test_send(mock_client_connection: tuple[MagicMock, ClientConnection]) -> None:
    mock_socket, connection = mock_client_connection

    connection.send(b"hello")

    mock_socket.sendall.assert_called_once_with(b"hello")


def test_send_concurrent(
    mock_client_connection: tuple[MagicMock, ClientConnection],
) -> None:
    mock_socket, connection = mock_client_connection

    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def fake_sendall(data: bytes) -> None:
        if data == b"Hello":
            first_entered.set()
            release_first.wait(timeout=2)

        elif data == b"World":
            second_entered.set()

    mock_socket.sendall.side_effect = fake_sendall

    thread_a = threading.Thread(target=connection.send, args=(b"Hello",))
    thread_b = threading.Thread(target=connection.send, args=(b"World",))

    try:
        thread_a.start()
        assert first_entered.wait(timeout=2)

        thread_b.start()

        assert not second_entered.wait(timeout=0.1)

    finally:
        release_first.set()

        thread_a.join(timeout=2)

        if thread_b.ident is not None:
            thread_b.join(timeout=2)

    assert not thread_a.is_alive()
    assert not thread_b.is_alive()

    assert second_entered.is_set()
    assert mock_socket.sendall.call_count == 2


def test_send_uses_lock(
    mock_client_connection: tuple[MagicMock, ClientConnection],
) -> None:
    mock_socket, connection = mock_client_connection

    mock_lock = MagicMock()
    connection.write_lock = mock_lock

    def check_lock(_data) -> None:
        mock_lock.__enter__.assert_called_once()
        mock_lock.__exit__.assert_not_called()

    mock_socket.sendall.side_effect = check_lock

    connection.send(b"Hello")

    mock_lock.__exit__.assert_called_once()
    mock_socket.sendall.assert_called_once_with(b"Hello")
