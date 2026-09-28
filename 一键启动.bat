@echo off
chcp 65001 >nul
title StudyMind 一键启动
echo ==================================================
echo    StudyMind —— 基于大模型的个性化AI学习助手
echo    一键启动脚本（Windows）
echo ==================================================
echo.

cd /d "%~dp0"

REM ---------- 0. 检查 API 密钥 ----------
findstr /c:"sk-在此填入你的密钥" .env >nul 2>&1
if not errorlevel 1 (
    echo [X] 尚未配置 DeepSeek API 密钥！
    echo     请用记事本打开本目录下的 .env 文件，
    echo     把第一行 DEEPSEEK_API_KEY= 后面的占位文字替换成真实密钥后保存。
    echo.
    pause
    exit /b 1
)

REM ---------- 1. 检查 Docker ----------
docker info >nul 2>&1
if errorlevel 1 (
    echo [X] 未检测到 Docker！请先安装并启动 Docker Desktop
    echo     （下载地址 https://www.docker.com/products/docker-desktop/）
    pause
    exit /b 1
)

REM ---------- 2. 导入数据库镜像（仅首次需要） ----------
docker images --format "{{.Repository}}:{{.Tag}}" | findstr /c:"postgres:16" >nul 2>&1
if errorlevel 1 (
    echo [i] 首次运行：导入 PostgreSQL 镜像（约 1 分钟）...
    docker load -i docker-images\postgres16.tar
)
docker images --format "{{.Repository}}:{{.Tag}}" | findstr /c:"neo4j:5-community" >nul 2>&1
if errorlevel 1 (
    echo [i] 首次运行：导入 Neo4j 镜像（约 1 分钟）...
    docker load -i docker-images\neo4j5.tar
)

REM ---------- 3. 启动数据库 ----------
echo [i] 启动数据库容器（PostgreSQL + Neo4j）...
docker compose up -d
if errorlevel 1 (
    echo [X] 数据库容器启动失败，请检查 Docker Desktop 是否已启动。
    pause
    exit /b 1
)

REM ---------- 4. 安装 Python 依赖（仅首次） ----------
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [i] 首次运行：安装 Python 依赖（约 3~5 分钟，之后不再重复）...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [X] 依赖安装失败，请确认已安装 Python 3.10~3.12 并加入 PATH。
        pause
        exit /b 1
    )
)

REM ---------- 5. 启动后端 ----------
echo [i] 等待数据库就绪...
timeout /t 8 /nobreak >nul
echo [i] 正在启动服务，浏览器将自动打开 http://localhost:8000
echo     关闭本窗口即停止服务。
start "" http://localhost:8000
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
