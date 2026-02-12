#!/bin/bash

################################################################################
# CostMatrix 一键部署脚本
# 功能：构建 Docker 镜像并启动所有服务
################################################################################

set -e  # 遇到错误立即退出

echo "=========================================="
echo "  CostMatrix Docker 一键部署脚本"
echo "=========================================="
echo ""

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ 错误：未检测到 Docker，请先安装 Docker"
    echo "   安装指南：https://docs.docker.com/engine/install/"
    exit 1
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ 错误：未检测到 Docker Compose，请先安装"
    echo "   安装指南：https://docs.docker.com/compose/install/"
    exit 1
fi

# 使用 docker compose 或 docker-compose
COMPOSE_CMD="docker-compose"
if ! command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker compose"
fi

echo "✅ Docker 环境检查通过"
echo ""

# 停止并清理旧容器（如果存在）
echo "🧹 清理旧容器..."
$COMPOSE_CMD down 2>/dev/null || true
echo ""

# 构建镜像
echo "🔨 开始构建 Docker 镜像..."
echo "   这可能需要几分钟时间，请耐心等待..."
echo ""
$COMPOSE_CMD build --no-cache

echo ""
echo "✅ 镜像构建完成"
echo ""

# 启动服务
echo "🚀 启动服务..."
$COMPOSE_CMD up -d

echo ""
echo "✅ 服务启动成功！"
echo ""

# 等待服务就绪
echo "⏳ 等待服务初始化..."
sleep 5

# 检查服务状态
echo ""
echo "📊 服务状态："
$COMPOSE_CMD ps

echo ""
echo "=========================================="
echo "  🎉 部署完成！"
echo "=========================================="
echo ""
echo "📍 访问地址："
echo "   前端界面： http://localhost:8180"
echo "   后端 API： http://localhost:8000"
echo "   API 文档： http://localhost:8180/docs"
echo ""
echo "💡 常用命令："
echo "   查看日志： $COMPOSE_CMD logs -f"
echo "   停止服务： ./stop.sh 或 $COMPOSE_CMD down"
echo "   重启服务： ./restart-dev.sh"
echo ""

