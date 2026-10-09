r"""Parse the migration with the real PostgreSQL grammar.

Catches syntax errors before the file is pasted into the Supabase SQL editor,
and reports the objects the migration is expected to create.

Run:  .venv\Scripts\python.exe -m scripts.lint_migration
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pglast import parse_sql  # noqa: E402

MIGRATION = (
    Path(__file__).resolve().parent.parent.parent
    / "supabase" / "migrations" / "0001_createflow_schema.sql"
)


def main() -> int:
    sql = MIGRATION.read_text(encoding="utf-8")
    print(f"parsing {MIGRATION.name} ({len(sql)} bytes) with the PostgreSQL grammar\n")

    try:
        statements = parse_sql(sql)
    except Exception as exc:
        print("SYNTAX ERROR\n")
        print(exc)
        return 1

    print(f"parsed OK: {len(statements)} statements")

    print("\nobjects the migration creates:")
    expectations = [
        (r"create table (?:if not exists )?public\.(\w+)", "table"),
        (r"create (?:unique )?index (?:if not exists )?(\w+)", "index"),
        (r"create policy \"?([\w]+)", "policy"),
        (r"create or replace function (public\.\w+)", "function"),
        (r"create trigger (\w+)", "trigger"),
        (r"alter table (public\.\w+) enable row level security", "RLS enabled"),
    ]
    for pattern, label in expectations:
        for match in sorted(set(re.findall(pattern, sql, re.I))):
            print(f"  {label:11} {match}")

    bucket = re.search(r"values \(\s*'(createflow-assets)'", sql)
    print(f"  {'bucket':11} {bucket.group(1) if bucket else 'MISSING'}")

    risky = re.findall(r"^\s*(drop\s+(?:table|policy)\s+[^;]*);", sql, re.I | re.M)
    if risky:
        print("\ndestructive statements (must only ever drop objects this app owns):")
        for statement in risky:
            print("  -", statement)

    print("\nresult: migration is valid PostgreSQL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())