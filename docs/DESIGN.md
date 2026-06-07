# NovelScripter 设计概要

## 架构

四层架构：客户端（React/Next.js）→ 服务层（FastAPI/Celery/Redis）→ AI引擎层（ModelRouter/Prompt Library/Instructor）→ 数据层（PostgreSQL/Redis/MinIO）

## Schema 设计原则

1. 结构化优先 — 剧本必须拆成项目、故事圣经、章节、场景和剧本元素
2. 可编辑优先 — 每个对象都有稳定 ID，便于前端编辑和局部再生成
3. 可校验优先 — JSON Schema 描述 YAML 结构，保障输出稳定
4. 可追踪优先 — 场景和元素保留 source_refs，降低 AI 幻觉风险
5. 可扩展优先 — schema_version 和 metadata 支持未来扩展
6. 编剧专业优先 — dramatic_purpose/conflict/beats 区别于小说摘要

## Pipeline 阶段

7阶段：章节识别 → 段落编号 → 逐章理解 → 故事圣经合并 → 场景拆分 → 剧本元素生成 → Schema校验修复

## 色彩体系（OKLCH）

| 角色 | 色值 | 用途 |
|------|------|------|
| 基底色 | oklch(0.15 0.02 260) | 背景 |
| 表面色 | oklch(0.22 0.03 260) | 卡片面板 |
| 前景色 | oklch(0.90 0.01 260) | 正文 |
| 强调色 | oklch(0.75 0.15 75) | 琥珀金 |
| 辅助色 | oklch(0.55 0.12 150) | 青绿 |
| 警示色 | oklch(0.65 0.18 25) | 错误红 |
| 边界色 | oklch(0.35 0.03 260) | 分割线 |

详细设计文档见最终整合版设计项目书。