"""Structure tests for the repository's workflows and the example workflows."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent


def load(path: str) -> dict:
    data = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    # PyYAML reads the key `on` as boolean True
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


def uses_lines(path: str) -> list[str]:
    text = (ROOT / path).read_text(encoding="utf-8")
    return re.findall(r"uses:\s*(\S+)", text)


class TestRepositoryCi:
    def test_ci_is_read_only_and_has_the_expected_jobs(self) -> None:
        wf = load(".github/workflows/tests.yml")
        assert wf["permissions"] == {"contents": "read"}
        assert {"lint", "test", "visual", "build"} <= set(wf["jobs"])

    def test_ci_runs_on_pushes_and_pull_requests_to_main_only(self) -> None:
        on = load(".github/workflows/tests.yml")["on"]
        assert on["push"]["branches"] == ["main"] and on["pull_request"]["branches"] == ["main"]

    def test_visual_job_uploads_failure_artifacts_and_the_gallery(self) -> None:
        steps = load(".github/workflows/tests.yml")["jobs"]["visual"]["steps"]
        uploads = [s for s in steps if "upload-artifact" in s.get("uses", "")]
        assert {u["with"]["name"] for u in uploads} == {
            "visual-regression-failures",
            "contribution-city-gallery",
        }
        failure_upload = next(
            u for u in uploads if u["with"]["name"] == "visual-regression-failures"
        )
        assert failure_upload["if"] == "failure()"

    def test_ci_never_approves_baselines(self) -> None:
        text = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        assert "visual approve" not in text

    def test_matrix_skips_pixel_baselines_which_run_in_the_visual_job(self) -> None:
        text = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        assert 'pytest --tb=short -m "not baseline"' in text
        assert "pytest --tb=short -m baseline" in text

    def test_all_third_party_actions_are_pinned_to_a_commit(self) -> None:
        for wf in (".github/workflows/tests.yml", "action.yml", *_examples()):
            for ref in uses_lines(wf):
                if ref.startswith(("./", "partialHuman/")):
                    continue
                assert re.search(r"@[0-9a-f]{40}$", ref), f"{wf}: {ref}"

    def test_build_job_checks_the_reported_version(self) -> None:
        steps = load(".github/workflows/tests.yml")["jobs"]["build"]["steps"]
        assert any("contribution_city.__version__" in s.get("run", "") for s in steps)


def _examples() -> list[str]:
    return [p.relative_to(ROOT).as_posix() for p in (ROOT / "examples/workflows").glob("*.yml")]


class TestExampleWorkflows:
    def test_gallery_example_only_reads_the_repository(self) -> None:
        wf = load("examples/workflows/gallery-artifact.yml")
        assert wf["permissions"] == {"contents": "read"}
        steps = wf["jobs"]["gallery"]["steps"]
        assert any("upload-artifact" in s.get("uses", "") for s in steps)
        assert not any("git push" in s.get("run", "") for s in steps)

    def test_commit_example_writes_only_where_it_commits_and_cannot_loop(self) -> None:
        path = "examples/workflows/generate-profile-city.yml"
        wf = load(path)
        assert wf["permissions"] == {"contents": "write"}
        triggers = set(wf["on"])
        assert triggers == {"schedule", "workflow_dispatch"}  # never on push, so no loop
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "[skip ci]" in text and "git diff --staged --quiet" in text
        assert "concurrency:" in text

    def test_commit_example_uses_the_new_options(self) -> None:
        text = (ROOT / "examples/workflows/generate-profile-city.yml").read_text(encoding="utf-8")
        assert "partialHuman/contribution-city@v1" in text
        assert "theme: profile-light" in text
