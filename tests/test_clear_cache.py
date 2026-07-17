"""Tests for monaco_assets.clear_cache."""

from pathlib import Path

import monaco_assets


def test_clear_cache_removes_existing_dir(isolated_cache_dir: Path) -> None:
    """clear_cache deletes the cache directory when it exists."""
    package_dir = isolated_cache_dir / "package"
    package_dir.mkdir(parents=True)
    (package_dir / "loader.js").write_text("cached")

    monaco_assets.clear_cache()

    assert not isolated_cache_dir.exists()


def test_clear_cache_is_a_noop_when_missing(isolated_cache_dir: Path) -> None:
    """clear_cache does not raise when the cache dir is missing."""
    assert not isolated_cache_dir.exists()

    monaco_assets.clear_cache()  # should not raise

    assert not isolated_cache_dir.exists()
