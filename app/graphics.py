"""Pillow + SVG graphic generation.

The poster and the square social graphic are drawn from the same
:class:`DesignSystem` as the deck, using only vector primitives, patterns and
typography — no remote images, so output is deterministic and always renders.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .content import headline_from, short, title_case
from .design import DesignSystem, contrast_ratio, ensure_contrast, mix, shade

# --------------------------------------------------------------------------
# font discovery — bundled system fonts with graceful fallbacks
# --------------------------------------------------------------------------
FONT_DIRS = [
    Path("C:/Windows/Fonts"),
    Path("C:/Windows/Fonts"),
]

FONT_CANDIDATES: dict[str, list[str]] = {
    "display": [
        "GARA.TTF", "georgiab.ttf", "GEORGIA.TTF", "Georgia.ttf",
        "times.ttf", "TIMES.TTF", "seguisb.ttf", "segoeuib.ttf",
        "ARLRDBD.TTF", "arialbd.ttf", "ARIALBD.TTF", "calibrib.ttf",
    ],
    "body": [
        "segoeui.ttf", "SEGOEUI.TTF", "calibri.ttf", "CALIBRI.TTF",
        "arial.ttf", "ARIAL.TTF", "tahoma.ttf", "verdana.ttf",
    ],
    "mono": ["consola.ttf", "CONSOLA.TTF", "cour.ttf", "cour.ttf"],
}

_RESERVED = {name.lower(): name for name in (
    "gara.ttf", "georgiab.ttf", "georgia.ttf", "times.ttf", "seguisb.ttf",
    "segoeuib.ttf", "arlrdbd.ttf", "arialbd.ttf", "calibrib.ttf", "segoeui.ttf",
    "calibri.ttf", "arial.ttf", "tahoma.ttf", "verdana.ttf", "consola.ttf",
    "cour.ttf", "arial.ttf", "seguibl.ttf", "trebuc.ttf", "cambria.ttc",
)}


def available_fonts() -> list[str]:
    found: list[str] = []
    for directory in FONT_DIRS:
        if not directory.exists():
            continue
        try:
            for path in directory.glob("*.*tf"):
                lower = path.name.lower()
                if lower in _RESERVED and path.name not in found:
                    found.append(path.name)
        except OSError:
            continue
    return found


def font_path(role: str) -> Optional[Path]:
    for directory in FONT_DIRS:
        for name in FONT_CANDIDATES.get(role, []):
            candidate = directory / name
            if candidate.exists():
                return candidate
    return None


_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def load_font(role: str, size: int) -> ImageFont.FreeTypeFont:
    key = (role, size)
    cached = _font_cache.get(key)
    if cached is not None:
        return cached
    path = font_path(role)
    try:
        font = ImageFont.truetype(str(path), size) if path else ImageFont.load_default(size)
    except OSError:
        font = ImageFont.load_default(size)
    _font_cache[key] = font
    return font


def display_font(size: int) -> ImageFont.FreeTypeFont:
    return load_font("display", size)


def body_font(size: int) -> ImageFont.FreeTypeFont:
    return load_font("body", size)


# --------------------------------------------------------------------------
# text helpers
# --------------------------------------------------------------------------
def text_width(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    if not text:
        return 0.0
    try:
        box = draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0]
    except (AttributeError, OSError):
        return font.getlength(text) if hasattr(font, "getlength") else len(text) * font.size * 0.5


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: float) -> list[str]:
    """Greedy word wrap that never exceeds ``max_width``."""
    words = [w for w in (text or "").split() if w]
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        probe = f"{current} {word}"
        if text_width(draw, probe, font) <= max_width:
            current = probe
        else:
            lines.append(current)
            current = word
    lines.append(current)

    # Hard-break any single token that is still too wide.
    result: list[str] = []
    for line in lines:
        while text_width(draw, line, font) > max_width and len(line) > 1:
            cut = len(line)
            while cut > 1 and text_width(draw, line[:cut], font) > max_width:
                cut -= 1
            result.append(line[:cut].rstrip("-"))
            line = line[cut:]
        result.append(line)
    return result


def draw_paragraph(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font,
    fill: str,
    max_width: float,
    line_gap: float = 0.45,
    max_lines: Optional[int] = None,
    align: str = "left",
) -> int:
    """Draw wrapped text, return the y coordinate just below the last line."""
    lines = wrap_text(draw, text, font, max_width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines:
            while lines and text_width(draw, lines[-1] + "…", font) > max_width:
                lines[-1] = lines[-1][:-1]
            lines[-1] = lines[-1].rstrip() + "…"
    line_height = int(font.size * (1.0 + line_gap))
    x, y = xy
    for line in lines:
        width = text_width(draw, line, font)
        offset = 0 if align == "left" else (max_width - width if align == "right" else (max_width - width) / 2)
        draw.text((int(x + offset), y), line, font=font, fill=fill)
        y += line_height
    return y


def tracked_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font,
                 fill: str, tracking: float = 2.0) -> int:
    """Letter-spaced label drawing (Pillow has no tracking)."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += int(text_width(draw, ch, font) + tracking)
    return x


# --------------------------------------------------------------------------
# motifs shared with the deck
# --------------------------------------------------------------------------
def motif_arcs(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], design: DesignSystem,
               base: str, weight: float = 1.0) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return
    # Anchor high and to the right so arcs sweep through the canvas instead of
    # bunching into a band along the bottom edge.
    cx = x0 + int(w * 0.68)
    cy = y0 + int(h * 0.30)
    span = int(min(w, h) * 1.5)
    width = max(2, int(min(w, h) * 0.006))
    for i, ratio in enumerate((1.0, 0.80, 0.60, 0.40, 0.22)):
        r = int(span * ratio / 2)
        color = mix(base, design.accent, max(0.04, 0.42 * weight - i * 0.07))
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=width)


def motif_grid(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], design: DesignSystem,
               base: str, weight: float = 1.0, spacing: int = 90) -> None:
    x0, y0, x1, y1 = box
    color = mix(base, design.ink if not design.dark_canvas else design.paper, 0.14 * weight)
    width = 2
    for x in range(x0, x1, spacing):
        draw.line((x, y0, x, y1), fill=color, width=width)
    for y in range(y0, y1, spacing):
        draw.line((x0, y, x1, y), fill=color, width=width)


def motif_diagonals(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], design: DesignSystem,
                    base: str, weight: float = 1.0, spacing: int = 130) -> None:
    x0, y0, x1, y1 = box
    color = mix(base, design.ink if not design.dark_canvas else design.paper, 0.16 * weight)
    width = max(6, (x1 - x0) // 90)
    for offset in range(-(y1 - y0), x1 - x0, spacing):
        draw.line((x0 + offset, y0, x0 + offset + (y1 - y0), y1), fill=color, width=width)


def motif_ledger(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], design: DesignSystem,
                 base: str, weight: float = 1.0, spacing: int = 64) -> None:
    x0, y0, x1, y1 = box
    color = mix(base, design.ink if not design.dark_canvas else design.paper, 0.12 * weight)
    for y in range(y0, y1, spacing):
        draw.line((x0, y, x1, y), fill=color, width=2)


def motif_spotlight(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], design: DesignSystem,
                    base: str, weight: float = 1.0) -> None:
    x0, y0, x1, y1 = box
    for i in range(7):
        t = i / 6
        radius = int((x1 - x0) * (0.18 + t * 0.5))
        color = mix(base, design.accent, 0.22 * weight * (1 - t) ** 1.6)
        draw.ellipse((x0 + radius * 0.4, y0 + radius * 0.4, x0 + radius * 2.4, y0 + radius * 2.4),
                     outline=color, width=max(2, int((x1 - x0) * 0.006)))


def motif_confetti(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], design: DesignSystem,
                   base: str, weight: float = 1.0) -> None:
    x0, y0, x1, y1 = box
    palette = design.series(4)
    span_x, span_y = x1 - x0, y1 - y0
    # Deterministic pseudo-random placement: no RNG so output is reproducible.
    for i in range(26):
        t = (i * 37 % 100) / 100.0
        u = (i * 61 % 100) / 100.0
        cx = x0 + int(span_x * (0.06 + 0.88 * t))
        cy = y0 + int(span_y * (0.06 + 0.88 * u))
        r = int(span_x * (0.012 + 0.026 * ((i * 17 % 10) / 10.0)))
        color = mix(base, palette[i % len(palette)], 0.30 * weight)
        if i % 3 == 0:
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
        elif i % 3 == 1:
            draw.rectangle((cx - r, cy - r, cx + r, cy + r), fill=color)
        else:
            draw.line((cx - r, cy, cx + r, cy), fill=color, width=max(3, r // 2))


MOTIFS = {
    "arches": motif_arcs,
    "grid": motif_grid,
    "diagonal": motif_diagonals,
    "ledger": motif_ledger,
    "spotlight": motif_spotlight,
    "confetti": motif_confetti,
}


def draw_motif(img: Image.Image, box, design: DesignSystem, base: str,
               weight: float = 1.0) -> None:
    """Draw the preset motif strictly inside ``box`` (nothing bleeds past it).

    ``weight`` scales the motif's visual weight; background sections pass a
    lower value so foreground copy always wins.
    """
    x0, y0, x1, y1 = (int(v) for v in box)
    if x1 <= x0 or y1 <= y0:
        return
    layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    local = ImageDraw.Draw(layer)
    fn = MOTIFS.get(design.pattern, motif_arcs)
    # Motifs are drawn relative to the local box, then the layer is composited
    # so geometry can never spill across a section boundary.
    fn(local, (0, 0, x1 - x0, y1 - y0), design, base, weight)  # type: ignore[operator]
    # Fade the motif out near the bottom edge so it never ends on a hard seam
    # against the next section. The multiplier scales existing alpha only;
    # transparent pixels stay transparent instead of turning into dark bands.
    w, h = layer.size
    ramp = max(2, int(h * 0.24))
    multiplier = Image.new("L", (1, ramp))
    mdraw = ImageDraw.Draw(multiplier)
    for row in range(ramp):
        mdraw.point((0, row), fill=int(255 * (1 - row / max(1, ramp - 1)) ** 1.4))
    multiplier = multiplier.resize((w, ramp))
    full = Image.new("L", (w, max(1, h - ramp)), 255)
    fade = Image.new("L", (w, h), 255)
    fade.paste(multiplier, (0, h - ramp))
    del full

    original = layer.getchannel("A")
    layer.putalpha(ImageChops.multiply(original, fade))
    img.paste(layer, (x0, y0), layer)


# --------------------------------------------------------------------------
# shared furniture
# --------------------------------------------------------------------------
def soft_light(img: Image.Image, design: DesignSystem) -> None:
    """Gentle radial bloom in the brand accent, full-bleed with no seam."""
    w, h = img.size
    scale = 8
    glow = Image.new("L", (max(2, w // scale), max(2, h // scale)), 0)
    gdraw = ImageDraw.Draw(glow)
    r = max(2, min(glow.size) // 3)
    gdraw.ellipse((glow.width // 2 - r, glow.height // 2 - r,
                   glow.width // 2 + r, glow.height // 2 + r), fill=52)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(4, r // 2)))
    glow = glow.resize((w, h), Image.Resampling.BILINEAR)
    tint = Image.new("RGB", (w, h), design.accent)
    img.paste(tint, (0, 0), glow)


def wordmark(draw: ImageDraw.ImageDraw, xy: tuple[int, int], design: DesignSystem,
             on_dark: bool, scale: float = 1.0) -> tuple[int, int]:
    """Logo lockup: monogram ring + wordmark + tagline. Returns (w, h)."""
    x, y = xy
    ring = int(56 * scale)
    stroke = max(2, int(3 * scale))
    draw.ellipse((x, y, x + ring, y + ring), outline=design.accent, width=stroke)
    mono = display_font(int(20 * scale))
    initials = design.brand_name[:2].upper()
    tw = text_width(draw, initials, mono)
    draw.text((x + (ring - tw) / 2, y + ring * 0.32), initials, font=mono, fill=design.accent)

    name_font = display_font(int(22 * scale))
    tag_font = body_font(int(12 * scale))
    on_dark_color = ensure_contrast("#FFFFFF", design.paper if not on_dark else "#000000", 6.0)
    name_color = design.ink if not on_dark else ensure_contrast("#FFFFFF", "#000000", 6.0)
    del on_dark_color
    tx = x + ring + int(16 * scale)
    tracked_text(draw, (tx, y + int(4 * scale)), design.brand_name.upper(), name_font,
                 name_color, tracking=1.6 * scale)
    if design.tagline:
        tracked_text(draw, (tx, y + int(32 * scale)),
                     design.tagline.upper()[:34], tag_font,
                     mix(name_color, design.accent if not on_dark else "#FFFFFF", 0.5),
                     tracking=2.0 * scale)
    return ring + int(16 * scale) + int(text_width(draw, design.brand_name.upper(), name_font)), max(ring, int(56 * scale))


def swatch_strip(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, design: DesignSystem,
                 height: int = 10) -> None:
    colors = [design.primary, design.secondary, design.accent, mix(design.primary, design.accent, 0.5)]
    seg = width // len(colors)
    for i, color in enumerate(colors):
        draw.rectangle((x + i * seg, y, x + (i + 1) * seg, y + height), fill=color)


def corner_ticks(draw: ImageDraw.ImageDraw, box, design: DesignSystem, length: int,
                 color: Optional[str] = None, width: int = 3) -> None:
    x0, y0, x1, y1 = box
    color = color or mix(design.paper if not design.dark_canvas else "#0A0A12", design.accent, 0.7)
    for cx, cy in ((x0, y0), (x1 - length, y0), (x0, y1 - width), (x1 - length, y1 - width)):
        draw.rectangle((cx, cy, cx + length, cy + width), fill=color)
    for cx, cy in ((x0, y0), (x0, y1 - length), (x1 - width, y0), (x1 - width, y1 - length)):
        draw.rectangle((cx, cy, cx + width, cy + length), fill=color)


def rule(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, design: DesignSystem,
         thickness: int = 6, color: Optional[str] = None) -> None:
    draw.rectangle((x, y, x + width, y + thickness), fill=color or design.accent)


# --------------------------------------------------------------------------
# poster
# --------------------------------------------------------------------------
def render_poster(design: DesignSystem, *, brief, out_path: Path,
                  width: int = 2480, height: int = 3508) -> dict:
    """A2 @300 dpi portrait poster. Every block is measured, never guessed."""
    margin = int(width * 0.085)
    inner_w = width - margin * 2
    paper = design.paper

    img = Image.new("RGB", (width, height), design.primary)
    draw = ImageDraw.Draw(img)

    # ------------------------------------------------------------------
    # dark section: background, motif and content, all measured up front
    # ------------------------------------------------------------------
    hero = headline_from(brief.topic, brief.project_name, 34)
    hero_font_size = int(height * 0.058)
    while True:
        hero_font = display_font(hero_font_size)
        hero_lines = wrap_text(draw, hero, hero_font, inner_w)
        if len(hero_lines) <= 3 or hero_font_size < int(height * 0.030):
            break
        hero_font_size -= 6
    hero_lines = hero_lines[:3]

    sub_font = body_font(int(height * 0.0158))
    sub_text = short(brief.tagline or brief.goal, 140).rstrip(".")
    sub_lines = wrap_text(draw, sub_text, sub_font, inner_w)[:3]

    quote_font = display_font(int(height * 0.0250))
    quote_text = f"“{title_case(short(brief.goal, 110).rstrip('.'))}”"
    quote_w = inner_w - int(width * 0.09)
    quote_lines = wrap_text(draw, quote_text, quote_font, quote_w)[:3]

    eyebrow_font = body_font(int(height * 0.0120))
    meta_font = body_font(int(height * 0.0105))

    head_h = int(height * 0.115)
    quote_block_h = int(quote_font.size * 1.36) * len(quote_lines)
    dark_h = (head_h
              + int(hero_font.size * 1.07) * len(hero_lines)
              + int(height * 0.016)
              + int(height * 0.012)
              + int(height * 0.030)
              + int(sub_font.size * 1.5) * len(sub_lines)
              + int(height * 0.026)
              + int(height * 0.034) + quote_block_h
              + int(height * 0.018) + int(meta_font.size * 1.8)
              + int(height * 0.028))

    band_h = int(dark_h)
    for i in range(band_h):
        t = i / band_h
        draw.line((0, i, width, i),
                  fill=mix(design.primary, mix(design.primary, design.accent, 0.30), t))
    draw_motif(img, (0, 0, width, band_h), design, design.primary, weight=0.75)
    soft_light(img, design)
    draw = ImageDraw.Draw(img)

    hero_color = ensure_contrast(paper, design.primary, 8.0)
    muted_on_dark = mix(design.primary, paper, 0.68)

    # top bar
    wordmark(draw, (margin, margin), design, on_dark=True, scale=1.5)
    kicker = f"{brief.presentation_type.value.replace('_', ' ').upper()} PACKAGE"
    tracked_text(draw, (margin, margin + int(104)), kicker, meta_font,
                 mix(design.primary, paper, 0.55), tracking=4.0)
    right_label = "CREATED WITH CREATEFLOW"
    rw = text_width(draw, right_label, meta_font)
    tracked_text(draw, (width - margin - rw - int(rw * 0.07), margin + int(104)), right_label,
                 meta_font, mix(design.primary, paper, 0.40), tracking=4.0)
    rule(draw, margin, margin + int(150), inner_w, design,
         thickness=max(3, int(height * 0.0020)), color=mix(design.primary, paper, 0.26))

    y = head_h
    tracked_text(draw, (margin, y), "NEW · " + design.brand_name.upper()[:30], eyebrow_font,
                 mix(design.primary, design.accent, 0.88), tracking=5.0)
    y += int(height * 0.030)

    line_h = int(hero_font.size * 1.07)
    for line in hero_lines:
        tracked_text(draw, (margin, y), line, hero_font, hero_color,
                     tracking=design.heading_tracking * 1.4)
        y += line_h
    y += int(height * 0.016)

    rule(draw, margin, y, int(width * 0.20), design, thickness=max(6, int(height * 0.0038)))
    y += int(height * 0.030)

    for line in sub_lines:
        draw.text((margin, y), line, font=sub_font, fill=muted_on_dark)
        y += int(sub_font.size * 1.5)
    y += int(height * 0.026)

    # pull quote panel, sized to its own text
    quote_h = int(height * 0.034) + quote_block_h + int(height * 0.018) + int(meta_font.size * 1.8)
    draw.rounded_rectangle((margin, y, width - margin, y + quote_h),
                           radius=int(height * 0.012), fill=design.accent)
    qx = margin + int(width * 0.045)
    quote_top = y + int(height * 0.034)
    draw_paragraph(draw, (qx, quote_top), quote_text, quote_font,
                   ensure_contrast(design.primary, design.accent, 5.0), quote_w,
                   line_gap=0.36, max_lines=len(quote_lines))
    tracked_text(draw, (qx, quote_top + quote_block_h + int(height * 0.008)),
                 f"THE BRIEF · {design.brand_name.upper()}", meta_font,
                 mix(design.accent, design.primary, 0.58), tracking=4.0)

    # ------------------------------------------------------------------
    # cream section: takes whatever height is left and fits its grid exactly
    # ------------------------------------------------------------------
    lower_y = min(height - int(height * 0.17), y + quote_h + int(height * 0.026))
    draw.rectangle((0, lower_y, width, height), fill=paper)
    draw.rectangle((0, lower_y, width, lower_y + max(6, int(height * 0.0032))), fill=design.accent)
    draw_motif(img, (0, lower_y, width, height), design, paper, weight=0.55)
    draw = ImageDraw.Draw(img)

    section_font = body_font(int(height * 0.0120))
    section_top = lower_y + int(height * 0.042)
    tracked_text(draw, (margin, section_top), "INSIDE THIS PACKAGE", section_font,
                 mix(paper, design.ink, 0.5), tracking=5.0)
    rule(draw, margin, section_top + int(height * 0.026), int(width * 0.09), design,
         thickness=max(5, int(height * 0.0028)))

    items = [
        ("01", f"{brief.presentation_length} editable slides",
         "Native text, shapes and charts in PowerPoint."),
        ("02", "Promotional poster", "This sheet, exported at 300 dpi."),
        ("03", "Social graphic", "Square artwork for feed publishing."),
        ("04", "One visual identity", f"{design.preset_label} — shared colours and type."),
    ]

    grid_top = section_top + int(height * 0.062)
    foot_y = height - int(height * 0.056)
    grid_h = max(int(height * 0.10), foot_y - int(height * 0.026) - grid_top)
    row_gap = int(height * 0.016)
    row_h = (grid_h - row_gap) // 2
    col_gap = int(width * 0.028)
    col_w = (inner_w - col_gap) // 2
    card_pad = int(width * 0.020)
    num_font = display_font(int(height * 0.028))
    head_font = display_font(int(height * 0.0158))
    body_copy = body_font(int(height * 0.0118))
    text_x_off = int(col_w * 0.155)
    text_w = col_w - card_pad * 2 - text_x_off

    for i, (num, head, body) in enumerate(items):
        r, c = divmod(i, 2)
        x = margin + (col_w + col_gap) * c
        cy = grid_top + (row_h + row_gap) * r
        draw.rounded_rectangle((x, cy, x + col_w, cy + row_h), radius=int(height * 0.008),
                               fill=mix(paper, design.secondary, 0.5),
                               outline=mix(paper, design.ink, 0.10), width=2)
        draw.text((x + card_pad, cy + card_pad + int(height * 0.003)), num, font=num_font,
                  fill=design.accent if i % 2 == 0 else design.primary)
        draw.text((x + card_pad + text_x_off, cy + card_pad), title_case(head),
                  font=head_font, fill=design.ink)
        draw_paragraph(draw, (x + card_pad + text_x_off, cy + card_pad + int(height * 0.024)),
                       body, body_copy, mix(paper, design.ink, 0.52), text_w,
                       line_gap=0.4, max_lines=2)

    swatch_strip(draw, margin, foot_y, int(inner_w * 0.40), design, height=int(height * 0.0038))
    foot_font = body_font(int(height * 0.0112))
    foot_text = f"{design.brand_name.upper()}  ·  {short(brief.audience, 42).upper()}"
    tracked_text(draw, (margin, foot_y + int(height * 0.015)), foot_text, foot_font,
                 mix(paper, design.ink, 0.55), tracking=3.0)
    url = "CREATEFLOW.STUDIO"
    uw = text_width(draw, url, foot_font)
    tracked_text(draw, (width - margin - uw - int(uw * 0.06), foot_y + int(height * 0.015)),
                 url, foot_font, design.accent, tracking=3.0)
    corner_ticks(draw, (margin, margin, width - margin, height - margin), design,
                 length=int(width * 0.018), color=mix(paper, design.ink, 0.18), width=3)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG", optimize=True)
    return {"width": width, "height": height, "content_type": "image/png"}

# --------------------------------------------------------------------------
# square social graphic
# --------------------------------------------------------------------------
def render_social(design: DesignSystem, *, brief, out_path: Path, size: int = 1440) -> dict:
    """Instagram-style 1:1 artwork."""
    img = Image.new("RGB", (size, size), design.paper)
    draw = ImageDraw.Draw(img)
    draw_motif(img, (0, 0, size, size), design, design.paper, weight=0.55)
    soft_light(img, design)
    draw = ImageDraw.Draw(img)

    margin = int(size * 0.085)
    pad = int(size * 0.055)
    inner_w = size - margin * 2 - pad * 2
    on_dark = ensure_contrast("#FFFFFF", design.primary, 8.0)

    # --- hero block: height is measured from its contents, never guessed ---
    headline = headline_from(brief.topic, brief.project_name, 26)
    hero_size = int(size * 0.092)
    while True:
        hero_font = display_font(hero_size)
        lines = wrap_text(draw, headline, hero_font, inner_w)
        if len(lines) <= 2 or hero_size < int(size * 0.048):
            break
        hero_size -= 3

    eyebrow_font = body_font(int(size * 0.021))
    tagline_font = body_font(int(size * 0.025))
    tagline = short(brief.tagline or brief.goal, 64).rstrip(".")
    tagline_lines = wrap_text(draw, tagline, tagline_font, inner_w)[:2]

    eyebrow_h = int(eyebrow_font.size * 1.6)
    hero_h = int(hero_font.size * 1.06) * len(lines)
    tag_h = int(tagline_font.size * 1.42) * len(tagline_lines)
    block_h = pad + eyebrow_h + hero_h + int(size * 0.018) + tag_h + pad

    draw.rounded_rectangle((margin, margin, size - margin, margin + block_h),
                           radius=int(size * 0.035), fill=design.primary)
    tracked_text(draw, (margin + pad, margin + pad), "INTRODUCING", eyebrow_font,
                 mix(design.primary, design.accent, 0.9), tracking=6.0)

    y = margin + pad + eyebrow_h
    for line in lines:
        tracked_text(draw, (margin + pad, y), line, hero_font, on_dark,
                     tracking=design.heading_tracking * 1.2)
        y += int(hero_font.size * 1.06)

    rule(draw, margin + pad, y + int(size * 0.006), int(inner_w * 0.18), design,
         thickness=max(4, int(size * 0.005)))
    # Base tone that actually reads on the block colour, softened toward the brand
    # only when that softening keeps contrast above 4.5:1.
    tag_color = ensure_contrast("#FFFFFF", design.primary, 4.5)
    for weight in (0.30, 0.20, 0.10):
        candidate = mix(design.primary, tag_color, weight)
        if contrast_ratio(candidate, design.primary) >= 4.5:
            tag_color = candidate
            break
    yy = y + int(size * 0.026)
    for line in tagline_lines:
        draw.text((margin + pad, yy), line, font=tagline_font, fill=tag_color)
        yy += int(tagline_font.size * 1.42)

    # --- bullet list, spaced to the space that is actually left ------------
    cta_h = int(size * 0.135)
    cta_y = size - margin - cta_h
    foot = body_font(int(size * 0.020))
    list_font = body_font(int(size * 0.026))

    points = [
        f"{brief.presentation_length}-slide editable deck",
        f"Poster + social graphic · {design.preset_label}",
        f"Built for {short(brief.audience, 32)}",
    ]

    foot_y = cta_y - int(size * 0.058)
    list_top = margin + block_h + int(size * 0.058)
    available = max(int(size * 0.2), foot_y - int(size * 0.035) - list_top)
    row = available / max(1, len(points))
    bullet_r = int(size * 0.010)

    for i, point in enumerate(points):
        by = int(list_top + row * i + row / 2)
        draw.ellipse((margin, by - bullet_r, margin + bullet_r * 2, by + bullet_r),
                     fill=design.accent)
        text = point
        while text_width(draw, text, list_font) > size - margin * 2 - int(size * 0.05):
            if list_font.size <= 14:
                break
            list_font = body_font(list_font.size - 1)
        if text_width(draw, text, list_font) > size - margin * 2 - int(size * 0.05):
            text = short(text, 60)
        draw.text((margin + int(size * 0.040), by - int(list_font.size * 0.62)), text,
                  font=list_font, fill=design.ink)

    # --- CTA bar: shrink, then wrap, then clip safely ----------------------
    draw.rounded_rectangle((margin, cta_y, size - margin, cta_y + cta_h),
                           radius=int(size * 0.03), fill=design.primary)
    cta_text = title_case(short(brief.goal, 96).rstrip("."))
    cta_pad = int(size * 0.06)
    cta_max_w = size - margin * 2 - cta_pad * 2
    cta_pad_v = int(size * 0.016)
    cta_font = display_font(int(size * 0.040))
    cta_lines = wrap_text(draw, cta_text, cta_font, cta_max_w)
    # Shrink until the wrapped block fits inside the bar, capped at 3 lines.
    while cta_font.size > 14 and (
        len(cta_lines) > 3
        or int(cta_font.size * 1.22) * len(cta_lines) > cta_h - cta_pad_v * 2
    ):
        cta_font = display_font(cta_font.size - 2)
        cta_lines = wrap_text(draw, cta_text, cta_font, cta_max_w)
    cta_lines = cta_lines[:3]
    cta_color = ensure_contrast("#FFFFFF", design.primary, 7.0)
    line_step = int(cta_font.size * 1.22)
    block_h_px = line_step * len(cta_lines) - int(cta_font.size * 0.22)
    start_y = int(cta_y + (cta_h - block_h_px) / 2)
    for line in cta_lines:
        w = text_width(draw, line, cta_font)
        tracked_text(draw, ((size - w) / 2, start_y), line, cta_font, cta_color, tracking=2.0)
        start_y += line_step

    tracked_text(draw, (margin, foot_y), design.brand_name.upper(), foot,
                 mix(design.paper, design.ink, 0.5), tracking=5.0)

    corner_ticks(draw, (int(size * 0.03), int(size * 0.03), size - int(size * 0.03), size - int(size * 0.03)),
                 design, length=int(size * 0.035), color=mix(design.paper, design.accent, 0.55),
                 width=3)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG", optimize=True)
    return {"width": size, "height": size, "content_type": "image/png"}


# --------------------------------------------------------------------------
# SVG companion (vector version of the social mark, for print/web)
# --------------------------------------------------------------------------
def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_svg(design: DesignSystem, *, brief, out_path: Path, size: int = 1080) -> dict:
    headline = _esc(headline_from(brief.topic, brief.project_name, 28))
    brand = _esc(design.brand_name.upper())
    tagline = _esc(short(brief.tagline or brief.goal, 72).rstrip("."))
    r = int(size * 0.46)
    cx = cy = size // 2

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <title>{brand} — CreateFlow</title>
  <desc>Vector brand mark generated from the project brief.</desc>
  <defs>
    <linearGradient id="cfGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{design.primary}"/>
      <stop offset="100%" stop-color="{mix(design.primary, design.accent, 0.6)}"/>
    </linearGradient>
  </defs>
  <rect width="{size}" height="{size}" fill="{design.paper}"/>
  <rect x="{int(size*0.04)}" y="{int(size*0.04)}" width="{int(size*0.92)}" height="{int(size*0.92)}"
        rx="{int(size*0.05)}" fill="url(#cfGrad)"/>
  <circle cx="{cx}" cy="{int(size*0.42)}" r="{r}" fill="none" stroke="{design.accent}" stroke-width="{max(2, size//200)}" opacity="0.75"/>
  <circle cx="{cx}" cy="{int(size*0.42)}" r="{int(r*0.62)}" fill="{design.accent}" opacity="0.22"/>
  <circle cx="{cx}" cy="{int(size*0.42)}" r="{int(r*0.26)}" fill="{design.accent}"/>
  <text x="{cx}" y="{int(size*0.46)}" text-anchor="middle" font-family="Georgia, 'Times New Roman', serif"
        font-size="{int(size*0.085)}" font-weight="700" fill="{design.accent}">{_esc(design.brand_name[:2].upper())}</text>
  <text x="{cx}" y="{int(size*0.78)}" text-anchor="middle" font-family="Georgia, 'Times New Roman', serif"
        font-size="{int(size*0.062)}" font-weight="700" fill="{design.paper}">{headline}</text>
  <text x="{cx}" y="{int(size*0.85)}" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif"
        font-size="{int(size*0.028)}" fill="{mix(design.primary, design.paper, 0.7)}">{tagline}</text>
  <text x="{cx}" y="{int(size*0.925)}" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif"
        font-size="{int(size*0.022)}" letter-spacing="{size*0.006:.1f}" fill="{design.accent}">{brand}</text>
</svg>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")
    return {"width": size, "height": size, "content_type": "image/svg+xml"}


def _unused() -> None:  # pragma: no cover
    del math, shade