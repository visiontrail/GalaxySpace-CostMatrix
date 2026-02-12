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
  Progress,
  List,
} from 'antd'
import {
  InboxOutlined,
  FileExcelOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { uploadFile, getUploadProgress } from '@/services/api'
import { useMonthContext } from '@/contexts/MonthContext'

const { Dragger } = AntUpload
const { Title, Text, Paragraph } = Typography

const Upload = () => {
  const navigate = useNavigate()
  const { refreshMonths } = useMonthContext()
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [currentStep, setCurrentStep] = useState('')
  const [steps, setSteps] = useState<Array<{ step: string; completed_at: string }>>([])
  const [status, setStatus] = useState<string>('')

  const pollProgress = async (id: string) => {
    try {
      const result = await getUploadProgress(id)
      
      if (result.success && result.data) {
        setUploadProgress(result.data.progress)
        setCurrentStep(result.data.current_step)
        setSteps(result.data.steps || [])
        setStatus(result.data.status)

        if (result.data.status === 'completed') {
          message.success('文件上传并解析成功！')
          await refreshMonths()
          setTimeout(() => {
            navigate('/')
          }, 1500)
          return
        }

        if (result.data.status === 'failed') {
          message.error(result.data.error || '文件上传失败')
          setUploading(false)
          setUploadProgress(0)
          return
        }

        if (result.data.status === 'uploading' || result.data.status === 'processing') {
          setTimeout(() => pollProgress(id), 1000)
        }
      }
    } catch (error: any) {
      if (error.response?.status === 404) {
        message.warning('任务已完成或已过期')
        setUploading(false)
        setUploadProgress(0)
      } else {
        message.error(error.message || '获取上传进度失败')
        setUploading(false)
        setUploadProgress(0)
      }
    }
  }

  const handleUpload = async (file: File) => {
    if (file.size > 50 * 1024 * 1024) {
      message.error('文件大小不能超过 50MB')
      return false
    }

    const validTypes = [
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel'
    ]
    if (!validTypes.includes(file.type) && !file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
      message.error('只支持 Excel 文件格式 (.xlsx, .xls)')
      return false
    }

    setUploading(true)
    setUploadProgress(0)
    setCurrentStep('正在上传文件...')
    setSteps([])
    setStatus('uploading')

    try {
      const result = await uploadFile(file)

      if (result.success && result.data?.task_id) {
        pollProgress(result.data.task_id)
      } else {
        message.error(result.message || '文件上传失败')
        setUploading(false)
        setUploadProgress(0)
      }
    } catch (error: any) {
      message.error(error.message || '文件上传失败')
      setUploadProgress(0)
      setUploading(false)
    }

    return false
  }

  const uploadProps = {
    name: 'file',
    multiple: false,
    accept: '.xlsx,.xls',
    beforeUpload: handleUpload,
    showUploadList: false,
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '24px' }}>
      <Card>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div style={{ textAlign: 'center' }}>
            <FileExcelOutlined style={{ fontSize: 64, color: '#1890ff' }} />
            <Title level={2} style={{ marginTop: 16 }}>
              上传数据文件
            </Title>
            <Paragraph type="secondary">
              支持 .xlsx 和 .xls 格式的 Excel 文件
            </Paragraph>
          </div>

          <Alert
            message="文件要求"
            description={
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                <li>文件大小不超过 50MB</li>
                <li>包含以下 Sheet：状态明细、机票、酒店、火车票</li>
                <li>上传后会自动解析并添加到统计月份列表</li>
              </ul>
            }
            type="info"
            showIcon
          />

          {uploading ? (
            <div style={{ padding: '40px 0' }}>
              <Spin size="large" />
              <div style={{ marginTop: 16, textAlign: 'center' }}>
                <Text strong>{currentStep}</Text>
              </div>
              <div style={{ marginTop: 8 }}>
                <Progress 
                  percent={uploadProgress} 
                  status={status === 'failed' ? 'exception' : status === 'completed' ? 'success' : 'active'}
                  strokeColor={status === 'failed' ? '#ff4d4f' : undefined}
                />
              </div>
              
              {steps.length > 0 && (
                <div style={{ marginTop: 24, background: '#f5f5f5', padding: 16, borderRadius: 8 }}>
                  <Text strong>处理进度：</Text>
                  <List
                    size="small"
                    dataSource={steps}
                    renderItem={(item) => (
                      <List.Item>
                        <Space>
                          <CheckCircleOutlined style={{ color: '#52c41a' }} />
                          <Text>{item.step}</Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                </div>
              )}
            </div>
          ) : (
            <Dragger {...uploadProps}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
              <p className="ant-upload-hint">
                支持单次上传。严禁上传公司数据或其他敏感信息。
              </p>
            </Dragger>
          )}

          <div style={{ textAlign: 'center', marginTop: 24 }}>
            <Button type="default" onClick={() => navigate('/')}>
              返回数据看板
            </Button>
          </div>
        </Space>
      </Card>
    </div>
  )
}

export default Upload
