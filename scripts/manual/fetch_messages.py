"""Manual smoke script: drives the real WeChat app. Not an automated test."""

from __future__ import annotations

from wechat_mcp.logging_config import configure_logging
from wechat_mcp.mcp_server import fetch_messages_by_chat


def main() -> None:
    configure_logging()
    print(fetch_messages_by_chat("家", last_n=30))


if __name__ == "__main__":
    main()
