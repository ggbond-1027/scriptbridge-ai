from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from pydantic import ValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from starlette.requests import Request
from starlette.responses import StreamingResponse

from .artifact_storage import ArtifactStorageError
from .chaptering import detect_chapters
from .exporters import to_fountain, to_json, to_markdown, to_yaml
from .importer import import_source_file, scan_source_file_upload, validate_source_file_upload
from .models import (
    AddProjectMemberRequest,
    AddProjectMemberResponse,
    AuditEventsResponse,
    CapabilitiesResponse,
    CreateImportSessionRequest,
    CreateCommentRequest,
    CreateCommentReplyRequest,
    CreateCommentReplyResponse,
    CreateCommentResponse,
    CreateProjectRequest,
    CreateProjectSessionRequest,
    DeadLetterQueueResponse,
    DetectChaptersRequest,
    ExportRequest,
    GenerateRequest,
    ImportSourceResponse,
    ImportSessionStatus,
    JobQueueStatus,
    ModelProfileResponse,
    ModelProfileTestRequest,
    ModelProfileTestResponse,
    ProjectApprovalDecisionRequest,
    ProjectApprovalHistoryResponse,
    ProjectApprovalRequest,
    ProjectApprovalResponse,
    ProjectDeliveryPackageHistoryResponse,
    ProjectDeliveryPackageRequest,
    ProjectDeliveryPackageResponse,
    ProjectExportRequest,
    ProjectExportResponse,
    ProjectExportHistoryResponse,
    ProjectReadinessResponse,
    SearchEvidenceRequest,
    StartGenerationJobRequest,
    StartRewriteJobRequest,
    RewriteSceneRequest,
    ProjectSessionResponse,
    RestoreProjectVersionRequest,
    SystemReadinessResponse,
    UpdateCommentRequest,
    UpdateCommentResponse,
    UpdateJobRequest,
    NotificationsResponse,
    UpdateNotificationRequest,
    UpdateNotificationResponse,
    UpdateProjectRequest,
    ValidateRequest,
)
from .model_profiles import (
    model_profile_response,
    public_profile,
    remember_runtime_profile,
    sanitize_payload,
    test_model_profile,
)
from .pipeline import generate_screenplay, rewrite_scene as rewrite_scene_pipeline
from .queue import configured_queue_mode, dispatch_job, job_queue_status, work_one
from .sample import SAMPLE_NOVEL
from .system_readiness import system_readiness
from .storage import (
    add_project_member,
    add_project_comment,
    add_project_comment_reply,
    cancel_job,
    create_project_session,
    create_job,
    current_version,
    compare_project_versions,
    create_project_approval,
    create_project_delivery_package,
    create_project_export,
    create_project,
    decide_project_approval,
    get_project_delivery_package_asset,
    get_job,
    get_project,
    index_project_evidence,
    list_project_versions,
    list_project_approvals,
    list_project_delivery_packages,
    list_project_exports,
    list_project_audit_events,
    list_project_import_history,
    list_project_notifications,
    list_dead_letter_jobs,
    local_project_actor,
    project_readiness,
    list_jobs,
    list_projects,
    retry_job,
    resolve_project_session,
    restore_project_version,
    save_project,
    search_project_evidence,
    is_local_single_user_mode,
    update_project_comment,
    update_project_notification,
    update_project,
    require_project_permission,
)
from .validation import validate_yaml_text


app = FastAPI(title="ScriptBridge AI API", version="0.1.0")

IMPORT_UPLOAD_DIR = Path(__file__).resolve().parents[2] / ".scriptbridge_data" / "imports"
CHUNK_UPLOAD_DIR = Path(__file__).resolve().parents[2] / ".scriptbridge_data" / "chunked-imports"


def _cors_origins() -> list[str]:
    configured = os.getenv("APP_CORS_ORIGINS", "")
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    if origins:
        return origins
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3010",
        "http://127.0.0.1:3010",
        "http://localhost:3011",
        "http://127.0.0.1:3011",
    ]


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _session_actor(project_id: str, authorization: str | None) -> str | None:
    if is_local_single_user_mode():
        try:
            return local_project_actor(get_project(project_id))
        except KeyError:
            return None
    token = _bearer_token(authorization)
    if not token:
        return None
    _, member = resolve_project_session(token, project_id)
    return member.name


def _apply_session_actor(payload, project_id: str, authorization: str | None):
    actor = _session_actor(project_id, authorization)
    if not actor:
        return payload
    return payload.model_copy(update={"actor": actor})


def _apply_session_author(payload, project_id: str, authorization: str | None):
    actor = _session_actor(project_id, authorization)
    if not actor:
        return payload
    return payload.model_copy(update={"author": actor})


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/capabilities")
def capabilities() -> CapabilitiesResponse:
    return CapabilitiesResponse(
        pipeline_agents=[
            "ChapterIndexer",
            "LongformChunker",
            "StoryBibleAgent",
            "TimelineAgent",
            "ScenePlanner",
            "ScriptWriter",
            "LocalHashEmbeddings",
            "ContinuityChecker",
            "ProductionBreakdownAgent",
            "DeliveryArtifactStorage",
            "SystemReadinessGate",
        ],
        open_source_stack=[
            "FastAPI",
            "Pydantic",
            "PyYAML",
            "jsonschema",
            "httpx",
            "SQLite FTS5",
            "Local artifact store",
            "boto3 S3/MinIO artifact adapter",
            "qiniu Kodo artifact adapter",
            "System readiness gate",
            "Next.js",
            "React",
            "Tailwind CSS",
            "lucide-react",
        ],
    )


@app.get("/api/model-profiles")
def model_profiles_route() -> ModelProfileResponse:
    return model_profile_response()


@app.post("/api/model-profiles/test")
async def test_model_profile_route(payload: ModelProfileTestRequest) -> ModelProfileTestResponse:
    return await test_model_profile(payload.profile)


@app.get("/api/system-readiness")
def system_readiness_route() -> SystemReadinessResponse:
    return system_readiness()


@app.get("/api/sample")
def sample() -> dict[str, str]:
    return {"title": "雨夜来信", "text": SAMPLE_NOVEL}


@app.post("/api/import/source")
async def import_source(file: UploadFile = File(...)) -> ImportSourceResponse:
    try:
        content = await file.read()
        return import_source_file(file.filename or "source.txt", file.content_type or "text/plain", content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/import-sessions")
def create_import_session(payload: CreateImportSessionRequest) -> ImportSessionStatus:
    try:
        safe_name = validate_source_file_upload(payload.filename, b"x")
        if payload.project_id:
            get_project(payload.project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {payload.project_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    session = ImportSessionStatus(
        id=f"upload_{uuid4().hex[:12]}",
        filename=safe_name,
        content_type=payload.content_type or "application/octet-stream",
        size_bytes=payload.size_bytes,
        total_chunks=payload.total_chunks,
        project_id=payload.project_id,
        actor=payload.actor.strip() or "system",
        status="pending",
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    _save_import_session(session)
    return session


@app.get("/api/import-sessions/{session_id}")
def import_session_status(session_id: str) -> ImportSessionStatus:
    try:
        return _load_import_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Import session not found: {session_id}") from exc


@app.put("/api/import-sessions/{session_id}/chunks/{chunk_index}")
async def upload_import_session_chunk(session_id: str, chunk_index: int, request: Request) -> ImportSessionStatus:
    try:
        session = _load_import_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Import session not found: {session_id}") from exc
    if session.status != "pending":
        raise HTTPException(status_code=409, detail="Import session is already completed.")
    if chunk_index < 0 or chunk_index >= session.total_chunks:
        raise HTTPException(status_code=422, detail="Chunk index is out of range.")
    chunk = await request.body()
    if not chunk:
        raise HTTPException(status_code=422, detail="Chunk body is empty.")

    session_dir = _import_session_dir(session.id)
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / f"{chunk_index:06d}.part").write_bytes(chunk)
    session.uploaded_chunks = _uploaded_chunk_indexes(session.id)
    session.uploaded_count = len(session.uploaded_chunks)
    session.updated_at = _now_iso()
    _save_import_session(session)
    return session


@app.post("/api/import-sessions/{session_id}/complete")
async def complete_import_session(session_id: str, background_tasks: BackgroundTasks):
    try:
        session = _load_import_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Import session not found: {session_id}") from exc
    if session.status == "completed":
        raise HTTPException(status_code=409, detail="Import session is already completed.")
    missing = [index for index in range(session.total_chunks) if index not in set(session.uploaded_chunks)]
    if missing:
        raise HTTPException(status_code=409, detail=f"Missing chunks: {missing[:10]}")

    assembled = _assemble_import_session_file(session)
    try:
        security_report = scan_source_file_upload(session.filename, session.content_type, assembled.read_bytes())
        if security_report.verdict == "blocked":
            raise ValueError("Source file security scan blocked upload: " + " / ".join(security_report.blocked_reasons))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if session.project_id:
        try:
            project = get_project(session.project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Project not found: {session.project_id}") from exc
    else:
        project = create_project(CreateProjectRequest(title=Path(session.filename).stem or "Imported source"))

    job = create_job(
        project.id,
        "import",
        queue_mode=configured_queue_mode(),
        request_payload={
            "filename": session.filename,
            "content_type": session.content_type,
            "size_bytes": session.size_bytes,
            "sha256": security_report.sha256,
            "security_report": security_report.model_dump(mode="json"),
            "file_path": str(assembled),
            "actor": session.actor,
            "upload_session_id": session.id,
            "upload_mode": "chunked",
        },
    )
    project.last_job_id = job.id
    save_project(project)
    session.status = "completed"
    session.project_id = project.id
    session.sha256 = security_report.sha256
    session.security_report = security_report
    session.updated_at = _now_iso()
    _save_import_session(session)
    dispatched = await dispatch_job(job, background_tasks=background_tasks)
    return {"session": session, "job": dispatched}


@app.post("/api/jobs/import-source")
async def start_import_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    actor: str = Form(default="system"),
):
    try:
        content = await file.read()
        safe_name = validate_source_file_upload(file.filename or "source.txt", content)
        security_report = scan_source_file_upload(safe_name, file.content_type or "application/octet-stream", content)
        if security_report.verdict == "blocked":
            raise ValueError("Source file security scan blocked upload: " + " / ".join(security_report.blocked_reasons))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if project_id:
        try:
            project = get_project(project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc
    else:
        project = create_project(CreateProjectRequest(title=Path(safe_name).stem or "Imported source"))

    IMPORT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}_{safe_name}"
    file_path = IMPORT_UPLOAD_DIR / stored_name
    file_path.write_bytes(content)
    job = create_job(
        project.id,
        "import",
        queue_mode=configured_queue_mode(),
        request_payload={
            "filename": safe_name,
            "content_type": file.content_type or "application/octet-stream",
            "size_bytes": len(content),
            "sha256": security_report.sha256,
            "security_report": security_report.model_dump(mode="json"),
            "file_path": str(file_path),
            "actor": actor,
            "upload_mode": "multipart",
        },
    )
    project.last_job_id = job.id
    save_project(project)
    return await dispatch_job(job, background_tasks=background_tasks)


@app.get("/api/projects")
def projects():
    return {"projects": list_projects()}


@app.post("/api/projects")
def create_project_route(payload: CreateProjectRequest):
    return create_project(payload)


@app.get("/api/projects/{project_id}")
def project_detail(project_id: str, authorization: str | None = Header(default=None)):
    try:
        project = get_project(project_id)
        actor = _session_actor(project_id, authorization)
        if actor:
            project.notifications = [item for item in project.notifications if item.recipient == actor]
        return project
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.patch("/api/projects/{project_id}")
def update_project_route(project_id: str, payload: UpdateProjectRequest):
    try:
        return update_project(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc


@app.get("/api/projects/{project_id}/versions")
def project_versions(project_id: str):
    try:
        return {"versions": list_project_versions(project_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc


@app.get("/api/projects/{project_id}/versions/compare")
def project_version_compare(project_id: str, base_version_id: str, target_version_id: str):
    try:
        return compare_project_versions(project_id, base_version_id, target_version_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project or version not found: {exc}") from exc


@app.get("/api/projects/{project_id}/import-history")
def project_import_history(project_id: str, limit: int = 30):
    try:
        return list_project_import_history(project_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc


@app.get("/api/projects/{project_id}/readiness")
def project_readiness_route(project_id: str) -> ProjectReadinessResponse:
    try:
        return project_readiness(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc


@app.get("/api/projects/{project_id}/exports")
def project_exports(project_id: str, limit: int = 30) -> ProjectExportHistoryResponse:
    try:
        return list_project_exports(project_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc


@app.post("/api/projects/{project_id}/exports")
def create_project_export_route(
    project_id: str,
    payload: ProjectExportRequest,
    authorization: str | None = Header(default=None),
) -> ProjectExportResponse:
    try:
        payload = _apply_session_actor(payload, project_id, authorization)
        _, export_record, content, readiness, audit_event = create_project_export(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project or version not found: {exc}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    status_code = 409 if export_record.status == "blocked" else 200
    if export_record.status == "blocked":
        raise HTTPException(
            status_code=status_code,
            detail={
                "message": "Project export blocked by readiness gate.",
                "export": export_record.model_dump(mode="json"),
                "readiness": readiness.model_dump(mode="json"),
                "audit_event": audit_event.model_dump(mode="json"),
            },
        )
    return ProjectExportResponse(export=export_record, content=content, readiness=readiness, audit_event=audit_event)


@app.get("/api/projects/{project_id}/approvals")
def project_approvals(project_id: str, limit: int = 30) -> ProjectApprovalHistoryResponse:
    try:
        return list_project_approvals(project_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc


@app.post("/api/projects/{project_id}/approvals")
def create_project_approval_route(
    project_id: str,
    payload: ProjectApprovalRequest,
    authorization: str | None = Header(default=None),
) -> ProjectApprovalResponse:
    try:
        payload = _apply_session_actor(payload, project_id, authorization)
        project, approval, readiness, audit_event, notifications = create_project_approval(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project or version not found: {exc}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if approval.status == "blocked":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Project approval blocked by readiness gate.",
                "approval": approval.model_dump(mode="json"),
                "readiness": readiness.model_dump(mode="json"),
                "audit_event": audit_event.model_dump(mode="json"),
            },
        )
    return ProjectApprovalResponse(
        project=project,
        approval=approval,
        readiness=readiness,
        audit_event=audit_event,
        notifications=notifications,
    )


@app.post("/api/projects/{project_id}/approvals/{approval_id}/decision")
def decide_project_approval_route(
    project_id: str,
    approval_id: str,
    payload: ProjectApprovalDecisionRequest,
    authorization: str | None = Header(default=None),
) -> ProjectApprovalResponse:
    try:
        payload = _apply_session_actor(payload, project_id, authorization)
        project, approval, readiness, audit_event, notifications = decide_project_approval(project_id, approval_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project or approval not found: {exc}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ProjectApprovalResponse(
        project=project,
        approval=approval,
        readiness=readiness,
        audit_event=audit_event,
        notifications=notifications,
    )


@app.get("/api/projects/{project_id}/delivery-packages")
def project_delivery_packages(
    project_id: str,
    limit: int = 30,
    actor: str | None = None,
    authorization: str | None = Header(default=None),
) -> ProjectDeliveryPackageHistoryResponse:
    try:
        session_actor = _session_actor(project_id, authorization)
        package_actor = session_actor or actor
        if package_actor:
            require_project_permission(get_project(project_id), package_actor, "package_delivery")
        return list_project_delivery_packages(project_id, limit=limit, include_downloads=bool(package_actor))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/delivery-packages")
def create_project_delivery_package_route(
    project_id: str,
    payload: ProjectDeliveryPackageRequest,
    authorization: str | None = Header(default=None),
) -> ProjectDeliveryPackageResponse:
    try:
        payload = _apply_session_actor(payload, project_id, authorization)
        project, package, assets, readiness, audit_event = create_project_delivery_package(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project, version, or approval not found: {exc}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ArtifactStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if package.status == "blocked":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Project delivery package blocked by approval or readiness gate.",
                "package": package.model_dump(mode="json"),
                "assets": [asset.model_dump(mode="json") for asset in assets],
                "readiness": readiness.model_dump(mode="json"),
                "audit_event": audit_event.model_dump(mode="json"),
            },
        )
    return ProjectDeliveryPackageResponse(
        project=project,
        package=package,
        assets=assets,
        readiness=readiness,
        audit_event=audit_event,
    )


@app.get("/api/projects/{project_id}/delivery-packages/{package_id}/assets/{asset_sha256}")
def download_project_delivery_package_asset_route(
    project_id: str,
    package_id: str,
    asset_sha256: str,
    token: str = Query(default=""),
) -> Response:
    try:
        _, asset, content = get_project_delivery_package_asset(project_id, package_id, asset_sha256, token)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Delivery package asset not found: {exc}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ArtifactStorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    encoded_filename = quote(asset.filename)
    return Response(
        content=content,
        media_type=asset.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=utf-8''{encoded_filename}",
            "X-Content-SHA256": asset.sha256,
        },
    )


@app.post("/api/projects/{project_id}/versions/{version_id}/restore")
def restore_project_version_route(
    project_id: str,
    version_id: str,
    payload: RestoreProjectVersionRequest,
    authorization: str | None = Header(default=None),
):
    try:
        payload = _apply_session_actor(payload, project_id, authorization)
        return restore_project_version(project_id, version_id, payload.actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project or version not found: {exc}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/api/auth/sessions")
def create_project_session_route(payload: CreateProjectSessionRequest) -> ProjectSessionResponse:
    try:
        project, session, member = create_project_session(payload.project_id, payload.member_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {payload.project_id}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ProjectSessionResponse(session=session, token=session.token, member=member, project=project)


@app.post("/api/projects/{project_id}/members")
def add_project_member_route(
    project_id: str,
    payload: AddProjectMemberRequest,
    authorization: str | None = Header(default=None),
) -> AddProjectMemberResponse:
    try:
        payload = _apply_session_actor(payload, project_id, authorization)
        project, member, audit_event = add_project_member(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AddProjectMemberResponse(project=project, member=member, audit_event=audit_event)


@app.post("/api/projects/{project_id}/comments")
def create_project_comment(
    project_id: str,
    payload: CreateCommentRequest,
    authorization: str | None = Header(default=None),
) -> CreateCommentResponse:
    try:
        payload = _apply_session_author(payload, project_id, authorization)
        project, comment, audit_event, notifications = add_project_comment(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CreateCommentResponse(project=project, comment=comment, audit_event=audit_event, notifications=notifications)


@app.patch("/api/projects/{project_id}/comments/{comment_id}")
def update_project_comment_route(
    project_id: str,
    comment_id: str,
    payload: UpdateCommentRequest,
    authorization: str | None = Header(default=None),
) -> UpdateCommentResponse:
    try:
        payload = _apply_session_author(payload, project_id, authorization)
        project, comment, audit_event = update_project_comment(project_id, comment_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project or comment not found: {exc}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return UpdateCommentResponse(project=project, comment=comment, audit_event=audit_event)


@app.post("/api/projects/{project_id}/comments/{comment_id}/replies")
def create_project_comment_reply(
    project_id: str,
    comment_id: str,
    payload: CreateCommentReplyRequest,
    authorization: str | None = Header(default=None),
) -> CreateCommentReplyResponse:
    try:
        payload = _apply_session_author(payload, project_id, authorization)
        project, comment, reply, audit_event, notifications = add_project_comment_reply(
            project_id,
            comment_id,
            payload.author,
            payload.body,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project or comment not found: {exc}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CreateCommentReplyResponse(
        project=project,
        comment=comment,
        reply=reply,
        audit_event=audit_event,
        notifications=notifications,
    )


@app.get("/api/projects/{project_id}/audit-events")
def project_audit_events(
    project_id: str,
    event_type: str | None = None,
    actor: str | None = None,
    limit: int = 50,
) -> AuditEventsResponse:
    try:
        events = list_project_audit_events(project_id, event_type=event_type, actor=actor, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc
    return AuditEventsResponse(audit_events=events)


@app.get("/api/projects/{project_id}/notifications")
def project_notifications(
    project_id: str,
    recipient: str | None = None,
    unread_only: bool = False,
    limit: int = 50,
    authorization: str | None = Header(default=None),
) -> NotificationsResponse:
    try:
        session_actor = _session_actor(project_id, authorization)
        if session_actor:
            recipient = session_actor
        notifications = list_project_notifications(
            project_id,
            recipient=recipient,
            unread_only=unread_only,
            limit=limit,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc
    return NotificationsResponse(notifications=notifications)


@app.patch("/api/projects/{project_id}/notifications/{notification_id}")
def update_project_notification_route(
    project_id: str,
    notification_id: str,
    payload: UpdateNotificationRequest,
    authorization: str | None = Header(default=None),
) -> UpdateNotificationResponse:
    try:
        payload = _apply_session_actor(payload, project_id, authorization)
        project, notification, audit_event = update_project_notification(project_id, notification_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project or notification not found: {exc}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return UpdateNotificationResponse(project=project, notification=notification, audit_event=audit_event)


@app.post("/api/jobs/generate")
async def start_generation_job(payload: StartGenerationJobRequest, background_tasks: BackgroundTasks):
    try:
        project = get_project(payload.project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {payload.project_id}") from exc
    if not project.source_text.strip():
        raise HTTPException(status_code=422, detail="Project source_text is empty.")
    job = create_job(
        project.id,
        "generate",
        queue_mode=configured_queue_mode(),
        request_payload=sanitize_payload(payload),
    )
    remember_runtime_profile(job.id, payload.model_profile)
    if payload.model_profile:
        project.settings.model_provider = payload.model_profile.provider
        project.settings.model_profile = public_profile(payload.model_profile)
    project.last_job_id = job.id
    save_project(project)
    return await dispatch_job(job, background_tasks=background_tasks)


@app.post("/api/jobs/rewrite")
async def start_rewrite_job(
    payload: StartRewriteJobRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
):
    try:
        payload = _apply_session_actor(payload, payload.project_id, authorization)
        project = get_project(payload.project_id)
        require_project_permission(project, payload.actor, "rewrite")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {payload.project_id}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not current_version(project):
        raise HTTPException(status_code=422, detail="Project has no screenplay version to rewrite.")
    job = create_job(
        project.id,
        "rewrite",
        queue_mode=configured_queue_mode(),
        request_payload=sanitize_payload(payload),
    )
    remember_runtime_profile(job.id, payload.model_profile)
    project.last_job_id = job.id
    save_project(project)
    return await dispatch_job(job, background_tasks=background_tasks)


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str):
    try:
        return get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}") from exc


@app.get("/api/job-queue/status")
def queue_status() -> JobQueueStatus:
    return job_queue_status()


@app.get("/api/job-queue/dead-letter")
def dead_letter_queue(limit: int = 20) -> DeadLetterQueueResponse:
    jobs = list_dead_letter_jobs(limit=limit)
    return DeadLetterQueueResponse(
        jobs=jobs,
        total=len(jobs),
        failed=sum(1 for job in jobs if job.status == "failed"),
        dead_lettered=sum(1 for job in jobs if job.status == "dead_lettered"),
    )


@app.post("/api/jobs/{job_id}")
async def update_job_route(job_id: str, payload: UpdateJobRequest, background_tasks: BackgroundTasks):
    try:
        job = get_job(job_id)
        project = get_project(job.project_id)
        require_project_permission(project, payload.actor, "manage_members")
        if payload.action == "cancel":
            return cancel_job(job_id, payload.actor)
        retried = retry_job(job_id, payload.actor)
        return await dispatch_job(retried, background_tasks=background_tasks)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Job not found: {exc}") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/workers/run-once")
async def worker_run_once():
    job = await work_one()
    return {"job": job, "queue": job_queue_status()}


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    try:
        get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}") from exc

    async def stream():
        last_payload = ""
        while True:
            try:
                job = get_job(job_id)
            except KeyError:
                yield _sse_event({"status": "missing", "job_id": job_id})
                break
            payload = json.dumps(job.model_dump(mode="json"), ensure_ascii=False)
            if payload != last_payload:
                yield f"event: job\n"
                yield f"data: {payload}\n\n"
                last_payload = payload
            if job.status in {"succeeded", "failed", "dead_lettered"}:
                break
            await asyncio.sleep(0.6)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/projects/{project_id}/jobs")
def project_jobs(project_id: str):
    try:
        get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc
    return {"jobs": list_jobs(project_id)}


@app.post("/api/projects/{project_id}/evidence/search")
def project_evidence_search(project_id: str, payload: SearchEvidenceRequest):
    try:
        project = get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}") from exc
    current = project.versions[-1] if project.versions else None
    if current:
        index_project_evidence(project.id, current.screenplay.chapters)
    return {"evidence": search_project_evidence(project.id, payload.query, payload.limit)}


@app.post("/api/detect-chapters")
def detect(payload: DetectChaptersRequest) -> dict[str, object]:
    chapters = detect_chapters(payload.text)
    return {"chapters": [chapter.model_dump(mode="json") for chapter in chapters], "count": len(chapters)}


@app.post("/api/generate")
async def generate(payload: GenerateRequest):
    return await generate_screenplay(payload.text, payload.title, payload.style, payload.use_llm, payload.model_profile)


@app.post("/api/rewrite-scene")
async def rewrite_scene_route(payload: RewriteSceneRequest):
    return await rewrite_scene_pipeline(
        payload.screenplay,
        payload.scene_id,
        payload.instruction,
        payload.mode,
        payload.use_llm,
        payload.model_profile,
    )


@app.post("/api/validate")
def validate(payload: ValidateRequest):
    return validate_yaml_text(payload.yaml_text)


@app.post("/api/export/{format_name}")
def export(format_name: str, payload: ExportRequest):
    screenplay = payload.screenplay
    if format_name == "yaml":
        return PlainTextResponse(to_yaml(screenplay), media_type="application/x-yaml")
    if format_name == "json":
        return PlainTextResponse(to_json(screenplay), media_type="application/json")
    if format_name == "markdown":
        return PlainTextResponse(to_markdown(screenplay), media_type="text/markdown")
    if format_name == "fountain":
        return PlainTextResponse(to_fountain(screenplay), media_type="text/plain")
    raise HTTPException(status_code=404, detail=f"Unsupported export format: {format_name}")


def _sse_event(payload: dict[str, object]) -> str:
    return f"event: job\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _now_iso() -> str:
    from .models import utc_now

    return utc_now()


def _import_session_dir(session_id: str) -> Path:
    return CHUNK_UPLOAD_DIR / session_id


def _import_session_meta_path(session_id: str) -> Path:
    return _import_session_dir(session_id) / "session.json"


def _save_import_session(session: ImportSessionStatus) -> None:
    session_dir = _import_session_dir(session.id)
    session_dir.mkdir(parents=True, exist_ok=True)
    _import_session_meta_path(session.id).write_text(
        json.dumps(session.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_import_session(session_id: str) -> ImportSessionStatus:
    path = _import_session_meta_path(session_id)
    if not path.exists():
        raise KeyError(session_id)
    try:
        session = ImportSessionStatus.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise KeyError(session_id) from exc
    session.uploaded_chunks = _uploaded_chunk_indexes(session.id)
    session.uploaded_count = len(session.uploaded_chunks)
    return session


def _uploaded_chunk_indexes(session_id: str) -> list[int]:
    session_dir = _import_session_dir(session_id)
    if not session_dir.exists():
        return []
    indexes: list[int] = []
    for path in session_dir.glob("*.part"):
        try:
            indexes.append(int(path.stem))
        except ValueError:
            continue
    return sorted(indexes)


def _assemble_import_session_file(session: ImportSessionStatus) -> Path:
    IMPORT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}_{session.filename}"
    assembled = IMPORT_UPLOAD_DIR / stored_name
    with assembled.open("wb") as target:
        for index in range(session.total_chunks):
            part_path = _import_session_dir(session.id) / f"{index:06d}.part"
            target.write(part_path.read_bytes())
    if assembled.stat().st_size != session.size_bytes:
        assembled.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409,
            detail=f"Assembled file size mismatch: expected {session.size_bytes}, got {assembled.stat().st_size if assembled.exists() else 0}.",
        )
    return assembled
