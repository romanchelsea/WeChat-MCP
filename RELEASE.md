# Release process

Releases are cut from `master`. The version comes from git tags (`vMAJOR.MINOR.PATCH`) via hatch-vcs, so there is no version to edit in `pyproject.toml`. Details and background are in [docs/releasing.md](docs/releasing.md).

## How it works

1. **Push to `master`** (Conventional Commits, direct pushes are fine).
   `release-draft.yml` runs [git-cliff](https://git-cliff.org) and keeps one **draft** GitHub Release up to date, with notes from the commits since the last tag and the suggested next version.
2. **Publish the draft** on the Releases page. This creates the tag on `master`.
3. **Publishing triggers `publish.yml`**, which builds the package, checks that the tag is plain `vX.Y.Z` and matches the built version, uploads to **PyPI** (trusted publishing, no stored token), then signs the files with Sigstore and attaches them to the Release.

## Next version

| Commits since the last tag | Bump (while major is `0`) |
|---|---|
| `fix:`, `docs:`, `chore:`, `feat:`, anything else | patch |
| `type!:` or a `BREAKING CHANGE:` footer | minor |

Preview locally: `uvx git-cliff --unreleased --bump` (notes) and `uvx git-cliff --bumped-version` (version). Rules live in [cliff.toml](cliff.toml).

## Cutting a release

1. Check that `master` has what you want to ship.
2. Open **Releases**, review the draft notes and tag (edit if needed; must stay `vMAJOR.MINOR.PATCH`).
3. Click **Publish release**.
4. Watch **Actions → Publish to PyPI**, then check the new version at <https://pypi.org/project/wechat-mcp-xiongwe/>.

PyPI versions cannot be replaced. If a release is bad, yank it on PyPI and publish a new patch version.

## Other runs

- **Retry a failed publish:** Actions → the failed run → **Re-run failed jobs**.
- **Test build on TestPyPI:** Actions → Publish to PyPI → **Run workflow**. This never touches PyPI.
- Pushes to `master` do not publish anything; they only update the draft.

## One-time setup

- PyPI and TestPyPI trusted publishers for `wechat-mcp-xiongwe`: this repo, workflow `publish.yml`, environments `pypi` and `testpypi`.
- GitHub environments `pypi` and `testpypi`, ideally with a required reviewer on `pypi`.
