'use client';

import React, { useState } from 'react';
import { BookOpen, Code, FileText, GitBranch, Link2, ShieldCheck } from 'lucide-react';

type DocumentationTab = 'schema' | 'reason';

const TOP_LEVEL_SCHEMA = [
  {
    name: 'schema_version',
    type: 'string',
    required: '是',
    description: 'Schema 版本号，遵循语义化版本，用于判断数据结构是否兼容。',
    fields: ['例如 "1.0.0"', '正则 ^\\d+\\.\\d+\\.\\d+$'],
  },
  {
    name: 'project',
    type: 'object',
    required: '是',
    description: '项目元信息，描述剧本标题、源语言、目标格式和改编风格。',
    fields: ['id', 'title', 'source_language', 'target_format', 'adaptation_style'],
  },
  {
    name: 'story_bible',
    type: 'object',
    required: '是',
    description: '故事圣经，集中定义角色、地点和时间线，供所有场景引用。',
    fields: ['characters', 'locations', 'timeline'],
  },
  {
    name: 'chapters',
    type: 'array',
    required: '是',
    description: '原文章节和段落结构，为场景和元素提供可追溯来源。',
    fields: ['id', 'order', 'title', 'paragraphs', 'summary'],
  },
  {
    name: 'scenes',
    type: 'array',
    required: '是',
    description: '剧本核心产物，承载场景标题、戏剧目的、冲突、节拍和剧本元素。',
    fields: ['heading', 'dramatic_purpose', 'conflict', 'characters', 'beats', 'elements'],
  },
  {
    name: 'metadata',
    type: 'object',
    required: '是',
    description: '生成元数据，记录生成时间、模型、章节数、场景数和元素数。',
    fields: ['generated_at', 'model', 'source_chapter_count', 'total_scenes', 'total_elements'],
  },
];

const ID_RULES = [
  ['角色', 'char_数字', 'char_1'],
  ['地点', 'loc_数字', 'loc_1'],
  ['时间线', 'tl_数字', 'tl_1'],
  ['章节', 'ch_数字', 'ch_1'],
  ['段落', 'p_章节_段落', 'p_1_3'],
  ['场景', 'sc_数字', 'sc_1'],
  ['元素', 'el_数字', 'el_1'],
];

const ENUM_RULES = [
  ['characters[].role', 'protagonist / supporting / antagonist / extra'],
  ['locations[].type', 'interior / exterior / mixed / unknown'],
  ['heading.context', 'INT / EXT / INT.EXT'],
  ['heading.time_of_day', 'DAY / NIGHT / DUSK / DAWN / UNKNOWN'],
  ['elements[].type', 'action / dialogue / parenthetical / transition / voice_over / shot / note'],
  ['relationships[].type', 'family / friend / enemy / lover / colleague / mentor / subordinate / other'],
  ['project.target_format', 'screenplay / teleplay / stage_play / animation_script'],
  ['adaptation_style.dialogue_style', 'natural / stylized / terse / verbose / poetic'],
];

const REFERENCE_RULES = [
  'scenes[].characters[] 必须引用 story_bible.characters[].id',
  'scenes[].heading.location_id 必须引用 story_bible.locations[].id',
  'scenes[].chapter_ids[] 必须引用 chapters[].id',
  'scenes[].source_refs[].paragraph_ids[] 必须引用对应章节的 paragraphs[].id',
  'elements[].character_id 必须引用 story_bible.characters[].id',
  'timeline[].chapter_id 必须引用 chapters[].id',
  'timeline[].affected_characters[] 必须引用 story_bible.characters[].id',
  'characters[].relationships[].character_id 必须引用其他已定义角色',
];

const DESIGN_REASONS = [
  {
    title: '为什么选择 YAML',
    body: 'YAML 的缩进结构比 JSON 更适合长文本审校，也比 Fountain 更能承载角色、地点、时间线和来源追踪。它既方便作者直接阅读和编辑，也能被程序解析后用 JSON Schema 或 Pydantic 校验。',
  },
  {
    title: '为什么要有 schema_version',
    body: '剧本数据结构会随着项目演进发生变化。版本号让前端、后端和导出工具能判断当前文件是否兼容，避免把旧结构误按新结构解析。',
  },
  {
    title: '为什么要有 project',
    body: '剧本不是孤立文本，它服务于某个改编目标。project 集中记录标题、源语言、目标格式和风格约束，让 AI 生成、人工审校和导出流程都能围绕同一组项目目标工作。',
  },
  {
    title: '为什么要有 story_bible',
    body: '小说转剧本最容易出现跨章节不一致：同一角色多个名字、地点描述前后矛盾、事件顺序混乱。story_bible 用集中定义和 ID 引用解决这个问题。',
  },
  {
    title: '为什么角色和地点使用 ID 引用',
    body: '如果场景里直接写角色名，角色改名时所有场景都要改。使用 char_1、loc_1 这类稳定 ID 后，只需在 story_bible 中改一次显示名称，所有引用仍然有效。',
  },
  {
    title: '为什么保留 chapters 和 paragraphs',
    body: '改编后的场景需要能回到原文。chapters 和 paragraphs 保留原文结构，source_refs 才能准确指向某章某段，降低 AI 凭空扩写或遗漏原文信息的风险。',
  },
  {
    title: '为什么 scenes 是核心',
    body: '剧本不是小说摘要，而是场景化叙事。scenes 把段落式叙事重组为可拍摄、可编辑、可导出的戏剧单元。',
  },
  {
    title: '为什么场景必须有 dramatic_purpose',
    body: 'dramatic_purpose 要求每个场景说明它为什么存在：推动什么情节、揭示什么人物、建立什么氛围。没有戏剧目的的场景很容易变成流水账。',
  },
  {
    title: '为什么保留 conflict',
    body: '冲突是戏剧驱动力。把 conflict 做成显式字段，是为了提醒生成和审校都关注场景内部的对抗、阻碍或选择压力。',
  },
  {
    title: '为什么使用 beats',
    body: 'beats 是场景内部节奏骨架。它帮助作者快速判断场景有没有起承转合，也方便后续局部重写、节奏调整和表演指导。',
  },
  {
    title: '为什么 elements 使用统一数组',
    body: '剧本阅读是线性的。动作、对白、旁白、转场按顺序放在 elements 中，能保留真实阅读顺序，也方便导出 Fountain、Markdown 或做单句改写。',
  },
  {
    title: '为什么 metadata 必不可少',
    body: 'AI 生成内容需要可追溯。metadata 记录模型、生成时间、章节数、场景数和元素数，便于审计、排错、版本比较和质量统计。',
  },
];

const MINIMAL_EXAMPLE = `schema_version: "1.0.0"
project:
  id: "proj_001"
  title: "雨夜来信"
  source_language: "zh-CN"
  target_format: "screenplay"

story_bible:
  characters:
    - id: "char_1"
      name: "沈默"
      role: "protagonist"
  locations:
    - id: "loc_1"
      name: "沈默老宅"
      type: "mixed"
  timeline:
    - id: "tl_1"
      chapter_id: "ch_1"
      sequence: 1
      event_summary: "沈默收到神秘来信。"

chapters:
  - id: "ch_1"
    order: 1
    paragraphs:
      - id: "p_1_1"
        index: 1
        text: "秋雨从黄昏开始落下。"

scenes:
  - id: "sc_1"
    chapter_ids: ["ch_1"]
    source_refs:
      - chapter_id: "ch_1"
        paragraph_ids: ["p_1_1"]
    heading:
      context: "INT"
      location_id: "loc_1"
      time_of_day: "NIGHT"
    title: "雨夜老宅"
    dramatic_purpose: "建立悬疑氛围。"
    conflict: "沈默想回避过去，但来信迫使他面对旧事。"
    characters: ["char_1"]
    beats:
      - description: "沈默发现信封。"
    elements:
      - id: "el_1"
        type: "action"
        text: "老宅内灯光昏黄，雨声压过钟声。"

metadata:
  generated_at: "2026-06-07T20:00:00+08:00"
  model: "gpt-5.5"
  source_chapter_count: 3
  total_scenes: 1
  total_elements: 1`;

export default function DocumentationPanel() {
  const [activeTab, setActiveTab] = useState<DocumentationTab>('schema');

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b p-3" style={{ borderColor: 'var(--color-border)' }}>
        <h3 className="flex items-center gap-1 text-sm font-semibold" style={{ color: 'var(--color-accent)' }}>
          <FileText size={14} />
          说明文档
        </h3>
        <div className="mt-2 grid grid-cols-2 gap-1 rounded p-1" style={{ backgroundColor: 'var(--color-base)' }}>
          <button
            type="button"
            onClick={() => setActiveTab('schema')}
            className="rounded px-2 py-1.5 text-xs font-medium transition-colors"
            style={{
              backgroundColor: activeTab === 'schema' ? 'var(--color-accent)' : 'transparent',
              color: activeTab === 'schema' ? 'var(--color-base)' : 'var(--color-muted)',
            }}
          >
            YAML Schema
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('reason')}
            className="rounded px-2 py-1.5 text-xs font-medium transition-colors"
            style={{
              backgroundColor: activeTab === 'reason' ? 'var(--color-accent)' : 'transparent',
              color: activeTab === 'reason' ? 'var(--color-base)' : 'var(--color-muted)',
            }}
          >
            Schema 设计原因
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-3">
        {activeTab === 'schema' ? <YamlSchemaDoc /> : <SchemaReasonDoc />}
      </div>
    </div>
  );
}

function YamlSchemaDoc() {
  return (
    <div className="space-y-4 text-xs leading-6" style={{ color: 'var(--color-label)' }}>
      <DocIntro
        icon={<Code size={16} />}
        title="剧本 YAML Schema"
        body="这份 Schema 定义小说转剧本后 YAML 必须遵守的字段结构、类型、必填规则、枚举值、ID 格式和引用关系。完整机器校验文件位于 apps/api/app/schemas/screenplay.schema.json。"
      />

      <DocSection title="顶层结构">
        <div className="space-y-2">
          {TOP_LEVEL_SCHEMA.map((item) => (
            <div key={item.name} className="rounded border p-2" style={{ borderColor: 'var(--color-border-subtle)', backgroundColor: 'var(--color-base)' }}>
              <div className="flex flex-wrap items-center gap-1.5">
                <code style={{ color: 'var(--color-accent)' }}>{item.name}</code>
                <span className="badge badge-muted">{item.type}</span>
                <span className="badge badge-accent">必填：{item.required}</span>
              </div>
              <p className="mt-1">{item.description}</p>
              <p className="mt-1">
                关键字段：{item.fields.join(' / ')}
              </p>
            </div>
          ))}
        </div>
      </DocSection>

      <DocSection title="ID 格式">
        <div className="grid grid-cols-1 gap-1">
          {ID_RULES.map(([label, rule, example]) => (
            <div key={label} className="grid grid-cols-[48px_minmax(0,1fr)] gap-2">
              <span style={{ color: 'var(--color-foreground)' }}>{label}</span>
              <span>
                {rule}，例如 <code style={{ color: 'var(--color-accent)' }}>{example}</code>
              </span>
            </div>
          ))}
        </div>
      </DocSection>

      <DocSection title="常用枚举">
        <div className="space-y-1">
          {ENUM_RULES.map(([field, values]) => (
            <div key={field}>
              <code style={{ color: 'var(--color-accent)' }}>{field}</code>
              <span>：{values}</span>
            </div>
          ))}
        </div>
      </DocSection>

      <DocSection title="引用关系">
        <ul className="space-y-1">
          {REFERENCE_RULES.map((rule) => (
            <li key={rule} className="flex gap-1.5">
              <Link2 size={12} className="mt-1 shrink-0" style={{ color: 'var(--color-accent)' }} />
              <span>{rule}</span>
            </li>
          ))}
        </ul>
      </DocSection>

      <DocSection title="最小完整示例">
        <pre
          className="overflow-auto rounded p-2 text-[11px] leading-5"
          style={{ backgroundColor: 'var(--color-base)', color: 'var(--color-foreground)' }}
        >
          <code>{MINIMAL_EXAMPLE}</code>
        </pre>
      </DocSection>
    </div>
  );
}

function SchemaReasonDoc() {
  return (
    <div className="space-y-4 text-xs leading-6" style={{ color: 'var(--color-label)' }}>
      <DocIntro
        icon={<ShieldCheck size={16} />}
        title="Schema 设计原因"
        body="这个 Schema 的核心目标是让 AI 输出稳定、让作者可以审校、让系统可以校验、让剧本内容可以追溯到原文。它不是为了形式复杂，而是为了让小说改编结果能继续编辑和交付。"
      />

      <DocSection title="核心目标">
        <div className="space-y-1">
          <ReasonPoint title="完整性" body="要求关键对象和字段必须存在，避免 AI 只输出零散自然语言。" />
          <ReasonPoint title="一致性" body="角色、地点、时间线集中定义，场景里只引用 ID，减少跨章节矛盾。" />
          <ReasonPoint title="可追溯性" body="场景和元素保留 source_refs，方便回查原文段落。" />
          <ReasonPoint title="可编辑性" body="每个角色、地点、场景和元素都有稳定 ID，支持局部修改和局部再生成。" />
          <ReasonPoint title="可导出性" body="结构稳定后，可以可靠转换为 YAML、JSON、Markdown、Fountain 和说明文档包。" />
        </div>
      </DocSection>

      <DocSection title="字段设计原因">
        <div className="space-y-2">
          {DESIGN_REASONS.map((item) => (
            <ReasonPoint key={item.title} title={item.title} body={item.body} />
          ))}
        </div>
      </DocSection>

      <DocSection title="Schema-first 工作流">
        <div className="space-y-1">
          {[
            '先定义章节、角色、地点、时间线和场景结构。',
            '再让 AI 按结构填充内容，而不是自由发挥输出长文。',
            '生成后执行字段、枚举、引用和业务规则校验。',
            '作者在编辑器里审校 YAML、剧本预览和故事圣经。',
            '最后导出为剧本文件或说明文档包。',
          ].map((text, index) => (
            <div key={text} className="flex gap-2">
              <span className="shrink-0 font-semibold" style={{ color: 'var(--color-accent)' }}>
                {index + 1}.
              </span>
              <span>{text}</span>
            </div>
          ))}
        </div>
      </DocSection>

      <DocSection title="文档与校验文件">
        <p>
          前端说明文档展示的是面向用户阅读的结构化说明。完整长文档在 <code>docs/YAML_SCREENPLAY_SCHEMA.md</code> 和 <code>docs/SCHEMA.md</code>，机器校验文件在 <code>apps/api/app/schemas/screenplay.schema.json</code>。
        </p>
      </DocSection>
    </div>
  );
}

function DocIntro({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="rounded border p-3" style={{ borderColor: 'var(--color-border)', backgroundColor: 'var(--color-base)' }}>
      <h4 className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--color-foreground)' }}>
        <span style={{ color: 'var(--color-accent)' }}>{icon}</span>
        {title}
      </h4>
      <p className="mt-2">{body}</p>
    </div>
  );
}

function DocSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h4 className="flex items-center gap-1 text-sm font-semibold" style={{ color: 'var(--color-accent)' }}>
        <BookOpen size={13} />
        {title}
      </h4>
      {children}
    </section>
  );
}

function ReasonPoint({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded border p-2" style={{ borderColor: 'var(--color-border-subtle)', backgroundColor: 'var(--color-base)' }}>
      <div className="flex items-center gap-1.5 font-semibold" style={{ color: 'var(--color-foreground)' }}>
        <GitBranch size={12} style={{ color: 'var(--color-accent)' }} />
        {title}
      </div>
      <p className="mt-1">{body}</p>
    </div>
  );
}
