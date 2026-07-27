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
    ├── load-images.sh
    └── upgrade-in-place.sh
```

## 4. 目标机首次部署
1) 上传并解压完整目录，并将首次部署目录固定下来，例如 `/opt/costmatrix`。
2) 准备 `.env`：
   ```bash
   cd /opt/costmatrix
   cp .env.example .env
   # 按需修改 DB_HOST/DB_USER/DB_PASSWORD、端口、SECRET_KEY、ALLOWED_ORIGINS 等
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

> `data/`、`config/` 和 `.env` 都通过相对路径使用。不要把新版本直接启动在另一个目录，否则会切换到另一套上传文件、SQLite 数据和配置。

## 5. 已运行生产环境的原位升级
1) 先备份外部 MySQL；如使用 SQLite，还要备份固定部署目录中的 `data/`。同时备份 `.env` 和 `config/`。
2) 将新发布包解压到临时目录，例如 `/opt/releases/costmatrix-20260727`，不要直接在临时目录启动。
3) 从新发布包执行原位升级：
   ```bash
   cd /opt/releases/costmatrix-20260727
   ./scripts/upgrade-in-place.sh /opt/costmatrix
   ```
4) 脚本只替换 Compose 与运维脚本、更新三个镜像字段，并保留目标目录现有的 `.env` 其他配置、`config/` 和 `data/`。新容器全部健康后才判定成功；失败会恢复旧 Compose 和旧镜像字段并尝试拉起旧容器。
5) 升级后检查：
   ```bash
   cd /opt/costmatrix
   ./scripts/status.sh
   curl -fsS http://127.0.0.1:8000/api/health
   ```

生产升级不得使用 `docker compose down -v`，也不得删除固定部署目录中的 `data/`。

## 6. 回滚
- 原位升级会把旧 `.env`、Compose 和脚本备份到固定部署目录的 `.upgrade-backups/<timestamp>/`。
- 如需人工回滚，恢复旧 `.env` 与 `docker-compose.yml` 后执行：
  ```bash
  cd /opt/costmatrix
  docker compose -p costmatrix -f docker-compose.yml up -d
  ```
- 回滚前必须确认旧镜像仍在本机；不要在升级验证完成前清理旧镜像。

## 7. 常用操作
- 停止服务：`./scripts/down.sh`
- 查看日志：`./scripts/logs.sh` 或 `./scripts/logs.sh backend`
- 查看状态：`./scripts/status.sh`

## 8. 参数说明（`.env`）
- `IMAGE_TAG`：镜像版本（与发布包一致），不建议修改
- `BACKEND_IMAGE` / `FRONTEND_IMAGE`：镜像名称
- `BACKEND_PORT` / `FRONTEND_PORT`：宿主暴露端口
- `ALLOWED_ORIGINS`：前端访问源，支持 JSON 数组或逗号分隔
  - 推荐：`["http://<frontend-host>:8180"]`
  - 兼容：`http://<frontend-host>:8180,http://localhost:8180`
- `SECRET_KEY`：JWT 加密秘钥，必须改为公司随机值
- `INITIAL_ADMIN_PASSWORD_FILE`：初始管理员密码文件路径，默认 `config/initial_admin_password.txt`
- `UPLOAD_DIR`：上传目录（默认 `/app/uploads`，映射到宿主 `data/uploads`）
- `DATABASE_URL`：完整连接串（优先级最高），示例：`mysql+pymysql://user:password@db.example.com:3306/costmatrix?charset=utf8mb4`
- `DB_TYPE`：默认 `mysql`；如需 SQLite 可改为 `sqlite`
- `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_CHARSET`：当 `DATABASE_URL` 为空时生效

## 9. 数据持久化
- `data/uploads`：上传文件与缓存
- `data/data`：仅在使用 SQLite 时保存数据库文件（默认 MySQL 模式下可忽略）
- `data/logs`：后端日志

## 10. DockerHub 镜像发布
联网环境可按 RavenAIService 的同类流程发布镜像：

```bash
./scripts/docker-publish.sh <dockerhub_namespace> <tag>
```

现有生产 Compose 的镜像契约保持不变。如使用仓库镜像，将生产 `.env` 中的 `BACKEND_IMAGE`、`FRONTEND_IMAGE` 指向对应 namespace，并使用不可变版本号作为 `IMAGE_TAG`；生产升级不要直接使用 `latest`。

## 11. 约束与注意事项
- 生产部署不要使用 `scripts/docker/deploy.sh`（该脚本会 `build --no-cache`，属于开发部署流程）
- 生产 compose 必须使用 `image:`，不能依赖目标机 `build`
- 镜像导出方式使用 `docker save`，但它不会包含 volumes、`.env`、运行中的容器状态
- 当前应用启动只执行 SQLAlchemy `create_all`，不会修改已存在列；未来如果模型字段变化，必须先提供可回滚的显式数据库迁移再升级

## 12. 故障排查
- 镜像无法加载：确认 `images/*.tar` 存在且账号有 Docker 权限
- 端口占用：调整 `.env` 中端口后重新执行 `./scripts/up.sh`
- 后端健康检查失败：查看 `data/logs` 或 `./scripts/logs.sh backend`
- MySQL 连接失败：确认 `.env` 中 `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME` 可从容器网络访问
