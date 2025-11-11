"""
Provide Monaco editor assets.

Download Monaco editor assets at first use. The assets are downloaded,
extracted, and made available in a platform specific cache folder. To
access the assets, a webserver based on fastapi and uvicorn is provided.
"""

import hashlib
import inspect
import logging
import shutil
import ssl
import tarfile
import threading
import urllib.request
from pathlib import Path

import certifi
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from platformdirs import user_cache_dir

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
        """
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
