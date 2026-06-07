'use client';

import React, { useState, useMemo } from 'react';
import {
  ChevronDown,
  ChevronRight,
  BookOpen,
  FileText,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { useProjectStore } from '@/store/project-store';
import { Chapter, Scene } from '@/lib/types';

export default function ChapterTree() {
  const { chapters, selectedChapterId, selectChapter, selectedSceneId, selectScene } =
    useProjectStore();
  const [expandedChapters, setExpandedChapters] = useState<Set<string>>(new Set());

  const toggleChapter = (chapterId: string) => {
    setExpandedChapters((prev) => {
      const next = new Set(prev);
      if (next.has(chapterId)) {
        next.delete(chapterId);
      } else {
        next.add(chapterId);
      }
      return next;
    });
  };

  if (chapters.length === 0) {
    return (
      <div className="text-center py-4" style={{ color: 'var(--color-muted)' }}>
        <FileText size={24} className="mb-2 mx-auto" style={{ color: 'var(--color-border)' }} />
        <p className="text-xs">暂无章节</p>
        <p className="text-xs">导入文本后将自动识别章节</p>
      </div>
    );
  }

  // Check if chapters are fewer than 3
  const chapterWarning = chapters.length < 3;

  return (
    <div className="space-y-1">
      {chapterWarning && (
        <div
          className="flex items-center gap-1 p-2 rounded text-xs mb-2"
          style={{
            backgroundColor: 'oklch(0.65 0.18 25 / 0.1)',
            color: 'var(--color-warning)',
          }}
        >
          <AlertTriangle size={14} />
          <span>不满足题目要求：章节少于3个</span>
        </div>
      )}

      {chapters.map((chapter) => (
        <ChapterItem
          key={chapter.id}
          chapter={chapter}
          isSelected={selectedChapterId === chapter.id}
          isExpanded={expandedChapters.has(chapter.id)}
          selectedSceneId={selectedSceneId}
          onSelect={() => selectChapter(chapter.id)}
          onToggle={() => toggleChapter(chapter.id)}
          onSelectScene={(sceneId) => selectScene(sceneId)}
        />
      ))}
    </div>
  );
}

interface ChapterItemProps {
  chapter: Chapter;
  isSelected: boolean;
  isExpanded: boolean;
  selectedSceneId: string | null;
  onSelect: () => void;
  onToggle: () => void;
  onSelectScene: (sceneId: string) => void;
}

function ChapterItem({
  chapter,
  isSelected,
  isExpanded,
  selectedSceneId,
  onSelect,
  onToggle,
  onSelectScene,
}: ChapterItemProps) {
  // Compute completion status for the chapter
  const chapterStatus = useMemo(() => {
    const scenesWithErrors = chapter.scenes.filter(
      (s) => s.validation_errors && s.validation_errors.length > 0
    );
    const scenesWithNoElements = chapter.scenes.filter(
      (s) => s.elements.length === 0
    );

    if (scenesWithErrors.length > 0) {
      return { status: 'warning', errorCount: scenesWithErrors.length };
    }
    if (scenesWithNoElements.length > 0) {
      return { status: 'partial', emptyCount: scenesWithNoElements.length };
    }
    return { status: 'complete' };
  }, [chapter.scenes]);

  const [isPreviewExpanded, setIsPreviewExpanded] = useState(false);
  const previewText = chapter.preview_text?.trim();
  const previewLimit = 120;
  const isPreviewLong = Boolean(previewText && previewText.length > previewLimit);
  const visiblePreview =
    previewText && !isPreviewExpanded && isPreviewLong
      ? `${previewText.slice(0, previewLimit)}...`
      : previewText;

  React.useEffect(() => {
    if (!isExpanded) {
      setIsPreviewExpanded(false);
    }
  }, [isExpanded]);

  return (
    <div>
      {/* Chapter header */}
      <div
        className={`flex items-center gap-1 px-2 py-1 rounded cursor-pointer transition-colors ${
          isSelected ? 'source-highlight' : ''
        }`}
        style={{
          color: isSelected ? 'var(--color-accent)' : 'var(--color-foreground)',
        }}
        onClick={() => {
          onSelect();
          onToggle();
        }}
      >
        {isExpanded ? (
          <ChevronDown size={14} style={{ color: 'var(--color-muted)' }} />
        ) : (
          <ChevronRight size={14} style={{ color: 'var(--color-muted)' }} />
        )}
        <BookOpen size={14} style={{ color: 'var(--color-teal)' }} />
        <span className="text-xs font-medium truncate flex-1">
          第{chapter.number}章 {chapter.title}
        </span>

        {/* Scene count badge - always visible */}
        <span
          className="text-xs shrink-0 px-1.5 py-0.5 rounded-full font-medium"
          style={{
            backgroundColor: 'oklch(0.55 0.12 200 / 0.12)',
            color: 'var(--color-teal)',
            minWidth: '2rem',
            textAlign: 'center',
          }}
        >
          {chapter.scenes.length}场
        </span>

        {/* Word count badge - more prominent */}
        <span
          className="text-xs shrink-0 px-1.5 py-0.5 rounded-full"
          style={{
            backgroundColor: 'oklch(0.55 0.08 260 / 0.08)',
            color: 'var(--color-accent)',
          }}
        >
          {chapter.word_count}字
        </span>

        {/* Completion status indicator */}
        {chapterStatus.status === 'complete' && (
          <CheckCircle2 size={14} style={{ color: 'oklch(0.65 0.18 140)' }} />
        )}
        {chapterStatus.status === 'warning' && (
          <span
            className="flex items-center gap-0.5 shrink-0 px-1.5 py-0.5 rounded-full text-xs font-medium"
            style={{
              backgroundColor: 'oklch(0.65 0.18 25 / 0.15)',
              color: 'var(--color-warning)',
            }}
          >
            <AlertCircle size={12} />
            {chapterStatus.errorCount}
          </span>
        )}
        {chapterStatus.status === 'partial' && (
          <AlertCircle size={14} style={{ color: 'var(--color-muted)' }} />
        )}
      </div>

      {/* Expanded content - with smooth animation */}
      <div
        className="transition-all duration-300 ease-in-out"
        style={{
          maxHeight: isExpanded ? 'none' : '0px',
          opacity: isExpanded ? 1 : 0,
          overflow: isExpanded ? 'visible' : 'hidden',
        }}
      >
        <div className="ml-4 mt-1 space-y-1">
          {/* Chapter stats */}
          <div className="text-xs px-2 py-1" style={{ color: 'var(--color-muted)' }}>
            {chapter.paragraph_count}段
          </div>

          {/* Preview text - compact by default, expandable for full reading. */}
          {previewText && (
            <div
              className="rounded px-2.5 py-2 text-xs transition-colors"
              style={{
                backgroundColor: 'var(--color-base)',
                border: '1px solid var(--color-border-subtle)',
                color: 'var(--color-muted)',
              }}
            >
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="font-medium" style={{ color: 'var(--color-label)' }}>
                  章节预览
                </span>
                {isPreviewLong && (
                  <button
                    type="button"
                    aria-expanded={isPreviewExpanded}
                    className="shrink-0 rounded px-1.5 py-0.5 text-xs transition-colors"
                    style={{
                      color: 'var(--color-accent)',
                      backgroundColor: 'oklch(0.75 0.15 75 / 0.10)',
                    }}
                    onClick={(event) => {
                      event.stopPropagation();
                      setIsPreviewExpanded((value) => !value);
                    }}
                  >
                    {isPreviewExpanded ? '收起' : '展开'}
                  </button>
                )}
              </div>
              <p className="whitespace-pre-wrap break-words leading-5">
                {visiblePreview}
              </p>
            </div>
          )}

          {/* Scenes list */}
          {chapter.scenes.map((scene) => (
            <SceneItem
              key={scene.id}
              scene={scene}
              isSelected={selectedSceneId === scene.id}
              onSelect={() => onSelectScene(scene.id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

interface SceneItemProps {
  scene: Scene;
  isSelected: boolean;
  onSelect: () => void;
}

function SceneItem({ scene, isSelected, onSelect }: SceneItemProps) {
  const hasErrors = scene.validation_errors && scene.validation_errors.length > 0;

  return (
    <div
      className={`flex items-center gap-1 px-2 py-1 rounded cursor-pointer text-xs transition-colors ${
        isSelected ? 'source-highlight' : ''
      }`}
      style={{
        color: isSelected ? 'var(--color-accent)' : 'var(--color-foreground)',
        borderLeft: hasErrors ? '2px solid var(--color-warning)' : undefined,
      }}
      onClick={onSelect}
    >
      <span className="truncate flex-1">
        {scene.heading.context} {scene.title || `场景${scene.order_in_chapter}`}
      </span>
      {hasErrors && (
        <AlertTriangle size={12} style={{ color: 'var(--color-warning)' }} />
      )}
      <span className="shrink-0" style={{ color: 'var(--color-muted)' }}>
        {scene.elements.length}元素
      </span>
    </div>
  );
}
