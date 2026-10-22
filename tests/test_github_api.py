"""Tests for GitHub API integration and error handling."""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from contribution_city.github_api import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubClient,
    GitHubRateLimitError,
    GitHubUserNotFoundError,
)


class TestGitHubClient:
    """Test suite for GitHubClient network calls and response handling."""

    def test_missing_token_raises_auth_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        client = GitHubClient(token=None)
        assert not client.has_token
        with pytest.raises(GitHubAuthError, match="requires authentication"):
            client.fetch_contributions("octocat")

    def test_empty_username_raises_value_error(self) -> None:
        client = GitHubClient(token="mock-token")
        with pytest.raises(ValueError, match="Username cannot be empty"):
            client.fetch_contributions("   ")

    def test_token_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "env-secret-token")
        client = GitHubClient()
        assert client.has_token
        assert client._token == "env-secret-token"

    @patch("urllib.request.urlopen")
    def test_successful_fetch(self, mock_urlopen: MagicMock) -> None:
        mock_response_data = {
            "data": {
                "user": {
                    "login": "octocat",
                    "contributionsCollection": {
                        "contributionCalendar": {
                            "totalContributions": 42,
                            "weeks": [
                                {
                                    "contributionDays": [
                                        {
                                            "date": "2025-01-01",
                                            "contributionCount": 5,
                                            "contributionLevel": "SECOND_QUARTILE",
                                            "weekday": 3,
                                        }
                                    ]
                                }
                            ],
                        }
                    },
                }
            }
        }
        mock_fp = io.BytesIO(json.dumps(mock_response_data).encode("utf-8"))
        mock_resp = MagicMock()
        mock_resp.read.side_effect = mock_fp.read
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = GitHubClient(token="mock-token")
        dataset = client.fetch_contributions("octocat")

        assert dataset.username == "octocat"
        assert dataset.total_contributions == 5
        assert len(dataset.days) == 1
        assert dataset.days[0].date == "2025-01-01"

    @patch("urllib.request.urlopen")
    def test_http_401_raises_auth_error(self, mock_urlopen: MagicMock) -> None:
        http_err = urllib.error.HTTPError(
            url="https://api.github.com/graphql",
            code=401,
            msg="Unauthorized",
            hdrs={},  # type: ignore[arg-type]
            fp=io.BytesIO(b'{"message": "Bad credentials"}'),
        )
        mock_urlopen.side_effect = http_err

        client = GitHubClient(token="invalid-token")
        with pytest.raises(GitHubAuthError, match="GitHub authentication error"):
            client.fetch_contributions("octocat")

    @patch("urllib.request.urlopen")
    def test_rate_limit_exceeded(self, mock_urlopen: MagicMock) -> None:
        headers = {"X-RateLimit-Remaining": "0"}
        http_err = urllib.error.HTTPError(
            url="https://api.github.com/graphql",
            code=403,
            msg="Forbidden",
            hdrs=headers,  # type: ignore[arg-type]
            fp=io.BytesIO(b'{"message": "API rate limit exceeded"}'),
        )
        mock_urlopen.side_effect = http_err

        client = GitHubClient(token="some-token")
        with pytest.raises(GitHubRateLimitError, match="rate limit exceeded"):
            client.fetch_contributions("octocat")

    @patch("urllib.request.urlopen")
    def test_graphql_user_not_found(self, mock_urlopen: MagicMock) -> None:
        mock_response_data = {
            "data": {"user": None},
            "errors": [
                {
                    "type": "NOT_FOUND",
                    "path": ["user"],
                    "locations": [{"line": 3, "column": 3}],
                    "message": "Could not resolve to a User with the login of 'non_existent_user_12345'.",
                }
            ],
        }
        mock_fp = io.BytesIO(json.dumps(mock_response_data).encode("utf-8"))
        mock_resp = MagicMock()
        mock_resp.read.side_effect = mock_fp.read
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = GitHubClient(token="mock-token")
        with pytest.raises(GitHubUserNotFoundError, match="was not found"):
            client.fetch_contributions("non_existent_user_12345")

    @patch("urllib.request.urlopen")
    def test_network_urlerror(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        client = GitHubClient(token="mock-token")
        with pytest.raises(GitHubAPIError, match="Network error connecting to GitHub"):
            client.fetch_contributions("octocat")
