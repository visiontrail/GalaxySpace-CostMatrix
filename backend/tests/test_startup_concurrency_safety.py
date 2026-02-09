"""Regression tests for multi-worker startup races."""

from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.db import database
from app.db.models import Base, User
from app.services.auth_service import ensure_initial_admin


def build_session_factory(db_path: Path):
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_ensure_initial_admin_handles_concurrent_insert(tmp_path, monkeypatch):
    session_factory = build_session_factory(tmp_path / "auth_race.db")

    password_file = tmp_path / "initial_password.txt"
    password_file.write_text("admin123\n", encoding="utf-8")

    monkeypatch.setattr(settings, "default_admin_username", "admin")
    monkeypatch.setattr(settings, "initial_admin_password_file", str(password_file))

    with session_factory() as db:
        original_commit = db.commit

        def race_commit():
            # Simulate another worker creating the admin user right before commit.
            with session_factory() as other:
                exists = other.query(User).filter(User.username == "admin").first()
                if not exists:
                    other.add(
                        User(
                            username="admin",
                            password_hash="external-worker",
                            is_admin=True,
                            is_active=True,
                        )
                    )
                    other.commit()
            original_commit()

        monkeypatch.setattr(db, "commit", race_commit)

        user = ensure_initial_admin(db)
        assert user.username == "admin"

    with session_factory() as check_db:
        count = check_db.query(User).filter(User.username == "admin").count()
        assert count == 1


def test_init_db_ignores_duplicate_table_error(tmp_path, monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=StaticPool,
    )

    def duplicate_table_error(*args, **kwargs):
        raise OperationalError(
            "CREATE TABLE users (...)",
            {},
            Exception("table users already exists"),
        )

    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "costmatrix.db")
    monkeypatch.setattr(Base.metadata, "create_all", duplicate_table_error)

    # Should not raise for benign race-condition duplicate DDL.
    database.init_db()


def test_init_db_rethrows_non_duplicate_ddl_error(tmp_path, monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=StaticPool,
    )

    def fatal_ddl_error(*args, **kwargs):
        raise OperationalError(
            "CREATE TABLE users (...)",
            {},
            Exception("disk I/O error"),
        )

    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "costmatrix.db")
    monkeypatch.setattr(Base.metadata, "create_all", fatal_ddl_error)

    with pytest.raises(OperationalError):
        database.init_db()
