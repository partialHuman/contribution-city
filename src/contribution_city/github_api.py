"""GitHub API client for retrieving contribution activity."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from contribution_city._version import __version__
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
query($username: String!, $from: DateTime, $to: DateTime) {
  user(login: $username) {
    login
    name
    contributionsCollection(from: $from, to: $to) {
      restrictedContributionsCount
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

# HTTP statuses that are worth retrying (temporary server-side problems)
_RETRY_STATUSES = frozenset({500, 502, 503, 504})
_MAX_DELAY = 60.0


def _as_date(value: str | date | None) -> date | None:
    if value is None or isinstance(value, date):
        return value  # type: ignore[return-value]
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError as err:
        raise ValueError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from err


def _iso_start(day: date) -> str:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _iso_end(day: date) -> str:
    return datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


class GitHubClient:
    """Client for fetching GitHub contribution data via the GraphQL API."""

    ENDPOINT = "https://api.github.com/graphql"

    def __init__(
        self,
        token: str | None = None,
        max_retries: int = 2,
        backoff: float = 1.5,
        timeout: float = 20.0,
    ) -> None:
        # Prefer explicit token, then standard environment variables
        self._token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.max_retries = max(0, int(max_retries))
        self.backoff = max(0.0, float(backoff))
        self.timeout = timeout

    @property
    def has_token(self) -> bool:
        """Return True if an authentication token is available."""
        return bool(self._token and self._token.strip())

    # ------------------------------------------------------------------ public API

    def fetch_contributions(
        self,
        username: str,
        start: str | date | None = None,
        end: str | date | None = None,
    ) -> ContributionDataSet:
        """Fetch the contribution calendar for a username.

        Args:
            username: GitHub username/handle.
            start: First day to include (YYYY-MM-DD). Defaults to one year before ``end``.
            end: Last day to include (YYYY-MM-DD). Defaults to today.

        GitHub allows at most one year per request, so ranges longer than 366 days are
        rejected; use :meth:`fetch_years` for several years.

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

        start_d, end_d = _as_date(start), _as_date(end)
        if start_d and end_d and end_d < start_d:
            raise ValueError("'to' date must not be before 'from' date")
        if start_d and end_d and (end_d - start_d).days > 366:
            raise ValueError(
                "A single request can cover at most one year; use several --year values"
            )
        if start_d and not end_d:
            end_d = min(start_d + timedelta(days=365), datetime.now(timezone.utc).date())
        if end_d and not start_d:
            start_d = end_d - timedelta(days=364)

        variables: dict[str, Any] = {"username": clean_user}
        if start_d and end_d:
            variables["from"] = _iso_start(start_d)
            variables["to"] = _iso_end(end_d)

        resp_data = self._post({"query": GRAPHQL_QUERY, "variables": variables}, clean_user)
        return self._process_response(resp_data, clean_user)

    def fetch_years(self, username: str, years: Iterable[int]) -> ContributionDataSet:
        """Fetch several calendar years and merge them into one dataset."""
        today = datetime.now(timezone.utc).date()
        parts: list[ContributionDataSet] = []
        for year in sorted(set(int(y) for y in years)):
            first = date(year, 1, 1)
            last = min(date(year, 12, 31), today)
            if first > today:
                raise ValueError(f"Year {year} is in the future")
            parts.append(self.fetch_contributions(username, first, last))
        if not parts:
            raise ValueError("No years requested")
        return ContributionDataSet.merge(*parts)

    # ------------------------------------------------------------------ internals

    def _delay_for(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(_MAX_DELAY, max(0.0, float(retry_after)))
            except ValueError:
                pass
        return min(_MAX_DELAY, self.backoff * (2**attempt))

    def _post(self, payload: dict[str, Any], clean_user: str) -> dict[str, Any]:
        """POST a GraphQL payload, retrying temporary failures with backoff."""
        body = json.dumps(payload).encode("utf-8")
        last_error: GitHubAPIError | None = None

        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(
                self.ENDPOINT,
                data=body,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                    "User-Agent": f"Contribution-City/{__version__}",
                    "Accept": "application/vnd.github.v4+json",
                },
                method="POST",
            )
            retry_after: str | None = None
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as err:
                retry_after = err.headers.get("Retry-After") if err.headers else None
                if err.code in (401, 403, 429):
                    remaining = err.headers.get("X-RateLimit-Remaining") if err.headers else None
                    if remaining == "0":
                        raise GitHubRateLimitError(
                            "GitHub API rate limit exceeded. Please wait or use an authenticated token."
                        ) from err
                    if err.code != 401 and retry_after:
                        # Secondary rate limit: GitHub tells us how long to wait
                        last_error = GitHubRateLimitError(
                            "GitHub secondary rate limit hit; try again later."
                        )
                    elif err.code == 429:
                        last_error = GitHubRateLimitError("GitHub rate limit exceeded (HTTP 429).")
                    else:
                        raise GitHubAuthError(
                            f"GitHub authentication error (HTTP {err.code}). "
                            "Verify that your GITHUB_TOKEN is valid and has read permissions."
                        ) from err
                elif err.code == 404:
                    raise GitHubUserNotFoundError(
                        f"User '{clean_user}' not found on GitHub."
                    ) from err
                elif err.code in _RETRY_STATUSES:
                    last_error = GitHubAPIError(f"GitHub API error (HTTP {err.code}): {err.reason}")
                else:
                    raise GitHubAPIError(
                        f"GitHub API error (HTTP {err.code}): {err.reason}"
                    ) from err
            except urllib.error.URLError as err:
                last_error = GitHubAPIError(f"Network error connecting to GitHub: {err.reason}")
            except json.JSONDecodeError as err:
                raise GitHubAPIError(f"GitHub returned an unreadable response: {err}") from err
            except Exception as err:
                raise GitHubAPIError(f"Unexpected error communicating with GitHub: {err}") from err

            if attempt < self.max_retries:
                time.sleep(self._delay_for(attempt, retry_after))

        assert last_error is not None
        raise last_error

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
