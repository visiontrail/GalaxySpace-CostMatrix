# 日志系统使用指南

## 概述

本系统已集成完整的日志记录功能，所有关键流程和操作都有详细的日志记录，便于问题追溯和性能监控。

## 日志文件位置

所有日志文件存储在 `logs/` 目录下：

```
logs/
├── main.log                # 主程序日志（API请求、路由等）
├── data_loader.log         # 数据加载和清洗日志
├── analysis_service.log    # 数据分析日志
├── export_service.log      # Excel导出日志
└── app.log                 # 通用应用日志
```

## 日志级别

系统支持以下日志级别（从高到低）：

- **ERROR**: 错误信息，包括异常堆栈
- **WARNING**: 警告信息，如数据质量问题
- **INFO**: 重要信息，如请求开始/结束、关键操作完成
- **DEBUG**: 调试信息，如详细的处理步骤

## 日志格式

每条日志包含以下信息：

```
2026-01-05 20:30:45 - [INFO] - [main:analyze_travel_data:75] - [a1b2c3d4] 接收到分析请求，文件名: data.xlsx
```

格式说明：
- 时间戳: `2026-01-05 20:30:45`
- 日志级别: `[INFO]`
- 模块位置: `[main:analyze_travel_data:75]` (模块名:函数名:行号)
- 日志内容: `[a1b2c3d4] 接收到分析请求...`
- 请求ID: `[a1b2c3d4]` (8位唯一标识符，用于追踪同一请求的所有日志)

## 日志记录内容

### 1. API请求日志

每个API请求都会记录：

- **请求开始**: 请求ID、端点、文件名、文件大小
- **处理步骤**: 
  - 文件保存
  - 数据加载（耗时）
  - 数据行数统计
  - 分析执行（耗时）
  - 结果生成
- **请求结束**: 总耗时、成功/失败状态
- **错误详情**: 完整的异常堆栈（如果失败）

示例：
```
2026-01-05 20:30:45 - [INFO] - [main:analyze_travel_data:75] - [a1b2c3d4] 接收到分析请求，文件名: data.xlsx
2026-01-05 20:30:45 - [INFO] - [main:analyze_travel_data:93] - [a1b2c3d4] 文件已保存到: /tmp/tmpxxx.xlsx, 大小: 524288 bytes
2026-01-05 20:30:46 - [INFO] - [main:analyze_travel_data:102] - [a1b2c3d4] 数据加载完成，耗时: 850.25ms
2026-01-05 20:30:46 - [INFO] - [main:analyze_travel_data:123] - [a1b2c3d4] 数据分析完成，耗时: 1250.50ms
2026-01-05 20:30:46 - [INFO] - [RequestLogger:log_request_success] - [REQUEST_SUCCESS] RequestID: a1b2c3d4 | Duration: 2150.75ms | Message: 数据分析成功
```

### 2. 数据加载日志

记录Excel文件的读取和数据清洗过程：

- 各Sheet的加载（行数、列数）
- 数据类型转换
- 无效数据警告（如无效日期、工时为0）
- 数据填充和清洗统计

示例：
```
2026-01-05 20:30:45 - [INFO] - [data_loader:load_all_sheets:42] - 考勤数据加载完成，行数: 1250, 列数: 15
2026-01-05 20:30:45 - [WARNING] - [data_loader:_clean_attendance_data:89] - 发现 5 条无效日期记录
2026-01-05 20:30:45 - [INFO] - [data_loader:_clean_travel_data:126] - 授信金额汇总: ¥125,350.00
```

### 3. 数据分析日志

记录所有分析算法的执行过程：

- 项目成本归集（项目数、Top项目）
- 异常检测（异常数量、类型分布）
- 预订行为分析（订单统计、紧急预订比例）
- Dashboard数据生成

示例：
```
2026-01-05 20:30:46 - [INFO] - [analysis_service:aggregate_project_cost:121] - 项目成本归集完成，共 25 个项目
2026-01-05 20:30:46 - [INFO] - [analysis_service:cross_check_anomalies:215] - 异常检测完成，发现 12 条异常记录
2026-01-05 20:30:46 - [DEBUG] - [analysis_service:cross_check_anomalies:217] - 其中冲突类型: 8, 无消费类型: 4
```

### 4. Excel导出日志

记录Excel文件的生成和导出过程：

- 工作簿加载
- 工作表创建
- 数据写入统计
- 文件大小

示例：
```
2026-01-05 20:30:46 - [INFO] - [export_service:load_workbook:35] - Excel工作簿加载成功，共 4 个工作表
2026-01-05 20:30:46 - [INFO] - [export_service:add_dashboard_sheet:185] - Dashboard_Data工作表添加完成: KPI指标已添加, Top项目=10, 部门指标=8
2026-01-05 20:30:46 - [INFO] - [export_service:save_to_bytes:281] - 工作簿已保存到内存，大小: 654321 bytes (638.99 KB)
```

## 性能监控

系统会记录关键操作的耗时：

```
2026-01-05 20:30:46 - [INFO] - [logger_config:log_performance:125] - [PERFORMANCE] Operation: [a1b2c3d4] 数据加载 | Duration: 850.25ms
2026-01-05 20:30:46 - [INFO] - [logger_config:log_performance:125] - [PERFORMANCE] Operation: [a1b2c3d4] 数据分析 | Duration: 1250.50ms
```

## 日志轮转

日志文件会自动轮转，避免单个文件过大：

- 单个日志文件最大: **10MB**
- 保留备份数量: **5个**
- 旧日志文件自动重命名: `main.log.1`, `main.log.2`, ...

## 查看日志的方法

### 1. 实时查看日志（跟踪最新日志）

```bash
# 查看主程序日志
tail -f logs/main.log

# 查看所有日志
tail -f logs/*.log
```

### 2. 查找特定请求的所有日志

```bash
# 使用请求ID查找
grep "a1b2c3d4" logs/*.log
```

### 3. 查找错误日志

```bash
# 查找所有错误
grep "ERROR" logs/*.log

# 查找特定模块的错误
grep "ERROR" logs/analysis_service.log
```

### 4. 统计分析

```bash
# 统计各级别日志数量
grep -c "ERROR" logs/main.log
grep -c "WARNING" logs/main.log

# 查看最近的错误
grep "ERROR" logs/*.log | tail -20
```

## 故障排查示例

### 场景1: API请求失败

1. 找到请求ID（从前端返回的响应中获取，或查看日志）
2. 使用请求ID搜索所有相关日志：
   ```bash
   grep "a1b2c3d4" logs/*.log
   ```
3. 查看错误堆栈和上下文信息

### 场景2: 数据加载问题

1. 查看data_loader.log：
   ```bash
   grep "ERROR\|WARNING" logs/data_loader.log | tail -50
   ```
2. 检查是否有"无效数据"的警告
3. 确认数据行数和列数是否正常

### 场景3: 性能问题

1. 查找性能日志：
   ```bash
   grep "PERFORMANCE" logs/main.log | tail -20
   ```
2. 分析哪个步骤耗时最长
3. 检查数据量是否异常

## 日志配置修改

如需调整日志配置，编辑 `logger_config.py`：

```python
# 修改日志级别
logger = setup_logger("main", "main.log", level=logging.DEBUG)

# 修改文件大小限制（字节）
max_bytes = 20 * 1024 * 1024  # 20MB

# 修改备份数量
backup_count = 10
```

## 生产环境建议

1. **定期清理日志**: 建议定期归档或删除旧日志文件
2. **监控日志大小**: 确保磁盘空间充足
3. **设置日志告警**: 可集成日志监控工具（如ELK、Prometheus）
4. **敏感信息**: 确保日志中不包含敏感数据（密码、密钥等）

## 常见问题

### Q: 日志文件太大怎么办？

A: 系统已配置自动轮转，超过10MB会自动切割。如需手动清理：
```bash
# 删除旧备份
rm logs/*.log.[3-9]

# 清空当前日志（谨慎！）
> logs/main.log
```

### Q: 如何提高日志级别以减少日志量？

A: 修改 `logger_config.py` 中的日志级别为 `logging.WARNING` 或 `logging.ERROR`

### Q: 日志没有生成怎么办？

A: 检查：
1. `logs/` 目录是否存在且有写入权限
2. 程序是否正常启动
3. 控制台是否有错误信息

## 联系支持

如有日志相关问题，请提供：
- 相关日志文件
- 请求ID（如果是API相关问题）
- 问题复现步骤

