"""Comprehensive tests for GitHub Action configuration and behavior."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from contribution_city.cli import create_parser, main


@pytest.fixture
def action_data() -> dict:
    """Load and parse action.yml."""
    action_path = Path(__file__).parent.parent / "action.yml"
    assert action_path.is_file(), "action.yml must exist at repository root"
    with open(action_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def consumer_workflow_data() -> dict:
    """Load and parse the example consumer workflow."""
    wf_path = Path(__file__).parent.parent / "examples/workflows/generate-profile-city.yml"
    assert wf_path.is_file(), "Consumer workflow example must exist"
    with open(wf_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestActionMetadata:
    """Test suite for action.yml metadata and structure."""

    def test_action_yml_structure(self, action_data: dict) -> None:
        assert action_data["name"] == "Contribution City"
        assert "description" in action_data
        assert "author" in action_data
        assert "branding" in action_data
        assert action_data["branding"]["icon"] == "map"
        assert action_data["branding"]["color"] == "blue"

    def test_composite_runs_definition(self, action_data: dict) -> None:
        runs = action_data.get("runs", {})
        assert runs.get("using") == "composite"
        steps = runs.get("steps", [])
        assert len(steps) >= 3

        # Step 1: setup-python
        step1 = steps[0]
        assert "setup-python" in step1.get("uses", "")
        # Must NOT contain cache: pip because caller repos won't have pyproject.toml
        step1_with = step1.get("with", {})
        assert "cache" not in step1_with, (
            "cache: pip must not be set in setup-python for composite action"
        )

        # Step 2: install package
        step2 = steps[1]
        assert "pip install" in step2.get("run", "")

        # Step 3: execution step
        step3 = steps[2]
        assert step3.get("id") == "generate"
        assert "python -m contribution_city.cli" in step3.get("run", "")
        assert "$GITHUB_OUTPUT" in step3.get("run", "")

    def test_output_mapping_contract(self, action_data: dict) -> None:
        outputs = action_data.get("outputs", {})
        assert "svg-path" in outputs
        # Must map to the generate step output
        assert outputs["svg-path"]["value"] == "${{ steps.generate.outputs.svg-path }}"

    def test_action_inputs_match_cli_parser(self, action_data: dict) -> None:
        inputs = action_data.get("inputs", {})
        parser = create_parser()

        # Map action input names to expected CLI options
        action_to_cli_option = {
            "username": "--username",
            "token": "--token",
            "theme": "--theme",
            "layout": "--layout",
            "config": "--config",
            "input": "--input",
            "output": "--output",
            "width": "--width",
            "height": "--height",
            "scale": "--scale",
        }

        # Collect all flags recognized by CLI parser
        cli_flags = set()
        for action in parser._actions:
            cli_flags.update(action.option_strings)

        for input_name, expected_flag in action_to_cli_option.items():
            assert input_name in inputs, f"Missing input '{input_name}' in action.yml"
            assert expected_flag in cli_flags, (
                f"Action input '{input_name}' ({expected_flag}) not recognized by CLI parser"
            )


class TestActionExecutionSimulation:
    """Test suite simulating action execution semantics in Python."""

    @pytest.fixture
    def fixture_json(self) -> str:
        fixture_path = Path(__file__).parent.parent / "examples/sample-contributions.json"
        assert fixture_path.is_file()
        return str(fixture_path)

    def test_action_run_offline_fixture(self, fixture_json: str, tmp_path: Path) -> None:
        out_svg = tmp_path / "action_dist" / "city.svg"
        ret = main(
            [
                "generate",
                "--input",
                fixture_json,
                "--theme",
                "navy-cyan",
                "--layout",
                "calendar",
                "--output",
                str(out_svg),
            ]
        )
        assert ret == 0
        assert out_svg.is_file()
        content = out_svg.read_text(encoding="utf-8")
        assert "<svg" in content
        assert "@octocat-architect" in content

    def test_action_run_creates_nested_directory(self, fixture_json: str, tmp_path: Path) -> None:
        deep_out = tmp_path / "deep" / "nested" / "subfolder" / "city.svg"
        assert not deep_out.parent.exists()
        ret = main(
            [
                "generate",
                "--input",
                fixture_json,
                "--output",
                str(deep_out),
            ]
        )
        assert ret == 0
        assert deep_out.is_file()

    def test_action_run_path_with_spaces(self, fixture_json: str, tmp_path: Path) -> None:
        spaced_out = tmp_path / "path with spaces" / "city output.svg"
        ret = main(
            [
                "generate",
                "--input",
                fixture_json,
                "--output",
                str(spaced_out),
            ]
        )
        assert ret == 0
        assert spaced_out.is_file()

    def test_credential_confidentiality(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        secret_token = "ghp_SUPER_SECRET_TOKEN_DO_NOT_LEAK_12345"
        monkeypatch.setenv("GITHUB_TOKEN", secret_token)

        out_svg = tmp_path / "leak_check.svg"

        mock_response = {
            "data": {
                "user": {
                    "login": "safe-user",
                    "contributionsCollection": {
                        "contributionCalendar": {
                            "totalContributions": 1,
                            "weeks": [
                                {
                                    "contributionDays": [
                                        {
                                            "date": "2025-01-01",
                                            "contributionCount": 1,
                                            "contributionLevel": "FIRST_QUARTILE",
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

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_fp = io.BytesIO(json.dumps(mock_response).encode("utf-8"))
            mock_resp = MagicMock()
            mock_resp.read.side_effect = mock_fp.read
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            ret = main(
                [
                    "generate",
                    "--username",
                    "safe-user",
                    "--token",
                    secret_token,
                    "--output",
                    str(out_svg),
                ]
            )

        assert ret == 0
        captured = capsys.readouterr()

        # Token must NEVER appear in stdout or stderr
        assert secret_token not in captured.out, "Secret token leaked into stdout!"
        assert secret_token not in captured.err, "Secret token leaked into stderr!"

        # Token must NEVER appear in generated SVG file
        svg_content = out_svg.read_text(encoding="utf-8")
        assert secret_token not in svg_content, "Secret token leaked into SVG output!"


class TestConsumerWorkflow:
    """Test suite for the example consumer profile workflow."""

    def test_least_privilege_permissions(self, consumer_workflow_data: dict) -> None:
        perms = consumer_workflow_data.get("permissions")
        assert perms == {"contents": "write"}, (
            "Consumer workflow must strictly use least-privilege 'contents: write'"
        )

    def test_schedule_and_triggers(self, consumer_workflow_data: dict) -> None:
        on = consumer_workflow_data.get("on") or consumer_workflow_data.get(True)
        assert "schedule" in on
        assert "workflow_dispatch" in on

    def test_idempotent_commit_logic(self) -> None:
        wf_path = Path(__file__).parent.parent / "examples/workflows/generate-profile-city.yml"
        content = wf_path.read_text(encoding="utf-8")
        assert "git diff --staged --quiet" in content, (
            "Workflow must check for git diff before committing"
        )
        assert "[skip ci]" in content, (
            "Commit message should include [skip ci] to avoid recursive runs"
        )
