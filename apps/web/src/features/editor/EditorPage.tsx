'use client';

import React, { useEffect } from 'react';
import { BookOpen, Loader2 } from 'lucide-react';
import { useProjectStore } from '@/store/project-store';
import { usePipelineStore } from '@/store/pipeline-store';
import { PIPELINE_STAGE_LABELS } from '@/lib/types';
import SceneCardList from '@/components/SceneCardList';
import SceneEditor from '@/components/SceneEditor';
import StoryBibleTable from '@/components/StoryBibleTable';

export default function EditorPage() {
  const {
    project,
    chapters,
    selectedChapterId,
    selectedSceneId,
    loadProject,
  } = useProjectStore();

  const {
    isRunning,
    overallProgress,
    currentStage,
    loadStatus,
  } = usePipelineStore();

  // Current stage label (for display in the progress bar)
  const currentStageLabel = currentStage
    ? PIPELINE_STAGE_LABELS[currentStage]
    : null;

  // Load project if not loaded
  useEffect(() => {
    const projectId = new URLSearchParams(window.location.search).get('project');
    if (!project && projectId) {
        loadProject(projectId);
    }
    if (projectId) {
      loadStatus(projectId);
    }
  }, [project, loadProject, loadStatus]);

  // Get selected chapter
  const selectedChapter = chapters.find((ch) => ch.id === selectedChapterId);
  const selectedScene = selectedChapter?.scenes.find(
    (sc) => sc.id === selectedSceneId
  );

  return (
    <div className="flex h-full overflow-hidden">
      {/* === Left Column: Source text with source_ref highlighting === */}
      <div
        className="flex flex-col border-r shrink-0 overflow-hidden"
        style={{
          width: '280px',
          backgroundColor: 'var(--color-surface)',
          borderColor: 'var(--color-border)',
        }}
      >
        <div className="p-3 border-b shrink-0" style={{ borderColor: 'var(--color-border-subtle)' }}>
          <h3 className="text-xs font-semibold" style={{ color: 'var(--color-muted)' }}>
            原稿对照
          </h3>
          <p className="text-xs" style={{ color: 'var(--color-muted)' }}>
            点击段落追踪对应场景
          </p>
        </div>
        <div className="flex-1 overflow-auto p-3">
          <SourceViewerWithHighlight />
        </div>
      </div>

      {/* === Middle Column: Scene cards + Scene editor === */}
      <div
        className="flex-1 flex flex-col overflow-hidden"
        style={{ backgroundColor: 'var(--color-base)' }}
      >
        {/* Pipeline progress bar - shown when pipeline is running */}
        {isRunning && (
          <div
            className="shrink-0"
            style={{ backgroundColor: 'var(--color-surface)', borderBottom: '1px solid var(--color-border)' }}
          >
            <div className="flex items-center gap-2 px-3 py-1.5">
              <Loader2
                size={14}
                className="animate-spin shrink-0"
                style={{ color: 'var(--color-accent)' }}
              />
              <span className="text-xs font-medium" style={{ color: 'var(--color-foreground)' }}>
                {currentStageLabel ?? '处理中'}
              </span>
              <span className="text-xs" style={{ color: 'var(--color-muted)' }}>
                {overallProgress}%
              </span>
            </div>
            {/* Thin progress bar spanning full width */}
            <div
              className="w-full overflow-hidden"
              style={{
                height: '2px',
                backgroundColor: 'var(--color-border)',
              }}
            >
              <div
                className="transition-all duration-500"
                style={{
                  width: `${overallProgress}%`,
                  height: '2px',
                  backgroundColor: 'var(--color-accent)',
                }}
              />
            </div>
          </div>
        )}

        <div className="p-3 border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold" style={{ color: 'var(--color-foreground)' }}>
              改编工作台
            </h3>
            {selectedChapter && (
              <span className="badge badge-accent">
                第{selectedChapter.number}章
              </span>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-auto p-4">
          {!selectedChapter ? (
            <div className="flex items-center justify-center h-full" style={{ color: 'var(--color-muted)' }}>
              <div className="text-center">
                <BookOpen size={48} className="mb-4 mx-auto" style={{ color: 'var(--color-border)' }} />
                <p>选择一个章节开始编辑</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Scene cards */}
              <SceneCardList />

              {/* Scene editor (if a scene is selected) */}
              {selectedScene && (
                <div className="mt-4 animate-slide-in">
                  <SceneEditor />
                </div>
              )}

              {/* Story bible (always available below) */}
              <div className="mt-6">
                <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-accent)' }}>
                  故事圣经
                </h3>
                <StoryBibleTable />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Source viewer with enhanced highlighting for the editor page.
 * Clicking a paragraph on the left scrolls the right panel to the corresponding scene.
 */
function SourceViewerWithHighlight() {
  const {
    selectedChapterId,
    paragraphsCache,
    selectedSceneId,
    chapters,
    selectParagraph,
  } = useProjectStore();

  const paragraphs = selectedChapterId
    ? paragraphsCache[selectedChapterId] || []
    : [];

  const selectedChapter = chapters.find((ch) => ch.id === selectedChapterId);
  const selectedScene = selectedChapter?.scenes.find(
    (sc) => sc.id === selectedSceneId
  );

  // Find paragraph indices referenced by selected scene
  const referencedIndices = selectedScene?.source_refs
    ? new Set(selectedScene.source_refs.map((ref) => ref.paragraph_index))
    : new Set<number>();

  if (paragraphs.length === 0) {
    return (
      <div className="text-center py-4" style={{ color: 'var(--color-muted)' }}>
        <p className="text-xs">选择章节查看原文</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {paragraphs.map((paragraph, index) => {
        const isHighlighted = referencedIndices.has(index);

        return (
          <div
            key={paragraph.id}
            className={`text-xs leading-relaxed rounded p-1.5 cursor-pointer transition-all ${
              isHighlighted ? 'source-highlight' : ''
            }`}
            style={{
              backgroundColor: isHighlighted ? undefined : 'transparent',
              color: isHighlighted ? 'var(--color-foreground)' : 'var(--color-muted)',
            }}
            onClick={() => selectParagraph(index)}
          >
            <span
              className="inline-block text-xs mr-0.5"
              style={{
                color: isHighlighted ? 'var(--color-accent)' : 'var(--color-border)',
              }}
            >
              {index}
            </span>
            {paragraph.text}
          </div>
        );
      })}
    </div>
  );
}
