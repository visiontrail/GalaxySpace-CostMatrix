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
} from 'antd'
import {
  InboxOutlined,
  FileExcelOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { uploadFile } from '@/services/api'
import { useMonthContext } from '@/contexts/MonthContext'

const { Dragger } = AntUpload
const { Title, Text, Paragraph } = Typography

const Upload = () => {
  const navigate = useNavigate()
  const { refreshMonths } = useMonthContext()
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)

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

    try {
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

      if (result.success) {
        message.success('文件上传并解析成功！')
        await refreshMonths()

        setTimeout(() => {
          navigate('/')
        }, 1500)
      } else {
        message.error(result.message || '文件上传失败')
        setUploadProgress(0)
      }
    } catch (error: any) {
      message.error(error.message || '文件上传失败')
      setUploadProgress(0)
    } finally {
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
                <Text>正在上传并解析文件... {uploadProgress}%</Text>
              </div>
              <div style={{ marginTop: 8 }}>
                <Progress percent={uploadProgress} />
              </div>
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
