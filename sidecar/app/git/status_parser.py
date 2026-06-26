from __future__ import annotations

from app.schemas.repositories import ChangedPath


def parse_porcelain_v1_z(
    raw: str,
) -> tuple[
    list[ChangedPath],
    list[ChangedPath],
    list[ChangedPath],
    list[ChangedPath],
]:
    staged: list[ChangedPath] = []
    modified: list[ChangedPath] = []
    untracked: list[ChangedPath] = []
    conflicts: list[ChangedPath] = []

    entries = raw.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue

        if entry.startswith("?? "):
            untracked.append(
                ChangedPath(path=entry[3:], index_status="?", worktree_status="?", kind="untracked")
            )
            continue

        if len(entry) < 4:
            continue

        status = entry[:2]
        path = entry[3:]

        # Rename/copy records have a second NUL-separated old path. It is not used in Phase 1.
        if "R" in status or "C" in status:
            index += 1

        item = ChangedPath(
            path=path,
            index_status=status[0],
            worktree_status=status[1],
            kind="modified",
        )

        if "U" in status or status in {"AA", "DD"}:
            item.kind = "conflict"
            conflicts.append(item)
            continue

        if status[0] != " ":
            item.kind = "staged"
            staged.append(item)
        if status[1] != " ":
            modified.append(item)

    return staged, modified, untracked, conflicts


def parse_branch_headers(raw: str) -> tuple[str | None, str | None, int, int]:
    branch: str | None = None
    upstream: str | None = None
    ahead = 0
    behind = 0

    for line in raw.splitlines():
        if line.startswith("# branch.head "):
            candidate = line.removeprefix("# branch.head ").strip()
            branch = None if candidate == "(detached)" else candidate
        elif line.startswith("# branch.upstream "):
            upstream = line.removeprefix("# branch.upstream ").strip() or None
        elif line.startswith("# branch.ab "):
            parts = line.removeprefix("# branch.ab ").split()
            for part in parts:
                if part.startswith("+"):
                    ahead = int(part[1:])
                elif part.startswith("-"):
                    behind = int(part[1:])

    return branch, upstream, ahead, behind
