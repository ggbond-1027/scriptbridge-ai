from __future__ import annotations

import base64
import hmac
import json
import hashlib
import os
import secrets
import sqlite3
import time
from difflib import unified_diff
from pathlib import Path
from uuid import uuid4

from .artifact_storage import configured_delivery_artifact_provider_name, delivery_artifact_provider
from .embeddings import cosine_similarity, embed_text
from .exporters import to_fountain, to_json, to_markdown, to_yaml
from .models import (
    AddProjectMemberRequest,
    AuditEvent,
    Chapter,
    CommentReply,
    CreateCommentRequest,
    CreateProjectRequest,
    ExportFormat,
    ImportHistoryItem,
    ImportHistoryResponse,
    ImportSecurityReport,
    JobEvent,
    JobRecord,
    JobQueueMode,
    JobSummary,
    JobStatus,
    WorkerStatus,
    ProjectComment,
    ProjectApprovalDecisionRequest,
    ProjectApprovalHistoryResponse,
    ProjectApprovalRecord,
    ProjectApprovalRequest,
    ProjectDeliveryPackageAsset,
    ProjectDeliveryPackageHistoryResponse,
    ProjectDeliveryPackageRecord,
    ProjectDeliveryPackageRequest,
    ProjectExportHistoryResponse,
    ProjectExportRecord,
    ProjectExportRequest,
    ProjectMember,
    ProjectNotification,
    ProjectRecord,
    ProjectReadinessCheck,
    ProjectReadinessResponse,
    ProjectSession,
    ReadinessStatus,
    ProjectSummary,
    ProjectVersion,
    ProjectVersionSummary,
    VersionCompareResponse,
    VersionSceneChange,
    SourceEvidence,
    UpdateNotificationRequest,
    UpdateCommentRequest,
    UpdateProjectRequest,
    utc_now,
)


DATA_DIR = Path(__file__).resolve().parents[2] / ".scriptbridge_data"
PROJECTS_DIR = DATA_DIR / "projects"
JOBS_DIR = DATA_DIR / "jobs"
DB_PATH = DATA_DIR / "scriptbridge.sqlite3"
DELIVERY_DOWNLOAD_TTL_SECONDS = 60 * 60
STRICT_AUTH_MODES = {"strict-rbac", "rbac", "enterprise"}
LOCAL_PROJECT_OWNER_NAME = "项目负责人"


def is_local_single_user_mode() -> bool:
    """Default local workbench mode: one user owns the whole project."""
    return os.getenv("AUTH_MODE", "local-single-user").strip().lower() not in STRICT_AUTH_MODES

ROLE_PERMISSIONS = {
    "owner": {
        "manage_members",
        "comment",
        "resolve",
        "reply",
        "read_notifications",
        "rewrite",
        "export",
        "submit_approval",
        "approve_delivery",
        "package_delivery",
    },
    "admin": {
        "manage_members",
        "comment",
        "resolve",
        "reply",
        "read_notifications",
        "rewrite",
        "export",
        "submit_approval",
        "approve_delivery",
        "package_delivery",
    },
    "writer": {"comment", "resolve", "reply", "read_notifications", "rewrite", "export", "submit_approval"},
    "reviewer": {"comment", "resolve", "reply", "read_notifications"},
    "producer": {"comment", "resolve", "reply", "read_notifications", "export", "approve_delivery", "package_delivery"},
    "viewer": {"read_notifications"},
}


def _default_members() -> list[ProjectMember]:
    return [
        ProjectMember(id="member_owner", name="项目负责人", role="owner"),
        ProjectMember(id="member_editor", name="主编", role="admin"),
        ProjectMember(id="member_reviewer", name="审阅者", role="reviewer"),
        ProjectMember(id="member_writer", name="编剧", role="writer"),
        ProjectMember(id="member_producer", name="制片", role="producer"),
        ProjectMember(id="member_producer_reviewer", name="制片审阅", role="producer"),
    ]


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    _init_db()
    _migrate_json_files_once()


def create_project(payload: CreateProjectRequest) -> ProjectRecord:
    project = ProjectRecord(
        id=f"proj_{uuid4().hex[:12]}",
        title=payload.title.strip() or "未命名改编项目",
        source_text=payload.source_text,
        settings=payload.settings,
        members=_default_members(),
    )
    save_project(project)
    return project


def update_project(project_id: str, payload: UpdateProjectRequest) -> ProjectRecord:
    project = get_project(project_id)
    if payload.title is not None:
        project.title = payload.title.strip() or project.title
    if payload.source_text is not None:
        project.source_text = payload.source_text
    if payload.settings is not None:
        project.settings = payload.settings
    project.updated_at = utc_now()
    save_project(project)
    return project


def list_projects() -> list[ProjectSummary]:
    ensure_data_dirs()
    summaries: list[ProjectSummary] = []
    with _connect() as conn:
        rows = conn.execute("SELECT payload FROM projects ORDER BY updated_at DESC").fetchall()
    for row in rows:
        project = ProjectRecord.model_validate(json.loads(row["payload"]))
        current = current_version(project)
        summaries.append(
            ProjectSummary(
                id=project.id,
                title=project.title,
                updated_at=project.updated_at,
                source_length=len(project.source_text),
                version_count=len(project.versions),
                quality_score=current.screenplay.quality_report.overall_score if current else None,
                validation_valid=current.validation.valid if current else None,
                last_job_id=project.last_job_id,
            )
        )
    return summaries


def get_project(project_id: str) -> ProjectRecord:
    ensure_data_dirs()
    with _connect() as conn:
        row = conn.execute("SELECT payload FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        raise KeyError(project_id)
    project = ProjectRecord.model_validate(json.loads(row["payload"]))
    _ensure_project_defaults(project)
    return project


def save_project(project: ProjectRecord) -> None:
    ensure_data_dirs()
    _ensure_project_defaults(project)
    project.updated_at = utc_now()
    payload = json.dumps(project.model_dump(mode="json"), ensure_ascii=False)
    current = current_version(project)
    quality_score = current.screenplay.quality_report.overall_score if current else None
    validation_valid = 1 if current and current.validation.valid else 0 if current else None
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO projects (
                id, title, source_length, updated_at, version_count,
                quality_score, validation_valid, last_job_id, payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                source_length = excluded.source_length,
                updated_at = excluded.updated_at,
                version_count = excluded.version_count,
                quality_score = excluded.quality_score,
                validation_valid = excluded.validation_valid,
                last_job_id = excluded.last_job_id,
                payload = excluded.payload
            """,
            (
                project.id,
                project.title,
                len(project.source_text),
                project.updated_at,
                len(project.versions),
                quality_score,
                validation_valid,
                project.last_job_id,
                payload,
            ),
        )


def _ensure_project_defaults(project: ProjectRecord) -> None:
    if not project.members:
        project.members = _default_members()
    if project.exports is None:
        project.exports = []
    if project.approvals is None:
        project.approvals = []
    if project.delivery_packages is None:
        project.delivery_packages = []


def _member_for(project: ProjectRecord, name: str) -> ProjectMember | None:
    normalized = name.strip()
    return next((member for member in project.members if member.active and member.name == normalized), None)


def _local_owner_member(project: ProjectRecord) -> ProjectMember:
    owner = next((member for member in project.members if member.active and member.role in {"owner", "admin"}), None)
    if owner:
        return owner
    if project.members:
        return project.members[0]
    project.members = _default_members()
    return project.members[0]


def local_project_actor(project: ProjectRecord) -> str:
    return _local_owner_member(project).name


def _require_permission(project: ProjectRecord, actor: str, permission: str) -> ProjectMember:
    if is_local_single_user_mode():
        return _local_owner_member(project)
    member = _member_for(project, actor)
    if not member:
        raise PermissionError(f"Project member not found: {actor}")
    if permission not in ROLE_PERMISSIONS.get(member.role, set()):
        raise PermissionError(f"{member.role} cannot {permission}.")
    return member


def require_project_permission(project: ProjectRecord, actor: str, permission: str) -> ProjectMember:
    return _require_permission(project, actor, permission)


def create_project_session(project_id: str, member_name: str) -> tuple[ProjectRecord, ProjectSession, ProjectMember]:
    project = get_project(project_id)
    member = _member_for(project, member_name)
    if not member:
        raise PermissionError(f"Project member not found: {member_name}")
    session = ProjectSession(
        id=f"sess_{uuid4().hex[:12]}",
        token=secrets.token_urlsafe(32),
        project_id=project.id,
        member_id=member.id,
        member_name=member.name,
        role=member.role,
    )
    save_project_session(session)
    return project, session, member


def save_project_session(session: ProjectSession) -> None:
    ensure_data_dirs()
    payload = json.dumps(session.model_dump(mode="json"), ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, token, project_id, member_id, member_name, active, updated_at, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                token = excluded.token,
                project_id = excluded.project_id,
                member_id = excluded.member_id,
                member_name = excluded.member_name,
                active = excluded.active,
                updated_at = excluded.updated_at,
                payload = excluded.payload
            """,
            (
                session.id,
                session.token,
                session.project_id,
                session.member_id,
                session.member_name,
                1 if session.active else 0,
                session.last_seen_at,
                payload,
            ),
        )


def resolve_project_session(token: str, project_id: str) -> tuple[ProjectSession, ProjectMember]:
    cleaned = token.strip()
    if not cleaned:
        raise PermissionError("Missing session token.")
    ensure_data_dirs()
    with _connect() as conn:
        row = conn.execute("SELECT payload FROM sessions WHERE token = ? AND active = 1", (cleaned,)).fetchone()
    if not row:
        raise PermissionError("Invalid session token.")
    session = ProjectSession.model_validate(json.loads(row["payload"]))
    if session.project_id != project_id:
        raise PermissionError("Session does not belong to this project.")
    project = get_project(project_id)
    member = _member_for(project, session.member_name)
    if not member or member.id != session.member_id:
        raise PermissionError("Session member is no longer active in this project.")
    session.role = member.role
    session.last_seen_at = utc_now()
    save_project_session(session)
    return session, member


def _add_audit_event(
    project: ProjectRecord,
    actor: str,
    event_type: str,
    target_type: str,
    target_id: str,
    summary: str,
    metadata: dict[str, str] | None = None,
) -> AuditEvent:
    audit_event = AuditEvent(
        id=f"audit_{uuid4().hex[:12]}",
        actor=actor,
        event_type=event_type,
        target_type=target_type,
        target_id=target_id,
        summary=summary,
        metadata=metadata or {},
    )
    project.audit_events.insert(0, audit_event)
    return audit_event


def add_audit_event(
    project: ProjectRecord,
    actor: str,
    event_type: str,
    target_type: str,
    target_id: str,
    summary: str,
    metadata: dict[str, str] | None = None,
) -> AuditEvent:
    return _add_audit_event(project, actor, event_type, target_type, target_id, summary, metadata)


def _add_notification(
    project: ProjectRecord,
    recipient: str | None,
    actor: str,
    event_type: str,
    target_type: str,
    target_id: str,
    summary: str,
    metadata: dict[str, str] | None = None,
) -> ProjectNotification | None:
    cleaned_recipient = recipient.strip() if recipient else ""
    if not cleaned_recipient or cleaned_recipient == actor:
        return None
    if not _member_for(project, cleaned_recipient):
        return None
    notification = ProjectNotification(
        id=f"note_{uuid4().hex[:12]}",
        recipient=cleaned_recipient,
        actor=actor,
        event_type=event_type,
        target_type=target_type,
        target_id=target_id,
        summary=summary,
        metadata=metadata or {},
    )
    project.notifications.insert(0, notification)
    return notification


def add_project_version(project: ProjectRecord, version: ProjectVersion) -> ProjectRecord:
    version.screenplay.project.id = project.id
    project.versions.append(version)
    project.current_version_id = version.id
    save_project(project)
    return project


def add_project_member(
    project_id: str,
    payload: AddProjectMemberRequest,
) -> tuple[ProjectRecord, ProjectMember, AuditEvent]:
    project = get_project(project_id)
    actor = payload.actor.strip() or "项目负责人"
    _require_permission(project, actor, "manage_members")
    name = payload.name.strip()
    if not name:
        raise ValueError("Member name is empty.")
    member = _member_for(project, name)
    if member:
        member.role = payload.role
        member.active = True
    else:
        member = ProjectMember(id=f"member_{uuid4().hex[:12]}", name=name, role=payload.role)
        project.members.append(member)
    audit_event = _add_audit_event(
        project,
        actor=actor,
        event_type="member.added",
        target_type="member",
        target_id=member.id,
        summary=f"{actor} 将 {member.name} 加入项目并设置为 {member.role}。",
        metadata={"member_id": member.id, "member_name": member.name, "role": member.role},
    )
    save_project(project)
    return project, member, audit_event


def add_project_comment(
    project_id: str,
    payload: CreateCommentRequest,
) -> tuple[ProjectRecord, ProjectComment, AuditEvent, list[ProjectNotification]]:
    project = get_project(project_id)
    actor = payload.author.strip() or "审阅者"
    _require_permission(project, actor, "comment")
    assignee = payload.assignee.strip() if payload.assignee else None
    comment = ProjectComment(
        id=f"comment_{uuid4().hex[:12]}",
        scene_id=payload.scene_id,
        author=actor,
        assignee=assignee or None,
        body=payload.body.strip(),
        status=payload.status,
    )
    if not comment.body:
        raise ValueError("Comment body is empty.")
    audit_event = _add_audit_event(
        project,
        actor=comment.author,
        event_type="comment.created",
        target_type="scene" if comment.scene_id else "project",
        target_id=comment.scene_id or project.id,
        summary=f"{comment.author} 新增审阅意见。",
        metadata={
            "comment_id": comment.id,
            "status": comment.status,
            "assignee": comment.assignee or "",
        },
    )
    notifications = []
    assigned_notification = _add_notification(
        project,
        recipient=comment.assignee,
        actor=comment.author,
        event_type="comment.assigned",
        target_type="comment",
        target_id=comment.id,
        summary=f"{comment.author} 指派你处理审阅意见。",
        metadata={"comment_id": comment.id, "scene_id": comment.scene_id or ""},
    )
    if assigned_notification:
        notifications.append(assigned_notification)
    project.comments.insert(0, comment)
    save_project(project)
    return project, comment, audit_event, notifications


def add_project_comment_reply(
    project_id: str,
    comment_id: str,
    author: str,
    body: str,
) -> tuple[ProjectRecord, ProjectComment, CommentReply, AuditEvent, list[ProjectNotification]]:
    project = get_project(project_id)
    comment = next((item for item in project.comments if item.id == comment_id), None)
    if not comment:
        raise KeyError(comment_id)
    actor = author.strip() or "审阅者"
    _require_permission(project, actor, "reply")
    reply = CommentReply(
        id=f"reply_{uuid4().hex[:12]}",
        author=actor,
        body=body.strip(),
    )
    if not reply.body:
        raise ValueError("Reply body is empty.")
    comment.replies.insert(0, reply)
    comment.updated_at = utc_now()
    audit_event = _add_audit_event(
        project,
        actor=reply.author,
        event_type="comment.replied",
        target_type="comment",
        target_id=comment.id,
        summary=f"{reply.author} 回复了审阅意见。",
        metadata={
            "comment_id": comment.id,
            "reply_id": reply.id,
            "scene_id": comment.scene_id or "",
        },
    )
    notifications: list[ProjectNotification] = []
    recipients = {comment.author}
    if comment.assignee:
        recipients.add(comment.assignee)
    for recipient in sorted(recipients):
        notification = _add_notification(
            project,
            recipient=recipient,
            actor=reply.author,
            event_type="comment.replied",
            target_type="comment",
            target_id=comment.id,
            summary=f"{reply.author} 回复了审阅意见。",
            metadata={"comment_id": comment.id, "reply_id": reply.id, "scene_id": comment.scene_id or ""},
        )
        if notification:
            notifications.append(notification)
    save_project(project)
    return project, comment, reply, audit_event, notifications


def update_project_comment(
    project_id: str,
    comment_id: str,
    payload: UpdateCommentRequest,
) -> tuple[ProjectRecord, ProjectComment, AuditEvent]:
    project = get_project(project_id)
    comment = next((item for item in project.comments if item.id == comment_id), None)
    if not comment:
        raise KeyError(comment_id)
    previous_status = comment.status
    actor = payload.author.strip() or comment.author or "审阅者"
    _require_permission(project, actor, "resolve")
    comment.status = payload.status
    comment.updated_at = utc_now()
    event_type = "comment.resolved" if comment.status == "resolved" else "comment.reopened"
    audit_event = _add_audit_event(
        project,
        actor=actor,
        event_type=event_type,
        target_type="comment",
        target_id=comment.id,
        summary=f"{actor} 将审阅意见标记为 {comment.status}。",
        metadata={
            "comment_id": comment.id,
            "previous_status": previous_status,
            "status": comment.status,
            "scene_id": comment.scene_id or "",
        },
    )
    save_project(project)
    return project, comment, audit_event


def list_project_audit_events(
    project_id: str,
    event_type: str | None = None,
    actor: str | None = None,
    limit: int = 50,
) -> list[AuditEvent]:
    project = get_project(project_id)
    events = project.audit_events
    if event_type:
        events = [event for event in events if event.event_type == event_type]
    if actor:
        events = [event for event in events if event.actor == actor]
    return events[: max(1, min(limit, 200))]


def list_project_notifications(
    project_id: str,
    recipient: str | None = None,
    unread_only: bool = False,
    limit: int = 50,
) -> list[ProjectNotification]:
    project = get_project(project_id)
    notifications = project.notifications
    if recipient:
        notifications = [notification for notification in notifications if notification.recipient == recipient]
    if unread_only:
        notifications = [notification for notification in notifications if notification.unread]
    return notifications[: max(1, min(limit, 200))]


def update_project_notification(
    project_id: str,
    notification_id: str,
    payload: UpdateNotificationRequest,
) -> tuple[ProjectRecord, ProjectNotification, AuditEvent]:
    project = get_project(project_id)
    actor = payload.actor.strip() or "审阅者"
    _require_permission(project, actor, "read_notifications")
    notification = next((item for item in project.notifications if item.id == notification_id), None)
    if not notification:
        raise KeyError(notification_id)
    if notification.recipient != actor:
        raise PermissionError("Only the recipient can update this notification.")
    notification.unread = payload.unread
    audit_event = _add_audit_event(
        project,
        actor=actor,
        event_type="notification.updated",
        target_type="notification",
        target_id=notification.id,
        summary=f"{actor} 将通知标记为 {'未读' if notification.unread else '已读'}。",
        metadata={"notification_id": notification.id, "unread": str(notification.unread).lower()},
    )
    save_project(project)
    return project, notification, audit_event


def current_version(project: ProjectRecord) -> ProjectVersion | None:
    if not project.versions:
        return None
    if project.current_version_id:
        for version in project.versions:
            if version.id == project.current_version_id:
                return version
    return project.versions[-1]


def list_project_versions(project_id: str) -> list[ProjectVersionSummary]:
    project = get_project(project_id)
    return [_version_summary(project, version) for version in reversed(project.versions)]


def restore_project_version(project_id: str, version_id: str, actor: str = "项目负责人") -> ProjectRecord:
    project = get_project(project_id)
    _require_permission(project, actor.strip() or "项目负责人", "manage_members")
    version = _version_by_id(project, version_id)
    project.current_version_id = version.id
    _add_audit_event(
        project,
        actor=actor.strip() or "项目负责人",
        event_type="version.restored",
        target_type="version",
        target_id=version.id,
        summary=f"{actor.strip() or '项目负责人'} 将当前剧本恢复到 {version.label}。",
        metadata={"version_id": version.id, "label": version.label},
    )
    save_project(project)
    return project


def compare_project_versions(project_id: str, base_version_id: str, target_version_id: str) -> VersionCompareResponse:
    project = get_project(project_id)
    base = _version_by_id(project, base_version_id)
    target = _version_by_id(project, target_version_id)
    base_quality = base.screenplay.quality_report.overall_score
    target_quality = target.screenplay.quality_report.overall_score
    return VersionCompareResponse(
        project_id=project.id,
        base_version_id=base.id,
        target_version_id=target.id,
        base_label=base.label,
        target_label=target.label,
        scene_count_delta=len(target.screenplay.scenes) - len(base.screenplay.scenes),
        quality_delta=round(target_quality - base_quality, 2),
        validation_changed=base.validation.valid != target.validation.valid,
        changed_scenes=_changed_scenes(base, target),
        yaml_diff_preview=_yaml_diff_preview(base, target),
    )


def create_project_export(project_id: str, payload: ProjectExportRequest) -> tuple[ProjectRecord, ProjectExportRecord, str, ProjectReadinessResponse, AuditEvent]:
    project = get_project(project_id)
    actor = payload.actor.strip() or "制片"
    _require_permission(project, actor, "export")
    readiness = project_readiness(project.id)
    version = _version_by_id(project, payload.version_id) if payload.version_id else current_version(project)
    blockers = [check.summary for check in readiness.blockers]
    warnings = [check.summary for check in readiness.warnings]
    blocked = payload.enforce_readiness and readiness.status == "blocked"
    content = ""
    size_bytes = 0
    sha256 = ""
    version_id = version.id if version else None
    version_label = version.label if version else ""
    filename = _export_filename(project.title, payload.format)
    content_type = _export_content_type(payload.format)

    if not blocked and not version:
        blocked = True
        blockers = [*blockers, "项目还没有可导出的当前剧本版本。"]

    if not blocked and version:
        content = _export_version_content(version, payload.format)
        content_bytes = content.encode("utf-8")
        size_bytes = len(content_bytes)
        sha256 = hashlib.sha256(content_bytes).hexdigest()

    record = ProjectExportRecord(
        id=f"export_{uuid4().hex[:12]}",
        project_id=project.id,
        version_id=version_id,
        version_label=version_label,
        format=payload.format,
        status="blocked" if blocked else "succeeded",
        actor=actor,
        filename=filename,
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=sha256,
        readiness_status=readiness.status,
        readiness_score=readiness.score,
        blockers=blockers,
        warnings=warnings,
    )
    audit_event = _add_audit_event(
        project,
        actor=actor,
        event_type="export.blocked" if blocked else "export.created",
        target_type="version" if version_id else "project",
        target_id=version_id or project.id,
        summary=(
            f"{actor} 的 {payload.format} 导出被交付门禁阻止。"
            if blocked
            else f"{actor} 导出 {payload.format} 交付物：{filename}。"
        ),
        metadata={
            "export_id": record.id,
            "format": payload.format,
            "status": record.status,
            "version_id": version_id or "",
            "readiness_status": readiness.status,
            "readiness_score": str(readiness.score),
            "size_bytes": str(size_bytes),
            "sha256": sha256,
        },
    )
    record.audit_event_id = audit_event.id
    project.exports.insert(0, record)
    save_project(project)
    return project, record, content, readiness, audit_event


def list_project_exports(project_id: str, limit: int = 30) -> ProjectExportHistoryResponse:
    project = get_project(project_id)
    exports = project.exports[: max(1, min(limit, 100))]
    return ProjectExportHistoryResponse(
        project_id=project.id,
        exports=exports,
        total=len(exports),
        succeeded=sum(1 for item in exports if item.status == "succeeded"),
        blocked=sum(1 for item in exports if item.status == "blocked"),
    )


def create_project_approval(
    project_id: str,
    payload: ProjectApprovalRequest,
) -> tuple[ProjectRecord, ProjectApprovalRecord, ProjectReadinessResponse, AuditEvent, list[ProjectNotification]]:
    project = get_project(project_id)
    actor = payload.actor.strip() or "编剧"
    _require_permission(project, actor, "submit_approval")
    readiness = project_readiness(project.id)
    version = _version_by_id(project, payload.version_id) if payload.version_id else current_version(project)
    blockers = [check.summary for check in readiness.blockers]
    warnings = [check.summary for check in readiness.warnings]
    blocked = payload.enforce_readiness and readiness.status == "blocked"
    if not version:
        blocked = True
        if "项目还没有可提交审批的当前剧本版本。" not in blockers:
            blockers = [*blockers, "项目还没有可提交审批的当前剧本版本。"]

    approval = ProjectApprovalRecord(
        id=f"approval_{uuid4().hex[:12]}",
        project_id=project.id,
        version_id=version.id if version else None,
        version_label=version.label if version else "",
        status="blocked" if blocked else "submitted",
        submitted_by=actor,
        submit_note=payload.note.strip(),
        requested_export_format=payload.requested_export_format,
        readiness_status=readiness.status,
        readiness_score=readiness.score,
        blockers=blockers,
        warnings=warnings,
    )
    audit_event = _add_audit_event(
        project,
        actor=actor,
        event_type="approval.blocked" if blocked else "approval.submitted",
        target_type="version" if approval.version_id else "project",
        target_id=approval.version_id or project.id,
        summary=(
            f"{actor} 的交付审批提交被门禁阻止。"
            if blocked
            else f"{actor} 提交 {approval.version_label or '当前版本'} 进入交付审批。"
        ),
        metadata={
            "approval_id": approval.id,
            "status": approval.status,
            "version_id": approval.version_id or "",
            "requested_export_format": approval.requested_export_format or "",
            "readiness_status": readiness.status,
            "readiness_score": str(readiness.score),
        },
    )
    approval.audit_event_id = audit_event.id
    project.approvals.insert(0, approval)

    notifications: list[ProjectNotification] = []
    if approval.status == "submitted":
        for recipient in _approval_reviewer_recipients(project, actor):
            notification = _add_notification(
                project,
                recipient=recipient,
                actor=actor,
                event_type="approval.submitted",
                target_type="approval",
                target_id=approval.id,
                summary=f"{actor} 提交了交付审批，请复核版本 {approval.version_label}。",
                metadata={"approval_id": approval.id, "version_id": approval.version_id or ""},
            )
            if notification:
                notifications.append(notification)

    save_project(project)
    return project, approval, readiness, audit_event, notifications


def decide_project_approval(
    project_id: str,
    approval_id: str,
    payload: ProjectApprovalDecisionRequest,
) -> tuple[ProjectRecord, ProjectApprovalRecord, ProjectReadinessResponse, AuditEvent, list[ProjectNotification]]:
    project = get_project(project_id)
    approval = _approval_by_id(project, approval_id)
    actor = payload.actor.strip() or "制片"
    _require_approval_decision_permission(project, approval, actor, payload.decision)
    if approval.status != "submitted":
        raise ValueError(f"Cannot {payload.decision} approval with status {approval.status}.")

    next_status: dict[str, str] = {
        "approve": "approved",
        "reject": "rejected",
        "revoke": "revoked",
    }
    approval.status = next_status[payload.decision]  # type: ignore[assignment]
    approval.decided_by = actor
    approval.decided_at = utc_now()
    approval.decision_note = payload.note.strip()
    event_type = f"approval.{approval.status}"
    audit_event = _add_audit_event(
        project,
        actor=actor,
        event_type=event_type,
        target_type="approval",
        target_id=approval.id,
        summary=f"{actor} 将交付审批标记为 {approval.status}。",
        metadata={
            "approval_id": approval.id,
            "status": approval.status,
            "version_id": approval.version_id or "",
            "submitted_by": approval.submitted_by,
            "readiness_status": approval.readiness_status,
            "readiness_score": str(approval.readiness_score),
        },
    )
    approval.decision_audit_event_id = audit_event.id
    notifications: list[ProjectNotification] = []
    notification = _add_notification(
        project,
        recipient=approval.submitted_by,
        actor=actor,
        event_type=event_type,
        target_type="approval",
        target_id=approval.id,
        summary=f"{actor} 已处理你提交的交付审批：{approval.status}。",
        metadata={"approval_id": approval.id, "version_id": approval.version_id or ""},
    )
    if notification:
        notifications.append(notification)
    save_project(project)
    readiness = project_readiness(project.id)
    return project, approval, readiness, audit_event, notifications


def list_project_approvals(project_id: str, limit: int = 30) -> ProjectApprovalHistoryResponse:
    project = get_project(project_id)
    approvals = project.approvals[: max(1, min(limit, 100))]
    return ProjectApprovalHistoryResponse(
        project_id=project.id,
        approvals=approvals,
        total=len(approvals),
        pending=sum(1 for item in approvals if item.status == "submitted"),
        approved=sum(1 for item in approvals if item.status == "approved"),
        rejected=sum(1 for item in approvals if item.status == "rejected"),
        revoked=sum(1 for item in approvals if item.status == "revoked"),
        blocked=sum(1 for item in approvals if item.status == "blocked"),
    )


def create_project_delivery_package(
    project_id: str,
    payload: ProjectDeliveryPackageRequest,
) -> tuple[ProjectRecord, ProjectDeliveryPackageRecord, list[ProjectDeliveryPackageAsset], ProjectReadinessResponse, AuditEvent]:
    project = get_project(project_id)
    actor = payload.actor.strip() or "制片"
    _require_permission(project, actor, "package_delivery")
    readiness = project_readiness(project.id)
    requested_version = _version_by_id(project, payload.version_id) if payload.version_id else None
    version = requested_version or current_version(project)
    blockers = [check.summary for check in readiness.blockers]
    warnings = [check.summary for check in readiness.warnings]
    blocked = payload.enforce_readiness and readiness.status == "blocked"
    approval: ProjectApprovalRecord | None = None

    if not version:
        blocked = True
        blockers = _append_unique(blockers, "项目还没有可打包的当前剧本版本。")

    if not blocked and payload.require_approval:
        approval = _resolve_delivery_package_approval(project, payload.approval_id, version.id if version else None)
        if not approval:
            blocked = True
            blockers = _append_unique(blockers, "交付包需要绑定已批准的交付审批。")
        elif approval.status != "approved":
            blocked = True
            blockers = _append_unique(blockers, f"审批 {approval.id} 当前状态为 {approval.status}，不能生成正式交付包。")
        elif version and approval.version_id and approval.version_id != version.id:
            blocked = True
            blockers = _append_unique(blockers, "审批版本与打包版本不一致。")

    assets_with_content: list[ProjectDeliveryPackageAsset] = []
    stored_assets: list[ProjectDeliveryPackageAsset] = []
    total_size = 0
    manifest_json = ""
    manifest_sha256 = ""
    manifest_filename = _delivery_manifest_filename(project.title)
    package_id = f"package_{uuid4().hex[:12]}"
    created_at = utc_now()
    artifact_provider = None

    if not blocked and version:
        artifact_provider = delivery_artifact_provider(DATA_DIR)
        for format_name in payload.formats:
            content = _export_version_content(version, format_name)
            content_bytes = content.encode("utf-8")
            storage_key = _delivery_storage_key(project.id, package_id, _delivery_asset_filename(project.title, format_name))
            stored_asset = ProjectDeliveryPackageAsset(
                format=format_name,
                filename=_delivery_asset_filename(project.title, format_name),
                content_type=_export_content_type(format_name),
                size_bytes=len(content_bytes),
                sha256=hashlib.sha256(content_bytes).hexdigest(),
                storage_provider=artifact_provider.name,
                storage_key=storage_key,
            )
            _write_delivery_artifact(storage_key, content_bytes)
            signed_asset = _with_delivery_download(stored_asset, project.id, package_id)
            assets_with_content.append(signed_asset.model_copy(update={"content": content}))
            stored_assets.append(stored_asset)
            total_size += stored_asset.size_bytes
        manifest_json = _delivery_manifest_json(
            package_id=package_id,
            project=project,
            version=version,
            approval=approval,
            readiness=readiness,
            actor=actor,
            note=payload.note.strip(),
            assets=stored_assets,
            formats=payload.formats,
            generated_at=created_at,
        )
        manifest_bytes = manifest_json.encode("utf-8")
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        manifest_storage_key = _delivery_storage_key(project.id, package_id, manifest_filename)
        _write_delivery_artifact(manifest_storage_key, manifest_bytes)
        manifest_asset = ProjectDeliveryPackageAsset(
            format="json",
            filename=manifest_filename,
            content_type="application/json",
            size_bytes=len(manifest_bytes),
            sha256=manifest_sha256,
            storage_provider=artifact_provider.name,
            storage_key=manifest_storage_key,
        )
        signed_manifest_asset = _with_delivery_download(manifest_asset, project.id, package_id)
        assets_with_content.append(signed_manifest_asset.model_copy(update={"content": manifest_json}))
        stored_assets.append(manifest_asset)
        total_size += manifest_asset.size_bytes

    record = ProjectDeliveryPackageRecord(
        id=package_id,
        project_id=project.id,
        version_id=version.id if version else None,
        version_label=version.label if version else "",
        approval_id=approval.id if approval else payload.approval_id,
        status="blocked" if blocked else "succeeded",
        actor=actor,
        note=payload.note.strip(),
        created_at=created_at,
        formats=payload.formats,
        assets=stored_assets,
        manifest_filename=manifest_filename if manifest_json else "",
        manifest_json=manifest_json,
        manifest_sha256=manifest_sha256,
        total_size_bytes=total_size,
        storage_provider=artifact_provider.name if artifact_provider else configured_delivery_artifact_provider_name(),
        artifact_count=len(stored_assets),
        readiness_status=readiness.status,
        readiness_score=readiness.score,
        blockers=blockers,
        warnings=warnings,
    )
    audit_event = _add_audit_event(
        project,
        actor=actor,
        event_type="delivery_package.blocked" if blocked else "delivery_package.created",
        target_type="version" if record.version_id else "project",
        target_id=record.version_id or project.id,
        summary=(
            f"{actor} 的正式交付包被交付链路阻止。"
            if blocked
            else f"{actor} 生成正式交付包 {record.id}，包含 {len(record.assets)} 个交付文件。"
        ),
        metadata={
            "package_id": record.id,
            "approval_id": record.approval_id or "",
            "version_id": record.version_id or "",
            "status": record.status,
            "formats": ",".join(record.formats),
            "manifest_sha256": manifest_sha256,
            "total_size_bytes": str(total_size),
            "readiness_status": readiness.status,
            "readiness_score": str(readiness.score),
        },
    )
    record.audit_event_id = audit_event.id
    project.delivery_packages.insert(0, record)
    save_project(project)
    return project, _with_delivery_package_downloads(record), assets_with_content, readiness, audit_event


def list_project_delivery_packages(
    project_id: str,
    limit: int = 30,
    include_downloads: bool = False,
) -> ProjectDeliveryPackageHistoryResponse:
    project = get_project(project_id)
    packages = project.delivery_packages[: max(1, min(limit, 100))]
    if include_downloads:
        packages = [_with_delivery_package_downloads(item) for item in packages]
    return ProjectDeliveryPackageHistoryResponse(
        project_id=project.id,
        packages=packages,
        total=len(packages),
        succeeded=sum(1 for item in packages if item.status == "succeeded"),
        blocked=sum(1 for item in packages if item.status == "blocked"),
    )


def get_project_delivery_package_asset(
    project_id: str,
    package_id: str,
    asset_sha256: str,
    token: str,
) -> tuple[ProjectDeliveryPackageRecord, ProjectDeliveryPackageAsset, bytes]:
    project = get_project(project_id)
    package = next((item for item in project.delivery_packages if item.id == package_id), None)
    if not package:
        raise KeyError(package_id)
    asset = next((item for item in package.assets if item.sha256 == asset_sha256), None)
    if not asset or not asset.storage_key:
        raise KeyError(asset_sha256)
    _verify_delivery_token(project_id, package_id, asset.sha256, token)
    content = _read_delivery_artifact(asset.storage_key, asset.storage_provider)
    actual_sha = hashlib.sha256(content).hexdigest()
    if actual_sha != asset.sha256:
        raise ValueError("Delivery artifact hash mismatch.")
    return package, asset, content


def project_readiness(project_id: str) -> ProjectReadinessResponse:
    project = get_project(project_id)
    version = current_version(project)
    checks: list[ProjectReadinessCheck] = []

    if not project.source_text.strip():
        checks.append(_readiness_check("source", "源文导入", "blocked", "项目还没有可用于改编的小说源文。"))
    else:
        checks.append(
            _readiness_check(
                "source",
                "源文导入",
                "ready",
                "项目源文已保存。",
                {"source_length": len(project.source_text)},
            )
        )

    if not version:
        checks.append(_readiness_check("version", "当前剧本版本", "blocked", "项目还没有生成过可交付剧本版本。"))
    else:
        screenplay = version.screenplay
        checks.append(
            _readiness_check(
                "version",
                "当前剧本版本",
                "ready",
                f"当前版本为 {version.label}。",
                {"scene_count": len(screenplay.scenes), "yaml_bytes": len(version.yaml_text.encode("utf-8"))},
            )
        )
        checks.append(_schema_readiness_check(version))
        checks.append(_quality_readiness_check(project, version))
        checks.append(_evidence_readiness_check(version))
        checks.append(_production_readiness_check(version))

    checks.append(_import_security_readiness_check(project_id))
    checks.append(_review_readiness_check(project))
    checks.append(_job_readiness_check(project_id))

    blockers = [check for check in checks if check.status == "blocked"]
    warnings = [check for check in checks if check.status == "warning"]
    passed = [check for check in checks if check.status == "ready"]
    score = _readiness_score(checks)
    status: ReadinessStatus = "blocked" if blockers else "warning" if warnings else "ready"
    return ProjectReadinessResponse(
        project_id=project.id,
        status=status,
        score=score,
        current_version_id=version.id if version else None,
        blockers=blockers,
        warnings=warnings,
        passed=passed,
        next_actions=_readiness_next_actions(blockers, warnings),
    )


def _readiness_check(
    check_id: str,
    label: str,
    status: ReadinessStatus,
    summary: str,
    evidence: dict[str, int | float | str | bool] | None = None,
) -> ProjectReadinessCheck:
    return ProjectReadinessCheck(id=check_id, label=label, status=status, summary=summary, evidence=evidence or {})


def _schema_readiness_check(version: ProjectVersion) -> ProjectReadinessCheck:
    issue_count = len(version.validation.issues)
    if version.validation.valid:
        return _readiness_check("schema", "Schema 校验", "ready", "当前 YAML 通过 Schema 校验。", {"issues": issue_count})
    return _readiness_check("schema", "Schema 校验", "blocked", f"当前 YAML 仍有 {issue_count} 个结构问题。", {"issues": issue_count})


def _quality_readiness_check(project: ProjectRecord, version: ProjectVersion) -> ProjectReadinessCheck:
    score = round(version.screenplay.quality_report.overall_score, 1)
    gate = project.settings.quality_gate_score
    if score >= gate:
        return _readiness_check("quality", "质量门禁", "ready", f"质量分 {score} 已达到门槛 {gate}。", {"score": score, "gate": gate})
    status: ReadinessStatus = "blocked" if score < max(60, gate - 20) else "warning"
    return _readiness_check("quality", "质量门禁", status, f"质量分 {score} 低于门槛 {gate}。", {"score": score, "gate": gate})


def _evidence_readiness_check(version: ProjectVersion) -> ProjectReadinessCheck:
    scenes = version.screenplay.scenes
    scene_count = len(scenes)
    scenes_with_refs = sum(1 for scene in scenes if scene.source_refs)
    element_count = sum(len(scene.elements) for scene in scenes)
    elements_with_refs = sum(1 for scene in scenes for element in scene.elements if element.source_refs)
    scene_coverage = round((scenes_with_refs / scene_count) * 100, 1) if scene_count else 0.0
    element_coverage = round((elements_with_refs / element_count) * 100, 1) if element_count else 0.0
    evidence = {
        "scene_count": scene_count,
        "scenes_with_refs": scenes_with_refs,
        "scene_coverage": scene_coverage,
        "element_count": element_count,
        "elements_with_refs": elements_with_refs,
        "element_coverage": element_coverage,
    }
    if scene_count and scenes_with_refs == scene_count and element_coverage >= 60:
        return _readiness_check("evidence", "证据链覆盖", "ready", f"场景证据覆盖 {scene_coverage}%，元素证据覆盖 {element_coverage}%。", evidence)
    status: ReadinessStatus = "blocked" if scene_coverage < 80 else "warning"
    return _readiness_check("evidence", "证据链覆盖", status, f"证据链不足：场景 {scene_coverage}%，元素 {element_coverage}%。", evidence)


def _production_readiness_check(version: ProjectVersion) -> ProjectReadinessCheck:
    production = version.screenplay.production
    has_breakdown = bool(production.location_breakdowns and production.shot_plan)
    evidence = {
        "estimated_pages": production.estimated_pages,
        "estimated_runtime_minutes": production.estimated_runtime_minutes,
        "location_breakdowns": len(production.location_breakdowns),
        "shot_plan": len(production.shot_plan),
    }
    if has_breakdown:
        return _readiness_check("production", "制片拆解", "ready", "制片拆解已包含地点拆解和镜头计划。", evidence)
    return _readiness_check("production", "制片拆解", "warning", "制片拆解还不完整，建议补齐地点拆解和镜头计划。", evidence)


def _import_security_readiness_check(project_id: str) -> ProjectReadinessCheck:
    history = list_project_import_history(project_id, limit=1)
    latest = history.imports[0] if history.imports else None
    if not latest:
        return _readiness_check("import_security", "导入安全", "warning", "没有可审计的导入历史，建议通过文件导入链路建立安全记录。")
    evidence = {
        "filename": latest.filename,
        "upload_mode": latest.upload_mode,
        "sha256": latest.sha256,
        "security_verdict": latest.security_report.verdict,
        "risk_level": latest.security_report.risk_level,
    }
    if latest.security_report.verdict == "blocked" or latest.security_report.risk_level in {"high", "critical"}:
        return _readiness_check("import_security", "导入安全", "blocked", "最近导入存在高风险安全扫描结论。", evidence)
    if latest.security_report.verdict == "warning" or latest.warning_count:
        return _readiness_check("import_security", "导入安全", "warning", "最近导入有扫描或提取警告，需要复核。", evidence)
    return _readiness_check("import_security", "导入安全", "ready", "最近导入安全扫描为 clean。", evidence)


def _review_readiness_check(project: ProjectRecord) -> ProjectReadinessCheck:
    open_count = sum(1 for comment in project.comments if comment.status == "open")
    if open_count:
        return _readiness_check("review", "审阅意见", "warning", f"仍有 {open_count} 条未解决审阅意见。", {"open_comments": open_count})
    return _readiness_check("review", "审阅意见", "ready", "没有未解决审阅意见。", {"open_comments": 0})


def _job_readiness_check(project_id: str) -> ProjectReadinessCheck:
    jobs = list_jobs(project_id)[:20]
    active = [job for job in jobs if job.status in {"queued", "running"}]
    failed = [job for job in jobs if job.status == "failed"]
    dead_lettered = [job for job in jobs if job.status == "dead_lettered"]
    if active:
        return _readiness_check("jobs", "任务队列", "blocked", f"仍有 {len(active)} 个任务未完成。", {"active_jobs": len(active), "failed_jobs": len(failed)})
    if dead_lettered:
        return _readiness_check(
            "jobs",
            "任务队列",
            "blocked",
            f"存在 {len(dead_lettered)} 个死信任务，需要重入队或人工处理。",
            {"active_jobs": 0, "failed_jobs": len(failed), "dead_lettered_jobs": len(dead_lettered)},
        )
    if failed:
        return _readiness_check("jobs", "任务队列", "warning", f"存在 {len(failed)} 个失败任务，建议复查。", {"active_jobs": 0, "failed_jobs": len(failed)})
    return _readiness_check("jobs", "任务队列", "ready", "没有阻塞交付的运行中任务。", {"active_jobs": 0, "failed_jobs": 0})


def _readiness_score(checks: list[ProjectReadinessCheck]) -> int:
    if not checks:
        return 0
    points = {"ready": 100, "warning": 65, "blocked": 0}
    return round(sum(points[check.status] for check in checks) / len(checks))


def _readiness_next_actions(blockers: list[ProjectReadinessCheck], warnings: list[ProjectReadinessCheck]) -> list[str]:
    actions: list[str] = []
    for check in blockers + warnings:
        if check.id == "source":
            actions.append("先导入或粘贴 3 章以上小说源文。")
        elif check.id == "version":
            actions.append("运行生成任务，保存一个可审阅剧本版本。")
        elif check.id == "schema":
            actions.append("进入 YAML 工作区修复 Schema 诊断问题。")
        elif check.id == "quality":
            actions.append("使用质量中心批量改写低质量或低证据场景。")
        elif check.id == "evidence":
            actions.append("补强场景和剧本元素的 source_refs 证据链。")
        elif check.id == "production":
            actions.append("复核制片拆解，补齐地点拆解和镜头计划。")
        elif check.id == "import_security":
            actions.append("复核最近导入的安全扫描和提取警告。")
        elif check.id == "review":
            actions.append("解决或关闭未完成审阅意见。")
        elif check.id == "jobs":
            actions.append("等待任务完成，或处理失败/阻塞任务。")
    return list(dict.fromkeys(actions))[:8]


def _version_by_id(project: ProjectRecord, version_id: str) -> ProjectVersion:
    for version in project.versions:
        if version.id == version_id:
            return version
    raise KeyError(version_id)


def _approval_by_id(project: ProjectRecord, approval_id: str) -> ProjectApprovalRecord:
    for approval in project.approvals:
        if approval.id == approval_id:
            return approval
    raise KeyError(approval_id)


def _approval_reviewer_recipients(project: ProjectRecord, actor: str) -> list[str]:
    recipients: list[str] = []
    for member in project.members:
        if not member.active or member.name == actor:
            continue
        if "approve_delivery" in ROLE_PERMISSIONS.get(member.role, set()):
            recipients.append(member.name)
    return recipients


def _resolve_delivery_package_approval(
    project: ProjectRecord,
    approval_id: str | None,
    version_id: str | None,
) -> ProjectApprovalRecord | None:
    if approval_id:
        try:
            return _approval_by_id(project, approval_id)
        except KeyError:
            return None
    approved = [
        approval
        for approval in project.approvals
        if approval.status == "approved" and (not version_id or approval.version_id == version_id)
    ]
    return approved[0] if approved else None


def _append_unique(items: list[str], value: str) -> list[str]:
    return items if value in items else [*items, value]


def _require_approval_decision_permission(
    project: ProjectRecord,
    approval: ProjectApprovalRecord,
    actor: str,
    decision: str,
) -> ProjectMember:
    if is_local_single_user_mode():
        return _local_owner_member(project)
    if decision in {"approve", "reject"}:
        return _require_permission(project, actor, "approve_delivery")
    if decision == "revoke":
        member = _member_for(project, actor)
        if not member:
            raise PermissionError(f"Project member not found: {actor}")
        if actor == approval.submitted_by or member.role in {"owner", "admin"}:
            return member
        raise PermissionError(f"{member.role} cannot revoke this approval.")
    raise ValueError(f"Unsupported approval decision: {decision}")


def _version_summary(project: ProjectRecord, version: ProjectVersion) -> ProjectVersionSummary:
    screenplay = version.screenplay
    return ProjectVersionSummary(
        id=version.id,
        created_at=version.created_at,
        label=version.label,
        scene_count=len(screenplay.scenes),
        quality_score=screenplay.quality_report.overall_score,
        validation_valid=version.validation.valid,
        provider=screenplay.metadata.provider,
        provider_status=screenplay.metadata.provider_status,
        yaml_bytes=len(version.yaml_text.encode("utf-8")),
        is_current=version.id == project.current_version_id,
    )


def _changed_scenes(base: ProjectVersion, target: ProjectVersion) -> list[VersionSceneChange]:
    base_scenes = {scene.id: scene for scene in base.screenplay.scenes}
    target_scenes = {scene.id: scene for scene in target.screenplay.scenes}
    changes: list[VersionSceneChange] = []
    for scene_id in sorted(set(base_scenes) | set(target_scenes)):
        before = base_scenes.get(scene_id)
        after = target_scenes.get(scene_id)
        if before and not after:
            changes.append(
                VersionSceneChange(
                    scene_id=scene_id,
                    title_before=before.title,
                    change_type="removed",
                    summary="场景已从目标版本移除。",
                )
            )
        elif after and not before:
            changes.append(
                VersionSceneChange(
                    scene_id=scene_id,
                    title_after=after.title,
                    change_type="added",
                    summary="目标版本新增场景。",
                )
            )
        elif before and after:
            diff_bits = []
            if before.summary != after.summary:
                diff_bits.append("summary")
            if before.conflict != after.conflict:
                diff_bits.append("conflict")
            if before.elements != after.elements:
                diff_bits.append("elements")
            if before.quality_flags != after.quality_flags:
                diff_bits.append("quality_flags")
            if diff_bits:
                changes.append(
                    VersionSceneChange(
                        scene_id=scene_id,
                        title_before=before.title,
                        title_after=after.title,
                        change_type="changed",
                        summary=f"字段变更: {', '.join(diff_bits)}",
                    )
                )
    return changes[:80]


def _yaml_diff_preview(base: ProjectVersion, target: ProjectVersion) -> list[str]:
    diff = unified_diff(
        base.yaml_text.splitlines(),
        target.yaml_text.splitlines(),
        fromfile=f"{base.label}.yaml",
        tofile=f"{target.label}.yaml",
        lineterm="",
        n=2,
    )
    return list(diff)[:120]


def _export_version_content(version: ProjectVersion, format_name: ExportFormat) -> str:
    if format_name == "yaml":
        return version.yaml_text or to_yaml(version.screenplay)
    if format_name == "json":
        return to_json(version.screenplay)
    if format_name == "markdown":
        return to_markdown(version.screenplay)
    if format_name == "fountain":
        return to_fountain(version.screenplay)
    raise ValueError(f"Unsupported export format: {format_name}")


def _export_content_type(format_name: ExportFormat) -> str:
    if format_name == "yaml":
        return "application/x-yaml"
    if format_name == "json":
        return "application/json"
    if format_name == "markdown":
        return "text/markdown"
    return "text/plain"


def _export_filename(project_title: str, format_name: ExportFormat) -> str:
    extension = "md" if format_name == "markdown" else format_name
    safe_title = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in project_title.strip())
    safe_title = "-".join(part for part in safe_title.split("-") if part)[:80] or "screenplay"
    return f"{safe_title}.{extension}"


def _delivery_asset_filename(project_title: str, format_name: ExportFormat) -> str:
    base_filename = _export_filename(project_title, format_name)
    stem, _, extension = base_filename.rpartition(".")
    safe_stem = stem or base_filename
    return f"{safe_stem}.delivery.{extension or format_name}"


def _delivery_manifest_filename(project_title: str) -> str:
    base_filename = _export_filename(project_title, "json")
    stem, _, _ = base_filename.rpartition(".")
    return f"{stem or 'screenplay'}.delivery-manifest.json"


def _delivery_storage_key(project_id: str, package_id: str, filename: str) -> str:
    safe_filename = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in filename.strip())
    safe_filename = "-".join(part for part in safe_filename.split("-") if part)[:120] or "artifact.txt"
    return f"{project_id}/{package_id}/{safe_filename}"


def _write_delivery_artifact(storage_key: str, content: bytes) -> None:
    delivery_artifact_provider(DATA_DIR).write(storage_key, content)


def _read_delivery_artifact(storage_key: str, storage_provider: str = "local") -> bytes:
    return delivery_artifact_provider(DATA_DIR, storage_provider).read(storage_key)


def _delivery_signing_secret() -> bytes:
    configured = os.getenv("DELIVERY_SIGNING_SECRET", "").strip()
    if configured:
        return configured.encode("utf-8")
    return hashlib.sha256(str(DB_PATH).encode("utf-8")).digest()


def _delivery_token(project_id: str, package_id: str, asset_sha256: str, expires_at: int) -> str:
    message = f"{project_id}|{package_id}|{asset_sha256}|{expires_at}".encode("utf-8")
    signature = hmac.new(_delivery_signing_secret(), message, hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{expires_at}.{encoded}"


def _verify_delivery_token(project_id: str, package_id: str, asset_sha256: str, token: str) -> None:
    expires_text, _, signature = token.partition(".")
    if not expires_text.isdigit() or not signature:
        raise PermissionError("Invalid delivery download token.")
    expires_at = int(expires_text)
    if expires_at < int(time.time()):
        raise PermissionError("Delivery download token expired.")
    expected = _delivery_token(project_id, package_id, asset_sha256, expires_at)
    if not hmac.compare_digest(expected, token):
        raise PermissionError("Invalid delivery download token.")


def _with_delivery_download(asset: ProjectDeliveryPackageAsset, project_id: str, package_id: str) -> ProjectDeliveryPackageAsset:
    if not asset.sha256 or not asset.storage_key:
        return asset
    expires_at = int(time.time()) + DELIVERY_DOWNLOAD_TTL_SECONDS
    token = _delivery_token(project_id, package_id, asset.sha256, expires_at)
    return asset.model_copy(
        update={
            "storage_provider": asset.storage_provider or configured_delivery_artifact_provider_name(),
            "download_url": f"/api/projects/{project_id}/delivery-packages/{package_id}/assets/{asset.sha256}?token={token}",
            "download_expires_at": utc_from_timestamp(expires_at),
        }
    )


def _with_delivery_package_downloads(package: ProjectDeliveryPackageRecord) -> ProjectDeliveryPackageRecord:
    if package.status != "succeeded":
        return package
    assets = [_with_delivery_download(asset, package.project_id, package.id) for asset in package.assets]
    return package.model_copy(
        update={
            "assets": assets,
            "storage_provider": package.storage_provider or "local",
            "artifact_count": package.artifact_count or len(assets),
            "download_expires_at": assets[0].download_expires_at if assets else package.download_expires_at,
        }
    )


def utc_from_timestamp(timestamp: int) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _delivery_manifest_json(
    *,
    package_id: str,
    project: ProjectRecord,
    version: ProjectVersion,
    approval: ProjectApprovalRecord | None,
    readiness: ProjectReadinessResponse,
    actor: str,
    note: str,
    assets: list[ProjectDeliveryPackageAsset],
    formats: list[ExportFormat],
    generated_at: str,
) -> str:
    manifest = {
        "schema": "scriptbridge.delivery-package.v1",
        "package_id": package_id,
        "project": {
            "id": project.id,
            "title": project.title,
        },
        "version": {
            "id": version.id,
            "label": version.label,
            "created_at": version.created_at,
            "validation_valid": version.validation.valid,
            "quality_score": version.screenplay.quality_report.overall_score,
        },
        "approval": {
            "id": approval.id if approval else None,
            "status": approval.status if approval else None,
            "submitted_by": approval.submitted_by if approval else None,
            "decided_by": approval.decided_by if approval else None,
            "decided_at": approval.decided_at if approval else None,
        },
        "readiness": {
            "status": readiness.status,
            "score": readiness.score,
            "generated_at": readiness.generated_at,
            "blockers": [item.summary for item in readiness.blockers],
            "warnings": [item.summary for item in readiness.warnings],
        },
        "formats": formats,
        "assets": [
            {
                "format": asset.format,
                "filename": asset.filename,
                "content_type": asset.content_type,
                "size_bytes": asset.size_bytes,
                "sha256": asset.sha256,
            }
            for asset in assets
        ],
        "actor": actor,
        "note": note,
        "generated_at": generated_at,
    }
    return json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def create_job(
    project_id: str,
    kind: str = "generate",
    *,
    queue_mode: JobQueueMode = "background",
    request_payload: dict[str, object] | None = None,
) -> JobRecord:
    job = JobRecord(
        id=f"job_{uuid4().hex[:12]}",
        project_id=project_id,
        kind=kind,  # type: ignore[arg-type]
        queue_mode=queue_mode,
        request_payload=request_payload or {},
    )
    save_job(job)
    return job


def get_job(job_id: str) -> JobRecord:
    ensure_data_dirs()
    with _connect() as conn:
        row = conn.execute("SELECT payload FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise KeyError(job_id)
    return JobRecord.model_validate(json.loads(row["payload"]))


def save_job(job: JobRecord) -> None:
    ensure_data_dirs()
    job.updated_at = utc_now()
    payload = json.dumps(job.model_dump(mode="json"), ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, project_id, kind, status, progress, updated_at,
                result_version_id, queue_mode, attempts, payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                project_id = excluded.project_id,
                kind = excluded.kind,
                status = excluded.status,
                progress = excluded.progress,
                updated_at = excluded.updated_at,
                result_version_id = excluded.result_version_id,
                queue_mode = excluded.queue_mode,
                attempts = excluded.attempts,
                payload = excluded.payload
            """,
            (
                job.id,
                job.project_id,
                job.kind,
                job.status,
                job.progress,
                job.updated_at,
                job.result_version_id,
                job.queue_mode,
                job.attempts,
                payload,
            ),
        )


def list_jobs(project_id: str | None = None) -> list[JobSummary]:
    ensure_data_dirs()
    query = "SELECT payload FROM jobs"
    params: tuple[str, ...] = ()
    if project_id:
        query += " WHERE project_id = ?"
        params = (project_id,)
    query += " ORDER BY updated_at DESC"
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    summaries: list[JobSummary] = []
    for row in rows:
        job = JobRecord.model_validate(json.loads(row["payload"]))
        summaries.append(
            JobSummary(
                id=job.id,
                project_id=job.project_id,
                kind=job.kind,
                status=job.status,
                progress=job.progress,
                updated_at=job.updated_at,
                result_version_id=job.result_version_id,
                queue_mode=job.queue_mode,
                attempts=job.attempts,
                max_attempts=job.max_attempts,
                error=job.error,
                dead_lettered_at=job.dead_lettered_at,
                dead_letter_reason=job.dead_letter_reason,
                dead_letter_source=job.dead_letter_source,
                requeue_count=job.requeue_count,
            )
        )
    return summaries


def list_dead_letter_jobs(limit: int = 20) -> list[JobSummary]:
    ensure_data_dirs()
    capped_limit = max(1, min(limit, 100))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT payload
            FROM jobs
            WHERE status IN ('failed', 'dead_lettered')
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (capped_limit,),
        ).fetchall()
    summaries: list[JobSummary] = []
    for row in rows:
        job = JobRecord.model_validate(json.loads(row["payload"]))
        summaries.append(
            JobSummary(
                id=job.id,
                project_id=job.project_id,
                kind=job.kind,
                status=job.status,
                progress=job.progress,
                updated_at=job.updated_at,
                result_version_id=job.result_version_id,
                queue_mode=job.queue_mode,
                attempts=job.attempts,
                max_attempts=job.max_attempts,
                error=job.error,
                dead_lettered_at=job.dead_lettered_at,
                dead_letter_reason=job.dead_letter_reason,
                dead_letter_source=job.dead_letter_source,
                requeue_count=job.requeue_count,
            )
        )
    return summaries


def list_project_import_history(project_id: str, limit: int = 30) -> ImportHistoryResponse:
    project = get_project(project_id)
    ensure_data_dirs()
    capped_limit = max(1, min(limit, 100))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT payload
            FROM jobs
            WHERE project_id = ? AND kind = 'import'
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (project_id, capped_limit),
        ).fetchall()
    jobs = [JobRecord.model_validate(json.loads(row["payload"])) for row in rows]
    imports = [_import_history_item(project, job) for job in jobs]
    return ImportHistoryResponse(
        project_id=project.id,
        imports=imports,
        total=len(imports),
        succeeded=sum(1 for item in imports if item.status == "succeeded"),
        failed=sum(1 for item in imports if item.status == "failed"),
        running=sum(1 for item in imports if item.status == "running"),
        queued=sum(1 for item in imports if item.status == "queued"),
        canceled=sum(1 for item in imports if item.status == "canceled"),
    )


def _import_history_item(project: ProjectRecord, job: JobRecord) -> ImportHistoryItem:
    result = job.result_payload if isinstance(job.result_payload, dict) else {}
    request = job.request_payload if isinstance(job.request_payload, dict) else {}
    latest_event = job.events[-1] if job.events else None
    filename = _string_meta(result.get("filename")) or _string_meta(request.get("filename"))
    audit_event = _audit_event_for_import_job(project, job.id)
    warnings = [str(item) for item in result.get("warnings", [])] if isinstance(result.get("warnings"), list) else []
    document_stats = result.get("document_stats") if isinstance(result.get("document_stats"), dict) else {}
    security_report = _security_report_meta(result.get("security_report") or request.get("security_report"))
    return ImportHistoryItem(
        job_id=job.id,
        project_id=job.project_id,
        status=job.status,
        queue_mode=job.queue_mode,
        actor=_string_meta(request.get("actor")) or "system",
        filename=filename,
        content_type=_string_meta(result.get("content_type")) or _string_meta(request.get("content_type")),
        size_bytes=_int_meta(result.get("size_bytes")) or _int_meta(request.get("size_bytes")),
        upload_mode=_string_meta(result.get("upload_mode")) or _string_meta(request.get("upload_mode")) or "multipart",
        sha256=_string_meta(result.get("sha256")) or _string_meta(request.get("sha256")) or security_report.sha256,
        extraction_method=_string_meta(result.get("extraction_method")),
        detected_encoding=_string_meta(result.get("detected_encoding")),
        chapter_count=_int_meta(result.get("chapter_count")),
        paragraph_count=_int_meta(result.get("paragraph_count")),
        warning_count=len(warnings),
        warnings=warnings,
        document_stats={str(key): value for key, value in document_stats.items() if isinstance(value, (int, str))},
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        progress=job.progress,
        attempts=job.attempts,
        error=job.error,
        last_stage_id=latest_event.stage_id if latest_event else "",
        last_stage_message=latest_event.message if latest_event else "",
        audit_event_id=audit_event.id if audit_event else None,
        security_report=security_report,
    )


def _audit_event_for_import_job(project: ProjectRecord, job_id: str) -> AuditEvent | None:
    return next(
        (
            event
            for event in project.audit_events
            if event.event_type == "import.source_completed" and event.metadata.get("job_id") == job_id
        ),
        None,
    )


def _string_meta(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _int_meta(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float):
        return max(int(value), 0)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _security_report_meta(value: object) -> ImportSecurityReport:
    if isinstance(value, dict):
        try:
            return ImportSecurityReport.model_validate(value)
        except Exception:
            pass
    return ImportSecurityReport(verdict="warning", risk_level="medium", warnings=["导入记录缺少安全扫描报告。"])


def list_queued_jobs(limit: int = 20, queue_mode: JobQueueMode | None = None) -> list[JobRecord]:
    ensure_data_dirs()
    query = "SELECT payload FROM jobs WHERE status = 'queued'"
    params: list[str | int] = []
    if queue_mode:
        query += " AND queue_mode = ?"
        params.append(queue_mode)
    query += " ORDER BY updated_at ASC LIMIT ?"
    params.append(max(1, min(limit, 100)))
    with _connect() as conn:
        rows = conn.execute(query, tuple(params)).fetchall()
    return [JobRecord.model_validate(json.loads(row["payload"])) for row in rows]


def claim_next_job(worker_id: str, queue_mode: JobQueueMode | None = None) -> JobRecord | None:
    queued = list_queued_jobs(limit=1, queue_mode=queue_mode)
    if not queued:
        return None
    job = queued[0]
    job.locked_by = worker_id
    job.locked_at = utc_now()
    save_job(job)
    return job


def claim_job(job_id: str, worker_id: str, queue_mode: JobQueueMode | None = None) -> JobRecord | None:
    try:
        job = get_job(job_id)
    except KeyError:
        return None
    if job.status != "queued":
        return None
    if queue_mode and job.queue_mode != queue_mode:
        return None
    job.locked_by = worker_id
    job.locked_at = utc_now()
    save_job(job)
    return job


def cancel_job(job_id: str, actor: str = "system") -> JobRecord:
    job = get_job(job_id)
    if job.status not in {"queued", "running"}:
        raise ValueError(f"Cannot cancel {job.status} job.")
    job.status = "canceled"
    job.completed_at = utc_now()
    job.error = f"Canceled by {actor}."
    job.events.append(JobEvent(stage_id="job.canceled", message=f"{actor} 取消了任务。", progress=job.progress))
    save_job(job)
    return job


def retry_job(job_id: str, actor: str = "system") -> JobRecord:
    job = get_job(job_id)
    if job.status not in {"failed", "canceled", "dead_lettered"}:
        raise ValueError(f"Cannot retry {job.status} job.")
    force_reset_attempts = job.status == "dead_lettered" or job.attempts >= job.max_attempts
    job.status = "queued"
    job.progress = 0
    job.error = None
    job.started_at = None
    job.completed_at = None
    job.locked_by = None
    job.locked_at = None
    job.result_version_id = None
    if force_reset_attempts:
        job.attempts = 0
        job.requeue_count += 1
    job.dead_lettered_at = None
    job.dead_letter_reason = None
    job.dead_letter_source = None
    job.queued_at = utc_now()
    job.events.append(JobEvent(stage_id="job.requeued", message=f"{actor} 将任务重新入队。", progress=0))
    save_job(job)
    return job


def queue_counts() -> dict[str, int]:
    ensure_data_dirs()
    with _connect() as conn:
        rows = conn.execute("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status").fetchall()
    return {str(row["status"]): int(row["count"]) for row in rows}


def mark_job_dead_lettered(
    job_id: str,
    reason: str,
    *,
    source: str = "queue",
    final_status: JobStatus = "dead_lettered",
) -> JobRecord:
    job = get_job(job_id)
    job.status = final_status
    job.progress = min(job.progress, 100)
    job.error = reason
    job.completed_at = utc_now()
    job.dead_lettered_at = job.completed_at
    job.dead_letter_reason = reason
    job.dead_letter_source = source
    job.locked_by = None
    job.locked_at = None
    job.events.append(JobEvent(stage_id="job.dead_lettered", message=reason, progress=job.progress))
    save_job(job)
    return job


def record_worker_status(status: WorkerStatus) -> WorkerStatus:
    ensure_data_dirs()
    status.last_seen_at = utc_now()
    payload = json.dumps(status.model_dump(mode="json"), ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO workers (
                worker_id, status, started_at, last_seen_at, current_job_id,
                completed_jobs, failed_jobs, payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(worker_id) DO UPDATE SET
                status = excluded.status,
                started_at = excluded.started_at,
                last_seen_at = excluded.last_seen_at,
                current_job_id = excluded.current_job_id,
                completed_jobs = excluded.completed_jobs,
                failed_jobs = excluded.failed_jobs,
                payload = excluded.payload
            """,
            (
                status.worker_id,
                status.status,
                status.started_at,
                status.last_seen_at,
                status.current_job_id,
                status.completed_jobs,
                status.failed_jobs,
                payload,
            ),
        )
    return status


def list_worker_statuses(limit: int = 10) -> list[WorkerStatus]:
    ensure_data_dirs()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT payload FROM workers ORDER BY last_seen_at DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
    return [WorkerStatus.model_validate(json.loads(row["payload"])) for row in rows]


def index_project_evidence(project_id: str, chapters: list[Chapter]) -> int:
    ensure_data_dirs()
    with _connect() as conn:
        conn.execute("DELETE FROM evidence_documents WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM evidence_embeddings WHERE project_id = ?", (project_id,))
        for chapter in chapters:
            for paragraph in chapter.paragraphs:
                doc_id = f"{project_id}:{chapter.id}:{paragraph.id}"
                embedding = embed_text(f"{chapter.title}\n{paragraph.text}")
                conn.execute(
                    """
                    INSERT INTO evidence_documents (
                        doc_id, project_id, chapter_id, chapter_title,
                        paragraph_id, paragraph_index, text
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        project_id,
                        chapter.id,
                        chapter.title,
                        paragraph.id,
                        paragraph.index,
                        paragraph.text,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO evidence_embeddings (
                        doc_id, project_id, embedding_model, dimensions, vector
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        project_id,
                        "local-hash-embedding-v1",
                        len(embedding),
                        json.dumps(embedding),
                    ),
                )
        conn.execute("INSERT INTO evidence_fts(evidence_fts) VALUES ('rebuild')")
        row = conn.execute("SELECT COUNT(*) AS count FROM evidence_documents WHERE project_id = ?", (project_id,)).fetchone()
    return int(row["count"]) if row else 0


def search_project_evidence(project_id: str, query: str, limit: int = 8) -> list[SourceEvidence]:
    ensure_data_dirs()
    normalized_query = _fts_query(query)
    if not normalized_query:
        return []
    with _connect() as conn:
        fts_rows: list[sqlite3.Row] = []
        try:
            fts_rows = conn.execute(
                """
                SELECT
                    d.chapter_id,
                    d.chapter_title,
                    d.paragraph_id,
                    d.paragraph_index,
                    d.text,
                    bm25(evidence_fts) AS rank
                FROM evidence_fts
                JOIN evidence_documents d ON d.rowid = evidence_fts.rowid
                WHERE evidence_fts MATCH ? AND d.project_id = ?
                ORDER BY rank
                LIMIT ?
                """,
                (normalized_query, project_id, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            fts_rows = []
        like_rows = _search_evidence_like(conn, project_id, query, limit)
        vector_rows = _search_evidence_vector(conn, project_id, query, limit)
    return _merge_evidence_rows(fts_rows, like_rows, vector_rows, limit)


def _search_evidence_like(
    conn: sqlite3.Connection,
    project_id: str,
    query: str,
    limit: int,
) -> list[sqlite3.Row]:
    keywords = _keyword_terms(query)
    if not keywords:
        return []
    clauses = " OR ".join(["text LIKE ? OR chapter_title LIKE ?" for _ in keywords])
    params: list[str | int] = [project_id]
    for keyword in keywords:
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    params.append(limit)
    return conn.execute(
        f"""
        SELECT chapter_id, chapter_title, paragraph_id, paragraph_index, text, 0 AS rank
        FROM evidence_documents
        WHERE project_id = ? AND ({clauses})
        ORDER BY chapter_id, paragraph_index
        LIMIT ?
        """,
        tuple(params),
    ).fetchall()


def _search_evidence_vector(
    conn: sqlite3.Connection,
    project_id: str,
    query: str,
    limit: int,
) -> list[tuple[sqlite3.Row, float]]:
    query_vector = embed_text(query)
    if not any(query_vector):
        return []
    rows = conn.execute(
        """
        SELECT
            d.chapter_id,
            d.chapter_title,
            d.paragraph_id,
            d.paragraph_index,
            d.text,
            e.vector
        FROM evidence_embeddings e
        JOIN evidence_documents d ON d.doc_id = e.doc_id
        WHERE e.project_id = ?
        """,
        (project_id,),
    ).fetchall()
    scored: list[tuple[sqlite3.Row, float]] = []
    for row in rows:
        try:
            vector = [float(value) for value in json.loads(row["vector"])]
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        score = cosine_similarity(query_vector, vector)
        if score > 0:
            scored.append((row, score))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]


def _merge_evidence_rows(
    fts_rows: list[sqlite3.Row],
    like_rows: list[sqlite3.Row],
    vector_rows: list[tuple[sqlite3.Row, float]],
    limit: int,
) -> list[SourceEvidence]:
    selected: dict[str, SourceEvidence] = {}
    for index, row in enumerate(fts_rows):
        _put_search_result(selected, row, "FTS 证据库命中", max(1.0, 96.0 - index * 4.0))
    for index, row in enumerate(like_rows):
        _put_search_result(selected, row, "LIKE 证据库命中", max(1.0, 84.0 - index * 3.0))
    for index, (row, similarity) in enumerate(vector_rows):
        score = min(99.0, max(1.0, similarity * 100.0 - index * 2.0))
        _put_search_result(selected, row, "向量证据库命中", score)
    return sorted(selected.values(), key=lambda item: (-item.score, item.chapter_id, item.paragraph_index))[:limit]


def _put_search_result(
    selected: dict[str, SourceEvidence],
    row: sqlite3.Row,
    reason: str,
    score: float,
) -> None:
    evidence = SourceEvidence(
        id=f"{row['chapter_id']}:{row['paragraph_id']}",
        chapter_id=row["chapter_id"],
        chapter_title=row["chapter_title"],
        paragraph_id=row["paragraph_id"],
        paragraph_index=int(row["paragraph_index"]),
        text=row["text"],
        reason=reason,
        score=round(score, 1),
    )
    existing = selected.get(evidence.paragraph_id)
    if existing and existing.score >= evidence.score:
        return
    selected[evidence.paragraph_id] = evidence


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source_length INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                version_count INTEGER NOT NULL DEFAULT 0,
                quality_score REAL,
                validation_valid INTEGER,
                last_job_id TEXT,
                payload TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_projects_updated_at
                ON projects(updated_at DESC);

            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                result_version_id TEXT,
                queue_mode TEXT NOT NULL DEFAULT 'background',
                attempts INTEGER NOT NULL DEFAULT 0,
                payload TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_project_updated_at
                ON jobs(project_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_jobs_status
                ON jobs(status);

            CREATE TABLE IF NOT EXISTS workers (
                worker_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                current_job_id TEXT,
                completed_jobs INTEGER NOT NULL DEFAULT 0,
                failed_jobs INTEGER NOT NULL DEFAULT 0,
                payload TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_workers_last_seen
                ON workers(last_seen_at DESC);

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                token TEXT NOT NULL UNIQUE,
                project_id TEXT NOT NULL,
                member_id TEXT NOT NULL,
                member_name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL,
                payload TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_token
                ON sessions(token);
            CREATE INDEX IF NOT EXISTS idx_sessions_project
                ON sessions(project_id);

            CREATE TABLE IF NOT EXISTS evidence_documents (
                doc_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                chapter_id TEXT NOT NULL,
                chapter_title TEXT NOT NULL,
                paragraph_id TEXT NOT NULL,
                paragraph_index INTEGER NOT NULL,
                text TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_evidence_project
                ON evidence_documents(project_id);

            CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts
                USING fts5(
                    text,
                    chapter_title,
                    project_id UNINDEXED,
                    content='evidence_documents',
                    content_rowid='rowid',
                    tokenize='unicode61'
                );

            CREATE TRIGGER IF NOT EXISTS evidence_ai AFTER INSERT ON evidence_documents BEGIN
                INSERT INTO evidence_fts(rowid, text, chapter_title, project_id)
                VALUES (new.rowid, new.text, new.chapter_title, new.project_id);
            END;

            CREATE TRIGGER IF NOT EXISTS evidence_ad AFTER DELETE ON evidence_documents BEGIN
                INSERT INTO evidence_fts(evidence_fts, rowid, text, chapter_title, project_id)
                VALUES ('delete', old.rowid, old.text, old.chapter_title, old.project_id);
            END;

            CREATE TRIGGER IF NOT EXISTS evidence_au AFTER UPDATE ON evidence_documents BEGIN
                INSERT INTO evidence_fts(evidence_fts, rowid, text, chapter_title, project_id)
                VALUES ('delete', old.rowid, old.text, old.chapter_title, old.project_id);
                INSERT INTO evidence_fts(rowid, text, chapter_title, project_id)
                VALUES (new.rowid, new.text, new.chapter_title, new.project_id);
            END;

            CREATE TABLE IF NOT EXISTS evidence_embeddings (
                doc_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                embedding_model TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                vector TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_evidence_embeddings_project
                ON evidence_embeddings(project_id);
            """
        )
        _ensure_column(conn, "jobs", "queue_mode", "TEXT NOT NULL DEFAULT 'background'")
        _ensure_column(conn, "jobs", "attempts", "INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_queue ON jobs(status, queue_mode, updated_at)"
        )


def _migrate_json_files_once() -> None:
    marker = DATA_DIR / ".json_migrated"
    if marker.exists():
        return
    _migrate_projects_from_json()
    _migrate_jobs_from_json()
    marker.write_text("ok", encoding="utf-8")


def _migrate_projects_from_json() -> None:
    if not PROJECTS_DIR.exists():
        return
    for path in PROJECTS_DIR.glob("*.json"):
        try:
            project = ProjectRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
            if not _exists("projects", project.id):
                save_project(project)
        except Exception:
            continue


def _migrate_jobs_from_json() -> None:
    if not JOBS_DIR.exists():
        return
    for path in JOBS_DIR.glob("*.json"):
        try:
            job = JobRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
            if not _exists("jobs", job.id):
                save_job(job)
        except Exception:
            continue


def _exists(table: str, item_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (item_id,)).fetchone()
    return bool(row)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if any(row["name"] == column for row in rows):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _fts_query(query: str) -> str:
    tokens = _keyword_terms(query)
    return " OR ".join(tokens[:12])


def _keyword_terms(query: str) -> list[str]:
    tokens: list[str] = []
    for token in query.replace('"', " ").replace("'", " ").split():
        cleaned = "".join(ch for ch in token if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
        if not cleaned:
            continue
        tokens.append(cleaned[:32])
        if any("\u4e00" <= ch <= "\u9fff" for ch in cleaned):
            tokens.extend(cleaned[index : index + 2] for index in range(0, min(len(cleaned) - 1, 8)))
    return list(dict.fromkeys(tokens))
