"""
API 路由定义
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from typing import Dict, Any
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


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version
    }


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
        
        return AnalysisResult(
            success=True,
            message="文件上传成功",
            data={
                "file_path": file_path,
                "file_name": file.filename,
                "file_size": file_size,
                "sheets": sheet_names,
                "upload_time": timestamp
            }
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
        
        # 执行各项分析（部门Top 15，项目Top 20）
        project_costs = timed_step("项目成本归集", processor.aggregate_project_costs, top_n=20)
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
                'flight_over_type_breakdown': flight_over_type_breakdown
            },
            'department_stats': department_stats,
            'project_top10': project_top10,
            'anomalies': anomaly_list
        }

        logger.info(f"分析流程结束，总耗时 {time.perf_counter() - overall_start:.2f}s")

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
        return {"success": True, "message": "文件已删除"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.delete("/data")
async def clear_all_data():
    """
    清除上传文件和后台生成的数据
    """
    upload_dir = Path(settings.upload_dir).resolve()
    cleared_uploads = 0
    cleared_logs = 0

    try:
        if upload_dir.exists() and upload_dir.is_dir():
            for item in upload_dir.iterdir():
                if item.is_file() or item.is_symlink():
                    item.unlink(missing_ok=True)
                    cleared_uploads += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    cleared_uploads += 1
            upload_dir.mkdir(parents=True, exist_ok=True)

        project_root = Path(__file__).resolve().parents[2]  # backend 根目录
        log_dir = project_root / "logs"
        if log_dir.exists() and log_dir.is_dir():
            for log_file in log_dir.iterdir():
                if log_file.is_file():
                    log_file.unlink(missing_ok=True)
                    cleared_logs += 1

        return {
            "success": True,
            "message": "数据已清除",
            "data": {
                "uploads_cleared": cleared_uploads,
                "logs_cleared": cleared_logs
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除数据失败: {str(e)}")
