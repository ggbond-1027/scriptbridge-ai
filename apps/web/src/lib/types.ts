export type SourceParagraph = {
  id: string;
  chapter_id: string;
  index: number;
  text: string;
  char_start: number;
  char_end: number;
};

export type SourceEvidence = {
  id: string;
  chapter_id: string;
  chapter_title: string;
  paragraph_id: string;
  paragraph_index: number;
  text: string;
  reason: string;
  score: number;
};

export type Chapter = {
  id: string;
  order: number;
  title: string;
  text: string;
  paragraphs: SourceParagraph[];
  summary: string;
};

export type Character = {
  id: string;
  name: string;
  role: string;
  description: string;
  goals: string[];
  aliases: string[];
  relationships: { character_id: string; type: string; description: string }[];
  arc: {
    start_state: string;
    end_state: string;
    desire: string;
    fear: string;
    turning_points: string[];
  };
  traits: string[];
  secrets: string[];
};

export type Location = {
  id: string;
  name: string;
  type: string;
  description: string;
};

export type ScriptElement = {
  id: string;
  type: string;
  text: string;
  character_id?: string | null;
  emotion?: string | null;
  parenthetical?: string | null;
  source_refs?: { chapter_id: string; paragraph_ids: string[] }[];
};

export type Scene = {
  id: string;
  chapter_ids: string[];
  source_refs: { chapter_id: string; paragraph_ids: string[] }[];
  heading: { context: string; location_id: string; time_of_day: string };
  title: string;
  dramatic_purpose: string;
  conflict: string;
  characters: string[];
  beats: string[];
  summary: string;
  elements: ScriptElement[];
  act: string;
  sequence: string;
  emotional_shift: string;
  production_notes: string[];
  rewrite_options: string[];
  quality_flags: string[];
};

export type PipelineStageReport = {
  id: string;
  name: string;
  agent: string;
  status: "pending" | "running" | "ok" | "warning" | "failed";
  summary: string;
  evidence_count: number;
  output_count: number;
  duration_ms: number;
};

export type QualityMetric = {
  id: string;
  name: string;
  score: number;
  status: "excellent" | "good" | "warning" | "critical";
  detail: string;
};

export type QualityReport = {
  overall_score: number;
  metrics: QualityMetric[];
  risks: ValidationIssue[];
  recommendations: string[];
  chapter_coverage: Record<string, number>;
};

export type ProductionBreakdown = {
  estimated_pages: number;
  estimated_runtime_minutes: number;
  cast_size: number;
  location_count: number;
  shooting_days: number;
  location_breakdowns: {
    location_id: string;
    scene_ids: string[];
    estimated_half_days: number;
    requirements: string[];
  }[];
  shot_plan: {
    scene_id: string;
    setup: string;
    camera: string;
    sound: string;
    difficulty: "low" | "medium" | "high";
  }[];
};

export type Screenplay = {
  schema_version: string;
  project: {
    id: string;
    title: string;
    source_language: string;
    target_format: string;
    adaptation_style: {
      genre: string;
      tone: string;
      dialogue_style: string;
      target_audience: string;
      episode_count: number;
      target_runtime_minutes: number;
      scene_density: "compact" | "balanced" | "expanded";
    };
  };
  story_bible: {
    characters: Character[];
    locations: Location[];
    timeline: { id: string; chapter_id: string; order: number; summary: string; character_ids: string[] }[];
    themes: { id: string; name: string; statement: string }[];
    conflicts: { id: string; title: string; stakes: string; status: string; involved_character_ids: string[] }[];
    foreshadowing: { id: string; setup: string; payoff: string; status: string }[];
    continuity_notes: string[];
  };
  chapters: Chapter[];
  scenes: Scene[];
  metadata: {
    generated_at: string;
    model: string;
    provider: string;
    provider_status: string;
    source_chapter_count: number;
    warnings: string[];
    pipeline_stages: PipelineStageReport[];
  };
  quality_report: QualityReport;
  production: ProductionBreakdown;
};

export type ValidationIssue = {
  path: string;
  message: string;
  severity: "error" | "warning";
};

export type ValidationResult = {
  valid: boolean;
  issues: ValidationIssue[];
};

export type GenerateResponse = {
  screenplay: Screenplay;
  yaml_text: string;
  validation: ValidationResult;
  provider: string;
  provider_status: string;
  warnings: string[];
};

export type RewriteSceneResponse = GenerateResponse & {
  changed_scene: Scene;
  evidence: SourceEvidence[];
  diff_summary: string[];
};

export type RewriteMode = "strengthen_conflict" | "rewrite_dialogue" | "short_drama" | "tighten_evidence";

export type CapabilitiesResponse = {
  product_tier: string;
  model_modes: string[];
  pipeline_agents: string[];
  exports: string[];
  open_source_stack: string[];
};

export type SystemReadinessStatus = "ready" | "warning" | "blocked";

export type SystemReadinessCheck = {
  id: string;
  label: string;
  status: SystemReadinessStatus;
  summary: string;
  evidence: Record<string, number | string | boolean>;
  required_for_production: boolean;
};

export type SystemReadinessResponse = {
  status: SystemReadinessStatus;
  score: number;
  environment: string;
  generated_at: string;
  checks: SystemReadinessCheck[];
  blockers: SystemReadinessCheck[];
  warnings: SystemReadinessCheck[];
  passed: SystemReadinessCheck[];
  next_actions: string[];
};

export type ModelProvider = "api" | "local" | "fallback";

export type ModelProfilePublic = {
  provider: ModelProvider;
  base_url: string;
  model: string;
  temperature: number;
  has_api_key: boolean;
  api_key_secret_ref?: string | null;
  source: "runtime" | "environment" | "fallback";
};

export type ModelProfileRuntime = Omit<ModelProfilePublic, "has_api_key" | "source"> & {
  api_key?: string | null;
};

export type ModelProfileResponse = {
  active: ModelProfilePublic;
  presets: ModelProfilePublic[];
  warnings: string[];
};

export type ModelProfileTestResponse = {
  profile: ModelProfilePublic;
  ok: boolean;
  status: string;
  provider_status: string;
  latency_ms: number;
  message: string;
  warnings: string[];
};

export type ImportSourceResponse = {
  title: string;
  text: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  detected_encoding: string;
  extraction_method: string;
  document_stats: Record<string, number | string>;
  chapter_count: number;
  paragraph_count: number;
  warnings: string[];
  security_report: ImportSecurityReport;
};

export type ImportSecurityReport = {
  scanner: string;
  verdict: "clean" | "warning" | "blocked";
  risk_level: "low" | "medium" | "high" | "critical";
  sha256: string;
  extension: string;
  detected_file_type: string;
  declared_content_type: string;
  checks: string[];
  warnings: string[];
  blocked_reasons: string[];
};

export type ImportHistoryItem = {
  job_id: string;
  project_id: string;
  status: JobRecord["status"];
  queue_mode: JobRecord["queue_mode"];
  actor: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  upload_mode: string;
  sha256: string;
  extraction_method: string;
  detected_encoding: string;
  chapter_count: number;
  paragraph_count: number;
  warning_count: number;
  warnings: string[];
  document_stats: Record<string, number | string>;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  progress: number;
  attempts: number;
  error?: string | null;
  last_stage_id: string;
  last_stage_message: string;
  audit_event_id?: string | null;
  security_report: ImportSecurityReport;
};

export type ImportHistoryResponse = {
  project_id: string;
  imports: ImportHistoryItem[];
  total: number;
  succeeded: number;
  failed: number;
  running: number;
  queued: number;
  canceled: number;
};

export type ImportSessionStatus = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  total_chunks: number;
  uploaded_chunks: number[];
  uploaded_count: number;
  status: "pending" | "completed";
  sha256: string;
  security_report?: ImportSecurityReport | null;
  project_id?: string | null;
  actor: string;
  created_at: string;
  updated_at: string;
};

export type CompleteImportSessionResponse = {
  session: ImportSessionStatus;
  job: JobRecord;
};

export type ProjectSettings = {
  style: Screenplay["project"]["adaptation_style"];
  model_provider: ModelProvider;
  model_profile?: ModelProfilePublic | null;
  require_schema_valid: boolean;
  require_source_refs: boolean;
  quality_gate_score: number;
};

export type ProjectVersion = {
  id: string;
  created_at: string;
  label: string;
  screenplay: Screenplay;
  yaml_text: string;
  validation: ValidationResult;
};

export type ProjectVersionSummary = {
  id: string;
  created_at: string;
  label: string;
  scene_count: number;
  quality_score?: number | null;
  validation_valid?: boolean | null;
  provider: string;
  provider_status: string;
  yaml_bytes: number;
  is_current: boolean;
};

export type VersionSceneChange = {
  scene_id: string;
  title_before?: string | null;
  title_after?: string | null;
  change_type: "added" | "removed" | "changed";
  summary: string;
};

export type VersionCompareResponse = {
  project_id: string;
  base_version_id: string;
  target_version_id: string;
  base_label: string;
  target_label: string;
  scene_count_delta: number;
  quality_delta: number;
  validation_changed: boolean;
  changed_scenes: VersionSceneChange[];
  yaml_diff_preview: string[];
};

export type ReadinessStatus = "ready" | "warning" | "blocked";

export type ProjectReadinessCheck = {
  id: string;
  label: string;
  status: ReadinessStatus;
  summary: string;
  evidence: Record<string, number | string | boolean>;
};

export type ProjectReadinessResponse = {
  project_id: string;
  status: ReadinessStatus;
  score: number;
  current_version_id?: string | null;
  generated_at: string;
  blockers: ProjectReadinessCheck[];
  warnings: ProjectReadinessCheck[];
  passed: ProjectReadinessCheck[];
  next_actions: string[];
};

export type ExportFormat = "yaml" | "json" | "markdown" | "fountain";

export type ProjectExportRecord = {
  id: string;
  project_id: string;
  version_id?: string | null;
  version_label: string;
  format: ExportFormat;
  status: "succeeded" | "blocked";
  actor: string;
  created_at: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  readiness_status: ReadinessStatus;
  readiness_score: number;
  blockers: string[];
  warnings: string[];
  audit_event_id?: string | null;
};

export type ProjectExportResponse = {
  export: ProjectExportRecord;
  content: string;
  readiness: ProjectReadinessResponse;
  audit_event: AuditEvent;
};

export type ProjectExportHistoryResponse = {
  project_id: string;
  exports: ProjectExportRecord[];
  total: number;
  succeeded: number;
  blocked: number;
};

export type ApprovalStatus = "submitted" | "approved" | "rejected" | "revoked" | "blocked";
export type ApprovalDecision = "approve" | "reject" | "revoke";

export type ProjectApprovalRecord = {
  id: string;
  project_id: string;
  version_id?: string | null;
  version_label: string;
  status: ApprovalStatus;
  submitted_by: string;
  submitted_at: string;
  decided_by?: string | null;
  decided_at?: string | null;
  submit_note: string;
  decision_note: string;
  requested_export_format?: ExportFormat | null;
  readiness_status: ReadinessStatus;
  readiness_score: number;
  blockers: string[];
  warnings: string[];
  audit_event_id?: string | null;
  decision_audit_event_id?: string | null;
};

export type ProjectApprovalResponse = {
  project: ProjectRecord;
  approval: ProjectApprovalRecord;
  readiness: ProjectReadinessResponse;
  audit_event: AuditEvent;
  notifications: ProjectNotification[];
};

export type ProjectApprovalHistoryResponse = {
  project_id: string;
  approvals: ProjectApprovalRecord[];
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  revoked: number;
  blocked: number;
};

export type ProjectDeliveryPackageAsset = {
  format: ExportFormat;
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  content?: string | null;
  storage_provider: string;
  storage_key: string;
  download_url: string;
  download_expires_at?: string | null;
};

export type ProjectDeliveryPackageRecord = {
  id: string;
  project_id: string;
  version_id?: string | null;
  version_label: string;
  approval_id?: string | null;
  status: "succeeded" | "blocked";
  actor: string;
  note: string;
  created_at: string;
  formats: ExportFormat[];
  assets: ProjectDeliveryPackageAsset[];
  manifest_filename: string;
  manifest_json: string;
  manifest_sha256: string;
  total_size_bytes: number;
  storage_provider: string;
  artifact_count: number;
  download_expires_at?: string | null;
  readiness_status: ReadinessStatus;
  readiness_score: number;
  blockers: string[];
  warnings: string[];
  audit_event_id?: string | null;
};

export type ProjectDeliveryPackageResponse = {
  project: ProjectRecord;
  package: ProjectDeliveryPackageRecord;
  assets: ProjectDeliveryPackageAsset[];
  readiness: ProjectReadinessResponse;
  audit_event: AuditEvent;
};

export type ProjectDeliveryPackageHistoryResponse = {
  project_id: string;
  packages: ProjectDeliveryPackageRecord[];
  total: number;
  succeeded: number;
  blocked: number;
};

export type ProjectComment = {
  id: string;
  created_at: string;
  updated_at: string;
  scene_id?: string | null;
  author: string;
  assignee?: string | null;
  body: string;
  status: "open" | "resolved";
  replies: CommentReply[];
};

export type ProjectMember = {
  id: string;
  name: string;
  role: "owner" | "admin" | "writer" | "reviewer" | "producer" | "viewer";
  joined_at: string;
  active: boolean;
};

export type ProjectSession = {
  id: string;
  token: string;
  project_id: string;
  member_id: string;
  member_name: string;
  role: ProjectMember["role"];
  created_at: string;
  last_seen_at: string;
  active: boolean;
};

export type ProjectSessionResponse = {
  session: ProjectSession;
  token: string;
  member: ProjectMember;
  project: ProjectRecord;
};

export type CommentReply = {
  id: string;
  created_at: string;
  author: string;
  body: string;
};

export type AuditEvent = {
  id: string;
  created_at: string;
  actor: string;
  event_type: string;
  target_type: string;
  target_id: string;
  summary: string;
  metadata: Record<string, string>;
};

export type ProjectNotification = {
  id: string;
  created_at: string;
  recipient: string;
  actor: string;
  event_type: string;
  target_type: string;
  target_id: string;
  summary: string;
  unread: boolean;
  metadata: Record<string, string>;
};

export type ProjectRecord = {
  id: string;
  title: string;
  source_text: string;
  settings: ProjectSettings;
  created_at: string;
  updated_at: string;
  current_version_id?: string | null;
  versions: ProjectVersion[];
  last_job_id?: string | null;
  members?: ProjectMember[];
  comments?: ProjectComment[];
  audit_events?: AuditEvent[];
  notifications?: ProjectNotification[];
  exports?: ProjectExportRecord[];
  approvals?: ProjectApprovalRecord[];
  delivery_packages?: ProjectDeliveryPackageRecord[];
};

export type ProjectSummary = {
  id: string;
  title: string;
  updated_at: string;
  source_length: number;
  version_count: number;
  quality_score?: number | null;
  validation_valid?: boolean | null;
  last_job_id?: string | null;
};

export type JobEvent = {
  at: string;
  stage_id: string;
  message: string;
  progress: number;
};

export type JobRecord = {
  id: string;
  project_id: string;
  kind: "generate" | "rewrite" | "import";
  status: "queued" | "running" | "succeeded" | "failed" | "canceled" | "dead_lettered";
  progress: number;
  created_at: string;
  updated_at: string;
  queued_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  events: JobEvent[];
  result_version_id?: string | null;
  queue_mode: "inline" | "background" | "external";
  queue_name: string;
  locked_by?: string | null;
  locked_at?: string | null;
  attempts: number;
  max_attempts: number;
  dead_lettered_at?: string | null;
  dead_letter_reason?: string | null;
  dead_letter_source?: string | null;
  requeue_count: number;
  request_payload: Record<string, unknown>;
  result_payload: Partial<ImportSourceResponse> & Record<string, unknown>;
};

export type JobSummary = {
  id: string;
  project_id: string;
  kind: string;
  status: JobRecord["status"];
  progress: number;
  updated_at: string;
  result_version_id?: string | null;
  queue_mode: JobRecord["queue_mode"];
  attempts: number;
  max_attempts: number;
  error?: string | null;
  dead_lettered_at?: string | null;
  dead_letter_reason?: string | null;
  dead_letter_source?: string | null;
  requeue_count: number;
};

export type JobQueueStatus = {
  mode: "inline" | "background" | "external";
  queued: number;
  running: number;
  failed: number;
  dead_lettered: number;
  succeeded: number;
  canceled: number;
  broker: "sqlite" | "redis";
  broker_queue: string;
  broker_depth: number;
  broker_error?: string | null;
  workers: WorkerStatus[];
  worker_hint: string;
};

export type DeadLetterQueueResponse = {
  jobs: JobSummary[];
  total: number;
  failed: number;
  dead_lettered: number;
};

export type WorkerStatus = {
  worker_id: string;
  status: "starting" | "idle" | "running" | "stopped" | "error";
  started_at: string;
  last_seen_at: string;
  completed_jobs: number;
  failed_jobs: number;
  current_job_id?: string | null;
  last_error?: string | null;
};
