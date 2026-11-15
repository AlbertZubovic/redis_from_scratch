"""Manage client connections and synchronised socket writes."""

import socket
import threading

class ClientConnection:
    def __init__(self, client_socket: socket.socket) -> None:
        self.socket = client_socket
        self.write_lock = threading.Lock()

    def send(self, data: bytes) -> None:
        """Send data to a client socket."""
        with self.write_lock:
            self.socket.sendall(data)