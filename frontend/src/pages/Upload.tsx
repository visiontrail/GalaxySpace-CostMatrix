import { useState } from 'react'
import { 
  Card, 
  Upload as AntUpload, 
  Button, 
  message, 
  Space, 
  Typography, 
  Alert,
  Spin,
  Steps,
  Progress
} from 'antd'
import { 
  InboxOutlined, 
  UploadOutlined, 
  CheckCircleOutlined, 
  SyncOutlined,
  FileExcelOutlined
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { uploadFile, analyzeExcel } from '@/services/api'
import type { AnalysisResult } from '@/types'

const { Dragger } = AntUpload
const { Title, Text, Paragraph } = Typography

const Upload = () => {
  const navigate = useNavigate()
  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [uploadedFilePath, setUploadedFilePath] = useState<string>('')
  const [uploadProgress, setUploadProgress] = useState(0)
  const [currentStep, setCurrentStep] = useState(0)
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null)

  const handleUpload = async (file: File) => {
    // 文件大小检查 (限制 50MB)
    if (file.size > 50 * 1024 * 1024) {
      message.error('文件大小不能超过 50MB')
      return false
    }

    // 文件类型检查
    const validTypes = [
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel'
    ]
    if (!validTypes.includes(file.type) && !file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      message.error('只支持 Excel 文件格式 (.xlsx, .xls)')
      return false
    }

    setUploading(true)
    setCurrentStep(0)
    setUploadProgress(0)
    
    try {
      // 模拟上传进度
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval)
            return 90
          }
          return prev + 10
        })
      }, 100)

      const result = await uploadFile(file)
      
      clearInterval(progressInterval)
      setUploadProgress(100)
      
      if (result.success && result.data) {
        message.success('文件上传成功！')
        setUploadedFilePath(result.data.file_path)
        setCurrentStep(1)
        
        // 自动开始分析
        setTimeout(() => {
          handleAnalyze(result.data!.file_path)
        }, 800)
      } else {
        message.error(result.message || '文件上传失败')
        setCurrentStep(0)
      }
    } catch (error: any) {
      message.error(error.message || '文件上传失败')
      setCurrentStep(0)
    } finally {
      setUploading(false)
    }
    
    return false // 阻止默认上传行为
  }

  const handleAnalyze = async (filePath: string) => {
    setAnalyzing(true)
    setCurrentStep(2)
    
    try {
      const result = await analyzeExcel(filePath)
      
      if (result.success && result.data) {
        message.success('数据分析完成！')
        setCurrentStep(3)
        setAnalysisResult(result.data)
        
        // 保存数据到 localStorage
        localStorage.setItem('dashboard_data', JSON.stringify(result.data))
        localStorage.setItem('current_file', filePath)
        
        // 显示分析结果摘要
        message.info({
          content: `分析完成：发现 ${result.data?.summary?.anomaly_count ?? 0} 条异常记录`,
          duration: 3
        })
        
        // 跳转到看板页面
        setTimeout(() => {
          navigate('/')
        }, 2000)
      } else {
        message.error(result.message || '数据分析失败')
        setCurrentStep(1)
      }
    } catch (error: any) {
      message.error(error.message || '数据分析失败')
      setCurrentStep(1)
    } finally {
      setAnalyzing(false)
    }
  }

  const steps = [
    {
      title: '上传文件',
      icon: uploading ? <SyncOutlined spin /> : <UploadOutlined />,
      description: '选择 Excel 文件'
    },
    {
      title: '文件验证',
      icon: <CheckCircleOutlined />,
      description: '检查文件格式'
    },
    {
      title: '数据分析',
      icon: analyzing ? <SyncOutlined spin /> : <SyncOutlined />,
      description: '处理分析数据'
    },
    {
      title: '完成',
      icon: <CheckCircleOutlined />,
      description: '查看结果'
    }
  ]

  return (
    <div className="upload-container">
      <Card variant="borderless">
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          {/* 页面标题 */}
          <div style={{ textAlign: 'center' }}>
            <Title level={2}>
              <FileExcelOutlined /> 上传 Excel 文件
            </Title>
            <Paragraph type="secondary">
              支持包含多个 Sheet 的 .xlsx 文件，系统将自动分析考勤、机票、酒店、火车票等数据
            </Paragraph>
          </div>

          {/* 步骤指示器 */}
          <Steps current={currentStep} items={steps} />

          {/* 文件要求说明 */}
          <Alert
            message="文件格式要求"
            description={
              <Space direction="vertical" size="small" style={{ width: '100%' }}>
                <Text>支持的 Sheet 名称：</Text>
                <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
                  <li><Text code>状态明细</Text> - 考勤数据</li>
                  <li><Text code>机票</Text> - 机票差旅明细</li>
                  <li><Text code>酒店</Text> - 酒店差旅明细</li>
                  <li><Text code>火车票</Text> - 火车票差旅明细</li>
                  <li><Text code>差旅汇总</Text> - 汇总参考数据（可选）</li>
                </ul>
                <Text type="warning">注意：文件大小不超过 50MB</Text>
              </Space>
            }
            type="info"
            showIcon
          />

          {/* 拖拽上传区域 */}
          <Dragger
            name="file"
            accept=".xlsx,.xls"
            multiple={false}
            beforeUpload={handleUpload}
            disabled={uploading || analyzing}
            showUploadList={false}
            style={{ padding: '30px 20px' }}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined style={{ fontSize: 72, color: '#1890ff' }} />
            </p>
            <p className="ant-upload-text" style={{ fontSize: 18 }}>
              点击或拖拽文件到此区域上传
            </p>
            <p className="ant-upload-hint" style={{ fontSize: 14 }}>
              仅支持 .xlsx 和 .xls 格式的 Excel 文件
            </p>
          </Dragger>

          {/* 上传进度条 */}
          {uploading && (
            <div style={{ padding: '20px 0' }}>
              <Progress 
                percent={uploadProgress} 
                status="active"
                strokeColor={{
                  '0%': '#108ee9',
                  '100%': '#87d068',
                }}
              />
              <div style={{ textAlign: 'center', marginTop: 10 }}>
                <Text type="secondary">正在上传文件...</Text>
              </div>
            </div>
          )}

          {/* 分析中状态 */}
          {analyzing && (
            <div style={{ textAlign: 'center', padding: '30px 0' }}>
              <Spin size="large" />
              <div style={{ marginTop: 16 }}>
                <Text strong style={{ fontSize: 16 }}>
                  正在分析数据，请稍候...
                </Text>
              </div>
              <div style={{ marginTop: 8 }}>
                <Text type="secondary">
                  系统正在处理考勤与差旅数据的交叉验证
                </Text>
              </div>
            </div>
          )}

          {/* 上传成功提示 */}
          {uploadedFilePath && !analyzing && currentStep >= 1 && (
            <Alert
              message="文件已上传"
              description={
                <Space direction="vertical">
                  <Text>文件路径: <Text code>{uploadedFilePath}</Text></Text>
                  {analysisResult?.summary && (
                    <Space direction="vertical" size="small">
                      <Text strong>分析结果概览：</Text>
                      <Text>• 总成本: ¥{(analysisResult.summary.total_cost ?? 0).toLocaleString()}</Text>
                      <Text>• 平均工时: {(analysisResult.summary.avg_work_hours ?? 0).toFixed(1)} 小时</Text>
                      <Text>• 异常记录: {analysisResult.summary.anomaly_count ?? 0} 条</Text>
                    </Space>
                  )}
                </Space>
              }
              type="success"
              showIcon
              action={
                !analyzing && currentStep < 3 && (
                  <Button 
                    size="small" 
                    type="primary"
                    onClick={() => handleAnalyze(uploadedFilePath)}
                  >
                    重新分析
                  </Button>
                )
              }
            />
          )}

          {/* 完成状态 */}
          {currentStep === 3 && (
            <Alert
              message="分析完成"
              description="数据分析已完成，即将跳转到数据看板..."
              type="success"
              showIcon
              action={
                <Button type="primary" onClick={() => navigate('/')}>
                  查看看板
                </Button>
              }
            />
          )}
        </Space>
      </Card>

      {/* 使用说明 */}
      <Card 
        title="使用说明" 
        variant="borderless"
        style={{ marginTop: 24 }}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Text strong>1. 准备 Excel 文件</Text>
            <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
              确保您的 Excel 文件包含所需的 Sheet，每个 Sheet 的列名需要符合系统要求。
            </Paragraph>
          </div>
          <div>
            <Text strong>2. 上传文件</Text>
            <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
              点击上方上传区域或拖拽文件到区域内，系统会自动开始上传和分析。
            </Paragraph>
          </div>
          <div>
            <Text strong>3. 查看结果</Text>
            <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
              分析完成后，系统会自动跳转到数据看板页面，您可以查看详细的分析结果和可视化图表。
            </Paragraph>
          </div>
          <div>
            <Text strong>4. 导出报告</Text>
            <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
              在数据看板页面，点击"导出分析结果"按钮可以下载完整的分析报告 Excel 文件。
            </Paragraph>
          </div>
        </Space>
      </Card>
    </div>
  )
}

export default Upload
