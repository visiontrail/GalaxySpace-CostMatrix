#!/bin/bash

################################################################################
# CostMatrix 开发环境快速重启脚本
# 功能：快速应用代码变更，无需重新安装依赖
# 适用场景：修改了业务代码，但未新增 npm/pip 依赖
################################################################################

set -e

echo "=========================================="
echo "  CostMatrix 快速重启脚本"
echo "=========================================="
echo ""

# 使用 docker compose 或 docker-compose
COMPOSE_CMD="docker-compose"
if ! command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker compose"
fi

# 检查是否有依赖文件变更
REBUILD_NEEDED=false

# 检查 requirements.txt 是否变更
if [ -f backend/requirements.txt ]; then
    BACKEND_HASH=$(md5sum backend/requirements.txt 2>/dev/null | cut -d' ' -f1 || echo "")
    BACKEND_HASH_FILE=".backend_deps_hash"
    
    if [ -f "$BACKEND_HASH_FILE" ]; then
        OLD_HASH=$(cat "$BACKEND_HASH_FILE")
        if [ "$BACKEND_HASH" != "$OLD_HASH" ]; then
            echo "⚠️  检测到 backend/requirements.txt 变更"
            REBUILD_NEEDED=true
        fi
    fi
    echo "$BACKEND_HASH" > "$BACKEND_HASH_FILE"
fi

# 检查 package.json 是否变更
if [ -f frontend/package.json ]; then
    FRONTEND_HASH=$(md5sum frontend/package.json 2>/dev/null | cut -d' ' -f1 || echo "")
    FRONTEND_HASH_FILE=".frontend_deps_hash"
    
    if [ -f "$FRONTEND_HASH_FILE" ]; then
        OLD_HASH=$(cat "$FRONTEND_HASH_FILE")
        if [ "$FRONTEND_HASH" != "$OLD_HASH" ]; then
            echo "⚠️  检测到 frontend/package.json 变更"
            REBUILD_NEEDED=true
        fi
    fi
    echo "$FRONTEND_HASH" > "$FRONTEND_HASH_FILE"
fi

if [ "$REBUILD_NEEDED" = true ]; then
    echo "📦 检测到依赖变更，需要重新构建镜像"
    echo "   请运行: ./deploy.sh"
    echo ""
    read -p "是否继续快速重启（不重装依赖）？ [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "🔄 重启服务（利用 Docker 缓存层）..."
echo ""

# 方案1：重启后端服务（应用后端代码变更）
echo "📋 重启后端服务（应用后端代码变更）..."
$COMPOSE_CMD restart backend

echo ""
echo "🔨 重新构建前端镜像（应用前端代码变更）..."
$COMPOSE_CMD build frontend

echo ""
echo "🚀 重启前端服务..."
$COMPOSE_CMD up -d frontend

# 可选：如果需要完全重启
# $COMPOSE_CMD restart

echo ""
echo "✅ 重启完成！"
echo ""

# 等待服务就绪
echo "⏳ 等待服务就绪..."
sleep 3

# 显示服务状态
echo ""
echo "📊 服务状态："
$COMPOSE_CMD ps

echo ""
echo "=========================================="
echo "  🎉 服务已重启"
echo "=========================================="
echo ""
echo "📍 访问地址："
echo "   前端界面： http://localhost:8180"
echo "   后端 API： http://localhost:8000"
echo ""
echo "💡 提示："
echo "   - 后端代码变更会自动生效（uvicorn --reload）"
echo "   - 前端代码变更已应用（重新构建）"
echo "   - 如果新增了依赖，请运行 ./deploy.sh"
echo ""
echo "📋 查看日志："
echo "   所有日志： $COMPOSE_CMD logs -f"
echo "   后端日志： $COMPOSE_CMD logs -f backend"
echo "   前端日志： $COMPOSE_CMD logs -f frontend"
echo ""

