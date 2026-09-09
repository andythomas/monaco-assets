"""Tests for monaco_assets.get_path."""

import tarfile
from pathlib import Path

import pytest

import monaco_assets


def _write_fake_tgz(tgz_path: Path, files: dict[str, bytes]) -> None:
    """Write a .tgz archive at tgz_path containing the given files."""
    src_dir = tgz_path.parent / "_src"
    src_dir.mkdir(exist_ok=True)
    for rel_path, content in files.items():
        full_path = src_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)

    with tarfile.open(tgz_path, "w:gz") as tar:
        for rel_path in files:
            tar.add(src_dir / rel_path, arcname=rel_path)


def test_get_path_returns_cached_assets_without_downloading(
    isolated_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If assets exist in the cache, get_path must not re-download."""
    package_dir = isolated_cache_dir / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "loader.js").write_text("cached")

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("_download_file should not be called when cache is warm")

    monkeypatch.setattr(monaco_assets, "_download_file", _fail_if_called)

    result = monaco_assets.get_path()

    assert result == package_dir
    assert (result / "loader.js").read_text() == "cached"


def test_get_path_downloads_and_extracts_when_cache_empty(
    isolated_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the cache is cold, get_path downloads and extracts."""

    def _fake_download(_url: str, filename: Path, **_kwargs) -> None:
        _write_fake_tgz(filename, {"package/loader.js": b"console.log('loader');"})

    monkeypatch.setattr(monaco_assets, "_download_file", _fake_download)
    monkeypatch.setattr(monaco_assets, "_verify_file_hash", lambda *_args, **_kwargs: True)

    result = monaco_assets.get_path()

    assert result == isolated_cache_dir / "package"
    assert (result / "loader.js").read_bytes() == b"console.log('loader');"
    # the downloaded archive should be cleaned up after extraction
    assert not any(isolated_cache_dir.glob("*.tgz"))


def test_get_path_raises_and_cleans_up_on_hash_mismatch(
    isolated_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed hash verification raises and cleans up the cache dir."""

    def _fake_download(_url: str, filename: Path, **_kwargs) -> None:
        _write_fake_tgz(filename, {"package/loader.js": b"console.log('loader');"})

    monkeypatch.setattr(monaco_assets, "_download_file", _fake_download)
    monkeypatch.setattr(monaco_assets, "_verify_file_hash", lambda *_args, **_kwargs: False)

    with pytest.raises(RuntimeError, match="Failed to download Monaco Editor assets"):
        monaco_assets.get_path()

    assert not isolated_cache_dir.exists()


def test_get_path_raises_and_cleans_up_on_download_failure(
    isolated_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A download failure raises and cleans up the cache dir."""

    def _fake_download(_url: str, _filename: Path, **_kwargs) -> None:
        raise OSError("network unreachable")

    monkeypatch.setattr(monaco_assets, "_download_file", _fake_download)

    with pytest.raises(RuntimeError, match="Failed to download Monaco Editor assets"):
        monaco_assets.get_path()

    assert not isolated_cache_dir.exists()


def test_get_path_treats_empty_package_dir_as_cache_miss(
    isolated_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An existing but empty package dir is treated as a cold cache."""
    package_dir = isolated_cache_dir / "package"
    package_dir.mkdir(parents=True)

    def _fake_download(_url: str, filename: Path, **_kwargs) -> None:
        _write_fake_tgz(filename, {"package/loader.js": b"console.log('loader');"})

    monkeypatch.setattr(monaco_assets, "_download_file", _fake_download)
    monkeypatch.setattr(monaco_assets, "_verify_file_hash", lambda *_args, **_kwargs: True)

    result = monaco_assets.get_path()

    assert (result / "loader.js").exists()
