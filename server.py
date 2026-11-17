import logging
import socket
import threading
from typing import Final

import database
import pubsub
import resp

from connection import ClientConnection


MAX_BUFFER_SIZE: Final[int] = 1024 * 1024


def run_server(port: int = 6379, shutdown_event: threading.Event | None = None) -> None:
    """
    Start the Redis-compatible TCP server.

    Accept client connections in separate threads, maintain a shared
    in-memory database and stop when shutdown is requested.
    """

    database_store: dict[bytes, tuple[bytes, float | None]] = {}
    database_lock = threading.Lock()
    pubsub_manager = pubsub.PubSub()

    with socket.socket() as server_socket:
        address = "0.0.0.0"

        # Allow the server to reuse the port shortly after restarting
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        server_socket.bind((address, port))
        logging.info("Server listening on %s:%d", address, port)
        server_socket.listen(5)

        # Periodically unblock accept() to check for shutdown requests
        server_socket.settimeout(1.0)

        while not shutdown_event.is_set():
            try:
                client_socket, client_address = server_socket.accept()
            except socket.timeout:
                continue

            client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address, database_store, shutdown_event, database_lock, pubsub_manager), daemon=True)
            client_thread.start()


def handle_client(client_socket: socket.socket, client_address: tuple[str, int], database_store: dict[bytes, tuple[bytes, float | None]], shutdown_event: threading.Event, database_lock: threading.Lock, pubsub_manager: pubsub.PubSub) -> None:
    """
    Handle RESP commands from a connected client.

    Synchronize access to the shared database, signal server shutdown
    when EXIT is received and close the client connection on exit.
    """

    client = ClientConnection(client_socket)
    subscribed_channels: set[bytes] = set()

    try:
        with client_socket:
            logging.info("Accepted connection from client %s:%d", client_address[0], client_address[1])

            buffer = b""
            while True:
                try:
                    received_data = client_socket.recv(1024)

                    if not received_data:
                        logging.info("Client %s:%d disconnected", client_address[0], client_address[1])
                        return

                    buffer += received_data

                    if len(buffer) > MAX_BUFFER_SIZE:
                        logging.warning("Client %s:%d exceeded maximum buffer size", *client_address)
                        client.send(b"-Parsing error!\r\n")
                        return

                    # Process all complete commands before receiving more data.
                    while True:

                        try:
                            result = resp.parse_resp_command(buffer)
                        except ValueError:
                            logging.warning("Invalid RESP data from client %s:%d", *client_address)
                            client.send(b"-Parsing error!\r\n")
                            return

                        if result is None:
                            break

                        command_elements, byte_count = result
                        buffer = buffer[byte_count:]
                        command = command_elements[0].upper()

                        if subscribed_channels and command not in {
                            b"SUBSCRIBE",
                            b"UNSUBSCRIBE",
                            b"PSUBSCRIBE",
                            b"PUNSUBSCRIBE",
                            b"PING",
                            b"QUIT",
                            b"RESET"
                        }:
                            response = resp.format_resp_error("ERR Can't execute command in subscribed mode")
                        else:

                            match command:

                                case b"PING":
                                    if len(command_elements) > 2:
                                        response = resp.format_resp_error("ERR wrong number of arguments for 'ping' command")
                                    elif subscribed_channels:
                                        payload = command_elements[1] if len(command_elements) == 2 else b""
                                        response = resp.format_resp_array(b"pong", payload)
                                    elif len(command_elements) == 1:
                                        response = resp.format_resp_simple_string("PONG")
                                    else:
                                        response = resp.format_resp_bulk_string(command_elements[1])

                                case b"EXIT":
                                    logging.info("Server shutting down")
                                    shutdown_event.set()
                                    return

                                case b"ECHO":
                                    if len(command_elements) != 2:
                                        response = resp.format_resp_error("ERR wrong number of arguments for 'echo' command")
                                    else:
                                        response = resp.format_resp_bulk_string(command_elements[1])

                                case b"GET":
                                    if len(command_elements) != 2:
                                        response = resp.format_resp_error("ERR wrong number of arguments for 'get' command")
                                    else:
                                        with database_lock:
                                            value = database.handle_get(command_elements[1], database_store)

                                        response = resp.format_resp_bulk_string(value)

                                case b"SET":
                                    if len(command_elements) == 3:
                                        with database_lock:
                                            database.handle_set(command_elements[1], command_elements[2], database_store)
                                        response = resp.format_resp_simple_string("OK")
                                    elif len(command_elements) == 5:
                                        if command_elements[3].upper() != b"EX":
                                            response = resp.format_resp_error("ERR Unknown command!")
                                        else:
                                            try:
                                                with database_lock:
                                                    database.handle_set(command_elements[1], command_elements[2], database_store, command_elements[4])
                                                response = resp.format_resp_simple_string("OK")
                                            except ValueError:
                                                response = resp.format_resp_error("ERR value is not an integer or out of range")
                                    else:
                                        response = resp.format_resp_error("ERR wrong number of arguments for 'set' command")

                                case b"DEL":
                                    if len(command_elements) < 2:
                                        response = resp.format_resp_error("ERR wrong number of arguments for 'del' command")
                                    else:
                                        with database_lock:
                                            value = database.handle_del(command_elements[1:], database_store)

                                        response = resp.format_resp_integer(value)

                                case b"SUBSCRIBE":
                                    if len(command_elements) < 2:
                                        response = resp.format_resp_error("ERR wrong number of arguments for 'subscribe' command")
                                    else:
                                        response = b""

                                        for channel_name in command_elements[1:]:
                                            pubsub_manager.subscribe(channel_name, client)
                                            subscribed_channels.add(channel_name)

                                            response += resp.format_resp_array(b"subscribe", channel_name, len(subscribed_channels))

                                case b"UNSUBSCRIBE":
                                    response = b""

                                    if len(command_elements) == 1:
                                        channel_names = list(subscribed_channels)
                                    else:
                                        channel_names = command_elements[1:]

                                    if not channel_names:
                                        response = resp.format_resp_array(b"unsubscribe", None, 0)
                                    else:
                                        for channel_name in channel_names:
                                            pubsub_manager.unsubscribe(channel_name, client)
                                            subscribed_channels.discard(channel_name)

                                            response += resp.format_resp_array(b"unsubscribe", channel_name, len(subscribed_channels))

                                case b"PUBLISH":
                                    if len(command_elements) != 3:
                                        response = resp.format_resp_error("ERR wrong number of arguments for 'publish' command")
                                    else:
                                        channel_name = command_elements[1]
                                        message = command_elements[2]

                                        subscribers = pubsub_manager.get_subscribers(channel_name)

                                        logging.debug("Publishing to channel %r (%d subscribers)",channel_name,len(subscribers))

                                        notification = resp.format_resp_array(b"message", channel_name, message)
                                        for subscriber in subscribers:
                                            try:
                                                subscriber.send(notification)
                                            except OSError as e:
                                                logging.warning("Failed to deliver message to channel %r: %s", channel_name, e)
                                                pubsub_manager.unsubscribe(channel_name, subscriber)

                                        response = resp.format_resp_integer(len(subscribers))

                                case _:
                                    response = resp.format_resp_error("ERR Unknown command!")

                            client.send(response)

                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
                    logging.warning("Client connection lost: %s", e)
                    break

    finally:
        for channel_name in subscribed_channels:
            pubsub_manager.unsubscribe(channel_name, client)