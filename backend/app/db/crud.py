"""CRUD operations for database access."""
import hashlib
import json
from datetime import datetime
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
    if level3_name and not (isinstance(level3_name, float) and pd.isna(level3_name)):
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


def get_or_create_employee(db: Session, name: str, level1_id: int, level2_id: Optional[int] = None, level3_id: Optional[int] = None) -> int:
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
    else:
        employee.department_id = level1_id
        if level2_id and level2_id > 0:
            employee.level2_department_id = level2_id
        else:
            employee.level2_department_id = None
        if level3_id and level3_id > 0:
            employee.level3_department_id = level3_id
        else:
            employee.level3_department_id = None
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
        latest_punch_time = None
        punch_time = row.get('最晚打卡时间')
        if pd.notna(punch_time) and isinstance(punch_time, str) and punch_time.strip():
            latest_punch_time = punch_time.strip()

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

        emp_id = get_or_create_employee(db, name, level1_id, level2_id, level3_id)

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

        records.append({
            'upload_id': upload_id,
            'date': travel_date,
            'employee_id': emp_id,
            'project_id': proj_id,
            'expense_type': mapped_type,
            'amount': float(row.get('授信金额', 0)) if pd.notna(row.get('授信金额')) else 0.0,
            'order_id': str(row.get('订单号', '')) if pd.notna(row.get('订单号')) else '',
            'is_over_standard': bool(row.get('是否超标') == '是'),
            'over_type': str(row.get('超标类型', '')) if pd.notna(row.get('超标类型')) else '',
            'advance_days': int(row.get('提前预定天数')) if pd.notna(row.get('提前预定天数')) else None
        })

    db.bulk_insert_mappings(TravelExpense, records)
    db.flush()
    return len(records)


def batch_insert_anomalies(db: Session, upload_id: int, anomalies: List[dict]) -> int:
    """Batch insert anomaly records."""
    records = []
    for anomaly in anomalies:
        dept_name = anomaly.get('dept', '未知部门')
        level1_id = get_or_create_department(db, dept_name, level=1, parent_id=None)
        emp_id = get_or_create_employee(db, anomaly['name'], level1_id)
        records.append({
            'upload_id': upload_id,
            'date': pd.to_datetime(anomaly['date']),
            'employee_id': emp_id,
            'anomaly_type': anomaly.get('type', 'A'),
            'attendance_status': anomaly.get('attendance_status', '上班'),
            'travel_records': json.dumps(anomaly.get('travel_records', [])),
            'description': anomaly.get('detail', '')
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
    ).filter(and_(*attendance_where)).first()

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
        Anomaly.description.label('detail'),
    ).join(
        Employee, Anomaly.employee_id == Employee.id
    ).join(
        Department, Employee.department_id == Department.id
    ).filter(and_(*where_clauses)).order_by(
        Anomaly.date.desc()
    ).limit(limit).all()

    return [
        {
            'date': row.date.strftime('%Y-%m-%d'),
            'name': row.name,
            'dept': row.dept,
            'type': row.type,
            'detail': row.detail or ''
        }
        for row in result
    ]


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
    ).filter(and_(*attendance_where)).group_by(
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
            AttendanceRecord.work_hours.isnot(None)
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
            AttendanceRecord.work_hours.isnot(None)
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
        AttendanceRecord.status == '上班'
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

    # Query 5: Weekend attendance (Saturday/Sunday)
    weekend_attendance = db.query(func.count(AttendanceRecord.id)).join(
        Employee, AttendanceRecord.employee_id == Employee.id
    ).filter(
        dept_field == dept.id,
        AttendanceRecord.upload_id == upload.id,
        AttendanceRecord.status.in_(['上班', '出差']),
        text("strftime('%w', date) IN ('0', '6')")  # Sunday=0, Saturday=6
    ).scalar() or 0

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
              AND a.status = '上班' AND a.work_hours IS NOT NULL
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
          AND a.status = '上班' AND a.work_hours IS NOT NULL
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
        AVG(CASE WHEN a.status = '上班' AND a.work_hours IS NOT NULL THEN a.work_hours END) as avg_work_hours,
        COUNT(CASE WHEN a.status = '上班' THEN 1 END) as workday_attendance_days,
        COUNT(CASE WHEN a.status = '公休日上班' THEN 1 END) as weekend_work_days,
        COUNT(CASE WHEN a.status = '出差' THEN 1 END) as travel_days,
        SUM(CASE WHEN a.status = '请假' THEN 1 ELSE 0 END) as leave_days,
        COUNT(DISTINCT CASE WHEN an.anomaly_type = 'A' THEN e.id END) as anomaly_days,
        COUNT(DISTINCT CASE WHEN a.is_late_after_1930 = 1 THEN e.id END) as late_after_1930_count,
        COUNT(CASE WHEN a.status IN ('上班', '出差') AND strftime('%w', a.date) IN ('0', '6') THEN 1 END) as weekend_attendance_count,
        COALESCE(SUM(t.amount), 0) as total_cost
    FROM dim_department d
    JOIN dim_employee e ON e.level2_department_id = d.id
    LEFT JOIN fact_attendance a ON a.employee_id = e.id AND a.upload_id = :upload_id
    LEFT JOIN anomalies an ON an.employee_id = e.id AND an.upload_id = :upload_id
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
    from datetime import datetime, timedelta

    month_start = datetime.strptime(f"{month}-01", "%Y-%m-%d")
    month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(seconds=1)

    travel_upload_ids = db.query(TravelExpense.upload_id).filter(
        TravelExpense.date >= month_start,
        TravelExpense.date <= month_end
    ).distinct().all()

    attendance_upload_ids = db.query(AttendanceRecord.upload_id).filter(
        AttendanceRecord.date >= month_start,
        AttendanceRecord.date <= month_end
    ).distinct().all()

    all_upload_ids = set(u[0] for u in travel_upload_ids)
    all_upload_ids.update(u[0] for u in attendance_upload_ids)

    return list(all_upload_ids)


def get_dashboard_summary_by_month(db: Session, month: str) -> dict:
    """Get dashboard summary aggregated from ALL files for the given month."""
    from datetime import datetime, timedelta

    upload_ids = get_all_uploads_for_month(db, month)

    if not upload_ids:
        return {
            'total_cost': 0,
            'total_orders': 0,
            'over_standard_count': 0,
            'avg_work_hours': 0
        }

    month_start = datetime.strptime(f"{month}-01", "%Y-%m-%d")
    month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(seconds=1)

    total_cost_result = db.query(
        func.sum(TravelExpense.amount).label('total_cost'),
        func.count(TravelExpense.id).label('total_orders'),
        func.sum(case((TravelExpense.is_over_standard == True, 1), else_=0)).label('over_standard_count')
    ).filter(
        TravelExpense.upload_id.in_(upload_ids),
        TravelExpense.date >= month_start,
        TravelExpense.date <= month_end
    ).first()

    avg_hours_result = db.query(
        func.avg(AttendanceRecord.work_hours).label('avg_hours')
    ).filter(
        AttendanceRecord.upload_id.in_(upload_ids),
        AttendanceRecord.date >= month_start,
        AttendanceRecord.date <= month_end
    ).first()

    return {
        'total_cost': float(total_cost_result.total_cost or 0),
        'total_orders': total_cost_result.total_orders or 0,
        'over_standard_count': total_cost_result.over_standard_count or 0,
        'avg_work_hours': float(avg_hours_result.avg_hours or 0)
    }


def get_department_stats_by_month(db: Session, month: str, top_n: int = 15) -> List[dict]:
    """Get department statistics aggregated from ALL files for the given month."""
    from datetime import datetime, timedelta

    upload_ids = get_all_uploads_for_month(db, month)

    if not upload_ids:
        return []

    month_start = datetime.strptime(f"{month}-01", "%Y-%m-%d")
    month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(seconds=1)

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
        TravelExpense.date >= month_start,
        TravelExpense.date <= month_end
    ).group_by(
        Department.id, Department.name
    ).order_by(
        func.sum(TravelExpense.amount).desc()
    ).limit(top_n).all()

    dept_stats = []
    for row in results:
        dept_id = db.query(Department.id).filter_by(name=row.dept).scalar()

        attendance_query = db.query(
            func.avg(AttendanceRecord.work_hours).label('avg_hours')
        ).join(
            Employee, AttendanceRecord.employee_id == Employee.id
        ).filter(
            AttendanceRecord.upload_id.in_(upload_ids),
            AttendanceRecord.date >= month_start,
            AttendanceRecord.date <= month_end,
            Employee.department_id == dept_id
        )

        avg_hours_result = attendance_query.first()
        avg_hours = float(avg_hours_result.avg_hours or 0) if avg_hours_result else 0

        dept_stats.append({
            'dept': row.dept,
            'cost': round(float(row.cost or 0), 2),
            'avg_hours': round(avg_hours, 2),
            'headcount': row.headcount or 0,
            'flight_cost': round(float(row.flight_cost or 0), 2),
            'hotel_cost': round(float(row.hotel_cost or 0), 2),
            'train_cost': round(float(row.train_cost or 0), 2)
        })

    return dept_stats


def get_project_stats_by_month(db: Session, month: str, top_n: int = 20) -> List[dict]:
    """Get project statistics aggregated from ALL files for the given month."""
    from datetime import datetime, timedelta

    upload_ids = get_all_uploads_for_month(db, month)

    if not upload_ids:
        return []

    month_start = datetime.strptime(f"{month}-01", "%Y-%m-%d")
    month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(seconds=1)

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
        TravelExpense.date >= month_start,
        TravelExpense.date <= month_end
    ).group_by(
        Project.id, Project.code, Project.name
    ).order_by(
        func.sum(TravelExpense.amount).desc()
    ).limit(top_n).all()

    return [
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


def get_anomalies_by_month(db: Session, month: str, limit: int = 50) -> List[dict]:
    """Get anomalies aggregated from ALL files for the given month."""
    from datetime import datetime, timedelta

    upload_ids = get_all_uploads_for_month(db, month)

    if not upload_ids:
        return []

    month_start = datetime.strptime(f"{month}-01", "%Y-%m-%d")
    month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(seconds=1)

    results = db.query(
        Anomaly.date.label('date'),
        Employee.name.label('name'),
        Department.name.label('dept'),
        Anomaly.anomaly_type.label('type'),
        Anomaly.attendance_status.label('status'),
        Anomaly.description.label('detail')
    ).join(
        Employee, Anomaly.employee_id == Employee.id
    ).join(
        Department, Employee.department_id == Department.id
    ).filter(
        Anomaly.upload_id.in_(upload_ids),
        Anomaly.date >= month_start,
        Anomaly.date <= month_end
    ).order_by(
        Anomaly.date.desc()
    ).limit(limit).all()

    return [
        {
            'date': row.date.strftime('%Y/%m/%d'),
            'name': row.name,
            'dept': row.dept,
            'type': row.type,
            'detail': f"{row.status} - {row.detail or ''}"
        }
        for row in results
    ]


def get_total_project_count_by_month(db: Session, month: str) -> int:
    """Get total count of distinct projects for the given month."""
    from datetime import datetime, timedelta

    upload_ids = get_all_uploads_for_month(db, month)

    if not upload_ids:
        return 0

    month_start = datetime.strptime(f"{month}-01", "%Y-%m-%d")
    month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(seconds=1)

    result = db.query(
        func.count(func.distinct(TravelExpense.project_id))
    ).filter(
        TravelExpense.upload_id.in_(upload_ids),
        TravelExpense.date >= month_start,
        TravelExpense.date <= month_end,
        TravelExpense.project_id.isnot(None)
    ).scalar()

    return result or 0


