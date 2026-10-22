"""Tests for YAML configuration system and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from contribution_city.config import AppConfig, CitySettings, ConfigError


class TestCitySettings:
    """Test suite for CitySettings."""

    def test_default_settings_valid(self) -> None:
        settings = CitySettings()
        settings.validate()
        assert settings.width == 1200
        assert settings.height == 680

    def test_invalid_width_raises(self) -> None:
        settings = CitySettings(width=150)
        with pytest.raises(ConfigError, match="city.width"):
            settings.validate()

    def test_invalid_height_raises(self) -> None:
        settings = CitySettings(height=100)
        with pytest.raises(ConfigError, match="city.height"):
            settings.validate()

    def test_invalid_scale_raises(self) -> None:
        settings = CitySettings(building_scale=0.0)
        with pytest.raises(ConfigError, match="city.building_scale"):
            settings.validate()


class TestAppConfig:
    """Test suite for AppConfig."""

    def test_from_dict_defaults(self) -> None:
        config = AppConfig.from_dict({})
        assert config.theme == "navy-cyan"
        assert config.layout == "calendar"
        assert config.output_file == "dist/city.svg"
        assert config.city.show_windows is True

    def test_from_dict_custom(self) -> None:
        data = {
            "username": "monalisa",
            "theme": "sunset-neon",
            "layout": "compact",
            "output": "custom/path.svg",
            "city": {
                "width": 1400,
                "height": 700,
                "building_scale": 1.5,
                "show_stars": False,
            },
        }
        config = AppConfig.from_dict(data)
        assert config.username == "monalisa"
        assert config.theme == "sunset-neon"
        assert config.layout == "compact"
        assert config.output_file == "custom/path.svg"
        assert config.city.width == 1400
        assert config.city.height == 700
        assert config.city.building_scale == 1.5
        assert config.city.show_stars is False

    def test_invalid_theme_raises(self) -> None:
        with pytest.raises(ConfigError, match="Invalid theme"):
            AppConfig.from_dict({"theme": "neon-glow-unknown"})

    def test_invalid_layout_raises(self) -> None:
        with pytest.raises(ConfigError, match="Invalid layout"):
            AppConfig.from_dict({"layout": "hexagonal"})

    def test_from_file_valid(self, tmp_path: Path) -> None:
        config_file = tmp_path / "test-config.yaml"
        config_file.write_text(
            """
username: tester
theme: matrix-green
layout: compact
output: dist/matrix.svg
city:
  width: 1000
  height: 500
  building_scale: 1.2
""",
            encoding="utf-8",
        )
        config = AppConfig.from_file(config_file)
        assert config.username == "tester"
        assert config.theme == "matrix-green"
        assert config.city.width == 1000

    def test_from_file_not_found(self) -> None:
        with pytest.raises(ConfigError, match="Configuration file not found"):
            AppConfig.from_file("non-existent-config.yaml")

    def test_to_render_config(self) -> None:
        config = AppConfig(theme="solar-amber", layout="compact")
        render_cfg = config.to_render_config()
        assert render_cfg.theme == "solar-amber"
        assert render_cfg.layout == "compact"
        assert render_cfg.width == 1200
