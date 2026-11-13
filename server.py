import logging
import socket
import time

from typing import Final


MAX_BUFFER_SIZE: Final[int] = 1024 * 1024
MAX_BULK_STRING_SIZE: Final[int] = 1024 * 1024


def run_server() -> None:
    """
    Start the Redis-compatible TCP server.

    Accept client connections, parse RESP commands and manage a shared
    in-memory key-value database with optional key expiration.

    Close client connections when they disconnect or send malformed data.
    """

    database: dict[bytes, tuple[bytes, float | None]] = {}

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

                                case b"GET":
                                    if len(command_elements) != 2:
                                        response = format_resp_error("ERR wrong number of arguments for 'get' command")
                                    else:
                                        response = format_resp_bulk_string(handle_get(command_elements[1], database))

                                case b"SET":
                                    if len(command_elements) == 3:
                                        handle_set(command_elements[1], command_elements[2], database)
                                        response = format_resp_simple_string("OK")
                                    elif len(command_elements) == 5:
                                        if command_elements[3].upper() != "EX":
                                            response = format_resp_error("ERR Unknown command!")
                                        else:
                                            try:
                                                handle_set(command_elements[1], command_elements[2], database, command_elements[4])
                                                response = format_resp_simple_string("OK")
                                            except ValueError:
                                                response = format_resp_error("ERR value is not an integer or out of range")
                                    else:
                                        response = format_resp_error("ERR wrong number of arguments for 'set' command")

                                case b"DEL":
                                    if len(command_elements) < 2:
                                        response = format_resp_error("ERR wrong number of arguments for 'del' command")
                                    else:
                                        response = format_resp_integer(handle_del(command_elements[1:], database))

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


def format_resp_bulk_string(payload: bytes | None) -> bytes:
    """Encode a message as a RESP Bulk String or Null Bulk String."""

    return (b"$%d\r\n" % len(payload)) + payload + b"\r\n" if payload is not None else b"$-1\r\n"


def format_resp_error(message: str) -> bytes:
    """Encode a message as a RESP Simple Error."""

    return f"-{message}\r\n".encode()


def format_resp_integer(value: int) -> bytes:
    """Encode a message as a RESP Integer."""

    return f":{value}\r\n".encode()


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


def handle_get(key: bytes, database: dict[bytes, tuple[bytes, float | None]]) -> bytes | None:
    """Return a key's value, removing expired entries and returning None if absent."""

    entry = database.get(key)

    if entry is None:
        return None

    value, expiration = entry

    if is_key_expired(expiration):
        del database[key]
        logging.debug("Key expired and removed: key=%r", key)
        return None

    logging.debug("GET key=%r: value retrieved", key)

    return value


def handle_set(key: bytes, value: bytes, database: dict[bytes, tuple[bytes, float | None]], expiration: bytes | None = None) -> None:
    """
    Store a key-value pair, overwriting any existing value and expiration.

    Args:
        key: Key to store.
        value: Value associated with the key.
        database: Shared in-memory database.
        expiration: Optional expiration duration in seconds, encoded as bytes.

    Raises:
        ValueError: If the expiration argument is invalid.
    """

    if expiration is None:
        database[key] = (value, None)
    else:
        expiration_time = expiration.decode()
        if expiration_time.isdigit():
            database[key] = (value, time.monotonic() + int(expiration_time))
            logging.debug("SET key=%r: value stored", key)
        else:
            raise ValueError()


def handle_del(keys: list[bytes], database: dict[bytes, tuple[bytes, float | None]]) -> int:
    """
    Delete the specified keys and return the number of keys removed.

    Expired and nonexistent keys are not counted.
    Expired entries encountered during deletion are also removed.
    """

    deleted_count = 0

    for key in keys:

        entry = database.get(key)

        if entry is None:
            continue

        expiration = entry[1]

        if is_key_expired(expiration):
            del database[key]
            logging.debug("Key expired and removed: key=%r", key)
            continue

        del database[key]
        deleted_count += 1
        logging.debug("DEL key=%r: key deleted", key)

    return deleted_count


def is_key_expired(expiration: float | None) -> bool:
    """Return whether the expiration deadline has passed."""
    return expiration is not None and expiration <= time.monotonic()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    run_server()