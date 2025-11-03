"""
Provide Monaco editor assets.

Download Monaco editor assets at first use. The assets are downloaded,
extracted, and made available in a platform specific cache folder.
"""

import hashlib
import inspect
import shutil
import ssl
import tarfile
import urllib.request
from pathlib import Path

import certifi
from platformdirs import user_cache_dir

VERSION = "0.54.0"
EXPECTED_SHA1 = "c0d6ebb46b83f1bef6f67f6aa471e38ba7ef8231"

CACHE_DIR = Path(user_cache_dir("monaco-assets", "monaco-assets"))


def _download_file(url: str, filename: Path) -> None:
    """
    Download a file from a URL to the destination path.

    Parameters
    ----------
    url : str
        The URL.
    filename : Path
        The filename of the received file.

    """
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(url, context=context) as response:
        with open(filename, "wb") as out_file:
            shutil.copyfileobj(response, out_file)  # type: ignore


def _verify_file_hash(filename: Path, expected_sha1: str) -> bool:
    """
    Verify the SHA1 hash of a file.

    Parameters
    ----------
    filename : Path
        The file to verify.
    expected_sha1 : str
        The expected SHA1 hash.

    Returns
    -------
    bool
        True if hash matches, False otherwise.
    """
    sha1_hash = hashlib.sha1()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha1_hash.update(chunk)
    actual_sha1 = sha1_hash.hexdigest()
    return actual_sha1 == expected_sha1


def _extract_tgz(tgz: Path) -> None:
    """
    Extract a .tgz file to the same directory.

    Parameters
    ----------
    tgz: Path
        The tar.gz file.
    """
    dest = tgz.parent
    with tarfile.open(tgz, "r:gz") as tar:
        # delete the if clause for Python>=3.12
        supports_filter = "filter" in inspect.signature(tar.extract).parameters
        for member in tar.getmembers():
            if supports_filter:
                tar.extract(member, dest, filter="data")
            else:
                tar.extract(member, dest)


def get_path() -> Path:
    """
    Download Monaco Editor assets if they do not exist.

    Returns
    -------
    Path
        The path to the assests.
    """
    assets_dir = CACHE_DIR / f"monaco-editor-{VERSION}"
    package_dir = assets_dir / "package"

    if package_dir.exists() and any(package_dir.iterdir()):
        return package_dir
    try:
        assets_dir.mkdir(parents=True, exist_ok=True)
        package = "monaco-editor"
        tgz = f"{package}-{VERSION}.tgz"
        url = f"https://registry.npmjs.org/{package}/-/{tgz}"
        tgz_file = assets_dir / tgz
        _download_file(url, tgz_file)
        if not _verify_file_hash(tgz_file, EXPECTED_SHA1):
            raise ValueError(f"Hash verification failed for {tgz_file}")
        _extract_tgz(tgz_file)
        tgz_file.unlink()
        return package_dir
    except Exception as e:
        if assets_dir.exists():
            shutil.rmtree(assets_dir, ignore_errors=True)
        raise RuntimeError(f"Failed to download Monaco Editor assets: {e}") from e


def clear_cache() -> None:
    """Clear Monaco Editor asset cache."""
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
