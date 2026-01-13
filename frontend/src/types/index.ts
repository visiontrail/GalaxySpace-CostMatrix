/**
 * CorpPilot 前端类型定义
 * 完全对应后端 POST /api/analyze 的返回结构
 */

// ============ 汇总统计 ============
export interface Summary {
  total_cost: number        // 总成本
  avg_work_hours: number    // 平均工时
  anomaly_count: number     // 异常数量
  total_orders?: number     // 订单总数
  order_breakdown?: {
    total?: number
    flight?: number
    hotel?: number
    train?: number
  }
  over_standard_count?: number  // 超标订单数
  over_standard_breakdown?: {
    total?: number
    flight?: number
    hotel?: number
    train?: number
  }
  flight_over_type_breakdown?: Record<string, number>  // 机票超标类型分布
  total_project_count?: number  // 项目总数
}

// ============ 部门统计 ============
export interface DepartmentStat {
  dept: string              // 部门名称
  cost: number              // 部门成本
  avg_hours: number         // 平均工时
  headcount: number         // 人数
}

// ============ 项目 Top10 ============
export interface ProjectTop10 {
  code: string              // 项目代码
  name: string              // 项目名称
  cost: number              // 项目成本
}

// ============ 项目详细信息 ============
export interface ProjectDetail {
  code: string              // 项目代码
  name: string              // 项目名称
  total_cost: number        // 总成本
  flight_cost: number       // 机票成本
  hotel_cost: number        // 酒店成本
  train_cost: number        // 火车票成本
  record_count: number      // 订单记录数
  flight_count: number      // 机票订单数
  hotel_count: number       // 酒店订单数
  train_count: number       // 火车票订单数
  person_count: number      // 涉及人数
  person_list: string[]     // 涉及人员列表
  date_range: {
    start: string           // 最早日期
    end: string             // 最晚日期
  }
  over_standard_count?: number  // 超标订单数
}

// ============ 项目订单记录 ============
export interface ProjectOrderRecord {
  id: string                // 记录ID
  project_code: string      // 项目代码
  project_name: string      // 项目名称
  person: string            // 姓名
  department?: string       // 部门
  type: 'flight' | 'hotel' | 'train'  // 订单类型
  amount: number            // 金额
  date: string              // 日期
  is_over_standard?: boolean  // 是否超标
  over_type?: string        // 超标类型
  advance_days?: number     // 提前预订天数
}

// ============ 异常记录 ============
export interface Anomaly {
  date: string              // 日期
  name: string              // 姓名
  dept: string              // 部门
  type: string              // 异常类型：Conflict, Missing, etc.
  detail: string            // 详细说明
}

// ============ 完整分析结果 ============
export interface AnalysisResult {
  summary: Summary
  department_stats: DepartmentStat[]
  project_top10: ProjectTop10[]
  anomalies: Anomaly[]
}

// ============ API 响应包装 ============
export interface ApiResponse<T = any> {
  success: boolean
  message: string
  data?: T
}

// ============ 上传响应 ============
export interface UploadRecord {
  file_path: string
  file_name: string
  file_size: number
  sheets: string[]
  upload_time?: string | null
  parsed?: boolean
  last_analyzed_at?: string | null
  exists?: boolean
}

export type UploadResponse = UploadRecord
