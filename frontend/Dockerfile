# Frontend Dockerfile - Multi-stage build
# Stage 1: Build React App
FROM node:18-alpine AS builder

WORKDIR /app

# 复制 package 文件
COPY package*.json ./

# 使用淘宝镜像加速安装依赖
RUN npm config set registry https://registry.npmmirror.com && \
    npm install

# 复制源代码
COPY . .

ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

# 构建生产版本
RUN npm run build

# Stage 2: Nginx Server
FROM nginx:alpine

# 复制自定义 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 从构建阶段复制构建好的文件到 nginx 目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 暴露端口
EXPOSE 80

# Nginx 默认会在前台运行
CMD ["nginx", "-g", "daemon off;"]
