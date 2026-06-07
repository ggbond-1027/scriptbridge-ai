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

- `apps/api`：FastAPI 后端，包含章节识别、LLM Provider、fallback 生成器、剧本生成、校验、导出、SQLite 项目/任务持久化、版本治理 API、项目交付门禁 API、导入历史 API、本地分片导入会话 API、本地项目成员会话、Bearer token 鉴权、可切换任务队列底座、SSE 任务进度流、批量改写任务和 pytest。
- `apps/api/longform.py`：LongformChunker 长篇上下文层，按章节压缩小说输入，保留标题、字数、段落数、首部/中部/尾部证据摘录和场景规划提示，供 LLM 改编计划使用。
- `apps/api/embeddings.py`：本地 deterministic embedding 层，用于离线语义证据检索；当前是可替换底座，不是最终生产级 embedding API。
- `apps/api/evidence.py`：场景证据检索层，根据 SQLite FTS 证据库、`source_refs`、相邻段落和关键词命中返回 `SourceEvidence`，用于约束局部改写。
- `apps/api/importer.py`：小说源文件导入层，支持文本/Markdown/DOCX/文本型 PDF，返回提取方法、文档统计、章节数、段落数、sha256、本地静态安全扫描报告、可选外部/ClamAV 风格扫描报告和导入警告。
- `apps/api/jobs.py` + `apps/api/queue.py`：统一任务执行层，当前支持 `generate`、`rewrite`、`import` 三类任务；导入任务会从本地上传暂存文件提取正文，刷新项目源文，写入 `result_payload` 和 `import.source_completed` 审计事件。
- `apps/web`：Next.js 企业级工作台，已按 Arc Studio 专业剧本编辑器方向重构，支持样例、章节索引、项目库、保存项目、版本列表、版本比较、版本恢复、项目交付门禁、导入历史、分片上传进度、启动任务、任务进度、剧本文稿、故事结构、场景证据、审阅意见、评论指派、线程回复、评论解决/重开、项目成员、项目会话、通知、审计事件过滤、质量中心、批量改写任务、制片拆解、诊断型 YAML 编辑器、校验、局部改写和导出。
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
- 本地项目持久化和任务系统已升级为 SQLite 底座：项目/版本/任务写入 `.scriptbridge_data/scriptbridge.sqlite3`，旧 JSON 运行数据会尝试一次性迁移；任务队列支持 `JOB_QUEUE_MODE=inline|background|external`、持久化 request payload、取消、重试、死信隔离、人工重入队、队列状态、external worker run-once 和可选 Redis list broker 适配层。当前仍是可替换底座，不是最终 Postgres + Celery/RQ/生产部署包架构。
- 版本治理底座已加入：`GET /api/projects/{project_id}/versions`、`GET /api/projects/{project_id}/versions/compare`、`POST /api/projects/{project_id}/versions/{version_id}/restore` 支持版本摘要、当前版本标记、场景变化清单、YAML diff 预览和恢复版本审计；恢复版本采用更新项目 `current_version_id` 的方式，不克隆新版本，需要 `manage_members` 权限。
- 项目交付门禁已加入：`GET /api/projects/{project_id}/readiness` 会按源文导入、当前剧本版本、Schema、质量分、证据链覆盖、制片拆解、导入安全、未解决审阅意见和任务队列状态返回 `ProjectReadinessResponse`，包含 status、score、blockers、warnings、passed 和 next_actions；前端顶部状态条显示 Gate 分数，右侧项目检查器新增 `ReadinessPanel` 展示交付阻塞项和下一步动作。
- 系统级部署就绪门禁已加入：`GET /api/system-readiness` 会按生产数据库、任务队列、模型密钥治理、导入安全、交付对象存储和认证/签名配置返回 `SystemReadinessResponse`，包含 status、score、environment、checks、blockers、warnings、passed 和 next_actions；前端顶部状态条显示 System 分数，右侧项目检查器新增 `SystemReadinessPanel` 展示部署阻塞项。该门禁用于暴露 Postgres/Redis/SSO/对象存储等生产化缺口；Redis broker adapter 已有，但这不等于已经完成实际 Postgres 迁移、Celery/RQ 级生产 scheduler、完整 worker 部署包或 SSO 集成。
- 项目级导出治理已加入：`GET /api/projects/{project_id}/exports` 返回项目导出历史，`POST /api/projects/{project_id}/exports` 从当前或指定版本生成 YAML/JSON/Markdown/Fountain 交付物，默认执行 readiness gate，成功写入 `export.created` 审计，阻塞写入 `export.blocked` 审计并返回 HTTP 409；记录 format、actor、version_id、filename、content_type、size_bytes、sha256、readiness_status/score、blockers、warnings 和 audit_event_id。前端右侧项目检查器新增 `ExportGovernancePanel`。
- 交付审批中心已加入：`GET /api/projects/{project_id}/approvals` 返回项目审批历史，`POST /api/projects/{project_id}/approvals` 提交当前或指定版本进入交付审批，`POST /api/projects/{project_id}/approvals/{approval_id}/decision` 支持批准/驳回/撤回。提交需要 owner/admin/writer，批准/驳回需要 owner/admin/producer，撤回允许提交人或 owner/admin；readiness gate 阻塞时返回 409 并写入 `approval.blocked`，成功提交/决策写入 `approval.submitted`、`approval.approved`、`approval.rejected` 或 `approval.revoked`，并通知相关成员。前端右侧项目检查器新增 `ApprovalCenterPanel`。
- 交付包中心已加入：`GET /api/projects/{project_id}/delivery-packages` 返回正式交付包历史，`POST /api/projects/{project_id}/delivery-packages` 从当前或指定版本生成正式包，默认要求绑定已批准审批并执行 readiness gate。owner/admin/producer 可生成包；缺少已批准审批或门禁阻塞会返回 409 并写入 `delivery_package.blocked`；成功写入 `delivery_package.created`，返回 YAML/Markdown/Fountain/JSON 等资产内容、规范 manifest JSON、manifest sha256、资产 sha256、总大小、版本、审批和门禁快照。交付资产通过 `apps/api/artifact_storage.py` 的可插拔 provider 写入；默认 `DELIVERY_ARTIFACT_PROVIDER=local` 写入 `.scriptbridge_data/delivery-artifacts/` 或 `DELIVERY_ARTIFACT_LOCAL_DIR` 指定目录；`s3/minio` 已接入 boto3-backed S3-compatible adapter，`qiniu` 已接入 qiniu-backed Kodo adapter，配置缺失或写读失败会返回 503 且不会伪造成功交付包。历史包有 `storage_provider/storage_key/artifact_count/download_expires_at` 元数据，下载时按资产自身 provider 读取；有 `package_delivery` 权限时返回 1 小时签名下载 URL，审阅者等无权限身份只能看历史 metadata，无下载链接。下载接口 `GET /api/projects/{project_id}/delivery-packages/{package_id}/assets/{asset_sha256}` 会校验 token、过期时间和 artifact sha256。前端右侧项目检查器新增 `DeliveryPackagePanel` 资产下载中心，下载后做浏览器端 sha256 校验。
- 任务进度已提供 SSE 接口 `/api/jobs/{job_id}/events`，前端优先使用 EventSource 实时更新，失败后回退轮询。
- 证据检索已加入 SQLite FTS5 + 本地 embedding 融合底座：项目生成后会索引章节段落和段落向量，`/api/projects/{project_id}/evidence/search` 可搜索项目证据库；中文检索包含 LIKE 兜底，并融合 `向量证据库命中`。当前不是最终 pgvector/Qdrant/API embedding 生产 RAG。
- 长篇输入已加入 deterministic LongformChunker：`_build_llm_prompt` 使用 `LONGFORM_CONTEXT` 覆盖所有章节，不再直接截取 `text[:12000]`；metadata pipeline stages 会显示 `stage_longform_context`。当前这仍不是最终向量 RAG 或 LangGraph 多 Agent 长篇理解。
- YAML 编辑器已从单 textarea 升级为诊断型编辑器壳：行号、校验状态、诊断列表、活动问题高亮、组件边界均已具备；当前仍不是 Monaco Editor + YAML language server。
- 审阅协作基础已加入：`ProjectComment`、`CommentReply`、`AuditEvent`、`POST /api/projects/{project_id}/comments`、`POST /api/projects/{project_id}/comments/{comment_id}/replies`、`PATCH /api/projects/{project_id}/comments/{comment_id}`、`GET /api/projects/{project_id}/audit-events`、右侧审阅面板、评论指派、线程回复、评论解决/重开和审计过滤动作。当前是单用户评论指派/线程/审计底座，不是完整多人权限、实时协作或指派通知系统。
- 团队/RBAC/通知底座已加入：`ProjectMember`、`ProjectSession`、`ProjectNotification`、`POST /api/auth/sessions`、`POST /api/projects/{project_id}/members`、`GET /api/projects/{project_id}/notifications`、`PATCH /api/projects/{project_id}/notifications/{notification_id}`；默认成员包含项目负责人、主编、审阅者、编剧、制片、制片审阅；owner/admin 可管理成员，writer 可批量改写，viewer 仅可读通知。协作接口优先使用 Bearer token 解析出的项目成员身份，并覆盖请求体里的 `actor`/`author` 字段；当前是本地项目成员会话底座，不是密码登录、SSO 或完整实时协作。
- 批量场景改写任务已加入：`POST /api/jobs/rewrite` 从当前项目版本选择显式 `scene_ids`，或自动选择质量标记/低证据/低冲突场景，逐场复用证据约束改写流水线，保存为新版本，重建证据索引，并写入 `rewrite.batch_completed` 审计事件。前端质量中心已有批量改写控制面板，任务进度沿用 SSE。
- 模型连接中心已加入：`apps/api/model_profiles.py`、`GET /api/model-profiles`、`POST /api/model-profiles/test`、运行时 `ModelProfileRuntime`、脱敏 `ModelProfilePublic`、前端 API/local/fallback 连接表单、短超时连接测试、生成/局部改写/批量改写 profile 透传。API key 只在当前请求/同进程 worker 内存中使用；服务端密钥引用 `api_key_secret_ref` 会按 `MODEL_SECRET_<REF>`、`MODEL_SECRET_REF_<REF>`、`OPENAI_API_KEY_<REF>` 解析服务端环境变量；任务 payload 和项目 settings 只保存 provider/base_url/model/temperature/has_api_key/api_key_secret_ref，不保存 key 明文。当前是 env-backed secret_ref 底座，不是完整生产级 Vault/KMS 密钥管理方案。
- 小说源文件导入底座已扩展：`apps/api/importer.py`、`POST /api/import/source` 和前端左栏导入按钮支持 `.txt`、`.md`、`.markdown`、`.docx`、文本型 `.pdf`。文本文件会识别 UTF-8/UTF-8 BOM/GB18030；DOCX 使用 `python-docx` 提取段落和表格文本；PDF 使用 `pypdf` 按页提取文本并返回页数/文本页数；导入响应返回 `extraction_method`、`document_stats`、章节数、段落数、字节数和导入警告，并自动刷新章节证据索引。
- 导入任务化已加入：`POST /api/jobs/import-source` 支持 multipart 上传并进入统一队列，可更新现有项目或自动创建项目壳；任务 `kind` 为 `import`，payload 只保存上传元数据和本地暂存路径，完成后更新项目源文、写入 `result_payload`、`import.source_completed` 审计事件，并由前端通过 SSE/Worker 完成路径回填标题、正文和章节索引。`GET /api/projects/{project_id}/import-history` 已提供脱敏项目导入历史，返回文件元数据、队列状态、提取统计、警告、最后阶段和审计事件关联，不返回正文或本地暂存路径。
- 本地分片导入会话已加入：`POST /api/import-sessions`、`GET /api/import-sessions/{session_id}`、`PUT /api/import-sessions/{session_id}/chunks/{chunk_index}`、`POST /api/import-sessions/{session_id}/complete` 支持本地可续传分片上传、缺失分片补齐、组装到现有导入暂存区并派发普通导入任务；前端对超过阈值的源文件自动走分片路径，左栏显示上传进度，右侧导入历史面板可展示活跃分片会话。当前这是本地上传底座，不是扫描 PDF OCR、对象存储或病毒扫描生产摄入平台。
- 导入安全治理底座已加入：`ImportSecurityReport` 会记录扫描器链路、verdict、risk_level、sha256、扩展名、检测文件类型、声明 MIME、检查项、警告和阻断原因；直接导入、任务化导入和分片组装导入都会做扩展名/大小/文件签名/MIME 一致性检查，伪装签名会在提取前被 422 阻断；`IMPORT_SECURITY_SCANNER=external|clamav` 可接入外部/ClamAV 风格 HTTP 扫描器，`IMPORT_SECURITY_ON_UNAVAILABLE=block|warn` 控制扫描器不可用时 fail-closed 或 warning 放行；任务 request/result payload、审计 metadata 和导入历史都会保留脱敏安全信息。当前仍不是完整对象存储隔离区/隔离运营平台。
- B 方案已进一步固化到前端工作台：顶部状态条展示项目、健康、证据覆盖、交付门禁、模型与会话状态；左栏强化素材导入/导入门槛/模型连接/分片上传进度，并将项目库改为独立滚动区以避免项目卡片点击被原文区挤压；中间剧本页增加场景工作条、质量旗标、证据覆盖；右栏场景检查增加可执行检查清单、交付门禁面板、交付审批面板、交付包下载中心、导出治理面板、导入历史面板、活跃分片会话状态、导入安全扫描结论和项目版本治理面板。交付门禁、导出治理、交付审批到交付包闭环、签名下载中心截图已补充；导入历史/版本治理/分片导入/安全扫描 UI 仍需后续浏览器截图补充视觉验证。

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
- 当前任务队列已有 inline/background/external 模式、持久化 payload、取消、重试、死信隔离、人工重入队、worker run-once、`python -m apps.api.worker` 独立 worker loop、worker heartbeat、Redis list broker adapter，并已覆盖生成、批量改写、源文导入三类任务；系统级部署就绪门禁会将缺少 external Redis broker 的本地队列标为未达生产就绪；正式企业级部署仍应替换为 Postgres、Celery/RQ 或等价生产 scheduler、完整 worker 部署包、对象存储，并继续完善生产级审计、权限和实时协作。
- 当前模型连接中心支持 API、本地 OpenAI-compatible 服务、fallback 和服务端 `secret_ref` 解析；正式多 worker 部署仍必须接入 Vault/KMS/集中密钥管理，不能只依赖本地进程内存或普通环境变量保存运行时 key。
- Markdown 导入时要清理文档顶层 H1，否则样例标题会被当作正文开头，影响章节识别和前端原文展示。
- 极简 PDF 或部分导出工具可能让 pypdf 抽出 Latin-1 形态的 UTF-8 字节串；`importer.py` 已加入保守修复：只有修复后中文字符更多才替换文本。
- 扫描 PDF 目前会返回“未提取到可用文本”的导入警告，不等于 OCR 能力已完成。
- 使用 agent-browser 验证 Next 页面时，如果先跑 `next build` 再复用 `next dev`，可能出现 `__webpack_modules__[moduleId] is not a function` 或空白截图；可改用干净浏览器会话 + `next start` 生产预览验证。2026-06-05 已用 3030 生产预览补测 B 方案桌面和移动截图。
- 移动端 topbar 状态 Badge 如果没有 `white-space: nowrap` 和横向滚动，会被挤成竖排；当前已加窄屏规则修复。
- 旧 `.scriptbridge_data/` 运行数据可能包含早期乱码标题；前端已做显示兜底，但不要把这当作当前源码文案问题。
- 使用浏览器工具验证左侧项目库打开项目时，项目卡片可能位于左栏底部裁切区；应先 `scrollintoview` 到完整卡片后再点击，否则可能看起来没触发 `GET /api/projects/{project_id}`。
- 使用 agent-browser 验证桌面右侧项目检查器时，`.studio-inspector` 是内部滚动区；可访问树可能列出屏幕下方按钮，但 ref click 不一定命中 React 事件。审批、交付包等右栏按钮应先把 `.studio-inspector` 滚到按钮进入视口，再点击或用 CSS 选择器点击。
- agent-browser 对左侧项目库的可访问树 ref 在滚动状态下偶尔会命中旧坐标；验证项目打开时可优先用 `button.project-item` 文本选择器触发，或先截图确认卡片真实位置。左栏项目库已改成独立滚动区以降低这个问题。

## Current Focus

2026-06-05: 已将项目非代码部分上传到 GitHub `https://github.com/ggbond-1027/scriptbridge-ai`。本地 `origin` 指向该仓库，`main` 分支跟踪 `origin/main`。首个提交 `2dd9b50` 仅包含文档、示例、Schema、`.env.example` 和 `.gitignore`；`apps/` 与 `package.json` 仍留在本地未提交。

当前阶段：Enterprise V2 基础重构继续推进。已完成 SQLite 项目/任务持久化、版本快照、版本治理、项目交付门禁、交付审批中心、交付包中心、可插拔交付 artifact provider 边界、本地 artifact store、boto3-backed S3/MinIO artifact adapter、qiniu-backed Kodo artifact adapter、签名下载中心、项目级导出治理、导入历史治理、本地分片导入会话、导入安全治理、可插拔外部/ClamAV 风格扫描底座、可切换任务队列底座、Redis list broker adapter、独立 worker loop 和 heartbeat、SSE 任务进度流、SQLite FTS + 本地 embedding 项目证据库、LongformChunker 长篇章节级上下文压缩、Arc Studio/B 方案前端工作台、诊断型 YAML 编辑器壳、场景证据检索、LLM 约束局部改写入口、批量场景改写任务、改写证据展示、审阅评论、评论指派、线程回复、评论解决/重开、项目成员、项目成员会话、Bearer token 鉴权、RBAC 底座、通知、审计事件过滤基础、模型连接中心和小说源文件导入。导入支持已从 `.txt/.md/.markdown` 扩展到 `.docx` 和文本型 `.pdf`，新增依赖 `python-docx`、`pypdf`，响应包含 `extraction_method`、`document_stats`、sha256 和 `security_report`；导入已接入 `/api/jobs/import-source` 任务入口，支持 inline/background/external 队列、自动创建项目壳或更新现有项目、`result_payload` 回填和 `import.source_completed` 审计事件；`/api/projects/{project_id}/import-history` 返回脱敏导入历史，不暴露正文或 `file_path`；本地分片导入会话已接入 `/api/import-sessions`、`/api/import-sessions/{session_id}`、`/api/import-sessions/{session_id}/chunks/{chunk_index}`、`/api/import-sessions/{session_id}/complete`，可续传补齐缺失分片，组装后派发普通导入任务；导入安全治理会阻断扩展名与文件签名不一致的稿件，可接外部扫描器阻断 infected/malicious 文件，并在导入历史展示上传模式、短 sha256、verdict/risk 和扫描器；项目交付门禁 API 会汇总源文、版本、Schema、质量分、证据链、制片拆解、导入安全、审阅意见和任务队列状态；交付审批 API 会按 readiness gate、项目成员权限、版本、审批说明、决策意见、通知和审计事件记录提交/批准/驳回/撤回历史，阻塞时返回 409 并写入 `approval.blocked`；交付包 API 会要求已批准审批、按 readiness gate 和权限生成正式交付包，记录资产 sha256、manifest sha256、版本、审批、门禁快照和 `delivery_package.created`/`delivery_package.blocked` 审计，并通过 `DELIVERY_ARTIFACT_PROVIDER` 写入可复取资产；默认 local provider 写入 `.scriptbridge_data/delivery-artifacts/` 或 `DELIVERY_ARTIFACT_LOCAL_DIR`，`s3/minio/qiniu` 已接入真实对象存储 adapter，缺配置或写读失败会 503 且不保存假成功包；有权限历史查询返回 1 小时签名下载 URL；项目导出治理 API 会按 readiness gate、项目成员权限、版本、格式、sha256 和审计事件记录 YAML/JSON/Markdown/Fountain 交付历史，阻塞时返回 409 并写入 `export.blocked`。API 测试覆盖 external 队列 worker 执行、Redis broker dispatch/consume/stale skip、独立 worker loop 心跳、queued job 取消、模型 profile 脱敏、运行时 key 使用、短超时连接测试、`.md` 导入元数据、DOCX 段落提取、PDF 页面文本提取、不支持扩展名拒绝、伪装文件签名阻断、外部扫描 infected 阻断/可疑 warning/不可用策略、导入任务更新现有项目、导入任务自动创建项目并等待 external worker、分片导入会话、分片组装外部扫描阻断、导入安全元数据、导入历史脱敏聚合、版本列表、版本比较、版本恢复、恢复权限拦截、项目交付门禁、审批提交/批准/权限拦截/阻塞审计、交付包创建/阻塞/权限拦截、交付包签名下载、local artifact root 配置和路径逃逸防护、S3/MinIO adapter、Qiniu Kodo adapter、远端缺配置 503、导出阻塞审计、生成项目 Markdown 导出元数据和 reviewer 导出权限拦截；前端已加入任务队列状态、broker/depth/worker heartbeat 展示、cancel/retry/Worker run-once、模型连接中心、源文件导入任务按钮、DOCX/PDF accept、分片上传进度、导入历史安全扫描行、B 方案工作区状态条、Gate 交付分数、左栏导入门槛、左栏项目库独立滚动区、剧本页质量旗标、右栏场景检查清单、交付门禁面板、交付审批面板、交付包签名下载中心、导出治理面板和项目版本治理面板。当前仍未完成真正企业级最终态：Postgres/生产数据库、Celery/RQ 或等价生产 scheduler 与完整 worker 部署包、LangGraph 式多 Agent、生产级向量 RAG 证据库、Monaco YAML language server、密码/SSO 登录、实时协作、Vault/KMS 密钥管理、外部通知投递、扫描 PDF OCR、对象存储隔离区/隔离运营、CDN/lifecycle/DAM/legal delivery hardening、法律级多级审批/电子签名/不可变留存和部署包装仍需要继续开发，不能把当前版本说成最终企业级完成。

2026-06-06 update: 本轮可插拔交付 artifact provider 切片完成后，S3/MinIO 已接入 boto3-backed adapter，local provider 已补路径逃逸防护，远端 object key 会拒绝 Windows 盘符/冒号 key；targeted artifact/delivery tests 已通过 13 个，`npm run test` 已全量通过：61 个后端测试、YamlEditor 静态检查、model profile workbench 静态检查和 Next 生产构建均通过；敏感扫描无用户 key/base_url 或 `sk-...` 模式命中。

2026-06-06 update: 七牛 Kodo 交付 artifact provider 已接入，新增依赖 `qiniu==7.17.0`；配置项为 `DELIVERY_ARTIFACT_PROVIDER=qiniu`、`DELIVERY_ARTIFACT_BUCKET`、`DELIVERY_ARTIFACT_QINIU_ACCESS_KEY`、`DELIVERY_ARTIFACT_QINIU_SECRET_KEY`、`DELIVERY_ARTIFACT_QINIU_DOMAIN`，可选 `DELIVERY_ARTIFACT_PREFIX`、上传/下载 token 过期时间。七牛缺配置、SDK 缺失或读写失败时返回 503，不保存假成功交付包；targeted `python -m pytest apps/api/tests/test_pipeline.py -q -k "qiniu or artifact_provider or delivery_package"` 已通过 15 个测试；`npm run test` 已全量通过：63 个后端测试、YamlEditor 静态检查、model profile workbench 静态检查和 Next 生产构建均通过。

2026-06-06 update: 导入安全已从本地静态扫描扩展为可插拔外部/ClamAV 风格扫描底座；新增配置 `IMPORT_SECURITY_SCANNER=local|external|clamav`、`IMPORT_SECURITY_EXTERNAL_ENDPOINT`、`IMPORT_SECURITY_EXTERNAL_SCANNER_NAME`、`IMPORT_SECURITY_EXTERNAL_TIMEOUT_SECONDS`、`IMPORT_SECURITY_ON_UNAVAILABLE=block|warn`。外部扫描结果会与本地扩展名/签名/MIME 检查合并到 `ImportSecurityReport`，直接导入、任务化导入和分片组装导入共用该模型；targeted `python -m pytest apps/api/tests/test_pipeline.py -q -k "import_source_external or external_security_scan or security_scan or import_source_job_persists_external or chunked_import_session_external or import_history"` 已通过 8 个测试；`npm run test` 已全量通过：69 个后端测试、YamlEditor 静态检查、model profile workbench 静态检查和 Next 生产构建均通过。

2026-06-06 update: 模型连接中心已补上服务端密钥引用解析底座；`OPENAI_API_KEY_SECRET_REF` 和运行时 `api_key_secret_ref` 会解析服务端环境变量 `MODEL_SECRET_<REF>`、`MODEL_SECRET_REF_<REF>`、`OPENAI_API_KEY_<REF>`，生成任务、连接测试和环境默认 profile 均可使用解析后的 key，但响应、项目 settings 和任务 payload 只保存脱敏 profile、`has_api_key` 和引用名，不保存 key 明文。targeted `python -m pytest apps/api/tests/test_pipeline.py -q -k "model_profile or generation_job_runtime_model_profile or generation_job_model_profile_secret_ref"` 已通过 7 个测试；`npm run test:web:model` 已通过；`npm run test` 已全量通过：72 个后端测试、YamlEditor 静态检查、model profile workbench 静态检查和 Next 生产构建均通过；敏感扫描无用户 key/base_url 或 `sk-...` 模式命中。该切片是 env-backed secret_ref 底座，仍不是最终 Vault/KMS。

2026-06-06 update: 新增系统级部署就绪门禁切片；后端新增 `apps/api/system_readiness.py` 和 `GET /api/system-readiness`，检查 `DATABASE_URL`/Postgres、`JOB_QUEUE_MODE=external` + broker、服务端模型 `secret_ref`、外部/ClamAV 导入扫描、远端交付 artifact provider、`AUTH_MODE` 与 `DELIVERY_SIGNING_SECRET`，只返回脱敏配置证据；`GET /api/capabilities` 增加 `SystemReadinessGate`。前端新增 `SystemReadinessResponse` 类型、`getSystemReadiness` client、顶部 System 分数和右侧 `SystemReadinessPanel`/“部署就绪”面板。targeted `python -m pytest apps/api/tests/test_pipeline.py -q -k "system_readiness or capabilities"` 已通过 3 个测试；`npm run test:web:model` 与 `npm --prefix apps/web run build` 已通过。该切片是生产化配置门禁，不等于已完成 Postgres/Redis/Celery/RQ/SSO 实际迁移。

2026-06-06 update: B 方案前端工作台进一步落地为 Arc Studio 风格的生产编辑台；`apps/web/src/app/page.tsx` 新增 `StudioCommandBand` 制片工作流指挥带，集中展示源文、剧本、Schema、审阅、交付和 System readiness 状态，并提供运行、校验、项目检查入口；`ScriptWorkspace` 增强场景索引、幕结构摘要、场景生产要素、剧本页页眉和证据/角色/制片备注信息，使主工作区更接近专业剧本编辑器。`apps/web/src/app/globals.css` 新增命令带、场景摘要、场景生产要素和剧本页样式，并补充桌面/移动响应式规则；`.gitignore` 增加 `.ui-check/` 忽略本地浏览器 QA 截图。验证：`npm run test:web:model`、`npm --prefix apps/web run build`、`npm run test` 均通过，`npm run test` 包含 74 个后端测试、YamlEditor 静态检查、model profile workbench 静态检查和 Next 生产构建；agent-browser 在 `http://127.0.0.1:3010` 完成桌面/移动截图和样例生成验证。该切片是 UI 信息架构和专业工作台体验增强，不代表 Postgres、Redis/Celery/RQ、Monaco、实时协作、SSO 或 Vault/KMS 已完成。

2026-06-06 update: 生产任务队列切片新增 Redis broker adapter；`apps/api/redis_broker.py` 支持 `JOB_BROKER_URL`/`REDIS_URL`、`JOB_BROKER_QUEUE`、`JOB_BROKER_POP_TIMEOUT_SECONDS`，external 任务派发时先写 SQLite job payload，再将 job id 推入 Redis list；worker run-once 从 Redis `brpop` 弹出 job id 后通过 SQLite `claim_job` 精确领取任务，并跳过 stale/canceled job。`/api/job-queue/status` 新增 `broker`、`broker_queue`、`broker_depth`、`broker_error`，前端任务队列面板展示 broker 元数据；`/api/system-readiness` 会识别 Redis/Rediss broker 并返回脱敏 evidence。targeted Redis broker tests、`npm run test:web:model`、py_compile 和全量 `npm run test` 已通过；全量测试包含 76 个后端测试、YamlEditor 静态检查、model profile workbench 静态检查和 Next 生产构建。该切片是 Redis list broker 适配层，不代表 Celery/RQ 级 scheduler、dead-letter policy、autoscaling worker、Postgres 迁移或生产部署包已完成。

2026-06-06 update: external worker 已从 `/api/workers/run-once` 扩展为可独立启动的 worker loop；新增 `apps/api/worker.py`，可用 `python -m apps.api.worker --worker-id studio-worker-1` 或 `npm run worker -- --worker-id studio-worker-1` 启动，`WORKER_IDLE_SLEEP_SECONDS` 控制空队列轮询间隔。SQLite 新增 `workers` 表记录 worker heartbeat、当前任务、完成数、失败数和错误；`/api/job-queue/status` 返回 `workers`，前端任务队列面板展示 worker 状态。targeted worker tests、py_compile、`npm run test:web:model` 和全量 `npm run test` 已通过；全量测试包含 77 个后端测试、YamlEditor 静态检查、model profile workbench 静态检查和 Next 生产构建。该切片仍不是 Celery/RQ 级 scheduler、死信队列、autoscaling worker fleet 或生产部署包。
2026-06-06 update: 生产任务队列治理新增死信队列切片；`JobRecord` 新增 `dead_lettered` 生命周期状态、`dead_lettered_at`、`dead_letter_reason`、`dead_letter_source` 和 `requeue_count`，`execute_job` 会把耗尽 `max_attempts` 的失败任务隔离为死信，`GET /api/job-queue/status` 返回 `dead_lettered` 计数，`GET /api/job-queue/dead-letter` 返回失败/死信任务摘要，`POST /api/jobs/{job_id}` 的 `retry` 支持 failed/canceled/dead_lettered 并会在 external Redis broker 模式下重新推送 job id。前端任务队列面板新增 dead-letter 计数、隔离原因、最近死信条目和一键重入队；项目 readiness 会把死信任务作为交付阻断。targeted `python -m pytest apps/api/tests/test_pipeline.py -q -k "dead_letter or worker_loop_records_heartbeat or redis_broker_worker or external_generation_job_uses_configured_redis_broker or queued_job_can_be_canceled"` 已通过 6 个测试，`npm run test:web:model`、`npm --prefix apps/web run build` 和 py_compile 已通过。该切片是本地/准生产死信治理闭环，仍不等于完整 Celery/RQ 级 scheduler、autoscaling worker fleet、多租户限流或生产部署包。
