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
  UserInfo,
  AuthResponse,
  CreateUserPayload,
  ChangePasswordPayload,
  UpdateUserPayload,
} from '@/types'

// API 基础地址
const API_BASE_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')
 
type DataAxiosInstance = Omit<AxiosInstance, 'request' | 'get' | 'delete' | 'post' | 'put'> & {
  request<T = any>(config: any): Promise<T>
  get<T = any>(url: string, config?: any): Promise<T>
  delete<T = any>(url: string, config?: any): Promise<T>
  post<T = any>(url: string, data?: any, config?: any): Promise<T>
  put<T = any>(url: string, data?: any, config?: any): Promise<T>
}

// 创建 axios 实例
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000, // 5分钟超时
  headers: {
    'Content-Type': 'application/json',
  },
}) as unknown as DataAxiosInstance

// 请求拦截：附加 Token
apiClient.interceptors.request.use((config: any) => {
  const token = localStorage.getItem('cm_auth_token')
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'
    console.error('API Error:', message)
    const err = new Error(message)
    ;(err as any).response = error.response
    ;(err as any).status = error.response?.status
    if (error.response?.status === 401) {
      // 清空失效的 token，交由前端路由重定向
      localStorage.removeItem('cm_auth_token')
    }
    return Promise.reject(err)
  }
)

// ============ API 方法 ============

/**
 * 上传 Excel 文件
 * @param file 文件对象
 * @returns 上传结果（包含文件路径和任务ID）
 */
export const uploadFile = async (file: File): Promise<ApiResponse<UploadResponse>> => {
  const formData = new FormData()
  formData.append('file', file)

  return apiClient.post<ApiResponse<UploadResponse>>(
    '/upload',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  )
}

/**
 * 获取上传进度
 * @param taskId 任务ID
 * @returns 上传进度信息
 */
export const getUploadProgress = async (taskId: string): Promise<ApiResponse<{
  task_id: string
  file_name: string
  status: string
  progress: number
  current_step: string
  steps: Array<{ step: string; completed_at: string }>
  error: string | null
  result?: any
}>> => {
  return apiClient.get<ApiResponse<{
    task_id: string
    file_name: string
    status: string
    progress: number
    current_step: string
    steps: Array<{ step: string; completed_at: string }>
    error: string | null
    result?: any
  }>>(`/progress/${encodeURIComponent(taskId)}`)
}

/**
 * 获取缓存的分析结果
 * @param fileName 文件名 (不含路径和扩展名)
 * @returns 缓存的分析结果
 */
export const getCache = async (fileName: string): Promise<ApiResponse<AnalysisResult>> => {
  return apiClient.get<ApiResponse<AnalysisResult>>(`/cache/${encodeURIComponent(fileName)}`)
}

/**
 * 获取已上传文件列表
 */
export const listUploads = async (): Promise<ApiResponse<UploadRecord[]>> => {
  return apiClient.get<ApiResponse<UploadRecord[]>>('/uploads')
}

/**
 * 获取所有可用的月份列表（跨所有文件）
 */
export const getAvailableMonths = async (): Promise<ApiResponse<string[]>> => {
  return apiClient.get<ApiResponse<string[]>>('/months')
}

/**
 * 删除指定月份的所有数据
 * @param month 月份 (YYYY-MM格式)
 * @returns 删除结果
 */
export const deleteMonth = async (month: string): Promise<ApiResponse<{
  deleted_uploads: string[]
  deleted_attendance: number
  deleted_travel: number
  deleted_anomalies: number
  deleted_files: string[]
}>> => {
  return apiClient.delete<ApiResponse<{
    deleted_uploads: string[]
    deleted_attendance: number
    deleted_travel: number
    deleted_anomalies: number
    deleted_files: string[]
  }>>(`/months/${encodeURIComponent(month)}`)
}

/**
 * 分析 Excel 文件
 * POST /api/analyze
 * @param filePath 文件路径（可选，不提供则从数据库读取）
 * @param options 可选参数
 * @param options.months 月份列表 (例如: ["2025-01", "2025-02"])
 * @param options.quarter 季度 (1, 2, 3, 4)
 * @param options.year 年份 (例如: 2025)
 * @returns 分析结果
 */
export const analyzeExcel = async (
  filePath: string | undefined,
  options?: {
    months?: string[]
    quarter?: number
    year?: number
  }
): Promise<ApiResponse<AnalysisResult>> => {
  const params: Record<string, string | number> = {}

  if (filePath) {
    params.file_path = filePath
  }

  if (options?.months && options.months.length > 0) {
    params.months = options.months.join(',')
  } else if (options?.quarter && options?.year) {
    params.quarter = options.quarter
    params.year = options.year
  } else if (options?.year) {
    params.year = options.year
  }

  return apiClient.post<ApiResponse<AnalysisResult>>('/analyze', null, { params })
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
      timeout: 120000,
    }
  )

  return response.data
}

/**
 * 导出 Dashboard 数据为 PPT
 * @param dashboardData Dashboard 分析结果
 * @param charts 前端导出的图表图片（base64 dataURL）
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
      charts,
    },
    {
      responseType: 'blob',
      timeout: 300000,
      headers: {
        'Content-Type': 'application/json',
      },
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

// ============ 认证与用户 ============
export const login = async (payload: { username: string; password: string }): Promise<AuthResponse> => {
  return apiClient.post<AuthResponse>('/login', payload)
}

export const fetchCurrentUser = async (): Promise<UserInfo> => {
  return apiClient.get<UserInfo>('/me')
}

export const listUsers = async (): Promise<UserInfo[]> => {
  return apiClient.get<UserInfo[]>('/users')
}

export const createUser = async (payload: CreateUserPayload): Promise<UserInfo> => {
  return apiClient.post<UserInfo>('/users', payload)
}

export const updateUser = async (username: string, payload: UpdateUserPayload): Promise<UserInfo> => {
  return apiClient.put<UserInfo>(`/users/${encodeURIComponent(username)}`, payload)
}

export const deleteUser = async (username: string): Promise<ApiResponse> => {
  return apiClient.delete<ApiResponse>(`/users/${encodeURIComponent(username)}`)
}

export const changePassword = async (payload: ChangePasswordPayload): Promise<ApiResponse> => {
  return apiClient.post<ApiResponse>('/change-password', payload)
}

/**
 * 获取所有项目的详细信息
 * @param filePath 文件路径（可选，不提供则从数据库读取）
 * @param months 月份列表（数据库模式下使用）
 * @returns 项目详情列表
 */
export const getAllProjects = async (
  filePath: string,
  months?: string[]
): Promise<ApiResponse<{
  projects: any[]
  total_count: number
}>> => {
  const params: Record<string, any> = {}
  if (filePath) {
    params.file_path = filePath
  }
  if (months && months.length > 0) {
    params.months = months.join(',')
  }

  return apiClient.get<ApiResponse<{
    projects: any[]
    total_count: number
  }>>('/projects', { params })
}

/**
 * 获取指定项目的所有订单记录
 * @param filePath 文件路径（可选，不提供则从数据库读取）
 * @param projectCode 项目代码
 * @param months 月份列表（数据库模式下使用）
 * @returns 项目订单记录列表
 */
export const getProjectOrders = async (
  filePath: string,
  projectCode: string,
  months?: string[]
): Promise<ApiResponse<{
  project_code: string
  orders: any[]
  total_count: number
}>> => {
  const params: Record<string, any> = {}
  if (filePath) {
    params.file_path = filePath
  }
  if (months && months.length > 0) {
    params.months = months.join(',')
  }

  return apiClient.get<ApiResponse<{
    project_code: string
    orders: any[]
    total_count: number
  }>>(`/projects/${encodeURIComponent(projectCode)}/orders`, { params })
}

/**
 * 获取部门层级结构
 * @param filePath 文件路径
 * @returns 部门层级结构
 */
export const getDepartmentHierarchy = async (
  filePath: string
): Promise<ApiResponse<{
  level1: string[]
  level2: Record<string, string[]>
  level3: Record<string, string[]>
}>> => {
  return apiClient.get<ApiResponse<{
    level1: string[]
    level2: Record<string, string[]>
    level3: Record<string, string[]>
  }>>('/departments/hierarchy', {
    params: { file_path: filePath }
  })
}

/**
 * 获取部门列表
 * @param filePath 文件路径（可选，不提供则从数据库读取）
 * @param level 部门层级 (1=一级, 2=二级, 3=三级)
 * @param parent 父部门名称（level>1时必需）
 * @param months 月份列表（数据库模式下使用）
 * @returns 部门列表
 */
export const getDepartmentList = async (
  filePath: string,
  level: number,
  parent?: string,
  months?: string[]
): Promise<ApiResponse<{
  level: number
  parent?: string
  departments: any[]
  total_count: number
}>> => {
  const params: Record<string, any> = { level }
  if (filePath) {
    params.file_path = filePath
  }
  if (parent) {
    params.parent = parent
  }
  if (months && months.length > 0) {
    params.months = months.join(',')
  }

  return apiClient.get<ApiResponse<{
    level: number
    parent?: string
    departments: any[]
    total_count: number
  }>>('/departments/list', { params })
}

/**
 * 获取指定部门的详细指标
 * @param filePath 文件路径（可选，不提供则从数据库读取）
 * @param departmentName 部门名称
 * @param level 部门层级 (1=一级, 2=二级, 3=三级，默认3)
 * @param months 月份列表（数据库模式下使用）
 * @returns 部门详细指标
 */
export const getDepartmentDetails = async (
  filePath: string,
  departmentName: string,
  level: number = 3,
  months?: string[]
): Promise<ApiResponse<any>> => {
  const params: Record<string, any> = { department_name: departmentName, level }
  if (filePath) {
    params.file_path = filePath
  }
  if (months && months.length > 0) {
    params.months = months.join(',')
  }

  return apiClient.get<ApiResponse<any>>('/departments/details', { params })
}

/**
 * 获取一级部门的汇总统计数据（用于二级部门表格下方的统计展示）
 * @param filePath 文件路径（可选，不提供则从数据库读取）
 * @param level1Name 一级部门名称
 * @param months 月份列表（数据库模式下使用）
 * @returns 一级部门统计数据
 */
export const getLevel1DepartmentStatistics = async (
  filePath: string,
  level1Name: string,
  months?: string[]
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
    holiday_avg_work_hours: number
    workday_attendance_days: number
    weekend_work_days: number
    weekend_attendance_count: number
    travel_days: number
    leave_days: number
    anomaly_days: number // 未知天数（疑似异常）
    late_after_1930_count: number
    total_cost: number
  }>
}>> => {
  const params: Record<string, any> = { level1_name: level1Name }
  if (filePath) {
    params.file_path = filePath
  }
  if (months && months.length > 0) {
    params.months = months.join(',')
  }

  return apiClient.get<ApiResponse<{
    department_name: string
    total_travel_cost: number
    attendance_days_distribution: Record<string, number>
    travel_ranking: Array<{ name: string; value: number; detail?: string }>
    avg_hours_ranking: Array<{ name: string; value: number; detail?: string }>
    level2_department_stats: Array<{
      name: string
      person_count: number
      avg_work_hours: number
      holiday_avg_work_hours: number
      workday_attendance_days: number
      weekend_work_days: number
      weekend_attendance_count: number
      travel_days: number
      leave_days: number
      anomaly_days: number // 未知天数（疑似异常）
      late_after_1930_count: number
      total_cost: number
    }>
  }>>('/departments/level1/statistics', { params })
}

/**
 * 获取二级部门的汇总统计数据（用于三级部门表格下方的统计展示）
 * @param filePath 文件路径（可选，不提供则从数据库读取）
 * @param level2Name 二级部门名称
 * @param months 月份列表（数据库模式下使用）
 * @returns 二级部门统计数据
 */
export const getLevel2DepartmentStatistics = async (
  filePath: string,
  level2Name: string,
  months?: string[]
): Promise<ApiResponse<{
  department_name: string
  parent_department?: string | null
  total_travel_cost: number
  attendance_days_distribution: Record<string, number>
  travel_ranking: Array<{ name: string; value: number; detail?: string }>
  avg_hours_ranking: Array<{ name: string; value: number; detail?: string }>
  level3_department_stats: Array<{
    name: string
    person_count: number
    avg_work_hours: number
    holiday_avg_work_hours: number
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
  const params: Record<string, any> = { level2_name: level2Name }
  if (filePath) {
    params.file_path = filePath
  }
  if (months && months.length > 0) {
    params.months = months.join(',')
  }

  return apiClient.get<ApiResponse<{
    department_name: string
    parent_department?: string | null
    total_travel_cost: number
    attendance_days_distribution: Record<string, number>
    travel_ranking: Array<{ name: string; value: number; detail?: string }>
    avg_hours_ranking: Array<{ name: string; value: number; detail?: string }>
    level3_department_stats: Array<{
      name: string
      person_count: number
      avg_work_hours: number
      holiday_avg_work_hours: number
      workday_attendance_days: number
      weekend_work_days: number
      weekend_attendance_count: number
      travel_days: number
      leave_days: number
      anomaly_days: number
      late_after_1930_count: number
      total_cost: number
    }>
  }>>('/departments/level2/statistics', { params })
}

/**
 * 获取异常记录详情
 * @param filePath 文件路径（可选，不提供则从数据库读取）
 * @param months 月份列表（数据库模式下使用）
 * @returns 异常记录列表
 */
export const getAnomalies = async (
  filePath: string,
  months?: string[]
): Promise<ApiResponse<{
  anomalies: any[]
  total_count: number
}>> => {
  const params: Record<string, any> = {}
  if (filePath) {
    params.file_path = filePath
  }
  if (months && months.length > 0) {
    params.months = months.join(',')
  }

  return apiClient.get<ApiResponse<{
    anomalies: any[]
    total_count: number
  }>>('/anomalies', { params })
}

// 导出 axios 实例供特殊情况使用
export default apiClient
