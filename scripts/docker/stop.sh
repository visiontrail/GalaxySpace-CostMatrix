#!/bin/bash

################################################################################
# CostMatrix 服务停止脚本
# 功能：停止并清理所有 Docker 容器和网络
################################################################################

set -e

echo "=========================================="
echo "  CostMatrix 服务停止脚本"
echo "=========================================="
echo ""

# 使用 docker compose 或 docker-compose
COMPOSE_CMD="docker-compose"
if ! command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker compose"
fi

echo "🛑 停止所有服务..."
$COMPOSE_CMD down

echo ""
echo "✅ 服务已停止"
echo ""

# 询问是否删除并重建容器
read -p "是否删除并重建容器（这将清除容器内的所有数据）？ [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  删除容器和卷..."
    $COMPOSE_CMD down -v
    echo "✅ 容器和卷已删除"
    echo ""
    echo "💡 下次启动将重新创建容器"
    echo "   运行: ./deploy.sh 或 $COMPOSE_CMD up -d --build"
else
    echo "💡 容器已保留，下次启动将使用现有容器"
    echo "   运行: ./deploy.sh 或 $COMPOSE_CMD up -d"
fi

echo ""

# 可选：清理未使用的镜像和容器
read -p "是否清理未使用的 Docker 资源（镜像、容器、网络）？ [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧹 清理 Docker 资源..."
    docker system prune -f
    echo "✅ 清理完成"
fi

echo ""
echo "=========================================="
echo "  👋 服务已完全停止"
echo "=========================================="
echo ""
echo "💡 重新启动："
echo "   快速启动： ./restart-dev.sh"
echo "   完整部署： ./deploy.sh"
echo ""

