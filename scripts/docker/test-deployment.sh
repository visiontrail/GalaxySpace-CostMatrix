#!/bin/bash

################################################################################
# CostMatrix 部署测试脚本
# 功能：验证 Docker 配置是否正确
################################################################################

set -e

echo "=========================================="
echo "  CostMatrix Docker 配置验证"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查函数
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✅${NC} $1"
        return 0
    else
        echo -e "${RED}❌${NC} $1 (缺失)"
        return 1
    fi
}

check_executable() {
    if [ -x "$1" ]; then
        echo -e "${GREEN}✅${NC} $1 (可执行)"
        return 0
    else
        echo -e "${YELLOW}⚠️${NC}  $1 (不可执行，但文件存在)"
        return 1
    fi
}

# 检查必需文件
echo "📋 检查配置文件..."
echo ""

MISSING=0

# Docker 配置文件
check_file "docker-compose.yml" || MISSING=$((MISSING + 1))
check_file "backend/Dockerfile" || MISSING=$((MISSING + 1))
check_file "frontend/Dockerfile" || MISSING=$((MISSING + 1))
check_file "frontend/nginx.conf" || MISSING=$((MISSING + 1))

echo ""
echo "📋 检查优化文件..."
echo ""

check_file "backend/.dockerignore" || MISSING=$((MISSING + 1))
check_file "frontend/.dockerignore" || MISSING=$((MISSING + 1))

echo ""
echo "📋 检查脚本文件..."
echo ""

check_executable "deploy.sh" || MISSING=$((MISSING + 1))
check_executable "restart-dev.sh" || MISSING=$((MISSING + 1))
check_executable "stop.sh" || MISSING=$((MISSING + 1))

echo ""
echo "📋 检查配置模板..."
echo ""

check_file "env.example" || echo -e "${YELLOW}⚠️${NC}  env.example (可选文件)"

echo ""
echo "📋 检查文档文件..."
echo ""

check_file "DOCKER_README.md" || echo -e "${YELLOW}⚠️${NC}  DOCKER_README.md"
check_file "DOCKER_QUICK_START.md" || echo -e "${YELLOW}⚠️${NC}  DOCKER_QUICK_START.md"
check_file "DOCKER_DEPLOYMENT.md" || echo -e "${YELLOW}⚠️${NC}  DOCKER_DEPLOYMENT.md"
check_file "DOCKER_FILES_SUMMARY.md" || echo -e "${YELLOW}⚠️${NC}  DOCKER_FILES_SUMMARY.md"

echo ""
echo "=========================================="

if [ $MISSING -eq 0 ]; then
    echo -e "${GREEN}✅ 所有必需文件检查通过！${NC}"
    echo ""
    echo "📝 配置文件语法验证..."
    
    # 验证 docker-compose.yml 语法
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
        COMPOSE_CMD="docker-compose"
        if ! command -v docker-compose &> /dev/null; then
            COMPOSE_CMD="docker compose"
        fi
        
        echo -n "   检查 docker-compose.yml ... "
        if $COMPOSE_CMD config > /dev/null 2>&1; then
            echo -e "${GREEN}✅ 语法正确${NC}"
        else
            echo -e "${RED}❌ 语法错误${NC}"
            $COMPOSE_CMD config
        fi
    else
        echo -e "${YELLOW}⚠️  未安装 Docker Compose，跳过语法检查${NC}"
    fi
    
    echo ""
    echo "=========================================="
    echo -e "${GREEN}🎉 配置验证完成！${NC}"
    echo "=========================================="
    echo ""
    echo "📍 下一步操作："
    echo "   1. 确保 Docker 和 Docker Compose 已安装"
    echo "   2. 运行: ./deploy.sh"
    echo "   3. 访问: http://localhost:8180"
    echo ""
    echo "📚 查看文档："
    echo "   - 快速启动: cat DOCKER_QUICK_START.md"
    echo "   - 完整文档: cat DOCKER_DEPLOYMENT.md"
    echo ""
else
    echo -e "${RED}❌ 发现 $MISSING 个问题${NC}"
    echo ""
    echo "请检查上述缺失或错误的文件。"
    exit 1
fi

