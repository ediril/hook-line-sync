from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from hls.selection import FileSelection, SelectionError
from hls.snapshot import EntryKind, TreeEntry, TreeSnapshot

Direction = Literal["push", "pull"]
ComparisonState = Literal[
    "identical",
    "local-only",
    "remote-only",
    "changed",
    "excluded",
    "type-conflict",
    "symlink-conflict",
]
PlanAction = Literal[
    "unchanged",
    "skip",
    "create-remote",
    "upload",
    "replace-remote",
    "replace-local",
    "delete-remote",
    "conflict",
    "excluded",
]


@dataclass(frozen=True)
class ComparisonEntry:
    path: str
    state: ComparisonState
    action: PlanAction
    local_kind: EntryKind | None
    remote_kind: EntryKind | None


@dataclass(frozen=True)
class ComparisonPlan:
    direction: Direction
    prune_remote: bool
    entries: tuple[ComparisonEntry, ...]

    @property
    def differences(self) -> tuple[ComparisonEntry, ...]:
        return tuple(entry for entry in self.entries if entry.action != "unchanged")


def _files_identical(local: TreeEntry, remote: TreeEntry) -> bool:
    if local.size != remote.size:
        return False
    if (
        local.modified_ns is None
        or remote.modified_ns is None
        or local.timestamp_precision_ns is None
        or remote.timestamp_precision_ns is None
    ):
        return False
    precision_ns = max(
        local.timestamp_precision_ns,
        remote.timestamp_precision_ns,
    )
    return (
        local.modified_ns // precision_ns
        == remote.modified_ns // precision_ns
    )


def build_comparison(
    local: TreeSnapshot,
    remote: TreeSnapshot,
    *,
    direction: Direction = "push",
    prune_remote: bool = False,
    selector: FileSelection | None = None,
) -> ComparisonPlan:
    local_entries = {entry.path: entry for entry in local.entries}
    remote_entries = {entry.path: entry for entry in remote.entries}
    comparison: list[ComparisonEntry] = []

    for path in sorted(local_entries.keys() | remote_entries.keys()):
        local_entry = local_entries.get(path)
        remote_entry = remote_entries.get(path)
        if selector is not None and not selector.matches(path):
            continue
        if any(
            entry is not None and entry.excluded
            for entry in (local_entry, remote_entry)
        ):
            comparison.append(
                ComparisonEntry(
                    path=path,
                    state="excluded",
                    action="excluded",
                    local_kind=local_entry.kind if local_entry else None,
                    remote_kind=remote_entry.kind if remote_entry else None,
                )
            )
            continue
        if local_entry is None:
            comparison.append(
                ComparisonEntry(
                    path=path,
                    state="remote-only",
                    action="delete-remote" if prune_remote else "skip",
                    local_kind=None,
                    remote_kind=remote_entry.kind if remote_entry else None,
                )
            )
            continue
        if remote_entry is None:
            if local_entry.kind == "symlink":
                action: PlanAction = "conflict"
            elif direction == "pull":
                action = "skip"
            elif local_entry.kind == "directory":
                action = "create-remote"
            else:
                action = "upload"
            comparison.append(
                ComparisonEntry(
                    path=path,
                    state="local-only",
                    action=action,
                    local_kind=local_entry.kind,
                    remote_kind=None,
                )
            )
            continue
        if local_entry.kind != remote_entry.kind:
            state: ComparisonState = "type-conflict"
            action = "conflict"
        elif local_entry.kind == "symlink":
            state = "symlink-conflict"
            action = "conflict"
        elif local_entry.kind == "directory" or _files_identical(
            local_entry, remote_entry
        ):
            state = "identical"
            action = "unchanged"
        else:
            state = "changed"
            action = "replace-remote" if direction == "push" else "replace-local"
        comparison.append(
            ComparisonEntry(
                path=path,
                state=state,
                action=action,
                local_kind=local_entry.kind,
                remote_kind=remote_entry.kind,
            )
        )

    if selector is not None and not comparison:
        raise SelectionError(
            f"file selector '{selector.pattern}' matched no paths"
        )
    return ComparisonPlan(direction, prune_remote, tuple(comparison))
