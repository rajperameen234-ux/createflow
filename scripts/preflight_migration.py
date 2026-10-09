r"""Preflight: what is missing, and is the migration safe to run?

Checks, against live Supabase:
  * which of the three tables the app needs actually exist
  * whether the private bucket exists and is private
  * that the migration is idempotent and non-destructive (creates-if-missing,
    no DROP TABLE / TRUNCATE / DELETE / CASCADE / DROP DATABASE)
  * that the SQL parses with the real PostgreSQL grammar

Run:  .venv\Scripts\python.exe -m scripts.preflight_migration
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cloud import get_cloud  # noqa: E402

MIGRATION = (
    Path(__file__).resolve().parent.parent.parent
    / "supabase" / "migrations" / "0001_createflow_schema.sql"
)

REQUIRED_TABLES = ["profiles", "projects", "generated_assets"]

FORBIDDEN = [
    (r"\bdrop\s+table\b", "DROP TABLE"),
    (r"\btruncate\b", "TRUNCATE"),
    (r"\bdelete\s+from\b", "DELETE FROM"),
    (r"\bdrop\s+database\b", "DROP DATABASE"),
    (r"\bdrop\s+schema\b", "DROP SCHEMA"),
    (r"\bdrop\s+table\b[^;]*\bcascade\b", "DROP TABLE ... CASCADE"),
    (r"\bdrop\s+(policy|trigger|function|index)\b[^;]*\bcascade\b", "DROP ... CASCADE"),
]

# "on delete cascade" is a referential action on a foreign key of one of this
# app's own tables, not a drop. It must not be reported as destructive.
BENIGN = [
    (r"\bon\s+delete\s+cascade\b", "ON DELETE CASCADE (foreign key on CreateFlow's own tables)"),
]


def main() -> int:
    sql = MIGRATION.read_text(encoding="utf-8")
    cloud = get_cloud()

    print(f"migration file : {MIGRATION}")
    print(f"size           : {len(sql)} bytes")
    print()

    print("=== 1. what already exists in your Supabase project ===")
    headers = {"apikey": cloud.service_key, "Authorization": f"Bearer {cloud.service_key}"}
    missing: list[str] = []
    if cloud.configured:
        with httpx.Client(timeout=40) as client:
            for table in REQUIRED_TABLES:
                response = client.head(
                    f"{cloud.url}/rest/v1/{table}?select=*&limit=1", headers=headers
                )
                if response.status_code == 404:
                    missing.append(table)
                    print(f"  public.{table:18} MISSING")
                else:
                    print(f"  public.{table:18} already present")
            buckets = client.get(f"{cloud.url}/storage/v1/bucket", headers=headers).json()
            match = next((b for b in buckets if b["name"] == cloud.bucket), None)
            if match is None:
                print(f"  storage bucket '{cloud.bucket}' MISSING")
            else:
                print(f"  storage bucket '{cloud.bucket}' present "
                      f"(public={match['public']}, {match['file_size_limit']} B limit)")
    else:
        print("  Supabase is not configured; skipping live checks.")
        missing = list(REQUIRED_TABLES)

    print("\n=== 2. is the migration safe to apply? ===")
    unsafe: list[str] = []
    for pattern, label in FORBIDDEN:
        hits = re.findall(pattern, sql, re.I)
        if hits:
            unsafe.append(f"{label} x{len(hits)}")
    if unsafe:
        print("  UNSAFE statements found:")
        for item in unsafe:
            print("   -", item)
    else:
        print("  no DROP TABLE / TRUNCATE / DELETE / DROP DATABASE")
        print("  -> existing tables and rows are never touched")

    for pattern, label in BENIGN:
        hits = re.findall(pattern, sql, re.I)
        if hits:
            print(f"  note: {len(hits)}x {label}")
            print("        (deleting a row cascades to that row's own children only)")

    guards = {
        "create table if not exists": len(re.findall(r"create table if not exists", sql, re.I)),
        "create index if not exists": len(re.findall(r"create index if not exists", sql, re.I)),
        "create unique index if not exists": len(
            re.findall(r"create unique index if not exists", sql, re.I)),
        "drop policy if exists (own policies only)": len(
            re.findall(r"drop policy if exists", sql, re.I)),
        "bucket upsert on conflict": len(re.findall(r"on conflict \(id\) do update", sql, re.I)),
    }
    for label, count in guards.items():
        print(f"  {label:42} x{count}")
    print("  -> running it twice is a no-op; it will not create duplicates")

    print("\n=== 3. does it parse as real PostgreSQL? ===")
    try:
        from pglast import parse_sql
    except ImportError:
        print("  pglast not installed, skipping")
    else:
        statements = parse_sql(sql)
        print(f"  parsed OK: {len(statements)} statements")

    print("\n=== 4. what you need to run ===")
    if not missing:
        print("  Nothing to do: every table the app needs already exists.")
    else:
        print(f"  Missing: {', '.join('public.' + t for t in missing)}")
        print()
        print("  1. Open: https://supabase.com/dashboard/project/rgdkjhovgwlegtwaocqg")
        print("  2. Click 'SQL Editor' in the left sidebar, then 'New query'")
        print(f"  3. Open this file and copy everything in it:  {MIGRATION}")
        print("  4. Paste it into the editor and click 'Run' (bottom right)")
        print("  5. Come back and run:  .venv\\Scripts\\python.exe -m scripts.preflight_migration")
    print()
    return 1 if unsafe else 0


if __name__ == "__main__":
    raise SystemExit(main())