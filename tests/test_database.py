import time

import pytest

from database import (
    MAX_INT,
    MIN_INT,
    handle_del,
    handle_exists,
    handle_get,
    handle_get_ttl,
    handle_increment,
    handle_persist,
    handle_rename,
    handle_set,
    handle_set_expire,
    handle_type,
    is_key_expired,
    remove_if_expired,
)


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
        b"expires_very_soon": (b"expire", now + 10),
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
def test_get_stored_values(
    key: bytes, expected: bytes, database: dict[bytes, tuple[bytes, float | None]]
) -> None:
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
def test_get_unexpired_key(
    key: bytes, expected: bytes, database: dict[bytes, tuple[bytes, float | None]]
) -> None:
    assert handle_get(key, database) == expected
    assert key in database


def test_get_expired_key_twice(
    database: dict[bytes, tuple[bytes, float | None]],
) -> None:
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
def test_set_stored_values(
    key: bytes,
    value: bytes,
    database: dict[bytes, tuple[bytes, float | None]],
    expiration: int | None,
) -> None:
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
def test_set_invalid_expiration(
    key: bytes,
    value: bytes,
    database: dict[bytes, tuple[bytes, float | None]],
    expiration: str | int,
) -> None:
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
def test_del_stored_values(
    keys: list[bytes], expected: int, database: dict[bytes, tuple[bytes, float | None]]
) -> None:
    assert handle_del(keys, database) == expected

    for key in keys:
        assert key not in database


# EXISTS
@pytest.mark.parametrize(
    "keys, expected",
    [
        ([b"name"], 1),
        ([b"wrong_key"], 0),
        ([b"name", b"age"], 2),
        ([b"name", b"wrong_key"], 1),
        ([b"name", b"name"], 2),
        ([b"name", b"age", b"wrong_key"], 2),
    ],
)
def test_exists_stored_values(
    keys: list[bytes], expected: int, database: dict[bytes, tuple[bytes, float | None]]
) -> None:
    assert handle_exists(keys, database) == expected


def test_exists_expired_key(database: dict[bytes, tuple[bytes, float | None]]) -> None:
    assert handle_exists([b"expired"], database) == 0
    assert b"expired" not in database


def test_exists_unexpired_key(
    database: dict[bytes, tuple[bytes, float | None]],
) -> None:
    assert handle_exists([b"expires_soon"], database) == 1


# TTL tests
@pytest.mark.parametrize(
    "key, mode",
    [
        (b"expires_soon", "ttl"),
        (b"expires_very_soon", "ttl"),
        (b"expires_soon", "pttl"),
        (b"expires_very_soon", "pttl"),
    ],
)
def test_get_ttl(
    key: bytes, mode: str, database: dict[bytes, tuple[bytes, float | None]]
):
    multiplier = 1000 if mode == "pttl" else 1

    expiration = database[key][1]
    assert expiration is not None

    before = max(0, int((expiration - time.monotonic()) * multiplier))
    ttl = handle_get_ttl(key, database, mode)
    after = max(0, int((expiration - time.monotonic()) * multiplier))

    assert after <= ttl <= before


@pytest.mark.parametrize(
    "key, mode",
    [
        (b"name", "ttl"),
        (b"age", "ttl"),
        (b"empty", "pttl"),
    ],
)
def test_get_ttl_with_no_expiration(
    key: bytes, mode: str, database: dict[bytes, tuple[bytes, float | None]]
):
    assert handle_get_ttl(key, database, mode) == -1


@pytest.mark.parametrize(
    "key",
    [b"invalid_key", b"expired"],
)
@pytest.mark.parametrize("mode", ["ttl", "pttl"])
def test_get_ttl_missing_or_expired(
    key: bytes, mode: str, database: dict[bytes, tuple[bytes, float | None]]
) -> None:
    assert handle_get_ttl(key, database, mode) == -2

    if key == b"expired":
        assert key not in database


# SET EXPIRE tests
@pytest.mark.parametrize(
    "mode, duration, expected_seconds",
    [
        ("expire", b"60", 60),
        ("pexpire", b"1500", 1.5),
        ("expire", b"1", 1),
        ("pexpire", b"1", 0.001),
    ],
)
def test_set_expire_success(
    database: dict[bytes, tuple[bytes, float | None]],
    mode: bytes,
    duration: bytes,
    expected_seconds: int,
):
    database[b"name"] = (b"Alice", None)

    before = time.monotonic()
    result = handle_set_expire(b"name", duration, database, mode)
    after = time.monotonic()

    assert result == 1

    value, deadline = database[b"name"]
    assert value == b"Alice"
    assert deadline is not None
    assert before + expected_seconds <= deadline <= after + expected_seconds


@pytest.mark.parametrize("mode", ["expire", "pexpire"])
def test_set_expire_missing_key(
    database: dict[bytes, tuple[bytes, float | None]], mode: bytes
):
    result = handle_set_expire(b"missing", b"60", database, mode)

    assert result == 0
    assert b"missing" not in database


@pytest.mark.parametrize("mode", ["expire", "pexpire"])
def test_set_expire_already_expired_key(
    database: dict[bytes, tuple[bytes, float | None]], mode: bytes
):
    database[b"name"] = (b"Alice", time.monotonic() - 10)

    result = handle_set_expire(b"name", b"60", database, mode)

    assert result == 0
    assert b"name" not in database


@pytest.mark.parametrize(
    "mode, duration",
    [
        ("expire", b"0"),
        ("expire", b"-10"),
        ("pexpire", b"0"),
        ("pexpire", b"-100"),
    ],
)
def test_set_expire_nonpositive_duration(
    database: dict[bytes, tuple[bytes, float | None]], mode: str, duration: bytes
):
    database[b"name"] = (b"Alice", None)

    result = handle_set_expire(b"name", duration, database, mode)

    assert result == 1
    assert b"name" not in database


@pytest.mark.parametrize(
    "mode, duration",
    [
        ("expire", b"hello"),
        ("expire", b"1.5"),
        ("expire", b""),
        ("pexpire", b"abc"),
        ("pexpire", b"2.5"),
        ("pexpire", b""),
    ],
)
def test_set_expire_invalid_duration(
    database: dict[bytes, tuple[bytes, float | None]], mode: str, duration: bytes
):
    database[b"name"] = (b"Alice", None)

    with pytest.raises(ValueError):
        handle_set_expire(b"name", duration, database, mode)

    assert database[b"name"] == (b"Alice", None)


@pytest.mark.parametrize("mode", ["expire", "pexpire"])
def test_set_expire_replaces_existing_expiration(
    database: dict[bytes, tuple[bytes, float | None]], mode: str
):
    old_deadline = time.monotonic() + 1000
    database[b"name"] = (b"Alice", old_deadline)

    result = handle_set_expire(b"name", b"10", database, mode)

    assert result == 1

    value, new_deadline = database[b"name"]

    assert value == b"Alice"
    assert new_deadline is not None
    assert new_deadline < old_deadline


@pytest.mark.parametrize("mode", ["expire", "pexpire"])
def test_set_expire_invalid_duration_missing_key(
    database: dict[bytes, tuple[bytes, float | None]], mode: str
):
    with pytest.raises(ValueError):
        handle_set_expire(b"missing", b"invalid", database, mode)

    assert b"missing" not in database


# PERSIST tests
@pytest.mark.parametrize(
    "key",
    [
        b"expires_soon",
        b"expires_very_soon",
        b"expires_later",
    ],
)
def test_persist_success(key: bytes, database: dict[bytes, tuple[bytes, float | None]]):
    assert handle_persist(key, database) == 1

    assert database[key][1] is None


def test_persist_missing_key(database: dict[bytes, tuple[bytes, float | None]]):
    assert handle_persist(b"missing", database) == 0

    assert b"missing" not in database


def test_persist_already_expired_key(database: dict[bytes, tuple[bytes, float | None]]):
    assert handle_persist(b"expired", database) == 0

    assert b"expired" not in database


def test_persist_no_expiration(database: dict[bytes, tuple[bytes, float | None]]):
    assert handle_persist(b"name", database) == 0

    assert database[b"name"][1] is None


# TYPE tests
@pytest.mark.parametrize(
    "key, expected",
    [
        (b"name", "string"),
        (b"missing", "none"),
        (b"expired", "none"),
    ],
)
def test_type(
    key: bytes, expected: bytes, database: dict[bytes, tuple[bytes, float | None]]
):
    assert handle_type(key, database) == expected

    if key == b"expired":
        assert key not in database


# RENAME tests
@pytest.mark.parametrize(
    "key, new_key",
    [
        (b"name", b"date"),
        (b"age", b"number"),
        (b"empty", b"entry"),
    ],
)
def test_rename(
    key: bytes, new_key: bytes, database: dict[bytes, tuple[bytes, float | None]]
):
    original_entry = database[key]

    assert handle_rename(key, new_key, database) == "OK"

    assert key not in database
    assert database[new_key] == original_entry


@pytest.mark.parametrize(
    "key, new_key, expected_error",
    [
        (b"expired", b"not_expired", "ERR no such key"),
        (b"no_key", b"key", "ERR no such key"),
        (b"binary", b"binary", "ERR source and destination objects are the same"),
    ],
)
def test_invalid_rename(key, new_key, expected_error, database):
    with pytest.raises(ValueError, match=expected_error):
        handle_rename(key, new_key, database)

    if key == b"expired":
        assert key not in database


def test_rename_overwrites_existing_key(database):
    original_entry = database[b"name"]

    assert handle_rename(b"name", b"age", database) == "OK"

    assert b"name" not in database
    assert database[b"age"] == original_entry


# INCR / DECR / INCRBY / DECRBY
@pytest.mark.parametrize(
    "key, amount, expected",
    [
        (b"counter", b"1", 11),
        (b"counter", b"-1", 9),
        (b"counter", b"5", 15),
        (b"counter", b"-5", 5),
        (b"counter", b"0", 10),
        (b"counter", b"-15", -5),
    ],
)
def test_increment(
    key: bytes,
    amount: bytes,
    expected: int,
    database: dict[bytes, tuple[bytes, float | None]],
):
    database[key] = (b"10", None)

    result = handle_increment(key, amount, database)

    assert result == expected
    assert database[key] == (str(expected).encode(), None)


@pytest.mark.parametrize(
    "amount, expected",
    [
        (b"1", 1),
        (b"-1", -1),
        (b"5", 5),
        (b"-5", -5),
        (b"0", 0),
    ],
)
def test_increment_missing_key(
    amount: bytes, expected: int, database: dict[bytes, tuple[bytes, float | None]]
):
    key = b"missing_increment_key"
    database.pop(key, None)

    result = handle_increment(key, amount, database)

    assert result == expected
    assert database[key] == (str(expected).encode(), None)


def test_increment_expired_key(database: dict[bytes, tuple[bytes, float | None]]):

    database[b"counter"] = (b"10", time.monotonic() - 10)

    result = handle_increment(b"counter", b"5", database)

    assert result == 5
    assert database[b"counter"] == (b"5", None)


def test_increment_preserves_expiration(
    database: dict[bytes, tuple[bytes, float | None]],
):

    expiration = time.monotonic() + 100
    database[b"counter"] = (b"10", expiration)

    result = handle_increment(b"counter", b"5", database)

    assert result == 15
    assert database[b"counter"] == (b"15", expiration)


@pytest.mark.parametrize(
    "value, amount",
    [
        (b"hello", b"1"),
        (b"10.5", b"1"),
        (b"10", b"hello"),
        (b"10", b"1.5"),
        (b"10", str(MAX_INT + 1).encode()),
        (str(MAX_INT + 1).encode(), b"1"),
        (str(MIN_INT - 1).encode(), b"1"),
    ],
)
def test_increment_invalid_integer(
    value: bytes, amount: bytes, database: dict[bytes, tuple[bytes, float | None]]
):
    database[b"counter"] = (value, None)

    with pytest.raises(ValueError, match="ERR value is not an integer or out of range"):
        handle_increment(b"counter", amount, database)

    assert database[b"counter"] == (value, None)


@pytest.mark.parametrize(
    "value, amount",
    [
        (MAX_INT, 1),
        (MIN_INT, -1),
        (MAX_INT, 10),
        (MIN_INT, -10),
    ],
)
def test_increment_overflow(
    value: int, amount: int, database: dict[bytes, tuple[bytes, float | None]]
):
    original_value = str(value).encode()
    database[b"counter"] = (original_value, None)

    with pytest.raises(ValueError, match="ERR increment or decrement would overflow"):
        handle_increment(b"counter", str(amount).encode(), database)

    assert database[b"counter"] == (original_value, None)


@pytest.mark.parametrize(
    "value, amount, expected",
    [
        (MAX_INT - 1, 1, MAX_INT),
        (MIN_INT + 1, -1, MIN_INT),
        (MAX_INT, 0, MAX_INT),
        (MIN_INT, 0, MIN_INT),
    ],
)
def test_increment_integer_boundaries(
    value: int,
    amount: int,
    expected: int,
    database: dict[bytes, tuple[bytes, float | None]],
):
    database[b"counter"] = (str(value).encode(), None)

    result = handle_increment(b"counter", str(amount).encode(), database)

    assert result == expected
    assert database[b"counter"] == (str(expected).encode(), None)


# Expiration helpers
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


@pytest.mark.parametrize(
    "key, expected, should_exist",
    [
        (b"expired", True, False),
        (b"expires_soon", False, True),
        (b"wrong_key", False, False),
    ],
)
def test_remove_if_expired(
    key: bytes,
    expected: bool,
    should_exist: bool,
    database: dict[bytes, tuple[bytes, float | None]],
) -> None:
    assert remove_if_expired(key, database) is expected
    assert (key in database) is should_exist
