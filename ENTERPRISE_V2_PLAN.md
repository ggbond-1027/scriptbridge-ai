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
- Project version governance summaries, current-version markers, scene-level version comparison, YAML diff previews, restore permission checks, and version-restore audit events.
- Generation job records with status, progress, stage events, errors, and result version, persisted in local SQLite.
- Rewrite job records with selected scenes, rewrite mode, stage events, result version, and audit linkage.
- Job queue metadata with `inline`, `background`, and `external` modes, persisted request payloads, retry attempts, cancellation, worker claiming, Redis broker pointers, dead-letter isolation metadata, manual requeue counts, and queue status snapshots.
- Project members, member sessions, bearer tokens, roles, role permissions, comments, assignments, threaded replies, comment status transitions, notifications, audit events, and audit-event filters for the first review-collaboration foundation.
- Model profiles with API/local/fallback providers, runtime-only API keys, server-side API key secret references, sanitized persisted profile summaries, and short-timeout connection testing.
- Source file import metadata for `.txt`, `.md`, `.markdown`, `.docx`, and text-based `.pdf` manuscript uploads, including encoding/extraction method, document stats, Markdown document-title stripping, chapter count, paragraph count, byte size, and import warnings.
- Import job records for queued manuscript ingestion, with persisted file metadata, progress events, result payloads, project source refresh, and audit linkage.
- Chunked import session metadata for local resumable manuscript uploads, including upload session ID, original file metadata, target project, chunk size, total chunks, uploaded chunk indexes, status, local chunk paths, assembly result, and dispatched import job ID.
- Import security reports with scanner chain name, verdict, risk level, sha256, extension, detected file type, declared content type, checks, warnings, and blocked reasons.
- Import history items for project-level import governance, with sanitized file metadata, queue state, extraction stats, warning counts, last pipeline stage, and linked audit events. The history response intentionally excludes manuscript text and local transient file paths.
- Project readiness gate reports with delivery status, score, blockers, warnings, passed checks, current version, and next actions across source import, version, schema, quality, evidence coverage, production breakdown, import security, review comments, and job queue state.
- System readiness gate reports with deployment status, score, blockers, warnings, passed checks, and next actions across production database, external worker queue, model secret governance, import scanning, delivery artifact storage, and auth/signing configuration.
- Project approval records with submitted/approved/rejected/revoked/blocked states, linked version metadata, readiness snapshot, submit/decision notes, role-gated decisions, notifications, and audit-event links.
- Project delivery package records with linked approved approval, version metadata, selected formats, asset list, artifact storage provider metadata, 1-hour signed download URLs, manifest JSON, manifest sha256, total byte size, readiness snapshot, blockers/warnings, and audit-event links.
- Project export governance records with format, actor, version ID, version label, filename, content type, byte size, sha256, readiness status/score, blockers, warnings, export status, and linked audit event.

## Implemented V2 APIs

- `GET /api/capabilities`
  - Returns available pipeline agents, exports, model modes, and open-source stack.
  - Includes `SystemReadinessGate` so the frontend and documentation surface deployment checks as a first-class enterprise capability.

- `GET /api/system-readiness`
  - Returns system-level deployment readiness for database, queue, model secrets, import security, artifact storage, and auth/signing.
  - Treats local SQLite, local/background queue execution, browser/runtime-only model keys, local-only artifact storage, and local member sessions as non-final production states.
  - Uses only sanitized evidence such as provider names, modes, and boolean configuration flags; it does not return secret values.

- `GET /api/model-profiles`
  - Returns the active environment model profile and API/local/fallback presets.
  - Only returns sanitized model metadata, `has_api_key`, and optional `api_key_secret_ref`, never the key value.
  - Resolves `OPENAI_API_KEY_SECRET_REF` through server environment secrets before runtime use.

- `POST /api/model-profiles/test`
  - Tests an API or local OpenAI-compatible model profile with a short timeout.
  - Returns sanitized profile metadata, latency, status, and warnings.
  - Supports runtime `api_key_secret_ref` values that resolve to server-side `MODEL_SECRET_*`, `MODEL_SECRET_REF_*`, or `OPENAI_API_KEY_*` environment variables.

- `POST /api/import/source`
  - Imports `.txt`, `.md`, `.markdown`, `.docx`, or text-based `.pdf` manuscript files through multipart upload.
  - Decodes UTF-8/UTF-8 BOM/GB18030 text files, extracts DOCX paragraphs with `python-docx`, extracts PDF page text with `pypdf`, strips a top-level Markdown document title, detects chapters and paragraph evidence counts, and returns extraction metadata before the project is saved.
  - Computes sha256 and runs the local static import scan plus optional external/ClamAV-style scanner before extraction.

- `POST /api/jobs/import-source`
  - Starts a queued source import job through multipart upload.
  - Can update an existing project when `project_id` is supplied, or create a new project shell when omitted.
  - Stores only upload metadata, sha256, security report, upload mode, and a local transient file path in the job request payload, not the manuscript text itself.
  - Dispatches through `inline`, `background`, or `external` queue modes.
  - On success, updates project title/source text, stores import metadata in `result_payload`, appends an `import.source_completed` audit event, and lets the frontend hydrate the source editor through the same job/SSE path as generation and rewrite tasks.

- `POST /api/import-sessions`
  - Creates a local chunked import session for resumable manuscript upload.
  - Persists sanitized file metadata, target project, desired title, actor, total size, chunk size, total chunk count, and initial session status.

- `GET /api/import-sessions/{session_id}`
  - Returns chunked import session state, uploaded chunk indexes, progress, completion status, and dispatched import job metadata.
  - Does not return manuscript text or local transient file paths.

- `PUT /api/import-sessions/{session_id}/chunks/{chunk_index}`
  - Stores one uploaded chunk in the local chunk staging area.
  - Supports retrying or resuming missing chunks before completion.

- `POST /api/import-sessions/{session_id}/complete`
  - Validates that all chunks are present, assembles them into the existing local import-upload staging area, and dispatches the normal `/api/jobs/import-source` flow.
  - Re-runs local static import scan plus optional external/ClamAV-style scanner on the assembled file, persists sha256/security metadata, and blocks mismatched file signatures or infected scan results before dispatch.
  - Returns the completed session plus the queued import job reference.

- `GET /api/projects/{project_id}/import-history`
  - Lists sanitized import runs for a project.
  - Returns import job status, queue mode, upload mode, actor, filename, content type, byte size, sha256, local scan verdict/risk, extraction method, encoding, chapter/paragraph counts, warnings, document stats, last stage, and linked audit event ID.
  - Does not return manuscript text or local transient upload paths.

- `GET /api/projects`
  - Lists locally persisted projects.

- `POST /api/projects`
  - Creates a project with source text and generation settings.

- `GET /api/projects/{project_id}`
  - Reads project details and version history.

- `PATCH /api/projects/{project_id}`
  - Updates title, source text, or settings.

- `GET /api/projects/{project_id}/versions`
  - Lists saved screenplay versions with summary metadata and the current-version marker.

- `GET /api/projects/{project_id}/versions/compare`
  - Compares two saved versions.
  - Returns added, removed, and modified scene summaries plus a compact YAML diff preview.

- `POST /api/projects/{project_id}/versions/{version_id}/restore`
  - Restores a saved version as the current project version.
  - Requires member-management permission and persists a `version.restored` audit event.

- `GET /api/projects/{project_id}/readiness`
  - Returns the project delivery gate status, score, current version, blockers, warnings, passed checks, and next actions.
  - Evaluates source text, current screenplay version, Schema validity, quality gate score, source evidence coverage, production breakdown completeness, latest import security status, unresolved review comments, and active or failed jobs.

- `GET /api/projects/{project_id}/exports`
  - Lists project-level export records.
  - Returns format, status, actor, version metadata, filename, content type, size, sha256, readiness status/score, blockers, warnings, and audit linkage.

- `POST /api/projects/{project_id}/exports`
  - Creates a governed project export for YAML, JSON, Markdown, or Fountain from the current or selected version.
  - Enforces export permission for owner/admin/writer/producer roles.
  - Enforces the project readiness gate by default; blocked exports return HTTP 409, persist an `export.blocked` audit event, and still appear in export history.
  - Successful exports return the text content and persist an `export.created` audit event with sha256 and delivery metadata.

- `GET /api/projects/{project_id}/approvals`
  - Lists project-level delivery approval records.
  - Returns pending, approved, rejected, revoked, and blocked counts plus version/readiness metadata.

- `POST /api/projects/{project_id}/approvals`
  - Submits the current or selected version into delivery approval.
  - Enforces submit permission for owner/admin/writer roles.
  - Captures the readiness snapshot, requested export format, submit note, blockers, warnings, and linked audit event.
  - Blocked approval submissions return HTTP 409, persist an `approval.blocked` audit event, and still appear in approval history.
  - Successful submissions persist an `approval.submitted` audit event and notify delivery approvers.

- `POST /api/projects/{project_id}/approvals/{approval_id}/decision`
  - Approves, rejects, or revokes a submitted delivery approval.
  - Enforces delivery approval permission for owner/admin/producer on approve/reject.
  - Allows revoke by the submitter or owner/admin.
  - Persists `approval.approved`, `approval.rejected`, or `approval.revoked` audit events and notifies the submitter.

- `GET /api/projects/{project_id}/delivery-packages`
  - Lists formal delivery package records for a project.
  - Returns package status, linked approval/version metadata, selected formats, persisted asset metadata, manifest hash, readiness snapshot, blockers/warnings, and audit linkage.
  - When the caller has `package_delivery` permission, returns temporary signed download URLs for locally stored artifacts; unauthorized metadata fallback returns history without download links.

- `POST /api/projects/{project_id}/delivery-packages`
  - Creates a formal delivery package from the current or selected version.
  - Enforces package permission for owner/admin/producer roles.
  - Requires a linked approved delivery approval by default.
  - Enforces the project readiness gate by default; blocked packages return HTTP 409, persist a `delivery_package.blocked` audit event, and still appear in package history.
  - Successful packages return package assets with content plus a canonical JSON manifest, write local artifacts under `.scriptbridge_data/delivery-artifacts/`, persist asset storage keys and manifest sha256, and write a `delivery_package.created` audit event.

- `GET /api/projects/{project_id}/delivery-packages/{package_id}/assets/{asset_sha256}`
  - Downloads one delivery package artifact through a signed token.
  - Verifies package ID, asset sha256, token signature, expiry, and stored artifact sha256 before returning the file.

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
  - Returns configured queue mode, status counts including `dead_lettered`, Redis/SQLite broker metadata, broker queue depth, broker errors, worker heartbeats, and worker instructions.

- `GET /api/job-queue/dead-letter`
  - Returns failed and dead-lettered job summaries with job kind, project ID, attempts, max attempts, error, dead-letter timestamp, dead-letter reason, source worker, and manual requeue count.

- `POST /api/jobs/{job_id}`
  - Supports `cancel` and `retry` actions for queued/running or failed/canceled/dead-lettered jobs.
  - Retrying a dead-lettered job clears dead-letter metadata, resets attempts, increments `requeue_count`, and re-dispatches the job through the configured queue or Redis broker.

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
  - The project-governed export path is `/api/projects/{project_id}/exports`; this compatibility route does not create project audit/history records.

## Frontend V2 Workspace

The old three-column MVP interface has been replaced by an Arc Studio-style professional editor workbench:

- Left rail:
  - Project title.
  - Local project library.
  - Adaptation style controls.
  - API/local model priority toggle.
  - Source file import readiness, supported manuscript format hint, chapter threshold, word count, paragraph count, and active chunked-upload progress.
  - Source novel editor.
  - Chapter evidence index.

- Central workspace:
  - Workspace status bar for Schema state, evidence coverage, and queue mode.
  - Professional screenplay editor.
  - Scene index.
  - Scene desk bar with act/sequence/review readiness.
  - Scene quality flags and evidence-count review strip.
  - Story structure and bible.
  - Quality center.
  - Production breakdown.
  - YAML workspace.

- Right rail:
  - Scene inspector with ID/chapter/evidence/character checklist and quality risk alerts.
  - Source evidence inspector.
  - Review comments, assignment, threaded replies, and audit-event inspector with event-type filters.
  - Project collaboration panel with actor switching, member roster, member add form, notifications, and mark-read action.
  - Project readiness panel with delivery score, blockers, warnings, passed checks, and next actions.
  - Delivery approval center with submit controls, requested export format, latest approval state, decision notes, role-aware approve/reject/revoke actions, readiness score, blockers/warnings, and recent approval history.
  - Delivery package center with approved-approval binding, format checkboxes, role-aware package generation, latest package state, asset list, manifest sha256, blockers/warnings, and recent package history.
  - Export governance panel with gated YAML/JSON/Markdown/Fountain actions, latest export state, readiness score, sha256 short fingerprint, blockers/warnings, and recent export history.
  - Import history panel with import run counts, active import progress, active chunk session state, latest import summary, warning display, extraction stats, upload mode, sha256 short fingerprint, local scan verdict/risk, and audit-linked job rows.
  - Version governance panel with current-version summary, baseline comparison selector, changed-scene list, YAML diff preview, and restore controls.
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
- python-docx
- pypdf
- boto3
- qiniu
- redis
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
- Queue foundation with `apps/api/queue.py`, `apps/api/redis_broker.py`, `apps/api/worker.py`, persisted job payloads, `JOB_QUEUE_MODE`, optional `JOB_BROKER_URL`/`REDIS_URL` Redis list broker, external worker run-once, independent worker loop, worker heartbeat records, stale/canceled job skipping, dead-letter isolation, manual requeue, cancel/retry APIs, broker/worker/dead-letter-aware queue status API, and frontend queue controls.
- Model connection center with `apps/api/model_profiles.py`, runtime `ModelProfileRuntime`, sanitized `ModelProfilePublic`, `/api/model-profiles`, `/api/model-profiles/test`, frontend provider/base URL/model/temperature/API key controls, server-side `api_key_secret_ref` controls, and model profile propagation into generation, rewrite, and batch rewrite paths.
- Environment-backed model secret reference resolver: `OPENAI_API_KEY_SECRET_REF` and runtime `api_key_secret_ref` values resolve to server-side `MODEL_SECRET_<REF>`, `MODEL_SECRET_REF_<REF>`, or `OPENAI_API_KEY_<REF>` variables; persisted project settings and job payloads keep only the reference and `has_api_key`, not the resolved key.
- Source import foundation with `apps/api/importer.py`, `/api/import/source`, `.txt/.md/.markdown/.docx/.pdf` upload support, text encoding detection, `python-docx` DOCX extraction, `pypdf` text-PDF extraction, Markdown H1 cleanup, extraction metadata, document stats, chapter/paragraph metadata, and a front-rail import button that fills the project title/source text and refreshes the chapter index.
- Source import job foundation with `/api/jobs/import-source`, `kind="import"` job support, persisted import result payloads, project source refresh, SSE/worker completion handling, and frontend import hydration through the shared task queue.
- Import history governance foundation with `/api/projects/{project_id}/import-history`, `ImportHistoryItem`, `ImportHistoryResponse`, sanitized job/result aggregation, audit-event linkage, frontend `listProjectImportHistory`, and a right-rail import history panel.
- Chunked import session foundation with `/api/import-sessions`, `/api/import-sessions/{session_id}`, `/api/import-sessions/{session_id}/chunks/{chunk_index}`, `/api/import-sessions/{session_id}/complete`, local chunk staging, assemble-and-dispatch flow into the existing import job queue, frontend chunk upload helpers, threshold-based chunked import path, left-rail upload progress, and right-rail active chunk session status.
- Import security governance foundation with `ImportSecurityReport`, local static extension/signature/MIME checks, optional external/ClamAV-style scanner integration, fail-closed or warn-on-unavailable policy, sha256 computation, blocked mismatched signatures or infected scan results, security metadata in import job request/result payloads, import audit metadata, sanitized import-history security fields, and right-rail security verdict display.
- B-style Arc Studio workbench refinement with top delivery-state bar, left-rail import readiness, script desk bar, scene quality flags, and right-rail scene inspection checklist.
- Version governance foundation with project-version list/compare/restore APIs, scene-change summaries, YAML diff preview, permission-gated restore, `version.restored` audit events, and a right-rail project version panel.
- Project readiness gate with `GET /api/projects/{project_id}/readiness`, backend checks for source/version/schema/quality/evidence/production/import security/review/jobs, frontend `ReadinessPanel`, topbar Gate score, and static workbench guard coverage.
- System deployment readiness gate with `GET /api/system-readiness`, backend checks for Postgres/DATABASE_URL, external queue broker, server-side model secret references, external import scanning, remote artifact storage, and auth/signing configuration, plus a right-rail `SystemReadinessPanel` and topbar System score.
- Project export governance with `GET/POST /api/projects/{project_id}/exports`, readiness-gated export records, `export.created`/`export.blocked` audit events, RBAC export permission checks, sha256 metadata, frontend `ExportGovernancePanel`, and static workbench guard coverage.
- Delivery package center with `GET/POST /api/projects/{project_id}/delivery-packages`, `GET /api/projects/{project_id}/delivery-packages/{package_id}/assets/{asset_sha256}`, approved-approval binding, readiness-gated package creation, local artifact persistence, signed download URLs, asset sha256 metadata, frontend sha256 download verification, canonical manifest JSON, `delivery_package.created`/`delivery_package.blocked` audit events, frontend `DeliveryPackagePanel`, and static plus browser workbench verification.
- Pluggable delivery artifact storage with `apps/api/artifact_storage.py`, `DELIVERY_ARTIFACT_PROVIDER`, configurable local artifact root, per-asset `storage_provider` reads, boto3-backed `s3`/`minio` S3-compatible writes and reads, qiniu-backed Kodo writes and private-download reads, optional object key prefixes, path-style MinIO support, and explicit 503 failures when required remote configuration is missing.
- Batch scene rewrite job endpoint and Quality Center control that rewrites risky scenes from the current project version, saves a new version, rebuilds evidence, streams job progress, and records `rewrite.batch_completed`.
- External queue runtime verification against `JOB_QUEUE_MODE=external`, confirming queued jobs remain pending until worker execution, worker run-once completes the persisted payload, and the Arc Studio-style right rail shows queue mode, counts, worker hint, and job controls.
- Redis broker adapter slice with `JOB_BROKER_URL`/`REDIS_URL`, `JOB_BROKER_QUEUE`, `JOB_BROKER_POP_TIMEOUT_SECONDS`, Redis `lpush` dispatch, `brpop` worker consumption, SQLite exact job claiming, stale/canceled Redis entry skipping, broker depth reporting, independent `python -m apps.api.worker` worker loop, worker heartbeat reporting, and system-readiness Redis evidence.
- Tests for evidence retrieval, fallback rewrite, and mocked LLM rewrite.
- Arc Studio-style frontend rebuild with script page, scene index, source evidence panel, rewrite diff panel, quality, production, and YAML workspaces.

## Enterprise Features Still To Build

These are not complete yet and should not be represented as finished:

- Production database storage such as Postgres. Current storage is local SQLite, not a production deployment database.
- Celery/RQ or equivalent production scheduler and deployment package. Current queue has inline/background/external modes, a Redis list broker adapter, an independent worker loop, and a local dead-letter governance path, but not a full scheduler, autoscaling worker fleet, multi-tenant throttling, or Kubernetes/systemd/Docker deployment packaging.
- The system readiness gate can detect and report Postgres/Redis/SSO/object-storage style configuration, but it is a deployment guard and not a replacement for the actual database migration, full production scheduler, or SSO integration.
- Production-grade progress streaming and notification infrastructure. Current progress streaming is SSE over local FastAPI.
- Real LangGraph-style multi-agent orchestration.
- Production RAG with API embedding models, pgvector/Qdrant, re-ranking, and migration tooling. Current evidence retrieval has SQLite FTS5 plus local deterministic embedding vectors, not a production vector database.
- Monaco Editor plus YAML language server. Current YAML surface is a diagnostic editor shell, not Monaco yet.
- Frontend-side schema hints and guided auto-fix.
- Full LangGraph-style multi-agent scene rewrite and review loop. Current LLM scene rewrite is a constrained single-call rewrite Agent with fallback.
- Password/SSO login, realtime review presence, and external cross-user notification delivery. Current implementation has local project-member sessions, bearer-token API calls, role checks, stored notifications, comment threads, and audit events, not full enterprise authentication or realtime collaboration.
- Secret vault integration for distributed workers. Current runtime API keys are sanitized before persistence and an environment-backed `secret_ref` resolver now exists for server-side/API-worker use, but this is still not a final Vault/KMS-backed multi-worker production secret store.
- Rich file import/export beyond local multipart/chunked extraction, such as scanned-PDF OCR, quarantine workflows, object-storage ingestion isolation, and full operational import dashboards. The current chunked upload path is a local resumable session foundation that assembles into local staging and then dispatches the normal import job; the current scanner has local static validation plus an external/ClamAV-style seam, but is not a final quarantine/object-storage ingestion platform.
- Current storage boundary note: local storage plus S3/MinIO/Qiniu artifact writes and reads are implemented; CDN controls, lifecycle policies, watermarking, immutable retention, and legal/DAM delivery hardening are still not complete.
- Production delivery center with object-storage-backed delivery, PDF rendering, watermarking, approvals, e-signature, immutable retention policies, CDN download controls, and storage lifecycle rules. Current delivery download center is an artifact-store foundation with signed URLs and sha256 verification, not a final DAM/legal delivery system.
- Full legal-grade approval workflows with multi-step routing, immutable retention, external signatures, SLA escalation, and signed delivery packages. Current delivery approval center is a local role-gated approval/audit foundation, not a final legal delivery system.
- Embedding-backed long-novel retrieval and map-reduce story bible synthesis for 100k+ character manuscripts. Current LongformChunker is deterministic chapter compression and sampling, not final vector RAG or multi-agent summarization.
- Production-ready deployment packaging.
- S3/MinIO use a boto3-backed adapter and Qiniu uses a qiniu-backed Kodo adapter, while missing remote configuration still fails with 503 and does not persist fake successful packages.

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

The model connection center slice was verified with:

- Backend tests confirming `/api/model-profiles` returns sanitized environment defaults and never exposes API key values.
- Backend tests confirming `/api/model-profiles` can resolve `OPENAI_API_KEY_SECRET_REF` through server-side environment secrets without exposing the resolved key.
- Backend tests confirming `/api/model-profiles/test` passes runtime credentials to `LLMProvider` without returning the key in the response.
- Backend tests confirming `/api/model-profiles/test` resolves runtime `api_key_secret_ref` values through server-side secrets without returning the resolved key.
- Backend tests confirming connection tests use a short timeout rather than the long generation timeout.
- Backend tests confirming generation jobs can receive a runtime API profile, use the in-memory key during execution, and persist only sanitized `has_api_key` profile metadata in job payloads and project settings.
- Backend tests confirming generation jobs can receive a server-side `api_key_secret_ref`, resolve it at runtime, and persist only the reference plus sanitized `has_api_key` metadata.
- Frontend static check `npm run test:web:model` confirming the Arc Studio workbench contains the model connection panel, runtime key input, server-side secret reference input, sanitized-copy warning, model profile API calls, and runtime/public profile helpers.
- HTTP runtime probe against `http://127.0.0.1:8020/api/model-profiles/test` confirmed a missing local Ollama/vLLM endpoint returns in about 1 second instead of blocking the UI path.
- `npm run test` passed with 28 backend tests, YAML editor check, model profile workbench check, and frontend production build.
- Browser screenshot verification was attempted on `http://127.0.0.1:3020`, but `agent-browser` became unstable and produced blank/error-page captures after Next dev/build cache transitions; this slice still needs a clean browser screenshot pass in a fresh browser session before calling the UI visually verified.

The source import slice was verified with:

- Backend tests confirming `.md` manuscript import returns title, normalized text, filename, encoding, 3 detected chapters, paragraph count, and strips the top-level Markdown document title from the screenplay source body.
- Backend tests confirming `.docx` manuscript import extracts paragraphs through `python-docx`, returns `extraction_method`, document stats, 3 detected chapters, and paragraph evidence counts.
- Backend tests confirming text-based `.pdf` manuscript import extracts page text through `pypdf`, returns page stats, 3 detected chapters, and imported source text.
- Backend tests confirming unsupported extensions such as `.epub` are rejected with HTTP 422.
- HTTP runtime probe against `http://127.0.0.1:8022/api/import/source` using `examples/sample_novel.md`, confirming `chapter_count: 3`, `paragraph_count: 12`, and normalized text without the leading Markdown H1.
- HTTP runtime probe against `http://127.0.0.1:8040/api/import/source` using generated DOCX/PDF fixtures, confirming DOCX returns `extraction_method: python-docx`, `chapter_count: 3`, `paragraph_count: 12`, and PDF returns `extraction_method: pypdf`, `document_stats.pages: 1`, `chapter_count: 3`.
- Frontend static check confirming the Arc Studio workbench includes the source import API call, hidden file input, and front-rail import button.
- `python -m pytest apps/api/tests/test_pipeline.py -q` passed with 32 backend tests after DOCX/PDF import expansion.
- `npm run test` passed with 32 backend tests, YAML editor check, model/profile/import workbench check, and frontend production build.

The import job foundation slice was verified with:

- Backend tests confirming `/api/jobs/import-source` can update an existing project in `inline` mode, persist a `kind: import` job, return import metadata in `result_payload`, avoid storing source text in `request_payload`, update project source text, and persist an `import.source_completed` audit event.
- Backend tests confirming `/api/jobs/import-source` can create a project shell and wait in `external` mode until `/api/workers/run-once` executes the import payload.
- Frontend static check confirming the workbench calls `/api/jobs/import-source`, includes `startImportSourceJob`, accepts `kind: "import"` jobs, and hydrates completed import tasks through `applyImportedSource`.
- `npm run test` passed with 34 backend tests, YAML editor check, model/profile/import workbench check, and frontend production build.

The chunked import session foundation slice was verified with:

- Backend tests confirming `/api/import-sessions` can create a local chunked upload session, accept file chunks, report uploaded chunk indexes, assemble the completed file, and dispatch the normal import job flow.
- Backend tests confirming related import job and import history paths still pass together with chunked import coverage.
- Frontend static check `npm run test:web:model` confirming the Arc Studio workbench contains chunked import API helpers, threshold-based chunked upload routing, and active chunk session state wiring.
- `python -m pytest apps/api/tests/test_pipeline.py -q -k "chunked_import or import_source_job or import_history"` passed with 4 targeted backend tests.
- `npm --prefix apps/web run build` passed after the chunked import client flow was added.
- `npm run test` passed with 38 backend tests, YAML editor check, model/profile/import/version/import-history workbench check, and frontend production build.
- Sensitive-value scan over docs, API, frontend source, scripts, `.env.example`, and `package.json` found no persisted user-provided API key or base URL.
- Browser screenshot verification for the newest chunked import/history/version UI is still pending.

The import security governance slice was verified with:

- Backend tests confirming direct `.md` import returns sha256 and a clean `local-static-import-scan-v1` security report.
- Backend tests confirming a `.txt` upload with a PDF file signature is blocked with HTTP 422 before extraction.
- Backend tests confirming an external/ClamAV-style scan result can block infected direct uploads, preserve suspicious warning results, fail closed when the scanner endpoint is unavailable, or continue with warning when configured to do so.
- Backend tests confirming import jobs persist sha256 and security reports in request/result payloads without storing manuscript text.
- Backend tests confirming import jobs persist external scanner metadata through request payload, result payload, and import history.
- Backend tests confirming import history returns upload mode, sha256, and sanitized security report fields while still excluding local transient paths and manuscript text.
- Backend tests confirming chunked import completion re-runs the external scanner and blocks infected assembled files before dispatching an import job.
- Backend tests confirming chunked imports carry security report metadata through assembled upload, import job result payload, and import history.
- Frontend static check `npm run test:web:model` confirming the Arc Studio workbench includes `ImportSecurityReport`, `security_report`, security verdict helpers, and the right-rail security UI row.
- `python -m pytest apps/api/tests/test_pipeline.py -q -k "import_source_external or external_security_scan or security_scan or import_source_job_persists_external or chunked_import_session_external or import_history"` passed with 8 targeted backend tests after the external scanner seam was added.
- `npm run test` passed with 39 backend tests, YAML editor check, model/profile/import/version/import-history/security static check, and frontend production build.
- Sensitive-value scan over docs, API, frontend source, scripts, `.env.example`, and `package.json` found no persisted user-provided API key or base URL.
- Browser screenshot verification for the newest security row in the import history panel is still pending.

The B-style workbench refinement was verified with:

- Frontend production build passing after the top status bar, import readiness, scene desk bar, scene quality strip, and inspector checklist changes.
- Frontend static model/profile/import check still passing after the UI restructuring.
- Browser verification against the production preview on `http://127.0.0.1:3030`, backed by the local API on `http://127.0.0.1:8000`, confirming the page is not blank, the sample manuscript loads, chapter indexing displays evidence cards, browser errors are empty, and console output has no application error.
- Desktop and mobile screenshots were captured at `.scriptbridge_data/verify-screens/b-style-desktop.png`, `.scriptbridge_data/verify-screens/b-style-sample-index-desktop.png`, and `.scriptbridge_data/verify-screens/b-style-mobile-fixed.png`.
- A mobile topbar wrapping issue was found in the screenshot pass and fixed with nowrap/overflow rules before final verification.

The version governance slice was verified with:

- Backend tests confirming project versions can be listed with current-version metadata.
- Backend tests confirming two versions can be compared with scene-level change summaries and a YAML diff preview.
- Backend tests confirming an owner/admin-level member can restore a saved version, update the current-version pointer, and persist a `version.restored` audit event.
- Backend tests confirming insufficient permissions block version restore.
- Frontend static check confirming the Arc Studio workbench includes version summary types, list/compare/restore API calls, project-version state, comparison controls, changed-scene output, YAML diff preview, and restore controls.
- `python -m pytest apps/api/tests/test_pipeline.py -q` passed with 36 backend tests.
- `npm run test:web:model` passed after the version governance panel was added.
- `npm --prefix apps/web run build` passed after the version governance panel was added.
- `npm run test` passed with API tests, YAML editor checks, model/profile/import/version workbench check, and frontend production build.
- Browser screenshot verification for the newest version governance panel is still pending.

The project readiness gate slice was verified with:

- Backend tests confirming an empty project is blocked by missing source/version requirements.
- Backend tests confirming readiness tracks Schema, quality score, evidence coverage, production breakdown, unresolved review comments, import security history, and job queue state.
- Frontend static check confirming the Arc Studio workbench includes the project readiness API client, response types, `ReadinessPanel`, and `交付门禁` label.
- `python -m pytest apps/api/tests/test_pipeline.py -q -k "project_readiness"` passed with 2 targeted tests.
- `npm run test` passed with 41 backend tests, YAML editor check, model/profile/import/version/import-history/security/readiness static check, and frontend production build when this slice landed.
- Sensitive-value scan over docs, API, frontend source, scripts, `.env.example`, and `package.json` found no persisted user-provided API key or base URL.
- Browser screenshot verification for the readiness panel completed at `.scriptbridge_data/verify-screens/readiness-desktop.png` and `.scriptbridge_data/verify-screens/readiness-mobile-gate-visible.png`.

The system deployment readiness gate slice was verified with:

- Backend tests confirming `/api/capabilities` exposes `SystemReadinessGate`.
- Backend tests confirming `/api/system-readiness` blocks local-only defaults such as SQLite storage, background queue mode, missing server-side model secret reference, local artifact storage, and local-session auth.
- Backend tests confirming `/api/system-readiness` reports ready when configured with a Postgres-compatible `DATABASE_URL`, external queue broker, server-side model `secret_ref`, external/ClamAV import scanner, remote artifact provider, OIDC auth mode, and delivery signing secret.
- Frontend static check confirming the Arc Studio workbench includes `SystemReadinessResponse`, `getSystemReadiness`, the `SystemReadinessPanel`, `部署就绪` copy, and topbar state wiring.

The Redis broker adapter slice was verified with:

- Backend tests confirming external generation jobs push their job id into a configured Redis broker and are consumed by worker run-once.
- Backend tests confirming Redis-popped stale or canceled job ids are skipped instead of executed.
- Backend tests confirming `/api/job-queue/status` exposes `broker`, `broker_queue`, `broker_depth`, and broker errors for frontend display.
- Backend tests confirming `run_worker_loop` processes Redis-backed external jobs, records worker heartbeat, and returns completed worker statistics.
- Frontend static check confirming the Arc Studio workbench includes broker metadata types and queue panel display guards.
- Full `npm run test` passed after this slice with 77 backend tests, the YAML editor static guard, the model profile/workbench static guard, and the Next production build.

The project export governance slice was verified with:

- Backend tests confirming an empty project export is blocked by readiness, persists an `export.blocked` audit event, and appears in export history.
- Backend tests confirming a generated project can export Markdown from the current version, records version ID, readiness score, byte size, sha256, `export.created` audit metadata, and persisted project export history.
- Backend tests confirming reviewer role cannot create governed exports.
- Frontend static check confirming the Arc Studio workbench includes project export API clients, response types, `ExportGovernancePanel`, and `导出治理` label.
- `python -m pytest apps/api/tests/test_pipeline.py -q -k "project_export"` passed with 3 targeted tests.
- `npm run test` passed with 44 backend tests, YAML editor check, model/profile/import/version/import-history/security/readiness/export static check, and frontend production build.
- Browser runtime verification against `http://127.0.0.1:3060`, backed by the local API on `http://127.0.0.1:8060`, confirmed the Arc Studio/B workbench can load the sample manuscript, generate a project version through the project job path, switch to a writer session, create a governed Markdown export, show `Gate 96% / warning`, show the successful export record with file size and sha256 short fingerprint, and persist the matching `export.created` audit event.
- Desktop and mobile screenshots were captured at `.scriptbridge_data/verify-screens/export-governance-desktop.png` and `.scriptbridge_data/verify-screens/export-governance-mobile.png`.

The delivery approval center slice was verified with:

- Backend tests confirming writer role can submit the current version into delivery approval, capture version/readiness metadata, persist `approval.submitted`, notify approvers, and list the approval as pending.
- Backend tests confirming producer role can approve a submitted approval, persist `approval.approved`, store decision notes, notify the submitter, and update approval history counts.
- Backend tests confirming reviewer role cannot submit or approve delivery approvals.
- Backend tests confirming an empty project approval submission is blocked by readiness, returns HTTP 409, persists `approval.blocked`, and appears in approval history.
- Frontend static check confirming the Arc Studio workbench includes project approval API clients, response types, `ApprovalCenterPanel`, `交付审批` label, and approval role helpers.
- `python -m pytest apps/api/tests/test_pipeline.py -q -k "approval"` passed with 4 targeted backend tests.
- `npm run test` passed with 48 backend tests, YAML editor check, model/profile/import/version/import-history/security/readiness/export/approval static check, and frontend production build.
- Browser verification confirmed the delivery approval center appears in the Arc Studio/B right rail during the approval-to-package flow; desktop/mobile package-flow screenshots are stored under `.scriptbridge_data/verify-screens/delivery-package-desktop.png` and `.scriptbridge_data/verify-screens/delivery-package-mobile.png`.

The delivery package center slice was verified with:

- Backend tests confirming a producer can generate a formal package only after a linked approval is approved, and that the response contains YAML/Markdown/Fountain assets, manifest content, manifest sha256, readiness metadata, `delivery_package.created`, history, and persisted project package records.
- Backend tests confirming package creation is blocked without an approved approval when approval is required, returns HTTP 409, persists `delivery_package.blocked`, and appears in package history.
- Backend tests confirming reviewer role cannot create formal delivery packages.
- Backend tests confirming the local artifact provider can use a configured root directory and that signed downloads still validate sha256.
- Backend tests confirming local artifact roots, local path escape rejection, boto3-backed S3/MinIO adapter behavior through fake clients, qiniu-backed Kodo adapter behavior through fake clients, unsafe remote key rejection, 503 failures for missing S3/Qiniu configuration, and no persisted fake successful packages.
- Frontend static check confirming the Arc Studio workbench includes project delivery package API clients, response types, `DeliveryPackagePanel`, `交付包` label, and package role helpers.
- `python -m pytest apps/api/tests/test_pipeline.py -q -k "qiniu or artifact_provider or delivery_package"` passed with 15 targeted backend tests.
- `npm run test` passed with 61 backend tests, YAML editor check, model profile workbench check, and frontend production build.
- Browser runtime verification against the local API confirmed the delivery package center shows 4/4 signed downloads for YAML, Markdown, Fountain, and manifest assets, displays expiry and short sha256 fingerprints, and triggers the signed asset endpoint successfully.
- Desktop and mobile screenshots were captured at `.scriptbridge_data/verify-screens/delivery-download-center-desktop.png` and `.scriptbridge_data/verify-screens/delivery-download-center-mobile.png`.
