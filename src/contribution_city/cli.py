"""Command-line interface for Contribution City."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from contribution_city._version import __version__
from contribution_city.config import AppConfig, ConfigError
from contribution_city.github_api import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubClient,
    GitHubRateLimitError,
    GitHubUserNotFoundError,
)
from contribution_city.models import ContributionDataSet
from contribution_city.renderer import CityRenderer
from contribution_city.renderer.layouts import LAYOUT_SPECS
from contribution_city.renderer.svg import APPEARANCES, BACKGROUND_MODES, HEIGHT_MODES, LAYOUTS
from contribution_city.renderer.themes import LIGHT_PAIRS, THEMES


def _theme_lines() -> str:
    width = max(len(name) for name in THEMES)
    return "\n".join(f"  {name:<{width}}  {theme.description}" for name, theme in THEMES.items())


def _layout_lines() -> str:
    width = max(len(name) for name in LAYOUT_SPECS)
    return "\n".join(
        f"  {name:<{width}}  {spec.description}" for name, spec in LAYOUT_SPECS.items()
    )


def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="contribution-city",
        description="Transform GitHub contribution activity into beautiful isometric pixel-art cities.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate city from sample or local JSON file:
  contribution-city generate --input examples/sample-contributions.json --theme navy-cyan --output dist/city.svg

  # Generate live city from GitHub username (requires GITHUB_TOKEN environment variable or --token):
  contribution-city generate --username octocat --theme matrix-green --output dist/octocat.svg

  # Generate using a YAML configuration file:
  contribution-city generate --config examples/config.example.yaml

  # New in 1.2: layouts, backgrounds and themes
  contribution-city generate --input examples/sample-contributions.json --theme cyberpunk --layout downtown
  contribution-city generate --input examples/sample-contributions.json --layout floating-island --background transparent-sky
  contribution-city generate --input examples/sample-contributions.json --layout wireframe --theme arctic-glass

  # Offline data can be limited to a year or a date range
  contribution-city generate --input examples/sample-contributions.json --from 2025-03-01 --to 2025-06-30

  # Compact skyline layout with custom dimensions:
  contribution-city generate --input examples/sample-contributions.json --layout compact --width 1000 --height 600

Available Themes:
{themes}

Layouts:
{layouts}

Backgrounds: solid | transparent | transparent-sky | auto   (--background overrides --transparent)
Light/dark: use --appearance auto with a theme that has a light variant ({pairs}) to embed both
palettes in one SVG, or generate a dark and a light file and switch them with an HTML <picture>.
Precedence: built-in defaults < configuration file < command-line options.
""".replace("{themes}", _theme_lines())
        .replace("{layouts}", _layout_lines())
        .replace("{pairs}", ", ".join(LIGHT_PAIRS)),
    )

    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    from contribution_city.visual.cli import add_subcommands

    add_subcommands(subparsers)
    gen_parser = subparsers.add_parser("generate", help="Generate isometric city SVG")

    for p in (parser, gen_parser):
        # Allow options either directly or under generate subcommand
        if p == gen_parser:
            p.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
        p.add_argument(
            "-i",
            "--input",
            dest="input_file",
            help="Path to local contributions JSON file (offline / fixture mode)",
        )
        p.add_argument(
            "-u",
            "--username",
            help="GitHub username to fetch live contributions from",
        )
        p.add_argument(
            "-t",
            "--token",
            help="GitHub personal access token (defaults to GITHUB_TOKEN or GH_TOKEN env vars)",
        )
        p.add_argument(
            "-c",
            "--config",
            dest="config_file",
            help="Path to YAML configuration file",
        )
        p.add_argument(
            "-o",
            "--output",
            dest="output_file",
            help="Destination file path for generated SVG (default: dist/city.svg)",
        )
        p.add_argument(
            "--theme",
            choices=list(THEMES.keys()),
            help="Visual theme (default: navy-cyan)",
        )
        p.add_argument(
            "--layout",
            choices=list(LAYOUTS),
            help="Grid layout style (default: calendar)",
        )
        p.add_argument("--width", type=int, help="Canvas width in pixels (min 300)")
        p.add_argument("--height", type=int, help="Canvas height in pixels (min 200)")
        p.add_argument(
            "--scale",
            type=float,
            dest="building_scale",
            help="Building height scaling multiplier (e.g. 1.0, 1.5)",
        )
        p.add_argument(
            "--no-windows",
            dest="show_windows",
            action="store_false",
            default=None,
            help="Disable glowing pixel windows on building sides",
        )
        p.add_argument(
            "--no-stars",
            dest="show_stars",
            action="store_false",
            default=None,
            help="Disable sky constellation stars",
        )
        p.add_argument(
            "--no-header",
            dest="show_header",
            action="store_false",
            default=None,
            help="Disable developer HUD stats header overlay",
        )
        p.add_argument(
            "--no-platform",
            dest="show_platform",
            action="store_false",
            default=None,
            help="Disable ground plinth platform beneath the city",
        )
        p.add_argument(
            "--title",
            dest="custom_title",
            help="Custom title in HUD header",
        )
        p.add_argument(
            "--appearance",
            choices=list(APPEARANCES),
            help="'fixed' (default) or 'auto' (adds the theme's light palette; needs a theme with one)",
        )
        p.add_argument(
            "--height-mode",
            dest="height_mode",
            choices=list(HEIGHT_MODES),
            help="How building height grows with commits (default: power; 'linear' is proportional)",
        )
        p.add_argument(
            "--year",
            dest="years",
            type=int,
            action="append",
            help="Calendar year to include; repeat for several years (works with --username and --input)",
        )
        p.add_argument(
            "--from",
            dest="date_from",
            metavar="YYYY-MM-DD",
            help="First day to include (live data: at most one year long)",
        )
        p.add_argument(
            "--to",
            dest="date_to",
            metavar="YYYY-MM-DD",
            help="Last day to include",
        )
        p.add_argument(
            "--retries",
            type=int,
            help="How many times to retry temporary GitHub API failures (default: 2)",
        )
        p.add_argument(
            "--background",
            choices=list(BACKGROUND_MODES),
            help=(
                "Background mode: solid, transparent (no rectangle, no stars), transparent-sky "
                "(no rectangle, stars kept) or auto. Overrides --transparent when both are given."
            ),
        )
        p.add_argument(
            "--id-prefix",
            dest="id_prefix",
            help="Prefix for element ids and CSS rules; use when inlining several SVGs in one page",
        )
        p.add_argument(
            "--transparent",
            dest="transparent",
            action="store_true",
            default=None,
            help="No background rectangle or stars, so the page behind the image shows through",
        )
        p.add_argument(
            "--no-tooltips",
            dest="show_tooltips",
            action="store_false",
            default=None,
            help="Omit hover tooltips (smaller file)",
        )
        p.add_argument(
            "--no-fit",
            dest="auto_fit",
            action="store_false",
            default=None,
            help="Do not scale the city to fill the canvas",
        )
        p.add_argument(
            "--smooth",
            dest="pixel_art",
            action="store_false",
            default=None,
            help="Use anti-aliased edges instead of hard pixel-art edges",
        )

    return parser


def build_config(args: argparse.Namespace) -> AppConfig:
    """Build and merge configuration from file, defaults, and CLI arguments."""
    # 1. Base from YAML config if supplied
    if args.config_file:
        config = AppConfig.from_file(args.config_file)
    else:
        config = AppConfig()

    # 2. Override with explicit CLI flags
    if args.username is not None:
        config.username = args.username
    if args.input_file is not None:
        config.input_file = args.input_file
    if args.output_file is not None:
        config.output_file = args.output_file
    if args.theme is not None:
        config.theme = args.theme
    if args.layout is not None:
        config.layout = args.layout
    if args.token is not None:
        config.token = args.token
    if args.appearance is not None:
        config.appearance = args.appearance
    if args.years:
        config.years = list(args.years)
    if args.date_from is not None:
        config.date_from = args.date_from
    if args.date_to is not None:
        config.date_to = args.date_to
    if args.retries is not None:
        config.retries = args.retries
    if args.height_mode is not None:
        config.city.height_mode = args.height_mode
    if args.transparent is not None:
        config.city.transparent = args.transparent
    if args.background is not None:
        config.city.background = args.background
    if args.id_prefix is not None:
        config.city.id_prefix = args.id_prefix
    if args.show_tooltips is not None:
        config.city.show_tooltips = args.show_tooltips
    if args.auto_fit is not None:
        config.city.auto_fit = args.auto_fit
    if args.pixel_art is not None:
        config.city.pixel_art = args.pixel_art

    if args.width is not None:
        config.city.width = args.width
    if args.height is not None:
        config.city.height = args.height
    if args.building_scale is not None:
        config.city.building_scale = args.building_scale
    if args.show_windows is not None:
        config.city.show_windows = args.show_windows
    if args.show_stars is not None:
        config.city.show_stars = args.show_stars
    if args.show_header is not None:
        config.city.show_header = args.show_header
    if args.show_platform is not None:
        config.city.show_platform = args.show_platform
    if args.custom_title is not None:
        config.city.custom_title = args.custom_title

    config.validate()
    return config


def load_dataset(config: AppConfig) -> ContributionDataSet:
    """Load contribution dataset from either input file or GitHub API."""
    if config.input_file:
        path = Path(config.input_file)
        if not path.is_file():
            raise FileNotFoundError(f"Input file not found: {path}")
        dataset = ContributionDataSet.from_file(path)
        if config.years or config.date_from or config.date_to:
            dataset = dataset.restrict(config.date_from, config.date_to, config.years)
            if not dataset.days:
                sys.stderr.write(
                    "Note: no days in the selected years/dates; the city will be empty.\n"
                )
        return dataset

    if config.username:
        client = GitHubClient(token=config.token, max_retries=config.retries)
        if config.years:
            return client.fetch_years(config.username, config.years)
        return client.fetch_contributions(config.username, config.date_from, config.date_to)

    raise ValueError(
        "No data source specified. Please provide either --input <file.json> "
        "or --username <github-username>."
    )


def run(args: argparse.Namespace) -> int:
    """Execute city generation pipeline."""
    try:
        config = build_config(args)
    except ConfigError as err:
        sys.stderr.write(f"Configuration Error: {err}\n")
        return 1

    try:
        dataset = load_dataset(config)
    except FileNotFoundError as err:
        sys.stderr.write(f"File Error: {err}\n")
        return 1
    except (GitHubUserNotFoundError, GitHubAuthError, GitHubRateLimitError, GitHubAPIError) as err:
        sys.stderr.write(f"GitHub API Error: {err}\n")
        return 1
    except ValueError as err:
        sys.stderr.write(f"Input Error: {err}\n")
        return 1
    except Exception as err:
        sys.stderr.write(f"Unexpected Error loading data: {err}\n")
        return 1

    # Render SVG
    try:
        render_cfg = config.to_render_config()
        renderer = CityRenderer(render_cfg)
        svg_content = renderer.render(dataset)
    except Exception as err:
        sys.stderr.write(f"Rendering Error: {err}\n")
        return 1

    # Save to output file
    output_path = Path(config.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
    except OSError as err:
        sys.stderr.write(f"Write Error: Could not save output to {output_path}: {err}\n")
        return 1

    user_label = dataset.username or "anonymous"
    print(
        f"[OK] Successfully generated Contribution City for '{user_label}' "
        f"({dataset.total_contributions:,} contributions across {len(dataset.days)} days) -> {output_path}"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)
    if args.command == "gallery":
        from contribution_city.visual.cli import run_gallery

        return run_gallery(args)
    if args.command == "visual":
        from contribution_city.visual.cli import run_visual

        return run_visual(args)
    if args.command == "check-svg":
        from contribution_city.visual.cli import run_check_svg

        return run_check_svg(args)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
