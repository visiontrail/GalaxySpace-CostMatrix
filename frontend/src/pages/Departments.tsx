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
  message,
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
  getLevel1DepartmentStatistics,
} from '@/services/api'
import { useMonthContext } from '@/contexts/MonthContext'

const { Title } = Typography

const Departments = () => {
  const navigate = useNavigate()
  const { selectedMonth } = useMonthContext()

  const [loading, setLoading] = useState(false)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const [statsLoading, setStatsLoading] = useState(false)
  const [currentLevel, setCurrentLevel] = useState<1 | 2 | 3>(1)
  const [selectedLevel1, setSelectedLevel1] = useState<string>('')
  const [selectedLevel2, setSelectedLevel2] = useState<string>('')
  const [departments, setDepartments] = useState<DepartmentListItem[]>([])
  const [drawerVisible, setDrawerVisible] = useState(false)
  const [selectedDepartment, setSelectedDepartment] = useState<DepartmentDetailMetrics | null>(null)
  const [level1Statistics, setLevel1Statistics] = useState<any>(null)

  useEffect(() => {
    if (selectedMonth) {
      loadDepartments(1)
    } else {
      setDepartments([])
    }
  }, [selectedMonth])

  // 当进入二级部门页面时，加载一级部门统计数据
  useEffect(() => {
    if (currentLevel === 2 && selectedLevel1 && selectedMonth) {
      loadLevel1Statistics(selectedLevel1)
    } else {
      setLevel1Statistics(null)
    }
  }, [currentLevel, selectedLevel1, selectedMonth])

  const loadLevel1Statistics = async (level1Name: string) => {
    if (!selectedMonth) return
    setStatsLoading(true)
    try {
      const result = await getLevel1DepartmentStatistics('', level1Name, [selectedMonth])
      if (result.success && result.data) {
        setLevel1Statistics(result.data)
      }
    } catch (error: any) {
      message.error('加载一级部门统计数据失败')
    } finally {
      setStatsLoading(false)
    }
  }

  const loadDepartments = async (level: 1 | 2 | 3, parent?: string) => {
    if (!selectedMonth) {
      return
    }

    setLoading(true)
    try {
      // 调用API时不传file_path，传递months参数从数据库获取数据
      const result = await getDepartmentList('', level, parent, [selectedMonth])
      if (result.success && result.data) {
        setDepartments(result.data.departments || [])
      }
    } catch (error: any) {
      message.error('加载部门列表失败')
    } finally {
      setLoading(false)
    }
  }

  const loadDepartmentDetails = async (deptName: string, level: number) => {
    if (!selectedMonth) {
      return
    }

    setDetailsLoading(true)
    try {
      const result = await getDepartmentDetails('', deptName, level, [selectedMonth])
      if (result.success && result.data) {
        setSelectedDepartment(result.data)
        setDrawerVisible(true)
      }
    } catch (error: any) {
      message.error('加载部门详情失败')
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

  const handleLevel2ViewDetails = (dept: string) => {
    loadDepartmentDetails(dept, 2)
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

  // 空状态 - 没有选择月份
  if (!selectedMonth) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Empty description="请从左侧选择月份查看部门数据" />
      </div>
    )
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
        title: '工作日平均工时 (小时)',
        dataIndex: 'avg_work_hours',
        key: 'avg_work_hours',
        render: (value: number) => `${value.toFixed(1)} h`,
        sorter: (a: DepartmentListItem, b: DepartmentListItem) => a.avg_work_hours - b.avg_work_hours,
      },
      {
        title: '节假日平均工时 (小时)',
        dataIndex: 'holiday_avg_work_hours',
        key: 'holiday_avg_work_hours',
        render: (value: number) => value > 0 ? `${value.toFixed(1)} h` : '-',
        sorter: (a: DepartmentListItem, b: DepartmentListItem) => a.holiday_avg_work_hours - b.holiday_avg_work_hours,
      },
      {
        title: '操作',
        key: 'action',
        render: (_: any, record: DepartmentListItem) => (
          <Space size="small">
            {currentLevel === 2 && (
              <a onClick={() => handleLevel2Click(record.name)}>进入下级</a>
            )}
            {currentLevel === 2 && (
              <a onClick={() => handleLevel2ViewDetails(record.name)}>查看详情</a>
            )}
            {currentLevel === 3 && (
              <a onClick={() => handleLevel3Click(record.name)}>查看详情</a>
            )}
          </Space>
        ),
      },
    ]

    return (
      <>
        <Table
          dataSource={departments}
          columns={columns}
          rowKey="name"
          loading={loading}
          pagination={{
            pageSize: 20,
            showSizeChanger: false,
            showTotal: (total) => `共 ${total} 个部门`,
          }}
        />
        {/* Level 2: 显示一级部门统计数据 */}
        {currentLevel === 2 && renderLevel1Statistics()}
      </>
    )
  }

  // 渲染一级部门统计数据（在二级部门表格下方）
  const renderLevel1Statistics = () => {
    if (!level1Statistics) return null

    const { total_travel_cost, attendance_days_distribution, travel_ranking, avg_hours_ranking, level2_department_stats } = level1Statistics

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
            value: value as number,
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
        data: [...travel_ranking].reverse().map((r: any) => r.name),
      },
      series: [
        {
          type: 'bar',
          data: [...travel_ranking].reverse().map((r: any) => ({
            value: r.value,
            itemStyle: { color: '#5470c6' },
          })),
          label: { show: true, position: 'right' },
        },
      ],
    }

    // 平均工时排行榜
    const avgHoursRankingOption: EChartsOption = {
      title: { text: '平均工时排行榜', left: 'center' },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'value', name: '小时' },
      yAxis: {
        type: 'category',
        data: [...avg_hours_ranking].reverse().map((r: any) => r.name),
      },
      series: [
        {
          type: 'bar',
          data: [...avg_hours_ranking].reverse().map((r: any) => ({
            value: r.value,
            itemStyle: { color: '#73c0de' },
          })),
          label: { show: true, position: 'right', formatter: '{c}h' },
        },
      ],
    }

    // 二级部门统计表格列
    const level2StatsColumns = [
      { title: '部门名称', dataIndex: 'name', key: 'name' },
      { title: '人数', dataIndex: 'person_count', key: 'person_count', render: (v: number) => `${v}人` },
      { title: '工作日出勤天数', dataIndex: 'workday_attendance_days', key: 'workday_attendance_days', render: (v: number) => `${v}天` },
      { title: '公休日上班天数', dataIndex: 'weekend_work_days', key: 'weekend_work_days', render: (v: number) => `${v}天` },
      { title: '周末出勤次数', dataIndex: 'weekend_attendance_count', key: 'weekend_attendance_count' },
      { title: '出差天数', dataIndex: 'travel_days', key: 'travel_days', render: (v: number) => `${v}天` },
      { title: '请假天数', dataIndex: 'leave_days', key: 'leave_days', render: (v: number) => `${v}天` },
      { title: '异常天数', dataIndex: 'anomaly_days', key: 'anomaly_days', render: (v: number) => `${v}天` },
      { title: '晚上7:30后下班人数', dataIndex: 'late_after_1930_count', key: 'late_after_1930_count', render: (v: number) => `${v}人` },
      { title: '工作日平均工时', dataIndex: 'avg_work_hours', key: 'avg_work_hours', render: (v: number) => `${v.toFixed(1)}h` },
      { title: '节假日平均工时', dataIndex: 'holiday_avg_work_hours', key: 'holiday_avg_work_hours', render: (v: number) => v > 0 ? `${v.toFixed(1)}h` : '-' },
      { title: '总成本', dataIndex: 'total_cost', key: 'total_cost', render: (v: number) => `¥${v.toLocaleString()}` },
    ]

    return (
      <Spin spinning={statsLoading}>
        <Divider orientation="left">{selectedLevel1} - 汇总统计</Divider>

        {/* 累计差旅成本 */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={24}>
            <Card>
              <Statistic
                title="累计差旅成本"
                value={total_travel_cost}
                prefix={<DollarOutlined />}
                precision={2}
                suffix="元"
                valueStyle={{ fontSize: 28, color: '#1890ff' }}
              />
            </Card>
          </Col>
        </Row>

        {/* 考勤天数分布和出差排行榜 */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
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

        {/* 平均工时排行榜 */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={24}>
            <Card title="平均工时排行榜 (Top 10)">
              <ReactECharts option={avgHoursRankingOption} style={{ height: 300 }} />
            </Card>
          </Col>
        </Row>

        {/* 二级部门统计表格 */}
        <Card title="二级部门统计详情">
          <Table
            dataSource={level2_department_stats}
            columns={level2StatsColumns}
            rowKey="name"
            pagination={{
              pageSize: 20,
              showSizeChanger: false,
              showTotal: (total) => `共 ${total} 个二级部门`,
            }}
            size="small"
          />
        </Card>
      </Spin>
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
            <Descriptions.Item label="节假日平均工时">{selectedDepartment.holiday_avg_work_hours > 0 ? `${selectedDepartment.holiday_avg_work_hours} 小时` : '-'}</Descriptions.Item>
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
