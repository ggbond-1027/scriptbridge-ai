/**
 * NovelScripter - API Client
 * Fetch wrapper for backend API communication
 * Now supports frontend-direct model configuration via model-store
 */

import {
  ProjectInfo,
  CreateProjectRequest,
  CreateProjectResponse,
  PipelineStatus,
  Screenplay,
  StoryBible,
  ValidationError,
  RepairRequest,
  RepairResponse,
  ExportRequest,
  ExportResponse,
  ModelSettings as ModelSettingsType,
  Chapter,
  Scene,
  Element,
  Character,
  Location,
  SourceParagraph,
  DiffResult,
} from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body?: unknown
  ) {
    super(`API Error ${status}: ${statusText}`);
    this.name = 'ApiError';
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = await response.text();
    }
    throw new ApiError(response.status, response.statusText, body);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

async function uploadRequest<T>(
  path: string,
  formData: FormData
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;

  const response = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = await response.text();
    }
    throw new ApiError(response.status, response.statusText, body);
  }

  return response.json() as Promise<T>;
}

/**
 * Direct LLM API call — used when frontend connects directly to model
 * Bypasses the backend entirely; reads config from localStorage via model-store
 */
async function directLlmRequest<T>(
  path: string,
  body: unknown,
  customHeaders?: Record<string, string>,
  customBaseUrl?: string
): Promise<T> {
  const baseUrl = customBaseUrl || API_BASE_URL;
  const url = `${baseUrl}${path}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(customHeaders || {}),
  };

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    let errorBody: unknown;
    try {
      errorBody = await response.json();
    } catch {
      errorBody = await response.text();
    }
    throw new ApiError(response.status, response.statusText, errorBody);
  }

  return response.json() as Promise<T>;
}

/* === Project API === */

export const projectApi = {
  /** Create a new project from text or file */
  create: async (data: CreateProjectRequest): Promise<CreateProjectResponse> => {
    if (data.source_file) {
      const formData = new FormData();
      formData.append('name', data.name);
      formData.append('adaptation_style', data.adaptation_style);
      formData.append('dialogue_style', data.dialogue_style);
      if (data.source_text) formData.append('source_text', data.source_text);
      formData.append('source_file', data.source_file);
      return uploadRequest<CreateProjectResponse>('/api/v1/projects', formData);
    }
    return request<CreateProjectResponse>('/api/v1/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /** Get project info */
  get: async (projectId: string): Promise<ProjectInfo> => {
    return request<ProjectInfo>(`/api/v1/projects/${projectId}`);
  },

  /** List all projects */
  list: async (): Promise<any[]> => {
    const response = await request<any>('/api/v1/projects');
    // Backend returns ProjectListResponse { projects, total, page, page_size }
    return response.projects || response || [];
  },

  /** Delete a project */
  delete: async (projectId: string): Promise<void> => {
    return request<void>(`/api/v1/projects/${projectId}`, {
      method: 'DELETE',
    });
  },

  /** Update project name */
  updateName: async (projectId: string, name: string): Promise<ProjectInfo> => {
    return request<ProjectInfo>(`/api/v1/projects/${projectId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    });
  },
};

/* === Pipeline API === */

export const pipelineApi = {
  /** Get pipeline status */
  getStatus: async (projectId: string): Promise<PipelineStatus> => {
    return request<PipelineStatus>(`/api/v1/projects/${projectId}/pipeline/status`);
  },

  /** Start/resume pipeline execution — includes model config */
  start: async (projectId: string, modelConfig?: Record<string, unknown>): Promise<PipelineStatus> => {
    return request<PipelineStatus>(`/api/v1/projects/${projectId}/pipeline/start`, {
      method: 'POST',
      body: JSON.stringify(modelConfig || {}),
    });
  },

  /** Cancel pipeline execution */
  cancel: async (projectId: string): Promise<void> => {
    return request<void>(`/api/v1/projects/${projectId}/pipeline/cancel`, {
      method: 'POST',
    });
  },

  /** Retry a failed stage */
  retryStage: async (projectId: string, stage: string): Promise<PipelineStatus> => {
    return request<PipelineStatus>(
      `/api/v1/projects/${projectId}/pipeline/retry/${stage}`,
      { method: 'POST' }
    );
  },
};

/* === Screenplay API === */

export const screenplayApi = {
  /** Get full screenplay */
  get: async (projectId: string): Promise<Screenplay> => {
    return request<Screenplay>(`/api/v1/projects/${projectId}/screenplay`);
  },

  /** Update screenplay metadata */
  update: async (
    projectId: string,
    data: Partial<Pick<Screenplay, 'title' | 'adaptation_style' | 'dialogue_style'>>
  ): Promise<Screenplay> => {
    return request<Screenplay>(`/api/v1/projects/${projectId}/screenplay`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },
};

/* === Chapter API === */

export const chapterApi = {
  /** Get chapters list */
  list: async (projectId: string): Promise<Chapter[]> => {
    return request<Chapter[]>(`/api/v1/projects/${projectId}/chapters`);
  },

  /** Get single chapter with scenes */
  get: async (projectId: string, chapterId: string): Promise<Chapter> => {
    return request<Chapter>(`/api/v1/projects/${projectId}/chapters/${chapterId}`);
  },

  /** Update chapter title */
  updateTitle: async (
    projectId: string,
    chapterId: string,
    title: string
  ): Promise<Chapter> => {
    return request<Chapter>(
      `/api/v1/projects/${projectId}/chapters/${chapterId}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ title }),
      }
    );
  },
};

/* === Scene API === */

export const sceneApi = {
  /** Get scenes for a chapter */
  list: async (projectId: string, chapterId: string): Promise<Scene[]> => {
    return request<Scene[]>(
      `/api/v1/projects/${projectId}/chapters/${chapterId}/scenes`
    );
  },

  /** Get single scene */
  get: async (projectId: string, sceneId: string): Promise<Scene> => {
    return request<Scene>(`/api/v1/projects/${projectId}/scenes/${sceneId}`);
  },

  /** Update scene */
  update: async (
    projectId: string,
    sceneId: string,
    data: Partial<Scene>
  ): Promise<Scene> => {
    return request<Scene>(`/api/v1/projects/${projectId}/scenes/${sceneId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  /** Delete scene */
  delete: async (projectId: string, sceneId: string): Promise<void> => {
    return request<void>(`/api/v1/projects/${projectId}/scenes/${sceneId}`, {
      method: 'DELETE',
    });
  },

  /** AI rewrite a single element */
  rewriteElement: async (
    projectId: string,
    sceneId: string,
    elementId: string,
    instruction?: string
  ): Promise<Element> => {
    return request<Element>(
      `/api/v1/projects/${projectId}/scenes/${sceneId}/elements/${elementId}/rewrite`,
      {
        method: 'POST',
        body: JSON.stringify({ instruction }),
      }
    );
  },
};

/* === Story Bible API === */

export const storyBibleApi = {
  /** Get story bible */
  get: async (projectId: string): Promise<StoryBible> => {
    return request<StoryBible>(`/api/v1/projects/${projectId}/story-bible`);
  },

  /** Update character */
  updateCharacter: async (
    projectId: string,
    characterId: string,
    data: Partial<Character>
  ): Promise<Character> => {
    return request<Character>(
      `/api/v1/projects/${projectId}/story-bible/characters/${characterId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(data),
      }
    );
  },

  /** Merge duplicate characters */
  mergeCharacters: async (
    projectId: string,
    sourceIds: string[],
    targetId: string
  ): Promise<Character> => {
    return request<Character>(
      `/api/v1/projects/${projectId}/story-bible/characters/merge`,
      {
        method: 'POST',
        body: JSON.stringify({ source_ids: sourceIds, target_id: targetId }),
      }
    );
  },

  /** Update location */
  updateLocation: async (
    projectId: string,
    locationId: string,
    data: Partial<Location>
  ): Promise<Location> => {
    return request<Location>(
      `/api/v1/projects/${projectId}/story-bible/locations/${locationId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(data),
      }
    );
  },
};

/* === Source Paragraphs API === */

export const sourceApi = {
  /** Get paragraphs for a chapter */
  getParagraphs: async (
    projectId: string,
    chapterId: string
  ): Promise<SourceParagraph[]> => {
    return request<SourceParagraph[]>(
      `/api/v1/projects/${projectId}/chapters/${chapterId}/paragraphs`
    );
  },
};

/* === Validation API === */

export const validationApi = {
  /** Get validation errors */
  getErrors: async (projectId: string): Promise<ValidationError[]> => {
    return request<ValidationError[]>(
      `/api/v1/projects/${projectId}/validation/errors`
    );
  },

  /** Repair validation errors */
  repair: async (
    projectId: string,
    data: RepairRequest
  ): Promise<RepairResponse> => {
    return request<RepairResponse>(
      `/api/v1/projects/${projectId}/repair`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    );
  },
};

/* === Export API === */

export const exportApi = {
  /** Export screenplay */
  export: async (
    projectId: string,
    data: ExportRequest
  ): Promise<ExportResponse> => {
    return request<ExportResponse>(`/api/v1/projects/${projectId}/export`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /** Export project-independent schema documentation bundle */
  exportDocumentation: async (): Promise<ExportResponse> => {
    return request<ExportResponse>('/api/v1/projects/documentation/export', {
      method: 'POST',
      body: JSON.stringify({ format: 'docs' }),
    });
  },

  /** Get export download URL */
  getDownloadUrl: async (
    projectId: string,
    format: string
  ): Promise<string> => {
    return `${API_BASE_URL}/api/v1/projects/${projectId}/export/download?format=${format}`;
  },

  /** Get project-independent schema documentation download URL */
  getDocumentationDownloadUrl: async (): Promise<string> => {
    return `${API_BASE_URL}/api/v1/projects/documentation/export/download`;
  },
};

/* === Model Settings API === */
/* Now uses localStorage-persisted config via model-store instead of backend API */

/**
 * Get current model settings from localStorage (synced with model-store)
 * This is a sync operation — no API call needed
 * Safe for SSR: returns defaults if localStorage is unavailable
 */
export function getModelSettingsFromStorage(): ModelSettingsType {
  // SSR safety: localStorage is not available on server
  if (typeof window === 'undefined') {
    return {
      mode: 'api',
      api_provider: 'deepseek',
      api_key: '',
      api_base_url: 'https://api.deepseek.com/v1',
      model_name: 'deepseek-chat',
      local_engine: 'ollama',
      local_base_url: 'http://localhost:11434/v1',
      local_model_name: '',
      temperature: 0.7,
      max_tokens: 4000,
      connection_status: 'unknown',
    };
  }
  try {
    const stored = localStorage.getItem('novelscripter_model_settings');
    if (stored) {
      return JSON.parse(stored);
    }
  } catch (e) {
    console.error('Failed to read model settings from localStorage:', e);
  }
  return {
    mode: 'api',
    api_provider: 'deepseek',
    api_key: '',
    api_base_url: 'https://api.deepseek.com/v1',
    model_name: 'deepseek-chat',
    local_engine: 'ollama',
    local_base_url: 'http://localhost:11434/v1',
    local_model_name: '',
    temperature: 0.7,
    max_tokens: 4000,
    connection_status: 'unknown',
  };
}

export const modelApi = {
  /** Get model settings from localStorage */
  getSettings: async (projectId: string): Promise<ModelSettingsType> => {
    return getModelSettingsFromStorage();
  },

  /** Update model settings — saves to localStorage (frontend-only) */
  updateSettings: async (
    projectId: string,
    data: ModelSettingsType
  ): Promise<ModelSettingsType> => {
    try {
      localStorage.setItem('novelscripter_model_settings', JSON.stringify(data));
      return data;
    } catch (e) {
      throw new Error('Failed to save model settings to localStorage');
    }
  },

  /**
   * Send a direct LLM request using frontend-configured model
   * Used for pipeline operations when bypassing backend
   */
  directGenerate: async (
    prompt: string,
    modelConfig?: Partial<ModelSettingsType>
  ): Promise<unknown> => {
    const config = modelConfig || getModelSettingsFromStorage();
    const baseUrl = config.mode === 'api' ? config.api_base_url : config.local_base_url;
    const apiKey = config.mode === 'api' ? config.api_key : '';
    const modelName = config.mode === 'api' ? config.model_name : config.local_model_name;

    if (!baseUrl) {
      throw new Error('未配置 API 地址或本地服务地址');
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (apiKey) {
      if (config.api_provider === 'anthropic') {
        headers['x-api-key'] = apiKey;
        headers['anthropic-version'] = '2023-06-01';
      } else {
        headers['Authorization'] = `Bearer ${apiKey}`;
      }
    }

    const body = {
      model: modelName,
      messages: [{ role: 'user', content: prompt }],
      temperature: config.temperature,
      max_tokens: config.max_tokens,
    };

    return directLlmRequest('/chat/completions', body, headers, baseUrl);
  },
};

/* === Diff API === */

export const diffApi = {
  /** Get diff for a rewritten element */
  getElementDiff: async (
    projectId: string,
    elementId: string
  ): Promise<DiffResult> => {
    return request<DiffResult>(
      `/api/v1/projects/${projectId}/elements/${elementId}/diff`
    );
  },
};

export { ApiError };
