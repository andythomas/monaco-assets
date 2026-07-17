"""Shared pytest fixtures for the monaco_assets test suite."""

import socket
from pathlib import Path

import pytest

import monaco_assets


@pytest.fixture
def isolated_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point monaco_assets.CACHE_DIR at a throwaway directory."""
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(monaco_assets, "CACHE_DIR", cache_dir)
    return cache_dir


@pytest.fixture
def free_port() -> int:
    """Return a TCP port on localhost that is currently free."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
