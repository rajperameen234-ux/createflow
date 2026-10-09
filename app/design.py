"""Design system: turns a brief into one coherent visual identity.

Every renderer (PPTX, poster, social graphic, SVG) consumes the same
:class:`DesignSystem` object, which is what keeps the three outputs on-brand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .schemas import StylePreset


# --------------------------------------------------------------------------
# colour helpers
# --------------------------------------------------------------------------
def clamp(value: float, low: float = 0.0, high: float = 255.0) -> int:
    return int(max(low, min(high, round(value))))


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = (clamp(c) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = relative_luminance(hex_to_rgb(a)), relative_luminance(hex_to_rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def mix(a: str, b: str, weight: float = 0.5) -> str:
    """Blend two colours; ``weight`` is how much of ``b`` to add."""
    ra, ga, ba = hex_to_rgb(a)
    rb, gb, bb = hex_to_rgb(b)
    return rgb_to_hex(
        (
            ra + (rb - ra) * weight,
            ga + (gb - ga) * weight,
            ba + (bb - ba) * weight,
        )
    )


def shade(color: str, amount: float) -> str:
    """Darken (negative) or lighten (positive) a colour."""
    return mix(color, "#000000" if amount < 0 else "#FFFFFF", abs(amount))


def ensure_contrast(foreground: str, background: str, minimum: float = 4.5) -> str:
    """Nudge ``foreground`` toward black or white until it is readable."""
    if contrast_ratio(foreground, background) >= minimum:
        return foreground
    dark = "#0B0B12"
    light = "#FFFFFF"
    best, best_score = foreground, contrast_ratio(foreground, background)
    for direction in (0.15, 0.3, 0.45, 0.6, 0.75, 0.9):
        for candidate in (mix(foreground, dark, direction), mix(foreground, light, direction)):
            score = contrast_ratio(candidate, background)
            if score > best_score:
                best, best_score = candidate, score
        if best_score >= minimum:
            break
    return best


def saturate(color: str, factor: float) -> str:
    r, g, b = hex_to_rgb(color)
    grey = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return rgb_to_hex(
        (grey + (r - grey) * factor, grey + (g - grey) * factor, grey + (b - grey) * factor)
    )


# --------------------------------------------------------------------------
# style presets
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class StylePresetSpec:
    label: str
    description: str
    motif: str
    heading_font: str
    body_font: str
    default_primary: str
    default_secondary: str
    default_accent: str
    paper: str
    ink: str
    dark_canvas: bool
    pattern: str
    corner_radius: int
    heading_tracking: float
    rule_weight: int


STYLE_PRESETS: dict[StylePreset, StylePresetSpec] = {
    StylePreset.EDITORIAL_LUXURY: StylePresetSpec(
        label="Editorial Luxury",
        description="Serif headlines, generous margins, quiet gold rules and archival tone.",
        motif="Editorial rules & foil arcs",
        heading_font="Georgia",
        body_font="Calibri",
        default_primary="#3A2418",
        default_secondary="#EFE3D0",
        default_accent="#C9A227",
        paper="#FAF6EF",
        ink="#20140D",
        dark_canvas=False,
        pattern="arches",
        corner_radius=4,
        heading_tracking=0.0,
        rule_weight=1,
    ),
    StylePreset.MODERN_MINIMAL: StylePresetSpec(
        label="Modern Minimal",
        description="Neutral canvas, one confident accent, tight grid and small caps labels.",
        motif="Hairline grid & blocks",
        heading_font="Segoe UI Semibold",
        body_font="Segoe UI",
        default_primary="#111827",
        default_secondary="#F3F4F6",
        default_accent="#4F46E5",
        paper="#FFFFFF",
        ink="#111827",
        dark_canvas=False,
        pattern="grid",
        corner_radius=14,
        heading_tracking=-0.4,
        rule_weight=1,
    ),
    StylePreset.BOLD_CREATIVE: StylePresetSpec(
        label="Bold Creative",
        description="Saturated colour blocking, oversized type and energetic diagonals.",
        motif="Colour blocks & diagonals",
        heading_font="Arial Black",
        body_font="Arial",
        default_primary="#1B1464",
        default_secondary="#FFD166",
        default_accent="#EF476F",
        paper="#FFF9F2",
        ink="#14102E",
        dark_canvas=False,
        pattern="diagonal",
        corner_radius=18,
        heading_tracking=-0.8,
        rule_weight=3,
    ),
    StylePreset.CORPORATE_PREMIUM: StylePresetSpec(
        label="Corporate Premium",
        description="Structured blues, disciplined alignment and confident data framing.",
        motif="Ledger lines & bars",
        heading_font="Segoe UI Semibold",
        body_font="Segoe UI",
        default_primary="#0B3C6B",
        default_secondary="#E8EEF5",
        default_accent="#2E8BC0",
        paper="#FAFCFE",
        ink="#0E2338",
        dark_canvas=False,
        pattern="ledger",
        corner_radius=8,
        heading_tracking=-0.2,
        rule_weight=1,
    ),
    StylePreset.DARK_CINEMATIC: StylePresetSpec(
        label="Dark Cinematic",
        description="Near-black stage, luminous accent and wide letter-spaced titles.",
        motif="Spotlight bloom & bars",
        heading_font="Segoe UI Light",
        body_font="Segoe UI",
        default_primary="#0A0A12",
        default_secondary="#1C1C2B",
        default_accent="#7C6BFF",
        paper="#101018",
        ink="#F2F2F7",
        dark_canvas=True,
        pattern="spotlight",
        corner_radius=12,
        heading_tracking=2.0,
        rule_weight=2,
    ),
    StylePreset.PLAYFUL_COLORFUL: StylePresetSpec(
        label="Playful Colorful",
        description="Warm candy palette, rounded shapes and friendly short copy.",
        motif="Confetti dots & blobs",
        heading_font="Arial Rounded MT Bold",
        body_font="Arial",
        default_primary="#EF476F",
        default_secondary="#FFF3E0",
        default_accent="#06D6A0",
        paper="#FFFBF5",
        ink="#22223B",
        dark_canvas=False,
        pattern="confetti",
        corner_radius=24,
        heading_tracking=-0.3,
        rule_weight=2,
    ),
}


# --------------------------------------------------------------------------
# the resolved identity
# --------------------------------------------------------------------------
@dataclass
class DesignSystem:
    brand_name: str
    tagline: str
    primary: str
    secondary: str
    accent: str
    paper: str
    ink: str
    heading_font: str
    body_font: str
    preset: StylePreset
    preset_label: str
    motif: str
    pattern: str
    dark_canvas: bool
    corner_radius: int
    heading_tracking: float
    rule_weight: int
    # derived
    on_primary: str = field(init=False)
    muted: str = field(init=False)
    soft_accent: str = field(init=False)
    surface: str = field(init=False)
    type_scale: dict = field(init=False)

    def __post_init__(self) -> None:
        self.on_primary = ensure_contrast("#FFFFFF", self.primary, 4.5)
        self.muted = mix(self.ink, self.paper, 0.45)
        self.soft_accent = mix(self.accent, self.paper, 0.82)
        self.surface = shade(self.paper, -0.03) if not self.dark_canvas else shade(self.paper, 0.05)
        # Contact sheets sit on a neutral canvas, never on the artwork itself.
        self.sheet = "#101014" if not self.dark_canvas else "#08080C"
        self.type_scale = {
            "hero": 54,
            "title": 38,
            "section": 32,
            "subtitle": 20,
            "body": 15,
            "small": 12,
            "micro": 10,
            "metric": 44,
        }

    # --- colour ramps used by charts and gradients -----------------------
    def series(self, count: int) -> list[str]:
        base = [self.accent, self.primary, mix(self.accent, self.primary, 0.4), mix(self.secondary, self.accent, 0.35)]
        out = []
        for i in range(count):
            if i < len(base):
                out.append(base[i])
            else:
                out.append(mix(self.accent, self.secondary, (i % 5) / 5))
        return out

    def gradient(self, steps: int = 24) -> list[str]:
        return [mix(self.primary, self.accent, i / (steps - 1)) for i in range(steps)]

    def summary(self) -> dict:
        return {
            "preset": self.preset.value,
            "preset_label": self.preset_label,
            "primary_color": self.primary,
            "secondary_color": self.secondary,
            "accent_color": self.accent,
            "ink": self.ink,
            "paper": self.paper,
            "heading_font": self.heading_font,
            "body_font": self.body_font,
            "motif": self.motif,
        }


def _pick_accent(primary: str, secondary: str, requested: Optional[str], spec: StylePresetSpec) -> str:
    if requested:
        base = requested
    else:
        base = spec.default_accent
    # Avoid an accent identical to the paper/ink of the chosen preset.
    if base.upper() in {spec.paper.upper(), spec.ink.upper()}:
        base = spec.default_accent
    return ensure_contrast(base, spec.paper, 3.0)


def build_design_system(brief) -> DesignSystem:
    """Resolve a validated brief into the shared design system."""
    spec = STYLE_PRESETS[brief.style_preset]
    primary = (brief.primary_color or spec.default_primary).upper()
    secondary = (brief.secondary_color or spec.default_secondary).upper()
    accent = _pick_accent(primary, secondary, brief.accent_color, spec)

    # Keep primary distinct from the paper for dark presets.
    if spec.dark_canvas and contrast_ratio(primary, spec.paper) < 1.6:
        primary = spec.default_primary

    paper = spec.paper
    ink = spec.ink
    if spec.dark_canvas:
        on_accent = ensure_contrast("#0A0A12", accent, 4.5)
        ink = ensure_contrast("#FFFFFF", paper, 8.0)
        del on_accent

    return DesignSystem(
        brand_name=(brief.brand_name or brief.project_name).strip() or brief.project_name,
        tagline=brief.tagline.strip(),
        primary=primary,
        secondary=secondary,
        accent=accent,
        paper=paper,
        ink=ink,
        heading_font=spec.heading_font,
        body_font=spec.body_font,
        preset=brief.style_preset,
        preset_label=spec.label,
        motif=spec.motif,
        pattern=spec.pattern,
        dark_canvas=spec.dark_canvas,
        corner_radius=spec.corner_radius,
        heading_tracking=spec.heading_tracking,
        rule_weight=spec.rule_weight,
    )


def swatch_palette(primary: str, secondary: str, accent: str, dark: bool) -> list[str]:
    """5-stop gradient used by the live preview swatches."""
    start, end = (primary, accent) if dark else (primary, secondary)
    return [mix(start, end, i / 4) for i in range(5)]


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str, max_len: int = 60) -> str:
    """Filesystem-safe base name (no path traversal, no reserved chars)."""
    cleaned = _SAFE_NAME.sub("-", (name or "createflow").strip()).strip("-._")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    if not cleaned:
        cleaned = "createflow"
    return cleaned[:max_len].strip("-._") or "createflow"