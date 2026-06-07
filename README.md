# NovelScripter — AI 小说转剧本工具

面向小说作者的 AI 辅助剧本创作工作台，将多章节小说自动转换为结构化剧本 YAML 格式，让作者快速获得可编辑、可追踪、可校验、可导出的专业剧本草稿。

## 在线演示

- 演示站点：[https://novel.ggbond686.online](https://novel.ggbond686.online)

## 功能亮点

1. **Schema-first 剧本生成** — 先定义结构，再让 AI 填充，输出稳定可控
2. **多阶段改编 Pipeline** — 7阶段从理解到生成，避免单 prompt 失控
3. **故事圣经** — 全局人物表、地点表、时间线，保证跨章节一致性
4. **来源追踪** — 每个场景可回到小说原文段落，降低 AI 幻觉风险
5. **可校验 YAML** — Pydantic + JSON Schema + 引用一致性三层校验
6. **局部再生成** — 只改一个场景或一句对白，不全篇重写
7. **章节级流水线与增量缓存** — 已完成章节可继续向后处理，重复运行可复用缓存减少等待
8. **API 与本地模型双模式** — 云端 API 或 Ollama/vLLM 本地部署
9. **标准剧本导出** — YAML / JSON / Markdown / Fountain / ZIP / 说明文档

## 技术架构

当前可运行版本采用前后端分离架构：

- **客户端层**：React 18 + Next.js 14 + TypeScript + Tailwind CSS + Zustand + React Flow
- **服务层**：FastAPI + Pydantic + httpx，提供项目、流水线、编辑、导出和模型连接 API
- **AI 引擎层**：OpenAI-compatible `/chat/completions`，支持 API 网关和本地 OpenAI-compatible 服务
- **数据层**：本地 SQLite 项目快照，保存项目、章节、剧本、故事圣经、缓存和导出相关状态
- **部署层**：Docker production 配置，线上部署在独立子域名 `novel.ggbond686.online`

## 快速开始

如果只是查看效果，可以直接访问线上演示站点；如果要在本地修改和调试，请按下面步骤启动。

### 1. 安装依赖

```bash
# 后端
cd apps/api
pip install -r requirements.txt

# 前端
cd apps/web
npm install
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key 或本地模型地址
```

不要把 `.env`、API key、token、数据库文件或本地运行日志提交到仓库。

### 3. 启动服务

```bash
# Docker Compose 开发环境
docker compose -f docker-compose.dev.yml up -d

# 或手动启动
# 后端
cd apps/api && uvicorn app.main:app --reload --port 8000

# 前端
cd apps/web && npm run dev
```

访问 http://localhost:3000 打开工作台。

### 4. 快速脚本启动

Windows:

```bash
start-local.bat
```

macOS/Linux:

```bash
./start-local.sh
```

### 5. 生产部署参考

生产 Docker 配置位于：

```text
deploy/production/
```

线上版本已按该目录的轻量生产方案部署，前端和后端分别运行，并由反向代理把 `/api/*` 转发到 FastAPI。

## 模型配置

### API 模式（推荐，保证 Demo 质量）

```env
LLM_PROVIDER=api
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o

# 也可以使用 DeepSeek、通义千问、Kimi、Gemini 等提供 OpenAI-compatible 接口的网关
OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1
MODEL_NAME=your-model-name
```

### 本地模型模式

```env
# Ollama
LLM_PROVIDER=local
OPENAI_BASE_URL=http://localhost:11434/v1
MODEL_NAME=qwen3
OPENAI_API_KEY=ollama

# vLLM
LLM_PROVIDER=local
OPENAI_BASE_URL=http://localhost:8000/v1
MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
```

说明：

- 前端模型设置面板支持临时填写 OpenAI-compatible base URL、model 和 API key。
- 本地项目快照会过滤 `api_key`、`token`、`secret`、`password`、`private_key` 等敏感字段。
- 真实生产环境建议使用服务端环境变量或密钥管理系统保存模型 key，不建议把 key 写进前端代码或文档。

## YAML Schema 说明

详见 [docs/SCHEMA.md](docs/SCHEMA.md) — 包含完整的 Schema 定义和设计原因说明。

核心 Schema 文件：[apps/api/app/schemas/screenplay.schema.json](apps/api/app/schemas/screenplay.schema.json)

面向评审和用户阅读的说明文档还包括：

- [docs/YAML_SCREENPLAY_SCHEMA.md](docs/YAML_SCREENPLAY_SCHEMA.md)：解释什么是 Schema、YAML Schema 的结构，以及本项目为什么这样设计。
- 前端“说明文档”Tab：内置 `YAML Schema` 和 `Schema 设计原因` 两个子 Tab。
- 导出中心：支持导出说明文档 ZIP，包含 Schema 文档、设计说明、机器校验 JSON Schema 和 manifest。

## 网页简单使用步骤

1. 打开 [https://novel.ggbond686.online](https://novel.ggbond686.online) 或本地 `http://localhost:3000`。
2. 在首页导入小说：可以粘贴文本，也可以上传本地小说文件。
3. 在模型设置里填写 OpenAI-compatible API 配置，或使用本地模型/fallback 演示路径。
4. 点击“开始改编”，系统会创建项目并启动 7 阶段流水线。
5. 在左侧查看处理进度、章节结构和原文段落；左侧三个区域可以拖动分隔线调整高度。
6. 在中间查看章节、场景、对白、动作和来源段落引用。
7. 在故事圣经中查看人物、地点、时间线和关系图谱；关系图谱支持拖动、缩放、调整高度并保存布局。
8. 在右侧切换 `YAML`、`剧本预览`、`说明文档` 和 `生成日志`。
9. 在 `说明文档` 中查看 `YAML Schema` 和 `Schema 设计原因`。
10. 点击导出中心，导出 YAML、JSON、Markdown、Fountain、ZIP 或说明文档。

## 本地测试

后端语法检查：

```bash
cd apps/api
python -m py_compile app/main.py app/routers/projects.py
```

后端单元测试：

```bash
cd apps/api
python -m pytest
```

前端构建：

```bash
cd apps/web
npm run build
```

## Demo 操作流程

Demo 视频链接：待补充。

推荐录制流程：

1. 打开线上演示站点，说明它是“AI 小说转剧本工作台”。
2. 导入一篇 3 章以上小说，展示章节识别和原文段落。
3. 配置模型连接，点击“开始改编”。
4. 展示流水线进度：章节理解、故事圣经、场景拆分、元素生成、校验和导出准备。
5. 展示左侧可调区域：处理进度、章节结构、原文段落。
6. 展示中间剧本编辑区：场景目的、冲突、角色对白、动作和来源追踪。
7. 展示故事圣经：人物表、地点表、S 型时间线和关系图谱。
8. 展示右侧 YAML、剧本预览、说明文档和生成日志。
9. 打开说明文档，重点说明 `YAML Schema` 和 `Schema 设计原因` 两部分。
10. 打开导出中心，导出 YAML、JSON、Markdown、Fountain、ZIP 或说明文档。
11. 总结技术亮点：Schema-first、来源追踪、可编辑、可导出、章节级流水线、增量缓存和线上部署。

## 开源项目与许可证

| 项目 | 许可证 | 用途 |
|------|--------|------|
| Monaco Editor | MIT | YAML 源码编辑器 |
| yaml-language-server | MIT | YAML 智能提示 |
| Ajv | MIT | 前端 Schema 校验 |
| Pydantic | MIT | 后端数据模型 |
| Instructor | MIT | LLM 结构化输出 |
| LangGraph | MIT | AI 工作流 |
| Ollama | MIT | 本地模型部署 |
| vLLM | Apache 2.0 | GPU 推理服务 |
| Qwen3 | Apache 2.0 | 中文模型 |
| React Flow | MIT | 关系图可视化 |
| NovelForge | **AGPL-3.0** | **只参考思路，不直接复用代码** |

## 目录结构

```
NovelScripter/
├── apps/
│   ├── api/                    # 后端 FastAPI
│   │   ├── app/
│   │   │   ├── core/           # 核心引擎（ModelRouter/Pipeline/校验/导出）
│   │   │   ├── models/         # Pydantic 数据模型
│   │   │   ├── schemas/        # JSON Schema
│   │   │   ├── routers/        # API 路由
│   │   │   ├── services/       # 业务服务（章节解析/故事圣经/场景拆分）
│   │   │   ├── prompts/        # Prompt Library
│   │   │   └── config.py
│   │   ├── tests/
│   │   └── requirements.txt
│   └── web/                    # 前端 Next.js
│       ├── src/
│       │   ├── app/
│       │   ├── components/     # UI 组件（18个）
│       │   ├── features/       # 功能页面（5个）
│       │   ├── lib/            # 工具库（API/YAML/Fountain）
│       │   └── store/          # 状态管理（zustand）
│       └── package.json
├── docs/
│   ├── SCHEMA.md               # YAML Schema 设计说明文档
│   ├── YAML_SCREENPLAY_SCHEMA.md # Schema 定义与设计原因说明
│   ├── DEMO.md                 # Demo 视频脚本和答辩要点
│   └── DESIGN.md               # 设计概要
├── examples/
│   ├── sample_novel.txt        # 示例小说（雨夜来信 3章）
│   ├── sample_output.yaml      # 示例 YAML 剧本输出
│   └── sample_output.fountain  # 示例 Fountain 输出
├── docker-compose.dev.yml      # 开发环境 Docker
├── .env.example                # 环境变量模板
└── README.md
```

## 后续规划

- **v2.0**：多语言剧本支持、分镜描述、音效标注、多模型切换 UI 完善
- **v3.0**：互动剧本分支结构、观众选择点标注、批量 IP 评估
