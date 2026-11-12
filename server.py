import logging
import socket

from typing import Final


MAX_BUFFER_SIZE: Final[int] = 1024 * 1024
MAX_BULK_STRING_SIZE: Final[int] = 1024 * 1024


def run_server() -> None:
    """
    Start the Redis-compatible TCP server.

    Accept client connections, buffer incoming data and process
    RESP commands until the client disconnects or sends malformed data.
    """
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
                buffer = b""

                close_connection = False

                # Process all complete commands before receiving more data.
                while True:
                    try:
                        received_data = client_socket.recv(1024)

                        if not received_data:
                            logging.info("Client %s:%d disconnected", client_address[0], client_address[1])
                            break

                        buffer += received_data

                        if len(buffer) > MAX_BUFFER_SIZE:
                            client_socket.sendall(b"-Parsing error!\r\n")
                            break

                        while True:

                            try:
                                result = parse_resp_command(buffer)
                            except ValueError:
                                client_socket.sendall(b"-Parsing error!\r\n")
                                close_connection = True
                                break

                            if result is None:
                                break

                            command_elements, byte_count = result
                            buffer = buffer[byte_count:]
                            command = command_elements[0].upper()

                            match command:

                                case b"PING":
                                    if len(command_elements) > 2:
                                        response = format_resp_error("ERR wrong number of arguments for 'ping' command")
                                    elif len(command_elements) == 1:
                                        response = format_resp_simple_string("PONG")
                                    else:
                                        response = format_resp_bulk_string(command_elements[1])

                                case b"EXIT":
                                    logging.info("Server shutting down")
                                    return

                                case b"ECHO":
                                    if len(command_elements) != 2:
                                        response = format_resp_error("ERR wrong number of arguments for 'echo' command")
                                    else:
                                        response = format_resp_bulk_string(command_elements[1])

                                case _:
                                    response = format_resp_error("ERR Unknown command!")

                            client_socket.sendall(response)

                        if close_connection:
                            break

                    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
                        logging.warning("Client connection lost: %s", e)
                        break


# Helpers
def format_resp_simple_string(message: str) -> bytes:
    """Encode a message as a RESP Simple String."""
    return f"+{message}\r\n".encode()


def format_resp_bulk_string(payload: bytes) -> bytes:
    """Encode a message as a RESP Bulk String."""
    return (b"$%d\r\n" % len(payload)) + payload + b"\r\n"


def format_resp_error(message: str) -> bytes:
    """Encode a message as a RESP Simple Error."""
    return f"-{message}\r\n".encode()


def parse_resp_command(buffer: bytes) -> tuple[list[bytes], int] | None:
    """
    Parse one RESP array command from a byte buffer.

    Args:
        buffer: Bytes containing complete or partial RESP request.

    Returns:
        A tuple containing the parsed elements and the number of bytes
        consumed, or None if the first request is incomplete.

    Raises:
        ValueError: If the RESP request is malformed or exceeds size limits.
    """

    elements = []

    if not buffer:
        return None

    if buffer.startswith(b"*"):
        header_end = buffer.find(b"\r\n")

        if header_end == -1:
            return None

        array_length_bytes = buffer[1:header_end]

        if not array_length_bytes.isdigit():
            raise ValueError("Invalid RESP format")

        element_count = int(array_length_bytes)

        if element_count < 1:
            raise ValueError("Invalid RESP format")

        position = header_end + 2
        for _ in range(element_count):
            if position >= len(buffer):
                return None

            if buffer[position:position + 1] != b"$":
                raise ValueError("Invalid RESP format")

            length_header_end = buffer.find(b"\r\n", position)

            if length_header_end == -1:
                return None

            payload_length_bytes = buffer[position + 1:length_header_end]

            if not payload_length_bytes.isdigit():
                raise ValueError("Invalid RESP format")

            payload_length = int(payload_length_bytes)

            if payload_length > MAX_BULK_STRING_SIZE:
                raise ValueError("Bulk string exceeds maximum size of 1MiB")

            position = length_header_end + 2

            # Bulk strings are length-prefixed, so CRLF may appear inside the payload.
            payload_end = position + payload_length

            if len(buffer) < payload_end + 2:
                return None

            if buffer[payload_end:payload_end + 2] != b"\r\n":
                raise ValueError("Invalid RESP format")

            elements.append(buffer[position:payload_end])

            position = payload_end + 2

        # Return the consumed byte count so the caller can retain subsequent requests.
        return elements, position

    raise ValueError("Invalid RESP format")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    run_server()