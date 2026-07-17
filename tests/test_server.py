"""Integration tests for monaco_assets.MonacoServer."""

import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import monaco_assets


def _wait_until(predicate, timeout: float = 5.0, interval: float = 0.05) -> bool:
    """Poll predicate() until it returns truthy or timeout elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _get(url: str, timeout: float = 0.5) -> bytes | None:
    """Return the response body for url, or None on failure."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.read()
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return None


@pytest.fixture
def static_assets_dir(tmp_path: Path) -> Path:
    """Create a directory with a known file, as fake Monaco assets."""
    (tmp_path / "hello.txt").write_text("hello monaco")
    return tmp_path


def test_server_serves_assets_and_stops_cleanly(
    static_assets_dir: Path, free_port: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MonacoServer serves get_path() files and shuts down on stop()."""
    monkeypatch.setattr(monaco_assets, "get_path", lambda: static_assets_dir)

    server = monaco_assets.MonacoServer(port=free_port)
    try:
        url = f"http://127.0.0.1:{free_port}/hello.txt"
        assert _wait_until(lambda: _get(url) == b"hello monaco"), (
            "server never started serving the expected file"
        )
        assert server.is_running() is True
    finally:
        server.stop()

    assert server.is_running() is False
    assert _wait_until(lambda: _get(url) is None), "server kept accepting connections after stop"


def test_server_is_running_false_when_asset_dir_missing(
    tmp_path: Path, free_port: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MonacoServer surfaces startup failure via is_running()."""
    missing_dir = tmp_path / "does-not-exist"
    monkeypatch.setattr(monaco_assets, "get_path", lambda: missing_dir)

    server = monaco_assets.MonacoServer(port=free_port)

    assert _wait_until(lambda: server.is_running() is False), (
        "server should stop trying to run once the asset directory mount fails"
    )
