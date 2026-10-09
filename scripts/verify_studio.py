r"""Verify the redesigned studio surface against the live backend.

Signs a throwaway user in, generates a real package, then exercises the slide
preview and contact sheet endpoints the results studio depends on.

Run:  .venv\Scripts\python.exe -m scripts.verify_studio
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cloud import get_cloud  # noqa: E402
from scripts.smoke import BRIEF  # noqa: E402

API = "http://127.0.0.1:8000"


def main() -> int:
    cloud = get_cloud()
    service = {
        "apikey": cloud.service_key,
        "Authorization": f"Bearer {cloud.service_key}",
        "Content-Type": "application/json",
    }
    body = BRIEF.model_dump(mode="json", exclude={"logo_data_url"})
    failures: list[str] = []

    email = f"studio-{uuid.uuid4().hex[:8]}@example.com"
    password = f"St-{uuid.uuid4().hex[:12]}!"

    with httpx.Client(timeout=180) as client:
        user = client.post(
            f"{cloud.url}/auth/v1/admin/users",
            headers=service,
            json={"email": email, "password": password, "email_confirm": True},
        ).json()
        token = client.post(
            f"{cloud.url}/auth/v1/token?grant_type=password",
            headers={"apikey": cloud.service_key, "Content-Type": "application/json"},
            json={"email": email, "password": password},
        ).json()["access_token"]
        auth = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        print(f"signed in as {email}\n")

        print("=== generate ===")
        started = time.perf_counter()
        response = client.post(f"{API}/api/generate", headers=auth, json=body)
        elapsed = time.perf_counter() - started
        if response.status_code != 200:
            print(f"  FAILED {response.status_code}: {response.text[:200]}")
            return 1
        data = response.json()
        print(f"  {elapsed:.1f}s · mode={data['cloud_mode']} · saved={data['cloud_saved']}"
              f" · slides={data['slide_count']} · files={len(data['assets'])}")
        print(f"  project_id: {data['project_id']}")
        if not data["cloud_saved"]:
            failures.append("cloud_saved is False")
        for asset in data["assets"]:
            print(f"    {asset['kind']:12} saved={asset['cloud_saved']}"
                  f" signed={'yes' if asset['download_url'] else 'NO'}")
        if not all(a["cloud_saved"] and a["download_url"] for a in data["assets"]):
            failures.append("not every asset is cloud-saved with a signed URL")

        print("\n=== slide previews (what the studio shows) ===")
        for index in (0, 3, data["slide_count"] - 1):
            started = time.perf_counter()
            preview = client.post(f"{API}/api/slides/preview?index={index}",
                                  headers=auth, json=body)
            took = time.perf_counter() - started
            content_type = preview.headers.get("content-type", "")
            print(f"  slide {index + 1:>2}  {preview.status_code}  {content_type}"
                  f"  {len(preview.content) // 1024} KB  {took:.2f}s")
            if preview.status_code != 200 or "image/png" not in content_type:
                failures.append(f"slide {index + 1} preview failed")
            elif preview.content[:8] != b"\x89PNG\r\n\x1a\n":
                failures.append(f"slide {index + 1} is not a PNG")

        print("\n=== contact sheet (project thumbnail) ===")
        started = time.perf_counter()
        sheet = client.post(f"{API}/api/slides/sheet", headers=auth, json=body)
        took = time.perf_counter() - started
        print(f"  {sheet.status_code}  {len(sheet.content) // 1024} KB  {took:.2f}s")
        if sheet.status_code != 200:
            failures.append("contact sheet failed")

        print("\n=== access control ===")
        anon = client.post(f"{API}/api/slides/preview?index=0", json=body)
        print(f"  no token          -> {anon.status_code}")
        if anon.status_code != 401:
            failures.append(f"unauthenticated preview returned {anon.status_code}")
        bad = client.post(f"{API}/api/slides/preview?index=0",
                          headers={"Authorization": "Bearer nope"}, json=body)
        print(f"  invalid token     -> {bad.status_code}")
        if bad.status_code != 401:
            failures.append(f"invalid token returned {bad.status_code}")

        print("\n=== cleanup ===")
        listing = client.get(f"{API}/api/projects", headers=auth)
        rows = listing.json()
        for row in rows:
            removed = client.delete(f"{API}/api/projects/{row['id']}", headers=auth)
            print(f"  deleted {row['project_id'] if 'project_id' in row else row['id']}"
                  f" -> {removed.status_code}")
        client.delete(f"{cloud.url}/auth/v1/admin/users/{user['id']}", headers=service)
        print("  test user removed")

    print("\n=== result ===")
    if failures:
        print("FAILURES:")
        for item in failures:
            print(" -", item)
        return 1
    print("studio surface verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())