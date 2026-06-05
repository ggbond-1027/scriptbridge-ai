# Demo 操作流程

## 启动

后端：

```powershell
python -m pip install -r apps/api/requirements.txt
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```powershell
npm --prefix apps/web install
npm --prefix apps/web run dev
```

打开：

```text
http://127.0.0.1:3000
```

## 演示脚本

1. 打开页面，说明这是本地 Web 工作台，前后端分离。
2. 点击“使用样例”，载入三章小说。
3. 点击“检测章节”，展示识别到 3 章和段落预览。
4. 保持“优先调用 API/本地模型”开启，点击“生成剧本”。
5. 如果没有 API key，系统会自动 fallback，并在顶部显示 provider 状态。
6. 展示故事圣经：人物、地点。
7. 展示场景卡片：场景目的、冲突、人物、地点。
8. 切换右侧 YAML，说明输出是结构化 YAML。
9. 点击“校验”，展示 Schema 通过。
10. 切换预览，展示标准剧本阅读效果。
11. 点击导出 YAML、Markdown、Fountain。

## 模型配置演示

API 模式：

```powershell
$env:LLM_PROVIDER="api"
$env:OPENAI_API_KEY="你的 key"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
$env:MODEL_NAME="gpt-5.5"
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

本地 Ollama/vLLM 模式：

```powershell
$env:LLM_PROVIDER="local"
$env:OPENAI_BASE_URL="http://127.0.0.1:11434/v1"
$env:OPENAI_API_KEY="ollama"
$env:MODEL_NAME="qwen3"
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

## 讲解重点

- 多阶段 Pipeline：章节识别、故事圣经、场景拆分、剧本生成、Schema 校验。
- Schema-first：后端使用 Pydantic 结构化对象，最终序列化为 YAML。
- 来源追踪：场景保留 `source_refs`。
- 双模型路径：API 优先，本地 OpenAI-compatible 模型可切换，失败有 fallback。
- 交付完整：YAML、Markdown、Fountain、Schema 文档、README、测试。
