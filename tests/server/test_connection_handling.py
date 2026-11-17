from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, call

import pytest

from server import MAX_BUFFER_SIZE, handle_client


def test_client_disconnect(server_state: dict[str, Any], mock_client: dict[str, Any]) -> None:
    mock_socket = mock_client["client_socket"]
    mock_socket.recv.return_value = b""

    handle_client(**mock_client, **server_state)

    mock_socket.sendall.assert_not_called()


def test_multiple_commands(run_command: Callable[[bytes], MagicMock]) -> None:
    command = (
        b"*1\r\n$4\r\nPING\r\n"
        b"*2\r\n$4\r\nECHO\r\n$5\r\nhello\r\n"
    )

    sendall = run_command(command)

    assert sendall.call_args_list == [
        call(b"+PONG\r\n"),
        call(b"$5\r\nhello\r\n"),
    ]


def test_partial_command(server_state: dict[str, Any], mock_client: dict[str, Any]) -> None:
    mock_socket = mock_client["client_socket"]

    mock_socket.recv.side_effect = [
        b"*2\r\n$4\r\nECHO\r\n$5\r\n",
        b"hello\r\n",
        b"",
    ]

    handle_client(**mock_client, **server_state)

    mock_socket.sendall.assert_called_once_with(b"$5\r\nhello\r\n")


def test_invalid_resp(run_command: Callable[[bytes], MagicMock],) -> None:
    sendall = run_command(b"invalid\r\n")

    sendall.assert_called_once_with(b"-Parsing error!\r\n")


def test_buffer_too_large(run_command: Callable[[bytes], MagicMock]) -> None:
    sendall = run_command(b"x" * (MAX_BUFFER_SIZE + 1))

    sendall.assert_called_once_with(b"-Parsing error!\r\n")


def test_exit(server_state: dict[str, Any], mock_client: dict[str, Any]) -> None:
    mock_socket = mock_client["client_socket"]

    mock_socket.recv.side_effect = [
        b"*1\r\n$4\r\nEXIT\r\n",
    ]

    handle_client(**mock_client, **server_state)

    assert server_state["shutdown_event"].is_set()
    mock_socket.sendall.assert_not_called()


@pytest.mark.parametrize(
    "exception",
    [
        ConnectionResetError,
        ConnectionAbortedError,
        BrokenPipeError,
    ],
    ids=[
        "connection-reset",
        "connection-aborted",
        "broken-pipe",
    ],
)
def test_connection_lost(server_state: dict[str, Any], mock_client: dict[str, Any], exception: type[OSError]) -> None:
    mock_socket = mock_client["client_socket"]
    mock_socket.recv.side_effect = exception

    handle_client(**mock_client, **server_state)

    mock_socket.sendall.assert_not_called()


def test_subscriber_disconnect_cleanup(server_state: dict[str, Any], mock_client: dict[str, Any]) -> None:
    mock_socket = mock_client["client_socket"]

    mock_socket.recv.side_effect = [
        b"*2\r\n$9\r\nSUBSCRIBE\r\n$4\r\nnews\r\n",
        b"",
    ]

    handle_client(**mock_client, **server_state)

    mock_socket.sendall.assert_called_once_with(
        b"*3\r\n$9\r\nsubscribe\r\n$4\r\nnews\r\n:1\r\n"
    )

    assert server_state["pubsub_manager"].get_subscribers(b"news") == set()
