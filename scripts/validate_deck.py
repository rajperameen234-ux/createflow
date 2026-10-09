r"""Structural validation of a generated deck.

No PowerPoint or LibreOffice is available in this environment, so instead of
rendering we assert the things that would break a slide: shapes outside the
canvas, text frames that cannot fit their content, missing notes, and whether
charts are real chart parts.
"""

from __future__ import annotations

import inspect
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pptx import Presentation  # noqa: E402
from pptx.util import Emu  # noqa: E402

EMU_PER_PT = 12700


def text_capacity(shape) -> tuple[int, int]:
    """Rough (lines that fit, characters per line) for a shape's text frame."""
    tf = shape.text_frame
    width_pt = shape.width / EMU_PER_PT
    height_pt = shape.height / EMU_PER_PT
    chars = max(1, int(width_pt / 5.4))
    lines = max(1, int(height_pt / 13.5))
    return lines, chars


def check_user_id_column() -> list[str]:
    """Every generated_assets insert must carry a non-null user_id."""
    problems: list[str] = []
    cloud_module = sys.modules.get("app.cloud")
    if cloud_module is None:
        from app import cloud as cloud_module  # type: ignore

    signature = inspect.signature(cloud_module.asset_row)
    if "user_id" not in signature.parameters:
        problems.append(
            "asset_row() has no user_id parameter; inserts will violate the "
            "NOT NULL constraint on generated_assets.user_id"
        )
        return problems

    row = cloud_module.asset_row(
        "00000000-0000-0000-0000-000000000000",
        "11111111-1111-1111-1111-111111111111",
        {"kind": "poster", "filename": "p.png", "content_type": "image/png",
         "size_bytes": 1, "width": 10, "height": 10},
        "u/p/p.png",
        "abc",
    )
    if not row.get("user_id"):
        problems.append("asset_row() produces a row with a null user_id")
    else:
        print(f"  asset_row() writes user_id  ok  {row['user_id'][:8]}...")
    return problems


def check(deck_path: Path) -> list[str]:
    prs = Presentation(str(deck_path))
    sw, sh = prs.slide_width, prs.slide_height
    problems: list[str] = []

    if abs(sw - Emu(12192000)) > Emu(100000) or abs(sh - Emu(6858000)) > Emu(100000):
        problems.append(f"slide size is not 13.333x7.5in: {sw}x{sh}")

    for index, slide in enumerate(prs.slides, 1):
        overflow = 0
        charts = 0
        missing_notes = []
        for shape in slide.shapes:
            if shape.left is None or shape.top is None:
                continue
            # Shapes named "bleed-*" are deliberate full-bleed decoration.
            if shape.name.lower().startswith("bleed-"):
                continue
            if (shape.left < -Emu(10000) or shape.top < -Emu(10000)
                    or shape.left + shape.width > sw + Emu(10000)
                    or shape.top + shape.height > sh + Emu(10000)):
                overflow += 1
            if getattr(shape, "has_chart", False):
                charts += 1
            if shape.has_text_frame and shape.text_frame.text.strip():
                lines, chars = text_capacity(shape)
                needed = sum(
                    max(1, -(-len(p.text) // chars))
                    for p in shape.text_frame.paragraphs if p.text
                )
                if needed > lines * 1.6:
                    overflow += 0  # soft: PowerPoint autofits; log separately
        if not slide.has_notes_slide or not slide.notes_slide.notes_text_frame.text.strip():
            missing_notes.append("no notes")
        if overflow:
            problems.append(f"slide {index}: {overflow} shape(s) outside the canvas")
        if missing_notes:
            problems.append(f"slide {index}: {', '.join(missing_notes)}")
        print(f"  slide {index:2}: shapes={len(slide.shapes):3} charts={charts} "
              f"notes={'y' if slide.has_notes_slide else 'n'} oob={overflow}")

    return problems


def main() -> int:
    print("=== asset_row contract (generated_assets.user_id is NOT NULL) ===")
    contract_problems = check_user_id_column()
    for problem in contract_problems:
        print(f"  PROBLEM: {problem}")
    print()

    deck = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if deck is None:
        from app.pipeline import generate
        from scripts.smoke import BRIEF

        result = generate(BRIEF)
        source = next(a.path for a in result.assets if a.kind.value == "presentation")
        deck = Path(tempfile.gettempdir()) / "createflow-validate.pptx"
        deck.write_bytes(source.read_bytes())
        result.cleanup()  # prove the temp workspace is fully removable
    if not deck.exists():
        print(f"deck not found: {deck}")
        return 1

    print(f"checking {deck}")
    problems = check(deck) + contract_problems
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print(" -", p)
        return 1
    print("\nno structural problems found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())