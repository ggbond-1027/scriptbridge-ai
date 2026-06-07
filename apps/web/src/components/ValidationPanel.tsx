'use client';

import React, { useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  Info,
  RefreshCw,
  Loader2,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Wrench,
  Locate,
} from 'lucide-react';
import { useProjectStore } from '@/store/project-store';
import { ValidationError } from '@/lib/types';

// Severity color configuration
const SEVERITY_CONFIG: Record<string, {
  bgColor: string;
  borderColor: string;
  textColor: string;
  label: string;
  badgeBg: string;
}> = {
  error: {
    bgColor: 'oklch(0.55 0.2 25 / 0.08)',
    borderColor: 'oklch(0.55 0.2 25)',
    textColor: 'oklch(0.55 0.2 25)',
    label: '错误',
    badgeBg: 'oklch(0.55 0.2 25 / 0.15)',
  },
  warning: {
    bgColor: 'oklch(0.65 0.15 75 / 0.08)',
    borderColor: 'oklch(0.65 0.15 75)',
    textColor: 'oklch(0.65 0.15 75)',
    label: '警告',
    badgeBg: 'oklch(0.65 0.15 75 / 0.15)',
  },
  info: {
    bgColor: 'oklch(0.55 0.18 250 / 0.08)',
    borderColor: 'oklch(0.55 0.18 250)',
    textColor: 'oklch(0.55 0.18 250)',
    label: '信息',
    badgeBg: 'oklch(0.55 0.18 250 / 0.15)',
  },
};

export default function ValidationPanel() {
  const { validationErrors, project, repairErrors, selectScene, selectChapter, setRightPanelTab, chapters } = useProjectStore();
  const [isRepairing, setIsRepairing] = useState(false);
  const [expandedErrors, setExpandedErrors] = useState<Set<string>>(new Set());
  const [repairResult, setRepairResult] = useState<string | null>(null);

  // Navigate to the relevant scene/character/location referenced by an error
  const navigateToError = (error: ValidationError) => {
    if (!project) return;

    // If error references a scene, find its chapter and navigate to it
    if (error.scene_id) {
      for (const chapter of chapters) {
        if (chapter.scenes.some(s => s.id === error.scene_id)) {
          selectChapter(chapter.id);
          selectScene(error.scene_id);
          setRightPanelTab('yaml');
          return;
        }
      }
    }

    // If error references a character or location (but no scene_id), switch to yaml tab
    // which shows the scene YAML data that may reference the character
    if (error.character_id || error.location_id) {
      // Try to find a scene that references this character/location
      for (const chapter of chapters) {
        const matchingScene = chapter.scenes.find(s =>
          s.characters.includes(error.character_id || '') ||
          s.heading?.location_id === error.location_id
        );
        if (matchingScene) {
          selectChapter(chapter.id);
          selectScene(matchingScene.id);
          setRightPanelTab('yaml');
          return;
        }
      }
      // No matching scene found, just switch to yaml tab
      setRightPanelTab('yaml');
    }

    // If error references a chapter_id, select that chapter
    if (error.chapter_id) {
      selectChapter(error.chapter_id);
      setRightPanelTab('yaml');
    }
  };

  const toggleError = (errorId: string) => {
    setExpandedErrors((prev) => {
      const next = new Set(prev);
      if (next.has(errorId)) next.delete(errorId);
      else next.add(errorId);
      return next;
    });
  };

  const handleRepair = async () => {
    if (!project) return;
    setIsRepairing(true);
    setRepairResult(null);
    try {
      await repairErrors(project.id);
      setRepairResult('修复完成');
    } catch (err) {
      setRepairResult(`修复失败: ${err instanceof Error ? err.message : '未知错误'}`);
    } finally {
      setIsRepairing(false);
    }
  };

  const handleRepairSingle = async (errorId: string) => {
    if (!project) return;
    setIsRepairing(true);
    try {
      await repairErrors(project.id, [errorId]);
      setRepairResult('单个修复完成');
    } catch (err) {
      setRepairResult(`修复失败: ${err instanceof Error ? err.message : '未知错误'}`);
    } finally {
      setIsRepairing(false);
    }
  };

  // Categorize errors
  const errors = validationErrors.filter((e) => e.severity === 'error');
  const warnings = validationErrors.filter((e) => e.severity === 'warning');
  const infos = validationErrors.filter((e) => e.severity === 'info');

  // Convert error messages to user-friendly Chinese
  const friendlyMessage = (error: ValidationError): string => {
    const { type, field, scene_id, character_id, location_id, message } = error;

    // Override with Chinese translations for common patterns
    if (type === 'invalid_reference' && field === 'character_id') {
      const sceneLabel = scene_id ? `第${extractSceneNumber(scene_id)}场` : '某场';
      return `${sceneLabel}引用了不存在的人物 ${character_id}`;
    }
    if (type === 'missing_field' && field === 'dramatic_purpose') {
      return `第${extractSceneNumber(scene_id || '')}场缺少 dramatic_purpose`;
    }
    if (type === 'missing_field' && field === 'conflict') {
      return `第${extractSceneNumber(scene_id || '')}场缺少冲突描述`;
    }
    if (type === 'consistency' && message.includes('source_ref')) {
      return `第${extractSceneNumber(scene_id || '')}场没有来源段落`;
    }
    if (type === 'duplicate') {
      return `发现重复内容: ${message}`;
    }
    if (type === 'format_error') {
      return `格式错误: ${message}`;
    }

    return message;
  };

  if (validationErrors.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-4" style={{ color: 'var(--color-teal)' }}>
        <CheckCircle2 size={32} className="mb-3" />
        <p className="text-sm font-semibold">校验通过</p>
        <p className="text-xs mt-1" style={{ color: 'var(--color-muted)' }}>
          所有场景和元素均符合Schema规范
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header with summary */}
      <div className="p-3 border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold flex items-center gap-1" style={{ color: 'var(--color-warning)' }}>
            <AlertCircle size={14} />
            校验问题
          </h3>
          {/* One-click repair */}
          <button
            onClick={handleRepair}
            disabled={isRepairing}
            className="btn-accent text-xs flex items-center gap-1"
          >
            {isRepairing ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <Wrench size={12} />
            )}
            一键修复
          </button>
        </div>

        {/* Error counts summary - color-coded badges */}
        <div className="flex items-center gap-2">
          {errors.length > 0 && (
            <span
              className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full"
              style={{
                backgroundColor: SEVERITY_CONFIG.error.badgeBg,
                color: SEVERITY_CONFIG.error.textColor,
              }}
            >
              <AlertCircle size={10} />
              {errors.length} 错误
            </span>
          )}
          {warnings.length > 0 && (
            <span
              className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full"
              style={{
                backgroundColor: SEVERITY_CONFIG.warning.badgeBg,
                color: SEVERITY_CONFIG.warning.textColor,
              }}
            >
              <AlertTriangle size={10} />
              {warnings.length} 警告
            </span>
          )}
          {infos.length > 0 && (
            <span
              className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full"
              style={{
                backgroundColor: SEVERITY_CONFIG.info.badgeBg,
                color: SEVERITY_CONFIG.info.textColor,
              }}
            >
              <Info size={10} />
              {infos.length} 信息
            </span>
          )}
        </div>

        {repairResult && (
          <div className="mt-2 text-xs" style={{ color: 'var(--color-teal)' }}>
            {repairResult}
          </div>
        )}
      </div>

      {/* Error list */}
      <div className="flex-1 overflow-auto p-3 space-y-2">
        {/* Errors section */}
        {errors.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold mb-1" style={{ color: 'var(--color-warning)' }}>
              错误
            </h4>
            {errors.map((error) => (
              <ErrorItem
                key={error.id}
                error={error}
                friendlyMsg={friendlyMessage(error)}
                isExpanded={expandedErrors.has(error.id)}
                onToggle={() => toggleError(error.id)}
                onRepair={() => handleRepairSingle(error.id)}
                isRepairing={isRepairing}
                onNavigate={() => navigateToError(error)}
              />
            ))}
          </div>
        )}

        {/* Warnings section */}
        {warnings.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold mb-1" style={{ color: 'var(--color-accent)' }}>
              警告
            </h4>
            {warnings.map((error) => (
              <ErrorItem
                key={error.id}
                error={error}
                friendlyMsg={friendlyMessage(error)}
                isExpanded={expandedErrors.has(error.id)}
                onToggle={() => toggleError(error.id)}
                onRepair={() => handleRepairSingle(error.id)}
                isRepairing={isRepairing}
                onNavigate={() => navigateToError(error)}
              />
            ))}
          </div>
        )}

        {/* Info section */}
        {infos.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold mb-1" style={{ color: 'var(--color-muted)' }}>
              提示
            </h4>
            {infos.map((error) => (
              <ErrorItem
                key={error.id}
                error={error}
                friendlyMsg={friendlyMessage(error)}
                isExpanded={expandedErrors.has(error.id)}
                onToggle={() => toggleError(error.id)}
                onRepair={() => handleRepairSingle(error.id)}
                isRepairing={isRepairing}
                onNavigate={() => navigateToError(error)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface ErrorItemProps {
  error: ValidationError;
  friendlyMsg: string;
  isExpanded: boolean;
  onToggle: () => void;
  onRepair: () => void;
  isRepairing: boolean;
  onNavigate: () => void;
}

function ErrorItem({ error, friendlyMsg, isExpanded, onToggle, onRepair, isRepairing, onNavigate }: ErrorItemProps) {
  const severityConfig = SEVERITY_CONFIG[error.severity];
  const hasNavigation = error.scene_id || error.character_id || error.location_id || error.chapter_id;

  return (
    <div
      className="rounded p-2 cursor-pointer transition-all hover:brightness-110"
      style={{
        backgroundColor: severityConfig.bgColor,
        borderLeft: `3px solid ${severityConfig.borderColor}`,
      }}
      onClick={onToggle}
    >
      <div className="flex items-start gap-2">
        {/* Severity badge */}
        <span
          className="inline-flex items-center justify-center shrink-0 text-xs font-bold px-1.5 py-0.5 rounded mt-0.5"
          style={{
            backgroundColor: severityConfig.badgeBg,
            color: severityConfig.textColor,
            minWidth: '28px',
          }}
        >
          {severityConfig.label}
        </span>

        {isExpanded ? (
          <ChevronDown size={12} className="mt-0.5 shrink-0" style={{ color: 'var(--color-muted)' }} />
        ) : (
          <ChevronRight size={12} className="mt-0.5 shrink-0" style={{ color: 'var(--color-muted)' }} />
        )}
        <span className="text-xs flex-1 font-medium" style={{ color: 'var(--color-foreground)' }}>
          {friendlyMsg}
        </span>

        {/* Navigate button */}
        {hasNavigation && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onNavigate();
            }}
            className="shrink-0 text-xs flex items-center gap-1 px-1.5 py-0.5 rounded transition-colors"
            style={{
              backgroundColor: severityConfig.badgeBg,
              color: severityConfig.textColor,
            }}
          >
            <Locate size={10} />
            跳转
          </button>
        )}

        {error.auto_fixable && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRepair();
            }}
            disabled={isRepairing}
            className="shrink-0 text-xs flex items-center gap-1"
            style={{ color: 'var(--color-teal)' }}
          >
            {isRepairing ? (
              <Loader2 size={10} className="animate-spin" />
            ) : (
              <Wrench size={10} />
            )}
            修复
          </button>
        )}
      </div>

      {isExpanded && (
        <div className="ml-8 mt-1 text-xs space-y-1" style={{ color: 'var(--color-muted)' }}>
          <div>
            <span className="font-medium">类型:</span> {error.type}
          </div>
          <div>
            <span className="font-medium">字段:</span> {error.field || '-'}
          </div>
          {error.scene_id && (
            <div className="flex items-center gap-1">
              <span className="font-medium">场景:</span> {error.scene_id}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onNavigate();
                }}
                className="inline-flex items-center gap-0.5 text-xs px-1 rounded"
                style={{
                  backgroundColor: SEVERITY_CONFIG.info.badgeBg,
                  color: SEVERITY_CONFIG.info.textColor,
                }}
              >
                <Locate size={9} />
                跳转到场景
              </button>
            </div>
          )}
          {error.character_id && (
            <div className="flex items-center gap-1">
              <span className="font-medium">人物:</span> {error.character_id}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onNavigate();
                }}
                className="inline-flex items-center gap-0.5 text-xs px-1 rounded"
                style={{
                  backgroundColor: SEVERITY_CONFIG.info.badgeBg,
                  color: SEVERITY_CONFIG.info.textColor,
                }}
              >
                <Locate size={9} />
                查看人物
              </button>
            </div>
          )}
          {error.location_id && (
            <div className="flex items-center gap-1">
              <span className="font-medium">地点:</span> {error.location_id}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onNavigate();
                }}
                className="inline-flex items-center gap-0.5 text-xs px-1 rounded"
                style={{
                  backgroundColor: SEVERITY_CONFIG.info.badgeBg,
                  color: SEVERITY_CONFIG.info.textColor,
                }}
              >
                <Locate size={9} />
                查看地点
              </button>
            </div>
          )}
          <div>
            <span className="font-medium">原始信息:</span> {error.message}
          </div>
          <div>
            <span className="font-medium">可自动修复:</span>
            {error.auto_fixable ? '是' : '否'}
          </div>
        </div>
      )}
    </div>
  );
}

function extractSceneNumber(sceneId: string): string {
  // Extract number from scene IDs like "sc_001", "sc_12", etc.
  const match = sceneId.match(/sc_?\d+/i);
  if (match) {
    const num = match[0].replace(/sc_?/i, '');
    return num;
  }
  return sceneId;
}