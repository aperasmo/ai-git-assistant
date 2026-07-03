from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.errors import GitCommandError, ValidationFailure
from app.git.client import GitClient
from app.git.remote_provider import detect_remote_provider
from app.git.status_parser import parse_branch_headers, parse_porcelain_v1_z
from app.schemas.repositories import BranchInfo, RemoteProviderInfo, RepositorySnapshot

IN_PROGRESS_MARKERS = {
    "MERGE_HEAD": (
        "A merge is in progress. Resolve it in your normal Git workflow before write actions."
    ),
    "CHERRY_PICK_HEAD": (
        "A cherry-pick is in progress. Resolve it in your normal Git workflow before write actions."
    ),
    "REVERT_HEAD": (
        "A revert is in progress. Resolve it in your normal Git workflow before write actions."
    ),
    "BISECT_LOG": (
        "A bisect is in progress. Resolve it in your normal Git workflow before write actions."
    ),
}


@dataclass(frozen=True)
class RepositoryInspection:
    canonical_path: Path
    snapshot: RepositorySnapshot

@dataclass(frozen=True)
class FolderClassification:
    kind: str
    selected_path: Path
    repository_root: Path | None
    can_initialise: bool
    message: str | None = None

class RepositoryInspector:

    def classify_selected_folder(
        self,
        selected_path: str | Path,
    ) -> FolderClassification:
        path = Path(selected_path).expanduser().resolve()

        if not path.exists() or not path.is_dir():
            raise ValidationFailure("Choose an existing folder.")

        client = GitClient(path)
        probe = client.run(
            ["rev-parse", "--show-toplevel"],
            allow_failure=True,
        )

        if probe.return_code == 0:
            try:
                repository_root = self.canonicalise_and_validate(path)
            except ValidationFailure:
                return FolderClassification(
                    kind="unsupported_repository",
                    selected_path=path,
                    repository_root=None,
                    can_initialise=False,
                    message=(
                        "This folder has Git metadata but is not a supported "
                        "Git working tree in v1."
                    ),
                )

            if path == repository_root:
                return FolderClassification(
                    kind="existing_repository",
                    selected_path=path,
                    repository_root=repository_root,
                    can_initialise=False,
                )

            return FolderClassification(
                kind="nested_repository",
                selected_path=path,
                repository_root=repository_root,
                can_initialise=False,
                message=(
                    "The selected folder belongs to a parent Git repository. "
                    "Add the repository root instead."
                ),
            )

        # Only offer initialisation for a known normal non-repository folder.
        # Any other Git failure, or detected Git metadata, remains blocked so
        # the application never runs git init over a damaged repository state.
        if "not a git repository" not in probe.stderr.lower():
            return FolderClassification(
                kind="unsupported_repository",
                selected_path=path,
                repository_root=None,
                can_initialise=False,
                message="Git could not safely inspect the selected folder.",
            )

        git_metadata = self._find_git_metadata(path)
        if git_metadata is not None:
            return FolderClassification(
                kind="unsupported_repository",
                selected_path=path,
                repository_root=None,
                can_initialise=False,
                message=(
                    "Git metadata was found in or above this folder, but the "
                    "repository is not a supported working tree."
                ),
            )

        return FolderClassification(
            kind="initialisation_required",
            selected_path=path,
            repository_root=None,
            can_initialise=True,
            message="This folder is not a Git repository yet.",
        )    
    def canonicalise_and_validate(self, selected_path: str | Path) -> Path:
        path = Path(selected_path).expanduser().resolve()

        if not path.exists() or not path.is_dir():
            raise ValidationFailure("Choose an existing folder.")

        client = GitClient(path)
        try:
            top_level = Path(client.rev_parse("--show-toplevel")).resolve()

            # Git may return relative metadata paths based on the selected
            # subfolder. Use the discovered repository root for all later
            # repository-level checks so those paths resolve consistently.
            repository_client = GitClient(top_level)

            inside = repository_client.rev_parse("--is-inside-work-tree")
            bare = repository_client.rev_parse("--is-bare-repository")
        except GitCommandError as exc:
            raise ValidationFailure(
                "The selected folder is not a standard Git working tree."
            ) from exc

        if inside != "true" or bare == "true":
            raise ValidationFailure("Only standard non-bare Git working trees are supported in v1.")

        # Ask Git for canonical absolute paths rather than resolving its
        # relative output ourselves. This keeps normal repositories and linked
        # worktrees distinguishable regardless of the selected subfolder.
        git_dir = Path(
            repository_client.run(
                ["rev-parse", "--absolute-git-dir"]
            ).stdout.strip()
        ).resolve()

        common_dir = Path(
            repository_client.run(
                ["rev-parse", "--path-format=absolute", "--git-common-dir"]
            ).stdout.strip()
        ).resolve()

        if git_dir != common_dir:
            raise ValidationFailure("Linked Git worktrees are not supported in v1.")

        if (top_level / ".gitmodules").exists():
            raise ValidationFailure("Repositories with submodules are not supported in v1.")

        return top_level

    def inspect(
        self,
        repository_id: str,
        canonical_path: Path,
        *,
        remote_last_refreshed_at: str | None,
    ) -> RepositoryInspection:
        client = GitClient(canonical_path)
        # Re-run minimal validity checks because a repository can change outside the application.
        self.canonicalise_and_validate(canonical_path)

        head = self._optional_rev_parse(client, "HEAD")
        porcelain_v1 = client.status_porcelain_v1_z()
        porcelain_v2 = client.status_porcelain_v2_branch()
        branch, upstream, ahead, behind = parse_branch_headers(porcelain_v2)
        staged, modified, untracked, conflicts = parse_porcelain_v1_z(porcelain_v1)

        git_dir = self._resolve_git_directory(client, canonical_path, "--git-dir")
        write_blocked_reason = self._write_block_reason(git_dir, conflicts)

        upstream_remote: str | None = None
        upstream_branch: str | None = upstream
        if upstream and "/" in upstream:
            upstream_remote = upstream.split("/", 1)[0]

        remote_names = client.remote_list()
        remote_urls = client.remote_url_map()
        remote_providers = self._detect_remote_providers(remote_names, remote_urls)
        local_branches = self._parse_branch_list(client.branch_list())

        snapshot = RepositorySnapshot(
            repository_id=repository_id,
            branch=branch,
            head_commit=head,
            upstream_remote=upstream_remote,
            upstream_branch=upstream_branch,
            staged_changes=staged,
            modified_changes=modified,
            untracked_paths=untracked,
            conflicts=conflicts,
            ahead=ahead,
            behind=behind,
            remote_last_refreshed_at=remote_last_refreshed_at,
            write_blocked_reason=write_blocked_reason,
            remote_names=remote_names,
            remote_urls=remote_urls,
            remote_providers=remote_providers,
            local_branches=local_branches,
            fingerprint=self._fingerprint(
                head=head,
                branch=branch,
                porcelain_v2=porcelain_v2,
                write_blocked_reason=write_blocked_reason,
            ),
        )
        return RepositoryInspection(canonical_path=canonical_path, snapshot=snapshot)

    @staticmethod
    def _detect_remote_providers(
        remote_names: list[str],
        remote_urls: dict[str, str],
    ) -> list[RemoteProviderInfo]:
        providers: list[RemoteProviderInfo] = []
        for remote in remote_names:
            url = remote_urls.get(remote)
            if url:
                detection = detect_remote_provider(url)
                providers.append(
                    RemoteProviderInfo(
                        remote=remote,
                        provider=detection.provider,
                        label=detection.label,
                        host=detection.host,
                        url=url,
                    )
                )
            else:
                providers.append(
                    RemoteProviderInfo(
                        remote=remote,
                        provider="unknown",
                        label="Unknown",
                        host=None,
                        url=None,
                    )
                )
        return providers

    @staticmethod
    def _parse_branch_list(raw: str) -> list[BranchInfo]:
        branches: list[BranchInfo] = []
        for line in raw.splitlines():
            if not line:
                continue
            fields = line.split("\t", 2)
            if len(fields) < 2:
                continue
            head_marker, name = fields[0], fields[1]
            upstream = fields[2] if len(fields) > 2 and fields[2] else None
            branches.append(BranchInfo(name=name, is_current=head_marker == "*", upstream=upstream))
        return branches

    @staticmethod
    def _find_git_metadata(path: Path) -> Path | None:
        # A .git directory or file can indicate an existing, damaged, or
        # unusual repository state. Do not offer git init in that situation.
        ceilings = {
            Path(value).expanduser().resolve()
            for value in os.environ.get("GIT_CEILING_DIRECTORIES", "").split(os.pathsep)
            if value
        }

        for candidate in (path, *path.parents):
            if candidate.resolve() in ceilings:
                break
            git_metadata = candidate / ".git"
            if git_metadata.exists():
                return git_metadata

        return None

    @staticmethod
    def _resolve_git_directory(client: GitClient, base_path: Path, argument: str) -> Path:
        raw_path = Path(client.rev_parse(argument))
        if raw_path.is_absolute():
            return raw_path.resolve()
        return (base_path / raw_path).resolve()

    @staticmethod
    def _optional_rev_parse(client: GitClient, argument: str) -> str | None:
        result = client.run(["rev-parse", argument], allow_failure=True)
        return result.stdout.strip() or None

    @staticmethod
    def _write_block_reason(git_dir: Path, conflicts: list[object]) -> str | None:
        if conflicts:
            return (
                "Unresolved conflicts detected. Write actions will remain blocked until resolved."
            )

        for marker, message in IN_PROGRESS_MARKERS.items():
            if (git_dir / marker).exists():
                return message

        rebase_merge = git_dir / "rebase-merge"
        rebase_apply = git_dir / "rebase-apply"
        if rebase_merge.exists() or rebase_apply.exists():
            return (
                "A rebase is in progress. Resolve it in your normal Git workflow before "
                "write actions."
            )

        return None

    @staticmethod
    def _fingerprint(
        *,
        head: str | None,
        branch: str | None,
        porcelain_v2: str,
        write_blocked_reason: str | None,
    ) -> str:
        canonical_state = {
            "head": head,
            "branch": branch,
            "status": porcelain_v2,
            "write_blocked_reason": write_blocked_reason,
        }
        return hashlib.sha256(
            json.dumps(canonical_state, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


def display_path_label(path: Path) -> str:
    home = Path.home().resolve()
    try:
        return f"~/{path.resolve().relative_to(home).as_posix()}"
    except ValueError:
        return path.name


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
