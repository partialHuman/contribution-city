"""Configuration schema and validation for Contribution City."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from contribution_city.renderer.svg import (
    APPEARANCES,
    BACKGROUND_MODES,
    HEIGHT_MODES,
    LAYOUTS,
    RenderConfig,
)
from contribution_city.renderer.themes import THEMES


class ConfigError(Exception):
    """Raised when configuration file or options are invalid."""


@dataclass
class CitySettings:
    """City geometry and visual customization settings."""

    width: int = 1200
    height: int = 680
    tile_width: float = 18.0
    tile_height: float = 9.0
    building_scale: float = 1.0
    min_building_height: float = 6.0
    max_building_height: float = 125.0
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
        if self.building_scale <= 0.0 or self.building_scale > 5.0:
            raise ConfigError(
                f"city.building_scale must be between 0.1 and 5.0, got {self.building_scale}"
            )
        if self.tile_width < 4.0 or self.tile_width > 64.0:
            raise ConfigError(
                f"city.tile_width must be between 4.0 and 64.0, got {self.tile_width}"
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
            building_scale=self.city.building_scale,
            min_building_height=self.city.min_building_height,
            max_building_height=self.city.max_building_height,
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
            width=int(city_data.get("width", 1200)),
            height=int(city_data.get("height", 680)),
            tile_width=float(city_data.get("tile_width", 18.0)),
            tile_height=float(city_data.get("tile_height", 9.0)),
            building_scale=float(city_data.get("building_scale", 1.0)),
            min_building_height=float(city_data.get("min_building_height", 6.0)),
            max_building_height=float(city_data.get("max_building_height", 125.0)),
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
