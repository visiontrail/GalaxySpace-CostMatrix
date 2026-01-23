"""
API 路由定义
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends, Query, Path, BackgroundTasks, status
from fastapi.responses import FileResponse, StreamingResponse
from typing import Dict, Any, Optional
import json
import os
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

from app.services.excel_processor import ExcelProcessor
from app.services.database_parser import DatabaseParser
from app.services.upload_progress import progress_manager
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_user as create_user_account,
    update_user as update_user_account,
    delete_user as delete_user_account,
    get_current_user,
    require_admin,
    change_password,
)
from app.models.schemas import (
    AnalysisResult,
    DashboardData,
    Token,
    LoginRequest,
    UserCreate,
    UserUpdate,
    UserBase,
    PasswordChangeRequest,
)
from app.config import settings
from app.utils.logger import get_logger
from app.db.database import get_db
from sqlalchemy.orm import Session
from app.db.models import User

router = APIRouter()
logger = get_logger("api.routes")
UPLOAD_RECORDS_FILE = Path(settings.upload_dir) / "upload_records.json"


def _load_upload_records() -> list[Dict[str, Any]]:
    """加载已上传文件的记录列表"""
    if not UPLOAD_RECORDS_FILE.exists():
        return []
    try:
        with open(UPLOAD_RECORDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"读取上传记录失败，已忽略: {e}")
        return []


def _save_upload_records(records: list[Dict[str, Any]]):
    """保存上传记录到磁盘"""
    try:
        UPLOAD_RECORDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(UPLOAD_RECORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"保存上传记录失败: {e}")


def _upsert_upload_record(record: Dict[str, Any]):
    """新增或更新上传记录"""
    records = _load_upload_records()
    target_path = record.get("file_path")
    updated = False

    if target_path:
        for idx, item in enumerate(records):
            if item.get("file_path") == target_path:
                records[idx] = {**item, **record}
                updated = True
                break

    if not updated:
        records.append(record)

    _save_upload_records(records)


def _mark_file_analyzed(file_path: str):
    """标记文件已完成解析"""
    records = _load_upload_records()
    updated = False
    analyzed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in records:
        if item.get("file_path") == file_path:
            item["last_analyzed_at"] = analyzed_at
            item["parsed"] = True
            updated = True
            break

    if not updated:
        # 如果缺失记录，补充最小信息后保存
        fallback_record = {
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            "sheets": [],
            "upload_time": None,
            "parsed": True,
            "last_analyzed_at": analyzed_at,
        }
        records.append(fallback_record)

    _save_upload_records(records)


@router.post("/login", response_model=Token, tags=["auth"])
async def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """用户登录，返回 JWT"""
    user = authenticate_user(db, credentials.username, credentials.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    access_token = create_access_token({"sub": user.username})
    user_data = UserBase(username=user.username, is_admin=user.is_admin, created_at=user.created_at)
    return Token(access_token=access_token, user=user_data)


@router.get("/me", response_model=UserBase, tags=["auth"])
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return UserBase(username=current_user.username, is_admin=current_user.is_admin, created_at=current_user.created_at)


@router.post("/change-password", tags=["auth"])
async def change_my_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    管理员修改自己的密码
    """
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="两次输入的新密码不一致")

    change_password(db, current_user, payload.current_password, payload.new_password)
    return {"success": True, "message": "密码修改成功"}


@router.get("/users", response_model=list[UserBase], tags=["users"])
async def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员获取用户列表"""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [
        UserBase(username=u.username, is_admin=u.is_admin, created_at=u.created_at)
        for u in users
    ]


@router.post("/users", response_model=UserBase, tags=["users"])
async def create_user(
    payload: UserCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员创建新用户"""
    user = create_user_account(db, payload.username.strip(), payload.password, payload.is_admin)
    return UserBase(username=user.username, is_admin=user.is_admin, created_at=user.created_at)


@router.put("/users/{username}", response_model=UserBase, tags=["users"])
async def update_user(
    username: str,
    payload: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员修改用户信息"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 防止管理员删除/禁用自己导致锁死
    if user.username == current_user.username and payload.is_active is False:
        raise HTTPException(status_code=400, detail="不能禁用当前登录账户")

    updated = update_user_account(
        db,
        user,
        password=payload.password,
        is_admin=payload.is_admin,
        is_active=payload.is_active,
    )
    return UserBase(username=updated.username, is_admin=updated.is_admin, created_at=updated.created_at)


@router.delete("/users/{username}", tags=["users"])
async def delete_user(
    username: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员删除用户"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.username == current_user.username:
        raise HTTPException(status_code=400, detail="不能删除当前登录账户")

    delete_user_account(db, user)
    return {"success": True, "message": "用户已删除"}


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version
    }


@router.get("/uploads")
async def list_uploads():
    """
    获取上传文件列表（所有用户可见）
    """
    records = _load_upload_records()
    result = []
    for item in records:
        file_path = item.get("file_path", "")
        exists = os.path.exists(file_path)
        result.append({**item, "exists": exists})
    return {"success": True, "data": result}


@router.get("/months")
async def get_available_months(db: Session = Depends(get_db)):
    """
    获取所有上传文件中的可用月份列表（从数据库获取）
    """
    try:
        from app.db.crud import get_available_months
        from app.db.models import Upload

        # 获取所有已上传的文件
        uploads = db.query(Upload).all()
        all_months = set()

        for upload in uploads:
            # 从数据库获取该文件的所有月份
            months = get_available_months(db, upload.file_path)
            all_months.update(months)

        return {
            "success": True,
            "data": sorted(list(all_months))
        }
    except Exception as e:
        logger.exception(f"获取月份列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取月份列表失败: {str(e)}")


@router.get("/progress/{task_id}")
async def get_upload_progress(task_id: str):
    """
    获取上传进度
    """
    progress = progress_manager.get_progress(task_id)
    
    if not progress:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    
    return {"success": True, "data": progress}


def _process_upload_task(file_path: str, file_name: str, task_id: str):
    """后台任务：处理文件上传和解析"""
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        progress_manager.update_progress(task_id, 30, "正在读取Excel文件...")
        progress_manager.add_step(task_id, f"✅ 文件已上传: {file_name} ({os.path.getsize(file_path) / 1024 / 1024:.2f} MB)")
        
        processor = ExcelProcessor(file_path)
        sheet_names = processor.get_sheet_names()
        progress_manager.add_step(task_id, f"📋 检测到 {len(sheet_names)} 个工作表: {', '.join(sheet_names)}")
        
        file_size = os.path.getsize(file_path)
        progress_manager.update_progress(task_id, 40, "正在解析数据并写入数据库...")

        def progress_callback(progress: int, message: str):
            progress_manager.update_progress(task_id, progress, message)
            progress_manager.add_step(task_id, message)

        parser = DatabaseParser(file_path, progress_callback)
        parse_stats = parser.parse_and_insert(db)
        
        progress_manager.add_step(task_id, f"✅ 考勤记录: {parse_stats['attendance_count']} 条")
        progress_manager.add_step(task_id, f"✅ 机票记录: {parse_stats['flight_count']} 条")
        progress_manager.add_step(task_id, f"✅ 酒店记录: {parse_stats['hotel_count']} 条")
        progress_manager.add_step(task_id, f"✅ 火车票记录: {parse_stats['train_count']} 条")
        progress_manager.add_step(task_id, f"✅ 异常记录: {parse_stats['anomalies_count']} 条")
        
        progress_manager.update_progress(task_id, 90, "正在保存上传记录...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _upsert_upload_record({
            "file_path": file_path,
            "file_name": file_name,
            "file_size": file_size,
            "sheets": sheet_names,
            "upload_time": timestamp,
            "parsed": True,
            "last_analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        
        progress_manager.update_progress(task_id, 100, "上传并解析完成")
        progress_manager.complete_task(task_id, {
            "file_path": file_path,
            "file_name": file_name,
            "upload_id": parse_stats.get("upload_id"),
            "stats": parse_stats
        })
    except Exception as e:
        db.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"文件上传失败: {e}")
        
        error_msg = str(e)
        progress_manager.fail_task(task_id, error_msg)
    finally:
        db.close()


@router.post("/upload", response_model=AnalysisResult)
async def upload_file(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    上传 Excel 文件并解析到数据库
    """
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 文件")

    task_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(settings.upload_dir, safe_filename)

    try:
        progress_manager.create_task(task_id, file.filename)
        progress_manager.update_progress(task_id, 10, "正在上传文件...")
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        progress_manager.update_progress(task_id, 20, "文件上传完成，开始解析...")
        
        # 添加后台任务处理文件
        background_tasks.add_task(_process_upload_task, file_path, file.filename, task_id)

        return AnalysisResult(
            success=True,
            message="文件上传成功，正在后台解析",
            data={
                "file_path": file_path,
                "file_name": file.filename,
                "task_id": task_id,
            },
        )

    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"文件上传失败: {e}")
        
        error_msg = str(e)
        progress_manager.fail_task(task_id, error_msg)
        
        raise HTTPException(status_code=500, detail=f"文件上传失败: {error_msg}")


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_excel(
    file_path: Optional[str] = Query(None, description="文件路径（可选，如果不提供则从数据库读取）"),
    months: Optional[str] = Query(None, description="月份列表，逗号分隔 (例如: 2025-01,2025-02)"),
    quarter: Optional[int] = Query(None, description="季度 (1, 2, 3, 4)"),
    year: Optional[int] = Query(None, description="年份")
):
    """
    分析 Excel 文件，返回完整的 Dashboard 数据
    支持按月份、季度、年份筛选数据
    """
    months_list = None
    if months:
        months_list = [m.strip() for m in months.split(',') if m.strip()]

    if not file_path:
        if not (months_list or quarter or year):
            raise HTTPException(status_code=400, detail="未指定文件路径时，必须提供 months、quarter 或 year 参数")

        try:
            from app.db.crud import get_dashboard_data
            from app.db.database import get_db

            db_gen = get_db()
            db = next(db_gen)

            dashboard_data = get_dashboard_data(
                db=db,
                months=months_list,
                quarter=quarter,
                year=year
            )

            return AnalysisResult(
                success=True,
                message="分析完成",
                data=dashboard_data
            )
        except Exception as e:
            logger.exception(f"数据库分析失败: {e}")
            raise HTTPException(status_code=500, detail=f"数据库分析失败: {str(e)}")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    if months_list or quarter or year:
        logger.warning(f"Excel 文件分析暂不支持月份过滤，将返回全部数据。参数: months={months_list}, quarter={quarter}, year={year}")
    
    try:
        logger.info(f"开始分析文件: {file_path}")
        overall_start = time.perf_counter()

        def timed_step(step_name: str, func, *args, **kwargs):
            step_start = time.perf_counter()
            result = func(*args, **kwargs)
            logger.info(f"{step_name}完成，用时 {(time.perf_counter() - step_start) * 1000:.0f}ms")
            return result

        processor = ExcelProcessor(file_path)
        load_start = time.perf_counter()
        processor.load_all_sheets(load_workbook_obj=False)
        logger.info(f"文件加载完成，用时 {(time.perf_counter() - load_start) * 1000:.0f}ms")
        
        # 执行各项分析（部门Top 15，项目Top 20 + 其他）
        project_costs, total_project_count = timed_step("项目成本归集", processor.aggregate_project_costs, top_n=20)
        department_costs = timed_step("部门成本汇总", processor.calculate_department_costs, top_n=15)
        anomalies = timed_step("考勤/差旅交叉验证", processor.cross_check_attendance_travel)
        booking_behavior = timed_step("预订行为分析", processor.analyze_booking_behavior)
        attendance_summary = timed_step("考勤汇总", processor.get_attendance_summary)
        over_standard_stats = timed_step("超标统计", processor.count_over_standard_orders)
        order_stats = timed_step("订单统计", processor.count_total_orders)
        over_standard_breakdown = {
            k: v for k, v in over_standard_stats.items() 
            if k != 'flight_over_types'
        }
        flight_over_type_breakdown = over_standard_stats.get('flight_over_types', {})
        
        # 计算总览数据
        total_cost = sum(item['total_cost'] for item in department_costs)
        avg_work_hours = attendance_summary.get('avg_work_hours', 0)
        holiday_avg_work_hours = attendance_summary.get('holiday_avg_work_hours', 0)
        anomaly_count = len(anomalies)
        
        # 转换部门数据格式为前端期望的结构
        department_stats = [
            {
                'dept': item['department'],
                'cost': item['total_cost'],
                'avg_hours': item.get('avg_hours', 0),
                'holiday_avg_hours': item.get('holiday_avg_hours', 0),
                'headcount': item.get('person_count', 0)
            }
            for item in department_costs
        ]
        
        # 转换项目数据格式为前端期望的结构（现在是Top 20 + "其他"）
        project_top10 = [
            {
                'code': item['project_code'],
                'name': item['project_name'],
                'cost': item['total_cost'],
                'flight_cost': item.get('flight_cost', 0),
                'hotel_cost': item.get('hotel_cost', 0),
                'train_cost': item.get('train_cost', 0)
            }
            for item in project_costs
        ]
        
        # 转换异常数据格式为前端期望的结构
        anomaly_list = [
            {
                'date': item.get('date', ''),
                'name': item.get('name', ''),
                'dept': item.get('department', ''),
                'type': item.get('anomaly_type', 'Unknown'),
                'status': item.get('attendance_status', ''),
                'detail': item.get('description', '')
            }
            for item in anomalies
        ]
        
        # 构建符合前端期望的数据结构
        dashboard_data = {
            'summary': {
                'total_cost': round(total_cost, 2),
                'avg_work_hours': round(avg_work_hours, 2),
                'holiday_avg_work_hours': round(holiday_avg_work_hours, 2),
                'anomaly_count': anomaly_count,
                'total_orders': order_stats.get('total', 0),
                'order_breakdown': order_stats,
                'over_standard_count': over_standard_stats.get('total', 0),
                'over_standard_breakdown': over_standard_breakdown,
                'flight_over_type_breakdown': flight_over_type_breakdown,
                'total_project_count': total_project_count
            },
            'department_stats': department_stats,
            'project_top10': project_top10,
            'anomalies': anomaly_list
        }

        logger.info(f"分析流程结束，总耗时 {time.perf_counter() - overall_start:.2f}s")
        _mark_file_analyzed(file_path)

        return AnalysisResult(
            success=True,
            message="分析完成",
            data=dashboard_data
        )
    
    except Exception as e:
        logger.exception(f"分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@router.post("/export")
async def export_results(file_path: str):
    """
    导出分析结果到 Excel（追加新 Sheet）
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        processor = ExcelProcessor(file_path)
        processor.load_all_sheets(load_workbook_obj=True)
        
        # 执行分析
        results = {
            'project_costs': processor.aggregate_project_costs(),
            'department_costs': processor.calculate_department_costs(),
            'anomalies': processor.cross_check_attendance_travel()
        }
        
        # 回写到 Excel
        output_path = processor.write_analysis_results(results)
        
        # 返回文件
        return FileResponse(
            path=output_path,
            filename=os.path.basename(output_path),
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/sheets/{file_path:path}")
async def get_sheets(file_path: str):
    """
    获取文件中所有 Sheet 名称
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        processor = ExcelProcessor(file_path)
        sheets = processor.load_all_sheets()
        
        return {
            "success": True,
            "sheets": [
                {
                    "name": name,
                    "rows": len(df),
                    "columns": len(df.columns)
                }
                for name, df in sheets.items()
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取失败: {str(e)}")


@router.delete("/files/{file_path:path}")
async def delete_file(file_path: str):
    """
    删除上传的文件
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        os.remove(file_path)
        # 同步删除记录
        records = [r for r in _load_upload_records() if r.get("file_path") != file_path]
        _save_upload_records(records)
        return {"success": True, "message": "文件已删除"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.delete("/data")
async def clear_data(file_path: str):
    """
    清除指定上传文件及其记录，而非全部数据
    """
    if not file_path:
        raise HTTPException(status_code=400, detail="缺少需要清除的文件路径")

    upload_dir = Path(settings.upload_dir).resolve()
    target_path = Path(file_path).resolve()

    if upload_dir not in target_path.parents:
        raise HTTPException(status_code=400, detail="只能清除上传目录下的文件")

    records = _load_upload_records()
    cleared_file = False
    removed_records = 0

    try:
        if target_path.exists():
            if target_path.is_file() or target_path.is_symlink():
                target_path.unlink(missing_ok=True)
                cleared_file = True
            elif target_path.is_dir():
                shutil.rmtree(target_path)
                cleared_file = True

        filtered_records = []
        for item in records:
            item_path = item.get("file_path")
            if item_path and Path(item_path).resolve() == target_path:
                removed_records += 1
                continue
            filtered_records.append(item)

        _save_upload_records(filtered_records)

        return {
            "success": True,
            "message": "指定数据已清除",
            "data": {
                "file_cleared": cleared_file,
                "records_removed": removed_records
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除数据失败: {str(e)}")


@router.get("/projects")
async def get_all_projects(
    file_path: Optional[str] = Query(None, description="文件路径（可选，不提供则从数据库读取）"),
    months: Optional[str] = Query(None, description="月份列表，逗号分隔 (例如: 2025-01,2025-02)"),
    db: Session = Depends(get_db)
):
    """
    获取所有项目的详细信息

    支持从Excel文件或数据库获取数据

    Args:
        file_path: Excel 文件路径（可选）
        months: 月份列表（数据库模式下使用）
    """
    # 如果没有提供file_path，从数据库获取
    if not file_path:
        if not months:
            raise HTTPException(status_code=400, detail="数据库模式下必须提供months参数")

        try:
            from app.db.crud import get_all_projects_from_db

            months_list = [m.strip() for m in months.split(',') if m.strip()]
            project_details = get_all_projects_from_db(db, months_list)

            return AnalysisResult(
                success=True,
                message="获取项目详情成功",
                data={
                    "projects": project_details,
                    "total_count": len(project_details)
                }
            )
        except Exception as e:
            logger.exception(f"从数据库获取项目详情失败: {e}")
            raise HTTPException(status_code=500, detail=f"获取项目详情失败: {str(e)}")

    # 从Excel文件获取
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        processor = ExcelProcessor(file_path)
        processor.load_all_sheets(load_workbook_obj=False)

        project_details = processor.get_all_project_details()

        return AnalysisResult(
            success=True,
            message="获取项目详情成功",
            data={
                "projects": project_details,
                "total_count": len(project_details)
            }
        )

    except Exception as e:
        logger.exception(f"获取项目详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目详情失败: {str(e)}")


@router.get("/projects/{project_code}/orders")
async def get_project_orders(
    project_code: str,
    file_path: Optional[str] = Query(None, description="文件路径（可选，不提供则从数据库读取）"),
    months: Optional[str] = Query(None, description="月份列表，逗号分隔 (例如: 2025-01,2025-02)"),
    db: Session = Depends(get_db)
):
    """
    获取指定项目的所有订单记录

    支持从Excel文件或数据库获取数据

    Args:
        file_path: Excel 文件路径（可选）
        project_code: 项目代码
        months: 月份列表（数据库模式下使用）
    """
    # 如果没有提供file_path，从数据库获取
    if not file_path:
        if not months:
            raise HTTPException(status_code=400, detail="数据库模式下必须提供months参数")

        try:
            from app.db.crud import get_project_orders_from_db

            months_list = [m.strip() for m in months.split(',') if m.strip()]
            order_records = get_project_orders_from_db(db, project_code, months_list)

            return AnalysisResult(
                success=True,
                message="获取项目订单记录成功",
                data={
                    "project_code": project_code,
                    "orders": order_records,
                    "total_count": len(order_records)
                }
            )
        except Exception as e:
            logger.exception(f"从数据库获取项目订单记录失败: {e}")
            raise HTTPException(status_code=500, detail=f"获取项目订单记录失败: {str(e)}")

    # 从Excel文件获取
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        processor = ExcelProcessor(file_path)
        processor.load_all_sheets(load_workbook_obj=False)

        order_records = processor.get_project_order_records(project_code)

        return AnalysisResult(
            success=True,
            message="获取项目订单记录成功",
            data={
                "project_code": project_code,
                "orders": order_records,
                "total_count": len(order_records)
            }
        )

    except Exception as e:
        logger.exception(f"获取项目订单记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目订单记录失败: {str(e)}")


@router.get("/departments/hierarchy")
async def get_department_hierarchy(file_path: str):
    """
    获取部门层级结构
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        processor = ExcelProcessor(file_path)
        processor.load_all_sheets(load_workbook_obj=False)

        hierarchy = processor.get_department_hierarchy()

        return AnalysisResult(
            success=True,
            message="获取部门层级结构成功",
            data=hierarchy
        )

    except Exception as e:
        logger.exception(f"获取部门层级结构失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取部门层级结构失败: {str(e)}")


@router.get("/departments/list")
async def get_department_list(
    file_path: Optional[str] = Query(None, description="文件路径（可选，不提供则从数据库读取）"),
    level: int = Query(..., description="部门层级 (1=一级, 2=二级, 3=三级)"),
    parent: Optional[str] = Query(None, description="父部门名称（level>1时必需）"),
    months: Optional[str] = Query(None, description="月份列表，逗号分隔 (例如: 2025-01,2025-02)"),
    db: Session = Depends(get_db)
):
    """
    获取部门列表

    支持从Excel文件或数据库获取数据

    Args:
        file_path: Excel 文件路径（可选）
        level: 部门层级 (1=一级, 2=二级, 3=三级)
        parent: 父部门名称（level>1时必需）
        months: 月份列表（数据库模式下使用）
    """
    if level not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="部门层级必须是1、2或3")

    if level > 1 and not parent:
        raise HTTPException(status_code=400, detail=f"{level}级部门需要指定父部门")

    # 如果没有提供file_path，从数据库获取
    if not file_path:
        if not months:
            raise HTTPException(status_code=400, detail="数据库模式下必须提供months参数")

        try:
            from app.db.crud import get_department_list_from_db

            months_list = [m.strip() for m in months.split(',') if m.strip()]
            departments = get_department_list_from_db(db, level, parent, months_list)

            return AnalysisResult(
                success=True,
                message="获取部门列表成功",
                data={
                    "level": level,
                    "parent": parent,
                    "departments": departments,
                    "total_count": len(departments)
                }
            )
        except Exception as e:
            logger.exception(f"从数据库获取部门列表失败: {e}")
            raise HTTPException(status_code=500, detail=f"获取部门列表失败: {str(e)}")

    # 从Excel文件获取
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        processor = ExcelProcessor(file_path)
        processor.load_all_sheets(load_workbook_obj=False)

        departments = processor.get_department_list(level, parent)

        return AnalysisResult(
            success=True,
            message="获取部门列表成功",
            data={
                "level": level,
                "parent": parent,
                "departments": departments,
                "total_count": len(departments)
            }
        )

    except Exception as e:
        logger.exception(f"获取部门列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取部门列表失败: {str(e)}")


@router.get("/departments/details")
async def get_department_details(
    file_path: Optional[str] = Query(None, description="文件路径（可选，不提供则从数据库读取）"),
    department_name: str = Query(..., description="部门名称"),
    level: int = Query(3, description="部门层级 (1=一级, 2=二级, 3=三级，默认3)"),
    months: Optional[str] = Query(None, description="月份列表，逗号分隔 (例如: 2025-01,2025-02)"),
    db: Session = Depends(get_db)
):
    """
    获取指定部门的详细指标

    支持从Excel文件或数据库获取数据

    Args:
        file_path: Excel 文件路径（可选）
        department_name: 部门名称
        level: 部门层级 (1=一级, 2=二级, 3=三级，默认3)
        months: 月份列表（数据库模式下使用）
    """
    if level not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="部门层级必须是1、2或3")

    # 如果没有提供file_path，从数据库获取
    if not file_path:
        if not months:
            raise HTTPException(status_code=400, detail="数据库模式下必须提供months参数")

        try:
            from app.db.crud import get_department_details_from_db

            months_list = [m.strip() for m in months.split(',') if m.strip()]
            details = get_department_details_from_db(db, department_name, level, months_list)

            if not details:
                raise HTTPException(status_code=404, detail=f"未找到部门: {department_name}")

            return AnalysisResult(
                success=True,
                message="获取部门详情成功",
                data=details
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"从数据库获取部门详情失败: {e}")
            raise HTTPException(status_code=500, detail=f"获取部门详情失败: {str(e)}")

    # 从Excel文件获取
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        processor = ExcelProcessor(file_path)
        processor.load_all_sheets(load_workbook_obj=False)

        details = processor.get_department_detail_metrics(department_name, level)

        if not details:
            raise HTTPException(status_code=404, detail=f"未找到部门: {department_name}")

        return AnalysisResult(
            success=True,
            message="获取部门详情成功",
            data=details
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取部门详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取部门详情失败: {str(e)}")


@router.get("/departments/level1/statistics")
async def get_level1_department_statistics(
    file_path: Optional[str] = Query(None, description="文件路径（可选，不提供则从数据库读取）"),
    level1_name: str = Query(..., description="一级部门名称"),
    months: Optional[str] = Query(None, description="月份列表，逗号分隔 (例如: 2025-01)"),
    db: Session = Depends(get_db)
):
    """
    获取一级部门的汇总统计数据（用于二级部门表格下方的统计展示）

    支持从Excel文件或数据库获取数据

    Args:
        file_path: Excel 文件路径（可选）
        level1_name: 一级部门名称
        months: 月份列表（数据库模式下使用）

    Returns:
        包含以下统计数据的字典:
        - department_name: 部门名称
        - total_travel_cost: 累计差旅成本
        - attendance_days_distribution: 考勤天数分布
        - travel_ranking: 出差排行榜（按人）
        - avg_hours_ranking: 平均工时排行榜（按人）
        - level2_department_stats: 二级部门统计列表（包含所有指标）
    """
    # 如果没有提供file_path，从数据库获取
    if not file_path:
        if not months:
            raise HTTPException(status_code=400, detail="数据库模式下必须提供months参数")

        try:
            from app.db.crud import get_level1_department_statistics_from_db

            months_list = [m.strip() for m in months.split(',') if m.strip()]
            statistics = get_level1_department_statistics_from_db(db, level1_name, months_list)

            if not statistics:
                raise HTTPException(status_code=404, detail=f"未找到一级部门: {level1_name}")

            return AnalysisResult(
                success=True,
                message="获取一级部门统计数据成功",
                data=statistics
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"从数据库获取一级部门统计数据失败: {e}")
            raise HTTPException(status_code=500, detail=f"获取一级部门统计数据失败: {str(e)}")

    # 从Excel文件获取
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        processor = ExcelProcessor(file_path)
        processor.load_all_sheets(load_workbook_obj=False)

        statistics = processor.get_level1_department_statistics(level1_name)

        if not statistics:
            raise HTTPException(status_code=404, detail=f"未找到一级部门: {level1_name}")

        return AnalysisResult(
            success=True,
            message="获取一级部门统计数据成功",
            data=statistics
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"获取一级部门统计数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取一级部门统计数据失败: {str(e)}")


@router.delete("/months/{month}")
async def delete_month(
    month: str,
    db: Session = Depends(get_db)
):
    """
    删除指定月份的所有数据

    删除内容包括:
    - 该月份的考勤记录
    - 该月份的差旅费用记录
    - 该月份的异常记录
    - 如果上传文件仅包含该月份数据，则同时删除上传记录和原始Excel文件

    Args:
        month: 月份 (YYYY-MM格式)
        db: 数据库会话

    Returns:
        删除统计信息
    """
    try:
        from app.db.crud import delete_month_data

        # 验证月份格式
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            raise HTTPException(status_code=400, detail="月份格式错误，应为 YYYY-MM")

        result = delete_month_data(db, month)

        return {
            "success": True,
            "message": f"已删除 {month} 月份的数据",
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"删除月份数据失败: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除月份数据失败: {str(e)}")


@router.get("/anomalies")
async def get_anomalies(
    file_path: Optional[str] = Query(None, description="文件路径（可选，不提供则从数据库读取）"),
    months: Optional[str] = Query(None, description="月份列表，逗号分隔 (例如: 2025-01,2025-02)"),
    db: Session = Depends(get_db)
):
    """
    获取异常记录详情

    支持从Excel文件或数据库获取数据

    Args:
        file_path: Excel 文件路径（可选）
        months: 月份列表（数据库模式下使用）
    """
    # 如果没有提供file_path，从数据库获取
    if not file_path:
        if not months:
            raise HTTPException(status_code=400, detail="数据库模式下必须提供months参数")

        try:
            from app.db.crud import get_anomalies_by_month

            months_list = [m.strip() for m in months.split(',') if m.strip()]
            # 获取所有月份的异常记录
            all_anomalies = []
            for month in months_list:
                anomalies = get_anomalies_by_month(db, month, limit=1000)
                all_anomalies.extend(anomalies)

            # 按日期降序排序
            all_anomalies.sort(key=lambda x: x['date'], reverse=True)

            return AnalysisResult(
                success=True,
                message="获取异常记录成功",
                data={
                    "anomalies": all_anomalies,
                    "total_count": len(all_anomalies)
                }
            )
        except Exception as e:
            logger.exception(f"从数据库获取异常记录失败: {e}")
            raise HTTPException(status_code=500, detail=f"获取异常记录失败: {str(e)}")

    # 从Excel文件获取
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    try:
        from app.db.crud import get_anomalies

        months_list = [m.strip() for m in months.split(',')] if months else None
        anomalies = get_anomalies(db, file_path, months=months_list, limit=1000)

        return AnalysisResult(
            success=True,
            message="获取异常记录成功",
            data={
                "anomalies": anomalies,
                "total_count": len(anomalies)
            }
        )

    except Exception as e:
        logger.exception(f"获取异常记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取异常记录失败: {str(e)}")
