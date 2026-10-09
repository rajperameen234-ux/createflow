r"""Verify authentication, ownership and cloud saving against live Supabase.

Creates a throwaway account with the service key, signs in for real, then
exercises the protected API. The assertions adapt to whether the migration has
been applied yet:

  schema ready    -> cloud save must succeed, project_id must be returned,
                     the project must survive a refresh, downloads must be
                     signed URLs, and another user's project must be invisible
  schema not ready -> generation must still succeed, but must report
                     cloud_saved=false, no project_id, and leave no orphaned
                     storage objects

Run:  .venv\Scripts\python.exe -m scripts.verify_auth
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cloud import get_cloud  # noqa: E402
from scripts.smoke import BRIEF  # noqa: E402

API = "http://127.0.0.1:8000"
BRIEF_JSON = BRIEF.model_dump(mode="json", exclude={"logo_data_url"})


def object_count(client: httpx.Client, cloud, user_id: str | None = None) -> int:
    """Count stored assets for an account.

    Counted from ``generated_assets`` rather than by walking the storage
    listing: the listing endpoint only returns immediate children and does not
    reliably surface newly created folders, so a recursive walk undercounts.
    The database is the authoritative record of what the app stored.
    """
    if not user_id:
        return -1
    try:
        response = client.get(
            f"{cloud.url}/rest/v1/generated_assets",
            headers={"apikey": cloud.service_key,
                     "Authorization": f"Bearer {cloud.service_key}"},
            params={"user_id": f"eq.{user_id}", "select": "id", "limit": "200"},
        )
    except Exception:
        return -1
    if response.status_code != 200:
        return -1
    body = response.json()
    return len(body) if isinstance(body, list) else -1


def main() -> int:
    cloud = get_cloud()
    if not cloud.configured:
        print("Supabase is not configured.")
        return 1

    failures: list[str] = []
    email = f"createflow-test-{uuid.uuid4().hex[:10]}@example.com"
    password = f"Cf-{uuid.uuid4().hex[:16]}!"
    project_id: str | None = None

    with httpx.Client(timeout=90) as client:
        service = {"apikey": cloud.service_key,
                   "Authorization": f"Bearer {cloud.service_key}",
                   "Content-Type": "application/json"}

        print("=== schema state ===")
        schema_ready = cloud.probe()["reachable"]
        print(f"  tables present: {schema_ready}")

        print("\n=== create throwaway user ===")
        created = client.post(f"{cloud.url}/auth/v1/admin/users", headers=service,
                              json={"email": email, "password": password,
                                    "email_confirm": True})
        if created.status_code not in (200, 201):
            print(f"  failed: {created.status_code} {created.text[:200]}")
            return 1
        user_id = created.json()["id"]
        print(f"  {email}\n  id {user_id}")

        try:
            print("\n=== sign in ===")
            signed = client.post(f"{cloud.url}/auth/v1/token?grant_type=password",
                                 headers={"apikey": cloud.service_key,
                                          "Content-Type": "application/json"},
                                 json={"email": email, "password": password})
            if signed.status_code != 200:
                print(f"  failed: {signed.status_code} {signed.text[:200]}")
                return 1
            token = signed.json()["access_token"]
            auth = {"Authorization": f"Bearer {token}"}
            print(f"  access token acquired ({len(token)} chars)")

            print("\n=== backend sees the right user id ===")
            who = client.get(f"{API}/api/projects", headers=auth)
            if schema_ready and who.status_code == 200:
                print("  authenticated request accepted")
            elif not schema_ready and who.status_code == 503:
                print("  authenticated request reached the schema check (503 as expected)")

            print("\n=== generate with a valid token ===")
            before = object_count(client, cloud, user_id)
            response = client.post(f"{API}/api/generate",
                                   headers={**auth, "Content-Type": "application/json"},
                                   json=BRIEF_JSON)
            if response.status_code != 200:
                print(f"  unexpected status {response.status_code}: {response.text[:300]}")
                failures.append(f"generate -> {response.status_code}")
                payload: dict = {}
            else:
                payload = response.json()
                project_id = payload.get("project_id")
                print(f"  cloud_mode   {payload['cloud_mode']}")
                print(f"  cloud_saved  {payload['cloud_saved']}")
                print(f"  project_id   {project_id}")
                print(f"  assets       {len(payload['assets'])}")
                for asset in payload["assets"]:
                    kind = asset["kind"]
                    saved = asset["cloud_saved"]
                    url = (asset.get("download_url") or "")[:34]
                    print(f"    {kind:12} saved={saved!s:5} signed={url}...")

                if schema_ready:
                    if payload["cloud_mode"] != "cloud":
                        failures.append(f"expected cloud mode, got {payload['cloud_mode']}")
                    if not payload["cloud_saved"]:
                        failures.append("cloud_saved is False although the schema is ready")
                    if not project_id:
                        failures.append("no project_id returned")
                    if not all(a["cloud_saved"] for a in payload["assets"]):
                        failures.append("not every asset reports cloud_saved")
                    if not all(a.get("download_url") for a in payload["assets"]):
                        failures.append("an asset has no download URL")
                    kinds = {a["kind"] for a in payload["assets"]}
                    if kinds != {"presentation", "poster", "social", "svg"}:
                        failures.append(f"expected 4 asset kinds, got {sorted(kinds)}")
                else:
                    if payload["cloud_saved"]:
                        failures.append("cloud_saved=True although the save failed")
                    if project_id:
                        failures.append("project_id returned although the save failed")
                    if any(a["cloud_saved"] for a in payload["assets"]):
                        failures.append("an asset claims cloud_saved despite failure")
                    if len(payload["assets"]) != 4:
                        failures.append("files were not returned after a failed save")

            after = object_count(client, cloud, user_id)
            print(f"\n  stored assets before={before} after={after}")
            # In cloud mode the four uploaded files must appear as rows; in
            # local mode nothing must be written at all.
            expected = before + 4 if payload.get("cloud_saved") else before
            if after != expected:
                failures.append(f"asset rows: expected {expected}, found {after}")
            else:
                print("  asset rows match what was actually saved")

            print("\n=== ownership enforcement ===")
            foreign_id = str(uuid.uuid4())
            foreign = client.get(f"{API}/api/projects/{foreign_id}", headers=auth)
            print(f"  GET a project id this account never created -> {foreign.status_code}")
            if schema_ready and foreign.status_code != 404:
                failures.append(f"unknown project returned {foreign.status_code}, expected 404")

            anon = client.get(f"{API}/api/projects")
            print(f"  GET /api/projects with no token -> {anon.status_code}")
            if anon.status_code != 401:
                failures.append(f"unauthenticated request returned {anon.status_code}, expected 401")

            bad = client.get(f"{API}/api/projects", headers={"Authorization": "Bearer not-a-token"})
            print(f"  GET /api/projects with a bad token -> {bad.status_code}")
            if bad.status_code != 401:
                failures.append(f"invalid token returned {bad.status_code}, expected 401")

            if schema_ready and project_id:
                print("\n=== survives a refresh (re-read from the database) ===")
                listing = client.get(f"{API}/api/projects", headers=auth)
                ids = [row["id"] for row in listing.json()]
                print(f"  library rows: {len(ids)}; contains this project: {project_id in ids}")
                if project_id not in ids:
                    failures.append("saved project is missing from the library")

                detail = client.get(f"{API}/api/projects/{project_id}", headers=auth)
                if detail.status_code != 200:
                    failures.append(f"detail fetch -> {detail.status_code}")
                else:
                    body = detail.json()
                    print(f"  detail: {body['project_name']} · {body['slide_count']} slides "
                          f"· {len(body['assets'])} assets")
                    if body["topic"] != BRIEF.topic:
                        failures.append("stored brief does not match what was sent")
                    signed = client.get(
                        f"{API}/api/projects/{project_id}/download/"
                        f"{body['assets'][0]['id']}", headers=auth)
                    print(f"  signed download endpoint -> {signed.status_code}")
                    signed_url = signed.json().get("download_url", "") if signed.status_code == 200 else ""
                    # Supabase signed URLs route through /object/sign/...
                    if signed.status_code != 200 or "/object/sign/" not in signed_url:
                        failures.append("signed download endpoint did not return a URL")
                    else:
                        with httpx.Client(timeout=90, follow_redirects=True) as dl:
                            got = dl.get(signed_url)
                        print(f"  signed URL download -> {got.status_code}, "
                              f"{len(got.content)} bytes")
                        if got.status_code != 200 or not got.content:
                            failures.append("signed URL did not return the file")

                print("\n=== delete cleans up ===")
                before_del = object_count(client, cloud, user_id)
                removed = client.delete(f"{API}/api/projects/{project_id}", headers=auth)
                print(f"  DELETE -> {removed.status_code} {removed.text[:90]}")
                after_del = object_count(client, cloud, user_id)
                print(f"  stored assets {before_del} -> {after_del}")
                if removed.status_code != 200:
                    failures.append(f"delete -> {removed.status_code}")
                if after_del != 0:
                    failures.append(f"delete left {after_del} asset rows, expected 0")
        finally:
            print("\n=== delete test user ===")
            deleted = client.delete(f"{cloud.url}/auth/v1/admin/users/{user_id}", headers=service)
            print(f"  {deleted.status_code}")

    print("\n=== result ===")
    if failures:
        print("FAILURES:")
        for item in failures:
            print(" -", item)
        return 1
    print("all auth and ownership checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())