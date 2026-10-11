from __future__ import annotations

import argparse
import logging
from typing import Any

from mcp.server.mcpserver import MCPServer

from .contacts import add_contact_by_wechat_id as ax_add_contact_by_wechat_id
from .logging_config import configure_logging
from .messages import ChatMessage, fetch_recent_messages, send_message
from .moments import publish_moment_without_media as ax_publish_moment
from .navigation import ensure_chat_open

logger = logging.getLogger(__name__)

mcp = MCPServer("WeChat Helper MCP Server")


@mcp.tool()
def fetch_messages_by_chat(
    chat_name: str,
    last_n: int = 50,
) -> list[dict[str, Any]]:
    """
    Fetch recent messages for a specific chat (contact or group).

    This will:
    - Look for the chat in the left sidebar session list
    - If found, click it to open the chat
    - If not found, search for the chat via the search box
    - Once the chat is open, retrieve recent messages from that chat
    """
    try:
        logger.info("Tool fetch_messages_by_chat called for chat=%s", chat_name)
        not_found = ensure_chat_open(chat_name)
        if not_found is not None:
            # No exact match; surface candidates instead of forcing a chat.
            logger.info(
                "open_chat_for_contact returned candidates for chat=%s; "
                "skipping message fetch",
                chat_name,
            )
            enriched = dict(not_found)
            enriched.setdefault("tool", "fetch_messages_by_chat")
            return [enriched]

        messages: list[ChatMessage] = fetch_recent_messages(last_n=last_n)
        result = [msg.to_dict() for msg in messages]
        logger.info("Returning %d messages for chat=%s", len(result), chat_name)
        return result
    except Exception as exc:
        logger.exception(
            "Error in fetch_messages_by_chat for chat=%s: %s",
            chat_name,
            exc,
        )
        return [
            {
                "error": str(exc),
                "chat_name": chat_name,
            }
        ]


@mcp.tool()
def reply_to_messages_by_chat(
    chat_name: str,
    reply_message: str | None = None,
) -> dict[str, Any]:
    """
    Optionally send a reply to a chat (contact or group).

    This tool is designed to be driven by the LLM using this MCP:
    - Call fetch_messages_by_chat first to inspect conversation history.
    - Have the LLM compose a reply string.
    - Call this tool with that reply string to send it.

    If reply_message is None or empty, no message is sent; the tool still
    ensures the chat is open.
    """
    logger.info(
        "Tool reply_to_messages_by_chat called for chat=%s (has_reply=%s)",
        chat_name,
        bool(reply_message),
    )
    try:
        not_found = ensure_chat_open(chat_name)
        if not_found is not None:
            logger.info(
                "open_chat_for_contact returned candidates for chat=%s; "
                "skipping reply send",
                chat_name,
            )
            enriched: dict[str, Any] = {
                "error": not_found.get("error"),
                "chat_name": chat_name,
                "candidates": not_found.get("candidates", {}),
                "reply_message": reply_message,
                "sent": False,
                "tool": "reply_to_messages_by_chat",
            }
            return enriched

        sent = False
        if reply_message is not None and reply_message.strip():
            send_message(reply_message)
            sent = True
            logger.info(
                "Reply sent to chat=%s; message length=%d",
                chat_name,
                len(reply_message),
            )

        return {
            "chat_name": chat_name,
            "reply_message": reply_message,
            "sent": sent,
        }
    except Exception as exc:
        logger.exception(
            "Error in reply_to_messages_by_chat for chat=%s: %s",
            chat_name,
            exc,
        )
        return {
            "error": str(exc),
            "chat_name": chat_name,
        }


@mcp.tool()
def add_contact_by_wechat_id(
    wechat_id: str,
    friending_msg: str | None = None,
    remark: str | None = None,
    tags: str | None = None,
    privacy: str | None = None,
    hide_my_posts: bool = False,
    hide_their_posts: bool = False,
) -> dict[str, Any]:
    """
    Add a new contact using a WeChat ID.

    This tool automates the WeChat flow:
    - Type the given WeChat ID into the global search box.
    - Click the "Search WeChat ID" card under the "More" section.
    - In the "Add Contacts" window, click "Add to Contacts".
    - In the "Send Friend Request" window, optionally customize the
      friending message, remark, and privacy options, then confirm.

    The `privacy` argument controls the "Privacy" section of the
    friend-request window:
    - "all" (default) selects "Chats, Moments, WeRun, etc." and applies
      the `hide_my_posts` / `hide_their_posts` flags.
    - "chats_only" selects "Chats Only" and ignores the hide flags.
    """
    logger.info(
        "Tool add_contact_by_wechat_id called for ID=%s (privacy=%r, hide_my_posts=%s, hide_their_posts=%s)",
        wechat_id,
        privacy,
        hide_my_posts,
        hide_their_posts,
    )
    try:
        result = ax_add_contact_by_wechat_id(
            wechat_id=wechat_id,
            friending_msg=friending_msg,
            remark=remark,
            tags=tags,
            privacy=privacy,
            hide_my_posts=hide_my_posts,
            hide_their_posts=hide_their_posts,
        )
        return result
    except Exception as exc:
        logger.exception(
            "Error in add_contact_by_wechat_id for ID=%s: %s",
            wechat_id,
            exc,
        )
        return {
            "error": str(exc),
            "wechat_id": wechat_id,
        }


@mcp.tool()
def publish_moment_without_media(
    content: str,
    publish: bool = True,
) -> dict[str, Any]:
    """
    Publish a Moments post containing only text (no media).

    This will:
    - Open the main WeChat window and click the "Moments" button.
    - Long-press the "Post" button in the Moments window to open the
      composer sheet.
    - Fill the text entry area with the provided content.
    - If `publish` is True (default), click the "Post" button in the
      sheet to publish the moment; if False, leave the composer open
      without sending.
    """
    logger.info(
        "Tool publish_moment_without_media called (content_length=%d, publish=%s)",
        len(content) if isinstance(content, str) else -1,
        publish,
    )
    try:
        result = ax_publish_moment(content=content, publish=publish)
        return result
    except Exception as exc:
        logger.exception("Error in publish_moment_without_media: %s", exc)
        return {
            "error": str(exc),
            "content": content,
        }


def main() -> None:
    """
    Entry point for the WeChat MCP server.
    """
    parser = argparse.ArgumentParser(description="WeChat Helper MCP Server")
    parser.add_argument(
        "--mcp-debug",
        action="store_true",
        help="Enable detailed MCP protocol debugging logs",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="Transport protocol to use (default: stdio)",
    )

    args = parser.parse_args()

    configure_logging(debug=args.mcp_debug)

    logger.info("Starting WeChat Helper MCP Server")
    logger.info("Transport: %s", args.transport)
    logger.info("MCP Debug mode: %s", args.mcp_debug)

    if args.transport == "stdio":
        mcp.run()
    elif args.transport == "streamable-http":
        mcp.run(transport="streamable-http")
    elif args.transport == "sse":
        mcp.run(transport="sse")


if __name__ == "__main__":
    main()
