"use client";

import {
  AlertCircle,
  BookOpen,
  Braces,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Clock,
  Download,
  FileCode2,
  FileText,
  Film,
  Gauge,
  GitBranch,
  History,
  Layers3,
  Library,
  ListChecks,
  Loader2,
  LockKeyhole,
  MapPin,
  MessageSquare,
  MessagesSquare,
  PanelRight,
  Play,
  RefreshCcw,
  Save,
  Server,
  Settings2,
  Shield,
  ShieldCheck,
  Sparkles,
  SquarePen,
  Wand2,
} from "lucide-react";
import type { ReactNode, RefObject, SetStateAction } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/Badge";
import { YamlEditor } from "@/components/YamlEditor";
import {
  completeImportSession,
  createProjectComment,
  createProjectCommentReply,
  createProjectApproval,
  createProjectDeliveryPackage,
  createProject,
  createProjectExport,
  createImportSession,
  createProjectSession,
  detectChapters,
  exportScreenplay,
  generateScreenplay,
  getDeadLetterQueue,
  getJobQueueStatus,
  getModelProfiles,
  getSystemReadiness,
  setActiveSessionToken,
  resolveApiUrl,
  getCapabilities,
  getJob,
  getProject,
  getProjectReadiness,
  getSample,
  compareProjectVersions,
  decideProjectApproval,
  listProjectImportHistory,
  listProjectAuditEvents,
  listProjectApprovals,
  listProjectDeliveryPackages,
  listProjectExports,
  listProjectNotifications,
  listProjectVersions,
  listProjects,
  restoreProjectVersion,
  rewriteScene,
  runWorkerOnce,
  searchProjectEvidence,
  startGenerationJob,
  startImportSourceJob,
  startRewriteJob,
  subscribeJobEvents,
  testModelProfile,
  uploadImportSessionChunk,
  updateProjectComment,
  updateProjectNotification,
  updateProject,
  updateJob,
  validateYaml,
} from "@/lib/api";
import type {
  AuditEvent,
  CapabilitiesResponse,
  Chapter,
  DeadLetterQueueResponse,
  GenerateResponse,
  ImportHistoryResponse,
  ImportSessionStatus,
  ImportSecurityReport,
  ImportSourceResponse,
  JobQueueStatus,
  JobRecord,
  ModelProfileRuntime,
  ModelProfileTestResponse,
  ExportFormat,
  ApprovalDecision,
  PipelineStageReport,
  ProjectApprovalHistoryResponse,
  ProjectApprovalRecord,
  ProjectApprovalResponse,
  ProjectDeliveryPackageAsset,
  ProjectDeliveryPackageHistoryResponse,
  ProjectDeliveryPackageRecord,
  ProjectDeliveryPackageResponse,
  ProjectExportHistoryResponse,
  ProjectExportRecord,
  ProjectExportResponse,
  ProjectComment,
  ProjectMember,
  ProjectNotification,
  ProjectRecord,
  ProjectReadinessCheck,
  ProjectReadinessResponse,
  ProjectSession,
  ProjectSettings,
  ProjectSummary,
  ProjectVersionSummary,
  QualityMetric,
  RewriteMode,
  Scene,
  Screenplay,
  SourceEvidence,
  SystemReadinessCheck,
  SystemReadinessResponse,
  ValidationResult,
  VersionCompareResponse,
} from "@/lib/types";

type WorkspaceView = "script" | "structure" | "quality" | "production" | "yaml";
type InspectorView = "scene" | "evidence" | "review" | "diff" | "project";
type AuditFilter = "all" | "comment.created" | "comment.replied" | "comment.resolved" | "comment.reopened";

const exportFormats: { id: ExportFormat; label: string }[] = [
  { id: "yaml", label: "YAML" },
  { id: "json", label: "JSON" },
  { id: "markdown", label: "Markdown" },
  { id: "fountain", label: "Fountain" },
];

const DEFAULT_STYLE: ProjectSettings["style"] = {
  genre: "悬疑短剧",
  tone: "克制、紧张、强钩子",
  dialogue_style: "自然、短句、有潜台词",
  target_audience: "短剧观众",
  episode_count: 1,
  target_runtime_minutes: 12,
  scene_density: "balanced",
};

const DEFAULT_MODEL_PROFILE: ModelProfileRuntime = {
  provider: "api",
  base_url: "https://api.openai.com/v1",
  model: "gpt-5.5",
  api_key: "",
  api_key_secret_ref: "",
  temperature: 0.4,
};

const CHUNKED_IMPORT_THRESHOLD_BYTES = 512 * 1024;
const IMPORT_CHUNK_SIZE_BYTES = 256 * 1024;
const LOCAL_PROJECT_ACTOR = "项目负责人";

const workspaceViews: { id: WorkspaceView; label: string; icon: ReactNode }[] = [
  { id: "script", label: "剧本", icon: <Film size={15} /> },
  { id: "structure", label: "结构", icon: <GitBranch size={15} /> },
  { id: "quality", label: "质量", icon: <Gauge size={15} /> },
  { id: "production", label: "制片", icon: <ClipboardCheck size={15} /> },
  { id: "yaml", label: "YAML", icon: <Braces size={15} /> },
];

const inspectorViews: { id: InspectorView; label: string; icon: ReactNode }[] = [
  { id: "scene", label: "场景", icon: <PanelRight size={14} /> },
  { id: "evidence", label: "证据", icon: <BookOpen size={14} /> },
  { id: "review", label: "审阅", icon: <MessagesSquare size={14} /> },
  { id: "diff", label: "改写", icon: <SquarePen size={14} /> },
  { id: "project", label: "项目", icon: <Settings2 size={14} /> },
];

const rewriteModes: { id: RewriteMode; label: string }[] = [
  { id: "strengthen_conflict", label: "增强冲突" },
  { id: "rewrite_dialogue", label: "改写对白" },
  { id: "short_drama", label: "短剧钩子" },
  { id: "tighten_evidence", label: "收紧证据" },
];

const auditFilters: { id: AuditFilter; label: string }[] = [
  { id: "all", label: "全部" },
  { id: "comment.created", label: "创建" },
  { id: "comment.replied", label: "回复" },
  { id: "comment.resolved", label: "解决" },
  { id: "comment.reopened", label: "重开" },
];

const approvalStatusLabels: Record<ProjectApprovalRecord["status"], string> = {
  submitted: "待审批",
  approved: "已批准",
  rejected: "已驳回",
  revoked: "已撤回",
  blocked: "被阻塞",
};

export default function HomePage() {
  const [title, setTitle] = useState("雨夜来信");
  const [sourceText, setSourceText] = useState("");
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [yamlText, setYamlText] = useState("");
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<WorkspaceView>("script");
  const [inspectorView, setInspectorView] = useState<InspectorView>("scene");
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [useLlm, setUseLlm] = useState(true);
  const [capabilities, setCapabilities] = useState<CapabilitiesResponse | null>(null);
  const [modelProfile, setModelProfile] = useState<ModelProfileRuntime>(DEFAULT_MODEL_PROFILE);
  const [modelTest, setModelTest] = useState<ModelProfileTestResponse | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [currentProject, setCurrentProject] = useState<ProjectRecord | null>(null);
  const [projectVersions, setProjectVersions] = useState<ProjectVersionSummary[]>([]);
  const [importHistory, setImportHistory] = useState<ImportHistoryResponse | null>(null);
  const [exportHistory, setExportHistory] = useState<ProjectExportHistoryResponse | null>(null);
  const [lastExport, setLastExport] = useState<ProjectExportRecord | null>(null);
  const [approvalHistory, setApprovalHistory] = useState<ProjectApprovalHistoryResponse | null>(null);
  const [lastApproval, setLastApproval] = useState<ProjectApprovalRecord | null>(null);
  const [deliveryPackageHistory, setDeliveryPackageHistory] = useState<ProjectDeliveryPackageHistoryResponse | null>(null);
  const [lastDeliveryPackage, setLastDeliveryPackage] = useState<ProjectDeliveryPackageRecord | null>(null);
  const [projectReadiness, setProjectReadiness] = useState<ProjectReadinessResponse | null>(null);
  const [systemReadiness, setSystemReadiness] = useState<SystemReadinessResponse | null>(null);
  const [activeImportSession, setActiveImportSession] = useState<ImportSessionStatus | null>(null);
  const [compareBaseVersionId, setCompareBaseVersionId] = useState("");
  const [versionCompare, setVersionCompare] = useState<VersionCompareResponse | null>(null);
  const [activeJob, setActiveJob] = useState<JobRecord | null>(null);
  const [queueStatus, setQueueStatus] = useState<JobQueueStatus | null>(null);
  const [deadLetterQueue, setDeadLetterQueue] = useState<DeadLetterQueueResponse | null>(null);
  const [logs, setLogs] = useState<string[]>(["等待项目输入"]);
  const [style, setStyle] = useState(DEFAULT_STYLE);
  const [rewriteInstruction, setRewriteInstruction] = useState("增强人物选择代价，并保留原文证据链。");
  const [rewriteMode, setRewriteMode] = useState<RewriteMode>("strengthen_conflict");
  const [batchRewriteMode, setBatchRewriteMode] = useState<RewriteMode>("tighten_evidence");
  const [batchRewriteInstruction, setBatchRewriteInstruction] = useState("优先处理低证据链或冲突不足的场景，保留原文事实边界。");
  const [batchRewriteMaxScenes, setBatchRewriteMaxScenes] = useState(5);
  const [evidenceQuery, setEvidenceQuery] = useState("");
  const [evidenceSearch, setEvidenceSearch] = useState<SourceEvidence[]>([]);
  const [reviewComment, setReviewComment] = useState("");
  const [reviewAssignee, setReviewAssignee] = useState("编剧");
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({});
  const [auditFilter, setAuditFilter] = useState<AuditFilter>("all");
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [currentActor, setCurrentActor] = useState(LOCAL_PROJECT_ACTOR);
  const [activeSession, setActiveSession] = useState<ProjectSession | null>(null);
  const [notifications, setNotifications] = useState<ProjectNotification[]>([]);
  const [lastRewrite, setLastRewrite] = useState<{
    sceneId: string;
    evidence: SourceEvidence[];
    diffSummary: string[];
    provider: string;
    providerStatus: string;
  } | null>(null);
  const importInputRef = useRef<HTMLInputElement | null>(null);

  const screenplay = result?.screenplay ?? null;
  const selectedScene = useMemo(() => {
    if (!screenplay) return null;
    return screenplay.scenes.find((scene) => scene.id === selectedSceneId) ?? screenplay.scenes[0] ?? null;
  }, [screenplay, selectedSceneId]);

  const selectedEvidence = useMemo(() => {
    if (!screenplay || !selectedScene) return [];
    if (lastRewrite?.sceneId === selectedScene.id && lastRewrite.evidence.length) {
      return lastRewrite.evidence;
    }
    return deriveSceneEvidence(screenplay, selectedScene);
  }, [screenplay, selectedScene, lastRewrite]);

  const health = useMemo(() => summarizeHealth(screenplay, validation), [screenplay, validation]);
  const coverage = useMemo(() => summarizeCoverage(screenplay), [screenplay]);

  useEffect(() => {
    getCapabilities()
      .then(setCapabilities)
      .catch(() => setCapabilities(null));
    getModelProfiles()
      .then((response) => {
        setModelProfile((current) => ({
          ...current,
          provider: response.active.provider,
          base_url: response.active.base_url,
          model: response.active.model,
          temperature: response.active.temperature,
        }));
        if (response.warnings.length) {
          setLogs((items) => [...response.warnings, ...items].slice(0, 8));
        }
      })
      .catch(() => undefined);
    refreshProjects();
    syncQueueStatus().catch(() => setQueueStatus(null));
    syncSystemReadiness().catch(() => setSystemReadiness(null));
    return () => {
      setActiveSessionToken(null);
    };
  }, []);

  useEffect(() => {
    if (!activeJob || !["queued", "running"].includes(activeJob.status)) return;
    let streamClosed = false;
    let streamFailed = false;
    const stopStream = subscribeJobEvents(activeJob.id, {
      onJob: (job) => {
        if (streamClosed) return;
        setActiveJob(job);
        syncQueueStatus().catch(() => undefined);
        if (job.status === "succeeded") {
          streamClosed = true;
          stopStream();
          syncImportHistory(job.project_id).catch(() => undefined);
          if (job.kind === "import") {
            applyImportedSource(job).catch((err) => setError(normalizeError(err)));
          } else {
            openProject(job.project_id).catch((err) => setError(normalizeError(err)));
          }
          setLogs((items) => [`任务完成：${job.id}`, ...items].slice(0, 8));
        }
        if (job.status === "failed" || job.status === "dead_lettered") {
          streamClosed = true;
          stopStream();
          setError(job.error ?? "任务失败");
        }
      },
      onError: () => {
        streamFailed = true;
      },
    });

    const timer = window.setInterval(async () => {
      if (!streamFailed) return;
      try {
        const job = await getJob(activeJob.id);
        setActiveJob(job);
        await syncQueueStatus();
        if (job.status === "succeeded") {
          await syncImportHistory(job.project_id).catch(() => undefined);
          if (job.kind === "import") {
            await applyImportedSource(job);
          } else {
            await openProject(job.project_id);
          }
          setLogs((items) => [`任务完成：${job.id}`, ...items].slice(0, 8));
        }
        if (job.status === "failed" || job.status === "dead_lettered") {
          setError(job.error ?? "任务失败");
        }
      } catch (err) {
        setError(normalizeError(err));
      }
    }, 1000);
    return () => {
      streamClosed = true;
      stopStream();
      window.clearInterval(timer);
    };
  }, [activeJob]);

  useEffect(() => {
    if (!currentProject) {
      setNotifications([]);
      return;
    }
    syncNotifications(currentProject.id, currentActor).catch(() => {
      setNotifications(currentProject.notifications?.filter((item) => item.recipient === currentActor) ?? []);
    });
  }, [currentActor, currentProject?.id]);

  useEffect(() => {
    if (!currentProject?.id) {
      setProjectReadiness(null);
      return;
    }
    syncProjectReadiness(currentProject.id).catch(() => setProjectReadiness(null));
  }, [
    activeJob?.status,
    activeJob?.updated_at,
    currentProject?.current_version_id,
    currentProject?.id,
    currentProject?.updated_at,
    importHistory?.total,
    exportHistory?.total,
    approvalHistory?.total,
  ]);

  async function loadSample() {
    setLoading("sample");
    setError(null);
    try {
      const sample = await getSample();
      setTitle(sample.title);
      setSourceText(sample.text);
      setLogs((items) => ["已加载内置样例", ...items]);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(null);
    }
  }

  async function handleImportSource(file: File) {
    setLoading("import-source");
    setError(null);
    try {
      const job =
        file.size >= CHUNKED_IMPORT_THRESHOLD_BYTES
          ? await startChunkedImportSource(file)
          : await startImportSourceJob({ file, projectId: currentProject?.id, actor: currentActor });
      setActiveJob(job);
      await syncQueueStatus();
      await refreshProjects();
      await syncProjectReadiness(job.project_id).catch(() => undefined);
      if (job.status === "succeeded") {
        await applyImportedSource(job);
      } else {
        setLogs((items) => [`导入任务已启动：${job.id}/${job.queue_mode}`, ...items].slice(0, 8));
      }
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(null);
      if (importInputRef.current) {
        importInputRef.current.value = "";
      }
    }
  }

  async function startChunkedImportSource(file: File) {
    const totalChunks = Math.max(1, Math.ceil(file.size / IMPORT_CHUNK_SIZE_BYTES));
    const session = await createImportSession({
      file,
      totalChunks,
      projectId: currentProject?.id,
      actor: currentActor,
    });
    setActiveImportSession(session);
    setLogs((items) => [`分片导入会话已创建：${session.id} / ${totalChunks} chunks`, ...items].slice(0, 8));
    let currentSession = session;
    for (let index = 0; index < totalChunks; index += 1) {
      const start = index * IMPORT_CHUNK_SIZE_BYTES;
      const chunk = file.slice(start, Math.min(file.size, start + IMPORT_CHUNK_SIZE_BYTES));
      currentSession = await uploadImportSessionChunk({
        sessionId: session.id,
        chunkIndex: index,
        chunk,
      });
      setActiveImportSession(currentSession);
    }
    const completed = await completeImportSession(session.id);
    setActiveImportSession(completed.session);
    setLogs((items) => [`分片导入已完成并进入任务队列：${completed.job.id}`, ...items].slice(0, 8));
    return completed.job;
  }

  async function applyImportedSource(job: JobRecord) {
    if (job.kind !== "import") return;
    const imported = parseImportJobResult(job);
    if (!imported) return;
    setTitle(imported.title);
    setSourceText(imported.text);
    const detected = await detectChapters(imported.text);
    setChapters(detected.chapters);
    setResult(null);
    setYamlText("");
    setValidation(null);
    setSelectedSceneId(null);
    setLastRewrite(null);
    setActiveView("script");
    setInspectorView("project");
    const project = await getProject(job.project_id);
    setCurrentProject(project);
    setAuditEvents(project.audit_events ?? []);
    await syncImportHistory(project.id).catch(() => setImportHistory(null));
    await syncProjectApprovals(project.id).catch(() => setApprovalHistory(null));
    await syncProjectDeliveryPackages(project.id).catch(() => setDeliveryPackageHistory(null));
    await syncProjectReadiness(project.id).catch(() => setProjectReadiness(null));
    setProjectVersions([]);
    setVersionCompare(null);
    setCompareBaseVersionId("");
    await refreshProjects();
    setLogs((items) => [
      `已导入 ${imported.filename}：${imported.extraction_method} / ${imported.chapter_count} 章 / ${imported.paragraph_count} 段 / ${formatBytes(imported.size_bytes)} / 安全扫描 ${imported.security_report.verdict}`,
      ...imported.warnings,
      ...items,
    ].slice(0, 10));
  }

  async function handleDetect() {
    setLoading("detect");
    setError(null);
    try {
      const response = await detectChapters(sourceText);
      setChapters(response.chapters);
      setLogs((items) => [`章节索引完成：${response.count} 章，${countParagraphs(response.chapters)} 段证据`, ...items]);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(null);
    }
  }

  async function handleGenerate() {
    setLoading("generate");
    setError(null);
    try {
      const response = await generateScreenplay({ text: sourceText, title, useLlm, style, modelProfile: activeModelProfile(useLlm, modelProfile) });
      setResult(response);
      setYamlText(response.yaml_text);
      setValidation(response.validation);
      setSelectedSceneId(response.screenplay.scenes[0]?.id ?? null);
      setActiveView("script");
      setInspectorView("scene");
      setLastRewrite(null);
      setLogs((items) => [
        `流水线完成：${response.screenplay.scenes.length} 场，质量 ${response.screenplay.quality_report.overall_score} 分`,
        ...response.warnings,
        ...items,
      ]);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(null);
    }
  }

  async function refreshProjects() {
    try {
      const response = await listProjects();
      setProjects(response.projects);
    } catch {
      setProjects([]);
    }
  }

  async function syncProjectVersions(projectId: string, preferredBaseId?: string) {
    const response = await listProjectVersions(projectId);
    setProjectVersions(response.versions);
    const current = response.versions.find((version) => version.is_current) ?? response.versions[0] ?? null;
    const nextBase =
      preferredBaseId && response.versions.some((version) => version.id === preferredBaseId && version.id !== current?.id)
        ? preferredBaseId
        : response.versions.find((version) => version.id !== current?.id)?.id ?? "";
    setCompareBaseVersionId(nextBase);
    return { versions: response.versions, current, baseVersionId: nextBase };
  }

  async function syncImportHistory(projectId: string) {
    const response = await listProjectImportHistory({ projectId, limit: 20 });
    setImportHistory(response);
    return response;
  }

  async function syncProjectReadiness(projectId: string) {
    const response = await getProjectReadiness(projectId);
    setProjectReadiness(response);
    return response;
  }

  async function syncSystemReadiness() {
    const response = await getSystemReadiness();
    setSystemReadiness(response);
    return response;
  }

  async function syncProjectExports(projectId: string) {
    const response = await listProjectExports({ projectId, limit: 20 });
    setExportHistory(response);
    setLastExport(response.exports[0] ?? null);
    return response;
  }

  async function syncProjectApprovals(projectId: string) {
    const response = await listProjectApprovals({ projectId, limit: 20 });
    setApprovalHistory(response);
    setLastApproval(response.approvals[0] ?? null);
    return response;
  }

  async function syncProjectDeliveryPackages(projectId: string, actorOverride?: string) {
    const actor = actorOverride ?? currentActor;
    let response: ProjectDeliveryPackageHistoryResponse;
    try {
      response = await listProjectDeliveryPackages({ projectId, limit: 20, actor });
    } catch {
      response = await listProjectDeliveryPackages({ projectId, limit: 20, skipAuth: true });
    }
    setDeliveryPackageHistory(response);
    setLastDeliveryPackage(response.packages[0] ?? null);
    return response;
  }

  async function syncQueueStatus() {
    const response = await getJobQueueStatus();
    setQueueStatus(response);
    getDeadLetterQueue(12)
      .then(setDeadLetterQueue)
      .catch(() => setDeadLetterQueue(null));
    return response;
  }

  async function handleTestModelProfile() {
    setLoading("model-test");
    setError(null);
    try {
      const response = await testModelProfile(modelProfile);
      setModelTest(response);
      setLogs((items) => [`模型连接${response.ok ? "通过" : "失败"}：${response.message}`, ...response.warnings, ...items].slice(0, 8));
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(null);
    }
  }

  async function saveCurrentProject() {
    setLoading("save-project");
    setError(null);
    try {
      const settings: ProjectSettings = {
        style,
        model_provider: useLlm ? modelProfile.provider : "fallback",
        model_profile: publicModelProfile(useLlm, modelProfile),
        require_schema_valid: true,
        require_source_refs: true,
        quality_gate_score: 80,
      };
      const project = currentProject
        ? await updateProject({ projectId: currentProject.id, title, sourceText, settings })
        : await createProject({ title, sourceText, settings });
      setCurrentProject(project);
      await switchProjectSession(project, LOCAL_PROJECT_ACTOR);
      await syncProjectReadiness(project.id).catch(() => setProjectReadiness(null));
      await syncProjectExports(project.id).catch(() => setExportHistory(null));
      await syncProjectApprovals(project.id).catch(() => setApprovalHistory(null));
      await syncProjectDeliveryPackages(project.id).catch(() => setDeliveryPackageHistory(null));
      await refreshProjects();
      setLogs((items) => [`项目已保存：${project.title}`, ...items]);
      return project;
    } catch (err) {
      setError(normalizeError(err));
      return null;
    } finally {
      setLoading(null);
    }
  }

  async function openProject(projectId: string) {
    setActiveSession(null);
    setActiveSessionToken(null);
    setImportHistory(null);
    setExportHistory(null);
    setLastExport(null);
    setApprovalHistory(null);
    setLastApproval(null);
    setDeliveryPackageHistory(null);
    setLastDeliveryPackage(null);
    setProjectReadiness(null);
    const project = await getProject(projectId);
    setCurrentProject(project);
    setAuditEvents(project.audit_events ?? []);
    setAuditFilter("all");
    setVersionCompare(null);
    setReplyDrafts({});
    setTitle(project.title);
    setSourceText(project.source_text);
    setStyle(project.settings.style);
    setUseLlm(project.settings.model_provider !== "fallback");
    if (project.settings.model_profile) {
      setModelProfile((current) => ({
        ...current,
        provider: project.settings.model_profile?.provider ?? current.provider,
        base_url: project.settings.model_profile?.base_url ?? current.base_url,
        model: project.settings.model_profile?.model ?? current.model,
        temperature: project.settings.model_profile?.temperature ?? current.temperature,
        api_key_secret_ref: project.settings.model_profile?.api_key_secret_ref ?? current.api_key_secret_ref,
      }));
    }
    const nextActor = resolveProjectActor(project, LOCAL_PROJECT_ACTOR);
    await switchProjectSession(project, nextActor);
    const currentVersion =
      project.versions.find((version) => version.id === project.current_version_id) ??
      project.versions[project.versions.length - 1] ??
      null;
    if (currentVersion) {
      setResult({
        screenplay: currentVersion.screenplay,
        yaml_text: currentVersion.yaml_text,
        validation: currentVersion.validation,
        provider: currentVersion.screenplay.metadata.provider,
        provider_status: currentVersion.screenplay.metadata.provider_status,
        warnings: currentVersion.screenplay.metadata.warnings,
      });
      setYamlText(currentVersion.yaml_text);
      setValidation(currentVersion.validation);
      setSelectedSceneId(currentVersion.screenplay.scenes[0]?.id ?? null);
      setLastRewrite(null);
    } else {
      setResult(null);
      setYamlText("");
      setValidation(null);
      setSelectedSceneId(null);
    }
    await syncProjectVersions(project.id).catch(() => setProjectVersions([]));
    await syncImportHistory(project.id).catch(() => setImportHistory(null));
    await syncProjectExports(project.id).catch(() => setExportHistory(null));
    await syncProjectApprovals(project.id).catch(() => setApprovalHistory(null));
    await syncProjectDeliveryPackages(project.id).catch(() => setDeliveryPackageHistory(null));
    await syncProjectReadiness(project.id).catch(() => setProjectReadiness(null));
    setLogs((items) => [`已打开项目：${project.title}`, ...items]);
    await refreshProjects();
  }

  async function switchProjectSession(project: ProjectRecord, memberName: string) {
    const nextActor = resolveProjectActor(project, memberName);
    const response = await createProjectSession({ projectId: project.id, memberName: nextActor });
    setActiveSessionToken(response.token);
    setActiveSession(response.session);
    setCurrentActor(response.member.name);
    setCurrentProject(response.project);
    setNotifications(response.project.notifications?.filter((item) => item.recipient === response.member.name) ?? []);
    return response;
  }

  async function handleProjectJob() {
    const project = await saveCurrentProject();
    if (!project) return;
    setLoading("start-job");
    setError(null);
    try {
      const job = await startGenerationJob({ projectId: project.id, useLlm, modelProfile: activeModelProfile(useLlm, modelProfile) });
      setActiveJob(job);
      await refreshProjects();
      await syncQueueStatus();
      if (job.status === "succeeded") {
        await openProject(project.id);
        setLogs((items) => [`任务完成：${job.id}`, ...items].slice(0, 8));
      } else {
        await syncProjectReadiness(project.id).catch(() => undefined);
        setLogs((items) => [`任务已启动：${job.id}`, ...items]);
      }
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(null);
    }
  }

  async function handleValidate() {
    setLoading("validate");
    setError(null);
    try {
      const response = await validateYaml(yamlText);
      setValidation(response);
      setActiveView("quality");
      setLogs((items) => [`YAML 校验${response.valid ? "通过" : "发现问题"}：${response.issues.length} 条`, ...items]);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(null);
    }
  }

  async function handleRewrite() {
    if (!screenplay || !selectedScene) return;
    setLoading("rewrite");
    setError(null);
    try {
      const response = await rewriteScene({
        screenplay,
        sceneId: selectedScene.id,
        instruction: rewriteInstruction,
        mode: rewriteMode,
        useLlm,
        modelProfile: activeModelProfile(useLlm, modelProfile),
      });
      setResult({
        screenplay: response.screenplay,
        yaml_text: response.yaml_text,
        validation: response.validation,
        provider: response.provider,
        provider_status: response.provider_status,
        warnings: response.warnings,
      });
      setYamlText(response.yaml_text);
      setValidation(response.validation);
      setSelectedSceneId(response.changed_scene.id);
      setLastRewrite({
        sceneId: response.changed_scene.id,
        evidence: response.evidence,
        diffSummary: response.diff_summary,
        provider: response.provider,
        providerStatus: response.provider_status,
      });
      setActiveView("script");
      setInspectorView("diff");
      setLogs((items) => [`局部改写完成：${response.diff_summary.join(" ")}`, ...response.warnings, ...items]);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(null);
    }
  }

  async function handleBatchRewrite() {
    setLoading("batch-rewrite");
    setError(null);
    try {
      const project = currentProject ?? (await saveCurrentProject());
      if (!project) return;
      if (!project.versions.length) {
        setError("当前项目还没有可改写的剧本版本，请先运行生成任务。");
        return;
      }
      const job = await startRewriteJob({
        projectId: project.id,
        actor: LOCAL_PROJECT_ACTOR,
        instruction: batchRewriteInstruction,
        mode: batchRewriteMode,
        useLlm,
        maxScenes: batchRewriteMaxScenes,
        modelProfile: activeModelProfile(useLlm, modelProfile),
      });
      setActiveJob(job);
      setInspectorView("scene");
      await refreshProjects();
      await syncQueueStatus();
      await syncProjectReadiness(project.id).catch(() => undefined);
      setLogs((items) => [`批量改写任务已启动：${job.id}`, ...items].slice(0, 8));
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(null);
    }
  }

  async function handleCompareVersions(baseVersionId?: string) {
    if (!currentProject?.current_version_id) return;
    const targetVersionId = currentProject.current_version_id;
    const nextBaseId = baseVersionId ?? compareBaseVersionId;
    if (!nextBaseId || nextBaseId === targetVersionId) {
      setVersionCompare(null);
      return;
    }
    setLoading("version-compare");
    setError(null);
    try {
      const response = await compareProjectVersions({
        projectId: currentProject.id,
        baseVersionId: nextBaseId,
        targetVersionId,
      });
      setVersionCompare(response);
      setCompareBaseVersionId(nextBaseId);
      setLogs((items) => [`版本比较完成：${response.base_label} -> ${response.target_label}`, ...items].slice(0, 8));
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(null);
    }
  }

  async function handleRestoreVersion(versionId: string) {
    if (!currentProject || !versionId || versionId === currentProject.current_version_id) return;
    setLoading(`version-restore-${versionId}`);
    setError(null);
    try {
      const project = await restoreProjectVersion({ projectId: currentProject.id, versionId, actor: currentActor });
      setCurrentProject(project);
      setAuditEvents(project.audit_events ?? []);
      await openProject(project.id);
      setInspectorView("project");
      setLogs((items) => [`已恢复版本：${versionId}`, ...items].slice(0, 8));
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(null);
    }
  }

  async function handleExport(format: ExportFormat) {
    if (!screenplay) return;
    setLoading(`export-${format}`);
    setError(null);
    try {
      if (currentProject) {
        const response = await createProjectExport({
          projectId: currentProject.id,
          format,
          actor: currentActor,
          enforceReadiness: true,
        });
        applyProjectExportResponse(response);
        downloadText(response.export.filename, response.content);
        await syncProjectExports(currentProject.id).catch(() => undefined);
        const project = await getProject(currentProject.id);
        setCurrentProject(project);
        setAuditEvents(project.audit_events ?? []);
        await syncProjectReadiness(currentProject.id).catch(() => undefined);
        setInspectorView("project");
        setLogs((items) => [`交付导出完成：${response.export.filename} / ${response.export.readiness_score}%`, ...items].slice(0, 8));
      } else {
        const content = await exportScreenplay(format, screenplay);
        const extension = format === "markdown" ? "md" : format === "fountain" ? "fountain" : format;
        downloadText(`${title || "screenplay"}.${extension}`, content);
        setLogs((items) => [`已导出临时 ${format}，保存项目后可进入交付治理`, ...items].slice(0, 8));
      }
    } catch (err) {
      const blocked = extractBlockedExport(err);
      if (blocked) {
        setLastExport(blocked.export);
        setProjectReadiness(blocked.readiness);
        setAuditEvents((items) => [blocked.audit_event, ...items.filter((item) => item.id !== blocked.audit_event.id)]);
        if (currentProject) {
          await syncProjectExports(currentProject.id).catch(() => undefined);
        }
        setInspectorView("project");
        setError(`${blocked.export.format} 导出被交付门禁阻止：${blocked.export.blockers[0] ?? "存在阻塞项"}`);
      } else {
        setError(normalizeError(err));
      }
    } finally {
      setLoading(null);
    }
  }

  async function handleSubmitApproval(format: ExportFormat | null, note: string) {
    if (!currentProject) return;
    setLoading("approval-submit");
    setError(null);
    try {
      const response = await createProjectApproval({
        projectId: currentProject.id,
        actor: currentActor,
        versionId: currentProject.current_version_id ?? null,
        note,
        requestedExportFormat: format,
        enforceReadiness: true,
      });
      await applyProjectApprovalResponse(response);
      setInspectorView("project");
      setLogs((items) => [`交付审批已提交：${response.approval.version_label || response.approval.id}`, ...items].slice(0, 8));
    } catch (err) {
      const blocked = extractBlockedApproval(err);
      if (blocked) {
        setLastApproval(blocked.approval);
        setProjectReadiness(blocked.readiness);
        setAuditEvents((items) => [blocked.audit_event, ...items.filter((item) => item.id !== blocked.audit_event.id)]);
        await syncProjectApprovals(currentProject.id).catch(() => undefined);
        setInspectorView("project");
        setError(`交付审批被门禁阻止：${blocked.approval.blockers[0] ?? "存在阻塞项"}`);
      } else {
        setError(normalizeError(err));
      }
    } finally {
      setLoading(null);
    }
  }

  async function handleDecideApproval(approvalId: string, decision: ApprovalDecision, note: string) {
    if (!currentProject) return;
    setLoading(`approval-${decision}`);
    setError(null);
    try {
      const response = await decideProjectApproval({
        projectId: currentProject.id,
        approvalId,
        actor: currentActor,
        decision,
        note,
      });
      await applyProjectApprovalResponse(response);
      setInspectorView("project");
      setLogs((items) => [`交付审批已${approvalDecisionLabel(decision)}：${response.approval.id}`, ...items].slice(0, 8));
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(null);
    }
  }

  async function handleCreateDeliveryPackage(formats: ExportFormat[], approvalId: string | null, note: string) {
    if (!currentProject) return;
    setLoading("delivery-package");
    setError(null);
    try {
      const response = await createProjectDeliveryPackage({
        projectId: currentProject.id,
        actor: currentActor,
        approvalId,
        versionId: currentProject.current_version_id ?? null,
        formats,
        enforceReadiness: true,
        requireApproval: true,
        note,
      });
      applyProjectDeliveryPackageResponse(response);
      downloadDeliveryPackageAssets(response.package, response.assets);
      await syncProjectDeliveryPackages(response.project.id, currentActor).catch(() => undefined);
      await syncProjectReadiness(response.project.id).catch(() => undefined);
      setInspectorView("project");
      setLogs((items) => [`交付包已生成：${response.package.id} / ${response.package.manifest_sha256.slice(0, 12)}`, ...items].slice(0, 8));
    } catch (err) {
      const blocked = extractBlockedDeliveryPackage(err);
      if (blocked) {
        setLastDeliveryPackage(blocked.package);
        setProjectReadiness(blocked.readiness);
        setAuditEvents((items) => [blocked.audit_event, ...items.filter((item) => item.id !== blocked.audit_event.id)]);
        await syncProjectDeliveryPackages(currentProject.id, currentActor).catch(() => undefined);
        setInspectorView("project");
        setError(`交付包被阻止：${blocked.package.blockers[0] ?? "缺少审批或存在门禁阻塞项"}`);
      } else {
        setError(normalizeError(err));
      }
    } finally {
      setLoading(null);
    }
  }

  async function handleEvidenceSearch() {
    if (!currentProject || !evidenceQuery.trim()) return;
    setLoading("evidence-search");
    setError(null);
    try {
      const response = await searchProjectEvidence({ projectId: currentProject.id, query: evidenceQuery, limit: 10 });
      setEvidenceSearch(response.evidence);
      setInspectorView("evidence");
      setLogs((items) => [`证据库检索：${response.evidence.length} 条命中`, ...items]);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setLoading(null);
    }
  }

  function applyProjectExportResponse(response: ProjectExportResponse) {
    setLastExport(response.export);
    setProjectReadiness(response.readiness);
    setAuditEvents((items) => [response.audit_event, ...items.filter((item) => item.id !== response.audit_event.id)]);
  }

  async function applyProjectApprovalResponse(response: ProjectApprovalResponse) {
    setLastApproval(response.approval);
    setProjectReadiness(response.readiness);
    setCurrentProject(response.project);
    setAuditEvents(response.project.audit_events ?? []);
    await syncProjectApprovals(response.project.id).catch(() => undefined);
    await syncProjectDeliveryPackages(response.project.id, currentActor).catch(() => undefined);
    await syncNotifications(response.project.id, currentActor).catch(() => undefined);
  }

  function applyProjectDeliveryPackageResponse(response: ProjectDeliveryPackageResponse) {
    setLastDeliveryPackage(response.package);
    setProjectReadiness(response.readiness);
    setCurrentProject(response.project);
    setAuditEvents(response.project.audit_events ?? []);
  }

  async function handleCreateComment() {
    if (!currentProject || !reviewComment.trim()) return;
    setLoading("comment");
    setError(null);
    try {
      const response = await createProjectComment({
        projectId: currentProject.id,
        sceneId: selectedScene?.id ?? null,
        author: currentActor,
        assignee: reviewAssignee,
        body: reviewComment,
        status: "open",
      });
      setCurrentProject(response.project);
      setAuditEvents(response.project.audit_events ?? []);
      await syncNotifications(response.project.id, currentActor);
      await syncProjectReadiness(response.project.id).catch(() => undefined);
      setAuditFilter("all");
      setReviewComment("");
      setLogs((items) => [`新增审阅意见：${response.comment.id}`, ...items].slice(0, 6));
      setInspectorView("review");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "提交审阅意见失败");
    } finally {
      setLoading(null);
    }
  }

  async function handleUpdateComment(commentId: string, status: ProjectComment["status"]) {
    if (!currentProject) return;
    setLoading(`comment-${commentId}`);
    setError(null);
    try {
      const response = await updateProjectComment({
        projectId: currentProject.id,
        commentId,
        author: currentActor,
        status,
      });
      setCurrentProject(response.project);
      await syncAuditEvents(response.project.id, auditFilter);
      await syncNotifications(response.project.id, currentActor);
      setLogs((items) => [`审阅意见已${status === "resolved" ? "解决" : "重开"}：${response.comment.id}`, ...items].slice(0, 6));
      setInspectorView("review");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "更新审阅意见失败");
    } finally {
      setLoading(null);
    }
  }

  async function handleCreateReply(commentId: string) {
    if (!currentProject) return;
    const body = replyDrafts[commentId]?.trim();
    if (!body) return;
    setLoading(`reply-${commentId}`);
    setError(null);
    try {
      const response = await createProjectCommentReply({
        projectId: currentProject.id,
        commentId,
        author: currentActor,
        body,
      });
      setCurrentProject(response.project);
      setReplyDrafts((drafts) => ({ ...drafts, [commentId]: "" }));
      await syncAuditEvents(response.project.id, auditFilter);
      await syncNotifications(response.project.id, currentActor);
      setLogs((items) => [`新增回复：${response.reply.id}`, ...items].slice(0, 6));
      setInspectorView("review");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "提交回复失败");
    } finally {
      setLoading(null);
    }
  }

  async function syncAuditEvents(projectId: string, nextFilter: AuditFilter) {
    const response = await listProjectAuditEvents({
      projectId,
      eventType: nextFilter === "all" ? undefined : nextFilter,
      limit: 30,
    });
    setAuditEvents(response.audit_events);
  }

  async function syncNotifications(projectId: string, recipient: string) {
    const response = await listProjectNotifications({ projectId, recipient, limit: 20 });
    setNotifications(response.notifications);
  }

  async function handleAuditFilter(nextFilter: AuditFilter) {
    setAuditFilter(nextFilter);
    if (!currentProject) return;
    setLoading("audit-filter");
    setError(null);
    try {
      await syncAuditEvents(currentProject.id, nextFilter);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载审计事件失败");
    } finally {
      setLoading(null);
    }
  }

  async function handleMarkNotificationRead(notificationId: string) {
    if (!currentProject) return;
    setLoading(`note-${notificationId}`);
    setError(null);
    try {
      const response = await updateProjectNotification({
        projectId: currentProject.id,
        notificationId,
        actor: currentActor,
        unread: false,
      });
      setCurrentProject(response.project);
      await syncNotifications(response.project.id, currentActor);
      await syncAuditEvents(response.project.id, auditFilter);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "更新通知失败");
    } finally {
      setLoading(null);
    }
  }

  async function handleJobAction(action: "cancel" | "retry", jobId?: string) {
    const targetJobId = jobId ?? activeJob?.id;
    if (!targetJobId) return;
    setLoading(`job-${action}`);
    setError(null);
    try {
      const job = await updateJob({ jobId: targetJobId, actor: currentActor, action });
      setActiveJob(job);
      await syncQueueStatus();
      setLogs((items) => [`任务${action === "cancel" ? "已取消" : "已重试"}：${job.id}`, ...items].slice(0, 8));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "更新任务失败");
    } finally {
      setLoading(null);
    }
  }

  async function handleRunWorkerOnce() {
    setLoading("worker-once");
    setError(null);
    try {
      const response = await runWorkerOnce();
      setQueueStatus(response.queue);
      const workerJob = response.job;
      if (workerJob) {
        setActiveJob(workerJob);
        if (workerJob.status === "succeeded") {
          if (workerJob.kind === "import") {
            await applyImportedSource(workerJob);
          } else {
            await openProject(workerJob.project_id);
          }
        }
        setLogs((items) => [`Worker 执行：${workerJob.id}/${workerJob.status}`, ...items].slice(0, 8));
      } else {
        setLogs((items) => ["Worker 未发现待执行 external 任务", ...items].slice(0, 8));
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Worker 执行失败");
    } finally {
      setLoading(null);
    }
  }

  return (
    <main className="studio-shell">
      <header className="studio-topbar">
        <div className="brand-lockup">
          <div className="brand-mark">
            <FileCode2 size={18} />
          </div>
          <div>
            <h1>ScriptBridge Studio</h1>
            <p>Arc-style screenplay desk</p>
          </div>
        </div>
        <div className="topbar-center">
          <span className="project-kicker">当前项目</span>
          <strong>{title || "未命名项目"}</strong>
          <span>{screenplay ? `${screenplay.scenes.length} 场剧本` : `${sourceText.length.toLocaleString()} 字原文`}</span>
          <Badge tone={health.tone}>{health.label}</Badge>
          <Badge tone={coverage.tone}>{coverage.label}</Badge>
          <Badge tone={screenplay?.metadata.provider_status === "ok" ? "success" : "warning"}>
            <Server size={12} className="mr-1" />
            {screenplay ? `${screenplay.metadata.provider}/${screenplay.metadata.provider_status}` : "provider 待运行"}
          </Badge>
          <Badge tone="success">
            <Shield size={12} className="mr-1" />
            {currentProject ? "本地全权限" : "本地单用户"}
          </Badge>
        </div>
        <div className="topbar-actions">
          <button className="icon-button" onClick={saveCurrentProject} disabled={!title || !!loading} title="保存项目">
            {loading === "save-project" ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
          </button>
          <button className="btn-secondary" onClick={() => handleExport("fountain")} disabled={!screenplay || !!loading}>
            <Download size={15} />
            Fountain
          </button>
          <button className="btn-primary" onClick={handleProjectJob} disabled={!sourceText || !!loading}>
            {loading === "start-job" ? <Loader2 className="animate-spin" size={15} /> : <Sparkles size={15} />}
            启动任务
          </button>
        </div>
      </header>

      {error && (
        <div className="error-strip">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <StudioCommandBand
        sourceTextLength={sourceText.length}
        chapters={chapters}
        screenplay={screenplay}
        validation={validation}
        activeJob={activeJob}
        queueStatus={queueStatus}
        projectReadiness={projectReadiness}
        systemReadiness={systemReadiness}
        approvalHistory={approvalHistory}
        deliveryPackageHistory={deliveryPackageHistory}
        onRun={handleProjectJob}
        onValidate={handleValidate}
        onOpenProjectInspector={() => setInspectorView("project")}
        loading={loading}
      />

      <section className="studio-grid">
        <ProjectRail
          title={title}
          setTitle={setTitle}
          sourceText={sourceText}
          setSourceText={setSourceText}
          chapters={chapters}
          projects={projects}
          currentProject={currentProject}
          style={style}
          setStyle={setStyle}
          useLlm={useLlm}
          setUseLlm={setUseLlm}
          modelProfile={modelProfile}
          setModelProfile={setModelProfile}
          modelTest={modelTest}
          loading={loading}
          activeImportSession={activeImportSession}
          onTestModel={handleTestModelProfile}
          importInputRef={importInputRef}
          onImportSource={handleImportSource}
          onSample={loadSample}
          onDetect={handleDetect}
          onSave={saveCurrentProject}
          onOpenProject={(projectId) => openProject(projectId).catch((err) => setError(normalizeError(err)))}
        />

        <section className="studio-main">
          <div className="studio-toolbar">
            <nav className="workspace-tabs" aria-label="工作区">
              {workspaceViews.map((view) => (
                <button
                  key={view.id}
                  className={activeView === view.id ? "active" : ""}
                  onClick={() => setActiveView(view.id)}
                  type="button"
                >
                  {view.icon}
                  {view.label}
                </button>
              ))}
            </nav>
            <div className="workspace-statebar" aria-label="交付状态">
              <StatusChip label="Schema" value={validation ? (validation.valid ? "valid" : `${validation.issues.length} issues`) : "unchecked"} tone={validation?.valid ? "success" : validation ? "error" : "neutral"} />
              <StatusChip label="Evidence" value={screenplay ? `${coverage.percent}%` : "waiting"} tone={coverage.tone} />
              <StatusChip label="Gate" value={projectReadiness ? `${projectReadiness.score}%` : "waiting"} tone={projectReadiness ? readinessTone(projectReadiness.status) : "neutral"} />
              <StatusChip label="System" value={systemReadiness ? `${systemReadiness.score}%` : "unknown"} tone={systemReadiness ? readinessTone(systemReadiness.status) : "neutral"} />
              <StatusChip label="Queue" value={queueStatus ? `${queueStatus.mode}/${queueStatus.queued}` : "unknown"} tone={queueStatus?.failed ? "error" : queueStatus?.queued ? "warning" : "neutral"} />
            </div>
            <div className="toolbar-actions">
              <button className="btn-secondary" onClick={handleGenerate} disabled={!sourceText || !!loading}>
                {loading === "generate" ? <Loader2 className="animate-spin" size={15} /> : <Play size={15} />}
                直接运行
              </button>
              <button className="btn-secondary" onClick={() => handleExport("yaml")} disabled={!screenplay || !!loading}>
                YAML
              </button>
              <button className="btn-secondary" onClick={() => handleExport("markdown")} disabled={!screenplay || !!loading}>
                Markdown
              </button>
            </div>
          </div>

          <div className="studio-workspace">
            {activeView === "script" && (
              <ScriptWorkspace
                screenplay={screenplay}
                selectedScene={selectedScene}
                selectedSceneId={selectedSceneId}
                setSelectedSceneId={setSelectedSceneId}
                rewriteInstruction={rewriteInstruction}
                setRewriteInstruction={setRewriteInstruction}
                rewriteMode={rewriteMode}
                setRewriteMode={setRewriteMode}
                onRewrite={handleRewrite}
                loading={loading}
              />
            )}
            {activeView === "structure" && <StructureWorkspace screenplay={screenplay} logs={logs} capabilities={capabilities} />}
            {activeView === "quality" && (
              <QualityWorkspace
                screenplay={screenplay}
                validation={validation}
                onValidate={handleValidate}
                loading={loading}
                batchRewriteMode={batchRewriteMode}
                setBatchRewriteMode={setBatchRewriteMode}
                batchRewriteInstruction={batchRewriteInstruction}
                setBatchRewriteInstruction={setBatchRewriteInstruction}
                batchRewriteMaxScenes={batchRewriteMaxScenes}
                setBatchRewriteMaxScenes={setBatchRewriteMaxScenes}
                onBatchRewrite={handleBatchRewrite}
                canBatchRewrite={!!currentProject?.versions.length}
                currentActor={LOCAL_PROJECT_ACTOR}
                currentActorRole="owner"
                sessionVerified
              />
            )}
            {activeView === "production" && <ProductionWorkspace screenplay={screenplay} />}
            {activeView === "yaml" && (
              <YamlWorkspace yamlText={yamlText} setYamlText={setYamlText} validation={validation} onValidate={handleValidate} loading={loading} />
            )}
          </div>
        </section>

        <InspectorPanel
          activeView={inspectorView}
          setActiveView={setInspectorView}
          selectedScene={selectedScene}
          screenplay={screenplay}
          validation={validation}
        activeJob={activeJob}
        queueStatus={queueStatus}
        deadLetterQueue={deadLetterQueue}
        capabilities={capabilities}
          evidence={selectedEvidence}
          evidenceQuery={evidenceQuery}
          setEvidenceQuery={setEvidenceQuery}
          evidenceSearch={evidenceSearch}
          onEvidenceSearch={handleEvidenceSearch}
          currentProject={currentProject}
          importHistory={importHistory}
          exportHistory={exportHistory}
          lastExport={lastExport}
          approvalHistory={approvalHistory}
          lastApproval={lastApproval}
          deliveryPackageHistory={deliveryPackageHistory}
          lastDeliveryPackage={lastDeliveryPackage}
          projectReadiness={projectReadiness}
          systemReadiness={systemReadiness}
          activeImportSession={activeImportSession}
          reviewComment={reviewComment}
          setReviewComment={setReviewComment}
          reviewAssignee={reviewAssignee}
          setReviewAssignee={setReviewAssignee}
          replyDrafts={replyDrafts}
          setReplyDrafts={setReplyDrafts}
          auditFilter={auditFilter}
          auditEvents={auditEvents}
          currentActor={currentActor}
          activeSession={activeSession}
          sessionVerified
          notifications={notifications}
          onCreateComment={handleCreateComment}
          onUpdateComment={handleUpdateComment}
          onCreateReply={handleCreateReply}
          onAuditFilter={handleAuditFilter}
          onMarkNotificationRead={handleMarkNotificationRead}
          onJobAction={handleJobAction}
          onRunWorkerOnce={handleRunWorkerOnce}
          onExport={handleExport}
          onSubmitApproval={handleSubmitApproval}
          onDecideApproval={handleDecideApproval}
          onCreateDeliveryPackage={handleCreateDeliveryPackage}
          projectVersions={projectVersions}
          compareBaseVersionId={compareBaseVersionId}
          setCompareBaseVersionId={setCompareBaseVersionId}
          versionCompare={versionCompare}
          onCompareVersions={handleCompareVersions}
          onRestoreVersion={handleRestoreVersion}
          loading={loading}
          lastRewrite={lastRewrite}
        />
      </section>
    </main>
  );
}

type UiTone = "success" | "warning" | "error" | "neutral" | "accent";

function StudioCommandBand({
  sourceTextLength,
  chapters,
  screenplay,
  validation,
  activeJob,
  queueStatus,
  projectReadiness,
  systemReadiness,
  approvalHistory,
  deliveryPackageHistory,
  onRun,
  onValidate,
  onOpenProjectInspector,
  loading,
}: {
  sourceTextLength: number;
  chapters: Chapter[];
  screenplay: Screenplay | null;
  validation: ValidationResult | null;
  activeJob: JobRecord | null;
  queueStatus: JobQueueStatus | null;
  projectReadiness: ProjectReadinessResponse | null;
  systemReadiness: SystemReadinessResponse | null;
  approvalHistory: ProjectApprovalHistoryResponse | null;
  deliveryPackageHistory: ProjectDeliveryPackageHistoryResponse | null;
  onRun: () => void;
  onValidate: () => void;
  onOpenProjectInspector: () => void;
  loading: string | null;
}) {
  const generated = Boolean(screenplay);
  const schemaTone: UiTone = validation ? (validation.valid ? "success" : "error") : "neutral";
  const projectGateTone: UiTone = projectReadiness ? readinessTone(projectReadiness.status) : "neutral";
  const systemGateTone: UiTone = systemReadiness ? readinessTone(systemReadiness.status) : "neutral";
  const approvedCount = approvalHistory?.approved ?? 0;
  const pendingCount = approvalHistory?.pending ?? 0;
  const packageSucceeded = deliveryPackageHistory?.succeeded ?? 0;
  const runningJob = activeJob && ["queued", "running"].includes(activeJob.status) ? activeJob : null;
  const steps: {
    id: string;
    icon: ReactNode;
    label: string;
    value: string;
    detail: string;
    tone: UiTone;
  }[] = [
    {
      id: "source",
      icon: <FileText size={15} />,
      label: "源文",
      value: sourceTextLength ? `${sourceTextLength.toLocaleString()} 字` : "待导入",
      detail: `${chapters.length} 章 / ${countParagraphs(chapters)} 段`,
      tone: chapters.length >= 3 ? "success" : sourceTextLength ? "warning" : "neutral",
    },
    {
      id: "screenplay",
      icon: <Film size={15} />,
      label: "剧本",
      value: screenplay ? `${screenplay.scenes.length} 场` : "待生成",
      detail: screenplay ? `${screenplay.story_bible.characters.length} 人物 / ${screenplay.story_bible.locations.length} 地点` : "流水线未产出",
      tone: generated ? "success" : "neutral",
    },
    {
      id: "schema",
      icon: <Braces size={15} />,
      label: "结构",
      value: validation ? (validation.valid ? "valid" : `${validation.issues.length} issues`) : "unchecked",
      detail: generated ? `Schema ${validation?.valid ? "通过" : "待修复"}` : "等待 YAML",
      tone: schemaTone,
    },
    {
      id: "review",
      icon: <MessagesSquare size={15} />,
      label: "审阅",
      value: approvalHistory ? `${approvedCount} 批准 / ${pendingCount} 待审` : "待提交",
      detail: projectReadiness ? `Gate ${projectReadiness.score}%` : "项目门禁未计算",
      tone: approvedCount ? "success" : pendingCount ? "warning" : projectGateTone,
    },
    {
      id: "package",
      icon: <ClipboardCheck size={15} />,
      label: "交付",
      value: deliveryPackageHistory ? `${packageSucceeded}/${deliveryPackageHistory.total} 包` : "待打包",
      detail: systemReadiness ? `System ${systemReadiness.score}%` : "部署门禁未加载",
      tone: packageSucceeded ? "success" : systemGateTone,
    },
  ];

  return (
    <section className="studio-command-band" aria-label="制片工作流">
      <div className="command-band-head">
        <strong>制片工作流</strong>
        <span>{runningJob ? `${runningJob.kind} ${runningJob.progress}%` : queueStatus ? `${queueStatus.mode} queue` : "standby"}</span>
      </div>
      <div className="command-steps">
        {steps.map((step) => (
          <div key={step.id} className={`command-step ${step.tone}`}>
            <div className="command-step-icon">{step.icon}</div>
            <div>
              <span>{step.label}</span>
              <strong>{step.value}</strong>
              <small>{step.detail}</small>
            </div>
          </div>
        ))}
      </div>
      <div className="command-actions">
        <button className="btn-primary compact-action" onClick={onRun} disabled={!sourceTextLength || !!loading} type="button">
          {loading === "start-job" ? <Loader2 className="animate-spin" size={14} /> : <Sparkles size={14} />}
          运行
        </button>
        <button className="btn-secondary compact-action" onClick={onValidate} disabled={!generated || !!loading} type="button">
          {loading === "validate" ? <Loader2 className="animate-spin" size={14} /> : <CheckCircle2 size={14} />}
          校验
        </button>
        <button className="btn-secondary compact-action" onClick={onOpenProjectInspector} type="button">
          <PanelRight size={14} />
          项目
        </button>
      </div>
    </section>
  );
}

function ProjectRail({
  title,
  setTitle,
  sourceText,
  setSourceText,
  chapters,
  projects,
  currentProject,
  style,
  setStyle,
  useLlm,
  setUseLlm,
  modelProfile,
  setModelProfile,
  modelTest,
  loading,
  activeImportSession,
  onTestModel,
  importInputRef,
  onImportSource,
  onSample,
  onDetect,
  onSave,
  onOpenProject,
}: {
  title: string;
  setTitle: (value: string) => void;
  sourceText: string;
  setSourceText: (value: string) => void;
  chapters: Chapter[];
  projects: ProjectSummary[];
  currentProject: ProjectRecord | null;
  style: ProjectSettings["style"];
  setStyle: (style: ProjectSettings["style"]) => void;
  useLlm: boolean;
  setUseLlm: (value: boolean) => void;
  modelProfile: ModelProfileRuntime;
  setModelProfile: (value: SetStateAction<ModelProfileRuntime>) => void;
  modelTest: ModelProfileTestResponse | null;
  loading: string | null;
  activeImportSession: ImportSessionStatus | null;
  onTestModel: () => void;
  importInputRef: RefObject<HTMLInputElement | null>;
  onImportSource: (file: File) => void;
  onSample: () => void;
  onDetect: () => void;
  onSave: () => void;
  onOpenProject: (projectId: string) => void;
}) {
  const importedEnough = chapters.length >= 3;
  const sourceParagraphs = sourceText
    .split(/\n{2,}/)
    .map((item) => item.trim())
    .filter(Boolean).length;

  return (
    <aside className="project-rail">
      <section className="rail-section project-section">
        <div className="section-heading">
          <span>项目设定</span>
          <Badge tone={importedEnough ? "success" : chapters.length > 0 ? "warning" : "neutral"}>{chapters.length} 章</Badge>
        </div>
        <label className="field-label" htmlFor="title">
          标题
        </label>
        <input id="title" className="input-control" value={title} onChange={(event) => setTitle(event.target.value)} />

        <div className="import-readiness">
          <div>
            <span>源文本</span>
            <strong>{sourceText.length.toLocaleString()} 字</strong>
          </div>
          <div>
            <span>段落</span>
            <strong>{sourceParagraphs}</strong>
          </div>
          <div>
            <span>门槛</span>
            <strong>{importedEnough ? "通过" : "需 3 章"}</strong>
          </div>
        </div>

        <div className="style-grid">
          <label>
            类型
            <input className="input-control" value={style.genre} onChange={(event) => setStyle({ ...style, genre: event.target.value })} />
          </label>
          <label>
            时长
            <input
              className="input-control"
              type="number"
              min={3}
              value={style.target_runtime_minutes}
              onChange={(event) => setStyle({ ...style, target_runtime_minutes: Number(event.target.value) || 12 })}
            />
          </label>
        </div>

        <label className="model-toggle">
          <input type="checkbox" checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)} />
          API 或本地模型优先
        </label>

        <div className="model-profile">
          <div className="model-profile-head">
            <span>模型连接</span>
            <Badge tone={!useLlm ? "neutral" : modelTest?.ok ? "success" : "warning"}>
              {!useLlm ? "fallback" : modelTest?.ok ? "已验证" : modelProfile.provider}
            </Badge>
          </div>
          <div className="segmented-control">
            {(["api", "local", "fallback"] as const).map((provider) => (
              <button
                key={provider}
                className={modelProfile.provider === provider ? "active" : ""}
                onClick={() => {
                  setUseLlm(provider !== "fallback");
                  setModelProfile((current) => ({
                    ...current,
                    provider,
                    base_url:
                      provider === "local"
                        ? "http://127.0.0.1:11434/v1"
                        : provider === "fallback"
                          ? "local://deterministic-fallback"
                          : current.base_url.startsWith("local://")
                            ? DEFAULT_MODEL_PROFILE.base_url
                            : current.base_url,
                    model: provider === "fallback" ? "fallback" : provider === "local" ? "qwen2.5:14b" : current.model || "gpt-5.5",
                  }));
                }}
                type="button"
              >
                {provider}
              </button>
            ))}
          </div>
          <label>
            Base URL
            <input
              className="input-control"
              value={modelProfile.base_url}
              disabled={modelProfile.provider === "fallback"}
              onChange={(event) => setModelProfile((current) => ({ ...current, base_url: event.target.value }))}
            />
          </label>
          <div className="style-grid">
            <label>
              模型
              <input
                className="input-control"
                value={modelProfile.model}
                disabled={modelProfile.provider === "fallback"}
                onChange={(event) => setModelProfile((current) => ({ ...current, model: event.target.value }))}
              />
            </label>
            <label>
              温度
              <input
                className="input-control"
                type="number"
                min={0}
                max={2}
                step={0.1}
                value={modelProfile.temperature}
                disabled={modelProfile.provider === "fallback"}
                onChange={(event) => setModelProfile((current) => ({ ...current, temperature: Number(event.target.value) || 0 }))}
              />
            </label>
          </div>
          <label>
            API Key
            <input
              className="input-control"
              type="password"
              autoComplete="off"
              value={modelProfile.api_key ?? ""}
              disabled={modelProfile.provider !== "api"}
              onChange={(event) => setModelProfile((current) => ({ ...current, api_key: event.target.value }))}
              placeholder={modelProfile.provider === "api" ? "仅当前浏览器会话使用" : "本地模型通常不需要"}
            />
          </label>
          <label>
            服务端密钥引用
            <input
              className="input-control"
              value={modelProfile.api_key_secret_ref ?? ""}
              disabled={modelProfile.provider !== "api"}
              onChange={(event) => setModelProfile((current) => ({ ...current, api_key_secret_ref: event.target.value }))}
              placeholder="例如 PROD_OPENAI，由服务端环境变量解析"
            />
          </label>
          <div className="model-profile-foot">
            <small>{modelTest ? `${modelTest.message} ${modelTest.latency_ms}ms` : "项目只保存脱敏配置，key 不写入任务或项目记录；生产可使用服务端密钥引用。"}</small>
            <button className="btn-secondary compact" onClick={onTestModel} disabled={!useLlm || !!loading} type="button">
              {loading === "model-test" ? <Loader2 className="animate-spin" size={14} /> : <Server size={14} />}
              测试
            </button>
          </div>
        </div>

        <div className="rail-callout">
          <strong>导入支持</strong>
          <span>.txt / .md / .markdown / .docx / .pdf，超过 {formatBytes(CHUNKED_IMPORT_THRESHOLD_BYTES)} 自动走分片上传。</span>
        </div>
        {activeImportSession && activeImportSession.status === "pending" && (
          <div className="chunk-session-meter">
            <div className="entity-heading">
              <strong>分片上传</strong>
              <Badge tone="warning">
                {activeImportSession.uploaded_count}/{activeImportSession.total_chunks}
              </Badge>
            </div>
            <div className="progress-track" aria-label="分片上传进度">
              <span style={{ width: `${Math.round((activeImportSession.uploaded_count / activeImportSession.total_chunks) * 100)}%` }} />
            </div>
          </div>
        )}

        <div className="button-row">
          <input
            ref={importInputRef}
            className="sr-only"
            type="file"
            accept=".txt,.md,.markdown,.docx,.pdf,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onImportSource(file);
            }}
          />
          <button className="btn-secondary flex-1" onClick={() => importInputRef.current?.click()} disabled={!!loading} type="button">
            {loading === "import-source" ? <Loader2 className="animate-spin" size={15} /> : <FileText size={15} />}
            导入
          </button>
          <button className="btn-secondary flex-1" onClick={onSample} disabled={!!loading}>
            {loading === "sample" ? <Loader2 className="animate-spin" size={15} /> : <BookOpen size={15} />}
            样例
          </button>
          <button className="btn-secondary flex-1" onClick={onDetect} disabled={!sourceText || !!loading}>
            <Layers3 size={15} />
            索引
          </button>
          <button className="btn-primary flex-1" onClick={onSave} disabled={!title || !!loading}>
            {loading === "save-project" ? <Loader2 className="animate-spin" size={15} /> : <Save size={15} />}
            保存
          </button>
        </div>
      </section>

      <section className="rail-section source-section">
        <div className="section-heading">
          <span>小说原文与证据</span>
          <small>{sourceText.length.toLocaleString()} 字</small>
        </div>
        <textarea
          className="source-editor"
          value={sourceText}
          onChange={(event) => setSourceText(event.target.value)}
          placeholder="粘贴小说正文，或导入 txt / md / markdown 文件"
        />
        <div className="chapter-stack">
          {chapters.map((chapter) => (
            <button key={chapter.id} className="chapter-item" type="button">
              <span>
                <strong>{chapter.title}</strong>
                <small>{chapter.paragraphs.length} 段证据</small>
              </span>
              <ChevronRight size={14} />
            </button>
          ))}
          {!chapters.length && <p className="empty-copy">导入或点击“索引”后显示章节证据。</p>}
        </div>
      </section>

      <section className="rail-section library-section">
        <div className="section-heading">
          <span>项目库</span>
          <small>{projects.length} 个</small>
        </div>
        <div className="project-stack">
          {projects.slice(0, 8).map((project) => (
            <button
              key={project.id}
              className={currentProject?.id === project.id ? "project-item active" : "project-item"}
              onClick={() => onOpenProject(project.id)}
              type="button"
            >
              <Library size={15} />
              <span>
                <strong>{displayTitle(project.title, "历史项目")}</strong>
                <small>
                  {project.version_count} 版 / {project.quality_score ?? "-"} 分
                </small>
              </span>
            </button>
          ))}
          {!projects.length && <p className="empty-copy">暂无已保存项目</p>}
        </div>
      </section>
    </aside>
  );
}

function ScriptWorkspace({
  screenplay,
  selectedScene,
  selectedSceneId,
  setSelectedSceneId,
  rewriteInstruction,
  setRewriteInstruction,
  rewriteMode,
  setRewriteMode,
  onRewrite,
  loading,
}: {
  screenplay: Screenplay | null;
  selectedScene: Scene | null;
  selectedSceneId: string | null;
  setSelectedSceneId: (id: string) => void;
  rewriteInstruction: string;
  setRewriteInstruction: (value: string) => void;
  rewriteMode: RewriteMode;
  setRewriteMode: (mode: RewriteMode) => void;
  onRewrite: () => void;
  loading: string | null;
}) {
  if (!screenplay || !selectedScene) {
    return <EmptyPanel icon={<Film size={24} />} title="等待剧本版本" text="运行流水线后显示专业剧本文稿。" />;
  }

  const selectedSceneIndex = screenplay.scenes.findIndex((scene) => scene.id === selectedScene.id);
  const evidenceCount = selectedScene.source_refs.reduce((total, ref) => total + ref.paragraph_ids.length, 0);
  const qualityFlags = selectedScene.quality_flags.length ? selectedScene.quality_flags : ["无阻断风险"];
  const actEntries = Array.from(
    screenplay.scenes.reduce((map, scene) => {
      map.set(scene.act, (map.get(scene.act) ?? 0) + 1);
      return map;
    }, new Map<string, number>()),
  );
  const characterNames = selectedScene.characters.map((id) => resolveCharacterName(screenplay, id)).slice(0, 4);
  const sourceRefSummary = selectedScene.source_refs
    .slice(0, 3)
    .map((ref) => `${ref.chapter_id}:${ref.paragraph_ids.length}`)
    .join(" / ");

  return (
    <div className="script-layout">
      <aside className="scene-index">
        <div className="pane-heading">
          <span>场景索引</span>
          <Badge>{screenplay.scenes.length} 场</Badge>
        </div>
        <div className="scene-index-summary">
          <div>
            <span>当前</span>
            <strong>{String(selectedSceneIndex + 1).padStart(2, "0")}</strong>
          </div>
          <div>
            <span>证据</span>
            <strong>{evidenceCount}</strong>
          </div>
          <div>
            <span>风险</span>
            <strong>{selectedScene.quality_flags.length}</strong>
          </div>
        </div>
        <div className="scene-act-map" aria-label="幕结构">
          {actEntries.map(([act, count]) => (
            <span key={act}>
              {act} <strong>{count}</strong>
            </span>
          ))}
        </div>
        <div className="scene-stack">
          {screenplay.scenes.map((scene, index) => (
            <button
              key={scene.id}
              className={scene.id === selectedSceneId ? "scene-row active" : "scene-row"}
              onClick={() => setSelectedSceneId(scene.id)}
              type="button"
            >
              <span className="scene-number">{String(index + 1).padStart(2, "0")}</span>
              <span>
                <strong>{scene.title}</strong>
                <small>
                  {scene.act} / {scene.sequence} / {scene.heading.context}.{scene.heading.time_of_day}
                </small>
              </span>
              <Badge tone={scene.quality_flags.length ? "warning" : "success"}>{scene.quality_flags.length ? "处理" : "就绪"}</Badge>
            </button>
          ))}
        </div>
      </aside>

      <article className="script-editor">
        <div className="script-deskbar">
          <span>Scene {String(selectedSceneIndex + 1).padStart(2, "0")}</span>
          <span>{selectedScene.act}</span>
          <span>{selectedScene.sequence}</span>
          <Badge tone={selectedScene.quality_flags.length ? "warning" : "success"}>{selectedScene.quality_flags.length ? "需处理" : "可审阅"}</Badge>
        </div>
        <header className="script-header">
          <div>
            <Badge tone="accent">
              {selectedScene.heading.context}. {selectedScene.heading.time_of_day}
            </Badge>
            <h2>{selectedScene.title}</h2>
            <p>{selectedScene.summary}</p>
          </div>
          <div className="scene-stat-strip">
            <MetricPill label="证据" value={`${evidenceCount}`} />
            <MetricPill label="元素" value={`${selectedScene.elements.length}`} />
            <MetricPill label="角色" value={`${selectedScene.characters.length}`} />
          </div>
        </header>

        <section className="scene-operation-grid" aria-label="场景生产要素">
          <div>
            <span>场景头</span>
            <strong>
              {selectedScene.heading.context} / {selectedScene.heading.time_of_day}
            </strong>
          </div>
          <div>
            <span>来源</span>
            <strong>{sourceRefSummary || "无 source_refs"}</strong>
          </div>
          <div>
            <span>角色</span>
            <strong>{characterNames.join(" / ") || "未指定"}</strong>
          </div>
          <div>
            <span>制片备注</span>
            <strong>{selectedScene.production_notes[0] || "待补充"}</strong>
          </div>
        </section>

        <section className="scene-brief">
          <div>
            <span>戏剧目的</span>
            <p>{selectedScene.dramatic_purpose}</p>
          </div>
          <div>
            <span>冲突</span>
            <p>{selectedScene.conflict}</p>
          </div>
          <div>
            <span>情绪转折</span>
            <p>{selectedScene.emotional_shift || "未定义"}</p>
          </div>
        </section>

        <section className="scene-review-strip" aria-label="场景质量旗标">
          {qualityFlags.slice(0, 4).map((flag) => (
            <span key={flag}>{flag}</span>
          ))}
        </section>

        <section className="screenplay-page" aria-label="剧本文稿">
          <div className="screenplay-page-head">
            <span>SCREENPLAY DRAFT</span>
            <strong>{selectedScene.title}</strong>
            <small>
              {selectedScene.act} / {selectedScene.sequence} / Scene {String(selectedSceneIndex + 1).padStart(2, "0")}
            </small>
          </div>
          {selectedScene.elements.map((element) => (
            <div key={element.id} className={`screenplay-line ${element.type}`}>
              <span>{element.type}</span>
              {element.type === "dialogue" && element.character_id && <strong>{resolveCharacterName(screenplay, element.character_id)}</strong>}
              {element.emotion && <em>{element.emotion}</em>}
              <p>{element.text}</p>
            </div>
          ))}
        </section>

        <section className="rewrite-console">
          <div className="rewrite-modes">
            {rewriteModes.map((mode) => (
              <button key={mode.id} className={rewriteMode === mode.id ? "active" : ""} onClick={() => setRewriteMode(mode.id)} type="button">
                {mode.label}
              </button>
            ))}
          </div>
          <textarea value={rewriteInstruction} onChange={(event) => setRewriteInstruction(event.target.value)} />
          <button className="btn-primary" onClick={onRewrite} disabled={!!loading}>
            {loading === "rewrite" ? <Loader2 className="animate-spin" size={15} /> : <Wand2 size={15} />}
            证据改写
          </button>
        </section>
      </article>
    </div>
  );
}

function StructureWorkspace({
  screenplay,
  logs,
  capabilities,
}: {
  screenplay: Screenplay | null;
  logs: string[];
  capabilities: CapabilitiesResponse | null;
}) {
  if (!screenplay) {
    return (
      <div className="overview-grid">
        {(capabilities?.pipeline_agents ?? ["ChapterIndexer", "StoryBibleAgent", "ScenePlanner", "ContinuityChecker"]).map((agent) => (
          <div key={agent} className="agent-tile">
            <ShieldCheck size={16} />
            <strong>{agent}</strong>
          </div>
        ))}
        <ActivityPanel logs={logs} />
      </div>
    );
  }

  return (
    <div className="structure-grid">
      <section className="studio-panel">
        <h3>人物弧光</h3>
        <div className="entity-stack">
          {screenplay.story_bible.characters.map((character) => (
            <article key={character.id} className="entity-card">
              <div className="entity-heading">
                <strong>{character.name}</strong>
                <Badge>{character.role}</Badge>
              </div>
              <p>{character.description}</p>
              <dl>
                <dt>欲望</dt>
                <dd>{character.arc.desire || character.goals[0]}</dd>
                <dt>恐惧</dt>
                <dd>{character.arc.fear || "未定义"}</dd>
              </dl>
            </article>
          ))}
        </div>
      </section>

      <section className="studio-panel">
        <h3>冲突与伏笔</h3>
        <div className="entity-stack">
          {screenplay.story_bible.conflicts.map((conflict) => (
            <article key={conflict.id} className="entity-card">
              <div className="entity-heading">
                <strong>{conflict.title}</strong>
                <Badge tone="warning">{conflict.status}</Badge>
              </div>
              <p>{conflict.stakes}</p>
            </article>
          ))}
          {screenplay.story_bible.foreshadowing.map((thread) => (
            <article key={thread.id} className="entity-card">
              <strong>伏笔：{thread.setup}</strong>
              <p>回收：{thread.payoff}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="studio-panel">
        <h3>流水线</h3>
        <div className="pipeline-stack">
          {screenplay.metadata.pipeline_stages.map((stage) => (
            <PipelineStage key={stage.id} stage={stage} />
          ))}
        </div>
      </section>
    </div>
  );
}

function QualityWorkspace({
  screenplay,
  validation,
  onValidate,
  loading,
  batchRewriteMode,
  setBatchRewriteMode,
  batchRewriteInstruction,
  setBatchRewriteInstruction,
  batchRewriteMaxScenes,
  setBatchRewriteMaxScenes,
  onBatchRewrite,
  canBatchRewrite,
  currentActor,
  currentActorRole,
  sessionVerified,
}: {
  screenplay: Screenplay | null;
  validation: ValidationResult | null;
  onValidate: () => void;
  loading: string | null;
  batchRewriteMode: RewriteMode;
  setBatchRewriteMode: (mode: RewriteMode) => void;
  batchRewriteInstruction: string;
  setBatchRewriteInstruction: (value: string) => void;
  batchRewriteMaxScenes: number;
  setBatchRewriteMaxScenes: (value: number) => void;
  onBatchRewrite: () => void;
  canBatchRewrite: boolean;
  currentActor: string;
  currentActorRole: ProjectMember["role"] | null;
  sessionVerified: boolean;
}) {
  if (!screenplay) {
    return <EmptyPanel icon={<Gauge size={24} />} title="等待质量报告" text="生成剧本后显示质量门禁。" />;
  }

  const riskySceneCount = screenplay.scenes.filter((scene) => scene.quality_flags.length || !scene.source_refs.length || scene.conflict.length < 20).length;

  return (
    <div className="quality-layout">
      <section className="score-panel">
        <Gauge size={28} />
        <strong>{screenplay.quality_report.overall_score}</strong>
        <span>综合质量分</span>
        <button className="btn-secondary" onClick={onValidate} disabled={!!loading}>
          {loading === "validate" ? <Loader2 className="animate-spin" size={15} /> : <RefreshCcw size={15} />}
          重新校验
        </button>
      </section>

      <section className="studio-panel">
        <h3>质量指标</h3>
        <div className="metric-stack">
          {screenplay.quality_report.metrics.map((metric) => (
            <MetricRow key={metric.id} metric={metric} />
          ))}
        </div>
      </section>

      <section className="studio-panel quality-action-panel">
        <div className="entity-heading">
          <h3>批量改写任务</h3>
          <Badge tone={riskySceneCount ? "warning" : "success"}>{riskySceneCount || screenplay.scenes.length} 待处理</Badge>
        </div>
        <p className="panel-copy">从当前项目版本选择低证据链、低冲突或带质量标记的场景，进入后台改写任务并保存为新版本。</p>
        <div className="permission-strip">
          <ShieldCheck size={14} />
          <span>{currentActor}</span>
          <Badge tone="success">{currentActorRole ?? "owner"}</Badge>
          <Badge tone="success">{sessionVerified ? "本地全权限" : "本地单用户"}</Badge>
        </div>
        <div className="rewrite-modes">
          {rewriteModes.map((mode) => (
            <button key={mode.id} className={batchRewriteMode === mode.id ? "active" : ""} onClick={() => setBatchRewriteMode(mode.id)} type="button">
              {mode.label}
            </button>
          ))}
        </div>
        <textarea
          value={batchRewriteInstruction}
          onChange={(event) => setBatchRewriteInstruction(event.target.value)}
          aria-label="批量改写指令"
        />
        <div className="batch-rewrite-footer">
          <label>
            上限
            <input
              className="input-control"
              type="number"
              min={1}
              max={20}
              value={batchRewriteMaxScenes}
              onChange={(event) => setBatchRewriteMaxScenes(Math.max(1, Math.min(20, Number(event.target.value) || 1)))}
            />
          </label>
          <button className="btn-primary" onClick={onBatchRewrite} disabled={!canBatchRewrite || !!loading}>
            {loading === "batch-rewrite" ? <Loader2 className="animate-spin" size={15} /> : <Wand2 size={15} />}
            启动批量改写
          </button>
        </div>
        {!canBatchRewrite && (
          <small className="field-hint">
            请先保存项目并生成至少一个剧本版本。
          </small>
        )}
      </section>

      <section className="studio-panel">
        <h3>风险与建议</h3>
        <div className="risk-stack">
          {(validation?.issues.length ? validation.issues : screenplay.quality_report.risks).slice(0, 8).map((issue, index) => (
            <div key={`${issue.path}-${index}`} className="risk-line">
              <span>{issue.path}</span>
              <p>{issue.message}</p>
            </div>
          ))}
          {!validation?.issues.length &&
            screenplay.quality_report.recommendations.map((item) => (
              <div key={item} className="recommendation">
                <CheckCircle2 size={15} />
                {item}
              </div>
            ))}
        </div>
      </section>
    </div>
  );
}

function ProductionWorkspace({ screenplay }: { screenplay: Screenplay | null }) {
  if (!screenplay) {
    return <EmptyPanel icon={<ClipboardCheck size={24} />} title="等待制片拆解" text="生成剧本后显示生产维度。" />;
  }

  return (
    <div className="production-layout">
      <MetricCard icon={<FileText size={16} />} label="预计页数" value={`${screenplay.production.estimated_pages}`} />
      <MetricCard icon={<Clock size={16} />} label="预计时长" value={`${screenplay.production.estimated_runtime_minutes}m`} />
      <MetricCard icon={<MessageSquare size={16} />} label="演员" value={`${screenplay.production.cast_size}`} />
      <MetricCard icon={<MapPin size={16} />} label="地点" value={`${screenplay.production.location_count}`} />

      <section className="studio-panel wide">
        <h3>地点拆解</h3>
        <div className="entity-stack">
          {screenplay.production.location_breakdowns.map((item) => (
            <article key={item.location_id} className="entity-card">
              <div className="entity-heading">
                <strong>{resolveLocationName(screenplay, item.location_id)}</strong>
                <Badge>{item.scene_ids.length} 场</Badge>
              </div>
              <p>预计 {item.estimated_half_days} 个半天</p>
              <small>{item.requirements.join(" / ")}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="studio-panel wide">
        <h3>镜头计划</h3>
        <div className="entity-stack">
          {screenplay.production.shot_plan.slice(0, 10).map((shot) => (
            <article key={shot.scene_id} className="entity-card">
              <div className="entity-heading">
                <strong>{shot.scene_id}</strong>
                <Badge tone={shot.difficulty === "high" ? "warning" : "neutral"}>{shot.difficulty}</Badge>
              </div>
              <p>{shot.camera}</p>
              <small>{shot.sound}</small>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function YamlWorkspace({
  yamlText,
  setYamlText,
  validation,
  onValidate,
  loading,
}: {
  yamlText: string;
  setYamlText: (value: string) => void;
  validation: ValidationResult | null;
  onValidate: () => void;
  loading: string | null;
}) {
  return (
    <div className="yaml-workspace">
      <div className="yaml-toolbar">
        <Badge tone={validation?.valid ? "success" : validation ? "error" : "neutral"}>
          {validation ? (validation.valid ? "Schema 通过" : `${validation.issues.length} 个问题`) : "未校验"}
        </Badge>
        <button className="btn-secondary" onClick={onValidate} disabled={!yamlText || !!loading}>
          {loading === "validate" ? <Loader2 className="animate-spin" size={15} /> : <RefreshCcw size={15} />}
          校验
        </button>
      </div>
      <YamlEditor
        value={yamlText}
        onChange={setYamlText}
        issues={validation?.issues ?? []}
        valid={validation?.valid}
        onValidate={onValidate}
        validating={loading === "validate"}
      />
    </div>
  );
}

function InspectorPanel({
  activeView,
  setActiveView,
  selectedScene,
  screenplay,
  validation,
  activeJob,
  queueStatus,
  deadLetterQueue,
  capabilities,
  evidence,
  evidenceQuery,
  setEvidenceQuery,
  evidenceSearch,
  onEvidenceSearch,
  currentProject,
  importHistory,
  exportHistory,
  lastExport,
  approvalHistory,
  lastApproval,
  deliveryPackageHistory,
  lastDeliveryPackage,
  projectReadiness,
  systemReadiness,
  activeImportSession,
  reviewComment,
  setReviewComment,
  reviewAssignee,
  setReviewAssignee,
  replyDrafts,
  setReplyDrafts,
  auditFilter,
  auditEvents,
  currentActor,
  activeSession,
  sessionVerified,
  notifications,
  onCreateComment,
  onUpdateComment,
  onCreateReply,
  onAuditFilter,
  onMarkNotificationRead,
  onJobAction,
  onRunWorkerOnce,
  onExport,
  onSubmitApproval,
  onDecideApproval,
  onCreateDeliveryPackage,
  projectVersions,
  compareBaseVersionId,
  setCompareBaseVersionId,
  versionCompare,
  onCompareVersions,
  onRestoreVersion,
  loading,
  lastRewrite,
}: {
  activeView: InspectorView;
  setActiveView: (view: InspectorView) => void;
  selectedScene: Scene | null;
  screenplay: Screenplay | null;
  validation: ValidationResult | null;
  activeJob: JobRecord | null;
  queueStatus: JobQueueStatus | null;
  deadLetterQueue: DeadLetterQueueResponse | null;
  capabilities: CapabilitiesResponse | null;
  evidence: SourceEvidence[];
  evidenceQuery: string;
  setEvidenceQuery: (value: string) => void;
  evidenceSearch: SourceEvidence[];
  onEvidenceSearch: () => void;
  currentProject: ProjectRecord | null;
  importHistory: ImportHistoryResponse | null;
  exportHistory: ProjectExportHistoryResponse | null;
  lastExport: ProjectExportRecord | null;
  approvalHistory: ProjectApprovalHistoryResponse | null;
  lastApproval: ProjectApprovalRecord | null;
  deliveryPackageHistory: ProjectDeliveryPackageHistoryResponse | null;
  lastDeliveryPackage: ProjectDeliveryPackageRecord | null;
  projectReadiness: ProjectReadinessResponse | null;
  systemReadiness: SystemReadinessResponse | null;
  activeImportSession: ImportSessionStatus | null;
  reviewComment: string;
  setReviewComment: (value: string) => void;
  reviewAssignee: string;
  setReviewAssignee: (value: string) => void;
  replyDrafts: Record<string, string>;
  setReplyDrafts: (value: SetStateAction<Record<string, string>>) => void;
  auditFilter: AuditFilter;
  auditEvents: AuditEvent[];
  currentActor: string;
  activeSession: ProjectSession | null;
  sessionVerified: boolean;
  notifications: ProjectNotification[];
  onCreateComment: () => void;
  onUpdateComment: (commentId: string, status: ProjectComment["status"]) => void;
  onCreateReply: (commentId: string) => void;
  onAuditFilter: (filter: AuditFilter) => void;
  onMarkNotificationRead: (notificationId: string) => void;
  onJobAction: (action: "cancel" | "retry", jobId?: string) => void;
  onRunWorkerOnce: () => void;
  onExport: (format: ExportFormat) => void;
  onSubmitApproval: (format: ExportFormat | null, note: string) => void;
  onDecideApproval: (approvalId: string, decision: ApprovalDecision, note: string) => void;
  onCreateDeliveryPackage: (formats: ExportFormat[], approvalId: string | null, note: string) => void;
  projectVersions: ProjectVersionSummary[];
  compareBaseVersionId: string;
  setCompareBaseVersionId: (value: string) => void;
  versionCompare: VersionCompareResponse | null;
  onCompareVersions: (baseVersionId?: string) => void;
  onRestoreVersion: (versionId: string) => void;
  loading: string | null;
  lastRewrite: { sceneId: string; evidence: SourceEvidence[]; diffSummary: string[]; provider: string; providerStatus: string } | null;
}) {
  const visibleEvidence = evidenceSearch.length ? evidenceSearch : evidence;
  const selectedEvidenceCount = selectedScene?.source_refs.reduce((total, ref) => total + ref.paragraph_ids.length, 0) ?? 0;
  return (
    <aside className="studio-inspector">
      <nav className="inspector-tabs" aria-label="检查器">
        {inspectorViews.map((view) => (
          <button key={view.id} className={activeView === view.id ? "active" : ""} onClick={() => setActiveView(view.id)} type="button">
            {view.icon}
            {view.label}
          </button>
        ))}
      </nav>

      {activeView === "scene" && (
        <div className="inspector-content">
          <section className="inspector-section">
            <div className="entity-heading">
              <h3>场景检查</h3>
              <Badge tone={selectedScene?.quality_flags.length ? "warning" : selectedScene ? "success" : "neutral"}>
                {selectedScene?.quality_flags.length ? "risk" : selectedScene ? "ready" : "empty"}
              </Badge>
            </div>
            {selectedScene ? (
              <>
                <div className="inspection-grid">
                  <div>
                    <span>ID</span>
                    <strong>{selectedScene.id}</strong>
                  </div>
                  <div>
                    <span>章节</span>
                    <strong>{selectedScene.chapter_ids.join(", ")}</strong>
                  </div>
                  <div>
                    <span>证据段</span>
                    <strong>{selectedEvidenceCount}</strong>
                  </div>
                  <div>
                    <span>人物</span>
                    <strong>{selectedScene.characters.length}</strong>
                  </div>
                </div>
                {!!selectedScene.quality_flags.length && (
                  <div className="inspection-alert">
                    <AlertCircle size={15} />
                    <span>{selectedScene.quality_flags.join(" / ")}</span>
                  </div>
                )}
                <div className="mini-stack">
                  {selectedScene.beats.map((beat) => (
                    <div key={beat} className="mini-line">
                      <ListChecks size={14} />
                      {beat}
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="empty-copy">暂无选中场景</p>
            )}
          </section>

          <JobSnapshot job={activeJob} queueStatus={queueStatus} deadLetterQueue={deadLetterQueue} onJobAction={onJobAction} onRunWorkerOnce={onRunWorkerOnce} loading={loading} />
          <QualitySnapshot screenplay={screenplay} validation={validation} />
        </div>
      )}

      {activeView === "evidence" && (
        <section className="inspector-section evidence-section">
          <h3>原文证据</h3>
          <div className="evidence-search">
            <input
              className="input-control"
              value={evidenceQuery}
              onChange={(event) => setEvidenceQuery(event.target.value)}
              placeholder="搜索项目证据库"
            />
            <button className="btn-secondary" onClick={onEvidenceSearch} disabled={!evidenceQuery.trim() || !!loading}>
              {loading === "evidence-search" ? <Loader2 className="animate-spin" size={15} /> : <BookOpen size={15} />}
              检索
            </button>
          </div>
          {visibleEvidence.length ? (
            visibleEvidence.map((item) => (
              <article key={item.id} className="evidence-card">
                <div className="entity-heading">
                  <strong>{item.chapter_title}</strong>
                  <Badge>{item.reason}</Badge>
                </div>
                <small>
                  第 {item.paragraph_index} 段 / {Math.round(item.score)} 分
                </small>
                <p>{item.text}</p>
              </article>
            ))
          ) : (
            <p className="empty-copy">暂无证据</p>
          )}
        </section>
      )}

      {activeView === "review" && (
        <ReviewPanel
          project={currentProject}
          selectedScene={selectedScene}
          reviewComment={reviewComment}
          setReviewComment={setReviewComment}
          reviewAssignee={reviewAssignee}
          setReviewAssignee={setReviewAssignee}
          replyDrafts={replyDrafts}
          setReplyDrafts={setReplyDrafts}
          auditFilter={auditFilter}
          auditEvents={auditEvents}
          onCreateComment={onCreateComment}
          onUpdateComment={onUpdateComment}
          onCreateReply={onCreateReply}
          onAuditFilter={onAuditFilter}
          loading={loading}
        />
      )}

      {activeView === "diff" && (
        <section className="inspector-section">
          <h3>改写结果</h3>
          {lastRewrite ? (
            <>
              <Badge tone={lastRewrite.providerStatus === "ok" ? "success" : "warning"}>
                {lastRewrite.provider}/{lastRewrite.providerStatus}
              </Badge>
              <div className="mini-stack">
                {lastRewrite.diffSummary.map((item) => (
                  <div key={item} className="mini-line">
                    <SquarePen size={14} />
                    {item}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="empty-copy">暂无局部改写记录</p>
          )}
        </section>
      )}

      {activeView === "project" && (
        <div className="inspector-content">
          <SystemReadinessPanel readiness={systemReadiness} />
          <ReadinessPanel readiness={projectReadiness} currentProject={currentProject} />
          <ApprovalCenterPanel
            project={currentProject}
            history={approvalHistory}
            lastApproval={lastApproval}
            readiness={projectReadiness}
            currentActor={currentActor}
            onSubmitApproval={onSubmitApproval}
            onDecideApproval={onDecideApproval}
            loading={loading}
          />
          <DeliveryPackagePanel
            project={currentProject}
            approvalHistory={approvalHistory}
            history={deliveryPackageHistory}
            lastPackage={lastDeliveryPackage}
            readiness={projectReadiness}
            currentActor={currentActor}
            onCreatePackage={onCreateDeliveryPackage}
            loading={loading}
          />
          <ExportGovernancePanel
            project={currentProject}
            history={exportHistory}
            lastExport={lastExport}
            readiness={projectReadiness}
            onExport={onExport}
            loading={loading}
          />
          <ProjectCollaborationPanel
            project={currentProject}
            currentActor={currentActor}
            activeSession={activeSession}
            sessionVerified={sessionVerified}
            notifications={notifications}
            onMarkNotificationRead={onMarkNotificationRead}
            loading={loading}
          />
          <ImportHistoryPanel
            history={importHistory}
            currentProject={currentProject}
            activeJob={activeJob}
            activeImportSession={activeImportSession}
          />
          <VersionPanel
            project={currentProject}
            versions={projectVersions}
            compareBaseVersionId={compareBaseVersionId}
            setCompareBaseVersionId={setCompareBaseVersionId}
            compare={versionCompare}
            onCompareVersions={onCompareVersions}
            onRestoreVersion={onRestoreVersion}
            loading={loading}
          />
          <PipelineSnapshot stages={screenplay?.metadata.pipeline_stages ?? []} />
          <section className="inspector-section">
            <h3>开源底层</h3>
            <div className="tag-cloud">
              {(capabilities?.open_source_stack ?? ["FastAPI", "Pydantic", "Next.js", "React"]).map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
          </section>
        </div>
      )}
    </aside>
  );
}

function ReviewPanel({
  project,
  selectedScene,
  reviewComment,
  setReviewComment,
  reviewAssignee,
  setReviewAssignee,
  replyDrafts,
  setReplyDrafts,
  auditFilter,
  auditEvents,
  onCreateComment,
  onUpdateComment,
  onCreateReply,
  onAuditFilter,
  loading,
}: {
  project: ProjectRecord | null;
  selectedScene: Scene | null;
  reviewComment: string;
  setReviewComment: (value: string) => void;
  reviewAssignee: string;
  setReviewAssignee: (value: string) => void;
  replyDrafts: Record<string, string>;
  setReplyDrafts: (value: SetStateAction<Record<string, string>>) => void;
  auditFilter: AuditFilter;
  auditEvents: AuditEvent[];
  onCreateComment: () => void;
  onUpdateComment: (commentId: string, status: ProjectComment["status"]) => void;
  onCreateReply: (commentId: string) => void;
  onAuditFilter: (filter: AuditFilter) => void;
  loading: string | null;
}) {
  const comments = project?.comments ?? [];
  const sceneComments = selectedScene ? comments.filter((comment) => comment.scene_id === selectedScene.id) : comments;
  const openCount = comments.filter((comment) => comment.status === "open").length;
  return (
    <div className="inspector-content">
      <section className="inspector-section review-compose">
        <div className="entity-heading">
          <h3>审阅意见</h3>
          <Badge tone={openCount ? "warning" : "success"}>{openCount} open</Badge>
        </div>
        <textarea
          value={reviewComment}
          onChange={(event) => setReviewComment(event.target.value)}
          placeholder={selectedScene ? `给 ${selectedScene.id} 写审阅意见` : "给项目写审阅意见"}
        />
        <div className="review-inline-grid">
          <input
            className="input-control"
            value={reviewAssignee}
            onChange={(event) => setReviewAssignee(event.target.value)}
            placeholder="指派给"
          />
          <button className="btn-primary" onClick={onCreateComment} disabled={!project || !reviewComment.trim() || !!loading}>
            {loading === "comment" ? <Loader2 className="animate-spin" size={15} /> : <MessageSquare size={15} />}
            提交
          </button>
        </div>
      </section>

      <section className="inspector-section">
        <h3>场景评论</h3>
        <div className="review-stack">
          {sceneComments.length ? (
            sceneComments
              .slice(0, 8)
              .map((comment) => (
                <CommentCard
                  key={comment.id}
                  comment={comment}
                  loading={loading}
                  replyDraft={replyDrafts[comment.id] ?? ""}
                  setReplyDraft={(value) => setReplyDrafts((drafts) => ({ ...drafts, [comment.id]: value }))}
                  onCreateReply={onCreateReply}
                  onUpdateComment={onUpdateComment}
                />
              ))
          ) : (
            <p className="empty-copy">暂无场景评论</p>
          )}
        </div>
      </section>

      <section className="inspector-section">
        <div className="entity-heading">
          <h3>审计事件</h3>
          {loading === "audit-filter" && <Loader2 className="animate-spin" size={14} />}
        </div>
        <div className="audit-filter" role="tablist" aria-label="审计事件过滤">
          {auditFilters.map((filter) => (
            <button
              key={filter.id}
              className={auditFilter === filter.id ? "active" : ""}
              onClick={() => onAuditFilter(filter.id)}
              disabled={!project || !!loading}
              type="button"
            >
              {filter.label}
            </button>
          ))}
        </div>
        <div className="review-stack">
          {auditEvents.length ? (
            auditEvents.slice(0, 10).map((event) => (
              <div key={event.id} className="audit-line">
                <strong>{event.event_type}</strong>
                <span>{event.actor} / {new Date(event.created_at).toLocaleString()}</span>
                <p>{event.summary}</p>
              </div>
            ))
          ) : (
            <p className="empty-copy">暂无审计事件</p>
          )}
        </div>
      </section>
    </div>
  );
}

function ReadinessPanel({
  readiness,
  currentProject,
}: {
  readiness: ProjectReadinessResponse | null;
  currentProject: ProjectRecord | null;
}) {
  const blockers = readiness?.blockers ?? [];
  const warnings = readiness?.warnings ?? [];
  const passed = readiness?.passed ?? [];
  const headline = readiness
    ? readiness.status === "ready"
      ? "交付可放行"
      : readiness.status === "blocked"
        ? "交付被阻塞"
        : "交付需复核"
    : currentProject
      ? "交付门禁加载中"
      : "等待项目";
  const details = [...blockers, ...warnings].slice(0, 5);
  const score = readiness?.score ?? 0;

  return (
    <section className="inspector-section readiness-panel">
      <div className="entity-heading">
        <h3>交付门禁</h3>
        <Badge tone={readiness ? readinessTone(readiness.status) : "neutral"}>{readiness?.status ?? "pending"}</Badge>
      </div>

      <div className="readiness-score-row">
        <div className={`readiness-dial ${readiness ? readinessTone(readiness.status) : "neutral"}`}>
          <strong>{readiness ? score : "-"}</strong>
          <span>score</span>
        </div>
        <div>
          <strong>{headline}</strong>
          <p>
            {readiness
              ? `${blockers.length} blockers / ${warnings.length} warnings / ${passed.length} passed`
              : currentProject
                ? "正在从源文、版本、质量、证据链、导入安全和队列状态计算。"
                : "保存或打开项目后显示交付状态。"}
          </p>
        </div>
      </div>

      {readiness && (
        <>
          <div className="readiness-meter" aria-label="交付门禁分数">
            <span style={{ width: `${score}%` }} />
          </div>

          <div className="readiness-summary-grid">
            <div>
              <span>阻塞</span>
              <strong>{blockers.length}</strong>
            </div>
            <div>
              <span>警告</span>
              <strong>{warnings.length}</strong>
            </div>
            <div>
              <span>通过</span>
              <strong>{passed.length}</strong>
            </div>
          </div>

          <div className="readiness-checks">
            {details.length ? (
              details.map((check) => <ReadinessCheckLine key={check.id} check={check} />)
            ) : (
              <div className="readiness-pass-line">
                <CheckCircle2 size={14} />
                所有交付检查均已通过
              </div>
            )}
          </div>

          {!!readiness.next_actions.length && (
            <div className="readiness-actions">
              {readiness.next_actions.slice(0, 4).map((action) => (
                <div key={action} className="mini-line">
                  <ChevronRight size={14} />
                  {action}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}

function ReadinessCheckLine({ check }: { check: ProjectReadinessCheck }) {
  return (
    <article className={`readiness-check-line ${check.status}`}>
      <div className="entity-heading">
        <strong>{check.label}</strong>
        <Badge tone={readinessTone(check.status)}>{check.status}</Badge>
      </div>
      <p>{check.summary}</p>
    </article>
  );
}

function SystemReadinessPanel({ readiness }: { readiness: SystemReadinessResponse | null }) {
  const blockers = readiness?.blockers ?? [];
  const warnings = readiness?.warnings ?? [];
  const passed = readiness?.passed ?? [];
  const details = readiness ? [...blockers, ...warnings, ...passed].slice(0, 6) : [];
  return (
    <section className="inspector-section system-readiness-panel">
      <div className="entity-heading">
        <h3>部署就绪</h3>
        <Badge tone={readiness ? readinessTone(readiness.status) : "neutral"}>{readiness?.status ?? "pending"}</Badge>
      </div>

      <div className="system-readiness-head">
        <div className={`readiness-dial ${readiness ? readinessTone(readiness.status) : "neutral"}`}>
          <strong>{readiness ? readiness.score : "-"}</strong>
          <span>system</span>
        </div>
        <div>
          <strong>{readiness ? `${readiness.environment} / ${readiness.status}` : "系统门禁加载中"}</strong>
          <p>
            {readiness
              ? `${blockers.length} blockers / ${warnings.length} warnings / ${passed.length} passed`
              : "检查数据库、队列、密钥、导入扫描、交付存储和认证签名。"}
          </p>
        </div>
      </div>

      {readiness && (
        <>
          <div className="system-readiness-grid">
            <div>
              <span>DB</span>
              <strong>{systemCheckStatus(readiness.checks, "database")}</strong>
            </div>
            <div>
              <span>Queue</span>
              <strong>{systemCheckStatus(readiness.checks, "queue")}</strong>
            </div>
            <div>
              <span>Secrets</span>
              <strong>{systemCheckStatus(readiness.checks, "model_secrets")}</strong>
            </div>
          </div>

          <div className="readiness-checks">
            {details.map((check) => <SystemReadinessCheckLine key={check.id} check={check} />)}
          </div>

          {!!readiness.next_actions.length && (
            <div className="readiness-actions">
              {readiness.next_actions.slice(0, 3).map((action) => (
                <div key={action} className="mini-line">
                  <ChevronRight size={14} />
                  {action}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}

function SystemReadinessCheckLine({ check }: { check: SystemReadinessCheck }) {
  return (
    <article className={`readiness-check-line ${check.status}`}>
      <div className="entity-heading">
        <strong>{check.label}</strong>
        <Badge tone={readinessTone(check.status)}>{check.status}</Badge>
      </div>
      <p>{check.summary}</p>
      <small>{formatSystemEvidence(check.evidence)}</small>
    </article>
  );
}

function ApprovalCenterPanel({
  project,
  history,
  lastApproval,
  readiness,
  currentActor,
  onSubmitApproval,
  onDecideApproval,
  loading,
}: {
  project: ProjectRecord | null;
  history: ProjectApprovalHistoryResponse | null;
  lastApproval: ProjectApprovalRecord | null;
  readiness: ProjectReadinessResponse | null;
  currentActor: string;
  onSubmitApproval: (format: ExportFormat | null, note: string) => void;
  onDecideApproval: (approvalId: string, decision: ApprovalDecision, note: string) => void;
  loading: string | null;
}) {
  const [approvalNote, setApprovalNote] = useState("当前版本已完成审阅，提交交付审批。");
  const [decisionNote, setDecisionNote] = useState("同意作为本轮交付版本。");
  const [approvalFormat, setApprovalFormat] = useState<ExportFormat | "">("fountain");
  const approvals = history?.approvals ?? project?.approvals ?? [];
  const latest = lastApproval ?? approvals[0] ?? null;
  const canSubmit = !!project && !!project.current_version_id && !loading;
  const canApprove = !!latest && latest.status === "submitted" && !loading;
  const canRevoke = !!latest && latest.status === "submitted" && !loading;

  return (
    <section className="inspector-section approval-center-panel">
      <div className="entity-heading">
        <h3>交付审批</h3>
        <Badge tone={latest ? approvalTone(latest.status) : history?.pending ? "warning" : "neutral"}>
          {latest ? approvalStatusLabels[latest.status] : `${history?.total ?? approvals.length} 条`}
        </Badge>
      </div>

      <div className="approval-gate-line">
        <div>
          <span>Gate</span>
          <strong>{readiness ? `${readiness.score}% / ${readiness.status}` : "waiting"}</strong>
        </div>
        <div>
          <span>Actor</span>
          <strong>{currentActor}</strong>
        </div>
      </div>

      {latest ? (
        <article className={`approval-history-line ${latest.status}`}>
          <div className="entity-heading">
            <strong>{latest.version_label || latest.version_id || "未绑定版本"}</strong>
            <Badge tone={approvalTone(latest.status)}>{approvalStatusLabels[latest.status]}</Badge>
          </div>
          <small>
            {new Date(latest.submitted_at).toLocaleString()} / {latest.submitted_by}
            {latest.decided_by ? ` -> ${latest.decided_by}` : ""}
          </small>
          <div className="import-history-meta">
            <span>{latest.requested_export_format ?? "format open"}</span>
            <span>{latest.readiness_score}%</span>
            <span>{latest.readiness_status}</span>
          </div>
          {latest.submit_note && <p>{latest.submit_note}</p>}
          {latest.decision_note && <p className="approval-decision-note">{latest.decision_note}</p>}
          {!!latest.blockers.length && <p className="import-error">{latest.blockers.slice(0, 2).join(" / ")}</p>}
          {!latest.blockers.length && !!latest.warnings.length && <p className="import-warning">{latest.warnings.slice(0, 2).join(" / ")}</p>}
        </article>
      ) : (
        <p className="empty-copy">生成项目版本后，可直接提交、批准或撤回交付审批，并留下审计链。</p>
      )}

      <label className="field-label">
        提交说明
        <input className="input-control" value={approvalNote} onChange={(event) => setApprovalNote(event.target.value)} />
      </label>
      <div className="approval-action-row">
        <select
          className="input-control compact-select"
          value={approvalFormat}
          onChange={(event) => setApprovalFormat(event.target.value as ExportFormat | "")}
          disabled={!project || !!loading}
        >
          <option value="">格式待定</option>
          {exportFormats.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
        <button className="btn-secondary compact" type="button" onClick={() => onSubmitApproval(approvalFormat || null, approvalNote)} disabled={!canSubmit}>
          {loading === "approval-submit" ? <Loader2 className="animate-spin" size={14} /> : <LockKeyhole size={14} />}
          提交审批
        </button>
      </div>
      {project && <p className="hint-copy">本地单用户模式下，审批用于记录交付流程，不再要求切换成员身份。</p>}

      <label className="field-label">
        审批意见
        <input className="input-control" value={decisionNote} onChange={(event) => setDecisionNote(event.target.value)} />
      </label>
      <div className="approval-action-row">
        <button className="btn-secondary compact" type="button" disabled={!canApprove} onClick={() => latest && onDecideApproval(latest.id, "approve", decisionNote)}>
          <CheckCircle2 size={14} />
          批准
        </button>
        <button className="btn-secondary compact" type="button" disabled={!canApprove} onClick={() => latest && onDecideApproval(latest.id, "reject", decisionNote || "需要继续修改。")}>
          <AlertCircle size={14} />
          驳回
        </button>
        <button className="btn-secondary compact" type="button" disabled={!canRevoke} onClick={() => latest && onDecideApproval(latest.id, "revoke", decisionNote || "提交人撤回审批。")}>
          <RefreshCcw size={14} />
          撤回
        </button>
      </div>

      <div className="approval-history-stack">
        {approvals.slice(0, 4).map((item) => (
          <div key={item.id} className="approval-mini-line">
            <span>{approvalStatusLabels[item.status]}</span>
            <strong>{item.submitted_by}</strong>
            <small>{item.readiness_score}%</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function DeliveryPackagePanel({
  project,
  approvalHistory,
  history,
  lastPackage,
  readiness,
  currentActor,
  onCreatePackage,
  loading,
}: {
  project: ProjectRecord | null;
  approvalHistory: ProjectApprovalHistoryResponse | null;
  history: ProjectDeliveryPackageHistoryResponse | null;
  lastPackage: ProjectDeliveryPackageRecord | null;
  readiness: ProjectReadinessResponse | null;
  currentActor: string;
  onCreatePackage: (formats: ExportFormat[], approvalId: string | null, note: string) => void;
  loading: string | null;
}) {
  const [selectedFormats, setSelectedFormats] = useState<ExportFormat[]>(["yaml", "markdown", "fountain"]);
  const [selectedApprovalId, setSelectedApprovalId] = useState("");
  const [packageNote, setPackageNote] = useState("审批通过后生成正式交付包。");
  const [downloadStatus, setDownloadStatus] = useState<{ assetSha256: string; tone: "success" | "error" | "neutral"; message: string } | null>(null);
  const packages = history?.packages ?? project?.delivery_packages ?? [];
  const latest = lastPackage ?? packages[0] ?? null;
  const approvedApprovals = (approvalHistory?.approvals ?? project?.approvals ?? []).filter((approval) => approval.status === "approved");
  const hasDownloadPermission = true;
  const approvalId = selectedApprovalId || approvedApprovals.find((approval) => approval.version_id === project?.current_version_id)?.id || approvedApprovals[0]?.id || "";
  const latestAssets = latest?.assets ?? [];
  const signedAssetCount = latestAssets.filter((asset) => !!asset.download_url).length;
  const artifactCount = latest?.artifact_count || latestAssets.length;
  const canPackage =
    !!project &&
    !!project.current_version_id &&
    !!approvalId &&
    selectedFormats.length > 0 &&
    !loading;

  function toggleFormat(format: ExportFormat) {
    setSelectedFormats((items) => (items.includes(format) ? items.filter((item) => item !== format) : [...items, format]));
  }

  async function handleDownloadAsset(asset: ProjectDeliveryPackageAsset) {
    if (!asset.download_url) return;
    setDownloadStatus({ assetSha256: asset.sha256, tone: "neutral", message: `正在下载 ${asset.filename}` });
    try {
      await downloadSignedDeliveryAsset(asset);
      setDownloadStatus({ assetSha256: asset.sha256, tone: "success", message: `${asset.filename} 已通过 sha256 校验` });
    } catch (error) {
      setDownloadStatus({
        assetSha256: asset.sha256,
        tone: "error",
        message: error instanceof Error ? error.message : "交付资产下载失败",
      });
    }
  }

  return (
    <section className="inspector-section delivery-package-panel">
      <div className="entity-heading">
        <h3>交付包</h3>
        <Badge tone={latest?.status === "blocked" ? "error" : history?.succeeded ? "success" : "neutral"}>
          {history?.total ?? packages.length} 包
        </Badge>
      </div>

      <div className="delivery-gate-line">
        <div>
          <span>审批</span>
          <strong>{approvedApprovals.length ? `${approvedApprovals.length} approved` : "required"}</strong>
        </div>
        <div>
          <span>Gate</span>
          <strong>{readiness ? `${readiness.score}% / ${readiness.status}` : "waiting"}</strong>
        </div>
      </div>

      {latest ? (
        <article className={`delivery-package-line ${latest.status}`}>
          <div className="entity-heading">
            <strong>{latest.id}</strong>
            <Badge tone={latest.status === "succeeded" ? "success" : "error"}>{latest.status}</Badge>
          </div>
          <small>
            {new Date(latest.created_at).toLocaleString()} / {latest.actor} / {latest.version_label || latest.version_id || "no version"}
          </small>
          <div className="import-history-meta">
            <span>{latest.formats.join(", ") || "no files"}</span>
            <span>{formatBytes(latest.total_size_bytes)}</span>
            <span>{latest.storage_provider || "local"}</span>
            <span>{artifactCount} artifacts</span>
            <span>{latest.readiness_score}%</span>
            {latest.manifest_sha256 && <code>{shortHash(latest.manifest_sha256)}</code>}
          </div>

          <div className="delivery-download-summary">
            <div>
              <ShieldCheck size={14} />
              <span>{signedAssetCount ? `${signedAssetCount}/${artifactCount} 个签名下载` : "历史资产 metadata"}</span>
            </div>
            <small>{signedAssetCount ? formatDownloadExpiry(latest.download_expires_at ?? latestAssets.find((asset) => asset.download_expires_at)?.download_expires_at) : "需要有交付打包权限才返回临时链接"}</small>
          </div>

          {!!latestAssets.length && (
            <div className="delivery-asset-stack" aria-label="交付资产下载中心">
              {latestAssets.map((asset) => (
                <div key={`${latest.id}-${asset.sha256}-${asset.filename}`} className={asset.download_url ? "delivery-asset-line downloadable" : "delivery-asset-line locked"}>
                  <div className="delivery-asset-main">
                    <span title={asset.filename}>{asset.filename}</span>
                    <small>
                      {asset.format.toUpperCase()} / {asset.content_type || "application/octet-stream"}
                    </small>
                  </div>
                  <div className="delivery-asset-meta">
                    <small>{formatBytes(asset.size_bytes)}</small>
                    <code title={asset.sha256}>{shortHash(asset.sha256)}</code>
                  </div>
                  <button
                    className="icon-button delivery-download-button"
                    type="button"
                    title={asset.download_url ? `下载 ${asset.filename}` : "暂无签名下载链接"}
                    aria-label={asset.download_url ? `下载 ${asset.filename}` : `${asset.filename} 暂无下载链接`}
                    disabled={!asset.download_url || downloadStatus?.assetSha256 === asset.sha256 && downloadStatus.tone === "neutral"}
                    onClick={() => handleDownloadAsset(asset)}
                  >
                    {downloadStatus?.assetSha256 === asset.sha256 && downloadStatus.tone === "neutral" ? (
                      <Loader2 className="animate-spin" size={14} />
                    ) : asset.download_url ? (
                      <Download size={14} />
                    ) : (
                      <LockKeyhole size={14} />
                    )}
                  </button>
                </div>
              ))}
            </div>
          )}
          {downloadStatus && (
            <p className={`delivery-download-status ${downloadStatus.tone}`}>{downloadStatus.message}</p>
          )}
          {latest.status === "succeeded" && !signedAssetCount && (
            <p className="hint-copy">
              当前交付包缺少可复取链接，请重新刷新或确认本地 artifact 存储。
            </p>
          )}
          {!!latest.blockers.length && <p className="import-error">{latest.blockers.slice(0, 2).join(" / ")}</p>}
          {!latest.blockers.length && !!latest.warnings.length && <p className="import-warning">{latest.warnings.slice(0, 2).join(" / ")}</p>}
        </article>
      ) : (
        <p className="empty-copy">审批批准后，可直接生成包含 YAML、Markdown、Fountain、manifest 和 sha256 的正式交付包。</p>
      )}

      <label className="field-label">
        绑定审批
        <select
          className="input-control compact-select"
          value={selectedApprovalId}
          onChange={(event) => setSelectedApprovalId(event.target.value)}
          disabled={!approvedApprovals.length || !!loading}
        >
          <option value="">自动选择已批准审批</option>
          {approvedApprovals.map((approval) => (
            <option key={approval.id} value={approval.id}>
              {approval.version_label || approval.version_id || approval.id} / {approval.submitted_by}
            </option>
          ))}
        </select>
      </label>

      <div className="delivery-format-grid" aria-label="交付包格式">
        {exportFormats.map((item) => (
          <label key={item.id} className={selectedFormats.includes(item.id) ? "delivery-format-option active" : "delivery-format-option"}>
            <input type="checkbox" checked={selectedFormats.includes(item.id)} onChange={() => toggleFormat(item.id)} disabled={!!loading} />
            <span>{item.label}</span>
          </label>
        ))}
      </div>

      <label className="field-label">
        包说明
        <input className="input-control" value={packageNote} onChange={(event) => setPackageNote(event.target.value)} />
      </label>

      <button className="btn-secondary compact" type="button" disabled={!canPackage} onClick={() => onCreatePackage(selectedFormats, approvalId || null, packageNote)}>
        {loading === "delivery-package" ? <Loader2 className="animate-spin" size={14} /> : <ClipboardCheck size={14} />}
        生成交付包
      </button>
      {!approvedApprovals.length && project && <p className="hint-copy">需要先在交付审批中批准当前版本。</p>}

      <div className="delivery-package-stack">
        {packages.slice(0, 4).map((item) => (
          <div key={item.id} className="delivery-mini-line">
            <span>{item.status}</span>
            <strong>{item.formats.join("+") || "blocked"}</strong>
            <small>{item.artifact_count || item.assets.length} / {item.readiness_score}%</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function ExportGovernancePanel({
  project,
  history,
  lastExport,
  readiness,
  onExport,
  loading,
}: {
  project: ProjectRecord | null;
  history: ProjectExportHistoryResponse | null;
  lastExport: ProjectExportRecord | null;
  readiness: ProjectReadinessResponse | null;
  onExport: (format: ExportFormat) => void;
  loading: string | null;
}) {
  const exports = history?.exports ?? project?.exports ?? [];
  const latest = lastExport ?? exports[0] ?? null;
  const canExport = !!project && !loading;
  return (
    <section className="inspector-section export-governance-panel">
      <div className="entity-heading">
        <h3>导出治理</h3>
        <Badge tone={latest?.status === "blocked" ? "error" : history?.succeeded ? "success" : "neutral"}>
          {history?.total ?? exports.length} 次
        </Badge>
      </div>

      <div className="export-format-grid">
        {exportFormats.map((item) => (
          <button
            key={item.id}
            className="btn-secondary compact"
            type="button"
            onClick={() => onExport(item.id)}
            disabled={!canExport}
          >
            {loading === `export-${item.id}` ? <Loader2 className="animate-spin" size={14} /> : <Download size={14} />}
            {item.label}
          </button>
        ))}
      </div>

      <div className="export-gate-line">
        <span>Gate</span>
        <strong>{readiness ? `${readiness.score}% / ${readiness.status}` : "waiting"}</strong>
        <Badge tone={readiness ? readinessTone(readiness.status) : "neutral"}>{readiness?.status ?? "pending"}</Badge>
      </div>

      {latest ? (
        <article className={`export-history-line ${latest.status}`}>
          <div className="entity-heading">
            <strong>{latest.filename || latest.format}</strong>
            <Badge tone={latest.status === "succeeded" ? "success" : "error"}>{latest.status}</Badge>
          </div>
          <small>
            {new Date(latest.created_at).toLocaleString()} / {latest.actor} / {latest.version_label || latest.version_id || "no version"}
          </small>
          <div className="import-history-meta">
            <span>{latest.format}</span>
            <span>{formatBytes(latest.size_bytes)}</span>
            <span>{latest.readiness_score}%</span>
            {latest.sha256 && <code>{shortHash(latest.sha256)}</code>}
          </div>
          {!!latest.blockers.length && <p className="import-error">{latest.blockers.slice(0, 2).join(" / ")}</p>}
          {!latest.blockers.length && !!latest.warnings.length && <p className="import-warning">{latest.warnings.slice(0, 2).join(" / ")}</p>}
        </article>
      ) : (
        <p className="empty-copy">保存项目并生成版本后，这里会记录导出格式、版本、门禁状态、文件大小、sha256 和审计事件。</p>
      )}

      <div className="export-history-stack">
        {exports.slice(0, 4).map((item) => (
          <div key={item.id} className="export-mini-line">
            <span>{item.format}</span>
            <strong>{item.status}</strong>
            <small>{item.readiness_score}%</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function ProjectCollaborationPanel({
  project,
  currentActor,
  activeSession,
  sessionVerified,
  notifications,
  onMarkNotificationRead,
  loading,
}: {
  project: ProjectRecord | null;
  currentActor: string;
  activeSession: ProjectSession | null;
  sessionVerified: boolean;
  notifications: ProjectNotification[];
  onMarkNotificationRead: (notificationId: string) => void;
  loading: string | null;
}) {
  const members = project?.members ?? [];
  const activeMember = members.find((member) => member.name === currentActor);
  const unreadCount = notifications.filter((notification) => notification.unread).length;

  return (
    <section className="inspector-section collaboration-panel">
      <div className="entity-heading">
        <h3>本地项目模式</h3>
        <Badge tone="success">全权限</Badge>
      </div>

      <div className="session-card">
        <div className="entity-heading">
          <strong>当前操作者</strong>
          <Badge tone={sessionVerified ? "success" : "neutral"}>{sessionVerified ? "local owner" : "local"}</Badge>
        </div>
        <div className="session-meta">
          <span>{currentActor}</span>
          <span>{activeMember ? activeMember.role : "owner"}</span>
          <span>{activeSession ? activeSession.id : "未创建会话"}</span>
        </div>
        <p className="panel-copy">本地 Web 工作台默认由当前用户拥有全部项目操作权限，生成、改写、导出、审批和交付包不再要求切换身份。</p>
      </div>

      <div className="member-stack">
        <div className="member-line active">
          <strong>{LOCAL_PROJECT_ACTOR}</strong>
          <Badge tone="success">owner</Badge>
        </div>
      </div>

      <div className="notification-stack">
        <div className="entity-heading compact-heading">
          <strong>流程通知</strong>
          <small>{unreadCount} 未读</small>
        </div>
        {notifications.length ? (
          notifications.slice(0, 6).map((notification) => (
            <article key={notification.id} className={notification.unread ? "notification-line unread" : "notification-line"}>
              <div className="entity-heading">
                <strong>{notification.event_type}</strong>
                <Badge tone={notification.unread ? "warning" : "neutral"}>{notification.unread ? "unread" : "read"}</Badge>
              </div>
              <small>{notification.actor} / {new Date(notification.created_at).toLocaleString()}</small>
              <p>{notification.summary}</p>
              {notification.unread && (
                <button className="btn-secondary compact" onClick={() => onMarkNotificationRead(notification.id)} disabled={!!loading}>
                  {loading === `note-${notification.id}` ? <Loader2 className="animate-spin" size={14} /> : <CheckCircle2 size={14} />}
                  已读
                </button>
              )}
            </article>
          ))
        ) : (
          <p className="empty-copy">暂无通知</p>
        )}
      </div>
    </section>
  );
}

function ImportHistoryPanel({
  history,
  currentProject,
  activeJob,
  activeImportSession,
}: {
  history: ImportHistoryResponse | null;
  currentProject: ProjectRecord | null;
  activeJob: JobRecord | null;
  activeImportSession: ImportSessionStatus | null;
}) {
  const activeImportJob = activeJob?.kind === "import" && activeJob.project_id === currentProject?.id ? activeJob : null;
  const imports = history?.imports ?? [];
  const latest = imports[0] ?? null;
  return (
    <section className="inspector-section import-history-panel">
      <div className="entity-heading">
        <h3>导入历史</h3>
        <Badge tone={history?.failed ? "error" : history?.queued || history?.running ? "warning" : history?.total ? "success" : "neutral"}>
          {history?.total ?? 0} 次
        </Badge>
      </div>

      <div className="import-history-summary">
        <div>
          <span>成功</span>
          <strong>{history?.succeeded ?? 0}</strong>
        </div>
        <div>
          <span>进行中</span>
          <strong>{(history?.queued ?? 0) + (history?.running ?? 0)}</strong>
        </div>
        <div>
          <span>失败</span>
          <strong>{history?.failed ?? 0}</strong>
        </div>
      </div>

      {activeImportSession && activeImportSession.status === "pending" && (
        <div className="import-active-line">
          <div className="entity-heading">
            <strong>分片会话</strong>
            <Badge tone="warning">
              {activeImportSession.uploaded_count}/{activeImportSession.total_chunks}
            </Badge>
          </div>
          <div className="progress-track" aria-label="分片会话进度">
            <span style={{ width: `${Math.round((activeImportSession.uploaded_count / activeImportSession.total_chunks) * 100)}%` }} />
          </div>
          <small>{activeImportSession.filename} / {formatBytes(activeImportSession.size_bytes)}</small>
        </div>
      )}

      {activeImportJob && (
        <div className="import-active-line">
          <div className="entity-heading">
            <strong>当前导入</strong>
            <Badge tone={jobTone(activeImportJob.status)}>{activeImportJob.status}</Badge>
          </div>
          <div className="progress-track" aria-label="导入进度">
            <span style={{ width: `${activeImportJob.progress}%` }} />
          </div>
          <small>{activeImportJob.id} / {activeImportJob.queue_mode}</small>
        </div>
      )}

      {latest && (
        <div className="import-latest">
          <span>最近完成</span>
          <strong>{latest.filename || latest.job_id}</strong>
          <small>
            {latest.extraction_method || "pending"} / {latest.chapter_count} 章 / {latest.paragraph_count} 段 / {formatBytes(latest.size_bytes)}
          </small>
          <div className="import-security-row">
            <Badge tone={securityTone(latest.security_report.verdict)}>{latest.security_report.verdict}</Badge>
            <span>{latest.security_report.risk_level}</span>
            <span>{latest.upload_mode}</span>
            {latest.sha256 && <code>{shortHash(latest.sha256)}</code>}
          </div>
          {latest.last_stage_message && <p>{latest.last_stage_message}</p>}
        </div>
      )}

      <div className="import-history-stack">
        {imports.length ? (
          imports.slice(0, 5).map((item) => (
            <article key={item.job_id} className="import-history-line">
              <div className="entity-heading">
                <strong>{item.filename || item.job_id}</strong>
                <Badge tone={jobTone(item.status)}>{item.status}</Badge>
              </div>
              <small>
                {new Date(item.updated_at).toLocaleString()} / {item.actor} / {item.extraction_method || item.queue_mode}
              </small>
              <div className="import-history-meta">
                <span>{item.chapter_count} 章</span>
                <span>{item.paragraph_count} 段</span>
                <span>{formatBytes(item.size_bytes)}</span>
                <span>{item.upload_mode}</span>
                <span>{item.last_stage_id || "queued"}</span>
              </div>
              <div className="import-security-row">
                <Badge tone={securityTone(item.security_report.verdict)}>{item.security_report.verdict}</Badge>
                <span>{item.security_report.detected_file_type}</span>
                <span>{item.security_report.scanner}</span>
                {item.sha256 && <code>{shortHash(item.sha256)}</code>}
              </div>
              {item.warning_count > 0 && <p className="import-warning">{item.warnings.slice(0, 2).join(" / ")}</p>}
              {item.security_report.warnings.length > 0 && <p className="import-warning">{item.security_report.warnings.slice(0, 2).join(" / ")}</p>}
              {item.error && <p className="import-error">{item.error}</p>}
            </article>
          ))
        ) : (
          <p className="empty-copy">导入任务完成后，这里会保留文件、提取方式、章节统计、阶段和审计关联。</p>
        )}
      </div>
    </section>
  );
}

function VersionPanel({
  project,
  versions,
  compareBaseVersionId,
  setCompareBaseVersionId,
  compare,
  onCompareVersions,
  onRestoreVersion,
  loading,
}: {
  project: ProjectRecord | null;
  versions: ProjectVersionSummary[];
  compareBaseVersionId: string;
  setCompareBaseVersionId: (value: string) => void;
  compare: VersionCompareResponse | null;
  onCompareVersions: (baseVersionId?: string) => void;
  onRestoreVersion: (versionId: string) => void;
  loading: string | null;
}) {
  const current = versions.find((version) => version.is_current) ?? versions[0] ?? null;
  const comparableVersions = versions.filter((version) => version.id !== current?.id);
  return (
    <section className="inspector-section version-panel">
      <div className="entity-heading">
        <h3>版本治理</h3>
        <Badge tone={versions.length > 1 ? "success" : versions.length ? "warning" : "neutral"}>{versions.length} 版</Badge>
      </div>

      {current ? (
        <>
          <div className="version-current">
            <span>当前版本</span>
            <strong>{current.label}</strong>
            <small>
              {current.scene_count} 场 / {current.quality_score ?? "-"} 分 / {current.provider_status || "unknown"}
            </small>
          </div>

          <div className="version-compare-bar">
            <select
              className="input-control"
              value={compareBaseVersionId}
              onChange={(event) => setCompareBaseVersionId(event.target.value)}
              disabled={!comparableVersions.length || !!loading}
            >
              <option value="">选择基线版本</option>
              {comparableVersions.map((version) => (
                <option key={version.id} value={version.id}>
                  {version.label}
                </option>
              ))}
            </select>
            <button className="btn-secondary compact" onClick={() => onCompareVersions()} disabled={!compareBaseVersionId || !!loading}>
              {loading === "version-compare" ? <Loader2 className="animate-spin" size={14} /> : <GitBranch size={14} />}
              比较
            </button>
          </div>

          {compare && (
            <div className="version-compare-result">
              <div className="inspection-grid">
                <div>
                  <span>场景变化</span>
                  <strong>{compare.scene_count_delta >= 0 ? `+${compare.scene_count_delta}` : compare.scene_count_delta}</strong>
                </div>
                <div>
                  <span>质量变化</span>
                  <strong>{compare.quality_delta >= 0 ? `+${compare.quality_delta}` : compare.quality_delta}</strong>
                </div>
              </div>
              <div className="mini-stack">
                {compare.changed_scenes.slice(0, 4).map((change) => (
                  <div key={`${change.scene_id}-${change.change_type}`} className="mini-line">
                    <small>{change.change_type}</small>
                    {change.scene_id}: {change.summary}
                  </div>
                ))}
                {!compare.changed_scenes.length && <div className="mini-line">场景层没有结构变化。</div>}
              </div>
              {!!compare.yaml_diff_preview.length && (
                <pre className="diff-preview">{compare.yaml_diff_preview.slice(0, 12).join("\n")}</pre>
              )}
            </div>
          )}

          <div className="version-stack">
            {versions.map((version) => (
              <article key={version.id} className={version.is_current ? "version-line active" : "version-line"}>
                <div>
                  <strong>{version.label}</strong>
                  <small>
                    {new Date(version.created_at).toLocaleString()} / {version.scene_count} 场 / {version.yaml_bytes} bytes
                  </small>
                </div>
                <div className="version-actions">
                  <Badge tone={version.validation_valid ? "success" : "error"}>{version.validation_valid ? "valid" : "risk"}</Badge>
                  {!version.is_current && (
                    <button className="btn-secondary compact" onClick={() => onRestoreVersion(version.id)} disabled={!project || !!loading}>
                      {loading === `version-restore-${version.id}` ? <Loader2 className="animate-spin" size={14} /> : <RefreshCcw size={14} />}
                      恢复
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        </>
      ) : (
        <p className="empty-copy">生成剧本后会显示版本历史、比较和恢复入口。</p>
      )}
    </section>
  );
}

function CommentCard({
  comment,
  loading,
  replyDraft,
  setReplyDraft,
  onCreateReply,
  onUpdateComment,
}: {
  comment: ProjectComment;
  loading: string | null;
  replyDraft: string;
  setReplyDraft: (value: string) => void;
  onCreateReply: (commentId: string) => void;
  onUpdateComment: (commentId: string, status: ProjectComment["status"]) => void;
}) {
  const nextStatus = comment.status === "resolved" ? "open" : "resolved";
  return (
    <article className="comment-card">
      <div className="entity-heading">
        <strong>{comment.author}</strong>
        <Badge tone={comment.status === "resolved" ? "success" : "warning"}>{comment.status}</Badge>
      </div>
      <small>{comment.scene_id ?? "project"} / {new Date(comment.created_at).toLocaleString()}</small>
      <div className="review-meta">
        <span>指派给 {comment.assignee || "未指派"}</span>
        <span>{comment.replies?.length ?? 0} 回复</span>
      </div>
      <p>{comment.body}</p>
      {!!comment.replies?.length && (
        <div className="reply-stack">
          {comment.replies.slice(0, 4).map((reply) => (
            <div key={reply.id} className="reply-line">
              <strong>{reply.author}</strong>
              <span>{new Date(reply.created_at).toLocaleString()}</span>
              <p>{reply.body}</p>
            </div>
          ))}
        </div>
      )}
      <div className="reply-compose">
        <input
          className="input-control"
          value={replyDraft}
          onChange={(event) => setReplyDraft(event.target.value)}
          placeholder="回复线程"
        />
        <button className="btn-secondary compact" onClick={() => onCreateReply(comment.id)} disabled={!replyDraft.trim() || !!loading}>
          {loading === `reply-${comment.id}` ? <Loader2 className="animate-spin" size={14} /> : <MessagesSquare size={14} />}
          回复
        </button>
      </div>
      <button className="btn-secondary compact" onClick={() => onUpdateComment(comment.id, nextStatus)} disabled={!!loading}>
        {loading === `comment-${comment.id}` ? <Loader2 className="animate-spin" size={14} /> : <CheckCircle2 size={14} />}
        {comment.status === "resolved" ? "重开" : "解决"}
      </button>
    </article>
  );
}

function QualitySnapshot({ screenplay, validation }: { screenplay: Screenplay | null; validation: ValidationResult | null }) {
  return (
    <section className="inspector-section">
      <h3>质量快照</h3>
      <div className="snapshot-score">{screenplay ? screenplay.quality_report.overall_score : "-"}</div>
      <div className="snapshot-row">
        <span>Schema</span>
        <Badge tone={validation?.valid ? "success" : validation ? "error" : "neutral"}>
          {validation ? (validation.valid ? "通过" : "失败") : "未校验"}
        </Badge>
      </div>
      <div className="snapshot-row">
        <span>风险</span>
        <strong>{validation?.issues.length ?? screenplay?.quality_report.risks.length ?? 0}</strong>
      </div>
    </section>
  );
}

function JobSnapshot({
  job,
  queueStatus,
  deadLetterQueue,
  onJobAction,
  onRunWorkerOnce,
  loading,
}: {
  job: JobRecord | null;
  queueStatus: JobQueueStatus | null;
  deadLetterQueue: DeadLetterQueueResponse | null;
  onJobAction: (action: "cancel" | "retry", jobId?: string) => void;
  onRunWorkerOnce: () => void;
  loading: string | null;
}) {
  const deadLetterCount = queueStatus?.dead_lettered ?? deadLetterQueue?.dead_lettered ?? 0;
  return (
    <section className="inspector-section">
      <div className="entity-heading">
        <h3>任务队列</h3>
        <Badge tone={deadLetterCount ? "error" : queueStatus?.mode === "external" ? "warning" : "neutral"}>{deadLetterCount ? `${deadLetterCount} dead` : queueStatus?.mode ?? "unknown"}</Badge>
      </div>
      {job ? (
        <div className="job-snapshot">
          <div className="snapshot-row">
            <span>{job.id}</span>
            <Badge tone={job.status === "succeeded" ? "success" : job.status === "failed" || job.status === "canceled" || job.status === "dead_lettered" ? "error" : "warning"}>
              {job.status}
            </Badge>
          </div>
          <div className="snapshot-row">
            <span>{job.kind}</span>
            <strong>{job.queue_mode} / {job.attempts}/{job.max_attempts}</strong>
          </div>
          <div className="progress-track" aria-label="任务进度">
            <span style={{ width: `${job.progress}%` }} />
          </div>
          <strong>{job.progress}%</strong>
          <div className="job-actions">
            <button className="btn-secondary compact" onClick={() => onJobAction("cancel")} disabled={!["queued", "running"].includes(job.status) || !!loading}>
              {loading === "job-cancel" ? <Loader2 className="animate-spin" size={14} /> : <AlertCircle size={14} />}
              取消
            </button>
            <button className="btn-secondary compact" onClick={() => onJobAction("retry")} disabled={!["failed", "canceled", "dead_lettered"].includes(job.status) || !!loading}>
              {loading === "job-retry" ? <Loader2 className="animate-spin" size={14} /> : <RefreshCcw size={14} />}
              重试
            </button>
            <button className="btn-secondary compact" onClick={onRunWorkerOnce} disabled={!!loading}>
              {loading === "worker-once" ? <Loader2 className="animate-spin" size={14} /> : <Server size={14} />}
              Worker
            </button>
          </div>
          {job.status === "dead_lettered" && (
            <div className="inspection-alert">
              <History size={15} />
              <span>{job.dead_letter_reason || job.error || "Dead-lettered job requires manual review."}</span>
            </div>
          )}
          <div className="mini-stack">
            {job.events.slice(-4).map((event) => (
              <div key={`${event.at}-${event.stage_id}`} className="mini-line">
                <small>{event.progress}%</small>
                {event.message}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <p className="empty-copy">暂无运行任务</p>
      )}
      {queueStatus && (
        <div className="queue-summary">
          <span>broker {queueStatus.broker}</span>
          <span>depth {queueStatus.broker_depth}</span>
          <span>queued {queueStatus.queued}</span>
          <span>running {queueStatus.running}</span>
          <span>failed {queueStatus.failed}</span>
          <span>dead {queueStatus.dead_lettered}</span>
          <span>done {queueStatus.succeeded}</span>
        </div>
      )}
      {deadLetterQueue?.jobs.length ? (
        <div className="dead-letter-stack" aria-label="dead letter queue">
          {deadLetterQueue.jobs.slice(0, 4).map((item) => (
            <button
              key={item.id}
              className="dead-letter-row"
              type="button"
              onClick={() => onJobAction("retry", item.id)}
              disabled={!!loading}
              title={item.error || item.dead_letter_reason || item.id}
            >
              <span>{item.kind}</span>
              <strong>{item.status}</strong>
              <small>{item.attempts}/{item.max_attempts}</small>
              <small>{item.dead_letter_source || item.queue_mode}</small>
            </button>
          ))}
        </div>
      ) : (
        <p className="field-hint">Dead-letter queue: empty</p>
      )}
      {queueStatus?.broker_queue && <p className="field-hint">Broker queue: {queueStatus.broker_queue}</p>}
      {queueStatus?.broker_error && <p className="field-hint">Broker error: {queueStatus.broker_error}</p>}
      {queueStatus?.workers?.length ? (
        <div className="worker-stack" aria-label="worker runtime status">
          {queueStatus.workers.slice(0, 3).map((worker) => (
            <div key={worker.worker_id} className="worker-line">
              <span>{worker.worker_id}</span>
              <Badge tone={worker.status === "error" ? "error" : worker.status === "running" ? "warning" : "neutral"}>{worker.status}</Badge>
              <small>{worker.completed_jobs}/{worker.failed_jobs}</small>
              {worker.current_job_id && <small>{worker.current_job_id}</small>}
              {worker.last_error && <small>{worker.last_error}</small>}
            </div>
          ))}
        </div>
      ) : (
        <p className="field-hint">Worker status: no heartbeat yet</p>
      )}
      {queueStatus?.worker_hint && <p className="field-hint">{queueStatus.worker_hint}</p>}
    </section>
  );
}

function PipelineSnapshot({ stages }: { stages: PipelineStageReport[] }) {
  return (
    <section className="inspector-section">
      <h3>流水线</h3>
      <div className="pipeline-stack">
        {stages.length ? stages.map((stage) => <PipelineStage key={stage.id} stage={stage} compact />) : <p className="empty-copy">等待运行</p>}
      </div>
    </section>
  );
}

function PipelineStage({ stage, compact = false }: { stage: PipelineStageReport; compact?: boolean }) {
  return (
    <article className={compact ? "pipeline-stage compact" : "pipeline-stage"}>
      <div>
        <Badge tone={stage.status === "ok" ? "success" : stage.status === "warning" ? "warning" : "neutral"}>{stage.status}</Badge>
        <strong>{stage.name}</strong>
      </div>
      {!compact && <p>{stage.summary}</p>}
      <small>
        {stage.agent} / {stage.evidence_count} 证据 / {stage.output_count} 输出
      </small>
    </article>
  );
}

function ActivityPanel({ logs }: { logs: string[] }) {
  return (
    <section className="studio-panel wide">
      <h3>运行日志</h3>
      <div className="mini-stack">
        {logs.slice(0, 8).map((log, index) => (
          <div key={`${log}-${index}`} className="mini-line">
            {log}
          </div>
        ))}
      </div>
    </section>
  );
}

function MetricRow({ metric }: { metric: QualityMetric }) {
  return (
    <div className="metric-row">
      <div>
        <strong>{metric.name}</strong>
        <p>{metric.detail}</p>
      </div>
      <span>{metric.score}</span>
    </div>
  );
}

function MetricCard({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="metric-card">
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MetricPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-pill">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusChip({ label, value, tone }: { label: string; value: string; tone: "success" | "warning" | "error" | "neutral" | "accent" }) {
  return (
    <div className={`status-chip ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function jobTone(status: JobRecord["status"]) {
  if (status === "succeeded") return "success" as const;
  if (status === "failed" || status === "canceled") return "error" as const;
  return "warning" as const;
}

function EmptyPanel({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return (
    <div className="empty-panel">
      {icon}
      <strong>{title}</strong>
      <p>{text}</p>
    </div>
  );
}

function summarizeHealth(screenplay: Screenplay | null, validation: ValidationResult | null) {
  if (!screenplay) return { label: "等待运行", tone: "neutral" as const };
  if (validation && !validation.valid) return { label: "结构风险", tone: "error" as const };
  if (screenplay.quality_report.overall_score >= 80) return { label: "生产就绪", tone: "success" as const };
  return { label: "需要打磨", tone: "warning" as const };
}

function summarizeCoverage(screenplay: Screenplay | null) {
  if (!screenplay || !screenplay.scenes.length) return { label: "证据待生成", percent: 0, tone: "neutral" as const };
  const covered = screenplay.scenes.filter((scene) => scene.source_refs.length > 0).length;
  const percent = Math.round((covered / screenplay.scenes.length) * 100);
  if (percent >= 90) return { label: `证据 ${percent}%`, percent, tone: "success" as const };
  if (percent >= 60) return { label: `证据 ${percent}%`, percent, tone: "warning" as const };
  return { label: `证据 ${percent}%`, percent, tone: "error" as const };
}

function countParagraphs(chapters: Chapter[]) {
  return chapters.reduce((total, chapter) => total + chapter.paragraphs.length, 0);
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(2)} MB`;
}

function deriveSceneEvidence(screenplay: Screenplay, scene: Scene): SourceEvidence[] {
  const chapterById = new Map(screenplay.chapters.map((chapter) => [chapter.id, chapter]));
  const evidence: SourceEvidence[] = [];
  for (const sourceRef of scene.source_refs) {
    const chapter = chapterById.get(sourceRef.chapter_id);
    if (!chapter) continue;
    for (const paragraphId of sourceRef.paragraph_ids) {
      const paragraph = chapter.paragraphs.find((item) => item.id === paragraphId);
      if (!paragraph) continue;
      evidence.push({
        id: `${chapter.id}:${paragraph.id}`,
        chapter_id: chapter.id,
        chapter_title: chapter.title,
        paragraph_id: paragraph.id,
        paragraph_index: paragraph.index,
        text: paragraph.text,
        reason: "场景 source_refs",
        score: 100,
      });
    }
  }
  return evidence.slice(0, 8);
}

function resolveCharacterName(screenplay: Screenplay, characterId: string) {
  return screenplay.story_bible.characters.find((character) => character.id === characterId)?.name ?? characterId;
}

function resolveLocationName(screenplay: Screenplay, locationId: string) {
  return screenplay.story_bible.locations.find((location) => location.id === locationId)?.name ?? locationId;
}

function downloadText(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  saveBlob(filename, blob);
}

function saveBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function downloadDeliveryPackageAssets(packageRecord: ProjectDeliveryPackageRecord, assets: ProjectDeliveryPackageAsset[]) {
  for (const asset of assets) {
    if (!asset.content) continue;
    downloadText(asset.filename || `${packageRecord.id}.${asset.format}`, asset.content);
  }
}

async function downloadSignedDeliveryAsset(asset: ProjectDeliveryPackageAsset) {
  if (!asset.download_url) return;
  const response = await fetch(resolveApiUrl(asset.download_url));
  if (!response.ok) {
    throw new Error((await response.text()) || `HTTP ${response.status}`);
  }
  const buffer = await response.arrayBuffer();
  const actualSha256 = await sha256Hex(buffer);
  if (asset.sha256 && actualSha256 !== asset.sha256) {
    throw new Error("下载文件 sha256 与交付清单不一致。");
  }
  const blob = new Blob([buffer], { type: asset.content_type || "application/octet-stream" });
  saveBlob(asset.filename || `${asset.sha256.slice(0, 12)}.${asset.format}`, blob);
}

async function sha256Hex(buffer: ArrayBuffer) {
  const digest = await window.crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function formatDownloadExpiry(value?: string | null) {
  if (!value) return "临时链接 1 小时内有效";
  const expiresAt = new Date(value);
  if (Number.isNaN(expiresAt.getTime())) return "临时链接 1 小时内有效";
  const minutes = Math.max(0, Math.round((expiresAt.getTime() - Date.now()) / 60000));
  if (minutes <= 0) return "签名链接已过期，请刷新历史";
  if (minutes < 60) return `签名链接约 ${minutes} 分钟后过期`;
  return `签名链接约 ${Math.round(minutes / 60)} 小时内有效`;
}

function extractBlockedExport(error: unknown):
  | { export: ProjectExportRecord; readiness: ProjectReadinessResponse; audit_event: AuditEvent }
  | null {
  if (!(error instanceof Error)) return null;
  const detailPayload = (error as Error & { detail?: unknown }).detail;
  if (!detailPayload || typeof detailPayload !== "object" || !("detail" in detailPayload)) return null;
  const detail = (detailPayload as { detail?: unknown }).detail;
  if (!detail || typeof detail !== "object") return null;
  const candidate = detail as {
    export?: ProjectExportRecord;
    readiness?: ProjectReadinessResponse;
    audit_event?: AuditEvent;
  };
  if (!candidate.export || !candidate.readiness || !candidate.audit_event) return null;
  return {
    export: candidate.export,
    readiness: candidate.readiness,
    audit_event: candidate.audit_event,
  };
}

function extractBlockedApproval(error: unknown):
  | { approval: ProjectApprovalRecord; readiness: ProjectReadinessResponse; audit_event: AuditEvent }
  | null {
  if (!(error instanceof Error)) return null;
  const detailPayload = (error as Error & { detail?: unknown }).detail;
  if (!detailPayload || typeof detailPayload !== "object" || !("detail" in detailPayload)) return null;
  const detail = (detailPayload as { detail?: unknown }).detail;
  if (!detail || typeof detail !== "object") return null;
  const candidate = detail as {
    approval?: ProjectApprovalRecord;
    readiness?: ProjectReadinessResponse;
    audit_event?: AuditEvent;
  };
  if (!candidate.approval || !candidate.readiness || !candidate.audit_event) return null;
  return {
    approval: candidate.approval,
    readiness: candidate.readiness,
    audit_event: candidate.audit_event,
  };
}

function extractBlockedDeliveryPackage(error: unknown):
  | { package: ProjectDeliveryPackageRecord; readiness: ProjectReadinessResponse; audit_event: AuditEvent }
  | null {
  if (!(error instanceof Error)) return null;
  const detailPayload = (error as Error & { detail?: unknown }).detail;
  if (!detailPayload || typeof detailPayload !== "object" || !("detail" in detailPayload)) return null;
  const detail = (detailPayload as { detail?: unknown }).detail;
  if (!detail || typeof detail !== "object") return null;
  const candidate = detail as {
    package?: ProjectDeliveryPackageRecord;
    readiness?: ProjectReadinessResponse;
    audit_event?: AuditEvent;
  };
  if (!candidate.package || !candidate.readiness || !candidate.audit_event) return null;
  return {
    package: candidate.package,
    readiness: candidate.readiness,
    audit_event: candidate.audit_event,
  };
}

function normalizeError(error: unknown) {
  return error instanceof Error ? error.message : "操作失败";
}

function parseImportJobResult(job: JobRecord): ImportSourceResponse | null {
  const payload = job.result_payload;
  if (!payload || typeof payload.text !== "string" || typeof payload.filename !== "string") {
    return null;
  }
  return {
    title: typeof payload.title === "string" ? payload.title : "Imported source",
    text: payload.text,
    filename: payload.filename,
    content_type: typeof payload.content_type === "string" ? payload.content_type : "application/octet-stream",
    size_bytes: typeof payload.size_bytes === "number" ? payload.size_bytes : 0,
    sha256: typeof payload.sha256 === "string" ? payload.sha256 : "",
    detected_encoding: typeof payload.detected_encoding === "string" ? payload.detected_encoding : "unknown",
    extraction_method: typeof payload.extraction_method === "string" ? payload.extraction_method : "unknown",
    document_stats: typeof payload.document_stats === "object" && payload.document_stats !== null
      ? payload.document_stats as Record<string, number | string>
      : {},
    chapter_count: typeof payload.chapter_count === "number" ? payload.chapter_count : 0,
    paragraph_count: typeof payload.paragraph_count === "number" ? payload.paragraph_count : 0,
    warnings: Array.isArray(payload.warnings) ? payload.warnings.filter((item): item is string => typeof item === "string") : [],
    security_report: parseSecurityReport(payload.security_report),
  };
}

function parseSecurityReport(value: unknown): ImportSecurityReport {
  if (typeof value === "object" && value !== null) {
    const report = value as Record<string, unknown>;
    return {
      scanner: typeof report.scanner === "string" ? report.scanner : "local-static-import-scan-v1",
      verdict: parseSecurityVerdict(report.verdict),
      risk_level: parseRiskLevel(report.risk_level),
      sha256: typeof report.sha256 === "string" ? report.sha256 : "",
      extension: typeof report.extension === "string" ? report.extension : "",
      detected_file_type: typeof report.detected_file_type === "string" ? report.detected_file_type : "unknown",
      declared_content_type: typeof report.declared_content_type === "string" ? report.declared_content_type : "",
      checks: Array.isArray(report.checks) ? report.checks.filter((item): item is string => typeof item === "string") : [],
      warnings: Array.isArray(report.warnings) ? report.warnings.filter((item): item is string => typeof item === "string") : [],
      blocked_reasons: Array.isArray(report.blocked_reasons) ? report.blocked_reasons.filter((item): item is string => typeof item === "string") : [],
    };
  }
  return {
    scanner: "local-static-import-scan-v1",
    verdict: "warning" as const,
    risk_level: "medium" as const,
    sha256: "",
    extension: "",
    detected_file_type: "unknown",
    declared_content_type: "",
    checks: [],
    warnings: ["旧导入记录缺少安全扫描报告。"],
    blocked_reasons: [],
  };
}

function parseSecurityVerdict(value: unknown): ImportSecurityReport["verdict"] {
  return value === "clean" || value === "warning" || value === "blocked" ? value : "warning";
}

function parseRiskLevel(value: unknown): ImportSecurityReport["risk_level"] {
  return value === "low" || value === "medium" || value === "high" || value === "critical" ? value : "medium";
}

function securityTone(verdict: "clean" | "warning" | "blocked") {
  if (verdict === "clean") return "success";
  if (verdict === "blocked") return "error";
  return "warning";
}

function readinessTone(status: "ready" | "warning" | "blocked") {
  if (status === "ready") return "success";
  if (status === "blocked") return "error";
  return "warning";
}

function systemCheckStatus(checks: SystemReadinessCheck[], id: string) {
  const status = checks.find((check) => check.id === id)?.status;
  if (!status) return "-";
  if (status === "ready") return "ready";
  if (status === "blocked") return "blocked";
  return "warn";
}

function formatSystemEvidence(evidence: SystemReadinessCheck["evidence"]) {
  const pairs = Object.entries(evidence).slice(0, 3);
  if (!pairs.length) return "no evidence";
  return pairs.map(([key, value]) => `${key}: ${String(value)}`).join(" / ");
}

function approvalTone(status: ProjectApprovalRecord["status"]) {
  if (status === "approved") return "success";
  if (status === "rejected" || status === "blocked") return "error";
  if (status === "revoked") return "neutral";
  return "warning";
}

function approvalDecisionLabel(decision: ApprovalDecision) {
  if (decision === "approve") return "批准";
  if (decision === "reject") return "驳回";
  return "撤回";
}

function shortHash(value: string) {
  return value.length > 12 ? `${value.slice(0, 8)}...${value.slice(-4)}` : value;
}

function activeModelProfile(useLlm: boolean, profile: ModelProfileRuntime): ModelProfileRuntime | undefined {
  if (!useLlm || profile.provider === "fallback") return undefined;
  return {
    provider: profile.provider,
    base_url: profile.base_url,
    model: profile.model,
    api_key: profile.provider === "api" ? profile.api_key || undefined : undefined,
    api_key_secret_ref: profile.provider === "api" ? profile.api_key_secret_ref || undefined : undefined,
    temperature: profile.temperature,
  };
}

function publicModelProfile(useLlm: boolean, profile: ModelProfileRuntime): ProjectSettings["model_profile"] {
  if (!useLlm || profile.provider === "fallback") {
    return {
      provider: "fallback",
      base_url: "local://deterministic-fallback",
      model: "fallback",
      temperature: 0,
      has_api_key: false,
      api_key_secret_ref: null,
      source: "fallback",
    };
  }
  return {
    provider: profile.provider,
    base_url: profile.base_url,
    model: profile.model,
    temperature: profile.temperature,
    has_api_key: profile.provider === "api" && Boolean(profile.api_key || profile.api_key_secret_ref),
    api_key_secret_ref: profile.provider === "api" ? profile.api_key_secret_ref || null : null,
    source: "runtime",
  };
}

function resolveProjectActor(project: ProjectRecord, preferred: string) {
  const members = project.members ?? [];
  if (members.some((member) => member.name === preferred)) return preferred;
  return members.find((member) => member.role === "reviewer")?.name ?? members[0]?.name ?? preferred;
}

function displayTitle(value: string, fallback: string) {
  const cleaned = value.trim();
  if (!cleaned || /^[?\s]+$/.test(cleaned)) return fallback;
  return cleaned;
}
