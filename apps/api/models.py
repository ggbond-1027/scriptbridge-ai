from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdaptationStyle(BaseModel):
    genre: str = "悬疑短剧"
    tone: str = "克制、紧张"
    dialogue_style: str = "自然"
    target_audience: str = "短剧观众"
    episode_count: int = 1
    target_runtime_minutes: int = 12
    scene_density: Literal["compact", "balanced", "expanded"] = "balanced"


class SourceParagraph(BaseModel):
    id: str
    chapter_id: str
    index: int
    text: str
    char_start: int
    char_end: int


class Chapter(BaseModel):
    id: str
    order: int
    title: str
    text: str
    paragraphs: list[SourceParagraph] = Field(default_factory=list)
    summary: str = ""


class SourceRef(BaseModel):
    chapter_id: str
    paragraph_ids: list[str]


class SourceEvidence(BaseModel):
    id: str
    chapter_id: str
    chapter_title: str
    paragraph_id: str
    paragraph_index: int
    text: str
    reason: str
    score: float = Field(default=0, ge=0)


class AppearanceRef(BaseModel):
    chapter_id: str
    paragraph_id: str


class Relationship(BaseModel):
    character_id: str
    type: str
    description: str


class CharacterArc(BaseModel):
    start_state: str = ""
    end_state: str = ""
    desire: str = ""
    fear: str = ""
    turning_points: list[str] = Field(default_factory=list)


class Character(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    role: Literal["protagonist", "supporting", "antagonist", "minor"] = "supporting"
    description: str
    goals: list[str] = Field(default_factory=list)
    first_appearance: AppearanceRef | None = None
    relationships: list[Relationship] = Field(default_factory=list)
    arc: CharacterArc = Field(default_factory=CharacterArc)
    traits: list[str] = Field(default_factory=list)
    secrets: list[str] = Field(default_factory=list)


class Location(BaseModel):
    id: str
    name: str
    type: Literal["interior", "exterior", "mixed", "unknown"] = "unknown"
    description: str
    first_appearance: AppearanceRef | None = None


class TimelineEvent(BaseModel):
    id: str
    chapter_id: str
    order: int
    summary: str
    character_ids: list[str] = Field(default_factory=list)


class ThemeThread(BaseModel):
    id: str
    name: str
    statement: str
    evidence_refs: list[SourceRef] = Field(default_factory=list)


class ConflictThread(BaseModel):
    id: str
    title: str
    stakes: str
    status: Literal["setup", "escalating", "resolved", "open"] = "open"
    involved_character_ids: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)


class ForeshadowingThread(BaseModel):
    id: str
    setup: str
    payoff: str
    status: Literal["seeded", "paid_off", "missing_payoff"] = "seeded"
    source_refs: list[SourceRef] = Field(default_factory=list)


class StoryBible(BaseModel):
    characters: list[Character] = Field(default_factory=list)
    locations: list[Location] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    themes: list[ThemeThread] = Field(default_factory=list)
    conflicts: list[ConflictThread] = Field(default_factory=list)
    foreshadowing: list[ForeshadowingThread] = Field(default_factory=list)
    continuity_notes: list[str] = Field(default_factory=list)


class SceneHeading(BaseModel):
    context: Literal["INT", "EXT", "INT/EXT", "UNKNOWN"] = "UNKNOWN"
    location_id: str
    time_of_day: Literal["DAY", "NIGHT", "DUSK", "DAWN", "UNKNOWN"] = "UNKNOWN"


class ElementType(str, Enum):
    action = "action"
    dialogue = "dialogue"
    parenthetical = "parenthetical"
    transition = "transition"
    voice_over = "voice_over"
    shot = "shot"
    note = "note"


class ScriptElement(BaseModel):
    id: str
    type: ElementType
    text: str
    character_id: str | None = None
    emotion: str | None = None
    parenthetical: str | None = None
    source_refs: list[SourceRef] = Field(default_factory=list)


class Scene(BaseModel):
    id: str
    chapter_ids: list[str]
    source_refs: list[SourceRef]
    heading: SceneHeading
    title: str
    dramatic_purpose: str
    conflict: str
    characters: list[str]
    beats: list[str] = Field(default_factory=list)
    summary: str
    elements: list[ScriptElement] = Field(default_factory=list)
    act: str = "A"
    sequence: str = "SQ1"
    emotional_shift: str = ""
    production_notes: list[str] = Field(default_factory=list)
    rewrite_options: list[str] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)


class PipelineStageReport(BaseModel):
    id: str
    name: str
    agent: str
    status: Literal["pending", "running", "ok", "warning", "failed"] = "pending"
    summary: str
    evidence_count: int = 0
    output_count: int = 0
    duration_ms: int = 0


class ValidationIssue(BaseModel):
    path: str
    message: str
    severity: Literal["error", "warning"] = "error"


class QualityMetric(BaseModel):
    id: str
    name: str
    score: float = Field(ge=0, le=100)
    status: Literal["excellent", "good", "warning", "critical"]
    detail: str
    evidence_refs: list[SourceRef] = Field(default_factory=list)


class QualityReport(BaseModel):
    overall_score: float = Field(default=0, ge=0, le=100)
    metrics: list[QualityMetric] = Field(default_factory=list)
    risks: list[ValidationIssue] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    chapter_coverage: dict[str, float] = Field(default_factory=dict)


class ShotPlan(BaseModel):
    scene_id: str
    setup: str
    camera: str
    sound: str
    difficulty: Literal["low", "medium", "high"] = "medium"


class LocationBreakdown(BaseModel):
    location_id: str
    scene_ids: list[str] = Field(default_factory=list)
    estimated_half_days: float = 0.5
    requirements: list[str] = Field(default_factory=list)


class ProductionBreakdown(BaseModel):
    estimated_pages: float = 0
    estimated_runtime_minutes: float = 0
    cast_size: int = 0
    location_count: int = 0
    shooting_days: int = 1
    location_breakdowns: list[LocationBreakdown] = Field(default_factory=list)
    shot_plan: list[ShotPlan] = Field(default_factory=list)


class ScreenplayProject(BaseModel):
    id: str = "proj_001"
    title: str
    source_language: str = "zh-CN"
    target_format: str = "screenplay"
    adaptation_style: AdaptationStyle = Field(default_factory=AdaptationStyle)


class GenerationMetadata(BaseModel):
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    model: str = "fallback"
    provider: str = "fallback"
    provider_status: str = "fallback"
    source_chapter_count: int
    warnings: list[str] = Field(default_factory=list)
    pipeline_stages: list[PipelineStageReport] = Field(default_factory=list)


class Screenplay(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    schema_version: str = "1.0"
    project: ScreenplayProject
    story_bible: StoryBible
    chapters: list[Chapter]
    scenes: list[Scene]
    metadata: GenerationMetadata
    quality_report: QualityReport = Field(default_factory=QualityReport)
    production: ProductionBreakdown = Field(default_factory=ProductionBreakdown)


class DetectChaptersRequest(BaseModel):
    text: str


class GenerateRequest(BaseModel):
    text: str
    title: str = "未命名改编项目"
    style: AdaptationStyle = Field(default_factory=AdaptationStyle)
    use_llm: bool = True
    model_profile: "ModelProfileRuntime | None" = None


class ValidateRequest(BaseModel):
    yaml_text: str


class SearchEvidenceRequest(BaseModel):
    query: str
    limit: int = Field(default=8, ge=1, le=30)


class ImportSourceResponse(BaseModel):
    title: str
    text: str
    filename: str
    content_type: str = "text/plain"
    size_bytes: int
    sha256: str = ""
    detected_encoding: str
    extraction_method: str = "plain-text"
    document_stats: dict[str, int | str] = Field(default_factory=dict)
    chapter_count: int
    paragraph_count: int
    warnings: list[str] = Field(default_factory=list)
    security_report: "ImportSecurityReport" = Field(default_factory=lambda: ImportSecurityReport())


class ImportSecurityReport(BaseModel):
    scanner: str = "local-static-import-scan-v1"
    verdict: Literal["clean", "warning", "blocked"] = "clean"
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    sha256: str = ""
    extension: str = ""
    detected_file_type: str = "unknown"
    declared_content_type: str = ""
    checks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)


class ImportHistoryItem(BaseModel):
    job_id: str
    project_id: str
    status: Literal["queued", "running", "succeeded", "failed", "canceled", "dead_lettered"]
    queue_mode: Literal["inline", "background", "external"]
    actor: str = "system"
    filename: str = ""
    content_type: str = ""
    size_bytes: int = 0
    upload_mode: str = "multipart"
    sha256: str = ""
    extraction_method: str = ""
    detected_encoding: str = ""
    chapter_count: int = 0
    paragraph_count: int = 0
    warning_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    document_stats: dict[str, int | str] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    completed_at: str | None = None
    progress: int = 0
    attempts: int = 0
    error: str | None = None
    last_stage_id: str = ""
    last_stage_message: str = ""
    audit_event_id: str | None = None
    security_report: ImportSecurityReport = Field(default_factory=ImportSecurityReport)


class ImportHistoryResponse(BaseModel):
    project_id: str
    imports: list[ImportHistoryItem] = Field(default_factory=list)
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    dead_lettered: int = 0
    running: int = 0
    queued: int = 0
    canceled: int = 0


class CreateImportSessionRequest(BaseModel):
    filename: str
    content_type: str = "application/octet-stream"
    size_bytes: int = Field(ge=1, le=8_000_000)
    total_chunks: int = Field(ge=1, le=512)
    project_id: str | None = None
    actor: str = "system"


class ImportSessionStatus(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    total_chunks: int
    uploaded_chunks: list[int] = Field(default_factory=list)
    uploaded_count: int = 0
    status: Literal["pending", "completed"]
    sha256: str = ""
    security_report: ImportSecurityReport | None = None
    project_id: str | None = None
    actor: str = "system"
    created_at: str
    updated_at: str


class CompleteImportSessionResponse(BaseModel):
    session: ImportSessionStatus
    job: "JobRecord"


class ExportRequest(BaseModel):
    screenplay: Screenplay


class ValidationResult(BaseModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    screenplay: Screenplay
    yaml_text: str
    validation: ValidationResult
    provider: str
    provider_status: str
    warnings: list[str] = Field(default_factory=list)


class RewriteSceneRequest(BaseModel):
    screenplay: Screenplay
    scene_id: str
    instruction: str = "增强冲突和可拍性"
    mode: Literal["strengthen_conflict", "rewrite_dialogue", "short_drama", "tighten_evidence"] = "strengthen_conflict"
    use_llm: bool = True
    model_profile: "ModelProfileRuntime | None" = None


RewriteMode = Literal["strengthen_conflict", "rewrite_dialogue", "short_drama", "tighten_evidence"]


class StartRewriteJobRequest(BaseModel):
    project_id: str
    actor: str = "编剧"
    scene_ids: list[str] = Field(default_factory=list)
    instruction: str = "批量强化低质量场景，并保留原文证据链。"
    mode: RewriteMode = "tighten_evidence"
    use_llm: bool = True
    max_scenes: int = Field(default=5, ge=1, le=20)
    model_profile: "ModelProfileRuntime | None" = None


class RewriteSceneResponse(BaseModel):
    screenplay: Screenplay
    yaml_text: str
    validation: ValidationResult
    changed_scene: Scene
    evidence: list[SourceEvidence] = Field(default_factory=list)
    diff_summary: list[str] = Field(default_factory=list)
    provider: str
    provider_status: str
    warnings: list[str] = Field(default_factory=list)


class CapabilitiesResponse(BaseModel):
    product_tier: str = "enterprise-v2"
    model_modes: list[str] = Field(default_factory=lambda: ["api", "local", "fallback"])
    pipeline_agents: list[str] = Field(default_factory=list)
    exports: list[str] = Field(default_factory=lambda: ["yaml", "json", "markdown", "fountain"])
    open_source_stack: list[str] = Field(default_factory=list)


SystemReadinessStatus = Literal["ready", "warning", "blocked"]


class SystemReadinessCheck(BaseModel):
    id: str
    label: str
    status: SystemReadinessStatus
    summary: str
    evidence: dict[str, str | int | float | bool] = Field(default_factory=dict)
    required_for_production: bool = True


class SystemReadinessResponse(BaseModel):
    status: SystemReadinessStatus
    score: int = Field(default=0, ge=0, le=100)
    environment: str = "local"
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    checks: list[SystemReadinessCheck] = Field(default_factory=list)
    blockers: list[SystemReadinessCheck] = Field(default_factory=list)
    warnings: list[SystemReadinessCheck] = Field(default_factory=list)
    passed: list[SystemReadinessCheck] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


ModelProvider = Literal["api", "local", "fallback"]


class ModelProfilePublic(BaseModel):
    provider: ModelProvider = "api"
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.5"
    temperature: float = Field(default=0.4, ge=0, le=2)
    has_api_key: bool = False
    api_key_secret_ref: str | None = None
    source: Literal["runtime", "environment", "fallback"] = "runtime"


class ModelProfileRuntime(BaseModel):
    provider: ModelProvider = "api"
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.5"
    api_key: str | None = None
    api_key_secret_ref: str | None = None
    temperature: float = Field(default=0.4, ge=0, le=2)

    @field_validator("base_url")
    @classmethod
    def normalize_base_url(cls, value: str) -> str:
        return (value or "").strip().rstrip("/") or "https://api.openai.com/v1"

    @field_validator("model")
    @classmethod
    def normalize_model(cls, value: str) -> str:
        return (value or "").strip() or "gpt-5.5"

    @field_validator("api_key")
    @classmethod
    def normalize_api_key(cls, value: str | None) -> str | None:
        stripped = (value or "").strip()
        return stripped or None

    @field_validator("api_key_secret_ref")
    @classmethod
    def normalize_api_key_secret_ref(cls, value: str | None) -> str | None:
        stripped = (value or "").strip()
        return stripped or None

    def to_public(self, source: Literal["runtime", "environment", "fallback"] = "runtime") -> ModelProfilePublic:
        return ModelProfilePublic(
            provider=self.provider,
            base_url=self.base_url,
            model=self.model,
            temperature=self.temperature,
            has_api_key=bool(self.api_key or self.api_key_secret_ref),
            api_key_secret_ref=self.api_key_secret_ref,
            source=source,
        )


class ModelProfileResponse(BaseModel):
    active: ModelProfilePublic
    presets: list[ModelProfilePublic] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ModelProfileTestRequest(BaseModel):
    profile: ModelProfileRuntime


class ModelProfileTestResponse(BaseModel):
    profile: ModelProfilePublic
    ok: bool
    status: str
    provider_status: str
    latency_ms: int = 0
    message: str
    warnings: list[str] = Field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectSettings(BaseModel):
    style: AdaptationStyle = Field(default_factory=AdaptationStyle)
    model_provider: ModelProvider = "api"
    model_profile: ModelProfilePublic | None = None
    require_schema_valid: bool = True
    require_source_refs: bool = True
    quality_gate_score: int = 80


class ProjectVersion(BaseModel):
    id: str
    created_at: str = Field(default_factory=utc_now)
    label: str
    screenplay: Screenplay
    yaml_text: str
    validation: ValidationResult


class ProjectVersionSummary(BaseModel):
    id: str
    created_at: str
    label: str
    scene_count: int = 0
    quality_score: float | None = None
    validation_valid: bool | None = None
    provider: str = ""
    provider_status: str = ""
    yaml_bytes: int = 0
    is_current: bool = False


class VersionSceneChange(BaseModel):
    scene_id: str
    title_before: str | None = None
    title_after: str | None = None
    change_type: Literal["added", "removed", "changed"]
    summary: str


class VersionCompareResponse(BaseModel):
    project_id: str
    base_version_id: str
    target_version_id: str
    base_label: str
    target_label: str
    scene_count_delta: int = 0
    quality_delta: float = 0
    validation_changed: bool = False
    changed_scenes: list[VersionSceneChange] = Field(default_factory=list)
    yaml_diff_preview: list[str] = Field(default_factory=list)


ReadinessStatus = Literal["ready", "warning", "blocked"]


class ProjectReadinessCheck(BaseModel):
    id: str
    label: str
    status: ReadinessStatus
    summary: str
    evidence: dict[str, int | float | str | bool] = Field(default_factory=dict)


class ProjectReadinessResponse(BaseModel):
    project_id: str
    status: ReadinessStatus
    score: int = Field(default=0, ge=0, le=100)
    current_version_id: str | None = None
    generated_at: str = Field(default_factory=utc_now)
    blockers: list[ProjectReadinessCheck] = Field(default_factory=list)
    warnings: list[ProjectReadinessCheck] = Field(default_factory=list)
    passed: list[ProjectReadinessCheck] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


ExportFormat = Literal["yaml", "json", "markdown", "fountain"]
ExportStatus = Literal["succeeded", "blocked"]
ApprovalStatus = Literal["submitted", "approved", "rejected", "revoked", "blocked"]
ApprovalDecision = Literal["approve", "reject", "revoke"]
DeliveryPackageStatus = Literal["succeeded", "blocked"]


class ProjectExportRequest(BaseModel):
    format: ExportFormat = "yaml"
    actor: str = "制片"
    version_id: str | None = None
    enforce_readiness: bool = True


class ProjectExportRecord(BaseModel):
    id: str
    project_id: str
    version_id: str | None = None
    version_label: str = ""
    format: ExportFormat = "yaml"
    status: ExportStatus = "succeeded"
    actor: str = "制片"
    created_at: str = Field(default_factory=utc_now)
    filename: str = ""
    content_type: str = "text/plain"
    size_bytes: int = 0
    sha256: str = ""
    readiness_status: ReadinessStatus = "blocked"
    readiness_score: int = 0
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    audit_event_id: str | None = None


class ProjectExportResponse(BaseModel):
    export: ProjectExportRecord
    content: str = ""
    readiness: ProjectReadinessResponse
    audit_event: AuditEvent


class ProjectExportHistoryResponse(BaseModel):
    project_id: str
    exports: list[ProjectExportRecord] = Field(default_factory=list)
    total: int = 0
    succeeded: int = 0
    blocked: int = 0


class ProjectApprovalRequest(BaseModel):
    version_id: str | None = None
    actor: str = "编剧"
    note: str = ""
    requested_export_format: ExportFormat | None = None
    enforce_readiness: bool = True


class ProjectApprovalDecisionRequest(BaseModel):
    actor: str = "制片"
    decision: ApprovalDecision = "approve"
    note: str = ""


class ProjectApprovalRecord(BaseModel):
    id: str
    project_id: str
    version_id: str | None = None
    version_label: str = ""
    status: ApprovalStatus = "submitted"
    submitted_by: str = "编剧"
    submitted_at: str = Field(default_factory=utc_now)
    decided_by: str | None = None
    decided_at: str | None = None
    submit_note: str = ""
    decision_note: str = ""
    requested_export_format: ExportFormat | None = None
    readiness_status: ReadinessStatus = "blocked"
    readiness_score: int = 0
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    audit_event_id: str | None = None
    decision_audit_event_id: str | None = None


class ProjectApprovalResponse(BaseModel):
    project: "ProjectRecord"
    approval: ProjectApprovalRecord
    readiness: ProjectReadinessResponse
    audit_event: "AuditEvent"
    notifications: list["ProjectNotification"] = Field(default_factory=list)


class ProjectApprovalHistoryResponse(BaseModel):
    project_id: str
    approvals: list[ProjectApprovalRecord] = Field(default_factory=list)
    total: int = 0
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    revoked: int = 0
    blocked: int = 0


class ProjectDeliveryPackageRequest(BaseModel):
    actor: str = "制片"
    approval_id: str | None = None
    version_id: str | None = None
    formats: list[ExportFormat] = Field(default_factory=lambda: ["yaml", "markdown", "fountain"])
    enforce_readiness: bool = True
    require_approval: bool = True
    note: str = ""

    @field_validator("formats")
    @classmethod
    def normalize_formats(cls, value: list[ExportFormat]) -> list[ExportFormat]:
        unique: list[ExportFormat] = []
        for item in value:
            if item not in unique:
                unique.append(item)
        return unique or ["yaml"]


class ProjectDeliveryPackageAsset(BaseModel):
    format: ExportFormat
    filename: str
    content_type: str
    size_bytes: int = 0
    sha256: str = ""
    content: str | None = None
    storage_provider: str = "local"
    storage_key: str = ""
    download_url: str = ""
    download_expires_at: str | None = None


class ProjectDeliveryPackageRecord(BaseModel):
    id: str
    project_id: str
    version_id: str | None = None
    version_label: str = ""
    approval_id: str | None = None
    status: DeliveryPackageStatus = "succeeded"
    actor: str = "制片"
    note: str = ""
    created_at: str = Field(default_factory=utc_now)
    formats: list[ExportFormat] = Field(default_factory=list)
    assets: list[ProjectDeliveryPackageAsset] = Field(default_factory=list)
    manifest_filename: str = ""
    manifest_json: str = ""
    manifest_sha256: str = ""
    total_size_bytes: int = 0
    storage_provider: str = "local"
    artifact_count: int = 0
    download_expires_at: str | None = None
    readiness_status: ReadinessStatus = "blocked"
    readiness_score: int = 0
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    audit_event_id: str | None = None


class ProjectDeliveryPackageResponse(BaseModel):
    project: "ProjectRecord"
    package: ProjectDeliveryPackageRecord
    assets: list[ProjectDeliveryPackageAsset] = Field(default_factory=list)
    readiness: ProjectReadinessResponse
    audit_event: "AuditEvent"


class ProjectDeliveryPackageHistoryResponse(BaseModel):
    project_id: str
    packages: list[ProjectDeliveryPackageRecord] = Field(default_factory=list)
    total: int = 0
    succeeded: int = 0
    blocked: int = 0


class RestoreProjectVersionRequest(BaseModel):
    actor: str = "项目负责人"


MemberRole = Literal["owner", "admin", "writer", "reviewer", "producer", "viewer"]


class ProjectMember(BaseModel):
    id: str
    name: str
    role: MemberRole = "viewer"
    joined_at: str = Field(default_factory=utc_now)
    active: bool = True


class ProjectSession(BaseModel):
    id: str
    token: str
    project_id: str
    member_id: str
    member_name: str
    role: MemberRole = "viewer"
    created_at: str = Field(default_factory=utc_now)
    last_seen_at: str = Field(default_factory=utc_now)
    active: bool = True


class CommentReply(BaseModel):
    id: str
    created_at: str = Field(default_factory=utc_now)
    author: str = "审阅者"
    body: str


class ProjectComment(BaseModel):
    id: str
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    scene_id: str | None = None
    author: str = "审阅者"
    assignee: str | None = None
    body: str
    status: Literal["open", "resolved"] = "open"
    replies: list[CommentReply] = Field(default_factory=list)


class AuditEvent(BaseModel):
    id: str
    created_at: str = Field(default_factory=utc_now)
    actor: str = "system"
    event_type: str
    target_type: str
    target_id: str
    summary: str
    metadata: dict[str, str] = Field(default_factory=dict)


class ProjectNotification(BaseModel):
    id: str
    created_at: str = Field(default_factory=utc_now)
    recipient: str
    actor: str
    event_type: str
    target_type: str
    target_id: str
    summary: str
    unread: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)


class ProjectRecord(BaseModel):
    id: str
    title: str
    source_text: str = ""
    settings: ProjectSettings = Field(default_factory=ProjectSettings)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    current_version_id: str | None = None
    versions: list[ProjectVersion] = Field(default_factory=list)
    last_job_id: str | None = None
    members: list[ProjectMember] = Field(default_factory=list)
    comments: list[ProjectComment] = Field(default_factory=list)
    audit_events: list[AuditEvent] = Field(default_factory=list)
    notifications: list[ProjectNotification] = Field(default_factory=list)
    exports: list[ProjectExportRecord] = Field(default_factory=list)
    approvals: list[ProjectApprovalRecord] = Field(default_factory=list)
    delivery_packages: list[ProjectDeliveryPackageRecord] = Field(default_factory=list)


class ProjectSummary(BaseModel):
    id: str
    title: str
    updated_at: str
    source_length: int
    version_count: int
    quality_score: float | None = None
    validation_valid: bool | None = None
    last_job_id: str | None = None


class CreateProjectRequest(BaseModel):
    title: str = "未命名改编项目"
    source_text: str = ""
    settings: ProjectSettings = Field(default_factory=ProjectSettings)


class UpdateProjectRequest(BaseModel):
    title: str | None = None
    source_text: str | None = None
    settings: ProjectSettings | None = None


class AddProjectMemberRequest(BaseModel):
    actor: str = "项目负责人"
    name: str
    role: MemberRole = "viewer"


class AddProjectMemberResponse(BaseModel):
    project: ProjectRecord
    member: ProjectMember
    audit_event: AuditEvent


class CreateProjectSessionRequest(BaseModel):
    project_id: str
    member_name: str = "审阅者"


class ProjectSessionResponse(BaseModel):
    session: ProjectSession
    token: str
    member: ProjectMember
    project: ProjectRecord


class CreateCommentRequest(BaseModel):
    scene_id: str | None = None
    author: str = "审阅者"
    assignee: str | None = None
    body: str
    status: Literal["open", "resolved"] = "open"


class CreateCommentResponse(BaseModel):
    project: ProjectRecord
    comment: ProjectComment
    audit_event: AuditEvent
    notifications: list[ProjectNotification] = Field(default_factory=list)


class UpdateCommentRequest(BaseModel):
    author: str = "审阅者"
    status: Literal["open", "resolved"]


class UpdateCommentResponse(BaseModel):
    project: ProjectRecord
    comment: ProjectComment
    audit_event: AuditEvent


class CreateCommentReplyRequest(BaseModel):
    author: str = "审阅者"
    body: str


class CreateCommentReplyResponse(BaseModel):
    project: ProjectRecord
    comment: ProjectComment
    reply: CommentReply
    audit_event: AuditEvent
    notifications: list[ProjectNotification] = Field(default_factory=list)


class AuditEventsResponse(BaseModel):
    audit_events: list[AuditEvent] = Field(default_factory=list)


class NotificationsResponse(BaseModel):
    notifications: list[ProjectNotification] = Field(default_factory=list)


class UpdateNotificationRequest(BaseModel):
    actor: str = "审阅者"
    unread: bool


class UpdateNotificationResponse(BaseModel):
    project: ProjectRecord
    notification: ProjectNotification
    audit_event: AuditEvent


class StartGenerationJobRequest(BaseModel):
    project_id: str
    use_llm: bool = True
    model_profile: ModelProfileRuntime | None = None


JobQueueMode = Literal["inline", "background", "external"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "canceled", "dead_lettered"]


class JobEvent(BaseModel):
    at: str = Field(default_factory=utc_now)
    stage_id: str
    message: str
    progress: int = Field(ge=0, le=100)


class JobRecord(BaseModel):
    id: str
    project_id: str
    kind: Literal["generate", "rewrite", "import"] = "generate"
    status: JobStatus = "queued"
    progress: int = Field(default=0, ge=0, le=100)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    queued_at: str = Field(default_factory=utc_now)
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    events: list[JobEvent] = Field(default_factory=list)
    result_version_id: str | None = None
    queue_mode: JobQueueMode = "background"
    queue_name: str = "default"
    locked_by: str | None = None
    locked_at: str | None = None
    attempts: int = 0
    max_attempts: int = 3
    dead_lettered_at: str | None = None
    dead_letter_reason: str | None = None
    dead_letter_source: str | None = None
    requeue_count: int = 0
    request_payload: dict[str, object] = Field(default_factory=dict)
    result_payload: dict[str, object] = Field(default_factory=dict)


class JobSummary(BaseModel):
    id: str
    project_id: str
    kind: str
    status: str
    progress: int
    updated_at: str
    result_version_id: str | None = None
    queue_mode: JobQueueMode = "background"
    attempts: int = 0
    max_attempts: int = 3
    error: str | None = None
    dead_lettered_at: str | None = None
    dead_letter_reason: str | None = None
    dead_letter_source: str | None = None
    requeue_count: int = 0


class WorkerStatus(BaseModel):
    worker_id: str
    status: Literal["starting", "idle", "running", "stopped", "error"] = "idle"
    started_at: str
    last_seen_at: str
    completed_jobs: int = 0
    failed_jobs: int = 0
    current_job_id: str | None = None
    last_error: str | None = None


class JobQueueStatus(BaseModel):
    mode: JobQueueMode
    queued: int = 0
    running: int = 0
    failed: int = 0
    dead_lettered: int = 0
    succeeded: int = 0
    canceled: int = 0
    broker: Literal["sqlite", "redis"] = "sqlite"
    broker_queue: str = "sqlite:jobs"
    broker_depth: int = 0
    broker_error: str | None = None
    workers: list[WorkerStatus] = Field(default_factory=list)
    worker_hint: str


class DeadLetterQueueResponse(BaseModel):
    jobs: list[JobSummary] = Field(default_factory=list)
    total: int = 0
    failed: int = 0
    dead_lettered: int = 0


class UpdateJobRequest(BaseModel):
    actor: str = "项目负责人"
    action: Literal["cancel", "retry"]
