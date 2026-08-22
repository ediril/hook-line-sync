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
3. Commit the release changes. From that clean checkout, with development
   dependencies installed, run:

   ```console
   python scripts/prepare_release.py
   ```

   The script runs the release identity check, lint, tests, isolated package
   build, Twine metadata check, and a clean wheel installation. It places the
   validated wheel and source archive in `dist/<version>/` and prints the exact
   upload command.
4. Review the output, then run the printed command. For example:

   ```console
   python -m twine upload dist/0.8.22.15/*
   ```

5. A Git tag is not required by PyPI. It is strongly recommended for source
   provenance: tag the release commit as `v<version>`, push that tag, and create
   a corresponding GitHub Release.
6. Install the published version in a clean environment and run `hls --version`
   before announcing it.

PyPI does not allow a published version to be replaced. If publication fails
after accepting either artifact, increment the version and create a new
release; do not reuse the failed version.
