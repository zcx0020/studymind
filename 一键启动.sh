#!/usr/bin/env bash
# StudyMind 一键启动（Linux / macOS / WSL）
set -e
cd "$(dirname "$0")"

echo "=================================================="
echo "   StudyMind —— 基于大模型的个性化AI学习助手"
echo "   一键启动脚本（Linux/macOS/WSL）"
echo "=================================================="

# 0. 检查 API 密钥
if grep -q "sk-在此填入你的密钥" .env; then
    echo "[X] 尚未配置 DeepSeek API 密钥！"
    echo "    请编辑 .env 文件，把 DEEPSEEK_API_KEY= 后面的占位文字替换成真实密钥。"
    exit 1
fi

# 1. 检查 Docker
if ! docker info >/dev/null 2>&1; then
    echo "[X] 未检测到 Docker！请先安装并启动 Docker。"
    exit 1
fi

# 2. 导入数据库镜像（仅首次需要）
if ! docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^postgres:16$"; then
    echo "[i] 首次运行：导入 PostgreSQL 镜像（约 1 分钟）..."
    docker load -i docker-images/postgres16.tar
fi
if ! docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^neo4j:5-community$"; then
    echo "[i] 首次运行：导入 Neo4j 镜像（约 1 分钟）..."
    docker load -i docker-images/neo4j5.tar
fi

# 3. 启动数据库
echo "[i] 启动数据库容器（PostgreSQL + Neo4j）..."
docker compose up -d

# 4. 安装 Python 依赖（仅首次）
if ! python3 -c "import fastapi" >/dev/null 2>&1; then
    echo "[i] 首次运行：安装 Python 依赖（约 3~5 分钟，之后不再重复）..."
    pip3 install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
fi

# 5. 启动后端
echo "[i] 等待数据库就绪..."
sleep 8
echo "[i] 正在启动服务：http://localhost:8000 （Ctrl+C 停止）"
cd backend
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
