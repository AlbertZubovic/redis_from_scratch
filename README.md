# Redis From Scratch

## Overview

A `redis-cli` compatible in memory key-value database server built from scratch in
Python.

The server communicates with clients over TCP using the Redis Serialization Protocol
(RESP) and supports common Redis commands, key expiration and Pub/Sub
messaging.

This project was built to explore socket programming, multithreading, network
protocols and the internal workings of an in-memory database.

## Features

- In-memory key-value storage.
- TCP server supporting multiple concurrent clients.
- Redis Serialization Protocol (RESP2) support.
- Compatible with `redis-cli`.
- Common Redis commands for key-value operations and expiration.
- Pub/Sub messaging between clients.
- Thread-safe database operations using locks.

## Getting Started

### Prerequisites

- Python 3.12 or later (tested on Python 3.12 and 3.14)
- `redis-cli` (optional, for interacting with the server)

### Installation

```bash
git clone https://github.com/AlbertZubovic/redis_from_scratch
cd redis_from_scratch
```

### Running the Server

```bash
python -m server
```

### Connecting to the Server

With the server running, open another terminal and connect using `redis-cli`:

```bash
redis-cli -p 6379
```

### Example Usage

```text
127.0.0.1:6379> SET name Alice
OK
127.0.0.1:6379> GET name
"Alice"
127.0.0.1:6379> INCR counter
(integer) 1
127.0.0.1:6379> INCR counter
(integer) 2
127.0.0.1:6379> GET counter
"2"
```

## Supported Commands

### Connection Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| PING | `PING [message]` | Checks the connection to the server. |
| ECHO | `ECHO message` | Returns the provided message. |

### String Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| GET | `GET key` | Returns the value associated with a key. |
| SET | `SET key value [EX seconds]` | Stores a value under a key, optionally with an expiration time. |
| INCR | `INCR key` | Increments an integer value by 1. |
| DECR | `DECR key` | Decrements an integer value by 1. |
| INCRBY | `INCRBY key increment` | Increments an integer value by a specified amount. |
| DECRBY | `DECRBY key decrement` | Decrements an integer value by a specified amount. |

### Key Management Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| DEL | `DEL key [key ...]` | Deletes one or more keys. |
| EXISTS | `EXISTS key [key ...]` | Returns the number of specified keys that exist. |
| TYPE | `TYPE key` | Returns the data type of a key. |
| RENAME | `RENAME key newkey` | Renames a key, overwriting the destination if it exists. |

### Expiration Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| EXPIRE | `EXPIRE key seconds` | Sets a key's expiration time in seconds. |
| PEXPIRE | `PEXPIRE key milliseconds` | Sets a key's expiration time in milliseconds. |
| TTL | `TTL key` | Returns a key's remaining lifetime in seconds. |
| PTTL | `PTTL key` | Returns a key's remaining lifetime in milliseconds. |
| PERSIST | `PERSIST key` | Removes a key's expiration time. |

### Pub/Sub Commands

| Command | Syntax | Description |
|---------|--------|-------------|
| SUBSCRIBE | `SUBSCRIBE channel [channel ...]` | Subscribes the client to one or more channels. |
| UNSUBSCRIBE | `UNSUBSCRIBE [channel ...]` | Unsubscribes the client from specified channels. |
| PUBLISH | `PUBLISH channel message` | Publishes a message to a channel and returns the number of recipients. |


## Architecture

### RESP Protocol

The server uses the Redis Serialization Protocol (RESP2) to communicate with clients.

Incoming RESP commands are parsed into their individual elements before being
processed by the command dispatcher. The results are then formatted as RESP
responses and sent back to the client.

RESP parsing and formatting are handled by the `resp.py` module.

### TCP Server and Multithreading

The server uses TCP sockets to accept incoming client connections and exchange
RESP messages.

Each client connection is handled by a separate thread, allowing multiple clients to
interact with the server concurrently.

A shared threading lock protects database operations, ensuring that multiple
threads cannot modify the database simultaneously.

### In-Memory Database

The server stores data received from clients in-memory, allowing for fast data
retrieval.

Data is stored as key-value pairs, with both keys and values represented as bytes.
Each key can also have an optional expiration time, after which the key is considered
expired and can no longer be accessed.

### Pub/Sub System

The server implements a Publish/Subscribe (Pub/Sub) messaging system, allowing
multiple clients to subscribe to channels.

Clients can publish messages to a channel, which are then delivered to all clients
currently subscribed to that channel.

## Testing

Install the development dependencies:

```bash
python -m pip install pytest ruff
```

### Unit Tests

Run the unit tests:

```bash
python -m pytest tests/ --ignore=tests/integration/ -v
```

### Integration Tests

Run the integration tests:

```bash
python -m pytest tests/integration/ -v
```

### Linting and Formatting

Check for linting issues using Ruff:

```bash
python -m ruff check .
```

Check code formatting:

```bash
python -m ruff format --check .
```

Automatically fix linting and formatting issues:

```bash
python -m ruff check . --fix
python -m ruff format .
```

### Continuous Integration

GitHub Actions is used to automatically run unit tests, integration tests and Ruff
linting and formatting checks on every push and pull request.


## Project Structure

```text
redis_from_scratch/
├── .github/
│   └── workflows/
│       └── tests.yml
├── tests/
│   ├── integration/
│   │   ├── conftest.py
│   │   └── test_server.py
│   ├── server/
│   │   ├── conftest.py
│   │   ├── test_basic_commands.py
│   │   ├── test_connection_handling.py
│   │   ├── test_database_commands.py
│   │   └── test_pubsub_commands.py
│   ├── test_connection.py
│   ├── test_database.py
│   ├── test_pubsub.py
│   └── test_resp.py
├── .gitignore
├── connection.py
├── database.py
├── main.py
├── pubsub.py
├── README.md
├── resp.py
└── server.py
```

### Key Modules

- **`main.py`** — Entry point for the application.
- **`server.py`** — TCP server, client handling, and command dispatching.
- **`connection.py`** — Client connection management.
- **`database.py`** — In-memory key-value storage and database operations.
- **`pubsub.py`** — Publish/Subscribe messaging functionality.
- **`resp.py`** — RESP parsing and response formatting.
- **`tests/`** — Unit and integration tests.
- **`.github/workflows/`** — GitHub Actions workflow for automated testing and code-quality checks.

## Limitations

- Only supports a subset of Redis commands.
- Only stores string values; other Redis data types are not implemented.
- Data is stored in memory and is lost when the server shuts down.
- Key expiration uses lazy expiration rather than background cleanup.

## Future Improvements

- **Additional Redis data types:** Implement lists, hashes, and sets, along with their associated commands.
- **AOF persistence:** Add append-only file persistence to preserve data between server restarts.
- **RESP3 support:** Implement RESP3 and protocol negotiation using `HELLO`.
- **Transactions:** Support atomic command execution using `MULTI`, `EXEC`, and `DISCARD`.
- **Improved protocol compatibility:** Expand RESP2 error handling, Pub/Sub behavior, and compatibility with Redis clients.
- **Event-driven networking:** Explore nonblocking sockets and event loops as an alternative to the current multithreaded architecture.
- **Replication:** Support primary-replica synchronization and write propagation.
- **Performance improvements:** Add benchmarking, load testing, and optimizations.
- **Docker support:** Containerize the server for easier deployment.


