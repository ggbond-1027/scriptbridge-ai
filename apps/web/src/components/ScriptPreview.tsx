'use client';

import React, { useState, useMemo } from 'react';
import { BookOpen, FileText, AlertTriangle, Layers, MapPin } from 'lucide-react';
import { useProjectStore } from '@/store/project-store';
import { renderFountainToHtml, screenplayToFountain } from '@/lib/fountain-render';

type ChapterFilter = 'all' | string; // 'all' for showing all scenes, or a chapterId

export default function ScriptPreview() {
  const { chapters, screenplay, validationErrors, selectedChapterId, selectChapter, storyBible } = useProjectStore();
  const [activeFilter, setActiveFilter] = useState<ChapterFilter>('all');

  // Build a location name resolution map from storyBible
  const locationNames = useMemo(() => {
    if (!storyBible?.locations) return {};
    const map: Record<string, string> = {};
    for (const loc of storyBible.locations) {
      map[loc.id] = loc.name;
    }
    return map;
  }, [storyBible]);

  // Collect all scenes from all chapters
  const allScenes = useMemo(() => chapters.flatMap((ch) => ch.scenes), [chapters]);

  // Determine which scenes to display based on the active filter
  const filteredScenes = useMemo(() => {
    if (activeFilter === 'all') {
      return allScenes;
    }
    const chapter = chapters.find((ch) => ch.id === activeFilter);
    return chapter ? chapter.scenes : allScenes;
  }, [activeFilter, allScenes, chapters]);

  // Count info
  const totalChapterCount = chapters.length;
  const totalSceneCount = allScenes.length;
  const filteredSceneCount = filteredScenes.length;

  if (allScenes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full p-4" style={{ color: 'var(--color-muted)' }}>
        <div className="text-center">
          <BookOpen size={32} className="mb-3 mx-auto" style={{ color: 'var(--color-border)' }} />
          <p className="text-sm">暂无场景可预览</p>
          <p className="text-xs mt-1">等待Pipeline完成场景生成</p>
        </div>
      </div>
    );
  }

  // Generate Fountain format from filtered scenes, with location name resolution
  const fountainText = screenplayToFountain(
    filteredScenes,
    screenplay?.title || '未命名剧本',
    locationNames
  );

  // Render Fountain to HTML
  const renderedHtml = renderFountainToHtml(fountainText);

  // Validation warning
  const hasErrors = validationErrors.filter((e) => e.severity === 'error').length > 0;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold flex items-center gap-1" style={{ color: 'var(--color-accent)' }}>
            <BookOpen size={14} />
            剧本预览
          </h3>
          <div className="flex items-center gap-2 text-xs">
            <span className="flex items-center gap-1" style={{ color: 'var(--color-foreground)', fontWeight: 500 }}>
              <Layers size={10} />
              {totalChapterCount} 章
            </span>
            <span className="flex items-center gap-1" style={{ color: 'var(--color-foreground)', fontWeight: 500 }}>
              <MapPin size={10} />
              {filteredSceneCount} 场景
            </span>
            {hasErrors && (
              <div className="flex items-center gap-1" style={{ color: 'var(--color-warning)' }}>
                <AlertTriangle size={10} />
                <span>{validationErrors.filter((e) => e.severity === 'error').length}个错误</span>
              </div>
            )}
          </div>
        </div>

        {/* Format label */}
        <div className="flex items-center gap-1 mt-1 text-xs" style={{ color: 'var(--color-muted)' }}>
          <FileText size={10} />
          <span>Fountain格式渲染</span>
          {activeFilter !== 'all' && (
            <span style={{ color: 'var(--color-accent)' }}>
              — {chapters.find((ch) => ch.id === activeFilter)?.title || ''}
            </span>
          )}
        </div>
      </div>

      {/* Chapter navigation tabs */}
      <div
        className="flex items-center gap-1 px-3 py-1.5 border-b shrink-0 overflow-x-auto"
        style={{ borderColor: 'var(--color-border)' }}
      >
        {/* "全部" tab */}
        <button
          onClick={() => setActiveFilter('all')}
          className="px-2.5 py-1 text-xs rounded-md transition-colors whitespace-nowrap"
          style={{
            backgroundColor: activeFilter === 'all' ? 'var(--color-accent)' : 'var(--color-surface)',
            color: activeFilter === 'all' ? 'var(--color-base)' : 'var(--color-muted)',
            border: `1px solid ${activeFilter === 'all' ? 'var(--color-accent)' : 'var(--color-border)'}`,
            fontWeight: activeFilter === 'all' ? 600 : 400,
          }}
        >
          全部 ({totalSceneCount})
        </button>

        {/* "当前章节" tab - filters to the selectedChapterId from the store */}
        {selectedChapterId && (
          <button
            onClick={() => {
              setActiveFilter(selectedChapterId);
              // Also sync the store selection so the left panel highlights the same chapter
              selectChapter(selectedChapterId);
            }}
            className="px-2.5 py-1 text-xs rounded-md transition-colors whitespace-nowrap"
            style={{
              backgroundColor: activeFilter === selectedChapterId ? 'var(--color-accent)' : 'var(--color-surface)',
              color: activeFilter === selectedChapterId ? 'var(--color-base)' : 'var(--color-muted)',
              border: `1px solid ${activeFilter === selectedChapterId ? 'var(--color-accent)' : 'var(--color-border)'}`,
              fontWeight: activeFilter === selectedChapterId ? 600 : 400,
            }}
          >
            当前章节 ({chapters.find((ch) => ch.id === selectedChapterId)?.scenes.length ?? 0})
          </button>
        )}

        {/* Individual chapter tabs */}
        {chapters.map((ch) => (
          <button
            key={ch.id}
            onClick={() => {
              setActiveFilter(ch.id);
              selectChapter(ch.id);
            }}
            className="px-2.5 py-1 text-xs rounded-md transition-colors whitespace-nowrap"
            style={{
              backgroundColor: activeFilter === ch.id ? 'var(--color-accent)' : 'var(--color-surface)',
              color: activeFilter === ch.id ? 'var(--color-base)' : 'var(--color-muted)',
              border: `1px solid ${activeFilter === ch.id ? 'var(--color-accent)' : 'var(--color-border)'}`,
              fontWeight: activeFilter === ch.id ? 600 : 400,
            }}
          >
            第{ch.number}章 ({ch.scenes.length})
          </button>
        ))}
      </div>

      {/* Script content - Fountain rendered */}
      <div
        className="flex-1 overflow-auto p-6 font-script"
        style={{
          backgroundColor: 'var(--color-base)',
          color: 'var(--color-foreground)',
          lineHeight: '1.8',
        }}
      >
        <div dangerouslySetInnerHTML={{ __html: renderedHtml }} />
      </div>
    </div>
  );
}