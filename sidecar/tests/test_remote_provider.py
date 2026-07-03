from __future__ import annotations

import pytest

from app.git.remote_provider import detect_remote_provider


@pytest.mark.parametrize(
    ("url", "provider", "label", "host"),
    [
        ("https://github.com/example/repo.git", "github", "GitHub", "github.com"),
        ("git@github.com:example/repo.git", "github", "GitHub", "github.com"),
        ("ssh://git@github.com/example/repo.git", "github", "GitHub", "github.com"),
        ("https://gitlab.com/group/project.git", "gitlab", "GitLab", "gitlab.com"),
        ("git@gitlab.company.test:team/project.git", "gitlab", "GitLab", "gitlab.company.test"),
        ("https://bitbucket.org/team/project.git", "bitbucket", "Bitbucket", "bitbucket.org"),
        ("https://dev.azure.com/org/project/_git/repo", "azure_devops", "Azure DevOps", "dev.azure.com"),
        ("git@ssh.dev.azure.com:v3/org/project/repo", "azure_devops", "Azure DevOps", "ssh.dev.azure.com"),
        ("D:/repos/remote.git", "unknown", "Unknown", None),
    ],
)
def test_detect_remote_provider(url: str, provider: str, label: str, host: str | None) -> None:
    detected = detect_remote_provider(url)

    assert detected.provider == provider
    assert detected.label == label
    assert detected.host == host
