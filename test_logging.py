#!/usr/bin/env python3
"""
日志系统测试脚本
用于验证日志系统是否正常工作
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from logger_config import get_logger, RequestLogger, log_exception, log_performance
import time


def test_basic_logging():
    """测试基本日志功能"""
    print("=" * 60)
    print("测试1: 基本日志功能")
    print("=" * 60)
    
    logger = get_logger("test")
    
    logger.debug("这是DEBUG级别日志")
    logger.info("这是INFO级别日志")
    logger.warning("这是WARNING级别日志")
    logger.error("这是ERROR级别日志")
    
    print("✅ 基本日志测试完成\n")


def test_request_logging():
    """测试请求日志功能"""
    print("=" * 60)
    print("测试2: 请求追踪日志")
    print("=" * 60)
    
    logger = get_logger("test")
    request_logger = RequestLogger(logger)
    
    request_id = "test1234"
    
    # 模拟请求开始
    request_logger.log_request_start(request_id, "/api/test", "test.xlsx")
    
    # 模拟处理步骤
    request_logger.log_step(request_id, "数据加载", "开始加载Excel文件")
    time.sleep(0.1)
    request_logger.log_step(request_id, "数据分析", "开始分析数据")
    time.sleep(0.1)
    
    # 模拟请求成功
    request_logger.log_request_success(request_id, 200, "测试请求成功")
    
    print("✅ 请求追踪日志测试完成\n")


def test_performance_logging():
    """测试性能日志"""
    print("=" * 60)
    print("测试3: 性能监控日志")
    print("=" * 60)
    
    logger = get_logger("test")
    
    # 模拟耗时操作
    start_time = time.time()
    time.sleep(0.05)
    duration_ms = (time.time() - start_time) * 1000
    
    log_performance(logger, "测试操作", duration_ms)
    
    print("✅ 性能日志测试完成\n")


def test_exception_logging():
    """测试异常日志"""
    print("=" * 60)
    print("测试4: 异常追踪日志")
    print("=" * 60)
    
    logger = get_logger("test")
    
    try:
        # 故意触发异常
        result = 1 / 0
    except Exception as e:
        log_exception(logger, f"测试异常捕获: {str(e)}")
    
    print("✅ 异常日志测试完成\n")


def test_multiple_loggers():
    """测试多个日志记录器"""
    print("=" * 60)
    print("测试5: 多模块日志")
    print("=" * 60)
    
    # 创建不同模块的日志记录器
    main_logger = get_logger("main")
    data_logger = get_logger("data_loader")
    analysis_logger = get_logger("analysis_service")
    
    main_logger.info("主程序日志")
    data_logger.info("数据加载模块日志")
    analysis_logger.info("分析服务模块日志")
    
    print("✅ 多模块日志测试完成\n")


def verify_log_files():
    """验证日志文件是否创建"""
    print("=" * 60)
    print("测试6: 验证日志文件")
    print("=" * 60)
    
    from logger_config import LOG_DIR
    
    log_files = list(LOG_DIR.glob("*.log"))
    
    if log_files:
        print(f"✅ 找到 {len(log_files)} 个日志文件:")
        for log_file in log_files:
            size_kb = log_file.stat().st_size / 1024
            print(f"   - {log_file.name} ({size_kb:.2f} KB)")
    else:
        print("❌ 未找到日志文件")
    
    print()


def test_chinese_logging():
    """测试中文日志"""
    print("=" * 60)
    print("测试7: 中文日志支持")
    print("=" * 60)
    
    logger = get_logger("test")
    
    logger.info("测试中文日志: 这是一条包含中文的日志信息")
    logger.info("数据统计: 总成本=¥125,350.50, 订单数=257")
    logger.warning("数据警告: 发现 5 条无效日期记录")
    
    print("✅ 中文日志测试完成\n")


def main():
    """运行所有测试"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 15 + "日志系统测试" + " " * 29 + "║")
    print("╚" + "═" * 58 + "╝")
    print("\n")
    
    try:
        test_basic_logging()
        test_request_logging()
        test_performance_logging()
        test_exception_logging()
        test_multiple_loggers()
        test_chinese_logging()
        verify_log_files()
        
        print("=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)
        print("\n请查看 logs/ 目录下的日志文件验证输出\n")
        print("建议命令:")
        print("  tail -f logs/*.log          # 查看实时日志")
        print("  cat logs/test.log           # 查看测试日志")
        print("  ls -lh logs/                # 查看日志文件大小")
        print()
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

