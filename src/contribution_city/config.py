"""Configuration schema and validation for Contribution City."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from contribution_city.renderer.svg import RenderConfig
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

    def validate(self) -> None:
        """Validate city dimensions and scaling factors."""
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
    token: str | None = None
    city: CitySettings = field(default_factory=CitySettings)

    def validate(self) -> None:
        """Validate entire application configuration."""
        valid_themes = list(THEMES.keys())
        if self.theme.lower() not in valid_themes:
            raise ConfigError(
                f"Invalid theme '{self.theme}'. Choose from: {', '.join(valid_themes)}"
            )

        valid_layouts = ("calendar", "compact", "isometric")
        if self.layout.lower() not in valid_layouts:
            raise ConfigError(
                f"Invalid layout '{self.layout}'. Choose from: {', '.join(valid_layouts)}"
            )

        self.city.validate()

    def to_render_config(self) -> RenderConfig:
        """Convert to renderer configuration dataclass."""
        # 'isometric' is alias for 'calendar'
        effective_layout = "calendar" if self.layout == "isometric" else self.layout
        return RenderConfig(
            width=self.city.width,
            height=self.city.height,
            theme=self.theme,
            layout=effective_layout,
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
        )

        app_cfg = cls(
            username=data.get("username"),
            input_file=data.get("input") or data.get("input_file"),
            output_file=data.get("output") or data.get("output_file", "dist/city.svg"),
            theme=str(data.get("theme", "navy-cyan")),
            layout=str(data.get("layout", "calendar")),
            token=data.get("token"),
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
