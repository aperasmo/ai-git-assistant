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
                f"GitHub token cannot create {operation}s for this repository. "
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
