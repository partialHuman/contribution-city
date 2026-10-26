"""Compact palette definitions for the v1.2 themes.

Each entry is plain data. ``themes.py`` turns every entry into a :class:`Theme`, so adding a theme
means adding one dictionary here (and, optionally, a gallery entry follows automatically because the
gallery is generated from the theme registry).

Level tuples are ``(roof, left_face, right_face, window_lit, window_dim, antenna_glow, stroke)``
for contribution levels 1 to 4 (low to high).
"""

from __future__ import annotations

from typing import Any

PALETTE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "neon-harbor",
        "description": "Deep navy harbor at night with cyan and electric-blue towers",
        "bg": ("#030A1C", "#071A3A"),
        "platform": ("#0A2342", "#061830", "#041022", "#14407A"),
        "ground": ("#0B2A4F", "#103A6B"),
        "text": ("#EAF8FF", "#7FB3D9", "#19E6FF"),
        "star": "#5BE0FF",
        "levels": (
            ("#1E6BD6", "#154FA3", "#0F3978", "#7FE9FF", "#1B4F96", "#19E6FF", "#0A2A5E"),
            ("#2E8BFF", "#1C66C9", "#134C9C", "#9AF0FF", "#2159A8", "#19E6FF", "#0C3270"),
            ("#19D3FF", "#1688E0", "#0F6AB8", "#C8F8FF", "#2A74C0", "#7FF5FF", "#0E4E92"),
            ("#7DF9FF", "#169ED8", "#1078B8", "#FFFFFF", "#3C9BE0", "#FFFFFF", "#1068A8"),
        ),
    },
    {
        "name": "cyberpunk",
        "description": "Near-black purple skyline with magenta, violet and electric cyan lights",
        "bg": ("#07020F", "#12051F"),
        "platform": ("#1A0B2E", "#10061D", "#0A0414", "#3B1668"),
        "ground": ("#190A2C", "#2A1048"),
        "text": ("#F6E8FF", "#B28AD6", "#FF2BD6"),
        "star": "#00E5FF",
        "levels": (
            ("#6D28D9", "#4C1D95", "#34146B", "#00E5FF", "#4C2A85", "#FF2BD6", "#1F0B40"),
            ("#A21CAF", "#7E1587", "#590F63", "#00E5FF", "#6A2A80", "#FF2BD6", "#3A0A47"),
            ("#FF2BD6", "#B3169E", "#8A0F7A", "#7DF9FF", "#8A2F8F", "#00E5FF", "#4F0A55"),
            ("#00E5FF", "#8B5CF6", "#6D3FD9", "#FFE8FF", "#7A4FD0", "#FFFFFF", "#3B1B8A"),
        ),
    },
    {
        "name": "emerald-matrix",
        "description": "Dark forest-green digital rain with emerald towers and lime peaks",
        "bg": ("#020B07", "#04160E"),
        "platform": ("#07261A", "#041A11", "#03120B", "#0F5A3A"),
        "ground": ("#06241A", "#0C3A28"),
        "text": ("#DDFBE9", "#7FBF9B", "#39FF88"),
        "star": "#7CFFB2",
        "levels": (
            ("#047857", "#065F46", "#064E3B", "#6EE7B7", "#0B6B50", "#34D399", "#022C22"),
            ("#10B981", "#059669", "#047857", "#A7F3D0", "#0E7A5A", "#34D399", "#064E3B"),
            ("#34D399", "#0E9F6E", "#047857", "#D1FAE5", "#17936D", "#A3E635", "#065F46"),
            ("#A3E635", "#16A34A", "#15803D", "#F7FEE7", "#3FB86A", "#ECFCCB", "#14532D"),
        ),
    },
    {
        "name": "copper-forge",
        "description": "Charcoal and graphite foundry with copper, bronze and amber highlights",
        "bg": ("#0B0B0D", "#161618"),
        "platform": ("#242427", "#18181A", "#101012", "#3A3A40"),
        "ground": ("#1E1E21", "#2E2E33"),
        "text": ("#F5EBE0", "#B3A08C", "#FFB347"),
        "star": "#D9A066",
        "levels": (
            ("#8C5A3C", "#6B4430", "#4A2F21", "#FFC474", "#5A3C2B", "#FFB347", "#2A1A12"),
            ("#B87333", "#8F5A29", "#66401E", "#FFC474", "#6A4A2C", "#FFB347", "#3A2410"),
            ("#D98E4A", "#B06E36", "#85511F", "#FFD79A", "#7A5530", "#FFD166", "#4A2E14"),
            ("#FFB347", "#D9822B", "#B1651A", "#FFF1D0", "#946A3A", "#FFFFFF", "#5E3A12"),
        ),
    },
    {
        "name": "arctic-glass",
        "description": "Cool blue night with steel, ice-cyan and pale white glass towers",
        "bg": ("#0B1626", "#13263D"),
        "platform": ("#1B3550", "#12263B", "#0C1B2C", "#3C6385"),
        "ground": ("#17304A", "#25496B"),
        "text": ("#F2FAFF", "#9DBBD3", "#8EE3FF"),
        "star": "#DDEFFF",
        "levels": (
            ("#5B8DB8", "#3F6C94", "#2E5373", "#DDF3FF", "#3A6488", "#8EE3FF", "#1B3A55"),
            ("#7FB3DA", "#5A8DB5", "#436F92", "#EAF8FF", "#4B7BA3", "#8EE3FF", "#2A5272"),
            ("#A9D6F0", "#6CA3C9", "#4F86AD", "#FFFFFF", "#6BA0C6", "#C9F1FF", "#3A6A8C"),
            ("#F4FBFF", "#C7DFEE", "#9FC3DA", "#1F4E79", "#7FA6C2", "#FFFFFF", "#5C8FB0"),
        ),
    },
    {
        "name": "sunset-grid",
        "description": "Midnight-purple retro sunset: violet to pink to coral to orange",
        "bg": ("#0B0420", "#2A0F4A"),
        "platform": ("#2B1250", "#1B0B38", "#12072A", "#7A2D8F"),
        "ground": ("#25104A", "#3D1A6E"),
        "text": ("#FFE9F3", "#C79BC9", "#FF7A59"),
        "star": "#FFB36B",
        "levels": (
            ("#7C3AED", "#5B2BB8", "#411F88", "#FFB36B", "#5A3A9A", "#FF7AC8", "#241048"),
            ("#C026D3", "#9A1FA8", "#72177E", "#FFC48A", "#7F2C95", "#FF7AC8", "#3E0D4A"),
            ("#FF5C8A", "#D9406F", "#A82F55", "#FFD7A8", "#A3416E", "#FFB36B", "#5A1230"),
            ("#FF9A3C", "#E8662F", "#B94A22", "#FFF0C8", "#B5683C", "#FFFFFF", "#6A2A10"),
        ),
    },
)
