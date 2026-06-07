# Project Context

## Overview

NovelScripter is an AI-assisted novel-to-screenplay workspace. It converts multi-chapter novel text into editable screenplay data with chapters, scenes, story bible, source paragraph references, validation feedback, preview, and export flows.

The current repository is a local demo/workbench rather than the full production architecture described in the README.

## Commands

Backend:

```bash
cd apps/api
pip install -r requirements.txt
python -m pytest
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
npm run build
```

Docker development:

```bash
docker compose -f docker-compose.dev.yml up -d
```

Production deployment on the user's server:

```bash
cd /opt/novelscripter/deploy/production
docker compose build
docker compose up -d
```

Quick local start scripts:

```bash
start-local.bat
./start-local.sh
```

Verified local test run on 2026-06-06:

```bash
# Backend
cd apps/api
D:\learn\qiyunniu-2\apps\api\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8017

# Frontend
cd apps/web
cmd /c set NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8017&& npm run dev -- --hostname 127.0.0.1 --port 3000
```

## Architecture

- Frontend: Next.js 14, React 18, TypeScript, Tailwind CSS, Zustand.
- Backend: FastAPI, Pydantic, OpenAI-compatible LLM calls through `httpx`.
- Main frontend entry: `apps/web/src/features/import/ImportPage.tsx` creates a project and starts the pipeline.
- Main frontend API wrapper: `apps/web/src/lib/api.ts`.
- Main frontend state: `apps/web/src/store/project-store.ts`, `pipeline-store.ts`, `model-store.ts`.
- Main backend runtime path for the current frontend: `apps/api/app/routers/projects.py`.
- Backend application entry: `apps/api/app/main.py`.
- The backend registers separate routers for projects, import, pipeline, editing, export, and models.
- `projects.py` keeps project, pipeline, chapter, scene, story bible, validation, and rewrite state in memory for the active demo flow, with local SQLite snapshots used to restore projects after backend restarts.
- Project snapshot persistence lives in `apps/api/app/project_persistence.py`; the default SQLite file is `apps/api/data/novelscripter_projects.sqlite3`, overrideable with `NOVELSCRIPTER_PROJECT_DB`.
- There is also a modular pipeline under `apps/api/app/core/pipeline.py` and `apps/api/app/services/*`, but the current frontend primarily uses the project-scoped endpoints in `projects.py`.

## Conventions

- Do not read or persist `.env` unless explicitly needed and safe; it may contain secrets.
- Do not write API keys, tokens, passwords, private keys, or server credentials into project memory or source files.
- The user may provide OpenAI-compatible model settings for temporary tests. Use them only as transient environment variables or request payloads.
- Project-facing replies should be in Simplified Chinese unless the user asks otherwise.

## Decisions

- The current verified working mental model is the in-memory demo path:
  - `POST /api/v1/projects`
  - `POST /api/v1/projects/{project_id}/pipeline/start`
  - `GET /api/v1/projects/{project_id}/pipeline/status`
  - `GET /api/v1/projects/{project_id}/chapters`
  - `GET /api/v1/projects/{project_id}/story-bible`
  - `GET /api/v1/projects/{project_id}/validation/errors`
- Model configuration for the frontend UI is persisted in browser localStorage by `model-store.ts`, not written to backend config files.
- On 2026-06-06, the active demo path was repaired and verified against a user-provided OpenAI-compatible `gpt-5.5` endpoint without persisting the key:
  - `projects.py::_call_llm` supports streamed `chat/completions` responses.
  - `POST /api/v1/projects` accepts both JSON and multipart form uploads.
  - Project-scoped screenplay, story bible, chapter patch, scene patch/delete, element rewrite/diff, export, and export download endpoints are available under `/api/v1/projects/{project_id}`.
  - Element generation uses bounded concurrency to keep long runs stable.
  - Scene, character, and location edits synchronize into the in-memory screenplay data used by preview, validation, and export.
  - `models.py` test connection performs a real short streamed chat completion check instead of only checking `/models`.
- On 2026-06-06, the active demo pipeline performance was optimized in `apps/api/app/routers/projects.py`:
  - Chapter understanding runs with bounded concurrency, default `NOVELSCRIPTER_CHAPTER_CONCURRENCY=2`.
  - Scene splitting runs with bounded concurrency, default `NOVELSCRIPTER_SCENE_CONCURRENCY=2`.
  - Element generation runs with bounded concurrency, default `NOVELSCRIPTER_ELEMENT_CONCURRENCY=3`.
  - Element prompts now generate a compact editable first draft, default `NOVELSCRIPTER_FAST_ELEMENT_TARGET=10`.
  - LLM stages use capped `max_tokens` to avoid upstream quota pre-charge failures: `NOVELSCRIPTER_CHAPTER_MAX_TOKENS=900`, `NOVELSCRIPTER_SCENE_MAX_TOKENS=1000`, `NOVELSCRIPTER_ELEMENT_MAX_TOKENS=900`, `NOVELSCRIPTER_REWRITE_MAX_TOKENS=600`.
  - `_call_llm` retries once on interrupted streamed responses such as incomplete chunked reads.
  - A 3-chapter test sample completed in 151.5 seconds with 14 scenes, 205 elements, 8 characters, 11 locations, 0 validation errors, and a working YAML export.
- On 2026-06-06, a `HTTP 403 insufficient_user_quota` regression during `chapter_understanding` was diagnosed as the OpenAI-compatible gateway rejecting requests during quota pre-charge because the previous `max_tokens=4000` cap made the estimated charge exceed the remaining balance. The fix above was verified with temporary request-payload model settings only:
  - 2-chapter smoke project completed in about 105 seconds: 8 scenes, 101 elements, 0 validation errors.
  - 1-chapter smoke project completed in about 50 seconds: 2 scenes, 24 elements, 11/11 dialogue elements retained `character_id`, 0 validation errors.
  - Do not record the user-provided API key in source or memory.
- On 2026-06-06, `apps/web/src/store/pipeline-store.ts` was updated so polling stops when `/pipeline/status` returns 404. This prevents repeated logs after the in-memory backend restarts and old browser tabs keep polling project IDs that no longer exist.
- A full generated demo project was verified on 2026-06-06 with 3 chapters, 7 scenes, 325 screenplay elements, and 0 validation issues.
- Project-scoped exports were verified on 2026-06-06 for `yaml`, `json`, `markdown`, `fountain`, and `zip`, including download endpoints.
- On 2026-06-06, the previously observed UI/runtime issues were fixed and re-verified:
  - `/favicon.ico` is served from `apps/web/public/favicon.ico` and returns 200 in the browser.
  - Direct editor URLs restore pipeline status from `/pipeline/status`, so completed projects show overall progress 100% instead of 0%.
  - Element rewrite output is cleaned server-side by `projects.py::_clean_rewrite_output`, removing common JSON/code-fence/string wrappers before saving.
  - Textarea layout in the scene editor and story bible editor is explicit and responsive:
    - `apps/web/src/app/globals.css` gives `.textarea-field` `width: 100%` and `min-width: 0`.
    - `SceneEditor.tsx` shows "戏剧目的" and "冲突" in a one-column mobile / two-column desktop grid.
    - `StoryBibleTable.tsx` shows character "描述", "目标", and "性格" in a one-column mobile / three-column desktop grid.
    - Browser verification passed; temporary screenshots from this QA run were later cleaned.
  - Browser verification after the fix showed no runtime errors, no 4xx/5xx network failures, and `npm run build` passed.
- On 2026-06-07, the editor left sidebar was updated in `apps/web/src/components/AppShell.tsx` and `apps/web/src/app/globals.css`:
  - The import button remains fixed at the top.
  - The internal left-sidebar sections `处理进度`, `章节结构`, and `原文段落` are vertically resizable with two horizontal drag handles.
  - Each section scrolls independently and has a minimum height, so one section can be expanded without removing the others.
  - The default ratio favors chapter browsing: progress 30%, chapter structure 42%, source paragraphs 28%.
  - Adjusted ratios are persisted in browser localStorage under `novelscripter_left_panel_layout_v1`.
  - Double-clicking a divider resets the sidebar to the default ratio.
  - `npm run build` passed and a clean browser session showed no runtime errors. Temporary QA screenshots were later cleaned.
- On 2026-06-07, the export dialog format cards were aligned in `apps/web/src/components/ExportDialog.tsx`:
  - Each export format option uses a fixed icon column and a left-aligned text column, so YAML, JSON, Markdown, Fountain, and ZIP labels/descriptions share the same x-axis.
  - Selected state uses a stable 1px border plus outline shadow rather than changing card dimensions.
  - The dialog width/height is responsive, keeping the desktop max width at 520px while avoiding mobile overflow and desktop button clipping.
  - `npm run build` passed and browser checks showed no runtime errors. Temporary QA screenshots were later cleaned.
- On 2026-06-07, chapter preview cards in the left chapter tree were clarified in `apps/web/src/components/ChapterTree.tsx`:
  - Expanded chapters label the inline text box as `章节预览`, making it clear the content is a chapter preview rather than a numbered source paragraph.
  - Preview text is no longer clipped by a fixed `4rem` height. Short previews render fully; longer previews are text-truncated with an explicit expand/collapse control.
  - Collapsing a chapter resets its preview expansion state.
  - `npm run build` passed and browser checks showed no runtime errors. Temporary QA screenshots were later cleaned.

- On 2026-06-07, story bible interaction fixes were completed in `apps/web/src/components/StoryBibleTable.tsx`, `apps/web/src/components/RelationshipGraph.tsx`, and `apps/web/src/app/globals.css`:
  - Duplicate-character merge suggestions now call the project-scoped backend merge endpoint for "merge as A/B"; "do not merge" hides the suggestion and closes the dialog when it was the last suggestion.
  - The timeline tab uses the user's selected B plan: desktop rows render as a horizontal snake sequence such as 1-2-3 then 6-5-4, while mobile remains single-column.
  - The relationship graph now has visible labelled directional edges. If explicit character relationships are missing, edges are inferred from shared timeline appearances.
  - React Flow controls and attribution are hidden. The MiniMap is normally hidden and appears only while the graph canvas is panned, then hides after movement stops.
  - The relationship graph height is resizable from 320px to 920px and resets on divider double-click.
  - Relationship graph node positions, viewport, and height are persisted in browser localStorage under `novelscripter_relationship_graph_layout_v2:{projectId}`, so switching tabs or returning to the graph does not reset custom layout.
  - Verified with `npm run build` and browser checks. Temporary QA screenshots were later cleaned.
- On 2026-06-07, the YAML editor toolbar was updated in `apps/web/src/components/YamlEditor.tsx`:
  - Added a compact `Schema说明` button next to the YAML toolbar actions.
  - Clicking it expands an inline `Schema说明（摘要）` panel that explicitly says the panel is only a common-structure summary and links to the full human doc `docs/SCHEMA.md` plus the machine validator `apps/api/app/schemas/screenplay.schema.json`.
  - The detail section is expanded by default and can be collapsed. It covers top-level structure, each top-level field's type/purpose/key fields, ID examples, common enum values, and reference-consistency rules.
  - The panel has its own vertical scroll area, so the detailed schema guide does not push the YAML editor out of the right panel.
  - The toolbar can wrap in narrow right panels, while long schema paths break safely instead of overflowing.
  - Verified with `npm run build` and browser checks. Temporary QA screenshots were later cleaned.
- On 2026-06-07, `docs/YAML_SCREENPLAY_SCHEMA.md` was added as a plain-language assignment/project document explaining what Schema and YAML Schema mean, how they differ, and why the novel-to-screenplay YAML Schema uses `schema_version`, `project`, `story_bible`, `chapters`, `scenes`, and `metadata`.
- On 2026-06-07, the right editor panel and export flow were updated for full Schema documentation:
  - `apps/web/src/components/AppShell.tsx` removed the right-panel `校验` tab and added a `说明文档` tab. The right tab order is now `YAML`, `剧本预览`, `说明文档`, `生成日志`.
  - `apps/web/src/components/DocumentationPanel.tsx` was added. It has two inner tabs: `YAML Schema` and `Schema 设计原因`, with detailed front-end readable documentation, schema structure, ID rules, enum rules, reference rules, a minimal YAML example, design reasons, and Schema-first workflow notes.
  - `apps/web/src/components/ExportDialog.tsx`, `apps/web/src/lib/api.ts`, and `apps/web/src/lib/types.ts` now support `docs` / `说明文档` export. The docs export hides validation status and ordinary export options because it is project-independent.
  - `apps/api/app/routers/projects.py` now supports project-level `docs` export and global documentation export routes:
    - `POST /api/v1/projects/documentation/export`
    - `GET /api/v1/projects/documentation/export/download`
  - The docs export zip contains `YAML_SCREENPLAY_SCHEMA.md`, `SCHEMA.md`, `screenplay.schema.json`, and `manifest.json`.
  - Static documentation export routes must stay before dynamic `/{project_id}/export` routes in `projects.py` to avoid route collision.
  - `apps/api/app/main.py` reports `docs` in `/api/v1/info` supported formats.
  - Verified with `npm run build`, `python -m py_compile apps\api\app\routers\projects.py apps\api\app\main.py`, API smoke tests, and browser checks. Temporary QA screenshots were later cleaned.
- On 2026-06-07, local SQLite project persistence was added for the active demo backend:
  - `apps/api/app/project_persistence.py` stores one sanitized JSON snapshot per project in `project_snapshots`.
  - `apps/api/app/main.py` calls `load_persisted_projects_into_memory()` during FastAPI startup, so saved projects are restored into `_projects_store`.
  - `apps/api/app/routers/projects.py` persists snapshots after project creation/update, pipeline start/cancel/completion/failure, stage completion/error, screenplay sync, validation repair, and project deletion.
  - `apps/api/app/routers/editing.py` and `apps/api/app/routers/pipeline.py` also persist snapshots after legacy edit/pipeline routes mutate project data.
  - The default database path is `apps/api/data/novelscripter_projects.sqlite3`; set `NOVELSCRIPTER_PROJECT_DB` to use another path.
  - `_model_config` and keys containing `api_key`, `apikey`, `token`, `secret`, `password`, or `private_key` are stripped before writing snapshots.
  - Verified with a temporary `NOVELSCRIPTER_PROJECT_DB`: created a project, confirmed one SQLite row, confirmed the payload did not contain sensitive key names, restarted Uvicorn, and confirmed `GET /api/v1/projects/` still returned the project.
- On 2026-06-07, the active project pipeline was optimized again in `apps/api/app/routers/projects.py`:
  - The main flow now uses `_stage_scene_element_pipeline()` after story bible merge, so scene splitting and element generation overlap per chapter instead of running as two fully separate serial stages.
  - Chapter understanding, scene splitting, and element generation use per-project incremental caches under `_pipeline_cache`; cache keys include source text, relevant story data, model/base URL/temperature/max token settings, and a cache version, but not API keys.
  - The cache is included in the sanitized SQLite project snapshot, so repeating the same project with the same text/model config after restart can reuse completed chapter/scene/element results.
  - Small scenes are batched for element generation with default `NOVELSCRIPTER_ELEMENT_BATCH_SIZE=2` and `NOVELSCRIPTER_ELEMENT_BATCH_TEXT_LIMIT=2600`, reducing per-scene request overhead while falling back to single-scene generation if a batch response cannot be mapped.
  - Element generation progress is kept monotonic while the pipeline discovers more scenes, avoiding progress jumping backward in the UI.
  - Verification: `py_compile` passed for the backend files; fake-LLM smoke tests confirmed first run generates data and second same-project/same-config run makes zero model calls; batch smoke confirmed two scenes can be handled by one element request.
- On 2026-06-07, a real API smoke/full-flow test was run against a user-provided OpenAI-compatible `gpt-5.5` gateway without persisting the key:
  - `/api/v1/models/test-connection` returned `connected`; available models included `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, and `codex-auto-review`.
  - A two-chapter project completed all seven project pipeline stages with 2 chapters, 9 scenes, 119 elements, 6 characters, 7 locations, 16 timeline entries, and 0 validation errors.
  - Project exports were verified for `yaml`, `json`, `markdown`, `fountain`, `zip`, and `docs`; global documentation export was also verified.
  - A same-project/same-config rerun completed in about 2.2 seconds, confirming the incremental cache works for repeated runs. The first-run exact 0-to-complete stopwatch was not captured because the initial poll script assumed a non-existent `is_running` field, but the continuous final polling window to completion was about 95.3 seconds.
- On 2026-06-07, project cleanup removed temporary verification artifacts that are not required for running the app:
  - Removed root-level `ui-*.png` QA screenshots and the `ui-check/` screenshot folder.
  - Removed `.codex-api-8028*` logs and `.codex-realtest-projects.sqlite3*` temporary real-test database files.
  - Removed root `data/` and `scripts/` because they were empty after cleanup.
  - Removed `apps/api/.pytest_cache`, project/test `__pycache__` folders, and `apps/web/tsconfig.tsbuildinfo`.
  - Kept `.env`, `apps/api/data/novelscripter_projects.sqlite3`, `apps/api/venv`, `apps/web/node_modules`, `apps/web/.next` while the frontend dev server is running, and active `8017`/`3000` service logs.
- On 2026-06-07, the user's Ubuntu 22.04 server was checked in read-only mode for deployment feasibility:
  - The server can deploy this project, but should use a lightweight production setup: FastAPI + Next.js + SQLite snapshot persistence.
  - Do not deploy the full development compose stack with PostgreSQL, Redis, MinIO, Celery, and vLLM on the current 2 CPU / about 1.6 GiB RAM server; it is too heavy and unnecessary for the active demo path.
  - Existing public ports 80/443 are owned by the `shengtu-image2` Caddy Docker container. Existing routes include `ggbond686.online`/`img.ggbond686.online`, `api.ggbond686.online`, and `stream.ggbond686.online`; use a new independent subdomain for NovelScripter.
  - Host Node/npm are not installed, but Docker, Docker Compose, git, rsync, curl, Python 3.10, and pip are available. Prefer Docker-based deployment or build artifacts locally and copy them to the server.
  - Candidate subdomains such as `qiyunniu.ggbond686.online`, `novel.ggbond686.online`, and `script.ggbond686.online` were not resolving during the check, so public deployment needs a new DNS A record first.
  - Recommended deployment directory: a new isolated path such as `/opt/novelscripter`, with independent container/service names and a SQLite data volume or bind mount.
- On 2026-06-07, NovelScripter was deployed to the user's Ubuntu server with the normal Docker production path:
  - Local deployment files were added under `deploy/production/`: `api.Dockerfile`, `web.Dockerfile`, `docker-compose.yml`, and `README.md`.
  - `apps/web/next.config.js` now uses `output: 'standalone'` so the production web image can run Next.js standalone output.
  - The project was uploaded to `/opt/novelscripter` without `.env*`, local virtualenvs, local SQLite data, `node_modules`, or `.next` artifacts.
  - Server build used the Dockerfiles directly: `docker compose build api` and `docker compose --progress=plain build web`; both completed successfully. The web image ran `next build` inside Docker and passed.
  - Runtime containers are `novelscripter-api` (`production-api`) and `novelscripter-web` (`production-web`) with a named volume `production_novelscripter_data` for `/workspace/data`.
  - API health was verified inside the container: `GET http://127.0.0.1:8000/api/v1/health` returned `{"status":"healthy","version":"1.0.0","llm_provider":"api","model_name":"gpt-4o"}`.
  - The existing Caddy container can reach the app containers on Docker network `shengtu-image2_default`; the Caddyfile now includes a `novel.ggbond686.online` site routing `/api/*` to `novelscripter-api:8000` and other paths to `novelscripter-web:3000`.
  - Caddy config was validated and reloaded. A timestamped Caddyfile backup was created at `/opt/shengtu-image2/Caddyfile.bak-novel-20260607180031`.
  - Public HTTPS is currently blocked by DNS, not by the app: Cloudflare authoritative nameservers `heather.ns.cloudflare.com` and `wilson.ns.cloudflare.com` return `NXDOMAIN` for `novel.ggbond686.online`, and Caddy/Let's Encrypt logs show certificate issuance failing for the same DNS reason.
  - To finish public access, add an authoritative DNS record in Cloudflare DNS: `novel` A record to `8.211.133.149` (prefer DNS-only until Caddy obtains the certificate). After DNS resolves, Caddy should retry certificate issuance automatically or can be reloaded to trigger it sooner.
  - Later on 2026-06-07, the Cloudflare DNS record resolved correctly to `8.211.133.149`. `caddy reload --force` triggered certificate issuance, and Caddy logged `certificate obtained successfully` for `novel.ggbond686.online`.
  - Final public verification passed: `https://novel.ggbond686.online` returned HTTP 200 from Next.js, and `https://novel.ggbond686.online/api/v1/health` returned the healthy API payload.

## Pitfalls

- This directory is now initialized as a Git repository for PR work against `https://github.com/ggbond-1027/scriptbridge-ai.git`.
- README/docs describe PostgreSQL, Redis, Celery, MinIO, Monaco, and a fuller architecture, but the active code path is mostly an in-memory demo implementation.
- Backend tests are not currently green. On 2026-06-06, `python -m pytest` in `apps/api` reported 53 passed and 28 failed. Failures clustered around export service bugs, schema validation inconsistencies, and one English chapter title expectation.
- Frontend build was verified on 2026-06-06 with `npm run build` in `apps/web`; it passed.
- Some OpenAI-compatible endpoints may require `stream: true`; keep streamed parsing in `_call_llm` and model test checks.
- Do not raise pipeline LLM concurrency blindly. A test with higher concurrency (`chapter=3`, `element=8`) triggered an incomplete chunked read during chapter understanding. Keep conservative defaults unless the target model endpoint is known to tolerate more parallel requests.
- Some OpenAI-compatible gateways pre-charge based on the requested `max_tokens`, not actual output tokens. If `HTTP 403` reports `insufficient_user_quota` during early pipeline stages, lower the per-stage `NOVELSCRIPTER_*_MAX_TOKENS` caps before assuming the API key or URL is wrong.
- Project-scoped `/pipeline/status` currently returns the frontend status payload but does not expose the internal `is_running` flag. Test scripts should determine completion from per-stage statuses unless this API response is expanded.
- Project data is now restored from local SQLite snapshots after backend restart, but active in-flight pipeline tasks are still process-local. If Uvicorn restarts while a pipeline is running, the project record may be restored while the running task itself is gone.
- Schema/data shapes are inconsistent across strict JSON Schema, Pydantic models, frontend types, examples, and the live in-memory pipeline.
- The live frontend pipeline uses `content` for elements, while Pydantic/export paths often expect `text`.
- Generated `metadata` in the project pipeline may not satisfy the Pydantic `GenerationMetadata` model expected by backend export routes.
- `apps/api/app/core/export.py` contains a likely bug: location name resolution references an undefined `screenplay` variable.
- `apps/api/app/routers/pipeline.py` imports `app.routers.import_router`, but the actual file is `import.py`; this can break the older modular pipeline route.
- Avoid implementing `favicon.ico` as an App Router route in this project; during dev hot reload it caused stale `.next` server chunk errors. Use the static file under `apps/web/public/favicon.ico`.
- After `npm run build`, Next dev can serve stale HTML that references missing `/_next/static/*` chunks, causing the page to render server HTML but not hydrate. If buttons do not respond, effects do not run, and chunk requests return 404, stop the frontend dev server, delete `apps/web/.next`, and restart `npm run dev`.
- On the 2 CPU / about 1.6 GiB RAM server, run production Docker builds serially (`api` first, then `web`) and monitor logs/resource usage. A previous combined build attempt made SSH and HTTP temporarily unresponsive until the server was rebooted.
- The authoritative DNS provider for `ggbond686.online` is Cloudflare (`heather.ns.cloudflare.com`, `wilson.ns.cloudflare.com`). Adding records in a non-authoritative DNS panel will not make `novel.ggbond686.online` resolve.

## Current Focus

- On 2026-06-07, README was updated for GitHub PR/project presentation work:
  - Added the public site URL `https://novel.ggbond686.online`.
  - Added local setup, quick start scripts, webpage usage steps, Schema documentation locations, and documentation export notes.
  - `.gitignore` excludes `.env`, `.env.*` except `.env.example`, logs, local SQLite/database files, Python virtualenv/cache files, `node_modules`, and `.next`.
- On 2026-06-07, README was redesigned in the style of polished open-source project homepages:
  - Added centered title, entry links, badges, product tour sections, quick experience flow, local run commands, architecture summary, and Schema links.
  - Added real website screenshots under `docs/assets/`: `novelscripter-home.png`, `novelscripter-docs.png`, and `novelscripter-export.png`.
  - Removed the health-check link and DNS troubleshooting note from the public README.
- On 2026-06-07, the old public presentation guidance material was removed from `docs/` and README; README now keeps only product, setup, usage, architecture, Schema, and export documentation.
- For functional hardening, prioritize unifying the screenplay schema/data model.
- For testing with a user-provided model endpoint, avoid persisting the model key and test through transient environment variables or request payloads only.
