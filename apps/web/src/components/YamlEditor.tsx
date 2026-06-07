'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  FileText,
  AlertCircle,
  BookOpen,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  List,
  Copy,
} from 'lucide-react';
import { useProjectStore } from '@/store/project-store';
import { validateYaml, formatYaml, YamlError, highlightYamlErrors, YamlLineInfo, serializeYaml, parseYaml } from '@/lib/yaml-utils';

const SCHEMA_TOP_LEVEL_FIELDS = [
  'schema_version',
  'project',
  'story_bible',
  'chapters',
  'scenes',
  'metadata',
];

const SCHEMA_STRUCTURE = [
  {
    name: 'schema_version',
    type: 'string',
    required: '必填',
    purpose: 'Schema 版本号，用于兼容性判断和后续迁移。',
    keyFields: ['SemVer 格式', '例如 1.0.0'],
  },
  {
    name: 'project',
    type: 'object',
    required: '必填',
    purpose: '项目元信息，描述来源、目标格式和改编风格。',
    keyFields: ['id', 'title', 'source_language', 'target_format', 'adaptation_style'],
  },
  {
    name: 'story_bible',
    type: 'object',
    required: '必填',
    purpose: '故事圣经，集中管理角色、地点和时间线，避免跨章节不一致。',
    keyFields: ['characters', 'locations', 'timeline'],
  },
  {
    name: 'chapters',
    type: 'array',
    required: '必填',
    purpose: '原文章节和段落结构，为场景和元素提供 source_refs 溯源。',
    keyFields: ['id', 'order', 'title', 'paragraphs', 'summary'],
  },
  {
    name: 'scenes',
    type: 'array',
    required: '必填',
    purpose: '剧本核心产物，按场景组织标题、冲突、节拍和剧本元素。',
    keyFields: ['heading', 'dramatic_purpose', 'conflict', 'beats', 'elements'],
  },
  {
    name: 'metadata',
    type: 'object',
    required: '必填',
    purpose: '生成元数据，用于审计、统计和质量追踪。',
    keyFields: ['generated_at', 'model', 'total_scenes', 'total_elements'],
  },
];

const SCHEMA_ID_RULES = [
  ['角色', 'char_1'],
  ['地点', 'loc_1'],
  ['时间线', 'tl_1'],
  ['章节', 'ch_1'],
  ['段落', 'p_1_1'],
  ['场景', 'sc_1'],
  ['元素', 'el_1'],
];

const SCHEMA_ENUM_RULES = [
  ['角色类型', 'protagonist / supporting / antagonist / extra'],
  ['地点类型', 'interior / exterior / mixed / unknown'],
  ['场景空间', 'INT / EXT / INT.EXT'],
  ['场景时间', 'DAY / NIGHT / DUSK / DAWN / UNKNOWN'],
  ['元素类型', 'action / dialogue / parenthetical / transition / voice_over / shot / note'],
];

const SCHEMA_REFERENCE_RULES = [
  'scenes[].characters 必须引用 story_bible.characters[].id',
  'scenes[].heading.location_id 必须引用 story_bible.locations[].id',
  'scenes[].chapter_ids 必须引用 chapters[].id',
  'scenes[].source_refs[].paragraph_ids 必须引用对应章节的 paragraphs[].id',
  'elements[].character_id 必须引用已定义角色',
  'story_bible.timeline[].affected_characters 必须引用已定义角色',
];

/**
 * Build a YAML-serializable object from whatever data is available.
 * - If `screenplay` exists, use it directly.
 * - If `screenplay` is null but `chapters` or `storyBible` are available,
 *   construct a composite screenplay-like object so the YAML panel can still
 *   render meaningful content.
 */
function buildYamlData(
  screenplay: unknown | null,
  chapters: unknown[],
  storyBible: unknown | null,
  project: unknown | null,
): unknown | null {
  if (screenplay) {
    return screenplay;
  }

  // screenplay is null — try to compose from chapters + storyBible
  const hasChapters = chapters && chapters.length > 0;
  const hasStoryBible = storyBible !== null;

  if (!hasChapters && !hasStoryBible) {
    return null;
  }

  const composite: Record<string, unknown> = {};

  // Pull top-level metadata from project if available
  if (project) {
    const proj = project as Record<string, unknown>;
    if (proj.title) composite.title = proj.title;
    if (proj.id) composite.id = proj.id;
  }

  if (hasChapters) {
    composite.chapters = chapters;
  }

  if (hasStoryBible) {
    composite.story_bible = storyBible;
  }

  return composite;
}

export default function YamlEditor() {
  const { screenplay, chapters, storyBible, project, setSaveStatus, isLoading } = useProjectStore();
  const [yamlContent, setYamlContent] = useState('');
  const [yamlErrors, setYamlErrors] = useState<YamlError[]>([]);
  const [lineInfos, setLineInfos] = useState<YamlLineInfo[]>([]);
  const [isModified, setIsModified] = useState(false);
  const [schemaInfoOpen, setSchemaInfoOpen] = useState(false);
  const [schemaDetailsOpen, setSchemaDetailsOpen] = useState(true);

  // Compute the YAML-serializable object from whatever data is available
  const yamlData = useMemo(
    () => buildYamlData(screenplay, chapters, storyBible, project),
    [screenplay, chapters, storyBible, project],
  );

  // Initialize YAML content from available data (screenplay, or chapters+storyBible composite)
  useEffect(() => {
    if (yamlData) {
      const yaml = serializeYaml(yamlData);
      setYamlContent(yaml);
      setYamlErrors([]);
      setLineInfos(highlightYamlErrors(yaml, []));
      setIsModified(false);
    }
  }, [yamlData]);

  // Validate on change
  const handleChange = useCallback((newContent: string) => {
    setYamlContent(newContent);
    setIsModified(true);

    const errors = validateYaml(newContent);
    setYamlErrors(errors);
    setLineInfos(highlightYamlErrors(newContent, errors));
  }, []);

  // Format YAML
  const handleFormat = () => {
    try {
      const formatted = formatYaml(yamlContent);
      setYamlContent(formatted);
      setYamlErrors([]);
      setLineInfos(highlightYamlErrors(formatted, []));
    } catch (err) {
      // Keep current content if format fails
    }
  };

  // Save changes (parse YAML and apply back to screenplay)
  const handleSave = async () => {
    try {
      const parsed = parseYaml(yamlContent);
      // In real implementation, this would call the API to update the screenplay
      setSaveStatus('saving');
      setTimeout(() => {
        setSaveStatus('saved');
        setIsModified(false);
      }, 1000);
    } catch (err) {
      setSaveStatus('error');
    }
  };

  // Copy to clipboard
  const handleCopy = () => {
    navigator.clipboard.writeText(yamlContent);
  };

  const lineCount = yamlContent.split('\n').length;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div
        className="flex flex-wrap items-center gap-2 px-3 py-2 border-b shrink-0"
        style={{ borderColor: 'var(--color-border-subtle)' }}
      >
        <div className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-muted)' }}>
          <FileText size={12} />
          <span>{lineCount} 行</span>
        </div>

        {yamlErrors.length > 0 && (
          <div className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-warning)' }}>
            <AlertCircle size={12} />
            <span>{yamlErrors.length} 个错误</span>
          </div>
        )}
        {yamlErrors.length === 0 && yamlContent && (
          <div className="flex items-center gap-1 text-xs" style={{ color: 'var(--color-teal)' }}>
            <CheckCircle2 size={12} />
            <span>语法正确</span>
          </div>
        )}

        {isModified && (
          <span className="badge badge-accent">已修改</span>
        )}

        <div className="flex flex-wrap items-center justify-end gap-1 ml-auto">
          <button
            onClick={() => setSchemaInfoOpen((open) => !open)}
            className="btn-ghost text-xs flex items-center gap-1 px-2 py-1 whitespace-nowrap"
            title="查看剧本 YAML Schema 说明"
            aria-expanded={schemaInfoOpen}
          >
            <BookOpen size={12} />
            Schema说明
          </button>
          <button
            onClick={handleFormat}
            className="btn-ghost text-xs flex items-center gap-1 px-2 py-1 whitespace-nowrap"
            title="格式化YAML"
          >
            <List size={12} />
            格式化
          </button>
          <button
            onClick={handleCopy}
            className="btn-ghost text-xs flex items-center gap-1 px-2 py-1 whitespace-nowrap"
            title="复制"
          >
            <Copy size={12} />
          </button>
          {isModified && (
            <button
              onClick={handleSave}
              className="btn-accent text-xs"
            >
              保存
            </button>
          )}
        </div>
      </div>

      {schemaInfoOpen && (
        <div
          className="shrink-0 border-b px-3 py-2 text-xs overflow-y-auto"
          style={{
            borderColor: 'var(--color-border-subtle)',
            backgroundColor: 'var(--color-surface)',
            color: 'var(--color-label)',
            maxHeight: 'min(58vh, 560px)',
          }}
        >
          <div className="flex items-start gap-2">
            <BookOpen size={14} className="mt-0.5 shrink-0" style={{ color: 'var(--color-accent)' }} />
            <div className="min-w-0 flex-1 space-y-2">
              <p className="font-medium" style={{ color: 'var(--color-foreground)' }}>
                Schema说明（摘要）
              </p>
              <p>
                这里展示的是常用结构摘要。完整 Schema 很长，包含字段类型、必填规则、枚举、ID 格式、引用一致性和设计原因。
              </p>
              <div className="space-y-0.5">
                <p>
                  完整说明：<code className="break-all">docs/SCHEMA.md</code>
                </p>
                <p>
                  校验文件：<code className="break-all">apps/api/app/schemas/screenplay.schema.json</code>
                </p>
              </div>
              <button
                onClick={() => setSchemaDetailsOpen((open) => !open)}
                className="btn-ghost text-xs flex items-center gap-1 px-2 py-1"
                type="button"
              >
                {schemaDetailsOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                {schemaDetailsOpen ? '收起详细结构' : '展开详细结构'}
              </button>

              {schemaDetailsOpen && (
                <div
                  className="space-y-3 pt-2 border-t"
                  style={{ borderColor: 'var(--color-border-subtle)' }}
                >
                  <section className="space-y-1.5">
                    <p className="font-medium" style={{ color: 'var(--color-foreground)' }}>
                      顶层结构
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {SCHEMA_TOP_LEVEL_FIELDS.map((field) => (
                        <code
                          key={field}
                          className="rounded px-1.5 py-0.5"
                          style={{
                            backgroundColor: 'var(--color-base)',
                            color: 'var(--color-accent)',
                          }}
                        >
                          {field}
                        </code>
                      ))}
                    </div>
                    <div className="space-y-1">
                      {SCHEMA_STRUCTURE.map((item) => (
                        <div
                          key={item.name}
                          className="grid gap-1 py-1.5 border-b last:border-b-0"
                          style={{ borderColor: 'var(--color-border-subtle)' }}
                        >
                          <div className="flex flex-wrap items-center gap-1.5">
                            <code style={{ color: 'var(--color-accent)' }}>{item.name}</code>
                            <span className="badge badge-muted">{item.type}</span>
                            <span className="badge badge-accent">{item.required}</span>
                          </div>
                          <p>{item.purpose}</p>
                          <p>
                            关键字段：{item.keyFields.join(' / ')}
                          </p>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="space-y-1.5">
                    <p className="font-medium" style={{ color: 'var(--color-foreground)' }}>
                      ID 规则
                    </p>
                    <div className="grid grid-cols-2 gap-1">
                      {SCHEMA_ID_RULES.map(([label, example]) => (
                        <div key={label} className="flex items-center gap-1 min-w-0">
                          <span className="shrink-0">{label}</span>
                          <code
                            className="rounded px-1.5 py-0.5 truncate"
                            style={{ backgroundColor: 'var(--color-base)', color: 'var(--color-accent)' }}
                          >
                            {example}
                          </code>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="space-y-1.5">
                    <p className="font-medium" style={{ color: 'var(--color-foreground)' }}>
                      常用枚举
                    </p>
                    <div className="space-y-1">
                      {SCHEMA_ENUM_RULES.map(([label, values]) => (
                        <div key={label}>
                          <span style={{ color: 'var(--color-foreground)' }}>{label}：</span>
                          <span>{values}</span>
                        </div>
                      ))}
                    </div>
                  </section>

                  <section className="space-y-1.5">
                    <p className="font-medium" style={{ color: 'var(--color-foreground)' }}>
                      引用关系校验
                    </p>
                    <ul className="space-y-1">
                      {SCHEMA_REFERENCE_RULES.map((rule) => (
                        <li key={rule} className="flex gap-1.5">
                          <span style={{ color: 'var(--color-accent)' }}>•</span>
                          <span>{rule}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Editor area with line numbers */}
      <div className="flex flex-1 overflow-auto font-mono text-xs" style={{ lineHeight: '1.5' }}>
        {/* Line numbers */}
        <div
          className="shrink-0 text-right pr-2 select-none"
          style={{
            width: '40px',
            backgroundColor: 'var(--color-base)',
            color: 'var(--color-border)',
            borderRight: '1px solid var(--color-border)',
          }}
        >
          {lineInfos.map((info) => (
            <div
              key={info.lineNumber}
              className="px-1"
              style={{
                color: info.error
                  ? info.error.severity === 'error'
                    ? 'var(--color-warning)'
                    : 'var(--color-accent)'
                  : 'var(--color-border)',
                backgroundColor: info.error
                  ? info.error.severity === 'error'
                    ? 'oklch(0.65 0.18 25 / 0.1)'
                    : 'oklch(0.75 0.15 75 / 0.05)'
                  : undefined,
              }}
            >
              {info.lineNumber}
            </div>
          ))}
        </div>

        {/* Code content */}
        <div className="flex-1 relative">
          <textarea
            className="w-full h-full p-2 resize-none text-xs font-mono"
            style={{
              backgroundColor: 'var(--color-base)',
              color: 'var(--color-foreground)',
              border: 'none',
              outline: 'none',
              lineHeight: '1.5',
              tabSize: 2,
            }}
            value={yamlContent}
            onChange={(e) => handleChange(e.target.value)}
            spellCheck={false}
          />
        </div>
      </div>

      {/* Error list at bottom */}
      {yamlErrors.length > 0 && (
        <div
          className="shrink-0 border-t overflow-auto max-h-24"
          style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-surface)' }}
        >
          {yamlErrors.map((error, index) => (
            <div
              key={index}
              className="flex items-center gap-2 px-3 py-1 text-xs"
              style={{
                color: error.severity === 'error' ? 'var(--color-warning)' : 'var(--color-accent)',
              }}
            >
              <AlertCircle size={12} />
              <span>
                行 {error.line}, 列 {error.column}: {error.message}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!yamlContent && (
        <div className="flex items-center justify-center flex-1" style={{ color: 'var(--color-muted)' }}>
          <div className="text-center">
            <FileText size={24} className="mb-2 mx-auto" style={{ color: 'var(--color-border)' }} />
            {isLoading ? (
              <p className="text-xs">正在加载项目数据...</p>
            ) : (
              <>
                <p className="text-xs mb-1">暂无剧本数据可显示</p>
                <p className="text-xs" style={{ color: 'var(--color-border)' }}>
                  请先创建项目并运行改编流程，或等待章节数据加载完成
                </p>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
