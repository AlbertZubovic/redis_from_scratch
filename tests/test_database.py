import time
import pytest

from database import handle_get, handle_set, handle_del, is_key_expired


# Fixtures
@pytest.fixture
def database() -> dict[bytes, tuple[bytes, float | None]]:
    now = time.monotonic()
    return {
        b"name": (b"alice", None),
        b"age": (b"25", None),
        b"empty": (b"", None),
        b"binary": (b"\x00\xff", None),

        # Expiration cases
        b"expired": (b"old_value", now - 60),
        b"expires_soon": (b"temporary", now + 60),
        b"expires_later": (b"long_lived", now + 3600),
    }


# GET
@pytest.mark.parametrize(
    "key, expected",
    [
        (b"name", b"alice"),
        (b"age", b"25"),
        (b"empty", b""),
        (b"binary", b"\x00\xff"),
    ],
)
def test_get_stored_values(key: bytes, expected: bytes, database: dict[bytes, tuple[bytes, float | None]]) -> None:
    assert handle_get(key, database) == expected


def test_get_missing_key(database: dict[bytes, tuple[bytes, float | None]]) -> None:
    assert handle_get(b"wrong_key", database) is None


def test_get_expired_key(database: dict[bytes, tuple[bytes, float | None]]) -> None:
    assert handle_get(b"expired", database) is None
    assert b"expired" not in database


@pytest.mark.parametrize(
    "key, expected",
    [
        (b"expires_soon", b"temporary"),
        (b"expires_later", b"long_lived"),
    ],
)
def test_get_unexpired_key(key: bytes, expected: bytes, database: dict[bytes, tuple[bytes, float | None]]) -> None:
    assert handle_get(key, database) == expected
    assert key in database


def test_get_expired_key_twice(database: dict[bytes, tuple[bytes, float | None]]) -> None:
    assert handle_get(b"expired", database) is None
    assert b"expired" not in database

    assert handle_get(b"expired", database) is None


# SET
@pytest.mark.parametrize(
    "key, value, expiration",
    [
        pytest.param(b"name", b"bob", None, id="overwrite-existing-key"),
        pytest.param(b"new_key", b"hello", None, id="new-key"),
        pytest.param(b"empty", b"", None, id="empty-value"),
        pytest.param(b"binary", b"\x00\xff", None, id="binary-value"),
        pytest.param(b"", b"hello", None, id="empty-key"),
        pytest.param(b"number", b"123", None, id="numeric-value"),
        pytest.param(b"expires_soon", b"permanent", None, id="overwrite-expiring-key"),
    ],
)
def test_set_stored_values(key: bytes, value: bytes, database: dict[bytes, tuple[bytes, float | None]], expiration: int | None) -> None:
    handle_set(key, value, database, expiration)

    assert handle_get(key, database) == value
    assert database[key] == (value, expiration)


@pytest.mark.parametrize("ttl", [b"1", b"60"])
def test_set_with_expiration(ttl, database) -> None:
    before = time.monotonic()

    handle_set(b"temporary", b"hello", database, ttl)

    after = time.monotonic()

    value, expiration = database[b"temporary"]

    assert value == b"hello"
    assert expiration is not None

    ttl_seconds = int(ttl)
    assert before + ttl_seconds <= expiration <= after + ttl_seconds


@pytest.mark.parametrize(
    "key, value, expiration",
    [
        pytest.param(b"name", b"bob", "10", id="string"),
        pytest.param(b"new_key", b"hello", -5, id="negative-time"),
    ],
)
def test_set_invalid_expiration(key: bytes, value: bytes, database: dict[bytes, tuple[bytes, float | None]], expiration: str | int) -> None:
    original = database.copy()

    with pytest.raises(ValueError):
        handle_set(key, value, database, expiration)

    assert database == original


# DEL
@pytest.mark.parametrize(
    "keys, expected",
    [
        pytest.param([b"name"], 1, id="delete-key"),
        pytest.param([b"age", b"binary"], 2, id="delete-multiple-keys"),
        pytest.param([b"wrong-key"], 0, id="missing-key"),
        pytest.param([b"empty", b"wrong-key"], 1, id="mixed-existing-missing"),
        pytest.param([b"name", b"name"], 1, id="duplicate-keys"),
        pytest.param([b"expired"], 0, id="expired-key"),
        pytest.param([b"name", b"expired"], 1, id="mixed-valid-expired"),
        pytest.param([b"expires_soon"], 1, id="unexpired-key"),
        pytest.param([], 0, id="empty-key-list"),
    ],
)
def test_del_stored_values(keys: list[bytes], expected: int, database: dict[bytes, tuple[bytes, float | None]]) -> None:
    assert handle_del(keys, database) == expected

    for key in keys:
        assert key not in database


# Expiration helper
@pytest.mark.parametrize(
    "offset, expected",
    [
        pytest.param(None, False, id="no-expiration"),
        pytest.param(-60, True, id="negative-timestamp"),
        pytest.param(0, True, id="expires-now"),
        pytest.param(60, False, id="future-expiration"),
    ],
)
def test_is_key_expired(offset: float | None, expected: bool) -> None:
    expiration = None if offset is None else time.monotonic() + offset

    assert is_key_expired(expiration) is expected