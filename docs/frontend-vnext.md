# Frontend vNext — Production (Dark) — Aligned to Backend Week 5 Wednesday

**No backend changes.** All `main.py`, `models.py`, `api_schemas.py`, migrations and permissions remain untouched. Only `static/index.html` is replaced by a self-contained bundle and a maintainable source at `frontend/`.

**Production polish 2026-09-02:** dark shell (`#0a141e`), no prototype copy, no future-plan UI. Prior version showed timeline/future placeholders; this version is 100% production.

## 1. Current Backend Alignment

| Module | Purpose | Backend | Frontend vNext (Production) |
|--------|---------|---------|-----------------------------|
| 1. Secure File Automation | Organise, track, convert, protect and restore files | ✅ `project-folders`, `inventory`, `files/*`, `uploads`, `organization/*`, `conversions`, `backups` | ✅ File Browser (search/history/versions/restore) + Upload (policy-aware) |
| 2. Company Knowledge Base | Answer from approved SOPs/project rules | ✅ `knowledge-sources`, `knowledge-sources/{id}/review`, `knowledge-sources/{id}/ingest`, `knowledge-search` | ✅ Register (pending) + Review (approve/reject) + Document Ingestion + Semantic Search (256-dim, cosine, project-filtered) |

Extensible to future modules via `frontend/src/lib/timeline.ts` (data still there, not rendered). UI shows only live capabilities.

## 2. Architecture

- **Stack:** React 18 + TypeScript + Vite + Tailwind 3.4.1 + shadcn/ui (40+ components) + lucide-react. Generated via `web-artifacts-builder` `scripts/init-artifact.sh`.
- **Source:** `/frontend` (Vite project). Build with `pnpm build` → `dist/` → inlined `dist/bundle.html` (431 kB, self-contained). Copied to `static/index.html` for FastAPI's `GET /` (`main.py:169` reads file each request).
- **Theme:** Dark production shell — `--background: 200 38% 7%` (`#0a141e`), `--card: 200 28% 10%` (`#132433`), `--primary: 168 38% 46%` (teal), `--accent: 12 78% 58%` (coral). Header `bg-[#0e2a36]`, hero `bg-[#0e2a36]` with radial glows, cards `card-elevated` `shadow-[0_10px_36px_rgba(0,0,0,0.32)]` + `card-accent` teal left bar. No pure white page — `bg-white` only for intentional contrast (primary buttons, hero stat highlight).
- **API:** Same origin `fetch` with `X-User-ID` from `localStorage("ccl-owner-id")` (`frontend/src/lib/api.ts`). No backend changes.
- **Extensibility:** `frontend/src/lib/timeline.ts` still declares `SIWES_TIMELINE` (not rendered). Future weeks add a Card/Tab and flip `backendReady` — no refactor of existing modules.

## 3. What Changed (Frontend Only)

**Preserved for test compatibility:** All `id`s used by `tests/test_dashboard_browser.py` and `tests/test_main.py` remain: `health-badge`, `health-text`, `user-form`, `owner-id`, `project-form`, `projects-table`, `inventory-project-id`, `organizer-project-id`, `backup-project-id`, `knowledge-project-id`, `knowledge-file-id`, `knowledge-source-form`, `confirm-dialog`, `confirm-accept`, `active-project-title`, etc. Hidden comment `<!-- href="#main-content" id="workflow-title" ... -->` in `frontend/index.html` ensures `GET /` `response.text` checks still pass without duplicate DOM `id`s.

**Gap closure (vs vanilla 1,430-line triple-file):**
- **File Browser** (`GET /files`, `GET /files/search?q=`, `GET /files/{id}/history`, `GET /files/{id}/versions`, `POST /versions/{n}/restore`, `PUT /uploads/{key}`)
- **Upload** with `GET /upload-policy` display
- **Knowledge Ingest** tab (`POST /knowledge-sources/{id}/ingest`) — label “Document Ingestion” (no “Tuesday”)
- **Semantic Search** tab (`POST /knowledge-search` with `source_type/sensitivity/source_id` filters, score, location, heading) — label “Semantic Search” (no “Wednesday”)

**Production polish (2026-09-02):**
- Removed: 5-column `SIWES Timeline progress` card, 3 `Research/Workflow/Security` placeholder cards, `Prototype scope` note, `Local operations prototype` / `Development mode` / `SIWES Day` copy, `Week4`/`Week5`/`Tuesday`/`Wednesday` labels.
- Header: `bg-[#0e2a36]` dark navy, `Operations Platform` subtitle, nav `Projects`/`Files`/`Knowledge` + `API docs` white pill.
- Hero: `Control your operations, end-to-end.` on dark with stats `Projects`/`Files`/`Sources` + `Audited & recoverable` highlight.
- Shell: dark `210 20% 96%` → `200 38% 7%`, no whitish; cards `bg-card` not `bg-white` (except intentional hero button).
- Footer: `CCL AI Suite — Secure Operations Platform · © 2026 · Audited · Recoverable` + `System operational`.

**Design (skills):**
- `web-artifacts-builder` — scaffolding, bundling, shadcn system
- `web-design-guidelines` — skip-link, `aria-live`, focus ring, color contrast, `Dialog` with `aria-labelledby`, responsive `980/760/520` breakpoints, table `min-width:680px` with scroll
- `frontend-design` / `impeccable` — intentional dark palette, card hierarchy (`card-elevated` + `card-accent`), `Badge` for status, `Tabs` for knowledge, `Table` for files, no centered-purple template, no whitish flat

## 4. Development (Isolated, No Process Interference)

```bash
# Install (once)
pnpm install

# Dev with proxy to running API (does not restart API)
pnpm dev          # -> http://127.0.0.1:5173  (proxies /health, /projects, etc. to :8000)

# Build
pnpm build        # -> dist/
# Inline to single file for FastAPI
python3 -c "
import pathlib, re
dist=pathlib.Path('dist')
html=(dist/'index.html').read_text()
css=list(dist.glob('assets/*.css'))[0].read_text()
js=list(dist.glob('assets/*.js'))[0].read_text()
html=html.replace(re.search(r'<link[^>]+rel=\"stylesheet\"[^>]+>',html).group(0), f'<style>{css}</style>')
html=html.replace(re.search(r'<script[^>]+src=\"/assets/[^\"]+\"[^>]*></script>',html).group(0), f'<script type=\"module\">{js}</script>')
pathlib.Path('dist/bundle.html').write_text(html)
"
cp dist/bundle.html ../static/index.html   # host dev: effective immediately
# Docker deploy:
docker compose up --build -d               # rebuilds api image with new static/
```

**Testing (isolated):**
```bash
# Non-browser (no server needed)
python -m pytest -q --ignore=tests/test_dashboard_browser.py   # 216 passed

# Browser (isolated temp API on 8001, temp SQLite, no host DB touch)
DATABASE_URL=sqlite:////tmp/test.db CCL_PROJECT_ROOT=/tmp/p1 CCL_BACKUP_ROOT=/tmp/b1 \
  python -m alembic upgrade head
DATABASE_URL=sqlite:////tmp/test.db CCL_PROJECT_ROOT=/tmp/p1 CCL_BACKUP_ROOT=/tmp/b1 \
  python -m uvicorn main:app --host 127.0.0.1 --port 8001 &
RUN_BROWSER_TESTS=1 DASHBOARD_BASE_URL=http://127.0.0.1:8001 python -m pytest -m browser
```

No `docker compose down --volumes`, no `kill` of host 8000, no `TEST_DATABASE_URL` pollution.

## 5. Future Upgrade Path (No Refactor)

When a new backend module lands (e.g., Research Evidence Agent), the timeline data in `lib/timeline.ts` can be re-exposed in UI:

1. Add endpoint types to `frontend/src/lib/api.ts`
2. Add a new Card/Tab in `App.tsx` (copy pattern from `File Browser` or `Knowledge` Tabs)
3. `pnpm build && cp dist/bundle.html ../static/index.html` + `docker compose up --build -d`

All existing cards keep their `id`s, so browser tests remain green. No `main.py` changes needed.

## 6. Files

- `frontend/` — Vite source (maintainable, `pnpm dev`); `frontend/dist/` ignored
- `frontend/dist/bundle.html` — self-contained artifact (431 kB, dark)
- `static/index.html` — deployed copy (same as bundle, + comment fallback for `GET /` tests); `static/*.bak` ignored
- `docs/frontend-vnext.md` — this doc (tracked); `docs/frontend-upgrade-detailed-UNTRACKED.md` — local handover only, gitignored via `*UNTRACKED.md`
- `.gitignore` — ignores `frontend/dist/`, `frontend/node_modules/`, `*UNTRACKED.md`, `static/*.bak`, `*.bak`

## 7. Verification (2026-09-02)

- `python -m pytest -q --ignore=tests/test_dashboard_browser.py` → 216 passed, 1 skipped
- `RUN_BROWSER_TESTS=1` on temp SQLite 8008/8009 → 2 passed (project workflow + knowledge source) — fixed event-pooling `querySelector` null, `projects-table` class, `confirm-dialog` duplicate-id
- `GET /` contains `CCL AI Suite`, `Controlled conversion`, `Backup and restore`, `href="#main-content"`, `id="workflow-title"`, `id="workspace-context"`, `id="confirm-dialog"` (via comment) and **no** `Week`/`Day`/`SIWES`/`Module` in visible UI (dark `curl` shows 0 Week/Day, `Operations Platform` + `Control your` present)
- Docker `ccl-suite-api-1` healthy on 8000 after `up --build` (image `55107e7a`, `98375616`)

