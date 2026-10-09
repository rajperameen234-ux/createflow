# CreateFlow

Turn one project brief into a coordinated creative package: an **editable
PowerPoint deck**, a **print-ready poster**, a **square social graphic** and a
**vector brand mark** — all sharing one visual identity.

The design system is the core idea. A brief resolves to a single
`DesignSystem` (palette, type pairing, motif, spacing scale), and every
renderer consumes that same object. The poster does not look like a different
brand from the deck because they are literally drawn from the same tokens.

```
frontend/   React + TypeScript + Vite + Tailwind   (dev server :5173)
backend/    FastAPI + python-pptx + Pillow + SVG   (API on :8000)
supabase/   SQL migrations: tables, indexes, RLS, private storage bucket
```

---

## Quick start (Windows PowerShell)

Run these from the repository root (`C:\Code\CreateFlow`).

### 1. Backend

```powershell
cd backend
py -3.12 -m venv .venv            # any Python 3.11+ works
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env        # optional: only needed for cloud features
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

If `py -3.12` is not available, check what you have with `py --list` and use
that version, e.g. `py -3.14 -m venv .venv`.

### 2. Frontend (second terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api` to
<http://127.0.0.1:8000>.

### 3. Verify

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

---

## Optional: one-command start

```powershell
.\scripts\start-dev.ps1
```

---

## What gets generated

| Output | Format | Size |
| --- | --- | --- |
| Presentation | `.pptx` (native text, autoshapes, connectors, embedded charts, speaker notes) | 16:9, 13.333×7.5 in |
| Poster | `.png` | 2480×3508 (A2 @ 300 dpi) |
| Social graphic | `.png` | 1440×1440 (1:1) |
| Brand mark | `.svg` | 1080×1080, fully vector |

Nothing is a flattened screenshot. Open the `.pptx` in PowerPoint, Keynote or
Google Slides and every headline, card, connector and chart is editable.

### Deck structure

Ten layouts, chosen per slide by the narrative engine:

`hero` · `two_column` · `quote_led` · `image_led` · `framework` ·
`numbered_process` · `metrics` (native chart) · `comparison` · `timeline` ·
`summary`

Every slide carries speaker notes. The deck opens on a title slide and closes
on a call to action; the middle adapts to the requested length (5–16 slides).

### Content honesty

Copy is derived from the brief's own words. CreateFlow does not invent
statistics, studies or testimonials. Where a chart needs numbers, the values
are a deterministic planning model and the slide itself is labelled
**"Illustrative data — replace with your own figures once measured."**

### Style presets

Editorial Luxury · Modern Minimal · Bold Creative · Corporate Premium ·
Dark Cinematic · Playful Colorful

Each preset defines its own palette, heading/body type pairing, corner radius,
rule weight and background motif. Picking a preset in the UI sets the default
colours, which remain individually editable.

## Interface

The UI is built on a small, deliberate system rather than a component dump:

- **Palette** — neutral graphite surfaces (`base-1000` → `base-700`) separated by
  hairlines, not glow. Exactly one accent (`brass`) carries meaning: primary
  action, active state, focus. Nothing else is coloured.
- **Type** — Inter for UI, JetBrains Mono for metadata and file sizes, with
  tabular numerals so columns of numbers align. A 4-step scale from `2xs` to
  `3xl`.
- **Geometry** — 5/7/8/10px radii, 4px spacing grid, one hairline token that
  intensifies on hover and focus.
- **Motion** — 150–260ms with a single easing curve, and fully disabled under
  `prefers-reduced-motion`.

### Real slide previews

PowerPoint has no browser renderer and this machine has no PowerPoint or
LibreOffice. Rather than draw a mock-up, `app/slide_preview.py` renders each
slide with Pillow from the **same outline object and the same design system**
the `.pptx` is built from. The results studio therefore shows real generated
content — correct titles, bullets, charts, colours and footers — and the
`.pptx` remains the editable deliverable.

Previews are rendered on demand, memoised per brief, and require an
authenticated identity whenever Supabase is configured, exactly like every
other asset endpoint.

---

## API

Interactive docs at <http://127.0.0.1:8000/docs>.

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/health` | public | Status, cloud state, fonts, capabilities |
| `GET` | `/api/presets` | public | Style presets and layouts |
| `POST` | `/api/preview` | public | Live theme + outline, writes no files |
| `POST` | `/api/generate` | optional | Generate the package |
| `POST` | `/api/slides/preview?index=N` | when cloud on | One real slide rendered as PNG |
| `POST` | `/api/slides/sheet` | when cloud on | Contact sheet of every slide (project thumbnail) |
| `GET` | `/api/download/{token}/{kind}` | see below | Serve a temporary file |
| `GET` | `/api/projects` | **required** | Project library |
| `GET` | `/api/projects/{id}` | **required** | Project detail + assets |
| `POST` | `/api/projects/{id}/regenerate` | **required** | Rebuild from the saved brief |
| `DELETE` | `/api/projects/{id}` | **required** | Delete row + storage objects |
| `GET` | `/api/projects/{id}/download/{asset_id}` | **required** | Short-lived signed URL |

Protected routes require `Authorization: Bearer <supabase access token>`, and
every query is scoped by `user_id`. When Supabase is not configured they return
`503` with an explicit message rather than pretending to be authenticated.

### Cloud modes

The API always reports the truth about where files went:

| `cloud_mode` | Meaning |
| --- | --- |
| `cloud` | Uploaded to private storage, rows written, signed URLs issued |
| `local-development` | Generated locally; temporary download for one hour, nothing persisted |
| `cloud-error` | Generation succeeded, the save failed, nothing marked as saved |

`cloud_saved` is `true` **only** after a real upload and database write
succeeded. On failure the partially-created project is rolled back.

---

## Supabase setup (optional but required for persistence)

Create a free project at <https://supabase.com>.

### 1. Run the migration

In the Supabase SQL editor, paste and run
`supabase/migrations/0001_createflow_schema.sql`. It creates:

- `profiles` — optional display mirror of `auth.users`
- `projects` — one row per brief, with the full brief stored as `brief_json`
- `generated_assets` — one row per file, with `storage_path` and checksum
- indexes on `(user_id, created_at desc)`, `(project_id)`, `(user_id)`
- RLS policies on both tables restricting every row to `auth.uid()`
- a **private** `createflow-assets` bucket (25 MB limit, MIME allow-list) plus
  `storage.objects` policies keyed on the first path segment (`<user_id>/...`)

### 2. Backend environment

```powershell
cd backend
Copy-Item .env.example .env
```

Fill in:

```dotenv
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<secret-key>
SUPABASE_STORAGE_BUCKET=createflow-assets
```

Confirm the key works without printing it:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_cloud
```

That reports `credentials ... ok`, the bucket state, and a full
upload → signed URL → download → delete round trip.

### 3. Frontend environment

```powershell
cd frontend
Copy-Item .env.example .env
```

```dotenv
VITE_SUPABASE_URL=https://<project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<publishable-or-anon-key>
```

Restart both dev servers afterwards.

> If the SQL Editor is unavailable to you, supply the **database password**
> (Settings → Database) or a Supabase personal access token instead, and the
> migration can be applied programmatically.

### Security notes

- The **service role key never leaves the backend**. It is not in any frontend
  bundle, not logged, and not returned by any endpoint.
- The frontend only ever holds the **anon key**, which is designed to be public
  and is constrained by RLS.
- Ownership is enforced twice: RLS for direct client access, and explicit
  `user_id` filters in the API before any read, update, delete or download.
- Uploads are validated by MIME type, extension, decoded with Pillow (SVG logos
  are additionally screened for scripts) and capped at 4 MB. Request bodies are
  capped at 8 MB.
- Downloads use signed URLs with a 15-minute TTL.

---

## Verification

Five backend scripts, no credentials needed for the first three:

```powershell
cd backend

# Generate a package; report file sizes, slide inventory, image validity
.\.venv\Scripts\python.exe -m scripts.smoke

# Structural deck check: shapes inside the canvas, notes present, real charts
.\.venv\Scripts\python.exe -m scripts.validate_deck

# Prove the SQL migration is valid, idempotent and non-destructive
.\.venv\Scripts\python.exe -m scripts.preflight_migration

# Confirm the API's insert payloads match the migration's columns
.\.venv\Scripts\python.exe -m scripts.check_schema_contract

# Live cloud checks (needs SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY, backend running)
.\.venv\Scripts\python.exe -m scripts.verify_cloud   # storage round trip
.\.venv\Scripts\python.exe -m scripts.verify_auth    # auth, ownership, saving
.\.venv\Scripts\python.exe -m scripts.verify_studio  # generation + slide previews
```

`verify_auth` creates a throwaway account, exercises the protected API and
deletes the account afterwards. Once the migration is applied it asserts that
`cloud_saved` is true, a `project_id` comes back, all four assets are uploaded,
the project survives a re-read, signed downloads work, a foreign `project_id`
returns 404, and deletion removes the storage objects.

Frontend checks:

```powershell
cd frontend
npm run typecheck
npm run build
```

---

## Notes on performance

- No local language models, no GPU, no paid APIs. The narrative engine is
  deterministic template logic over the user's brief.
- A full 8-slide package renders in roughly 2–4 seconds on a laptop.
- Memory stays flat: Pillow images are written and released per asset, and the
  pipeline holds one generation workspace at a time.
- Temporary files live in `backend/.tmp/<uuid>/`, are deleted immediately after
  a successful upload, and orphaned workspaces are purged on startup and after
  an hour.

## Known limitations

- PowerPoint has no browser renderer, so the deck preview in the results
  workspace shows asset metadata and a download action rather than slide pixels.
  Slides render when the file is opened.
- Direct in-app slide editing is not implemented. Editing happens by revising
  the brief and regenerating, which rebuilds all four files consistently.
- Presentation-type differences are presentational: report mode tightens figure
  labelling, it does not change the analysis.
- Cloud saving, the project library and signed downloads are unverified in this
  build because no Supabase project was configured.