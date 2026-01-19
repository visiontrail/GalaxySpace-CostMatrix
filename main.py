"""
FastAPI 主入口
提供差旅分析 API 服务
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os
from typing import Dict
import traceback
import time
import uuid
from datetime import datetime

from data_loader import DataLoader
from analysis_service import TravelAnalyzer
from export_service import ExcelExporter
from logger_config import get_logger, RequestLogger, log_exception, log_performance


# 初始化日志系统
logger = get_logger("main")
request_logger = RequestLogger(logger)

logger.info("=" * 80)
logger.info("系统启动中...")
logger.info("=" * 80)

# 创建 FastAPI 应用
app = FastAPI(
    title="CostMatrix - 企业差旅分析平台",
    description="基于 Excel 数据的差旅成本分析与异常检测 API",
    version="1.0.0"
)

logger.info("FastAPI 应用已创建")

# 配置 CORS（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("CORS 中间件已配置")


@app.get("/")
async def root():
    """根路径，返回 API 信息"""
    logger.info("访问根路径")
    return {
        "message": "Welcome to CostMatrix API",
        "version": "1.0.0",
        "endpoints": {
            "analyze": "/api/analyze",
            "export": "/api/export",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """健康检查接口"""
    logger.debug("健康检查")
    return {
        "status": "healthy",
        "service": "CostMatrix API"
    }


@app.post("/api/analyze")
async def analyze_travel_data(file: UploadFile = File(...)) -> Dict:
    """
    分析差旅数据
    
    接收上传的 .xlsx 文件，返回 Dashboard 所需的 JSON 数据
    
    Args:
        file: 上传的 Excel 文件
        
    Returns:
        包含分析结果的 JSON 数据
    """
    # 生成唯一请求ID
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    # 记录请求开始
    request_logger.log_request_start(request_id, "/api/analyze", file.filename)
    logger.info(f"[{request_id}] 接收到分析请求，文件名: {file.filename}, 大小: {file.size if hasattr(file, 'size') else 'Unknown'}")
    
    # 验证文件格式
    if not file.filename.endswith('.xlsx'):
        logger.warning(f"[{request_id}] 文件格式不正确: {file.filename}")
        raise HTTPException(
            status_code=400,
            detail="只支持 .xlsx 格式的 Excel 文件"
        )
    
    temp_file = None
    temp_file_path = None
    
    try:
        # 保存上传文件到临时目录
        logger.debug(f"[{request_id}] 开始保存上传文件到临时目录")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        logger.info(f"[{request_id}] 文件已保存到: {temp_file_path}, 大小: {len(content)} bytes")
        
        # 加载数据
        logger.debug(f"[{request_id}] 开始加载Excel数据")
        load_start = time.time()
        loader = DataLoader(temp_file_path)
        data_sheets = loader.load_all_sheets()
        load_duration = (time.time() - load_start) * 1000
        logger.info(f"[{request_id}] 数据加载完成，耗时: {load_duration:.2f}ms")
        log_performance(logger, f"[{request_id}] 数据加载", load_duration)
        
        # 记录加载的数据统计
        logger.info(f"[{request_id}] 考勤数据行数: {len(data_sheets['attendance'])}")
        logger.info(f"[{request_id}] 机票数据行数: {len(data_sheets['flight'])}")
        logger.info(f"[{request_id}] 酒店数据行数: {len(data_sheets['hotel'])}")
        logger.info(f"[{request_id}] 火车票数据行数: {len(data_sheets['train'])}")
        
        # 执行分析
        logger.debug(f"[{request_id}] 开始执行数据分析")
        analysis_start = time.time()
        analyzer = TravelAnalyzer(
            attendance_df=data_sheets['attendance'],
            flight_df=data_sheets['flight'],
            hotel_df=data_sheets['hotel'],
            train_df=data_sheets['train']
        )
        
        # 生成 Dashboard 数据
        dashboard_data = analyzer.generate_dashboard_data()
        analysis_duration = (time.time() - analysis_start) * 1000
        logger.info(f"[{request_id}] 数据分析完成，耗时: {analysis_duration:.2f}ms")
        log_performance(logger, f"[{request_id}] 数据分析", analysis_duration)
        
        # 记录分析结果摘要
        kpi = dashboard_data.get('kpi', {})
        logger.info(f"[{request_id}] 分析结果摘要: "
                   f"总成本={kpi.get('total_cost', 0):.2f}, "
                   f"订单数={kpi.get('total_orders', 0)}, "
                   f"异常数={kpi.get('anomaly_count', 0)}")
        
        # 记录请求成功
        total_duration = (time.time() - start_time) * 1000
        request_logger.log_request_success(request_id, total_duration, "数据分析成功")
        
        return JSONResponse(
            content={
                "success": True,
                "data": dashboard_data,
                "message": "分析完成",
                "request_id": request_id
            }
        )
    
    except Exception as e:
        # 记录错误详情
        error_detail = traceback.format_exc()
        total_duration = (time.time() - start_time) * 1000
        
        logger.error(f"[{request_id}] 数据分析失败: {str(e)}")
        log_exception(logger, f"[{request_id}] 详细错误堆栈", exc_info=True)
        request_logger.log_request_error(request_id, total_duration, str(e))
        
        raise HTTPException(
            status_code=500,
            detail=f"数据分析失败: {str(e)}"
        )
    
    finally:
        # 清理临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.debug(f"[{request_id}] 临时文件已清理: {temp_file_path}")
            except Exception as e:
                logger.error(f"[{request_id}] 清理临时文件失败: {str(e)}")


@app.post("/api/export")
async def export_with_analysis(file: UploadFile = File(...)):
    """
    导出带分析结果的 Excel 文件
    
    接收上传的 .xlsx 文件，追加分析结果 Sheet，返回修改后的文件流
    
    Args:
        file: 上传的 Excel 文件
        
    Returns:
        包含分析结果的 Excel 文件流
    """
    # 生成唯一请求ID
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    # 记录请求开始
    request_logger.log_request_start(request_id, "/api/export", file.filename)
    logger.info(f"[{request_id}] 接收到导出请求，文件名: {file.filename}")
    
    # 验证文件格式
    if not file.filename.endswith('.xlsx'):
        logger.warning(f"[{request_id}] 文件格式不正确: {file.filename}")
        raise HTTPException(
            status_code=400,
            detail="只支持 .xlsx 格式的 Excel 文件"
        )
    
    temp_file = None
    temp_file_path = None
    
    try:
        # 保存上传文件到临时目录
        logger.debug(f"[{request_id}] 开始保存上传文件到临时目录")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        logger.info(f"[{request_id}] 文件已保存到: {temp_file_path}")
        
        # 加载数据
        logger.debug(f"[{request_id}] 开始加载Excel数据")
        load_start = time.time()
        loader = DataLoader(temp_file_path)
        data_sheets = loader.load_all_sheets()
        load_duration = (time.time() - load_start) * 1000
        logger.info(f"[{request_id}] 数据加载完成，耗时: {load_duration:.2f}ms")
        
        # 执行分析
        logger.debug(f"[{request_id}] 开始执行数据分析")
        analysis_start = time.time()
        analyzer = TravelAnalyzer(
            attendance_df=data_sheets['attendance'],
            flight_df=data_sheets['flight'],
            hotel_df=data_sheets['hotel'],
            train_df=data_sheets['train']
        )
        
        # 生成分析数据
        dashboard_data = analyzer.generate_dashboard_data()
        anomalies = dashboard_data.get('anomalies', [])
        analysis_duration = (time.time() - analysis_start) * 1000
        logger.info(f"[{request_id}] 数据分析完成，耗时: {analysis_duration:.2f}ms, "
                   f"发现异常数: {len(anomalies)}")
        
        # 导出 Excel
        logger.debug(f"[{request_id}] 开始生成Excel导出文件")
        export_start = time.time()
        exporter = ExcelExporter(temp_file_path)
        output_stream = exporter.export_with_analysis(dashboard_data, anomalies)
        export_duration = (time.time() - export_start) * 1000
        logger.info(f"[{request_id}] Excel导出完成，耗时: {export_duration:.2f}ms")
        log_performance(logger, f"[{request_id}] Excel导出", export_duration)
        
        # 生成输出文件名
        original_filename = file.filename.replace('.xlsx', '')
        output_filename = f"{original_filename}_分析结果.xlsx"
        logger.info(f"[{request_id}] 输出文件名: {output_filename}")
        
        # 记录请求成功
        total_duration = (time.time() - start_time) * 1000
        request_logger.log_request_success(request_id, total_duration, "Excel导出成功")
        
        # 返回文件流
        return StreamingResponse(
            output_stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}"
            }
        )
    
    except Exception as e:
        # 记录错误详情
        total_duration = (time.time() - start_time) * 1000
        
        logger.error(f"[{request_id}] 文件导出失败: {str(e)}")
        log_exception(logger, f"[{request_id}] 详细错误堆栈", exc_info=True)
        request_logger.log_request_error(request_id, total_duration, str(e))
        
        raise HTTPException(
            status_code=500,
            detail=f"文件导出失败: {str(e)}"
        )
    
    finally:
        # 清理临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.debug(f"[{request_id}] 临时文件已清理: {temp_file_path}")
            except Exception as e:
                logger.error(f"[{request_id}] 清理临时文件失败: {str(e)}")


@app.post("/api/export-ppt")
async def export_ppt(request: Request):
    """
    导出 Dashboard 数据为 PowerPoint 演示文稿

    接收 JSON 格式的数据和图表，生成 PPT 文件

    Request Body (JSON):
    {
        "dashboard_data": {...},  # Dashboard 数据
        "charts": [
            {"title": "部门成本分布", "image": "data:image/png;base64,..."},
            {"title": "项目成本排名", "image": "data:image/png;base64,..."},
            ...
        ]
    }

    Returns:
        PPT 文件流
    """
    # 生成唯一请求ID
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # 记录请求开始
    request_logger.log_request_start(request_id, "/api/export-ppt", "dashboard_data")
    logger.info(f"[{request_id}] 接收到 PPT 导出请求")

    try:
        # 解析请求体
        logger.debug(f"[{request_id}] 开始解析请求体")
        body = await request.json()
        dashboard_data = body.get('dashboard_data', {})
        charts = body.get('charts', [])

        logger.info(f"[{request_id}] 接收到 {len(charts)} 个前端图表（将优先使用数据驱动的内置图表）")

        # 创建 PPT 导出器
        logger.debug(f"[{request_id}] 开始创建 PPT")
        ppt_start = time.time()
        exporter = PPTExporter()

        # 1. 创建 KPI 指标页
        logger.debug(f"[{request_id}] 创建 KPI 指标页")
        kpi_data = {
            'total_cost': dashboard_data.get('kpi', {}).get('total_cost', 0),
            'total_orders': dashboard_data.get('kpi', {}).get('total_orders', 0),
            'anomaly_count': dashboard_data.get('kpi', {}).get('anomaly_count', 0),
            'over_standard_count': dashboard_data.get('kpi', {}).get('over_standard_count', 0),
            'urgent_booking_ratio': dashboard_data.get('kpi', {}).get('urgent_booking_ratio', 0)
        }
        exporter.create_kpi_slide(kpi_data)

        # 2. 创建数据驱动的图表页
        dept_stats = dashboard_data.get('department_metrics', [])
        if dept_stats:
            logger.debug(f"[{request_id}] 创建部门成本分布图表")
            exporter.create_department_cost_chart(dept_stats)

        projects = dashboard_data.get('top_projects', [])
        if projects:
            logger.debug(f"[{request_id}] 创建项目成本排名图表，共 {len(projects)} 条")
            exporter.create_project_cost_chart(projects)

        over_stats = dashboard_data.get('over_standard_breakdown', {})
        if over_stats or kpi_data.get('total_orders'):
            logger.debug(f"[{request_id}] 创建超标订单占比图表")
            exporter.create_over_standard_chart(over_stats, kpi_data.get('total_orders', 0))

        booking_behavior = dashboard_data.get('booking_behavior', {})
        if booking_behavior:
            logger.debug(f"[{request_id}] 创建预订行为占比图表")
            exporter.create_booking_behavior_chart(booking_behavior)

        # 3. 如果有前端截图图表，作为补充附加到 PPT（兼容旧流程）
        for i, chart in enumerate(charts):
            logger.debug(f"[{request_id}] 附加前端图表页 {i+1}/{len(charts)}: {chart.get('title', '')}")
            exporter.create_chart_slide(
                title=chart.get('title', ''),
                chart_image_base64=chart.get('image', '')
            )

        # 4. 创建部门统计表格页
        if dept_stats:
            logger.debug(f"[{request_id}] 创建部门统计表格页，共 {len(dept_stats)} 行")
            headers = ['部门', '成本(元)', '总工时', '涉及成本人员', '饱和度(%)']
            rows = [
                [
                    d.get('一级部门', ''),
                    d.get('总成本', 0),
                    d.get('总工时', 0),
                    d.get('人员数量', 0),
                    d.get('饱和度', 0)
                ]
                for d in dept_stats[:20]  # 限制20行
            ]
            exporter.create_table_slide('部门工时成本概览', headers, rows)

        if projects:
            logger.debug(f"[{request_id}] 创建项目成本表格页，共 {len(projects)} 行")
            headers = ['项目代码', '项目名称', '总成本(元)', '机票成本', '酒店成本', '火车票成本']
            rows = [
                [
                    p.get('项目代码', ''),
                    p.get('项目名称', ''),
                    p.get('总成本', 0),
                    p.get('机票成本', 0),
                    p.get('酒店成本', 0),
                    p.get('火车票成本', 0)
                ]
                for p in projects[:20]  # 限制20行
            ]
            exporter.create_table_slide('项目成本详情 (Top 20)', headers, rows)

        # 5. 创建异常记录表格页（限制前50条，避免PPT过大）
        anomalies = dashboard_data.get('anomalies', [])[:50]
        if anomalies:
            logger.debug(f"[{request_id}] 创建异常记录表格页，共 {len(anomalies)} 行")
            headers = ['异常类型', '姓名', '日期', '部门', '详细说明']
            rows = [
                [
                    a.get('type', ''),
                    a.get('name', ''),
                    a.get('date', ''),
                    a.get('dept', ''),
                    a.get('detail', '')[:80]  # 限制说明长度
                ]
                for a in anomalies
            ]
            exporter.create_table_slide('异常记录详情 (前50条)', headers, rows)

        # 导出为字节流
        logger.debug(f"[{request_id}] 导出 PPT 到字节流")
        output_stream = exporter.export_to_bytes()

        ppt_duration = (time.time() - ppt_start) * 1000
        logger.info(f"[{request_id}] PPT 创建完成，耗时: {ppt_duration:.2f}ms")
        log_performance(logger, f"[{request_id}] PPT生成", ppt_duration)

        # 生成输出文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # 使用 ASCII 文件名避免 header 编码问题
        output_filename = f"CostMatrix_Report_{timestamp}.pptx"
        logger.info(f"[{request_id}] 输出文件名: {output_filename}")

        # 记录请求成功
        total_duration = (time.time() - start_time) * 1000
        request_logger.log_request_success(request_id, total_duration, "PPT导出成功")

        # 返回文件流
        return StreamingResponse(
            output_stream,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}"
            }
        )

    except Exception as e:
        # 记录错误详情
        total_duration = (time.time() - start_time) * 1000

        logger.error(f"[{request_id}] PPT 导出失败: {str(e)}")
        log_exception(logger, f"[{request_id}] 详细错误堆栈", exc_info=True)
        request_logger.log_request_error(request_id, total_duration, str(e))

        raise HTTPException(
            status_code=500,
            detail=f"PPT 导出失败: {str(e)}"
        )


@app.post("/api/preview")
async def preview_data(file: UploadFile = File(...)) -> Dict:
    """
    预览 Excel 数据结构
    
    返回各个 Sheet 的列名和前几行数据，用于调试
    
    Args:
        file: 上传的 Excel 文件
        
    Returns:
        数据预览信息
    """
    # 生成唯一请求ID
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    # 记录请求开始
    request_logger.log_request_start(request_id, "/api/preview", file.filename)
    logger.info(f"[{request_id}] 接收到预览请求，文件名: {file.filename}")
    
    if not file.filename.endswith('.xlsx'):
        logger.warning(f"[{request_id}] 文件格式不正确: {file.filename}")
        raise HTTPException(
            status_code=400,
            detail="只支持 .xlsx 格式的 Excel 文件"
        )
    
    temp_file = None
    temp_file_path = None
    
    try:
        # 保存上传文件
        logger.debug(f"[{request_id}] 开始保存上传文件")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        logger.info(f"[{request_id}] 文件已保存到: {temp_file_path}")
        
        # 加载数据
        logger.debug(f"[{request_id}] 开始加载Excel数据")
        loader = DataLoader(temp_file_path)
        data_sheets = loader.load_all_sheets()
        
        # 构建预览数据
        preview = {}
        for sheet_name, df in data_sheets.items():
            preview[sheet_name] = {
                "columns": df.columns.tolist(),
                "row_count": len(df),
                "sample_data": df.head(3).to_dict('records') if not df.empty else []
            }
            logger.debug(f"[{request_id}] Sheet '{sheet_name}': {len(df)} rows, {len(df.columns)} columns")
        
        # 记录请求成功
        total_duration = (time.time() - start_time) * 1000
        request_logger.log_request_success(request_id, total_duration, "数据预览成功")
        
        return JSONResponse(
            content={
                "success": True,
                "data": preview,
                "message": "数据预览加载成功",
                "request_id": request_id
            }
        )
    
    except Exception as e:
        # 记录错误详情
        total_duration = (time.time() - start_time) * 1000
        
        logger.error(f"[{request_id}] 数据预览失败: {str(e)}")
        log_exception(logger, f"[{request_id}] 详细错误堆栈", exc_info=True)
        request_logger.log_request_error(request_id, total_duration, str(e))
        
        raise HTTPException(
            status_code=500,
            detail=f"数据预览失败: {str(e)}"
        )
    
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.debug(f"[{request_id}] 临时文件已清理: {temp_file_path}")
            except Exception as e:
                logger.error(f"[{request_id}] 清理临时文件失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    
    logger.info("=" * 80)
    logger.info("准备启动 Uvicorn 服务器")
    logger.info("监听地址: 0.0.0.0:8000")
    logger.info("热重载: 已启用")
    logger.info("=" * 80)
    
    # 启动服务器
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式启用热重载
        log_level="info"
    )
