import type {
  CapabilitiesResponse,
  AuditEvent,
  Chapter,
  CommentReply,
  GenerateResponse,
  CompleteImportSessionResponse,
  DeadLetterQueueResponse,
  ImportHistoryResponse,
  ImportSessionStatus,
  ImportSourceResponse,
  JobQueueStatus,
  JobRecord,
  ModelProfileResponse,
  ModelProfileRuntime,
  ModelProfileTestResponse,
  ExportFormat,
  ApprovalDecision,
  ProjectApprovalHistoryResponse,
  ProjectApprovalResponse,
  ProjectDeliveryPackageHistoryResponse,
  ProjectDeliveryPackageResponse,
  ProjectExportHistoryResponse,
  ProjectExportResponse,
  ProjectComment,
  ProjectMember,
  ProjectNotification,
  ProjectRecord,
  ProjectReadinessResponse,
  ProjectSessionResponse,
  ProjectSettings,
  ProjectSummary,
  ProjectVersionSummary,
  RewriteMode,
  RewriteSceneResponse,
  Screenplay,
  SourceEvidence,
  SystemReadinessResponse,
  ValidationResult,
  VersionCompareResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

let activeSessionToken: string | null = null;

export function resolveApiUrl(pathOrUrl: string) {
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  const normalized = pathOrUrl.startsWith("/") ? pathOrUrl : `/${pathOrUrl}`;
  return `${API_BASE}${normalized}`;
}

export function setActiveSessionToken(token: string | null) {
  activeSessionToken = token;
}

export function getActiveSessionToken() {
  return activeSessionToken;
}

type ApiRequestInit = RequestInit & { skipAuth?: boolean };

async function request<T>(path: string, options?: ApiRequestInit): Promise<T> {
  const { skipAuth, ...fetchOptions } = options ?? {};
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(!skipAuth && activeSessionToken ? { Authorization: `Bearer ${activeSessionToken}` } : {}),
    ...(fetchOptions.headers ?? {}),
  };
  const response = await fetch(`${API_BASE}${path}`, {
    ...fetchOptions,
    headers,
  });

  if (!response.ok) {
    const text = await response.text();
    let detailMessage = "";
    try {
      const payload = JSON.parse(text) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        detailMessage = payload.detail;
      }
    } catch {
      detailMessage = "";
    }
    throw new Error(detailMessage || text || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function requestJsonWithDetail<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(activeSessionToken ? { Authorization: `Bearer ${activeSessionToken}` } : {}),
    ...(options?.headers ?? {}),
  };
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }
  if (!response.ok) {
    const error = new Error(readErrorMessage(payload, text, response.status));
    (error as Error & { detail?: unknown }).detail = payload;
    throw error;
  }
  return payload as T;
}

function readErrorMessage(payload: unknown, fallback: string, status: number) {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      const message = (detail as { message?: unknown }).message;
      if (typeof message === "string") return message;
    }
  }
  return fallback || `HTTP ${status}`;
}

export async function getSample(): Promise<{ title: string; text: string }> {
  return request("/api/sample");
}

export async function importSourceFile(file: File): Promise<ImportSourceResponse> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}/api/import/source`, {
    method: "POST",
    headers: {
      ...(activeSessionToken ? { Authorization: `Bearer ${activeSessionToken}` } : {}),
    },
    body: form,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<ImportSourceResponse>;
}

export async function startImportSourceJob(params: {
  file: File;
  projectId?: string | null;
  actor?: string;
}): Promise<JobRecord> {
  const form = new FormData();
  form.append("file", params.file);
  if (params.projectId) {
    form.append("project_id", params.projectId);
  }
  if (params.actor) {
    form.append("actor", params.actor);
  }
  const response = await fetch(`${API_BASE}/api/jobs/import-source`, {
    method: "POST",
    headers: {
      ...(activeSessionToken ? { Authorization: `Bearer ${activeSessionToken}` } : {}),
    },
    body: form,
  });
  if (!response.ok) {
    const text = await response.text();
    let detailMessage = "";
    try {
      const payload = JSON.parse(text) as { detail?: unknown };
      if (typeof payload.detail === "string") {
        detailMessage = payload.detail;
      }
    } catch {
      detailMessage = "";
    }
    throw new Error(detailMessage || text || `HTTP ${response.status}`);
  }
  return response.json() as Promise<JobRecord>;
}

export async function createImportSession(params: {
  file: File;
  totalChunks: number;
  projectId?: string | null;
  actor?: string;
}): Promise<ImportSessionStatus> {
  return request("/api/import-sessions", {
    method: "POST",
    body: JSON.stringify({
      filename: params.file.name,
      content_type: params.file.type || "application/octet-stream",
      size_bytes: params.file.size,
      total_chunks: params.totalChunks,
      project_id: params.projectId ?? null,
      actor: params.actor ?? "system",
    }),
  });
}

export async function uploadImportSessionChunk(params: {
  sessionId: string;
  chunkIndex: number;
  chunk: Blob;
}): Promise<ImportSessionStatus> {
  const response = await fetch(`${API_BASE}/api/import-sessions/${params.sessionId}/chunks/${params.chunkIndex}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/octet-stream",
      ...(activeSessionToken ? { Authorization: `Bearer ${activeSessionToken}` } : {}),
    },
    body: params.chunk,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<ImportSessionStatus>;
}

export async function completeImportSession(sessionId: string): Promise<CompleteImportSessionResponse> {
  return request(`/api/import-sessions/${sessionId}/complete`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function getCapabilities(): Promise<CapabilitiesResponse> {
  return request("/api/capabilities");
}

export async function getSystemReadiness(): Promise<SystemReadinessResponse> {
  return request("/api/system-readiness");
}

export async function getModelProfiles(): Promise<ModelProfileResponse> {
  return request("/api/model-profiles");
}

export async function testModelProfile(profile: ModelProfileRuntime): Promise<ModelProfileTestResponse> {
  return request("/api/model-profiles/test", {
    method: "POST",
    body: JSON.stringify({ profile }),
  });
}

export async function listProjects(): Promise<{ projects: ProjectSummary[] }> {
  return request("/api/projects");
}

export async function createProject(params: {
  title: string;
  sourceText: string;
  settings: ProjectSettings;
}): Promise<ProjectRecord> {
  return request("/api/projects", {
    method: "POST",
    body: JSON.stringify({
      title: params.title,
      source_text: params.sourceText,
      settings: params.settings,
    }),
  });
}

export async function createProjectSession(params: {
  projectId: string;
  memberName: string;
}): Promise<ProjectSessionResponse> {
  return request("/api/auth/sessions", {
    method: "POST",
    body: JSON.stringify({
      project_id: params.projectId,
      member_name: params.memberName,
    }),
  });
}

export async function getProject(projectId: string): Promise<ProjectRecord> {
  return request(`/api/projects/${projectId}`);
}

export async function getProjectReadiness(projectId: string): Promise<ProjectReadinessResponse> {
  return request(`/api/projects/${projectId}/readiness`);
}

export async function listProjectExports(params: {
  projectId: string;
  limit?: number;
}): Promise<ProjectExportHistoryResponse> {
  const query = new URLSearchParams();
  if (params.limit) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request(`/api/projects/${params.projectId}/exports${suffix}`);
}

export async function createProjectExport(params: {
  projectId: string;
  format: ExportFormat;
  actor: string;
  versionId?: string | null;
  enforceReadiness?: boolean;
}): Promise<ProjectExportResponse> {
  return requestJsonWithDetail(`/api/projects/${params.projectId}/exports`, {
    method: "POST",
    body: JSON.stringify({
      format: params.format,
      actor: params.actor,
      version_id: params.versionId ?? null,
      enforce_readiness: params.enforceReadiness ?? true,
    }),
  });
}

export async function listProjectApprovals(params: {
  projectId: string;
  limit?: number;
}): Promise<ProjectApprovalHistoryResponse> {
  const query = new URLSearchParams();
  if (params.limit) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request(`/api/projects/${params.projectId}/approvals${suffix}`);
}

export async function createProjectApproval(params: {
  projectId: string;
  actor: string;
  versionId?: string | null;
  note?: string;
  requestedExportFormat?: ExportFormat | null;
  enforceReadiness?: boolean;
}): Promise<ProjectApprovalResponse> {
  return requestJsonWithDetail(`/api/projects/${params.projectId}/approvals`, {
    method: "POST",
    body: JSON.stringify({
      actor: params.actor,
      version_id: params.versionId ?? null,
      note: params.note ?? "",
      requested_export_format: params.requestedExportFormat ?? null,
      enforce_readiness: params.enforceReadiness ?? true,
    }),
  });
}

export async function decideProjectApproval(params: {
  projectId: string;
  approvalId: string;
  actor: string;
  decision: ApprovalDecision;
  note?: string;
}): Promise<ProjectApprovalResponse> {
  return request(`/api/projects/${params.projectId}/approvals/${params.approvalId}/decision`, {
    method: "POST",
    body: JSON.stringify({
      actor: params.actor,
      decision: params.decision,
      note: params.note ?? "",
    }),
  });
}

export async function listProjectDeliveryPackages(params: {
  projectId: string;
  limit?: number;
  actor?: string | null;
  skipAuth?: boolean;
}): Promise<ProjectDeliveryPackageHistoryResponse> {
  const query = new URLSearchParams();
  if (params.limit) query.set("limit", String(params.limit));
  if (params.actor) query.set("actor", params.actor);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request(`/api/projects/${params.projectId}/delivery-packages${suffix}`, { skipAuth: params.skipAuth });
}

export async function createProjectDeliveryPackage(params: {
  projectId: string;
  actor: string;
  approvalId?: string | null;
  versionId?: string | null;
  formats: ExportFormat[];
  enforceReadiness?: boolean;
  requireApproval?: boolean;
  note?: string;
}): Promise<ProjectDeliveryPackageResponse> {
  return requestJsonWithDetail(`/api/projects/${params.projectId}/delivery-packages`, {
    method: "POST",
    body: JSON.stringify({
      actor: params.actor,
      approval_id: params.approvalId ?? null,
      version_id: params.versionId ?? null,
      formats: params.formats,
      enforce_readiness: params.enforceReadiness ?? true,
      require_approval: params.requireApproval ?? true,
      note: params.note ?? "",
    }),
  });
}

export async function updateProject(params: {
  projectId: string;
  title?: string;
  sourceText?: string;
  settings?: ProjectSettings;
}): Promise<ProjectRecord> {
  return request(`/api/projects/${params.projectId}`, {
    method: "PATCH",
    body: JSON.stringify({
      ...(params.title !== undefined ? { title: params.title } : {}),
      ...(params.sourceText !== undefined ? { source_text: params.sourceText } : {}),
      ...(params.settings !== undefined ? { settings: params.settings } : {}),
    }),
  });
}

export async function listProjectVersions(projectId: string): Promise<{ versions: ProjectVersionSummary[] }> {
  return request(`/api/projects/${projectId}/versions`);
}

export async function compareProjectVersions(params: {
  projectId: string;
  baseVersionId: string;
  targetVersionId: string;
}): Promise<VersionCompareResponse> {
  const query = new URLSearchParams({
    base_version_id: params.baseVersionId,
    target_version_id: params.targetVersionId,
  });
  return request(`/api/projects/${params.projectId}/versions/compare?${query.toString()}`);
}

export async function restoreProjectVersion(params: {
  projectId: string;
  versionId: string;
  actor: string;
}): Promise<ProjectRecord> {
  return request(`/api/projects/${params.projectId}/versions/${params.versionId}/restore`, {
    method: "POST",
    body: JSON.stringify({ actor: params.actor }),
  });
}

export async function listProjectImportHistory(params: {
  projectId: string;
  limit?: number;
}): Promise<ImportHistoryResponse> {
  const query = new URLSearchParams();
  if (params.limit) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request(`/api/projects/${params.projectId}/import-history${suffix}`);
}

export async function addProjectMember(params: {
  projectId: string;
  actor: string;
  name: string;
  role: ProjectMember["role"];
}): Promise<{ project: ProjectRecord; member: ProjectMember; audit_event: AuditEvent }> {
  return request(`/api/projects/${params.projectId}/members`, {
    method: "POST",
    body: JSON.stringify({
      actor: params.actor,
      name: params.name,
      role: params.role,
    }),
  });
}

export async function createProjectComment(params: {
  projectId: string;
  sceneId?: string | null;
  author: string;
  assignee?: string | null;
  body: string;
  status?: "open" | "resolved";
}): Promise<{ project: ProjectRecord; comment: ProjectComment; audit_event: AuditEvent; notifications: ProjectNotification[] }> {
  return request(`/api/projects/${params.projectId}/comments`, {
    method: "POST",
    body: JSON.stringify({
      scene_id: params.sceneId ?? null,
      author: params.author,
      assignee: params.assignee ?? null,
      body: params.body,
      status: params.status ?? "open",
    }),
  });
}

export async function updateProjectComment(params: {
  projectId: string;
  commentId: string;
  author: string;
  status: "open" | "resolved";
}): Promise<{ project: ProjectRecord; comment: ProjectComment; audit_event: AuditEvent }> {
  return request(`/api/projects/${params.projectId}/comments/${params.commentId}`, {
    method: "PATCH",
    body: JSON.stringify({
      author: params.author,
      status: params.status,
    }),
  });
}

export async function createProjectCommentReply(params: {
  projectId: string;
  commentId: string;
  author: string;
  body: string;
}): Promise<{
  project: ProjectRecord;
  comment: ProjectComment;
  reply: CommentReply;
  audit_event: AuditEvent;
  notifications: ProjectNotification[];
}> {
  return request(`/api/projects/${params.projectId}/comments/${params.commentId}/replies`, {
    method: "POST",
    body: JSON.stringify({
      author: params.author,
      body: params.body,
    }),
  });
}

export async function listProjectAuditEvents(params: {
  projectId: string;
  eventType?: string;
  actor?: string;
  limit?: number;
}): Promise<{ audit_events: AuditEvent[] }> {
  const query = new URLSearchParams();
  if (params.eventType) query.set("event_type", params.eventType);
  if (params.actor) query.set("actor", params.actor);
  if (params.limit) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request(`/api/projects/${params.projectId}/audit-events${suffix}`);
}

export async function listProjectNotifications(params: {
  projectId: string;
  recipient?: string;
  unreadOnly?: boolean;
  limit?: number;
}): Promise<{ notifications: ProjectNotification[] }> {
  const query = new URLSearchParams();
  if (params.recipient) query.set("recipient", params.recipient);
  if (params.unreadOnly) query.set("unread_only", "true");
  if (params.limit) query.set("limit", String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request(`/api/projects/${params.projectId}/notifications${suffix}`);
}

export async function updateProjectNotification(params: {
  projectId: string;
  notificationId: string;
  actor: string;
  unread: boolean;
}): Promise<{ project: ProjectRecord; notification: ProjectNotification; audit_event: AuditEvent }> {
  return request(`/api/projects/${params.projectId}/notifications/${params.notificationId}`, {
    method: "PATCH",
    body: JSON.stringify({
      actor: params.actor,
      unread: params.unread,
    }),
  });
}

export async function startGenerationJob(params: { projectId: string; useLlm: boolean; modelProfile?: ModelProfileRuntime }): Promise<JobRecord> {
  return request("/api/jobs/generate", {
    method: "POST",
    body: JSON.stringify({ project_id: params.projectId, use_llm: params.useLlm, model_profile: params.modelProfile }),
  });
}

export async function startRewriteJob(params: {
  projectId: string;
  actor: string;
  sceneIds?: string[];
  instruction: string;
  mode: RewriteMode;
  useLlm: boolean;
  maxScenes?: number;
  modelProfile?: ModelProfileRuntime;
}): Promise<JobRecord> {
  return request("/api/jobs/rewrite", {
    method: "POST",
    body: JSON.stringify({
      project_id: params.projectId,
      actor: params.actor,
      scene_ids: params.sceneIds ?? [],
      instruction: params.instruction,
      mode: params.mode,
      use_llm: params.useLlm,
      max_scenes: params.maxScenes ?? 5,
      model_profile: params.modelProfile,
    }),
  });
}

export async function getJob(jobId: string): Promise<JobRecord> {
  return request(`/api/jobs/${jobId}`);
}

export async function getJobQueueStatus(): Promise<JobQueueStatus> {
  return request("/api/job-queue/status");
}

export async function getDeadLetterQueue(limit = 20): Promise<DeadLetterQueueResponse> {
  return request(`/api/job-queue/dead-letter?limit=${encodeURIComponent(String(limit))}`);
}

export async function updateJob(params: {
  jobId: string;
  actor: string;
  action: "cancel" | "retry";
}): Promise<JobRecord> {
  return request(`/api/jobs/${params.jobId}`, {
    method: "POST",
    body: JSON.stringify({
      actor: params.actor,
      action: params.action,
    }),
  });
}

export async function runWorkerOnce(): Promise<{ job: JobRecord | null; queue: JobQueueStatus }> {
  return request("/api/workers/run-once", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function searchProjectEvidence(params: {
  projectId: string;
  query: string;
  limit?: number;
}): Promise<{ evidence: SourceEvidence[] }> {
  return request(`/api/projects/${params.projectId}/evidence/search`, {
    method: "POST",
    body: JSON.stringify({ query: params.query, limit: params.limit ?? 8 }),
  });
}

export function subscribeJobEvents(jobId: string, handlers: {
  onJob: (job: JobRecord) => void;
  onError?: (error: Event) => void;
}) {
  const source = new EventSource(`${API_BASE}/api/jobs/${jobId}/events`);
  source.addEventListener("job", (event) => {
    const message = event as MessageEvent<string>;
    handlers.onJob(JSON.parse(message.data) as JobRecord);
  });
  source.onerror = (event) => {
    handlers.onError?.(event);
  };
  return () => source.close();
}

export async function detectChapters(text: string): Promise<{ chapters: Chapter[]; count: number }> {
  return request("/api/detect-chapters", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export async function generateScreenplay(params: {
  text: string;
  title: string;
  useLlm: boolean;
  style?: {
    genre: string;
    tone: string;
    dialogue_style: string;
    target_audience: string;
    episode_count: number;
    target_runtime_minutes: number;
    scene_density: "compact" | "balanced" | "expanded";
  };
  modelProfile?: ModelProfileRuntime;
}): Promise<GenerateResponse> {
  return request("/api/generate", {
    method: "POST",
    body: JSON.stringify({
      text: params.text,
      title: params.title,
      use_llm: params.useLlm,
      ...(params.style ? { style: params.style } : {}),
      model_profile: params.modelProfile,
    }),
  });
}

export async function rewriteScene(params: {
  screenplay: Screenplay;
  sceneId: string;
  instruction: string;
  mode: "strengthen_conflict" | "rewrite_dialogue" | "short_drama" | "tighten_evidence";
  useLlm: boolean;
  modelProfile?: ModelProfileRuntime;
}): Promise<RewriteSceneResponse> {
  return request("/api/rewrite-scene", {
    method: "POST",
    body: JSON.stringify({
      screenplay: params.screenplay,
      scene_id: params.sceneId,
      instruction: params.instruction,
      mode: params.mode,
      use_llm: params.useLlm,
      model_profile: params.modelProfile,
    }),
  });
}

export async function validateYaml(yamlText: string): Promise<ValidationResult> {
  return request("/api/validate", {
    method: "POST",
    body: JSON.stringify({ yaml_text: yamlText }),
  });
}

export async function exportScreenplay(format: string, screenplay: Screenplay): Promise<string> {
  const response = await fetch(`${API_BASE}/api/export/${format}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ screenplay }),
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.text();
}
