# ScriptBridge AI 小说剧本改编工作台

ScriptBridge AI 是一个前后端分离的本地 Web 工作台，用于把 3 个章节以上的小说文本转换为可追踪、可校验、可编辑的结构化剧本 YAML。

项目默认优先调用 OpenAI-compatible API，也支持本地 Ollama/vLLM。未配置模型或调用失败时，会自动使用 deterministic fallback 生成器，保证 Demo 可完整跑通。

当前项目已从比赛 MVP 方向升级为 Enterprise V2 方向：目标不是简单 prompt wrapper，而是小说证据链、故事圣经、场景编辑、质量门禁、制片拆解和导出一体化的 AI 剧本改编平台。V2 规划和完成边界见：

```text
ENTERPRISE_V2_PLAN.md
```

## 功能亮点

- 3 章以上小说导入和章节识别。
- 长篇上下文压缩：按章节保留标题、字数、段落数、首部/中部/尾部证据摘录和场景规划提示，避免 LLM 只读取小说开头。
- 段落编号、SQLite FTS + 本地 embedding 融合证据索引和 `source_refs` 来源追踪。
- 故事圣经：人物、地点、时间线、主题线、冲突线、伏笔线。
- 场景拆分：场景目的、冲突、人物、地点、节拍、情绪转折、制片备注。
- 企业级质量中心：章节覆盖、证据链、冲突强度、故事圣经完整度、可拍性评分。
- 制片拆解：预计页数、时长、演员、地点、拍摄天数、镜头计划。
- 局部场景改写：增强冲突、改写对白、短剧钩子、收紧证据；支持项目证据库检索、LLM JSON 改写计划和 fallback 规则。
- 批量场景改写任务：质量中心可把低证据链、低冲突或带质量标记的场景送入后台改写任务，完成后保存为新版本并写入审计。
- 本地项目库：创建、保存、打开项目，SQLite 持久化项目和版本。
- 项目版本治理：版本摘要、当前版本标记、版本比较、场景变化清单、YAML diff 预览、按权限恢复版本并写入审计。
- 项目交付门禁：按源文导入、当前版本、Schema、质量分、证据链覆盖、制片拆解、导入安全、未解决审阅意见和任务队列状态计算可交付性，右侧项目检查器展示阻塞项、警告项、通过项和下一步动作。
- 交付审批中心：编剧/主编/项目负责人可提交当前版本进入审批，制片/主编/项目负责人可批准或驳回；审批会记录版本、门禁分、阻塞/警告、审批意见、通知和审计事件。
- 交付包中心：制片/主编/项目负责人可基于已批准审批生成正式交付包，包含 YAML/Markdown/Fountain/JSON 资产、manifest、资产 sha256、总大小、版本、审批、门禁快照和审计事件；当前本地底座会把交付资产写入 `.scriptbridge_data/delivery-artifacts/`，历史包可通过 1 小时签名 URL 复取下载，前端下载后会做 sha256 校验。
- 审阅协作基础：项目成员、项目成员会话、Bearer token 鉴权、角色权限、项目/场景评论、评论指派、线程回复、评论解决/重开、通知、右侧审阅面板和审计事件过滤。
- 后台生成任务：启动项目级生成任务、记录进度事件、SSE 实时进度流、保存版本快照；支持 `inline`、`background`、`external` 三种队列模式、Redis broker 适配层、Worker run-once 执行入口、死信隔离和人工重入队。
- 任务化源文导入：`.txt/.md/.markdown/.docx/.pdf` 上传可进入统一任务队列，记录进度事件，支持 inline/background/external 执行和 Redis broker 分发，完成后回填项目源文、章节索引和审计事件；本地分片/可续传上传会话已接入导入任务，导入链路记录 sha256、上传模式、本地静态安全扫描、可选外部/ClamAV 风格扫描报告和脱敏导入历史。
- 结构化剧本 YAML 生成。
- YAML 语法、JSON Schema、人物/地点/段落引用校验，以及带行号、诊断列表、状态栏的问题定位式 YAML 编辑器壳。
- 企业级产品工作台：Arc Studio 风格剧本编辑器、场景索引、故事结构、原文证据、改写结果、质量中心、制片拆解、YAML。
- 导出 YAML、JSON、Markdown、Fountain。
- 项目级导出治理：基于当前版本和交付门禁导出，记录格式、版本、actor、文件大小、sha256、门禁分数、阻塞/警告、导出历史和审计事件。
- API 模型和本地部署模型双模式。

## 技术栈

前端：

- Next.js
- React
- TypeScript
- Tailwind CSS
- lucide-react

后端：

- FastAPI
- Pydantic
- PyYAML
- jsonschema
- httpx
- python-docx
- pypdf
- redis
- pytest

模型：

- API：任意 OpenAI-compatible `/chat/completions`
- 本地：Ollama、vLLM、llama.cpp 等 OpenAI-compatible 服务
- fallback：无 key 或模型失败时的离线生成器

## 目录结构

```text
apps/
  api/                 # FastAPI 后端
  web/                 # Next.js 前端
docs/
  SCHEMA.md            # YAML Schema 设计说明
  DEMO.md              # 演示流程
examples/
  sample_novel.md      # 三章样例小说
schemas/
  screenplay.schema.json
AI_NOVEL_TO_SCREENPLAY_DESIGN.md
PROJECT_CONTEXT.md
PRODUCT.md
DESIGN.md
```

## 快速开始

### 1. 启动后端

```powershell
python -m pip install -r apps/api/requirements.txt
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

检查：

```text
http://127.0.0.1:8000/health
```

### 2. 启动前端

```powershell
npm --prefix apps/web install
npm --prefix apps/web run dev
```

打开：

```text
http://127.0.0.1:3000
```

### 3. 启动 external worker（可选）

当 `JOB_QUEUE_MODE=external` 时，另开终端运行：

```powershell
python -m apps.api.worker --worker-id studio-worker-1
```

## 使用工作台

当前前端按 B 方案落地为 Arc Studio 式专业编剧工作台：

- 左栏是素材台：项目设定、模型连接、文件导入、小说原文、章节证据索引和本地项目库。
- 中间是剧本桌面：工作区状态条、场景索引、剧本文稿、故事结构、质量中心、制片拆解和 YAML。
- 右栏是检查器：场景检查、原文证据、审阅协作、导入历史、版本治理、改写差异、任务队列、流水线和开源底层。

文件导入支持 `.txt`、`.md`、`.markdown`、`.docx`、文本型 `.pdf`。后端会自动识别 UTF-8/UTF-8 BOM/GB18030，使用 `python-docx` 提取 Word 段落，使用 `pypdf` 按页提取 PDF 文本，规范化换行，清理 Markdown 顶层标题，并返回章节数、段落数、字节数、sha256、提取方式、文档统计和安全扫描报告。当前已支持导入任务进入统一队列、SSE/Worker 进度、项目审计、本地分片/可续传上传会话、扩展名/文件签名/MIME 一致性检查、可插拔外部/ClamAV 风格扫描和导入历史安全治理展示；扫描 PDF OCR、对象存储隔离和完整隔离区运营仍属于后续企业级增强。

### 导入安全扫描

默认只启用本地静态扫描：

```powershell
$env:IMPORT_SECURITY_SCANNER="local"
```

接入外部病毒扫描或 ClamAV HTTP 网关时：

```powershell
$env:IMPORT_SECURITY_SCANNER="clamav"
$env:IMPORT_SECURITY_EXTERNAL_ENDPOINT="http://127.0.0.1:3310/scan"
$env:IMPORT_SECURITY_EXTERNAL_SCANNER_NAME="clamav-http"
$env:IMPORT_SECURITY_EXTERNAL_TIMEOUT_SECONDS="15"
$env:IMPORT_SECURITY_ON_UNAVAILABLE="block"
```

说明：

- 外部扫描响应需要返回 JSON：`scanner`、`verdict`、`risk_level`、`checks`、`warnings`、`blocked_reasons`。
- `verdict` 支持 `clean`、`warning/suspicious`、`blocked/infected/malicious` 语义。
- `IMPORT_SECURITY_ON_UNAVAILABLE=block` 是 fail-closed；设为 `warn` 时扫描器不可用会保留 warning 并允许导入继续。
- 直接导入、任务化导入和分片组装导入共用同一扫描结果模型。

## 模型配置

### API 模式

```powershell
$env:LLM_PROVIDER="api"
$env:OPENAI_API_KEY="你的 key"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
$env:MODEL_NAME="gpt-5.5"
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

### 服务端密钥引用

生产或准生产环境不建议把模型 key 放进浏览器表单。可以只在项目设置和任务 payload 中保存一个脱敏引用名，让后端或 external worker 在服务端环境变量中解析真实 key：

```powershell
$env:LLM_PROVIDER="api"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
$env:MODEL_NAME="gpt-5.5"
$env:OPENAI_API_KEY_SECRET_REF="studio-prod"
$env:MODEL_SECRET_STUDIO_PROD="你的服务端 key"
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

运行时也可以在前端“模型连接”面板填写“服务端密钥引用”。例如填写 `studio-prod` 时，后端会按 `MODEL_SECRET_STUDIO_PROD`、`MODEL_SECRET_REF_STUDIO_PROD`、`OPENAI_API_KEY_STUDIO_PROD` 的顺序查找服务端环境变量。

### 本地模型模式

以 Ollama 为例：

```powershell
$env:LLM_PROVIDER="local"
$env:OPENAI_BASE_URL="http://127.0.0.1:11434/v1"
$env:OPENAI_API_KEY="ollama"
$env:MODEL_NAME="qwen3"
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

说明：

- 前端提供模型连接中心，可在 API、本地 OpenAI-compatible 服务和 fallback 之间切换。
- 前端运行时输入的 API key 只用于当前浏览器会话发起请求；项目设置和任务 payload 只保存脱敏的 provider/base_url/model/has_api_key/api_key_secret_ref 摘要。
- 服务端密钥引用不会把真实 key 返回给浏览器，也不会把真实 key 写入项目设置或任务 payload；如果引用没有解析到服务端环境变量，连接测试会明确失败并提示引用未解析。
- 后端统一通过 `LLMProvider` 调用模型，并提供 `/api/model-profiles/test` 做短超时连接测试。
- 模型失败时响应中会标记 `provider_status=fallback` 和 warnings。

## 生产任务队列 / Redis broker

默认 `JOB_QUEUE_MODE=background` 会使用 FastAPI 后台任务，适合本地演示。准生产或多进程 worker 验证时可切到 external 模式，并配置 Redis broker：

```powershell
$env:JOB_QUEUE_MODE="external"
$env:JOB_BROKER_URL="redis://127.0.0.1:6379/0"
$env:JOB_BROKER_QUEUE="scriptbridge:jobs:default"
$env:JOB_BROKER_POP_TIMEOUT_SECONDS="1"
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

另开一个终端启动独立 worker：

```powershell
$env:JOB_QUEUE_MODE="external"
$env:JOB_BROKER_URL="redis://127.0.0.1:6379/0"
python -m apps.api.worker --worker-id studio-worker-1
```

也可以通过根命令启动：

```powershell
npm run worker -- --worker-id studio-worker-1
```

也可以使用 `REDIS_URL` 作为 `JOB_BROKER_URL` 的 fallback。external 模式下，新任务会先写入 SQLite job 表，再把 job id 推入 Redis list；Worker 通过独立 worker 进程或 `/api/workers/run-once` 从 Redis 队列弹出 job id，并使用 SQLite claim 防止 stale/canceled job 被执行。独立 worker 会把心跳、当前任务、完成数和失败数写入本地 SQLite，方便前端任务队列面板和 `/api/job-queue/status` 观察运行状态。

任务失败治理：
- 达到 `max_attempts` 的失败任务会进入 `dead_lettered` 状态，保留 `dead_lettered_at`、`dead_letter_reason`、`dead_letter_source` 和 `requeue_count`。
- `GET /api/job-queue/dead-letter` 返回失败/死信任务摘要，前端任务队列面板会显示 dead-letter 计数、最近隔离条目和原因。
- `POST /api/jobs/{job_id}` 的 `retry` 支持把 `failed`、`canceled` 或 `dead_lettered` 任务重新入队；死信重入队会清理隔离元数据、重置尝试次数，并在 external Redis broker 模式下重新推送 job id。

说明：

- `/api/job-queue/status` 会返回 `broker`、`broker_queue`、`broker_depth`、`broker_error`、`dead_lettered` 和 `workers`，前端任务队列面板会展示这些 broker/worker/死信元数据。
- Redis broker 是当前生产化队列的适配层，解决 external worker 的跨进程任务分发；死信队列已具备本地治理闭环，但它还不是完整 Celery/RQ 调度器、Kubernetes worker 部署包、自动伸缩 worker fleet 或多租户限流体系。
- 如果未配置 `JOB_BROKER_URL`/`REDIS_URL`，external worker 会回退到 SQLite queued job claim 路径，便于本地测试，但系统就绪门禁会继续把它标为非最终生产状态。

## 交付资产存储配置

正式交付包资产通过可插拔 provider 访问：

```powershell
$env:DELIVERY_ARTIFACT_PROVIDER="local"
$env:DELIVERY_ARTIFACT_LOCAL_DIR=""
$env:DELIVERY_ARTIFACT_ENDPOINT=""
$env:DELIVERY_ARTIFACT_BUCKET=""
$env:DELIVERY_ARTIFACT_ACCESS_KEY_ID=""
$env:DELIVERY_ARTIFACT_SECRET_ACCESS_KEY=""
$env:DELIVERY_ARTIFACT_REGION="us-east-1"
$env:DELIVERY_ARTIFACT_FORCE_PATH_STYLE=""
$env:DELIVERY_ARTIFACT_PREFIX=""
$env:DELIVERY_ARTIFACT_DOMAIN=""
$env:DELIVERY_ARTIFACT_QINIU_ACCESS_KEY=""
$env:DELIVERY_ARTIFACT_QINIU_SECRET_KEY=""
$env:DELIVERY_ARTIFACT_QINIU_DOMAIN=""
$env:DELIVERY_ARTIFACT_QINIU_UPLOAD_TOKEN_EXPIRES="3600"
$env:DELIVERY_ARTIFACT_QINIU_DOWNLOAD_URL_EXPIRES="3600"
$env:DELIVERY_SIGNING_SECRET="your-signing-secret"
```

说明：

- 默认 `local` 会把交付资产写入 `.scriptbridge_data/delivery-artifacts/`，也可以用 `DELIVERY_ARTIFACT_LOCAL_DIR` 指定本地根目录。
- `s3` 使用 boto3 S3 client 写入和读取正式交付资产；`DELIVERY_ARTIFACT_ENDPOINT` 对 AWS S3 可为空，对兼容服务可填写服务地址。
- `minio` 使用同一套 S3-compatible adapter，要求配置 `DELIVERY_ARTIFACT_ENDPOINT`，默认启用 path-style addressing。
- `s3`/`minio` 需要 `DELIVERY_ARTIFACT_BUCKET`、`DELIVERY_ARTIFACT_ACCESS_KEY_ID`、`DELIVERY_ARTIFACT_SECRET_ACCESS_KEY`；可选 `DELIVERY_ARTIFACT_REGION`、`DELIVERY_ARTIFACT_FORCE_PATH_STYLE`、`DELIVERY_ARTIFACT_PREFIX`。
- `qiniu` 使用七牛 Kodo Python SDK 写入正式交付资产，并通过七牛私有下载 URL 读取；需要 `DELIVERY_ARTIFACT_BUCKET`、`DELIVERY_ARTIFACT_QINIU_ACCESS_KEY`、`DELIVERY_ARTIFACT_QINIU_SECRET_KEY`、`DELIVERY_ARTIFACT_QINIU_DOMAIN`。也可用通用 `DELIVERY_ARTIFACT_ACCESS_KEY_ID`、`DELIVERY_ARTIFACT_SECRET_ACCESS_KEY` 作为七牛 key fallback。
- `qiniu` 可选 `DELIVERY_ARTIFACT_PREFIX`、`DELIVERY_ARTIFACT_QINIU_UPLOAD_TOKEN_EXPIRES`、`DELIVERY_ARTIFACT_QINIU_DOWNLOAD_URL_EXPIRES`；缺配置或 SDK/网络读写失败时 API 会返回 503，不会伪装成已成功存储。
- 历史交付包会保存每个资产的 `storage_provider` 和 `storage_key`，下载时按资产记录读取，避免运行时 provider 切换后破坏旧包复取。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| GET | `/api/capabilities` | 企业级能力清单 |
| GET | `/api/system-readiness` | 查询系统级部署就绪门禁，检查数据库、队列、模型密钥、导入扫描、交付存储和认证签名配置 |
| GET | `/api/model-profiles` | 查询脱敏后的默认模型 profile 和本地/fallback 预设 |
| POST | `/api/model-profiles/test` | 测试 API 或本地 OpenAI-compatible 模型连接 |
| POST | `/api/import/source` | 上传 `.txt/.md/.markdown/.docx/.pdf` 小说源文件并返回正文、提取方式、文档统计、章节数、段落数和导入警告 |
| POST | `/api/jobs/import-source` | 以任务方式上传源文件，支持自动创建项目或更新现有项目，完成后回填源文、章节元数据和导入审计 |
| POST | `/api/import-sessions` | 创建本地分片导入会话，记录文件元数据、目标项目和分片参数 |
| GET | `/api/import-sessions/{session_id}` | 查询分片导入会话状态、已上传分片和进度 |
| PUT | `/api/import-sessions/{session_id}/chunks/{chunk_index}` | 上传指定分片，支持断点后继续补齐缺失分片 |
| POST | `/api/import-sessions/{session_id}/complete` | 组装已上传分片并派发普通导入任务 |
| GET | `/api/projects/{project_id}/import-history` | 查询项目导入历史，返回脱敏文件元数据、阶段、提取统计、警告和审计关联，不返回正文或本地暂存路径 |
| GET | `/api/sample` | 获取样例小说 |
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects` | 创建项目 |
| GET | `/api/projects/{project_id}` | 项目详情 |
| PATCH | `/api/projects/{project_id}` | 更新项目 |
| GET | `/api/projects/{project_id}/versions` | 查询项目版本摘要和当前版本 |
| GET | `/api/projects/{project_id}/versions/compare` | 比较两个版本，返回场景变化和 YAML diff 预览 |
| POST | `/api/projects/{project_id}/versions/{version_id}/restore` | 按权限恢复指定版本为当前版本，并写入审计事件 |
| GET | `/api/projects/{project_id}/readiness` | 查询项目交付门禁，返回总状态、分数、阻塞项、警告项、通过项和下一步动作 |
| GET | `/api/projects/{project_id}/approvals` | 查询项目交付审批历史，返回待审批、已批准、已驳回、已撤回和被阻塞记录 |
| POST | `/api/projects/{project_id}/approvals` | 提交当前或指定版本进入交付审批；门禁阻塞会返回 409 并写入 `approval.blocked` 审计 |
| POST | `/api/projects/{project_id}/approvals/{approval_id}/decision` | 批准、驳回或撤回交付审批，并通知提交人 |
| GET | `/api/projects/{project_id}/delivery-packages` | 查询正式交付包历史，返回包状态、版本、审批、资产清单、manifest hash、门禁分数和审计关联；有 `package_delivery` 权限时返回临时签名下载链接 |
| POST | `/api/projects/{project_id}/delivery-packages` | 基于已批准审批生成正式交付包；缺少审批或门禁阻塞会返回 409 并写入 `delivery_package.blocked`，成功写入 `delivery_package.created` 并落盘本地 artifact |
| GET | `/api/projects/{project_id}/delivery-packages/{package_id}/assets/{asset_sha256}` | 使用签名 token 下载交付包资产，后端校验 token、过期时间和 artifact sha256 |
| GET | `/api/projects/{project_id}/exports` | 查询项目导出历史，返回格式、版本、状态、actor、文件大小、sha256、门禁分数和审计关联 |
| POST | `/api/projects/{project_id}/exports` | 创建项目级治理导出；阻塞项会返回 409 并写入 `export.blocked` 审计，成功导出写入 `export.created` |
| POST | `/api/auth/sessions` | 为项目成员创建本地会话，返回 Bearer token |
| POST | `/api/projects/{project_id}/members` | 添加或更新项目成员，受 owner/admin 权限控制 |
| POST | `/api/projects/{project_id}/comments` | 创建项目或场景审阅意见，并写入审计事件 |
| POST | `/api/projects/{project_id}/comments/{comment_id}/replies` | 回复审阅意见线程，并写入回复审计事件 |
| PATCH | `/api/projects/{project_id}/comments/{comment_id}` | 更新审阅意见状态，并写入解决/重开审计事件 |
| GET | `/api/projects/{project_id}/audit-events` | 查询项目审计事件，支持按事件类型或 actor 过滤 |
| GET | `/api/projects/{project_id}/notifications` | 查询项目通知，支持 recipient 和 unread 过滤 |
| PATCH | `/api/projects/{project_id}/notifications/{notification_id}` | 通知接收者标记已读或未读 |
| POST | `/api/jobs/generate` | 启动项目级生成任务 |
| POST | `/api/jobs/rewrite` | 启动项目级批量场景改写任务 |
| GET | `/api/job-queue/status` | 查询任务队列模式、状态计数、Redis/SQLite broker 元数据和 Worker 提示 |
| GET | `/api/job-queue/dead-letter` | 查询失败/死信任务摘要、隔离原因和重入队计数 |
| POST | `/api/jobs/{job_id}` | 取消或重试任务 |
| POST | `/api/workers/run-once` | 执行一个 external 队列任务 |
| GET | `/api/jobs/{job_id}` | 查询任务进度 |
| GET | `/api/jobs/{job_id}/events` | SSE 订阅任务进度 |
| GET | `/api/projects/{project_id}/jobs` | 查询项目任务 |
| POST | `/api/projects/{project_id}/evidence/search` | 搜索项目证据库 |
| POST | `/api/detect-chapters` | 章节识别 |
| POST | `/api/generate` | 生成剧本 |
| POST | `/api/rewrite-scene` | 局部场景改写，返回 evidence 和 diff_summary |
| POST | `/api/validate` | 校验 YAML |
| POST | `/api/export/yaml` | 导出 YAML |
| POST | `/api/export/json` | 导出 JSON |
| POST | `/api/export/markdown` | 导出 Markdown |
| POST | `/api/export/fountain` | 导出 Fountain |

## 测试

后端测试：

```powershell
python -m pytest apps/api/tests
```

前端构建：

```powershell
npm --prefix apps/web run build
```

全部验证：

```powershell
npm run test
```

## YAML Schema

Schema 文件：

```text
schemas/screenplay.schema.json
```

设计说明：

```text
docs/SCHEMA.md
```

## Demo

演示步骤见：

```text
docs/DEMO.md
```

推荐演示流程：

1. 点击“样例”。
2. 点击“索引”。
3. 点击“直接运行”或“启动任务”。
4. 查看剧本文稿、场景索引和右侧原文证据。
5. 切换 YAML，点击“校验”。
6. 在右侧“交付审批”中提交当前版本，由制片身份批准或驳回。
7. 在右侧“交付包”中基于已批准审批生成正式交付包，并检查 manifest hash、资产 sha256 和审计记录。
8. 在右侧“导出治理”中导出 YAML、Markdown、Fountain，并检查导出历史、门禁状态和审计记录。

## 开源项目

- Monaco Editor：后续可替换当前轻量 `YamlEditor` 为完整 Monaco 编辑器。
- yaml-language-server：后续可接入 YAML Schema 自动补全。
- Ajv：前端 Schema 校验可扩展选项。
- Pydantic：后端结构化模型和校验。
- python-docx：DOCX 稿件正文提取。
- pypdf：文本型 PDF 稿件正文提取。
- redis-py：external worker 模式下的 Redis list broker 适配层。
- Fountain：剧本导出格式。
- ScreenJSON：Schema 设计参考。
- Ollama/vLLM：本地模型服务。

## 当前实现说明

当前 YAML 编辑器已从单一 textarea 升级为诊断型编辑器壳，包含行号、校验状态、诊断列表和问题定位入口，并保留 `YamlEditor` 组件边界。后续仍应升级为 Monaco Editor + YAML language server。

Enterprise V2 已新增 SQLite 持久化、SQLite FTS + 本地 embedding 融合证据索引、可切换任务队列底座、Redis broker 适配层、死信队列治理、SSE 进度流、长篇章节级上下文压缩、证据检索、LLM 约束局部改写入口、批量改写任务、任务化源文导入、本地分片上传会话、导入安全治理、可插拔外部病毒扫描底座、导入历史治理、版本治理、项目交付门禁、系统级部署就绪门禁、交付审批中心、交付包中心、本地 artifact store、S3/MinIO/七牛 Kodo artifact adapter、签名下载中心、项目级导出治理、成员/RBAC 底座、项目成员会话、Bearer token 鉴权、审阅评论指派、线程回复、状态流转、通知、审计过滤和 Arc Studio 风格工作台。`/api/system-readiness` 会检查 Postgres/DATABASE_URL、external 队列 broker、服务端模型密钥引用、外部导入扫描、远端交付对象存储和认证/签名配置，并在前端项目检查器显示部署阻塞项。当前运行数据写入 `.scriptbridge_data/`，local 交付资产写入 `.scriptbridge_data/delivery-artifacts/`，这些目录不会提交。正式企业级部署时仍应替换为 Postgres、Celery/RQ 或等价生产调度器、独立 worker 部署包、pgvector/外部 embedding 服务，并继续补齐密码/SSO 登录、实时协作、外部通知投递、OCR、对象存储隔离区/隔离运营、CDN/生命周期/水印/PDF 渲染、不可变留存和生产级审计。
