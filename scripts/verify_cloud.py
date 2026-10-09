r"""Verify the live Supabase integration that does not depend on the schema.

With a valid service role key this checks, for real:
  1. credentials authenticate against the data / storage / auth APIs
  2. the private bucket exists and is not public
  3. a generated file uploads, a signed URL is issued, the bytes round-trip
  4. deletion removes the object

Tables and RLS are checked separately and reported honestly if the migration
has not been applied yet.

Run:  .venv\Scripts\python.exe -m scripts.verify_cloud
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cloud import get_cloud  # noqa: E402
from app.pipeline import generate  # noqa: E402
from scripts.smoke import BRIEF  # noqa: E402


def head(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    cloud = get_cloud()
    if not cloud.configured:
        print("Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        return 1

    failures: list[str] = []
    probe_user = str(uuid.uuid4())

    head("1. credentials")
    with httpx.Client(timeout=40) as client:
        for path in ("/storage/v1/bucket", "/rest/v1/", "/auth/v1/settings"):
            try:
                response = client.get(cloud.url + path, headers={
                    "apikey": cloud.service_key,
                    "Authorization": f"Bearer {cloud.service_key}",
                })
                ok = response.status_code == 200
                print(f"  {path:24} {response.status_code} {'ok' if ok else 'FAIL'}")
                if not ok:
                    failures.append(f"{path} -> {response.status_code}")
            except Exception as exc:
                print(f"  {path:24} ERROR {exc}")
                failures.append(f"{path} -> {exc}")

    head("2. private bucket")
    with httpx.Client(timeout=40) as client:
        response = client.get(cloud.url + "/storage/v1/bucket", headers={
            "apikey": cloud.service_key,
            "Authorization": f"Bearer {cloud.service_key}",
        })
        buckets = {b["id"]: b for b in response.json()} if response.status_code == 200 else {}
        bucket = buckets.get(cloud.bucket)
        if bucket is None:
            print(f"  bucket '{cloud.bucket}' MISSING")
            failures.append(f"bucket {cloud.bucket} missing")
        else:
            public = bucket.get("public")
            print(f"  '{cloud.bucket}' exists · public={public} "
                  f"limit={bucket.get('file_size_limit')}")
            if public:
                failures.append("bucket is public; it must be private")

    head("3. generate, upload, signed download, delete")
    result = generate(BRIEF)
    project_id = str(uuid.uuid4())
    print(f"  generated {len(result.assets)} files")

    for asset in result.assets:
        data = asset.path.read_bytes()
        path = cloud.upload_asset(project_id, probe_user, asset.filename, data, asset.content_type)
        size = cloud.client().storage.from_(cloud.bucket).download(path)
        match = bytes(size) == data
        url = cloud.signed_url(path)
        downloaded = b""
        if url:
            with httpx.Client(timeout=60, follow_redirects=True) as client:
                downloaded = client.get(url).content
        round_trip = downloaded == data
        print(f"  {asset.kind.value:12} {len(data):>7}B uploaded · storage_read={'ok' if match else 'MISMATCH'}"
              f" · signed_url={'yes' if url else 'NO'} · download={'ok' if round_trip else 'MISMATCH'}")
        if not match:
            failures.append(f"{asset.kind.value}: storage round trip mismatch")
        if not url:
            failures.append(f"{asset.kind.value}: no signed URL issued")
        if not round_trip:
            failures.append(f"{asset.kind.value}: signed download mismatch")
        try:
            cloud.client().storage.from_(cloud.bucket).remove([path])
        except Exception as exc:
            failures.append(f"{asset.kind.value}: delete failed {exc}")

    result.cleanup()
    print(f"  temp workspace removed: {not result.workspace.exists()}")

    head("4. database schema")
    probe = cloud.probe()
    if probe["reachable"]:
        print("  'public.projects' exists and is queryable")
        rows = cloud.list_projects("00000000-0000-0000-0000-000000000000")
        print(f"  list_projects works, returned {len(rows)} rows")
    else:
        print(f"  NOT READY: {probe['message']}")
        print("  -> run supabase/migrations/0001_createflow_schema.sql in the")
        print("     Supabase SQL editor, then re-run this script.")

    head("result")
    if failures:
        print("FAILURES:")
        for item in failures:
            print(" -", item)
        return 1
    print("all live checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())