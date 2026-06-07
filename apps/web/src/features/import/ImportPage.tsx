'use client';

import React, { useState, useEffect } from 'react';
import {
  FileText,
  Upload,
  BookOpen,
  Sparkles,
  ChevronRight,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Clock,
  FolderOpen,
  Trash2,
  Edit3,
  Eye,
  X,
  Users,
  Film,
} from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import { useRouter } from 'next/navigation';
import { projectApi } from '@/lib/api';
import { useProjectStore } from '@/store/project-store';
import { usePipelineStore } from '@/store/pipeline-store';
import {
  AdaptationStyle,
  DialogueStyle,
  CreateProjectRequest,
  Chapter,
  SampleNovel,
  PipelineStage,
  PIPELINE_STAGES,
  PIPELINE_STAGE_LABELS,
} from '@/lib/types';
import { showToast } from '@/components/Toast';

const ADAPTATION_STYLES: { value: AdaptationStyle; label: string; description: string }[] = [
  { value: 'short_series', label: '短剧', description: '每集3-5分钟，节奏紧凑，适合短视频平台' },
  { value: 'tv_series', label: '影视剧', description: '标准电视剧格式，每集45分钟' },
  { value: 'radio_drama', label: '广播剧', description: '纯声音叙事，侧重对白和音效描写' },
  { value: 'stage_play', label: '舞台剧', description: '舞台表演格式，侧重场面调度和台词' },
];

const DIALOGUE_STYLES: { value: DialogueStyle; label: string; description: string }[] = [
  { value: 'natural', label: '自然', description: '贴近日常对话，口语化表达' },
  { value: 'restrained', label: '克制', description: '克制内敛，适合严肃题材' },
  { value: 'internet', label: '网感', description: '网络流行语，适合年轻观众' },
  { value: 'dramatic', label: '戏剧化', description: '台词华丽，适合舞台表演' },
];

// Import flow steps
const IMPORT_STEPS = [
  { number: 1, label: '输入文本', description: '粘贴或上传小说原文' },
  { number: 2, label: '选择风格', description: '设定改编和对白风格' },
  { number: 3, label: '创建项目', description: '命名项目并开始AI改编' },
] as const;

// Estimated time for each pipeline stage (display purposes)
const ESTIMATED_STAGE_TIMES: Record<PipelineStage, string> = {
  chapter_identification: '约10秒',
  paragraph_numbering: '约5秒',
  chapter_understanding: '约30-60秒',
  story_bible_merge: '约15秒',
  scene_splitting: '约20秒',
  element_generation: '约30-90秒',
  schema_validation: '约5秒',
};

// Built-in sample novel
const SAMPLE_Novel: SampleNovel = {
  id: 'sample_001',
  title: '月光下的咖啡馆',
  author: '示例',
  description: '一段关于友谊和梦想的都市故事，包含3章6场景',
  text: `第一章 相遇

城市的夜晚总是喧嚣的，但在这家名叫"月光"的小咖啡馆里，时间仿佛慢了下来。

李晓推开那扇陈旧的木门时，门铃发出一声清脆的响声。她刚刚结束了一段令人疲惫的加班，肩膀酸痛，眼睛干涩。咖啡馆里只有三四个客人，都安静地坐在自己的角落。

"还是老样子？"老板王叔从柜台后抬头，微笑着问。

"嗯，一杯拿铁，少糖。"李晓在靠窗的位置坐下，那是她最喜欢的位置，可以看到街上匆匆而过的人群。

就在这时，一个陌生的身影走进了咖啡馆。他穿着一件洗得发白的蓝色衬衫，手里提着一个看起来很重的背包。他在门口犹豫了一会儿，最终选了李晓旁边的桌子坐下。

"你好，请问这里有插座吗？"他礼貌地问王叔。

"窗边那桌有。"王叔指了指李晓的方向。

年轻人朝李晓微微一笑，走过来坐在她对面。"打扰了，我叫陈远。"他伸出手。

李晓有些惊讶，但还是握了握他的手。"李晓。"

第二章 梦想

接下来的几天，陈远成了咖啡馆的常客。每次来，他都带着那台老旧的笔记本电脑，认真地敲打着键盘。李晓有时会好奇地瞥一眼他的屏幕，上面总是密密麻麻的文字。

"你在写什么？"有一天，她终于忍不住问。

"一个故事。"陈远抬起头，眼里闪着光，"关于一个想要改变世界的普通人。"

"听起来很浪漫。"李晓笑了笑。

"不，一点都不浪漫。"陈远摇了摇头，"改变世界的代价很大，故事里的人为此放弃了很多。"

李晓沉默了一会儿。她自己也有梦想——开一家自己的设计工作室，但那个梦想似乎总是离她很远。

"你呢？"陈远问，"你的梦想是什么？"

第三章 选择

一个月后，陈远的故事写完了。他把最后的稿件打印出来，放在桌上，看起来有些疲惫但很满足。

"我要去出版社了。"他告诉李晓。

"恭喜你。"李晓真心地说。

"但是……"陈远犹豫了一下，"出版社在北京，我需要离开这座城市。"

咖啡馆里又安静了下来，只有门铃偶尔发出的响声。李晓看着窗外，月光洒在街道上，把一切染成了银白色。

"那你的咖啡馆呢？"陈远问，他指的是李晓一直想开的那家。

"也许，我该也做个选择了。"李晓轻声说。

王叔在柜台后面静静地听着，他擦拭着一只咖啡杯，嘴角带着理解的微笑。月光咖啡馆，见证了许多故事，而这只是其中一个。

月色如水，故事未完。`,
  chapters: 3,
};

// Step indicator component for the import flow
function StepIndicator({ currentStep, completed }: { currentStep: number; completed: boolean }) {
  return (
    <div className="flex items-center justify-center gap-0 mb-6">
      {IMPORT_STEPS.map((step, index) => {
        const isActive = step.number === currentStep;
        const isCompleted = completed || step.number < currentStep;
        const isLast = index === IMPORT_STEPS.length - 1;

        return (
          <React.Fragment key={step.number}>
            {/* Step circle + label */}
            <div className="flex flex-col items-center" style={{ minWidth: '100px' }}>
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300"
                style={{
                  backgroundColor: isCompleted
                    ? 'var(--color-teal)'
                    : isActive
                      ? 'var(--color-accent)'
                      : 'var(--color-surface)',
                  color: isCompleted
                    ? 'white'
                    : isActive
                      ? 'white'
                      : 'var(--color-muted)',
                  border: !isCompleted && !isActive ? '2px solid var(--color-border)' : 'none',
                  boxShadow: isActive ? '0 0 12px oklch(0.7 0.15 250 / 0.4)' : 'none',
                }}
              >
                {isCompleted ? <CheckCircle2 size={16} /> : step.number}
              </div>
              <span
                className="text-xs font-semibold mt-1.5 text-center"
                style={{
                  color: isActive ? 'var(--color-accent)' : isCompleted ? 'var(--color-teal)' : 'var(--color-muted)',
                }}
              >
                {step.label}
              </span>
              <span
                className="text-xs text-center mt-0.5"
                style={{ color: 'var(--color-muted)', fontSize: '10px' }}
              >
                {step.description}
              </span>
            </div>

            {/* Connector line between steps */}
            {!isLast && (
              <div
                className="h-0.5 flex-1 mx-2 transition-all duration-300"
                style={{
                  backgroundColor: step.number < currentStep || completed
                    ? 'var(--color-teal)'
                    : 'var(--color-border)',
                  minWidth: '40px',
                  maxWidth: '80px',
                }}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// Mini pipeline progress display for the success state
function MiniPipelineProgress({ stages, overallProgress, isRunning, estimatedTimeRemaining }: {
  stages: any[];
  overallProgress: number;
  isRunning: boolean;
  estimatedTimeRemaining?: number;
}) {
  return (
    <div className="space-y-2">
      {/* Overall progress bar */}
      <div>
        <div className="flex items-center justify-between text-xs mb-1">
          <span style={{ color: 'var(--color-muted)' }}>总体进度</span>
          <span className="font-semibold" style={{ color: 'var(--color-foreground)' }}>{overallProgress}%</span>
        </div>
        <div
          className="w-full rounded-full overflow-hidden"
          style={{ height: '8px', backgroundColor: 'var(--color-border)' }}
        >
          <div
            className="rounded-full transition-all duration-700 ease-out"
            style={{
              width: `${overallProgress}%`,
              height: '8px',
              backgroundColor: 'var(--color-accent)',
            }}
          />
        </div>
      </div>

      {/* Stage list with estimated times */}
      <div className="space-y-1 mt-2">
        {PIPELINE_STAGES.map((stage) => {
          const stageStatus = stages.find((s: any) => s.stage === stage);
          const status = stageStatus?.status || 'pending';
          const progress = stageStatus?.progress || 0;

          return (
            <div key={stage} className="flex items-center gap-2">
              {/* Status icon */}
              <div className="shrink-0 w-4 h-4 flex items-center justify-center">
                {status === 'completed' && <CheckCircle2 size={12} style={{ color: 'var(--color-teal)' }} />}
                {status === 'running' && <Loader2 size={12} className="animate-spin" style={{ color: 'var(--color-accent)' }} />}
                {status === 'error' && <AlertCircle size={12} style={{ color: 'var(--color-warning)' }} />}
                {status === 'pending' && (
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: 'var(--color-border)' }}
                  />
                )}
              </div>

              {/* Stage name */}
              <span
                className="text-xs flex-1"
                style={{
                  color: status === 'running' ? 'var(--color-accent)' :
                    status === 'completed' ? 'var(--color-teal)' :
                    'var(--color-muted)',
                  fontWeight: status === 'running' ? 600 : 400,
                }}
              >
                {PIPELINE_STAGE_LABELS[stage]}
              </span>

              {/* Estimated time */}
              <span className="text-xs shrink-0" style={{ color: 'var(--color-muted)', fontSize: '10px' }}>
                <Clock size={10} className="inline mr-0.5" />
                {ESTIMATED_STAGE_TIMES[stage]}
              </span>

              {/* Mini progress for running stages */}
              {status === 'running' && (
                <div
                  className="w-16 rounded-full overflow-hidden shrink-0"
                  style={{ height: '3px', backgroundColor: 'var(--color-border)' }}
                >
                  <div
                    className="rounded-full transition-all duration-500"
                    style={{
                      width: `${progress}%`,
                      height: '3px',
                      backgroundColor: 'var(--color-accent)',
                    }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Estimated time remaining */}
      {isRunning && estimatedTimeRemaining && estimatedTimeRemaining > 0 && (
        <div className="flex items-center gap-1 mt-2 pt-2 border-t" style={{ borderColor: 'var(--color-border)' }}>
          <Clock size={12} style={{ color: 'var(--color-muted)' }} />
          <span className="text-xs" style={{ color: 'var(--color-muted)' }}>
            预估剩余时间: {Math.ceil(estimatedTimeRemaining / 60)}分钟
          </span>
        </div>
      )}
    </div>
  );
}

export default function ImportPage() {
  const [sourceText, setSourceText] = useState('');
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [adaptationStyle, setAdaptationStyle] = useState<AdaptationStyle>('short_series');
  const [dialogueStyle, setDialogueStyle] = useState<DialogueStyle>('natural');
  const [projectName, setProjectName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [showChapterPreview, setShowChapterPreview] = useState(false);
  const [previewChapters, setPreviewChapters] = useState<Chapter[]>([]);
  const [createdProjectId, setCreatedProjectId] = useState<string | null>(null);

  // History projects state
  const [historyProjects, setHistoryProjects] = useState<any[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [overviewProject, setOverviewProject] = useState<any | null>(null);
  const [showOverview, setShowOverview] = useState(false);

  const { loadProject } = useProjectStore();
  const { startPipeline, stages, overallProgress, isRunning, currentStage, pipelineStatus } = usePipelineStore();
  const router = useRouter();

  // Load history projects on mount
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const projects = await projectApi.list();
        setHistoryProjects(projects);
      } catch (err) {
        console.warn('加载历史项目失败:', err);
      } finally {
        setIsLoadingHistory(false);
      }
    };
    loadHistory();
  }, []);

  // Determine current step in the import flow
  const currentStep = createdProjectId
    ? 3 // all steps completed, pipeline running
    : (!sourceText && !uploadedFile)
      ? 1 // need text input
      : !projectName
        ? 2 // have text, need project name / style confirmation
        : 3; // ready to create

  // File drop zone
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
    },
    maxFiles: 1,
    onDrop: (files) => {
      if (files.length > 0) {
        setUploadedFile(files[0]);
        // Read file content for preview
        const reader = new FileReader();
        reader.onload = (e) => {
          const text = e.target?.result as string;
          setSourceText(text);
        };
        reader.readAsText(files[0]);
      }
    },
  });

  // Load sample novel
  const loadSample = () => {
    setSourceText(SAMPLE_Novel.text);
    setProjectName(SAMPLE_Novel.title);
    setUploadedFile(null);
    showToast.info('已加载示例小说《月光下的咖啡馆》');
  };

  // Detect chapters in text
  const detectChapters = (text: string): Chapter[] => {
    const chapterPattern = /^第[一二三四五六七八九十百千万零\d]+章\s+.+/gm;
    const matches = Array.from(text.matchAll(chapterPattern));

    if (matches.length === 0) {
      // If no chapter markers, treat entire text as one chapter
      return [{
        id: 'chap_preview_1',
        title: '全文',
        number: 1,
        paragraph_count: text.split('\n\n').length,
        word_count: text.length,
        scenes: [],
        preview_text: text.slice(0, 300),
      }];
    }

    const chapters: Chapter[] = [];
    for (let i = 0; i < matches.length; i++) {
      const startIdx = matches[i].index!;
      const endIdx = i + 1 < matches.length ? matches[i + 1].index! : text.length;
      const chapterText = text.slice(startIdx, endIdx).trim();
      const titleLine = chapterText.split('\n')[0];

      chapters.push({
        id: `chap_preview_${i + 1}`,
        title: titleLine.replace(/^第[一二三四五六七八九十百千万零\d]+章\s+/, ''),
        number: i + 1,
        paragraph_count: chapterText.split('\n\n').length,
        word_count: chapterText.length,
        scenes: [],
        preview_text: chapterText.slice(titleLine.length, titleLine.length + 300).trim(),
      });
    }

    return chapters;
  };

  // Preview chapters
  const handlePreview = () => {
    if (!sourceText) {
      showToast.warning('请先输入或上传文本');
      return;
    }
    const chapters = detectChapters(sourceText);
    setPreviewChapters(chapters);
    setShowChapterPreview(true);
  };

  // Create project
  const handleCreate = async () => {
    if (!sourceText && !uploadedFile) {
      showToast.warning('请先输入或上传文本');
      return;
    }
    if (!projectName) {
      showToast.warning('请输入项目名称');
      return;
    }

    setIsCreating(true);
    try {
      const request: CreateProjectRequest = {
        name: projectName,
        source_text: sourceText,
        source_file: uploadedFile || undefined,
        adaptation_style: adaptationStyle,
        dialogue_style: dialogueStyle,
      };

      const response = await projectApi.create(request);
      setCreatedProjectId(response.project_id);
      showToast.success(`项目 "${projectName}" 创建成功`);

      // Refresh history list
      try {
        const projects = await projectApi.list();
        setHistoryProjects(projects);
      } catch (_) {}

      // Load project and start pipeline
      await loadProject(response.project_id);
      await startPipeline(response.project_id);
    } catch (err) {
      showToast.error(`创建失败: ${err instanceof Error ? err.message : '未知错误'}`);
    } finally {
      setIsCreating(false);
    }
  };

  // View project overview
  const handleViewProject = async (projectId: string) => {
    try {
      const project = await projectApi.get(projectId);
      setOverviewProject(project);
      setShowOverview(true);
    } catch (err) {
      showToast.error('加载项目详情失败');
    }
  };

  // Go to editor
  const handleGoToEditor = async (projectId: string) => {
    await loadProject(projectId);
    router.push(`/editor?project=${projectId}`);
  };

  // Delete project
  const handleDeleteProject = async (projectId: string) => {
    try {
      await projectApi.delete(projectId);
      setHistoryProjects(prev => prev.filter(p => p.id !== projectId));
      showToast.success('项目已删除');
    } catch (err) {
      showToast.error('删除失败');
    }
  };

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6 animate-fade-in">
      {/* Title */}
      <div className="text-center mb-6">
        <h1 className="text-2xl font-bold" style={{ color: 'var(--color-foreground)' }}>
          NovelScripter
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--color-muted)' }}>
          AI小说转剧本工具 — 从文字到画面，一键改编
        </p>
      </div>

      {/* === History Projects Section === */}
      {!isLoadingHistory && (
        <div className="panel">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <FolderOpen size={16} style={{ color: 'var(--color-accent)' }} />
              <h2 className="text-sm font-semibold" style={{ color: 'var(--color-foreground)' }}>
                历史项目
              </h2>
            </div>
            {historyProjects.length > 0 && (
              <span className="badge badge-accent">
                {historyProjects.length} 个项目
              </span>
            )}
          </div>

          {historyProjects.length === 0 ? (
            <div className="text-center py-6" style={{ color: 'var(--color-muted)' }}>
              <FolderOpen size={32} className="mx-auto mb-2 opacity-40" />
              <p className="text-sm">暂无历史项目</p>
              <p className="text-xs mt-1">创建新项目后，下次访问即可在此查看和编辑</p>
            </div>
          ) : (
            <div className="space-y-2">
              {historyProjects.map((project) => (
                <div
                  key={project.id}
                  className="flex items-center gap-3 p-3 rounded transition-colors hover:bg-surfaceHover"
                  style={{ backgroundColor: 'var(--color-base)' }}
                >
                  {/* Project icon */}
                  <div
                    className="w-10 h-10 rounded flex items-center justify-center shrink-0"
                    style={{ backgroundColor: 'oklch(0.55 0.08 260 / 0.12)' }}
                  >
                    <Film size={18} style={{ color: 'var(--color-accent)' }} />
                  </div>

                  {/* Project info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold truncate" style={{ color: 'var(--color-foreground)' }}>
                        {project.name || project.title || '未命名项目'}
                      </span>
                      <span className="badge shrink-0" style={{
                        backgroundColor: project.status === 'completed' ? 'oklch(0.65 0.15 150 / 0.15)' : 'oklch(0.55 0.08 260 / 0.12)',
                        color: project.status === 'completed' ? 'var(--color-teal)' : 'var(--color-muted)',
                      }}>
                        {project.status === 'completed' ? '已完成' : project.status === 'editing' ? '编辑中' : project.status === 'failed' ? '失败' : '处理中'}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs" style={{ color: 'var(--color-muted)' }}>
                      {project.chapter_count && (
                        <span className="flex items-center gap-1">
                          <BookOpen size={10} />
                          {project.chapter_count} 章
                        </span>
                      )}
                      {project.scene_count && (
                        <span className="flex items-center gap-1">
                          <Film size={10} />
                          {project.scene_count} 场景
                        </span>
                      )}
                      {project.updated_at && (
                        <span className="flex items-center gap-1">
                          <Clock size={10} />
                          {new Date(project.updated_at).toLocaleDateString('zh-CN')}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Action buttons */}
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={(e) => { e.stopPropagation(); handleViewProject(project.id); }}
                      className="p-1.5 rounded transition-colors hover:bg-surfaceHover"
                      style={{ color: 'var(--color-accent)' }}
                      title="查看概览"
                    >
                      <Eye size={16} />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleGoToEditor(project.id); }}
                      className="p-1.5 rounded transition-colors hover:bg-surfaceHover"
                      style={{ color: 'var(--color-teal)' }}
                      title="进入编辑"
                    >
                      <Edit3 size={16} />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeleteProject(project.id); }}
                      className="p-1.5 rounded transition-colors hover:bg-surfaceHover"
                      style={{ color: 'var(--color-muted)' }}
                      title="删除项目"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Loading state for history */}
      {isLoadingHistory && (
        <div className="panel flex items-center justify-center py-4">
          <Loader2 size={16} className="animate-spin" style={{ color: 'var(--color-muted)' }} />
          <span className="text-xs ml-2" style={{ color: 'var(--color-muted)' }}>加载历史项目...</span>
        </div>
      )}

      {/* Step progress indicator */}
      <StepIndicator currentStep={currentStep} completed={!!createdProjectId} />

      {/* Step 3 partial: Project name */}
      <div className="panel">
        <div className="flex items-center gap-2 mb-2">
          <span
            className="inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold shrink-0"
            style={{
              backgroundColor: currentStep >= 3 ? 'var(--color-accent)' : 'var(--color-border)',
              color: currentStep >= 3 ? 'white' : 'var(--color-muted)',
            }}
          >
            3
          </span>
          <label className="text-xs font-semibold" style={{ color: 'var(--color-muted)' }}>
            创建项目 — 项目名称
          </label>
        </div>
        <input
          type="text"
          className="input-field text-sm"
          placeholder="为你的改编项目起个名字"
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
        />
      </div>

      {/* Step 1: Text input */}
      <div className="panel" style={{
        borderLeft: currentStep === 1 && !createdProjectId ? '3px solid var(--color-accent)' : undefined,
      }}>
        <div className="flex items-center gap-2 mb-2">
          <span
            className="inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold shrink-0"
            style={{
              backgroundColor: currentStep >= 1 ? 'var(--color-accent)' : 'var(--color-border)',
              color: currentStep >= 1 ? 'white' : 'var(--color-muted)',
            }}
          >
            1
          </span>
          <label className="text-xs font-semibold" style={{ color: 'var(--color-muted)' }}>
            输入文本 — 小说原文
          </label>
        </div>
        <textarea
          className="textarea-field text-sm"
          rows={12}
          placeholder="粘贴小说原文到这里，或上传文件..."
          value={sourceText}
          onChange={(e) => setSourceText(e.target.value)}
        />

        {/* Upload / Sample buttons */}
        <div className="flex items-center gap-2 mt-3">
          {/* Dropzone upload */}
          <div
            {...getRootProps()}
            className="btn-ghost flex items-center gap-1 text-sm cursor-pointer"
            style={{
              borderWidth: isDragActive ? '2px' : undefined,
              borderColor: isDragActive ? 'var(--color-accent)' : 'var(--color-border)',
            }}
          >
            <input {...getInputProps()} />
            <Upload size={14} />
            上传 txt/md
          </div>

          {/* Sample novel button */}
          <button
            onClick={loadSample}
            className="btn-ghost flex items-center gap-1 text-sm"
          >
            <Sparkles size={14} />
            内置样例
          </button>

          {/* Preview chapters button */}
          <button
            onClick={handlePreview}
            className="btn-ghost flex items-center gap-1 text-sm"
            disabled={!sourceText}
          >
            <FileText size={14} />
            预览章节
          </button>

          {uploadedFile && (
            <span className="badge badge-teal">
              {uploadedFile.name}
            </span>
          )}
        </div>
      </div>

      {/* Chapter preview */}
      {showChapterPreview && (
        <div className="panel animate-slide-in">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold" style={{ color: 'var(--color-accent)' }}>
              章节识别结果
            </h3>
            <span className="badge badge-accent">
              识别{previewChapters.length}章
            </span>
          </div>

          {/* Warning for fewer than 3 chapters */}
          {previewChapters.length < 3 && (
            <div
              className="flex items-center gap-2 p-3 rounded mb-3"
              style={{
                backgroundColor: 'oklch(0.65 0.18 25 / 0.1)',
                borderLeft: '3px solid var(--color-warning)',
              }}
            >
              <AlertTriangle size={16} style={{ color: 'var(--color-warning)' }} />
              <div>
                <p className="text-sm" style={{ color: 'var(--color-warning)' }}>
                  不满足题目要求
                </p>
                <p className="text-xs" style={{ color: 'var(--color-muted)' }}>
                  章节少于3个，建议补充章节标题或上传更完整的文本
                </p>
              </div>
            </div>
          )}

          {/* Chapter list */}
          <div className="space-y-2">
            {previewChapters.map((chapter) => (
              <ChapterPreviewItem key={chapter.id} chapter={chapter} />
            ))}
          </div>
        </div>
      )}

      {/* Step 2: Adaptation style selection */}
      <div className="panel" style={{
        borderLeft: currentStep === 2 && !createdProjectId ? '3px solid var(--color-accent)' : undefined,
      }}>
        <div className="flex items-center gap-2 mb-3">
          <span
            className="inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold shrink-0"
            style={{
              backgroundColor: currentStep >= 2 ? 'var(--color-accent)' : 'var(--color-border)',
              color: currentStep >= 2 ? 'white' : 'var(--color-muted)',
            }}
          >
            2
          </span>
          <label className="text-xs font-semibold" style={{ color: 'var(--color-muted)' }}>
            选择风格 — 改编风格
          </label>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {ADAPTATION_STYLES.map((style) => (
            <button
              key={style.value}
              onClick={() => setAdaptationStyle(style.value)}
              className={`panel flex items-center gap-2 cursor-pointer transition-all ${
                adaptationStyle === style.value ? 'ring-1' : ''
              }`}
              style={{
                borderColor: adaptationStyle === style.value ? 'var(--color-accent)' : 'var(--color-border)',
              }}
            >
              <BookOpen size={16} style={{
                color: adaptationStyle === style.value ? 'var(--color-accent)' : 'var(--color-muted)',
              }} />
              <div>
                <span className="font-semibold text-sm" style={{ color: 'var(--color-foreground)' }}>
                  {style.label}
                </span>
                <p className="text-xs" style={{ color: 'var(--color-muted)' }}>
                  {style.description}
                </p>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Step 2 continued: Dialogue style selection */}
      <div className="panel">
        <div className="flex items-center gap-2 mb-3">
          <span
            className="inline-flex items-center justify-center w-5 h-5 rounded-full text-xs font-bold shrink-0"
            style={{
              backgroundColor: currentStep >= 2 ? 'var(--color-accent)' : 'var(--color-border)',
              color: currentStep >= 2 ? 'white' : 'var(--color-muted)',
            }}
          >
            2
          </span>
          <label className="text-xs font-semibold" style={{ color: 'var(--color-muted)' }}>
            选择风格 — 对白风格
          </label>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {DIALOGUE_STYLES.map((style) => (
            <button
              key={style.value}
              onClick={() => setDialogueStyle(style.value)}
              className={`panel flex items-center gap-2 cursor-pointer transition-all ${
                dialogueStyle === style.value ? 'ring-1' : ''
              }`}
              style={{
                borderColor: dialogueStyle === style.value ? 'var(--color-accent)' : 'var(--color-border)',
              }}
            >
              <div>
                <span className="font-semibold text-sm" style={{ color: 'var(--color-foreground)' }}>
                  {style.label}
                </span>
                <p className="text-xs" style={{ color: 'var(--color-muted)' }}>
                  {style.description}
                </p>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Create button */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleCreate}
          disabled={isCreating || (!sourceText && !uploadedFile)}
          className="btn-accent flex-1 flex items-center justify-center gap-2 text-sm py-3"
        >
          {isCreating ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              创建项目并开始分析...
            </>
          ) : (
            <>
              <Sparkles size={16} />
              开始改编
            </>
          )}
        </button>
      </div>

      {/* Success state — Pipeline waiting state with mini PipelineStepper */}
      {createdProjectId && (
        <div
          className="panel animate-slide-in"
          style={{ borderLeft: '3px solid var(--color-accent)' }}
        >
          <div className="flex items-center gap-2 mb-3">
            {isRunning ? (
              <Loader2 size={16} className="animate-spin" style={{ color: 'var(--color-accent)' }} />
            ) : (
              <CheckCircle2 size={16} style={{ color: 'var(--color-teal)' }} />
            )}
            <span className="text-sm font-semibold" style={{
              color: isRunning ? 'var(--color-accent)' : 'var(--color-teal)',
            }}>
              {isRunning ? 'AI改编流水线正在执行...' : '改编完成'}
            </span>
            {isRunning && (
              <span className="badge badge-accent ml-auto">
                {overallProgress}%
              </span>
            )}
          </div>

          {/* Mini pipeline progress display */}
          <MiniPipelineProgress
            stages={stages}
            overallProgress={overallProgress}
            isRunning={isRunning}
            estimatedTimeRemaining={pipelineStatus?.estimated_time_remaining}
          />

          {/* Navigation buttons */}
          <div className="flex items-center gap-2 mt-3 pt-3 border-t" style={{ borderColor: 'var(--color-border)' }}>
            {!isRunning && (
              <button
                onClick={() => router.push(`/editor?project=${createdProjectId}`)}
                className="btn-accent flex-1 flex items-center justify-center gap-1 text-sm"
              >
                进入编辑器
                <ChevronRight size={14} />
              </button>
            )}
            {isRunning && (
              <button
                onClick={() => router.push(`/editor?project=${createdProjectId}`)}
                className="btn-ghost flex-1 flex items-center justify-center gap-1 text-sm"
              >
                在编辑器中查看进度
                <ChevronRight size={14} />
              </button>
            )}
          </div>
        </div>
      )}

      {/* === Project Overview Modal === */}
      {showOverview && overviewProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0"
            style={{ backgroundColor: 'oklch(0.10 0.02 260 / 0.8)' }}
            onClick={() => setShowOverview(false)}
          />
          <div
            className="relative panel z-10 w-full max-w-lg animate-slide-in"
            style={{ backgroundColor: 'var(--color-surface)' }}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold" style={{ color: 'var(--color-foreground)' }}>
                {overviewProject.name || overviewProject.title || '未命名项目'}
              </h3>
              <div className="flex items-center gap-2">
                <span className="badge" style={{
                  backgroundColor: overviewProject.status === 'completed' ? 'oklch(0.65 0.15 150 / 0.15)' : 'oklch(0.55 0.08 260 / 0.12)',
                  color: overviewProject.status === 'completed' ? 'var(--color-teal)' : 'var(--color-muted)',
                }}>
                  {overviewProject.status === 'completed' ? '已完成' : overviewProject.status === 'editing' ? '编辑中' : overviewProject.status === 'failed' ? '失败' : '处理中'}
                </span>
                <button onClick={() => setShowOverview(false)} style={{ color: 'var(--color-muted)' }}>
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="p-3 rounded text-center" style={{ backgroundColor: 'var(--color-base)' }}>
                <BookOpen size={20} style={{ color: 'var(--color-teal)' }} className="mx-auto mb-1" />
                <span className="text-lg font-bold" style={{ color: 'var(--color-foreground)' }}>
                  {overviewProject.chapter_count || 0}
                </span>
                <span className="text-xs block mt-0.5" style={{ color: 'var(--color-muted)' }}>章节</span>
              </div>
              <div className="p-3 rounded text-center" style={{ backgroundColor: 'var(--color-base)' }}>
                <Film size={20} style={{ color: 'var(--color-accent)' }} className="mx-auto mb-1" />
                <span className="text-lg font-bold" style={{ color: 'var(--color-foreground)' }}>
                  {overviewProject.scene_count || 0}
                </span>
                <span className="text-xs block mt-0.5" style={{ color: 'var(--color-muted)' }}>场景</span>
              </div>
              <div className="p-3 rounded text-center" style={{ backgroundColor: 'var(--color-base)' }}>
                <Users size={20} style={{ color: 'var(--color-accent)' }} className="mx-auto mb-1" />
                <span className="text-lg font-bold" style={{ color: 'var(--color-foreground)' }}>
                  {overviewProject.source_text_length || 0}
                </span>
                <span className="text-xs block mt-0.5" style={{ color: 'var(--color-muted)' }}>原文字数</span>
              </div>
            </div>

            {/* Project details */}
            <div className="space-y-2 mb-4">
              {overviewProject.description && (
                <div>
                  <span className="text-xs font-medium" style={{ color: 'var(--color-muted)' }}>描述</span>
                  <p className="text-sm mt-1" style={{ color: 'var(--color-foreground)' }}>{overviewProject.description}</p>
                </div>
              )}
              <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--color-muted)' }}>
                {overviewProject.adaptation_style && (
                  <span>改编风格: {overviewProject.adaptation_style}</span>
                )}
                {overviewProject.created_at && (
                  <span>创建: {new Date(overviewProject.created_at).toLocaleDateString('zh-CN')}</span>
                )}
                {overviewProject.updated_at && (
                  <span>更新: {new Date(overviewProject.updated_at).toLocaleDateString('zh-CN')}</span>
                )}
              </div>
            </div>

            {/* Pipeline status summary */}
            {overviewProject.pipeline_status && (
              <div className="mb-4">
                <span className="text-xs font-medium" style={{ color: 'var(--color-muted)' }}>Pipeline 阶段</span>
                <div className="flex items-center gap-2 mt-1">
                  {overviewProject.pipeline_status.stages?.map((stage: any) => (
                    <div
                      key={stage.stage}
                      className="w-6 h-6 rounded-full flex items-center justify-center"
                      style={{
                        backgroundColor: stage.status === 'completed' ? 'oklch(0.65 0.15 150 / 0.2)' :
                          stage.status === 'running' ? 'oklch(0.55 0.15 260 / 0.2)' :
                          stage.status === 'error' ? 'oklch(0.65 0.18 25 / 0.2)' :
                          'var(--color-surface)',
                        border: '2px solid ' + (
                          stage.status === 'completed' ? 'var(--color-teal)' :
                            stage.status === 'running' ? 'var(--color-accent)' :
                              stage.status === 'error' ? 'var(--color-warning)' :
                                'var(--color-border)'
                        ),
                      }}
                      title={PIPELINE_STAGE_LABELS[stage.stage as PipelineStage] + ': ' + stage.status}
                    >
                      {stage.status === 'completed' ? <CheckCircle2 size={10} style={{ color: 'var(--color-teal)' }} /> :
                        stage.status === 'running' ? <Loader2 size={10} className="animate-spin" style={{ color: 'var(--color-accent)' }} /> :
                          stage.status === 'error' ? <AlertCircle size={10} style={{ color: 'var(--color-warning)' }} /> :
                            null}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex items-center gap-3 pt-3 border-t" style={{ borderColor: 'var(--color-border)' }}>
              <button
                onClick={() => handleGoToEditor(overviewProject.id)}
                className="btn-accent flex-1 flex items-center justify-center gap-1 text-sm"
              >
                <Edit3 size={14} />
                进入编辑器
                <ChevronRight size={14} />
              </button>
              <button
                onClick={() => setShowOverview(false)}
                className="btn-ghost text-sm"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface ChapterPreviewItemProps {
  chapter: Chapter;
}

function ChapterPreviewItem({ chapter }: ChapterPreviewItemProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="rounded p-2 cursor-pointer"
      style={{ backgroundColor: 'var(--color-base)' }}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen size={14} style={{ color: 'var(--color-teal)' }} />
          <span className="text-sm font-medium" style={{ color: 'var(--color-foreground)' }}>
            第{chapter.number}章 {chapter.title}
          </span>
        </div>
        <span className="text-xs" style={{ color: 'var(--color-muted)' }}>
          {chapter.paragraph_count}段 | {chapter.word_count}字
        </span>
      </div>

      {expanded && chapter.preview_text && (
        <div
          className="mt-2 text-xs leading-relaxed p-2 rounded"
          style={{
            backgroundColor: 'var(--color-surface)',
            color: 'var(--color-muted)',
            maxHeight: '80px',
            overflow: 'auto',
          }}
        >
          {chapter.preview_text}
        </div>
      )}
    </div>
  );
}