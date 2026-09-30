"""Keep the offline test suite offline.

The tests either mock the provider HTTP layer or use fixtures, so no real socket
should ever open. This guard turns an accidental network call into a clear
failure instead of a slow, flaky test.
"""
import socket

import pytest


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise RuntimeError('Network access is disabled during the test suite.')

    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket.socket, 'connect_ex', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)
