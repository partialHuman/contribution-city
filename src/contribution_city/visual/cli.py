"""Command-line entry points for the gallery and the visual regression suite."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from contribution_city.svgcheck import check_svg
from contribution_city.visual import VisualDependencyError

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


def add_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Register ``gallery``, ``visual`` and ``check-svg`` on the main parser."""
    gal = subparsers.add_parser(
        "gallery",
        help="Render every theme/layout case to SVG + PNG with a contact sheet and manifest",
        description="Generate the preview gallery from deterministic local fixtures (no network).",
    )
    gal.add_argument(
        "-o", "--output-dir", default="gallery", help="Output directory (default: gallery)"
    )
    gal.add_argument("--thumb-width", type=int, default=360, help="Thumbnail width in pixels")
    gal.add_argument("--columns", type=int, default=4, help="Contact sheet columns")
    gal.add_argument("--case", dest="cases", action="append", help="Only this case id (repeatable)")
    gal.add_argument(
        "--tag", dest="tags", action="append", help="Only cases with this tag (repeatable)"
    )
    gal.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit with status 1 if any case failed to render or failed SVG validation",
    )

    vis = subparsers.add_parser(
        "visual",
        help="Visual regression: list, check or approve reference renders",
        description="Compare renders with approved baselines. Baselines are only written by 'approve'.",
    )
    vsub = vis.add_subparsers(dest="visual_command", required=True)

    lst = vsub.add_parser("list", help="List visual cases")
    lst.add_argument("--baseline-only", action="store_true", help="Only cases with a baseline")

    for name, helptext in (
        ("check", "Compare current renders with approved baselines (never writes baselines)"),
        ("approve", "Write or replace approved baselines (requires --yes)"),
    ):
        sp = vsub.add_parser(name, help=helptext)
        sp.add_argument("--baseline-dir", default="tests/visual/baselines")
        sp.add_argument(
            "--case", dest="cases", action="append", help="Only this case id (repeatable)"
        )
        sp.add_argument("--width", type=int, default=560, help="Render width in pixels")
        if name == "check":
            sp.add_argument(
                "--artifacts-dir",
                default="visual-artifacts",
                help="Where current/baseline/diff images of failures are written",
            )
        else:
            sp.add_argument("--yes", action="store_true", help="Confirm writing baseline files")

    chk = subparsers.add_parser(
        "check-svg",
        help="Validate generated SVG files (well-formed, unique ids, no external references)",
    )
    chk.add_argument("files", nargs="+", help="SVG files to check")
    chk.add_argument("--strict", action="store_true", help="Treat accessibility warnings as errors")


def _need_extras(fn):
    def wrapper(args):
        try:
            return fn(args)
        except VisualDependencyError as err:
            sys.stderr.write(f"Missing dependency: {err}\n")
            return EXIT_USAGE

    return wrapper


@_need_extras
def run_gallery(args: argparse.Namespace) -> int:
    from contribution_city.visual.cases import build_cases
    from contribution_city.visual.gallery import generate_gallery, select_cases

    try:
        cases = select_cases(build_cases(), args.cases, args.tags)
    except KeyError as err:
        sys.stderr.write(f"Error: {err.args[0]}\n")
        return EXIT_USAGE
    if not cases:
        sys.stderr.write("Error: no cases match the given --case/--tag filters.\n")
        return EXIT_USAGE

    manifest = generate_gallery(args.output_dir, cases, args.thumb_width, args.columns)
    t = manifest["totals"]
    print(
        f"[gallery] {t['cases']} cases: {t['ok']} ok, {t['invalid']} invalid, {t['failed']} failed "
        f"-> {Path(args.output_dir) / 'manifest.json'}"
    )
    for rec in manifest["cases"]:
        if rec["status"] != "ok":
            detail = rec.get("error") or "; ".join(rec["validation"]["errors"])
            sys.stderr.write(f"  {rec['status'].upper():8} {rec['id']}: {detail}\n")
    bad = t["invalid"] + t["failed"]
    return EXIT_FAIL if (bad and args.fail_on_error) else EXIT_OK


@_need_extras
def run_visual(args: argparse.Namespace) -> int:
    from contribution_city.visual import baseline as bl
    from contribution_city.visual.cases import baseline_cases, build_cases
    from contribution_city.visual.gallery import select_cases

    cmd = args.visual_command
    if cmd == "list":
        cases = baseline_cases() if args.baseline_only else build_cases()
        for c in cases:
            mark = "baseline" if c.baseline else "gallery "
            print(f"{c.id:42} {mark}  {', '.join(c.tags)}")
        print(f"{len(cases)} cases")
        return EXIT_OK

    pool = baseline_cases()
    try:
        cases = select_cases(pool, args.cases) if args.cases else pool
    except KeyError as err:
        sys.stderr.write(f"Error: {err.args[0]} (only baseline cases can be checked or approved)\n")
        return EXIT_USAGE

    if cmd == "approve":
        if not args.yes:
            print("Dry run: these baselines would be written (nothing changed):")
            for c in cases:
                print(f"  {bl.baseline_path(c.id, args.baseline_dir)}")
            print("Review the renders first (contribution-city gallery), then re-run with --yes.")
            return EXIT_USAGE
        written = bl.approve_cases(cases, args.baseline_dir, args.width)
        print(f"Approved {len(written)} baselines in {args.baseline_dir}")
        return EXIT_OK

    results = bl.check_cases(cases, args.baseline_dir, Path(args.artifacts_dir), args.width)
    failed = [r for r in results if not r.ok]
    for r in results:
        if not r.ok:
            sys.stderr.write(f"  {r.status.upper():9} {r.case_id}: {r.message}\n")
    orphans = bl.orphaned_baselines(build_cases(), args.baseline_dir)
    for path in orphans:
        sys.stderr.write(f"  ORPHAN    {path.name}: no baseline case uses this file any more\n")
    print(
        f"[visual] {len(results)} compared: {len(results) - len(failed)} match, "
        f"{len(failed)} need attention" + (f"; artifacts in {args.artifacts_dir}" if failed else "")
    )
    return EXIT_FAIL if (failed or orphans) else EXIT_OK


def run_check_svg(args: argparse.Namespace) -> int:
    status = EXIT_OK
    for name in args.files:
        path = Path(name)
        if not path.is_file():
            sys.stderr.write(f"{name}: file not found\n")
            status = EXIT_FAIL
            continue
        report = check_svg(path.read_text(encoding="utf-8"))
        problems = list(report.errors) + (list(report.warnings) if args.strict else [])
        if problems:
            status = EXIT_FAIL
            for p in problems:
                sys.stderr.write(f"{name}: {p}\n")
        else:
            print(f"{name}: OK ({report.ids} ids, {report.references} references)")
    return status


def dump_json(data) -> None:  # pragma: no cover - convenience for scripts
    print(json.dumps(data, indent=2))
