# Debugging Moments across WeChat UI layouts

`publish_moment_without_media` drives WeChat through the macOS
Accessibility (AX) tree, so it depends on how the client lays out its UI.
This page records the variants seen so far and how to inspect a new one.

## Layouts seen in the wild

| Aspect | Variant A | Variant B |
|---|---|---|
| Main window title | `Weixin` (also `WeChat`, `微信` in other builds) | `WeChat` |
| Sidebar | `Moments`, `Search`, `Game Center`, ... buttons | `Chats`, `Contacts`, `Favorites`, `Discover` |
| How Moments opens | sidebar `Moments` button | `Window > Moments` menu item |
| Where Moments shows | its own window, or a side panel of the main window | inside the main window |

Do not rely on a window title or one button name. The code therefore:

1. reuses Moments if a window already has both a `Post` and a `Refresh`
   button (pressing the entry point again may toggle it away);
2. otherwise presses the sidebar `Moments` button if present;
3. otherwise presses `Moments` in the `Window` menu;
4. then long-presses `Post` to open the composer sheet.

## What the AX tree does and does not expose

- WeChat is a Qt application. The Moments side panel is an empty `AXGroup`
  with no `AXChildren`; `AXManualAccessibility` and
  `AXEnhancedUserInterface` are not supported.
- Elements inside the panel can still be reached by position with
  `AXUIElementCopyElementAtPosition`, but its title-bar icons (including
  "detach to a window") answer with `-25208`, so they cannot be found by
  name. A detached Moments window is fully accessible, as is Moments when
  opened through `Window > Moments`.
- The "visibility scope" setting did not change what the AX tree exposes.

## Inspecting a new layout

```bash
uv run python scripts/dump_ax_tree.py > debug-artifacts/ax_tree.txt
```

Dumps contain real chat names and message previews. They go under
`debug-artifacts/`, which is git-ignored. Redact before sharing.

When publishing fails, the error names the stage that failed
(`stage` in the tool result). The usual causes are a main window title or
sidebar entry the code does not know yet.

## Running the real MCP server from a checkout

`uvx --from <dir>` builds the package into a cached environment and does
**not** pick up later edits to `src/`. While developing, run the project in
its own environment instead:

```json
"wechat-mcp": {
  "type": "stdio",
  "command": "uv",
  "args": ["run", "--project", "/path/to/WeChat-MCP", "wechat-mcp"]
}
```

## Open items

- `publish=True` (actually pressing Post in the composer) has not been
  re-verified on the Discover layout.
- Opening Moments from a fully closed state, from the chat view, and with
  Moments already open are covered by unit tests with fake AX elements,
  but only the first two were exercised against a live WeChat.
- `Post` is opened with a synthesized long press (a mouse event), which may
  misbehave on unusual display layouts.
- Button and menu labels (`Post`, `Refresh`, `Window`, `Moments`) are
  matched in English; a Chinese UI language is not handled yet.
