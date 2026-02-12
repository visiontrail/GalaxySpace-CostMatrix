"""
FastAPI 主应用入口
"""
import sys
from pathlib import Path

# 尝试将包含 logger_config.py 的仓库根目录加入 sys.path（仅在存在时）
PROJECT_ROOT = next(
    (p for p in Path(__file__).resolve().parents if (p / "logger_config.py").exists()),
    None,
)
if PROJECT_ROOT and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes import router
from app.db.database import init_db, SessionLocal
from app.services.auth_service import ensure_initial_admin

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="企业级行政与差旅成本效能分析平台",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api", tags=["analysis"])


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()

    cache_dir = Path(settings.upload_dir) / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 确保默认管理员账号存在
    with SessionLocal() as db:
        ensure_initial_admin(db)


@app.get("/")
async def root():
    """根路径"""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
