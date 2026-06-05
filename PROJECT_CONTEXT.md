# Project Context

## Overview

当前项目围绕七牛云 XEngineer 暑期实训营第二批次议题三展开：AI 小说转剧本工具。

目标是构建一个面向小说作者的 AI 剧本改编工作台，将 3 个章节以上的小说文本转换为结构化剧本 YAML，并提供 YAML Schema 文档、Schema 设计理由、可编辑工作流和 Demo 演示。

主设计文档位于：

- `AI_NOVEL_TO_SCREENPLAY_DESIGN.md`

## Commands

已实现命令：

- 安装后端依赖：`python -m pip install -r apps/api/requirements.txt`
- 启动后端：`python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000`
- 安装前端依赖：`npm --prefix apps/web install`
- 启动前端：`npm --prefix apps/web run dev`
- 后端测试：`python -m pytest apps/api/tests`
- 前端构建：`npm --prefix apps/web run build`
- 根测试命令：`npm run test`

## Architecture

规划架构：

- 前端：Next.js、React、TypeScript、Tailwind CSS、Monaco Editor、Ajv、Zustand、TanStack Query。
- 后端：FastAPI、Pydantic、PyYAML 或 ruamel.yaml、Instructor、可选 LangGraph。
- 大模型：支持 OpenAI-compatible API，也支持本地 Ollama、vLLM、llama.cpp。
- 数据结构：Schema-first，后端使用 Pydantic 定义模型并生成 JSON Schema，最终序列化为 YAML。
- 核心流水线：小说导入 -> 章节识别 -> 文本预处理 -> 逐章理解 -> 故事圣经合并 -> 场景拆分 -> 剧本生成 -> Schema 校验 -> 编辑与导出。

当前实现：

- `apps/api`：FastAPI 后端，包含章节识别、LLM Provider、fallback 生成器、剧本生成、校验、导出、SQLite 项目/任务持久化、本地项目成员会话、Bearer token 鉴权、可切换任务队列底座、SSE 任务进度流、批量改写任务和 pytest。
- `apps/api/longform.py`：LongformChunker 长篇上下文层，按章节压缩小说输入，保留标题、字数、段落数、首部/中部/尾部证据摘录和场景规划提示，供 LLM 改编计划使用。
- `apps/api/embeddings.py`：本地 deterministic embedding 层，用于离线语义证据检索；当前是可替换底座，不是最终生产级 embedding API。
- `apps/api/evidence.py`：场景证据检索层，根据 SQLite FTS 证据库、`source_refs`、相邻段落和关键词命中返回 `SourceEvidence`，用于约束局部改写。
- `apps/web`：Next.js 企业级工作台，已按 Arc Studio 专业剧本编辑器方向重构，支持样例、章节索引、项目库、保存项目、启动任务、任务进度、剧本文稿、故事结构、场景证据、审阅意见、评论指派、线程回复、评论解决/重开、项目成员、项目会话、通知、审计事件过滤、质量中心、批量改写任务、制片拆解、诊断型 YAML 编辑器、校验、局部改写和导出。
- `schemas/screenplay.schema.json`：JSON Schema。
- `docs/SCHEMA.md`、`docs/DEMO.md`、`README.md`：提交和演示文档。
- `examples/sample_novel.md`、`examples/sample_output.yaml`：示例输入输出。
- `ENTERPRISE_V2_PLAN.md`：企业级 V2 方向、已实现能力和未完成边界。

## Conventions

- 默认中文回复和中文产品文档。
- 题目三项目必须按企业级 AI 剧本改编平台开发，不再按“应付比赛的 MVP”标准收敛。
- 项目应优先保证完整产品链路，而不是只做 prompt wrapper。
- YAML 生成应采用结构化 JSON/Pydantic 输出后再序列化，避免直接让模型输出最终 YAML。
- 所有场景应尽量保留 `source_refs`，方便追踪原文来源。
- 大模型接入必须支持 API 和本地部署两种路径。

## Decisions

- 选题确定为“AI 小说转剧本工具”。
- 产品定位为“可追踪、可校验、可编辑的剧本改编工作台”。
- UI 风格锁定为 Arc Studio 专业剧本编辑器方向：左侧项目/原文/章节，中间剧本文稿和场景索引，右侧场景检查/原文证据/改写结果/项目能力检查器。
- 推荐使用 Fountain 作为剧本导出格式之一，ScreenJSON 作为 Schema 设计参考。
- 默认模型名使用 `gpt-5.5`，通过 OpenAI-compatible `/chat/completions` 接入。
- LLM 采用“模型生成改编计划，程序组装严格 Schema”的策略，避免模型直接输出完整 YAML 导致格式不稳定。
- 若未配置 API key、模型不可用或调用失败，系统自动使用 deterministic fallback，保证 Demo 可跑通，并在 metadata/warnings 中标记。
- 前端风格选用 B 方案：Arc Studio 的专业剧本编辑器质感为主，融合 Novelcrafter 的故事/证据系统与 Celtx/StudioBinder 的制片拆解模块。
- V2 已加入质量报告、生产拆解、流水线阶段报告、故事圣经扩展、局部场景改写接口和企业级能力清单 API。
- 局部场景改写已升级为“证据检索 + LLM JSON 改写计划 + 安全字段应用 + fallback 规则”的路径；响应返回 `evidence`、`diff_summary`、`provider_status`，并保留场景 ID、`source_refs`、章节和角色引用。
- 本地项目持久化和任务系统已升级为 SQLite 底座：项目/版本/任务写入 `.scriptbridge_data/scriptbridge.sqlite3`，旧 JSON 运行数据会尝试一次性迁移；任务队列支持 `JOB_QUEUE_MODE=inline|background|external`、持久化 request payload、取消、重试、队列状态和 external worker run-once。当前仍是可替换底座，不是最终 Postgres + Redis/Celery/RQ 生产队列架构。
- 任务进度已提供 SSE 接口 `/api/jobs/{job_id}/events`，前端优先使用 EventSource 实时更新，失败后回退轮询。
- 证据检索已加入 SQLite FTS5 + 本地 embedding 融合底座：项目生成后会索引章节段落和段落向量，`/api/projects/{project_id}/evidence/search` 可搜索项目证据库；中文检索包含 LIKE 兜底，并融合 `向量证据库命中`。当前不是最终 pgvector/Qdrant/API embedding 生产 RAG。
- 长篇输入已加入 deterministic LongformChunker：`_build_llm_prompt` 使用 `LONGFORM_CONTEXT` 覆盖所有章节，不再直接截取 `text[:12000]`；metadata pipeline stages 会显示 `stage_longform_context`。当前这仍不是最终向量 RAG 或 LangGraph 多 Agent 长篇理解。
- YAML 编辑器已从单 textarea 升级为诊断型编辑器壳：行号、校验状态、诊断列表、活动问题高亮、组件边界均已具备；当前仍不是 Monaco Editor + YAML language server。
- 审阅协作基础已加入：`ProjectComment`、`CommentReply`、`AuditEvent`、`POST /api/projects/{project_id}/comments`、`POST /api/projects/{project_id}/comments/{comment_id}/replies`、`PATCH /api/projects/{project_id}/comments/{comment_id}`、`GET /api/projects/{project_id}/audit-events`、右侧审阅面板、评论指派、线程回复、评论解决/重开和审计过滤动作。当前是单用户评论指派/线程/审计底座，不是完整多人权限、实时协作或指派通知系统。
- 团队/RBAC/通知底座已加入：`ProjectMember`、`ProjectSession`、`ProjectNotification`、`POST /api/auth/sessions`、`POST /api/projects/{project_id}/members`、`GET /api/projects/{project_id}/notifications`、`PATCH /api/projects/{project_id}/notifications/{notification_id}`；默认成员包含项目负责人、主编、审阅者、编剧、制片、制片审阅；owner/admin 可管理成员，writer 可批量改写，viewer 仅可读通知。协作接口优先使用 Bearer token 解析出的项目成员身份，并覆盖请求体里的 `actor`/`author` 字段；当前是本地项目成员会话底座，不是密码登录、SSO 或完整实时协作。
- 批量场景改写任务已加入：`POST /api/jobs/rewrite` 从当前项目版本选择显式 `scene_ids`，或自动选择质量标记/低证据/低冲突场景，逐场复用证据约束改写流水线，保存为新版本，重建证据索引，并写入 `rewrite.batch_completed` 审计事件。前端质量中心已有批量改写控制面板，任务进度沿用 SSE。

## Pitfalls

- 不要做成单次 prompt 直接输出 YAML，这会导致格式不稳定、长文本遗漏和难以解释。
- 不要只展示最终 YAML，必须体现作者可编辑、可校验和可追踪。
- 注意开源许可证，AGPL 项目只参考思路，不直接复用代码。
- 不要把 API key、token 或任何敏感配置写入项目记忆或提交文档。
- Windows PowerShell 的 `Start-Process` 在当前环境不支持 `-Environment` 参数，启动带环境变量的后端时应先在当前 shell 设置 `$env:*` 再启动。
- Windows PowerShell 内置变量 `$PID` 是只读变量，端口重启脚本不要使用 `$pid` 作为循环变量名，改用 `$procId`。
- Next dev/build 如果在中途被停止，`.next` 缓存可能出现 `Unexpected end of JSON input` 或 dev 端口 500；先删除 `apps/web/.next` 再重新 `npm --prefix apps/web run build` / `npm --prefix apps/web run dev`。
- 后端 CORS 默认放行本地前端 3000、3010、3011；如需其他端口，设置 `APP_CORS_ORIGINS` 为逗号分隔 origin 列表。
- Next dev 在 CSS 热更新后可能出现 React Client Manifest 或 `__webpack_modules__[moduleId] is not a function` 覆盖层；清理 `apps/web/.next` 并重启 dev server 后已验证恢复。
- 当前 YAML 编辑器是诊断型 textarea 编辑器壳，保留 `YamlEditor` 组件边界，后续可替换 Monaco + YAML language server。
- 当前局部改写和批量改写已有 LLM 证据改写入口、SQLite FTS + 本地 embedding 证据索引、fallback 规则、版本快照和审计记录，长篇输入已有章节级压缩采样，但还不是完整 LangGraph 多 Agent 改写系统，也不是生产级向量数据库 RAG；后续需要替换为 pgvector/Qdrant/API embedding、map-reduce 故事圣经合成、正式改写审阅流和生产队列。
- 当前任务队列已有 inline/background/external 模式、持久化 payload、取消、重试和 worker run-once；正式企业级部署仍应替换为 Postgres、Redis/Celery/RQ 等生产级队列、对象存储，并继续完善生产级审计、权限和实时协作。
- 旧 `.scriptbridge_data/` 运行数据可能包含早期乱码标题；前端已做显示兜底，但不要把这当作当前源码文案问题。
- 使用浏览器工具验证左侧项目库打开项目时，项目卡片可能位于左栏底部裁切区；应先 `scrollintoview` 到完整卡片后再点击，否则可能看起来没触发 `GET /api/projects/{project_id}`。

## Current Focus

当前阶段：Enterprise V2 基础重构继续推进。已完成 SQLite 项目/任务持久化、版本快照、可切换任务队列底座、SSE 任务进度流、SQLite FTS + 本地 embedding 项目证据库、LongformChunker 长篇章节级上下文压缩、Arc Studio 风格前端工作台、诊断型 YAML 编辑器壳、场景证据检索、LLM 约束局部改写入口、批量场景改写任务、改写证据展示、审阅评论、评论指派、线程回复、评论解决/重开、项目成员、项目成员会话、Bearer token 鉴权、RBAC 底座、通知和审计事件过滤基础。API 测试已扩展到 24 个，覆盖 external 队列 worker 执行和 queued job 取消；前端已加入任务队列状态、cancel/retry/Worker run-once 控制。队列底座已用 `JOB_QUEUE_MODE=external` 在本地 8016/3016 验证：worker run-once 执行后队列状态显示 `external`、`queued 0`、`running 0`、`failed 0`、`done 13`，截图位于 `.scriptbridge_data/verify-screens/queue-external-desktop.png`、`.scriptbridge_data/verify-screens/queue-external-mobile.png`、`.scriptbridge_data/verify-screens/queue-external-mobile-queue.png`。当前仍未完成真正企业级最终态：Postgres/生产数据库、Redis/Celery/RQ 生产队列、LangGraph 式多 Agent、生产级向量 RAG 证据库、Monaco YAML language server、密码/SSO 登录、实时协作、外部通知投递和部署包装仍需要继续开发，不能把当前版本说成最终企业级完成。
