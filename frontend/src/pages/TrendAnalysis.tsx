import { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import { LineChartOutlined, ReloadOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { analyzeExcel, getAllProjects } from '@/services/api'
import { useMonthContext } from '@/contexts/MonthContext'

const { Title, Text } = Typography

interface ProjectSummary {
  code: string
  name: string
  total_cost: number
  flight_cost: number
  hotel_cost: number
  train_cost: number
}

interface MonthlyTrendPoint {
  month: string
  totalCost: number
  flightCost: number
  hotelCost: number
  trainCost: number
  avgWorkHours: number
  holidayAvgWorkHours: number
  anomalyCount: number
  projectCount: number
  overStandardCount: number
  projectCosts: Record<string, number>
}

const formatMonthDisplay = (month: string) => {
  const [year, monthNum] = month.split('-')
  return `${year}年${monthNum}月`
}

const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`

const calcMom = (current: number, previous?: number) => {
  if (previous === undefined || previous === 0) return undefined
  return (current - previous) / previous
}

const TrendAnalysis = () => {
  const {
    availableMonths,
    selectedMonths,
    setPendingMonths,
    applySelectedMonths,
  } = useMonthContext()
  const [trendData, setTrendData] = useState<MonthlyTrendPoint[]>([])
  const [loading, setLoading] = useState(false)
  const [localMonths, setLocalMonths] = useState<string[]>(selectedMonths)
  const [projectOptions, setProjectOptions] = useState<Array<{ value: string; label: string }>>([])
  const [selectedProjectCodes, setSelectedProjectCodes] = useState<string[]>([])

  useEffect(() => {
    setLocalMonths(selectedMonths)
  }, [selectedMonths])

  useEffect(() => {
    const fetchData = async () => {
      if (selectedMonths.length === 0) {
        setTrendData([])
        setProjectOptions([])
        setSelectedProjectCodes([])
        return
      }

      setLoading(true)
      try {
        const sortedMonths = [...selectedMonths].sort()
        const results = await Promise.allSettled(
          sortedMonths.map(async (month) => {
            const [analysisRes, projectsRes] = await Promise.all([
              analyzeExcel(undefined, { months: [month] }),
              getAllProjects('', [month]),
            ])

            if (!analysisRes.success || !analysisRes.data) {
              throw new Error(`分析数据获取失败: ${month}`)
            }

            const projects = (projectsRes.data?.projects ?? []) as ProjectSummary[]
            const categoryCost = projects.reduce(
              (acc: { flight: number; hotel: number; train: number }, project) => ({
                flight: acc.flight + Number(project.flight_cost || 0),
                hotel: acc.hotel + Number(project.hotel_cost || 0),
                train: acc.train + Number(project.train_cost || 0),
              }),
              { flight: 0, hotel: 0, train: 0 }
            )

            const projectCosts = projects.reduce<Record<string, number>>((acc, project) => {
              acc[project.code] = Number(project.total_cost || 0)
              return acc
            }, {})

            const summary = analysisRes.data.summary
            return {
              month,
              totalCost: Number(summary.total_cost || 0),
              flightCost: categoryCost.flight,
              hotelCost: categoryCost.hotel,
              trainCost: categoryCost.train,
              avgWorkHours: Number(summary.avg_work_hours || 0),
              holidayAvgWorkHours: Number(summary.holiday_avg_work_hours || 0),
              anomalyCount: Number(summary.anomaly_count || 0),
              projectCount: Number(summary.total_project_count || 0),
              overStandardCount: Number(summary.over_standard_count || 0),
              projectCosts,
              projects,
            }
          })
        )

        const successData = results
          .filter((item): item is PromiseFulfilledResult<{
            month: string
            totalCost: number
            flightCost: number
            hotelCost: number
            trainCost: number
            avgWorkHours: number
            holidayAvgWorkHours: number
            anomalyCount: number
            projectCount: number
            overStandardCount: number
            projectCosts: Record<string, number>
            projects: ProjectSummary[]
          }> => item.status === 'fulfilled')
          .map((item) => item.value)
          .sort((a, b) => a.month.localeCompare(b.month))

        const nextTrendData = successData.map(({ projects: _projects, ...rest }) => rest)

        const failedCount = results.length - successData.length
        if (failedCount > 0) {
          message.warning(`有 ${failedCount} 个月份数据加载失败，已展示其余月份趋势`)
        }

        const projectMap = new Map<string, { code: string; name: string; totalCost: number }>()
        successData.forEach((item) => {
          item.projects.forEach((project) => {
            const existing = projectMap.get(project.code)
            const nextTotalCost = (existing?.totalCost || 0) + Number(project.total_cost || 0)
            projectMap.set(project.code, {
              code: project.code,
              name: project.name,
              totalCost: nextTotalCost,
            })
          })
        })

        const sortedProjectOptions = Array.from(projectMap.values())
          .sort((a, b) => b.totalCost - a.totalCost)
          .map((item) => ({
            value: item.code,
            label: `${item.code}${item.name && item.name !== item.code ? ` - ${item.name}` : ''}`,
          }))

        setTrendData(nextTrendData)
        setProjectOptions(sortedProjectOptions)
        setSelectedProjectCodes((prev) => {
          const validSet = new Set(sortedProjectOptions.map((item) => item.value))
          const filteredPrev = prev.filter((code) => validSet.has(code))
          if (filteredPrev.length > 0) {
            return filteredPrev
          }
          return sortedProjectOptions.slice(0, Math.min(5, sortedProjectOptions.length)).map((item) => item.value)
        })
      } catch (error: any) {
        message.error(error.message || '趋势数据加载失败')
        setTrendData([])
        setProjectOptions([])
        setSelectedProjectCodes([])
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [selectedMonths])

  const handleApplyMonths = () => {
    const nextMonths = [...localMonths].sort()
    setPendingMonths(nextMonths)
    applySelectedMonths(nextMonths)
    message.success('趋势分析月份已更新')
  }

  const latestPoint = trendData[trendData.length - 1]
  const previousPoint = trendData.length > 1 ? trendData[trendData.length - 2] : undefined
  const latestMonthDisplay = latestPoint ? formatMonthDisplay(latestPoint.month) : ''
  const previousMonthDisplay = previousPoint ? formatMonthDisplay(previousPoint.month) : ''

  const totalCostMom = latestPoint ? calcMom(latestPoint.totalCost, previousPoint?.totalCost) : undefined
  const holidayAvgHoursMom = latestPoint
    ? calcMom(latestPoint.holidayAvgWorkHours, previousPoint?.holidayAvgWorkHours)
    : undefined
  const avgHoursMom = latestPoint ? calcMom(latestPoint.avgWorkHours, previousPoint?.avgWorkHours) : undefined
  const projectMom = latestPoint ? calcMom(latestPoint.projectCount, previousPoint?.projectCount) : undefined

  const xAxisData = useMemo(
    () => trendData.map((item) => formatMonthDisplay(item.month)),
    [trendData]
  )

  const totalCostOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: '3%', right: '3%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: xAxisData },
    yAxis: {
      type: 'value',
      name: '成本（元）',
      axisLabel: { formatter: (value: number) => `¥${(value / 10000).toFixed(0)}万` },
    },
    series: [
      {
        name: '项目总成本',
        type: 'line',
        smooth: true,
        showSymbol: true,
        lineStyle: { width: 3 },
        areaStyle: { opacity: 0.12 },
        data: trendData.map((item) => item.totalCost),
      },
    ],
  }

  const selectedProjectLabels = useMemo(
    () => projectOptions.filter((item) => selectedProjectCodes.includes(item.value)),
    [projectOptions, selectedProjectCodes]
  )

  const projectCostByProjectOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { top: 0, type: 'scroll' },
    grid: { left: '3%', right: '3%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: xAxisData },
    yAxis: {
      type: 'value',
      name: '成本（元）',
      axisLabel: { formatter: (value: number) => `¥${(value / 10000).toFixed(0)}万` },
    },
    series: selectedProjectCodes.map((projectCode) => ({
      name: selectedProjectLabels.find((item) => item.value === projectCode)?.label || projectCode,
      type: 'line',
      smooth: true,
      showSymbol: true,
      data: trendData.map((item) => item.projectCosts[projectCode] || 0),
    })),
  }

  const categoryCostOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: '3%', right: '3%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: xAxisData },
    yAxis: {
      type: 'value',
      name: '成本（元）',
      axisLabel: { formatter: (value: number) => `¥${(value / 10000).toFixed(0)}万` },
    },
    series: [
      {
        name: '机票成本',
        type: 'line',
        smooth: true,
        data: trendData.map((item) => item.flightCost),
      },
      {
        name: '酒店成本',
        type: 'line',
        smooth: true,
        data: trendData.map((item) => item.hotelCost),
      },
      {
        name: '火车票成本',
        type: 'line',
        smooth: true,
        data: trendData.map((item) => item.trainCost),
      },
    ],
  }

  const coreMetricOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: '4%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: xAxisData },
    yAxis: { type: 'value', name: '数量' },
    series: [
      {
        name: '异常记录数',
        type: 'line',
        smooth: true,
        data: trendData.map((item) => item.anomalyCount),
      },
      {
        name: '项目数量',
        type: 'line',
        smooth: true,
        data: trendData.map((item) => item.projectCount),
      },
      {
        name: '超标订单数',
        type: 'line',
        smooth: true,
        data: trendData.map((item) => item.overStandardCount),
      },
    ],
  }

  const avgWorkHoursOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: '4%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: xAxisData },
    yAxis: { type: 'value', name: '工时（小时）' },
    series: [
      {
        name: '工作日平均工时',
        type: 'line',
        smooth: true,
        data: trendData.map((item) => Number(item.avgWorkHours.toFixed(2))),
      },
      {
        name: '节假日平均工时',
        type: 'line',
        smooth: true,
        data: trendData.map((item) => Number(item.holidayAvgWorkHours.toFixed(2))),
      },
    ],
  }

  if (availableMonths.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Empty description="暂无可分析月份，请先上传数据" />
      </div>
    )
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card>
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <Title level={4} style={{ margin: 0 }}>
                <LineChartOutlined /> 趋势分析
              </Title>
              <Text type="secondary">多月份维度自动提取关键业务指标，并生成趋势折线图</Text>
            </div>
            <Button icon={<ReloadOutlined />} onClick={handleApplyMonths}>
              应用月份
            </Button>
          </div>

          <Select
            mode="multiple"
            allowClear
            style={{ width: '100%' }}
            placeholder="选择一个或多个月份"
            value={localMonths}
            onChange={(value) => setLocalMonths(value.sort())}
            options={availableMonths.map((month) => ({
              value: month,
              label: formatMonthDisplay(month),
            }))}
          />

          {selectedMonths.length > 0 && (
            <Space size={[8, 8]} wrap>
              <Text type="secondary">当前分析月份：</Text>
              {selectedMonths.map((month) => (
                <Tag key={month} color="blue">
                  {formatMonthDisplay(month)}
                </Tag>
              ))}
            </Space>
          )}
        </Space>
      </Card>

      {selectedMonths.length === 0 ? (
        <Empty description="请选择月份后查看趋势分析" />
      ) : loading ? (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <Space direction="vertical">
            <Spin size="large" />
            <Text type="secondary">正在加载趋势分析数据...</Text>
          </Space>
        </div>
      ) : trendData.length === 0 ? (
        <Alert type="warning" showIcon message="所选月份暂无可用数据，请调整月份后重试" />
      ) : (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} md={12} lg={6}>
              <Card>
                <Statistic
                  title={`最新月总成本${latestMonthDisplay ? `（${latestMonthDisplay}）` : ''}`}
                  value={latestPoint?.totalCost || 0}
                  precision={0}
                  prefix="¥"
                  valueStyle={{ color: '#1677ff' }}
                />
                <Text type={totalCostMom !== undefined && totalCostMom >= 0 ? 'danger' : 'success'}>
                  环比（{latestMonthDisplay || '--'} vs {previousMonthDisplay || '--'}）：{totalCostMom !== undefined ? formatPercent(totalCostMom) : '--'}
                </Text>
              </Card>
            </Col>
            <Col xs={24} md={12} lg={6}>
              <Card>
                <Statistic title={`最新月项目数量${latestMonthDisplay ? `（${latestMonthDisplay}）` : ''}`} value={latestPoint?.projectCount || 0} />
                <Text type={projectMom !== undefined && projectMom >= 0 ? 'danger' : 'success'}>
                  环比（{latestMonthDisplay || '--'} vs {previousMonthDisplay || '--'}）：{projectMom !== undefined ? formatPercent(projectMom) : '--'}
                </Text>
              </Card>
            </Col>
            <Col xs={24} md={12} lg={6}>
              <Card>
                <Statistic
                  title={`最新月平均工时${latestMonthDisplay ? `（${latestMonthDisplay}）` : ''}`}
                  value={latestPoint?.avgWorkHours || 0}
                  precision={2}
                  suffix="h"
                />
                <Text type={avgHoursMom !== undefined && avgHoursMom >= 0 ? 'danger' : 'success'}>
                  环比（{latestMonthDisplay || '--'} vs {previousMonthDisplay || '--'}）：{avgHoursMom !== undefined ? formatPercent(avgHoursMom) : '--'}
                </Text>
              </Card>
            </Col>
            <Col xs={24} md={12} lg={6}>
              <Card>
                <Statistic
                  title={`最新月节假日平均工时${latestMonthDisplay ? `（${latestMonthDisplay}）` : ''}`}
                  value={latestPoint?.holidayAvgWorkHours || 0}
                  precision={2}
                  suffix="h"
                />
                <Text type={holidayAvgHoursMom !== undefined && holidayAvgHoursMom >= 0 ? 'danger' : 'success'}>
                  环比（{latestMonthDisplay || '--'} vs {previousMonthDisplay || '--'}）：{holidayAvgHoursMom !== undefined ? formatPercent(holidayAvgHoursMom) : '--'}
                </Text>
              </Card>
            </Col>
          </Row>

          <Card title="项目成本趋势（折线图）">
            <ReactECharts option={totalCostOption} style={{ height: 360 }} />
          </Card>

          <Card title="项目成本走势（按项目）">
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Select
                mode="multiple"
                allowClear
                maxTagCount="responsive"
                style={{ width: '100%' }}
                placeholder="选择一个或多个项目查看成本走势"
                value={selectedProjectCodes}
                onChange={(value) => setSelectedProjectCodes(value)}
                options={projectOptions}
              />
              {selectedProjectCodes.length === 0 ? (
                <Alert type="info" showIcon message="请选择至少一个项目以查看走势" />
              ) : (
                <ReactECharts
                  option={projectCostByProjectOption}
                  replaceMerge={['series']}
                  style={{ height: 360 }}
                />
              )}
            </Space>
          </Card>

          <Card title="各类成本分析趋势（折线图）">
            <ReactECharts option={categoryCostOption} style={{ height: 360 }} />
          </Card>

          <Card title="核心指标变化趋势（折线图）">
            <ReactECharts option={coreMetricOption} style={{ height: 360 }} />
          </Card>

          <Card title="平均工时变化趋势（折线图）">
            <ReactECharts option={avgWorkHoursOption} style={{ height: 360 }} />
          </Card>

          <Card title="月度趋势明细">
            <Table
              rowKey="month"
              pagination={false}
              dataSource={trendData}
              columns={[
                {
                  title: '月份',
                  dataIndex: 'month',
                  key: 'month',
                  render: (value: string) => formatMonthDisplay(value),
                },
                {
                  title: '总成本',
                  dataIndex: 'totalCost',
                  key: 'totalCost',
                  render: (value: number) => `¥${value.toLocaleString()}`,
                },
                {
                  title: '机票成本',
                  dataIndex: 'flightCost',
                  key: 'flightCost',
                  render: (value: number) => `¥${value.toLocaleString()}`,
                },
                {
                  title: '酒店成本',
                  dataIndex: 'hotelCost',
                  key: 'hotelCost',
                  render: (value: number) => `¥${value.toLocaleString()}`,
                },
                {
                  title: '火车票成本',
                  dataIndex: 'trainCost',
                  key: 'trainCost',
                  render: (value: number) => `¥${value.toLocaleString()}`,
                },
                {
                  title: '工作日平均工时',
                  dataIndex: 'avgWorkHours',
                  key: 'avgWorkHours',
                  render: (value: number) => `${value.toFixed(2)} h`,
                },
                {
                  title: '节假日平均工时',
                  dataIndex: 'holidayAvgWorkHours',
                  key: 'holidayAvgWorkHours',
                  render: (value: number) => `${value.toFixed(2)} h`,
                },
                {
                  title: '异常记录数',
                  dataIndex: 'anomalyCount',
                  key: 'anomalyCount',
                },
                {
                  title: '项目数量',
                  dataIndex: 'projectCount',
                  key: 'projectCount',
                },
              ]}
            />
          </Card>
        </>
      )}
    </Space>
  )
}

export default TrendAnalysis
