# Releasing HLS

HLS publishes the `hook-line-sync` distribution to PyPI. The installed command
and import package remain `hls`.

## PyPI requirements

Use an existing PyPI account with two-factor authentication and an API token.
Twine prompts for credentials during publication; do not store the token in the
repository.

## Release procedure

1. Set `src/hls/__init__.py` to the next
   `0.<month>.<day>.<increment>` version without leading zeroes.
2. Add a matching dated section to `CHANGELOG.md`.
3. Commit the release changes, tag that commit with exactly `v<version>`, such
   as `v0.8.22.15`, and work from a clean checkout of that tag.
4. With development dependencies installed, run:

   ```console
   python scripts/check_release.py --tag "$(git describe --tags --exact-match)"
   ruff check .
   pytest
   release_root="$(mktemp -d)"
   python -m build --outdir "$release_root/dist"
   python -m twine check "$release_root/dist/"*
   python -m venv "$release_root/venv"
   "$release_root/venv/bin/python" -m pip install "$release_root/dist/"*.whl
   "$release_root/venv/bin/hls" --version
   ```

5. Review the output, then publish the two validated artifacts manually:

   ```console
   python -m twine upload "$release_root/dist/"*
   ```

6. Push the tag, create its GitHub Release, then install the published version
   in a clean environment and run `hls --version` before announcing it.

PyPI does not allow a published version to be replaced. If publication fails
after accepting either artifact, increment the version and create a new
release; do not reuse the failed version.
