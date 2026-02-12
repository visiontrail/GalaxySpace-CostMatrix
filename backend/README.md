# CostMatrix Backend

FastAPI 后端服务，提供数据分析 REST API。

## 技术栈

- **FastAPI**: Web 框架
- **Pandas**: 数据分析
- **Openpyxl**: Excel 操作
- **Pydantic**: 数据验证
- **Uvicorn**: ASGI 服务器

## 快速开始

### 安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate  # Mac/Linux
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 运行服务

```bash
# 开发模式（自动重载）
uvicorn app.main:app --reload --port 8000

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 访问 API 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 端点

### 核心端点

- `GET /api/health` - 健康检查
- `POST /api/upload` - 上传 Excel 文件
- `POST /api/analyze` - 分析数据
- `POST /api/export` - 导出分析结果

## 项目结构

```
backend/
├── app/
│   ├── main.py              # FastAPI 应用
│   ├── config.py            # 配置
│   ├── api/routes.py        # API 路由
│   ├── models/schemas.py    # 数据模型
│   └── services/excel_processor.py  # 核心业务逻辑
└── requirements.txt
```

## 核心模块

### ExcelProcessor

Excel 数据处理核心类：

```python
from app.services.excel_processor import ExcelProcessor

processor = ExcelProcessor('file.xlsx')
processor.load_all_sheets()

# 项目成本归集
projects = processor.aggregate_project_costs()

# 交叉验证
anomalies = processor.cross_check_attendance_travel()

# 预订行为分析
behavior = processor.analyze_booking_behavior()
```

## 环境变量

创建 `.env` 文件（已被 `.gitignore` 忽略）：

```env
APP_NAME=CostMatrix
DEBUG=True
ALLOWED_ORIGINS=http://localhost:5173
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE=50

# 数据库（推荐 MySQL）
DB_TYPE=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=costmatrix
DB_USER=root
DB_PASSWORD=your_password
DB_CHARSET=utf8mb4

# 或直接使用完整连接串（优先级更高）
# DATABASE_URL=mysql+pymysql://root:your_password@127.0.0.1:3306/costmatrix?charset=utf8mb4
```

## 测试

```bash
# 运行测试
pytest

# 覆盖率报告
pytest --cov=app
```

## 部署

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Systemd Service

```ini
[Unit]
Description=CostMatrix Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/corppilot/backend
ExecStart=/var/www/costmatrix/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## License

MIT

