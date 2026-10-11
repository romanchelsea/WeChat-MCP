"""
Reading and sending messages in the currently open WeChat chat.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Literal

from ApplicationServices import (
    AXUIElementPerformAction,
    AXUIElementSetAttributeValue,
    kAXChildrenAttribute,
    kAXListRole,
    kAXPositionAttribute,
    kAXRaiseAction,
    kAXSizeAttribute,
    kAXTextAreaRole,
    kAXTitleAttribute,
    kAXValueAttribute,
)
from PIL import ImageGrab

from .accessibility import (
    KEYCODE_RETURN,
    ax_get,
    axvalue_to_point,
    axvalue_to_size,
    dfs,
    element_center,
    element_frame,
    post_scroll,
    send_key_with_modifiers,
)
from .navigation import get_wechat_ax_app

logger = logging.getLogger(__name__)


def get_messages_list(ax_app: Any) -> Any:
    """
    Find the AX list that contains chat messages in the current WeChat window.
    """

    def is_message_list(el, role, title, identifier):
        return role == kAXListRole and (title or "") == "Messages"

    msg_list = dfs(ax_app, is_message_list)
    if msg_list is None:
        raise RuntimeError("Could not find WeChat 'Messages' list in AX tree")
    return msg_list


def capture_message_area(msg_list: Any):
    """
    Capture a screenshot of the visible message area for the given list and
    return the image together with the list origin and size.
    """
    origin, size = element_frame(msg_list, "WeChat messages list")
    x, y = origin
    w, h = size

    bbox = (int(x), int(y), int(x + w), int(y + h))
    image = ImageGrab.grab(bbox=bbox)
    return image, origin, size


def scroll_to_bottom(msg_list: Any, center: tuple[float, float]) -> None:
    """
    Scroll the messages list to the bottom (newest messages) by repeatedly
    sending large negative scroll events until the last visible message
    stabilizes.
    """
    last_text: str | None = None
    stable = 0

    for _ in range(40):
        # Negative delta moves towards newer messages (bottom of history).
        post_scroll(center, -1000)
        time.sleep(0.05)

        children = ax_get(msg_list, kAXChildrenAttribute) or []
        texts: list[str] = []
        for child in children:
            txt = ax_get(child, kAXValueAttribute) or ax_get(child, kAXTitleAttribute)
            if txt:
                texts.append(str(txt))
        if not texts:
            continue

        new_last = texts[-1]
        if new_last == last_text:
            stable += 1
            if stable >= 3:
                break
        else:
            last_text = new_last
            stable = 0

    time.sleep(0.2)


def scroll_up_small(center: tuple[float, float]) -> None:
    """
    Scroll slightly upwards to reveal older messages.
    """
    # Positive delta scrolls towards older messages.
    post_scroll(center, 50)
    time.sleep(0.1)


def count_colored_pixels(
    image, left: float, top: float, right: float, bottom: float
) -> tuple[int, int]:
    left_i = max(0, int(left))
    top_i = max(0, int(top))
    right_i = min(image.width, int(right))
    bottom_i = min(image.height, int(bottom))
    if right_i <= left_i or bottom_i <= top_i:
        return 0, 0

    region = image.crop((left_i, top_i, right_i, bottom_i)).convert("RGB")
    pixels = region.load()

    width, height = region.size
    colored = 0
    total = width * height

    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            brightness = (r + g + b) / 3.0
            if brightness < 20:
                continue
            if brightness > 40 or (max(r, g, b) - min(r, g, b)) > 10:
                colored += 1

    return colored, total


SenderLabel = Literal["ME", "OTHER", "UNKNOWN"]


def classify_sender_for_message(
    image, list_origin, message_pos, message_size
) -> SenderLabel:
    """
    Heuristic classification of a message sender by sampling coloured pixels on
    the left/right side of the message bubble.
    """
    list_x, list_y = list_origin
    msg_x, msg_y = message_pos
    msg_w, msg_h = message_size

    rel_x = msg_x - list_x
    rel_y = msg_y - list_y

    band_height = min(40.0, msg_h)
    center_y = rel_y + msg_h / 2.0
    top = center_y - band_height / 2.0
    bottom = top + band_height

    margin = 5.0
    sample_width = min(100.0, msg_w / 3.0)

    left_left = rel_x + margin
    left_right = left_left + sample_width

    right_right = rel_x + msg_w - margin
    right_left = right_right - sample_width

    left_colored, left_total = count_colored_pixels(
        image, left_left, top, left_right, bottom
    )
    right_colored, right_total = count_colored_pixels(
        image, right_left, top, right_right, bottom
    )

    avg_area = (left_total + right_total) / 2.0 if (left_total + right_total) else 0.0
    min_signal = max(10.0, avg_area * 0.01)

    if left_colored < min_signal and right_colored < min_signal:
        return "UNKNOWN"

    if right_colored > left_colored * 1.5:
        return "ME"
    if left_colored > right_colored * 1.5:
        return "OTHER"
    return "UNKNOWN"


@dataclass
class ChatMessage:
    sender: SenderLabel
    text: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def fetch_recent_messages(
    last_n: int = 100, max_scrolls: int | None = None
) -> list[ChatMessage]:
    """
    Fetch the true last N messages from the currently open chat, even
    when the history spans multiple screens.

    Uses a scrolling strategy that involves:
    - Scrolls to the bottom of the chat history.
    - Repeatedly scrolls upwards in small steps.
    - At each position, captures a screenshot of the message area and
      collects all visible messages plus their positions/sizes.
    - Classifies each message as ME/OTHER/UNKNOWN using the same
      screenshot-based heuristic as before.
    - Merges newly revealed older messages at the front of the list by
      aligning on the oldest already-known message text.
    """
    ax_app = get_wechat_ax_app()
    msg_list = get_messages_list(ax_app)
    center = element_center(msg_list, "list element")
    scroll_to_bottom(msg_list, center)

    messages: list[ChatMessage] = []
    scrolls = 0
    no_new_counter = 0

    while True:
        image, list_origin, _ = capture_message_area(msg_list)

        children = ax_get(msg_list, kAXChildrenAttribute) or []
        visible: list[ChatMessage] = []

        for child in children:
            text = ax_get(child, kAXValueAttribute) or ax_get(child, kAXTitleAttribute)
            if not text:
                continue

            pos_ref = ax_get(child, kAXPositionAttribute)
            size_ref = ax_get(child, kAXSizeAttribute)
            point = axvalue_to_point(pos_ref)
            size = axvalue_to_size(size_ref)
            if point is None or size is None:
                sender: SenderLabel = "UNKNOWN"
            else:
                sender = classify_sender_for_message(image, list_origin, point, size)

            visible.append(ChatMessage(sender=sender, text=str(text)))

        if not visible:
            break

        if not messages:
            messages = visible
        else:
            # Align on the oldest already-known message using its text as anchor.
            anchor_text = messages[0].text
            idx: int | None = None
            for i, msg in enumerate(visible):
                if msg.text == anchor_text:
                    idx = i
                    break

            if idx is None:
                new_older = visible
            else:
                new_older = visible[:idx]

            if new_older:
                messages = new_older + messages
                no_new_counter = 0
            else:
                no_new_counter += 1
                if no_new_counter >= 5:
                    break

        if len(messages) >= last_n:
            break

        scroll_up_small(center)

        scrolls += 1
        if max_scrolls is not None and scrolls >= max_scrolls:
            break

    if len(messages) > last_n:
        messages = messages[-last_n:]

    logger.info(
        "Fetched %d messages from current chat (requested last_n=%d)",
        len(messages),
        last_n,
    )
    return messages


def find_input_field(ax_app: Any):
    """
    Locate the chat input text area in the current WeChat window.
    """

    def is_input(el, role, title, identifier):
        return role == kAXTextAreaRole and identifier == "chat_input_field"

    input_field = dfs(ax_app, is_input)
    if input_field is None:
        raise RuntimeError(
            "Could not find WeChat chat input field via Accessibility API"
        )
    return input_field


def send_message(text: str) -> None:
    """
    Send a message in the currently open chat by focusing the input
    field, setting its value, and pressing Return.
    """
    logger.info("Sending message of length %d characters", len(text))
    ax_app = get_wechat_ax_app()
    input_field = find_input_field(ax_app)

    AXUIElementPerformAction(input_field, kAXRaiseAction)

    err = AXUIElementSetAttributeValue(input_field, kAXValueAttribute, text)
    if err != 0:
        raise RuntimeError(f"Failed to set input text, AX error {err}")

    time.sleep(0.1)
    send_key_with_modifiers(KEYCODE_RETURN)
    logger.info("Message sent")
