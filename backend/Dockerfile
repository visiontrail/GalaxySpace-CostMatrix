# Backend Dockerfile for FastAPI
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
# gosu 用于 entrypoint 从 root 降权到普通用户：Claude Agent SDK 在
# root/sudo 下拒绝使用 --dangerously-skip-permissions，应用进程不能以 root 运行。
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 使用清华源安装 Python 依赖
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

RUN groupadd -r appuser && useradd -r -g appuser -m -d /home/appuser appuser && \
    mkdir -p /app/uploads /app/data /app/logs && \
    chown -R appuser:appuser /app /home/appuser

# 开发模式：代码通过 volume 挂载，不在此处 COPY
# 生产模式：取消下面注释
# COPY . .

# 暴露端口
EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# 启动命令（开发模式使用 --reload）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
