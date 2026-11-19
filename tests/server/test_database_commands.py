from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest


# GET tests
def test_get(
    run_command: Callable[[bytes], MagicMock], server_state: dict[str, Any]
) -> None:
    server_state["database_store"][b"name"] = (b"Alice", None)

    sendall = run_command(b"*2\r\n$3\r\nGET\r\n$4\r\nname\r\n")
    sendall.assert_called_once_with(b"$5\r\nAlice\r\n")


@pytest.mark.parametrize(
    "command, expected",
    [
        (
            b"*2\r\n$3\r\nGET\r\n$7\r\nmissing\r\n",
            b"$-1\r\n",
        ),
        (
            b"*1\r\n$3\r\nGET\r\n",
            b"-ERR wrong number of arguments for 'get' command\r\n",
        ),
    ],
    ids=["missing-key", "no-arguments"],
)
def test_get_invalid_or_missing(
    run_command: Callable[[bytes], MagicMock], command: bytes, expected: bytes
) -> None:
    sendall = run_command(command)
    sendall.assert_called_once_with(expected)


def test_set(
    run_command: Callable[[bytes], MagicMock], server_state: dict[str, Any]
) -> None:
    sendall = run_command(b"*3\r\n$3\r\nSET\r\n$4\r\nname\r\n$5\r\nAlice\r\n")
    sendall.assert_called_once_with(b"+OK\r\n")

    assert server_state["database_store"][b"name"][0] == b"Alice"


# SET tests
def test_set_with_expiration(
    run_command: Callable[[bytes], MagicMock], server_state: dict[str, Any]
) -> None:
    sendall = run_command(
        b"*5\r\n$3\r\nSET\r\n$4\r\nname\r\n$5\r\nAlice\r\n$2\r\nEX\r\n$2\r\n10\r\n"
    )
    sendall.assert_called_once_with(b"+OK\r\n")

    value, expiration = server_state["database_store"][b"name"]

    assert value == b"Alice"
    assert expiration is not None


@pytest.mark.parametrize(
    "command, expected",
    [
        (
            b"*1\r\n$3\r\nSET\r\n",
            b"-ERR wrong number of arguments for 'set' command\r\n",
        ),
        (
            b"*2\r\n$3\r\nSET\r\n$4\r\nname\r\n",
            b"-ERR wrong number of arguments for 'set' command\r\n",
        ),
        (
            b"*5\r\n$3\r\nSET\r\n$4\r\nname\r\n$5\r\nAlice\r\n$2\r\nEX\r\n$3\r\nabc\r\n",
            b"-ERR value is not an integer or out of range\r\n",
        ),
        (
            b"*5\r\n$3\r\nSET\r\n$4\r\nname\r\n$5\r\nAlice\r\n$2\r\nNX\r\n$2\r\n10\r\n",
            b"-ERR Unknown command!\r\n",
        ),
    ],
    ids=["no-arguments", "missing-value", "invalid-expiration", "unsupported-option"],
)
def test_set_invalid(
    run_command: Callable[[bytes], MagicMock], command: bytes, expected: bytes
) -> None:
    sendall = run_command(command)
    sendall.assert_called_once_with(expected)


# DEL tests
def test_del_existing(
    run_command: Callable[[bytes], MagicMock], server_state: dict[str, Any]
) -> None:
    server_state["database_store"][b"name"] = (b"Alice", None)

    sendall = run_command(b"*2\r\n$3\r\nDEL\r\n$4\r\nname\r\n")
    sendall.assert_called_once_with(b":1\r\n")

    assert b"name" not in server_state["database_store"]


def test_del_nonexistent(run_command: Callable[[bytes], MagicMock]) -> None:
    sendall = run_command(b"*2\r\n$3\r\nDEL\r\n$7\r\nmissing\r\n")
    sendall.assert_called_once_with(b":0\r\n")


def test_del_multiple(
    run_command: Callable[[bytes], MagicMock], server_state: dict[str, Any]
) -> None:
    database = server_state["database_store"]

    database[b"name"] = (b"Alice", None)
    database[b"age"] = (b"25", None)

    sendall = run_command(
        b"*4\r\n$3\r\nDEL\r\n$4\r\nname\r\n$3\r\nage\r\n$7\r\nmissing\r\n"
    )
    sendall.assert_called_once_with(b":2\r\n")

    assert database == {}


def test_del_no_arguments(run_command: Callable[[bytes], MagicMock]) -> None:
    sendall = run_command(b"*1\r\n$3\r\nDEL\r\n")

    sendall.assert_called_once_with(
        b"-ERR wrong number of arguments for 'del' command\r\n"
    )
