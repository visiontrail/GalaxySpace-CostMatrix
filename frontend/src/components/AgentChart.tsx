import { useCallback, useMemo, useRef, useState } from 'react'
import { Alert, Card, Tooltip, Typography, message as antdMessage } from 'antd'
import { CopyOutlined, LoadingOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import type { AgentChartSpec } from '@/types'
import {
  copyPngToClipboard,
  downloadDataUrl,
  isImageClipboardSupported,
} from '@/utils/agentExport'

const { Text, Title } = Typography

const AgentChart = ({ spec }: { spec: AgentChartSpec }) => {
  const chartRef = useRef<ReactECharts | null>(null)
  const [copying, setCopying] = useState(false)

  const valid = useMemo(() => {
    const option = spec?.echarts_option
    return Boolean(
      spec?.title &&
      option &&
      typeof option === 'object' &&
      ('series' in option || 'xAxis' in option || 'dataset' in option)
    )
  }, [spec])

  const copyImage = useCallback(async () => {
    const instance = chartRef.current?.getEchartsInstance()
    if (!instance) return
    setCopying(true)
    try {
      // 图表本身透明背景，导出时补白底，粘贴到文档里才不会糊成一片。
      const dataUrl = instance.getDataURL({
        type: 'png',
        pixelRatio: 2,
        backgroundColor: '#ffffff',
      })
      if (isImageClipboardSupported()) {
        await copyPngToClipboard(dataUrl)
        antdMessage.success('图表图片已复制到剪贴板')
      } else {
        // HTTP 部署下浏览器禁用剪贴板写入，退化为下载，功能不至于失效。
        downloadDataUrl(dataUrl, `${spec.title || '图表'}.png`)
        antdMessage.warning('当前浏览器不支持复制图片，已改为下载')
      }
    } catch (error: any) {
      antdMessage.error(error?.message || '图表图片复制失败')
    } finally {
      setCopying(false)
    }
  }, [spec.title])

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
        <Tooltip title="复制图片到剪贴板">
          <button
            type="button"
            className="agent-chart-copy"
            onClick={copyImage}
            disabled={copying}
            aria-label="复制图片到剪贴板"
          >
            {copying ? <LoadingOutlined /> : <CopyOutlined />}
          </button>
        </Tooltip>
      </div>
      <ReactECharts
        ref={chartRef}
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
