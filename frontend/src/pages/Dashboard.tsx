import { useState, useEffect } from 'react'
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
  Divider
} from 'antd'
import { 
  DollarOutlined, 
  ClockCircleOutlined, 
  WarningOutlined,
  DownloadOutlined,
  ReloadOutlined,
  TeamOutlined,
  ProjectOutlined
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { AnalysisResult, Anomaly, DepartmentStat, ProjectTop10 } from '@/types'
import { exportResults } from '@/services/api'

const { Title, Text } = Typography

const Dashboard = () => {
  const [data, setData] = useState<AnalysisResult | null>(null)
  const [currentFile, setCurrentFile] = useState<string>('')
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = () => {
    const savedData = localStorage.getItem('dashboard_data')
    const savedFile = localStorage.getItem('current_file')
    
    if (savedData) {
      try {
        const parsedData = JSON.parse(savedData)
        // 确保关键属性存在，提供默认值
        const safeData = {
          ...parsedData,
          department_stats: parsedData.department_stats || [],
          project_top10: parsedData.project_top10 || [],
          anomalies: parsedData.anomalies || [],
          summary: parsedData.summary || {
            total_cost: 0,
            avg_work_hours: 0,
            anomaly_count: 0
          }
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

  // 空状态
  if (!data || !data.department_stats || !data.project_top10 || !data.anomalies) {
    return (
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
    )
  }

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
        <Col xs={24} sm={12} lg={8}>
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
        <Col xs={24} sm={12} lg={8}>
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
        <Col xs={24} sm={12} lg={8}>
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
      </Row>

      {/* 次要指标卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12}>
          <Card variant="borderless" hoverable>
            <Statistic
              title="部门数量"
              value={data.department_stats.length}
              prefix={<TeamOutlined />}
              suffix="个"
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card variant="borderless" hoverable>
            <Statistic
              title="项目数量"
              value={data.project_top10.length}
              prefix={<ProjectOutlined />}
              suffix="个"
              valueStyle={{ color: '#eb2f96' }}
            />
          </Card>
        </Col>
      </Row>

      <Divider orientation="left">数据可视化</Divider>

      {/* 图表区域 - 第一行 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={12}>
          <Card variant="borderless" hoverable>
            <ReactECharts 
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
              option={deptHeadcountCostScatterOption} 
              style={{ height: 400 }} 
              notMerge={true}
              lazyUpdate={true}
            />
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
        title={<><ProjectOutlined /> 项目成本详情（Top 10）</>}
        variant="borderless"
        style={{ marginBottom: 24 }}
      >
        <Table
          dataSource={data.project_top10}
          columns={projectColumns}
          rowKey="code"
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
