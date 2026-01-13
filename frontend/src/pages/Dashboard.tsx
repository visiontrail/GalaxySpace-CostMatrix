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
  Popconfirm,
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
  FileTextOutlined,
  DeleteOutlined
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { AnalysisResult, Anomaly, DepartmentStat, ProjectTop10, UploadRecord } from '@/types'
import { analyzeExcel, clearData, exportResults, exportPpt } from '@/services/api'
import { useOutletContext } from 'react-router-dom'
import type { UploadContextValue } from '@/layouts/MainLayout'

const { Title, Text } = Typography

const Dashboard = () => {
  const navigate = useNavigate()
  const [data, setData] = useState<AnalysisResult | null>(null)
  const [currentFile, setCurrentFile] = useState<string>('')
  const [currentFileName, setCurrentFileName] = useState<string>('')
  const [exporting, setExporting] = useState(false)
  const [exportingPpt, setExportingPpt] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [loadingData, setLoadingData] = useState(false)
  const { selectedUpload, refreshUploads } = useOutletContext<UploadContextValue>()

  // ECharts 图表引用，用于导出图片
  const departmentCostChartRef = useRef<any>(null)
  const projectCostChartRef = useRef<any>(null)
  const departmentHoursChartRef = useRef<any>(null)
  const deptHeadcountCostChartRef = useRef<any>(null)
  const flightOverTypeChartRef = useRef<any>(null)

  useEffect(() => {
    if (selectedUpload?.file_path) {
      fetchAnalysis(selectedUpload)
    } else {
      loadData()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedUpload?.file_path])

  const fetchAnalysis = async (upload: UploadRecord) => {
    setLoadingData(true)
    try {
      const result = await analyzeExcel(upload.file_path)
      if (result.success && result.data) {
        setData(result.data)
        setCurrentFile(upload.file_path)
        setCurrentFileName(upload.file_name)
        localStorage.setItem('dashboard_data', JSON.stringify(result.data))
        localStorage.setItem('current_file', upload.file_path)
        localStorage.setItem('current_file_name', upload.file_name)
      } else {
        message.error(result.message || '数据加载失败')
      }
    } catch (error: any) {
      message.error(error.message || '数据加载失败')
    } finally {
      setLoadingData(false)
      refreshUploads()
    }
  }

  const loadData = () => {
    const savedData = localStorage.getItem('dashboard_data')
    const savedFile = localStorage.getItem('current_file')
    const savedFileName = localStorage.getItem('current_file_name')
    
    if (savedData) {
      try {
        const parsedData = JSON.parse(savedData)
        // 确保关键属性存在，提供默认值
        const summary = parsedData.summary || {}
        const safeSummary = {
          total_cost: summary.total_cost ?? 0,
          avg_work_hours: summary.avg_work_hours ?? 0,
          anomaly_count: summary.anomaly_count ?? 0,
          total_orders: summary.total_orders ?? summary.order_breakdown?.total ?? 0,
          order_breakdown: summary.order_breakdown || {
            total: summary.total_orders ?? 0,
            flight: 0,
            hotel: 0,
            train: 0
          },
          over_standard_count: summary.over_standard_count ?? summary.over_standard_breakdown?.total ?? 0,
          over_standard_breakdown: summary.over_standard_breakdown || {
            total: 0,
            flight: 0,
            hotel: 0,
            train: 0
          },
          flight_over_type_breakdown: summary.flight_over_type_breakdown 
            || summary.over_standard_breakdown?.flight_over_types 
            || {}
        }
        const safeData = {
          ...parsedData,
          department_stats: parsedData.department_stats || [],
          project_top10: parsedData.project_top10 || [],
          anomalies: parsedData.anomalies || [],
          summary: safeSummary
        }
        setData(safeData)
      } catch (error) {
        console.error('Failed to parse dashboard data:', error)
        message.error('数据加载失败')
      }
    }
    
    if (savedFile) {
      setCurrentFile(savedFile)
    }
    if (savedFileName) {
      setCurrentFileName(savedFileName)
    }
  }

  const handleExport = async () => {
    if (!currentFile) {
      message.warning('请先上传并分析文件')
      return
    }

    setExporting(true)
    try {
      const blob = await exportResults(currentFile)
      
      // 创建下载链接
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `分析结果_${new Date().getTime()}.xlsx`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      
      message.success('导出成功！')
    } catch (error: any) {
      message.error(error.message || '导出失败')
    } finally {
      setExporting(false)
    }
  }

  const handleExportPpt = async () => {
    if (!data) {
      message.warning('暂无数据可导出')
      return
    }

    setExportingPpt(true)

    try {
      // 1. 捕获所有图表为 base64 图片
      const charts = []

      // 获取 ECharts 实例并导出图片
      const chartRefs = [
        { ref: departmentCostChartRef, title: '部门成本分布' },
        { ref: projectCostChartRef, title: '项目成本排名（Top 20）' },
        { ref: departmentHoursChartRef, title: '部门平均工时' },
        { ref: deptHeadcountCostChartRef, title: '部门人数与成本关系' },
        { ref: flightOverTypeChartRef, title: '机票超标类型分布' }
      ]

      for (const { ref, title } of chartRefs) {
        if (ref.current) {
          const echartInstance = ref.current.getEchartsInstance()
          const imageBase64 = echartInstance.getDataURL({
            type: 'png',
            pixelRatio: 2,  // 高清图片
            backgroundColor: '#fff'
          })
          charts.push({ title, image: imageBase64 })
        }
      }

      // 2. 调用 API 导出 PPT
      const blob = await exportPpt(data, charts)

      // 3. 下载文件
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `CorpPilot分析报告_${new Date().getTime()}.pptx`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)

      message.success('PPT 导出成功！')
    } catch (error: any) {
      message.error(error.message || 'PPT 导出失败')
    } finally {
      setExportingPpt(false)
    }
  }

  const handleClearData = async () => {
    if (!currentFile) {
      message.warning('暂无可清除的数据文件，请先上传并选择文件')
      return
    }

    setClearing(true)
    try {
      await clearData(currentFile)
      message.success('当前数据文件已清除，请重新上传')
    } catch (error: any) {
      message.error(error.message || '清除数据失败（本地缓存已清空）')
    } finally {
      localStorage.removeItem('dashboard_data')
      localStorage.removeItem('current_file')
      localStorage.removeItem('current_file_name')
      setData(null)
      setCurrentFile('')
      setCurrentFileName('')
      setClearing(false)
      refreshUploads()
    }
  }

  // 空状态
  if (!data || !data.department_stats || !data.project_top10 || !data.anomalies) {
    return (
      <Spin spinning={loadingData} tip="正在加载数据">
        <div style={{ textAlign: 'center', padding: '100px 0' }}>
          <Empty
            description="暂无数据，请先上传 Excel 文件进行分析"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Button type="primary" href="/upload">
              立即上传
            </Button>
          </Empty>
        </div>
      </Spin>
    )
  }

  if (loadingData) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" tip="正在加载数据..." />
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
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: true,
          formatter: '{b}: {d}%'
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
      right: '7%',
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
    series: [
      {
        type: 'scatter',
        symbolSize: 20,
        data: data.department_stats.map(item => [item.headcount, item.cost]),
        itemStyle: {
          color: '#ee6666'
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
      fixed: 'left' as const
    },
    {
      title: '项目名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
      width: 200
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
    }
  ]

  // 异常记录表格列
  const anomalyColumns = [
    {
      title: '日期',
      dataIndex: 'date',
      key: 'date',
      width: 120,
      sorter: (a: Anomaly, b: Anomaly) => a.date.localeCompare(b.date)
    },
    {
      title: '姓名',
      dataIndex: 'name',
      key: 'name',
      width: 100
    },
    {
      title: '部门',
      dataIndex: 'dept',
      key: 'dept',
      width: 120
    },
    {
      title: '异常类型',
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (type: string) => {
        const colorMap: Record<string, string> = {
          'Conflict': 'red',
          'Missing': 'orange',
          'Duplicate': 'purple',
          'Invalid': 'volcano'
        }
        return (
          <Tag color={colorMap[type] || 'default'}>
            {type}
          </Tag>
        )
      }
    },
    {
      title: '详细说明',
      dataIndex: 'detail',
      key: 'detail',
      ellipsis: true
    }
  ]

  return (
    <div>
      {/* 页面标题和操作按钮 */}
      <Space style={{ marginBottom: 24, width: '100%', justifyContent: 'space-between' }}>
        <Title level={2} style={{ margin: 0 }}>
          CorpPilot 管理驾驶舱
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadData}>
            刷新
          </Button>
          <Popconfirm
            title="确认清除当前数据？"
            description={`将删除当前数据文件${currentFileName ? `（${currentFileName}）` : ''}及其缓存，操作不可恢复。`}
            okText="确认清除"
            cancelText="取消"
            onConfirm={handleClearData}
          >
            <Button danger icon={<DeleteOutlined />} loading={clearing} disabled={!currentFile}>
              清除数据
            </Button>
          </Popconfirm>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            loading={exporting}
            onClick={handleExport}
          >
            导出分析结果
          </Button>
          <Button
            icon={<FileTextOutlined />}
            loading={exportingPpt}
            onClick={handleExportPpt}
          >
            导出 PPT
          </Button>
        </Space>
      </Space>

      {/* 核心指标卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card variant="borderless" hoverable>
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
          <Card variant="borderless" hoverable>
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
          <Card variant="borderless" hoverable>
            <Statistic
              title="异常记录"
              value={data.summary.anomaly_count}
              prefix={<WarningOutlined />}
              suffix="条"
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card variant="borderless" hoverable>
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
        variant="borderless"
        style={{ marginBottom: 24 }}
      >
        <Table
          dataSource={data.department_stats}
          columns={deptColumns}
          rowKey="dept"
          pagination={{ 
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 个部门`
          }}
          scroll={{ x: 800 }}
          size="middle"
        />
      </Card>

      {/* 项目统计表格 */}
      <Card
        title={<><ProjectOutlined /> 项目成本详情（Top 20 + 其他）</>}
        variant="borderless"
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

      {/* 异常记录表格 */}
      <Card 
        title={<><WarningOutlined /> 异常记录详情</>}
        variant="borderless"
        extra={
          <Tag color="red">
            共 {data.anomalies.length} 条异常
          </Tag>
        }
      >
        <Table
          dataSource={data.anomalies}
          columns={anomalyColumns}
          rowKey={(record) => `${record.date}-${record.name}-${record.type}`}
          pagination={{ 
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条异常记录`
          }}
          scroll={{ x: 800 }}
          size="middle"
        />
      </Card>
    </div>
  )
}

export default Dashboard
