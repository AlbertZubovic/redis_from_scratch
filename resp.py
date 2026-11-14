from typing import Final

MAX_BULK_STRING_SIZE: Final[int] = 1024 * 1024


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