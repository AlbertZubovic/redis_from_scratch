import socket
import threading
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest

from pubsub import PubSub
from server import handle_client


@pytest.fixture
def server_state() -> dict[str, Any]:
    return {
        "database_store": {},
        "shutdown_event": threading.Event(),
        "database_lock": threading.Lock(),
        "pubsub_manager": PubSub(),
    }


@pytest.fixture
def mock_client() -> dict[str, Any]:
    return {
        "client_socket": MagicMock(spec=socket.socket),
        "client_address": ("127.0.0.1", 12345),
    }


@pytest.fixture
def run_command(server_state: dict[str, Any], mock_client: dict[str, Any]) -> Callable[[bytes], MagicMock]:
    def _run(command: bytes) -> MagicMock:
        mock_socket = mock_client["client_socket"]

        mock_socket.recv.side_effect = [command, b""]

        handle_client(**mock_client, **server_state)

        return mock_socket.sendall

    return _run