'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  BookOpen,
  Download,
  Settings,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  FileText,
  GitBranch,
  Cpu,
  Globe,
  GripHorizontal,
} from 'lucide-react';
import { useProjectStore } from '@/store/project-store';
import { usePipelineStore } from '@/store/pipeline-store';
import { useModelStore } from '@/store/model-store';
import PipelineStepper from './PipelineStepper';
import ChapterTree from './ChapterTree';
import SourceViewer from './SourceViewer';
import YamlEditor from './YamlEditor';
import ScriptPreview from './ScriptPreview';
import ModelSettings from './ModelSettings';
import ExportDialog from './ExportDialog';
import DocumentationPanel from './DocumentationPanel';
import Toast from './Toast';
import { RightPanelTab, API_PROVIDER_PRESETS, LOCAL_ENGINE_PRESETS } from '@/lib/types';

interface AppShellProps {
  children?: React.ReactNode;
}

type LeftPanelRatios = {
  progress: number;
  chapters: number;
  source: number;
};

type LeftPanelSectionKey = keyof LeftPanelRatios;

const LEFT_PANEL_LAYOUT_STORAGE_KEY = 'novelscripter_left_panel_layout_v1';
const DEFAULT_LEFT_PANEL_RATIOS: LeftPanelRatios = {
  progress: 30,
  chapters: 42,
  source: 28,
};
const LEFT_PANEL_SECTION_MIN_PX: Record<LeftPanelSectionKey, number> = {
  progress: 96,
  chapters: 96,
  source: 96,
};
const LEFT_PANEL_DIVIDER_HEIGHT = 10;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function normalizeLeftPanelRatios(ratios: LeftPanelRatios): LeftPanelRatios {
  const total = ratios.progress + ratios.chapters + ratios.source;
  if (!Number.isFinite(total) || total <= 0) {
    return DEFAULT_LEFT_PANEL_RATIOS;
  }
  return {
    progress: (ratios.progress / total) * 100,
    chapters: (ratios.chapters / total) * 100,
    source: (ratios.source / total) * 100,
  };
}

function readSavedLeftPanelRatios(): LeftPanelRatios {
  if (typeof window === 'undefined') return DEFAULT_LEFT_PANEL_RATIOS;
  try {
    const stored = window.localStorage.getItem(LEFT_PANEL_LAYOUT_STORAGE_KEY);
    if (!stored) return DEFAULT_LEFT_PANEL_RATIOS;
    const parsed = JSON.parse(stored) as Partial<LeftPanelRatios>;
    if (
      typeof parsed.progress === 'number' &&
      typeof parsed.chapters === 'number' &&
      typeof parsed.source === 'number'
    ) {
      return normalizeLeftPanelRatios({
        progress: parsed.progress,
        chapters: parsed.chapters,
        source: parsed.source,
      });
    }
  } catch {
    return DEFAULT_LEFT_PANEL_RATIOS;
  }
  return DEFAULT_LEFT_PANEL_RATIOS;
}

export default function AppShell({ children }: AppShellProps) {
  const {
    project,
    rightPanelTab,
    rightPanelCollapsed,
    saveStatus,
    setRightPanelTab,
    toggleRightPanel,
  } = useProjectStore();

  const { isRunning, overallProgress } = usePipelineStore();
  const modelSettings = useModelStore((s) => s.settings);
  const hydrate = useModelStore((s) => s.hydrate);
  const isHydrated = useModelStore((s) => s.hydrated);

  // Hydrate model settings from localStorage after client mount
  // This prevents SSR/client hydration mismatch
  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const [showModelSettings, setShowModelSettings] = useState(false);
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [leftPanelRatios, setLeftPanelRatios] = useState<LeftPanelRatios>(DEFAULT_LEFT_PANEL_RATIOS);
  const [leftPanelLayoutHydrated, setLeftPanelLayoutHydrated] = useState(false);
  const leftPanelSectionsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLeftPanelRatios(readSavedLeftPanelRatios());
    setLeftPanelLayoutHydrated(true);
  }, []);

  useEffect(() => {
    if (!leftPanelLayoutHydrated) return;
    window.localStorage.setItem(
      LEFT_PANEL_LAYOUT_STORAGE_KEY,
      JSON.stringify(leftPanelRatios)
    );
  }, [leftPanelLayoutHydrated, leftPanelRatios]);

  const getLeftPanelMinRatios = useCallback(() => {
    const container = leftPanelSectionsRef.current;
    if (!container) {
      return {
        progress: 12,
        chapters: 12,
        source: 14,
      };
    }

    const usableHeight = Math.max(
      container.getBoundingClientRect().height - LEFT_PANEL_DIVIDER_HEIGHT * 2,
      1
    );

    return {
      progress: (LEFT_PANEL_SECTION_MIN_PX.progress / usableHeight) * 100,
      chapters: (LEFT_PANEL_SECTION_MIN_PX.chapters / usableHeight) * 100,
      source: (LEFT_PANEL_SECTION_MIN_PX.source / usableHeight) * 100,
    };
  }, []);

  const resizeLeftPanel = useCallback((dividerIndex: 0 | 1, deltaPercent: number, startRatios: LeftPanelRatios) => {
    const minRatios = getLeftPanelMinRatios();
    const next = { ...startRatios };

    if (dividerIndex === 0) {
      const pairTotal = startRatios.progress + startRatios.chapters;
      next.progress = clamp(
        startRatios.progress + deltaPercent,
        minRatios.progress,
        pairTotal - minRatios.chapters
      );
      next.chapters = pairTotal - next.progress;
    } else {
      const pairTotal = startRatios.chapters + startRatios.source;
      next.chapters = clamp(
        startRatios.chapters + deltaPercent,
        minRatios.chapters,
        pairTotal - minRatios.source
      );
      next.source = pairTotal - next.chapters;
    }

    setLeftPanelRatios(normalizeLeftPanelRatios(next));
  }, [getLeftPanelMinRatios]);

  const handleLeftPanelDividerPointerDown = useCallback((dividerIndex: 0 | 1, event: React.PointerEvent<HTMLButtonElement>) => {
    const container = leftPanelSectionsRef.current;
    if (!container) return;

    event.preventDefault();
    const startY = event.clientY;
    const startRatios = leftPanelRatios;
    const usableHeight = Math.max(
      container.getBoundingClientRect().height - LEFT_PANEL_DIVIDER_HEIGHT * 2,
      1
    );

    document.body.classList.add('is-resizing-left-panel');

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const deltaPercent = ((moveEvent.clientY - startY) / usableHeight) * 100;
      resizeLeftPanel(dividerIndex, deltaPercent, startRatios);
    };

    const handlePointerUp = () => {
      document.body.classList.remove('is-resizing-left-panel');
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
  }, [leftPanelRatios, resizeLeftPanel]);

  const handleLeftPanelDividerKeyDown = useCallback((dividerIndex: 0 | 1, event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;

    event.preventDefault();
    const deltaPercent = event.key === 'ArrowDown' ? 4 : -4;
    resizeLeftPanel(dividerIndex, deltaPercent, leftPanelRatios);
  }, [leftPanelRatios, resizeLeftPanel]);

  const resetLeftPanelRatios = useCallback(() => {
    setLeftPanelRatios(DEFAULT_LEFT_PANEL_RATIOS);
  }, []);

  const rightPanelTabs: { id: RightPanelTab; label: string; icon: React.ReactNode }[] = [
    { id: 'yaml', label: 'YAML', icon: <FileText size={14} /> },
    { id: 'preview', label: '剧本预览', icon: <BookOpen size={14} /> },
    { id: 'docs', label: '说明文档', icon: <FileText size={14} /> },
    { id: 'logs', label: '生成日志', icon: <GitBranch size={14} /> },
  ];

  return (
    <div className="flex flex-col h-screen" style={{ backgroundColor: 'var(--color-base)' }}>
      {/* === Top Bar === */}
      <header
        className="flex items-center justify-between px-4 h-12 border-b shrink-0"
        style={{
          backgroundColor: 'var(--color-surface)',
          borderColor: 'var(--color-border)',
        }}
      >
        {/* Left: Project name */}
        <div className="flex items-center gap-3">
          <BookOpen size={18} style={{ color: 'var(--color-accent)' }} />
          <span className="font-semibold text-sm" style={{ color: 'var(--color-foreground)' }}>
            NovelScripter
          </span>
          {project && (
            <>
              <span style={{ color: 'var(--color-muted)' }}>|</span>
              <span className="text-sm" style={{ color: 'var(--color-foreground)' }}>
                {project.name}
              </span>
            </>
          )}
        </div>

        {/* Center: Pipeline status indicator */}
        <div className="flex items-center gap-2">
          {isRunning && (
            <div className="flex items-center gap-2 badge badge-accent">
              <Loader2 size={12} className="animate-spin" />
              <span className="text-xs">处理中 {overallProgress}%</span>
            </div>
          )}
          {!isRunning && overallProgress === 100 && (
            <div className="flex items-center gap-1 badge badge-teal">
              <CheckCircle2 size={12} />
              <span className="text-xs">已完成</span>
            </div>
          )}
        </div>

        {/* Right: Save status + Export + Gear Settings */}
        <div className="flex items-center gap-3">
          {/* Save status */}
          <div className="flex items-center gap-1 text-xs">
            {saveStatus === 'idle' && (
              <span style={{ color: 'var(--color-muted)' }}>未保存</span>
            )}
            {saveStatus === 'saving' && (
              <div className="flex items-center gap-1" style={{ color: 'var(--color-accent)' }}>
                <Loader2 size={12} className="animate-spin" />
                <span>保存中...</span>
              </div>
            )}
            {saveStatus === 'saved' && (
              <div className="flex items-center gap-1" style={{ color: 'var(--color-teal)' }}>
                <CheckCircle2 size={12} />
                <span>已保存</span>
              </div>
            )}
            {saveStatus === 'error' && (
              <div className="flex items-center gap-1" style={{ color: 'var(--color-warning)' }}>
                <AlertCircle size={12} />
                <span>保存失败</span>
              </div>
            )}
          </div>

          {/* Export button */}
          <button
            onClick={() => setShowExportDialog(true)}
            className="btn-ghost flex items-center gap-1 text-xs"
          >
            <Download size={14} />
            导出
          </button>

          {/* Gear Settings Button - prominent with hover spin animation */}
          <button
            onClick={() => setShowModelSettings(true)}
            className="group relative flex items-center gap-2 px-3 py-1.5 rounded-md border transition-all duration-200"
            style={{
              backgroundColor: modelSettings.connection_status === 'connected' ? 'oklch(0.55 0.12 150 / 0.12)' : 'var(--color-surface)',
              borderColor: modelSettings.connection_status === 'connected' ? 'var(--color-teal)' : modelSettings.connection_status === 'failed' ? 'var(--color-warning)' : 'var(--color-border)',
            }}
            title="模型配置"
          >
            {/* Connection status dot */}
            <span
              className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full border"
              style={{
                backgroundColor:
                  modelSettings.connection_status === 'connected' ? 'var(--color-teal)' :
                  modelSettings.connection_status === 'failed' ? 'var(--color-warning)' :
                  modelSettings.connection_status === 'testing' ? 'var(--color-accent)' :
                  'var(--color-muted)',
                borderColor: 'var(--color-base)',
              }}
            />
            {/* Gear icon with spin animation on hover */}
            <Settings
              size={16}
              className="transition-transform duration-500 group-hover:rotate-90"
              style={{
                color:
                  modelSettings.connection_status === 'connected' ? 'var(--color-teal)' :
                  modelSettings.connection_status === 'failed' ? 'var(--color-warning)' :
                  'var(--color-accent)',
              }}
            />
            {/* Current model indicator - only show dynamic content after hydration */}
            <span className="text-xs font-medium" style={{ color: 'var(--color-foreground)' }}>
              {isHydrated
                ? (modelSettings.mode === 'api'
                    ? (modelSettings.api_provider === 'custom'
                      ? modelSettings.model_name || '自定义'
                      : API_PROVIDER_PRESETS.find(p => p.provider === modelSettings.api_provider)?.label || modelSettings.api_provider)
                    : LOCAL_ENGINE_PRESETS.find(p => p.engine === modelSettings.local_engine)?.label || modelSettings.local_engine)
                : '模型配置'}
            </span>
            {/* Mode icon */}
            {isHydrated && (modelSettings.mode === 'api' ? <Globe size={12} style={{ color: 'var(--color-muted)' }} /> : <Cpu size={12} style={{ color: 'var(--color-muted)' }} />)}
          </button>
        </div>
      </header>

      {/* === Main Content Area === */}
      <div className="flex flex-1 overflow-hidden">
        {/* === Left Panel (240px) === */}
        <div
          className="flex flex-col border-r shrink-0 overflow-hidden"
          style={{
            width: '240px',
            backgroundColor: 'var(--color-surface)',
            borderColor: 'var(--color-border)',
          }}
        >
          {/* Import entry */}
          <div className="p-3 border-b" style={{ borderColor: 'var(--color-border-subtle)' }}>
            <button
              className="btn-accent w-full text-xs flex items-center justify-center gap-1"
              onClick={() => window.location.href = '/'}
            >
              <BookOpen size={14} />
              导入新文本
            </button>
          </div>

          <div ref={leftPanelSectionsRef} className="flex-1 min-h-0 flex flex-col overflow-hidden">
            <LeftSidebarSection title="处理进度" basisPercent={leftPanelRatios.progress}>
              <PipelineStepper />
            </LeftSidebarSection>

            <LeftPanelDivider
              index={0}
              onPointerDown={handleLeftPanelDividerPointerDown}
              onKeyDown={handleLeftPanelDividerKeyDown}
              onDoubleClick={resetLeftPanelRatios}
            />

            <LeftSidebarSection title="章节结构" basisPercent={leftPanelRatios.chapters}>
              <ChapterTree />
            </LeftSidebarSection>

            <LeftPanelDivider
              index={1}
              onPointerDown={handleLeftPanelDividerPointerDown}
              onKeyDown={handleLeftPanelDividerKeyDown}
              onDoubleClick={resetLeftPanelRatios}
            />

            <LeftSidebarSection title="原文段落" basisPercent={leftPanelRatios.source}>
              <SourceViewer />
            </LeftSidebarSection>
          </div>
        </div>

        {/* === Main Content (flex-1) === */}
        <main
          className="flex-1 overflow-auto p-4"
          style={{ backgroundColor: 'var(--color-base)' }}
        >
          {children || (
            <div
              className="flex items-center justify-center h-full"
              style={{ color: 'var(--color-muted)' }}
            >
              <div className="text-center">
                <BookOpen size={48} className="mb-4 mx-auto" style={{ color: 'var(--color-border)' }} />
                <p className="text-lg">导入小说文本开始改编</p>
                <p className="text-sm mt-2">支持粘贴文本、上传文件或使用内置样例</p>
              </div>
            </div>
          )}
        </main>

        {/* === Right Panel (320px, collapsible) === */}
        {!rightPanelCollapsed && (
          <div
            className="flex flex-col border-l shrink-0 overflow-hidden"
            style={{
              width: '320px',
              backgroundColor: 'var(--color-surface)',
              borderColor: 'var(--color-border)',
            }}
          >
            {/* Tab bar */}
            <div
              className="flex items-center border-b px-2 shrink-0 overflow-x-auto"
              style={{ borderColor: 'var(--color-border)' }}
            >
              {rightPanelTabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setRightPanelTab(tab.id)}
                  className={`tab-item flex shrink-0 items-center gap-1 text-xs ${
                    rightPanelTab === tab.id ? 'active' : ''
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
              <button
                onClick={toggleRightPanel}
                className="ml-auto p-1"
                style={{ color: 'var(--color-muted)' }}
              >
                <ChevronRight size={14} />
              </button>
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-auto">
              {rightPanelTab === 'yaml' && <YamlEditor />}
              {rightPanelTab === 'preview' && <ScriptPreview />}
              {rightPanelTab === 'docs' && <DocumentationPanel />}
              {rightPanelTab === 'logs' && (
                <GenerationLogsPanel />
              )}
            </div>
          </div>
        )}

        {/* Collapsed right panel toggle */}
        {rightPanelCollapsed && (
          <button
            onClick={toggleRightPanel}
            className="flex items-center justify-center border-l shrink-0 w-8 hover:bg-surfaceHover"
            style={{
              backgroundColor: 'var(--color-surface)',
              borderColor: 'var(--color-border)',
              color: 'var(--color-muted)',
            }}
          >
            <ChevronLeft size={14} />
          </button>
        )}
      </div>

      {/* === Modals === */}
      {showModelSettings && (
        <ModelSettings onClose={() => setShowModelSettings(false)} />
      )}
      {showExportDialog && (
        <ExportDialog onClose={() => setShowExportDialog(false)} />
      )}

      {/* === Toast Notifications === */}
      <Toast />
    </div>
  );
}

function LeftSidebarSection({
  title,
  basisPercent,
  children,
}: {
  title: string;
  basisPercent: number;
  children: React.ReactNode;
}) {
  return (
    <section
      className="min-h-0 overflow-hidden"
      style={{ flex: `0 1 ${basisPercent}%` }}
    >
      <div className="flex h-full min-h-0 flex-col p-3">
        <h3
          className="shrink-0 text-xs font-semibold mb-2"
          style={{ color: 'var(--color-muted)' }}
        >
          {title}
        </h3>
        <div className="min-h-0 flex-1 overflow-auto">
          {children}
        </div>
      </div>
    </section>
  );
}

function LeftPanelDivider({
  index,
  onPointerDown,
  onKeyDown,
  onDoubleClick,
}: {
  index: 0 | 1;
  onPointerDown: (index: 0 | 1, event: React.PointerEvent<HTMLButtonElement>) => void;
  onKeyDown: (index: 0 | 1, event: React.KeyboardEvent<HTMLButtonElement>) => void;
  onDoubleClick: () => void;
}) {
  return (
    <button
      type="button"
      className="left-panel-divider group flex h-2.5 shrink-0 items-center justify-center border-y"
      style={{
        borderColor: 'var(--color-border-subtle)',
        backgroundColor: 'var(--color-surface)',
      }}
      title="拖动调整区域高度"
      aria-label="拖动调整左侧区域高度"
      onPointerDown={(event) => onPointerDown(index, event)}
      onKeyDown={(event) => onKeyDown(index, event)}
      onDoubleClick={onDoubleClick}
    >
      <GripHorizontal
        size={14}
        className="opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100"
        style={{ color: 'var(--color-muted)' }}
      />
    </button>
  );
}

/**
 * Generation Logs Panel - Shows generation metadata and logs
 */
function GenerationLogsPanel() {
  const { screenplay } = useProjectStore();

  if (!screenplay) {
    return (
      <div className="p-4 text-center" style={{ color: 'var(--color-muted)' }}>
        <p className="text-sm">暂无生成日志</p>
      </div>
    );
  }

  const metadata = screenplay.metadata;

  return (
    <div className="p-4 space-y-3">
      <div className="panel">
        <h4 className="text-xs font-semibold mb-2" style={{ color: 'var(--color-accent)' }}>
          生成信息
        </h4>
        <div className="space-y-1 text-xs" style={{ color: 'var(--color-muted)' }}>
          <div className="flex justify-between">
            <span>模型</span>
            <span style={{ color: 'var(--color-foreground)' }}>{metadata.model_name}</span>
          </div>
          <div className="flex justify-between">
            <span>Prompt版本</span>
            <span style={{ color: 'var(--color-foreground)' }}>{metadata.prompt_version}</span>
          </div>
          <div className="flex justify-between">
            <span>生成耗时</span>
            <span style={{ color: 'var(--color-foreground)' }}>{metadata.generation_time_ms}ms</span>
          </div>
          {metadata.token_count && (
            <div className="flex justify-between">
              <span>Token数量</span>
              <span style={{ color: 'var(--color-foreground)' }}>{metadata.token_count}</span>
            </div>
          )}
          {metadata.cost_estimate && (
            <div className="flex justify-between">
              <span>预估成本</span>
              <span style={{ color: 'var(--color-foreground)' }}>${metadata.cost_estimate.toFixed(4)}</span>
            </div>
          )}
          <div className="flex justify-between">
            <span>生成时间</span>
            <span style={{ color: 'var(--color-foreground)' }}>
              {new Date(metadata.timestamp).toLocaleString('zh-CN')}
            </span>
          </div>
        </div>
      </div>

      <div className="panel">
        <h4 className="text-xs font-semibold mb-2" style={{ color: 'var(--color-accent)' }}>
          统计摘要
        </h4>
        <div className="space-y-1 text-xs" style={{ color: 'var(--color-muted)' }}>
          <div className="flex justify-between">
            <span>章节数</span>
            <span style={{ color: 'var(--color-foreground)' }}>{screenplay.chapters.length}</span>
          </div>
          <div className="flex justify-between">
            <span>场景总数</span>
            <span style={{ color: 'var(--color-foreground)' }}>
              {screenplay.chapters.reduce((sum, ch) => sum + ch.scenes.length, 0)}
            </span>
          </div>
          <div className="flex justify-between">
            <span>人物数</span>
            <span style={{ color: 'var(--color-foreground)' }}>{screenplay.story_bible.characters.length}</span>
          </div>
          <div className="flex justify-between">
            <span>地点数</span>
            <span style={{ color: 'var(--color-foreground)' }}>{screenplay.story_bible.locations.length}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
