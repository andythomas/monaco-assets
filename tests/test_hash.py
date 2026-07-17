"""Tests for monaco_assets._verify_file_hash."""

import hashlib
from pathlib import Path

import monaco_assets


def test_verify_file_hash_matches(tmp_path: Path) -> None:
    """Return True when the file's SHA1 matches the expected hash."""
    file_path = tmp_path / "data.bin"
    file_path.write_bytes(b"hello monaco")
    expected = hashlib.sha1(b"hello monaco").hexdigest()

    assert monaco_assets._verify_file_hash(file_path, expected) is True


def test_verify_file_hash_mismatch(tmp_path: Path) -> None:
    """Return False when the file's SHA1 does not match."""
    file_path = tmp_path / "data.bin"
    file_path.write_bytes(b"hello monaco")

    assert monaco_assets._verify_file_hash(file_path, "0" * 40) is False


def test_verify_file_hash_large_file(tmp_path: Path) -> None:
    """Hash verification works across multiple 4096-byte read chunks."""
    file_path = tmp_path / "large.bin"
    content = b"x" * 10_000
    file_path.write_bytes(content)
    expected = hashlib.sha1(content).hexdigest()

    assert monaco_assets._verify_file_hash(file_path, expected) is True
