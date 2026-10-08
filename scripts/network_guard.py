"""Test-only socket guard with a narrowly controlled Windows wakeup socketpair."""

import socket
import sys

# Capture before pytest or the installed smoke applies its global network guard.
_SOCKET = socket.socket


def local_socketpair(family=None, type=socket.SOCK_STREAM, proto=0):
    """Create only connected IPv4 loopback peers for asyncio's internal wakeup."""
    if family not in (None, socket.AF_INET) or type != socket.SOCK_STREAM or proto != 0:
        raise ValueError("The test wakeup pair only supports local TCP streams")
    client = _SOCKET(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with _SOCKET(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.settimeout(2)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            client.settimeout(2)
            client.connect(listener.getsockname())
            # socket.accept() wraps via the now-guarded global constructor.
            # CPython's raw accept lets us wrap this known local descriptor only.
            descriptor, _ = listener._accept()
            try:
                server = _SOCKET(socket.AF_INET, socket.SOCK_STREAM, fileno=descriptor)
            except BaseException:
                socket.close(descriptor)
                raise
        client.settimeout(None)
        server.settimeout(None)
        return server, client
    except BaseException:
        client.close()
        raise


def block_network():
    """Deny network socket creation and DNS in an installed test subprocess."""

    def denied(*args, **kwargs):
        raise RuntimeError("Network is forbidden in installed smoke tests")

    class OfflineSocket(_SOCKET):
        def __init__(self, family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0, fileno=None):
            if family != getattr(socket, "AF_UNIX", None):
                denied()
            super().__init__(family, type, proto, fileno)

    socket.socket = OfflineSocket
    socket.create_connection = denied
    socket.getaddrinfo = denied
    if sys.platform == "win32":
        socket.socketpair = local_socketpair
