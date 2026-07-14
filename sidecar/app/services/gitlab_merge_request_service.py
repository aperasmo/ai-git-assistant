from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.errors import ValidationFailure


_HTTPS_REMOTE = re.compile(r"^https://([^/\s]+)/(.+?)(?:\.git)?/?$")
_SSH_REMOTE = re.compile(r"^git@([^:\s]+):(.+?)(?:\.git)?$")
_SSH_URL_REMOTE = re.compile(r"^ssh://git@([^/\s]+)/(.+?)(?:\.git)?/?$")


@dataclass(frozen=True)
class GitLabRepositoryRef:
    host: str
    namespace_path: str

    @property
    def slug(self) -> str:
        return self.namespace_path

    @property
    def api_project_id(self) -> str:
        return quote(self.namespace_path, safe="")


@dataclass(frozen=True)
class GitLabDraftMergeRequestResult:
    number: int
    merge_request_url: str
    title: str


@dataclass(frozen=True)
class GitLabMergeRequestStatusResult:
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


def parse_gitlab_remote_url(remote_url: str) -> GitLabRepositoryRef | None:
    value = remote_url.strip()
    for pattern in (_HTTPS_REMOTE, _SSH_REMOTE, _SSH_URL_REMOTE):
        match = pattern.match(value)
        if not match:
            continue
        host = match.group(1)
        if "gitlab" not in host.lower():
            continue
        namespace_path = match.group(2).strip("/")
        if not namespace_path:
            continue
        return GitLabRepositoryRef(host=host, namespace_path=namespace_path)
    return None


class GitLabMergeRequestClient:
    def __init__(
        self,
        token: str,
        *,
        base_url: str | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._token = token
        self._base_url = (base_url or "https://gitlab.com").rstrip("/")
        self._timeout = timeout_seconds

    def create_draft_merge_request(
        self,
        *,
        repository: GitLabRepositoryRef,
        title: str,
        body: str,
        source_branch: str,
        target_branch: str,
    ) -> GitLabDraftMergeRequestResult:
        headers = {
            "Accept": "application/json",
            "PRIVATE-TOKEN": self._token,
        }
        payload: dict[str, object] = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": _draft_title(title),
            "description": body,
            "remove_source_branch": False,
            "squash": False,
        }
        api_url = f"{self._base_url}/api/v4/projects/{repository.api_project_id}/merge_requests"
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                response = client.post(api_url, headers=headers, data=payload)
                self._raise_for_gitlab_error(response)
                merge_request = response.json()
        except httpx.HTTPError as exc:
            raise ValidationFailure(f"GitLab merge request request failed: {exc}") from exc

        return GitLabDraftMergeRequestResult(
            number=int(merge_request.get("iid") or merge_request.get("id") or 0),
            merge_request_url=str(merge_request.get("web_url") or ""),
            title=str(merge_request.get("title") or payload["title"]),
        )

    def get_merge_request_status(
        self,
        *,
        repository: GitLabRepositoryRef,
        source_branch: str,
    ) -> GitLabMergeRequestStatusResult | None:
        headers = {
            "Accept": "application/json",
            "PRIVATE-TOKEN": self._token,
        }
        api_root = f"{self._base_url}/api/v4/projects/{repository.api_project_id}"
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                response = client.get(
                    f"{api_root}/merge_requests",
                    headers=headers,
                    params={
                        "state": "opened",
                        "source_branch": source_branch,
                        "per_page": 5,
                    },
                )
                self._raise_for_gitlab_error(response)
                merge_requests = response.json()
                if not merge_requests:
                    return None
                merge_request = merge_requests[0]
                iid = int(merge_request.get("iid") or 0)
                head_sha = str(merge_request.get("sha") or "")
                diff_refs = merge_request.get("diff_refs") or {}
                if not head_sha:
                    head_sha = str(diff_refs.get("head_sha") or "")

                ci_status = "unknown"
                head_pipeline = merge_request.get("head_pipeline") or {}
                if head_pipeline.get("status"):
                    ci_status = str(head_pipeline.get("status"))
                elif head_sha:
                    status_response = client.get(
                        f"{api_root}/repository/commits/{head_sha}/statuses",
                        headers=headers,
                        params={"per_page": 50},
                    )
                    if status_response.status_code < 400:
                        ci_status = _aggregate_gitlab_status(
                            [str(item.get("status") or "") for item in status_response.json()]
                        )

                notes_response = client.get(
                    f"{api_root}/merge_requests/{iid}/notes",
                    headers=headers,
                    params={"per_page": 10},
                )
                latest_comments: list[str] = []
                comment_count = 0
                if notes_response.status_code < 400:
                    notes = [item for item in notes_response.json() if not item.get("system")]
                    comment_count = len(notes)
                    latest_comments = [_note_preview(item) for item in notes[:5]]
        except httpx.HTTPError as exc:
            raise ValidationFailure(f"GitLab merge request status request failed: {exc}") from exc

        return GitLabMergeRequestStatusResult(
            number=iid,
            url=str(merge_request.get("web_url") or ""),
            title=str(merge_request.get("title") or ""),
            state=str(merge_request.get("state") or "opened"),
            draft=bool(merge_request.get("draft") or str(merge_request.get("work_in_progress")).lower() == "true"),
            base_branch=str(merge_request.get("target_branch") or ""),
            head_branch=str(merge_request.get("source_branch") or source_branch),
            head_sha=head_sha,
            ci_status=ci_status,
            review_summary=_gitlab_review_summary(merge_request),
            review_count=0,
            comment_count=comment_count,
            latest_comments=tuple(comment for comment in latest_comments if comment),
        )

    @staticmethod
    def _raise_for_gitlab_error(response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        try:
            payload = response.json()
            message = payload.get("message") or payload.get("error") or response.text
        except ValueError:
            message = response.text
        if response.status_code in {401, 403}:
            raise ValidationFailure(
                "GitLab token cannot access merge requests for this repository. "
                "Create or update a GitLab personal access token with api scope for this project, "
                "then save it again in Settings."
            )
        raise ValidationFailure(
            f"GitLab returned {response.status_code}: {str(message).strip()[:300]}"
        )


def _draft_title(title: str) -> str:
    clean = title.strip()
    return clean if clean.lower().startswith(("draft:", "wip:")) else f"Draft: {clean}"


def _aggregate_gitlab_status(statuses: list[str]) -> str:
    clean = [status for status in statuses if status]
    if not clean:
        return "unknown"
    if any(status in {"failed", "canceled", "skipped"} for status in clean):
        return "failed"
    if any(status in {"running", "pending", "created", "waiting_for_resource", "manual"} for status in clean):
        return "pending"
    if all(status == "success" for status in clean):
        return "success"
    return clean[0]


def _gitlab_review_summary(merge_request: dict) -> str:
    approvals = merge_request.get("upvotes") or 0
    downvotes = merge_request.get("downvotes") or 0
    parts: list[str] = []
    if approvals:
        parts.append(f"{approvals} upvotes")
    if downvotes:
        parts.append(f"{downvotes} downvotes")
    return ", ".join(parts) if parts else "no approval signal"


def _note_preview(item: dict) -> str:
    author = (item.get("author") or {}).get("username") or "reviewer"
    body = str(item.get("body") or "").strip().replace("\r", " ").replace("\n", " ")
    if len(body) > 140:
        body = body[:137].rstrip() + "..."
    return f"{author}: {body}" if body else ""
