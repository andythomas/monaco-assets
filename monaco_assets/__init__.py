"""
Provide Monaco editor assets.

Download Monaco editor assets at first use. The assets are downloaded,
extracted, and made available in a platform specific cache folder. To
access the assets via HTTP, an optional webserver based on fastapi and
uvicorn is provided (install the ``server`` extra).
"""

import hashlib
import inspect
import logging
import shutil
import ssl
import tarfile
import threading
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import certifi
from platformdirs import user_cache_dir

if TYPE_CHECKING:
    import uvicorn

VERSION = "0.54.0"
EXPECTED_SHA1 = "c0d6ebb46b83f1bef6f67f6aa471e38ba7ef8231"

CACHE_DIR = Path(user_cache_dir("monaco-assets", "monaco-assets")) / f"monaco-editor-{VERSION}"

logger = logging.getLogger(f"{__name__}")
logger.debug("using monaco-editor-%s", VERSION)
logger.debug("using Monaco from directory %s", CACHE_DIR)


class UvicornToMonacoHandler(logging.Handler):
    """Capture uvicorn logs and pipe them to MonacoServer logger."""

    def __init__(self, monaco_logger: logging.Logger):
        super().__init__()
        self.monaco_logger = monaco_logger

    def emit(self, record: logging.LogRecord) -> None:
        """Log all uvicorn messages as debug level."""
        msg = f"[uvicorn] {record.getMessage()}"
        self.monaco_logger.debug(msg)


def _server_dependencies():
    """Import the optional server dependencies (fastapi and uvicorn)."""
    try:
        import uvicorn
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:
        raise ImportError(
            "MonacoServer requires the optional server dependencies. "
            "Install them with 'pip install monaco-assets[server]' (or "
            "'uv pip install monaco-assets[server]')."
        ) from exc
    return FastAPI, StaticFiles, uvicorn


class MonacoServer:
    """HTTP server to serve Monaco editor assets."""

    def __init__(self, port: int = 8000):
        """
        Initialize and start Monaco Editor assets server.

        Start a local HTTP server in a background thread. The assets
        will be available at: http://localhost:<port>/pathtofile. The
        internal server logs are only visible if the logging level is
        set to DEBUG level to avoid log chatter.

        Parameters
        ----------
        port : int
            Port number for the HTTP server (default: 8000)

        Raises
        ------
        ImportError
            If the optional server dependencies are not installed.
        """
        _server_dependencies()  # Fail fast if the extras are missing.
        self.logger = logging.getLogger(f"{__name__}.MonacoServer")
        self._port: int = port
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = threading.Thread(
            target=self._run_server, daemon=True
        )
        self.logger.info("starting Monaco webserver.")
        self._thread.start()

    def _run_server(self):
        """Run the server and download assets if not cached."""
        FastAPI, StaticFiles, uvicorn = _server_dependencies()
        try:
            app = FastAPI()
            assets_path = get_path()
            app.mount("/", StaticFiles(directory=str(assets_path)), name="static")

            log_config = {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "default": {
                        "format": "%(levelprefix)s %(message)s",
                    },
                },
                "handlers": {
                    "monaco_handler": {
                        "()": UvicornToMonacoHandler,
                        "monaco_logger": self.logger,
                    },
                },
                "loggers": {
                    "uvicorn": {
                        "handlers": ["monaco_handler"],
                        "level": "DEBUG",
                        "propagate": False,
                    },
                    "uvicorn.error": {
                        "handlers": ["monaco_handler"],
                        "level": "DEBUG",
                        "propagate": False,
                    },
                    "uvicorn.access": {
                        "handlers": ["monaco_handler"],
                        "level": "DEBUG",
                        "propagate": False,
                    },
                },
            }

            config = uvicorn.Config(
                app=app,
                host="127.0.0.1",
                port=self._port,
                log_config=log_config,
                access_log=True,
            )
            self._server = uvicorn.Server(config)
            self._server.run()
        except Exception as e:
            self.logger.error("Monaco webserver failed to start on port %s: %s", self._port, e)
            self._server = None

    def stop(self) -> None:
        """Stop the Monaco editor assets server."""
        self.logger.info("stopping Monaco webserver.")
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None
        self._server = None
        self.logger.info("Monaco webserver stopped.")

    def is_running(self) -> bool:
        """Check if the server is currently running."""
        return (
            self._server is not None
            and self._thread is not None
            and self._thread.is_alive()
            and not getattr(self._server, "should_exit", True)
        )


def _download_file(
    url: str,
    filename: Path,
    progress_callback: Callable[[int, int | None], None] | None = None,
) -> None:
    """
    Download a file from a URL to the destination path.

    Parameters
    ----------
    url : str
        The URL.
    filename : Path
        The filename of the received file.
    progress_callback : callable or None, optional
        Called during the download with
        ``(bytes_downloaded, total_bytes)``. ``total_bytes``
        is ``None`` if the server did not send a
        ``Content-Length`` header. The first chunk is always
        reported; further invocations are throttled to at most
        one per 0.5 seconds, plus a final call when the last
        expected byte has been received.

    """
    logger.debug("downloading %s from %s", filename, url)
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(url, context=context) as response:
        content_length = response.headers.get("Content-Length")
        total = int(content_length) if content_length else None
        downloaded = 0
        last_report: float | None = None
        with open(filename, "wb") as out_file:
            while chunk := response.read(64 * 1024):  # 64 KiB chunks
                out_file.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if progress_callback is not None and (
                    last_report is None or now - last_report >= 0.5 or downloaded == total
                ):
                    last_report = now
                    progress_callback(downloaded, total)
                logger.debug(
                    "downloaded %d of %s bytes", downloaded, total if total is not None else "?"
                )


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
    logger.debug("compare hash to be %s for %s", expected_sha1, filename)
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
    logger.debug("extracting %s", tgz)
    dest = tgz.parent
    with tarfile.open(tgz, "r:gz") as tar:
        # delete the if clause for Python>=3.12
        supports_filter = "filter" in inspect.signature(tar.extract).parameters
        for member in tar.getmembers():
            if supports_filter:
                tar.extract(member, dest, filter="data")
            else:
                tar.extract(member, dest)


def get_path(
    progress_callback: Callable[[int, int | None], None] | None = None,
) -> Path:
    """
    Download Monaco Editor assets if they do not exist.

    Parameters
    ----------
    progress_callback : callable or None, optional
        Forwarded to the download step; called with
        ``(bytes_downloaded, total_bytes)`` while the assets are being
        downloaded. Only invoked if a download actually takes place
        (i.e. the assets are not already cached).

    Returns
    -------
    Path
        The path to the assests.
    """
    package_dir = CACHE_DIR / "package"

    if package_dir.exists() and any(package_dir.iterdir()):
        return package_dir
    try:
        logger.info("no existing Monaco assets found, caching assets.")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        package = "monaco-editor"
        tgz = f"{package}-{VERSION}.tgz"
        url = f"https://registry.npmjs.org/{package}/-/{tgz}"
        tgz_file = CACHE_DIR / tgz
        _download_file(url, tgz_file, progress_callback=progress_callback)
        if not _verify_file_hash(tgz_file, EXPECTED_SHA1):
            raise ValueError(f"Hash verification failed for {tgz_file}")
        _extract_tgz(tgz_file)
        tgz_file.unlink()
        return package_dir
    except Exception as e:
        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR, ignore_errors=True)
        raise RuntimeError(f"Failed to download Monaco Editor assets: {e}") from e


def clear_cache() -> None:
    """Clear Monaco Editor asset cache."""
    if CACHE_DIR.exists():
        logger.debug("deleting Monaco assets in %s.", CACHE_DIR)
        shutil.rmtree(CACHE_DIR)
