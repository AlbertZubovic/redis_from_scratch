from collections.abc import Callable
from unittest.mock import MagicMock

import pytest


@pytest.mark.parametrize(
    "command, expected",
    [
        (
            b"*1\r\n$4\r\nPING\r\n",
            b"+PONG\r\n",
        ),
        (
            b"*2\r\n$4\r\nPING\r\n$5\r\nhello\r\n",
            b"$5\r\nhello\r\n",
        ),
        (
            b"*3\r\n$4\r\nPING\r\n$5\r\nhello\r\n$5\r\nworld\r\n",
            b"-ERR wrong number of arguments for 'ping' command\r\n",
        ),
    ],
    ids=["ping", "ping-with-message", "too-many-arguments"],
)
def test_ping(run_command: Callable[[bytes], MagicMock], command: bytes, expected: bytes) -> None:
    sendall = run_command(command)

    sendall.assert_called_once_with(expected)


@pytest.mark.parametrize(
    "command, expected",
    [
        (
            b"*2\r\n$4\r\nECHO\r\n$5\r\nhello\r\n",
            b"$5\r\nhello\r\n",
        ),
        (
            b"*1\r\n$4\r\nECHO\r\n",
            b"-ERR wrong number of arguments for 'echo' command\r\n",
        ),
        (
            b"*3\r\n$4\r\nECHO\r\n$5\r\nhello\r\n$5\r\nworld\r\n",
            b"-ERR wrong number of arguments for 'echo' command\r\n",
        ),
    ],
    ids=["valid", "no-arguments", "too-many-arguments"],
)
def test_echo(run_command: Callable[[bytes], MagicMock], command: bytes, expected: bytes) -> None:
    sendall = run_command(command)

    sendall.assert_called_once_with(expected)


def test_unknown_command(run_command: Callable[[bytes], MagicMock]) -> None:
    sendall = run_command(b"*1\r\n$7\r\nINVALID\r\n")

    sendall.assert_called_once_with(b"-ERR Unknown command!\r\n")
