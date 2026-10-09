r"""Real slide previews.

PowerPoint has no browser renderer and this machine has no PowerPoint or
LibreOffice, so the slide *thumbnail* is drawn here with Pillow from the exact
same objects the deck is built from: the same :class:`Slide` outline and the
same :class:`DesignSystem`. What the user sees in the results studio is
therefore the real generated content and real brand identity, not a mock-up.

The .pptx itself remains the editable deliverable; this is a faithful preview of
it at 16:9.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

from .content import Slide
from .design import DesignSystem, ensure_contrast, mix
from .graphics import body_font, display_font, draw_motif, text_width, tracked_text, wrap_text

W, H = 1600, 900
MARGIN = 88
CONTENT_TOP = 236
CONTENT_BOTTOM = 806

_cache: dict[str, bytes] = {}
_CACHE_LIMIT = 160


def _on(design: DesignSystem, background: str) -> str:
    return ensure_contrast(design.paper if not design.dark_canvas else "#FFFFFF",
                           background, 7.0)


def _rect(draw, box, fill=None, outline=None, width=1, radius=0):
    x0, y0, x1, y1 = box
    if radius:
        draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    else:
        draw.rectangle(box, fill=fill, outline=outline, width=width)


def _text(draw, xy, text, font, fill, max_w, line_gap=0.5, max_lines=3, align="left"):
    lines = wrap_text(draw, text, font, max_w)[:max_lines]
    step = int(font.size * (1 + line_gap))
    x, y = xy
    for line in lines:
        offset = 0
        if align == "center":
            offset = (max_w - text_width(draw, line, font)) / 2
        draw.text((int(x + offset), int(y)), line, font=font, fill=fill)
        y += step
    return y


def _frame(draw, design: DesignSystem, kicker: str, title: str, index: int, total: int,
           bg: str):
    ink = _on(design, bg)
    muted = mix(bg, ink, 0.62)
    if kicker:
        tracked_text(draw, (MARGIN, 84), kicker.upper(),
                     body_font(15), mix(bg, design.accent, 0.9), tracking=2.4)
    tracked_text(draw, (MARGIN, 124), title, display_font(46), ink,
                 tracking=design.heading_tracking * 0.6)
    _rect(draw, (MARGIN, 196, MARGIN + 120, 201), fill=design.accent)

    base = mix(bg, ink, 0.16)
    _rect(draw, (MARGIN, H - 62, W - MARGIN, H - 61), fill=base)
    tracked_text(draw, (MARGIN, H - 46), f"{design.brand_name.upper()} · "
                 f"{design.preset_label.upper()}", body_font(12), muted, tracking=1.6)
    tracked_text(draw, (W - MARGIN - 90, H - 46), f"{index:02d} / {total:02d}",
                 body_font(12), muted, tracking=1.6)


def render_slide(slide: Slide, design: DesignSystem, index: int, total: int) -> Image.Image:
    bg = design.paper
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)
    draw_motif(img, (0, 0, W, H), design, bg, weight=0.35)
    draw = ImageDraw.Draw(img)

    ink = _on(design, bg)
    muted = mix(bg, ink, 0.62)
    surface = mix(bg, design.secondary, 0.35)
    border = mix(bg, ink, 0.12)

    if slide.layout == "hero":
        hero_bg = design.primary if not design.dark_canvas else shade_hex(design.paper)
        img = Image.new("RGB", (W, H), hero_bg)
        draw = ImageDraw.Draw(img)
        draw_motif(img, (0, 0, W, H), design, hero_bg, weight=0.7)
        draw = ImageDraw.Draw(img)
        hero_ink = ensure_contrast(design.paper, hero_bg, 8.0)
        cx, cy = int(W * 0.79), int(H * 0.52)
        for i, ratio in enumerate((1.0, 0.78, 0.56, 0.34)):
            r = int(430 * ratio)
            draw.ellipse((cx - r, cy - r, cx + r, cy + r),
                         outline=mix(hero_bg, design.accent, 0.7 - i * 0.1), width=2)
        tracked_text(draw, (MARGIN, 300), slide.kicker.upper(), body_font(16),
                     mix(hero_bg, design.accent, 0.9), tracking=2.6)
        _text(draw, (MARGIN, 350), slide.title, display_font(64), hero_ink,
              900, line_gap=0.22, max_lines=3)
        _rect(draw, (MARGIN, 600, MARGIN + 140, 605), fill=design.accent)
        _text(draw, (MARGIN, 640), slide.body, body_font(22),
              mix(hero_bg, hero_ink, 0.35), 760, line_gap=0.5, max_lines=2)
        tracked_text(draw, (MARGIN, H - 62), design.brand_name.upper(), body_font(13),
                     hero_ink, tracking=2.0)
        return img

    _frame(draw, design, slide.kicker, slide.title, index, total, bg)
    inner_w = W - MARGIN * 2

    if slide.layout in ("two_column", "summary"):
        col_w = (inner_w - 40) // 2
        body_text = slide.body or slide.title
        bullets = slide.bullets[:4]
        block_h = 230 + len(bullets) * 108
        # Centre the block so slides never look top-heavy with a dead lower half.
        offset = max(0, (CONTENT_BOTTOM - CONTENT_TOP - block_h) // 2)
        top = CONTENT_TOP + offset
        _text(draw, (MARGIN, top), body_text, display_font(30), ink,
              col_w, line_gap=0.36, max_lines=5)
        y = top + 230
        for i, bullet in enumerate(bullets):
            _rect(draw, (MARGIN + col_w + 40, y + 6, MARGIN + col_w + 44, y + 34),
                  fill=design.accent, radius=14)
            draw.text((MARGIN + col_w + 46, y + 6), str(i + 1), font=body_font(14),
                      fill=ensure_contrast("#FFFFFF", design.accent, 4.0))
            tracked_text(draw, (MARGIN + col_w + 84, y + 4), bullet.head,
                         display_font(21), ink, tracking=0)
            _text(draw, (MARGIN + col_w + 84, y + 40), bullet.body, body_font(16),
                  muted, col_w - 84, line_gap=0.5, max_lines=3)
            y += 108
        return img

    if slide.layout == "numbered_process":
        n = len(slide.steps[:5]) or 1
        gap = 22
        col_w = (inner_w - gap * (n - 1)) // n
        _rect(draw, (MARGIN, CONTENT_TOP - 26, W - MARGIN, CONTENT_TOP - 25),
              fill=mix(bg, ink, 0.18))
        for i, (head, body) in enumerate(slide.steps[:5]):
            x = MARGIN + (col_w + gap) * i
            cx = x + col_w // 2
            draw.ellipse((cx - 9, CONTENT_TOP - 35, cx + 9, CONTENT_TOP - 17),
                         fill=design.accent)
            _rect(draw, (x, CONTENT_TOP, x + col_w, CONTENT_BOTTOM - 40), fill=surface,
                  outline=border, radius=12)
            _rect(draw, (x, CONTENT_TOP, x + col_w, CONTENT_TOP + 5),
                  fill=design.accent if i == 0 else design.primary)
            tracked_text(draw, (x + 22, CONTENT_TOP + 34), f"{i + 1:02d}",
                         display_font(34), mix(bg, design.accent, 0.8))
            tracked_text(draw, (x + 22, CONTENT_TOP + 92), head.upper(), body_font(17),
                         ink, tracking=0.8)
            _text(draw, (x + 22, CONTENT_TOP + 124), body, body_font(15), muted,
                  col_w - 44, line_gap=0.5, max_lines=6)
        return img

    if slide.layout == "timeline":
        items = slide.timeline[:5]
        rail_y = CONTENT_TOP + 66
        _rect(draw, (MARGIN, rail_y, W - MARGIN, rail_y + 3), fill=mix(bg, ink, 0.2))
        step = (W - MARGIN * 2 - 120) // max(1, len(items) - 1)
        for i, (label, body) in enumerate(items):
            cx = MARGIN + 60 + step * i
            draw.ellipse((cx - 13, rail_y - 12, cx + 13, rail_y + 14), fill=design.accent)
            card_w = 250
            card_x = max(MARGIN, min(cx - card_w // 2, W - MARGIN - card_w))
            above = i % 2 == 0
            card_y = rail_y - 44 - 150 if above else rail_y + 44
            _rect(draw, (card_x, card_y, card_x + card_w, card_y + 150),
                  fill=surface, outline=border, radius=12)
            tracked_text(draw, (card_x + 20, card_y + 20), label.upper(), body_font(13),
                         design.accent, tracking=1.4)
            _text(draw, (card_x + 20, card_y + 50), body, body_font(15), ink,
                  card_w - 40, line_gap=0.5, max_lines=5)
        return img

    if slide.layout == "metrics":
        top = CONTENT_TOP
        if slide.body:
            _text(draw, (MARGIN, top), slide.body, body_font(19), muted, 1000,
                  line_gap=0.5, max_lines=2)
            top += 66
        metrics = slide.metrics[:4]
        if metrics and not slide.series:
            # No chart to fill the lower half: centre the metric strip.
            top = CONTENT_TOP + max(0, (CONTENT_BOTTOM - CONTENT_TOP - 190) // 2)
        if metrics:
            gap = 24
            card_w = (inner_w - gap * 3) // 4
            for i, metric in enumerate(metrics):
                x = MARGIN + (card_w + gap) * i
                _rect(draw, (x, top, x + card_w, top + 190), fill=surface,
                      outline=border, radius=12)
                _rect(draw, (x, top, x + card_w, top + 4),
                      fill=design.accent if i % 2 == 0 else design.primary)
                draw.text((x + 24, top + 34), metric.value, font=display_font(46),
                          fill=ensure_contrast(design.accent, surface, 3.0))
                _text(draw, (x + 24, top + 100), metric.label, body_font(16), ink,
                      card_w - 48, line_gap=0.4, max_lines=2)
            top += 214
        if slide.series:
            _chart(draw, design, slide, bg, surface, border, top, CONTENT_BOTTOM - 30)
        return img

    if slide.layout == "comparison":
        before, after, impact = slide.compare
        col_w = (inner_w - 300) // 2
        y = CONTENT_TOP + 10
        _rect(draw, (MARGIN + 280, y, MARGIN + 280 + col_w, y + 46), fill=design.paper,
              outline=border, radius=8)
        _rect(draw, (MARGIN + 280 + col_w + 20, y,
                     MARGIN + 280 + col_w * 2 + 20, y + 46), fill=design.primary, radius=8)
        tracked_text(draw, (MARGIN + 300, y + 15), slide.compare_titles[0].upper(),
                     body_font(14), ink, tracking=1.4)
        tracked_text(draw, (MARGIN + 300 + col_w + 20, y + 15),
                     slide.compare_titles[1].upper(), body_font(14),
                     _on(design, design.primary), tracking=1.4)
        y += 62
        rows = max(len(before), len(after), len(impact), 1)
        row_h = (CONTENT_BOTTOM - 40 - y) // rows
        for i in range(rows):
            if i % 2 == 0:
                _rect(draw, (MARGIN, y, W - MARGIN, y + row_h), fill=surface)
            _text(draw, (MARGIN, y + 14), impact[i] if i < len(impact) else "",
                  body_font(15), ink, 250, line_gap=0.4, max_lines=3)
            left = before[i] if i < len(before) else ""
            right = after[i] if i < len(after) else ""
            cy = y + row_h // 2
            draw.ellipse((MARGIN + 296, cy - 7, MARGIN + 310, cy + 7),
                         outline=mix(bg, ink, 0.5), width=2)
            _text(draw, (MARGIN + 330, y + 12), left, body_font(15), muted,
                  col_w - 60, line_gap=0.45, max_lines=3)
            draw.ellipse((MARGIN + 316 + col_w, cy - 7, MARGIN + 330 + col_w, cy + 7),
                         fill=design.accent)
            _text(draw, (MARGIN + 350 + col_w, y + 12), right, body_font(15), ink,
                  col_w - 60, line_gap=0.45, max_lines=3)
            y += row_h
        return img

    if slide.layout == "framework":
        items = slide.quadrant[:4]
        gap = 24
        card_w = (inner_w - gap) // 2
        card_h = (CONTENT_BOTTOM - CONTENT_TOP - 40 - gap) // 2
        for i, (num, head, body) in enumerate(items):
            r, c = divmod(i, 2)
            x = MARGIN + (card_w + gap) * c
            y = CONTENT_TOP + (card_h + gap) * r
            _rect(draw, (x, y, x + card_w, y + card_h), fill=surface, outline=border,
                  radius=12)
            _rect(draw, (x, y, x + 6, y + card_h),
                  fill=design.accent if i % 2 == 0 else design.primary)
            draw.text((x + 34, y + 26), num, font=display_font(40),
                      fill=mix(bg, design.accent, 0.65))
            tracked_text(draw, (x + 130, y + 34), head.upper(), display_font(22), ink,
                         tracking=0.4)
            _text(draw, (x + 130, y + 74), body, body_font(16), muted,
                  card_w - 170, line_gap=0.5, max_lines=4)
        return img

    if slide.layout == "quote_led":
        panel_w = int(inner_w * 0.72)
        _rect(draw, (MARGIN, CONTENT_TOP + 10, MARGIN + panel_w, CONTENT_BOTTOM - 10),
              fill=design.primary, radius=16)
        hero_ink = _on(design, design.primary)
        _rect(draw, (MARGIN + 48, CONTENT_TOP + 56, MARGIN + 148, CONTENT_TOP + 61),
              fill=design.accent)
        _text(draw, (MARGIN + 48, CONTENT_TOP + 96), slide.body or slide.title,
              display_font(38), hero_ink, panel_w - 96, line_gap=0.4, max_lines=5)
        if slide.media_label:
            tracked_text(draw, (MARGIN + 48, CONTENT_BOTTOM - 70),
                         f"— {slide.media_label.upper()}", body_font(14),
                         mix(design.primary, hero_ink, 0.55), tracking=1.4)
        rx = MARGIN + panel_w + 40
        rw = W - MARGIN - rx
        for i, ratio in enumerate((0.95, 0.68, 0.42)):
            size = int(rw * ratio)
            cx, cy = rx + rw // 2, (CONTENT_TOP + CONTENT_BOTTOM) // 2
            draw.ellipse((cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2),
                         outline=mix(bg, design.accent, 0.65 - i * 0.14), width=2)
        return img

    if slide.layout == "image_led":
        media_w = int(inner_w * 0.44)
        media_x = W - MARGIN - media_w
        _text(draw, (MARGIN, CONTENT_TOP), slide.body or slide.title, body_font(20),
              ink, inner_w - media_w - 40, line_gap=0.55, max_lines=6)
        y = CONTENT_TOP + 190
        for i, bullet in enumerate(slide.bullets[:3]):
            _rect(draw, (MARGIN, y + 6, MARGIN + 4, y + 34), fill=design.accent)
            tracked_text(draw, (MARGIN + 22, y + 2), bullet.head, display_font(20), ink,
                         tracking=0)
            _text(draw, (MARGIN + 22, y + 34), bullet.body, body_font(15), muted,
                  inner_w - media_w - 70, line_gap=0.5, max_lines=3)
            y += 118
        top, bottom = CONTENT_TOP, CONTENT_BOTTOM - 20
        _rect(draw, (media_x, top, media_x + media_w, bottom), fill=design.primary,
              radius=16)
        ring = int(min(media_w, bottom - top) * 0.42)
        cx, cy = media_x + media_w // 2, (top + bottom) // 2
        draw.ellipse((cx - ring, cy - ring, cx + ring, cy + ring),
                     outline=mix(design.primary, design.accent, 0.8), width=3)
        inner = int(ring * 0.6)
        draw.ellipse((cx - inner, cy - inner, cx + inner, cy + inner),
                     fill=mix(design.primary, design.accent, 0.3))
        core = int(ring * 0.24)
        draw.ellipse((cx - core, cy - core, cx + core, cy + core), fill=design.accent)
        if slide.media_label:
            tracked_text(draw, (media_x, bottom - 44), slide.media_label.upper()[:28],
                         body_font(13), _on(design, design.primary), tracking=1.4)
        return img

    return img


def _chart(draw, design: DesignSystem, slide: Slide, bg: str, surface: str, border: str,
           top: int, bottom: int):
    series = slide.series[:3]
    if not series or not series[0].points:
        return
    ink = _on(design, bg)
    x0, x1 = MARGIN, W - MARGIN
    panel_h = max(80, bottom - top)
    _rect(draw, (x0, top, x1, top + panel_h), fill=surface, outline=border, radius=12)
    tracked_text(draw, (x0 + 24, top + 18), (slide.chart_title or "Illustrative model"),
                 body_font(15), ink, tracking=0.6)
    tracked_text(draw, (x0 + 24, top + 42), "ILLUSTRATIVE DATA — REPLACE WITH YOUR OWN",
                 body_font(11), mix(bg, ink, 0.5), tracking=1.6)

    plot_top = top + 70
    plot_bottom = top + panel_h - 44
    categories = [p[0] for p in series[0].points]
    values = [v for ser in series for _, v in ser.points]
    peak = max(values) or 1
    slot = (x1 - x0 - 48) // max(1, len(categories))
    group_w = slot * 0.66
    bar_w = max(6, group_w // len(series) - 6)
    palette = [design.accent, design.primary, mix(design.accent, design.primary, 0.5)]
    for c, _ in enumerate(categories):
        base = x0 + 24 + slot * c + (slot - group_w) / 2
        for s, ser in enumerate(series):
            value = ser.points[c][1] if c < len(ser.points) else 0
            height = int((plot_bottom - plot_top) * (value / peak))
            bx = base + (bar_w + 6) * s
            _rect(draw, (bx, plot_bottom - height, bx + bar_w, plot_bottom),
                  fill=palette[s % len(palette)], radius=4)
        tracked_text(draw, (base, plot_bottom + 14), categories[c].upper(), body_font(12),
                     mix(bg, ink, 0.55), tracking=1.0)
    for s, ser in enumerate(series):
        lx = x0 + 24 + s * 190
        _rect(draw, (lx, top + panel_h - 22, lx + 14, top + panel_h - 16),
              fill=palette[s % len(palette)], radius=3)
        draw.text((lx + 24, top + panel_h - 28), ser.name, font=body_font(12),
                  fill=mix(bg, ink, 0.6))


def shade_hex(color: str) -> str:
    return mix(color, "#000000", 0.02)


def slide_png(slide: Slide, design: DesignSystem, index: int, total: int) -> bytes:
    import io

    buffer = io.BytesIO()
    render_slide(slide, design, index, total).save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def cached_slide_png(brief, slide: Slide, index: int, total: int) -> bytes:
    """Render a slide, memoised on the brief so navigation is instant."""
    key_source = json.dumps(
        {
            "brief": brief.model_dump(mode="json", exclude={"logo_data_url"}),
            "index": index,
            "total": total,
        },
        sort_keys=True,
    )
    key = hashlib.sha256(key_source.encode("utf-8")).hexdigest()
    hit = _cache.get(key)
    if hit is not None:
        return hit
    from .design import build_design_system

    data = slide_png(slide, build_design_system(brief), index, total)
    if len(_cache) >= _CACHE_LIMIT:
        _cache.pop(next(iter(_cache)))
    _cache[key] = data
    return data


def contact_sheet_png(brief, slides: list[Slide], design: DesignSystem,
                      out_path: Path, columns: int = 4) -> dict:
    """One image showing every slide; used as the project thumbnail."""
    from .content import build_outline

    if not slides:
        slides = build_outline(brief)
    total = len(slides)
    thumb_w = 320
    thumb_h = int(thumb_w * H / W)
    rows = math_rows = (total + columns - 1) // columns
    pad = 18
    sheet = Image.new("RGB", (columns * thumb_w + pad * (columns + 1),
                              rows * (thumb_h + 26) + pad * (rows + 1)), design.sheet)
    d = ImageDraw.Draw(sheet)
    for i, spec in enumerate(slides[: total]):
        r, c = divmod(i, columns)
        tile = render_slide(spec, design, i + 1, total).resize((thumb_w, thumb_h),
                                                              Image.Resampling.LANCZOS)
        sheet.paste(tile, (pad + c * (thumb_w + pad), pad + r * (thumb_h + 26)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, format="PNG", optimize=True)
    return {"width": sheet.width, "height": sheet.height}


def clear_cache() -> None:
    _cache.clear()