from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class RemoteProviderDetection:
    provider: str
    label: str
    host: str | None


_SCP_LIKE_REMOTE = re.compile(r"^(?:[^@\s]+@)?(?P<host>[^:\s/]+):(?P<path>.+)$")


def detect_remote_provider(remote_url: str) -> RemoteProviderDetection:
    host = _remote_host(remote_url)
    if not host:
        return RemoteProviderDetection(provider="unknown", label="Unknown", host=None)

    host = host.lower().strip("[]")
    if host == "github.com":
        return RemoteProviderDetection(provider="github", label="GitHub", host=host)
    if host == "gitlab.com" or "gitlab" in host:
        return RemoteProviderDetection(provider="gitlab", label="GitLab", host=host)
    if host == "bitbucket.org" or "bitbucket" in host:
        return RemoteProviderDetection(provider="bitbucket", label="Bitbucket", host=host)
    if (
        host == "dev.azure.com"
        or host.endswith(".visualstudio.com")
        or host.endswith(".dev.azure.com")
        or host == "ssh.dev.azure.com"
    ):
        return RemoteProviderDetection(provider="azure_devops", label="Azure DevOps", host=host)
    return RemoteProviderDetection(provider="unknown", label="Unknown", host=host)


def _remote_host(remote_url: str) -> str | None:
    value = remote_url.strip()
    if not value:
        return None

    parsed = urlparse(value)
    if parsed.scheme and parsed.hostname:
        return parsed.hostname

    scp_like = _SCP_LIKE_REMOTE.match(value)
    if scp_like:
        host = scp_like.group("host")
        if "." in host:
            return host

    return None
