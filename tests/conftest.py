"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retry back-off must never slow the test suite down."""
    monkeypatch.setattr("contribution_city.github_api.time.sleep", lambda _seconds: None)
