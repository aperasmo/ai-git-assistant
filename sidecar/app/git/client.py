from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.errors import GitCommandError


_EMPTY_TREE_HASH = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def _hidden_subprocess_flags() -> int:
    if os.name == "nt":
        return subprocess.CREATE_NO_WINDOW
    return 0


@dataclass(frozen=True)
class GitResult:
    stdout: str
    stderr: str
    return_code: int


@dataclass(frozen=True)
class GitHttpAuth:
    username: str
    password: str


class GitClient:
    def __init__(self, repository_path: Path | None = None) -> None:
        self.repository_path = repository_path

    def run(
        self,
        args: Sequence[str],
        *,
        timeout_seconds: int = 20,
        allow_failure: bool = False,
        http_auth: GitHttpAuth | None = None,
    ) -> GitResult:
        command = ["git", *args]
        environment = os.environ.copy()
        environment.update(
            {
                # The desktop application must never open an uncontrolled Git
                # credential or editor prompt. Existing Git Credential Manager
                # or SSH authentication remains available to Git itself.
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_PAGER": "cat",
                "PAGER": "cat",
                "LC_ALL": "C",
            }
        )
        askpass_path: Path | None = None
        if http_auth is not None:
            askpass_path = self._write_askpass_helper()
            environment.update(
                {
                    "GIT_ASKPASS": str(askpass_path),
                    "TM_GIT_USERNAME": http_auth.username,
                    "TM_GIT_PASSWORD": http_auth.password,
                }
            )

        try:
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(self.repository_path) if self.repository_path else None,
                    shell=False,
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_seconds,
                    env=environment,
                    creationflags=_hidden_subprocess_flags(),
                )
            except FileNotFoundError as exc:
                raise GitCommandError("Git was not found on PATH.", status_code=503) from exc
            except subprocess.TimeoutExpired as exc:
                raise GitCommandError("Git command timed out.") from exc

            result = GitResult(
                stdout=completed.stdout,
                stderr=completed.stderr,
                return_code=completed.returncode,
            )

            if completed.returncode != 0 and not allow_failure:
                raise GitCommandError(self._safe_error(result))

            return result
        finally:
            if askpass_path is not None:
                try:
                    askpass_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _write_askpass_helper() -> Path:
        """Create a short-lived helper that returns credentials from env vars."""
        if os.name == "nt":
            content = (
                "@echo off\r\n"
                "echo %* | findstr /I \"username\" >nul\r\n"
                "if %ERRORLEVEL% EQU 0 (\r\n"
                "  echo %TM_GIT_USERNAME%\r\n"
                ") else (\r\n"
                "  echo %TM_GIT_PASSWORD%\r\n"
                ")\r\n"
            )
            suffix = ".cmd"
        else:
            content = (
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "  *sername*|*Username*) printf '%s\\n' \"$TM_GIT_USERNAME\" ;;\n"
                "  *) printf '%s\\n' \"$TM_GIT_PASSWORD\" ;;\n"
                "esac\n"
            )
            suffix = ".sh"

        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=suffix, delete=False)
        try:
            handle.write(content)
            path = Path(handle.name)
        finally:
            handle.close()
        if os.name != "nt":
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    @staticmethod
    def _safe_error(result: GitResult) -> str:
        raw = "\n".join(part for part in (result.stderr, result.stdout) if part).strip()
        if not raw:
            raw = "Git command failed."
        lines = raw.splitlines()
        # Git can print transfer lines such as "From <remote>" before the
        # actionable failure. Prefer the line that explains what blocked.
        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()
            if not stripped or lower.startswith("warning:") or lower.startswith("hint:"):
                continue
            if (
                lower.startswith("fatal:")
                or lower.startswith("error:")
                or "[rejected]" in lower
                or "failed to push some refs" in lower
                or "not possible to fast-forward" in lower
                or "automatic merge failed" in lower
            ):
                return stripped[:500]

        # Skip advisory lines so the real error is always visible.
        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()
            if (
                stripped
                and not lower.startswith("warning:")
                and not lower.startswith("hint:")
                and not lower.startswith("from ")
                and not lower.startswith("to ")
            ):
                return stripped[:500]
        # All lines were warnings/hints — fall back to the first non-empty line.
        fallback = next((l.strip() for l in lines if l.strip()), "Git command failed.")
        return fallback[:500]

    def version(self) -> str:
        return self.run(["--version"]).stdout.strip()

    def rev_parse(self, argument: str) -> str:
        return self.run(["rev-parse", argument]).stdout.strip()

    def initialise_repository(self, initial_branch: str) -> GitResult:
        # Repository creation is an explicit write operation. Keep it inside the
        # Git client so it uses the same non-interactive, argument-array execution
        # boundary as every other Git command in the application.
        result = self.run(["init", "-b", initial_branch], allow_failure=True)
        if result.return_code == 0:
            return result

        combined = f"{result.stderr}\n{result.stdout}".lower()
        if "unknown switch `b'" not in combined and "unknown switch 'b'" not in combined:
            raise GitCommandError(self._safe_error(result))

        fallback = self.run(["init"])
        if initial_branch:
            self.run(["symbolic-ref", "HEAD", f"refs/heads/{initial_branch}"])
        return fallback

    def status_porcelain_v1_z(self) -> str:
        return self.run(["status", "--porcelain=v1", "--untracked-files=all", "-z"]).stdout

    def status_porcelain_v2_branch(self) -> str:
        return self.run(["status", "--porcelain=v2", "--branch", "--untracked-files=all"]).stdout

    def log(self, limit: int) -> str:
        bounded_limit = max(1, min(limit, 50))
        return self.run(
            [
                "log",
                f"-n{bounded_limit}",
                "--format=%H%x1f%h%x1f%an%x1f%aI%x1f%s%x1e",
            ]
        ).stdout

    def commit_graph(self, limit: int = 40) -> str:
        bounded_limit = max(1, min(limit, 80))
        return self.run(
            [
                "log",
                "--graph",
                "--decorate",
                "--oneline",
                "--all",
                f"-n{bounded_limit}",
            ]
        ).stdout

    def file_history(self, path: str, limit: int = 30) -> str:
        bounded_limit = max(1, min(limit, 50))
        return self.run(
            [
                "log",
                "--follow",
                f"-n{bounded_limit}",
                "--format=%H%x1f%h%x1f%an%x1f%aI%x1f%s%x1e",
                "--",
                path,
            ]
        ).stdout

    def blame(self, path: str) -> str:
        return self.run(["blame", "--date=short", "--", path]).stdout

    def branch_list(self) -> str:
        # Git ref-filter formatting uses %09 for a literal tab. One branch is
        # emitted per line, allowing the service to preserve the HEAD marker.
        return self.run(
            ["branch", "--format=%(HEAD)%09%(refname:short)%09%(upstream:short)"]
        ).stdout

    def diff_stat(self, scope: str = "all") -> str:
        if scope == "staged":
            arguments = ["diff", "--cached", "--no-ext-diff", "--stat"]
        elif scope == "unstaged":
            arguments = ["diff", "--no-ext-diff", "--stat"]
        else:
            arguments = ["diff", "HEAD", "--no-ext-diff", "--stat"]
        return self.run(arguments).stdout

    def diff_check(self, scope: str = "unstaged") -> str:
        arguments = ["diff"]
        if scope == "staged":
            arguments.append("--cached")
        arguments.extend(["--no-ext-diff", "--check"])
        return self.run(arguments).stdout

    def diff_patch(self, scope: str = "all") -> str:
        if scope == "staged":
            arguments = ["diff", "--cached", "--no-ext-diff", "--find-renames", "--patch"]
        elif scope == "unstaged":
            arguments = ["diff", "--no-ext-diff", "--find-renames", "--patch"]
        else:
            arguments = ["diff", "HEAD", "--no-ext-diff", "--find-renames", "--patch"]
        return self.run(arguments).stdout

    def diff_patch_for_paths(self, paths: Sequence[str]) -> str:
        if not paths:
            return self.diff_patch("all")
        return self.run(
            [
                "diff",
                self._working_tree_diff_base(),
                "--no-ext-diff",
                "--find-renames",
                "--patch",
                "--",
                *paths,
            ],
            allow_failure=True,
        ).stdout

    def diff_numstat_for_paths(self, paths: Sequence[str]) -> str:
        if not paths:
            return ""
        return self.run(
            [
                "diff",
                self._working_tree_diff_base(),
                "--no-ext-diff",
                "--numstat",
                "--",
                *paths,
            ],
            allow_failure=True,
        ).stdout

    def _working_tree_diff_base(self) -> str:
        """Use Git's empty tree when an initial repository has no HEAD commit."""
        head = self.run(
            ["rev-parse", "--verify", "HEAD^{commit}"],
            allow_failure=True,
        )
        return "HEAD" if head.return_code == 0 else _EMPTY_TREE_HASH

    def fetch_prune(self, *, http_auth: GitHttpAuth | None = None) -> GitResult:
        return self.run(["fetch", "--prune"], timeout_seconds=45, http_auth=http_auth)

    def stage_paths(self, paths: Sequence[str]) -> GitResult:
        if not paths:
            raise GitCommandError("No file paths were selected for staging.")

        result = self.run(["add", "--", *paths], allow_failure=True)
        if result.return_code == 0:
            return result

        combined = result.stderr + result.stdout
        # Non-zero exit caused only by CRLF/autocrlf warnings — treat as success.
        non_advisory = [
            l for l in combined.splitlines()
            if l.strip() and not l.strip().lower().startswith(("warning:", "hint:"))
        ]
        if not non_advisory:
            return result

        if "does not have a commit checked out" in combined:
            # Nested git repositories cannot be staged as regular files.
            # Extract the offending directory prefix and retry without it.
            nested = set()
            for line in combined.splitlines():
                m = re.search(r"error: '([^']+)' does not have a commit checked out", line)
                if m:
                    nested.add(m.group(1).rstrip("/\\"))
            stageable = [
                p for p in paths
                if not any(p == n or p.startswith(n + "/") or p.startswith(n + "\\") for n in nested)
            ]
            if not stageable:
                raise GitCommandError("No files could be staged — nested repositories were skipped.")
            return self.run(["add", "--", *stageable])

        if "ignored by one of your .gitignore files" not in combined:
            raise GitCommandError(self._safe_error(result))

        # Some paths became gitignore-excluded since the snapshot was taken.
        # Batch-check all paths and retry with only the stageable subset.
        ignored = self._check_ignored_batch(paths)
        stageable = [p for p in paths if p not in ignored]
        if not stageable:
            raise GitCommandError(
                "All selected files are excluded by .gitignore rules. "
                "Refresh the file list and try again."
            )
        return self.run(["add", "--", *stageable])

    def _check_ignored_batch(self, paths: Sequence[str]) -> set[str]:
        """Return the set of paths that are gitignore-excluded."""
        command = ["git", "check-ignore", "--stdin"]
        environment = os.environ.copy()
        environment.update({"GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat", "PAGER": "cat", "LC_ALL": "C"})
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.repository_path) if self.repository_path else None,
                shell=False,
                check=False,
                input="\n".join(paths),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                env=environment,
                creationflags=_hidden_subprocess_flags(),
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return set()
        return {line.strip() for line in completed.stdout.splitlines() if line.strip()}

    def commit(self, message: str) -> GitResult:
        # The message is passed as one subprocess argument, never concatenated
        # into a shell command. -m also prevents Git from opening an editor.
        return self.run(["commit", "-m", message], timeout_seconds=45)

    def resolve_commit(self, revision: str) -> str:
        return self.run(["rev-parse", "--verify", f"{revision}^{{commit}}"]).stdout.strip()

    def commit_parent_count(self, revision: str) -> int:
        line = self.run(["rev-list", "--parents", "-n", "1", revision]).stdout.strip()
        return max(0, len(line.split()) - 1)

    def revert_commit(self, commit_hash: str) -> GitResult:
        result = self.run(["revert", "--no-edit", commit_hash], timeout_seconds=90, allow_failure=True)
        if result.return_code == 0:
            return result
        combined = f"{result.stderr}\n{result.stdout}".strip()
        if "conflict" in combined.lower():
            # Keep the reviewed operation atomic. A failed revert must not leave
            # the repository stuck in an in-progress sequencer state.
            self.run(["revert", "--abort"], allow_failure=True)
            raise GitCommandError(
                "Revert would cause conflicts, so AI Git Assistant aborted it and restored the pre-revert state."
            )
        raise GitCommandError(self._safe_error(result))

    def remote_list(self) -> list[str]:
        result = self.run(["remote"], allow_failure=True)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def remote_url_map(self) -> dict[str, str]:
        """Return {name: fetch_url} for all remotes (one git remote -v call)."""
        result = self.run(["remote", "-v"], allow_failure=True)
        urls: dict[str, str] = {}
        for line in result.stdout.splitlines():
            # e.g.  origin  https://github.com/user/repo.git (fetch)
            if "(fetch)" not in line:
                continue
            parts = line.split(None, 2)
            if len(parts) >= 2:
                urls[parts[0]] = parts[1]
        return urls

    def remote_verbose(self) -> str:
        return self.run(["remote", "-v"], allow_failure=True).stdout

    def tag_list(self) -> str:
        return self.run(
            [
                "tag",
                "--list",
                "--sort=-creatordate",
                "--format=%(refname:short)%09%(creatordate:iso8601)%09%(subject)",
            ],
            allow_failure=True,
        ).stdout

    def tag_show(self, tag_name: str) -> str:
        return self.run(
            [
                "show",
                "--stat",
                "--decorate",
                "--no-ext-diff",
                "--format=fuller",
                tag_name,
            ]
        ).stdout

    def create_annotated_tag(self, tag_name: str, message: str) -> GitResult:
        return self.run(["tag", "-a", tag_name, "-m", message])

    def delete_tag(self, tag_name: str) -> GitResult:
        return self.run(["tag", "-d", tag_name])

    def push_tag(self, remote: str, tag_name: str, *, http_auth: GitHttpAuth | None = None) -> GitResult:
        return self.run(
            ["push", "--porcelain", remote, f"refs/tags/{tag_name}:refs/tags/{tag_name}"],
            timeout_seconds=90,
            http_auth=http_auth,
        )

    def push_current_head(
        self,
        remote: str,
        branch: str,
        *,
        http_auth: GitHttpAuth | None = None,
    ) -> GitResult:
        # Intentionally non-force; pins the remote ref previewed to the user.
        return self.run(
            ["push", "--porcelain", remote, f"HEAD:refs/heads/{branch}"],
            timeout_seconds=90,
            http_auth=http_auth,
        )

    def pull_ff_only(self, *, http_auth: GitHttpAuth | None = None) -> GitResult:
        return self.run(["pull", "--ff-only"], timeout_seconds=60, http_auth=http_auth)

    def set_upstream(self, remote: str, branch: str) -> GitResult:
        return self.run(["branch", "--set-upstream-to", f"{remote}/{branch}", branch])

    def restore_staged(self, paths: Sequence[str]) -> GitResult:
        if not paths:
            raise GitCommandError("No file paths were selected for unstaging.")
        return self.run(["restore", "--staged", "--", *paths])

    def restore_working_tree(self, paths: Sequence[str]) -> GitResult:
        if not paths:
            raise GitCommandError("No file paths were selected for discard.")
        return self.run(["restore", "--", *paths])

    def switch_branch(self, name: str) -> GitResult:
        return self.run(["switch", name])

    def create_and_switch_branch(self, name: str) -> GitResult:
        return self.run(["switch", "-c", name])

    def rename_branch(self, name: str) -> GitResult:
        result = self.run(["branch", "-M", name], allow_failure=True)
        # "already exists" means we're already on that branch — treat as success.
        if result.return_code == 0 or "already exists" in (result.stderr + result.stdout):
            return result
        raise GitCommandError(self._safe_error(result))

    def remote_add(self, name: str, url: str) -> GitResult:
        return self.run(["remote", "add", name, url])

    def clone(self, url: str, target_path: Path) -> GitResult:
        return self.run(["clone", url, str(target_path)], timeout_seconds=300)

    def worktree_add(self, target_path: Path, branch_name: str, base_ref: str) -> GitResult:
        return self.run(
            ["worktree", "add", "-b", branch_name, str(target_path), base_ref],
            timeout_seconds=120,
        )

    def worktree_remove(self, target_path: Path, *, force: bool = False) -> GitResult:
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(str(target_path))
        return self.run(args, timeout_seconds=90)

    def branch_delete_force(self, name: str) -> GitResult:
        return self.run(["branch", "-D", name], allow_failure=True)

    def rev_list_count(self, revision_range: str) -> int:
        result = self.run(["rev-list", "--count", revision_range], allow_failure=True)
        try:
            return int(result.stdout.strip() or "0")
        except ValueError:
            return 0

    def short_status(self) -> str:
        return self.run(["status", "--short"], allow_failure=True).stdout

    def last_commit_oneline(self) -> str:
        return self.run(["log", "-1", "--oneline"], allow_failure=True).stdout.strip()

    def compare_name_status(self, base_ref: str, branch_name: str) -> str:
        return self.run(
            ["diff", "--name-status", f"{base_ref}...{branch_name}"],
            allow_failure=True,
        ).stdout

    def compare_stat(self, base_ref: str, branch_name: str) -> str:
        return self.run(
            ["diff", "--stat", f"{base_ref}...{branch_name}"],
            allow_failure=True,
        ).stdout

    def log_range_oneline(self, revision_range: str) -> str:
        return self.run(["log", "--oneline", revision_range], allow_failure=True).stdout

    def remote_branch_exists(
        self,
        remote: str,
        branch: str,
        *,
        http_auth: GitHttpAuth | None = None,
    ) -> bool:
        result = self.run(
            ["ls-remote", "--heads", remote, branch],
            timeout_seconds=60,
            allow_failure=True,
            http_auth=http_auth,
        )
        return bool(result.stdout.strip())

    def stash_push(self, message: str | None = None) -> GitResult:
        args: list[str] = ["stash", "push", "--include-untracked"]
        if message:
            args.extend(["-m", message])
        result = self.run(args, allow_failure=True)
        if result.return_code == 0:
            return result
        # Fall back without --include-untracked (e.g. Windows reserved filenames like nul)
        args_fallback: list[str] = ["stash", "push"]
        if message:
            args_fallback.extend(["-m", message])
        return self.run(args_fallback)

    def stash_pop(self) -> GitResult:
        return self.run(["stash", "pop"])

    def stash_list(self) -> str:
        return self.run(["stash", "list", "--format=%gd%x1f%cr%x1f%gs%x1e"], allow_failure=True).stdout

    def stash_show_patch(self, stash_ref: str) -> str:
        return self.run(["stash", "show", "--patch", "--stat", "--no-ext-diff", stash_ref]).stdout

    def stash_apply(self, stash_ref: str) -> GitResult:
        return self.run(["stash", "apply", stash_ref])

    def stash_drop(self, stash_ref: str) -> GitResult:
        return self.run(["stash", "drop", stash_ref])

    def delete_branch(self, name: str) -> GitResult:
        return self.run(["branch", "-d", name])

    def merge_branch(self, name: str) -> GitResult:
        result = self.run(["merge", "--no-edit", name], timeout_seconds=90, allow_failure=True)
        if result.return_code == 0:
            return result
        combined = (result.stderr + "\n" + result.stdout).strip()
        if "automatic merge failed" in combined.lower() or "conflict" in combined.lower():
            raise GitCommandError(combined[:1000])
        raise GitCommandError(self._safe_error(result))

    def merge_branch_no_ff(self, name: str, message: str) -> GitResult:
        result = self.run(
            ["merge", "--no-ff", name, "-m", message],
            timeout_seconds=120,
            allow_failure=True,
        )
        if result.return_code == 0:
            return result
        combined = (result.stderr + "\n" + result.stdout).strip()
        if "automatic merge failed" in combined.lower() or "conflict" in combined.lower():
            raise GitCommandError(combined[:1000])
        raise GitCommandError(self._safe_error(result))

    def merge_abort(self) -> GitResult:
        return self.run(["merge", "--abort"])

    def merge_commit(self) -> GitResult:
        return self.run(["commit", "--no-edit"], timeout_seconds=45)

    def push_with_set_upstream(
        self,
        remote: str,
        branch: str,
        *,
        http_auth: GitHttpAuth | None = None,
    ) -> GitResult:
        # Used for branches that have no tracking upstream yet. Sets the
        # upstream tracking reference so subsequent pushes can use the simpler
        # push_current_head path.
        return self.run(
            ["push", "--porcelain", "--set-upstream", remote, f"HEAD:refs/heads/{branch}"],
            timeout_seconds=90,
            http_auth=http_auth,
        )
