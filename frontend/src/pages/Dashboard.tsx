import { useState, useEffect, useRef } from 'react'
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
  Spin,
} from 'antd'
import {
  DollarOutlined,
  ClockCircleOutlined,
  WarningOutlined,
  DownloadOutlined,
  ReloadOutlined,
  FileTextOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { AnalysisResult } from '@/types'
import { analyzeExcel, exportPpt } from '@/services/api'
import { useMonthContext } from '@/contexts/MonthContext'

const { Title } = Typography

const Dashboard = () => {
  const [data, setData] = useState<AnalysisResult | null>(null)
  const [exportingPpt, setExportingPpt] = useState(false)
  const [loadingData, setLoadingData] = useState(false)
  const { selectedMonth } = useMonthContext()

  const departmentCostChartRef = useRef<any>(null)
  const projectCostChartRef = useRef<any>(null)

  useEffect(() => {
    if (selectedMonth) {
      fetchAnalysis()
    }
  }, [selectedMonth])

  const fetchAnalysis = async () => {
    if (!selectedMonth) return

    setLoadingData(true)
    try {
      const result = await analyzeExcel(undefined, {
        months: [selectedMonth]
      })
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

  const handleExportPpt = async () => {
    if (!data || !selectedMonth) return

    setExportingPpt(true)
    try {
      const charts = [
        {
          title: '部门成本分布',
          image: departmentCostChartRef.current?.getDataURL({ type: 'png' }) || ''
        },
        {
          title: '项目成本TOP10',
          image: projectCostChartRef.current?.getDataURL({ type: 'png' }) || ''
        }
      ]

      const blob = await exportPpt(data, charts)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `CostMatrix_Report_${selectedMonth || 'data'}.pptx`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      message.success('PPT导出成功')
    } catch (error: any) {
      message.error(error.message || 'PPT导出失败')
    } finally {
      setExportingPpt(false)
    }
  }

  const formatMonth = (month: string) => {
    const [year, monthNum] = month.split('-')
    return `${year}年${monthNum}月`
  }

  const departmentCostOption: EChartsOption = {
    title: { text: '部门成本分布', left: 'center' },
    tooltip: { trigger: 'item', formatter: '{b}: {c}元 ({d}%)' },
    legend: { orient: 'vertical', left: 'left' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 10,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: { show: false, position: 'center' },
      emphasis: {
        label: {
          show: true,
          fontSize: 20,
          fontWeight: 'bold'
        }
      },
      labelLine: { show: false },
      data: data?.department_stats.map(d => ({ name: d.dept, value: d.cost })) || []
    }]
  }

  const projectCostOption: EChartsOption = {
    title: { text: '项目成本TOP10', left: 'center' },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: data?.project_top10.map(p => `${p.code}\n${p.name}`) || [] },
    yAxis: { type: 'value' },
    series: [{
      data: data?.project_top10.map(p => p.cost) || [],
      type: 'bar',
      itemStyle: { color: '#1890ff' }
    }]
  }

  const anomalyColumns = [
    { title: '日期', dataIndex: 'date', key: 'date' },
    { title: '姓名', dataIndex: 'name', key: 'name' },
    { title: '部门', dataIndex: 'dept', key: 'dept' },
    { title: '异常类型', dataIndex: 'type', key: 'type', render: (type: string) => <Tag color="red">{type}</Tag> },
    { title: '详细说明', dataIndex: 'detail', key: 'detail' }
  ]

  if (!selectedMonth) {
    return (
      <div style={{ textAlign: 'center', marginTop: 100 }}>
        <Empty description="请选择月份查看数据" />
      </div>
    )
  }

  return (
    <div>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Title level={3} style={{ margin: 0 }}>
          {formatMonth(selectedMonth)} 数据看板
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchAnalysis} loading={loadingData}>
            刷新
          </Button>
          <Button icon={<DownloadOutlined />} onClick={handleExportPpt} loading={exportingPpt}>
            导出PPT
          </Button>
        </Space>
      </Space>

      {loadingData ? (
        <div style={{ textAlign: 'center', padding: 100 }}>
          <Spin size="large" />
        </div>
      ) : data ? (
        <>
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={6}>
              <Card>
                <Statistic
                  title="总成本"
                  value={data.summary.total_cost}
                  precision={2}
                  prefix={<DollarOutlined />}
                  suffix="元"
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="总订单数"
                  value={data.summary.total_orders}
                  prefix={<FileTextOutlined />}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="异常数量"
                  value={data.summary.anomaly_count}
                  valueStyle={{ color: '#cf1322' }}
                  prefix={<WarningOutlined />}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="平均工时"
                  value={data.summary.avg_work_hours}
                  precision={2}
                  prefix={<ClockCircleOutlined />}
                  suffix="小时"
                />
              </Card>
            </Col>
          </Row>

          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={12}>
              <Card>
                <ReactECharts
                  ref={departmentCostChartRef}
                  option={departmentCostOption}
                  style={{ height: 400 }}
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card>
                <ReactECharts
                  ref={projectCostChartRef}
                  option={projectCostOption}
                  style={{ height: 400 }}
                />
              </Card>
            </Col>
          </Row>

          <Card title="异常记录" style={{ marginBottom: 24 }}>
            <Table
              dataSource={data.anomalies}
              columns={anomalyColumns}
              rowKey={(record) => `${record.date}-${record.name}`}
              pagination={{ pageSize: 10 }}
            />
          </Card>
        </>
      ) : (
        <Empty description="暂无数据" />
      )}
    </div>
  )
}

export default Dashboard
