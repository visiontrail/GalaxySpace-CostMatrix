"""CRUD operations for database access."""
import hashlib
import json
from datetime import datetime, time, timedelta
from typing import List, Optional, Tuple
import pandas as pd
from sqlalchemy import func, and_, or_, select, text, alias, case, bindparam
from sqlalchemy.orm import Session, aliased
from app.db.models import (
    Upload, Department, Project, Employee,
    AttendanceRecord, TravelExpense, Anomaly
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _month_ranges(months: List[str]) -> List[Tuple[datetime, datetime]]:
    """Convert YYYY-MM strings to (start, end) datetime ranges."""
    ranges = []
    for month in months:
        try:
            month_start = datetime.strptime(f"{month}-01", "%Y-%m-%d")
        except ValueError:
            continue
        month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(seconds=1)
        ranges.append((month_start, month_end))
    return ranges


def _date_range_filter(column, ranges: List[Tuple[datetime, datetime]]):
    """Build OR date filter for SQLAlchemy based on multiple ranges."""
    if not ranges:
        return None
    return or_(*[and_(column >= start, column <= end) for start, end in ranges])


def _unknown_status_condition(status_column):
    """SQL condition for unknown/empty attendance status."""
    trimmed = func.trim(status_column)
    return or_(status_column.is_(None), trimmed.in_(['', '未知', 'nan', 'None']))


def _serialize_anomaly_row(row, date_format: str = '%Y-%m-%d') -> dict:
    """Normalize anomaly row with a fallback description."""
    date_str = row.date.strftime(date_format)
    detail = row.detail or ''
    if not detail and row.travel_records:
        try:
            travel_records = json.loads(row.travel_records)
        except Exception:
            travel_records = []
        if travel_records:
            status_text = row.status or '上班'
            detail = f"{row.name} 在 {date_str} 考勤显示{status_text}，但有 {','.join(travel_records)} 消费记录，存在时间和地点冲突"

    return {
        'date': date_str,
        'name': row.name,
        'dept': row.dept,
        'type': row.type,
        'status': row.status,
        'detail': detail
    }


def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_or_create_department(db: Session, name: str, level: int = 1, parent_id: Optional[int] = None) -> int:
    """Get or create a department, returning its ID."""
    import pandas as pd

    if not name or (isinstance(name, str) and name.strip() == '') or (isinstance(name, float) and pd.isna(name)):
        name = '未知部门'

    # Query by (name, level, parent_id) to support multi-level hierarchy
    query = db.query(Department).filter_by(name=name, level=level)
    if parent_id is not None:
        query = query.filter_by(parent_id=parent_id)
    else:
        query = query.filter(Department.parent_id.is_(None))

    dept = query.first()
    if not dept:
        dept = Department(name=name, level=level, parent_id=parent_id)
        db.add(dept)
        db.flush()
    return dept.id


def get_or_create_department_hierarchy(db: Session, level1_name: str, level2_name: Optional[str] = None, level3_name: Optional[str] = None) -> Tuple[int, int, int]:
    """
    Get or create a complete 3-level department hierarchy, returning (level1_id, level2_id, level3_id).

    Args:
        db: Database session
        level1_name: Level-1 department name (required)
        level2_name: Level-2 department name (optional)
        level3_name: Level-3 department name (optional)

    Returns:
        Tuple of (level1_id, level2_id, level3_id). Missing levels return 0.
    """
    import pandas as pd

    # Create/get level-1 department
    level1_id = get_or_create_department(db, level1_name, level=1, parent_id=None)

    level2_id = 0
    if level2_name and not (isinstance(level2_name, float) and pd.isna(level2_name)):
        level2_id = get_or_create_department(db, level2_name, level=2, parent_id=level1_id)

    level3_id = 0
    if level3_name and not (isinstance(level3_name, float) and pd.isna(level3_name)) and level2_id > 0:
        level3_id = get_or_create_department(db, level3_name, level=3, parent_id=level2_id)

    return level1_id, level2_id, level3_id


def get_or_create_project(db: Session, code: str, name: str) -> int:
    """Get or create a project, returning its ID."""
    import pandas as pd
    
    if not code or (isinstance(code, str) and code.strip() == '') or (isinstance(code, float) and pd.isna(code)):
        code = '未知项目'
    if not name or (isinstance(name, str) and name.strip() == '') or (isinstance(name, float) and pd.isna(name)):
        name = '未知项目'
    
    project = db.query(Project).filter_by(code=code).first()
    if not project:
        project = Project(code=code, name=name)
        db.add(project)
        db.flush()
    return project.id


def get_or_create_employee(db: Session, name: str, level1_id: int, level2_id: Optional[int] = None, level3_id: Optional[int] = None, update_dept: bool = False) -> int:
    """Get or create an employee with full department hierarchy, returning their ID."""
    import pandas as pd

    if not name or (isinstance(name, str) and name.strip() == '') or (isinstance(name, float) and pd.isna(name)):
        name = '未知员工'

    employee = db.query(Employee).filter_by(name=name).first()
    if not employee:
        employee = Employee(
            name=name,
            department_id=level1_id,
            level2_department_id=level2_id if level2_id and level2_id > 0 else None,
            level3_department_id=level3_id if level3_id and level3_id > 0 else None
        )
        db.add(employee)
        db.flush()
    elif update_dept:
        # 只有在明确要求更新部门时才更新（避免覆盖已有的正确部门信息）
        employee.department_id = level1_id

        # 仅当新数据提供了有效的部门 ID 时才更新，避免因为差旅表缺少三级部门信息而把已有映射清空
        if level2_id and level2_id > 0:
            employee.level2_department_id = level2_id
        # 如果没有提供 level2_id，则保留现有值

        if level3_id and level3_id > 0:
            employee.level3_department_id = level3_id
        # 如果没有提供 level3_id，则保留现有值，防止被意外置空
        db.flush()
    return employee.id


def create_or_get_upload_record(
    db: Session,
    file_name: str,
    file_path: str,
    file_size: int,
    sheets_info: List[str]
) -> Upload:
    file_hash = calculate_file_hash(file_path)
    existing_upload = db.query(Upload).filter_by(file_hash=file_hash).first()
    
    if existing_upload:
        existing_upload.file_path = file_path
        existing_upload.file_name = file_name
        existing_upload.file_size = file_size
        existing_upload.sheets_info = json.dumps(sheets_info)
        db.flush()
        return existing_upload
    
    upload = Upload(
        file_name=file_name,
        file_path=file_path,
        file_size=file_size,
        file_hash=file_hash,
        sheets_info=json.dumps(sheets_info),
        parse_status="parsed"
    )
    db.add(upload)
    db.flush()
    return upload


def delete_upload_data(db: Session, upload_id: int):
    db.query(AttendanceRecord).filter_by(upload_id=upload_id).delete()
    db.query(TravelExpense).filter_by(upload_id=upload_id).delete()
    db.query(Anomaly).filter_by(upload_id=upload_id).delete()
    db.flush()


def batch_insert_attendance(db: Session, upload_id: int, df: pd.DataFrame) -> int:
    """Batch insert attendance records from DataFrame."""
    import pandas as pd

    def _normalize_punch_time(punch_time):
        """Convert mixed Excel time formats to zero-padded HH:MM:SS strings."""
        if pd.isna(punch_time):
            return None

        if isinstance(punch_time, str):
            punch_time = punch_time.strip()
            if not punch_time:
                return None
            for fmt in ("%H:%M:%S", "%H:%M"):
                try:
                    return datetime.strptime(punch_time, fmt).strftime("%H:%M:%S")
                except ValueError:
                    continue
            return punch_time

        if isinstance(punch_time, pd.Timestamp):
            return punch_time.to_pydatetime().strftime("%H:%M:%S")

        if isinstance(punch_time, time):
            return punch_time.strftime("%H:%M:%S")

        if isinstance(punch_time, datetime):
            return punch_time.strftime("%H:%M:%S")

        if isinstance(punch_time, (int, float)):
            try:
                total_seconds = float(punch_time) * 24 * 3600
                if total_seconds < 0:
                    return None
                hours = int(total_seconds // 3600) % 24
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(round(total_seconds % 60))
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            except Exception:
                return None

        return None

    records = []
    for _, row in df.iterrows():
        name = row['姓名']
        if pd.isna(name) or (isinstance(name, str) and name.strip() == ''):
            continue

        # Extract all three department levels
        level1_name = row.get('一级部门', '未知部门')
        if pd.isna(level1_name) or (isinstance(level1_name, str) and level1_name.strip() == ''):
            level1_name = '未知部门'

        level2_name = row.get('二级部门')
        level3_name = row.get('三级部门')

        status = row['当日状态判断']
        if pd.isna(status) or (isinstance(status, str) and status.strip() == ''):
            status = '未知'

        # Create full department hierarchy
        level1_id, level2_id, level3_id = get_or_create_department_hierarchy(
            db, level1_name, level2_name, level3_name
        )

        emp_id = get_or_create_employee(db, name, level1_id, level2_id, level3_id)

        # Extract latest_punch_time from '最晚打卡时间' column
        latest_punch_time = _normalize_punch_time(row.get('最晚打卡时间'))

        # Check if late after 19:30 from '最晚19:30之后' column
        is_late_after_1930 = False
        late_marker = row.get('最晚19:30之后')
        if pd.notna(late_marker) and isinstance(late_marker, str) and late_marker.strip() == '符合':
            is_late_after_1930 = True

        records.append({
            'upload_id': upload_id,
            'date': pd.to_datetime(row['日期']),
            'employee_id': emp_id,
            'status': status,
            'work_hours': float(row.get('工时', 0)) if pd.notna(row.get('工时')) else 0.0,
            'latest_punch_time': latest_punch_time,
            'is_late_after_1930': is_late_after_1930
        })

    db.bulk_insert_mappings(AttendanceRecord, records)
    db.flush()
    return len(records)


def batch_insert_travel_expenses(
    db: Session,
    upload_id: int,
    df: pd.DataFrame,
    expense_type: str
) -> int:
    """Batch insert travel expense records from DataFrame."""
    import pandas as pd

    type_mapping = {'机票': 'flight', '酒店': 'hotel', '火车票': 'train'}
    mapped_type = type_mapping.get(expense_type, expense_type.lower())

    def _to_clean_str(v) -> str:
        if v is None:
            return ""
        if isinstance(v, float) and pd.isna(v):
            return ""
        if pd.isna(v):
            return ""
        return str(v).strip()

    def _is_yes(v) -> bool:
        s = _to_clean_str(v)
        if not s:
            return False
        # 兼容 "是"/"否"、"Y"/"N"、"true"/"false"、"1"/"0"
        if s in {"是", "Y", "YES", "Yes", "yes", "TRUE", "True", "true", "1"}:
            return True
        return "是" in s

    def _extract_over_type(row) -> str:
        # 不同月份模板可能使用不同列名
        for key in ("超标类型", "超标项", "超标项目", "超标类别", "超标选项"):
            val = _to_clean_str(row.get(key, ""))
            if val:
                return val
        return ""

    def _compute_is_over_standard(sheet: str, row) -> bool:
        # 酒店/火车票通常提供“是否超标”
        if _is_yes(row.get("是否超标")):
            return True

        over_type = _extract_over_type(row)
        if not over_type:
            return False

        # 机票：按“超标类型”关键字判断
        if sheet == "机票":
            return any(k in over_type for k in ("超折扣", "超时间", "超标"))

        # 兜底：若有“超标”描述但没有“是否超标”
        return "超" in over_type

    records = []
    for _, row in df.iterrows():
        name = row['姓名']
        if pd.isna(name) or (isinstance(name, str) and name.strip() == ''):
            continue

        # Extract all three department levels
        level1_name = row.get('一级部门', '未知部门')
        if pd.isna(level1_name) or (isinstance(level1_name, str) and level1_name.strip() == ''):
            level1_name = '未知部门'

        level2_name = row.get('二级部门')
        level3_name = row.get('三级部门')

        # Create full department hierarchy
        level1_id, level2_id, level3_id = get_or_create_department_hierarchy(db, level1_name, level2_name, level3_name)

        # 只有当部门信息有效时才更新员工部门（避免用"未知部门"覆盖已有正确部门）
        emp_id = get_or_create_employee(db, name, level1_id, level2_id, level3_id, update_dept=(level1_name != '未知部门'))

        project_str = str(row.get('项目', ''))
        if pd.isna(project_str) or project_str.strip() == '':
            project_code = '未知项目'
            project_name = '未知项目'
        else:
            project_code = project_str.split()[0] if ' ' in project_str else project_str
            project_name = project_str.split(' ', 1)[1] if ' ' in project_str and len(project_str.split(' ')) > 1 else project_str

        proj_id = get_or_create_project(db, project_code, project_name)

        date_field_map = {
            '机票': '起飞日期',
            '酒店': '入住日期',
            '火车票': '出发日期'
        }
        date_field = date_field_map.get(expense_type, '出发日期')
        travel_date = pd.to_datetime(row[date_field]) if pd.notna(row.get(date_field)) else None

        if not travel_date:
            continue

        is_over_standard = _compute_is_over_standard(expense_type, row)
        over_type = _extract_over_type(row)

        records.append({
            'upload_id': upload_id,
            'date': travel_date,
            'employee_id': emp_id,
            'project_id': proj_id,
            'expense_type': mapped_type,
            'amount': float(row.get('授信金额', 0)) if pd.notna(row.get('授信金额')) else 0.0,
            'order_id': str(row.get('订单号', '')) if pd.notna(row.get('订单号')) else '',
            'is_over_standard': bool(is_over_standard),
            'over_type': over_type,
            'advance_days': int(row.get('提前预定天数')) if pd.notna(row.get('提前预定天数')) else None
        })

    db.bulk_insert_mappings(TravelExpense, records)
    db.flush()
    return len(records)


def batch_insert_anomalies(db: Session, upload_id: int, anomalies: List[dict]) -> int:
    """Batch insert anomaly records."""
    records = []
    for anomaly in anomalies:
        dept_name = anomaly.get('dept') or anomaly.get('department') or '未知部门'
        level1_id = get_or_create_department(db, dept_name, level=1, parent_id=None)
        emp_id = get_or_create_employee(db, anomaly['name'], level1_id)
        anomaly_type = anomaly.get('type') or anomaly.get('anomaly_type') or 'A'
        description = anomaly.get('description') or anomaly.get('detail') or ''
        travel_records = anomaly.get('travel_records', [])
        records.append({
            'upload_id': upload_id,
            'date': pd.to_datetime(anomaly['date']),
            'employee_id': emp_id,
            'anomaly_type': anomaly_type,
            'attendance_status': anomaly.get('attendance_status', '上班'),
            'travel_records': json.dumps(travel_records),
            'description': description
        })

    db.bulk_insert_mappings(Anomaly, records)
    db.flush()
    return len(records)


def get_dashboard_summary(
    db: Session,
    file_path: str,
    months: Optional[List[str]] = None,
    quarter: Optional[int] = None,
    year: Optional[int] = None
) -> dict:
    """Get dashboard summary with optional date filters."""
    upload = db.query(Upload).filter_by(file_path=file_path).first()
    if not upload:
        return {}

    where_clauses = [TravelExpense.upload_id == upload.id]

    if months:
        month_placeholders = ','.join([f':month_{i}' for i in range(len(months))])
        params = {f'month_{i}': month for i, month in enumerate(months)}
        where_clauses.append(text(f"strftime('%Y-%m', TravelExpense.date) IN ({month_placeholders})").bindparams(**params))
    elif quarter and year:
        where_clauses.extend([
            func.extract('quarter', TravelExpense.date) == quarter,
            func.extract('year', TravelExpense.date) == year
        ])
    elif year:
        where_clauses.append(func.extract('year', TravelExpense.date) == year)

    total_cost_result = db.query(
        func.sum(TravelExpense.amount).label('total_cost'),
        func.count(TravelExpense.id).label('total_orders'),
        func.sum(case((TravelExpense.is_over_standard == True, 1), else_=0)).label('over_standard_count')
    ).filter(and_(*where_clauses)).first()

    attendance_where = [AttendanceRecord.upload_id == upload.id]
    if months:
        month_placeholders = ','.join([f':month_{i}' for i in range(len(months))])
        params = {f'month_{i}': month for i, month in enumerate(months)}
        attendance_where.append(text(f"strftime('%Y-%m', date) IN ({month_placeholders})").bindparams(**params))
    elif quarter and year:
        attendance_where.extend([
            func.extract('quarter', AttendanceRecord.date) == quarter,
            func.extract('year', AttendanceRecord.date) == year
        ])
    elif year:
        attendance_where.append(func.extract('year', AttendanceRecord.date) == year)

    avg_hours_result = db.query(
        func.avg(AttendanceRecord.work_hours).label('avg_hours')
    ).filter(
        and_(*attendance_where),
        AttendanceRecord.work_hours != 0
    ).first()

    return {
        'total_cost': float(total_cost_result.total_cost or 0),
        'total_orders': total_cost_result.total_orders or 0,
        'over_standard_count': total_cost_result.over_standard_count or 0,
        'avg_work_hours': float(avg_hours_result.avg_hours or 0)
    }


def get_anomalies(
    db: Session,
    file_path: str,
    months: Optional[List[str]] = None,
    quarter: Optional[int] = None,
    year: Optional[int] = None,
    limit: int = 50
) -> List[dict]:
    """Get anomalies with optional date filters."""
    upload = db.query(Upload).filter_by(file_path=file_path).first()
    if not upload:
        return []

    where_clauses = [Anomaly.upload_id == upload.id]

    if months:
        month_placeholders = ','.join([f':month_{i}' for i in range(len(months))])
        params = {f'month_{i}': month for i, month in enumerate(months)}
        where_clauses.append(text(f"strftime('%Y-%m', date) IN ({month_placeholders})").bindparams(**params))
    elif quarter and year:
        where_clauses.extend([
            func.extract('quarter', Anomaly.date) == quarter,
            func.extract('year', Anomaly.date) == year
        ])
    elif year:
        where_clauses.append(func.extract('year', Anomaly.date) == year)

    result = db.query(
        Anomaly.date,
        Employee.name.label('name'),
        Department.name.label('dept'),
        Anomaly.anomaly_type.label('type'),
        Anomaly.attendance_status.label('status'),
        Anomaly.description.label('detail'),
        Anomaly.travel_records.label('travel_records'),
    ).join(
        Employee, Anomaly.employee_id == Employee.id
    ).join(
        Department, Employee.department_id == Department.id
    ).filter(and_(*where_clauses)).order_by(
        Anomaly.date.desc()
    ).limit(limit).all()

    return [_serialize_anomaly_row(row) for row in result]


def get_available_months(db: Session, file_path: str) -> List[str]:
    """Get list of available months (YYYY-MM format) for a file."""
    upload = db.query(Upload).filter_by(file_path=file_path).first()
    if not upload:
        return []

    result = db.query(
        func.distinct(text("strftime('%Y-%m', date)")).label('month')
    ).filter(
        AttendanceRecord.upload_id == upload.id
    ).order_by('month').all()

    return [row.month for row in result]


def get_project_total_cost_by_month(
    db: Session,
    file_path: str,
    project_code: str,
    month: str
) -> float:
    """
    Get total cost for a specific project in a specific month.

    Args:
        db: Database session
        file_path: Excel file path
        project_code: Project code (e.g., '00000' for '公司公共')
        month: Month in 'YYYY-MM' format (e.g., '2025-08')

    Returns:
        Total cost as a float
    """
    upload = db.query(Upload).filter_by(file_path=file_path).first()
    if not upload:
        return 0.0

    # Query total cost for the project in the specified month
    result = db.query(
        func.sum(TravelExpense.amount).label('total_cost')
    ).join(
        Project, TravelExpense.project_id == Project.id
    ).filter(
        and_(
            TravelExpense.upload_id == upload.id,
            Project.code == project_code,
            text(f"strftime('%Y-%m', fact_travel_expense.date) = :month").bindparams(month=month)
        )
    ).first()

    return float(result.total_cost or 0.0)


def get_all_project_details(db: Session, file_path: str) -> List[dict]:
    """Get detailed information for all projects from database."""
    upload = db.query(Upload).filter_by(file_path=file_path).first()
    if not upload:
        return []

    project_result = db.query(
        Project.code,
        Project.name,
        func.sum(TravelExpense.amount).label('total_cost'),
        func.count(TravelExpense.id).label('record_count'),
        func.sum(case((TravelExpense.expense_type == 'flight', TravelExpense.amount), else_=0)).label('flight_cost'),
        func.sum(case((TravelExpense.expense_type == 'hotel', TravelExpense.amount), else_=0)).label('hotel_cost'),
        func.sum(case((TravelExpense.expense_type == 'train', TravelExpense.amount), else_=0)).label('train_cost'),
        func.count(func.distinct(Employee.id)).label('person_count'),
        func.min(TravelExpense.date).label('date_start'),
        func.max(TravelExpense.date).label('date_end'),
        func.sum(case((TravelExpense.is_over_standard == True, 1), else_=0)).label('over_standard_count'),
    ).join(
        TravelExpense, Project.id == TravelExpense.project_id
    ).join(
        Employee, TravelExpense.employee_id == Employee.id
    ).filter(
        TravelExpense.upload_id == upload.id
    ).group_by(
        Project.code, Project.name
    ).order_by(
        func.sum(TravelExpense.amount).desc()
    ).all()

    results = []
    for row in project_result:
        results.append({
            'code': row.code,
            'name': row.name,
            'total_cost': float(row.total_cost or 0),
            'flight_cost': float(row.flight_cost or 0),
            'hotel_cost': float(row.hotel_cost or 0),
            'train_cost': float(row.train_cost or 0),
            'record_count': row.record_count or 0,
            'person_count': row.person_count or 0,
            'date_range': {
                'start': row.date_start.strftime('%Y-%m-%d') if row.date_start else '',
                'end': row.date_end.strftime('%Y-%m-%d') if row.date_end else ''
            },
            'over_standard_count': row.over_standard_count or 0
        })

    return results


def get_project_order_records(db: Session, file_path: str, project_code: str) -> List[dict]:
    """Get all order records for a specific project from database."""
    upload = db.query(Upload).filter_by(file_path=file_path).first()
    if not upload:
        return []

    result = db.query(
        TravelExpense.id.label('id'),
        Project.code.label('project_code'),
        Project.name.label('project_name'),
        Employee.name.label('person'),
        Department.name.label('department'),
        TravelExpense.expense_type.label('type'),
        TravelExpense.amount.label('amount'),
        TravelExpense.date.label('date'),
        TravelExpense.is_over_standard.label('is_over_standard'),
        TravelExpense.over_type.label('over_type'),
        TravelExpense.advance_days.label('advance_days'),
    ).join(
        Project, TravelExpense.project_id == Project.id
    ).join(
        Employee, TravelExpense.employee_id == Employee.id
    ).join(
        Department, Employee.department_id == Department.id
    ).filter(
        TravelExpense.upload_id == upload.id,
        Project.code == project_code
    ).order_by(
        TravelExpense.date.desc()
    ).all()

    records = []
    for row in result:
        records.append({
            'id': str(row.id),
            'project_code': row.project_code,
            'project_name': row.project_name,
            'person': row.person,
            'department': row.department,
            'type': row.type,
            'amount': float(row.amount),
            'date': row.date.strftime('%Y-%m-%d') if row.date else '',
            'is_over_standard': bool(row.is_over_standard),
            'over_type': row.over_type or '',
            'advance_days': row.advance_days
        })

    return records


def get_department_stats(
    db: Session,
    file_path: str,
    months: Optional[List[str]] = None,
    quarter: Optional[int] = None,
    year: Optional[int] = None,
    top_n: int = 15
) -> List[dict]:
    """Get department statistics with optional date filters."""
    upload = db.query(Upload).filter_by(file_path=file_path).first()
    if not upload:
        return []

    where_clauses = [TravelExpense.upload_id == upload.id]

    if months:
        month_placeholders = ','.join([f':month_{i}' for i in range(len(months))])
        params = {f'month_{i}': month for i, month in enumerate(months)}
        where_clauses.append(text(f"strftime('%Y-%m', TravelExpense.date) IN ({month_placeholders})").bindparams(**params))
    elif quarter and year:
        where_clauses.extend([
            func.extract('quarter', TravelExpense.date) == quarter,
            func.extract('year', TravelExpense.date) == year
        ])
    elif year:
        where_clauses.append(func.extract('year', TravelExpense.date) == year)

    result = db.query(
        Department.name.label('dept'),
        func.sum(TravelExpense.amount).label('cost'),
        func.sum(case((TravelExpense.expense_type == 'flight', TravelExpense.amount), else_=0)).label('flight_cost'),
        func.sum(case((TravelExpense.expense_type == 'hotel', TravelExpense.amount), else_=0)).label('hotel_cost'),
        func.sum(case((TravelExpense.expense_type == 'train', TravelExpense.amount), else_=0)).label('train_cost'),
        func.count(func.distinct(Employee.id)).label('headcount'),
    ).join(
        Employee, TravelExpense.employee_id == Employee.id
    ).join(
        Department, Employee.department_id == Department.id
    ).filter(and_(*where_clauses)).group_by(
        Department.name
    ).order_by(
        func.sum(TravelExpense.amount).desc()
    ).limit(top_n).all()

    attendance_where = [AttendanceRecord.upload_id == upload.id]
    if months:
        month_placeholders = ','.join([f':month_{i}' for i in range(len(months))])
        params = {f'month_{i}': month for i, month in enumerate(months)}
        attendance_where.append(text(f"strftime('%Y-%m', date) IN ({month_placeholders})").bindparams(**params))
    elif quarter and year:
        attendance_where.extend([
            func.extract('quarter', AttendanceRecord.date) == quarter,
            func.extract('year', AttendanceRecord.date) == year
        ])
    elif year:
        attendance_where.append(func.extract('year', AttendanceRecord.date) == year)

    attendance_result = db.query(
        Department.name.label('dept'),
        func.avg(AttendanceRecord.work_hours).label('avg_hours')
    ).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).join(
        Department, Employee.department_id == Department.id
    ).filter(
        and_(*attendance_where),
        AttendanceRecord.work_hours != 0
    ).group_by(
        Department.name
    ).all()

    avg_hours_map = {row.dept: float(row.avg_hours or 0) for row in attendance_result}

    stats = []
    for row in result:
        stats.append({
            'dept': row.dept,
            'cost': float(row.cost or 0),
            'flight_cost': float(row.flight_cost or 0),
            'hotel_cost': float(row.hotel_cost or 0),
            'train_cost': float(row.train_cost or 0),
            'headcount': row.headcount or 0,
            'avg_hours': avg_hours_map.get(row.dept, 0)
        })

    return stats


def get_project_stats(
    db: Session,
    file_path: str,
    months: Optional[List[str]] = None,
    quarter: Optional[int] = None,
    year: Optional[int] = None,
    top_n: int = 20
) -> List[dict]:
    """Get project statistics with optional date filters."""
    upload = db.query(Upload).filter_by(file_path=file_path).first()
    if not upload:
        return []

    where_clauses = [TravelExpense.upload_id == upload.id]

    if months:
        month_placeholders = ','.join([f':month_{i}' for i in range(len(months))])
        params = {f'month_{i}': month for i, month in enumerate(months)}
        where_clauses.append(text(f"strftime('%Y-%m', TravelExpense.date) IN ({month_placeholders})").bindparams(**params))
    elif quarter and year:
        where_clauses.extend([
            func.extract('quarter', TravelExpense.date) == quarter,
            func.extract('year', TravelExpense.date) == year
        ])
    elif year:
        where_clauses.append(func.extract('year', TravelExpense.date) == year)

    result = db.query(
        Project.code.label('code'),
        Project.name.label('name'),
        func.sum(TravelExpense.amount).label('cost'),
        func.sum(case((TravelExpense.expense_type == 'flight', TravelExpense.amount), else_=0)).label('flight_cost'),
        func.sum(case((TravelExpense.expense_type == 'hotel', TravelExpense.amount), else_=0)).label('hotel_cost'),
        func.sum(case((TravelExpense.expense_type == 'train', TravelExpense.amount), else_=0)).label('train_cost'),
        func.count(TravelExpense.id).label('order_count'),
    ).join(
        TravelExpense, Project.id == TravelExpense.project_id
    ).filter(and_(*where_clauses)).group_by(
        Project.code, Project.name
    ).order_by(
        func.sum(TravelExpense.amount).desc()
    ).limit(top_n).all()

    stats = []
    for row in result:
        stats.append({
            'code': row.code,
            'name': row.name,
            'cost': float(row.cost or 0),
            'flight_cost': float(row.flight_cost or 0),
            'hotel_cost': float(row.hotel_cost or 0),
            'train_cost': float(row.train_cost or 0),
            'order_count': row.order_count or 0
        })

    return stats


def get_total_project_count(
    db: Session,
    file_path: str,
    months: Optional[List[str]] = None,
    quarter: Optional[int] = None,
    year: Optional[int] = None
) -> int:
    """Get total count of distinct projects with optional date filters."""
    upload = db.query(Upload).filter_by(file_path=file_path).first()
    if not upload:
        return 0

    where_clauses = [TravelExpense.upload_id == upload.id]

    if months:
        month_placeholders = ','.join([f':month_{i}' for i in range(len(months))])
        params = {f'month_{i}': month for i, month in enumerate(months)}
        where_clauses.append(text(f"strftime('%Y-%m', TravelExpense.date) IN ({month_placeholders})").bindparams(**params))
    elif quarter and year:
        where_clauses.extend([
            func.extract('quarter', TravelExpense.date) == quarter,
            func.extract('year', TravelExpense.date) == year
        ])
    elif year:
        where_clauses.append(func.extract('year', TravelExpense.date) == year)

    result = db.query(
        func.count(func.distinct(TravelExpense.project_id)).label('total_count')
    ).filter(and_(*where_clauses)).first()

    return result.total_count or 0


def get_all_departments(db: Session, file_path: str) -> List[dict]:
    """Get all departments with their statistics."""
    upload = db.query(Upload).filter_by(file_path=file_path).first()
    if not upload:
        return []

    departments = db.query(Department).all()

    result = []
    for dept in departments:
        total_cost = db.query(func.sum(TravelExpense.amount)).join(
            Employee, Employee.department_id == dept.id
        ).join(
            TravelExpense, TravelExpense.employee_id == Employee.id
        ).filter(TravelExpense.upload_id == upload.id).scalar() or 0

        person_count = len(dept.employees)

        avg_hours = db.query(func.avg(AttendanceRecord.work_hours)).join(
            Employee, Employee.department_id == dept.id
        ).filter(
            AttendanceRecord.upload_id == upload.id,
            AttendanceRecord.work_hours.isnot(None),
            AttendanceRecord.work_hours != 0
        ).scalar() or 0

        result.append({
            'id': dept.id,
            'name': dept.name,
            'level': dept.level,
            'parent_id': dept.parent_id,
            'total_cost': round(float(total_cost), 2),
            'person_count': person_count,
            'avg_work_hours': round(float(avg_hours), 2)
        })

    return result


def get_department_hierarchy(db: Session, file_path: str) -> dict:
    """Get department hierarchy structure."""
    upload = db.query(Upload).filter_by(file_path=file_path).first()
    if not upload:
        return {'level1': [], 'level2': {}, 'level3': {}}

    level1 = db.query(Department).filter_by(level=1).all()
    level1_names = [d.name for d in level1]

    level2_map = {}
    level3_map = {}

    for l1 in level1:
        level2 = db.query(Department).filter_by(level=2, parent_id=l1.id).all()
        l2_names = [d.name for d in level2]
        level2_map[l1.name] = l2_names

        for l2 in level2:
            level3 = db.query(Department).filter_by(level=3, parent_id=l2.id).all()
            l3_names = [d.name for d in level3]
            if l3_names:
                level3_map[l2.name] = l3_names

    return {
        'level1': level1_names,
        'level2': level2_map,
        'level3': level3_map
    }


def get_department_list(
    db: Session,
    file_path: str,
    level: int,
    parent: Optional[str] = None
) -> List[dict]:
    """Get departments at specified level with cost and person count."""
    upload = db.query(Upload).filter_by(file_path=file_path).first()
    if not upload:
        return []

    # Build base query for departments
    dept_query = db.query(Department).filter_by(level=level)

    # Filter by parent if level > 1
    if level == 2 and parent:
        parent_dept = db.query(Department).filter_by(name=parent, level=1).first()
        if parent_dept:
            dept_query = dept_query.filter_by(parent_id=parent_dept.id)
    elif level == 3 and parent:
        parent_dept = db.query(Department).filter_by(name=parent, level=2).first()
        if parent_dept:
            dept_query = dept_query.filter_by(parent_id=parent_dept.id)

    departments = dept_query.all()

    result = []
    for dept in departments:
        # Determine which department field to use based on level
        dept_field_map = {
            1: Employee.department_id,
            2: Employee.level2_department_id,
            3: Employee.level3_department_id
        }
        dept_field = dept_field_map.get(level, Employee.department_id)

        # Single query for travel costs with conditional aggregation
        cost_result = db.query(
            func.sum(TravelExpense.amount).label('total_cost'),
            func.sum(case((TravelExpense.expense_type == 'flight', TravelExpense.amount), else_=0)).label('flight_cost'),
            func.sum(case((TravelExpense.expense_type == 'hotel', TravelExpense.amount), else_=0)).label('hotel_cost'),
            func.sum(case((TravelExpense.expense_type == 'train', TravelExpense.amount), else_=0)).label('train_cost')
        ).join(Employee, TravelExpense.employee_id == Employee.id).filter(
            dept_field == dept.id,
            TravelExpense.upload_id == upload.id
        ).first()

        # Single query for average work hours
        avg_hours = db.query(func.avg(AttendanceRecord.work_hours)).join(
            Employee, AttendanceRecord.employee_id == Employee.id
        ).filter(
            dept_field == dept.id,
            AttendanceRecord.upload_id == upload.id,
            AttendanceRecord.status == '上班',
            AttendanceRecord.work_hours.isnot(None),
            AttendanceRecord.work_hours != 0
        ).scalar() or 0

        # Count employees at this specific department level
        if level == 1:
            person_count = db.query(func.count(Employee.id)).filter(
                Employee.department_id == dept.id
            ).scalar() or 0
        elif level == 2:
            person_count = db.query(func.count(Employee.id)).filter(
                Employee.level2_department_id == dept.id
            ).scalar() or 0
        else:
            person_count = db.query(func.count(Employee.id)).filter(
                Employee.level3_department_id == dept.id
            ).scalar() or 0

        result.append({
            'name': dept.name,
            'level': level,
            'parent': parent,
            'person_count': person_count,
            'total_cost': float(cost_result.total_cost or 0),
            'flight_cost': float(cost_result.flight_cost or 0),
            'hotel_cost': float(cost_result.hotel_cost or 0),
            'train_cost': float(cost_result.train_cost or 0),
            'avg_work_hours': round(float(avg_hours), 2)
        })

    # Sort by cost descending
    result.sort(key=lambda x: x['total_cost'], reverse=True)
    return result


def get_department_detail_metrics(
    db: Session,
    file_path: str,
    department_name: str,
    level: int = 3
) -> dict:
    """Get 15 detailed metrics for a specific department using optimized SQL."""
    upload = db.query(Upload).filter_by(file_path=file_path).first()
    if not upload:
        return {}

    dept = db.query(Department).filter_by(name=department_name, level=level).first()
    if not dept:
        return {}

    # Determine which department field to use based on level
    dept_field_map = {
        1: Employee.department_id,
        2: Employee.level2_department_id,
        3: Employee.level3_department_id
    }
    dept_field = dept_field_map.get(level, Employee.department_id)

    # Get parent department
    parent_dept = None
    if dept.parent_id:
        parent = db.query(Department).get(dept.parent_id)
        if parent:
            parent_dept = parent.name

    # Query 1: Attendance status distribution
    attendance_dist = db.query(
        AttendanceRecord.status,
        func.count(AttendanceRecord.id).label('count')
    ).join(Employee, AttendanceRecord.employee_id == Employee.id).filter(
        dept_field == dept.id,
        AttendanceRecord.upload_id == upload.id
    ).group_by(AttendanceRecord.status).all()

    attendance_days_distribution = {row.status: row.count for row in attendance_dist}

    # Query 2: Workday stats (attendance + avg hours)
    workday_stats = db.query(
        func.count(AttendanceRecord.id).label('workday_attendance_days'),
        func.avg(AttendanceRecord.work_hours).label('avg_work_hours')
    ).join(Employee, AttendanceRecord.employee_id == Employee.id).filter(
        dept_field == dept.id,
        AttendanceRecord.upload_id == upload.id,
        AttendanceRecord.status == '上班',
        AttendanceRecord.work_hours != 0
    ).first()

    workday_attendance_days = workday_stats.workday_attendance_days or 0
    avg_work_hours = float(workday_stats.avg_work_hours or 0)

    # Query 3: Other days (travel, leave, weekend work) using FILTER clause
    other_days = db.query(
        func.count(AttendanceRecord.id).label('travel_days'),
        func.sum(case((AttendanceRecord.status == '请假', 1), else_=0)).label('leave_days'),
        func.sum(case((AttendanceRecord.status == '公休日上班', 1), else_=0)).label('weekend_work_days')
    ).join(Employee, AttendanceRecord.employee_id == Employee.id).filter(
        dept_field == dept.id,
        AttendanceRecord.upload_id == upload.id
    ).first()

    travel_days = other_days.travel_days or 0
    leave_days = other_days.leave_days or 0
    weekend_work_days = other_days.weekend_work_days or 0

    # Query 4: Anomaly count (Type A conflicts)
    anomaly_count = db.query(func.count(Anomaly.id)).join(
        Employee, Anomaly.employee_id == Employee.id
    ).filter(
        dept_field == dept.id,
        Anomaly.upload_id == upload.id,
        Anomaly.anomaly_type == 'A'
    ).scalar() or 0

    # Query 5: Weekend attendance，按"公休日上班"计数以与考勤分布对齐
    weekend_attendance = weekend_work_days

    # Query 6: Late after 19:30 count
    late_after_1930_count = db.query(func.count(func.distinct(Employee.id))).join(
        AttendanceRecord, AttendanceRecord.employee_id == Employee.id
    ).filter(
        dept_field == dept.id,
        AttendanceRecord.upload_id == upload.id,
        AttendanceRecord.is_late_after_1930 == True
    ).scalar() or 0

    # Query 7: All rankings in single CTE query (most efficient approach)
    # We need to dynamically build the WHERE clause based on the department level
    where_clause = ""
    if level == 1:
        where_clause = "e.department_id = :dept_id"
    elif level == 2:
        where_clause = "e.level2_department_id = :dept_id"
    else:
        where_clause = "e.level3_department_id = :dept_id"

    rankings_query = text(f"""
    WITH travel_counts AS (
        SELECT
            e.name,
            COUNT(CASE WHEN a.status = '出差' THEN 1 END) as travel_days,
            RANK() OVER (ORDER BY COUNT(CASE WHEN a.status = '出差' THEN 1 END) DESC) as travel_rank
        FROM fact_attendance a
        JOIN dim_employee e ON a.employee_id = e.id
        WHERE {where_clause} AND a.upload_id = :upload_id
        GROUP BY e.name
    ),
    anomaly_counts AS (
        SELECT
            e.name,
            COUNT(*) as anomaly_count,
            RANK() OVER (ORDER BY COUNT(*) DESC) as anomaly_rank
        FROM anomalies an
        JOIN dim_employee e ON an.employee_id = e.id
        WHERE {where_clause} AND an.upload_id = :upload_id AND an.anomaly_type = 'A'
        GROUP BY e.name
    ),
    avg_hours_by_person AS (
        SELECT
            e.name,
            AVG(a.work_hours) as avg_hours,
            RANK() OVER (ORDER BY AVG(a.work_hours) DESC) as hours_rank
        FROM fact_attendance a
        JOIN dim_employee e ON a.employee_id = e.id
        WHERE {where_clause} AND a.upload_id = :upload_id
              AND a.status = '上班' AND a.work_hours IS NOT NULL AND a.work_hours != 0
        GROUP BY e.name
    ),
    latest_checkout AS (
        SELECT
            e.name,
            a.latest_punch_time,
            RANK() OVER (ORDER BY a.latest_punch_time DESC) as checkout_rank
        FROM fact_attendance a
        JOIN dim_employee e ON a.employee_id = e.id
        WHERE {where_clause} AND a.upload_id = :upload_id
              AND a.latest_punch_time IS NOT NULL
        GROUP BY e.name, a.latest_punch_time
    )
    SELECT
        (SELECT JSON_GROUP_ARRAY(json_object('name', name, 'value', travel_days, 'detail', travel_days || '天'))
         FROM travel_counts WHERE travel_rank <= 10) as travel_ranking,
        (SELECT JSON_GROUP_ARRAY(json_object('name', name, 'value', anomaly_count, 'detail', anomaly_count || '次'))
         FROM anomaly_counts WHERE anomaly_rank <= 10) as anomaly_ranking,
        (SELECT JSON_GROUP_ARRAY(json_object('name', name, 'value', ROUND(avg_hours, 2), 'detail', ROUND(avg_hours, 2) || '小时'))
         FROM avg_hours_by_person WHERE hours_rank <= 10) as longest_hours_ranking,
        (SELECT JSON_GROUP_ARRAY(json_object('name', name, 'value', 0, 'detail', latest_punch_time))
         FROM latest_checkout WHERE checkout_rank <= 10) as latest_checkout_ranking
    """)

    result = db.execute(rankings_query, {'dept_id': dept.id, 'upload_id': upload.id}).first()

    travel_ranking = json.loads(result.travel_ranking or '[]')
    anomaly_ranking = json.loads(result.anomaly_ranking or '[]')
    longest_hours_ranking = json.loads(result.longest_hours_ranking or '[]')
    latest_checkout_ranking = json.loads(result.latest_checkout_ranking or '[]')

    return {
        'department_name': department_name,
        'department_level': f'{level}级部门',
        'parent_department': parent_dept,
        'attendance_days_distribution': attendance_days_distribution,
        'weekend_work_days': weekend_work_days,
        'workday_attendance_days': workday_attendance_days,
        'avg_work_hours': round(avg_work_hours, 2),
        'travel_days': travel_days,
        'leave_days': leave_days,
        'anomaly_days': anomaly_count,
        'late_after_1930_count': late_after_1930_count,
        'weekend_attendance_count': weekend_attendance,
        'travel_ranking': travel_ranking,
        'anomaly_ranking': anomaly_ranking,
        'latest_checkout_ranking': latest_checkout_ranking,
        'longest_hours_ranking': longest_hours_ranking
    }


def get_level1_department_statistics(
    db: Session,
    file_path: str,
    level1_name: str
) -> dict:
    """Get aggregated statistics for level 1 department."""
    upload = db.query(Upload).filter_by(file_path=file_path).first()
    if not upload:
        return {}

    level1_dept = db.query(Department).filter_by(name=level1_name, level=1).first()
    if not level1_dept:
        return {}

    # Get all level 2 departments
    level2_depts = db.query(Department).filter_by(level=2, parent_id=level1_dept.id).all()
    dept_ids = tuple(d.id for d in level2_depts)

    if not dept_ids:
        return {}

    # Query 1: Total travel cost
    total_cost = db.query(func.sum(TravelExpense.amount)).join(
        Employee, TravelExpense.employee_id == Employee.id
    ).filter(
        Employee.level2_department_id.in_(dept_ids),
        TravelExpense.upload_id == upload.id
    ).scalar() or 0

    # Query 2: Attendance distribution
    attendance_dist = db.query(
        AttendanceRecord.status,
        func.count(AttendanceRecord.id).label('count')
    ).join(Employee, AttendanceRecord.employee_id == Employee.id).filter(
        Employee.level2_department_id.in_(dept_ids),
        AttendanceRecord.upload_id == upload.id
    ).group_by(AttendanceRecord.status).all()

    attendance_days_distribution = {row.status: row.count for row in attendance_dist}

    # Query 3: Travel ranking (Top 10)
    travel_ranking_query = text("""
    SELECT e.name, COUNT(CASE WHEN a.status = '出差' THEN 1 END) as travel_days
    FROM fact_attendance a
    JOIN dim_employee e ON a.employee_id = e.id
    WHERE e.level2_department_id IN :dept_ids AND a.upload_id = :upload_id
    GROUP BY e.name
    ORDER BY travel_days DESC
    LIMIT 10
    """).bindparams(bindparam('dept_ids', expanding=True))

    travel_ranking = [
        {'name': row.name, 'value': row.travel_days, 'detail': f'{row.travel_days}天'}
        for row in db.execute(travel_ranking_query, {'dept_ids': dept_ids, 'upload_id': upload.id})
    ]

    # Query 4: Average hours ranking (Top 10)
    hours_ranking_query = text("""
    SELECT e.name, AVG(a.work_hours) as avg_hours
    FROM fact_attendance a
    JOIN dim_employee e ON a.employee_id = e.id
    WHERE e.level2_department_id IN :dept_ids AND a.upload_id = :upload_id
          AND a.status = '上班' AND a.work_hours IS NOT NULL AND a.work_hours != 0
    GROUP BY e.name
    ORDER BY avg_hours DESC
    LIMIT 10
    """).bindparams(bindparam('dept_ids', expanding=True))

    avg_hours_ranking = [
        {'name': row.name, 'value': round(float(row.avg_hours), 2), 'detail': f'{row.avg_hours:.2f}小时'}
        for row in db.execute(hours_ranking_query, {'dept_ids': dept_ids, 'upload_id': upload.id})
    ]

    # Query 5: Level 2 department stats (batch query with GROUP BY)
    level2_stats_query = text("""
    SELECT
        d.name as name,
        COUNT(DISTINCT e.id) as person_count,
        AVG(CASE WHEN a.status = '上班' AND a.work_hours IS NOT NULL AND a.work_hours != 0 THEN a.work_hours END) as avg_work_hours,
        COUNT(CASE WHEN a.status = '上班' THEN 1 END) as workday_attendance_days,
        COUNT(CASE WHEN a.status = '公休日上班' THEN 1 END) as weekend_work_days,
        COUNT(CASE WHEN a.status = '出差' THEN 1 END) as travel_days,
        SUM(CASE WHEN a.status = '请假' THEN 1 ELSE 0 END) as leave_days,
        COUNT(CASE WHEN COALESCE(TRIM(a.status), '') IN ('', '未知', 'nan', 'None') THEN 1 END) as anomaly_days,
        COUNT(DISTINCT CASE WHEN a.is_late_after_1930 = 1 THEN e.id END) as late_after_1930_count,
        COUNT(CASE WHEN a.status = '公休日上班' THEN 1 END) as weekend_attendance_count,
        COALESCE(SUM(t.amount), 0) as total_cost
    FROM dim_department d
    JOIN dim_employee e ON e.level2_department_id = d.id
    LEFT JOIN fact_attendance a ON a.employee_id = e.id AND a.upload_id = :upload_id
    LEFT JOIN fact_travel_expense t ON t.employee_id = e.id AND t.upload_id = :upload_id
    WHERE d.id IN :dept_ids
    GROUP BY d.id
    ORDER BY total_cost DESC
    """).bindparams(bindparam('dept_ids', expanding=True))

    level2_department_stats = [
        {
            'name': row.name,
            'person_count': row.person_count or 0,
            'avg_work_hours': round(float(row.avg_work_hours or 0), 2),
            'workday_attendance_days': row.workday_attendance_days or 0,
            'weekend_work_days': row.weekend_work_days or 0,
            'weekend_attendance_count': row.weekend_attendance_count or 0,
            'travel_days': row.travel_days or 0,
            'leave_days': row.leave_days or 0,
            'anomaly_days': row.anomaly_days or 0,
            'late_after_1930_count': row.late_after_1930_count or 0,
            'total_cost': round(float(row.total_cost or 0), 2)
        }
        for row in db.execute(level2_stats_query, {'dept_ids': dept_ids, 'upload_id': upload.id})
    ]

    return {
        'department_name': level1_name,
        'total_travel_cost': round(float(total_cost), 2),
        'attendance_days_distribution': attendance_days_distribution,
        'travel_ranking': travel_ranking,
        'avg_hours_ranking': avg_hours_ranking,
        'level2_department_stats': level2_department_stats
    }


def get_all_uploads_for_month(db: Session, month: str) -> List[int]:
    """Get all upload_ids that have data for the given month."""
    ranges = _month_ranges([month])
    return get_all_uploads_for_months(db, [month]) if ranges else []


def get_all_uploads_for_months(db: Session, months: List[str]) -> List[int]:
    """Get all upload_ids that have data for any of the given months."""
    ranges = _month_ranges(months)
    if not ranges:
        return []

    date_filter = _date_range_filter(TravelExpense.date, ranges)
    travel_upload_ids = db.query(TravelExpense.upload_id).filter(
        date_filter
    ).distinct().all()

    attendance_filter = _date_range_filter(AttendanceRecord.date, ranges)
    attendance_upload_ids = db.query(AttendanceRecord.upload_id).filter(
        attendance_filter
    ).distinct().all()

    all_upload_ids = set(u[0] for u in travel_upload_ids)
    all_upload_ids.update(u[0] for u in attendance_upload_ids)

    return list(all_upload_ids)


def get_dashboard_summary_by_month(db: Session, month: str) -> dict:
    """Get dashboard summary aggregated from ALL files for the given month."""
    return get_dashboard_summary(db, [month])


def get_dashboard_summary(db: Session, months: List[str]) -> dict:
    """Get dashboard summary aggregated from ALL files for given months (multi-month supported)."""
    ranges = _month_ranges(months)
    upload_ids = get_all_uploads_for_months(db, months)

    if not ranges or not upload_ids:
        return {
            'total_cost': 0,
            'total_orders': 0,
            'over_standard_count': 0,
            'avg_work_hours': 0,
            'holiday_avg_work_hours': 0,
            'work_hours_count': 0,
            'holiday_work_hours_count': 0
        }

    date_filter_travel = _date_range_filter(TravelExpense.date, ranges)
    date_filter_attendance = _date_range_filter(AttendanceRecord.date, ranges)

    total_cost_result = db.query(
        func.sum(TravelExpense.amount).label('total_cost'),
        func.count(TravelExpense.id).label('total_orders'),
        func.sum(case((TravelExpense.is_over_standard == True, 1), else_=0)).label('over_standard_count')
    ).filter(
        TravelExpense.upload_id.in_(upload_ids),
        date_filter_travel
    ).first()

    avg_hours_result = db.query(
        func.avg(AttendanceRecord.work_hours).label('avg_hours'),
        func.count(AttendanceRecord.id).label('count')
    ).filter(
        AttendanceRecord.upload_id.in_(upload_ids),
        date_filter_attendance,
        AttendanceRecord.work_hours != 0
    ).first()

    holiday_avg_hours_result = db.query(
        func.avg(case((AttendanceRecord.status.like('%公休日上班%'), AttendanceRecord.work_hours), else_=None)).label('holiday_avg_hours'),
        func.count(case((AttendanceRecord.status.like('%公休日上班%'), 1), else_=None)).label('holiday_count')
    ).filter(
        AttendanceRecord.upload_id.in_(upload_ids),
        date_filter_attendance,
        AttendanceRecord.work_hours != 0
    ).first()

    return {
        'total_cost': float(total_cost_result.total_cost or 0),
        'total_orders': total_cost_result.total_orders or 0,
        'over_standard_count': total_cost_result.over_standard_count or 0,
        'avg_work_hours': float(avg_hours_result.avg_hours or 0),
        'holiday_avg_work_hours': float(holiday_avg_hours_result.holiday_avg_hours or 0),
        'work_hours_count': avg_hours_result.count or 0,
        'holiday_work_hours_count': holiday_avg_hours_result.holiday_count or 0
    }


def get_department_stats_by_month(db: Session, month: str, top_n: int = 15) -> List[dict]:
    """Backward-compatible single-month wrapper."""
    return get_department_stats(db, [month], top_n)


def get_department_stats(db: Session, months: List[str], top_n: int = 15) -> List[dict]:
    """Get department statistics aggregated from ALL files for the given months."""
    ranges = _month_ranges(months)
    upload_ids = get_all_uploads_for_months(db, months)

    if not ranges or not upload_ids:
        return []

    date_filter_travel = _date_range_filter(TravelExpense.date, ranges)
    date_filter_attendance = _date_range_filter(AttendanceRecord.date, ranges)

    results = db.query(
        Department.name.label('dept'),
        func.sum(TravelExpense.amount).label('cost'),
        func.count(func.distinct(TravelExpense.employee_id)).label('headcount'),
        func.sum(case((TravelExpense.expense_type == 'flight', TravelExpense.amount), else_=0)).label('flight_cost'),
        func.sum(case((TravelExpense.expense_type == 'hotel', TravelExpense.amount), else_=0)).label('hotel_cost'),
        func.sum(case((TravelExpense.expense_type == 'train', TravelExpense.amount), else_=0)).label('train_cost')
    ).join(
        Employee, TravelExpense.employee_id == Employee.id
    ).join(
        Department, Employee.department_id == Department.id
    ).filter(
        TravelExpense.upload_id.in_(upload_ids),
        date_filter_travel
    ).group_by(
        Department.id, Department.name
    ).order_by(
        func.sum(TravelExpense.amount).desc()
    ).all()

    dept_stats = []
    for row in results:
        dept_id = db.query(Department.id).filter_by(name=row.dept).first()

        attendance_query = db.query(
            func.avg(case((AttendanceRecord.status == '上班', AttendanceRecord.work_hours), else_=None)).label('avg_hours'),
            func.avg(case((AttendanceRecord.status.like('%公休日上班%'), AttendanceRecord.work_hours), else_=None)).label('holiday_avg_hours')
        ).join(
            Employee, AttendanceRecord.employee_id == Employee.id
        ).filter(
            AttendanceRecord.upload_id.in_(upload_ids),
            date_filter_attendance,
            AttendanceRecord.work_hours != 0,
            Employee.department_id == (dept_id.id if dept_id else None)
        )

        avg_hours_result = attendance_query.first()
        avg_hours = float(avg_hours_result.avg_hours or 0) if avg_hours_result else 0
        holiday_avg_hours = float(avg_hours_result.holiday_avg_hours or 0) if avg_hours_result else 0

        dept_stats.append({
          'dept': row.dept,
          'cost': round(float(row.cost or 0), 2),
          'avg_hours': round(avg_hours, 2),
          'holiday_avg_hours': round(holiday_avg_hours, 2),
          'headcount': row.headcount or 0,
          'flight_cost': round(float(row.flight_cost or 0), 2),
          'hotel_cost': round(float(row.hotel_cost or 0), 2),
          'train_cost': round(float(row.train_cost or 0), 2)
        })

    return sorted(dept_stats, key=lambda x: x['cost'], reverse=True)[:top_n]


def get_project_stats_by_month(db: Session, month: str, top_n: int = 20) -> List[dict]:
    """Backward-compatible single-month wrapper."""
    return get_project_stats(db, [month], top_n)


def get_project_stats(db: Session, months: List[str], top_n: int = 20) -> List[dict]:
    """Get project statistics aggregated from ALL files for the given months."""
    ranges = _month_ranges(months)
    upload_ids = get_all_uploads_for_months(db, months)

    if not ranges or not upload_ids:
        return []

    date_filter_travel = _date_range_filter(TravelExpense.date, ranges)

    results = db.query(
        Project.code.label('code'),
        Project.name.label('name'),
        func.sum(TravelExpense.amount).label('cost'),
        func.count(TravelExpense.id).label('order_count'),
        func.sum(case((TravelExpense.expense_type == 'flight', TravelExpense.amount), else_=0)).label('flight_cost'),
        func.sum(case((TravelExpense.expense_type == 'hotel', TravelExpense.amount), else_=0)).label('hotel_cost'),
        func.sum(case((TravelExpense.expense_type == 'train', TravelExpense.amount), else_=0)).label('train_cost'),
        func.count(func.distinct(TravelExpense.employee_id)).label('person_count')
    ).join(
        TravelExpense, TravelExpense.project_id == Project.id
    ).filter(
        TravelExpense.upload_id.in_(upload_ids),
        date_filter_travel
    ).group_by(
        Project.id, Project.code, Project.name
    ).order_by(
        func.sum(TravelExpense.amount).desc()
    ).all()

    project_list = [
        {
            'code': row.code,
            'name': row.name,
            'cost': round(float(row.cost or 0), 2),
            'order_count': row.order_count or 0,
            'flight_cost': round(float(row.flight_cost or 0), 2),
            'hotel_cost': round(float(row.hotel_cost or 0), 2),
            'train_cost': round(float(row.train_cost or 0), 2),
            'person_count': row.person_count or 0
        }
        for row in results
    ]

    return sorted(project_list, key=lambda x: x['cost'], reverse=True)[:top_n]


def get_anomalies_by_month(db: Session, month: str, limit: int = 50) -> List[dict]:
    """Backward-compatible single-month wrapper."""
    return get_anomalies(db, [month], limit)


def get_anomalies(db: Session, months: List[str], limit: int = 200) -> List[dict]:
    """Get anomalies aggregated from ALL files for the given months."""
    ranges = _month_ranges(months)
    upload_ids = get_all_uploads_for_months(db, months)

    if not ranges or not upload_ids:
        return []

    date_filter_anomaly = _date_range_filter(Anomaly.date, ranges)

    results = db.query(
        Anomaly.date.label('date'),
        Employee.name.label('name'),
        Department.name.label('dept'),
        Anomaly.anomaly_type.label('type'),
        Anomaly.attendance_status.label('status'),
        Anomaly.description.label('detail'),
        Anomaly.travel_records.label('travel_records')
    ).join(
        Employee, Anomaly.employee_id == Employee.id
    ).join(
        Department, Employee.department_id == Department.id
    ).filter(
        Anomaly.upload_id.in_(upload_ids),
        date_filter_anomaly,
        Anomaly.attendance_status == '上班'
    ).order_by(
        Anomaly.date.desc()
    ).limit(limit).all()

    return [_serialize_anomaly_row(row, '%Y/%m/%d') for row in results]


def get_total_project_count_by_month(db: Session, month: str) -> int:
    """Backward-compatible single-month wrapper."""
    return get_total_project_count(db, [month])


def get_total_project_count(db: Session, months: List[str]) -> int:
    """Get total count of distinct projects for the given months."""
    ranges = _month_ranges(months)
    upload_ids = get_all_uploads_for_months(db, months)

    if not ranges or not upload_ids:
        return 0

    date_filter_travel = _date_range_filter(TravelExpense.date, ranges)

    result = db.query(
        func.count(func.distinct(TravelExpense.project_id))
    ).filter(
        TravelExpense.upload_id.in_(upload_ids),
        date_filter_travel,
        TravelExpense.project_id.isnot(None)
    ).scalar()

    return result or 0


def get_order_breakdown_by_month(db: Session, month: str) -> dict:
    """Backward-compatible single-month wrapper."""
    return get_order_breakdown(db, [month])


def get_order_breakdown(db: Session, months: List[str]) -> dict:
    """Get order breakdown by expense type (count, not cost) for given months."""
    ranges = _month_ranges(months)
    upload_ids = get_all_uploads_for_months(db, months)

    if not ranges or not upload_ids:
        return {
            'total': 0,
            'flight': 0,
            'hotel': 0,
            'train': 0
        }

    date_filter_travel = _date_range_filter(TravelExpense.date, ranges)

    result = db.query(
        TravelExpense.expense_type.label('expense_type'),
        func.count(TravelExpense.id).label('count')
    ).filter(
        TravelExpense.upload_id.in_(upload_ids),
        date_filter_travel
    ).group_by(
        TravelExpense.expense_type
    ).all()

    breakdown = {
        'total': 0,
        'flight': 0,
        'hotel': 0,
        'train': 0
    }

    for row in result:
        if row.expense_type in breakdown:
            breakdown[row.expense_type] = row.count or 0
            breakdown['total'] += row.count or 0

    return breakdown


def get_over_standard_breakdown_by_month(db: Session, month: str) -> dict:
    """Backward-compatible single-month wrapper."""
    return get_over_standard_breakdown(db, [month])


def get_over_standard_breakdown(db: Session, months: List[str]) -> dict:
    """Get over standard order breakdown by expense type for the given months."""
    ranges = _month_ranges(months)
    upload_ids = get_all_uploads_for_months(db, months)

    if not ranges or not upload_ids:
        return {
            'total': 0,
            'flight': 0,
            'hotel': 0,
            'train': 0
        }

    date_filter_travel = _date_range_filter(TravelExpense.date, ranges)

    result = db.query(
        TravelExpense.expense_type.label('expense_type'),
        func.count(TravelExpense.id).label('count')
    ).filter(
        TravelExpense.upload_id.in_(upload_ids),
        date_filter_travel,
        TravelExpense.is_over_standard == True
    ).group_by(
        TravelExpense.expense_type
    ).all()

    breakdown = {
        'total': 0,
        'flight': 0,
        'hotel': 0,
        'train': 0
    }

    for row in result:
        if row.expense_type in breakdown:
            breakdown[row.expense_type] = row.count or 0
            breakdown['total'] += row.count or 0

    return breakdown


def get_flight_over_type_breakdown_by_month(db: Session, month: str) -> dict:
    """Backward-compatible single-month wrapper."""
    return get_flight_over_type_breakdown(db, [month])


def get_flight_over_type_breakdown(db: Session, months: List[str]) -> dict:
    """Get flight over type breakdown for the given months."""
    import re

    ranges = _month_ranges(months)
    upload_ids = get_all_uploads_for_months(db, months)

    if not ranges or not upload_ids:
        return {}

    date_filter_travel = _date_range_filter(TravelExpense.date, ranges)

    results = db.query(
        TravelExpense.over_type.label('over_type')
    ).filter(
        TravelExpense.upload_id.in_(upload_ids),
        date_filter_travel,
        TravelExpense.expense_type == 'flight',
        TravelExpense.is_over_standard == True,
        TravelExpense.over_type.isnot(None),
        TravelExpense.over_type != ''
    ).all()

    breakdown = {}
    for row in results:
        if row.over_type:
            raw = str(row.over_type)
            tokens = []

            for part in re.split(r'[;,，、/\\s]+', raw):
                cleaned = part.strip()
                if cleaned and '超' in cleaned:
                    tokens.append(cleaned)

            for keyword in ['超折扣', '超时间']:
                if keyword in raw and keyword not in tokens:
                    tokens.append(keyword)

            for token in tokens:
                breakdown[token] = breakdown.get(token, 0) + 1

    return breakdown


def get_dashboard_data(
    db: Session,
    months: Optional[List[str]] = None,
    quarter: Optional[int] = None,
    year: Optional[int] = None
) -> dict:
    """
    Get dashboard data with optional date filters.
    Supports single or multiple months via the months parameter.
    """
    if not months:
        raise ValueError("months parameter is required")

    summary = get_dashboard_summary(db, months)
    department_stats = get_department_stats(db, months, top_n=15)
    project_stats = get_project_stats(db, months, top_n=20)
    anomalies = get_anomalies(db, months, limit=200)
    total_project_count = get_total_project_count(db, months)
    order_breakdown = get_order_breakdown(db, months)
    over_standard_breakdown = get_over_standard_breakdown(db, months)
    flight_over_type_breakdown = get_flight_over_type_breakdown(db, months)

    return {
        'summary': {
            **summary,
            'anomaly_count': len(anomalies),
            'order_breakdown': order_breakdown,
            'over_standard_breakdown': over_standard_breakdown,
            'flight_over_type_breakdown': flight_over_type_breakdown,
            'total_project_count': total_project_count
        },
        'department_stats': [
            {
                'dept': item['dept'],
                'cost': item['cost'],
                'avg_hours': item['avg_hours'],
                'holiday_avg_hours': item.get('holiday_avg_hours', 0),
                'headcount': item['headcount']
            }
            for item in department_stats
        ],
        'project_top10': [
            {
                'code': item['code'],
                'name': item['name'],
                'cost': item['cost'],
                'flight_cost': item.get('flight_cost', 0),
                'hotel_cost': item.get('hotel_cost', 0),
                'train_cost': item.get('train_cost', 0)
            }
            for item in project_stats
        ],
        'anomalies': anomalies
    }



def get_department_list_from_db(
    db: Session,
    level: int,
    parent: Optional[str] = None,
    months: Optional[List[str]] = None
) -> List[dict]:
    """
    Get department list from database by level and parent.
    Supports filtering by months.

    Args:
        db: Database session
        level: Department level (1, 2, or 3)
        parent: Parent department name (required for level 2 and 3)
        months: List of months to filter (YYYY-MM format)

    Returns:
        List of department items with person_count, total_cost, avg_work_hours
    """
    if not months:
        raise ValueError("Months parameter is required")

    ranges = _month_ranges(months)
    if not ranges:
        return []

    # Get upload IDs for the given months
    upload_ids = get_all_uploads_for_months(db, months)
    if not upload_ids:
        return []

    date_filter_attendance = _date_range_filter(AttendanceRecord.date, ranges)
    date_filter_travel = _date_range_filter(TravelExpense.date, ranges)

    # Determine which department level to query
    dept_level_map = {1: 'department_id', 2: 'level2_department_id', 3: 'level3_department_id'}
    dept_id_column = dept_level_map.get(level)

    if not dept_id_column:
        raise ValueError(f"Invalid department level: {level}")

    # Build query conditions
    where_clauses = [
        AttendanceRecord.upload_id.in_(upload_ids),
        date_filter_attendance
    ]
    where_clauses = [c for c in where_clauses if c is not None]

    # Get departments with employee count
    dept_join_map = {
        1: Department.id == Employee.department_id,
        2: Department.id == Employee.level2_department_id,
        3: Department.id == Employee.level3_department_id,
    }

    # Filter by parent department if needed
    parent_filter = None
    if parent:
        parent_dept = db.query(Department).filter_by(name=parent, level=level - 1).first()
        if parent_dept:
            parent_id = parent_dept.id
            # For level 2, filter by Department.parent_id matching level 1 department
            # For level 3, filter by Department.parent_id matching level 2 department
            parent_filter = Department.parent_id == parent_id

    # Query attendance data with correct work hours calculation:
    # - avg_work_hours: only for status='上班' (workday attendance)
    # - holiday_avg_hours: only for status='公休日上班' (holiday work)
    result = db.query(
        Department.id.label('dept_id'),
        Department.name.label('name'),
        func.count(func.distinct(Employee.id)).label('person_count'),
        func.avg(case((AttendanceRecord.status == '上班', AttendanceRecord.work_hours), else_=None)).label('avg_work_hours'),
        func.avg(case((AttendanceRecord.status == '公休日上班', AttendanceRecord.work_hours), else_=None)).label('holiday_avg_hours')
    ).join(
        Employee, dept_join_map[level]
    ).join(
        AttendanceRecord, Employee.id == AttendanceRecord.employee_id
    ).filter(
        *where_clauses,
        AttendanceRecord.work_hours != 0
    )

    # Add parent filter if needed
    if parent_filter is not None:
        result = result.filter(parent_filter)

    result = result.group_by(
        Department.id, Department.name
    ).all()

    # Build a map from department id to employee ids for cost calculation
    dept_employee_map = {}
    for row in result:
        dept_id = row.dept_id
        dept_name = row.name
        
        # Get all employees belonging to this department at this level
        emp_id_col_map = {
            1: Employee.department_id,
            2: Employee.level2_department_id,
            3: Employee.level3_department_id,
        }
        
        emp_ids = db.query(Employee.id).filter(
            emp_id_col_map[level] == dept_id
        ).all()
        emp_ids = [e[0] for e in emp_ids]
        
        dept_employee_map[dept_name] = {
            'dept_id': dept_id,
            'person_count': row.person_count or 0,
            'avg_work_hours': float(row.avg_work_hours or 0),
            'holiday_avg_hours': float(row.holiday_avg_hours or 0),
            'emp_ids': emp_ids
        }

    # Get travel costs for each department using employee IDs directly
    departments = []
    for dept_name, info in dept_employee_map.items():
        emp_ids = info['emp_ids']
        
        total_cost = 0.0
        if emp_ids:
            # Query travel expenses by employee IDs directly (no need to join Department again)
            travel_where = [
                TravelExpense.upload_id.in_(upload_ids),
                TravelExpense.employee_id.in_(emp_ids)
            ]
            if date_filter_travel is not None:
                travel_where.append(date_filter_travel)

            cost_result = db.query(
                func.sum(TravelExpense.amount).label('total_cost')
            ).filter(
                *travel_where
            ).first()

            total_cost = float(cost_result.total_cost or 0) if cost_result else 0.0

        departments.append({
            'name': dept_name,
            'person_count': info['person_count'],
            'total_cost': total_cost,
            'avg_work_hours': info['avg_work_hours'],
            'holiday_avg_work_hours': info['holiday_avg_hours']
        })

    # Sort by total_cost descending
    departments.sort(key=lambda x: x['total_cost'], reverse=True)

    return departments


def get_department_details_from_db(
    db: Session,
    department_name: str,
    level: int = 3,
    months: Optional[List[str]] = None
) -> Optional[dict]:
    """
    Get detailed metrics for a specific department from database.

    Args:
        db: Database session
        department_name: Department name
        level: Department level (1, 2, or 3)
        months: List of months to filter (YYYY-MM format)

    Returns:
        Department detail metrics dict or None if not found
    """
    if not months:
        raise ValueError("Months parameter is required")

    ranges = _month_ranges(months)
    if not ranges:
        return None

    # Get upload IDs for the given months
    upload_ids = get_all_uploads_for_months(db, months)
    if not upload_ids:
        return None

    date_filter_attendance = _date_range_filter(AttendanceRecord.date, ranges)
    date_filter_travel = _date_range_filter(TravelExpense.date, ranges)

    # Get the department (filter by level to ensure correct match)
    dept = db.query(Department).filter_by(name=department_name, level=level).first()
    if not dept:
        # Fallback: try without level filter for backward compatibility
        dept = db.query(Department).filter_by(name=department_name).first()
        if not dept:
            return None

    # Build query conditions based on department level
    dept_join_map = {
        1: Department.id == Employee.department_id,
        2: Department.id == Employee.level2_department_id,
        3: Department.id == Employee.level3_department_id,
    }

    # Resolve parent department name for display (only meaningful for level 2/3)
    parent_department_name = None
    if dept.parent_id:
        parent_dept = db.query(Department).filter(Department.id == dept.parent_id).first()
        if parent_dept:
            parent_department_name = parent_dept.name

    # Get employee IDs for this department at this level (for travel cost query)
    emp_id_col_map = {
        1: Employee.department_id,
        2: Employee.level2_department_id,
        3: Employee.level3_department_id,
    }
    dept_emp_ids = db.query(Employee.id).filter(
        emp_id_col_map[level] == dept.id
    ).all()
    dept_emp_ids = [e[0] for e in dept_emp_ids]

    where_clauses = [
        Department.name == department_name,
        AttendanceRecord.upload_id.in_(upload_ids),
        date_filter_attendance
    ]
    where_clauses = [c for c in where_clauses if c is not None]

    # Get basic statistics with correct work hours calculation:
    # - avg_work_hours: only for status='上班' (workday attendance)
    result = db.query(
        func.count(func.distinct(Employee.id)).label('person_count'),
        func.avg(case((AttendanceRecord.status == '上班', AttendanceRecord.work_hours), else_=None)).label('avg_work_hours'),
        func.count(AttendanceRecord.id).label('total_attendance_days')
    ).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).join(
        Department, dept_join_map[level]
    ).filter(
        and_(*where_clauses),
        AttendanceRecord.work_hours != 0
    ).first()

    if not result:
        return None

    # Get workday/weekend statistics
    workday_where = list(where_clauses) + [
        func.extract('dow', AttendanceRecord.date).in_([0, 1, 2, 3, 4])  # Monday=0 in SQLite
    ]

    workday_attendance = db.query(func.count(AttendanceRecord.id)).select_from(
        AttendanceRecord
    ).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).join(
        Department, dept_join_map[level]
    ).filter(and_(*workday_where)).scalar() or 0

    weekend_work_days = 0
    weekend_attendance_count = 0

    # Get holiday average work hours (公休日上班) - use exact match
    holiday_avg_work_hours = db.query(
        func.avg(AttendanceRecord.work_hours)
    ).select_from(
        AttendanceRecord
    ).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).join(
        Department, dept_join_map[level]
    ).filter(
        Department.name == department_name,
        AttendanceRecord.status == '公休日上班',
        AttendanceRecord.upload_id.in_(upload_ids),
        date_filter_attendance if date_filter_attendance is not None else True,
        AttendanceRecord.work_hours.isnot(None),
        AttendanceRecord.work_hours != 0
    ).scalar() or 0

    # Get late after 19:30 count
    late_count = db.query(func.count(func.distinct(Employee.id))).select_from(
        AttendanceRecord
    ).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).join(
        Department, dept_join_map[level]
    ).filter(
        Department.name == department_name,
        AttendanceRecord.is_late_after_1930 == True,
        AttendanceRecord.upload_id.in_(upload_ids),
        date_filter_attendance if date_filter_attendance is not None else True
    ).scalar() or 0

    # Get travel cost using employee IDs directly (not through Department JOIN)
    travel_cost = 0
    travel_days = 0
    if dept_emp_ids:
        travel_where = [
            TravelExpense.upload_id.in_(upload_ids),
            TravelExpense.employee_id.in_(dept_emp_ids)
        ]
        if date_filter_travel is not None:
            travel_where.append(date_filter_travel)
        
        travel_cost = db.query(func.sum(TravelExpense.amount)).filter(
            *travel_where
        ).scalar() or 0

        # Get unique travel days
        travel_days = db.query(func.count(func.distinct(func.date(TravelExpense.date)))).filter(
            *travel_where
        ).scalar() or 0

    # Get leave days (assuming status like '请假' indicates leave)
    leave_days = db.query(func.count(func.distinct(func.date(AttendanceRecord.date)))).select_from(
        AttendanceRecord
    ).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).join(
        Department, dept_join_map[level]
    ).filter(
        Department.name == department_name,
        AttendanceRecord.status.like('%请假%'),
        AttendanceRecord.upload_id.in_(upload_ids),
        date_filter_attendance if date_filter_attendance is not None else True
    ).scalar() or 0

    # Get unknown days (疑似异常)：考勤状态缺失/未知的记录数
    unknown_status_cond = _unknown_status_condition(AttendanceRecord.status)
    anomaly_days = db.query(func.count(AttendanceRecord.id)).select_from(
        AttendanceRecord
    ).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).join(
        Department, dept_join_map[level]
    ).filter(
        Department.name == department_name,
        AttendanceRecord.upload_id.in_(upload_ids),
        date_filter_attendance if date_filter_attendance is not None else True,
        unknown_status_cond
    ).scalar() or 0

    # Get attendance days distribution (person-days, strict status match)
    attendance_dist_rows = db.query(
        AttendanceRecord.status,
        func.count(AttendanceRecord.id).label('count')
    ).select_from(
        AttendanceRecord
    ).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).join(
        Department, dept_join_map[level]
    ).filter(
        Department.name == department_name,
        AttendanceRecord.upload_id.in_(upload_ids),
        date_filter_attendance if date_filter_attendance is not None else True
    ).group_by(
        AttendanceRecord.status
    ).all()

    attendance_dist = {
        (row.status or '未知'): row.count
        for row in attendance_dist_rows
    }

    # Align weekend metrics with attendance distribution ("公休日上班"为周末出勤)
    weekend_work_days = int(attendance_dist.get('公休日上班', 0))
    weekend_attendance_count = weekend_work_days

    # Get travel ranking (top 10 by travel days count)
    travel_ranking = db.query(
        Employee.name.label('name'),
        func.count(func.distinct(func.date(AttendanceRecord.date))).label('travel_days')
    ).select_from(
        AttendanceRecord
    ).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).join(
        Department, dept_join_map[level]
    ).filter(
        Department.name == department_name,
        AttendanceRecord.status == '出差',
        AttendanceRecord.upload_id.in_(upload_ids),
        date_filter_attendance if date_filter_attendance is not None else True
    ).group_by(Employee.name).order_by(
        func.count(func.distinct(func.date(AttendanceRecord.date))).desc()
    ).limit(10).all()

    travel_ranking_list = [
        {'name': r.name, 'value': int(r.travel_days or 0), 'detail': f'{r.travel_days}天'}
        for r in travel_ranking
    ]

    # Get anomaly ranking (top 10 by count)
    anomaly_ranking = db.query(
        Employee.name.label('name'),
        func.count(AttendanceRecord.id).label('value')
    ).select_from(
        AttendanceRecord
    ).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).join(
        Department, dept_join_map[level]
    ).filter(
        Department.name == department_name,
        AttendanceRecord.upload_id.in_(upload_ids),
        date_filter_attendance if date_filter_attendance is not None else True,
        unknown_status_cond
    ).group_by(Employee.name).order_by(
        func.count(AttendanceRecord.id).desc()
    ).limit(10).all()

    anomaly_ranking_list = [
        {'name': r.name, 'value': int(r.value or 0), 'detail': f'{r.value}天'}
        for r in anomaly_ranking
    ]

    # Get longest hours ranking (top 10 by average hours)
    longest_hours = db.query(
        Employee.name.label('name'),
        func.avg(AttendanceRecord.work_hours).label('avg_hours')
    ).select_from(
        AttendanceRecord
    ).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).join(
        Department, dept_join_map[level]
    ).filter(
        Department.name == department_name,
        AttendanceRecord.status == '上班',
        AttendanceRecord.upload_id.in_(upload_ids),
        date_filter_attendance if date_filter_attendance is not None else True,
        AttendanceRecord.work_hours.isnot(None),
        AttendanceRecord.work_hours != 0
    ).group_by(Employee.name).order_by(
        func.avg(AttendanceRecord.work_hours).desc()
    ).limit(10).all()

    longest_hours_list = [
        {'name': r.name, 'value': float(round(r.avg_hours or 0, 2)), 'detail': f'{round(r.avg_hours or 0, 2)}小时'}
        for r in longest_hours
    ]

    # Get latest checkout ranking (top 10)
    latest_checkout = db.query(
        Employee.name.label('name'),
        func.max(AttendanceRecord.latest_punch_time).label('latest_time')
    ).select_from(
        AttendanceRecord
    ).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).join(
        Department, dept_join_map[level]
    ).filter(
        Department.name == department_name,
        AttendanceRecord.upload_id.in_(upload_ids),
        date_filter_attendance if date_filter_attendance is not None else True,
        AttendanceRecord.latest_punch_time.isnot(None)
    ).group_by(Employee.name).order_by(
        func.max(AttendanceRecord.latest_punch_time).desc()
    ).limit(10).all()

    latest_checkout_list = [
        {'name': r.name, 'value': 0, 'detail': r.latest_time if r.latest_time else ''}
        for r in latest_checkout
    ]

    return {
        'department_name': department_name,
        'department_level': f'{level}级部门',
        'parent_department': parent_department_name or '',
        'avg_work_hours': float(result.avg_work_hours or 0),
        'holiday_avg_work_hours': float(holiday_avg_work_hours or 0),
        'workday_attendance_days': workday_attendance,
        'weekend_work_days': weekend_work_days,
        'weekend_attendance_count': weekend_attendance_count,
        'late_after_1930_count': late_count,
        'total_cost': travel_cost,
        'travel_days': travel_days,
        'leave_days': leave_days,
        'anomaly_days': anomaly_days,
        'attendance_days_distribution': attendance_dist,
        'travel_ranking': travel_ranking_list,
        'anomaly_ranking': anomaly_ranking_list,
        'longest_hours_ranking': longest_hours_list,
        'latest_checkout_ranking': latest_checkout_list
    }


def get_all_projects_from_db(
    db: Session,
    months: Optional[List[str]] = None
) -> List[dict]:
    """
    Get all projects from database with optional month filtering.

    Args:
        db: Database session
        months: List of months to filter (YYYY-MM format)

    Returns:
        List of project detail dicts
    """
    if not months:
        raise ValueError("Months parameter is required")

    ranges = _month_ranges(months)
    if not ranges:
        return []

    # Get upload IDs for the given months
    upload_ids = get_all_uploads_for_months(db, months)
    if not upload_ids:
        return []

    date_filter_travel = _date_range_filter(TravelExpense.date, ranges)

    project_result = db.query(
        Project.id.label('project_id'),
        Project.code,
        Project.name,
        func.sum(TravelExpense.amount).label('total_cost'),
        func.count(TravelExpense.id).label('record_count'),
        func.sum(case((TravelExpense.expense_type == 'flight', TravelExpense.amount), else_=0)).label('flight_cost'),
        func.sum(case((TravelExpense.expense_type == 'hotel', TravelExpense.amount), else_=0)).label('hotel_cost'),
        func.sum(case((TravelExpense.expense_type == 'train', TravelExpense.amount), else_=0)).label('train_cost'),
        func.sum(case((TravelExpense.expense_type == 'flight', 1), else_=0)).label('flight_count'),
        func.sum(case((TravelExpense.expense_type == 'hotel', 1), else_=0)).label('hotel_count'),
        func.sum(case((TravelExpense.expense_type == 'train', 1), else_=0)).label('train_count'),
        func.count(func.distinct(Employee.id)).label('person_count'),
        func.min(TravelExpense.date).label('date_start'),
        func.max(TravelExpense.date).label('date_end'),
        func.sum(case((TravelExpense.is_over_standard == True, 1), else_=0)).label('over_standard_count'),
    ).join(
        TravelExpense, Project.id == TravelExpense.project_id
    ).join(
        Employee, TravelExpense.employee_id == Employee.id
    ).filter(
        TravelExpense.upload_id.in_(upload_ids),
        date_filter_travel if date_filter_travel is not None else True
    ).group_by(
        Project.id, Project.code, Project.name
    ).order_by(
        func.sum(TravelExpense.amount).desc()
    ).all()

    results = []
    for row in project_result:
        # Get person list for this project
        persons = db.query(Employee.name).join(
            TravelExpense, Employee.id == TravelExpense.employee_id
        ).filter(
            TravelExpense.project_id == row.project_id,
            TravelExpense.upload_id.in_(upload_ids),
            date_filter_travel if date_filter_travel is not None else True
        ).distinct().all()
        person_list = [p.name for p in persons]

        # Get department list for this project
        departments = db.query(Department.name).join(
            Employee, Department.id == Employee.department_id
        ).join(
            TravelExpense, Employee.id == TravelExpense.employee_id
        ).filter(
            TravelExpense.project_id == row.project_id,
            TravelExpense.upload_id.in_(upload_ids),
            date_filter_travel if date_filter_travel is not None else True
        ).distinct().all()
        department_list = [d.name for d in departments]

        results.append({
            'code': row.code,
            'name': row.name,
            'total_cost': float(row.total_cost or 0),
            'flight_cost': float(row.flight_cost or 0),
            'hotel_cost': float(row.hotel_cost or 0),
            'train_cost': float(row.train_cost or 0),
            'flight_count': int(row.flight_count or 0),
            'hotel_count': int(row.hotel_count or 0),
            'train_count': int(row.train_count or 0),
            'record_count': row.record_count or 0,
            'person_count': row.person_count or 0,
            'date_range': {
                'start': row.date_start.strftime('%Y-%m-%d') if row.date_start else '',
                'end': row.date_end.strftime('%Y-%m-%d') if row.date_end else ''
            },
            'over_standard_count': row.over_standard_count or 0,
            'person_list': person_list,
            'department_list': department_list
        })

    return results


def get_level1_department_statistics_from_db(
    db: Session,
    level1_name: str,
    months: Optional[List[str]] = None
) -> dict:
    """
    Get aggregated statistics for level 1 department from database.

    Args:
        db: Database session
        level1_name: Level 1 department name
        months: List of months to filter (YYYY-MM format)

    Returns:
        Dictionary containing aggregated statistics
    """
    if not months:
        raise ValueError("Months parameter is required")

    ranges = _month_ranges(months)
    if not ranges:
        return {}

    # Get upload IDs for the given months
    upload_ids = get_all_uploads_for_months(db, months)
    if not upload_ids:
        return {}

    date_filter_attendance = _date_range_filter(AttendanceRecord.date, ranges)
    date_filter_travel = _date_range_filter(TravelExpense.date, ranges)

    # Get the level 1 department
    level1_dept = db.query(Department).filter_by(name=level1_name, level=1).first()
    if not level1_dept:
        return {}

    # Get all level 2 departments under this level 1
    level2_depts = db.query(Department).filter_by(level=2, parent_id=level1_dept.id).all()
    level2_dept_ids = [d.id for d in level2_depts]

    if not level2_dept_ids:
        return {}

    # Query 1: Total travel cost for the level 1 department (aggregating all level 2 departments)
    total_cost = db.query(func.sum(TravelExpense.amount)).join(
        Employee, TravelExpense.employee_id == Employee.id
    ).filter(
        Employee.level2_department_id.in_(level2_dept_ids),
        TravelExpense.upload_id.in_(upload_ids),
        date_filter_travel if date_filter_travel is not None else True
    ).scalar() or 0

    # Query 2: Attendance status distribution for all level 2 departments（person-days, strict status match）
    attendance_dist = db.query(
        AttendanceRecord.status,
        func.count(AttendanceRecord.id).label('count')
    ).join(Employee, AttendanceRecord.employee_id == Employee.id).filter(
        Employee.level2_department_id.in_(level2_dept_ids),
        AttendanceRecord.upload_id.in_(upload_ids),
        date_filter_attendance if date_filter_attendance is not None else True
    ).group_by(AttendanceRecord.status).all()

    attendance_days_distribution = {row.status: row.count for row in attendance_dist}

    # Query 3: Travel ranking (Top 10 by person)
    travel_ranking = db.query(
        Employee.name.label('name'),
        func.count(func.distinct(func.date(AttendanceRecord.date))).label('travel_days')
    ).join(
        AttendanceRecord, AttendanceRecord.employee_id == Employee.id
    ).filter(
        Employee.level2_department_id.in_(level2_dept_ids),
        AttendanceRecord.upload_id.in_(upload_ids),
        AttendanceRecord.status == '出差',
        date_filter_attendance if date_filter_attendance is not None else True
    ).group_by(
        Employee.name
    ).order_by(
        func.count(func.distinct(func.date(AttendanceRecord.date))).desc()
    ).limit(10).all()

    travel_ranking = [
        {'name': row.name, 'value': int(row.travel_days or 0), 'detail': f'{row.travel_days}天'}
        for row in travel_ranking
    ]

    # Query 4: Average hours ranking (Top 10 by person)
    avg_hours_ranking = db.query(
        Employee.name.label('name'),
        func.avg(AttendanceRecord.work_hours).label('avg_hours')
    ).join(
        AttendanceRecord, AttendanceRecord.employee_id == Employee.id
    ).filter(
        Employee.level2_department_id.in_(level2_dept_ids),
        AttendanceRecord.upload_id.in_(upload_ids),
        AttendanceRecord.status == '上班',
        AttendanceRecord.work_hours.isnot(None),
        AttendanceRecord.work_hours != 0,
        date_filter_attendance if date_filter_attendance is not None else True
    ).group_by(
        Employee.name
    ).order_by(
        func.avg(AttendanceRecord.work_hours).desc()
    ).limit(10).all()

    avg_hours_ranking = [
        {'name': row.name, 'value': round(float(row.avg_hours or 0), 2), 'detail': f'{row.avg_hours:.2f}小时'}
        for row in avg_hours_ranking
    ]

    # Query 5: Level 2 department stats (batch query with GROUP BY)
    level2_stats_query = text("""
    SELECT
        d.name as name,
        COUNT(DISTINCT e.id) as person_count,
        AVG(CASE WHEN a.status = '上班' AND a.work_hours IS NOT NULL AND a.work_hours != 0 THEN a.work_hours END) as avg_work_hours,
        AVG(CASE WHEN a.status = '公休日上班' AND a.work_hours IS NOT NULL AND a.work_hours != 0 THEN a.work_hours END) as holiday_avg_work_hours,
        COUNT(DISTINCT CASE WHEN a.status = '上班' THEN DATE(a.date) END) as workday_attendance_days,
        COUNT(DISTINCT CASE WHEN a.status = '公休日上班' THEN DATE(a.date) END) as weekend_work_days,
        COUNT(CASE WHEN a.status = '公休日上班' THEN 1 END) as weekend_attendance_count,
        COUNT(DISTINCT CASE WHEN a.status = '出差' THEN DATE(a.date) END) as travel_days,
        COUNT(DISTINCT CASE WHEN a.status LIKE '%请假%' THEN DATE(a.date) END) as leave_days,
        COUNT(CASE WHEN COALESCE(TRIM(a.status), '') IN ('', '未知', 'nan', 'None') THEN 1 END) as anomaly_days,
        COUNT(DISTINCT CASE WHEN a.is_late_after_1930 = 1 THEN e.id END) as late_after_1930_count,
        COALESCE(tc.total_cost, 0) as total_cost
    FROM dim_department d
    JOIN dim_employee e ON e.level2_department_id = d.id
    LEFT JOIN fact_attendance a ON a.employee_id = e.id AND a.upload_id IN :upload_ids
    LEFT JOIN (
        SELECT e2.level2_department_id, COALESCE(SUM(t2.amount), 0) as total_cost
        FROM dim_employee e2
        JOIN fact_travel_expense t2 ON t2.employee_id = e2.id
        WHERE t2.upload_id IN :upload_ids
        GROUP BY e2.level2_department_id
    ) tc ON d.id = tc.level2_department_id
    WHERE d.id IN :dept_ids
    GROUP BY d.id, tc.total_cost
    ORDER BY total_cost DESC
    """).bindparams(bindparam('dept_ids', expanding=True), bindparam('upload_ids', expanding=True))

    level2_department_stats = [
        {
            'name': row.name,
            'person_count': row.person_count or 0,
            'avg_work_hours': round(float(row.avg_work_hours or 0), 2),
            'holiday_avg_work_hours': round(float(row.holiday_avg_work_hours or 0), 2),
            'workday_attendance_days': row.workday_attendance_days or 0,
            'weekend_work_days': row.weekend_work_days or 0,
            'weekend_attendance_count': row.weekend_attendance_count or 0,
            'travel_days': row.travel_days or 0,
            'leave_days': row.leave_days or 0,
            'anomaly_days': row.anomaly_days or 0,
            'late_after_1930_count': row.late_after_1930_count or 0,
            'total_cost': round(float(row.total_cost or 0), 2)
        }
        for row in db.execute(level2_stats_query, {'dept_ids': level2_dept_ids, 'upload_ids': upload_ids})
    ]

    return {
        'department_name': level1_name,
        'total_travel_cost': round(float(total_cost), 2),
        'attendance_days_distribution': attendance_days_distribution,
        'travel_ranking': travel_ranking,
        'avg_hours_ranking': avg_hours_ranking,
        'level2_department_stats': level2_department_stats
    }


def get_level2_department_statistics_from_db(
    db: Session,
    level2_name: str,
    months: Optional[List[str]] = None
) -> dict:
    """
    Get aggregated statistics for a level 2 department (used for level 3 view).

    Args:
        db: Database session
        level2_name: Level 2 department name
        months: List of months to filter (YYYY-MM format)

    Returns:
        Dictionary containing aggregated statistics for the level 2 department
    """
    if not months:
        raise ValueError("Months parameter is required")

    ranges = _month_ranges(months)
    if not ranges:
        return {}

    upload_ids = get_all_uploads_for_months(db, months)
    if not upload_ids:
        return {}

    date_filter_attendance = _date_range_filter(AttendanceRecord.date, ranges)
    date_filter_travel = _date_range_filter(TravelExpense.date, ranges)

    level2_dept = db.query(Department).filter_by(name=level2_name, level=2).first()
    if not level2_dept:
        return {}

    parent_department = None
    if level2_dept.parent_id:
        parent = db.query(Department).filter(Department.id == level2_dept.parent_id).first()
        parent_department = parent.name if parent else None

    # Total travel cost for this level 2 department
    travel_filters = [
        Employee.level2_department_id == level2_dept.id,
        TravelExpense.upload_id.in_(upload_ids)
    ]
    if date_filter_travel is not None:
        travel_filters.append(date_filter_travel)

    total_cost = db.query(func.sum(TravelExpense.amount)).join(
        Employee, TravelExpense.employee_id == Employee.id
    ).filter(
        *travel_filters
    ).scalar() or 0

    # Attendance distribution
    attendance_filters = [
        Employee.level2_department_id == level2_dept.id,
        AttendanceRecord.upload_id.in_(upload_ids)
    ]
    if date_filter_attendance is not None:
        attendance_filters.append(date_filter_attendance)

    attendance_dist = db.query(
        AttendanceRecord.status,
        func.count(AttendanceRecord.id).label('count')
    ).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).filter(
        *attendance_filters
    ).group_by(
        AttendanceRecord.status
    ).all()
    attendance_days_distribution = {row.status: row.count for row in attendance_dist}

    # Travel ranking (Top 10)
    travel_ranking = db.query(
        Employee.name.label('name'),
        func.count(func.distinct(func.date(AttendanceRecord.date))).label('travel_days')
    ).join(
        AttendanceRecord, AttendanceRecord.employee_id == Employee.id
    ).filter(
        Employee.level2_department_id == level2_dept.id,
        AttendanceRecord.upload_id.in_(upload_ids),
        AttendanceRecord.status == '出差',
        date_filter_attendance if date_filter_attendance is not None else True
    ).group_by(
        Employee.name
    ).order_by(
        func.count(func.distinct(func.date(AttendanceRecord.date))).desc()
    ).limit(10).all()

    travel_ranking = [
        {'name': row.name, 'value': int(row.travel_days or 0), 'detail': f'{row.travel_days}天'}
        for row in travel_ranking
    ]

    # Average hours ranking (Top 10)
    avg_hours_ranking = db.query(
        Employee.name.label('name'),
        func.avg(AttendanceRecord.work_hours).label('avg_hours')
    ).join(
        AttendanceRecord, AttendanceRecord.employee_id == Employee.id
    ).filter(
        Employee.level2_department_id == level2_dept.id,
        AttendanceRecord.upload_id.in_(upload_ids),
        AttendanceRecord.status == '上班',
        AttendanceRecord.work_hours.isnot(None),
        AttendanceRecord.work_hours != 0,
        date_filter_attendance if date_filter_attendance is not None else True
    ).group_by(
        Employee.name
    ).order_by(
        func.avg(AttendanceRecord.work_hours).desc()
    ).limit(10).all()

    avg_hours_ranking = [
        {'name': row.name, 'value': round(float(row.avg_hours or 0), 2), 'detail': f'{row.avg_hours:.2f}小时'}
        for row in avg_hours_ranking
    ]

    # Level 3 department stats under this level 2 department
    level3_depts = db.query(Department).filter_by(level=3, parent_id=level2_dept.id).all()
    level3_dept_ids = [d.id for d in level3_depts]

    level3_department_stats = []
    if level3_dept_ids:
        level3_stats_query = text("""
        SELECT
            d.name as name,
            COUNT(DISTINCT e.id) as person_count,
            AVG(CASE WHEN a.status = '上班' AND a.work_hours IS NOT NULL AND a.work_hours != 0 THEN a.work_hours END) as avg_work_hours,
            AVG(CASE WHEN a.status = '公休日上班' AND a.work_hours IS NOT NULL AND a.work_hours != 0 THEN a.work_hours END) as holiday_avg_work_hours,
            COUNT(DISTINCT CASE WHEN a.status = '上班' THEN DATE(a.date) END) as workday_attendance_days,
            COUNT(DISTINCT CASE WHEN a.status = '公休日上班' THEN DATE(a.date) END) as weekend_work_days,
            COUNT(CASE WHEN a.status = '公休日上班' THEN 1 END) as weekend_attendance_count,
            COUNT(DISTINCT CASE WHEN a.status = '出差' THEN DATE(a.date) END) as travel_days,
            COUNT(DISTINCT CASE WHEN a.status LIKE '%请假%' THEN DATE(a.date) END) as leave_days,
            COUNT(CASE WHEN COALESCE(TRIM(a.status), '') IN ('', '未知', 'nan', 'None') THEN 1 END) as anomaly_days,
            COUNT(DISTINCT CASE WHEN a.is_late_after_1930 = 1 THEN e.id END) as late_after_1930_count,
            COALESCE(tc.total_cost, 0) as total_cost
        FROM dim_department d
        JOIN dim_employee e ON e.level3_department_id = d.id
        LEFT JOIN fact_attendance a ON a.employee_id = e.id AND a.upload_id IN :upload_ids
        LEFT JOIN (
            SELECT e2.level3_department_id, COALESCE(SUM(t2.amount), 0) as total_cost
            FROM dim_employee e2
            JOIN fact_travel_expense t2 ON t2.employee_id = e2.id
            WHERE t2.upload_id IN :upload_ids
            GROUP BY e2.level3_department_id
        ) tc ON d.id = tc.level3_department_id
        WHERE d.id IN :dept_ids
        GROUP BY d.id, tc.total_cost
        ORDER BY total_cost DESC
        """).bindparams(bindparam('dept_ids', expanding=True), bindparam('upload_ids', expanding=True))

        level3_department_stats = [
            {
                'name': row.name,
                'person_count': row.person_count or 0,
                'avg_work_hours': round(float(row.avg_work_hours or 0), 2),
                'holiday_avg_work_hours': round(float(row.holiday_avg_work_hours or 0), 2),
                'workday_attendance_days': row.workday_attendance_days or 0,
                'weekend_work_days': row.weekend_work_days or 0,
                'weekend_attendance_count': row.weekend_attendance_count or 0,
                'travel_days': row.travel_days or 0,
                'leave_days': row.leave_days or 0,
                'anomaly_days': row.anomaly_days or 0,
                'late_after_1930_count': row.late_after_1930_count or 0,
                'total_cost': round(float(row.total_cost or 0), 2)
            }
            for row in db.execute(level3_stats_query, {'dept_ids': level3_dept_ids, 'upload_ids': upload_ids})
        ]

    return {
        'department_name': level2_name,
        'parent_department': parent_department,
        'total_travel_cost': round(float(total_cost), 2),
        'attendance_days_distribution': attendance_days_distribution,
        'travel_ranking': travel_ranking,
        'avg_hours_ranking': avg_hours_ranking,
        'level3_department_stats': level3_department_stats
    }


def get_project_orders_from_db(
    db: Session,
    project_code: str,
    months: Optional[List[str]] = None
) -> List[dict]:
    """
    Get all order records for a specific project from database.

    Args:
        db: Database session
        project_code: Project code
        months: List of months to filter (YYYY-MM format)

    Returns:
        List of order record dicts
    """
    if not months:
        raise ValueError("Months parameter is required")

    ranges = _month_ranges(months)
    if not ranges:
        return []

    # Get upload IDs for the given months
    upload_ids = get_all_uploads_for_months(db, months)
    if not upload_ids:
        return []

    date_filter_travel = _date_range_filter(TravelExpense.date, ranges)

    result = db.query(
        TravelExpense.id.label('id'),
        Project.code.label('project_code'),
        Project.name.label('project_name'),
        Employee.name.label('person'),
        Department.name.label('department'),
        TravelExpense.expense_type.label('type'),
        TravelExpense.amount.label('amount'),
        TravelExpense.date.label('date'),
        TravelExpense.is_over_standard.label('is_over_standard'),
        TravelExpense.over_type.label('over_type'),
        TravelExpense.advance_days.label('advance_days'),
    ).join(
        Project, TravelExpense.project_id == Project.id
    ).join(
        Employee, TravelExpense.employee_id == Employee.id
    ).join(
        Department, Employee.department_id == Department.id
    ).filter(
        TravelExpense.upload_id.in_(upload_ids),
        Project.code == project_code,
        date_filter_travel if date_filter_travel is not None else True
    ).order_by(
        TravelExpense.date.desc()
    ).all()

    records = []
    for row in result:
        records.append({
            'id': str(row.id),
            'project_code': row.project_code,
            'project_name': row.project_name,
            'person': row.person,
            'department': row.department,
            'type': row.type,
            'amount': float(row.amount),
            'date': row.date.strftime('%Y-%m-%d') if row.date else '',
            'is_over_standard': bool(row.is_over_standard),
            'over_type': row.over_type or '',
            'advance_days': row.advance_days
        })

    return records


def delete_month_data(db: Session, month: str) -> dict:
    """
    Delete all data for a specific month from the database.

    This deletes:
    - Attendance records for the month
    - Travel expenses for the month
    - Anomalies for the month
    - The corresponding Upload records if they only contain data for this month

    Args:
        db: Database session
        month: Month in 'YYYY-MM' format

    Returns:
        dict: Statistics about what was deleted
    """
    import os
    from pathlib import Path

    # Get all uploads that contain data for this month from any table
    # We need to check both attendance and travel expense tables
    attendance_uploads = db.query(Upload.id).join(
        AttendanceRecord, Upload.id == AttendanceRecord.upload_id
    ).filter(
        text(f"strftime('%Y-%m', fact_attendance.date) = :month")
    ).params(month=month).distinct().all()

    travel_uploads = db.query(Upload.id).join(
        TravelExpense, Upload.id == TravelExpense.upload_id
    ).filter(
        text(f"strftime('%Y-%m', fact_travel_expense.date) = :month")
    ).params(month=month).distinct().all()

    # Combine upload IDs from both sources using set to avoid duplicates
    upload_ids_set = set()
    upload_ids_set.update([u.id for u in attendance_uploads])
    upload_ids_set.update([u.id for u in travel_uploads])
    upload_ids = list(upload_ids_set)

    # Get the full Upload objects for later use
    uploads_with_month = db.query(Upload).filter(Upload.id.in_(upload_ids)).all()

    if not upload_ids:
        return {
            'success': True,
            'deleted_uploads': [],
            'deleted_attendance': 0,
            'deleted_travel': 0,
            'deleted_anomalies': 0,
            'deleted_files': []
        }

    # Delete attendance records for this month
    attendance_deleted = db.query(AttendanceRecord).filter(
        AttendanceRecord.upload_id.in_(upload_ids),
        text(f"strftime('%Y-%m', fact_attendance.date) = :month")
    ).params(month=month).delete(synchronize_session=False)

    # Delete travel expenses for this month
    travel_deleted = db.query(TravelExpense).filter(
        TravelExpense.upload_id.in_(upload_ids),
        text(f"strftime('%Y-%m', fact_travel_expense.date) = :month")
    ).params(month=month).delete(synchronize_session=False)

    # Delete anomalies for this month
    anomalies_deleted = db.query(Anomaly).filter(
        Anomaly.upload_id.in_(upload_ids),
        text(f"strftime('%Y-%m', anomalies.date) = :month")
    ).params(month=month).delete(synchronize_session=False)

    # Check which uploads now have no data and delete them along with their files
    deleted_uploads = []
    deleted_files = []

    for upload in uploads_with_month:
        # Check if this upload has any remaining data
        has_attendance = db.query(AttendanceRecord).filter_by(upload_id=upload.id).first()
        has_travel = db.query(TravelExpense).filter_by(upload_id=upload.id).first()
        has_anomalies = db.query(Anomaly).filter_by(upload_id=upload.id).first()

        if not (has_attendance or has_travel or has_anomalies):
            # Delete the upload record
            deleted_uploads.append(upload.file_path)
            db.delete(upload)

            # Delete the Excel file
            file_path = Path(upload.file_path)
            if file_path.exists():
                try:
                    os.remove(file_path)
                    deleted_files.append(str(file_path))
                except Exception as e:
                    logger.warning(f"Failed to delete file {file_path}: {e}")

    db.commit()

    return {
        'success': True,
        'deleted_uploads': deleted_uploads,
        'deleted_attendance': attendance_deleted,
        'deleted_travel': travel_deleted,
        'deleted_anomalies': anomalies_deleted,
        'deleted_files': deleted_files
    }
