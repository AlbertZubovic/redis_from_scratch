"""Implement Redis key-value database operations."""

import logging
import time

logger = logging.getLogger(__name__)

MIN_INT = -(2**63)
MAX_INT = 2**63 - 1


def handle_get(
    key: bytes, database: dict[bytes, tuple[bytes, float | None]]
) -> bytes | None:
    """Return a key's value, removing expired entries and returning None if absent."""

    if remove_if_expired(key, database):
        return None

    entry = database.get(key)

    if entry is None:
        return None

    value, _ = entry

    logger.debug("GET key=%r: value retrieved", key)

    return value


def handle_set(
    key: bytes,
    value: bytes,
    database: dict[bytes, tuple[bytes, float | None]],
    expiration: bytes | None = None,
) -> None:
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
        if not isinstance(expiration, bytes):
            raise ValueError()

        expiration_time = expiration.decode()

        if expiration_time.isdigit() and int(expiration_time) > 0:
            database[key] = (value, time.monotonic() + int(expiration_time))
        else:
            raise ValueError()
    logger.debug("SET key=%r: value stored", key)


def handle_del(
    keys: list[bytes], database: dict[bytes, tuple[bytes, float | None]]
) -> int:
    """
    Delete the specified keys and return the number of keys removed.

    Expired and nonexistent keys are not counted.
    Expired entries encountered during deletion are also removed.
    """

    deleted_count = 0

    for key in keys:
        if remove_if_expired(key, database):
            continue

        entry = database.get(key)

        if entry is None:
            continue

        del database[key]
        deleted_count += 1
        logger.debug("DEL key=%r: key deleted", key)

    return deleted_count


def handle_exists(
    keys: list[bytes], database: dict[bytes, tuple[bytes, float | None]]
) -> int:
    """Return the number of existing, non-expired keys."""

    keys_found = 0
    for key in keys:
        if remove_if_expired(key, database):
            continue

        if key in database:
            keys_found += 1

    return keys_found


def handle_get_ttl(
    key: bytes, database: dict[bytes, tuple[bytes, float | None]], mode: str = "ttl"
) -> int:
    """Return the remaining expiration time of a key in seconds or milliseconds."""

    if remove_if_expired(key, database):
        return -2

    entry = database.get(key)

    if entry is None:
        return -2

    expiration = entry[1]

    if expiration is None:
        return -1

    remaining_time = max(0.0, entry[1] - time.monotonic())

    return int(remaining_time) if mode == "ttl" else int(remaining_time * 1000)


def handle_set_expire(
    key: bytes,
    expiration: bytes,
    database: dict[bytes, tuple[bytes, float | None]],
    mode: str = "expire",
) -> int:
    """Set or replace a key's expiration, returning 1 on success or 0 otherwise."""

    duration = int(expiration)

    if mode == "pexpire":
        duration /= 1000

    if remove_if_expired(key, database):
        return 0

    if key not in database:
        return 0

    if duration <= 0:
        del database[key]
        return 1

    value, _ = database[key]
    database[key] = (value, time.monotonic() + duration)

    return 1


def handle_persist(
    key: bytes, database: dict[bytes, tuple[bytes, float | None]]
) -> int:
    """Remove a key's expiration, returning 1 if removed or 0 otherwise."""

    if remove_if_expired(key, database):
        return 0

    if key not in database:
        return 0

    if database[key][1] is None:
        return 0

    value, _ = database[key]
    database[key] = (value, None)

    return 1


# TODO: Extend type detection when additional Redis data types are supported.
def handle_type(key: bytes, database: dict[bytes, tuple[bytes, float | None]]) -> str:
    """Return the Redis type of a key."""

    if remove_if_expired(key, database):
        return "none"

    if key not in database:
        return "none"

    return "string"


def handle_rename(
    key: bytes, new_key: bytes, database: dict[bytes, tuple[bytes, float | None]]
) -> str:
    """Rename a key while preserving its value."""

    if remove_if_expired(key, database):
        raise ValueError("ERR no such key")

    if key not in database:
        raise ValueError("ERR no such key")

    if key == new_key:
        raise ValueError("ERR source and destination objects are the same")

    database[new_key] = database.pop(key)

    logger.debug("RENAME key=%r: renamed to %r", key, new_key)

    return "OK"


def handle_increment(
    key: bytes, amount: bytes, database: dict[bytes, tuple[bytes, float | None]]
) -> int:
    """Increment a key's integer value by the specified amount and return the result."""

    remove_if_expired(key, database)

    try:
        increment_amount = int(amount)
        value, expiration = database.get(key, (b"0", None))
        current_value = int(value)
    except ValueError:
        raise ValueError("ERR value is not an integer or out of range")

    if not MIN_INT <= increment_amount <= MAX_INT:
        raise ValueError("ERR value is not an integer or out of range")

    if not MIN_INT <= current_value <= MAX_INT:
        raise ValueError("ERR value is not an integer or out of range")

    new_value = current_value + increment_amount

    if not MIN_INT <= new_value <= MAX_INT:
        raise ValueError("ERR increment or decrement would overflow")

    database[key] = (str(new_value).encode(), expiration)

    logger.debug("INCREMENT key=%r: new_value=%d", key, new_value)

    return new_value


def remove_if_expired(
    key: bytes, database: dict[bytes, tuple[bytes, float | None]]
) -> bool:
    """Remove an expired key and return True if it was removed."""

    entry = database.get(key)

    if entry is None:
        return False

    if is_key_expired(entry[1]):
        del database[key]
        logger.debug("Key expired and removed: key=%r", key)
        return True

    return False


def is_key_expired(expiration: float | None) -> bool:
    """Return whether the expiration deadline has passed."""

    return expiration is not None and expiration <= time.monotonic()
