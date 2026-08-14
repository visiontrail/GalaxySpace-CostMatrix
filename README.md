# CostMatrix 企业差旅成本分析平台

CostMatrix 是一个面向企业差旅数据的分析平台。系统可读取 Excel 数据，对机票、酒店、火车票和考勤记录进行汇总分析，并通过可视化页面展示成本、项目、部门及异常情况。

## 主要功能

- 上传并解析 Excel 差旅数据
- 汇总项目和部门差旅成本
- 检测考勤与差旅记录中的异常情况
- 展示成本指标、趋势及排行图表
- 导出包含分析结果的 Excel 文件
- 支持通过 AI 助手查询业务数据

## 技术栈

- 后端：Python、FastAPI、Pandas、OpenPyXL
- 前端：React、TypeScript、Vite
- 部署：Docker、Docker Compose

## 快速启动

推荐使用 Docker Compose 启动完整服务：

```bash
cp env.example .env
docker-compose up --build
```

启动后可访问：

- 前端页面：<http://localhost:8180>
- 后端接口：<http://localhost:8000>
- API 文档：<http://localhost:8000/docs>

停止服务：

```bash
docker-compose down
```

## 目录说明

```text
├── backend/        # FastAPI 后端服务
├── frontend/       # React 前端项目
├── scripts/        # 数据处理及运维脚本
├── main.py         # 根目录 API 入口
└── docker-compose.yml
```

## 注意事项

- 请使用 `.xlsx` 格式的数据文件。
- 配置项请参考 `env.example`，敏感信息应保存在本地 `.env` 中。
- 请勿提交真实业务数据、账号密码、上传文件或运行日志。
