"""
数据模型定义
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, date


class AnalysisResult(BaseModel):
    """分析结果基础模型"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class AttendanceRecord(BaseModel):
    """考勤记录"""
    date: date
    name: str
    department: str
    status: str  # 上班/出差/休假
    work_hours: Optional[float] = None
    earliest_clock: Optional[str] = None
    latest_clock: Optional[str] = None


class TravelRecord(BaseModel):
    """差旅记录"""
    travel_person: str
    amount: float
    project: Optional[str] = None
    travel_date: date
    travel_type: str  # 机票/酒店/火车票
    is_overbudget: Optional[bool] = None
    advance_days: Optional[int] = None


class CrossCheckAnomaly(BaseModel):
    """交叉验证异常记录"""
    name: str
    date: date
    anomaly_type: str  # A: 上班但有差旅, B: 出差但无差旅
    attendance_status: str
    travel_records: List[str]
    description: str


class ProjectCostSummary(BaseModel):
    """项目成本汇总"""
    project_code: str
    project_name: str
    total_cost: float
    record_count: int
    details: List[Dict[str, Any]]


class DepartmentCostSummary(BaseModel):
    """部门成本汇总"""
    department: str
    total_cost: float
    flight_cost: float
    hotel_cost: float
    train_cost: float
    person_count: int
    avg_work_hours: float
    holiday_avg_work_hours: float = 0


class BookingBehaviorAnalysis(BaseModel):
    """预订行为分析"""
    avg_advance_days: float
    correlation_advance_cost: float
    advance_day_distribution: Dict[str, int]
    cost_by_advance_days: List[Dict[str, Any]]


class DashboardData(BaseModel):
    """Dashboard 数据汇总"""
    overview: Dict[str, Any]
    department_costs: List[DepartmentCostSummary]
    project_costs: List[ProjectCostSummary]
    anomalies: List[CrossCheckAnomaly]
    booking_behavior: Optional[BookingBehaviorAnalysis] = None
    attendance_summary: Dict[str, Any]


class EmployeeRanking(BaseModel):
    """员工排行榜项"""
    name: str
    value: float
    detail: Optional[str] = None


class DepartmentDetailMetrics(BaseModel):
    """部门详细指标"""
    # 基本信息
    department_name: str
    department_level: str
    parent_department: Optional[str] = None

    # 考勤相关指标
    attendance_days_distribution: Dict[str, int]
    weekend_work_days: int
    workday_attendance_days: int
    avg_work_hours: float
    holiday_avg_work_hours: float = 0

    # 状态天数
    travel_days: int
    leave_days: int

    # 异常统计
    anomaly_days: int
    late_after_1930_count: int
    weekend_attendance_count: int

    # 排行榜
    travel_ranking: List[EmployeeRanking]
    anomaly_ranking: List[EmployeeRanking]
    latest_checkout_ranking: List[EmployeeRanking]
    longest_hours_ranking: List[EmployeeRanking]


class DepartmentHierarchy(BaseModel):
    """部门层级结构"""
    level1: List[str]  # 一级部门列表
    level2: Dict[str, List[str]]  # 一级部门 -> 二级部门列表
    level3: Dict[str, List[str]]  # 二级部门 -> 三级部门列表


class DepartmentListItem(BaseModel):
    """部门列表项"""
    name: str
    level: int  # 1=一级, 2=二级, 3=三级
    parent: Optional[str] = None
    person_count: int
    total_cost: float
    avg_work_hours: float
    holiday_avg_work_hours: float = 0


class Level2DepartmentStats(BaseModel):
    """二级部门统计（用于一级部门统计展示）"""
    name: str
    person_count: int
    avg_work_hours: float
    holiday_avg_work_hours: float = 0
    workday_attendance_days: int
    weekend_work_days: int
    weekend_attendance_count: int
    travel_days: int
    leave_days: int
    anomaly_days: int
    late_after_1930_count: int
    total_cost: float


class Level1DepartmentStatistics(BaseModel):
    """一级部门汇总统计数据"""
    department_name: str
    total_travel_cost: float
    attendance_days_distribution: Dict[str, int]
    travel_ranking: List[EmployeeRanking]
    avg_hours_ranking: List[EmployeeRanking]
    level2_department_stats: List[Level2DepartmentStats]