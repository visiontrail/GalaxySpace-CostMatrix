## 1. 前置条件
- 已安装 Docker 20+；已安装 Docker Compose v2（推荐）或 v1
- 端口：`8180`（前端）与 `8000`（后端 API）可用
- 发布机与目标机架构保持一致（如都为 amd64 或都为 arm64）

## 2. 在发布机制作离线包
在仓库根目录执行：

```bash
VERSION=20260209 ./scripts/release/make_release.sh
```

产物目录默认位于 `release/packages/`，会生成：
- `release/packages/costmatrix-<version>/`
- `release/packages/costmatrix-<version>.tar.gz`

> 该脚本会完成生产镜像构建、后端 smoke test、`docker save` 导出、发布目录组装与压缩。

## 3. 发布包内容
```text
costmatrix-<version>/
├── docker-compose.yml
├── .env.example
├── DEPLOY.md
├── config/
├── data/
├── images/
│   ├── costmatrix-backend-<version>.tar
│   └── costmatrix-frontend-<version>.tar
└── scripts/
    ├── up.sh
    ├── down.sh
    ├── status.sh
    ├── logs.sh
    └── load-images.sh
```

## 4. 目标机首次部署 / 升级
1) 上传并解压完整目录，例如 `/opt/costmatrix-20260209`。
2) 准备 `.env`：
   ```bash
   cd /opt/costmatrix-20260209
   cp .env.example .env
   # 按需修改端口、SECRET_KEY、ALLOWED_ORIGINS 等
   ```
3) 启动（离线自动加载镜像）：
   ```bash
   ./scripts/up.sh
   ```
4) 查看状态：
   ```bash
   ./scripts/status.sh
   # 访问 http://<server-ip>:8180
   ```

> 升级时直接在新版本目录重复上述步骤，数据目录会复用。

## 5. 回滚
- 保留旧版本发布目录（含 `images/*.tar`），回滚时执行：
  ```bash
  cd /opt/costmatrix-<old_version>
  ./scripts/up.sh
  ```

## 6. 常用操作
- 停止服务：`./scripts/down.sh`
- 查看日志：`./scripts/logs.sh` 或 `./scripts/logs.sh backend`
- 查看状态：`./scripts/status.sh`

## 7. 参数说明（`.env`）
- `IMAGE_TAG`：镜像版本（与发布包一致），不建议修改
- `BACKEND_IMAGE` / `FRONTEND_IMAGE`：镜像名称
- `BACKEND_PORT` / `FRONTEND_PORT`：宿主暴露端口
- `ALLOWED_ORIGINS`：前端访问源，逗号分隔
- `SECRET_KEY`：JWT 加密秘钥，必须改为公司随机值
- `INITIAL_ADMIN_PASSWORD_FILE`：初始管理员密码文件路径，默认 `config/initial_admin_password.txt`
- `UPLOAD_DIR`：上传目录（默认 `/app/uploads`，映射到宿主 `data/uploads`）

## 8. 数据持久化
- `data/uploads`：上传文件与缓存
- `data/data`：内置 SQLite 数据库
- `data/logs`：后端日志

## 9. 约束与注意事项
- 生产部署不要使用 `scripts/docker/deploy.sh`（该脚本会 `build --no-cache`，属于开发部署流程）
- 生产 compose 必须使用 `image:`，不能依赖目标机 `build`
- 镜像导出方式使用 `docker save`，但它不会包含 volumes、`.env`、运行中的容器状态

## 10. 故障排查
- 镜像无法加载：确认 `images/*.tar` 存在且账号有 Docker 权限
- 端口占用：调整 `.env` 中端口后重新执行 `./scripts/up.sh`
- 后端健康检查失败：查看 `data/logs` 或 `./scripts/logs.sh backend`
