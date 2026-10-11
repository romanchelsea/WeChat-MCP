# Repository Guidelines

## Project Structure & Modules
- Core code lives in `src/wechat_mcp` (MCP server, accessibility helpers, logging).
- Entry point is `wechat_mcp.mcp_server:main`, exposed as the `wechat-mcp` script.
- Logs are written to `~/Library/Logs/wechat-mcp/` by default (configurable via `WECHAT_MCP_LOG_DIR`).
  Modules use `logging.getLogger(__name__)`; only `main()` calls `logging_config.configure_logging()`.
- Modules are layered: generic macOS Accessibility/input helpers in `accessibility.py`, WeChat app and
  chat navigation in `navigation.py`, and one module per feature area (`messages.py`, `contacts.py`,
  `moments.py`). New tools go into the matching feature module; `mcp_server.py` stays a thin wrapper.

## Build, Run & Development
- Install dependencies: `uv sync` from the repository root.
- Run the MCP server (stdio): `uv run wechat-mcp --transport stdio`.
- Run over HTTP/SSE: `uv run wechat-mcp --transport streamable-http` or `--transport sse`.
- Enable protocol debugging: `uv run wechat-mcp --mcp-debug --transport stdio`.
- Point an MCP client at a checkout with `uv run --project <repo> wechat-mcp`; `uvx --from <repo>` caches
  its build and will not pick up edits to `src/`.
- Inspect WeChat's UI tree with `scripts/dump_ax_tree.py`; write dumps under `debug-artifacts/`
  (git-ignored, they contain real chat names). See `docs/debugging-moments-layouts.md`.

## Coding Style & Naming
- Python 3.12+, PEP 8 style, 4-space indentation, type hints where practical.
- Use `snake_case` for functions/variables, `PascalCase` for classes, and relative imports within `wechat_mcp`.
- Log via a module-level `logger = logging.getLogger(__name__)`; never `print` (stdout carries the
  stdio protocol).
- Keep functions small, with clear docstrings explaining interaction with macOS Accessibility APIs.

## Testing Guidelines
- Automated tests use `pytest` under `tests/`, mirroring `src/wechat_mcp`. They replace the
  Accessibility tree with fake elements and must never drive the real WeChat app.
- Scripts that do drive the real app (smoke checks that fetch, reply, add a contact or open the
  Moments composer) live in `scripts/manual/` and are not collected by pytest.
- Name test files `test_*.py` and test functions `test_*`.
- Run tests with `uv run pytest`.
- Avoid hitting real Accessibility APIs in unit tests; isolate them behind helper functions and use fakes where possible.

## Commit & Pull Request Guidelines
- Follow Conventional Commit style seen in history (e.g., `feat:`, `docs:`, `refactor(scope):`).
- Keep commits focused and descriptive; explain behavior changes, not just code moves.
- PRs should include: summary, motivation, how to reproduce/verify, and any macOS/WeChat version specifics.
- Attach relevant log snippets from `~/Library/Logs/wechat-mcp/wechat_mcp.log` when debugging Accessibility issues.

## Versioning & Releases
- The package version comes from git tags (`vMAJOR.MINOR.PATCH`) via `hatch-vcs`; do not edit a version in
  `pyproject.toml`. See `docs/releasing.md` for the bump rules and how to cut a release.

## Agent-Specific Instructions
- Keep diffs minimal and localized; avoid large refactors unless explicitly requested.
- Preserve existing logging, error handling, and transport behavior when extending features.
- Update `README.md` and this file when adding new tools, transports, or configuration knobs.
