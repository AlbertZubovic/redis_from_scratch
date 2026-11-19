import socket
import time
from concurrent.futures import ThreadPoolExecutor


def test_ping(test_server: tuple[str, int]) -> None:
    host, port = test_server

    with socket.create_connection((host, port), timeout=2) as client:
        client.sendall(b"*1\r\n$4\r\nPING\r\n")

        assert client.recv(1024) == b"+PONG\r\n"


def test_set_get_del(test_server: tuple[str, int]) -> None:
    host, port = test_server

    with socket.create_connection((host, port), timeout=2) as client:
        client.sendall(b"*3\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n")
        assert client.recv(1024) == b"+OK\r\n"

        client.sendall(b"*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n")
        assert client.recv(1024) == b"$3\r\nbar\r\n"

        client.sendall(b"*2\r\n$3\r\nDEL\r\n$3\r\nfoo\r\n")
        assert client.recv(1024) == b":1\r\n"


def test_multiple_commands(test_server: tuple[str, int]) -> None:
    host, port = test_server

    with socket.create_connection((host, port), timeout=2) as client:
        client.sendall(b"*1\r\n$4\r\nPING\r\n*1\r\n$4\r\nPING\r\n")

        response = b""
        while len(response) < len(b"+PONG\r\n+PONG\r\n"):
            response += client.recv(1024)

        assert response == b"+PONG\r\n+PONG\r\n"


def test_partial_command(test_server: tuple[str, int]) -> None:
    host, port = test_server

    with socket.create_connection((host, port), timeout=2) as client:
        client.sendall(b"*1\r\n$4\r\n")
        time.sleep(0.05)
        client.sendall(b"PING\r\n")

        assert client.recv(1024) == b"+PONG\r\n"


def test_connection_after_error(test_server: tuple[str, int]) -> None:
    host, port = test_server

    with socket.create_connection((host, port), timeout=2) as client:
        client.sendall(b"*1\r\n$4\r\nINCR\r\n")

        assert client.recv(1024) == (
            b"-ERR wrong number of arguments for 'incr' command\r\n"
        )

        client.sendall(b"*1\r\n$4\r\nPING\r\n")
        assert client.recv(1024) == b"+PONG\r\n"


def test_invalid_command(test_server: tuple[str, int]) -> None:
    host, port = test_server

    with socket.create_connection((host, port), timeout=2) as client:
        client.sendall(b"*1\r\n$7\r\nUNKNOWN\r\n")

        assert client.recv(1024).startswith(b"-ERR")

        client.sendall(b"*1\r\n$4\r\nPING\r\n")

        assert client.recv(1024) == b"+PONG\r\n"


import pytest


@pytest.mark.parametrize(
    "command, expected",
    [
        (
            b"*1\r\n$3\r\nGET\r\n",
            b"-ERR wrong number of arguments for 'get' command\r\n",
        ),
        (
            b"*1\r\n$3\r\nSET\r\n",
            b"-ERR wrong number of arguments for 'set' command\r\n",
        ),
        (
            b"*1\r\n$4\r\nINCR\r\n",
            b"-ERR wrong number of arguments for 'incr' command\r\n",
        ),
        (
            b"*1\r\n$6\r\nRENAME\r\n",
            b"-ERR wrong number of arguments for 'rename' command\r\n",
        ),
    ],
)
def test_invalid_arguments(
    test_server: tuple[str, int], command: bytes, expected: bytes
) -> None:
    host, port = test_server

    with socket.create_connection((host, port), timeout=2) as client:
        client.sendall(command)

        assert client.recv(1024) == expected


def test_multiple_clients(test_server: tuple[str, int]) -> None:
    host, port = test_server

    with (
        socket.create_connection((host, port), timeout=2) as client1,
        socket.create_connection((host, port), timeout=2) as client2,
    ):
        client1.sendall(b"*3\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n")
        assert client1.recv(1024) == b"+OK\r\n"

        client2.sendall(b"*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n")
        assert client2.recv(1024) == b"$3\r\nbar\r\n"


def test_pubsub(test_server: tuple[str, int]) -> None:
    host, port = test_server

    with (
        socket.create_connection((host, port), timeout=2) as client1,
        socket.create_connection((host, port), timeout=2) as client2,
    ):
        client1.sendall(b"*2\r\n$9\r\nSUBSCRIBE\r\n$7\r\nchannel\r\n")
        assert client1.recv(1024) == b"*3\r\n$9\r\nsubscribe\r\n$7\r\nchannel\r\n:1\r\n"

        client2.sendall(b"*3\r\n$7\r\nPUBLISH\r\n$7\r\nchannel\r\n$5\r\nhello\r\n")
        assert client2.recv(1024) == b":1\r\n"

        assert (
            client1.recv(1024)
            == b"*3\r\n$7\r\nmessage\r\n$7\r\nchannel\r\n$5\r\nhello\r\n"
        )


def test_expiration(test_server: tuple[str, int]) -> None:
    host, port = test_server

    with socket.create_connection((host, port), timeout=2) as client:
        client.sendall(
            b"*5\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n$2\r\nEX\r\n$1\r\n1\r\n"
        )
        assert client.recv(1024) == b"+OK\r\n"

        client.sendall(b"*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n")
        assert client.recv(1024) == b"$3\r\nbar\r\n"

        time.sleep(1.1)

        client.sendall(b"*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n")
        assert client.recv(1024) == b"$-1\r\n"


def test_concurrent_increments(test_server: tuple[str, int]) -> None:
    host, port = test_server

    def increment_counter() -> None:
        with (
            socket.create_connection((host, port), timeout=2) as client,
            client.makefile("rb") as reader,
        ):
            for _ in range(100):
                client.sendall(b"*2\r\n$4\r\nINCR\r\n$7\r\ncounter\r\n")
                assert reader.readline().startswith(b":")

    with socket.create_connection((host, port), timeout=2) as client:
        client.sendall(b"*3\r\n$3\r\nSET\r\n$7\r\ncounter\r\n$1\r\n0\r\n")
        assert client.recv(1024) == b"+OK\r\n"

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(increment_counter) for _ in range(5)]

        for future in futures:
            future.result()

    with socket.create_connection((host, port), timeout=2) as client:
        client.sendall(b"*2\r\n$3\r\nGET\r\n$7\r\ncounter\r\n")
        assert client.recv(1024) == b"$3\r\n500\r\n"
