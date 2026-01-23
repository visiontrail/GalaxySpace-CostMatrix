"""SQLAlchemy database models for CostMatrix using star schema design."""
from datetime import datetime
from sqlalchemy import (
    String, Integer, Numeric, DateTime, ForeignKey, Boolean,
    Index, CheckConstraint, text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """System user for authentication"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=text("(DATETIME('now'))"),
    )

    __table_args__ = (
        Index("idx_users_username", "username", unique=True),
        Index("idx_users_admin", "is_admin"),
    )


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    upload_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    parse_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    last_analyzed: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    sheets_info: Mapped[str] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        Index("idx_uploads_hash", "file_hash"),
        Index("idx_uploads_time", "upload_time"),
    )


class Department(Base):
    __tablename__ = "dim_department"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_id: Mapped[int] = mapped_column(Integer, ForeignKey("dim_department.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    parent = relationship("Department", remote_side=[id], backref="children")

    __table_args__ = (
        Index("idx_dept_level", "level"),
        Index("idx_dept_parent", "parent_id"),
        Index("idx_dept_unique", "name", "level", "parent_id", unique=True),
    )


class Project(Base):
    __tablename__ = "dim_project"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_project_code", "code"),
    )


class Employee(Base):
    __tablename__ = "dim_employee"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("dim_department.id"), nullable=False)
    level2_department_id: Mapped[int] = mapped_column(Integer, ForeignKey("dim_department.id"), nullable=True)
    level3_department_id: Mapped[int] = mapped_column(Integer, ForeignKey("dim_department.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    department = relationship("Department", foreign_keys=[department_id], backref="employees")
    level2_department = relationship("Department", foreign_keys=[level2_department_id], backref="employees_l2")
    level3_department = relationship("Department", foreign_keys=[level3_department_id], backref="employees_l3")

    __table_args__ = (
        Index("idx_emp_dept", "department_id"),
        Index("idx_emp_dept_l2", "level2_department_id"),
        Index("idx_emp_dept_l3", "level3_department_id"),
    )


class AttendanceRecord(Base):
    __tablename__ = "fact_attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upload_id: Mapped[int] = mapped_column(Integer, ForeignKey("uploads.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("dim_employee.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    work_hours: Mapped[float] = mapped_column(Numeric(4, 2), default=0)
    latest_punch_time: Mapped[str] = mapped_column(String(10), nullable=True)  # HH:MM:SS format
    is_late_after_1930: Mapped[bool] = mapped_column(Boolean, default=False)

    employee = relationship("Employee", backref="attendance_records")
    upload = relationship("Upload", backref="attendance_records")

    __table_args__ = (
        Index("idx_attendance_date_emp", "date", "employee_id"),
        Index("idx_attendance_upload", "upload_id"),
        Index("idx_attendance_emp", "employee_id"),
        Index("idx_attendance_status", "status"),
        Index("idx_attendance_punch_time", "latest_punch_time"),
        CheckConstraint("work_hours >= 0", name="check_attendance_hours_positive"),
    )


class TravelExpense(Base):
    __tablename__ = "fact_travel_expense"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upload_id: Mapped[int] = mapped_column(Integer, ForeignKey("uploads.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("dim_employee.id"), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("dim_project.id"), nullable=True)
    expense_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    order_id: Mapped[str] = mapped_column(String(100), nullable=True)
    is_over_standard: Mapped[bool] = mapped_column(Boolean, default=False)
    over_type: Mapped[str] = mapped_column(String(50), nullable=True)
    advance_days: Mapped[int] = mapped_column(Integer, nullable=True)

    employee = relationship("Employee", backref="travel_expenses")
    project = relationship("Project", backref="travel_expenses")
    upload = relationship("Upload", backref="travel_expenses")

    __table_args__ = (
        Index("idx_travel_date_proj", "date", "project_id"),
        Index("idx_travel_type_date", "expense_type", "date"),
        Index("idx_travel_upload", "upload_id"),
        Index("idx_travel_emp_date", "employee_id", "date"),
        Index("idx_travel_emp", "employee_id"),
    )


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upload_id: Mapped[int] = mapped_column(Integer, ForeignKey("uploads.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("dim_employee.id"), nullable=False)
    anomaly_type: Mapped[str] = mapped_column(String(20), nullable=False)
    attendance_status: Mapped[str] = mapped_column(String(50), nullable=False)
    travel_records: Mapped[str] = mapped_column(String(500), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    employee = relationship("Employee", backref="anomalies")
    upload = relationship("Upload", backref="anomalies")

    __table_args__ = (
        Index("idx_anomalies_upload", "upload_id"),
        Index("idx_anomalies_date", "date", "employee_id"),
    )
