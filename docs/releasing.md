# Releasing and versioning

The package version is **derived from git tags**; there is no version
string to edit in `pyproject.toml`. Tags follow
[Semantic Versioning](https://semver.org/): `vMAJOR.MINOR.PATCH`.

## How the version is computed

[`hatch-vcs`](https://github.com/ofek/hatch-vcs) reads the latest `v*` tag
reachable from the commit being built:

| Checkout | Version |
|---|---|
| exactly on tag `v0.3.0` | `0.3.0` |
| 4 commits after `v0.3.0` | `0.3.1.dev4` |
| no tag reachable | `0.1.dev<N>` (fallback; should not happen in CI) |

Development versions use the *next patch* with `.devN`, which sorts **before**
the next release and **after** the previous one, as PEP 440 requires. The
`+g<hash>` local suffix is disabled, because PyPI and TestPyPI reject it.

Check what a build would produce:

```bash
uv build -o /tmp/dist && ls /tmp/dist
# or, for the installed project:
uv run python -c "import importlib.metadata as m; print(m.version('wechat-mcp-xiongwe'))"
```

## What bumps what

Pick the tag from the changes since the last release. With Conventional
Commits (already used in this repo) the mapping is:

| Change | Commit prefix | Bump |
|---|---|---|
| Backwards-incompatible (tool removed/renamed, input or output shape changed, new minimum for a runtime dependency) | `feat!:`, `fix!:` or a `BREAKING CHANGE:` footer | MAJOR |
| New backwards-compatible capability | `feat:` | MINOR |
| Backwards-compatible fix | `fix:`, `perf:` | PATCH |
| No user-visible change | `docs:`, `test:`, `chore:`, `ci:`, `build:` (unless it changes requirements) | none |

While the major version is `0`, anything may change (SemVer item 4). This
project treats a breaking change in `0.y.z` as a **minor** bump and
everything else as a **patch** bump. Raising the required `mcp` major
version is a breaking change for people who pin it, so it is a minor bump.

## Cutting a release

`release-draft.yml` keeps one **draft** GitHub Release up to date on every push
to `master`. [git-cliff](https://git-cliff.org) (config: `cliff.toml`) builds
the notes from the Conventional Commit messages since the latest `v*` tag
(grouped as Features / Fixes / Docs / Maintenance / Other) and suggests the
next version from the same prefixes: a breaking change (`type!:` or a
`BREAKING CHANGE:` footer) bumps minor while the major version is `0`,
everything else bumps patch. No pull requests are needed; direct pushes are
fine. Preview locally with `uvx git-cliff --unreleased --bump` and
`uvx git-cliff --bumped-version`.

1. Make sure `master` contains what you want to ship and CI is green.
2. Open **Releases**, review the draft (edit notes or the version if the
   suggestion is wrong; the tag must be a plain `vMAJOR.MINOR.PATCH`) and
   click **Publish release**. This creates the tag on `master` and triggers
   `publish.yml`, which builds, checks the tag, publishes to PyPI and attaches
   Sigstore signatures to the Release.

To retry a failed publish, open the failed run under **Actions → Publish to
PyPI** and use **Re-run failed jobs**; it reuses the release event and tag.

## Guards in CI

`publish.yml` fails the run before anything is uploaded when:

- publishing to PyPI and the ref is not a plain `vMAJOR.MINOR.PATCH` tag
  (pre-release tags such as `v0.3.0rc1` are not accepted by this check; extend
  the regular expression if you start publishing pre-releases);
- the built wheel or sdist version does not match the tag.

`publish.yml` runs in two cases only:

- a GitHub Release is **published**: build, checks, publish to **PyPI**, sign;
- **Run workflow** from the Actions tab (`workflow_dispatch`): build and
  publish to **TestPyPI** only, never PyPI.

Pushes to `master` do not run it.

## Gotchas

- CI must check out with `fetch-depth: 0`; a shallow clone has no tags and
  produces a nonsense version.
- A fork needs the upstream tags (`git fetch upstream --tags`, then push them)
  for its builds to get sensible versions.
- Do not move or delete a tag after it has been released.
- `uv.lock` records the project version as dynamic, so ordinary commits do not
  invalidate `uv sync --locked`.
