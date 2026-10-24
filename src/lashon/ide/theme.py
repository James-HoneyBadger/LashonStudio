"""Palettes for Lashon Studio.

The look is borrowed from a CRT-era workstation: a near-black tube, one bright
phosphor for accents, dim phosphor for secondary text, and a monospace face for
anything that is code. Three palettes ship — green (default), amber, and a
neutral dark theme for long sessions on a modern display.

Select with ``--theme`` or the ``LASHON_THEME`` environment variable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """Every colour the workbench paints with."""

    name: str
    title: str
    bg: str
    panel: str
    panel_alt: str
    border: str
    fg: str
    muted: str
    accent: str
    green: str
    red: str
    yellow: str

    def outline(self) -> tuple[str, ...]:
        return (self.bg, self.panel, self.panel_alt, self.border, self.fg)


GREEN = Palette(
    name="green",
    title="Green phosphor",
    bg="#05080a",
    panel="#0a1210",
    panel_alt="#101c17",
    border="#1d3b2f",
    fg="#b6ffd0",
    muted="#5f9c7c",
    accent="#33ff66",
    green="#33ff66",
    red="#ff6b6b",
    yellow="#ffd166",
)

AMBER = Palette(
    name="amber",
    title="Amber phosphor",
    bg="#0a0704",
    panel="#140f08",
    panel_alt="#1d160c",
    border="#3d2f15",
    fg="#ffe0b3",
    muted="#a67c42",
    accent="#ffb000",
    green="#ffcf5c",
    red="#ff6b4a",
    yellow="#ffd166",
)

DARK = Palette(
    name="dark",
    title="Neutral dark",
    bg="#0d1117",
    panel="#161b22",
    panel_alt="#21262d",
    border="#30363d",
    fg="#c9d1d9",
    muted="#8b949e",
    accent="#58a6ff",
    green="#3fb950",
    red="#f85149",
    yellow="#d29922",
)

PALETTES: dict[str, Palette] = {
    "green": GREEN,
    "amber": AMBER,
    "dark": DARK,
}

DEFAULT = "green"

UI_FONT = ("DejaVu Sans", 10)
UI_FONT_BOLD = ("DejaVu Sans", 10, "bold")
TITLE_FONT = ("DejaVu Sans", 17, "bold")
MONO_FONT = ("Courier New", 10)
MONO_FONT_BOLD = ("Courier New", 10, "bold")


def get_palette(name: str | None = None) -> Palette:
    """Return a palette by name, defaulting to :data:`DEFAULT`."""
    return PALETTES.get((name or DEFAULT).lower(), GREEN)


def names() -> list[str]:
    """Palette names, in menu order."""
    return list(PALETTES)
