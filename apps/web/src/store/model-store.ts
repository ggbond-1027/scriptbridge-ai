/**
 * NovelScripter - Model Settings Store (Zustand)
 * Manages LLM model configuration with localStorage persistence
 * Uses deferred hydration to avoid SSR/client mismatch
 */

import { create } from 'zustand';
import {
  ModelSettings,
  ApiProvider,
  LocalEngine,
  API_PROVIDER_PRESETS,
  LOCAL_ENGINE_PRESETS,
} from '@/lib/types';

const STORAGE_KEY = 'novelscripter_model_settings';

function getDefaultSettings(): ModelSettings {
  return {
    mode: 'api',
    api_provider: 'deepseek',
    api_key: '',
    api_base_url: API_PROVIDER_PRESETS.find(p => p.provider === 'deepseek')!.defaultBaseUrl,
    model_name: API_PROVIDER_PRESETS.find(p => p.provider === 'deepseek')!.defaultModel,
    local_engine: 'ollama',
    local_base_url: LOCAL_ENGINE_PRESETS.find(p => p.engine === 'ollama')!.defaultBaseUrl,
    local_model_name: '',
    temperature: 0.7,
    max_tokens: 4000,
    connection_status: 'unknown',
    connection_error: undefined,
  };
}

function readFromStorage(): ModelSettings | null {
  if (typeof window === 'undefined') return null; // SSR safety
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      // Merge with defaults to ensure new fields exist
      return { ...getDefaultSettings(), ...parsed, connection_status: 'unknown', connection_error: undefined };
    }
  } catch (e) {
    console.error('Failed to load model settings from localStorage:', e);
  }
  return null;
}

function saveToStorage(settings: ModelSettings): void {
  if (typeof window === 'undefined') return; // SSR safety
  try {
    // Don't persist connection_status/error — they're ephemeral
    const toSave = { ...settings, connection_status: 'unknown', connection_error: undefined };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave));
  } catch (e) {
    console.error('Failed to save model settings to localStorage:', e);
  }
}

interface ModelStoreState {
  settings: ModelSettings;
  isConfigured: boolean;
  hydrated: boolean; // Whether localStorage data has been loaded

  /* === Actions === */
  hydrate: () => void; // Load from localStorage after client mount
  updateSettings: (partial: Partial<ModelSettings>) => void;
  setProvider: (provider: ApiProvider) => void;
  setLocalEngine: (engine: LocalEngine) => void;
  testConnection: () => Promise<void>;
  resetToDefaults: () => void;

  /* === Helpers === */
  getEffectiveBaseUrl: () => string;
  getEffectiveApiKey: () => string;
  getEffectiveModelName: () => string;
  getApiHeaders: () => Record<string, string>;
}

// Always initialize with defaults — no localStorage read at creation time
// This ensures SSR and client initial render produce identical HTML
const DEFAULTS = getDefaultSettings();

export const useModelStore = create<ModelStoreState>((set, get) => ({
  settings: DEFAULTS,
  isConfigured: false,
  hydrated: false,

  // Call this after client mount (useEffect) to load saved settings from localStorage
  hydrate: () => {
    if (get().hydrated) return; // Only hydrate once
    const stored = readFromStorage();
    if (stored) {
      set({
        settings: stored,
        isConfigured: stored.api_key !== '' || stored.mode === 'local',
        hydrated: true,
      });
    } else {
      set({ hydrated: true });
    }
  },

  updateSettings: (partial: Partial<ModelSettings>) => {
    const newSettings = { ...get().settings, ...partial };
    saveToStorage(newSettings);
    set({
      settings: newSettings,
      isConfigured: newSettings.mode === 'local' || newSettings.api_key !== '',
    });
  },

  setProvider: (provider: ApiProvider) => {
    const preset = API_PROVIDER_PRESETS.find(p => p.provider === provider);
    if (!preset) return;
    const current = get().settings;
    const newSettings: ModelSettings = {
      ...current,
      api_provider: provider,
      api_base_url: preset.defaultBaseUrl || current.api_base_url,
      model_name: preset.defaultModel || current.model_name,
    };
    saveToStorage(newSettings);
    set({
      settings: newSettings,
      isConfigured: newSettings.api_key !== '' || newSettings.mode === 'local',
    });
  },

  setLocalEngine: (engine: LocalEngine) => {
    const preset = LOCAL_ENGINE_PRESETS.find(p => p.engine === engine);
    if (!preset) return;
    const current = get().settings;
    const newSettings: ModelSettings = {
      ...current,
      local_engine: engine,
      local_base_url: preset.defaultBaseUrl || current.local_base_url,
    };
    saveToStorage(newSettings);
    set({ settings: newSettings });
  },

  testConnection: async () => {
    const { settings } = get();
    set({
      settings: { ...settings, connection_status: 'testing', connection_error: undefined },
    });

    const baseUrl = settings.mode === 'api' ? settings.api_base_url : settings.local_base_url;

    if (!baseUrl) {
      set({
        settings: { ...get().settings, connection_status: 'failed', connection_error: '未配置 API 地址或本地服务地址' },
      });
      return;
    }

    try {
      // Route through backend proxy to avoid browser CORS restrictions
      const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${backendUrl}/api/v1/models/test-connection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: settings.mode,
          api_provider: settings.api_provider,
          api_key: settings.api_key,
          api_base_url: settings.api_base_url,
          model_name: settings.model_name,
          local_engine: settings.local_engine,
          local_base_url: settings.local_base_url,
          local_model_name: settings.local_model_name,
        }),
        signal: AbortSignal.timeout(25000), // 25s timeout (backend has 20s + overhead)
      });

      if (!response.ok) {
        set({
          settings: { ...get().settings, connection_status: 'failed', connection_error: `后端服务不可达 (${response.status})，请确保后端 API 已启动` },
        });
        return;
      }

      const result = await response.json();

      if (result.status === 'connected') {
        set({
          settings: { ...get().settings, connection_status: 'connected', connection_error: undefined },
        });
      } else {
        set({
          settings: { ...get().settings, connection_status: 'failed', connection_error: result.error || '连接失败' },
        });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '连接超时';
      if (message.includes('Failed to fetch') || message.includes('NetworkError') || message.includes('ERR_CONNECTION_REFUSED')) {
        set({
          settings: { ...get().settings, connection_status: 'failed', connection_error: '后端服务不可达，请先启动后端 API (端口 8000)' },
        });
      } else {
        set({
          settings: { ...get().settings, connection_status: 'failed', connection_error: `测试超时: ${message}。如在中国大陆使用 OpenAI，请配置代理地址` },
        });
      }
    }
  },

  resetToDefaults: () => {
    const defaults = getDefaultSettings();
    saveToStorage(defaults);
    set({ settings: defaults, isConfigured: false });
  },

  getEffectiveBaseUrl: () => {
    const { settings } = get();
    return settings.mode === 'api' ? settings.api_base_url : settings.local_base_url;
  },

  getEffectiveApiKey: () => {
    const { settings } = get();
    return settings.mode === 'api' ? settings.api_key : '';
  },

  getEffectiveModelName: () => {
    const { settings } = get();
    return settings.mode === 'api' ? settings.model_name : settings.local_model_name;
  },

  getApiHeaders: () => {
    const { settings } = get();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (settings.mode === 'api' && settings.api_key) {
      if (settings.api_provider === 'anthropic') {
        headers['x-api-key'] = settings.api_key;
        headers['anthropic-version'] = '2023-06-01';
      } else {
        headers['Authorization'] = `Bearer ${settings.api_key}`;
      }
    }

    return headers;
  },
}));