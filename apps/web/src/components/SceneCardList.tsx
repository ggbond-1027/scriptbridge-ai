'use client';

import React from 'react';
import {
  MapPin,
  Clock,
  Users,
  Target,
  Swords,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
} from 'lucide-react';
import { useProjectStore } from '@/store/project-store';
import { Scene, ElementType } from '@/lib/types';
import { getElementTypeLabel } from '@/lib/fountain-render';

export default function SceneCardList() {
  const { chapters, selectedChapterId, selectedSceneId, selectScene } =
    useProjectStore();

  const selectedChapter = chapters.find((ch) => ch.id === selectedChapterId);
  const scenes = selectedChapter?.scenes || [];

  if (scenes.length === 0) {
    return (
      <div className="text-center py-8" style={{ color: 'var(--color-muted)' }}>
        <p className="text-sm">该章节暂无场景</p>
        <p className="text-xs mt-1">等待Pipeline完成场景拆分阶段</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {scenes.map((scene) => (
        <SceneCard
          key={scene.id}
          scene={scene}
          isSelected={selectedSceneId === scene.id}
          onSelect={() => selectScene(scene.id)}
          characters={getSceneCharacters(scene)}
        />
      ))}
    </div>
  );
}

interface SceneCardProps {
  scene: Scene;
  isSelected: boolean;
  onSelect: () => void;
  characters: string[];
}

function SceneCard({ scene, isSelected, onSelect, characters }: SceneCardProps) {
  const hasErrors = scene.validation_errors && scene.validation_errors.length > 0;
  const { storyBible } = useProjectStore();

  // Resolve location name
  const locationName = storyBible?.locations.find(
    (loc) => loc.id === scene.heading.location_id
  )?.name || scene.heading.location_id;

  // Resolve character names
  const characterNames = scene.characters.map((charId) => {
    const char = storyBible?.characters.find((c) => c.id === charId);
    return char?.name || charId;
  });

  return (
    <div
      className="panel cursor-pointer transition-all"
      style={{
        borderWidth: isSelected ? '2px' : undefined,
        borderColor: isSelected ? 'var(--color-accent)' : 'var(--color-border)',
      }}
      onClick={onSelect}
    >
      {/* Scene heading */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className="text-xs font-bold"
            style={{ color: 'var(--color-accent)' }}
          >
            场景{scene.order_in_chapter}
          </span>
          <span className="text-sm font-medium" style={{ color: 'var(--color-foreground)' }}>
            {scene.title}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {hasErrors ? (
            <AlertTriangle size={14} style={{ color: 'var(--color-warning)' }} />
          ) : (
            <CheckCircle2 size={14} style={{ color: 'var(--color-teal)' }} />
          )}
          <ChevronRight size={14} style={{ color: 'var(--color-muted)' }} />
        </div>
      </div>

      {/* Scene heading info */}
      <div className="flex items-center gap-2 mb-2 text-xs">
        <div className="flex items-center gap-1" style={{ color: 'var(--color-muted)' }}>
          <MapPin size={12} />
          <span>{scene.heading.context} {locationName}</span>
        </div>
        <div className="flex items-center gap-1" style={{ color: 'var(--color-muted)' }}>
          <Clock size={12} />
          <span>{scene.heading.time_of_day}</span>
        </div>
      </div>

      {/* Characters */}
      {characterNames.length > 0 && (
        <div className="flex items-center gap-1 mb-2 text-xs">
          <Users size={12} style={{ color: 'var(--color-teal)' }} />
          <span style={{ color: 'var(--color-muted)' }}>出场:</span>
          {characterNames.slice(0, 4).map((name) => (
            <span key={name} className="badge badge-teal">
              {name}
            </span>
          ))}
          {characterNames.length > 4 && (
            <span className="badge badge-muted">+{characterNames.length - 4}</span>
          )}
        </div>
      )}

      {/* Dramatic purpose */}
      {scene.dramatic_purpose && (
        <div className="flex items-start gap-1 mb-1 text-xs">
          <Target size={12} className="mt-0.5 shrink-0" style={{ color: 'var(--color-accent)' }} />
          <span style={{ color: 'var(--color-muted)' }}>
            <span className="font-medium" style={{ color: 'var(--color-accent-dim)' }}>戏剧目的: </span>
            {scene.dramatic_purpose}
          </span>
        </div>
      )}

      {/* Conflict */}
      {scene.conflict && (
        <div className="flex items-start gap-1 mb-1 text-xs">
          <Swords size={12} className="mt-0.5 shrink-0" style={{ color: 'var(--color-warning)' }} />
          <span style={{ color: 'var(--color-muted)' }}>
            <span className="font-medium" style={{ color: 'oklch(0.65 0.18 25)' }}>冲突: </span>
            {scene.conflict}
          </span>
        </div>
      )}

      {/* Element count summary */}
      <div className="flex items-center gap-2 mt-2 text-xs" style={{ color: 'var(--color-muted)' }}>
        {getElementCounts(scene.elements).map(({ type, count }) => (
          <span key={type}>
            {getElementTypeLabel(type)} {count}
          </span>
        ))}
      </div>

      {/* Validation errors */}
      {hasErrors && (
        <div className="mt-2 text-xs" style={{ color: 'var(--color-warning)' }}>
          {scene.validation_errors!.slice(0, 2).map((err, i) => (
            <div key={i} className="flex items-center gap-1">
              <AlertTriangle size={10} />
              <span>{err}</span>
            </div>
          ))}
          {scene.validation_errors!.length > 2 && (
            <span>+{scene.validation_errors!.length - 2}个错误</span>
          )}
        </div>
      )}
    </div>
  );
}

function getSceneCharacters(scene: Scene): string[] {
  return scene.characters;
}

function getElementCounts(elements: { type: ElementType }[]): { type: ElementType; count: number }[] {
  const counts: Record<ElementType, number> = {} as Record<ElementType, number>;
  for (const el of elements) {
    counts[el.type] = (counts[el.type] || 0) + 1;
  }
  return Object.entries(counts)
    .map(([type, count]) => ({ type: type as ElementType, count }))
    .sort((a, b) => b.count - a.count);
}