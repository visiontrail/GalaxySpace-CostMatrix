/**
 * API 服务层
 * 对接后端 FastAPI 接口
 */
import axios, { AxiosInstance } from 'axios'
import type {
  ApiResponse,
  AnalysisResult,
  UploadResponse,
  UploadRecord,
  ProjectDetail,
  ProjectOrderRecord,
  DepartmentHierarchy,
  DepartmentListItem,
  DepartmentDetailMetrics,
} from '@/types'

// API 基础地址
const API_BASE_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')

// 创建 axios 实例
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5分钟超时
  headers: {
    'Content-Type': 'application/json',
  },
})

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    console.error('API Error:', message)
    return Promise.reject(new Error(message))
  }
)

// ============ API 方法 ============

/**
 * 上传 Excel 文件
 * @param file 文件对象
 * @returns 上传结果（包含文件路径）
 */
export const uploadFile = async (file: File): Promise<ApiResponse<UploadResponse>> => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await axios.post<ApiResponse<UploadResponse>>(
    `${API_BASE_URL}/upload`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      // 上传文件可能较大，延长超时以避免 60s 限制
      timeout: 300000, // 5 分钟
    }
  )

  return response.data
}

/**
 * 分析 Excel 文件
 * POST /api/analyze
 * @param filePath 文件路径
 * @returns 分析结果
 */
export const analyzeExcel = async (filePath: string): Promise<ApiResponse<AnalysisResult>> => {
  return apiClient.post('/analyze', null, {
    params: { file_path: filePath },
  }) as Promise<ApiResponse<AnalysisResult>>
}

/**
 * 获取已上传文件列表
 */
export const listUploads = async (): Promise<ApiResponse<UploadRecord[]>> => {
  return apiClient.get('/uploads') as Promise<ApiResponse<UploadRecord[]>>
}

/**
 * 导出分析结果为 Excel
 * @param filePath 原始文件路径
 * @returns Excel 文件 Blob
 */
export const exportResults = async (filePath: string): Promise<Blob> => {
  const response = await axios.post(
    `${API_BASE_URL}/export`,
    null,
    {
      params: { file_path: filePath },
      responseType: 'blob',
      timeout: 120000, // 导出超时 2 分钟
    }
  )

  return response.data
}

/**
 * 导出 Dashboard 数据为 PPT
 * @param dashboardData Dashboard 分析数据
 * @param charts 图表图片数组
 * @returns PPT 文件 Blob
 */
export const exportPpt = async (
  dashboardData: AnalysisResult,
  charts: Array<{ title: string; image: string }>
): Promise<Blob> => {
  const response = await axios.post(
    `${API_BASE_URL}/export-ppt`,
    {
      dashboard_data: dashboardData,
      charts: charts
    },
    {
      responseType: 'blob',
      timeout: 180000, // 导出超时 3 分钟
      headers: {
        'Content-Type': 'application/json'
      }
    }
  )

  return response.data
}

/**
 * 健康检查
 * @returns 健康状态
 */
export const healthCheck = async (): Promise<any> => {
  return apiClient.get('/health')
}

/**
 * 删除文件
 * @param filePath 文件路径
 * @returns 删除结果
 */
export const deleteFile = async (filePath: string): Promise<ApiResponse> => {
  return apiClient.delete(`/files/${encodeURIComponent(filePath)}`)
}

/**
 * 清除后端持久化数据
 */
export const clearData = async (filePath: string): Promise<ApiResponse> => {
  return apiClient.delete('/data', { params: { file_path: filePath } })
}

/**
 * 获取所有项目的详细信息
 * @param filePath 文件路径
 * @returns 项目详情列表
 */
export const getAllProjects = async (filePath: string): Promise<ApiResponse<{
  projects: ProjectDetail[]
  total_count: number
}>> => {
  return apiClient.get('/projects', {
    params: { file_path: filePath }
  }) as Promise<ApiResponse<{
    projects: ProjectDetail[]
    total_count: number
  }>>
}

/**
 * 获取指定项目的所有订单记录
 * @param filePath 文件路径
 * @param projectCode 项目代码
 * @returns 项目订单记录列表
 */
export const getProjectOrders = async (
  filePath: string,
  projectCode: string
): Promise<ApiResponse<{
  project_code: string
  orders: ProjectOrderRecord[]
  total_count: number
}>> => {
  return apiClient.get(`/projects/${encodeURIComponent(projectCode)}/orders`, {
    params: { file_path: filePath }
  }) as Promise<ApiResponse<{
    project_code: string
    orders: ProjectOrderRecord[]
    total_count: number
  }>>
}

/**
 * 获取部门层级结构
 * @param filePath 文件路径
 * @returns 部门层级结构
 */
export const getDepartmentHierarchy = async (
  filePath: string
): Promise<ApiResponse<DepartmentHierarchy>> => {
  return apiClient.get('/departments/hierarchy', {
    params: { file_path: filePath }
  }) as Promise<ApiResponse<DepartmentHierarchy>>
}

/**
 * 获取部门列表
 * @param filePath 文件路径
 * @param level 部门层级 (1=一级, 2=二级, 3=三级)
 * @param parent 父部门名称（level>1时必需）
 * @returns 部门列表
 */
export const getDepartmentList = async (
  filePath: string,
  level: number,
  parent?: string
): Promise<ApiResponse<{
  level: number
  parent?: string
  departments: DepartmentListItem[]
  total_count: number
}>> => {
  return apiClient.get('/departments/list', {
    params: { file_path: filePath, level, parent }
  }) as Promise<ApiResponse<{
    level: number
    parent?: string
    departments: DepartmentListItem[]
    total_count: number
  }>>
}

/**
 * 获取指定部门的详细指标
 * @param filePath 文件路径
 * @param departmentName 部门名称
 * @param level 部门层级 (1=一级, 2=二级, 3=三级，默认3)
 * @returns 部门详细指标
 */
export const getDepartmentDetails = async (
  filePath: string,
  departmentName: string,
  level: number = 3
): Promise<ApiResponse<DepartmentDetailMetrics>> => {
  return apiClient.get('/departments/details', {
    params: { file_path: filePath, department_name: departmentName, level }
  }) as Promise<ApiResponse<DepartmentDetailMetrics>>
}

/**
 * 获取一级部门的汇总统计数据（用于二级部门表格下方的统计展示）
 * @param filePath 文件路径
 * @param level1Name 一级部门名称
 * @returns 一级部门统计数据
 */
export const getLevel1DepartmentStatistics = async (
  filePath: string,
  level1Name: string
): Promise<ApiResponse<{
  department_name: string
  total_travel_cost: number
  attendance_days_distribution: Record<string, number>
  travel_ranking: Array<{ name: string; value: number; detail?: string }>
  avg_hours_ranking: Array<{ name: string; value: number; detail?: string }>
  level2_department_stats: Array<{
    name: string
    person_count: number
    avg_work_hours: number
    workday_attendance_days: number
    weekend_work_days: number
    weekend_attendance_count: number
    travel_days: number
    leave_days: number
    anomaly_days: number
    late_after_1930_count: number
    total_cost: number
  }>
}>> => {
  return apiClient.get('/departments/level1/statistics', {
    params: { file_path: filePath, level1_name: level1Name }
  }) as Promise<ApiResponse<{
    department_name: string
    total_travel_cost: number
    attendance_days_distribution: Record<string, number>
    travel_ranking: Array<{ name: string; value: number; detail?: string }>
    avg_hours_ranking: Array<{ name: string; value: number; detail?: string }>
    level2_department_stats: Array<{
      name: string
      person_count: number
      avg_work_hours: number
      workday_attendance_days: number
      weekend_work_days: number
      weekend_attendance_count: number
      travel_days: number
      leave_days: number
      anomaly_days: number
      late_after_1930_count: number
      total_cost: number
    }>
  }>>
}

// 导出 axios 实例供特殊情况使用
export default apiClient
