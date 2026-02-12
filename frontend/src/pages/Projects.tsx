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
  Drawer,
  Descriptions,
  Row,
  Col,
  Statistic,
  Divider,
} from 'antd'
import {
  ArrowLeftOutlined,
  DollarOutlined,
  UserOutlined,
  WarningOutlined,
  FileTextOutlined,
  TeamOutlined,
  ProjectOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'
import type { ProjectDetail, ProjectOrderRecord } from '@/types'
import { getAllProjects, getProjectOrders } from '@/services/api'
import { useMonthContext } from '@/contexts/MonthContext'

const { Title, Text } = Typography

const Projects = () => {
  const navigate = useNavigate()
  const { selectedMonths } = useMonthContext()

  const [projects, setProjects] = useState<ProjectDetail[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedProject, setSelectedProject] = useState<ProjectDetail | null>(null)
  const [orders, setOrders] = useState<ProjectOrderRecord[]>([])
  const [ordersLoading, setOrdersLoading] = useState(false)
  const [drawerVisible, setDrawerVisible] = useState(false)

  useEffect(() => {
    if (selectedMonths.length > 0) {
      fetchProjects()
    } else {
      setProjects([])
    }
  }, [selectedMonths])

  const fetchProjects = async () => {
    if (selectedMonths.length === 0) {
      message.warning('请先选择月份')
      return
    }

    setLoading(true)
    try {
      // 调用API时不传file_path，传递months参数从数据库获取数据
      const result = await getAllProjects('', selectedMonths)
      if (result.success && result.data?.projects) {
        setProjects(result.data.projects)
      } else {
        message.error(result.message || '获取项目数据失败')
      }
    } catch (error: any) {
      message.error(error.message || '获取项目数据失败')
    } finally {
      setLoading(false)
    }
  }

  const handleViewOrders = async (project: ProjectDetail) => {
    if (selectedMonths.length === 0) {
      message.warning('请先选择月份')
      return
    }

    setSelectedProject(project)
    setDrawerVisible(true)
    setOrdersLoading(true)

    try {
      const result = await getProjectOrders('', project.code, selectedMonths)
      if (result.success && result.data?.orders) {
        setOrders(result.data.orders)
      } else {
        message.error(result.message || '获取订单记录失败')
      }
    } catch (error: any) {
      message.error(error.message || '获取订单记录失败')
    } finally {
      setOrdersLoading(false)
    }
  }

  const handleDrawerClose = () => {
    setDrawerVisible(false)
    setSelectedProject(null)
    setOrders([])
  }

  // 项目列表表格列定义
  const projectColumns: ColumnsType<ProjectDetail> = [
    {
      title: '项目代码',
      dataIndex: 'code',
      key: 'code',
      fixed: 'left',
      width: 120,
      sorter: (a, b) => a.code.localeCompare(b.code),
      render: (value: string) => value === 'nan' ? '未知编号' : value,
    },
    {
      title: '项目名称',
      dataIndex: 'name',
      key: 'name',
      width: 250,
      ellipsis: true,
      sorter: (a, b) => a.name.localeCompare(b.name),
      render: (value: string) => value === 'nan' ? '未知项目' : value,
    },
    {
      title: '总成本 (元)',
      dataIndex: 'total_cost',
      key: 'total_cost',
      width: 150,
      sorter: (a, b) => a.total_cost - b.total_cost,
      render: (value: number) => (
        <Text strong style={{ color: '#52c41a' }}>
          ¥{value.toLocaleString()}
        </Text>
      ),
    },
    {
      title: '机票成本',
      dataIndex: 'flight_cost',
      key: 'flight_cost',
      width: 120,
      sorter: (a, b) => a.flight_cost - b.flight_cost,
      render: (value: number) => `¥${value.toLocaleString()}`,
    },
    {
      title: '酒店成本',
      dataIndex: 'hotel_cost',
      key: 'hotel_cost',
      width: 120,
      sorter: (a, b) => a.hotel_cost - b.hotel_cost,
      render: (value: number) => `¥${value.toLocaleString()}`,
    },
    {
      title: '火车票成本',
      dataIndex: 'train_cost',
      key: 'train_cost',
      width: 120,
      sorter: (a, b) => a.train_cost - b.train_cost,
      render: (value: number) => `¥${value.toLocaleString()}`,
    },
    {
      title: '订单数',
      dataIndex: 'record_count',
      key: 'record_count',
      width: 100,
      sorter: (a, b) => a.record_count - b.record_count,
      render: (value: number) => (
        <Tag color="blue">{value} 单</Tag>
      ),
    },
    {
      title: '涉及人数',
      dataIndex: 'person_count',
      key: 'person_count',
      width: 100,
      sorter: (a, b) => a.person_count - b.person_count,
      render: (value: number) => (
        <Tag color="cyan">{value} 人</Tag>
      ),
    },
    {
      title: '超标订单',
      dataIndex: 'over_standard_count',
      key: 'over_standard_count',
      width: 100,
      sorter: (a, b) => (a.over_standard_count || 0) - (b.over_standard_count || 0),
      render: (value: number) => {
        if (value > 0) {
          return <Tag color="red">{value} 单</Tag>
        }
        return <Tag color="green">0 单</Tag>
      },
    },
    {
      title: '日期范围',
      key: 'date_range',
      width: 180,
      render: (_, record) => (
        <Text type="secondary">
          {record.date_range.start && record.date_range.end
            ? `${record.date_range.start} ~ ${record.date_range.end}`
            : '-'}
        </Text>
      ),
    },
    {
      title: '操作',
      key: 'action',
      fixed: 'right',
      width: 100,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          onClick={() => handleViewOrders(record)}
        >
          查看订单
        </Button>
      ),
    },
  ]

  // 订单记录表格列定义
  const orderColumns: ColumnsType<ProjectOrderRecord> = [
    {
      title: '日期',
      dataIndex: 'date',
      key: 'date',
      width: 120,
      sorter: (a, b) => a.date.localeCompare(b.date),
    },
    {
      title: '姓名',
      dataIndex: 'person',
      key: 'person',
      width: 100,
    },
    {
      title: '部门',
      dataIndex: 'department',
      key: 'department',
      width: 120,
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 80,
      render: (type: string) => {
        const typeMap: Record<string, { label: string; color: string }> = {
          flight: { label: '机票', color: 'blue' },
          hotel: { label: '酒店', color: 'green' },
          train: { label: '火车票', color: 'orange' },
        }
        const info = typeMap[type] || { label: type, color: 'default' }
        return <Tag color={info.color}>{info.label}</Tag>
      },
    },
    {
      title: '金额 (元)',
      dataIndex: 'amount',
      key: 'amount',
      width: 120,
      sorter: (a, b) => a.amount - b.amount,
      render: (value: number) => `¥${value.toLocaleString()}`,
    },
    {
      title: '是否超标',
      dataIndex: 'is_over_standard',
      key: 'is_over_standard',
      width: 100,
      render: (isOver: boolean) => {
        if (isOver) {
          return <Tag color="red" icon={<WarningOutlined />}>是</Tag>
        }
        return <Tag color="green">否</Tag>
      },
    },
    {
      title: '超标类型',
      dataIndex: 'over_type',
      key: 'over_type',
      width: 150,
      ellipsis: true,
    },
    {
      title: '提前预订天数',
      dataIndex: 'advance_days',
      key: 'advance_days',
      width: 120,
      render: (days: number | null) => {
        if (days === null || days === undefined) {
          return <Text type="secondary">-</Text>
        }
        if (days < 0) {
          return <Tag color="red">紧急 {Math.abs(days)} 天</Tag>
        }
        return <Tag color="blue">{days} 天</Tag>
      },
    },
  ]

  if (selectedMonths.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Empty description="请从左侧选择月份（可多选）查看项目数据" />
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
            项目详情
          </Title>
          <Space align="center" size={[4, 4]} wrap>
            <Text type="secondary">当前月份:</Text>
            {selectedMonths.map(month => (
              <Tag key={month} color="blue">{month}</Tag>
            ))}
          </Space>
          <Tag color="purple">共 {projects.length} 个项目</Tag>
        </Space>
        <Button onClick={fetchProjects} loading={loading}>
          刷新数据
        </Button>
      </Space>

      <Card>
        <Spin spinning={loading}>
          {projects.length > 0 ? (
            <Table
              dataSource={projects}
              columns={projectColumns}
              rowKey="code"
              pagination={{
                pageSize: 20,
                showSizeChanger: false,
                showTotal: (total) => `共 ${total} 个项目`,
              }}
              scroll={{ x: 1500 }}
              size="middle"
            />
          ) : (
            <Empty description="暂无项目数据" />
          )}
        </Spin>
      </Card>

      <Drawer
        title={`项目详情 - ${selectedProject?.name || ''}`}
        placement="right"
        width={800}
        open={drawerVisible}
        onClose={handleDrawerClose}
      >
        {selectedProject && (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            {/* 项目基本信息 */}
            <Card size="small" title={<><ProjectOutlined /> 基本信息</>}>
              <Descriptions column={2} size="small">
                <Descriptions.Item label="项目代码">{selectedProject.code}</Descriptions.Item>
                <Descriptions.Item label="涉及人数">{selectedProject.person_count} 人</Descriptions.Item>
                <Descriptions.Item label="总成本" span={2}>
                  <Text strong style={{ color: '#52c41a', fontSize: 16 }}>
                    ¥{selectedProject.total_cost.toLocaleString()}
                  </Text>
                </Descriptions.Item>
                <Descriptions.Item label="日期范围" span={2}>
                  {selectedProject.date_range.start && selectedProject.date_range.end
                    ? `${selectedProject.date_range.start} 至 ${selectedProject.date_range.end}`
                    : '-'}
                </Descriptions.Item>
              </Descriptions>
            </Card>

            {/* 成本统计 */}
            <Card size="small" title={<><DollarOutlined /> 成本统计</>}>
              <Row gutter={16}>
                <Col span={8}>
                  <Statistic
                    title="机票成本"
                    value={selectedProject.flight_cost}
                    precision={2}
                    prefix="¥"
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="酒店成本"
                    value={selectedProject.hotel_cost}
                    precision={2}
                    prefix="¥"
                    valueStyle={{ color: '#52c41a' }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="火车票成本"
                    value={selectedProject.train_cost}
                    precision={2}
                    prefix="¥"
                    valueStyle={{ color: '#fa8c16' }}
                  />
                </Col>
              </Row>
            </Card>

            {/* 订单统计 */}
            <Card size="small" title={<><FileTextOutlined /> 订单统计</>}>
              <Row gutter={16}>
                <Col span={8}>
                  <Statistic
                    title="总订单数"
                    value={selectedProject.record_count}
                    suffix="单"
                    valueStyle={{ color: '#722ed1' }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="机票订单"
                    value={selectedProject.flight_count}
                    suffix="单"
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="酒店订单"
                    value={selectedProject.hotel_count}
                    suffix="单"
                    valueStyle={{ color: '#52c41a' }}
                  />
                </Col>
              </Row>
              <Row gutter={16} style={{ marginTop: 16 }}>
                <Col span={12}>
                  <Statistic
                    title="火车票订单"
                    value={selectedProject.train_count}
                    suffix="单"
                    valueStyle={{ color: '#fa8c16' }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="超标订单"
                    value={selectedProject.over_standard_count || 0}
                    suffix="单"
                    valueStyle={{ color: '#cf1322' }}
                  />
                </Col>
              </Row>
            </Card>

            {/* 涉及人员 */}
            {selectedProject.person_list.length > 0 && (
              <Card size="small" title={<><TeamOutlined /> 涉及人员 ({selectedProject.person_list.length})</>}>
                <Space wrap>
                  {selectedProject.person_list.map((person, idx) => (
                    <Tag key={idx} color="geekblue" icon={<UserOutlined />}>
                      {person}
                    </Tag>
                  ))}
                </Space>
              </Card>
            )}

            {/* 涉及部门 */}
            {selectedProject.department_list && selectedProject.department_list.length > 0 && (
              <Card size="small" title={<><TeamOutlined /> 涉及部门 ({selectedProject.department_list.length})</>}>
                <Space wrap>
                  {selectedProject.department_list.map((dept, idx) => (
                    <Tag key={idx} color="purple">
                      {dept}
                    </Tag>
                  ))}
                </Space>
              </Card>
            )}

            <Divider />

            {/* 订单记录详情 */}
            <Card size="small" title={<><FileTextOutlined /> 订单记录详情</>}>
              <Spin spinning={ordersLoading}>
                {orders.length > 0 ? (
                  <Table
                    dataSource={orders}
                    columns={orderColumns}
                    rowKey="id"
                    pagination={{
                      pageSize: 10,
                      showSizeChanger: false,
                      showTotal: (total) => `共 ${total} 条订单记录`,
                    }}
                    scroll={{ x: 1000 }}
                    size="small"
                  />
                ) : (
                  <Empty description="暂无订单记录" />
                )}
              </Spin>
            </Card>
          </Space>
        )}
      </Drawer>
    </div>
  )
}

export default Projects
