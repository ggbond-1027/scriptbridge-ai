#!/bin/bash
# NovelScripter 本地启动脚本（无需 Docker）
# 适用于快速开发和 Demo 验证

set -e

echo "=== NovelScripter 本地启动 ==="

# -------------------- 配置环境变量 --------------------
echo "[1/4] 配置环境变量..."

if [ ! -f .env ]; then
    echo "  复制 .env.example → .env"
    cp .env.example .env
    echo "  ⚠ 请编辑 .env 填入你的 API Key（至少填 OPENAI_API_KEY 或 DEEPSEEK_API_KEY）"
    echo "  然后重新运行此脚本"
    exit 1
fi

# -------------------- 后端 --------------------
echo "[2/4] 启动后端 FastAPI..."

cd apps/api

# 安装依赖（如果还没安装）
if [ ! -d "venv" ]; then
    echo "  创建 Python 虚拟环境..."
    python -m venv venv
fi

source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

echo "  安装 Python 依赖..."
pip install -r requirements.txt -q

echo "  启动 FastAPI (端口 8000)..."
uvicorn app.main:app --reload --port 8000 &
API_PID=$!

cd ../..

# -------------------- 前端 --------------------
echo "[3/4] 启动前端 Next.js..."

cd apps/web

# 安装依赖（如果还没安装）
if [ ! -d "node_modules" ]; then
    echo "  安装 Node 依赖..."
    npm install
fi

echo "  启动 Next.js (端口 3000)..."
npm run dev &
WEB_PID=$!

cd ../..

# -------------------- 等待 --------------------
echo "[4/4] 服务已启动！"
echo ""
echo "  前端: http://localhost:3000"
echo "  后端: http://localhost:8000"
echo "  API文档: http://localhost:8000/docs"
echo ""
echo "  按 Ctrl+C 停止所有服务"

wait