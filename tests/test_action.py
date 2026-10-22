"""Tests for GitHub Action configuration."""

from __future__ import annotations

from pathlib import Path

import yaml


def test_action_yml_structure() -> None:
    action_path = Path(__file__).parent.parent / "action.yml"
    assert action_path.is_file(), "action.yml must exist at repository root"

    with open(action_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert isinstance(data, dict)
    assert data["name"] == "Contribution City"
    assert "description" in data
    assert "inputs" in data
    assert "outputs" in data
    assert "runs" in data

    # Verify essential inputs
    inputs = data["inputs"]
    assert "username" in inputs
    assert "token" in inputs
    assert "theme" in inputs
    assert "output" in inputs

    # Verify composite run definition
    runs = data["runs"]
    assert runs.get("using") == "composite"
    assert isinstance(runs.get("steps"), list)
    assert len(runs["steps"]) >= 3
