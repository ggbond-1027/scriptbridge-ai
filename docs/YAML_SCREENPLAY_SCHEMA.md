# 剧本 YAML Schema 定义与设计说明

## 1. Schema 是什么

Schema 可以理解为一份“数据结构规则书”。

它不负责存储具体内容，而是规定一份数据应该长什么样。例如：

- 必须有哪些字段；
- 每个字段是什么类型；
- 哪些字段可以为空，哪些不能为空；
- 某些字段只能从固定选项中选择；
- 不同字段之间是否存在引用关系；
- 数据是否满足业务规则。

如果把一份 YAML 或 JSON 文件看成一张表单，那么 Schema 就是这张表单的填写规则。

例如，剧本中的一个角色对象可以被 Schema 规定为：

```yaml
id: "char_1"        # 必填，字符串，格式必须是 char_数字
name: "沈默"        # 必填，字符串
role: "protagonist" # 必填，只能是 protagonist/supporting/antagonist/extra 之一
```

如果缺少 `name`，或者 `role` 写成了 Schema 未允许的值，校验器就可以判断这份数据不合格。

## 2. YAML Schema 是什么

YAML Schema 是针对 YAML 数据定义的一套结构规则。

YAML 是一种数据书写格式，特点是可读性强，适合人类编辑；Schema 是规则；YAML Schema 就是“这份 YAML 文件应该遵守什么结构和约束”。

在实际工程中，YAML 通常会先被解析成普通数据对象，然后使用 JSON Schema、Pydantic、Ajv 等工具进行校验。因此，所谓 YAML Schema 往往不是一种全新的语法，而是“用于校验 YAML 内容的数据结构规范”。

本项目中的剧本 YAML Schema 指的是：

> 将三章以上小说文本自动转换为结构化剧本 YAML 时，输出 YAML 必须遵守的字段结构、类型约束、引用关系和业务规则。

## 3. Schema 与 YAML Schema 的区别

| 概念 | 含义 | 关注点 | 示例 |
|---|---|---|---|
| Schema | 泛指数据规则 | 数据应该有哪些字段、类型、约束 | “角色必须有 id/name/role” |
| YAML | 一种数据格式 | 如何把数据写得易读 | `name: "沈默"` |
| YAML Schema | 面向 YAML 文件的 Schema | YAML 内容是否符合预期结构 | “这个剧本 YAML 是否有 project/story_bible/scenes” |
| JSON Schema | 一种具体的 Schema 规范 | 用 JSON 格式描述数据规则，可用于校验 JSON，也常用于校验 YAML 解析后的数据 | `type: object`, `required: [...]` |

简单说：

- Schema 是规则本身；
- YAML 是承载数据的格式；
- YAML Schema 是用于约束 YAML 数据的规则；
- JSON Schema 是常用的机器可执行 Schema 表达方式。

## 4. 剧本 YAML Schema 的目标

该 Schema 服务于“小说转剧本”的自动化流程，目标是将三章以上的小说文本转换为可编辑、可追溯、可校验、可继续打磨的结构化剧本初稿。

核心目标包括：

1. 保证 AI 输出稳定，不是随意的自然语言文本。
2. 保留小说原文章节和段落来源，方便作者回查。
3. 抽取统一的角色、地点和时间线，减少跨章节不一致。
4. 将小说叙事重组为剧本场景。
5. 将每个场景拆成动作、对白、旁白、转场等剧本元素。
6. 支持后续导出为 YAML、JSON、Markdown、Fountain 等格式。
7. 支持程序自动校验，发现缺字段、引用错误和结构错误。

## 5. 顶层结构定义

剧本 YAML 的顶层结构包含六个字段：

```yaml
schema_version: "1.0.0"

project:
  # 项目信息

story_bible:
  # 故事圣经：角色、地点、时间线

chapters:
  # 原小说章节与段落结构

scenes:
  # 改编后的剧本场景

metadata:
  # 生成元数据
```

### 5.1 schema_version

`schema_version` 用于标识当前剧本数据遵守的 Schema 版本。

```yaml
schema_version: "1.0.0"
```

设计原因：

- 方便未来升级字段结构；
- 让程序在读取 YAML 前判断是否兼容；
- 避免不同版本的数据被错误解析。

### 5.2 project

`project` 记录项目级元信息，包括标题、语言、目标格式和改编风格。

```yaml
project:
  id: "proj_001"
  title: "雨夜来信"
  source_language: "zh-CN"
  target_format: "screenplay"
  adaptation_style:
    genre:
      - "悬疑"
    tone:
      - "紧张"
      - "冷峻"
    dialogue_style: "natural"
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | 是 | 项目唯一 ID |
| `title` | string | 是 | 改编后剧本标题 |
| `source_language` | string | 是 | 原小说语言 |
| `target_format` | string | 是 | 输出目标，如 `screenplay` |
| `adaptation_style` | object | 否 | 类型、基调、对白风格 |

设计原因：

- 将改编目标集中存放，避免每个场景重复描述；
- 为 AI 生成提供统一风格约束；
- 为后续导出和项目管理提供基础信息。

### 5.3 story_bible

`story_bible` 是故事圣经，集中定义角色、地点和时间线。

```yaml
story_bible:
  characters:
    - id: "char_1"
      name: "沈默"
      aliases:
        - "沈警官"
      role: "protagonist"
      description: "刑侦警官，冷静、克制，正在调查一封神秘来信。"
      goals:
        - "查清来信来源"
      personality:
        - "冷静"
        - "执拗"

  locations:
    - id: "loc_1"
      name: "沈默老宅"
      type: "mixed"
      description: "江南古镇巷尾的一座老宅。"
      atmosphere: "阴冷、潮湿、压抑"

  timeline:
    - id: "tl_1"
      chapter_id: "ch_1"
      sequence: 1
      event_summary: "沈默在雨夜收到神秘来信。"
      affected_characters:
        - "char_1"
```

设计原因：

- 小说转剧本经常出现角色名称混乱、地点描述不一致、时间线错乱；
- 使用 `story_bible` 统一注册角色和地点；
- 场景中只引用 `char_1`、`loc_1` 这类 ID，而不是直接复制名称；
- 角色改名时只需修改一处，所有场景引用保持稳定。

### 5.4 chapters

`chapters` 保存原小说的章节和段落结构。

```yaml
chapters:
  - id: "ch_1"
    order: 1
    title: "旧宅来信"
    source_title: "第一章 旧宅来信"
    paragraphs:
      - id: "p_1_1"
        index: 1
        text: "秋雨从黄昏开始落下，到深夜仍未停歇。"
        char_start: 0
        char_end: 21
    summary: "主角在雨夜收到一封来历不明的信。"
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | 是 | 章节 ID，如 `ch_1` |
| `order` | integer | 是 | 章节顺序，从 1 开始 |
| `title` | string | 是 | 改编后章节标题 |
| `source_title` | string | 否 | 原小说章节标题 |
| `paragraphs` | array | 是 | 原文段落列表 |
| `summary` | string | 是 | 章节摘要 |

设计原因：

- 保留原文结构，方便作者对照；
- 每个段落都有 ID，供场景和剧本元素引用；
- `char_start` 和 `char_end` 可用于精确定位原文位置；
- 为“剧本内容是否忠实原文”提供追溯依据。

### 5.5 scenes

`scenes` 是剧本的核心输出。小说段落会被重组为一个个剧本场景。

```yaml
scenes:
  - id: "sc_1"
    chapter_ids:
      - "ch_1"
    source_refs:
      - chapter_id: "ch_1"
        paragraph_ids:
          - "p_1_1"
    heading:
      context: "INT"
      location_id: "loc_1"
      time_of_day: "NIGHT"
    title: "雨夜老宅"
    dramatic_purpose: "建立悬疑氛围，并引出神秘来信。"
    conflict: "沈默想回避旧事，但来信迫使他重新面对过去。"
    characters:
      - "char_1"
    beats:
      - description: "沈默站在窗前听雨。"
        emotional_arc: "平静到不安"
        key_action: "发现门缝下的信"
    elements:
      - id: "el_1"
        type: "action"
        text: "雨水顺着老宅屋檐落下，屋内只有一盏昏黄台灯。"
        source_ref:
          chapter_id: "ch_1"
          paragraph_ids:
            - "p_1_1"
      - id: "el_2"
        type: "dialogue"
        character_id: "char_1"
        text: "谁会在这个时候送信？"
        emotion: "警觉"
        source_ref:
          chapter_id: "ch_1"
          paragraph_ids:
            - "p_1_1"
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | 是 | 场景 ID，如 `sc_1` |
| `chapter_ids` | array | 是 | 该场景对应的原文章节 |
| `source_refs` | array | 是 | 该场景来源段落 |
| `heading` | object | 是 | 场景标题行信息 |
| `title` | string | 是 | 场景标题 |
| `dramatic_purpose` | string | 是 | 戏剧目的 |
| `conflict` | string | 否 | 场景冲突 |
| `characters` | array | 是 | 出场角色 ID |
| `beats` | array | 是 | 场景节拍 |
| `elements` | array | 是 | 剧本正文元素 |

设计原因：

- 剧本不是小说摘要，而是由场景推动；
- `heading` 对应影视剧本中的场景标题行；
- `dramatic_purpose` 强制每个场景说明“为什么存在”；
- `conflict` 强化戏剧驱动力；
- `beats` 帮助作者快速判断场景内部节奏；
- `elements` 用线性数组保存动作、对白、旁白等，符合剧本阅读顺序。

### 5.6 elements

`elements` 表示剧本正文中的最小可编辑单元。

常用类型包括：

| type | 含义 |
|---|---|
| `action` | 动作描写 |
| `dialogue` | 角色对白 |
| `parenthetical` | 括号提示 |
| `transition` | 转场 |
| `voice_over` | 画外音或旁白 |
| `shot` | 镜头指示 |
| `note` | 编剧备注 |

设计原因：

- 不把对白、动作、旁白拆成多个分散数组，而是统一放入 `elements`；
- 保持剧本天然的线性阅读顺序；
- 局部改写时可以只重写某一个元素；
- 导出 Fountain、Markdown 时可以按顺序遍历转换。

### 5.7 metadata

`metadata` 记录生成过程信息。

```yaml
metadata:
  generated_at: "2026-06-07T20:00:00+08:00"
  model: "gpt-5.5"
  source_chapter_count: 3
  total_scenes: 12
  total_elements: 180
```

设计原因：

- 记录生成时间和模型，便于审计；
- 记录源章节数，确保满足三章以上要求；
- 记录场景数和元素数，便于快速检查输出规模；
- 后续可以用于质量统计和版本追踪。

## 6. 核心校验规则

本 Schema 应至少支持以下校验规则。

### 6.1 基础结构校验

- 顶层必须包含 `schema_version`、`project`、`story_bible`、`chapters`、`scenes`、`metadata`；
- `chapters` 至少包含 3 个章节；
- `scenes` 至少包含 1 个场景；
- 每个场景至少包含 1 个 `beat` 和 1 个 `element`；
- 必填字段不能为空字符串。

### 6.2 ID 格式校验

| 对象 | ID 格式 | 示例 |
|---|---|---|
| 角色 | `char_数字` | `char_1` |
| 地点 | `loc_数字` | `loc_1` |
| 时间线事件 | `tl_数字` | `tl_1` |
| 章节 | `ch_数字` | `ch_1` |
| 段落 | `p_章节序号_段落序号` | `p_1_3` |
| 场景 | `sc_数字` | `sc_1` |
| 元素 | `el_数字` | `el_1` |

### 6.3 引用一致性校验

- `scenes[].chapter_ids[]` 必须指向已存在的 `chapters[].id`；
- `scenes[].source_refs[].paragraph_ids[]` 必须指向对应章节中的段落 ID；
- `scenes[].heading.location_id` 必须指向已存在的 `story_bible.locations[].id`；
- `scenes[].characters[]` 必须指向已存在的 `story_bible.characters[].id`；
- `elements[].character_id` 必须指向已存在的角色 ID；
- `timeline[].chapter_id` 必须指向已存在的章节 ID；
- `timeline[].affected_characters[]` 必须指向已存在的角色 ID。

### 6.4 业务规则校验

- `metadata.source_chapter_count` 应等于 `chapters.length`；
- `metadata.source_chapter_count` 必须大于或等于 3；
- `metadata.total_scenes` 应等于 `scenes.length`；
- `metadata.total_elements` 应等于所有场景 `elements.length` 的总和；
- `dialogue` 和 `voice_over` 类型元素应包含 `character_id`；
- 每个场景必须有明确的 `dramatic_purpose`；
- 每个场景建议包含 `conflict`，否则容易变成流水账式摘要。

## 7. 为什么选择 YAML

本项目选择 YAML 作为剧本初稿格式，而不是只使用 JSON 或纯文本，原因如下。

| 格式 | 优点 | 局限 |
|---|---|---|
| YAML | 可读性强，适合人工编辑，结构清晰 | 对缩进敏感，需要 Schema 校验 |
| JSON | 机器友好，校验工具成熟 | 长文本中花括号和引号较多，不适合作者直接编辑 |
| Fountain | 接近行业剧本格式 | 结构化能力弱，不适合角色、地点、时间线和来源追踪 |
| Markdown | 阅读友好 | 结构约束弱，难以稳定校验 |

YAML 的价值在于同时兼顾作者和程序：

- 作者可以直接读懂和修改；
- 程序可以解析、校验、导出；
- AI 可以按固定结构生成；
- 后续可以转换成 JSON、Markdown、Fountain 等格式。

## 8. Schema-first 的设计原因

本项目采用 Schema-first 思路，即先定义结构，再让 AI 填充内容。

这样做有几个直接好处：

1. 输出稳定：AI 不会每次换一种格式。
2. 易于校验：缺字段、类型错误、引用错误可以被程序发现。
3. 易于编辑：作者知道每个字段应该填什么。
4. 易于追溯：每个场景和元素都能回到原文章节与段落。
5. 易于导出：结构稳定后，可以可靠转换成其他剧本格式。
6. 易于局部重写：修改某句对白或某个场景时，不需要重生成整篇剧本。

## 9. 推荐转换流程

从三章以上小说文本到剧本 YAML，推荐使用以下流程：

1. 章节识别：将小说拆成 `chapters`。
2. 段落编号：为每章段落生成 `p_章节_段落` ID。
3. 故事理解：抽取角色、地点和关键事件，生成 `story_bible`。
4. 场景规划：把小说叙事拆成剧本场景，生成 `scenes` 的骨架。
5. 剧本生成：为每个场景生成 `beats` 和 `elements`。
6. 来源绑定：为场景和元素补充 `source_refs`。
7. Schema 校验：检查字段、类型、枚举、引用和业务规则。
8. 人工打磨：作者在 YAML 编辑器中继续修改。
9. 格式导出：导出为 YAML、JSON、Markdown、Fountain 或 ZIP。

## 10. 最小完整示例

下面是一个简化示例，展示三章小说转换后的剧本 YAML 骨架。

```yaml
schema_version: "1.0.0"

project:
  id: "proj_001"
  title: "雨夜来信"
  source_language: "zh-CN"
  target_format: "screenplay"
  adaptation_style:
    genre:
      - "悬疑"
    tone:
      - "紧张"
    dialogue_style: "natural"

story_bible:
  characters:
    - id: "char_1"
      name: "沈默"
      role: "protagonist"
      description: "刑侦警官，正在调查一封神秘来信。"
  locations:
    - id: "loc_1"
      name: "沈默老宅"
      type: "mixed"
      description: "江南古镇巷尾的一座老宅。"
  timeline:
    - id: "tl_1"
      chapter_id: "ch_1"
      sequence: 1
      event_summary: "沈默收到神秘来信。"
      affected_characters:
        - "char_1"

chapters:
  - id: "ch_1"
    order: 1
    title: "旧宅来信"
    paragraphs:
      - id: "p_1_1"
        index: 1
        text: "秋雨从黄昏开始落下，到深夜仍未停歇。"
        char_start: 0
        char_end: 21
    summary: "沈默收到一封来历不明的信。"
  - id: "ch_2"
    order: 2
    title: "密室旧档"
    paragraphs:
      - id: "p_2_1"
        index: 1
        text: "他在祖父的密室里发现一份旧档案。"
        char_start: 22
        char_end: 40
    summary: "沈默发现旧案线索。"
  - id: "ch_3"
    order: 3
    title: "雨幕尽头"
    paragraphs:
      - id: "p_3_1"
        index: 1
        text: "雨幕深处，那个失踪多年的人影再次出现。"
        char_start: 41
        char_end: 61
    summary: "真相开始浮出水面。"

scenes:
  - id: "sc_1"
    chapter_ids:
      - "ch_1"
    source_refs:
      - chapter_id: "ch_1"
        paragraph_ids:
          - "p_1_1"
    heading:
      context: "INT"
      location_id: "loc_1"
      time_of_day: "NIGHT"
    title: "雨夜老宅"
    dramatic_purpose: "建立悬疑氛围，引出神秘来信。"
    conflict: "沈默想逃避过去，但来信迫使他重新面对旧事。"
    characters:
      - "char_1"
    beats:
      - description: "沈默听见门外传来信封落地的声音。"
        emotional_arc: "平静到警觉"
        key_action: "拾起信封"
    elements:
      - id: "el_1"
        type: "action"
        text: "老宅内灯光昏黄，雨声压过墙上老钟的滴答声。"
        source_ref:
          chapter_id: "ch_1"
          paragraph_ids:
            - "p_1_1"
      - id: "el_2"
        type: "dialogue"
        character_id: "char_1"
        text: "谁会在这个时候送信？"
        emotion: "警觉"
        source_ref:
          chapter_id: "ch_1"
          paragraph_ids:
            - "p_1_1"

metadata:
  generated_at: "2026-06-07T20:00:00+08:00"
  model: "gpt-5.5"
  source_chapter_count: 3
  total_scenes: 1
  total_elements: 2
```

## 11. 与项目实现的关系

该文档是剧本 YAML Schema 的说明文档，面向作者、评审和开发者。

项目中的机器可执行 Schema 可放在：

```text
apps/api/app/schemas/screenplay.schema.json
```

实际运行时可以使用以下方式校验：

- 后端使用 Pydantic 校验 API 数据结构；
- 前端使用 Ajv 校验 YAML 编辑结果；
- 导出前再次执行引用一致性和业务规则校验。

这样可以形成“作者可读 YAML + 程序可校验 Schema + 可追溯剧本数据”的完整工作流。
