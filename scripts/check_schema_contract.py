r"""Static check that the API's insert payloads match the SQL migration columns.

Catches column-name typos before the migration is applied, so the first real
cloud save does not fail on a schema mismatch.

Run:  .venv\Scripts\python.exe -m scripts.check_schema_contract
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cloud import asset_row, project_payload  # noqa: E402
from app.design import build_design_system  # noqa: E402
from scripts.smoke import BRIEF  # noqa: E402

MIGRATION = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations" / "0001_createflow_schema.sql"


def columns(sql: str, table: str) -> set[str]:
    match = re.search(
        rf"create table if not exists public\.{table}\s*\((.*?)\n\);", sql, re.S | re.I
    )
    if not match:
        raise SystemExit(f"could not find table {table} in {MIGRATION.name}")
    found: set[str] = set()
    for raw in match.group(1).split("\n"):
        line = raw.strip().rstrip(",")
        if not line or line.startswith("--"):
            continue
        name = line.split()[0]
        if re.fullmatch(r"[a-z_]+", name):
            found.add(name)
    return found


def main() -> int:
    sql = MIGRATION.read_text(encoding="utf-8")
    project_cols = columns(sql, "projects")
    asset_cols = columns(sql, "generated_assets")

    design = build_design_system(BRIEF)
    project_payload_rows = set(project_payload(BRIEF, design, 8, ["hero"]).keys())

    fake_asset = {
        "kind": "presentation",
        "filename": "x.pptx",
        "content_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "size_bytes": 1,
        "width": None,
        "height": None,
    }
    # user_id is supplied by asset_row itself, so mirror a real call here.
    asset_payload_rows = set(asset_row("00000000-0000-0000-0000-000000000000",
                                       "11111111-1111-1111-1111-111111111111",
                                       fake_asset, "a/b/x.pptx", "deadbeef").keys())
    if "user_id" not in asset_payload_rows:
        print("\n  PROBLEM: asset_row() does not write user_id "
              "(generated_assets.user_id is NOT NULL)")
        ok = False

    ok = True
    for label, rows, cols in (
        ("projects", project_payload_rows, project_cols),
        ("generated_assets", asset_payload_rows, asset_cols),
    ):
        extra = sorted(rows - cols)
        print(f"\n=== {label} ===")
        print(f"  columns in migration : {len(cols)}")
        print(f"  columns sent by API  : {len(rows)}")
        if extra:
            print(f"  UNKNOWN COLUMNS SENT: {extra}")
            ok = False
        else:
            print("  every column sent exists in the migration")

    print("\n=== index / policy coverage ===")
    for needle, label in (
        ("projects_user_created_idx", "projects (user_id, created_at desc) index"),
        ("assets_project_idx", "generated_assets (project_id) index"),
        ("projects_select_own", "projects RLS select policy"),
        ("projects_insert_own", "projects RLS insert policy"),
        ("projects_update_own", "projects RLS update policy"),
        ("projects_delete_own", "projects RLS delete policy"),
        ("assets_select_own", "generated_assets RLS select policy"),
        ("assets_insert_own", "generated_assets RLS insert policy"),
        ("assets_delete_own", "generated_assets RLS delete policy"),
        ("assets_read_own", "storage.objects read policy"),
        ("assets_insert_own_objects" , "storage.objects write policy"),
        ("createflow-assets", "private storage bucket"),
        ("public = false", "bucket marked private"),
    ):
        found = needle in sql
        print(f"  {'ok  ' if found else 'MISS'} {label}")
        if not found and label != "storage.objects write policy":
            ok = False

    # the storage insert policy shares a name prefix; confirm it exists
    if "create policy \"assets_insert_own\"\n  on storage.objects" not in sql:
        print("  MISS storage.objects write policy")
        ok = False

    print("\n=== result ===")
    print("schema contract matches" if ok else "MISMATCHES FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())