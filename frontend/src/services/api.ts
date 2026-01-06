/**
 * API 服务层
 * 对接后端 FastAPI 接口
 */
import axios, { AxiosInstance } from 'axios'
import type { 
  ApiResponse, 
  AnalysisResult, 
  UploadResponse 
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
      timeout: 60000, // 上传超时 1 分钟
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
export const clearData = async (): Promise<ApiResponse> => {
  return apiClient.delete('/data')
}

// 导出 axios 实例供特殊情况使用
export default apiClient
