import socket
import time


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
        client.sendall(
            b"*1\r\n$4\r\nPING\r\n"
            b"*1\r\n$4\r\nPING\r\n"
        )

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

        assert client1.recv(1024) == b"*3\r\n$7\r\nmessage\r\n$7\r\nchannel\r\n$5\r\nhello\r\n"


def test_expiration(test_server: tuple[str, int]) -> None:
    host, port = test_server

    with socket.create_connection((host, port), timeout=2) as client:
        client.sendall(b"*5\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n$2\r\nEX\r\n$1\r\n1\r\n")
        assert client.recv(1024) == b"+OK\r\n"

        client.sendall(b"*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n")
        assert client.recv(1024) == b"$3\r\nbar\r\n"

        time.sleep(1.1)

        client.sendall(b"*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n")
        assert client.recv(1024) == b"$-1\r\n"
