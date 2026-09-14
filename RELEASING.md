# Releasing HLSync

HLSync publishes the `hook-line-sync` distribution to PyPI. The installed
command and import package are both `hlsync`.

## PyPI requirements

Use an existing PyPI account with two-factor authentication and an API token.
Twine uses credentials from `~/.pypirc` or `TWINE_USERNAME`/`TWINE_PASSWORD`,
and prompts if needed. Do not store the token in the repository.

## Release procedure

1. Set `src/hlsync/__init__.py` to the next
   `0.<month>.<day>.<increment>` version without leading zeroes.
2. Add a matching dated section to `CHANGELOG.md`.
3. Commit the release changes. From that clean checkout, with development
   dependencies installed, run:

   ```console
   ./scripts/publish.sh
   ```

   The script uses the repository's `.venv/bin/python` when available, otherwise
   `python3`; set `PYTHON` to select another interpreter. It builds through
   `prepare_release.py`, which runs identity checks, lint, tests, isolated builds,
   metadata checks, and a clean wheel installation, then uploads both artifacts.
   If `dist/<version>/` already exists, it reuses those prepared artifacts after
   checking their metadata. Bump the version when releasing new source changes;
   existing artifacts are not rebuilt automatically.

   To prepare artifacts without publishing, run `python scripts/prepare_release.py`.

4. A Git tag is not required by PyPI. It is strongly recommended for source
   provenance: tag the release commit as `v<version>`, push that tag, and create
   a corresponding GitHub Release.
5. Install the published version in a clean environment and run `hlsync --version`
   before announcing it.

PyPI does not allow a published version to be replaced. If publication fails
after accepting either artifact, increment the version and create a new
release; do not reuse the failed version.
