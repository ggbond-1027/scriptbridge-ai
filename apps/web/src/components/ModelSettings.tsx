'use client';

import React, { useState, useCallback } from 'react';
import {
  X,
  Settings,
  Cpu,
  Globe,
  Key,
  Thermometer,
  Save,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Zap,
  Eye,
  EyeOff,
  Server,
  RotateCcw,
} from 'lucide-react';
import { useModelStore } from '@/store/model-store';
import {
  ApiProvider,
  LocalEngine,
  API_PROVIDER_PRESETS,
  LOCAL_ENGINE_PRESETS,
} from '@/lib/types';

interface ModelSettingsProps {
  onClose: () => void;
}

export default function ModelSettings({ onClose }: ModelSettingsProps) {
  const {
    settings,
    updateSettings,
    setProvider,
    setLocalEngine,
    testConnection,
    resetToDefaults,
  } = useModelStore();

  const [showApiKey, setShowApiKey] = useState(false);

  const handleProviderChange = useCallback((provider: ApiProvider) => {
    setProvider(provider);
  }, [setProvider]);

  const handleLocalEngineChange = useCallback((engine: LocalEngine) => {
    setLocalEngine(engine);
  }, [setLocalEngine]);

  const handleTestConnection = useCallback(async () => {
    await testConnection();
  }, [testConnection]);

  const handleSaveAndClose = useCallback(() => {
    onClose();
  }, [onClose]);

  const currentProviderPreset = API_PROVIDER_PRESETS.find(p => p.provider === settings.api_provider);
  const currentEnginePreset = LOCAL_ENGINE_PRESETS.find(p => p.engine === settings.local_engine);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Overlay */}
      <div
        className="absolute inset-0"
        style={{ backgroundColor: 'oklch(0.10 0.02 260 / 0.85)' }}
        onClick={onClose}
      />

      {/* Dialog */}
      <div
        className="relative panel w-[520px] z-10 max-h-[85vh] overflow-auto"
        style={{
          backgroundColor: 'var(--color-surface)',
          borderColor: 'var(--color-accent)',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--color-foreground)' }}>
            <Settings size={20} style={{ color: 'var(--color-accent)' }} />
            模型配置
          </h2>
          <div className="flex items-center gap-2">
            {/* Connection status badge */}
            <div
              className="badge flex items-center gap-1"
              style={{
                backgroundColor:
                  settings.connection_status === 'connected' ? 'oklch(0.55 0.12 150 / 0.15)' :
                  settings.connection_status === 'failed' ? 'oklch(0.65 0.18 25 / 0.15)' :
                  settings.connection_status === 'testing' ? 'oklch(0.75 0.15 75 / 0.15)' :
                  'oklch(0.55 0.02 260 / 0.15)',
                color:
                  settings.connection_status === 'connected' ? 'var(--color-teal)' :
                  settings.connection_status === 'failed' ? 'var(--color-warning)' :
                  settings.connection_status === 'testing' ? 'var(--color-accent)' :
                  'var(--color-muted)',
              }}
            >
              {settings.connection_status === 'testing' && <Loader2 size={12} className="animate-spin" />}
              {settings.connection_status === 'connected' && <CheckCircle2 size={12} />}
              {settings.connection_status === 'failed' && <AlertCircle size={12} />}
              {settings.connection_status === 'unknown' && <Server size={12} />}
              {settings.connection_status === 'connected' ? '已连接' :
               settings.connection_status === 'failed' ? '连接失败' :
               settings.connection_status === 'testing' ? '测试中...' :
               '未测试'}
            </div>
            <button onClick={onClose} style={{ color: 'var(--color-muted)' }}>
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Mode selection: API / Local */}
        <div className="mb-5">
          <h3 className="text-xs font-semibold mb-2" style={{ color: 'var(--color-muted)' }}>
            运行模式
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => updateSettings({ mode: 'api' })}
              className="panel flex items-center gap-3 cursor-pointer transition-all"
              style={{
                borderColor: settings.mode === 'api' ? 'var(--color-accent)' : 'var(--color-border)',
                borderWidth: settings.mode === 'api' ? '2px' : '1px',
                backgroundColor: settings.mode === 'api' ? 'oklch(0.75 0.15 75 / 0.08)' : 'var(--color-surface)',
              }}
            >
              <Globe size={20} style={{ color: settings.mode === 'api' ? 'var(--color-accent)' : 'var(--color-muted)' }} />
              <div>
                <span className="font-semibold text-sm" style={{ color: 'var(--color-foreground)' }}>
                  API 模式
                </span>
                <p className="text-xs" style={{ color: 'var(--color-muted)' }}>
                  OpenAI / DeepSeek / GLM / Claude
                </p>
              </div>
            </button>
            <button
              onClick={() => updateSettings({ mode: 'local' })}
              className="panel flex items-center gap-3 cursor-pointer transition-all"
              style={{
                borderColor: settings.mode === 'local' ? 'var(--color-accent)' : 'var(--color-border)',
                borderWidth: settings.mode === 'local' ? '2px' : '1px',
                backgroundColor: settings.mode === 'local' ? 'oklch(0.75 0.15 75 / 0.08)' : 'var(--color-surface)',
              }}
            >
              <Cpu size={20} style={{ color: settings.mode === 'local' ? 'var(--color-accent)' : 'var(--color-muted)' }} />
              <div>
                <span className="font-semibold text-sm" style={{ color: 'var(--color-foreground)' }}>
                  本地模式
                </span>
                <p className="text-xs" style={{ color: 'var(--color-muted)' }}>
                  Ollama / vLLM / llama.cpp
                </p>
              </div>
            </button>
          </div>
        </div>

        {/* ==================== API Mode Settings ==================== */}
        {settings.mode === 'api' && (
          <div className="space-y-4 mb-5">
            {/* Provider selection cards */}
            <div>
              <label className="text-xs font-semibold mb-2 block" style={{ color: 'var(--color-muted)' }}>
                API 提供商
              </label>
              <div className="grid grid-cols-3 gap-2">
                {API_PROVIDER_PRESETS.map((preset) => (
                  <button
                    key={preset.provider}
                    onClick={() => handleProviderChange(preset.provider)}
                    className="panel flex flex-col items-center gap-1 py-2 px-3 cursor-pointer transition-all text-center"
                    style={{
                      borderColor: settings.api_provider === preset.provider ? 'var(--color-accent)' : 'var(--color-border)',
                      borderWidth: settings.api_provider === preset.provider ? '2px' : '1px',
                      backgroundColor: settings.api_provider === preset.provider ? 'oklch(0.75 0.15 75 / 0.08)' : 'var(--color-surface)',
                    }}
                  >
                    <span className="font-semibold text-xs" style={{ color: settings.api_provider === preset.provider ? 'var(--color-accent)' : 'var(--color-foreground)' }}>
                      {preset.label}
                    </span>
                    {preset.defaultModel && (
                      <span className="text-xs" style={{ color: 'var(--color-muted)' }}>
                        {preset.defaultModel}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* API Base URL - ALWAYS visible */}
            <div>
              <label className="text-xs font-semibold flex items-center gap-1 mb-1" style={{ color: 'var(--color-muted)' }}>
                <Server size={10} />
                API 地址 (Base URL)
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  className="input-field text-sm flex-1"
                  value={settings.api_base_url}
                  onChange={(e) => updateSettings({ api_base_url: e.target.value })}
                  placeholder={currentProviderPreset?.defaultBaseUrl || 'https://api.example.com/v1'}
                />
                {currentProviderPreset && currentProviderPreset.defaultBaseUrl && settings.api_base_url !== currentProviderPreset.defaultBaseUrl && (
                  <button
                    onClick={() => updateSettings({ api_base_url: currentProviderPreset!.defaultBaseUrl })}
                    className="btn-ghost text-xs px-2 py-1 flex items-center gap-1"
                    title="恢复默认地址"
                  >
                    <RotateCcw size={10} />
                    默认
                  </button>
                )}
              </div>
              <p className="text-xs mt-1" style={{ color: 'var(--color-muted)' }}>
                {settings.api_provider === 'custom'
                  ? '输入自定义 API 地址，需兼容 OpenAI 接口格式'
                  : `默认地址: ${currentProviderPreset?.defaultBaseUrl || '-'}，可修改为代理地址`}
              </p>
            </div>

            {/* API Key */}
            <div>
              <label className="text-xs font-semibold flex items-center gap-1 mb-1" style={{ color: 'var(--color-muted)' }}>
                <Key size={10} />
                API 密钥
              </label>
              <div className="flex items-center gap-2">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  className="input-field text-sm flex-1"
                  value={settings.api_key}
                  onChange={(e) => updateSettings({ api_key: e.target.value })}
                  placeholder={currentProviderPreset?.keyPrefix ? `${currentProviderPreset.keyPrefix}...` : '输入 API Key'}
                />
                <button
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="btn-ghost px-2 py-1"
                  title={showApiKey ? '隐藏' : '显示'}
                >
                  {showApiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
              {settings.api_key && (
                <p className="text-xs mt-1" style={{ color: 'var(--color-teal)' }}>
                  已配置 ({settings.api_key.slice(0, 8)}...{settings.api_key.slice(-4)})
                </p>
              )}
            </div>

            {/* Model Name */}
            <div>
              <label className="text-xs font-semibold mb-1 block" style={{ color: 'var(--color-muted)' }}>
                模型名称
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  className="input-field text-sm flex-1"
                  value={settings.model_name}
                  onChange={(e) => updateSettings({ model_name: e.target.value })}
                  placeholder={currentProviderPreset?.defaultModel || 'model-name'}
                />
                {currentProviderPreset && currentProviderPreset.defaultModel && settings.model_name !== currentProviderPreset.defaultModel && (
                  <button
                    onClick={() => updateSettings({ model_name: currentProviderPreset!.defaultModel })}
                    className="btn-ghost text-xs px-2 py-1 flex items-center gap-1"
                    title="恢复默认模型"
                  >
                    <RotateCcw size={10} />
                    默认
                  </button>
                )}
              </div>
              {/* Common model suggestions for current provider */}
              {settings.api_provider !== 'custom' && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {getModelsForProvider(settings.api_provider).map((model) => (
                    <button
                      key={model}
                      onClick={() => updateSettings({ model_name: model })}
                      className="badge cursor-pointer transition-all"
                      style={{
                        backgroundColor: settings.model_name === model ? 'oklch(0.75 0.15 75 / 0.2)' : 'oklch(0.55 0.02 260 / 0.15)',
                        color: settings.model_name === model ? 'var(--color-accent)' : 'var(--color-muted)',
                      }}
                    >
                      {model}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ==================== Local Mode Settings ==================== */}
        {settings.mode === 'local' && (
          <div className="space-y-4 mb-5">
            {/* Local engine selection */}
            <div>
              <label className="text-xs font-semibold mb-2 block" style={{ color: 'var(--color-muted)' }}>
                本地推理引擎
              </label>
              <div className="grid grid-cols-3 gap-2">
                {LOCAL_ENGINE_PRESETS.map((preset) => (
                  <button
                    key={preset.engine}
                    onClick={() => handleLocalEngineChange(preset.engine)}
                    className="panel flex flex-col items-center gap-1 py-2 px-3 cursor-pointer transition-all text-center"
                    style={{
                      borderColor: settings.local_engine === preset.engine ? 'var(--color-accent)' : 'var(--color-border)',
                      borderWidth: settings.local_engine === preset.engine ? '2px' : '1px',
                      backgroundColor: settings.local_engine === preset.engine ? 'oklch(0.75 0.15 75 / 0.08)' : 'var(--color-surface)',
                    }}
                  >
                    <span className="font-semibold text-xs" style={{ color: settings.local_engine === preset.engine ? 'var(--color-accent)' : 'var(--color-foreground)' }}>
                      {preset.label}
                    </span>
                    <span className="text-xs" style={{ color: 'var(--color-muted)' }}>
                      {preset.defaultBaseUrl}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Local Base URL */}
            <div>
              <label className="text-xs font-semibold flex items-center gap-1 mb-1" style={{ color: 'var(--color-muted)' }}>
                <Server size={10} />
                本地服务地址
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  className="input-field text-sm flex-1"
                  value={settings.local_base_url}
                  onChange={(e) => updateSettings({ local_base_url: e.target.value })}
                  placeholder={currentEnginePreset?.defaultBaseUrl || 'http://localhost:11434/v1'}
                />
                {currentEnginePreset && settings.local_base_url !== currentEnginePreset.defaultBaseUrl && (
                  <button
                    onClick={() => updateSettings({ local_base_url: currentEnginePreset!.defaultBaseUrl })}
                    className="btn-ghost text-xs px-2 py-1 flex items-center gap-1"
                    title="恢复默认地址"
                  >
                    <RotateCcw size={10} />
                    默认
                  </button>
                )}
              </div>
              <p className="text-xs mt-1" style={{ color: 'var(--color-muted)' }}>
                本地模式不需要 API Key，请确保本地服务已启动且端口正确
              </p>
            </div>

            {/* Local Model Name */}
            <div>
              <label className="text-xs font-semibold mb-1 block" style={{ color: 'var(--color-muted)' }}>
                模型名称
              </label>
              <input
                type="text"
                className="input-field text-sm"
                value={settings.local_model_name}
                onChange={(e) => updateSettings({ local_model_name: e.target.value })}
                placeholder={settings.local_engine === 'ollama' ? 'qwen2.5:7b / llama3:8b' : '本地模型名称'}
              />
              {settings.local_engine === 'ollama' && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {['qwen2.5:7b', 'qwen2.5:14b', 'llama3:8b', 'deepseek-r1:7b', 'glm4:9b'].map((model) => (
                    <button
                      key={model}
                      onClick={() => updateSettings({ local_model_name: model })}
                      className="badge cursor-pointer transition-all"
                      style={{
                        backgroundColor: settings.local_model_name === model ? 'oklch(0.75 0.15 75 / 0.2)' : 'oklch(0.55 0.02 260 / 0.15)',
                        color: settings.local_model_name === model ? 'var(--color-accent)' : 'var(--color-muted)',
                      }}
                    >
                      {model}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ==================== Common Parameters ==================== */}
        <div className="space-y-4 mb-5 panel" style={{ backgroundColor: 'oklch(0.22 0.03 260 / 0.5)' }}>
          <h3 className="text-xs font-semibold flex items-center gap-1" style={{ color: 'var(--color-accent)' }}>
            <Thermometer size={12} />
            生成参数
          </h3>

          {/* Temperature */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-semibold" style={{ color: 'var(--color-muted)' }}>
                温度 (Temperature)
              </label>
              <span className="text-sm font-mono font-semibold" style={{ color: 'var(--color-accent)' }}>
                {settings.temperature.toFixed(1)}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={settings.temperature}
              onChange={(e) => updateSettings({ temperature: parseFloat(e.target.value) })}
              style={{ accentColor: 'var(--color-accent)' }}
              className="w-full"
            />
            <div className="flex justify-between text-xs mt-1" style={{ color: 'var(--color-muted)' }}>
              <span>0 = 精确/确定性</span>
              <span>1 = 创造性/多样性</span>
            </div>
          </div>

          {/* Max tokens */}
          <div>
            <label className="text-xs font-semibold mb-1 block" style={{ color: 'var(--color-muted)' }}>
              最大 Token 数
            </label>
            <input
              type="number"
              className="input-field text-sm"
              value={settings.max_tokens}
              onChange={(e) => updateSettings({ max_tokens: parseInt(e.target.value) || 4000 })}
              min="100"
              max="32000"
              step="500"
            />
            <p className="text-xs mt-1" style={{ color: 'var(--color-muted)' }}>
              建议值: 4000 (短场景) / 8000 (长章节)
            </p>
          </div>
        </div>

        {/* Connection error message */}
        {settings.connection_status === 'failed' && settings.connection_error && (
          <div
            className="mb-4 p-3 rounded-md flex items-start gap-2 text-xs"
            style={{
              backgroundColor: 'oklch(0.65 0.18 25 / 0.1)',
              borderColor: 'var(--color-warning)',
              border: '1px solid var(--color-warning)',
            }}
          >
            <AlertCircle size={14} style={{ color: 'var(--color-warning)' }} className="shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold" style={{ color: 'var(--color-warning)' }}>连接失败</p>
              <p style={{ color: 'var(--color-muted)' }}>{settings.connection_error}</p>
            </div>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {/* Test connection */}
          <button
            onClick={handleTestConnection}
            disabled={settings.connection_status === 'testing' || (!settings.api_base_url && !settings.local_base_url)}
            className="btn-ghost flex items-center gap-2 text-sm px-4"
            style={{
              borderColor: settings.connection_status === 'connected' ? 'var(--color-teal)' : 'var(--color-border)',
            }}
          >
            {settings.connection_status === 'testing' ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Zap size={14} />
            )}
            测试连接
          </button>

          {/* Reset defaults */}
          <button
            onClick={resetToDefaults}
            className="btn-ghost flex items-center gap-2 text-sm px-3"
            style={{ borderColor: 'var(--color-border)' }}
          >
            <RotateCcw size={14} />
            重置
          </button>

          {/* Save & close */}
          <button
            onClick={handleSaveAndClose}
            className="btn-accent flex-1 flex items-center justify-center gap-2"
          >
            <Save size={14} />
            保存并关闭
          </button>
        </div>

        {/* Hint */}
        <p className="text-xs mt-3 text-center" style={{ color: 'var(--color-muted)' }}>
          配置自动保存至浏览器本地存储，关闭页面后仍然保留
        </p>
      </div>
    </div>
  );
}

/* === Model suggestions per provider === */

function getModelsForProvider(provider: ApiProvider): string[] {
  switch (provider) {
    case 'openai':
      return ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'];
    case 'deepseek':
      return ['deepseek-chat', 'deepseek-reasoner'];
    case 'glm':
      return ['glm-4-plus', 'glm-4-flash', 'glm-4-long', 'glm-4v-plus'];
    case 'anthropic':
      return ['claude-sonnet-4-20250514', 'claude-3-5-haiku-20241022', 'claude-3-5-sonnet-20241022'];
    case 'custom':
      return [];
    default:
      return [];
  }
}