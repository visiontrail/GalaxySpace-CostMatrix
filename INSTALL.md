# CostMatrix 环境安装指南

本文档介绍如何在全新机器上快速搭建 CostMatrix 开发环境。

## 系统要求

- **操作系统**: Linux (推荐 Ubuntu 20.04+)
- **Python**: 3.8 或更高版本
- **Node.js**: 16 或更高版本

## 快速开始

### 方法一：一键安装后端环境（推荐）

使用项目提供的一键安装脚本：

```bash
./install-backend.sh
```

这个脚本会自动完成以下操作：
1. 检查 Python 版本
2. 安装 `python3-venv`（如果需要）
3. 创建 Python 虚拟环境
4. 升级 pip
5. 安装所有 Python 依赖
6. 验证关键依赖和后端应用

### 方法二：手动安装

如果需要手动安装，请按以下步骤操作：

```bash
# 1. 进入 backend 目录
cd backend

# 2. 创建虚拟环境
python3 -m venv venv

# 3. 激活虚拟环境
source venv/bin/activate

# 4. 升级 pip
pip install --upgrade pip

# 5. 安装依赖
pip install -r requirements.txt

# 6. 创建安装标记（可选）
touch venv/.installed
```

## 启动服务

安装完成后，使用项目根目录的启动脚本：

```bash
./start.sh
```

或者分别启动前后端：

```bash
# 启动后端（在 backend 目录下）
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 启动前端（在 frontend 目录下，新终端）
cd frontend
npm install  # 首次运行需要
npm run dev
```

## 服务访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:5173 | React 前端界面 |
| 后端 API | http://localhost:8000 | FastAPI 后端服务 |
| API 文档 | http://localhost:8000/docs | Swagger UI |
| API 文档 | http://localhost:8000/redoc | ReDoc |

## 已安装的 Python 依赖

以下依赖会在安装过程中自动安装：

| 类别 | 包名 | 版本要求 |
|------|------|----------|
| Web框架 | fastapi | >=0.109.0 |
| ASGI服务器 | uvicorn[standard] | >=0.27.0 |
| 文件上传 | python-multipart | >=0.0.6 |
| 数据处理 | pandas | >=2.2.0 |
| Excel处理 | openpyxl | >=3.1.2 |
| Excel读取 | xlrd | >=2.0.1 |
| 图像处理 | Pillow | >=10.0.0 |
| 数据验证 | pydantic | >=2.10.0 |
| 配置管理 | pydantic-settings | >=2.6.0 |
| 环境变量 | python-dotenv | >=1.0.0 |
| 数值计算 | numpy | >=1.26.0 |
| 数据库 ORM | sqlalchemy | >=2.0.0 |
| MySQL驱动 | pymysql | >=1.1.0 |
| 加密库 | cryptography | >=42.0.0 |
| 密码哈希 | passlib[bcrypt] | >=1.7.4 |
| JWT认证 | PyJWT | >=2.8.0 |

## 故障排除

### Python 版本过低

如果系统 Python 版本低于 3.8，可以使用 pyenv 或 conda 安装新版本：

```bash
# 使用 pyenv（推荐）
curl https://pyenv.run | bash
pyenv install 3.12.0
pyenv global 3.12.0

# 或使用 conda
conda create -n costmatrix python=3.12
conda activate costmatrix
```

### python3-venv 未安装

在 Debian/Ubuntu 系统上：

```bash
apt-get update
apt-get install -y python3-venv
```

在 CentOS/RHEL 系统上：

```bash
yum install -y python3-venv
```

### 依赖安装失败

如果遇到网络问题，可以使用国内镜像源：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 端口被占用

如果 8000 或 5173 端口被占用，可以先释放端口或修改配置：

```bash
# 查看端口占用
ss -lntp | grep :8000
ss -lntp | grep :5173

# 或在启动时使用其他端口
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
npm run dev -- --port 5174
```

## 生产环境部署

生产环境部署建议使用 Docker Compose，请参考项目根目录的 `docker-compose.yml`。

## 许可证

请参考项目根目录的 LICENSE 文件。
