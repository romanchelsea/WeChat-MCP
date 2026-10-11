"""
Generic macOS Accessibility (AX) and synthetic input helpers.

Nothing in this module knows about WeChat: it walks AX trees, reads
element geometry, and posts mouse, keyboard and scroll events through
Quartz. WeChat-specific navigation lives in `navigation`.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    AXValueGetType,
    AXValueGetValue,
    kAXChildrenAttribute,
    kAXIdentifierAttribute,
    kAXPositionAttribute,
    kAXRoleAttribute,
    kAXSizeAttribute,
    kAXTitleAttribute,
    kAXValueCGPointType,
    kAXValueCGSizeType,
    kAXWindowRole,
)
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventCreateMouseEvent,
    CGEventCreateScrollWheelEvent,
    CGEventPost,
    CGEventSetFlags,
    CGEventSetLocation,
    CGPoint,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseUp,
    kCGHIDEventTap,
    kCGScrollEventUnitLine,
)

logger = logging.getLogger(__name__)

KEYCODE_A = 0  # US keyboard 'A'
KEYCODE_V = 9  # US keyboard 'V'
KEYCODE_RETURN = 36


def ax_get(element, attribute):
    err, value = AXUIElementCopyAttributeValue(element, attribute, None)
    if err != 0:
        return None
    return value


def dfs(element, predicate: Callable[[Any, Any, Any, Any], bool]):
    if element is None:
        return None

    role = ax_get(element, kAXRoleAttribute)
    title = ax_get(element, kAXTitleAttribute)
    identifier = ax_get(element, kAXIdentifierAttribute)

    if predicate(element, role, title, identifier):
        return element

    children = ax_get(element, kAXChildrenAttribute) or []
    for child in children:
        found = dfs(child, predicate)
        if found is not None:
            return found
    return None


def axvalue_to_point(ax_value):
    if ax_value is None or AXValueGetType(ax_value) != kAXValueCGPointType:
        return None
    ok, cg_point = AXValueGetValue(ax_value, kAXValueCGPointType, None)
    if not ok:
        return None
    return float(cg_point.x), float(cg_point.y)


def axvalue_to_size(ax_value):
    if ax_value is None or AXValueGetType(ax_value) != kAXValueCGSizeType:
        return None
    ok, cg_size = AXValueGetValue(ax_value, kAXValueCGSizeType, None)
    if not ok:
        return None
    return float(cg_size.width), float(cg_size.height)


def element_frame(
    element, description: str = "element"
) -> tuple[tuple[float, float], tuple[float, float]]:
    """
    Return the on-screen ((x, y), (width, height)) of an AX element.

    Raises RuntimeError mentioning `description` if either is unavailable.
    """
    origin = axvalue_to_point(ax_get(element, kAXPositionAttribute))
    size = axvalue_to_size(ax_get(element, kAXSizeAttribute))
    if origin is None or size is None:
        raise RuntimeError(f"Failed to get bounds for {description}")
    return origin, size


def element_center(element, description: str = "element") -> tuple[float, float]:
    """
    Return the on-screen center point of an AX element.
    """
    (x, y), (w, h) = element_frame(element, description)
    return x + w / 2.0, y + h / 2.0


def click_element_center(element) -> None:
    """
    Synthesize a left mouse click at the visual center of the element.
    """
    cx, cy = element_center(element, "element to click")

    event_down = CGEventCreateMouseEvent(
        None, kCGEventLeftMouseDown, CGPoint(cx, cy), 0
    )
    event_up = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, CGPoint(cx, cy), 0)
    CGEventPost(kCGHIDEventTap, event_down)
    CGEventPost(kCGHIDEventTap, event_up)


def long_press_element_center(element, hold_seconds: float = 2.2) -> None:
    """
    Synthesize a long left mouse press at the visual center of the
    given element.
    """
    cx, cy = element_center(element, "element to long-press")

    event_down = CGEventCreateMouseEvent(
        None, kCGEventLeftMouseDown, CGPoint(cx, cy), 0
    )
    CGEventPost(kCGHIDEventTap, event_down)
    try:
        time.sleep(max(0.0, hold_seconds))
    finally:
        event_up = CGEventCreateMouseEvent(
            None, kCGEventLeftMouseUp, CGPoint(cx, cy), 0
        )
        CGEventPost(kCGHIDEventTap, event_up)


def send_key_with_modifiers(keycode: int, flags: int = 0) -> None:
    """
    Synthesize a key press (down + up) with the given modifier flags.
    """
    event_down = CGEventCreateKeyboardEvent(None, keycode, True)
    CGEventSetFlags(event_down, flags)
    event_up = CGEventCreateKeyboardEvent(None, keycode, False)
    CGEventSetFlags(event_up, flags)
    CGEventPost(kCGHIDEventTap, event_down)
    CGEventPost(kCGHIDEventTap, event_up)


def post_scroll(center, delta_lines: int) -> None:
    """
    Post a scroll-wheel event at the given screen position.

    On a standard macOS configuration:
    - Positive delta_lines scrolls towards older content (upwards in history).
    - Negative delta_lines scrolls towards newer content (downwards in history).
    """
    cx, cy = center
    event = CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 1, delta_lines)
    CGEventSetLocation(event, CGPoint(cx, cy))
    CGEventPost(kCGHIDEventTap, event)


def find_window_by_title(ax_app: Any, title: str):
    """
    Locate a top-level window of the app with the given title.
    """

    def is_window(el, role, current_title, identifier):
        return (
            role == kAXWindowRole
            and isinstance(current_title, str)
            and current_title == title
        )

    return dfs(ax_app, is_window)


def wait_for_window(ax_app: Any, title: str, timeout: float = 5.0):
    """
    Wait for a window with the given title to appear, returning the AX
    element or None if the timeout expires.
    """
    end = time.time() + timeout
    while time.time() < end:
        window = find_window_by_title(ax_app, title)
        if window is not None:
            logger.info("Found window %r", title)
            return window
        time.sleep(0.1)
    logger.warning("Timed out waiting for window %r", title)
    return None
