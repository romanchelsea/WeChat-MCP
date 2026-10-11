"""
Unit tests for the Moments-opening logic in publish_moment_utils.

WeChat's Accessibility tree is replaced with small fake elements, so these
tests never touch the real app. They cover the UI variants seen in the
wild: "WeChat" vs "Weixin" vs "微信" main windows, a sidebar "Moments"
button vs. a "Discover" layout that only exposes Window > Moments, and
Moments opening in its own window vs. inside the main window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pytest
from ApplicationServices import (
    kAXButtonRole,
    kAXChildrenAttribute,
    kAXTitleAttribute,
    kAXWindowsAttribute,
)

from wechat_mcp import publish_moment_utils as pmu


@dataclass
class El:
    role: str = "AXGroup"
    title: str | None = None
    children: list["El"] = field(default_factory=list)
    on_press: Callable[[], None] | None = None


class FakeApp(El):
    def __init__(self) -> None:
        super().__init__(role="AXApplication")
        self.windows: list[El] = []
        self.menu_bar = El(role="AXMenuBar")


def button(title: str, on_press: Callable[[], None] | None = None) -> El:
    return El(role=kAXButtonRole, title=title, on_press=on_press)


def window(title: str, *buttons: El) -> El:
    return El(role="AXWindow", title=title, children=list(buttons))


def moments_content() -> list[El]:
    return [button("Post"), button("Refresh"), button("Messages")]


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> FakeApp:
    fake = FakeApp()
    presses: list[El] = []
    fake.presses = presses  # type: ignore[attr-defined]

    def ax_get(el: Any, attr: str) -> Any:
        if attr == kAXTitleAttribute:
            return el.title
        if attr == kAXChildrenAttribute:
            return el.children
        if attr == kAXWindowsAttribute:
            return el.windows
        if attr == "AXMenuBar":
            return el.menu_bar
        return None

    def dfs(el: El, predicate: Callable[..., bool]) -> El | None:
        if el is None:
            return None
        if predicate(el, el.role, el.title, None):
            return el
        for child in el.children:
            found = dfs(child, predicate)
            if found is not None:
                return found
        return None

    def find_window_by_title(app_el: FakeApp, title: str) -> El | None:
        return next((w for w in app_el.windows if w.title == title), None)

    def perform_action(el: El, action: str) -> int:
        presses.append(el)
        if el.on_press is not None:
            el.on_press()
        return 0

    monkeypatch.setattr(pmu, "ax_get", ax_get)
    monkeypatch.setattr(pmu, "dfs", dfs)
    monkeypatch.setattr(pmu, "_find_window_by_title", find_window_by_title)
    monkeypatch.setattr(pmu, "AXUIElementPerformAction", perform_action)
    monkeypatch.setattr(pmu, "click_element_center", lambda el: None)
    monkeypatch.setattr(pmu.time, "sleep", lambda s: None)
    return fake


def add_window_menu_item(app: FakeApp, title: str, on_press: Callable[[], None]) -> None:
    entry = El(role="AXMenuItem", title=title, on_press=on_press)
    app.menu_bar.children.append(
        El(role="AXMenuBarItem", title="Window", children=[El(role="AXMenu", children=[entry])])
    )


# --- _find_moments_window ---------------------------------------------------


def test_finds_window_titled_moments(app: FakeApp) -> None:
    main = window("Weixin", button("Contacts"))
    moments = window("Moments", *moments_content())
    app.windows = [main, moments]
    assert pmu._find_moments_window(app) is moments


def test_finds_untitled_window_by_post_and_refresh(app: FakeApp) -> None:
    main = window("Weixin", button("Contacts"))
    detached = window("WeChat (Window)", *moments_content())
    app.windows = [main, detached]
    assert pmu._find_moments_window(app) is detached


def test_falls_back_to_main_window_when_moments_is_embedded(app: FakeApp) -> None:
    main = window("WeChat", button("Contacts"), button("Discover"), *moments_content())
    app.windows = [main]
    assert pmu._find_moments_window(app) is main


def test_prefers_separate_window_over_main(app: FakeApp) -> None:
    main = window("WeChat", button("Contacts"), *moments_content())
    detached = window("WeChat (Window)", *moments_content())
    app.windows = [main, detached]
    assert pmu._find_moments_window(app) is detached


def test_returns_none_without_post_and_refresh(app: FakeApp) -> None:
    app.windows = [window("WeChat", button("Contacts"), button("Post"))]
    assert pmu._find_moments_window(app) is None


# --- _open_moments_window ---------------------------------------------------


@pytest.mark.parametrize("title", ["WeChat", "Weixin", "微信"])
def test_presses_sidebar_button_for_any_main_window_title(app: FakeApp, title: str) -> None:
    def open_moments() -> None:
        app.windows.append(window("Moments", *moments_content()))

    app.windows = [window(title, button("Moments", on_press=open_moments))]
    result = pmu._open_moments_window(app, timeout=0.5)
    assert result.title == "Moments"
    assert len(app.presses) == 1  # type: ignore[attr-defined]


def test_reuses_open_moments_without_pressing(app: FakeApp) -> None:
    moments = window("Moments", *moments_content())
    app.windows = [window("Weixin", button("Moments")), moments]
    assert pmu._open_moments_window(app, timeout=0.5) is moments
    assert app.presses == []  # type: ignore[attr-defined]


def test_uses_window_menu_when_sidebar_only_has_discover(app: FakeApp) -> None:
    main = window("WeChat", button("Contacts"), button("Discover"))
    app.windows = [main]

    def open_moments() -> None:
        main.children.extend(moments_content())

    add_window_menu_item(app, "Moments", open_moments)
    assert pmu._open_moments_window(app, timeout=0.5) is main


def test_raises_when_no_button_and_no_menu_item(app: FakeApp) -> None:
    app.windows = [window("WeChat", button("Contacts"), button("Discover"))]
    with pytest.raises(RuntimeError, match="Window menu"):
        pmu._open_moments_window(app, timeout=0.5)


def test_raises_when_main_window_missing(app: FakeApp) -> None:
    app.windows = [window("Settings")]
    with pytest.raises(RuntimeError, match="main WeChat window"):
        pmu._open_moments_window(app, timeout=0.5)


def test_raises_when_moments_never_appears(app: FakeApp) -> None:
    app.windows = [window("Weixin", button("Moments"))]  # press does nothing
    with pytest.raises(RuntimeError, match="did not appear"):
        pmu._open_moments_window(app, timeout=0.05)
