"""Database connection and initialization for CostMatrix."""
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

DB_DIR = Path(settings.upload_dir).parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_DB_PATH = DB_DIR / "costmatrix.db"


def _normalize_database_url(database_url: str) -> str:
    normalized = database_url.strip()
    if normalized.startswith("mysql://"):
        return normalized.replace("mysql://", "mysql+pymysql://", 1)
    return normalized


def _build_database_config():
    raw_url = settings.database_url.strip()
    if raw_url:
        database_url = _normalize_database_url(raw_url)
        if database_url.startswith("sqlite://"):
            sqlite_path = DEFAULT_DB_PATH
            try:
                parsed = make_url(database_url)
                if parsed.database:
                    parsed_path = Path(parsed.database)
                    if not parsed_path.is_absolute():
                        parsed_path = Path.cwd() / parsed_path
                    parsed_path.parent.mkdir(parents=True, exist_ok=True)
                    sqlite_path = parsed_path
            except Exception:
                pass
            return "sqlite", database_url, sqlite_path
        if database_url.startswith("mysql+pymysql://") or database_url.startswith("mysql://"):
            return "mysql", database_url, None
        return "unknown", database_url, None

    if settings.db_type == "mysql":
        mysql_url = URL.create(
            drivername="mysql+pymysql",
            username=settings.db_user,
            password=settings.db_password or None,
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
            query={"charset": settings.db_charset},
        )
        return "mysql", mysql_url.render_as_string(hide_password=False), None

    sqlite_url = f"sqlite:///{DEFAULT_DB_PATH}"
    return "sqlite", sqlite_url, DEFAULT_DB_PATH


DB_BACKEND, DATABASE_URL, DB_PATH = _build_database_config()
IS_SQLITE = DB_BACKEND == "sqlite"

engine_kwargs = {"echo": False}
if IS_SQLITE:
    engine_kwargs.update(
        connect_args={
            "check_same_thread": False,
            "timeout": 30,
        },
        poolclass=StaticPool,
    )
else:
    engine_kwargs.update(
        pool_pre_ping=True,
        pool_recycle=1800,
    )

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database with schema and indexes."""
    try:
        from app.db.models import Base

        try:
            Base.metadata.create_all(bind=engine)
        except OperationalError as exc:
            # Multiple Uvicorn workers may run startup concurrently. If another
            # worker has created tables first, treat "already exists" as benign.
            if "already exists" not in str(exc).lower():
                raise
            logger.warning(f"Concurrent schema initialization detected, skipping duplicate DDL: {exc}")

        if IS_SQLITE:
            with engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=DELETE"))
                conn.execute(text("PRAGMA synchronous=NORMAL"))
                conn.execute(text("PRAGMA cache_size=-64000"))
                conn.execute(text("PRAGMA foreign_keys=ON"))
                conn.execute(text("PRAGMA busy_timeout=30000"))
                conn.commit()

        location = str(DB_PATH) if DB_PATH else DATABASE_URL
        logger.info(f"Database initialized successfully ({DB_BACKEND}): {location}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_path() -> Optional[Path]:
    """Get sqlite database file path when using sqlite backend."""
    return DB_PATH
