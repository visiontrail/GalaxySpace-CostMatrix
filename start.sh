#!/bin/bash

# CostMatrix 一键启动脚本

REINSTALL_PY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reinstall-py-deps|-r)
      REINSTALL_PY=true
      shift
      ;;
    -h|--help)
      echo "用法: $0 [--reinstall-py-deps|-r]"
      exit 0
      ;;
    *)
      echo "未知参数: $1"
      echo "用法: $0 [--reinstall-py-deps|-r]"
      exit 1
      ;;
  esac
done

echo "🚀 Starting CostMatrix..."

# 检查是否安装了 Python 和 Node.js
command -v python3 >/dev/null 2>&1 || { echo "❌ Python3 未安装，请先安装 Python 3.8+"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ Node.js 未安装，请先安装 Node.js 16+"; exit 1; }

echo "✅ 环境检查通过"

# 启动后端
echo "📦 启动后端服务..."
cd backend

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建 Python 虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
if [ "$REINSTALL_PY" = true ]; then
    echo "重新安装 Python 依赖..."
    pip install --upgrade --force-reinstall -r requirements.txt
    touch venv/.installed
elif [ ! -f "venv/.installed" ]; then
    echo "安装 Python 依赖..."
    pip install -r requirements.txt
    touch venv/.installed
fi

# 启动后端服务
echo "🌐 后端服务启动中... (http://localhost:8000)"
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

cd ..

# 启动前端
echo "📦 启动前端服务..."
cd frontend

# 安装依赖
if [ ! -d "node_modules" ]; then
    echo "安装 Node.js 依赖..."
    npm install
fi

# 启动前端服务
echo "🌐 前端服务启动中... (http://localhost:5173)"
npm run dev &
FRONTEND_PID=$!

cd ..

echo ""
echo "✅ CostMatrix 已启动！"
echo ""
echo "📊 前端地址: http://localhost:5173"
echo "🔌 后端地址: http://localhost:8000"
echo "📖 API 文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止服务"

# 等待用户中断
trap "echo ''; echo '🛑 停止服务...'; kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait

