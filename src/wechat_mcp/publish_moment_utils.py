from __future__ import annotations

import time
from typing import Any

from ApplicationServices import (
    AXUIElementPerformAction,
    AXUIElementSetAttributeValue,
    kAXButtonRole,
    kAXChildrenAttribute,
    kAXPressAction,
    kAXRaiseAction,
    kAXSheetRole,
    kAXTextAreaRole,
    kAXTitleAttribute,
    kAXValueAttribute,
    kAXWindowsAttribute,
)

from .logging_config import logger
from .wechat_accessibility import (
    _find_window_by_title,
    ax_get,
    click_element_center,
    dfs,
    get_wechat_ax_app,
    long_press_element_center,
)

_MAIN_WINDOW_TITLES = ("WeChat", "Weixin", "微信")


def _open_moments_window(ax_app: Any, timeout: float = 5.0) -> Any:
    """
    Ensure the WeChat Moments window is open and return it.

    Depending on the build/layout, Moments is reachable either through a
    sidebar button in the main window or only through the Window menu
    (the sidebar then exposes a "Discover" entry instead). If it is
    already open it is reused, since pressing again may toggle it away.
    """
    existing = _find_moments_window(ax_app)
    if existing is not None:
        return existing

    # The same macOS client is branded "WeChat" (international) or
    # "Weixin"/"微信" (mainland), and the main window title follows suit.
    main_window = None
    for window_title in _MAIN_WINDOW_TITLES:
        main_window = _find_window_by_title(ax_app, window_title)
        if main_window is not None:
            break
    if main_window is None:
        raise RuntimeError(
            "Could not find main WeChat window with any of the titles "
            f"{list(_MAIN_WINDOW_TITLES)}"
        )

    def is_moments_button(el, role, title, identifier):
        return role == kAXButtonRole and isinstance(title, str) and title == "Moments"

    button = dfs(main_window, is_moments_button)
    if button is not None:
        logger.info("Pressing 'Moments' button in main window")
        # Prefer the AX press action over a synthesized mouse click.
        if AXUIElementPerformAction(button, kAXPressAction) != 0:
            click_element_center(button)
    elif not _press_window_menu_item(ax_app, "Moments"):
        raise RuntimeError(
            "Could not find a 'Moments' button in the main window nor a "
            "'Moments' item in the Window menu"
        )

    end = time.time() + timeout
    while time.time() < end:
        moments_window = _find_moments_window(ax_app)
        if moments_window is not None:
            return moments_window
        time.sleep(0.1)

    raise RuntimeError("The 'Moments' window did not appear after opening it")


def _press_window_menu_item(ax_app: Any, item_title: str) -> bool:
    """
    Press an item of the app's "Window" menu by title. Returns whether the
    item was found and pressed.
    """
    menu_bar = ax_get(ax_app, "AXMenuBar")
    for bar_item in ax_get(menu_bar, kAXChildrenAttribute) or []:
        if ax_get(bar_item, kAXTitleAttribute) != "Window":
            continue
        for menu in ax_get(bar_item, kAXChildrenAttribute) or []:
            for entry in ax_get(menu, kAXChildrenAttribute) or []:
                if ax_get(entry, kAXTitleAttribute) == item_title:
                    logger.info("Pressing Window > %s menu item", item_title)
                    return AXUIElementPerformAction(entry, kAXPressAction) == 0
    return False


def _find_moments_window(ax_app: Any) -> Any | None:
    """
    Locate the window currently showing Moments.

    Its title varies by build ("Moments", a generic "WeChat (Window)", or
    the main window itself), so fall back to the window that has both a
    'Post' and a 'Refresh' button, preferring windows that are not the
    main one.
    """
    window = _find_window_by_title(ax_app, "Moments")
    if window is not None:
        return window

    def has_button(window, name):
        return (
            dfs(
                window,
                lambda el, role, title, ident: role == kAXButtonRole and title == name,
            )
            is not None
        )

    candidates = ax_get(ax_app, kAXWindowsAttribute) or []
    candidates = sorted(
        candidates,
        key=lambda w: ax_get(w, kAXTitleAttribute) in _MAIN_WINDOW_TITLES,
    )
    for candidate in candidates:
        if has_button(candidate, "Post") and has_button(candidate, "Refresh"):
            return candidate
    return None


def _open_moment_composer(moments_window: Any) -> None:
    """
    Open the Moments composer sheet by long-pressing the Post button in
    the Moments window.
    """

    def is_post_button(el, role, title, identifier):
        return role == kAXButtonRole and isinstance(title, str) and title == "Post"

    button = dfs(moments_window, is_post_button)
    if button is None:
        raise RuntimeError("Could not find 'Post' button in Moments window")

    logger.info("Long-pressing 'Post' button to open composer sheet")
    long_press_element_center(button, hold_seconds=1.4)
    time.sleep(0.3)


def _find_moments_sheet(moments_window: Any, timeout: float = 5.0) -> Any | None:
    """
    Wait for the Moments composer sheet to appear inside the Moments
    window, returning the sheet element or None if the timeout expires.
    """

    def is_sheet(el, role, title, identifier):
        return role == kAXSheetRole

    end = time.time() + timeout
    while time.time() < end:
        sheet = dfs(moments_window, is_sheet)
        if sheet is not None:
            logger.info("Found Moments composer sheet")
            return sheet
        time.sleep(0.1)

    logger.warning("Timed out waiting for Moments composer sheet")
    return None


def _find_editor_root(moments_window: Any, timeout: float = 5.0) -> Any | None:
    """
    Return the root element that contains the Moments composer controls.

    Prefer the dedicated AXSheet element; fall back to the Moments
    window itself if the sheet cannot be located.
    """
    sheet = _find_moments_sheet(moments_window, timeout=timeout)
    if sheet is not None:
        return sheet

    logger.warning(
        "Falling back to using the Moments window as editor root "
        "because composer sheet was not found"
    )
    return moments_window


def _find_moment_text_area(root: Any) -> Any | None:
    """
    Locate the text entry area used to compose a Moments post.
    """

    def is_text_area(el, role, title, identifier):
        return role == kAXTextAreaRole

    return dfs(root, is_text_area)


def _find_post_button_in_editor(root: Any) -> Any | None:
    """
    Locate the Post button within the composer editor root (sheet or
    Moments window).
    """

    def is_post_button(el, role, title, identifier):
        return role == kAXButtonRole and isinstance(title, str) and title == "Post"

    return dfs(root, is_post_button)


def publish_moment_without_media(content: str, publish: bool = True) -> dict[str, Any]:
    """
    Publish a Moments post containing only text (no media).

    High-level flow:
    - Click the "Moments" button in the main WeChat window to open the
      Moments window.
    - Long-press the "Post" button in the Moments window to reveal the
      composer sheet.
    - In the composer sheet, set the text entry area's value to the
      provided content.
    - If `publish` is True (default), click the "Post" button in the
      sheet to publish the moment; if False, leave the composer open
      without sending, so that the user can modify the draft in the
      composer.
    """
    if not isinstance(content, str) or not content.strip():
        return {
            "error": "content must be a non-empty string",
            "content": content,
            "stage": "validate_input",
        }

    logger.info(
        "Starting publish_moment_without_media (content_length=%d, publish=%s)",
        len(content),
        publish,
    )

    try:
        ax_app = get_wechat_ax_app()
        moments_window = _open_moments_window(ax_app)
        _open_moment_composer(moments_window)

        editor_root = _find_editor_root(moments_window, timeout=5.0)
        if editor_root is None:
            error_msg = "Could not locate Moments composer editor root"
            logger.warning(error_msg)
            return {
                "error": error_msg,
                "content": content,
                "stage": "editor_root",
            }

        text_area = _find_moment_text_area(editor_root)
        if text_area is None:
            error_msg = "Could not find text entry area in Moments composer"
            logger.warning(error_msg)
            return {
                "error": error_msg,
                "content": content,
                "stage": "text_area",
            }

        AXUIElementPerformAction(text_area, kAXRaiseAction)
        err = AXUIElementSetAttributeValue(text_area, kAXValueAttribute, content)
        if err != 0:
            error_msg = f"Failed to set composer text, AX error {err}"
            logger.warning(error_msg)
            return {
                "error": error_msg,
                "content": content,
                "stage": "set_text",
            }

        if not publish:
            logger.info(
                "Moments composer text updated; publish=False so skipping Post click"
            )
            return {
                "content": content,
                "posted": False,
            }

        logger.info("Moments composer text updated; clicking Post in sheet")
        post_button = _find_post_button_in_editor(editor_root)
        if post_button is None:
            error_msg = "Could not find 'Post' button in Moments composer"
            logger.warning(error_msg)
            return {
                "error": error_msg,
                "content": content,
                "stage": "post_button",
            }

        click_element_center(post_button)
        time.sleep(0.5)

        logger.info("Moments post submitted successfully")
        return {
            "content": content,
            "posted": True,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error while publishing moment without media: %s", exc)
        return {
            "error": str(exc),
            "content": content,
            "stage": "unexpected_error",
        }
