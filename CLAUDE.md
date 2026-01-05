# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CorpPilot is an enterprise travel expense analysis platform built with:
- **Backend**: FastAPI + Pandas + OpenPyXL (Python)
- **Frontend**: React 18 + Vite + Ant Design Pro + ECharts (TypeScript)
- **Deployment**: Docker Compose with separate frontend/backend containers

The system analyzes corporate travel expenses from Excel files (.xlsx), performs cross-validation against attendance records, detects anomalies, and generates visualization-ready JSON data and enhanced Excel reports.

## Development Commands

### Backend

```bash
# Install dependencies (from project root)
pip install -r requirements.txt

# Start development server (hot reload enabled)
python main.py
# Server runs at http://localhost:8000
# API docs at http://localhost:8000/docs

# Run with specific logging
python main.py  # Logs go to logs/ directory
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
# Server runs at http://localhost:5173

# Build for production
npm run build

# Lint TypeScript/TSX files
npm run lint

# Preview production build
npm run preview
```

### Docker Deployment

```bash
# Start all services (backend on :8000, frontend on :8180)
docker-compose up -d

# View logs
docker-compose logs -f

# Rebuild after code changes
docker-compose up -d --build

# Stop all services
docker-compose down
```

## Architecture Overview

### Core Data Flow

1. **Upload**: User uploads .xlsx file via frontend → `POST /api/analyze`
2. **Load**: `DataLoader` reads 4 required sheets: 状态明细 (attendance), 机票 (flights), 酒店 (hotels), 火车票 (trains)
3. **Analyze**: `TravelAnalyzer` performs 5 parallel analyses (see below)
4. **Visualize**: Frontend Dashboard renders ECharts + tables
5. **Export**: `ExcelExporter` writes results back to original file using `openpyxl` (preserves formatting)

### Backend Services (Root Level)

The backend has a **dual structure**: older root-level modules (actively used) and newer `backend/app/` modules (legacy/backup):

**Active modules (root level)**:
- `main.py`: FastAPI entry point, defines `/api/analyze`, `/api/export`, `/api/preview` endpoints
- `data_loader.py`: Excel sheet loading and cleaning (attendance + travel data)
- `analysis_service.py`: Core business logic via `TravelAnalyzer` class
- `export_service.py`: Excel export with `openpyxl` to preserve formatting
- `logger_config.py`: Structured logging with request IDs, performance tracking

**Legacy modules (`backend/app/`)**:
- Similar structure but not currently in use
- Kept for reference or future refactoring

### Analysis Algorithms (analysis_service.py)

`TravelAnalyzer` performs these core analyses:

1. **Project Cost Aggregation** (`aggregate_project_cost`)
   - Extracts project codes from "项目" field (format: "05010013 市场-整星...")
   - Sums 授信金额 (authorized amounts) by project and travel type
   - Returns Top 10 projects by total cost

2. **Cross-Validation Anomalies** (`cross_check_anomalies`)
   - **Type 1 (Conflict)**: Attendance shows "上班" (working) but same-day travel expense exists
   - **Type 2 (NoExpense)**: Attendance shows "出差" (business trip) but no travel expense within ±3 days
   - Critical for detecting expense fraud or data entry errors

3. **Booking Behavior Analysis** (`analyze_booking_behavior`)
   - Calculates ratio of urgent bookings (≤2 days advance)
   - Computes average advance booking days
   - Used to identify cost-saving opportunities

4. **Department Metrics** (`calculate_department_metrics`)
   - Aggregates cost and working hours by 一级部门 (department)
   - Calculates saturation = total_hours / (employee_count × 176 standard_hours)

5. **KPI Statistics**
   - Total cost, order count, anomaly count, over-standard count

### Excel Format Preservation

**Critical**: Always use `openpyxl` for Excel exports, never `pandas.to_excel()`:

```python
# ✅ Correct - preserves original formatting
from openpyxl import load_workbook
wb = load_workbook(file_path)  # Keeps all styles, formulas, charts
ws = wb.create_sheet("分析结果")
# ... write data ...
wb.save(output_path)

# ❌ Wrong - destroys original file
df.to_excel(file_path, sheet_name="分析结果")  # Overwrites everything
```

### Frontend Architecture

```
src/
├── pages/
│   ├── Dashboard.tsx    # Main visualization page (ECharts + Ant Design tables)
│   └── Upload.tsx       # File upload with Dragger component
├── services/
│   └── api.ts           # Axios wrapper for backend calls
├── layouts/
│   └── MainLayout.tsx   # Header + Content + Footer
└── utils/
    └── mockData.ts      # Development mock data
```

**State Management**: Uses `localStorage` to persist Dashboard data between page refreshes.

**Routing**: React Router v6 with paths: `/` (Dashboard), `/upload`

## Logging System

All logs are written to `logs/` directory with automatic rotation (10MB max, 5 backups):

- `main.log`: API requests, performance metrics
- `data_loader.log`: Excel parsing, data cleaning
- `analysis_service.log`: Analysis algorithm execution
- `export_service.log`: Excel export operations

**Request Tracking**: Each API request gets a unique 8-character ID (`[a1b2c3d4]`) for tracing all related log entries.

**Performance Logging**: Key operations log execution time:
```
[PERFORMANCE] Operation: [a1b2c3d4] 数据加载 | Duration: 850.25ms
```

View logs in real-time:
```bash
tail -f logs/main.log
grep "ERROR" logs/*.log  # Find all errors
grep "a1b2c3d4" logs/*.log  # Trace specific request
```

## Data Model Requirements

### Required Excel Sheets

The uploaded .xlsx file must contain these sheets with specific columns:

1. **状态明细** (Attendance):
   - 日期, 姓名, 一级部门, 当日状态判断, 工时

2. **机票** (Flights):
   - 授信金额, 项目, 预订人姓名, 差旅人员姓名, 出发日期, 提前预定天数, 是否超标, 一级部门

3. **酒店** (Hotels):
   - Same as flights but with 入住日期 instead of 出发日期

4. **火车票** (Trains):
   - Same structure as flights

### Data Cleaning (data_loader.py)

`DataLoader` automatically:
- Converts 授信金额 from string (¥1,234.56) to float
- Parses dates with `pd.to_datetime`
- Extracts project codes using regex: `(\d+)\s+(.*)`
- Fills missing 一级部门 with "未知"
- Warns about invalid dates or zero working hours

## API Endpoints

| Endpoint | Method | Purpose | Input | Output |
|----------|--------|---------|-------|--------|
| `/api/analyze` | POST | Analyze Excel data | file: .xlsx | JSON with dashboard data |
| `/api/export` | POST | Export results to Excel | file: .xlsx | Enhanced .xlsx file |
| `/api/preview` | POST | Preview data structure | file: .xlsx | Sheet metadata + sample rows |
| `/health` | GET | Health check | - | `{status: "healthy"}` |

## Common Development Patterns

### Adding a New Analysis Feature

1. Add method to `TravelAnalyzer` class in `analysis_service.py`
2. Call it in `generate_dashboard_data()` method
3. Update frontend Dashboard.tsx to render the new data
4. Add corresponding ECharts configuration if visualizing

### Adding a New API Endpoint

1. Define route in `main.py` with FastAPI decorator
2. Add request/response models if needed (can use Pydantic)
3. Use `RequestLogger` for tracking: `request_logger.log_request_start()`
4. Always wrap in try/except with proper logging
5. Update API client in `frontend/src/services/api.ts`

### Working with Logs

When debugging issues:
1. Find the request ID from frontend response or recent logs
2. `grep "[request_id]" logs/*.log` to see full request lifecycle
3. Check for ERROR/WARNING entries
4. Review performance metrics to identify bottlenecks

## Testing

### Backend Manual Testing

```bash
# Health check
curl http://localhost:8000/health

# Analyze data
curl -X POST http://localhost:8000/api/analyze \
  -F "file=@test_data.xlsx" \
  -o result.json

# Export Excel
curl -X POST http://localhost:8000/api/export \
  -F "file=@test_data.xlsx" \
  -o output.xlsx
```

### Frontend Testing

Use the `/upload` page to upload sample Excel files and verify:
- File upload progress
- Dashboard rendering (charts, tables, KPIs)
- Export functionality
- Error handling for invalid files

## Important Constraints

1. **File Size**: Maximum upload is 50MB (configurable in FastAPI)
2. **Excel Format**: Only .xlsx supported (not .xls or .csv)
3. **CORS**: Currently allows all origins (`allow_origins=["*"]`) - restrict in production
4. **Temp Files**: All uploads are saved to temp directory and auto-deleted after processing
5. **Anomaly Limit**: Only first 100 anomalies returned to frontend (performance)

## Production Deployment Notes

When deploying to production:
- Set `DEBUG=False` in environment
- Configure specific CORS origins in `main.py`
- Use Gunicorn with Uvicorn workers: `gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker`
- Enable HTTPS
- Set up log aggregation (ELK, CloudWatch, etc.)
- Monitor `logs/` directory size
- Consider adding authentication middleware

## Code Style

- Python: Follow PEP 8, use type hints where helpful
- TypeScript: ESLint config in `frontend/` enforces React best practices
- Logging: Always use structured logging with request IDs for API operations
- Error Handling: Include descriptive error messages, full stack traces in logs

## Project-Specific Context

This is an internal tool for **银河航天 (GalaxySpace)** to analyze corporate travel expenses and detect policy violations. The Chinese field names in Excel sheets and code are intentional and should not be translated. When working with data analysis logic, preserve business domain terminology (e.g., 一级部门, 授信金额, 当日状态判断).
