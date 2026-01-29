## 1. 前置条件
- 已安装 Docker 20+；已安装 Docker Compose v2（推荐）或 v1
- 端口：`8180`（前端）与 `8000`（后端 API）可用；

## 2. 发布包内容
```
costmatrix-<version>/
├── docker-compose.yml           # 生产 compose
├── .env.example                 # 变量示例（会自动生成 .env）
├── DEPLOY.md                    # 本指南
├── config/                      # 配置文件（默认初始密码等）
├── data/                        # 运行时数据（首次运行会创建）
├── images/                      # 预打包 Docker 镜像 *.tar
└── scripts/                     # 操作脚本：up/down/logs/status/load-images
```

## 3. 首次部署 / 升级
1) 上传完整目录到目标服务器，例如 `/opt/costmatrix-20260129`.
2) 进入目录并准备 `.env`：
   ```bash
   cd /opt/costmatrix-20260129
   cp .env.example .env          # 如果脚本未自动生成
   # 可按需修改端口、SECRET_KEY、ALLOWED_ORIGINS 等
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

> 升级时直接使用新版本目录执行同样步骤，新 compose 会复用同名卷（数据保持）。

## 4. 回滚
- 保留旧版本发布包（含镜像 tar）。需要回滚时：
  ```bash
  cd /opt/costmatrix-<old_version>
  ./scripts/up.sh
  ```
- 依赖同名 `COMPOSE_PROJECT_NAME=costmatrix`，因此数据卷共享，回滚仅切换镜像版本。

## 5. 常用操作
- 停止服务：`./scripts/down.sh`
- 查看日志：`./scripts/logs.sh` 或 `./scripts/logs.sh backend`
- 查看状态：`./scripts/status.sh`

## 6. 参数说明（`.env`）
- `IMAGE_TAG`：镜像版本（与发布包一致），不建议修改。
- `BACKEND_PORT` / `FRONTEND_PORT`：宿主暴露端口。
- `ALLOWED_ORIGINS`：前端访问源，逗号分隔。
- `SECRET_KEY`：JWT 加密秘钥，必须改为公司随机值。
- `INITIAL_ADMIN_PASSWORD_FILE`：初始管理员密码文件路径，默认 `config/initial_admin_password.txt`。
- `UPLOAD_DIR`：上传目录（默认 `/app/uploads`，映射到宿主 `data/uploads`）。

## 7. 目录/数据持久化
- `data/uploads`：上传的 Excel 与缓存。
- `data/data`：内置 SQLite 数据库。
- `data/logs`：后端日志。
- 修改配置（如初始密码）可编辑 `config/initial_admin_password.txt` 后重启。

## 8. 故障排查
- 镜像无法加载：确认 `images/*.tar` 是否存在且账号有 Docker 权限。
- 端口占用：调整 `.env` 中端口后重新执行 `./scripts/up.sh`。
- 后端健康检查失败：查看 `data/logs` 或 `./scripts/logs.sh backend`。
