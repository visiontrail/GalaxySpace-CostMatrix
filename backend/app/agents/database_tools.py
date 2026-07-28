"""提供给 Claude Agent 的全库只读查询工具集。"""
from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.db.database import SessionLocal, engine


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FORBIDDEN_SQL_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|"
    r"pragma|vacuum|grant|revoke|call|execute|set|merge|upsert|copy)\b",
    re.IGNORECASE,
)
_FORBIDDEN_SECRET_RE = re.compile(
    r"\b(password_hash|encrypted_api_key|api_key)\b",
    re.IGNORECASE,
)
_FORBIDDEN_READ_SIDE_EFFECT_RE = re.compile(
    r"\b(into\s+outfile|into\s+dumpfile|load_file|load_extension|readfile|"
    r"writefile|sleep|benchmark|get_lock|release_lock|for\s+update|"
    r"lock\s+in\s+share\s+mode)\b|:=",
    re.IGNORECASE,
)
_SENSITIVE_RESULT_COLUMNS = {
    "password_hash",
    "encrypted_api_key",
    "api_key",
}


class ReadOnlyQueryError(ValueError):
    """SQL 不满足 Agent 只读安全策略。"""


def _strip_comments_and_literals(sql: str) -> str:
    """去掉注释和字符串字面量，避免关键字检查被内容干扰。"""
    without_block_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    without_line_comments = re.sub(r"--[^\r\n]*", " ", without_block_comments)
    without_hash_comments = re.sub(r"#[^\r\n]*", " ", without_line_comments)
    without_single_quotes = re.sub(r"'(?:''|\\.|[^'])*'", "''", without_hash_comments)
    return re.sub(r'"(?:""|\\.|[^"])*"', '""', without_single_quotes)


def validate_readonly_sql(sql: str) -> str:
    """仅允许单条 SELECT / WITH ... SELECT / EXPLAIN SELECT。"""
    cleaned = sql.strip()
    if not cleaned:
        raise ReadOnlyQueryError("SQL 不能为空")

    normalized = _strip_comments_and_literals(cleaned).strip()
    normalized_without_trailing = normalized[:-1].rstrip() if normalized.endswith(";") else normalized
    if ";" in normalized_without_trailing:
        raise ReadOnlyQueryError("仅允许执行一条 SQL")
    if not re.match(r"^(select|with|explain)\b", normalized_without_trailing, re.IGNORECASE):
        raise ReadOnlyQueryError("仅允许 SELECT、WITH ... SELECT 或 EXPLAIN 查询")
    if _FORBIDDEN_SQL_RE.search(normalized_without_trailing):
        raise ReadOnlyQueryError("SQL 包含写入、DDL 或管理命令，已拒绝")
    if _FORBIDDEN_SECRET_RE.search(normalized_without_trailing):
        raise ReadOnlyQueryError("认证机密字段不可查询")
    if _FORBIDDEN_READ_SIDE_EFFECT_RE.search(normalized_without_trailing):
        raise ReadOnlyQueryError("SQL 包含文件、锁、延时或其他非纯读取操作，已拒绝")
    return cleaned[:-1].rstrip() if cleaned.endswith(";") else cleaned


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bytes):
        return f"<binary:{len(value)} bytes>"
    return str(value)


def _redact_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: (
            "[REDACTED]"
            if key.lower() in _SENSITIVE_RESULT_COLUMNS
            else _serialize(value)
        )
        for key, value in row.items()
    }


class DatabaseToolkit:
    """SQLAlchemy 驱动的可发现、可审计、只读数据库工具集。"""

    def __init__(
        self,
        *,
        db_engine: Engine = engine,
        session_factory: sessionmaker = SessionLocal,
        max_rows: int = 500,
        trace: Optional[List[Dict[str, Any]]] = None,
    ):
        self.engine = db_engine
        self.session_factory = session_factory
        self.max_rows = max(1, min(int(max_rows), 5_000))
        self.trace = trace if trace is not None else []

    def _table_names(self) -> List[str]:
        return sorted(inspect(self.engine).get_table_names())

    def _validate_identifier(self, value: str, *, kind: str) -> str:
        if not _IDENTIFIER_RE.fullmatch(value or ""):
            raise ReadOnlyQueryError(f"{kind}名称不合法")
        return value

    def _quote(self, value: str) -> str:
        return self.engine.dialect.identifier_preparer.quote(value)

    def list_tables(self) -> Dict[str, Any]:
        db_inspector = inspect(self.engine)
        tables = []
        for table_name in self._table_names():
            columns = db_inspector.get_columns(table_name)
            visible_columns = [
                column["name"]
                for column in columns
                if column["name"].lower() not in _SENSITIVE_RESULT_COLUMNS
            ]
            tables.append(
                {
                    "table": table_name,
                    "columns": visible_columns,
                    "column_count": len(visible_columns),
                }
            )
        return {"database": self.engine.dialect.name, "tables": tables}

    def describe_table(self, table_name: str) -> Dict[str, Any]:
        table_name = self._validate_identifier(table_name, kind="表")
        if table_name not in self._table_names():
            raise ReadOnlyQueryError(f"表不存在：{table_name}")

        db_inspector = inspect(self.engine)
        columns = []
        for column in db_inspector.get_columns(table_name):
            if column["name"].lower() in _SENSITIVE_RESULT_COLUMNS:
                continue
            columns.append(
                {
                    "name": column["name"],
                    "type": str(column["type"]),
                    "nullable": bool(column.get("nullable", True)),
                    "primary_key": bool(column.get("primary_key", False)),
                    "default": _serialize(column.get("default")),
                }
            )
        foreign_keys = [
            {
                "columns": item.get("constrained_columns", []),
                "references_table": item.get("referred_table"),
                "references_columns": item.get("referred_columns", []),
            }
            for item in db_inspector.get_foreign_keys(table_name)
        ]
        return {
            "table": table_name,
            "columns": columns,
            "foreign_keys": foreign_keys,
        }

    def execute_readonly_sql(self, sql: str, limit: Optional[int] = None) -> Dict[str, Any]:
        validated = validate_readonly_sql(sql)
        row_limit = min(max(int(limit or self.max_rows), 1), self.max_rows)
        stripped = _strip_comments_and_literals(validated).lstrip().lower()
        statement = (
            validated
            if stripped.startswith("explain")
            else f"SELECT * FROM ({validated}) AS costmatrix_agent_query LIMIT {row_limit + 1}"
        )

        with self.engine.connect() as connection:
            result = connection.execute(text(statement))
            raw_rows = [dict(row._mapping) for row in result.fetchall()]
            columns = list(result.keys())

        truncated = len(raw_rows) > row_limit
        rows = [_redact_row(row) for row in raw_rows[:row_limit]]
        return {
            "columns": [
                column
                for column in columns
                if column.lower() not in _SENSITIVE_RESULT_COLUMNS
            ],
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
            "max_rows": row_limit,
        }

    def sample_rows(self, table_name: str, limit: int = 5) -> Dict[str, Any]:
        table_name = self._validate_identifier(table_name, kind="表")
        if table_name not in self._table_names():
            raise ReadOnlyQueryError(f"表不存在：{table_name}")
        row_limit = min(max(int(limit), 1), 20)
        return self.execute_readonly_sql(
            f"SELECT * FROM {self._quote(table_name)}",
            limit=row_limit,
        )

    def get_distinct_values(
        self,
        table_name: str,
        column_name: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        table_name = self._validate_identifier(table_name, kind="表")
        column_name = self._validate_identifier(column_name, kind="字段")
        description = self.describe_table(table_name)
        visible_columns = {column["name"] for column in description["columns"]}
        if column_name not in visible_columns:
            raise ReadOnlyQueryError(f"字段不存在或不可访问：{column_name}")
        row_limit = min(max(int(limit), 1), 100)
        quoted_column = self._quote(column_name)
        return self.execute_readonly_sql(
            (
                f"SELECT {quoted_column} AS value, COUNT(*) AS record_count "
                f"FROM {self._quote(table_name)} "
                f"GROUP BY {quoted_column} ORDER BY record_count DESC"
            ),
            limit=row_limit,
        )

    def system_overview(self) -> Dict[str, Any]:
        overview: Dict[str, Any] = {
            "database": self.engine.dialect.name,
            "tables": [],
        }
        for table_name in self._table_names():
            try:
                quoted = self._quote(table_name)
                with self.engine.connect() as connection:
                    count = connection.execute(
                        text(f"SELECT COUNT(*) FROM {quoted}")
                    ).scalar_one()
                overview["tables"].append({"table": table_name, "row_count": int(count)})
            except Exception:
                overview["tables"].append({"table": table_name, "row_count": None})
        return overview

    def record_trace(
        self,
        *,
        tool_name: str,
        arguments: Dict[str, Any],
        started_at: float,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        summary = None
        if result is not None:
            summary = {
                "row_count": result.get("row_count"),
                "table_count": len(result.get("tables", []))
                if isinstance(result.get("tables"), list)
                else None,
                "truncated": result.get("truncated"),
            }
        self.trace.append(
            {
                "tool": tool_name,
                "arguments": arguments,
                "duration_ms": round((time.monotonic() - started_at) * 1_000),
                "result": summary,
                "error": error,
            }
        )


def _tool_response(payload: Dict[str, Any], *, is_error: bool = False) -> Dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            }
        ],
        **({"is_error": True} if is_error else {}),
    }


def build_database_mcp_server(
    *,
    max_rows: int,
    trace: List[Dict[str, Any]],
) -> tuple[Any, List[str]]:
    """创建每次 Agent 运行独立的数据库 MCP server。"""
    try:
        from claude_agent_sdk import create_sdk_mcp_server, tool
    except ImportError as exc:
        raise RuntimeError(
            "Claude Agent SDK 未安装，请执行 pip install -r requirements.txt"
        ) from exc

    toolkit = DatabaseToolkit(max_rows=max_rows, trace=trace)

    async def invoke(name: str, arguments: Dict[str, Any], function: Any) -> Dict[str, Any]:
        started_at = time.monotonic()
        try:
            result = function()
            toolkit.record_trace(
                tool_name=name,
                arguments=arguments,
                started_at=started_at,
                result=result,
            )
            return _tool_response(result)
        except Exception as exc:  # 工具错误要反馈给模型，以便它修正查询。
            toolkit.record_trace(
                tool_name=name,
                arguments=arguments,
                started_at=started_at,
                error=str(exc),
            )
            return _tool_response({"error": str(exc)}, is_error=True)

    @tool(
        "list_database_tables",
        "列出 CostMatrix 当前数据库中的全部表及可访问字段。开始分析前优先调用。",
        {},
    )
    async def list_database_tables(args):
        return await invoke("list_database_tables", args, toolkit.list_tables)

    @tool(
        "describe_database_table",
        "查看指定数据库表的字段类型和外键关系。",
        {"table_name": str},
    )
    async def describe_database_table(args):
        return await invoke(
            "describe_database_table",
            args,
            lambda: toolkit.describe_table(args["table_name"]),
        )

    @tool(
        "sample_database_rows",
        "抽样查看指定表的数据，最多 20 行。认证机密会自动隐藏。",
        {"table_name": str, "limit": int},
    )
    async def sample_database_rows(args):
        return await invoke(
            "sample_database_rows",
            args,
            lambda: toolkit.sample_rows(args["table_name"], args.get("limit", 5)),
        )

    @tool(
        "execute_readonly_sql",
        (
            "执行一条只读 SELECT、WITH ... SELECT 或 EXPLAIN SQL。"
            "结果会被限制行数，禁止写入、DDL、多语句和认证机密字段。"
        ),
        {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "只读 SQL"},
                "limit": {
                    "type": "integer",
                    "description": "返回行数，不超过系统设置上限",
                    "default": max_rows,
                },
            },
            "required": ["sql"],
        },
    )
    async def execute_readonly_sql(args):
        return await invoke(
            "execute_readonly_sql",
            args,
            lambda: toolkit.execute_readonly_sql(args["sql"], args.get("limit")),
        )

    @tool(
        "get_distinct_values",
        "查看字段的不同值及记录数，用于理解枚举、状态和数据分布。",
        {
            "type": "object",
            "properties": {
                "table_name": {"type": "string"},
                "column_name": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
            "required": ["table_name", "column_name"],
        },
    )
    async def get_distinct_values(args):
        return await invoke(
            "get_distinct_values",
            args,
            lambda: toolkit.get_distinct_values(
                args["table_name"],
                args["column_name"],
                args.get("limit", 50),
            ),
        )

    @tool(
        "get_system_data_overview",
        "返回全部数据库表和各表记录数，用于快速判断系统数据范围。",
        {},
    )
    async def get_system_data_overview(args):
        return await invoke(
            "get_system_data_overview",
            args,
            toolkit.system_overview,
        )

    tools = [
        list_database_tables,
        describe_database_table,
        sample_database_rows,
        execute_readonly_sql,
        get_distinct_values,
        get_system_data_overview,
    ]
    server_name = "costmatrix_db"
    server = create_sdk_mcp_server(name=server_name, version="1.0.0", tools=tools)
    allowed_tools = [f"mcp__{server_name}__{item.name}" for item in tools]
    return server, allowed_tools
