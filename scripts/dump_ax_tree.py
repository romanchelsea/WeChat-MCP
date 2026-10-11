"""
Dump WeChat's macOS Accessibility (AX) tree for debugging selectors.

Read-only: it does not click, type or activate WeChat. Run it from a
terminal that has Accessibility permission (System Settings > Privacy &
Security > Accessibility), with a chat open in WeChat:

    uv run python scripts/dump_ax_tree.py > debug-artifacts/ax_tree.txt

For transient UI such as search results (which close when WeChat loses
focus), pass --delay so you can switch back to WeChat before the dump:

    uv run python scripts/dump_ax_tree.py --delay 8 > debug-artifacts/ax_tree_search.txt

Each line shows: role, subrole, title, identifier, description, value,
position and size.

Privacy: the dump includes contact names and message previews that are
visible in WeChat. Write it under `debug-artifacts/` (git-ignored) and
redact it before sharing or attaching it to an issue.
"""

from __future__ import annotations

import argparse
import sys
import time

import AppKit
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXValueGetType,
    AXValueGetValue,
    kAXChildrenAttribute,
    kAXDescriptionAttribute,
    kAXIdentifierAttribute,
    kAXPositionAttribute,
    kAXRoleAttribute,
    kAXSizeAttribute,
    kAXSubroleAttribute,
    kAXTitleAttribute,
    kAXValueAttribute,
    kAXValueCGPointType,
    kAXValueCGSizeType,
)

MAX_NODES = 5000


def ax_get(element, attribute):
    err, value = AXUIElementCopyAttributeValue(element, attribute, None)
    return value if err == 0 else None


def fmt_geom(element) -> str:
    pos = ax_get(element, kAXPositionAttribute)
    size = ax_get(element, kAXSizeAttribute)
    out = ""
    if pos is not None and AXValueGetType(pos) == kAXValueCGPointType:
        _, p = AXValueGetValue(pos, kAXValueCGPointType, None)
        out += f" @({p.x:.0f},{p.y:.0f})"
    if size is not None and AXValueGetType(size) == kAXValueCGSizeType:
        _, s = AXValueGetValue(size, kAXValueCGSizeType, None)
        out += f" {s.width:.0f}x{s.height:.0f}"
    return out


def short(value) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\n", "\\n")
    return text[:60] + ("…" if len(text) > 60 else "")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="seconds to wait before dumping (time to switch to WeChat)",
    )
    parser.add_argument("--max-depth", type=int, default=40)
    args = parser.parse_args()

    print(f"AXIsProcessTrusted: {AXIsProcessTrusted()}", file=sys.stderr)
    for remaining in range(int(args.delay), 0, -1):
        print(f"Dumping in {remaining}s... switch to WeChat now", file=sys.stderr)
        time.sleep(1)
    time.sleep(args.delay - int(args.delay))
    print("Dumping...", file=sys.stderr)
    apps = AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_(
        "com.tencent.xinWeChat"
    )
    if not apps:
        sys.exit("WeChat is not running")
    ax_app = AXUIElementCreateApplication(apps[0].processIdentifier())

    count = 0

    def walk(element, depth: int) -> None:
        nonlocal count
        count += 1
        if count > MAX_NODES:
            return
        fields = {
            "sub": ax_get(element, kAXSubroleAttribute),
            "title": ax_get(element, kAXTitleAttribute),
            "id": ax_get(element, kAXIdentifierAttribute),
            "desc": ax_get(element, kAXDescriptionAttribute),
            "value": short(ax_get(element, kAXValueAttribute)),
        }
        attrs = " ".join(f"{k}={v!r}" for k, v in fields.items() if v not in (None, ""))
        role = ax_get(element, kAXRoleAttribute)
        print(f"{'  ' * depth}{role} {attrs}{fmt_geom(element)}")
        if depth >= args.max_depth:
            return
        for child in ax_get(element, kAXChildrenAttribute) or []:
            walk(child, depth + 1)

    walk(ax_app, 0)
    print(f"# nodes visited: {count}", file=sys.stderr)


if __name__ == "__main__":
    main()
