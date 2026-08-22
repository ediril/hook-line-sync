import pytest

from hls.comparison import build_comparison
from hls.selection import FileSelector, SelectionError
from hls.snapshot import TreeEntry, TreeSnapshot


def test_comparison_projects_push_pull_prune_and_timestamp_precision() -> None:
    second = 1_700_000_000_000_000_000
    local = TreeSnapshot(
        (
            TreeEntry("assets", "directory"),
            TreeEntry(
                "assets/same.css",
                "file",
                size=10,
                modified_ns=second + 900_000_000,
                timestamp_precision_ns=1,
            ),
            TreeEntry(
                "changed.txt",
                "file",
                size=12,
                modified_ns=second,
                timestamp_precision_ns=1,
            ),
            TreeEntry(
                "conflict",
                "file",
                size=1,
                modified_ns=second,
                timestamp_precision_ns=1,
            ),
            TreeEntry("linked", "symlink"),
            TreeEntry(
                "local.txt",
                "file",
                size=5,
                modified_ns=second,
                timestamp_precision_ns=1,
            ),
        )
    )
    remote = TreeSnapshot(
        (
            TreeEntry("assets", "directory"),
            TreeEntry(
                "assets/same.css",
                "file",
                size=10,
                modified_ns=second,
                timestamp_precision_ns=1_000_000_000,
            ),
            TreeEntry(
                "changed.txt",
                "file",
                size=13,
                modified_ns=second,
                timestamp_precision_ns=1_000_000_000,
            ),
            TreeEntry("conflict", "directory"),
            TreeEntry(
                "remote.txt",
                "file",
                size=6,
                modified_ns=second,
                timestamp_precision_ns=1_000_000_000,
            ),
        )
    )

    push = {entry.path: entry for entry in build_comparison(local, remote).entries}
    pull = {
        entry.path: entry
        for entry in build_comparison(
            local,
            remote,
            direction="pull",
            prune_remote=True,
        ).entries
    }

    assert (push["assets/same.css"].state, push["assets/same.css"].action) == (
        "identical",
        "unchanged",
    )
    assert push["changed.txt"].action == "replace-remote"
    assert pull["changed.txt"].action == "replace-local"
    assert push["local.txt"].action == "upload"
    assert pull["local.txt"].action == "skip"
    assert push["remote.txt"].action == "skip"
    assert pull["remote.txt"].action == "delete-remote"
    assert push["conflict"].action == "conflict"
    assert push["linked"].action == "conflict"

    selected = build_comparison(
        local,
        remote,
        selector=FileSelector("*.txt"),
    )
    assert [entry.path for entry in selected.entries] == [
        "changed.txt",
        "local.txt",
        "remote.txt",
    ]
    with pytest.raises(SelectionError, match="matched no"):
        build_comparison(
            local,
            remote,
            selector=FileSelector("missing/**/*.js"),
        )
