"""Tests for YAML configuration system and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from contribution_city.config import AppConfig, CitySettings, ConfigError, _coerce_dim


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


class TestNewOptions:
    def test_isometric_layout_gives_helpful_error(self) -> None:
        from contribution_city.config import AppConfig, ConfigError

        with pytest.raises(ConfigError, match="'calendar'"):
            AppConfig.from_dict({"layout": "isometric"})

    def test_new_fields_are_parsed(self) -> None:
        from contribution_city.config import AppConfig

        cfg = AppConfig.from_dict(
            {
                "theme": "profile",
                "appearance": "auto",
                "years": [2024, 2025],
                "retries": 4,
                "city": {"height_mode": "linear", "transparent": True, "show_tooltips": False},
            }
        )
        rc = cfg.to_render_config()
        assert rc.appearance == "auto" and rc.height_mode == "linear"
        assert rc.transparent is True and rc.show_tooltips is False
        assert cfg.years == [2024, 2025] and cfg.retries == 4

    @pytest.mark.parametrize(
        "bad",
        [
            {"appearance": "sepia"},
            {"years": [1999]},
            {"from": "yesterday"},
            {"years": [2024], "from": "2024-01-01"},
            {"retries": 99},
            {"city": {"height_mode": "cubic"}},
        ],
    )
    def test_invalid_values_rejected(self, bad: dict) -> None:
        from contribution_city.config import AppConfig, ConfigError

        with pytest.raises(ConfigError):
            AppConfig.from_dict(bad)


class TestTileDimensionValidation:
    """Regression tests for tile_width and tile_height validation (v1.3.0 bug fixes)."""

    # ---------------------------------------------------------------- tile_width

    @pytest.mark.parametrize(
        "tw",
        [
            float("nan"),
            float("inf"),
            float("-inf"),
        ],
    )
    def test_tile_width_non_finite_raises(self, tw: float) -> None:
        """NaN and infinities must be rejected with a clear ConfigError (B2 fix)."""
        with pytest.raises(ConfigError, match="tile_width"):
            AppConfig.from_dict({"city": {"tile_width": tw}})

    @pytest.mark.parametrize("tw", [0.0, -1.0, 3.9])
    def test_tile_width_too_small_raises(self, tw: float) -> None:
        with pytest.raises(ConfigError, match="tile_width"):
            AppConfig.from_dict({"city": {"tile_width": tw}})

    @pytest.mark.parametrize("tw", [64.1, 999.0])
    def test_tile_width_too_large_raises(self, tw: float) -> None:
        with pytest.raises(ConfigError, match="tile_width"):
            AppConfig.from_dict({"city": {"tile_width": tw}})

    @pytest.mark.parametrize("tw", [4.0, 9.0, 18.0, 32.0, 64.0])
    def test_tile_width_valid_range_accepted(self, tw: float) -> None:
        cfg = AppConfig.from_dict({"city": {"tile_width": tw}})
        assert cfg.city.tile_width == tw

    # ---------------------------------------------------------------- tile_height

    @pytest.mark.parametrize(
        "th",
        [
            float("nan"),
            float("inf"),
            float("-inf"),
        ],
    )
    def test_tile_height_non_finite_raises(self, th: float) -> None:
        """NaN and infinities must be rejected (B1 fix)."""
        with pytest.raises(ConfigError, match="tile_height"):
            AppConfig.from_dict({"city": {"tile_height": th}})

    @pytest.mark.parametrize("th", [0.0, -1.0, 3.9])
    def test_tile_height_too_small_raises(self, th: float) -> None:
        """Zero and sub-minimum tile_height must be rejected (B1 fix)."""
        with pytest.raises(ConfigError, match="tile_height"):
            AppConfig.from_dict({"city": {"tile_height": th}})

    @pytest.mark.parametrize("th", [64.1, 999.0])
    def test_tile_height_too_large_raises(self, th: float) -> None:
        """Excessively large tile_height must be rejected (B1 fix)."""
        with pytest.raises(ConfigError, match="tile_height"):
            AppConfig.from_dict({"city": {"tile_height": th}})

    @pytest.mark.parametrize("th", [4.0, 9.0, 10.0, 18.0, 64.0])
    def test_tile_height_valid_range_accepted(self, th: float) -> None:
        """Values within [4.0, 64.0] must continue to work (compatibility)."""
        cfg = AppConfig.from_dict({"city": {"tile_height": th}})
        assert cfg.city.tile_height == th

    def test_tile_height_default_unaffected(self) -> None:
        """Default tile_height 9.0 must continue to pass validation."""
        cfg = AppConfig.from_dict({})
        assert cfg.city.tile_height == 9.0

    def test_legacy_tile_height_config_still_accepted(self) -> None:
        """tile_height=10.0 (a typical v1.2 override) must still work."""
        cfg = AppConfig.from_dict({"city": {"tile_height": 10.0}})
        assert cfg.city.tile_height == 10.0

    # ---------------------------------------------------------------- NaN error messages

    def test_tile_width_nan_error_mentions_field(self) -> None:
        with pytest.raises(ConfigError, match="tile_width"):
            AppConfig.from_dict({"city": {"tile_width": float("nan")}})

    def test_tile_height_nan_error_mentions_field(self) -> None:
        with pytest.raises(ConfigError, match="tile_height"):
            AppConfig.from_dict({"city": {"tile_height": float("nan")}})


class TestDimensionCoercion:
    """Regression tests for width/height parsing in AppConfig.from_dict (v1.3.0 B3 fix)."""

    # ---------------------------------------------------------------- null / None

    def test_null_width_raises_config_error(self) -> None:
        """YAML 'width:' (null) must raise ConfigError, not TypeError."""
        with pytest.raises(ConfigError, match="width"):
            AppConfig.from_dict({"city": {"width": None}})

    def test_null_height_raises_config_error(self) -> None:
        """YAML 'height:' (null) must raise ConfigError, not TypeError."""
        with pytest.raises(ConfigError, match="height"):
            AppConfig.from_dict({"city": {"height": None}})

    # ---------------------------------------------------------------- booleans

    def test_bool_width_raises_config_error(self) -> None:
        """Boolean True must be rejected specifically by _coerce_dim."""
        with pytest.raises(ConfigError, match=r"city\.width must be an integer, got True"):
            AppConfig.from_dict({"city": {"width": True}})
        with pytest.raises(ConfigError, match=r"city\.width must be an integer, got True"):
            _coerce_dim({"width": True}, "width", 1200)

    def test_bool_false_width_raises_config_error(self) -> None:
        """Boolean False must be rejected specifically by _coerce_dim."""
        with pytest.raises(ConfigError, match=r"city\.width must be an integer, got False"):
            AppConfig.from_dict({"city": {"width": False}})
        with pytest.raises(ConfigError, match=r"city\.width must be an integer, got False"):
            _coerce_dim({"width": False}, "width", 1200)

    def test_bool_height_raises_config_error(self) -> None:
        """Boolean height dimensions must be rejected specifically with boolean value in error."""
        with pytest.raises(ConfigError, match=r"city\.height must be an integer, got True"):
            AppConfig.from_dict({"city": {"height": True}})
        with pytest.raises(ConfigError, match=r"city\.height must be an integer, got False"):
            AppConfig.from_dict({"city": {"height": False}})
        with pytest.raises(ConfigError, match=r"city\.height must be an integer, got True"):
            _coerce_dim({"height": True}, "height", 680)
        with pytest.raises(ConfigError, match=r"city\.height must be an integer, got False"):
            _coerce_dim({"height": False}, "height", 680)

    # ---------------------------------------------------------------- fractional floats

    def test_fractional_width_raises_config_error(self) -> None:
        """Non-integer floats must not be silently truncated."""
        with pytest.raises(ConfigError, match="width"):
            AppConfig.from_dict({"city": {"width": 1200.9}})

    def test_fractional_height_raises_config_error(self) -> None:
        with pytest.raises(ConfigError, match="height"):
            AppConfig.from_dict({"city": {"height": 680.5}})

    def test_integer_valued_float_width_accepted(self) -> None:
        """1200.0 is unambiguously an integer value and must be accepted."""
        cfg = AppConfig.from_dict({"city": {"width": 1200.0}})
        assert cfg.city.width == 1200

    def test_integer_valued_float_height_accepted(self) -> None:
        cfg = AppConfig.from_dict({"city": {"height": 680.0}})
        assert cfg.city.height == 680

    # ---------------------------------------------------------------- invalid strings

    def test_string_width_raises_config_error(self) -> None:
        """Non-numeric strings must raise ConfigError."""
        with pytest.raises(ConfigError, match="width"):
            AppConfig.from_dict({"city": {"width": "wide"}})

    def test_string_height_raises_config_error(self) -> None:
        with pytest.raises(ConfigError, match="height"):
            AppConfig.from_dict({"city": {"height": "tall"}})

    # ---------------------------------------------------------------- valid paths

    def test_valid_integer_width_accepted(self) -> None:
        cfg = AppConfig.from_dict({"city": {"width": 800}})
        assert cfg.city.width == 800

    def test_valid_integer_height_accepted(self) -> None:
        cfg = AppConfig.from_dict({"city": {"height": 400}})
        assert cfg.city.height == 400

    def test_omitted_width_uses_default(self) -> None:
        """When width is omitted entirely, the default 1200 must apply."""
        cfg = AppConfig.from_dict({})
        assert cfg.city.width == 1200

    def test_omitted_height_uses_default(self) -> None:
        cfg = AppConfig.from_dict({})
        assert cfg.city.height == 680
