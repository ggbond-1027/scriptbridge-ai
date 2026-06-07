'use client';

import React from 'react';
import { useProjectStore } from '@/store/project-store';
import { SourceParagraph } from '@/lib/types';

export default function SourceViewer() {
  const {
    selectedChapterId,
    paragraphsCache,
    highlightedSourceRefs,
    selectedParagraphIndex,
    selectParagraph,
    selectedSceneId,
  } = useProjectStore();

  const paragraphs: SourceParagraph[] = selectedChapterId
    ? paragraphsCache[selectedChapterId] || []
    : [];

  // Find paragraphs that are referenced by the selected scene
  const { chapters, screenplay } = useProjectStore();
  const selectedChapter = chapters.find((ch) => ch.id === selectedChapterId);
  const selectedScene = selectedChapter?.scenes.find(
    (sc) => sc.id === selectedSceneId
  );

  // Get paragraph indices referenced by selected scene
  const referencedIndices = selectedScene?.source_refs
    ? new Set(selectedScene.source_refs.map((ref) => ref.paragraph_index))
    : new Set<number>();

  if (paragraphs.length === 0) {
    return (
      <div className="text-center py-4" style={{ color: 'var(--color-muted)' }}>
        <p className="text-xs">选择章节查看原文段落</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {paragraphs.map((paragraph, index) => {
        const isHighlighted = referencedIndices.has(index);
        const isSelected = selectedParagraphIndex === index;

        return (
          <div
            key={paragraph.id}
            className={`text-xs leading-relaxed rounded p-2 cursor-pointer transition-all ${
              isHighlighted ? 'source-highlight' : ''
            } ${isSelected ? 'source-highlight active' : ''}`}
            style={{
              backgroundColor: isSelected || isHighlighted
                ? undefined
                : 'var(--color-base)',
              color: isHighlighted || isSelected
                ? 'var(--color-foreground)'
                : 'var(--color-muted)',
            }}
            onClick={() => selectParagraph(index)}
          >
            {/* Paragraph index badge */}
            <span
              className="inline-block text-xs mr-1 rounded px-1"
              style={{
                backgroundColor: isHighlighted
                  ? 'oklch(0.75 0.15 75 / 0.2)'
                  : 'var(--color-surface)',
                color: isHighlighted
                  ? 'var(--color-accent)'
                  : 'var(--color-muted)',
              }}
            >
              {index}
            </span>

            {/* Dialogue hint */}
            {paragraph.is_dialogue_hint && (
              <span
                className="inline-block text-xs mr-1 badge badge-accent"
              >
                对话
              </span>
            )}

            {/* Paragraph text */}
            <span>{paragraph.text}</span>
          </div>
        );
      })}
    </div>
  );
}