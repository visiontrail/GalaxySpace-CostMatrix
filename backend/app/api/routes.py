"""
API 路由定义
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from typing import Dict, Any, Optional
import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from app.services.excel_processor import ExcelProcessor
from app.services.ppt_export_service import PPTExporter
from app.models.schemas import AnalysisResult, DashboardData
from app.config import settings
from app.utils.logger import get_logger

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


@router.post("/upload", response_model=AnalysisResult)
async def upload_file(file: UploadFile = File(...)):
    """
    上传 Excel 文件
    """
    # 验证文件类型
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 文件")
    
    # 生成唯一文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(settings.upload_dir, safe_filename)
    
    try:
        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 验证文件可读性，但仅读取 Sheet 名称以提升速度
        processor = ExcelProcessor(file_path)
        sheet_names = processor.get_sheet_names()
        file_size = os.path.getsize(file_path)
        record = {
            "file_path": file_path,
            "file_name": file.filename,
            "file_size": file_size,
            "sheets": sheet_names,
            "upload_time": timestamp,
            "parsed": False,
            "last_analyzed_at": None,
        }
        _upsert_upload_record(record)

        return AnalysisResult(
            success=True,
            message="文件上传成功",
            data=record,
        )
    
    except Exception as e:
        # 清理失败的文件
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.post("/analyze", response_model=AnalysisResult)
async def analyze_excel(file_path: str):
    """
    分析 Excel 文件，返回完整的 Dashboard 数据
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
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
        anomaly_count = len(anomalies)
        
        # 转换部门数据格式为前端期望的结构
        department_stats = [
            {
                'dept': item['department'],
                'cost': item['total_cost'],
                'avg_hours': item.get('avg_hours', 0),
                'headcount': item.get('person_count', 0)
            }
            for item in department_costs
        ]
        
        # 转换项目数据格式为前端期望的结构（现在是Top 20 + "其他"）
        project_top10 = [
            {
                'code': item['project_code'],
                'name': item['project_name'],
                'cost': item['total_cost']
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
                'detail': item.get('description', '')
            }
            for item in anomalies
        ]
        
        # 构建符合前端期望的数据结构
        dashboard_data = {
            'summary': {
                'total_cost': round(total_cost, 2),
                'avg_work_hours': round(avg_work_hours, 2),
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


@router.post("/export-ppt")
async def export_ppt(request: Request):
    """
    导出 Dashboard 数据为 PPT

    请求体:
    {
        "dashboard_data": {...},
        "charts": [{"title": "...", "image": "data:image/png;base64,..."}]
    }
    """
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的请求体: {str(e)}")

    dashboard_data = body.get("dashboard_data", {}) or {}
    charts = body.get("charts", []) or []

    try:
        exporter = PPTExporter()

        # 1) KPI 概览页
        summary = dashboard_data.get("summary", {}) or {}
        kpi_data = {
            "total_cost": summary.get("total_cost", 0),
            "total_orders": summary.get("total_orders", 0),
            "anomaly_count": summary.get("anomaly_count", 0),
            "over_standard_count": summary.get("over_standard_count", 0),
            "urgent_booking_ratio": summary.get("urgent_booking_ratio", 0),
        }
        exporter.create_kpi_slide(kpi_data)

        # 2) 图表页
        for chart in charts:
            exporter.create_chart_slide(
                title=chart.get("title", ""),
                chart_image_base64=chart.get("image", ""),
            )

        # 3) 部门统计表
        department_stats = dashboard_data.get("department_stats", []) or []
        if department_stats:
            headers = ["部门", "成本(元)", "平均工时", "人数"]
            rows = [
                [
                    item.get("dept", ""),
                    item.get("cost", 0),
                    item.get("avg_hours", 0),
                    item.get("headcount", 0),
                ]
                for item in department_stats[:20]
            ]
            exporter.create_table_slide("部门统计详情", headers, rows)

        # 4) 项目成本表
        project_top = dashboard_data.get("project_top10", []) or []
        if project_top:
            headers = ["项目代码", "项目名称", "总成本(元)"]
            rows = [
                [
                    item.get("code", ""),
                    item.get("name", ""),
                    item.get("cost", 0),
                ]
                for item in project_top[:20]
            ]
            exporter.create_table_slide("项目成本详情 (Top 20)", headers, rows)

        # 5) 异常记录表
        anomalies = dashboard_data.get("anomalies", []) or []
        if anomalies:
            headers = ["异常类型", "姓名", "日期", "部门", "详细说明"]
            rows = [
                [
                    item.get("type", ""),
                    item.get("name", ""),
                    item.get("date", ""),
                    item.get("dept", ""),
                    str(item.get("detail", ""))[:80],
                ]
                for item in anomalies[:50]
            ]
            exporter.create_table_slide("异常记录详情 (前50条)", headers, rows)

        # 导出为字节流
        output_stream = exporter.export_to_bytes()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 使用 ASCII 文件名避免 header 编码问题
        output_filename = f"CorpPilot_Report_{timestamp}.pptx"

        return StreamingResponse(
            output_stream,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f"attachment; filename={output_filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PPT 导出失败: {str(e)}")


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
async def get_all_projects(file_path: str):
    """
    获取所有项目的详细信息
    """
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
async def get_project_orders(file_path: str, project_code: str):
    """
    获取指定项目的所有订单记录
    """
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
async def get_department_list(file_path: str, level: int, parent: Optional[str] = None):
    """
    获取部门列表

    Args:
        file_path: Excel 文件路径
        level: 部门层级 (1=一级, 2=二级, 3=三级)
        parent: 父部门名称（level>1时必需）
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    if level not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="部门层级必须是1、2或3")

    if level > 1 and not parent:
        raise HTTPException(status_code=400, detail=f"{level}级部门需要指定父部门")

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
async def get_department_details(file_path: str, department_name: str, level: int = 3):
    """
    获取指定部门的详细指标

    Args:
        file_path: Excel 文件路径
        department_name: 部门名称
        level: 部门层级 (1=一级, 2=二级, 3=三级，默认3)
    """
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    if level not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="部门层级必须是1、2或3")

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
async def get_level1_department_statistics(file_path: str, level1_name: str):
    """
    获取一级部门的汇总统计数据（用于二级部门表格下方的统计展示）

    Args:
        file_path: Excel 文件路径
        level1_name: 一级部门名称

    Returns:
        包含以下统计数据的字典:
        - total_travel_cost: 累计差旅成本
        - attendance_days_distribution: 考勤天数分布
        - travel_ranking: 出差排行榜（按人）
        - avg_hours_ranking: 平均工时排行榜（按人）
        - level2_department_stats: 二级部门统计列表（包含所有指标）
    """
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