'use client';

import React from 'react';
import {
  Loader2,
  CheckCircle2,
  AlertTriangle,
  BookOpen,
  Users,
  MapPin,
  Clock,
} from 'lucide-react';
import { useProjectStore } from '@/store/project-store';
import { usePipelineStore } from '@/store/pipeline-store';
import PipelineStepper from '@/components/PipelineStepper';
import ProgressBar from '@/components/ProgressBar';
import StoryBibleTable from '@/components/StoryBibleTable';
import { PIPELINE_STAGES, PIPELINE_STAGE_LABELS } from '@/lib/types';

export default function OutlinePage() {
  const { project, screenplay, chapters, storyBible } = useProjectStore();
  const { isRunning, overallProgress, stages, isStageCompleted } = usePipelineStore();

  const bibleMergeCompleted = isStageCompleted('story_bible_merge');
  const sceneSplitCompleted = isStageCompleted('scene_splitting');

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6 animate-fade-in">
      {/* Header */}
      <div className="text-center mb-4">
        <h1 className="text-xl font-bold" style={{ color: 'var(--color-foreground)' }}>
          分析进度与审核
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--color-muted)' }}>
          Pipeline正在处理你的小说文本，完成后可审核故事圣经
        </p>
      </div>

      {/* Overall progress */}
      <div className="panel">
        <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-accent)' }}>
          总体进度
        </h3>
        <ProgressBar value={overallProgress} max={100} showLabel accent />
        <div className="mt-2">
          <PipelineStepper />
        </div>
      </div>

      {/* Pipeline results preview */}
      {stages.length > 0 && (
        <div className="panel">
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--color-accent)' }}>
            处理产物概览
          </h3>
          <div className="grid grid-cols-3 gap-3">
            {/* Chapters count */}
            <div className="text-center p-3 rounded" style={{ backgroundColor: 'var(--color-base)' }}>
              <BookOpen size={20} className="mb-1 mx-auto" style={{ color: 'var(--color-accent)' }} />
              <span className="text-lg font-bold" style={{ color: 'var(--color-foreground)' }}>
                {chapters.length}
              </span>
              <p className="text-xs" style={{ color: 'var(--color-muted)' }}>章</p>
            </div>

            {/* Characters count */}
            <div className="text-center p-3 rounded" style={{ backgroundColor: 'var(--color-base)' }}>
              <Users size={20} className="mb-1 mx-auto" style={{ color: 'var(--color-teal)' }} />
              <span className="text-lg font-bold" style={{ color: 'var(--color-foreground)' }}>
                {storyBible?.characters.length || 0}
              </span>
              <p className="text-xs" style={{ color: 'var(--color-muted)' }}>人物</p>
            </div>

            {/* Locations count */}
            <div className="text-center p-3 rounded" style={{ backgroundColor: 'var(--color-base)' }}>
              <MapPin size={20} className="mb-1 mx-auto" style={{ color: 'var(--color-teal)' }} />
              <span className="text-lg font-bold" style={{ color: 'var(--color-foreground)' }}>
                {storyBible?.locations.length || 0}
              </span>
              <p className="text-xs" style={{ color: 'var(--color-muted)' }}>地点</p>
            </div>
          </div>

          {/* Scene count */}
          {sceneSplitCompleted && (
            <div className="mt-2 text-center p-2 rounded" style={{ backgroundColor: 'var(--color-base)' }}>
              <span className="text-sm" style={{ color: 'var(--color-foreground)' }}>
                识别{chapters.reduce((sum, ch) => sum + ch.scenes.length, 0)}个候选场景
              </span>
            </div>
          )}
        </div>
      )}

      {/* Story Bible Review (only after merge completed) */}
      {bibleMergeCompleted && storyBible && (
        <div className="panel animate-slide-in">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-1" style={{ color: 'var(--color-accent)' }}>
            <BookOpen size={14} />
            故事圣经审核
          </h3>
          <p className="text-xs mb-3" style={{ color: 'var(--color-muted)' }}>
            请审核识别出的角色、地点和时间线。修改人物名称时系统会提示是否同步所有引用。
          </p>
          <StoryBibleTable />
        </div>
      )}

      {/* Waiting state */}
      {!bibleMergeCompleted && (
        <div className="panel text-center py-8">
          <Loader2 size={32} className="mb-3 mx-auto animate-spin" style={{ color: 'var(--color-accent)' }} />
          <p className="text-sm" style={{ color: 'var(--color-muted)' }}>
            正在执行分析Pipeline，请等待...
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--color-muted)' }}>
            故事圣经审核将在"故事圣经合并"阶段完成后可用
          </p>
        </div>
      )}
    </div>
  );
}