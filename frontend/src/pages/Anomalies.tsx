import { useState, useEffect } from 'react'
import {
  Card,
  Table,
  Button,
  Space,
  Typography,
  Tag,
  Empty,
  Spin,
  message,
  Tooltip,
} from 'antd'
import {
  ArrowLeftOutlined,
  WarningOutlined,
  CalendarOutlined,
  UserOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'
import type { AnomalyDetail } from '@/types'
import { getAnomalies } from '@/services/api'
import { useMonthContext } from '@/contexts/MonthContext'

const { Title, Text } = Typography

const Anomalies = () => {
  const navigate = useNavigate()
  const { selectedMonths } = useMonthContext()

  const [anomalies, setAnomalies] = useState<AnomalyDetail[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (selectedMonths.length > 0) {
      fetchAnomalies()
    } else {
      setAnomalies([])
    }
  }, [selectedMonths])

  const fetchAnomalies = async () => {
    if (selectedMonths.length === 0) {
      message.warning('请先选择月份')
      return
    }

    setLoading(true)
    try {
      // 调用API时不传file_path，传递months参数从数据库获取数据
      const result = await getAnomalies('', selectedMonths)
      if (result.success && result.data?.anomalies) {
        setAnomalies(result.data.anomalies)
      } else {
        message.error(result.message || '获取异常记录失败')
      }
    } catch (error: any) {
      message.error(error.message || '获取异常记录失败')
    } finally {
      setLoading(false)
    }
  }

  // 异常记录表格列定义
  const anomalyColumns: ColumnsType<AnomalyDetail> = [
    {
      title: '日期',
      dataIndex: 'date',
      key: 'date',
      width: 120,
      fixed: 'left',
      sorter: (a, b) => a.date.localeCompare(b.date),
      render: (date: string) => (
        <Space>
          <CalendarOutlined />
          <Text>{date}</Text>
        </Space>
      ),
    },
    {
      title: '姓名',
      dataIndex: 'name',
      key: 'name',
      width: 120,
      sorter: (a, b) => a.name.localeCompare(b.name),
      render: (name: string) => (
        <Space>
          <UserOutlined />
          <Text strong>{name}</Text>
        </Space>
      ),
    },
    {
      title: '部门',
      dataIndex: 'dept',
      key: 'dept',
      width: 150,
      sorter: (a, b) => a.dept.localeCompare(b.dept),
      render: (dept: string) => (
        <Space>
          <TeamOutlined />
          <Text>{dept}</Text>
        </Space>
      ),
    },
    {
      title: '异常类型',
      dataIndex: 'type',
      key: 'type',
      width: 120,
      sorter: (a, b) => a.type.localeCompare(b.type),
      render: (type: string) => {
        const colorMap: Record<string, string> = {
          'A': 'red',
          'Conflict': 'red',
          'B': 'orange',
          'Missing': 'orange',
          'C': 'purple',
          'Duplicate': 'purple',
          'D': 'volcano',
          'Invalid': 'volcano',
        }
        const displayType = type === 'A' ? '冲突' : type
        return (
          <Tag color={colorMap[type] || 'default'} icon={<WarningOutlined />}>
            {displayType}
          </Tag>
        )
      },
    },
    {
      title: '考勤状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status?: string) => {
        if (!status) return <Text type="secondary">-</Text>
        return <Tag color="blue">{status}</Tag>
      },
    },
    {
      title: '详细说明',
      dataIndex: 'detail',
      key: 'detail',
      ellipsis: true,
      render: (detail: string) => (
        <Tooltip title={detail}>
          <Text>{detail}</Text>
        </Tooltip>
      ),
    },
  ]

  if (selectedMonths.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Empty description="请从左侧选择月份（可多选）查看异常记录" />
      </div>
    )
  }

  return (
    <div>
      <Space style={{ marginBottom: 24, width: '100%', justifyContent: 'space-between' }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
            返回
          </Button>
          <Title level={2} style={{ margin: 0 }}>
            异常记录详情
          </Title>
          <Space align="center" size={[4, 4]} wrap>
            <Text type="secondary">当前月份:</Text>
            {selectedMonths.map(month => (
              <Tag key={month} color="blue">{month}</Tag>
            ))}
          </Space>
          <Tag color="red" icon={<WarningOutlined />}>
            共 {anomalies.length} 条异常
          </Tag>
        </Space>
        <Button onClick={fetchAnomalies} loading={loading}>
          刷新数据
        </Button>
      </Space>

      <Card>
        <Spin spinning={loading}>
          {anomalies.length > 0 ? (
            <Table
              dataSource={anomalies}
              columns={anomalyColumns}
              rowKey={(record) => `${record.date}-${record.name}-${record.dept}-${record.type}`}
              pagination={{
                pageSize: 20,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 条异常记录`,
                pageSizeOptions: ['10', '20', '50', '100'],
              }}
              scroll={{ x: 1000 }}
              size="middle"
            />
          ) : (
            <Empty
              description="暂无异常记录"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}
        </Spin>
      </Card>
    </div>
  )
}

export default Anomalies
