import socket
import threading
import time
from collections.abc import Iterator

import pytest

from server import run_server


@pytest.fixture
def test_server() -> Iterator[tuple[str, int]]:
    host = "127.0.0.1"
    port = 6379
    shutdown_event = threading.Event()

    server_thread = threading.Thread(
        target=run_server,
        args=(port, shutdown_event),
        daemon=True,
    )

    server_thread.start()

    try:
        wait_for_server(host, port)

        yield host, port
    finally:
        shutdown_event.set()
        server_thread.join(timeout=2)


def wait_for_server(host: str, port: int) -> None:
    for _ in range(50):
        try:
            with socket.create_connection((host, port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.01)

    raise RuntimeError("Server failed to start")
