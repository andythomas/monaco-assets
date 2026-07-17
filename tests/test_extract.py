"""Tests for monaco_assets._extract_tgz."""

import tarfile
from pathlib import Path

import monaco_assets


def _make_tgz(tgz_path: Path, files: dict[str, bytes]) -> None:
    """Create a .tgz archive at tgz_path containing the given files."""
    src_dir = tgz_path.parent / "_src"
    src_dir.mkdir(exist_ok=True)
    for rel_path, content in files.items():
        full_path = src_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)

    with tarfile.open(tgz_path, "w:gz") as tar:
        for rel_path in files:
            tar.add(src_dir / rel_path, arcname=rel_path)


def test_extract_tgz_creates_files(tmp_path: Path) -> None:
    """Extracting a .tgz recreates its files under the archive dir."""
    tgz_path = tmp_path / "package-1.0.0.tgz"
    _make_tgz(
        tgz_path,
        {
            "package/loader.js": b"console.log('loader');",
            "package/min/vs/editor.js": b"console.log('editor');",
        },
    )

    monaco_assets._extract_tgz(tgz_path)

    loader = tmp_path / "package" / "loader.js"
    editor = tmp_path / "package" / "min" / "vs" / "editor.js"
    assert loader.read_bytes() == b"console.log('loader');"
    assert editor.read_bytes() == b"console.log('editor');"


def test_extract_tgz_preserves_directory_structure(tmp_path: Path) -> None:
    """Nested directories in the archive are preserved on extraction."""
    tgz_path = tmp_path / "package-1.0.0.tgz"
    _make_tgz(
        tgz_path,
        {
            "package/a/b/c/deep.txt": b"deep",
        },
    )

    monaco_assets._extract_tgz(tgz_path)

    deep_file = tmp_path / "package" / "a" / "b" / "c" / "deep.txt"
    assert deep_file.exists()
    assert deep_file.read_bytes() == b"deep"
