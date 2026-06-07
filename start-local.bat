@echo off
REM NovelScripter 本地启动脚本（Windows）
REM 适用于快速开发和 Demo 验证

echo === NovelScripter 本地启动 ===

REM -------------------- 配置环境变量 --------------------
echo [1/4] 配置环境变量...

if not exist .env (
    echo   复制 .env.example - .env
    copy .env.example .env
    echo   !! 请编辑 .env 填入你的 API Key
    echo   !! 至少填 OPENAI_API_KEY 或 DEEPSEEK_API_KEY
    echo   !! 然后重新运行此脚本
    pause
    exit /b 1
)

REM -------------------- 后端 --------------------
echo [2/4] 启动后端 FastAPI...

cd apps\api

REM 安装依赖
if not exist venv (
    echo   创建 Python 虚拟环境...
    python -m venv venv
)

call venv\Scripts\activate

echo   安装 Python 依赖...
pip install -r requirements.txt -q

echo   启动 FastAPI (端口 8000)...
start "NovelScripter API" cmd /k "venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"

cd ..\..

REM -------------------- 前端 --------------------
echo [3/4] 启动前端 Next.js...

cd apps\web

REM 安装依赖
if not exist node_modules (
    echo   安装 Node 依赖...
    call npm install
)

echo   启动 Next.js (端口 3000)...
start "NovelScripter Web" cmd /k "npm run dev"

cd ..\..

REM -------------------- 完成 --------------------
echo [4/4] 服务已启动！
echo.
echo   前端: http://localhost:3000
echo   后端: http://localhost:8000
echo   API文档: http://localhost:8000/docs
echo.
echo   关闭对应命令窗口即可停止服务
pause