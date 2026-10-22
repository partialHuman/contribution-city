"""GitHub API client for retrieving contribution activity."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from contribution_city.models import ContributionDataSet


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""


class GitHubAuthError(GitHubAPIError):
    """Raised on authentication or permission failure."""


class GitHubRateLimitError(GitHubAPIError):
    """Raised when GitHub rate limit is exceeded."""


class GitHubUserNotFoundError(GitHubAPIError):
    """Raised when requested GitHub user cannot be found."""


GRAPHQL_QUERY = """
query($username: String!) {
  user(login: $username) {
    login
    name
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            contributionLevel
            weekday
          }
        }
      }
    }
  }
}
"""


class GitHubClient:
    """Client for fetching GitHub contribution data via the GraphQL API."""

    ENDPOINT = "https://api.github.com/graphql"

    def __init__(self, token: str | None = None) -> None:
        # Prefer explicit token, then standard environment variables
        self._token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    @property
    def has_token(self) -> bool:
        """Return True if an authentication token is available."""
        return bool(self._token and self._token.strip())

    def fetch_contributions(self, username: str) -> ContributionDataSet:
        """Fetch full contribution calendar for given username.

        Args:
            username: GitHub username/handle.

        Returns:
            Normalized ContributionDataSet.

        Raises:
            GitHubAuthError: If authentication fails or token is missing.
            GitHubUserNotFoundError: If username does not exist.
            GitHubRateLimitError: If rate limit is hit.
            GitHubAPIError: For other network or API errors.
        """
        clean_user = username.strip().lstrip("@")
        if not clean_user:
            raise ValueError("Username cannot be empty")

        if not self.has_token:
            raise GitHubAuthError(
                "GitHub GraphQL API requires authentication. "
                "Please provide a token via --token or set the GITHUB_TOKEN environment variable."
            )

        payload = {
            "query": GRAPHQL_QUERY,
            "variables": {"username": clean_user},
        }

        req = urllib.request.Request(
            self.ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "User-Agent": "Contribution-City/0.1.0",
                "Accept": "application/vnd.github.v4+json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            if err.code in (401, 403):
                # Check for rate limit in headers
                remaining = err.headers.get("X-RateLimit-Remaining")
                if remaining == "0":
                    raise GitHubRateLimitError(
                        "GitHub API rate limit exceeded. Please wait or use an authenticated token."
                    ) from err
                raise GitHubAuthError(
                    f"GitHub authentication error (HTTP {err.code}). "
                    "Verify that your GITHUB_TOKEN is valid and has read permissions."
                ) from err
            if err.code == 404:
                raise GitHubUserNotFoundError(f"User '{clean_user}' not found on GitHub.") from err
            raise GitHubAPIError(f"GitHub API error (HTTP {err.code}): {err.reason}") from err
        except urllib.error.URLError as err:
            raise GitHubAPIError(f"Network error connecting to GitHub: {err.reason}") from err
        except Exception as err:
            raise GitHubAPIError(f"Unexpected error communicating with GitHub: {err}") from err

        return self._process_response(resp_data, clean_user)

    def _process_response(self, data: dict[str, Any], username: str) -> ContributionDataSet:
        """Process GraphQL response dictionary and handle logical errors."""
        errors = data.get("errors")
        if errors and isinstance(errors, list):
            for err in errors:
                msg = err.get("message", "")
                err_type = err.get("type")
                if "Could not resolve to a User" in msg or err_type == "NOT_FOUND":
                    raise GitHubUserNotFoundError(f"GitHub user '{username}' was not found.")
                if "rate limit" in msg.lower():
                    raise GitHubRateLimitError(f"GitHub rate limit exceeded: {msg}")
            # Other GraphQL error
            first_msg = errors[0].get("message", "Unknown GraphQL error")
            raise GitHubAPIError(f"GitHub GraphQL error: {first_msg}")

        user_data = (data.get("data") or {}).get("user")
        if not user_data:
            raise GitHubUserNotFoundError(f"GitHub user '{username}' not found or returned empty.")

        return ContributionDataSet.from_dict(data, username=username)
