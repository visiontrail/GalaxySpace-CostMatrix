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
  Level1DepartmentStatistics,
  Level2DepartmentStatistics,
} from '@/types'
import {
  getDepartmentList,
  getDepartmentDetails,
  getLevel1DepartmentStatistics,
  getLevel2DepartmentStatistics,
} from '@/services/api'
import { useMonthContext } from '@/contexts/MonthContext'

const { Title } = Typography

const Departments = () => {
  const navigate = useNavigate()
  const { selectedMonths } = useMonthContext()

  const [loading, setLoading] = useState(false)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const [statsLoading, setStatsLoading] = useState(false)
  const [currentLevel, setCurrentLevel] = useState<1 | 2 | 3>(1)
  const [selectedLevel1, setSelectedLevel1] = useState<string>('')
  const [selectedLevel2, setSelectedLevel2] = useState<string>('')
  const [departments, setDepartments] = useState<DepartmentListItem[]>([])
  const [drawerVisible, setDrawerVisible] = useState(false)
  const [selectedDepartment, setSelectedDepartment] = useState<DepartmentDetailMetrics | null>(null)
  const [level1Statistics, setLevel1Statistics] = useState<Level1DepartmentStatistics | null>(null)
  const [level2Statistics, setLevel2Statistics] = useState<Level2DepartmentStatistics | null>(null)

  useEffect(() => {
    if (selectedMonths.length === 0) {
      setDepartments([])
      return
    }

    if (currentLevel === 1) {
      loadDepartments(1)
    } else if (currentLevel === 2 && selectedLevel1) {
      loadDepartments(2, selectedLevel1)
    } else if (currentLevel === 3 && selectedLevel2) {
      loadDepartments(3, selectedLevel2)
    }
  }, [selectedMonths])

  // 当进入二级部门页面时，加载一级部门统计数据
  useEffect(() => {
    if (currentLevel === 2 && selectedLevel1 && selectedMonths.length > 0) {
      loadLevel1Statistics(selectedLevel1)
    } else {
      setLevel1Statistics(null)
    }
  }, [currentLevel, selectedLevel1, selectedMonths])

  useEffect(() => {
    if (currentLevel === 3 && selectedLevel2 && selectedMonths.length > 0) {
      loadLevel2Statistics(selectedLevel2)
    } else {
      setLevel2Statistics(null)
    }
  }, [currentLevel, selectedLevel2, selectedMonths])

  const loadLevel1Statistics = async (level1Name: string) => {
    if (selectedMonths.length === 0) return
    setStatsLoading(true)
    try {
      const result = await getLevel1DepartmentStatistics('', level1Name, selectedMonths)
      if (result.success && result.data) {
        setLevel1Statistics(result.data)
      }
    } catch (error: any) {
      message.error('加载一级部门统计数据失败')
    } finally {
      setStatsLoading(false)
    }
  }

  const loadLevel2Statistics = async (level2Name: string) => {
    if (selectedMonths.length === 0) return
    setStatsLoading(true)
    try {
      const result = await getLevel2DepartmentStatistics('', level2Name, selectedMonths)
      if (result.success && result.data) {
        setLevel2Statistics(result.data)
      }
    } catch (error: any) {
      message.error('加载二级部门统计数据失败')
    } finally {
      setStatsLoading(false)
    }
  }

  const loadDepartments = async (level: 1 | 2 | 3, parent?: string) => {
    if (selectedMonths.length === 0) {
      return
    }

    setLoading(true)
    try {
      // 调用API时不传file_path，传递months参数从数据库获取数据
      const result = await getDepartmentList('', level, parent, selectedMonths)
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
    if (selectedMonths.length === 0) {
      return
    }

    setDetailsLoading(true)
    try {
      const result = await getDepartmentDetails('', deptName, level, selectedMonths)
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
  if (selectedMonths.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Empty description="请从左侧选择月份查看部门数据" />
      </div>
    )
  }

  // 面包屑导航
  const breadcrumbItems = [
    {
      key: 'home',
      title: <a onClick={() => navigate('/')}>首页</a>,
    },
  ]
  if (currentLevel >= 1) {
    breadcrumbItems.push({
      key: 'departments',
      title: currentLevel > 1 ? <a onClick={() => handleBreadcrumbClick(1)}>部门管理</a> : '部门管理',
    })
  }
  if (currentLevel >= 2 && selectedLevel1) {
    breadcrumbItems.push({
      key: `level1-${selectedLevel1}`,
      title: currentLevel > 2 ? <a onClick={() => handleBreadcrumbClick(2)}>{selectedLevel1}</a> : selectedLevel1,
    })
  }
  if (currentLevel === 3 && selectedLevel2) {
    breadcrumbItems.push({
      key: `level2-${selectedLevel2}`,
      title: selectedLevel2,
    })
  }

  const formatMonthDisplay = (month: string) => {
    const [year, monthNum] = month.split('-')
    return `${year}年${monthNum}月`
  }

  const departmentStatsColumns = [
    { title: '部门名称', dataIndex: 'name', key: 'name' },
    { title: '人数', dataIndex: 'person_count', key: 'person_count', render: (v: number) => `${v}人` },
    { title: '工作日出勤（人天）', dataIndex: 'workday_attendance_days', key: 'workday_attendance_days', render: (v: number) => `${v}人天` },
    { title: '公休日上班（人天）', dataIndex: 'weekend_work_days', key: 'weekend_work_days', render: (v: number) => `${v}人天` },
    { title: '出差（人天）', dataIndex: 'travel_days', key: 'travel_days', render: (v: number) => `${v}人天` },
    { title: '请假（人天）', dataIndex: 'leave_days', key: 'leave_days', render: (v: number) => `${v}人天` },
    { title: '未知天数（疑似异常）', dataIndex: 'anomaly_days', key: 'anomaly_days', render: (v: number) => `${v}人天` },
    { title: '晚上7:30后下班人数', dataIndex: 'late_after_1930_count', key: 'late_after_1930_count', render: (v: number) => `${v}人` },
    { title: '工作日平均工时', dataIndex: 'avg_work_hours', key: 'avg_work_hours', render: (v: number) => `${v.toFixed(1)}h` },
    { title: '节假日平均工时', dataIndex: 'holiday_avg_work_hours', key: 'holiday_avg_work_hours', render: (v: number) => v > 0 ? `${v.toFixed(1)}h` : '-' },
    { title: '总成本', dataIndex: 'total_cost', key: 'total_cost', render: (v: number) => `¥${v.toLocaleString()}` },
  ]

  const mapAttendanceLabel = (name: string) => name === '上班' ? '工作日上班' : name

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
        {/* Level 3: 显示二级部门统计数据 */}
        {currentLevel === 3 && renderLevel2Statistics()}
      </>
    )
  }

  // 渲染一级部门统计数据（在二级部门表格下方）
  const renderLevel1Statistics = () => {
    if (!level1Statistics) return null

    const { total_travel_cost, attendance_days_distribution, travel_ranking, avg_hours_ranking, level2_department_stats } = level1Statistics

    // 排行榜数据：确保按数值从高到低（顶部为最大值）
    const travelRankingDesc = [...travel_ranking].sort((a: any, b: any) => b.value - a.value)
    const avgHoursRankingDesc = [...avg_hours_ranking].sort((a: any, b: any) => b.value - a.value)

    // 考勤天数分布饼图
    const attendancePieOption: EChartsOption = {
      title: { text: '考勤天数分布', left: 'center' },
      tooltip: { trigger: 'item', formatter: '{b}: {c}人天 ({d}%)' },
      legend: { orient: 'vertical', left: 'left' },
      series: [
        {
          name: '人天',
          type: 'pie',
          radius: '50%',
          label: { show: true, formatter: '{b}: {d}%' },
          data: Object.entries(attendance_days_distribution).map(([name, value]) => ({
            name: mapAttendanceLabel(name),
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
        data: travelRankingDesc.map((r: any) => r.name),
        inverse: true,
      },
      series: [
        {
          type: 'bar',
          data: travelRankingDesc.map((r: any) => ({
            value: r.value,
            itemStyle: { color: '#5470c6' },
          })),
          label: { show: true, position: 'right' },
        },
      ],
    }

    // 平均工时排行榜
    const avgHoursRankingOption: EChartsOption = {
      title: {
        text: '平均工时排行榜',
        subtext: '仅统计工作日出勤的平均工时',
        left: 'center',
      },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'value', name: '小时' },
      yAxis: {
        type: 'category',
        data: avgHoursRankingDesc.map((r: any) => r.name),
        inverse: true,
      },
      series: [
        {
          type: 'bar',
          data: avgHoursRankingDesc.map((r: any) => ({
            value: r.value,
            itemStyle: { color: '#73c0de' },
          })),
          label: { show: true, position: 'right', formatter: '{c}h' },
        },
      ],
    }

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
            <Card title="平均工时排行榜 (Top 10) —— 工作日">
              <ReactECharts option={avgHoursRankingOption} style={{ height: 300 }} />
            </Card>
          </Col>
        </Row>

        {/* 二级部门统计表格 */}
        <Card title="二级部门统计详情">
          <Table
            dataSource={level2_department_stats}
            columns={departmentStatsColumns}
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

  const renderLevel2Statistics = () => {
    if (!level2Statistics) return null

    const { total_travel_cost, attendance_days_distribution, travel_ranking, avg_hours_ranking, level3_department_stats, parent_department } = level2Statistics

    const travelRankingDesc = [...travel_ranking].sort((a: any, b: any) => b.value - a.value)
    const avgHoursRankingDesc = [...avg_hours_ranking].sort((a: any, b: any) => b.value - a.value)

    const attendancePieOption: EChartsOption = {
      title: { text: '考勤天数分布', left: 'center' },
      tooltip: { trigger: 'item', formatter: '{b}: {c}人天 ({d}%)' },
      legend: { orient: 'vertical', left: 'left' },
      series: [
        {
          name: '人天',
          type: 'pie',
          radius: '50%',
          label: { show: true, formatter: '{b}: {d}%' },
          data: Object.entries(attendance_days_distribution).map(([name, value]) => ({
            name: mapAttendanceLabel(name),
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

    const travelRankingOption: EChartsOption = {
      title: { text: '出差排行榜', left: 'center' },
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        data: travelRankingDesc.map((r: any) => r.name),
        inverse: true,
      },
      series: [
        {
          type: 'bar',
          data: travelRankingDesc.map((r: any) => ({
            value: r.value,
            itemStyle: { color: '#5470c6' },
          })),
          label: { show: true, position: 'right' },
        },
      ],
    }

    const avgHoursRankingOption: EChartsOption = {
      title: {
        text: '平均工时排行榜',
        subtext: '仅统计工作日出勤的平均工时',
        left: 'center',
      },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'value', name: '小时' },
      yAxis: {
        type: 'category',
        data: avgHoursRankingDesc.map((r: any) => r.name),
        inverse: true,
      },
      series: [
        {
          type: 'bar',
          data: avgHoursRankingDesc.map((r: any) => ({
            value: r.value,
            itemStyle: { color: '#73c0de' },
          })),
          label: { show: true, position: 'right', formatter: '{c}h' },
        },
      ],
    }

    return (
      <Spin spinning={statsLoading}>
        <Divider orientation="left">
          {selectedLevel2} - 汇总统计
          {parent_department ? `（上级: ${parent_department}）` : ''}
        </Divider>

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

        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={24}>
            <Card title="平均工时排行榜 (Top 10) —— 工作日">
              <ReactECharts option={avgHoursRankingOption} style={{ height: 300 }} />
            </Card>
          </Col>
        </Row>

        <Card title="三级部门统计详情">
          <Table
            dataSource={level3_department_stats}
            columns={departmentStatsColumns}
            rowKey="name"
            pagination={{
              pageSize: 20,
              showSizeChanger: false,
              showTotal: (total) => `共 ${total} 个三级部门`,
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
    const mapAttendanceLabel = (name: string) => name === '上班' ? '工作日上班' : name

    // 考勤天数分布饼图
    const attendancePieOption: EChartsOption = {
      title: { text: '考勤天数分布', left: 'center' },
      tooltip: { trigger: 'item', formatter: '{b}: {c}人天 ({d}%)' },
      legend: { orient: 'vertical', left: 'left' },
      series: [
        {
          name: '人天',
          type: 'pie',
          radius: '50%',
          label: { show: true, formatter: '{b}: {d}%' },
          data: Object.entries(attendance_days_distribution).map(([name, value]) => ({
            name: mapAttendanceLabel(name),
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

    // 排行榜数据：确保按数值从高到低展示（顶部为最高值）
    const travelRankingDesc = [...selectedDepartment.travel_ranking].sort((a, b) => b.value - a.value)
    const longestHoursDesc = [...selectedDepartment.longest_hours_ranking].sort((a, b) => b.value - a.value)

    // 出差排行榜
    const travelRankingOption: EChartsOption = {
      title: { text: '出差排行榜', left: 'center' },
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        data: travelRankingDesc.map((r) => r.name),
        inverse: true,
      },
      series: [
        {
          type: 'bar',
          data: travelRankingDesc.map((r) => ({
            value: r.value,
            itemStyle: { color: '#5470c6' },
          })),
          label: { show: true, position: 'right' },
        },
      ],
    }

    // 未知天数排行榜（疑似异常）
    const anomalyRankingOption: EChartsOption = {
      title: { text: '未知天数排行榜（疑似异常）', left: 'center' },
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'value' },
      yAxis: {
        type: 'category',
        data: [...selectedDepartment.anomaly_ranking].sort((a, b) => b.value - a.value).map((r) => r.name),
        inverse: true,
      },
      series: [
        {
          type: 'bar',
          data: [...selectedDepartment.anomaly_ranking].sort((a, b) => b.value - a.value).map((r) => ({
            value: r.value,
            itemStyle: { color: '#ee6666' },
          })),
          label: { show: true, position: 'right' },
        },
      ],
    }

    // 最长工时排行榜
    const longestHoursOption: EChartsOption = {
      title: {
        text: '最长工时排行榜',
        subtext: '基于工作日平均工时',
        left: 'center',
      },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'value', name: '小时' },
      yAxis: {
        type: 'category',
        data: longestHoursDesc.map((r) => r.name),
        inverse: true,
      },
      series: [
        {
          type: 'bar',
          data: longestHoursDesc.map((r) => ({
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
            <Descriptions.Item label="工作日出勤天数">{attendance_days_distribution['上班'] || 0} 人天</Descriptions.Item>
            <Descriptions.Item label="公休日上班天数">{attendance_days_distribution['公休日上班'] || 0} 人天</Descriptions.Item>
            <Descriptions.Item label="周末出勤次数">{selectedDepartment.weekend_attendance_count} 次</Descriptions.Item>
          </Descriptions>

          <Descriptions bordered column={3}>
            <Descriptions.Item label="出差天数">{attendance_days_distribution['出差'] || 0} 人天</Descriptions.Item>
            <Descriptions.Item label="请假天数">{attendance_days_distribution['请假'] || 0} 人天</Descriptions.Item>
            <Descriptions.Item label="未知天数（疑似异常）">{selectedDepartment.anomaly_days} 人天</Descriptions.Item>
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
              <Card title="未知天数排行榜（疑似异常） (Top 10)">
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
        <Space direction="vertical" size={4}>
          <Space>
            <ArrowLeftOutlined onClick={goBack} style={{ cursor: 'pointer', fontSize: 20 }} />
            <Title level={3} style={{ margin: 0 }}>
              {currentLevel === 1 && '一级部门'}
              {currentLevel === 2 && `${selectedLevel1} - 二级部门`}
              {currentLevel === 3 && `${selectedLevel2} - 三级部门`}
            </Title>
          </Space>
          <Space align="center" size={[4, 4]} wrap>
            <Typography.Text type="secondary">统计月份:</Typography.Text>
            {selectedMonths.map(month => (
              <Tag key={month} color="blue">{formatMonthDisplay(month)}</Tag>
            ))}
          </Space>
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
