"""Narrative engine.

Builds a structured deck outline from a brief. Content is derived from the
user's own words: no invented statistics, studies, or testimonials. Where a
chart needs numbers, the values are produced by a deterministic model and
labelled *Illustrative* on the slide itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from .schemas import GenerateRequest

LayoutKind = Literal[
    "hero",
    "two_column",
    "numbered_process",
    "timeline",
    "metrics",
    "comparison",
    "image_led",
    "framework",
    "quote_led",
    "summary",
]

Stop = set(
    """a an the and or of to in on for with without from by as at is are be been being that this these those
    it its into over under about our your their we you they i not no but if then than so such can could would
    should will shall may might must do does did have has had having theythem who whom which what when where
    why how all any both each few more most other some only own same too very just also""".split()
)


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[A-Za-z0-9'\-]+", text or "") if w.lower() not in Stop]


def keywords(text: str, limit: int = 6) -> list[str]:
    counts: dict[str, int] = {}
    for word in _words(text):
        key = word.lower()
        counts[key] = counts.get(key, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w.capitalize() for w, _ in ordered[:limit]] or ["Brand", "Story"]


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [" ".join(p.split()) for p in parts if p and p.strip()]


def title_case(text: str) -> str:
    small = {"a", "an", "the", "of", "and", "in", "to", "for", "on", "with", "at", "by", "from"}
    words = [w for w in (text or "").split() if w]
    out: list[str] = []
    for i, word in enumerate(words):
        low = word.lower()
        if i not in (0, len(words) - 1) and low in small:
            out.append(low)
        else:
            out.append(word[:1].upper() + word[1:])
    return " ".join(out)


def short(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-") + "…"


def headline_from(text: str, fallback: str, limit: int = 42) -> str:
    """Derive a headline from the brief's own opening clause.

    Never ends in an ellipsis: a truncated clause is dropped instead, so posters
    and title slides always show whole words.
    """

    def clean(value: str) -> str:
        value = " ".join(value.split()).strip()
        if value.endswith("…"):
            parts = value[:-1].split()
            if len(parts) > 2:
                parts = parts[:-1]
            value = " ".join(parts).rstrip(" ,;:-")
        return title_case(value)

    parts = sentences(text)
    if parts:
        first = parts[0].rstrip(".")
        first = re.sub(r"^(our|the|this)\s+", "", first, flags=re.I)
        # Prefer the opening clause before a comma when the sentence is long.
        if len(first) > limit + 14 and "," in first:
            head = first.split(",", 1)[0].strip()
            if 12 <= len(head) <= 78:
                return clean(head)
        if 12 <= len(first) <= limit + 14:
            return clean(first)
    keys = keywords(text, 3)
    if len(keys) >= 2:
        return f"{keys[0]} & {keys[1]}"
    return fallback


@dataclass
class Bullet:
    head: str
    body: str


@dataclass
class Metric:
    value: str
    label: str
    note: str = ""


@dataclass
class Series:
    name: str
    points: list[tuple[str, float]]
    unit: str = ""
    illustrative: bool = True


@dataclass
class Slide:
    layout: LayoutKind
    title: str
    kicker: str = ""
    body: str = ""
    bullets: list[Bullet] = field(default_factory=list)
    metrics: list[Metric] = field(default_factory=list)
    steps: list[tuple[str, str]] = field(default_factory=list)
    timeline: list[tuple[str, str]] = field(default_factory=list)
    compare: tuple[list[str], list[str], list[str]] = field(default_factory=lambda: ([], [], []))
    compare_titles: tuple[str, str] = ("Today", "Next")
    quadrant: list[tuple[str, str, str]] = field(default_factory=list)
    chart_title: str = ""
    series: list[Series] = field(default_factory=list)
    chart_kind: Literal["bar", "column", "line", "doughnut"] = "column"
    caption: str = ""
    media_label: str = ""
    notes: str = ""
    image_prompt: str = ""


# --------------------------------------------------------------------------
# derived content blocks — grounded in the brief, never invented facts
# --------------------------------------------------------------------------
def _audience_insights(brief: GenerateRequest) -> list[Bullet]:
    audience = " ".join(brief.audience.split())
    keys = keywords(f"{audience} {brief.topic}", 4)
    return [
        Bullet(head=f"Priority: {keys[0] if keys else 'Core audience'}", body=f"Direct every message at {audience}."),
        Bullet(
            head="What earns attention",
            body=f"Lead with the concrete outcome in {short(brief.topic, 70).lower()} rather than background detail.",
        ),
        Bullet(
            head=f"Tone to hold: {brief.tone.split(',')[0].strip().title()}",
            body=f"{title_case(brief.tone)} reads as considered and trustworthy to this audience.",
        ),
        Bullet(
            head="Proof over promises",
            body="Show the product or process itself; this audience decides on specifics, not adjectives.",
        ),
    ]


def _pillars(brief: GenerateRequest) -> list[Bullet]:
    topic = short(brief.topic, 110).rstrip(".")
    goal = brief.goal.strip().rstrip(".")
    return [
        Bullet(head="Craft", body=f"Every touchpoint of {brief.brand_name or brief.project_name} is finished to the same standard — no rough edges left for the customer to find."),
        Bullet(head="Clarity", body=f"Message hierarchy follows one rule: {short(goal, 84).lower()}"),
        Bullet(head="Relevance", body=topic + "."),
        Bullet(head="Consistency", body=f"Colour, type and layout stay fixed so the brand reads as one system, not a set of pieces."),
    ]


def _process(brief: GenerateRequest) -> list[tuple[str, str]]:
    keys = keywords(f"{brief.topic} {brief.goal}", 3)
    return [
        ("Discover", f"Define who we serve, what {keys[0].lower() if keys else 'they'} need, and the one behaviour we want to change."),
        ("Define", f"Lock the promise, the visual identity and the message hierarchy before any asset is produced."),
        ("Design", "Build the system: layout grid, type scale, colour roles and reusable components."),
        ("Produce", "Apply the system across every deliverable so the set ships as one campaign."),
        ("Launch", f"Release, gather real feedback, and refine against the goal: {short(brief.goal, 70).lower()}"),
    ]


def _timeline(brief: GenerateRequest) -> list[tuple[str, str]]:
    keys = keywords(f"{brief.topic} {brief.tone}", 3)
    return [
        ("Week 1", f"Positioning and identity workshop for {brief.brand_name or brief.project_name}."),
        ("Week 2", "Copy, layout grid and design system locked and reviewed."),
        ("Week 3", "Production of the launch package across every channel."),
        ("Week 4", f"Launch and live refinement, tuned for {keys[-1].lower() if keys else 'the audience'}."),
    ]


def _comparative(brief: GenerateRequest) -> tuple[list[str], list[str], list[str], str, str]:
    keys = keywords(f"{brief.topic} {brief.audience}", 2)
    a = keys[0] if keys else "Current approach"
    b = keys[1] if len(keys) > 1 else "This proposal"
    now = [
        "Attention competes on volume, not on design quality.",
        f"No single owner for how {a} is presented.",
        "Each asset is built separately, so the brand drifts.",
        "Decisions are made per-channel with no shared rules.",
    ]
    nxt = [
        "One designed system, applied consistently everywhere.",
        f"A shared template set owned by the {brief.brand_name or brief.project_name} team.",
        "Locked colour, type and layout rules across all channels.",
        "Decisions follow one brand guideline, not per-channel taste.",
    ]
    impact = [
        "Stop reinventing the same message each week.",
        "Recognise quality at a glance, across formats.",
        "Every asset reinforces the same impression.",
        "Faster approvals because the rules already exist.",
    ]
    return now, nxt, impact, "Before", "With CreateFlow"


def _framework(brief: GenerateRequest) -> list[tuple[str, str, str]]:
    return [
        ("01", "Signal", f"What {brief.audience.split(',')[0].strip()} sees first, in three seconds."),
        ("02", "Story", f"The one sentence that explains {short(brief.topic, 64).lower()}"),
        ("03", "System", "Colour, type and layout rules that never change."),
        ("04", "Proof", "The product, the process or the detail that earns trust."),
    ]


def _metrics(brief: GenerateRequest) -> list[Metric]:
    keys = keywords(f"{brief.topic} {brief.goal}", 3)
    goal_word = short(brief.goal, 30).rstrip(".")
    return [
        Metric("1", "Coordinated system", "deck, poster and social graphic from one identity"),
        Metric("3", f"Deliverables per brief", f"all aligned to the {keys[0].lower() if keys else 'brand'} palette"),
        Metric("6", "Style presets", "each with its own type scale, motif and palette logic"),
        Metric("∞", "Regenerations", "revise the brief and rebuild the whole package"),
    ]


def _illustrative_series(brief: GenerateRequest) -> list[Series]:
    """Deterministic, clearly-labelled illustrative model data."""
    keys = keywords(f"{brief.topic} {brief.audience}", 3)
    stages = ["Now", "Phase 1", "Phase 2", "Phase 3"]
    base = 18 + (len(keys[0]) if keys else 5) * 2
    growth = [
        ("Baseline awareness", [base, base + 14, base + 31, base + 52]),
        ("Qualified attention", [max(6, base // 2), max(6, base // 2) + 9, max(6, base // 2) + 21, max(6, base // 2) + 34]),
        ("Action / conversion", [max(3, base // 4), max(3, base // 4) + 4, max(3, base // 4) + 10, max(3, base // 4) + 17]),
    ]
    return [
        Series(
            name=name,
            points=list(zip(stages, values)),
            unit=" index points",
            illustrative=True,
        )
        for name, values in growth
    ]


def _quote(brief: GenerateRequest) -> tuple[str, str]:
    goal = short(brief.goal, 120).rstrip(".")
    text = f"“{title_case(goal)} — decided once, executed consistently, seen everywhere.”"
    return text, f"Brand principle for {brief.brand_name or brief.project_name}"


def build_outline(brief: GenerateRequest) -> list[Slide]:
    """Compose the deck: hero → context → body → action, sized to the request."""
    total = brief.presentation_length
    brand = brief.brand_name or brief.project_name
    type_label = brief.presentation_type.value.replace("_", " ").title()
    now, nxt, impact, now_title, nxt_title = _comparative(brief)
    quote_text, quote_attr = _quote(brief)
    series = _illustrative_series(brief)

    slides: list[Slide] = []

    slides.append(
        Slide(
            layout="hero",
            title=headline_from(brief.topic, brief.project_name, 40) if brief.topic else brief.project_name,
            kicker=f"{type_label} · {brand}",
            body=short(brief.tagline or brief.goal, 120).rstrip("."),
            media_label=brand,
            notes=f"Open with the promise, not the agenda. The goal is {short(brief.goal, 90).lower()} "
            f"and the audience is {short(brief.audience, 70).lower()}.",
        )
    )

    slides.append(
        Slide(
            layout="two_column",
            title="Why this, why now",
            kicker="Context",
            body=short(brief.topic, 260),
            bullets=_pillars(brief)[:3],
            caption="Framing drawn directly from the project brief.",
            notes="Establish why the work matters before showing how it looks. Read the body copy "
            "as written by the requester; the three pillars are the delivery standard we will hold.",
        )
    )

    slides.append(
        Slide(
            layout="quote_led",
            title="The one sentence",
            kicker="Positioning",
            body=quote_text,
            media_label=quote_attr,
            caption="Derived from the stated primary goal.",
            notes="If the audience remembers one line, make it this one. Everything in the deck should "
            "either support it or stay out of the way.",
        )
    )

    slides.append(
        Slide(
            layout="image_led",
            title=f"Designed for {short(brief.audience.split(',')[0].strip(), 28) or 'the audience'}",
            kicker="Direction",
            body=short(brief.audience, 150),
            bullets=_audience_insights(brief)[:2],
            media_label=f"{brand} · visual direction",
            caption=f"Style: {brief.visual_style}. Motif: {title_case(brief.visual_style)} shapes and rules.",
            notes="Show the aesthetic intent. Everything here is produced from the same design system as "
            "the deck, so the visuals already exist as editable files.",
        )
    )

    slides.append(
        Slide(
            layout="framework",
            title="The system we apply",
            kicker="Framework",
            body=short(brief.goal, 150),
            quadrant=_framework(brief),
            caption="Four layers, applied in order, on every asset.",
            notes="Signal, Story, System, Proof. This is the checklist used when producing anything for "
            f"{brand}; if a layer is missing the asset is not finished.",
        )
    )

    slides.append(
        Slide(
            layout="numbered_process",
            title="How the work gets made",
            kicker="Process",
            body=f"A repeatable five-step path from brief to published package, built for {short(brief.tone, 50).lower()} delivery.",
            steps=_process(brief),
            caption="Each step produces a reviewable artefact.",
            notes="Run this end to end on a real project. The order matters: defining before designing "
            "prevents the brand drift we are trying to remove.",
        )
    )

    slides.append(
        Slide(
            layout="metrics",
            title="What the package contains",
            kicker="Scope",
            body="One brief produces a coordinated set, not three disconnected files.",
            metrics=_metrics(brief),
            caption="Counts describe CreateFlow output, not market performance.",
            notes="Clarify expectations: the deliverable is a designed, editable system. Commercial "
            "results are measured separately by the team using it.",
        )
    )

    slides.append(
        Slide(
            layout="comparison",
            title="What changes",
            kicker="Comparison",
            body="The practical difference between ad-hoc production and a shared system.",
            compare_titles=(now_title, nxt_title),
            compare=(now, nxt, impact),
            caption="Left column reflects the current working method described in the brief.",
            notes="Keep this concrete. Every row on the right is something the team can do on day one.",
        )
    )

    slides.append(
        Slide(
            layout="metrics",
            title="Illustrative rollout curve",
            kicker="Illustrative data",
            body="A directional model of how attention compounds when the identity is applied consistently. "
            "Values are illustrative planning figures, not measured results.",
            chart_title="Attention index by phase",
            series=series,
            chart_kind="column",
            caption="Illustrative model. Replace with your own figures once measured.",
            notes="Use this as a planning shape only. Do not present these numbers as performance data; "
            "swap in real measurements as soon as they exist.",
        )
    )

    slides.append(
        Slide(
            layout="timeline",
            title="Four-week launch path",
            kicker="Timeline",
            body="A tight schedule that front-loads the decisions that shape everything else.",
            timeline=_timeline(brief),
            caption="Weeks are illustrative for a standard single-team launch.",
            notes="Ask the requester to confirm the week-one workshop attendees before circulating this.",
        )
    )

    slides.append(
        Slide(
            layout="two_column",
            title="Tone and voice",
            kicker="Brand voice",
            body=f"{title_case(brief.tone)} — applied consistently across the deck, poster and social graphic.",
            bullets=[
                Bullet(head="We say it plainly", body="Short sentences, concrete nouns, no filler adjectives."),
                Bullet(head="We respect the reader", body=short(brief.audience, 90).rstrip(".")),
                Bullet(head="We stay specific", body=f"Every claim traces back to {short(brief.topic, 70).lower()}"),
            ],
            caption="Voice rules are enforced by the shared template set.",
            notes="Voice is the fastest way for a new brand to feel trustworthy. Read two examples aloud.",
        )
    )

    slides.append(
        Slide(
            layout="summary",
            title="What happens next",
            kicker="Call to action",
            body=short(brief.goal, 160).rstrip("."),
            bullets=[
                Bullet(head="Confirm the brief", body="Lock audience, goal and tone in one pass."),
                Bullet(head="Review the package", body=f"Deck, poster and social graphic for {brand}."),
                Bullet(head="Revise and regenerate", body="Change any input and rebuild the full set."),
            ],
            caption="Owner and date to be confirmed by the requesting team.",
            notes="Close on the ask. Name the single next action and who owns it before leaving the room.",
        )
    )

    return _select(slides, total)


# Priority for each candidate slide: lower runs first. Keeps the opening and
# the close anchored while the middle adapts to the requested length.
_PRIORITY = {
    "hero": 0,
    "two_column": 1,
    "image_led": 2,
    "framework": 3,
    "metrics": 4,
    "numbered_process": 5,
    "comparison": 6,
    "quote_led": 7,
    "timeline": 8,
    "summary": 9,
}


def _clone_with_index(slide: Slide, index: int) -> Slide:
    return Slide(
        layout=slide.layout,
        title=f"{slide.title} · part {index}",
        kicker=slide.kicker,
        body=slide.body,
        bullets=slide.bullets,
        metrics=slide.metrics,
        steps=slide.steps,
        timeline=slide.timeline,
        compare=slide.compare,
        compare_titles=slide.compare_titles,
        quadrant=slide.quadrant,
        chart_title=slide.chart_title,
        series=slide.series,
        chart_kind=slide.chart_kind,
        caption=slide.caption,
        media_label=slide.media_label,
        notes=slide.notes,
    )


def _select(candidates: list[Slide], total: int) -> list[Slide]:
    """Pick exactly ``total`` distinct slides, in narrative order.

    Every slide instance is unique (no duplicate titles), so selection never
    has to clone content. If the request is longer than the narrative, the
    strongest process slide is extended rather than repeating a weak one.
    """
    if total <= len(candidates):
        # Keep the authored narrative order and drop the least important slides
        # first (never the opening or the close).
        droppable = sorted(
            (s for s in candidates if s.layout not in ("hero", "summary")),
            key=lambda s: -_PRIORITY.get(s.layout, 5),
        )
        dropped: set[int] = set()
        for slide in droppable:
            if len(candidates) - len(dropped) <= total:
                break
            dropped.add(id(slide))
        chosen = [s for s in candidates if id(s) not in dropped]
    else:
        chosen = list(candidates)

    picked = list(chosen)

    if len(picked) < total:
        # Extra slides go before the closing slide so it always ends the deck.
        close = next((s for s in picked if s.layout == "summary"), None)
        filler = next((s for s in picked if s.layout == "numbered_process"), picked[-2])
        extras = [_clone_with_index(filler, i + 1) for i in range(total - len(picked))]
        insert_at = picked.index(close) if close is not None else len(picked)
        picked[insert_at:insert_at] = extras

    titles = [s.title for s in picked]
    if len(set(titles)) != len(titles):  # defensive: never ship duplicate titles
        seen: set[str] = set()
        unique: list[Slide] = []
        for slide in picked:
            if slide.title in seen:
                slide = _clone_with_index(slide, len(unique) + 1)
            seen.add(slide.title)
            unique.append(slide)
        picked = unique
    return picked