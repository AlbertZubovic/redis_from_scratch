import socket
import threading
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, call

import pytest

from server import handle_client


# SUBSCRIBE tests
def test_subscribe(run_command: Callable[[bytes], MagicMock]) -> None:
    sendall = run_command(b"*2\r\n$9\r\nSUBSCRIBE\r\n$4\r\nnews\r\n")

    sendall.assert_called_once_with(b"*3\r\n$9\r\nsubscribe\r\n$4\r\nnews\r\n:1\r\n")


def test_subscribe_multiple(run_command: Callable[[bytes], MagicMock]) -> None:
    sendall = run_command(b"*3\r\n$9\r\nSUBSCRIBE\r\n$4\r\nnews\r\n$6\r\nsports\r\n")

    sendall.assert_called_once_with(b"*3\r\n$9\r\nsubscribe\r\n$4\r\nnews\r\n:1\r\n"b"*3\r\n$9\r\nsubscribe\r\n$6\r\nsports\r\n:2\r\n")


def test_subscribe_no_arguments(run_command: Callable[[bytes], MagicMock]) -> None:
    sendall = run_command(b"*1\r\n$9\r\nSUBSCRIBE\r\n")

    sendall.assert_called_once_with(b"-ERR wrong number of arguments for 'subscribe' command\r\n")


# UNSUBSCRIBE tests
def test_unsubscribe(server_state: dict[str, Any], mock_client: dict[str, Any]) -> None:
    mock_socket = mock_client["client_socket"]

    mock_socket.recv.side_effect = [
        b"*2\r\n$9\r\nSUBSCRIBE\r\n$4\r\nnews\r\n",
        b"*2\r\n$11\r\nUNSUBSCRIBE\r\n$4\r\nnews\r\n",
        b"",
    ]

    handle_client(**mock_client, **server_state)

    assert mock_socket.sendall.call_args_list == [
        call(b"*3\r\n$9\r\nsubscribe\r\n$4\r\nnews\r\n:1\r\n"),
        call(b"*3\r\n$11\r\nunsubscribe\r\n$4\r\nnews\r\n:0\r\n"),
    ]


def test_unsubscribe_all(server_state: dict[str, Any], mock_client: dict[str, Any]) -> None:
    mock_socket = mock_client["client_socket"]

    mock_socket.recv.side_effect = [
        b"*3\r\n$9\r\nSUBSCRIBE\r\n$4\r\nnews\r\n$6\r\nsports\r\n",
        b"*1\r\n$11\r\nUNSUBSCRIBE\r\n",
        b"",
    ]

    handle_client(**mock_client, **server_state)

    subscribe_response = (
        b"*3\r\n$9\r\nsubscribe\r\n$4\r\nnews\r\n:1\r\n"
        b"*3\r\n$9\r\nsubscribe\r\n$6\r\nsports\r\n:2\r\n"
    )

    unsubscribe_response = mock_socket.sendall.call_args_list[1].args[0]

    assert mock_socket.sendall.call_count == 2
    assert mock_socket.sendall.call_args_list[0] == call(subscribe_response)

    expected_responses = {
        (
            b"*3\r\n$11\r\nunsubscribe\r\n$4\r\nnews\r\n:1\r\n"
            b"*3\r\n$11\r\nunsubscribe\r\n$6\r\nsports\r\n:0\r\n"
        ),
        (
            b"*3\r\n$11\r\nunsubscribe\r\n$6\r\nsports\r\n:1\r\n"
            b"*3\r\n$11\r\nunsubscribe\r\n$4\r\nnews\r\n:0\r\n"
        ),
    }

    assert unsubscribe_response in expected_responses


def test_unsubscribe_not_subscribed(run_command: Callable[[bytes], MagicMock]) -> None:
    sendall = run_command(b"*1\r\n$11\r\nUNSUBSCRIBE\r\n")

    sendall.assert_called_once_with(b"*3\r\n$11\r\nunsubscribe\r\n$-1\r\n:0\r\n")


# PUBLISH tests
def test_publish_no_subscribers(run_command: Callable[[bytes], MagicMock]) -> None:
    sendall = run_command(b"*3\r\n$7\r\nPUBLISH\r\n$4\r\nnews\r\n$5\r\nhello\r\n")

    sendall.assert_called_once_with(b":0\r\n")


def test_publish_to_subscriber(server_state: dict[str, Any]) -> None:
    subscriber_socket = MagicMock(spec=socket.socket)
    publisher_socket = MagicMock(spec=socket.socket)

    subscribed = threading.Event()
    disconnect = threading.Event()

    def subscriber_recv(_: int) -> bytes:
        if not subscribed.is_set():
            return b"*2\r\n$9\r\nSUBSCRIBE\r\n$4\r\nnews\r\n"

        disconnect.wait(timeout=5)
        return b""

    subscriber_socket.recv.side_effect = subscriber_recv

    def subscriber_sendall(data: bytes) -> None:
        if data == b"*3\r\n$9\r\nsubscribe\r\n$4\r\nnews\r\n:1\r\n":
            subscribed.set()

    subscriber_socket.sendall.side_effect = subscriber_sendall

    subscriber_thread = threading.Thread(target=handle_client, args=(subscriber_socket, ("127.0.0.1", 12345)), kwargs=server_state)

    subscriber_thread.start()

    try:
        assert subscribed.wait(timeout=5), "Subscriber did not subscribe"

        publisher_socket.recv.side_effect = [
            b"*3\r\n$7\r\nPUBLISH\r\n$4\r\nnews\r\n$5\r\nhello\r\n",
            b"",
        ]

        handle_client(client_socket=publisher_socket, client_address=("127.0.0.1", 12346), **server_state)

        publisher_socket.sendall.assert_called_once_with(b":1\r\n")

        subscriber_socket.sendall.assert_any_call(
            b"*3\r\n$7\r\nmessage\r\n$4\r\nnews\r\n$5\r\nhello\r\n"
        )

    finally:
        disconnect.set()
        subscriber_thread.join(timeout=5)

    assert not subscriber_thread.is_alive()


@pytest.mark.parametrize(
    "command, expected",
    [
        (
            b"*1\r\n$7\r\nPUBLISH\r\n",
            b"-ERR wrong number of arguments for 'publish' command\r\n",
        ),
        (
            b"*2\r\n$7\r\nPUBLISH\r\n$4\r\nnews\r\n",
            b"-ERR wrong number of arguments for 'publish' command\r\n",
        ),
        (
            b"*4\r\n$7\r\nPUBLISH\r\n$4\r\nnews\r\n$5\r\nhello\r\n$5\r\nextra\r\n",
            b"-ERR wrong number of arguments for 'publish' command\r\n",
        ),
    ],
    ids=["no-arguments", "missing-message", "too-many-arguments"],
)
def test_publish_invalid(run_command: Callable[[bytes], MagicMock], command: bytes, expected: bytes) -> None:
    sendall = run_command(command)

    sendall.assert_called_once_with(expected)


# Subscribed-mode tests
def test_ping_subscribed(server_state: dict[str, Any], mock_client: dict[str, Any]) -> None:
    mock_socket = mock_client["client_socket"]

    mock_socket.recv.side_effect = [
        b"*2\r\n$9\r\nSUBSCRIBE\r\n$4\r\nnews\r\n",
        b"*2\r\n$4\r\nPING\r\n$5\r\nhello\r\n",
        b"",
    ]

    handle_client(**mock_client, **server_state)

    assert mock_socket.sendall.call_args_list == [
        call(b"*3\r\n$9\r\nsubscribe\r\n$4\r\nnews\r\n:1\r\n"),
        call(b"*2\r\n$4\r\npong\r\n$5\r\nhello\r\n"),
    ]



