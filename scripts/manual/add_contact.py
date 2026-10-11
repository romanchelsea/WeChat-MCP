"""Manual smoke script: drives the real WeChat app. Not an automated test."""

from __future__ import annotations

from wechat_mcp.logging_config import configure_logging
from wechat_mcp.mcp_server import add_contact_by_wechat_id


def main() -> None:
    configure_logging()
    print(add_contact_by_wechat_id("wew123"))


if __name__ == "__main__":
    main()
