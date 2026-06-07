'use client';

import React from 'react';
import {
  CheckCircle2,
  Loader2,
  AlertCircle,
  Circle,
  ChevronRight,
} from 'lucide-react';
import { usePipelineStore } from '@/store/pipeline-store';
import {
  PipelineStage,
  PIPELINE_STAGES,
  PIPELINE_STAGE_LABELS,
} from '@/lib/types';

export default function PipelineStepper() {
  const {
    stages,
    isRunning,
    overallProgress,
    currentStage,
    getStageResultSummary,
  } = usePipelineStore();

  return (
    <div className="space-y-1">
      {PIPELINE_STAGES.map((stage, index) => {
        const stageStatus = stages.find((s) => s.stage === stage);
        const status = stageStatus?.status || 'pending';
        const progress = stageStatus?.progress || 0;
        const resultSummary = getStageResultSummary(stage);
        const artifactsCount = stageStatus?.artifacts_count;
        const errorMessage = stageStatus?.error_message;
        const isCurrent = currentStage === stage;

        return (
          <div key={stage} className={`pipeline-step ${status}`}>
            {/* Status icon */}
            <div className="shrink-0 w-5 h-5 flex items-center justify-center">
              {status === 'completed' && (
                <CheckCircle2 size={16} style={{ color: 'var(--color-teal)' }} />
              )}
              {status === 'running' && (
                <Loader2
                  size={16}
                  className="animate-spin"
                  style={{ color: 'var(--color-accent)' }}
                />
              )}
              {status === 'error' && (
                <AlertCircle size={16} style={{ color: 'var(--color-warning)' }} />
              )}
              {status === 'pending' && (
                <Circle size={16} style={{ color: 'var(--color-border)' }} />
              )}
            </div>

            {/* Step content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1">
                <span className="text-xs font-medium truncate">
                  {PIPELINE_STAGE_LABELS[stage]}
                </span>
                {isCurrent && isRunning && (
                  <ChevronRight
                    size={12}
                    style={{ color: 'var(--color-accent)' }}
                  />
                )}
              </div>

              {/* Result summary - show actual artifact counts */}
              {resultSummary && (
                <p
                  className="text-xs truncate mt-0.5"
                  style={{ color: 'var(--color-muted)' }}
                >
                  {resultSummary}
                </p>
              )}
              {artifactsCount && !resultSummary && status === 'completed' && (
                <p
                  className="text-xs truncate mt-0.5"
                  style={{ color: 'var(--color-muted)' }}
                >
                  产物: {artifactsCount}项
                </p>
              )}
              {errorMessage && (
                <p
                  className="text-xs truncate mt-0.5"
                  style={{ color: 'var(--color-warning)' }}
                >
                  {errorMessage}
                </p>
              )}

              {/* Progress bar for running stage */}
              {status === 'running' && progress > 0 && (
                <div className="mt-1">
                  <ProgressBar value={progress} max={100} size="xs" />
                </div>
              )}
            </div>

            {/* Step number */}
            <span
              className="text-xs shrink-0"
              style={{ color: 'var(--color-border)' }}
            >
              {index + 1}
            </span>
          </div>
        );
      })}

      {/* Overall progress */}
      <div className="mt-2 pt-2 border-t" style={{ borderColor: 'var(--color-border-subtle)' }}>
        <div className="flex items-center justify-between text-xs mb-1">
          <span style={{ color: 'var(--color-muted)' }}>总体进度</span>
          <span style={{ color: 'var(--color-foreground)' }}>{overallProgress}%</span>
        </div>
        <ProgressBar value={overallProgress} max={100} size="sm" accent />
      </div>
    </div>
  );
}

/**
 * Inline ProgressBar component for PipelineStepper
 */
function ProgressBar({
  value,
  max,
  size = 'sm',
  accent = false,
}: {
  value: number;
  max: number;
  size?: 'xs' | 'sm' | 'md';
  accent?: boolean;
}) {
  const heights = { xs: '2px', sm: '4px', md: '8px' };
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  return (
    <div
      className="w-full rounded-full overflow-hidden"
      style={{
        height: heights[size],
        backgroundColor: 'var(--color-border)',
      }}
    >
      <div
        className="rounded-full transition-all duration-500"
        style={{
          width: `${percentage}%`,
          height: heights[size],
          backgroundColor: accent ? 'var(--color-accent)' : 'var(--color-teal)',
        }}
      />
    </div>
  );
}