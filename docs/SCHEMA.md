# ScriptBridge Screenplay YAML Schema

## 目标

本 Schema 用于描述“小说改编后的结构化剧本资产”。它不是单纯的文本格式，而是让剧本可以被编辑、校验、追踪来源和导出到标准剧本格式。

Schema 文件：

- `schemas/screenplay.schema.json`

## 顶层结构

```yaml
schema_version: "1.0"
project: {}
story_bible: {}
chapters: []
scenes: []
metadata: {}
```

## 设计原则

1. 结构化优先  
   剧本必须拆成项目、故事圣经、章节、场景和剧本元素，避免大段文本不可编辑。

2. 可追踪优先  
   `source_refs` 让每个场景和元素都能回到小说原文段落，降低 AI 幻觉风险。

3. 可校验优先  
   JSON Schema 和后端引用校验共同保证 YAML 不是“看起来像 YAML”，而是可被程序读取的结构。

4. 可编辑优先  
   人物、地点、场景和元素都有稳定 `id`，方便局部编辑、全局重命名和局部再生成。

5. 可扩展优先  
   `schema_version`、`metadata` 和 `type` 枚举让后续支持短剧、广播剧、舞台剧、镜头脚本等扩展。

## 核心字段说明

| 字段 | 说明 | 设计原因 |
|---|---|---|
| `schema_version` | Schema 版本 | 支持未来升级和兼容 |
| `project` | 项目信息和改编风格 | 记录标题、语言、剧本类型、语气 |
| `story_bible.characters` | 人物表 | 保证跨章节人物一致 |
| `story_bible.locations` | 地点表 | 保证场景引用稳定 |
| `story_bible.timeline` | 时间线 | 保留故事推进顺序 |
| `chapters` | 原始章节结构 | 证明输入满足 3 章以上，并服务来源追踪 |
| `scenes` | 剧本场景数组 | 剧本核心结构 |
| `source_refs` | 来源段落引用 | 让用户检查每场来自哪里 |
| `dramatic_purpose` | 场景目的 | 避免流水账式改编 |
| `conflict` | 场景冲突 | 强化剧本性 |
| `elements` | 动作、对白、转场等元素 | 方便编辑和导出 |
| `metadata` | 生成信息 | 记录模型、provider、警告和输入章节数 |

## 剧本元素类型

| 类型 | 用途 |
|---|---|
| `action` | 动作和画面描述 |
| `dialogue` | 角色对白 |
| `parenthetical` | 括注 |
| `transition` | 转场 |
| `voice_over` | 旁白 |
| `shot` | 镜头提示 |
| `note` | 工作台内部备注 |

## 引用校验

除 JSON Schema 外，后端还会做引用一致性校验：

- `scene.heading.location_id` 必须存在于 `story_bible.locations`。
- `scene.characters` 必须存在于 `story_bible.characters`。
- `dialogue.character_id` 必须存在于 `story_bible.characters`。
- `source_refs.chapter_id` 必须存在于 `chapters`。
- `source_refs.paragraph_ids` 必须存在于对应章节段落。

## 示例

```yaml
schema_version: "1.0"
project:
  id: "proj_001"
  title: "雨夜来信"
  source_language: "zh-CN"
  target_format: "screenplay"
  adaptation_style:
    genre: "悬疑短剧"
    tone: "克制、紧张"
    dialogue_style: "自然"
story_bible:
  characters:
    - id: "char_001"
      name: "林舟"
      aliases: []
      role: "protagonist"
      description: "关键人物"
      goals: ["推动核心事件"]
      relationships: []
  locations:
    - id: "loc_001"
      name: "老宅书房"
      type: "interior"
      description: "承载关键线索的空间"
  timeline: []
chapters: []
scenes:
  - id: "sc_001"
    chapter_ids: ["ch_001"]
    source_refs:
      - chapter_id: "ch_001"
        paragraph_ids: ["p_001_001"]
    heading:
      context: "INT"
      location_id: "loc_001"
      time_of_day: "NIGHT"
    title: "发现匿名信"
    dramatic_purpose: "引出主线谜团"
    conflict: "林舟必须决定是否追查"
    characters: ["char_001"]
    beats: ["发现信件", "读到线索", "决定行动"]
    summary: "林舟在雨夜发现匿名信。"
    elements:
      - id: "el_001"
        type: "action"
        text: "雨声敲打窗棂。"
        source_refs:
          - chapter_id: "ch_001"
            paragraph_ids: ["p_001_001"]
metadata:
  generated_at: "2026-06-05T12:00:00Z"
  model: "fallback"
  provider: "fallback"
  provider_status: "fallback"
  source_chapter_count: 3
  warnings: []
```
