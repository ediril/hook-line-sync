import pytest

from hlsync.gitignore import GitIgnores


@pytest.mark.parametrize("worktree", [False, True])
def test_subdirectory_profile_uses_repository_scopes(tmp_path, worktree):
    repo = tmp_path / "repo"
    profile = repo / "site/public"
    profile.mkdir(parents=True)
    marker = repo / ".git"
    if worktree:
        marker.write_text("gitdir: /unused/worktree/metadata\n")
    else:
        marker.mkdir()
    (tmp_path / ".gitignore").write_text("outside.txt\n")
    (repo / ".gitignore").write_text(
        "/site/public/notes/\n/root-only.txt\n*.log\n"
    )
    (repo / "site/.gitignore").write_text("!keep.log\n")
    (profile / ".gitignore").write_text("!notes/\nlocal.tmp\n")

    rules = GitIgnores(profile)
    assert rules.excludes("error.log")
    assert not rules.excludes("keep.log")
    assert not rules.excludes("root-only.txt")
    assert not rules.excludes("outside.txt")
    assert not rules.excludes("notes", is_directory=True)
    assert rules.excludes("local.tmp")

    # Ignoring the mapped directory itself still excludes its descendants.
    (repo / ".gitignore").write_text("/site/public/\n")
    assert GitIgnores(profile).excludes("notes/index.php")
