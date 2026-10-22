"""Color themes for Contribution City SVG visualizations."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LevelPalette:
    """Colors for a specific contribution tier."""

    roof: str
    left_face: str
    right_face: str
    window_lit: str
    window_dim: str
    antenna_glow: str
    stroke: str


@dataclass(frozen=True)
class Theme:
    """Complete visual styling theme for city generation."""

    name: str
    description: str
    bg_top: str
    bg_bottom: str
    platform_top: str
    platform_left: str
    platform_right: str
    platform_grid: str
    ground_tile_fill: str
    ground_tile_stroke: str
    text_primary: str
    text_secondary: str
    text_accent: str
    star_color: str
    levels: dict[int, LevelPalette] = field(default_factory=dict)

    def get_level_palette(self, level: int) -> LevelPalette:
        """Retrieve palette for a given level (clamped 1-4)."""
        clamped = max(1, min(4, level))
        return self.levels[clamped]


# 1. Navy Cyan (Signature Theme)
THEME_NAVY_CYAN = Theme(
    name="navy-cyan",
    description="Signature deep navy with electric cyan and cobalt lighting",
    bg_top="#050813",
    bg_bottom="#0A1128",
    platform_top="#0D1B2A",
    platform_left="#08101A",
    platform_right="#050B12",
    platform_grid="#1E3A5F",
    ground_tile_fill="#0E1E33",
    ground_tile_stroke="#162E4D",
    text_primary="#E0FBFC",
    text_secondary="#7EA8BE",
    text_accent="#00F0FF",
    star_color="#4CC9F0",
    levels={
        1: LevelPalette(
            roof="#0096C7",
            left_face="#0077B6",
            right_face="#023E8A",
            window_lit="#90E0EF",
            window_dim="#0077B6",
            antenna_glow="#00B4D8",
            stroke="#03045E",
        ),
        2: LevelPalette(
            roof="#00B4D8",
            left_face="#0096C7",
            right_face="#0077B6",
            window_lit="#CAF0F8",
            window_dim="#48CAE4",
            antenna_glow="#90E0EF",
            stroke="#023E8A",
        ),
        3: LevelPalette(
            roof="#00F0FF",
            left_face="#00B4D8",
            right_face="#0096C7",
            window_lit="#FFFFFF",
            window_dim="#90E0EF",
            antenna_glow="#00F0FF",
            stroke="#0077B6",
        ),
        4: LevelPalette(
            roof="#70EEFF",
            left_face="#00F0FF",
            right_face="#00B4D8",
            window_lit="#FFFFFF",
            window_dim="#CAF0F8",
            antenna_glow="#FFFFFF",
            stroke="#0096C7",
        ),
    },
)

# 2. Matrix Green (Cyberpunk Terminal)
THEME_MATRIX_GREEN = Theme(
    name="matrix-green",
    description="Monochrome phosphor green matrix cyberpunk theme",
    bg_top="#040D06",
    bg_bottom="#081A0D",
    platform_top="#0F2E1B",
    platform_left="#0A1C11",
    platform_right="#06120B",
    platform_grid="#1B4D2E",
    ground_tile_fill="#0C2415",
    ground_tile_stroke="#163821",
    text_primary="#D2FBD4",
    text_secondary="#57A773",
    text_accent="#00FF66",
    star_color="#39D353",
    levels={
        1: LevelPalette(
            roof="#0E4429",
            left_face="#0B3721",
            right_face="#072416",
            window_lit="#39D353",
            window_dim="#1F6F43",
            antenna_glow="#26A641",
            stroke="#04150C",
        ),
        2: LevelPalette(
            roof="#006D32",
            left_face="#0E4429",
            right_face="#0A331E",
            window_lit="#56F076",
            window_dim="#26A641",
            antenna_glow="#39D353",
            stroke="#072616",
        ),
        3: LevelPalette(
            roof="#26A641",
            left_face="#006D32",
            right_face="#005226",
            window_lit="#A8FFBF",
            window_dim="#39D353",
            antenna_glow="#56F076",
            stroke="#00401D",
        ),
        4: LevelPalette(
            roof="#39D353",
            left_face="#26A641",
            right_face="#006D32",
            window_lit="#FFFFFF",
            window_dim="#56F076",
            antenna_glow="#FFFFFF",
            stroke="#006D32",
        ),
    },
)

# 3. Sunset Neon (Synthwave / Vaporwave)
THEME_SUNSET_NEON = Theme(
    name="sunset-neon",
    description="80s synthwave neon magenta, purple, and sunset orange",
    bg_top="#0F051D",
    bg_bottom="#23093B",
    platform_top="#321350",
    platform_left="#1E0A31",
    platform_right="#140621",
    platform_grid="#63258A",
    ground_tile_fill="#260F3D",
    ground_tile_stroke="#401B63",
    text_primary="#FFE2FD",
    text_secondary="#C385D9",
    text_accent="#FF3399",
    star_color="#FF77AA",
    levels={
        1: LevelPalette(
            roof="#7B2CBF",
            left_face="#5A189A",
            right_face="#3C096C",
            window_lit="#E0AAFF",
            window_dim="#9D4EDD",
            antenna_glow="#C77DFF",
            stroke="#240046",
        ),
        2: LevelPalette(
            roof="#B5179E",
            left_face="#7209B7",
            right_face="#560BAD",
            window_lit="#FF99E6",
            window_dim="#D633B0",
            antenna_glow="#F72585",
            stroke="#3F076B",
        ),
        3: LevelPalette(
            roof="#F72585",
            left_face="#B5179E",
            right_face="#7209B7",
            window_lit="#FFE3F1",
            window_dim="#FF66B2",
            antenna_glow="#FF4DA6",
            stroke="#560BAD",
        ),
        4: LevelPalette(
            roof="#FF5D8F",
            left_face="#F72585",
            right_face="#B5179E",
            window_lit="#FFFFFF",
            window_dim="#FFAFCC",
            antenna_glow="#FFFFFF",
            stroke="#7209B7",
        ),
    },
)

# 4. Monochrome Slate (Minimalist Developer)
THEME_MONOCHROME_SLATE = Theme(
    name="monochrome-slate",
    description="Minimalist obsidian, slate gray, and ice white",
    bg_top="#090B0E",
    bg_bottom="#14181F",
    platform_top="#1F242C",
    platform_left="#13171C",
    platform_right="#0B0D10",
    platform_grid="#363E4B",
    ground_tile_fill="#191D24",
    ground_tile_stroke="#272E38",
    text_primary="#F0F6FC",
    text_secondary="#8B949E",
    text_accent="#E6EDF3",
    star_color="#C9D1D9",
    levels={
        1: LevelPalette(
            roof="#484F58",
            left_face="#30363D",
            right_face="#21262D",
            window_lit="#8B949E",
            window_dim="#484F58",
            antenna_glow="#6E7681",
            stroke="#161B22",
        ),
        2: LevelPalette(
            roof="#6E7681",
            left_face="#484F58",
            right_face="#30363D",
            window_lit="#C9D1D9",
            window_dim="#8B949E",
            antenna_glow="#B1BAC4",
            stroke="#21262D",
        ),
        3: LevelPalette(
            roof="#8B949E",
            left_face="#6E7681",
            right_face="#484F58",
            window_lit="#F0F6FC",
            window_dim="#C9D1D9",
            antenna_glow="#E6EDF3",
            stroke="#30363D",
        ),
        4: LevelPalette(
            roof="#C9D1D9",
            left_face="#8B949E",
            right_face="#6E7681",
            window_lit="#FFFFFF",
            window_dim="#E6EDF3",
            antenna_glow="#FFFFFF",
            stroke="#484F58",
        ),
    },
)

# 5. Solar Amber (Warm Industrial Golden Glow)
THEME_SOLAR_AMBER = Theme(
    name="solar-amber",
    description="Warm amber, industrial bronze, and solar orange",
    bg_top="#120B04",
    bg_bottom="#241407",
    platform_top="#38210D",
    platform_left="#231407",
    platform_right="#160C03",
    platform_grid="#593717",
    ground_tile_fill="#291809",
    ground_tile_stroke="#42270F",
    text_primary="#FFF2E2",
    text_secondary="#D4A373",
    text_accent="#FFAA00",
    star_color="#FFD166",
    levels={
        1: LevelPalette(
            roof="#9A5B1E",
            left_face="#7C4714",
            right_face="#532F0C",
            window_lit="#FFD166",
            window_dim="#B07026",
            antenna_glow="#E0922D",
            stroke="#361F07",
        ),
        2: LevelPalette(
            roof="#CA7927",
            left_face="#A45E1A",
            right_face="#743F0F",
            window_lit="#FFE39F",
            window_dim="#E0922D",
            antenna_glow="#FFB703",
            stroke="#4A290A",
        ),
        3: LevelPalette(
            roof="#F48C06",
            left_face="#D06E00",
            right_face="#9C4F00",
            window_lit="#FFF3C4",
            window_dim="#FFB703",
            antenna_glow="#FFBA08",
            stroke="#633500",
        ),
        4: LevelPalette(
            roof="#FFBA08",
            left_face="#FAA307",
            right_face="#D06E00",
            window_lit="#FFFFFF",
            window_dim="#FFF3C4",
            antenna_glow="#FFFFFF",
            stroke="#8F4800",
        ),
    },
)

THEMES: dict[str, Theme] = {
    "navy-cyan": THEME_NAVY_CYAN,
    "matrix-green": THEME_MATRIX_GREEN,
    "sunset-neon": THEME_SUNSET_NEON,
    "monochrome-slate": THEME_MONOCHROME_SLATE,
    "solar-amber": THEME_SOLAR_AMBER,
}


def get_theme(name: str) -> Theme:
    """Retrieve theme by name, defaulting to navy-cyan if not found."""
    normalized = name.strip().lower()
    if normalized not in THEMES:
        valid_keys = ", ".join(THEMES.keys())
        raise ValueError(f"Unknown theme '{name}'. Available themes: {valid_keys}")
    return THEMES[normalized]
