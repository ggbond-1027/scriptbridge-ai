/**
 * NovelScripter - Pipeline Store (Zustand)
 * Manages pipeline execution state and progress tracking
 */

import { create } from 'zustand';
import {
  PipelineStatus,
  PipelineStage,
  PipelineStageStatus,
  PIPELINE_STAGES,
} from '@/lib/types';
import { ApiError, pipelineApi } from '@/lib/api';
import { useModelStore } from '@/store/model-store';
import { useProjectStore } from '@/store/project-store';

interface PipelineState {
  /* === Core data === */
  pipelineStatus: PipelineStatus | null;
  currentStage: PipelineStage | null;
  stages: PipelineStageStatus[];
  overallProgress: number;

  /* === Execution state === */
  isRunning: boolean;
  isPolling: boolean;
  error: string | null;
  pollIntervalId: NodeJS.Timeout | null;

  /* === Actions === */
  startPipeline: (projectId: string) => Promise<void>;
  loadStatus: (projectId: string) => Promise<void>;
  cancelPipeline: (projectId: string) => Promise<void>;
  retryStage: (projectId: string, stage: PipelineStage) => Promise<void>;
  pollStatus: (projectId: string) => Promise<void>;
  startPolling: (projectId: string) => void;
  stopPolling: () => void;

  /* === Helpers === */
  getStageStatus: (stage: PipelineStage) => PipelineStageStatus | undefined;
  getStageResultSummary: (stage: PipelineStage) => string | null;
  isStageCompleted: (stage: PipelineStage) => boolean;
  isStageRunning: (stage: PipelineStage) => boolean;
  isStageError: (stage: PipelineStage) => boolean;
  getCompletedStagesCount: () => number;

  reset: () => void;
}

const initialStages: PipelineStageStatus[] = PIPELINE_STAGES.map((stage) => ({
  stage,
  status: 'pending',
  progress: 0,
}));

const initialState = {
  pipelineStatus: null,
  currentStage: null,
  stages: initialStages,
  overallProgress: 0,
  isRunning: false,
  isPolling: false,
  error: null,
  pollIntervalId: null as NodeJS.Timeout | null,
};

export const usePipelineStore = create<PipelineState>((set, get) => ({
  ...initialState,

  startPipeline: async (projectId: string) => {
    set({ isRunning: true, error: null });
    try {
      // Send model config along with pipeline start request
      const modelSettings = useModelStore.getState().settings;
      const modelConfig = {
        mode: modelSettings.mode,
        api_base_url: modelSettings.mode === 'api' ? modelSettings.api_base_url : '',
        api_key: modelSettings.mode === 'api' ? modelSettings.api_key : '',
        model_name: modelSettings.mode === 'api' ? modelSettings.model_name : '',
        temperature: modelSettings.temperature,
        max_tokens: modelSettings.max_tokens,
        local_base_url: modelSettings.mode === 'local' ? modelSettings.local_base_url : '',
        local_model_name: modelSettings.mode === 'local' ? modelSettings.local_model_name : '',
      };
      const status = await pipelineApi.start(projectId, modelConfig);
      set({
        pipelineStatus: status,
        currentStage: status.current_stage,
        stages: status.stages,
        overallProgress: status.overall_progress,
      });
      // Start polling for updates
      get().startPolling(projectId);
    } catch (err) {
      set({
        isRunning: false,
        error: err instanceof Error ? err.message : 'Failed to start pipeline',
      });
    }
  },

  loadStatus: async (projectId: string) => {
    try {
      const status = await pipelineApi.getStatus(projectId);
      const isRunning = status.stages.some((s) => s.status === 'running');
      const hasError = status.stages.some((s) => s.status === 'error');
      set({
        pipelineStatus: status,
        currentStage: status.current_stage,
        stages: status.stages,
        overallProgress: status.overall_progress,
        isRunning,
        error: hasError ? status.stages.find((s) => s.status === 'error')?.error_message || null : null,
      });
      if (isRunning) {
        get().startPolling(projectId);
      }
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to load pipeline status',
      });
    }
  },

  cancelPipeline: async (projectId: string) => {
    try {
      await pipelineApi.cancel(projectId);
      get().stopPolling();
      set({ isRunning: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to cancel pipeline',
      });
    }
  },

  retryStage: async (projectId: string, stage: PipelineStage) => {
    try {
      const status = await pipelineApi.retryStage(projectId, stage);
      set({
        pipelineStatus: status,
        currentStage: status.current_stage,
        stages: status.stages,
        overallProgress: status.overall_progress,
        isRunning: true,
      });
      get().startPolling(projectId);
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to retry stage',
      });
    }
  },

  pollStatus: async (projectId: string) => {
    try {
      const status = await pipelineApi.getStatus(projectId);
      set({
        pipelineStatus: status,
        currentStage: status.current_stage,
        stages: status.stages,
        overallProgress: status.overall_progress,
      });

      // Check if pipeline is completed or has errors
      const allCompleted = status.stages.every(
        (s) => s.status === 'completed' || s.status === 'error'
      );
      const hasError = status.stages.some((s) => s.status === 'error');

      if (allCompleted) {
        get().stopPolling();
        set({ isRunning: false });
        if (hasError) {
          const errorStage = status.stages.find((s) => s.status === 'error');
          set({
            error: errorStage?.error_message || 'Pipeline encountered errors',
          });
        }
        // Reload project data (chapters, story bible, etc.) after pipeline completes
        const projectId = status.project_id;
        if (projectId && !hasError) {
          const { loadProject } = useProjectStore.getState();
          loadProject(projectId);
        }
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        get().stopPolling();
        set({
          isRunning: false,
          error: '项目不存在或后端已重启，请重新导入小说后再开始改编',
        });
        return;
      }
      console.error('Failed to poll pipeline status:', err);
    }
  },

  startPolling: (projectId: string) => {
    // Stop existing polling
    get().stopPolling();

    const intervalId = setInterval(() => {
      get().pollStatus(projectId);
    }, 3000); // Poll every 3 seconds

    set({ isPolling: true, pollIntervalId: intervalId });
  },

  stopPolling: () => {
    const { pollIntervalId } = get();
    if (pollIntervalId) {
      clearInterval(pollIntervalId);
    }
    set({ isPolling: false, pollIntervalId: null });
  },

  getStageStatus: (stage: PipelineStage) => {
    return get().stages.find((s) => s.stage === stage);
  },

  getStageResultSummary: (stage: PipelineStage) => {
    const status = get().getStageStatus(stage);
    return status?.result_summary || null;
  },

  isStageCompleted: (stage: PipelineStage) => {
    const status = get().getStageStatus(stage);
    return status?.status === 'completed';
  },

  isStageRunning: (stage: PipelineStage) => {
    const status = get().getStageStatus(stage);
    return status?.status === 'running';
  },

  isStageError: (stage: PipelineStage) => {
    const status = get().getStageStatus(stage);
    return status?.status === 'error';
  },

  getCompletedStagesCount: () => {
    return get().stages.filter((s) => s.status === 'completed').length;
  },

  reset: () => {
    get().stopPolling();
    set(initialState);
  },
}));
