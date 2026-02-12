#!/bin/bash

# CostMatrix 后端环境一键安装脚本
# 用于在全新机器上快速搭建 Python 虚拟环境并安装所有依赖

set -e  # 遇到错误立即退出

echo "=========================================="
echo "  CostMatrix 后端环境安装脚本"
echo "=========================================="
echo ""

# 切换到脚本所在目录的 backend 子目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/backend" || { echo "错误: 找不到 backend 目录"; exit 1; }

echo "📍 当前目录: $(pwd)"
echo ""

# 1. 检查 Python 版本
echo "🔍 检查 Python 版本..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✅ Python 版本: $PYTHON_VERSION"

# 检查 Python 版本是否 >= 3.8
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo "❌ 错误: 需要 Python 3.8 或更高版本"
    exit 1
fi
echo ""

# 2. 安装 python3-venv (仅针对 Debian/Ubuntu 系统)
if [ -f /etc/debian_version ]; then
    echo "📦 检测到 Debian/Ubuntu 系统，安装 python3-venv..."
    if ! dpkg -l | grep -q python3.*-venv; then
        apt-get update && apt-get install -y python3-venv
    else
        echo "✅ python3-venv 已安装"
    fi
    echo ""
fi

# 3. 删除旧虚拟环境（如果存在）
if [ -d "venv" ]; then
    echo "🗑️  删除旧的虚拟环境..."
    rm -rf venv
fi

# 4. 创建新的虚拟环境
echo "🏗️  创建 Python 虚拟环境..."
python3 -m venv venv
echo "✅ 虚拟环境创建完成"
echo ""

# 5. 激活虚拟环境并升级 pip
echo "⬆️  升级 pip..."
source venv/bin/activate
pip install --upgrade pip
echo "✅ pip 已升级到最新版本"
echo ""

# 6. 安装依赖
echo "📥 安装 Python 依赖包..."
if [ ! -f "requirements.txt" ]; then
    echo "❌ 错误: 找不到 requirements.txt 文件"
    exit 1
fi

pip install -r requirements.txt
echo "✅ 依赖安装完成"
echo ""

# 7. 创建安装标记文件
echo "📝 创建安装标记文件..."
touch venv/.installed
echo "✅ 安装标记文件已创建"
echo ""

# 8. 验证关键依赖
echo "🔍 验证关键依赖..."
REQUIRED_PACKAGES=("fastapi" "uvicorn" "pandas" "openpyxl" "pydantic" "sqlalchemy" "pymysql" "cryptography" "passlib" "PyJWT")
for pkg in "${REQUIRED_PACKAGES[@]}"; do
    if python -c "import $pkg" 2>/dev/null; then
        VERSION=$(python -c "import $pkg; print($pkg.__version__)" 2>/dev/null || echo "unknown")
        echo "  ✅ $pkg ($VERSION)"
    else
        echo "  ❌ $pkg - 导入失败"
        exit 1
    fi
done
echo ""

# 9. 验证后端应用导入
echo "🧪 验证后端应用..."
if python -c "from app.main import app" 2>/dev/null; then
    echo "✅ 后端应用加载成功"
else
    echo "⚠️  警告: 后端应用加载失败，请检查代码"
fi
echo ""

echo "=========================================="
echo "  安装完成！"
echo "=========================================="
echo ""
echo "📊 已安装的虚拟环境: $(pwd)/venv"
echo ""
echo "🚀 启动后端服务:"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "📖 或使用项目根目录的启动脚本:"
echo "   ./start.sh"
echo ""
