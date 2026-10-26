"""The visual test-case registry.

Cases are generated from the theme and layout registries, so a new theme or layout shows up in the
gallery automatically. Only a curated subset is marked as a *baseline* case; the rest appear in the
gallery and in structural tests but have no stored reference image.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from contribution_city.models import ContributionDataSet
from contribution_city.renderer import CityRenderer, RenderConfig
from contribution_city.renderer.layouts import LAYOUT_NAMES
from contribution_city.renderer.svg import HEIGHT_MODES
from contribution_city.renderer.themes import THEMES
from contribution_city.visual.fixtures import HOSTILE_TITLE, build_fixture

# Header text depends on installed fonts, so most cases hide it. Cases that show it are not
# compared pixel by pixel.
BASE_OPTIONS: dict[str, Any] = {"show_header": False}


@dataclass(frozen=True)
class VisualCase:
    """One reproducible render: fixture + filters + RenderConfig options."""

    id: str
    title: str
    fixture: str = "full-year"
    options: dict[str, Any] = field(default_factory=dict)
    years: tuple[int, ...] = ()
    date_from: str | None = None
    date_to: str | None = None
    tags: tuple[str, ...] = ()
    baseline: bool = False  # has an approved reference image
    pixel_compare: bool = True  # False for font-dependent output
    tolerance: str = "default"  # 'default', 'text' (small text may differ between fonts)

    # -- building blocks -------------------------------------------------

    def dataset(self) -> ContributionDataSet:
        data = build_fixture(self.fixture)
        if self.years or self.date_from or self.date_to:
            data = data.restrict(self.date_from, self.date_to, list(self.years))
        return data

    def render_config(self) -> RenderConfig:
        return RenderConfig(**{**BASE_OPTIONS, **self.options})

    def render_svg(self) -> str:
        return CityRenderer(self.render_config()).render(self.dataset())

    # -- identity --------------------------------------------------------

    def effective_settings(self) -> dict[str, Any]:
        """Normalised settings: two cases with equal settings render identically."""
        cfg = self.render_config()
        renderer = CityRenderer(cfg)  # validates the options
        data = asdict(cfg)
        data["theme"] = renderer.theme.name
        data["layout"] = cfg.layout.lower()
        data["background"] = renderer.background_mode
        data.pop("transparent", None)
        return data

    def effective_key(self) -> str:
        ds = self.dataset()
        days = json.dumps([(d.date, d.count) for d in ds.days], separators=(",", ":"))
        payload = json.dumps(
            {
                "settings": self.effective_settings(),
                "days": hashlib.sha256(days.encode()).hexdigest(),
                "user": ds.username,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def describe(self) -> dict[str, Any]:
        """Machine-readable settings for the manifest."""
        settings = self.effective_settings()
        return {
            "fixture": self.fixture,
            "years": list(self.years),
            "date_from": self.date_from,
            "date_to": self.date_to,
            "theme": settings["theme"],
            "layout": settings["layout"],
            "background": settings["background"],
            "appearance": settings["appearance"],
            "height_mode": settings["height_mode"],
            "width": settings["width"],
            "height": settings["height"],
            "building_scale": settings["building_scale"],
            "show_tooltips": settings["show_tooltips"],
            "auto_fit": settings["auto_fit"],
            "settings": settings,
        }


def _case(id_: str, title: str, *, tags: tuple[str, ...] = (), **kw: Any) -> VisualCase:
    return VisualCase(id=id_, title=title, tags=tags, **kw)


def raw_cases() -> list[VisualCase]:
    """Every case generated from the registries, before de-duplication."""
    cases: list[VisualCase] = []

    # Every theme on the default layout
    for name in THEMES:
        cases.append(
            _case(f"theme-{name}", name, tags=("theme",), options={"theme": name}, baseline=True)
        )

    # Every layout with the default theme (calendar is covered by the theme cases)
    for name in LAYOUT_NAMES:
        if name == "calendar":
            continue
        cases.append(
            _case(f"layout-{name}", name, tags=("layout",), options={"layout": name}, baseline=True)
        )

    # New themes shown on the new layouts
    for theme, layout in (
        ("neon-harbor", "downtown"),
        ("cyberpunk", "dense-grid"),
        ("emerald-matrix", "wireframe"),
        ("copper-forge", "dense-grid"),
        ("arctic-glass", "floating-island"),
        ("sunset-grid", "floating-island"),
    ):
        cases.append(
            _case(
                f"combo-{theme}-{layout}",
                f"{theme} / {layout}",
                tags=("theme", "layout"),
                options={"theme": theme, "layout": layout},
            )
        )

    # Height modes
    for mode in HEIGHT_MODES:
        cases.append(
            _case(
                f"height-{mode}",
                f"height {mode}",
                tags=("height",),
                options={"height_mode": mode},
                baseline=mode != "power",
            )
        )

    # Background modes (and the legacy flag), appearance
    for mode in ("solid", "transparent", "transparent-sky", "auto"):
        cases.append(
            _case(
                f"background-{mode}",
                f"background {mode}",
                tags=("background",),
                options={"background": mode},
                baseline=mode in ("transparent", "transparent-sky"),
            )
        )
    cases += [
        _case(
            "background-legacy-transparent",
            "legacy transparent=True",
            tags=("background", "compat"),
            options={"transparent": True},
        ),
        _case(
            "background-auto-with-appearance-auto",
            "background auto + appearance auto",
            tags=("background", "appearance"),
            options={"theme": "profile", "background": "auto", "appearance": "auto"},
        ),
        _case(
            "appearance-auto-profile",
            "appearance auto (profile)",
            tags=("appearance",),
            options={"theme": "profile", "appearance": "auto"},
        ),
        _case(
            "appearance-fixed-profile-light",
            "profile-light on a solid page",
            tags=("appearance",),
            options={"theme": "profile-light", "background": "transparent"},
        ),
    ]

    # Layout-related switches
    cases += [
        _case("tooltips-off", "tooltips off", tags=("tooltips",), options={"show_tooltips": False}),
        _case("fit-off", "auto-fit off", tags=("fit",), options={"auto_fit": False}, baseline=True),
        _case(
            "custom-size",
            "800x450, scale 1.5",
            tags=("size",),
            options={"width": 800, "height": 450, "building_scale": 1.5},
            baseline=True,
        ),
        _case(
            "pixel-art-off",
            "smooth edges",
            tags=("render",),
            options={"pixel_art": False},
        ),
    ]

    # Fixtures
    for fixture in ("minimal", "empty", "isolated-peaks", "uniform", "long-streak", "extreme"):
        cases.append(
            _case(
                f"fixture-{fixture}",
                fixture,
                tags=("fixture",),
                fixture=fixture,
                baseline=True,
                # the empty city draws a small placeholder sentence, which depends on fonts
                tolerance="text" if fixture == "empty" else "default",
            )
        )
    cases.append(
        _case(
            "fixture-special-chars",
            "special characters (header off)",
            tags=("fixture", "escaping"),
            fixture="special-chars",
            baseline=True,
        )
    )
    cases.append(
        _case(
            "fixture-special-chars-header",
            "special characters (header on)",
            tags=("fixture", "escaping", "font-dependent"),
            fixture="special-chars",
            options={"show_header": True, "custom_title": HOSTILE_TITLE},
            pixel_compare=False,
        )
    )

    # Date ranges and calendar years (offline filtering of one fixture)
    cases += [
        _case(
            "year-2025",
            "calendar year 2025",
            tags=("filter",),
            fixture="two-years",
            years=(2025,),
            baseline=True,
        ),
        _case(
            "year-2024",
            "calendar year 2024",
            tags=("filter",),
            fixture="two-years",
            years=(2024,),
        ),
        _case(
            "range-2024-q4",
            "2024-10-01 to 2024-12-31",
            tags=("filter",),
            fixture="two-years",
            date_from="2024-10-01",
            date_to="2024-12-31",
            baseline=True,
        ),
    ]

    # Header on (text rendering depends on installed fonts, so no pixel comparison)
    cases += [
        _case(
            "header-default",
            "header on",
            tags=("header", "font-dependent"),
            options={"show_header": True},
            pixel_compare=False,
        ),
        _case(
            "header-profile-light",
            "header on (profile-light)",
            tags=("header", "font-dependent"),
            options={"show_header": True, "theme": "profile-light"},
            pixel_compare=False,
        ),
    ]

    return cases


def build_cases() -> list[VisualCase]:
    """All gallery cases, generated from the registries and de-duplicated."""
    return dedupe(raw_cases())


def dedupe(cases: list[VisualCase]) -> list[VisualCase]:
    """Drop cases whose effective settings, data and user are identical to an earlier case."""
    seen: dict[str, str] = {}
    unique: list[VisualCase] = []
    for case in cases:
        key = case.effective_key()
        if key in seen:
            continue
        seen[key] = case.id
        unique.append(case)
    return unique


def baseline_cases(cases: list[VisualCase] | None = None) -> list[VisualCase]:
    """The curated subset that has approved reference images."""
    return [c for c in (cases if cases is not None else build_cases()) if c.baseline]


def get_case(case_id: str) -> VisualCase:
    for case in build_cases():
        if case.id == case_id:
            return case
    valid = ", ".join(c.id for c in build_cases())
    raise KeyError(f"Unknown visual case '{case_id}'. Available: {valid}")
