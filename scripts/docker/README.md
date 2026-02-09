# Docker 部署脚本

本目录包含 CostMatrix 的 Docker 部署相关脚本。

> 说明：本目录脚本用于开发/联调环境。  
> 生产离线发布（`docker save` + `load + up`）请使用 `scripts/release/make_release.sh` 生成发布包，并按 `release/DEPLOY.md` 执行。

## 脚本说明

### `deploy.sh` - 一键部署脚本（开发环境）
构建 Docker 镜像并启动所有服务。

**功能：**
- 检查 Docker 和 Docker Compose 环境
- 清理旧容器
- 构建镜像（使用 `--no-cache` 清除缓存）
- 启动所有服务
- 显示服务状态和访问地址

**使用场景：**
- 首次部署
- 需要完全重新构建镜像（如修改依赖、Dockerfile 等）
- 本地开发调试

**不适用：**
- 生产离线发布（该脚本会执行 `docker compose build --no-cache`）

**示例：**
```bash
./scripts/docker/deploy.sh
```

---

### `stop.sh` - 服务停止脚本
停止并清理所有 Docker 容器和网络。

**功能：**
- 停止所有服务
- **交互式询问**是否删除并重建容器（清除容器内所有数据）
- **交互式询问**是否清理未使用的 Docker 资源（镜像、容器、网络）

**使用场景：**
- 停止服务
- 清理测试数据
- 重置容器环境

**示例：**
```bash
./scripts/docker/stop.sh
```

**交互选项：**
1. **删除并重建容器**：选择 `y` 将删除容器和卷，下次启动将重新创建（清除所有容器内数据）
2. **清理 Docker 资源**：选择 `y` 将清理未使用的镜像、容器和网络

---

### `restart-dev.sh` - 快速重启脚本
快速应用代码变更，无需重新安装依赖。

**功能：**
- 检测依赖文件变更（`requirements.txt`、`package.json`）
- 如果检测到依赖变更，提示用户运行 `deploy.sh` 重新构建
- 重启后端服务（应用后端代码变更）
- 重新构建前端镜像（应用前端代码变更）
- 重启前端服务

**使用场景：**
- 修改了业务代码，但未新增 npm/pip 依赖
- 快速开发和测试

**示例：**
```bash
./scripts/docker/restart-dev.sh
```

**注意：**
- 后端代码变更会自动生效（uvicorn --reload）
- 前端代码变更需要重新构建
- 如果新增了依赖，请运行 `./deploy.sh`

---

### `test-deployment.sh` - 部署测试脚本
验证 Docker 配置是否正确。

**功能：**
- 检查必需文件是否存在
- 检查脚本文件是否可执行
- 验证 docker-compose.yml 语法
- 显示缺失或错误的文件

**使用场景：**
- 部署前检查配置
- 排查部署问题
- 验证环境完整性

**示例：**
```bash
./scripts/docker/test-deployment.sh
```

---

## 使用流程

### 首次部署（开发）
```bash
# 1. 检查配置
./scripts/docker/test-deployment.sh

# 2. 部署服务
./scripts/docker/deploy.sh
```

### 日常开发
```bash
# 快速重启（应用代码变更）
./scripts/docker/restart-dev.sh
```

### 重置环境
```bash
# 停止服务并删除容器
./scripts/docker/stop.sh
# 选择 y 删除并重建容器

# 重新部署
./scripts/docker/deploy.sh
```

---

## 常用 Docker Compose 命令

所有脚本都自动检测并使用 `docker-compose` 或 `docker compose` 命令。

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 停止服务
docker-compose down

# 停止并删除卷
docker-compose down -v

# 重启特定服务
docker-compose restart backend

# 重新构建并启动
docker-compose up -d --build
```

---

## 目录结构

```
scripts/docker/
├── deploy.sh              # 一键部署脚本
├── stop.sh                # 服务停止脚本（支持交互式删除容器）
├── restart-dev.sh         # 快速重启脚本
├── test-deployment.sh     # 部署测试脚本
└── README.md              # 本文档
```

---

## 注意事项

1. **脚本路径**：所有脚本应在项目根目录下运行，使用 `./scripts/docker/xxx.sh` 的形式
2. **交互式询问**：`stop.sh` 使用交互式询问，而非命令行参数，更加友好
3. **依赖变更检测**：`restart-dev.sh` 会自动检测依赖变更，避免遗漏重新构建
4. **容器数据**：删除容器会清除容器内所有数据，请谨慎操作
5. **生产部署**：请勿用本目录脚本，改用 `./scripts/release/make_release.sh` + 发布包内 `./scripts/up.sh`

---

## 故障排查

### 服务启动失败
```bash
# 查看日志
docker-compose logs -f

# 检查服务状态
docker-compose ps

# 重新部署
./scripts/docker/deploy.sh
```

### 需要完全重置
```bash
# 停止并删除所有容器和卷
docker-compose down -v

# 清理所有未使用的资源
docker system prune -a

# 重新部署
./scripts/docker/deploy.sh
```
