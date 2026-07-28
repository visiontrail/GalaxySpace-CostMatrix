import { useMemo } from 'react'
import { Alert, Card, Typography } from 'antd'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { AgentChartSpec } from '@/types'

const { Text, Title } = Typography

const AgentChart = ({ spec }: { spec: AgentChartSpec }) => {
  const valid = useMemo(() => {
    const option = spec?.echarts_option
    return Boolean(
      spec?.title &&
      option &&
      typeof option === 'object' &&
      ('series' in option || 'xAxis' in option || 'dataset' in option)
    )
  }, [spec])

  if (!valid) {
    return <Alert type="error" showIcon message="图表配置无效，无法渲染" />
  }

  return (
    <Card className="agent-chart-card" variant="borderless">
      <div className="agent-chart-heading">
        <div>
          <Text className="agent-chart-kicker">ECHARTS · {spec.chart_type.toUpperCase()}</Text>
          <Title level={5}>{spec.title}</Title>
          {spec.subtitle && <Text type="secondary">{spec.subtitle}</Text>}
        </div>
      </div>
      <ReactECharts
        option={spec.echarts_option as EChartsOption}
        style={{ width: '100%', height: 380 }}
        notMerge
        lazyUpdate
        opts={{ renderer: 'canvas' }}
      />
    </Card>
  )
}

export default AgentChart
