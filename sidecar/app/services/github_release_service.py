from __future__ import annotations

import hashlib
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx

from app.errors import ValidationFailure


_HTTPS_REMOTE = re.compile(r"^https://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")
_SSH_REMOTE = re.compile(r"^git@github\.com:([^/\s]+)/([^/\s]+?)(?:\.git)?$")
_SSH_URL_REMOTE = re.compile(r"^ssh://git@github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")


@dataclass(frozen=True)
class GitHubRepositoryRef:
    owner: str
    repo: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"


@dataclass(frozen=True)
class GitHubDraftReleaseResult:
    tag_name: str
    release_url: str
    asset_url: str | None
    asset_name: str | None
    asset_sha256: str | None


@dataclass(frozen=True)
class GitHubDraftPullRequestResult:
    number: int
    pull_request_url: str
    title: str


@dataclass(frozen=True)
class GitHubPullRequestStatusResult:
    number: int
    url: str
    title: str
    state: str
    draft: bool
    base_branch: str
    head_branch: str
    head_sha: str
    ci_status: str
    review_summary: str
    review_count: int
    comment_count: int
    latest_comments: tuple[str, ...] = ()


def parse_github_remote_url(remote_url: str) -> GitHubRepositoryRef | None:
    value = remote_url.strip()
    for pattern in (_HTTPS_REMOTE, _SSH_REMOTE, _SSH_URL_REMOTE):
        match = pattern.match(value)
        if match:
            return GitHubRepositoryRef(owner=match.group(1), repo=match.group(2))
    return None


class GitHubReleaseClient:
    def __init__(self, token: str, *, timeout_seconds: float = 120.0) -> None:
        self._token = token
        self._timeout = timeout_seconds

    def create_draft_release(
        self,
        *,
        repository: GitHubRepositoryRef,
        tag_name: str,
        title: str,
        body: str,
        target_commitish: str | None,
        prerelease: bool,
        asset_path: Path | None,
    ) -> GitHubDraftReleaseResult:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        payload: dict[str, object] = {
            "tag_name": tag_name,
            "name": title,
            "body": body,
            "draft": True,
            "prerelease": prerelease,
            "generate_release_notes": False,
        }
        if target_commitish:
            payload["target_commitish"] = target_commitish

        api_url = f"https://api.github.com/repos/{repository.owner}/{repository.repo}/releases"
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                release_response = client.post(api_url, headers=headers, json=payload)
                self._raise_for_github_error(release_response)
                release = release_response.json()

                asset_url = None
                asset_name = None
                asset_sha256 = None
                if asset_path is not None:
                    asset_name = asset_path.name
                    asset_sha256 = _sha256_file(asset_path)
                    upload_url = (
                        release.get("upload_url", "")
                        .split("{", 1)[0]
                        .rstrip("?")
                    )
                    if not upload_url:
                        release_id = release.get("id")
                        upload_url = (
                            f"https://uploads.github.com/repos/{repository.owner}/{repository.repo}"
                            f"/releases/{release_id}/assets"
                        )
                    upload_response = client.post(
                        f"{upload_url}?name={quote(asset_name)}",
                        headers={
                            **headers,
                            "Content-Type": mimetypes.guess_type(asset_name)[0]
                            or "application/octet-stream",
                        },
                        content=asset_path.read_bytes(),
                    )
                    self._raise_for_github_error(upload_response)
                    asset = upload_response.json()
                    asset_url = asset.get("browser_download_url")

        except httpx.HTTPError as exc:
            raise ValidationFailure(f"GitHub release request failed: {exc}") from exc

        return GitHubDraftReleaseResult(
            tag_name=tag_name,
            release_url=str(release.get("html_url") or ""),
            asset_url=asset_url,
            asset_name=asset_name,
            asset_sha256=asset_sha256,
        )

    def create_draft_pull_request(
        self,
        *,
        repository: GitHubRepositoryRef,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> GitHubDraftPullRequestResult:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        payload: dict[str, object] = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "draft": True,
            "maintainer_can_modify": True,
        }
        api_url = f"https://api.github.com/repos/{repository.owner}/{repository.repo}/pulls"
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                response = client.post(api_url, headers=headers, json=payload)
                self._raise_for_github_error(response, operation="pull request")
                pull_request = response.json()
        except httpx.HTTPError as exc:
            raise ValidationFailure(f"GitHub pull request request failed: {exc}") from exc

        return GitHubDraftPullRequestResult(
            number=int(pull_request.get("number") or 0),
            pull_request_url=str(pull_request.get("html_url") or ""),
            title=str(pull_request.get("title") or title),
        )

    def get_pull_request_status(
        self,
        *,
        repository: GitHubRepositoryRef,
        head_branch: str,
    ) -> GitHubPullRequestStatusResult | None:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        api_root = f"https://api.github.com/repos/{repository.owner}/{repository.repo}"
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                response = client.get(
                    f"{api_root}/pulls",
                    headers=headers,
                    params={
                        "state": "open",
                        "head": f"{repository.owner}:{head_branch}",
                        "per_page": 5,
                    },
                )
                self._raise_for_github_error(response, operation="pull request status")
                pulls = response.json()
                if not pulls:
                    return None
                pull_request = pulls[0]
                number = int(pull_request.get("number") or 0)
                head = pull_request.get("head") or {}
                base = pull_request.get("base") or {}
                head_sha = str(head.get("sha") or "")

                ci_status = "unknown"
                if head_sha:
                    status_response = client.get(
                        f"{api_root}/commits/{head_sha}/status",
                        headers=headers,
                    )
                    if status_response.status_code < 400:
                        ci_status = str((status_response.json() or {}).get("state") or "unknown")

                reviews_response = client.get(
                    f"{api_root}/pulls/{number}/reviews",
                    headers=headers,
                    params={"per_page": 100},
                )
                review_states: list[str] = []
                if reviews_response.status_code < 400:
                    review_states = [
                        str(item.get("state") or "").lower()
                        for item in reviews_response.json()
                        if item.get("state")
                    ]

                issue_comments_response = client.get(
                    f"{api_root}/issues/{number}/comments",
                    headers=headers,
                    params={"per_page": 5},
                )
                latest_comments: list[str] = []
                issue_comment_count = 0
                if issue_comments_response.status_code < 400:
                    issue_comments = issue_comments_response.json()
                    issue_comment_count = len(issue_comments)
                    latest_comments.extend(_comment_preview(item) for item in issue_comments[:5])

                review_comments_response = client.get(
                    f"{api_root}/pulls/{number}/comments",
                    headers=headers,
                    params={"per_page": 5},
                )
                review_comment_count = 0
                if review_comments_response.status_code < 400:
                    review_comments = review_comments_response.json()
                    review_comment_count = len(review_comments)
                    latest_comments.extend(_comment_preview(item) for item in review_comments[:5])
        except httpx.HTTPError as exc:
            raise ValidationFailure(f"GitHub pull request status request failed: {exc}") from exc

        return GitHubPullRequestStatusResult(
            number=number,
            url=str(pull_request.get("html_url") or ""),
            title=str(pull_request.get("title") or ""),
            state=str(pull_request.get("state") or "open"),
            draft=bool(pull_request.get("draft")),
            base_branch=str(base.get("ref") or ""),
            head_branch=str(head.get("ref") or head_branch),
            head_sha=head_sha,
            ci_status=ci_status,
            review_summary=_review_summary(review_states),
            review_count=len(review_states),
            comment_count=issue_comment_count + review_comment_count,
            latest_comments=tuple(comment for comment in latest_comments if comment),
        )

    @staticmethod
    def _raise_for_github_error(response: httpx.Response, *, operation: str = "release") -> None:
        if response.status_code < 400:
            return
        try:
            message = response.json().get("message", response.text)
        except ValueError:
            message = response.text
        if (
            response.status_code == 403
            and "resource not accessible by personal access token" in str(message).lower()
        ):
            raise ValidationFailure(
                f"GitHub token cannot access {operation} data for this repository. "
                "Create or update a fine-grained token for this repo with Contents: Read and write "
                "and Pull requests: Read and write, "
                "then save it again in Settings."
            )
        raise ValidationFailure(
            f"GitHub returned {response.status_code}: {str(message).strip()[:300]}"
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _review_summary(states: list[str]) -> str:
    if not states:
        return "no reviews"
    approvals = states.count("approved")
    changes = states.count("changes_requested")
    comments = states.count("commented")
    parts: list[str] = []
    if approvals:
        parts.append(f"{approvals} approved")
    if changes:
        parts.append(f"{changes} changes requested")
    if comments:
        parts.append(f"{comments} commented")
    return ", ".join(parts) if parts else f"{len(states)} review events"


def _comment_preview(item: dict) -> str:
    user = (item.get("user") or {}).get("login") or "reviewer"
    body = str(item.get("body") or "").strip().replace("\r", " ").replace("\n", " ")
    if len(body) > 140:
        body = body[:137].rstrip() + "..."
    return f"{user}: {body}" if body else ""
