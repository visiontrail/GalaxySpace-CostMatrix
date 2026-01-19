import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card,
  Row,
  Col,
  Statistic,
  Table,
  Tag,
  Button,
  message,
  Empty,
  Space,
  Typography,
  Divider,
  Spin,
} from 'antd'
import {
  DollarOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  ExclamationCircleOutlined,
  DownloadOutlined,
  ReloadOutlined,
  TeamOutlined,
  ProjectOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { AnalysisResult, DepartmentStat, ProjectTop10 } from '@/types'
import { analyzeExcel } from '@/services/api'
import { useMonthContext } from '@/contexts/MonthContext'

const { Title, Text } = Typography

const Dashboard = () => {
  const navigate = useNavigate()
  const [data, setData] = useState<AnalysisResult | null>(null)
  const [exporting, setExporting] = useState(false)
  const [loadingData, setLoadingData] = useState(false)
  const { selectedMonth, availableMonths, refreshMonths } = useMonthContext()

  // ECharts 图表引用，用于导出图片
  const departmentCostChartRef = useRef<any>(null)
  const projectCostChartRef = useRef<any>(null)
  const departmentHoursChartRef = useRef<any>(null)
  const deptHeadcountCostChartRef = useRef<any>(null)
  const flightOverTypeChartRef = useRef<any>(null)

  useEffect(() => {
    refreshMonths()
  }, [refreshMonths])

  useEffect(() => {
    if (selectedMonth) {
      fetchData()
    } else {
      setData(null)
    }
  }, [selectedMonth])

  const fetchData = async () => {
    if (!selectedMonth) {
      return
    }

    setLoadingData(true)
    try {
      // 调用数据库分析API，传递月份参数
      const result = await analyzeExcel(undefined, { months: [selectedMonth] })
      if (result.success && result.data) {
        setData(result.data)
      } else {
        message.error(result.message || '数据加载失败')
      }
    } catch (error: any) {
      message.error(error.message || '数据加载失败')
    } finally {
      setLoadingData(false)
    }
  }

  const handleExport = async () => {
    if (!selectedMonth) {
      message.warning('请先选择月份')
      return
    }

    setExporting(true)
    try {
      // 导出功能需要文件路径，这里暂时禁用或需要后端支持按月份导出
      message.warning('数据库模式下的导出功能正在开发中')
    } catch (error: any) {
      message.error(error.message || '导出失败')
    } finally {
      setExporting(false)
    }
  }

  // 空状态 - 没有选择月份
  if (!selectedMonth || availableMonths.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Empty
          description={availableMonths.length === 0 ? "暂无数据，请先上传 Excel 文件" : "请从左侧选择月份查看数据"}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          {availableMonths.length === 0 && (
            <Button type="primary" href="/upload">
              立即上传
            </Button>
          )}
        </Empty>
      </div>
    )
  }

  // 加载状态
  if (loadingData || !data) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" tip={`正在加载 ${selectedMonth} 数据...`} />
      </div>
    )
  }

  const overStandardBreakdown = {
    total: data.summary.over_standard_breakdown?.total ?? data.summary.over_standard_count ?? 0,
    flight: data.summary.over_standard_breakdown?.flight ?? 0,
    hotel: data.summary.over_standard_breakdown?.hotel ?? 0,
    train: data.summary.over_standard_breakdown?.train ?? 0
  }
  const overStandardCount = data.summary.over_standard_count ?? overStandardBreakdown.total
  const orderBreakdown = {
    total: data.summary.order_breakdown?.total ?? data.summary.total_orders ?? 0,
    flight: data.summary.order_breakdown?.flight ?? 0,
    hotel: data.summary.order_breakdown?.hotel ?? 0,
    train: data.summary.order_breakdown?.train ?? 0
  }
  const flightOverTypeBreakdown = data.summary.flight_over_type_breakdown || {}
  const flightOverTypeData = Object.entries(flightOverTypeBreakdown)
    .filter(([, value]) => value > 0)
    .map(([name, value]) => ({
      name,
      value
    }))
    .sort((a, b) => b.value - a.value)
  const flightOverTypeTotal = flightOverTypeData.reduce((sum, item) => sum + item.value, 0)

  // ============ ECharts 配置 ============

  // 部门成本饼图
  const departmentCostPieOption: EChartsOption = {
    title: {
      text: '部门成本分布',
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },
    tooltip: {
      trigger: 'item',
      formatter: '{b}<br/>成本: ¥{c}<br/>占比: {d}%'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'middle',
      type: 'scroll',
      pageButtonPosition: 'end'
    },
    series: [
      {
        name: '部门成本',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['40%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: true,
          formatter: (params: any) => {
            const name = params.name || ''
            const percent = params.percent || 0
            const formattedName = name.replace(/(.{5})/g, '$1\n')
            return `${formattedName}\n${percent}%`
          }
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold'
          }
        },
        data: data.department_stats
          .sort((a, b) => b.cost - a.cost)
          .slice(0, 15)
          .map(item => ({
            value: item.cost,
            name: item.dept
          }))
      }
    ]
  }

  // 项目成本柱状图 (Top 20)
  const projectCostBarOption: EChartsOption = {
    title: {
      text: '项目成本排名（Top 20）',
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: (params: any) => {
        const item = params[0]
        return `${item.name}<br/>成本: ¥${item.value.toLocaleString()}`
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: 50,
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: '成本 (元)',
      axisLabel: {
        formatter: (value: number) => `¥${(value / 10000).toFixed(0)}万`
      }
    },
    yAxis: {
      type: 'category',
      data: data.project_top10
        .map(item => item.name.length > 10 ? item.name.substring(0, 10) + '...' : item.name)
        .reverse(),
      axisLabel: {
        interval: 0
      }
    },
    series: [
      {
        name: '成本',
        type: 'bar',
        data: data.project_top10.map(item => item.cost).reverse(),
        itemStyle: {
          color: '#5470c6',
          borderRadius: [0, 5, 5, 0]
        },
        label: {
          show: true,
          position: 'right',
          formatter: (params: any) => `¥${params.value.toLocaleString()}`
        }
      }
    ]
  }

  // 部门工时柱状图
  const departmentHoursBarOption: EChartsOption = {
    title: {
      text: '部门平均工时',
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: 50,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: data.department_stats
        .filter(item => item.dept !== '未知部门')
        .sort((a, b) => b.avg_hours - a.avg_hours)
        .slice(0, 15)
        .map(item => item.dept),
      axisLabel: {
        interval: 0,
        rotate: 45
      }
    },
    yAxis: {
      type: 'value',
      name: '平均工时 (小时)',
      axisLabel: {
        formatter: '{value} h'
      }
    },
    series: [
      {
        name: '平均工时',
        type: 'bar',
        data: data.department_stats
          .filter(item => item.dept !== '未知部门')
          .sort((a, b) => b.avg_hours - a.avg_hours)
          .slice(0, 15)
          .map(item => item.avg_hours),
        itemStyle: {
          color: '#91cc75',
          borderRadius: [5, 5, 0, 0]
        },
        label: {
          show: true,
          position: 'top',
          formatter: (params: any) => `${params.value.toFixed(1)}h`
        }
      }
    ]
  }

  // 部门人数 vs 成本散点图
  const deptHeadcountCostScatterOption: EChartsOption = {
    title: {
      text: '部门人数与成本关系',
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const dept = data.department_stats[params.dataIndex]
        return `${dept.dept}<br/>人数: ${dept.headcount}<br/>成本: ¥${dept.cost.toLocaleString()}`
      }
    },
    grid: {
      left: '3%',
      right: '15%',
      bottom: '3%',
      top: 50,
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: '人数',
      splitLine: {
        show: true
      }
    },
    yAxis: {
      type: 'value',
      name: '成本 (元)',
      axisLabel: {
        formatter: (value: number) => `¥${(value / 10000).toFixed(0)}万`
      },
      splitLine: {
        show: true
      }
    },
    graphic: [
      {
        type: 'text',
        left: '15%',
        top: '30%',
        style: {
          text: '小型高成本\n(人均成本高)',
          fontSize: 12,
          fill: '#999',
          fontWeight: 'lighter',
          lineHeight: 16
        }
      },
      {
        type: 'text',
        right: '15%',
        bottom: '30%',
        style: {
          text: '大型低成本\n(人均成本低)',
          fontSize: 12,
          fill: '#999',
          fontWeight: 'lighter',
          lineHeight: 16
        }
      }
    ],
    series: [
      {
        type: 'scatter',
        symbolSize: (data: any) => Math.max(10, Math.min(30, data[0] * 1.5)),
        data: data.department_stats.map((item, index) => ({
          value: [item.headcount, item.cost],
          itemStyle: {
            color: [
              '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
              '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#1890ff',
              '#52c41a', '#faad14', '#f5222d', '#13c2c2', '#722ed1'
            ][index % 15]
          }
        })),
        label: {
          show: true,
          position: 'right',
          formatter: (params: any) => {
            const dept = data.department_stats[params.dataIndex]
            const sortedByCost = [...data.department_stats].sort((a, b) => b.cost - a.cost)
            const sortedByHeadcount = [...data.department_stats].sort((a, b) => b.headcount - a.headcount)
            const topCostIndex = sortedByCost.findIndex(d => d.dept === dept.dept)
            const topHeadcountIndex = sortedByHeadcount.findIndex(d => d.dept === dept.dept)
            if (topCostIndex < 10 || topHeadcountIndex < 5) {
              return dept.dept
            }
            return ''
          },
          fontSize: 10,
          color: '#333',
          backgroundColor: 'rgba(255, 255, 255, 0.7)',
          padding: [2, 4],
          borderRadius: 3,
          borderWidth: 1,
          borderColor: '#ddd'
        },
        labelLayout: {
          hideOverlap: true
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 12,
            fontWeight: 'bold',
            backgroundColor: 'rgba(255, 255, 255, 0.9)',
            padding: [3, 6]
          },
          itemStyle: {
            borderColor: '#fff',
            borderWidth: 2,
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.3)'
          }
        }
      }
    ]
  }

  // 超标订单占比
  const compliantOrders = Math.max(orderBreakdown.total - overStandardCount, 0)
  const overStandardPieOption: EChartsOption = {
    title: {
      text: '超标订单占比',
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },
    tooltip: {
      trigger: 'item',
      formatter: '{b}<br/>订单数: {c} ({d}%)'
    },
    legend: {
      orient: 'horizontal',
      bottom: 0
    },
    series: [
      {
        name: '订单',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: true,
          formatter: '{b}: {d}%'
        },
        data: [
          { value: overStandardCount, name: '超标订单' },
          { value: compliantOrders, name: '合规订单' }
        ]
      }
    ]
  }

  // 机票超标类型分布
  const flightOverTypeBarOption: EChartsOption = {
    title: {
      text: '机票超标类型分布',
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: (params: any) => {
        const item = params[0]
        return `${item.name}<br/>超标订单: ${item.value} 单`
      }
    },
    grid: {
      left: '5%',
      right: '5%',
      bottom: '5%',
      top: 60,
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: '订单数',
      axisLabel: {
        formatter: '{value} 单'
      }
    },
    yAxis: {
      type: 'category',
      data: flightOverTypeData.map(item => item.name),
      axisLabel: {
        interval: 0
      }
    },
    series: [
      {
        type: 'bar',
        data: flightOverTypeData.map(item => item.value),
        itemStyle: {
          color: '#73c0de',
          borderRadius: [0, 6, 6, 0]
        },
        label: {
          show: true,
          position: 'right',
          formatter: (params: any) => `${params.value} 单`
        }
      }
    ]
  }

  // ============ 表格列定义 ============

  // 部门统计表格列
  const deptColumns = [
    {
      title: '部门',
      dataIndex: 'dept',
      key: 'dept',
      fixed: 'left' as const,
      width: 150,
      sorter: (a: DepartmentStat, b: DepartmentStat) => a.dept.localeCompare(b.dept)
    },
    {
      title: '成本 (元)',
      dataIndex: 'cost',
      key: 'cost',
      width: 150,
      sorter: (a: DepartmentStat, b: DepartmentStat) => a.cost - b.cost,
      render: (value: number) => (
        <Text strong style={{ color: '#1890ff' }}>
          ¥{value.toLocaleString()}
        </Text>
      )
    },
    {
      title: '平均工时 (小时)',
      dataIndex: 'avg_hours',
      key: 'avg_hours',
      width: 150,
      sorter: (a: DepartmentStat, b: DepartmentStat) => a.avg_hours - b.avg_hours,
      render: (value: number) => `${value.toFixed(1)} h`
    },
    {
      title: '人数',
      dataIndex: 'headcount',
      key: 'headcount',
      width: 100,
      sorter: (a: DepartmentStat, b: DepartmentStat) => a.headcount - b.headcount,
      render: (value: number) => (
        <Tag color="blue">{value} 人</Tag>
      )
    },
    {
      title: '人均成本 (元)',
      key: 'avg_cost',
      width: 150,
      sorter: (a: DepartmentStat, b: DepartmentStat) =>
        (a.cost / a.headcount) - (b.cost / b.headcount),
      render: (_: any, record: DepartmentStat) =>
        `¥${(record.cost / record.headcount).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
    }
  ]

  // 项目表格列
  const projectColumns = [
    {
      title: '项目代码',
      dataIndex: 'code',
      key: 'code',
      width: 120,
      fixed: 'left' as const,
      render: (value: string) => value === 'nan' ? '未知编号' : value
    },
    {
      title: '项目名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
      width: 200,
      render: (value: string) => value === 'nan' ? '未知项目' : value
    },
    {
      title: '成本 (元)',
      dataIndex: 'cost',
      key: 'cost',
      width: 150,
      sorter: (a: ProjectTop10, b: ProjectTop10) => a.cost - b.cost,
      render: (value: number) => (
        <Text strong style={{ color: '#52c41a' }}>
          ¥{value.toLocaleString()}
        </Text>
      )
    },
    {
      title: '机票 (元)',
      dataIndex: 'flight_cost',
      key: 'flight_cost',
      width: 120,
      sorter: (a: any, b: any) => (a.flight_cost || 0) - (b.flight_cost || 0),
      render: (value: number) => (
        <Text style={{ color: '#1890ff' }}>
          ¥{(value || 0).toLocaleString()}
        </Text>
      )
    },
    {
      title: '酒店 (元)',
      dataIndex: 'hotel_cost',
      key: 'hotel_cost',
      width: 120,
      sorter: (a: any, b: any) => (a.hotel_cost || 0) - (b.hotel_cost || 0),
      render: (value: number) => (
        <Text style={{ color: '#722ed1' }}>
          ¥{(value || 0).toLocaleString()}
        </Text>
      )
    },
    {
      title: '火车票 (元)',
      dataIndex: 'train_cost',
      key: 'train_cost',
      width: 120,
      sorter: (a: any, b: any) => (a.train_cost || 0) - (b.train_cost || 0),
      render: (value: number) => (
        <Text style={{ color: '#fa8c16' }}>
          ¥{(value || 0).toLocaleString()}
        </Text>
      )
    }
  ]

  const formatMonthDisplay = (month: string) => {
    const [year, monthNum] = month.split('-')
    return `${year}年${monthNum}月`
  }

  return (
    <div>
      {/* 页面标题和操作按钮 */}
      <Space style={{ marginBottom: 24, width: '100%', justifyContent: 'space-between' }}>
        <div>
          <Title level={2} style={{ margin: 0 }}>
            CostMatrix 成本管理中心
          </Title>
          <Text type="secondary">
            当前统计月份: <Tag color="blue">{formatMonthDisplay(selectedMonth)}</Tag>
          </Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loadingData}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            loading={exporting}
            onClick={handleExport}
          >
            导出分析结果
          </Button>
        </Space>
      </Space>

      {/* 核心指标卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="总成本"
              value={data.summary.total_cost}
              precision={2}
              prefix={<DollarOutlined />}
              suffix="元"
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="平均工时"
              value={data.summary.avg_work_hours}
              precision={1}
              prefix={<ClockCircleOutlined />}
              suffix="小时"
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card variant="borderless" hoverable onClick={() => navigate('/anomalies')} style={{ cursor: 'pointer' }}>
            <Statistic
              title="异常记录"
              value={data.summary.anomaly_count}
              prefix={<WarningOutlined />}
              suffix="条"
              valueStyle={{ color: '#cf1322' }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              点击查看详情
            </Text>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="超标订单"
              value={overStandardCount}
              prefix={<ExclamationCircleOutlined />}
              suffix="单"
              valueStyle={{ color: '#fa8c16' }}
            />
            <Text type="secondary">
              航 {overStandardBreakdown.flight} / 酒 {overStandardBreakdown.hotel} / 火 {overStandardBreakdown.train}
            </Text>
          </Card>
        </Col>
      </Row>

      {/* 次要指标卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12}>
          <Card variant="borderless" hoverable onClick={() => navigate('/departments')} style={{ cursor: 'pointer' }}>
            <Statistic
              title="部门数量"
              value={data.department_stats.length}
              prefix={<TeamOutlined />}
              suffix="个"
              valueStyle={{ color: '#722ed1' }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              点击查看详情
            </Text>
          </Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card variant="borderless" hoverable onClick={() => navigate('/projects')} style={{ cursor: 'pointer' }}>
            <Statistic
              title="项目数量"
              value={data.summary.total_project_count ?? data.project_top10.length}
              prefix={<ProjectOutlined />}
              suffix="个"
              valueStyle={{ color: '#eb2f96' }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              点击查看详情
            </Text>
          </Card>
        </Col>
      </Row>

      <Divider orientation="left">数据可视化</Divider>

      {/* 图表区域 - 第一行 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={12}>
          <Card variant="borderless" hoverable>
            <ReactECharts
              ref={departmentCostChartRef}
              option={departmentCostPieOption}
              style={{ height: 400 }}
              notMerge={true}
              lazyUpdate={true}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card variant="borderless" hoverable>
            <ReactECharts
              ref={projectCostChartRef}
              option={projectCostBarOption}
              style={{ height: 400 }}
              notMerge={true}
              lazyUpdate={true}
            />
          </Card>
        </Col>
      </Row>

      {/* 图表区域 - 第二行 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={12}>
          <Card variant="borderless" hoverable>
            <ReactECharts
              ref={departmentHoursChartRef}
              option={departmentHoursBarOption}
              style={{ height: 400 }}
              notMerge={true}
              lazyUpdate={true}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card variant="borderless" hoverable>
            <ReactECharts
              ref={deptHeadcountCostChartRef}
              option={deptHeadcountCostScatterOption}
              style={{ height: 400 }}
              notMerge={true}
              lazyUpdate={true}
            />
          </Card>
        </Col>
      </Row>

      {/* 图表区域 - 第三行 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={12}>
          <Card variant="borderless" hoverable>
            <Space direction="vertical" size="small">
              <Text strong>总订单：{orderBreakdown.total}</Text>
              <Text type="warning">超标订单：{overStandardCount}</Text>
            </Space>
            <ReactECharts
              option={overStandardPieOption}
              style={{ height: 360 }}
              notMerge={true}
              lazyUpdate={true}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card variant="borderless" hoverable>
            <Space direction="vertical" size="small">
              <Text strong>机票超标订单：{overStandardBreakdown.flight}</Text>
              <Text type="secondary">
                类型标签计数：{flightOverTypeTotal}（{flightOverTypeData.length} 类）
              </Text>
            </Space>
            {flightOverTypeData.length > 0 ? (
              <ReactECharts
                ref={flightOverTypeChartRef}
                option={flightOverTypeBarOption}
                style={{ height: 360 }}
                notMerge={true}
                lazyUpdate={true}
              />
            ) : (
              <div style={{ height: 360, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Empty
                  description="暂无机票超标类型数据"
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                />
              </div>
            )}
          </Card>
        </Col>
      </Row>

      <Divider orientation="left">详细数据</Divider>

      {/* 部门统计表格 */}
      <Card
        title={<><TeamOutlined /> 部门统计详情</>}
        style={{ marginBottom: 24 }}
      >
        <Table
          dataSource={data.department_stats}
          columns={deptColumns}
          rowKey="dept"
          pagination={{
            pageSize: 10,
            showSizeChanger: false,
            showTotal: (total) => `共 ${total} 个部门`,
          }}
          scroll={{ x: 800 }}
          size="middle"
        />
      </Card>

      {/* 项目统计表格 */}
      <Card
        title={<><ProjectOutlined /> 项目成本详情（Top 20）</>}
        style={{ marginBottom: 24 }}
      >
        <Table
          dataSource={data.project_top10}
          columns={projectColumns}
          rowKey={(record) => record.code || '其他'}
          pagination={false}
          scroll={{ x: 600 }}
          size="middle"
        />
      </Card>
    </div>
  )
}

export default Dashboard
