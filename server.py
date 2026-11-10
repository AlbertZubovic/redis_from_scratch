import logging
import socket


def run_server() -> None:
    """Start the TCP server and handle incoming client commands."""
    with socket.socket() as server_socket:
        address = "0.0.0.0"
        port = 6379

        # Allow the server to reuse the port shortly after restarting
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        server_socket.bind((address, port))
        logging.info("Server listening on %s:%d", address, port)
        server_socket.listen(5)

        while True:
            client_socket, client_address = server_socket.accept()
            with client_socket:
                logging.info("Accepted connection from client %s:%d", client_address[0], client_address[1])
                while True:
                    try:
                        data = client_socket.recv(1024).decode()

                        if not data:
                            logging.info("Client %s:%d disconnected", client_address[0], client_address[1])
                            break

                        if data.startswith("+") and data.endswith("\r\n"):
                            if data == "+PING\r\n":
                                response = format_redis_message("PONG", "response")
                            elif data == "+EXIT\r\n":
                                logging.info("Server shutting down")
                                return
                            else:
                                response = format_redis_message("Unknown command!", "error")

                        # Reject messages that don't match the expected RESP format
                        else:
                            response = format_redis_message("ERR Protocol error", "error")
                        client_socket.sendall(response)
                    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
                        logging.warning("Client connection lost: %s", e)
                        break


# Helpers
def format_redis_message(message: str, message_type: str) -> bytes:
    """Encode a message as a RESP Simple String or Simple Error."""
    if message_type == "response":
        sign = "+"
    elif message_type == "error":
        sign = "-"
    else:
        raise ValueError("Incorrect message type parsed into message formatter")

    return f"{sign}{message}\r\n".encode()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    run_server()