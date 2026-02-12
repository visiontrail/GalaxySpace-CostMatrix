/**
 * 模拟数据 - 用于开发和测试
 */
import type { AnalysisResult } from '@/types'

export const mockAnalysisResult: AnalysisResult = {
  summary: {
    total_cost: 1250000,
    avg_work_hours: 9.5,
    anomaly_count: 42,
    total_orders: 320,
    order_breakdown: {
      total: 320,
      flight: 140,
      hotel: 100,
      train: 80
    },
    over_standard_count: 18,
    over_standard_breakdown: {
      total: 18,
      flight: 10,
      hotel: 5,
      train: 3
    },
    flight_over_type_breakdown: {
      '超折扣': 6,
      '超时间': 4
    }
  },
  department_stats: [
    {
      dept: '研发部',
      cost: 450000,
      avg_hours: 10.2,
      headcount: 50,
      holiday_avg_hours: 12.5
    },
    {
      dept: '市场部',
      cost: 280000,
      avg_hours: 9.1,
      headcount: 25,
      holiday_avg_hours: 10.8
    },
    {
      dept: '销售部',
      cost: 320000,
      avg_hours: 8.8,
      headcount: 35,
      holiday_avg_hours: 9.5
    },
    {
      dept: '行政部',
      cost: 80000,
      avg_hours: 8.5,
      headcount: 15,
      holiday_avg_hours: 8.8
    },
    {
      dept: '财务部',
      cost: 60000,
      avg_hours: 8.3,
      headcount: 10,
      holiday_avg_hours: 8.5
    },
    {
      dept: '人力资源部',
      cost: 40000,
      avg_hours: 8.4,
      headcount: 8,
      holiday_avg_hours: 8.6
    },
    {
      dept: '技术支持部',
      cost: 120000,
      avg_hours: 9.6,
      headcount: 20,
      holiday_avg_hours: 10.2
    },
    {
      dept: '运营部',
      cost: 150000,
      avg_hours: 9.2,
      headcount: 22,
      holiday_avg_hours: 9.8
    }
  ],
  project_top10: [
    { code: '0501', name: '灵犀卫星', cost: 300000 },
    { code: '0502', name: '星链计划', cost: 280000 },
    { code: '0503', name: '天宫空间站对接', cost: 250000 },
    { code: '0401', name: '5G基站建设', cost: 180000 },
    { code: '0301', name: '智慧城市项目', cost: 150000 },
    { code: '0302', name: '物联网平台', cost: 120000 },
    { code: '0201', name: '大数据分析系统', cost: 100000 },
    { code: '0202', name: 'AI算法优化', cost: 85000 },
    { code: '0103', name: '云计算平台', cost: 70000 },
    { code: '0104', name: '区块链应用', cost: 65000 }
  ],
  anomalies: [
    {
      date: '2025-08-01',
      name: '张三',
      dept: '行政部',
      type: 'Conflict',
      detail: '考勤在岗但有酒店入住记录'
    },
    {
      date: '2025-08-03',
      name: '李四',
      dept: '研发部',
      type: 'Missing',
      detail: '有差旅记录但无考勤数据'
    },
    {
      date: '2025-08-05',
      name: '王五',
      dept: '销售部',
      type: 'Conflict',
      detail: '考勤状态为出差但无差旅预订记录'
    },
    {
      date: '2025-08-07',
      name: '赵六',
      dept: '市场部',
      type: 'Duplicate',
      detail: '同一天有多条重复的差旅记录'
    },
    {
      date: '2025-08-10',
      name: '钱七',
      dept: '研发部',
      type: 'Conflict',
      detail: '考勤显示请假但有机票预订'
    },
    {
      date: '2025-08-12',
      name: '孙八',
      dept: '技术支持部',
      type: 'Invalid',
      detail: '差旅费用异常（超出正常范围）'
    },
    {
      date: '2025-08-15',
      name: '周九',
      dept: '运营部',
      type: 'Conflict',
      detail: '考勤在岗但有火车票记录'
    },
    {
      date: '2025-08-18',
      name: '吴十',
      dept: '财务部',
      type: 'Missing',
      detail: '出差期间无酒店入住记录'
    },
    {
      date: '2025-08-20',
      name: '郑十一',
      dept: '行政部',
      type: 'Conflict',
      detail: '考勤状态冲突：同时标记为在岗和出差'
    },
    {
      date: '2025-08-22',
      name: '王十二',
      dept: '销售部',
      type: 'Invalid',
      detail: '差旅时间与考勤时间不匹配'
    }
  ]
}

/**
 * 将模拟数据存储到 localStorage
 */
export const loadMockData = () => {
  localStorage.setItem('dashboard_data', JSON.stringify(mockAnalysisResult))
  localStorage.setItem('current_file', 'mock_data.xlsx')
  console.log('✅ 模拟数据已加载')
}

/**
 * 清除 localStorage 中的数据
 */
export const clearMockData = () => {
  localStorage.removeItem('dashboard_data')
  localStorage.removeItem('current_file')
  console.log('🗑️ 数据已清除')
}

