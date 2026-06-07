# NovelScripter 剧本 YAML Schema 设计说明

## 1. 引言与设计动机

### 1.1 为什么选择 YAML

NovelScripter 选择 YAML 作为剧本结构化输出的主要格式，而非 JSON、XML 或纯文本（Fountain），基于以下核心考量：

| 格式 | 可读性 | 结构化程度 | 编辑友好性 | AI 生成适配 | 人工审校适配 |
|------|--------|------------|------------|-------------|-------------|
| **YAML** | **极高** | **高** | **极高** | **高** | **极高** |
| JSON | 中 | 高 | 低 | 高 | 低 |
| XML | 低 | 高 | 低 | 中 | 低 |
| Fountain | 高 | 低 | 中 | 低 | 中 |

**YAML 的核心优势：**

1. **可读性优于 JSON**：YAML 的缩进式结构天然适合人类阅读和审校。剧本作为创意产出，需要编剧人工审校和调整，YAML 的格式让审校者无需工具辅助即可直观理解数据结构。JSON 的花括号和引号在长文档中极度干扰阅读。

2. **结构化优于 Fountain**：Fountain 是剧本行业标准格式，但它本质是纯文本标记，缺乏结构化的角色、地点、时间线管理能力。NovelScripter 需要保证跨章节角色一致性、地点引用一致性和时间线连贯性，这些需求要求结构化数据而非纯文本。

3. **编辑友好优于 XML**：XML 的标签冗余使得手动编辑极为繁琐。YAML 的极简标记（缩进 + 冒号 + 列表符号）让编剧可以快速定位和修改任何字段，而不需要在开闭标签之间寻找内容。

4. **AI 生成适配**：YAML 格式与大语言模型（LLM）的输出特性天然契合。LLM 生成长文本时倾向于自然语言式的排版，YAML 的缩进和列表风格比 JSON 的花括号嵌套更容易被模型稳定产出。

5. **YAML ↔ JSON 双向转换**：YAML 与 JSON 在数据模型层面完全等价，可以无损双向转换。这意味着同一 Schema 可以同时用于 YAML 输出（供人工审校）和 JSON 校验（供程序验证），实现"人读 YAML、机校 JSON"的协同工作流。

### 1.2 设计目标

NovelScripter 的 YAML Schema 设计围绕三个核心目标：

- **完整性**：保证 AI 生成结果包含所有必要字段，避免遗漏关键信息。
- **一致性**：通过引用机制（ID）和 story_bible 集中定义，保证跨章节的角色、地点、时间线引用一致，降低 AI 幻觉风险。
- **可校验性**：通过 JSON Schema + Pydantic Model + Ajv 三层校验机制，保证输出数据在任何环节都可被程序验证。

---

## 2. 与行业标准的关系

### 2.1 Fountain 标准映射

Fountain 是剧本创作领域广泛使用的纯文本标记标准。NovelScripter 的 YAML Schema 与 Fountain 标准之间存在明确的映射关系：

| YAML Schema 字段 | Fountain 对应元素 | 映射说明 |
|-------------------|-------------------|----------|
| `scenes[].heading` | Slug Line / Scene Heading | `context` + `location_id`（解析为地点名） + `time_of_day` → 组合为 Fountain 场景标题行，如 `INT. 沈默老宅密室 - 夜` |
| `elements[type=dialogue]` | Character + Dialogue | `character_id`（解析为角色名）居中大写 → 下一行对话文本 |
| `elements[type=parenthetical]` | Parenthetical | `parenthetical` 字段 → Fountain 括号提示 `(低声)` |
| `elements[type=action]` | Action | `text` 字段 → Fountain 动作描述行 |
| `elements[type=transition]` | Transition | `text` 字段 → Fountain 转场行（右对齐大写，如 `CUT TO:`） |
| `elements[type=voice_over]` | Character (V.O.) + Dialogue | `character_id` + `(V.O.)` → 画外音对话 |
| `elements[type=shot]` | Shot | `text` 字段 → Fountain 镜头指示行（大写） |
| `elements[type=note]` | Note / Comment | `text` 字段 → Fountain 注释 `[[注释内容]]` |
| `scenes[].title` | 无直接对应 | YAML 扩展字段，Fountain 中无场景标题概念 |
| `scenes[].dramatic_purpose` | 无直接对应 | YAML 独创字段，Fountain 中无戏剧目的记录 |
| `scenes[].conflict` | 无直接对应 | YAML 独创字段，Fountain 中无冲突描述 |
| `scenes[].beats` | 无直接对应 | YAML 独创字段，Fountain 中无节拍概念 |
| `story_bible` | 无直接对应 | YAML 独创字段，Fountain 不管理角色/地点/时间线 |

**关键差异**：Fountain 是面向**人类写作**的格式，侧重排版和阅读体验；NovelScripter 的 YAML Schema 是面向**AI 生成 + 人工审校**的格式，侧重结构化、可校验性和一致性管理。Fountain 可以从 YAML 无损导出，但 YAML 包含了 Fountain 无法表达的元数据（戏剧目的、冲突、节拍、溯源引用等）。

### 2.2 从 YAML 到 Fountain 的转换规则

1. 场景标题行：`heading.context + 解析(location_id) + "-" + heading.time_of_day 中文`，如 `INT. 沈默老宅密室 - 夜`
2. 角色名居中大写显示，括号提示紧跟其后
3. 对话文本居中偏左
4. 动作描述全宽度左对齐
5. 转场行右对齐大写
6. 注释使用 `[[...]]` 格式
7. 画外音角色名后加 `(V.O.)` / `(O.S.)`

---

## 3. 顶层结构

YAML Schema 定义六个顶层键，每个键承担明确的设计职责：

```
schema_version    ← 版本标识与兼容性控制
project           ← 项目元信息与改编风格指导
story_bible       ← 角色/地点/时间线集中定义
chapters          ← 原文章节结构与段落溯源
scenes            ← 剧本场景产出（核心数据）
metadata          ← 生成元数据与审计追溯
```

### 3.1 六个顶层键的设计动机

| 顶层键 | 设计动机 |
|--------|---------|
| `schema_version` | 版本控制是数据格式演进的基石。不同版本的 Schema 可能存在字段增删或语义变更，`schema_version` 使得消费者可以在解析前判断兼容性，避免因版本不一致导致的解析错误或数据丢失。 |
| `project` | 剧本不是孤立存在的——它从一个项目产生，服务于特定改编目标。`project` 将"改编什么、改编成什么、以什么风格改编"这些高层决策集中定义，使得 AI 在生成时可以参考这些指导，也使得审校者可以验证生成结果是否符合改编意图。 |
| `story_bible` | 这是最关键的顶层键。将角色、地点、时间线集中在一个"圣经"中定义，而非在每章每场景中分散描述，是为了保证**跨章节一致性**。AI 在生成多章节内容时极易出现角色名称不一致、地点描述矛盾等问题，story_bible 通过 ID 引用机制强制所有场景引用同一套角色/地点定义，消除一致性问题。 |
| `chapters` | 保留原文结构。`chapters` 将小说原文拆分为结构化段落（含字符偏移量），为 `scenes[].source_refs` 提供溯源锚点。没有 `chapters`，`source_refs` 就无法定位到具体段落，溯源校验就无法执行。 |
| `scenes` | 核心产出。小说转剧本的本质是将段落式的叙事重组为场景式的戏剧结构。`scenes` 是这一重组的结果，也是整个 Schema 最核心的数据。每个场景必须包含戏剧目的、冲突和节拍——这是区分"剧本"和"流水账"的根本标准。 |
| `metadata` | 审计追溯。AI 生成结果需要可追溯——谁生成、何时生成、用什么模型生成、从多少章源文本生成。`metadata` 提供了这些信息，使得在发现质量问题时可以回溯到具体的生成过程。 |

---

## 4. 字段定义详解

### 4.1 schema_version

| 属性 | 值 |
|------|-----|
| 名称 | `schema_version` |
| 类型 | `string` |
| 是否必填 | 是 |
| 默认值 | `"1.0.0"` |
| 约束 | 正则 `^\d+\.\d+\.\d+$`（语义化版本） |
| 语义含义 | Schema 的版本标识符，遵循 SemVer 规范 |
| 设计原因 | 数据格式必然随需求演进。版本号让消费者在解析前判断兼容性，避免因版本不一致导致的数据错误。语义化版本号便于人类理解版本间的关系（主版本变更=不兼容、次版本变更=向后兼容新增、修订号=向后兼容修复）。 |

### 4.2 project

| 属性 | 值 |
|------|-----|
| 名称 | `project` |
| 类型 | `object` |
| 是否必填 | 是 |
| 语义含义 | 项目元信息，定义剧本的来源、目标和风格 |

**子字段详解：**

| 子字段 | 类型 | 必填 | 默认值 | 语义含义 | 设计原因 |
|--------|------|------|--------|----------|----------|
| `id` | string | 是 | - | 项目唯一标识 | 跨系统引用和数据库索引的基础 |
| `title` | string | 是 | - | 剧本标题 | 1-256字符，标题是项目的外部标识 |
| `source_language` | string | 否 | `"zh-CN"` | 源文本语言 | BCP 47 规范，影响 AI 生成时的语言策略 |
| `target_format` | string | 否 | `"screenplay"` | 目标输出格式 | 不同格式影响场景标题、元素类型等规范 |
| `adaptation_style.genre` | string[] | 否 | - | 类型标签 | 多选，指导 AI 的整体改编方向 |
| `adaptation_style.tone` | string[] | 否 | - | 基调标签 | 多选，指导 AI 的情绪基调 |
| `adaptation_style.dialogue_style` | string | 否 | `"natural"` | 对话风格 | 枚举限制避免 AI 自由发挥导致风格不一致 |

### 4.3 story_bible

| 属性 | 值 |
|------|-----|
| 名称 | `story_bible` |
| 类型 | `object` |
| 是否必填 | 是 |
| 语义含义 | 故事圣经——角色、地点、时间线的集中定义 |
| 设计原因 | 保证跨章节一致性。AI 在生成多章节内容时极易出现角色名称不一致、地点描述矛盾、时间线错乱等问题。story_bible 通过 ID 引用机制强制所有场景引用同一套定义，消除一致性问题。这是"集中定义 + 引用机制"而非"分散定义"的核心设计选择。 |

**characters 子字段详解：**

| 子字段 | 类型 | 必填 | 默认值 | 语义含义 | 设计原因 |
|--------|------|------|--------|----------|----------|
| `id` | string(pattern `^char_\d+$`) | 是 | - | 角色唯一ID | 使用 ID 而非姓名引用角色，避免同名别名批量重命名问题。如果用姓名引用，当角色改名或出现同名不同人时，所有引用点都需要修改。ID 引用只改一处定义即可。 |
| `name` | string | 是 | - | 角色主要名称 | 剧本中默认显示名 |
| `aliases` | string[] | 否 | - | 别名列表 | 对话识别和角色追踪。角色可能在不同身份下使用不同称呼，aliases 让 AI 在对话中正确识别说话人。 |
| `role` | string(enum) | 是 | `"supporting"` | 角色类型 | protagonist/supporting/antagonist/extra。分类指导 AI 对角色投入不同篇幅和深度。 |
| `description` | string | 否 | - | 角色简介 | 涵盖背景、性格核心和故事定位 |
| `goals` | string[] | 否 | - | 目标/动机 | 驱动角色行为的核心动力，指导 AI 生成符合角色动机的对话和行动 |
| `personality` | string[] | 否 | - | 性格特征 | 标签式描述便于 AI 快速把握角色性格 |
| `appearance` | string | 否 | - | 外貌描写 | 用于动作描述和场景设定参考 |
| `first_appearance` | object | 否 | - | 首次出现位置 | 含 chapter_id 和 paragraph_id，校验角色出场顺序 |
| `relationships[].character_id` | string | 是 | - | 关联角色ID | 必须指向已定义角色，校验引用一致性 |
| `relationships[].type` | string(enum) | 是 | - | 关系类型 | 分类便于 AI 理解角色间关系 |
| `relationships[].description` | string | 是 | - | 关系描述 | 非空要求保证关系不只是标签，有具体语义 |

**locations 子字段详解：**

| 子字段 | 类型 | 必填 | 默认值 | 语义含义 | 设计原因 |
|--------|------|------|--------|----------|----------|
| `id` | string(pattern `^loc_\d+$`) | 是 | - | 地点唯一ID | 场景引用地点时保持一致。与角色 ID 同理，避免地点改名时的批量修改问题。 |
| `name` | string | 是 | - | 地点名称 | 场景标题行解析时使用 |
| `type` | string(enum) | 是 | `"unknown"` | 地点类型 | interior/exterior/mixed/unknown。影响场景标题行的 INT/EXT 判断。 |
| `description` | string | 否 | - | 详细描述 | AI 生成场景动作描写时参考 |
| `atmosphere` | string | 否 | - | 氛围关键词 | 指导 AI 生成场景氛围和情绪基调 |
| `first_appearance` | object | 否 | - | 首次出现位置 | 校验地点出场顺序 |

**timeline 子字段详解：**

| 子字段 | 类型 | 必填 | 默认值 | 语义含义 | 设计原因 |
|--------|------|------|--------|----------|----------|
| `id` | string(pattern `^tl_\d+$`) | 是 | - | 事件唯一ID | 引用基础 |
| `chapter_id` | string | 是 | - | 所属章节 | 关联到章节结构 |
| `sequence` | integer(≥1) | 是 | - | 章节内顺序 | 保证时间线事件的排列顺序 |
| `event_summary` | string | 是 | - | 事件摘要 | 非空保证摘要有实际内容 |
| `affected_characters` | string[] | 是 | - | 受影响角色 | 校验角色引用一致性 |

### 4.4 chapters

| 属性 | 值 |
|------|-----|
| 名称 | `chapters` |
| 类型 | `array` |
| 是否必填 | 是 |
| 语义含义 | 原文章节结构，保留段落内容和溯源信息 |
| 设计原因 | 为 `scenes[].source_refs` 提供溯源锚点。没有 chapters 的段落定义，source_refs 就无法精确定位到原文段落。char_start/char_end 字段提供字符级精度溯源，便于程序自动比对原文和生成内容。 |

**paragraphs 子字段详解：**

| 子字段 | 类型 | 必填 | 默认值 | 语义含义 | 设计原因 |
|--------|------|------|--------|----------|----------|
| `id` | string(pattern `^p_\d+_\d+$`) | 是 | - | 段落唯一ID | 格式 `p_{章节序号}_{段落序号}`，如 `p_1_3`。source_refs 使用此ID定位段落。 |
| `index` | integer(≥1) | 是 | - | 段落序号 | 保证段落排列顺序 |
| `text` | string | 是 | - | 段落原文 | 保留原文供溯源比对 |
| `char_start` | integer(≥0) | 是 | - | 起始字符偏移 | 精确溯源，程序可以自动定位到原文中的确切位置 |
| `char_end` | integer(≥0) | 是 | - | 结束字符偏移 | 与 char_start 配合构成精确溯源范围 |

### 4.5 scenes

| 属性 | 值 |
|------|-----|
| 名称 | `scenes` |
| 类型 | `array` |
| 是否必填 | 是 |
| 语义含义 | 剧本场景列表——核心产出数据 |
| 设计原因 | 小说转剧本的本质是将段落式叙事重组为场景式戏剧结构。scenes 是重组结果，也是整个 Schema 最核心的数据。 |

**子字段详解：**

| 子字段 | 类型 | 必填 | 默认值 | 语义含义 | 设计原因 |
|--------|------|------|--------|----------|----------|
| `id` | string(pattern `^sc_\d+$`) | 是 | - | 场景唯一ID | 引用基础 |
| `chapter_ids` | string[] | 是(minItems 1) | - | 所属章节 | 跨章节场景需列出所有相关章节 |
| `source_refs` | array | 是(minItems 1) | - | 溯源引用 | 降低 AI 幻觉风险。source_refs 强制每个场景声明其内容来自原文哪些段落，审校者可以据此比对生成内容是否忠实于原文。 |
| `source_refs[].chapter_id` | string | 是 | - | 溯源章节 | 关联到 chapters |
| `source_refs[].paragraph_ids` | string[] | 是(minItems 1) | - | 溯源段落 | 至少1项，保证场景有明确的原文来源 |
| `heading.context` | string(enum) | 是 | `"INT"` | 空间类型 | INT/EXT/INT.EXT，对应 Fountain Slug Line |
| `heading.location_id` | string | 是 | - | 地点引用 | 必须指向 story_bible.locations 中已定义的地点 |
| `heading.time_of_day` | string(enum) | 是 | `"UNKNOWN"` | 时间 | DAY/NIGHT/DUSK/DAWN/UNKNOWN |
| `title` | string | 是(minLength 1) | - | 场景标题 | 简洁概括场景内容 |
| `dramatic_purpose` | string | 是(minLength 1) | - | **戏剧目的** | **剧本场景必须有戏剧目的，避免流水账。** 这是区分剧本与小说段落式叙事的根本标准。每个场景必须声明它为什么存在——推动什么情节、揭示什么人物、建立什么氛围。没有戏剧目的的场景就是流水账。 |
| `conflict` | string | 否 | - | **场景冲突** | **强制保留冲突描述，提升剧本质量。** 冲突是戏剧的核心驱动力。即使不强制必填，Schema 将 conflict 作为显式字段提醒 AI 和审校者关注冲突——如果一个场景的 conflict 为空，审校者应该质疑这个场景是否真的有戏剧价值。 |
| `characters` | string[] | 是(minItems 1) | - | 出场角色 | 必须指向 story_bible.characters 中已定义的角色 |
| `beats` | array | 是(minItems 1) | - | **场景节拍** | **表示场景内部节奏。** beats 是场景的骨架——将场景拆分为若干节拍，每个节拍描述发生了什么、情绪如何变化、关键动作是什么。节拍使得场景不再是扁平的动作序列，而是有节奏、有弧线的戏剧单元。 |
| `beats[].description` | string | 是(minLength 1) | - | 节拍描述 | 必填保证节拍有实际内容 |
| `beats[].emotional_arc` | string | 否 | - | 情绪弧线 | 如"紧张→释然"，指导表演和情绪追踪 |
| `beats[].key_action` | string | 否 | - | 关键动作 | 节拍中的核心行为 |
| `elements` | array | 是(minItems 1) | - | **剧本元素** | **用统一数组表达多种剧本元素。** 而非分类型存储（如分别存储对话、动作、旁白）。统一数组的优势：①便于线性编排——剧本是线性叙事，元素必须按出现顺序排列，统一数组天然保持顺序；②便于阅读——审校者可以像读剧本一样从头到尾阅读 elements，无需在不同分类之间跳转；③便于 Fountain 导出——统一数组按序遍历即可生成 Fountain 文本。 |
| `elements[].id` | string(pattern `^el_\d+$`) | 是 | - | 元素唯一ID | 引用基础 |
| `elements[].type` | string(enum 7种) | 是 | - | 元素类型 | action/dialogue/parenthetical/transition/voice_over/shot/note。七种类型覆盖剧本中所有常见元素。 |
| `elements[].text` | string | 是(minLength 1) | - | 元素文本 | 必填不可为空——空文本的元素是无意义的 |
| `elements[].character_id` | string | 否 | - | 说话角色 | dialogue 和 parenthetical 类型应填此字段 |
| `elements[].emotion` | string | 否 | - | 情绪标签 | 表演指导和情绪追踪 |
| `elements[].parenthetical` | string | 否 | - | 括号提示 | 如（低声）、（犹豫地），仅在 dialogue 类型中使用 |
| `elements[].source_ref` | object | 否 | - | 元素级溯源 | 更精细的溯源——不仅场景级别溯源到段落，每个元素也可以溯源到具体段落 |

### 4.6 metadata

| 属性 | 值 |
|------|-----|
| 名称 | `metadata` |
| 类型 | `object` |
| 是否必填 | 是 |
| 语义含义 | 生成元数据，用于审计和追溯 |

| 子字段 | 类型 | 必填 | 默认值 | 语义含义 | 设计原因 |
|--------|------|------|--------|----------|----------|
| `generated_at` | string(date-time) | 是 | - | 生成时间 | ISO 8601 格式，审计时间线 |
| `model` | string | 是 | - | AI 模型名称 | 追溯生成质量到具体模型 |
| `source_chapter_count` | integer(≥3) | 是 | - | 源文本章节数 | 至少3章保证故事有足够结构层次 |
| `total_scenes` | integer(≥1) | 是 | - | 总场景数 | 快速验证数据完整性 |
| `total_elements` | integer(≥1) | 是 | - | 总元素数 | 与 scenes 内 elements 总计交叉验证 |

---

## 5. 核心设计原因表

以下是最重要的字段设计原因汇总，每一条都经过深思熟虑而非随意添加：

| 字段 | 核心设计原因 |
|------|-------------|
| `dramatic_purpose` | 剧本场景必须有戏剧目的，避免流水账。没有戏剧目的的场景是小说段落的直接搬运，不是剧本。dramatic_purpose 强制 AI 和审校者思考每个场景存在的理由——它推动了什么情节？揭示了什么人物？建立了什么氛围？这是从"叙事"到"戏剧"的关键跨越。 |
| `conflict` | 强制保留冲突描述，提升剧本质量。冲突是戏剧的核心驱动力——没有冲突就没有戏剧。将 conflict 作为显式字段（即使不强制必填）提醒 AI 和审校者关注冲突。如果一个场景的 conflict 为空，审校者应该质疑这个场景是否有戏剧价值。 |
| `beats` | 表示场景内部节奏。beats 是场景的骨架——将场景拆分为若干节拍，每个节拍有描述、情绪弧线和关键动作。节拍使得场景不再是扁平的动作序列，而是有节奏、有弧线的戏剧单元。审校者可以通过 beats 快速理解场景的节奏结构，无需阅读每一个 elements。 |
| `story_bible` | 保证跨章节一致性。AI 在生成多章节内容时极易出现角色名称不一致、地点描述矛盾等问题。story_bible 通过集中定义 + ID 引用机制强制所有场景引用同一套角色/地点定义，消除一致性问题。这是"单点定义 + 多点引用"而非"多点定义"的核心设计。 |
| `source_refs` | 降低 AI 幻觉风险。source_refs 强制每个场景声明其内容来自原文哪些段落，审校者可以据此比对生成内容是否忠实于原文。没有 source_refs 的场景可能是 AI 纯粹虚构的，审校者需要警惕。 |
| `characters[].id` | 避免同名别名批量重命名问题。如果用角色姓名引用角色，当角色改名或出现同名不同人时，所有引用点都需要修改。ID 引用只改一处定义即可——改 story_bible 中的 name，所有引用自动更新。 |
| `locations[].id` | 场景引用地点时保持一致。与角色 ID 同理。地点可能在不同章节中被不同称呼，ID 引用保证所有场景标题行指向同一个地点定义。 |
| `elements[].type` 统一数组 | 用统一数组表达多种剧本元素。而非分类型存储（对话单独数组、动作单独数组等）。统一数组的优势：①便于线性编排——剧本是线性叙事，元素必须按出现顺序排列；②便于阅读——审校者可以像读剧本一样从头到尾阅读；③便于 Fountain 导出——按序遍历即可生成文本。 |
| `paragraphs[].char_start`/`char_end` | 精确溯源到字符级。程序可以自动定位原文中的确切位置，实现自动化的生成内容与原文比对。 |
| `metadata.source_chapter_count` ≥ 3 | 至少3章保证故事有足够的结构层次（起始、发展、高潮/结局），否则改编为剧本缺乏戏剧弧线的空间。 |

---

## 6. 扩展机制

YAML Schema 的 `additionalProperties: false` 设置在当前版本中严格限制额外字段，但以下扩展机制预留了未来扩展路径：

### 6.1 custom_fields（v2.0 规划）

在 v2.0 版本中，计划在每个顶层对象中增加 `custom_fields` 字段：

```yaml
scenes:
  - id: "sc_1"
    # ... 标准字段 ...
    custom_fields:
      lighting: "暗调"
      sound_design: "雨声持续"
```

`custom_fields` 允许用户添加项目特定的自定义字段，不影响标准 Schema 的校验。程序在解析时忽略未知的 custom_fields 内容，但可以将其传递给下游系统。

### 6.2 annotations（v2.0 规划）

在 v2.0 版本中，计划增加 `annotations` 字段用于审校标记：

```yaml
scenes:
  - id: "sc_1"
    # ... 标准字段 ...
    annotations:
      - id: "ann_1"
        author: "编剧A"
        type: "suggestion"
        target: "el_5"
        content: "这段对话可以更紧凑，去掉重复的'雨'意象"
        created_at: "2026-06-05T14:00:00+08:00"
```

annotations 允许多人协作审校，标记针对具体元素的修改建议。

### 6.3 tags（v1.0 已预留）

tags 可以作为任何对象的附加标签：

```yaml
story_bible:
  characters:
    - id: "char_1"
      name: "沈默"
      # ... 标准字段 ...
      tags:
        - "核心角色"
        - "第一幕出场"
        - "需要深度审校"
```

tags 在 v1.0 中作为可选字段通过 `additionalProperties` 限制暂不可用，但 v2.0 将正式开放。

### 6.4 扩展原则

- **向后兼容**：任何扩展字段不应破坏 v1.0 解析器的正常工作。
- **非破坏性**：`custom_fields`、`annotations`、`tags` 都不影响标准字段的语义和校验。
- **版本标识**：使用 `schema_version` 区分是否支持扩展字段。v1.0 解析器遇到 v2.0 数据时，可以选择忽略扩展字段或报错。

---

## 7. 校验规则

### 7.1 Pydantic Model 校验（后端 API 层）

后端 FastAPI 使用 Pydantic Model 对 YAML 解析后的数据进行第一层校验：

```python
from pydantic import BaseModel, Field, constr, validator
from typing import List, Optional
from enum import Enum

class HeadingContext(str, Enum):
    INT = "INT"
    EXT = "EXT"
    INT_EXT = "INT.EXT"

class TimeOfDay(str, Enum):
    DAY = "DAY"
    NIGHT = "NIGHT"
    DUSK = "DUSK"
    DAWN = "DAWN"
    UNKNOWN = "UNKNOWN"

class CharacterRole(str, Enum):
    protagonist = "protagonist"
    supporting = "supporting"
    antagonist = "antagonist"
    extra = "extra"

class ElementType(str, Enum):
    action = "action"
    dialogue = "dialogue"
    parenthetical = "parenthetical"
    transition = "transition"
    voice_over = "voice_over"
    shot = "shot"
    note = "note"

class Screenplay(BaseModel):
    schema_version: constr(pattern=r'^\d+\.\d+\.\d+$')
    project: Project
    story_bible: StoryBible
    chapters: List[Chapter]
    scenes: List[Scene]
    metadata: Metadata

    @validator('scenes')
    def validate_dramatic_purpose_not_empty(cls, v):
        for scene in v:
            if not scene.dramatic_purpose or scene.dramatic_purpose.strip() == "":
                raise ValueError(f"Scene {scene.id}: dramatic_purpose must not be empty")
        return v
```

**校验范围：**
- 类型校验（string、integer、array、object）
- 必填字段校验（required 字段缺失时报错）
- 枚举值校验（role、type、context 等枚举字段）
- 正则 pattern 校验（ID 格式）
- minLength/minLength 校验（文本字段非空）
- minimum 校验（数值字段下限）
- minItems 校验（数组字段最少项数）
- 自定义 validator（dramatic_purpose 非空等业务规则）

### 7.2 JSON Schema 校验（数据交换层）

JSON Schema 定义在 `apps/api/app/schemas/screenplay.schema.json`，用于：

- YAML ↔ JSON 转换后的数据校验
- 前端表单数据校验
- API 请求/响应数据校验
- CI/CD 管道中的自动化数据质量检查

**核心校验规则：**
- `required` 字段列表保证关键数据不缺失
- `additionalProperties: false` 禁止未定义字段，保证数据结构纯净
- `pattern` 正则约束保证 ID 格式一致
- `enum` 约束保证类型字段只能取合法值
- `minItems` / `minLength` 保证数组/文本不为空
- `minimum` 保证数值字段在下限以上

### 7.3 Ajv 校验（前端层）

前端使用 Ajv（JSON Schema 校验库）对用户编辑中的 YAML 数据进行实时校验：

```javascript
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import screenplaySchema from './screenplay.schema.json';

const ajv = new Ajv({ allErrors: true, strict: true });
addFormats(ajv);
const validate = ajv.compile(screenplaySchema);

function validateScreenplay(data) {
  const valid = validate(data);
  if (!valid) {
    return validate.errors.map(err => ({
      path: err.instancePath,
      message: err.message,
      params: err.params
    }));
  }
  return [];
}
```

Ajv 提供：
- 实时校验反馈（编辑时即时提示错误）
- 完整的错误路径（精确到字段位置）
- 自定义错误消息（用户友好的中文提示）

### 7.4 引用一致性校验规则

除 Schema 结构校验外，还需要一套引用一致性校验规则，保证 ID 之间的引用关系正确：

| 校验规则 | 说明 |
|----------|------|
| **场景 → 角色引用** | `scenes[].characters[]` 中的每个 ID 必须存在于 `story_bible.characters[].id` 中 |
| **场景 → 地点引用** | `scenes[].heading.location_id` 必须存在于 `story_bible.locations[].id` 中 |
| **场景 → 章节引用** | `scenes[].chapter_ids[]` 中的每个 ID 必须存在于 `chapters[].id` 中 |
| **场景 → 段落引用** | `scenes[].source_refs[].paragraph_ids[]` 中的每个 ID 必须存在于对应 `chapters[].paragraphs[].id` 中 |
| **元素 → 角色引用** | `elements[].character_id` 必须存在于 `story_bible.characters[].id` 中 |
| **时间线 → 章节引用** | `timeline[].chapter_id` 必须存在于 `chapters[].id` 中 |
| **时间线 → 角色引用** | `timeline[].affected_characters[]` 中的每个 ID 必须存在于 `story_bible.characters[].id` 中 |
| **角色关系 → 角色引用** | `characters[].relationships[].character_id` 必须存在于 `story_bible.characters[].id` 中（不含自身） |
| **首次出现 → 章节+段落** | `characters[].first_appearance.chapter_id` + `paragraph_id` 必须存在于 `chapters` 中 |
| **ID 全局唯一性** | 所有 ID（char_、loc_、tl_、ch_、p_、sc_、el_）在其各自范围内必须唯一 |
| **章节数一致性** | `metadata.source_chapter_count` 必须等于 `chapters` 数组的长度 |
| **场景数一致性** | `metadata.total_scenes` 必须等于 `scenes` 数组的长度 |
| **元素数一致性** | `metadata.total_elements` 必须等于所有 `scenes[].elements` 数组的元素总数 |
| **段落顺序连续性** | 每章的 paragraphs[].index 从1开始连续递增，无间断 |
| **章节顺序连续性** | chapters[].order 从1开始连续递增，无间断 |

---

## 8. 完整示例

### 8.1 三章小说 → YAML 剧本示例

以下示例基于悬疑短篇小说《雨夜来信》，展示从三章小说到 YAML 剧本的完整输出结构。

**故事梗概**：刑侦警官沈默在雨夜收到神秘来信，打开祖父密室发现时间封印的秘密。追查过程中发现二十年前和六十年前的两起失踪案都与时间叠影现象有关。最终沈默选择走进雨幕中的时间通道面对真相。

完整示例文件位于：
- 源小说：`examples/sample_novel.txt`
- YAML 剧本输出：`examples/sample_output.yaml`
- Fountain 格式输出：`examples/sample_output.fountain`

### 8.2 YAML 剧本关键结构示例

```yaml
schema_version: "1.0.0"

project:
  id: "proj_yuanye_001"
  title: "雨夜来信"
  source_language: "zh-CN"
  target_format: "screenplay"
  adaptation_style:
    genre:
      - "悬疑"
      - "惊悚"
    tone:
      - "紧张"
      - "暗黑"
      - "诗意"
    dialogue_style: "terse"

story_bible:
  characters:
    - id: "char_1"
      name: "沈默"
      aliases:
        - "沈队"
      role: "protagonist"
      description: "刑侦队资深警官，十二年刑侦经验。冷静、固执、不愿面对封闭记忆。"
      goals:
        - "追查神秘来信的真相"
        - "理解祖父密室中被封印的秘密"
      personality:
        - "冷静"
        - "固执"
        - "压抑"
      appearance: "三十余岁男性，面容沉稳，目光锐利。"
      first_appearance:
        chapter_id: "ch_1"
        paragraph_id: "p_1_1"
      relationships:
        - character_id: "char_2"
          type: "colleague"
          description: "刑侦搭档，彼此信任。"

  locations:
    - id: "loc_1"
      name: "沈默老宅"
      type: "mixed"
      description: "江南古镇巷尾的老宅，沈默祖父留下。"
      atmosphere: "孤寂、阴沉、时间停滞"

  timeline:
    - id: "tl_1"
      chapter_id: "ch_1"
      sequence: 1
      event_summary: "沈默在雨夜收到神秘来信。"
      affected_characters:
        - "char_1"

chapters:
  - id: "ch_1"
    order: 1
    title: "旧宅来信"
    source_title: "第一章 旧宅来信"
    paragraphs:
      - id: "p_1_1"
        index: 1
        text: "秋雨从黄昏开始落下，到深夜仍未停歇。沈默站在老宅二楼的窗前……"
        char_start: 0
        char_end: 86
    summary: "沈默在雨夜收到神秘来信，打开祖父密室。"

scenes:
  - id: "sc_1"
    chapter_ids:
      - "ch_1"
    source_refs:
      - chapter_id: "ch_1"
        paragraph_ids:
          - "p_1_1"
          - "p_1_2"
          - "p_1_3"
    heading:
      context: "EXT"
      location_id: "loc_1"
      time_of_day: "NIGHT"
    title: "雨夜旧宅"
    dramatic_purpose: "建立故事氛围和主角处境。雨夜老宅的孤寂感暗示着某种被时间封存的秘密即将揭开。"
    conflict: "沈默的内心冲突——对封闭记忆的抗拒 vs 收到神秘来信后无法忽视的好奇与不安。"
    characters:
      - "char_1"
    beats:
      - description: "沈默站在窗前看雨，老宅的孤寂与雨夜的暗沉交织。"
        emotional_arc: "平静 → 不安"
        key_action: "站在窗前观望"
      - description: "沈默发现神秘来信，拆开看到'你所遗忘的，正在回来'。"
        emotional_arc: "好奇 → 冷意蔓延"
        key_action: "拆开信件"
    elements:
      - id: "el_1"
        type: "action"
        text: "秋雨从黄昏开始落下，到深夜仍未停歇。沈默站在老宅二楼的窗前……"
        source_ref:
          chapter_id: "ch_1"
          paragraph_ids:
            - "p_1_1"
      - id: "el_2"
        type: "voice_over"
        text: "这座宅子是他祖父留下的，位于江南古镇的巷尾。"
        source_ref:
          chapter_id: "ch_1"
          paragraph_ids:
            - "p_1_1"

metadata:
  generated_at: "2026-06-05T12:00:00+08:00"
  model: "deepseek-chat"
  source_chapter_count: 3
  total_scenes: 17
  total_elements: 91
```

---

## 9. 版本演进

### 9.1 v1.0 — 当前版本（基础结构）

**目标**：建立核心数据结构，保证 AI 生成结果的基本完整性和一致性。

**包含**：
- 六个顶层键：schema_version / project / story_bible / chapters / scenes / metadata
- ID 引用机制（char_ / loc_ / tl_ / ch_ / p_ / sc_ / el_）
- dramatic_purpose / conflict / beats 核心戏剧字段
- source_refs 溯源机制
- JSON Schema + Pydantic + Ajv 三层校验
- additionalProperties: false 严格模式

**不包含**：
- custom_fields / annotations / tags 扩展字段
- 多版本兼容的迁移机制
- 自动化引用一致性校验工具

### 9.2 v2.0 — 扩展版本（协作与定制）

**目标**：支持多人协作审校和项目定制化需求。

**新增**：
- `custom_fields`：每个顶层对象允许添加自定义字段，不影响标准 Schema 校验
- `annotations`：审校标记系统，支持多人协作批注和修改建议
- `tags`：标签系统，用于分类、筛选和工作流管理
- `versions`：剧本版本管理，记录每次修改的 diff 和原因
- `review_status`：审校状态字段（draft / reviewed / approved / final）
- 引用一致性自动校验工具（CLI + API）
- YAML → Fountain 高保真转换器

**变更**：
- `additionalProperties` 从 false 改为条件性允许（仅 custom_fields / annotations / tags）
- 增加 `schema_version: "2.0.0"` 兼容性判断逻辑
- v1.0 数据可以被 v2.0 解析器读取（向后兼容）
- v2.0 数据中的扩展字段在 v1.0 解析器中被忽略（向前兼容）

### 9.3 v3.0 — 智能版本（AI 增强）

**目标**：深度整合 AI 能力，实现智能审校、自动补全和迭代优化。

**新增**：
- `ai_suggestions`：AI 生成的修改建议，标注 confidence 级别
- `scene_graph`：场景之间的依赖关系图（因果关系、时间顺序、情绪流向）
- `character_arcs`：角色弧线追踪——每个角色在故事中的变化轨迹
- `pacing_analysis`：节奏分析——场景节奏的快慢分布和整体节奏曲线
- `adaptation_notes`：改编笔记——从小说到剧本的改编决策记录
- 多模型对比输出——同一章节用不同模型生成，标注差异
- 自动化质量评分——基于 dramatic_purpose、conflict、beats 完备性等指标

**变更**：
- `metadata` 增加 `quality_score` 和 `iteration_count` 字段
- `scenes` 增加 `scene_graph_edges` 引用字段
- 支持增量生成——新增章节时只生成受影响的场景，而非全量重新生成
- 引入 semantic versioning 严格语义：主版本变更=不兼容破坏性变更

---

## 附录 A：ID 格式规范

| ID 类型 | 格式 | 正则 | 示例 |
|---------|------|------|------|
| 角色 | `char_{序号}` | `^char_\d+$` | `char_1`, `char_15` |
| 地点 | `loc_{序号}` | `^loc_\d+$` | `loc_1`, `loc_8` |
| 时间线 | `tl_{序号}` | `^tl_\d+$` | `tl_1`, `tl_12` |
| 章节 | `ch_{序号}` | `^ch_\d+$` | `ch_1`, `ch_3` |
| 段落 | `p_{章节序号}_{段落序号}` | `^p_\d+_\d+$` | `p_1_1`, `p_2_5` |
| 场景 | `sc_{序号}` | `^sc_\d+$` | `sc_1`, `sc_17` |
| 元素 | `el_{序号}` | `^el_\d+$` | `el_1`, `el_91` |

序号从 1 开始递增，不跳跃。全局唯一性要求：同一类型 ID 不可重复。

## 附录 B：枚举值一览

| 字段 | 枚举值 | 说明 |
|------|--------|------|
| `characters[].role` | protagonist / supporting / antagonist / extra | 角色4级分类 |
| `locations[].type` | interior / exterior / mixed / unknown | 地点4种类型 |
| `heading.context` | INT / EXT / INT.EXT | 场景空间3种 |
| `heading.time_of_day` | DAY / NIGHT / DUSK / DAWN / UNKNOWN | 时间5种 |
| `elements[].type` | action / dialogue / parenthetical / transition / voice_over / shot / note | 元素7种类型 |
| `relationships[].type` | family / friend / enemy / lover / colleague / mentor / subordinate / other | 关系8种类型 |
| `project.target_format` | screenplay / teleplay / stage_play / animation_script | 输出4种格式 |
| `adaptation_style.dialogue_style` | natural / stylized / terse / verbose / poetic | 对话5种风格 |