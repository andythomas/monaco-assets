"""
Provide Monaco editor assets.

Download Monaco editor assets at first use. The assets are downloaded,
extracted, and made available in a platform specific cache folder. To
access the assets,a simple webserver can be used.
"""

import hashlib
import http.server
import inspect
import logging
import shutil
import socketserver
import ssl
import tarfile
import threading
import urllib.request
from functools import partial
from pathlib import Path

import certifi
from platformdirs import user_cache_dir

VERSION = "0.54.0"
EXPECTED_SHA1 = "c0d6ebb46b83f1bef6f67f6aa471e38ba7ef8231"

CACHE_DIR = Path(user_cache_dir("monaco-assets", "monaco-assets")) / f"monaco-editor-{VERSION}"

logger = logging.getLogger(f"{__name__}")
logger.debug("using monaco-editor-%s", VERSION)
logger.debug("using Monaco from directory %s", CACHE_DIR)


class _MonacoRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP request handler that uses logging."""

    def __init__(self, *args, logger=None, **kwargs):
        """Init with optional logger."""
        self.logger = logger
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):  # noqa: A002
        """Override log_message to use logger.debug."""
        if self.logger:
            self.logger.debug(format, *args)
        else:
            super().log_message(format, *args)


class MonacoServer:
    """HTTP server to serve Monaco editor assets."""

    def __init__(self, port: int = 8000):
        """
        Initialize and start Monaco Editor assets server.

        Download assets if needed and start a local HTTP server in a
        background thread. The assets will be available at:
        http://localhost:<port>

        Parameters
        ----------
        port : int
            Port number for the HTTP server (default: 8000)
        """
        self.logger = logging.getLogger(f"{__name__}.MonacoServer")
        self._port: int = port
        self._httpd: socketserver.TCPServer | None = None
        self._server_error: Exception | None = None
        self._thread: threading.Thread | None = threading.Thread(
            target=self._run_server, daemon=True
        )
        self.logger.info("starting Monaco webserver.")
        self._thread.start()

    def _run_server(self):
        """Run the HTTP server in a background thread."""
        try:
            handler = partial(_MonacoRequestHandler, directory=get_path(), logger=self.logger)
            self._httpd = socketserver.TCPServer(
                ("127.0.0.1", self._port), handler, bind_and_activate=False
            )
            self._httpd.allow_reuse_address = True
            self._httpd.server_bind()
            self._httpd.server_activate()
            self._httpd.serve_forever()
        except Exception as e:
            self._server_error = e
            self.logger.error("Monaco webserver failed to start on port %s: %s", self._port, e)
            self._httpd = None

    def stop(self) -> bool:
        """
        Stop the Monaco editor assets server.

        Returns
        -------
        bool
            True if server was stopped, False if no server was running.
        """
        self.logger.info("stopping Monaco webserver.")
        if self._httpd is None:
            self.logger.warning("no Monaco webserver was running!")
            return False
        self.logger.debug("shutting down Monaco webserver.")
        shutdown_thread = threading.Thread(target=self._httpd.shutdown)
        shutdown_thread.daemon = True
        shutdown_thread.start()
        shutdown_thread.join(timeout=2.0)
        if shutdown_thread.is_alive():
            self.logger.warning("Monaco webserver shutdown timed out (common on windows)!")
        self.logger.debug("closing Monaco webserver.")
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None
        self._httpd = None
        self.logger.info("Monaco webserver stopped.")
        return True

    def is_running(self) -> bool:
        """
        Check if the Monaco Editor assets server is currently running.

        Returns
        -------
        bool
            True if server is running, False otherwise
        """
        return (
            self._thread is not None
            and self._thread.is_alive()
            and self._httpd is not None
            and self._server_error is None
        )

    def get_server_error(self) -> Exception | None:
        """
        Get the last server error (if one occured).

        Returns
        -------
        Exception | None
            The last exception during server startup or None.
        """
        return self._server_error


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
    logger.debug("downloading %s from %s", filename, url)
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


def get_path() -> Path:
    """
    Download Monaco Editor assets if they do not exist.

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
        _download_file(url, tgz_file)
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
