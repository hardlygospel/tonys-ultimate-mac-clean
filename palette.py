"""
Colour palette, Theme dataclass, 38 themes, and colour management.
All 256-colour indices use the xterm-256color standard.
"""
from __future__ import annotations

import curses
from dataclasses import dataclass, fields
from typing import Any

DEFAULT_BG: int = -1  # terminal default background (transparency)


@dataclass(frozen=True)
class ColourSlot:
    """A foreground/background pair for 256-colour curses."""
    fg: int
    bg: int = DEFAULT_BG


@dataclass(frozen=True)
class Theme:
    """14 semantic colour slots for the entire UI."""
    name: str
    header: ColourSlot
    title: ColourSlot
    dim: ColourSlot
    border: ColourSlot
    bar_cpu: ColourSlot
    bar_mem: ColourSlot
    bar_disk: ColourSlot
    bar_net: ColourSlot
    bar_alt: ColourSlot
    row_normal: ColourSlot
    row_selected: ColourSlot
    row_highlight: ColourSlot
    status: ColourSlot
    graph: ColourSlot

    def colour_slots(self) -> list[tuple[str, ColourSlot]]:
        """Yield (slot_name, ColourSlot) pairs for colour init."""
        return [
            (f.name, getattr(self, f.name))
            for f in fields(self)
            if isinstance(getattr(self, f.name), ColourSlot)
        ]


# Compact theme constructor — keeps 38 definitions readable
_B = DEFAULT_BG

def _t(name: str, header, title, dim, border,
       bar_cpu, bar_mem, bar_disk, bar_net, bar_alt,
       row_normal, row_selected, row_highlight, status, graph) -> Theme:
    return Theme(name,
        ColourSlot(*header), ColourSlot(*title), ColourSlot(*dim), ColourSlot(*border),
        ColourSlot(*bar_cpu), ColourSlot(*bar_mem), ColourSlot(*bar_disk),
        ColourSlot(*bar_net), ColourSlot(*bar_alt),
        ColourSlot(*row_normal), ColourSlot(*row_selected), ColourSlot(*row_highlight),
        ColourSlot(*status), ColourSlot(*graph))


# ── 38 Themes ────────────────────────────────────────────────
# fmt: off
THEMES: list[Theme] = [
    # ── Dark / Vivid ──
    _t("Synthwave",      (201,_B),(135,_B),(93,_B),(99,_B),(201,_B),(51,_B),(226,_B),(171,_B),(85,_B),(255,_B),(232,201),(201,_B),(93,_B),(201,_B)),
    _t("Matrix",         (82,_B),(46,_B),(28,_B),(34,_B),(82,_B),(46,_B),(226,_B),(51,_B),(118,_B),(82,_B),(232,82),(118,_B),(28,_B),(82,_B)),
    _t("Ocean",          (51,_B),(117,_B),(67,_B),(33,_B),(51,_B),(117,_B),(46,_B),(123,_B),(80,_B),(255,_B),(232,51),(209,_B),(67,_B),(51,_B)),
    _t("Dracula",        (183,_B),(228,_B),(135,_B),(141,_B),(212,_B),(117,_B),(228,_B),(183,_B),(85,_B),(255,_B),(232,228),(196,_B),(135,_B),(212,_B)),
    _t("Blood Moon",     (196,_B),(214,_B),(124,_B),(160,_B),(196,_B),(214,_B),(202,_B),(209,_B),(220,_B),(255,_B),(232,196),(220,_B),(124,_B),(196,_B)),
    _t("Neon City",      (199,_B),(226,_B),(57,_B),(93,_B),(199,_B),(51,_B),(226,_B),(123,_B),(82,_B),(255,_B),(232,199),(226,_B),(57,_B),(199,_B)),
    _t("Hacker",         (82,_B),(118,_B),(22,_B),(28,_B),(82,_B),(118,_B),(226,_B),(46,_B),(34,_B),(82,_B),(22,82),(255,_B),(22,_B),(82,_B)),
    _t("Deep Space",     (27,_B),(105,_B),(18,_B),(57,_B),(33,_B),(105,_B),(220,_B),(51,_B),(171,_B),(255,_B),(18,33),(196,_B),(18,_B),(33,_B)),
    _t("Midnight",       (69,_B),(105,_B),(60,_B),(57,_B),(69,_B),(105,_B),(228,_B),(123,_B),(183,_B),(252,_B),(17,105),(209,_B),(60,_B),(69,_B)),
    _t("Ember",          (208,_B),(220,_B),(130,_B),(166,_B),(208,_B),(220,_B),(196,_B),(214,_B),(118,_B),(255,_B),(232,208),(226,_B),(130,_B),(208,_B)),
    _t("Cobalt",         (33,_B),(117,_B),(24,_B),(27,_B),(33,_B),(117,_B),(220,_B),(51,_B),(123,_B),(255,_B),(17,33),(209,_B),(24,_B),(33,_B)),
    _t("Forest",         (70,_B),(118,_B),(22,_B),(64,_B),(70,_B),(118,_B),(220,_B),(86,_B),(157,_B),(255,_B),(22,70),(208,_B),(22,_B),(70,_B)),
    _t("Retro Terminal", (220,_B),(228,_B),(136,_B),(142,_B),(220,_B),(214,_B),(226,_B),(154,_B),(190,_B),(220,_B),(232,220),(255,_B),(136,_B),(220,_B)),
    _t("Twilight",       (141,_B),(183,_B),(96,_B),(105,_B),(141,_B),(183,_B),(228,_B),(123,_B),(212,_B),(255,_B),(54,141),(209,_B),(96,_B),(141,_B)),
    _t("Amber",          (214,_B),(220,_B),(130,_B),(136,_B),(214,_B),(220,_B),(46,_B),(208,_B),(226,_B),(255,_B),(232,214),(196,_B),(130,_B),(214,_B)),
    # ── Pastel / Soft ──
    _t("Cotton Candy",   (218,_B),(183,_B),(182,_B),(175,_B),(218,_B),(183,_B),(228,_B),(153,_B),(157,_B),(255,_B),(225,218),(209,_B),(182,_B),(218,_B)),
    _t("Mint Breeze",    (121,_B),(157,_B),(108,_B),(114,_B),(121,_B),(157,_B),(228,_B),(117,_B),(183,_B),(255,_B),(193,121),(209,_B),(108,_B),(121,_B)),
    _t("Lavender Mist",  (183,_B),(189,_B),(146,_B),(141,_B),(183,_B),(189,_B),(228,_B),(153,_B),(218,_B),(255,_B),(225,183),(205,_B),(146,_B),(183,_B)),
    _t("Peach Fuzz",     (222,_B),(228,_B),(180,_B),(179,_B),(222,_B),(228,_B),(121,_B),(153,_B),(218,_B),(255,_B),(230,214),(209,_B),(180,_B),(222,_B)),
    _t("Sakura",         (218,_B),(212,_B),(175,_B),(204,_B),(218,_B),(212,_B),(228,_B),(183,_B),(157,_B),(255,_B),(225,218),(196,_B),(175,_B),(218,_B)),
    _t("Baby Blue",      (153,_B),(117,_B),(110,_B),(109,_B),(153,_B),(117,_B),(228,_B),(51,_B),(183,_B),(255,_B),(195,153),(209,_B),(110,_B),(153,_B)),
    _t("Blush",          (218,_B),(183,_B),(182,_B),(168,_B),(218,_B),(183,_B),(228,_B),(183,_B),(157,_B),(255,_B),(225,218),(196,_B),(182,_B),(218,_B)),
    _t("Butter",         (228,_B),(230,_B),(187,_B),(179,_B),(228,_B),(230,_B),(121,_B),(153,_B),(183,_B),(255,_B),(230,228),(196,_B),(187,_B),(228,_B)),
    _t("Seafoam",        (157,_B),(121,_B),(108,_B),(114,_B),(157,_B),(121,_B),(228,_B),(51,_B),(218,_B),(255,_B),(193,157),(209,_B),(108,_B),(157,_B)),
    _t("Wisteria",       (183,_B),(141,_B),(96,_B),(141,_B),(183,_B),(141,_B),(228,_B),(153,_B),(218,_B),(255,_B),(225,183),(205,_B),(96,_B),(183,_B)),
    _t("Lemon Drop",     (228,_B),(230,_B),(186,_B),(185,_B),(228,_B),(230,_B),(121,_B),(117,_B),(218,_B),(255,_B),(230,228),(214,_B),(186,_B),(228,_B)),
    _t("Coral",          (209,_B),(216,_B),(174,_B),(167,_B),(209,_B),(216,_B),(228,_B),(183,_B),(121,_B),(255,_B),(224,209),(196,_B),(174,_B),(209,_B)),
    _t("Lilac Dream",    (183,_B),(189,_B),(140,_B),(135,_B),(183,_B),(189,_B),(228,_B),(117,_B),(157,_B),(255,_B),(225,183),(209,_B),(140,_B),(183,_B)),
    _t("Morning Mist",   (152,_B),(189,_B),(110,_B),(109,_B),(152,_B),(189,_B),(228,_B),(117,_B),(183,_B),(255,_B),(195,152),(209,_B),(110,_B),(152,_B)),
    # ── High contrast / special ──
    _t("Arctic",         (51,_B),(255,_B),(250,_B),(153,_B),(51,_B),(255,_B),(226,_B),(123,_B),(183,_B),(255,_B),(232,51),(196,_B),(245,_B),(51,_B)),
    _t("Monochrome",     (255,_B),(250,_B),(240,_B),(245,_B),(255,_B),(250,_B),(245,_B),(240,_B),(235,_B),(255,_B),(232,255),(255,_B),(240,_B),(255,_B)),
    _t("Neon Pink",      (199,_B),(218,_B),(162,_B),(168,_B),(199,_B),(218,_B),(226,_B),(183,_B),(82,_B),(255,_B),(232,199),(226,_B),(162,_B),(199,_B)),
    _t("Sunset",         (208,_B),(220,_B),(130,_B),(166,_B),(196,_B),(208,_B),(220,_B),(209,_B),(118,_B),(255,_B),(232,208),(226,_B),(130,_B),(196,_B)),
    _t("Neon Aqua",      (51,_B),(123,_B),(30,_B),(37,_B),(51,_B),(123,_B),(220,_B),(82,_B),(199,_B),(255,_B),(232,51),(196,_B),(30,_B),(51,_B)),
    _t("Pastel Rainbow", (218,_B),(183,_B),(153,_B),(141,_B),(209,_B),(183,_B),(228,_B),(153,_B),(157,_B),(255,_B),(225,218),(209,_B),(141,_B),(218,_B)),
    _t("Dusk",           (141,_B),(105,_B),(60,_B),(99,_B),(141,_B),(105,_B),(220,_B),(123,_B),(209,_B),(255,_B),(54,105),(196,_B),(60,_B),(141,_B)),
    _t("Tangerine",      (208,_B),(220,_B),(130,_B),(172,_B),(208,_B),(220,_B),(82,_B),(51,_B),(196,_B),(255,_B),(232,208),(226,_B),(130,_B),(208,_B)),
    _t("Rose Gold",      (218,_B),(222,_B),(174,_B),(175,_B),(218,_B),(222,_B),(121,_B),(153,_B),(157,_B),(255,_B),(225,218),(209,_B),(174,_B),(218,_B)),
]
# fmt: on

del _B  # remove shorthand from module namespace

THEME_NAMES: list[str] = [t.name for t in THEMES]

# ── Colour attribute cache ───────────────────────────────────
_colour_attrs: dict[str, int] = {}
_BOLD_SLOTS = {"header", "title", "row_selected", "bar_cpu", "graph"}


def init_colours(theme: Theme) -> None:
    """Register 256-colour pairs for the chosen theme.
    Safe fallback if terminal only supports 8 colours."""
    curses.start_color()
    try:
        curses.use_default_colors()
    except curses.error:
        pass

    _colour_attrs.clear()
    for pair_num, (slot_name, slot) in enumerate(theme.colour_slots(), start=1):
        actual_fg = slot.fg if slot.fg < curses.COLORS else (slot.fg % 8)
        actual_bg = slot.bg if (slot.bg == -1 or slot.bg < curses.COLORS) else (slot.bg % 8)
        try:
            curses.init_pair(pair_num, actual_fg, actual_bg)
        except curses.error:
            try:
                curses.init_pair(pair_num, slot.fg % 8, -1)
            except curses.error:
                pass
        bold = curses.A_BOLD if slot_name in _BOLD_SLOTS else 0
        _colour_attrs[slot_name] = curses.color_pair(pair_num) | bold


def ca(slot: str) -> int:
    """Get curses attribute for a named colour slot."""
    return _colour_attrs.get(slot, curses.A_NORMAL)
