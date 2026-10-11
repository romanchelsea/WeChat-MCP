"""
Logging setup for the WeChat MCP server.

Modules log through `logging.getLogger(__name__)` and never configure
handlers themselves; only the entry point calls `configure_logging()`, so
importing the package has no side effects.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# macOS convention for per-user app logs; also browsable in Console.app.
DEFAULT_LOG_DIR = Path.home() / "Library" / "Logs" / "wechat-mcp"
LOG_FILE_NAME = "wechat_mcp.log"
MAX_LOG_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
_DEBUG_FORMAT = (
    "%(asctime)s [%(levelname)s] %(name)s %(funcName)s:%(lineno)d - %(message)s"
)

logger = logging.getLogger(__name__)


def get_log_dir() -> Path:
    """
    Return the log directory: $WECHAT_MCP_LOG_DIR if set, otherwise
    ~/Library/Logs/wechat-mcp.
    """
    return Path(os.getenv("WECHAT_MCP_LOG_DIR") or DEFAULT_LOG_DIR).expanduser()


def configure_logging(debug: bool = False) -> None:
    """
    Send log records to stderr and to a rotating file.

    stdout is left alone because the stdio transport uses it for MCP
    protocol messages. Any existing root handlers are replaced: the MCP
    SDK installs its own when MCPServer is created, which would otherwise
    print every record twice.

    `debug` lowers the console level to DEBUG, adds function/line info to
    the format, and turns on DEBUG logging for the MCP SDK, anyio and
    httpx.
    """
    formatter = logging.Formatter(_DEBUG_FORMAT if debug else _FORMAT)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(formatter)
    handlers: list[logging.Handler] = [console_handler]

    log_file = get_log_dir() / LOG_FILE_NAME
    file_error: OSError | None = None
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError as exc:
        # A read-only or unexpected working directory must not stop the
        # server from starting; fall back to stderr only.
        file_error = exc
    else:
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        handlers=handlers,
        force=True,
    )
    # Our own DEBUG records always reach the file handler.
    logging.getLogger("wechat_mcp").setLevel(logging.DEBUG)
    if debug:
        for name in ("mcp", "anyio", "httpx"):
            logging.getLogger(name).setLevel(logging.DEBUG)

    if file_error is None:
        logger.info("Logging to %s", log_file)
    else:
        logger.warning(
            "Could not open log file %s (%s); logging to stderr only",
            log_file,
            file_error,
        )
