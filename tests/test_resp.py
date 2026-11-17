import pytest

from resp import parse_resp_command, format_resp_simple_string, format_resp_bulk_string, format_resp_error, format_resp_integer, format_resp_array


# RESP formatting tests
@pytest.mark.parametrize(
    "input_value, expected",
    [
        pytest.param("ping", b"+ping\r\n", id="lowercase"),
        pytest.param("PONG", b"+PONG\r\n", id="uppercase"),
        pytest.param("Hello World", b"+Hello World\r\n", id="spaces"),
        pytest.param("", b"+\r\n", id="empty-string"),
        pytest.param("123", b"+123\r\n", id="numbers"),
        pytest.param("OK!", b"+OK!\r\n", id="special-characters"),
        pytest.param("café", b"+caf\xc3\xa9\r\n", id="unicode"),
        pytest.param("a" * 1000, b"+" + b"a" * 1000 + b"\r\n", id="long-string"),
    ]
)
def test_format_resp_simple_string(input_value: str, expected: bytes) -> None:
    assert format_resp_simple_string(input_value) == expected


@pytest.mark.parametrize(
    "input_value, expected",
    [
        pytest.param(b"ping", b"$4\r\nping\r\n", id="lowercase"),
        pytest.param(b"PONG", b"$4\r\nPONG\r\n", id="uppercase"),
        pytest.param(b"Hello World", b"$11\r\nHello World\r\n", id="spaces"),
        pytest.param(b"", b"$0\r\n\r\n", id="empty-bytes"),
        pytest.param(None, b"$-1\r\n", id="null"),
        pytest.param(b"123", b"$3\r\n123\r\n", id="numbers"),
        pytest.param(b"\x00\xff", b"$2\r\n\x00\xff\r\n", id="binary-data"),
        pytest.param(b"hello\r\nworld", b"$12\r\nhello\r\nworld\r\n", id="embedded-crlf"),
    ]
)
def test_format_resp_bulk_string(input_value: bytes | None, expected: bytes) -> None:
    assert format_resp_bulk_string(input_value) == expected


@pytest.mark.parametrize(
    "input_value, expected",
        [pytest.param("error", b"-error\r\n", id="lowercase"),
            pytest.param("ERROR", b"-ERROR\r\n", id="uppercase"),
            pytest.param("Major Error", b"-Major Error\r\n", id="spaces"),
            pytest.param("", b"-\r\n", id="empty-string"),
            pytest.param("ERR unknown command", b"-ERR unknown command\r\n", id="redis-error"),
        ],
)
def test_format_resp_error(input_value: str, expected: bytes) -> None:
    assert format_resp_error(input_value) == expected


@pytest.mark.parametrize(
    "input_value, expected",
        [
            pytest.param(1, b":1\r\n", id="single-digit"),
            pytest.param(10, b":10\r\n", id="multiple-digits"),
            pytest.param(0, b":0\r\n", id="zero"),
            pytest.param(-1, b":-1\r\n", id="negative"),
            pytest.param(9223372036854775807, b":9223372036854775807\r\n", id="max-int64"),
        ],
)
def test_format_resp_integer(input_value: int, expected: bytes) -> None:
    assert format_resp_integer(input_value) == expected


@pytest.mark.parametrize(
    "input_value, expected",
    [
        pytest.param(
            (b"subscribe", b"notifications", 1),
            b"*3\r\n$9\r\nsubscribe\r\n$13\r\nnotifications\r\n:1\r\n",
            id="subscribe-notification-with-one-channel",
        ),
        pytest.param(
            (),
            b"*0\r\n",
            id="empty-array",
        ),
        pytest.param(
            (b"hello",),
            b"*1\r\n$5\r\nhello\r\n",
            id="single-element",
        ),
        pytest.param(
            (b"unsubscribe", None, 0),
            b"*3\r\n$11\r\nunsubscribe\r\n$-1\r\n:0\r\n",
            id="null-element",
        ),
        pytest.param(
            (b"", -1),
            b"*2\r\n$0\r\n\r\n:-1\r\n",
            id="empty-bulk-and-negative-integer",
        ),
    ],
)
def test_format_resp_array(input_value: tuple[bytes | int | None, ...], expected: bytes) -> None:
    assert format_resp_array(*input_value) == expected


# RESP parsing tests
@pytest.mark.parametrize(
    "input_value, expected",
    [
        pytest.param(
            b"*1\r\n$4\r\nping\r\n",
            ([b"ping"], 14),
            id="complete-ping-command",
        ),
        pytest.param(
            b"*2\r\n$3\r\nGET\r\n$5\r\nhello\r\n",
            ([b"GET", b"hello"], 24),
            id="multiple-arguments",
        ),
        pytest.param(
            b"*2\r\n$3\r\nGET\r\n",
            None,
            id="incomplete-command",
        ),
        pytest.param(
            b"*1\r\n$4\r\npi",
            None,
            id="incomplete-bulk-string",
        ),
        pytest.param(
            b"*1\r\n$4\r\nPING\r\n*1\r\n$4\r\nPONG\r\n",
            ([b"PING"], 14),
            id="pipelined-commands",
        ),
        pytest.param(
            b"*1\r\n$4\r\nPING\r\nextra",
            ([b"PING"], 14),
            id="extra-trailing-bytes",
        ),
        pytest.param(
            b"*2\r\n$3\r\nSET\r\n$4\r\na\x00\xffb\r\n",
            ([b"SET", b"a\x00\xffb"], 23),
            id="binary-data",
        ),
        pytest.param(
            b"*2\r\n$3\r\nSET\r\n$0\r\n\r\n",
            ([b"SET", b""], 19),
            id="empty-bulk-string-argument",
        ),
        pytest.param(
            b"*2\r\n$3\r\nSET\r\n$4\r\na\r\nb\r\n",
            ([b"SET", b"a\r\nb"], 23),
            id="embedded-crlf-in-bulk-string",
        ),
    ],
)
def test_parse_resp_command(input_value: bytes, expected: tuple[list[bytes], int] | None) -> None:
    assert parse_resp_command(input_value) == expected


@pytest.mark.parametrize(
    "input_value",
    [
        pytest.param(
            b"PING\r\n",
            id="missing-array-prefix",
        ),
        pytest.param(
            b"*abc\r\n",
            id="invalid-array-length",
        ),
        pytest.param(
            b"*1\r\n!4\r\nPING\r\n",
            id="invalid-bulk-string-prefix",
        ),
        pytest.param(
            b"*1\r\n$abc\r\nPING\r\n",
            id="invalid-bulk-string-length",
        ),
        pytest.param(
            b"*1\r\n$4\r\nPINGxx",
            id="missing-bulk-string-terminator",
        ),
    ],
)
def test_parse_resp_command_invalid_input(input_value: bytes) -> None:
    with pytest.raises(ValueError):
        parse_resp_command(input_value)


@pytest.mark.parametrize(
    "input_value",
    [
        pytest.param(b"", id="empty-buffer"),
        pytest.param(b"*", id="partial-array-header"),
        pytest.param(b"*1\r", id="incomplete-array-crlf"),
        pytest.param(b"*1\r\n$", id="partial-bulk-header"),
        pytest.param(b"*1\r\n$4\r", id="incomplete-bulk-crlf"),
        pytest.param(b"*1\r\n$4\r\nPING\r", id="incomplete-payload-crlf"),
    ],
)
def test_parse_resp_command_incomplete_headers(input_value: bytes) -> None:
    assert parse_resp_command(input_value) is None


def test_parse_resp_command_pipelined():
    buffer = (
        b"*1\r\n$4\r\nPING\r\n"
        b"*1\r\n$4\r\nPONG\r\n"
    )

    first_command, consumed = parse_resp_command(buffer)
    assert first_command == [b"PING"]

    second_command, second_consumed = parse_resp_command(buffer[consumed:])
    assert second_command == [b"PONG"]

    assert consumed + second_consumed == len(buffer)


@pytest.mark.parametrize(
    "split_index",
    range(14),
)
def test_parse_resp_command_partial_ping(split_index: int) -> None:
    command = b"*1\r\n$4\r\nPING\r\n"

    assert parse_resp_command(command[:split_index]) is None
    assert parse_resp_command(command) == ([b"PING"], 14)