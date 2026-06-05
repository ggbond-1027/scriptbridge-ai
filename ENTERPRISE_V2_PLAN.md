# ScriptBridge AI Enterprise V2 Plan

## Product Direction

ScriptBridge AI is being rebuilt as an enterprise-grade AI screenplay adaptation platform, not a simple contest demo.

The chosen product style is a hybrid of:

- Arc Studio-style professional screenplay editing as the primary UI direction.
- Novelcrafter-style story memory, source evidence, and codex.
- Celtx/StudioBinder-style production breakdown and workflow control.

The product must support a complete authoring workflow: import source fiction, build a traceable story bible, generate scenes, inspect quality gates, rewrite individual scenes, validate the deliverable, and export production-ready formats.

## V2 Capability Model

The backend now models the following enterprise objects:

- Chapter and paragraph evidence index.
- Character bible with goals, traits, secrets, relationships, and character arcs.
- Location bible.
- Timeline events.
- Theme threads.
- Conflict threads.
- Foreshadowing threads.
- Scene act, sequence, emotional shift, production notes, rewrite options, and quality flags.
- Source evidence snippets returned from scene rewrite and derived from SQLite FTS search, `source_refs`, adjacent paragraphs, and keyword hits.
- Pipeline stage reports.
- Quality metrics and risk reports.
- Production breakdown with estimated pages, runtime, cast, locations, shooting days, location breakdown, and shot plan.
- Project records with settings, source text, version snapshots, and last job pointer, persisted in local SQLite.
- Generation job records with status, progress, stage events, errors, and result version, persisted in local SQLite.
- Rewrite job records with selected scenes, rewrite mode, stage events, result version, and audit linkage.
- Job queue metadata with `inline`, `background`, and `external` modes, persisted request payloads, retry attempts, cancellation, worker claiming, and queue status snapshots.
- Project members, member sessions, bearer tokens, roles, role permissions, comments, assignments, threaded replies, comment status transitions, notifications, audit events, and audit-event filters for the first review-collaboration foundation.

## Implemented V2 APIs

- `GET /api/capabilities`
  - Returns available pipeline agents, exports, model modes, and open-source stack.

- `GET /api/projects`
  - Lists locally persisted projects.

- `POST /api/projects`
  - Creates a project with source text and generation settings.

- `GET /api/projects/{project_id}`
  - Reads project details and version history.

- `PATCH /api/projects/{project_id}`
  - Updates title, source text, or settings.

- `POST /api/auth/sessions`
  - Creates a local project-member session for an existing project member.
  - Returns a bearer token used by project collaboration APIs.
  - Session identity overrides request-body `actor` or `author` fields, so permissions and audit events use the verified member.

- `POST /api/projects/{project_id}/members`
  - Adds or updates a project member.
  - Enforces owner/admin-only member management.
  - Persists a `member.added` audit event.

- `POST /api/projects/{project_id}/comments`
  - Creates a project-level or scene-level review comment.
  - Supports an optional assignee field.
  - Persists a matching `comment.created` audit event with actor, target, summary, and metadata.
  - Creates an unread `comment.assigned` notification for the assignee when applicable.

- `POST /api/projects/{project_id}/comments/{comment_id}/replies`
  - Adds a threaded reply to a review comment.
  - Persists a matching `comment.replied` audit event.
  - Notifies the original author and assignee, excluding the reply author.

- `PATCH /api/projects/{project_id}/comments/{comment_id}`
  - Resolves or reopens a review comment.
  - Persists `comment.resolved` or `comment.reopened` audit events with previous and next status metadata.

- `GET /api/projects/{project_id}/audit-events`
  - Lists audit events.
  - Supports `event_type`, `actor`, and `limit` query filters.

- `GET /api/projects/{project_id}/notifications`
  - Lists project notifications.
  - Supports `recipient`, `unread_only`, and `limit` query filters.

- `PATCH /api/projects/{project_id}/notifications/{notification_id}`
  - Lets the notification recipient mark a notification read or unread.
  - Persists a `notification.updated` audit event.

- `POST /api/jobs/generate`
  - Starts a project-level generation job and records progress events.
  - Persists the request payload and dispatches through the configured queue mode.

- `POST /api/jobs/rewrite`
  - Starts a project-level batch scene rewrite job from the current saved screenplay version.
  - Enforces rewrite permission for owner/admin/writer roles.
  - Selects explicit `scene_ids` when provided, otherwise prioritizes quality-flagged, low-evidence, or weak-conflict scenes.
  - Reuses the evidence-bound scene rewrite pipeline, saves a new version, rebuilds the evidence index, and persists a `rewrite.batch_completed` audit event.
  - Persists the rewrite request payload for retry and external-worker execution.

- `GET /api/job-queue/status`
  - Returns configured queue mode, status counts, and worker instructions.

- `POST /api/jobs/{job_id}`
  - Supports `cancel` and `retry` actions for queued/running or failed/canceled jobs.

- `POST /api/workers/run-once`
  - Lets the local API execute one queued `external` job, providing a compatibility seam for a future standalone worker process.

- `GET /api/jobs/{job_id}`
  - Reads job status, progress, events, and result version.

- `GET /api/jobs/{job_id}/events`
  - Streams job progress with Server-Sent Events.
  - Frontend uses EventSource first and falls back to polling if the stream fails.

- `POST /api/projects/{project_id}/evidence/search`
  - Searches the project evidence index.
  - Uses SQLite FTS5 with keyword/LIKE fallback for Chinese text.

- `POST /api/generate`
  - Keeps the existing API-compatible generation route.
  - Now returns V2 screenplay objects with quality report, production breakdown, and pipeline stages.

- `POST /api/rewrite-scene`
  - Supports scene-level rewrite modes:
    - `strengthen_conflict`
    - `rewrite_dialogue`
    - `short_drama`
    - `tighten_evidence`
  - Retrieves source evidence before rewrite.
  - Uses LLM JSON rewrite plans when API/local model is available.
  - Applies only safe scene fields and preserves IDs, source refs, chapter refs, location refs, and character refs.
  - Falls back to deterministic local rewrite rules when model access is unavailable.
  - Returns `evidence`, `diff_summary`, `provider`, and `provider_status`.

- `POST /api/validate`
  - Validates YAML syntax, Pydantic model contract, JSON Schema, and cross-reference integrity.

- `POST /api/export/{yaml|json|markdown|fountain}`
  - Keeps export compatibility.

## Frontend V2 Workspace

The old three-column MVP interface has been replaced by an Arc Studio-style professional editor workbench:

- Left rail:
  - Project title.
  - Local project library.
  - Adaptation style controls.
  - API/local model priority toggle.
  - Source novel editor.
  - Chapter evidence index.

- Central workspace:
  - Professional screenplay editor.
  - Scene index.
  - Story structure and bible.
  - Quality center.
  - Production breakdown.
  - YAML workspace.

- Right rail:
  - Scene inspector.
  - Source evidence inspector.
  - Review comments, assignment, threaded replies, and audit-event inspector with event-type filters.
  - Project collaboration panel with actor switching, member roster, member add form, notifications, and mark-read action.
  - Rewrite diff inspector.
  - Job progress.
  - Quality snapshot.
  - Pipeline status.
  - Open-source stack and model capability summary.

## Open-Source Stack Actually Used

Backend:

- FastAPI
- Uvicorn
- Pydantic
- PyYAML
- jsonschema
- httpx
- pytest

Frontend:

- Next.js
- React
- TypeScript
- Tailwind CSS
- lucide-react

## Latest Verified Slice

The current verified slice adds:

- `apps/api/evidence.py` source evidence retrieval.
- `SourceEvidence` response model.
- LLM-backed `rewrite_scene` pipeline with safe application and fallback rules.
- SQLite-backed project and job persistence in `.scriptbridge_data/scriptbridge.sqlite3`.
- One-time migration path from legacy JSON runtime records into SQLite.
- SSE job progress endpoint and frontend EventSource subscription with polling fallback.
- SQLite FTS5 project evidence index for chapter paragraphs.
- Project evidence search API and frontend evidence search panel.
- Project generation path forces saved screenplay project IDs to match the persisted project ID before indexing evidence.
- `apps/api/longform.py` LongformChunker for chapter-level long novel context compression.
- LLM generation prompts now use `LONGFORM_CONTEXT` with all chapter titles, character counts, paragraph counts, beginning/middle/ending excerpts, and per-chapter scene guidance instead of truncating to the first 12000 characters.
- Pipeline reports now include `stage_longform_context`, so the Arc Studio-style workspace can show longform compression as a first-class stage.
- `apps/api/embeddings.py` local deterministic embedding backend for offline evidence retrieval.
- SQLite evidence indexing now stores paragraph vectors in `evidence_embeddings` and fuses FTS, LIKE, and vector search results.
- `YamlEditor` upgraded from a plain textarea into a diagnostic editor shell with line numbers, validation status, issue list, and active issue highlighting.
- Review-collaboration foundation with `ProjectComment`, `CommentReply`, `AuditEvent`, create/update comment APIs, assignment, threaded replies, resolve/reopen actions, audit-event filtering, and a right-rail review panel.
- Team/RBAC/notification foundation with `ProjectMember`, `ProjectNotification`, owner/admin member management, viewer restrictions, assignment notifications, reply notifications, and recipient-only mark-read.
- Local project-member session foundation with `ProjectSession`, `POST /api/auth/sessions`, bearer-token request headers, session-scoped notification reads, and server-side session identity overriding request-body `actor`/`author` fields.
- Queue foundation with `apps/api/queue.py`, persisted job payloads, `JOB_QUEUE_MODE`, external worker run-once, cancel/retry APIs, queue status API, and frontend queue controls.
- Batch scene rewrite job endpoint and Quality Center control that rewrites risky scenes from the current project version, saves a new version, rebuilds evidence, streams job progress, and records `rewrite.batch_completed`.
- External queue runtime verification against `JOB_QUEUE_MODE=external`, confirming queued jobs remain pending until worker execution, worker run-once completes the persisted payload, and the Arc Studio-style right rail shows queue mode, counts, worker hint, and job controls.
- Tests for evidence retrieval, fallback rewrite, and mocked LLM rewrite.
- Arc Studio-style frontend rebuild with script page, scene index, source evidence panel, rewrite diff panel, quality, production, and YAML workspaces.

## Enterprise Features Still To Build

These are not complete yet and should not be represented as finished:

- Production database storage such as Postgres. Current storage is local SQLite, not a production deployment database.
- Redis/Celery/RQ backed production worker deployment. Current queue has inline/background/external modes and a worker seam, but not a distributed broker or multi-process production scheduler.
- Production-grade progress streaming and notification infrastructure. Current progress streaming is SSE over local FastAPI.
- Real LangGraph-style multi-agent orchestration.
- Production RAG with API embedding models, pgvector/Qdrant, re-ranking, and migration tooling. Current evidence retrieval has SQLite FTS5 plus local deterministic embedding vectors, not a production vector database.
- Monaco Editor plus YAML language server. Current YAML surface is a diagnostic editor shell, not Monaco yet.
- Frontend-side schema hints and guided auto-fix.
- Full LangGraph-style multi-agent scene rewrite and review loop. Current LLM scene rewrite is a constrained single-call rewrite Agent with fallback.
- Password/SSO login, realtime review presence, and external cross-user notification delivery. Current implementation has local project-member sessions, bearer-token API calls, role checks, stored notifications, comment threads, and audit events, not full enterprise authentication or realtime collaboration.
- File import/export for large manuscripts.
- Embedding-backed long-novel retrieval and map-reduce story bible synthesis for 100k+ character manuscripts. Current LongformChunker is deterministic chapter compression and sampling, not final vector RAG or multi-agent summarization.
- Production-ready deployment packaging.

## Verification

Current V2 foundation was verified with:

- `python -m pytest apps/api/tests`
- `npm --prefix apps/web run build`
- `npm run test`

All passed after the evidence rewrite and Arc Studio-style frontend rebuild.

The project/job persistence foundation was verified with backend tests covering:

- Project creation.
- Generation job start.
- Job event persistence.
- Version snapshot creation.
- Project list summary.
- SSE job event endpoint.
- SQLite FTS evidence indexing and search.
- Persisted screenplay project ID alignment before evidence indexing.

The evidence rewrite slice was verified with:

- Backend tests covering direct source-ref evidence retrieval.
- API rewrite tests confirming fallback rewrite returns evidence and diff summary.
- Mocked LLM rewrite tests confirming safe field application and preserved `source_refs`.
- Browser smoke verification against `http://127.0.0.1:3000` showing the script editor, scene index, evidence inspector, and generated screenplay state.
- HTTP runtime probe confirming SQLite project creation, generation job completion, SSE event delivery, and version persistence.

The longform context slice was verified with:

- Backend tests confirming `_build_llm_prompt` includes late-chapter titles and clues through `LONGFORM_CONTEXT`.
- Backend tests confirming `stage_longform_context` is present with `LongformChunker`.
- `python -m pytest apps/api/tests` passing 13 tests after the LongformChunker integration.

The local vector evidence slice was verified with:

- Backend tests confirming semantic-neighbor retrieval can return `向量证据库命中` when FTS/LIKE terms are insufficient.
- Backend tests confirming FTS evidence search still works.
- `python -m pytest apps/api/tests` passing 14 tests after the local embedding integration.

The YAML editor shell slice was verified with:

- `npm run test:web:editor` confirming line-number and diagnostic editor affordances exist.
- `npm --prefix apps/web run build` passing after the component upgrade.

The review/audit foundation was verified with:

- Backend test confirming a scene comment creates a persisted `comment.created` audit event.
- Backend test confirming comment resolve creates a persisted `comment.resolved` audit event.
- Backend test confirming comment assignment, threaded reply, and filtered `comment.replied` audit events.
- Browser verification against `http://127.0.0.1:3013` confirming assignment display, reply thread display, comment resolve/reopen action, and `comment.replied` / `comment.resolved` audit filters.
- `python -m pytest apps/api/tests` passing 17 tests.
- `npm run test` passing API tests, YAML editor checks, and frontend production build.

The team/RBAC/notification and batch rewrite slice was verified with:

- Backend tests confirming default project members, owner/admin member management, reviewer/viewer permission failures, assignment notifications, reply notifications, and recipient-only notification read updates.
- Backend tests confirming `/api/jobs/rewrite` creates a rewrite job, rewrites selected scenes, saves a new project version, preserves `source_refs`, emits rewrite job events, and persists `rewrite.batch_completed`.
- Backend test confirming viewer role cannot start a batch rewrite job.
- Backend tests confirming bearer-token project sessions override request-body `actor`/`author`, block reviewer escalation to owner/admin-only member management, and reject cross-project session tokens.
- Browser verification against `http://127.0.0.1:3015` confirming project session creation, reviewer-disabled batch rewrite, writer-enabled batch rewrite, `编剧/已验证` topbar state, successful rewrite job completion, and `rewrite.batch_completed` audit actor recorded as `编剧`.
- Desktop and mobile screenshots were captured at `.scriptbridge_data/verify-screens/session-quality-desktop.png` and `.scriptbridge_data/verify-screens/session-quality-mobile.png`.
- `python -m pytest apps/api/tests` passing 22 tests.
- `npm run test` passing API tests, YAML editor checks, and frontend production build.

The queue foundation slice was verified with:

- Backend tests confirming an `external` generation job is queued without running until `/api/workers/run-once` claims and executes it.
- Backend tests confirming a queued job can be canceled before worker execution.
- HTTP runtime probe against `http://127.0.0.1:8016` confirming `GET /api/job-queue/status` reports `external`, `queued 0`, `running 0`, `failed 0`, and `succeeded 13` after worker execution.
- Browser verification against `http://127.0.0.1:3016` confirming the latest project opens with 3 screenplay scenes, quality score 95, verified reviewer session, and a right-rail task queue panel showing `external`, `queued 0`, `running 0`, `failed 0`, `done 13`, plus the external worker hint.
- Desktop and mobile screenshots were captured at `.scriptbridge_data/verify-screens/queue-external-desktop.png`, `.scriptbridge_data/verify-screens/queue-external-mobile.png`, and `.scriptbridge_data/verify-screens/queue-external-mobile-queue.png`.
- Browser runtime checks reported no page errors; console output contained only the React DevTools development hint.
