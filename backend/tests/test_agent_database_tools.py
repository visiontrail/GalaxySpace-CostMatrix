"""Claude Agent 数据库与图表工具的安全边界测试。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.chart_tools import validate_chart_spec
from app.agents.database_tools import (
    DatabaseToolkit,
    ReadOnlyQueryError,
    validate_readonly_sql,
)
from app.db.models import Base, Department, User


@pytest.fixture()
def toolkit():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    session_factory = sessionmaker(bind=test_engine)
    with session_factory() as db:
        db.add_all(
            [
                Department(name="研发中心", level=1),
                Department(name="市场中心", level=1),
                Department(name="交付中心", level=1),
                User(
                    username="operator",
                    password_hash="must-never-leak",
                    is_admin=False,
                ),
            ]
        )
        db.commit()
    return DatabaseToolkit(
        db_engine=test_engine,
        session_factory=session_factory,
        max_rows=2,
    )


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE dim_department SET name='x'",
        "DELETE FROM dim_department",
        "DROP TABLE dim_department",
        "PRAGMA table_info(dim_department)",
        "SELECT 1; SELECT 2",
        "WITH x AS (DELETE FROM dim_department RETURNING id) SELECT * FROM x",
        "SELECT SLEEP(10)",
        "SELECT * FROM users INTO OUTFILE '/tmp/users.csv'",
        "SELECT @value := 1",
    ],
)
def test_readonly_validator_rejects_mutating_or_multi_statement_sql(sql):
    with pytest.raises(ReadOnlyQueryError):
        validate_readonly_sql(sql)


def test_readonly_validator_accepts_select_and_cte():
    assert validate_readonly_sql("SELECT 1;") == "SELECT 1"
    assert validate_readonly_sql("WITH x AS (SELECT 1 AS n) SELECT n FROM x")


def test_toolkit_discovers_all_tables_and_describes_business_fields(toolkit):
    payload = toolkit.list_tables()
    table_names = {item["table"] for item in payload["tables"]}
    assert "fact_attendance" in table_names
    assert "fact_travel_expense" in table_names
    assert "dim_department" in table_names

    user_fields = {
        column["name"] for column in toolkit.describe_table("users")["columns"]
    }
    assert "username" in user_fields
    assert "password_hash" not in user_fields


def test_toolkit_limits_rows_and_redacts_select_star_secrets(toolkit):
    departments = toolkit.execute_readonly_sql(
        "SELECT name FROM dim_department ORDER BY id"
    )
    assert departments["row_count"] == 2
    assert departments["truncated"] is True

    users = toolkit.execute_readonly_sql("SELECT * FROM users")
    assert users["rows"][0]["password_hash"] == "[REDACTED]"
    assert "password_hash" not in users["columns"]


def test_toolkit_blocks_explicit_secret_column_access(toolkit):
    with pytest.raises(ReadOnlyQueryError):
        toolkit.execute_readonly_sql("SELECT password_hash FROM users")


def test_chart_spec_requires_complete_json_echarts_option():
    spec = validate_chart_spec(
        {
            "chart_type": "bar",
            "title": "部门成本",
            "echarts_option": {
                "xAxis": {"type": "category", "data": ["研发", "市场"]},
                "yAxis": {"type": "value"},
                "series": [{"type": "bar", "data": [20, 10]}],
            },
        }
    )
    assert spec["chart_type"] == "bar"
    assert spec["echarts_option"]["series"][0]["type"] == "bar"

    with pytest.raises(ValueError):
        validate_chart_spec(
            {
                "chart_type": "unknown",
                "title": "x",
                "echarts_option": {"series": []},
            }
        )
