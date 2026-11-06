"""All automated tests are offline; live probes are separate manual scripts."""
import socket
import os

import pytest


@pytest.fixture(autouse=True)
def deny_network_connections(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('Network connections are prohibited in automated tests')

    monkeypatch.setattr(socket, 'create_connection', blocked)
    original_connect = socket.socket.connect
    def allow_windows_socketpair(sock, address):
        if os.name == 'nt' and isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):
            return original_connect(sock, address)
        return blocked(sock, address)
    monkeypatch.setattr(socket.socket, 'connect', allow_windows_socketpair)
    monkeypatch.setattr(socket.socket, 'connect_ex', blocked)
