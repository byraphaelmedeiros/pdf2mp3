"""Windows event loops need a local TCP socketpair, never outbound networking."""

import asyncio
import socket

import pytest
import pytest_socket

from scripts.network_guard import local_socketpair


def test_local_socketpair_supports_event_loop_without_opening_network(monkeypatch):
    monkeypatch.setattr(socket, "socketpair", local_socketpair)

    async def run():
        await asyncio.sleep(0)
        return "awake"

    assert asyncio.run(run()) == "awake"
    with pytest.raises(pytest_socket.SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def test_pair_is_connected_and_local():
    reader, writer = local_socketpair()
    try:
        assert reader.getpeername()[0] == writer.getpeername()[0] == "127.0.0.1"
        writer.sendall(b"synthetic")
        assert reader.recv(9) == b"synthetic"
    finally:
        reader.close()
        writer.close()


def test_installed_guard_preserves_windows_event_loop_and_denies_network(monkeypatch):
    import sys

    from scripts.network_guard import block_network

    native_platform = sys.platform
    with monkeypatch.context() as temporary:
        for name in ["socket", "socketpair", "create_connection", "getaddrinfo"]:
            temporary.setattr(socket, name, getattr(socket, name))
        temporary.setattr(sys, "platform", "win32")
        block_network()
        temporary.setattr(sys, "platform", native_platform)

        async def run():
            await asyncio.sleep(0)
            return "awake"

        assert asyncio.run(run()) == "awake"
        for operation in [
            lambda: socket.socket(socket.AF_INET),
            lambda: socket.create_connection(("192.0.2.1", 443)),
            lambda: socket.getaddrinfo("example.invalid", 443),
        ]:
            with pytest.raises(RuntimeError, match="Network"):
                operation()
