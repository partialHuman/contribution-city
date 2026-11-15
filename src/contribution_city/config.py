"""Configuration schema and validation for Contribution City."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from contribution_city.renderer.presets import (
    HEIGHT_PRESET_NAMES,
    LIMITS,
    VIEW_ANGLE_NAMES,
)
from contribution_city.renderer.svg import (
    APPEARANCES,
    BACKGROUND_MODES,
    BUILDING_STYLES,
    HEIGHT_MODES,
    LAYOUTS,
    RenderConfig,
)
from contribution_city.renderer.themes import THEMES


class ConfigError(Exception):
    """Raised when configuration file or options are invalid."""


def _opt_float(data: dict[str, Any], key: str) -> float | None:
    """A float setting that may be absent (None = use the preset)."""
    value = data.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as err:
        raise ConfigError(f"city.{key} must be a number, got {value!r}") from err


def _opt_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    return None if value is None else str(value)


def _coerce_dim(data: dict[str, Any], key: str, default: int) -> int:
    """Parse a canvas dimension (width / height) with strict type checking.

    Accepts only plain integers (and integer-valued floats like ``1200.0``).
    Rejects ``null``, booleans, non-integer floats, and non-numeric strings —
    all with a readable :class:`ConfigError`.
    """
    value = data.get(key)
    if value is None:
        if key in data:
            # An explicitly supplied YAML null (e.g. ``width:``) is an invalid dimension type.
            raise ConfigError(f"city.{key} must be an integer, got null")
        # When the key is omitted entirely, fall back to the default dimension.
        return default
    if isinstance(value, bool):
        raise ConfigError(f"city.{key} must be an integer, got {value!r}")
    if isinstance(value, float):
        if not math.isfinite(value) or value != int(value):
            raise ConfigError(f"city.{key} must be a whole-number integer, got {value!r}")
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError) as err:
        raise ConfigError(f"city.{key} must be an integer, got {value!r}") from err


@dataclass
class CitySettings:
    """City geometry and visual customization settings."""

    width: int = 1200
    height: int = 680
    tile_width: float = 18.0
    tile_height: float = 9.0
    # Height controls. Unset (None) means "use the preset"; setting building_scale or a min/max
    # height without a preset keeps the 1.2.0 behaviour (preset 'custom').
    height_preset: str | None = None
    building_scale: float | None = None
    min_building_height: float | None = None
    max_building_height: float | None = None
    building_style: str = "detailed"
    view_angle: str | None = None
    view_elevation: float | None = None
    show_windows: bool = True
    show_stars: bool = True
    show_header: bool = True
    show_platform: bool = True
    show_zero_tiles: bool = True
    custom_title: str | None = None
    height_mode: str = "power"
    transparent: bool = False
    show_tooltips: bool = True
    auto_fit: bool = True
    pixel_art: bool = True
    # Background mode (solid | transparent | transparent-sky | auto). When set it takes precedence
    # over the legacy ``transparent`` flag.
    background: str | None = None
    id_prefix: str | None = None

    def validate(self) -> None:
        """Validate city dimensions and scaling factors."""
        if self.background is not None and self.background not in BACKGROUND_MODES:
            raise ConfigError(
                f"city.background must be one of {', '.join(BACKGROUND_MODES)}, "
                f"got '{self.background}'"
            )
        if self.id_prefix is not None and not re.fullmatch(
            r"[A-Za-z][A-Za-z0-9_-]{0,30}", self.id_prefix
        ):
            raise ConfigError(
                f"city.id_prefix '{self.id_prefix}' is invalid: use letters, digits, '-' or '_', "
                "starting with a letter (max 31 characters)."
            )
        if self.height_mode not in HEIGHT_MODES:
            raise ConfigError(
                f"city.height_mode must be one of {', '.join(HEIGHT_MODES)}, got '{self.height_mode}'"
            )
        if not isinstance(self.width, int) or self.width < 300:
            raise ConfigError(f"city.width must be an integer >= 300, got {self.width}")
        if not isinstance(self.height, int) or self.height < 200:
            raise ConfigError(f"city.height must be an integer >= 200, got {self.height}")
        if self.height_preset is not None and self.height_preset not in HEIGHT_PRESET_NAMES:
            raise ConfigError(
                f"city.height_preset must be one of {', '.join(HEIGHT_PRESET_NAMES)}, "
                f"got '{self.height_preset}'"
            )
        if self.building_style not in BUILDING_STYLES:
            raise ConfigError(
                f"city.building_style must be one of {', '.join(BUILDING_STYLES)}, "
                f"got '{self.building_style}'"
            )
        if self.view_angle is not None and self.view_angle not in VIEW_ANGLE_NAMES:
            raise ConfigError(
                f"city.view_angle must be one of {', '.join(VIEW_ANGLE_NAMES)}, "
                f"got '{self.view_angle}'"
            )
        for key in (
            "building_scale",
            "min_building_height",
            "max_building_height",
            "view_elevation",
        ):
            value = getattr(self, key)
            if value is None:
                continue
            lo, hi = LIMITS[key]
            if not lo <= value <= hi:
                raise ConfigError(f"city.{key} must be between {lo} and {hi}, got {value}")
        low = self.min_building_height
        high = self.max_building_height
        if low is not None and high is not None and high < low + 1.0:
            raise ConfigError(
                f"city.max_building_height ({high}) must be at least 1 higher than "
                f"city.min_building_height ({low})"
            )
        if not (4.0 <= self.tile_width <= 64.0) or not math.isfinite(self.tile_width):
            raise ConfigError(
                f"city.tile_width must be between 4.0 and 64.0, got {self.tile_width}"
            )
        if not (4.0 <= self.tile_height <= 64.0) or not math.isfinite(self.tile_height):
            raise ConfigError(
                f"city.tile_height must be between 4.0 and 64.0, got {self.tile_height}"
            )


@dataclass
class AppConfig:
    """Top-level application configuration."""

    username: str | None = None
    input_file: str | None = None
    output_file: str = "dist/city.svg"
    theme: str = "navy-cyan"
    layout: str = "calendar"
    appearance: str = "fixed"
    token: str | None = None
    years: list[int] = field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None
    retries: int = 2
    city: CitySettings = field(default_factory=CitySettings)

    def validate(self) -> None:
        """Validate entire application configuration."""
        valid_themes = list(THEMES.keys())
        if self.theme.lower() not in valid_themes:
            raise ConfigError(
                f"Invalid theme '{self.theme}'. Choose from: {', '.join(valid_themes)}"
            )

        if self.layout.lower() == "isometric":
            raise ConfigError(
                "Layout 'isometric' was removed: the 'calendar' layout already is the isometric "
                "city. Use 'calendar' or 'compact'."
            )
        if self.layout.lower() not in LAYOUTS:
            raise ConfigError(f"Invalid layout '{self.layout}'. Choose from: {', '.join(LAYOUTS)}")

        if self.appearance not in APPEARANCES:
            raise ConfigError(
                f"Invalid appearance '{self.appearance}'. Choose from: {', '.join(APPEARANCES)}"
            )

        this_year = date.today().year
        for year in self.years:
            if not 2008 <= year <= this_year:
                raise ConfigError(
                    f"Invalid year {year}. GitHub started in 2008; max is {this_year}."
                )
        for label, value in (("from", self.date_from), ("to", self.date_to)):
            if value is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value)):
                raise ConfigError(f"'{label}' must be a date like 2025-01-31, got '{value}'")
        if self.years and (self.date_from or self.date_to):
            raise ConfigError("Use either 'years' or 'from'/'to', not both.")
        if not 0 <= self.retries <= 10:
            raise ConfigError(f"retries must be between 0 and 10, got {self.retries}")

        self.city.validate()

    def to_render_config(self) -> RenderConfig:
        """Convert to renderer configuration dataclass."""
        return RenderConfig(
            width=self.city.width,
            height=self.city.height,
            theme=self.theme,
            layout=self.layout.lower(),
            appearance=self.appearance,
            tile_width=self.city.tile_width,
            tile_height=self.city.tile_height,
            height_preset=self.city.height_preset,
            building_scale=self.city.building_scale,
            min_building_height=self.city.min_building_height,
            max_building_height=self.city.max_building_height,
            building_style=self.city.building_style,
            view_angle=self.city.view_angle,
            view_elevation=self.city.view_elevation,
            show_windows=self.city.show_windows,
            show_stars=self.city.show_stars,
            show_header=self.city.show_header,
            show_platform=self.city.show_platform,
            show_zero_tiles=self.city.show_zero_tiles,
            custom_title=self.city.custom_title,
            height_mode=self.city.height_mode,
            transparent=self.city.transparent,
            show_tooltips=self.city.show_tooltips,
            auto_fit=self.city.auto_fit,
            pixel_art=self.city.pixel_art,
            background=self.city.background,
            id_prefix=self.city.id_prefix,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        """Create AppConfig from dictionary with validation."""
        if not isinstance(data, dict):
            raise ConfigError(f"Configuration root must be a mapping, got {type(data).__name__}")

        city_data = data.get("city") or {}
        if not isinstance(city_data, dict):
            raise ConfigError(f"Field 'city' must be a mapping, got {type(city_data).__name__}")

        city_settings = CitySettings(
            width=_coerce_dim(city_data, "width", 1200),
            height=_coerce_dim(city_data, "height", 680),
            tile_width=float(city_data.get("tile_width", 18.0)),
            tile_height=float(city_data.get("tile_height", 9.0)),
            height_preset=_opt_str(city_data, "height_preset"),
            building_scale=_opt_float(city_data, "building_scale"),
            min_building_height=_opt_float(city_data, "min_building_height"),
            max_building_height=_opt_float(city_data, "max_building_height"),
            building_style=str(city_data.get("building_style", "detailed")),
            view_angle=_opt_str(city_data, "view_angle"),
            view_elevation=_opt_float(city_data, "view_elevation"),
            show_windows=bool(city_data.get("show_windows", True)),
            show_stars=bool(city_data.get("show_stars", True)),
            show_header=bool(city_data.get("show_header", True)),
            show_platform=bool(city_data.get("show_platform", True)),
            show_zero_tiles=bool(city_data.get("show_zero_tiles", True)),
            custom_title=city_data.get("custom_title"),
            height_mode=str(city_data.get("height_mode", "power")),
            transparent=bool(city_data.get("transparent", False)),
            show_tooltips=bool(city_data.get("show_tooltips", True)),
            auto_fit=bool(city_data.get("auto_fit", True)),
            pixel_art=bool(city_data.get("pixel_art", True)),
            background=(
                str(city_data["background"]) if city_data.get("background") is not None else None
            ),
            id_prefix=(
                str(city_data["id_prefix"]) if city_data.get("id_prefix") is not None else None
            ),
        )

        raw_years = data.get("years") or []
        if isinstance(raw_years, int):
            raw_years = [raw_years]
        try:
            years = [int(y) for y in raw_years]
        except (TypeError, ValueError) as err:
            raise ConfigError(f"'years' must be a list of integers, got {raw_years!r}") from err
        date_from = data.get("from")
        date_to = data.get("to")

        app_cfg = cls(
            username=data.get("username"),
            input_file=data.get("input") or data.get("input_file"),
            output_file=data.get("output") or data.get("output_file", "dist/city.svg"),
            theme=str(data.get("theme", "navy-cyan")),
            layout=str(data.get("layout", "calendar")),
            appearance=str(data.get("appearance", "fixed")),
            token=data.get("token"),
            years=years,
            date_from=str(date_from) if date_from is not None else None,
            date_to=str(date_to) if date_to is not None else None,
            retries=int(data.get("retries", 2)),
            city=city_settings,
        )
        app_cfg.validate()
        return app_cfg

    @classmethod
    def from_file(cls, path: str | Path) -> AppConfig:
        """Load configuration from a YAML file."""
        p = Path(path)
        if not p.is_file():
            raise ConfigError(f"Configuration file not found: {p}")

        try:
            with open(p, encoding="utf-8") as f:
                content = yaml.safe_load(f)
        except yaml.YAMLError as err:
            raise ConfigError(f"YAML parsing error in {p}: {err}") from err

        if content is None:
            content = {}

        return cls.from_dict(content)
