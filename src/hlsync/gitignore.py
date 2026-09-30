"""Repository-scoped Git ignores, loaded lazily for profile-relative paths."""

from pathlib import Path, PurePosixPath

from pathspec import GitIgnoreSpec


class GitIgnores:
    def __init__(self, root: Path) -> None:
        self.root = next(
            (
                directory
                for directory in (root, *root.parents)
                if (directory / ".git").is_dir() or (directory / ".git").is_file()
            ),
            root,
        )
        self._profile_prefix = root.relative_to(self.root)
        self._specs: dict[PurePosixPath, GitIgnoreSpec] = {}

    def _spec(self, directory: PurePosixPath) -> GitIgnoreSpec:
        if directory not in self._specs:
            source = self.root.joinpath(*directory.parts, ".gitignore")
            # Like Git, do not follow symlinked ignore files.
            if source.is_symlink():
                lines = []
            else:
                try:
                    lines = source.read_text(
                        encoding="utf-8", errors="surrogateescape"
                    ).splitlines()
                except FileNotFoundError:
                    lines = []
            self._specs[directory] = GitIgnoreSpec.from_lines(lines)
        return self._specs[directory]

    def excludes(self, path: str, *, is_directory: bool = False) -> bool:
        parts = (PurePosixPath(self._profile_prefix) / path).parts
        scopes: list[PurePosixPath] = []
        for depth in range(len(parts)):
            parent = PurePosixPath(*parts[:depth])
            if self.root.joinpath(*parent.parts).is_symlink():
                return False
            scopes.append(parent)
            directory = depth < len(parts) - 1 or is_directory
            ignored = False
            for scope in scopes:
                candidate = PurePosixPath(
                    *parts[len(scope.parts) : depth + 1]
                ).as_posix()
                result = self._spec(scope).check_file(
                    candidate + ("/" if directory else "")
                )
                if result.include is not None:
                    ignored = result.include
            # A negation inside an ignored parent cannot reopen that parent.
            if ignored:
                return True
        return False
