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
- 审阅协作基础：项目成员、项目成员会话、Bearer token 鉴权、角色权限、项目/场景评论、评论指派、线程回复、评论解决/重开、通知、右侧审阅面板和审计事件过滤。
- 后台生成任务：启动项目级生成任务、记录进度事件、SSE 实时进度流、保存版本快照；支持 `inline`、`background`、`external` 三种队列模式和 Worker run-once 执行入口。
- 结构化剧本 YAML 生成。
- YAML 语法、JSON Schema、人物/地点/段落引用校验，以及带行号、诊断列表、状态栏的问题定位式 YAML 编辑器壳。
- 企业级产品工作台：Arc Studio 风格剧本编辑器、场景索引、故事结构、原文证据、改写结果、质量中心、制片拆解、YAML。
- 导出 YAML、JSON、Markdown、Fountain。
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

## 模型配置

### API 模式

```powershell
$env:LLM_PROVIDER="api"
$env:OPENAI_API_KEY="你的 key"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
$env:MODEL_NAME="gpt-5.5"
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

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

- 前端不保存 API key。
- 后端统一通过 `LLMProvider` 调用模型。
- 模型失败时响应中会标记 `provider_status=fallback` 和 warnings。

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| GET | `/api/capabilities` | 企业级能力清单 |
| GET | `/api/sample` | 获取样例小说 |
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects` | 创建项目 |
| GET | `/api/projects/{project_id}` | 项目详情 |
| PATCH | `/api/projects/{project_id}` | 更新项目 |
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
| GET | `/api/job-queue/status` | 查询任务队列模式、状态计数和 Worker 提示 |
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
6. 导出 YAML、Markdown、Fountain。

## 开源项目

- Monaco Editor：后续可替换当前轻量 `YamlEditor` 为完整 Monaco 编辑器。
- yaml-language-server：后续可接入 YAML Schema 自动补全。
- Ajv：前端 Schema 校验可扩展选项。
- Pydantic：后端结构化模型和校验。
- Fountain：剧本导出格式。
- ScreenJSON：Schema 设计参考。
- Ollama/vLLM：本地模型服务。

## 当前实现说明

当前 YAML 编辑器已从单一 textarea 升级为诊断型编辑器壳，包含行号、校验状态、诊断列表和问题定位入口，并保留 `YamlEditor` 组件边界。后续仍应升级为 Monaco Editor + YAML language server。

Enterprise V2 已新增 SQLite 持久化、SQLite FTS + 本地 embedding 融合证据索引、可切换任务队列底座、SSE 进度流、长篇章节级上下文压缩、证据检索、LLM 约束局部改写入口、批量改写任务、成员/RBAC 底座、项目成员会话、Bearer token 鉴权、审阅评论指派、线程回复、状态流转、通知、审计过滤和 Arc Studio 风格工作台。当前运行数据写入 `.scriptbridge_data/`，该目录不会提交。正式企业级部署时应替换为 Postgres、Redis/Celery/RQ 等生产队列、对象存储、pgvector/外部 embedding 服务，并继续补齐密码/SSO 登录、实时协作、外部通知投递和生产级审计。
