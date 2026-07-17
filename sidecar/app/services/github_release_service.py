from __future__ import annotations

import hashlib
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
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
    assets: tuple["GitHubReleaseAssetResult", ...] = ()
    action: str = "created"


@dataclass(frozen=True)
class GitHubReleaseAssetResult:
    name: str
    url: str | None
    sha256: str | None
    status: str = "uploaded"


@dataclass(frozen=True)
class GitHubDraftReleaseDetails:
    tag_name: str
    title: str
    body: str
    release_url: str
    assets: tuple[GitHubReleaseAssetResult, ...] = ()


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
        asset_paths: Sequence[Path] | None = None,
        asset_path: Path | None = None,
    ) -> GitHubDraftReleaseResult:
        upload_paths = tuple(asset_paths or (() if asset_path is None else (asset_path,)))
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

        api_root = f"https://api.github.com/repos/{repository.owner}/{repository.repo}"
        api_url = f"{api_root}/releases"
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                existing_release = self._find_release_by_tag(
                    client=client,
                    headers=headers,
                    repository=repository,
                    tag_name=tag_name,
                )
                if existing_release is not None:
                    if not bool(existing_release.get("draft")):
                        raise ValidationFailure(
                            f"Release tag '{tag_name}' already exists as a published release. "
                            "Choose a new tag or update the published release on GitHub."
                        )
                    release_id = existing_release.get("id")
                    release_response = client.patch(
                        f"{api_url}/{release_id}",
                        headers=headers,
                        json=payload,
                    )
                    self._raise_for_github_error(release_response)
                    release = release_response.json()
                    release_action = "updated"
                else:
                    release_response = client.post(api_url, headers=headers, json=payload)
                    self._raise_for_github_error(release_response)
                    release = release_response.json()
                    release_action = "created"

                existing_assets = {
                    str(asset.get("name") or ""): asset
                    for asset in self._release_assets(client, headers, release)
                    if asset.get("name")
                }

                uploaded_assets: list[GitHubReleaseAssetResult] = []
                for asset_path in upload_paths:
                    asset_name = asset_path.name
                    asset_sha256 = _sha256_file(asset_path)
                    existing_asset = existing_assets.get(asset_name)
                    if existing_asset is not None:
                        uploaded_assets.append(
                            GitHubReleaseAssetResult(
                                name=asset_name,
                                url=str(existing_asset.get("browser_download_url") or "")
                                or None,
                                sha256=asset_sha256,
                                status="already_exists",
                            )
                        )
                        continue

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
                    uploaded_assets.append(
                        GitHubReleaseAssetResult(
                            name=asset_name,
                            url=str(asset_url) if asset_url else None,
                            sha256=asset_sha256,
                            status="uploaded",
                        )
                    )
                    existing_assets[asset_name] = asset

        except httpx.HTTPError as exc:
            raise ValidationFailure(f"GitHub release request failed: {exc}") from exc

        first_asset = uploaded_assets[0] if uploaded_assets else None
        return GitHubDraftReleaseResult(
            tag_name=tag_name,
            release_url=str(release.get("html_url") or ""),
            asset_url=first_asset.url if first_asset else None,
            asset_name=first_asset.name if first_asset else None,
            asset_sha256=first_asset.sha256 if first_asset else None,
            assets=tuple(uploaded_assets),
            action=release_action,
        )

    def get_draft_release(
        self,
        *,
        repository: GitHubRepositoryRef,
        tag_name: str,
    ) -> GitHubDraftReleaseDetails:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                release = self._find_release_by_tag(
                    client=client,
                    headers=headers,
                    repository=repository,
                    tag_name=tag_name,
                )
                if release is None:
                    raise ValidationFailure(
                        f"No GitHub draft release was found for tag '{tag_name}'. "
                        "Choose Create new draft, or create the draft on GitHub first."
                    )
                if not bool(release.get("draft")):
                    raise ValidationFailure(
                        f"Release tag '{tag_name}' already exists as a published release. "
                        "Only draft releases can be edited from the app."
                    )

                assets = tuple(
                    GitHubReleaseAssetResult(
                        name=str(asset.get("name") or ""),
                        url=str(asset.get("browser_download_url") or "") or None,
                        sha256=None,
                        status="existing",
                    )
                    for asset in self._release_assets(client, headers, release)
                    if asset.get("name")
                )
        except httpx.HTTPError as exc:
            raise ValidationFailure(f"GitHub release request failed: {exc}") from exc

        return GitHubDraftReleaseDetails(
            tag_name=str(release.get("tag_name") or tag_name),
            title=str(release.get("name") or f"Release {tag_name}"),
            body=str(release.get("body") or ""),
            release_url=str(release.get("html_url") or ""),
            assets=assets,
        )

    def _find_release_by_tag(
        self,
        *,
        client: httpx.Client,
        headers: dict[str, str],
        repository: GitHubRepositoryRef,
        tag_name: str,
    ) -> dict | None:
        api_root = f"https://api.github.com/repos/{repository.owner}/{repository.repo}"
        response = client.get(
            f"{api_root}/releases/tags/{quote(tag_name, safe='')}",
            headers=headers,
        )
        if response.status_code == 200:
            return response.json()
        if response.status_code not in {404, 422}:
            self._raise_for_github_error(response)

        releases_response = client.get(
            f"{api_root}/releases",
            headers=headers,
            params={"per_page": 100},
        )
        self._raise_for_github_error(releases_response)
        for release in releases_response.json():
            if str(release.get("tag_name") or "") == tag_name:
                return release
        return None

    def _release_assets(
        self,
        client: httpx.Client,
        headers: dict[str, str],
        release: dict,
    ) -> list[dict]:
        assets_url = release.get("assets_url")
        if assets_url:
            response = client.get(str(assets_url), headers=headers, params={"per_page": 100})
            self._raise_for_github_error(response)
            return [asset for asset in response.json() if isinstance(asset, dict)]

        assets = release.get("assets")
        if isinstance(assets, list):
            return [asset for asset in assets if isinstance(asset, dict)]
        return []

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
