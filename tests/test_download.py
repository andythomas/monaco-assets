"""Tests for monaco_assets._download_file progress reporting."""

from pathlib import Path

import pytest

import monaco_assets


class _FakeResponse:
    """Minimal stand-in for the object returned by urlopen."""

    def __init__(self, payload: bytes, content_length: str | None) -> None:
        self._payload = payload
        self._headers = {"Content-Length": content_length} if content_length else {}
        self._pos = 0

    @property
    def headers(self) -> dict[str, str]:
        return self._headers

    def read(self, size: int | None = None) -> bytes:
        chunk = self._payload[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _install_fake_response(monkeypatch: pytest.MonkeyPatch, response: _FakeResponse) -> None:
    """Make urllib.request.urlopen return the given fake response."""

    def _fake_urlopen(_url: str, context: object) -> _FakeResponse:
        return response

    monkeypatch.setattr(monaco_assets.urllib.request, "urlopen", _fake_urlopen)


def test_download_invokes_progress_callback_with_totals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Callback receives monotonic progress and a final call at 100%."""
    payload = b"x" * 200_000  # larger than the 64 KiB chunk size
    _install_fake_response(monkeypatch, _FakeResponse(payload, str(len(payload))))

    calls: list[tuple[int, int | None]] = []
    monaco_assets._download_file(
        "https://example.org/file.tgz",
        tmp_path / "file.tgz",
        progress_callback=lambda done, total: calls.append((done, total)),
    )

    assert (tmp_path / "file.tgz").read_bytes() == payload
    assert calls, "progress callback was never invoked"
    # progress must be monotonic and never exceed the total
    assert all(done <= len(payload) for done, _ in calls)
    assert all(a <= b for a, b in zip(calls, calls[1:], strict=False))
    # the total must come from Content-Length
    assert all(total == len(payload) for _, total in calls)
    # the final call must report full completion
    assert calls[-1] == (len(payload), len(payload))


def test_download_progress_callback_reports_none_total_without_content_length(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If Content-Length is missing, total_bytes is reported as None."""
    payload = b"y" * 10_000
    _install_fake_response(monkeypatch, _FakeResponse(payload, None))

    calls: list[tuple[int, int | None]] = []
    monaco_assets._download_file(
        "https://example.org/file.tgz",
        tmp_path / "file.tgz",
        progress_callback=lambda done, total: calls.append((done, total)),
    )

    assert (tmp_path / "file.tgz").read_bytes() == payload
    assert calls, "progress callback was never invoked"
    assert all(total is None for _, total in calls)
    assert calls[-1][0] == len(payload)


def test_download_without_progress_callback_still_downloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default (no callback) keeps working and writes the file."""
    payload = b"z" * 100_000
    _install_fake_response(monkeypatch, _FakeResponse(payload, str(len(payload))))

    monaco_assets._download_file("https://example.org/file.tgz", tmp_path / "file.tgz")

    assert (tmp_path / "file.tgz").read_bytes() == payload
