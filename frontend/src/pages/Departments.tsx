import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card,
  Row,
  Col,
  Breadcrumb,
  Statistic,
  Table,
  Drawer,
  Spin,
  Empty,
  Tag,
  Divider,
  Space,
  Typography,
  Descriptions,
} from 'antd'
import {
  ArrowLeftOutlined,
  TeamOutlined,
  DollarOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type {
  DepartmentListItem,
  DepartmentDetailMetrics,
} from '@/types'
import {
  getDepartmentList,
  getDepartmentDetails,
} from '@/services/api'
import { useOutletContext } from 'react-router-dom'
import type { UploadContextValue } from '@/layouts/MainLayout'

const { Title } = Typography

const Departments = () => {
  const navigate = useNavigate()
  const { selectedUpload } = useOutletContext<UploadContextValue>()

  const [loading, setLoading] = useState(false)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const [currentLevel, setCurrentLevel] = useState<1 | 2 | 3>(1)
  const [selectedLevel1, setSelectedLevel1] = useState<string>('')
  const [selectedLevel2, setSelectedLevel2] = useState<string>('')
  const [departments, setDepartments] = useState<DepartmentListItem[]>([])
  const [drawerVisible, setDrawerVisible] = useState(false)
  const [selectedDepartment, setSelectedDepartment] = useState<DepartmentDetailMetrics | null>(null)

  const filePath = selectedUpload?.file_path || localStorage.getItem('current_file') || ''

  useEffect(() => {
    if (filePath) {
      loadDepartments(1)
    }
  }, [filePath])

  const loadDepartments = async (level: 1 | 2 | 3, parent?: string) => {
    if (!filePath) return
    setLoading(true)
    try {
      const result = await getDepartmentList(filePath, level, parent)
      if (result.success && result.data) {
        setDepartments(result.data.departments || [])
      }
    } catch (error: any) {
      console.error('加载部门列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadDepartmentDetails = async (deptName: string, level: number) => {
    if (!filePath) return
    setDetailsLoading(true)
    try {
      const result = await getDepartmentDetails(filePath, deptName, level)
      if (result.success && result.data) {
        setSelectedDepartment(result.data)
        setDrawerVisible(true)
      }
    } catch (error: any) {
      console.error('加载部门详情失败:', error)
    } finally {
      setDetailsLoading(false)
    }
  }

  const handleLevel1Click = (dept: string) => {
    setSelectedLevel1(dept)
    setCurrentLevel(2)
    loadDepartments(2, dept)
  }

  const handleLevel2Click = (dept: string) => {
    setSelectedLevel2(dept)
    setCurrentLevel(3)
    loadDepartments(3, dept)
  }

  const handleLevel3Click = (dept: string) => {
    loadDepartmentDetails(dept, 3)
  }

  const handleBreadcrumbClick = (level: 1 | 2) => {
    if (level === 1) {
      setSelectedLevel1('')
      setSelectedLevel2('')
      setCurrentLevel(1)
      loadDepartments(1)
    } else if (level === 2 && selectedLevel1) {
      setSelectedLevel2('')
      setCurrentLevel(2)
      loadDepartments(2, selectedLevel1)
    }
  }

  const goBack = () => {
    if (currentLevel === 3 && selectedLevel1) {
      handleBreadcrumbClick(2)
    } else if (currentLevel === 2) {
      handleBreadcrumbClick(1)
    } else {
      navigate('/')
    }
  }

  // 面包屑导航
  const breadcrumbItems = [
    { title: '首页' },
  ]
  if (currentLevel >= 1) {
    breadcrumbItems.push({ title: '部门管理' })
  }
  if (currentLevel >= 2 && selectedLevel1) {
    breadcrumbItems.push({ title: selectedLevel1 })
  }
  if (currentLevel === 3 && selectedLevel2) {
    breadcrumbItems.push({ title: selectedLevel2 })
  }

  // Level 1: 一级部门卡片视图
  const renderLevel1 = () => (
    <Row gutter={[16, 16]}>
      {departments.map((dept) => (
        <Col xs={24} sm={12} lg={8} xl={6} key={dept.name}>
          <Card
            hoverable
            onClick={() => handleLevel1Click(dept.name)}
            style={{ height: '100%' }}
          >
            <Space direction="vertical" style={{ width: '100%' }}>
              <Title level={4} style={{ margin: 0 }}>{dept.name}</Title>
              <Row gutter={16}>
                <Col span={12}>
                  <Statistic
                    title="人数"
                    value={dept.person_count}
                    prefix={<TeamOutlined />}
                    valueStyle={{ fontSize: 20 }}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="成本"
                    value={dept.total_cost}
                    prefix={<DollarOutlined />}
                    precision={0}
                    valueStyle={{ fontSize: 20 }}
                  />
                </Col>
              </Row>
              <Statistic
                title="平均工时"
                value={dept.avg_work_hours}
                suffix="小时"
                prefix={<ClockCircleOutlined />}
                precision={1}
                valueStyle={{ fontSize: 16 }}
              />
            </Space>
          </Card>
        </Col>
      ))}
    </Row>
  )

  // Level 2 & 3: 部门表格视图
  const renderLevel2Or3 = () => {
    const columns = [
      {
        title: '部门名称',
        dataIndex: 'name',
        key: 'name',
        render: (text: string, record: DepartmentListItem) => (
          <a onClick={() => {
            if (currentLevel === 2) {
              handleLevel2Click(record.name)
            } else {
              handleLevel3Click(record.name)
            }
          }}>
            {text}
          </a>
        ),
      },
      {
        title: '人数',
        dataIndex: 'person_count',
        key: 'person_count',
        render: (value: number) => <Tag color="blue">{value} 人</Tag>,
        sorter: (a: DepartmentListItem, b: DepartmentListItem) => a.person_count - b.person_count,
      },
      {
        title: '总成本 (元)',
        dataIndex: 'total_cost',
        key: 'total_cost',
        render: (value: number) => `¥${value.toLocaleString()}`,
        sorter: (a: DepartmentListItem, b: DepartmentListItem) => a.total_cost - b.total_cost,
      },
      {
        title: '平均工时 (小时)',
        dataIndex: 'avg_work_hours',
        key: 'avg_work_hours',
        render: (value: number) => `${value.toFixed(1)} h`,
        sorter: (a: DepartmentListItem, b: DepartmentListItem) => a.avg_work_hours - b.avg_work_hours,
      },
      {
        title: '操作',
        key: 'action',
        render: (_: any, record: DepartmentListItem) => (
          currentLevel === 3 ? (
            <a onClick={() => handleLevel3Click(record.name)}>查看详情</a>
          ) : (
            <a onClick={() => handleLevel2Click(record.name)}>进入下级</a>
          )
        ),
      },
    ]

    return (
      <Table
        dataSource={departments}
        columns={columns}
        rowKey="name"
        loading={loading}
        pagination={{ pageSize: 20 }}
      />
    )
  }

  // 部门详情抽屉
  const renderDetailDrawer = () => {
    if (!selectedDepartment) return null

    const { attendance_days_distribution } = selectedDepartment

    // 考勤天数分布饼图
    const attendancePieOption: EChartsOption = {
      title: { text: '考勤天数分布', left: 'center' },
      tooltip: { trigger: 'item' },
      legend: { orient: 'vertical', left: 'left' },
      series: [
        {
          name: '天数',
          type: 'pie',
          radius: '50%',
          data: Object.entries(attendance_days_distribution).map(([name, value]) => ({
            name,
            value,
          })),
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        },
      ],
    }

    // 出差排行榜
    const travelRankingOption: EChartsOption = {
      title: { text: '出差排行榜', left: 'center' },
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        data: selectedDepartment.travel_ranking.map((r) => r.name),
      },
      series: [
        {
          type: 'bar',
          data: selectedDepartment.travel_ranking.map((r) => ({
            value: r.value,
            itemStyle: { color: '#5470c6' },
          })),
          label: { show: true, position: 'right' },
        },
      ],
    }

    // 异常排行榜
    const anomalyRankingOption: EChartsOption = {
      title: { text: '异常排行榜', left: 'center' },
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        data: selectedDepartment.anomaly_ranking.map((r) => r.name),
      },
      series: [
        {
          type: 'bar',
          data: selectedDepartment.anomaly_ranking.map((r) => ({
            value: r.value,
            itemStyle: { color: '#ee6666' },
          })),
          label: { show: true, position: 'right' },
        },
      ],
    }

    // 最长工时排行榜
    const longestHoursOption: EChartsOption = {
      title: { text: '最长工时排行榜', left: 'center' },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'value', name: '小时' },
      yAxis: {
        type: 'category',
        data: selectedDepartment.longest_hours_ranking.map((r) => r.name),
      },
      series: [
        {
          type: 'bar',
          data: selectedDepartment.longest_hours_ranking.map((r) => ({
            value: r.value,
            itemStyle: { color: '#73c0de' },
          })),
          label: { show: true, position: 'right', formatter: '{c}h' },
        },
      ],
    }

    return (
      <Drawer
        title={`${selectedDepartment.department_name} - 详细指标`}
        placement="right"
        width={1200}
        open={drawerVisible}
        onClose={() => setDrawerVisible(false)}
        loading={detailsLoading}
      >
        <Spin spinning={detailsLoading}>
          <Descriptions title="基本信息" bordered column={2}>
            <Descriptions.Item label="部门名称">{selectedDepartment.department_name}</Descriptions.Item>
            <Descriptions.Item label="部门层级">{selectedDepartment.department_level}</Descriptions.Item>
            <Descriptions.Item label="父部门">{selectedDepartment.parent_department || '-'}</Descriptions.Item>
            <Descriptions.Item label="工作日平均工时">{selectedDepartment.avg_work_hours} 小时</Descriptions.Item>
          </Descriptions>

          <Divider />

          <Descriptions title="考勤统计" bordered column={3}>
            <Descriptions.Item label="工作日出勤天数">{selectedDepartment.workday_attendance_days} 天</Descriptions.Item>
            <Descriptions.Item label="公休日上班天数">{selectedDepartment.weekend_work_days} 天</Descriptions.Item>
            <Descriptions.Item label="周末出勤次数">{selectedDepartment.weekend_attendance_count} 次</Descriptions.Item>
          </Descriptions>

          <Descriptions bordered column={3}>
            <Descriptions.Item label="出差天数">{selectedDepartment.travel_days} 天</Descriptions.Item>
            <Descriptions.Item label="请假天数">{selectedDepartment.leave_days} 天</Descriptions.Item>
            <Descriptions.Item label="异常天数">{selectedDepartment.anomaly_days} 天</Descriptions.Item>
          </Descriptions>

          <Descriptions bordered column={2}>
            <Descriptions.Item label="晚上7:30后下班人数">{selectedDepartment.late_after_1930_count} 人</Descriptions.Item>
          </Descriptions>

          <Divider />

          <Row gutter={16}>
            <Col span={12}>
              <Card title="考勤天数分布">
                <ReactECharts option={attendancePieOption} style={{ height: 300 }} />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="出差排行榜 (Top 10)">
                <ReactECharts option={travelRankingOption} style={{ height: 300 }} />
              </Card>
            </Col>
          </Row>

          <Row gutter={16} style={{ marginTop: 16 }}>
            <Col span={12}>
              <Card title="异常排行榜 (Top 10)">
                <ReactECharts option={anomalyRankingOption} style={{ height: 300 }} />
              </Card>
            </Col>
            <Col span={12}>
              <Card title="最长工时排行榜 (Top 10)">
                <ReactECharts option={longestHoursOption} style={{ height: 300 }} />
              </Card>
            </Col>
          </Row>

          <Divider />

          <Card title="最晚下班排行榜 (Top 10)">
            <Table
              dataSource={selectedDepartment.latest_checkout_ranking.map((r, i) => ({
                key: i,
                name: r.name,
                time: r.detail,
              }))}
              columns={[
                { title: '排名', key: 'rank', render: (_: any, __: any, index: number) => index + 1 },
                { title: '姓名', dataIndex: 'name', key: 'name' },
                { title: '最晚下班时间', dataIndex: 'time', key: 'time' },
              ]}
              pagination={false}
              size="small"
            />
          </Card>
        </Spin>
      </Drawer>
    )
  }

  return (
    <div style={{ padding: 24 }}>
      <Breadcrumb items={breadcrumbItems} style={{ marginBottom: 16 }} />

      <div style={{ marginBottom: 16 }}>
        <Space>
          <ArrowLeftOutlined onClick={goBack} style={{ cursor: 'pointer', fontSize: 20 }} />
          <Title level={3} style={{ margin: 0 }}>
            {currentLevel === 1 && '一级部门'}
            {currentLevel === 2 && `${selectedLevel1} - 二级部门`}
            {currentLevel === 3 && `${selectedLevel2} - 三级部门`}
          </Title>
        </Space>
      </div>

      <Spin spinning={loading}>
        {departments.length === 0 && !loading ? (
          <Empty description="暂无部门数据" />
        ) : (
          <>
            {currentLevel === 1 && renderLevel1()}
            {(currentLevel === 2 || currentLevel === 3) && renderLevel2Or3()}
          </>
        )}
      </Spin>

      {renderDetailDrawer()}
    </div>
  )
}

export default Departments
