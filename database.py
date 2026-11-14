import logging
import time


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
        else:
            raise ValueError()
    logging.debug("SET key=%r: value stored", key)


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