"""Generate the browsable SVG preview gallery (``previews/``) and the README grids.

Every file is produced by the real renderer from deterministic sample data, so the gallery can be
regenerated, and checked for staleness, with one command::

    contribution-city previews --readme README.md
    contribution-city previews --check --readme README.md
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from html import escape
from pathlib import Path
from typing import Any

from contribution_city._version import __version__
from contribution_city.renderer import CityRenderer, RenderConfig
from contribution_city.renderer.layouts import LAYOUT_SPECS
from contribution_city.renderer.presets import VIEW_ANGLES
from contribution_city.renderer.svg import HEIGHT_MODES
from contribution_city.renderer.themes import THEMES
from contribution_city.svgcheck import check_svg
from contribution_city.visual.fixtures import build_fixture

FIXTURE = "preview"
CANVAS = {"width": 720, "height": 420}
# Small files: no tooltips, no header. Everything else is the documented default.
BASE = {**CANVAS, "show_tooltips": False, "show_header": False, "id_prefix": "pv"}

CATEGORIES = (
    ("themes", "Themes", "Every theme, default settings (calendar layout, standard heights)."),
    ("layouts", "Layouts", "Every layout with the default theme."),
    ("heights", "Heights", "Height presets (the overall profile) and height modes (the curve)."),
    ("building-styles", "Building styles", "Detailed (windows, beacons) and solid (plain boxes)."),
    ("viewing-angles", "Viewing angles", "The camera presets, from low to top-down."),
    ("backgrounds", "Backgrounds", "solid, transparent, transparent-sky and auto."),
)

# Sample setups per category, so the files within a category differ in one thing only
HEIGHTS_BASE = {"layout": "dense-grid", "theme": "neon-harbor"}
STYLES_BASE = {"layout": "dense-grid", "theme": "copper-forge"}
VIEWS_BASE = {"layout": "dense-grid", "theme": "arctic-glass"}
BACKGROUNDS_BASE = {"layout": "dense-grid", "theme": "cyberpunk"}

CHECKER_DARK, CHECKER_LIGHT = "#2b3140", "#3a4254"


@dataclass(frozen=True)
class PreviewSpec:
    """One preview: where it goes, what it shows, and how it is made."""

    category: str
    name: str  # file stem
    label: str
    options: dict[str, Any]
    cli: str  # the documented flags that produce it
    checker: bool = False  # also write an "on checkerboard" companion for transparent output
    note: str = ""

    @property
    def path(self) -> str:
        return f"{self.category}/{self.name}.svg"

    @property
    def checker_path(self) -> str:
        return f"{self.category}/{self.name}.on-checkerboard.svg"

    def config(self) -> RenderConfig:
        return RenderConfig(**{**BASE, **self.options})


def _spec(category: str, name: str, label: str, cli: str, **options: Any) -> PreviewSpec:
    checker = options.pop("_checker", False)
    note = options.pop("_note", "")
    return PreviewSpec(category, name, label, options, cli, checker, note)


def preview_specs() -> list[PreviewSpec]:
    """All previews, generated from the registries (a new theme or layout appears automatically)."""
    specs: list[PreviewSpec] = []

    for name in THEMES:
        specs.append(_spec("themes", name, name, f"--theme {name}", theme=name))

    for name in LAYOUT_SPECS:
        specs.append(_spec("layouts", name, name, f"--layout {name}", layout=name))

    # Heights: presets first, then the four modes under each preset
    specs.append(
        _spec(
            "heights", "standard", "standard (default)", "--height-preset standard", **HEIGHTS_BASE
        )
    )
    specs.append(
        _spec(
            "heights",
            "tall-custom",
            "tall",
            "--height-preset tall",
            height_preset="tall",
            **HEIGHTS_BASE,
        )
    )
    specs.append(
        _spec(
            "heights",
            "custom-scale-1-5-max-90",
            "custom: scale 1.5, max 90",
            "--height-preset custom --scale 1.5 --max-building-height 90",
            height_preset="custom",
            building_scale=1.5,
            max_building_height=90.0,
            **HEIGHTS_BASE,
        )
    )
    for preset in ("standard", "tall"):
        for mode in HEIGHT_MODES:
            if mode == "power":
                continue  # power is the default curve: identical to the preset files above
            name = f"{preset}-{mode}"
            extra = {"height_preset": "tall"} if preset == "tall" else {}
            specs.append(
                _spec(
                    "heights",
                    name,
                    f"{preset} + {mode}",
                    f"--height-preset {preset} --height-mode {mode}",
                    height_mode=mode,
                    **extra,
                    **HEIGHTS_BASE,
                )
            )

    for style in ("detailed", "solid"):
        specs.append(
            _spec(
                "building-styles",
                style,
                style,
                f"--building-style {style}",
                building_style=style,
                height_preset="tall",
                **STYLES_BASE,
            )
        )

    for name, view in VIEW_ANGLES.items():
        file = "standard-isometric" if name == "isometric" else name
        specs.append(
            _spec(
                "viewing-angles",
                file,
                f"{name} ({view.elevation:g} deg)",
                f"--view-angle {name}",
                view_angle=name,
                **VIEWS_BASE,
            )
        )

    specs += [
        _spec(
            "backgrounds",
            "solid",
            "solid",
            "--background solid",
            background="solid",
            **BACKGROUNDS_BASE,
        ),
        _spec(
            "backgrounds",
            "transparent",
            "transparent",
            "--background transparent",
            background="transparent",
            _checker=True,
            **BACKGROUNDS_BASE,
        ),
        _spec(
            "backgrounds",
            "transparent-sky",
            "transparent-sky",
            "--background transparent-sky",
            background="transparent-sky",
            _checker=True,
            **BACKGROUNDS_BASE,
        ),
        _spec(
            "backgrounds",
            "auto-with-auto-appearance",
            "auto + appearance auto",
            "--background auto --appearance auto --theme profile",
            background="auto",
            appearance="auto",
            layout="dense-grid",
            theme="profile",
            _checker=True,
            _note="Resolves to transparent-sky; carries a dark and a light palette.",
        ),
    ]
    return specs


# --------------------------------------------------------------------------- rendering


_FLAGS = {
    "theme": "--theme",
    "layout": "--layout",
    "height_preset": "--height-preset",
    "height_mode": "--height-mode",
    "building_scale": "--scale",
    "min_building_height": "--min-building-height",
    "max_building_height": "--max-building-height",
    "building_style": "--building-style",
    "view_angle": "--view-angle",
    "view_elevation": "--view-elevation",
    "background": "--background",
    "appearance": "--appearance",
}


def full_cli(spec: PreviewSpec) -> list[str]:
    """The complete ``contribution-city generate`` arguments (minus input/output) for a preview.

    This is the documented configuration: running it on the sample data gives exactly the file.
    """
    args = [
        "--no-tooltips",
        "--no-header",
        "--width",
        str(CANVAS["width"]),
        "--height",
        str(CANVAS["height"]),
    ]
    args += ["--id-prefix", str(BASE["id_prefix"])]
    for key, flag in _FLAGS.items():
        if key in spec.options:
            args += [flag, str(spec.options[key])]
    return args


def sample_days() -> list[dict[str, Any]]:
    """The sample data as the JSON structure ``--input`` reads."""
    data = build_fixture(FIXTURE)
    return [{"date": d.date, "count": d.count} for d in data.days]


def render_spec(spec: PreviewSpec) -> str:
    return CityRenderer(spec.config()).render(build_fixture(FIXTURE))


def normalise(svg: str) -> str:
    """Drop provenance metadata some tools embed into saved SVG files (not part of the drawing)."""
    return re.sub(r'\s+xmlns:c2pa="[^"]*"|<metadata>.*?</metadata>', "", svg, flags=re.DOTALL)


def checkerboard_preview(svg: str, title: str) -> str:
    """Wrap an SVG on a checkerboard so transparency is visible. The original is not modified."""
    root = re.search(r'<svg[^>]*\swidth="(\d+)"[^>]*\sheight="(\d+)"', svg)
    if not root:  # pragma: no cover - the renderer always writes both
        raise ValueError("cannot find the canvas size")
    w, h = root.group(1), root.group(2)
    inner = svg.split("?>", 1)[1].strip() if svg.startswith("<?xml") else svg
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        'role="img" aria-labelledby="checker-title">\n'
        f'  <title id="checker-title">{escape(title)} on a checkerboard (preview only)</title>\n'
        '  <defs><pattern id="checker" width="24" height="24" patternUnits="userSpaceOnUse">'
        f'<rect width="24" height="24" fill="{CHECKER_DARK}"/>'
        f'<rect width="12" height="12" fill="{CHECKER_LIGHT}"/>'
        f'<rect x="12" y="12" width="12" height="12" fill="{CHECKER_LIGHT}"/></pattern></defs>\n'
        f'  <rect width="{w}" height="{h}" fill="url(#checker)"/>\n'
        f"  {inner}\n"
        "</svg>\n"
    )


@dataclass
class PreviewResult:
    spec: PreviewSpec
    svg: str
    file: str  # canonical file (may belong to an earlier identical spec)
    alias_of: str | None = None
    checker_svg: str | None = None
    valid: dict[str, Any] = field(default_factory=dict)


def build_previews() -> list[PreviewResult]:
    """Render every spec; identical output is written once and referenced by the later specs."""
    results: list[PreviewResult] = []
    seen: dict[str, str] = {}
    for spec in preview_specs():
        svg = render_spec(spec)
        key = normalise(svg)
        if key in seen:
            results.append(PreviewResult(spec, svg, seen[key], alias_of=seen[key]))
            continue
        seen[key] = spec.path
        res = PreviewResult(spec, svg, spec.path, valid=check_svg(svg).to_dict())
        if spec.checker:
            res.checker_svg = checkerboard_preview(svg, spec.label)
        results.append(res)
    return results


def display_file(res: PreviewResult) -> str:
    """The file a README grid should show (the checkerboard companion for transparent output)."""
    return res.spec.checker_path if res.checker_svg else res.file


# --------------------------------------------------------------------------- markdown


def _cell(res: PreviewResult, root: str, columns: int) -> str:
    spec = res.spec
    img = f"{root}/{display_file(res)}"
    link = f"{root}/{res.file}"
    alias = f"<br><sub>same file as <code>{res.alias_of}</code></sub>" if res.alias_of else ""
    note = f"<br><sub>{escape(spec.note)}</sub>" if spec.note else ""
    return (
        f'<td align="center" valign="top" width="{100 // columns}%">'
        f'<a href="{link}"><img src="{img}" width="100%" alt="{escape(spec.label)}"></a><br>'
        f"<sub><b>{escape(spec.label)}</b><br><code>{escape(spec.cli)}</code></sub>{alias}{note}</td>"
    )


def grid(results: list[PreviewResult], root: str, columns: int = 4) -> str:
    rows = []
    for i in range(0, len(results), columns):
        chunk = results[i : i + columns]
        cells = "".join(_cell(r, root, columns) for r in chunk)
        cells += "".join(
            f'<td width="{100 // columns}%"></td>' for _ in range(columns - len(chunk))
        )
        rows.append(f"<tr>{cells}</tr>")
    return "<table>\n" + "\n".join(rows) + "\n</table>"


def by(
    results: list[PreviewResult], category: str, names: list[str] | None = None
) -> list[PreviewResult]:
    chosen = [r for r in results if r.spec.category == category]
    if names is not None:
        chosen = [next(r for r in chosen if r.spec.name == n) for n in names]
    return chosen


def relabel(items: list[PreviewResult], labels: dict[str, tuple[str, str]]) -> list[PreviewResult]:
    """Same files, captions that name what the surrounding grid varies (here: the height mode)."""
    out = []
    for r in items:
        if r.spec.name in labels:
            label, cli = labels[r.spec.name]
            r = replace(r, spec=replace(r.spec, label=label, cli=cli))
        out.append(r)
    return out


def readme_blocks(results: list[PreviewResult], root: str = "previews") -> dict[str, str]:
    """Markdown for the marked blocks of the root README."""
    presets = ["standard", "tall-custom", "custom-scale-1-5-max-90"]
    standard_modes = ["standard", "standard-linear", "standard-sqrt", "standard-log"]
    tall_modes = ["tall-custom", "tall-linear", "tall-sqrt", "tall-log"]
    mode_names = {
        "standard": ("power (default curve)", "--height-mode power"),
        "standard-linear": ("linear", "--height-mode linear"),
        "standard-sqrt": ("sqrt", "--height-mode sqrt"),
        "standard-log": ("log", "--height-mode log"),
        "tall-custom": ("power (default curve)", "--height-mode power"),
        "tall-linear": ("linear", "--height-mode linear"),
        "tall-sqrt": ("sqrt", "--height-mode sqrt"),
        "tall-log": ("log", "--height-mode log"),
    }
    return {
        "themes": grid(by(results, "themes"), root),
        "layouts": grid(by(results, "layouts"), root),
        "heights-presets": grid(by(results, "heights", presets), root, 3),
        "heights-standard-modes": grid(
            relabel(by(results, "heights", standard_modes), mode_names), root
        ),
        "heights-tall-modes": grid(relabel(by(results, "heights", tall_modes), mode_names), root),
        "building-styles": grid(by(results, "building-styles"), root, 2),
        "viewing-angles": grid(by(results, "viewing-angles"), root),
        "backgrounds": grid(by(results, "backgrounds"), root),
    }


def replace_block(text: str, name: str, content: str) -> str:
    start, end = f"<!-- previews:{name}:start -->", f"<!-- previews:{name}:end -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise ValueError(f"README has no '{name}' preview block ({start} ... {end})")
    return pattern.sub(lambda _m: f"{start}\n{content}\n{end}", text)


def apply_readme(text: str, blocks: dict[str, str]) -> str:
    for name, content in blocks.items():
        text = replace_block(text, name, content)
    return text


def category_readme(category: str, title: str, blurb: str, results: list[PreviewResult]) -> str:
    items = by(results, category)
    cols = 3 if len(items) <= 9 else 4
    lines = [
        f"# {title}",
        "",
        blurb,
        "",
        "Click a preview to open the SVG. Each file was produced by `contribution-city generate` "
        "with the flags shown under it (plus `--no-tooltips --no-header`, a 720x420 canvas and the "
        "deterministic sample data described in the [gallery index](../README.md)).",
        "",
        grid(items, "..", cols),
        "",
        "[Back to the gallery index](../README.md) | [Customization guide](../../examples/README.md)",
        "",
    ]
    return "\n".join(lines)


def index_readme(results: list[PreviewResult]) -> str:
    counts = {c: len({r.file for r in results if r.spec.category == c}) for c, _, _ in CATEGORIES}
    rows = "\n".join(
        f"| [{title}]({cat}/README.md) | {blurb} | {counts[cat]} |"
        for cat, title, blurb in CATEGORIES
    )
    return f"""# Preview gallery

Every SVG here is generated by the real Contribution City renderer. Open a category to browse its
files, or use the grids in the [root README](../README.md).

| Category | What it shows | SVG files |
|---|---|---|
{rows}

## How these files are made

- **Sample data:** the deterministic `preview` fixture (16 weeks, a few busy spells and one
  standout day, user `preview-user`). It never changes, so the previews only change when the
  renderer does.
- **Settings:** the default settings, plus the flags printed under each preview. The heights,
  building-style, viewing-angle and background categories use a dense-grid city so towers are easy
  to compare; each category changes one thing only.
- **Size:** 720x420 canvas, `--no-tooltips`, no header text. Typical file size is 40-90 KB.
- **Identical output is stored once.** For example the layout `calendar` preview is the same file as
  `themes/navy-cyan.svg`; the grids say "same file as ...".
- **Transparent previews:** GitHub shows transparency as the page colour, so each transparent file
  has a companion `*.on-checkerboard.svg`. The companion only adds a checkerboard behind the
  unchanged SVG; the real files stay transparent.
- **Regenerate:** `contribution-city previews --readme README.md` rewrites this folder and the
  grids; `contribution-city previews --check --readme README.md` fails if anything is out of date.
  `manifest.json` lists every file with its settings and validation result.

[Customization guide](../examples/README.md) | [Project README](../README.md)
"""


# --------------------------------------------------------------------------- writing


def build_manifest(results: list[PreviewResult]) -> dict[str, Any]:
    files = []
    for r in results:
        entry = {
            "id": f"{r.spec.category}/{r.spec.name}",
            "label": r.spec.label,
            "category": r.spec.category,
            "cli": r.spec.cli,
            "file": r.file,
            "alias_of": r.alias_of,
            "checkerboard_companion": r.spec.checker_path if r.checker_svg else None,
            "settings": {k: v for k, v in {**BASE, **r.spec.options}.items() if k != "id_prefix"},
        }
        if r.alias_of is None:
            entry["bytes"] = len(r.svg.encode("utf-8"))
            entry["valid"] = r.valid.get("ok", False)
            entry["errors"] = r.valid.get("errors", [])
        files.append(entry)
    unique = [f for f in files if f["alias_of"] is None]
    return {
        "contribution_city_version": __version__,
        "fixture": FIXTURE,
        "canvas": CANVAS,
        "totals": {
            "previews": len(files),
            "files": len(unique),
            "aliases": len(files) - len(unique),
        },
        "previews": files,
    }


def planned_files(results: list[PreviewResult]) -> dict[str, str]:
    """Relative path -> file content for everything the gallery consists of."""
    out: dict[str, str] = {}
    for r in results:
        if r.alias_of is None:
            out[r.spec.path] = r.svg
            if r.checker_svg:
                out[r.spec.checker_path] = r.checker_svg
    for cat, title, blurb in CATEGORIES:
        out[f"{cat}/README.md"] = category_readme(cat, title, blurb, results)
    out["README.md"] = index_readme(results)
    out["manifest.json"] = json.dumps(build_manifest(results), indent=2) + "\n"
    return out


def generate_previews(output_dir: Path | str, readme: Path | str | None = None) -> dict[str, Any]:
    """Write the gallery (and the README grids, when ``readme`` is given). Returns the manifest."""
    out = Path(output_dir)
    results = build_previews()
    files = planned_files(results)
    for rel in [p for p in out.rglob("*") if p.is_file() and p.suffix == ".svg"]:
        rel.unlink()  # stale previews from removed themes/options disappear
    for rel, content in files.items():
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    if readme:
        path = Path(readme)
        path.write_text(
            apply_readme(path.read_text(encoding="utf-8"), readme_blocks(results, out.name)),
            encoding="utf-8",
        )
    return json.loads(files["manifest.json"])


def check_previews(output_dir: Path | str, readme: Path | str | None = None) -> list[str]:
    """Return a list of problems: missing, stale or unexpected files and out-of-date README grids."""
    out = Path(output_dir)
    results = build_previews()
    problems: list[str] = []
    expected = planned_files(results)
    for rel, content in expected.items():
        path = out / rel
        if not path.is_file():
            problems.append(f"missing: {out.name}/{rel}")
        elif normalise(path.read_text(encoding="utf-8")) != normalise(content):
            problems.append(f"out of date: {out.name}/{rel}")
    if out.exists():
        for path in out.rglob("*.svg"):
            if path.relative_to(out).as_posix() not in expected:
                problems.append(f"unexpected: {out.name}/{path.relative_to(out).as_posix()}")
    if readme:
        text = Path(readme).read_text(encoding="utf-8")
        try:
            if apply_readme(text, readme_blocks(results, out.name)) != text:
                problems.append(f"out of date: preview grids in {Path(readme).name}")
        except ValueError as err:
            problems.append(str(err))
    return problems
