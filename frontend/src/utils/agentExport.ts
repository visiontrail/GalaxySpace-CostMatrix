/**
 * Agent 回复的导出与剪贴板能力：复制 Markdown、导出 PDF、复制图表图片。
 *
 * PDF 走「html2canvas-pro 光栅化 + jsPDF 直接生成」，不依赖浏览器打印对话框，
 * 与 RavenAI 主项目的单条回复导出保持一致。
 */
import html2canvas from 'html2canvas-pro'
import { jsPDF } from 'jspdf'

export interface AgentPdfChart {
  title: string
  dataUrl: string
}

export interface AgentPdfOptions {
  /** 会话标题，作为 PDF 抬头 */
  title: string
  /** 已渲染好的回复 HTML（Markdown 转换结果） */
  contentHtml: string
  /** 回复内嵌的 ECharts 图片，按出现顺序 */
  charts?: AgentPdfChart[]
  model?: string | null
  durationMs?: number | null
}

const pad = (value: number) => String(value).padStart(2, '0')

/** 把工作时长毫秒数格式化成人类可读文本。 */
export const formatDuration = (durationMs?: number | null): string => {
  if (typeof durationMs !== 'number' || !Number.isFinite(durationMs) || durationMs < 0) {
    return ''
  }
  const seconds = durationMs / 1000
  if (seconds < 60) return `${seconds.toFixed(1)} 秒`
  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds - minutes * 60)
  // 四舍五入到 60 秒时进位，避免出现「3 分 60 秒」。
  if (rest === 60) return `${minutes + 1} 分 00 秒`
  return `${minutes} 分 ${pad(rest)} 秒`
}

export const formatExportDateTime = (value: Date): string =>
  `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())} ` +
  `${pad(value.getHours())}:${pad(value.getMinutes())}:${pad(value.getSeconds())}`

const formatFileStamp = (value: Date): string =>
  `${value.getFullYear()}${pad(value.getMonth() + 1)}${pad(value.getDate())}` +
  `-${pad(value.getHours())}${pad(value.getMinutes())}${pad(value.getSeconds())}`

const sanitizeFilename = (value: string): string =>
  (value || '对话')
    .replace(/[\\/:*?"<>|\r\n\t]/g, '_')
    .trim()
    .slice(0, 60) || '对话'

const escapeHtml = (value: string): string =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

/**
 * 复制纯文本。HTTP 部署下 navigator.clipboard 不可用，
 * 因此保留 execCommand 兜底，返回是否成功而不是抛异常。
 */
export const copyText = async (text: string): Promise<boolean> => {
  if (!text) return false
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // 继续走兜底方案
  }
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', 'readonly')
    textarea.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0'
    document.body.appendChild(textarea)
    textarea.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(textarea)
    return ok
  } catch {
    return false
  }
}

const dataUrlToBlob = (dataUrl: string): Blob => {
  const [header, body] = dataUrl.split(',')
  const mime = header.match(/data:([^;]+)/)?.[1] || 'image/png'
  const binary = atob(body)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return new Blob([bytes], { type: mime })
}

export const isImageClipboardSupported = (): boolean =>
  typeof ClipboardItem !== 'undefined' &&
  !!navigator.clipboard?.write &&
  window.isSecureContext

/** 把 PNG dataURL 写入系统剪贴板，失败时抛出可直接展示的错误。 */
export const copyPngToClipboard = async (dataUrl: string): Promise<void> => {
  if (!isImageClipboardSupported()) {
    throw new Error('当前浏览器不支持复制图片到剪贴板，请改用下载')
  }
  await navigator.clipboard.write([
    new ClipboardItem({ 'image/png': dataUrlToBlob(dataUrl) }),
  ])
}

export const downloadDataUrl = (dataUrl: string, filename: string): void => {
  const link = document.createElement('a')
  link.href = dataUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

/**
 * 从消息 DOM 中取出所有 ECharts 画布，作为 PDF 的图片素材。
 * ECharts 用 canvas 渲染器绘制，直接读取画布即可，无需再持有实例引用。
 */
export const collectChartImages = (root: HTMLElement | null): AgentPdfChart[] => {
  if (!root) return []
  const charts: AgentPdfChart[] = []
  root.querySelectorAll<HTMLElement>('.agent-chart-card').forEach((card, index) => {
    const canvas = card.querySelector('canvas')
    if (!canvas) return
    try {
      charts.push({
        title: card.querySelector('h5')?.textContent?.trim() || `图表 ${index + 1}`,
        dataUrl: canvas.toDataURL('image/png'),
      })
    } catch {
      // 画布被污染时跳过该图，正文仍然导出。
    }
  })
  return charts
}

// PDF 容器样式，全部以 `.agent-pdf-root` 作用域，注入后不会污染当前页面。
const PDF_STYLES = `
.agent-pdf-root, .agent-pdf-root * { box-sizing: border-box; }
.agent-pdf-root {
  width: auto;
  margin: 0;
  padding: 0;
  background: #fff;
  color: #1f2937;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
  font-size: 13px;
  line-height: 1.62;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.agent-pdf-title {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 650;
  line-height: 1.25;
  color: #0b1628;
}
.agent-pdf-meta {
  margin: 0 0 18px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
  color: #8a8f98;
  font-size: 11.5px;
}
.agent-pdf-content h1,
.agent-pdf-content h2,
.agent-pdf-content h3,
.agent-pdf-content h4 {
  margin: 18px 0 8px;
  color: #12243a;
  font-weight: 650;
  line-height: 1.35;
  page-break-after: avoid;
}
.agent-pdf-content h1 { font-size: 18px; }
.agent-pdf-content h2 { font-size: 16px; }
.agent-pdf-content h3 { font-size: 14.5px; }
.agent-pdf-content h4 { font-size: 13.5px; }
.agent-pdf-content p { margin: 0 0 10px; }
.agent-pdf-content ul,
.agent-pdf-content ol { margin: 8px 0 10px; padding-left: 1.6em; }
.agent-pdf-content ul { list-style-type: disc; }
.agent-pdf-content ol { list-style-type: decimal; }
.agent-pdf-content li { margin: 4px 0; }
.agent-pdf-content a { color: #0d74ce; text-decoration: none; }
.agent-pdf-content blockquote {
  margin: 10px 0;
  padding: 8px 12px;
  border-left: 3px solid #d1d5db;
  background: #f9fafb;
  color: #4b5563;
}
.agent-pdf-content code {
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 12px;
  background: #f3f4f6;
  color: #111827;
  border-radius: 4px;
  padding: 1px 5px;
}
.agent-pdf-content pre {
  margin: 10px 0;
  padding: 12px;
  overflow: hidden;
  white-space: pre-wrap;
  word-break: break-word;
  border-radius: 8px;
  background: #102239;
  color: #f9fafb;
  page-break-inside: avoid;
}
.agent-pdf-content pre code {
  padding: 0;
  background: transparent;
  color: inherit;
  font-size: 11.5px;
}
/* 正文直接复用页面里已渲染好的 DOM，因此要压掉聊天气泡里的滚动容器样式，
   否则超宽表格在光栅化时会被裁掉。 */
.agent-pdf-content .agent-markdown-table {
  margin: 10px 0;
  overflow: visible;
  border: none;
  border-radius: 0;
}
.agent-pdf-content table {
  width: 100%;
  min-width: 0;
  border-collapse: collapse;
  margin: 10px 0;
  font-size: 12px;
  white-space: normal;
  page-break-inside: avoid;
}
.agent-pdf-content th,
.agent-pdf-content td {
  border: 1px solid #e5e7eb;
  padding: 5px 8px;
  text-align: left;
  vertical-align: top;
}
.agent-pdf-content th { background: #f9fafb; font-weight: 650; }
.agent-pdf-content img { max-width: 100%; height: auto; }
.agent-pdf-chart {
  margin: 14px 0;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  page-break-inside: avoid;
}
.agent-pdf-chart h4 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 650;
  color: #12243a;
}
.agent-pdf-chart img { display: block; width: 100%; height: auto; }
`

// A4 纸张与内容区尺寸（mm），以及离屏渲染宽度（px）。
const PDF_PAGE = {
  marginMm: 10,
  widthMm: 210,
  heightMm: 297,
  contentWidthMm: 190,
  contentHeightMm: 277,
  renderWidthPx: 760,
  scale: 2,
}

/** 把单条回复导出成 A4 PDF，正文按块级元素边界分页，避免文字被切断。 */
export const exportAgentMessagePdf = async (options: AgentPdfOptions): Promise<void> => {
  const exportedAt = new Date()
  const metaParts = [`导出时间：${formatExportDateTime(exportedAt)}`]
  if (options.model) metaParts.push(`模型：${options.model}`)
  const duration = formatDuration(options.durationMs)
  if (duration) metaParts.push(`耗时：${duration}`)

  const chartsHtml = (options.charts || [])
    .map(
      (chart) =>
        `<div class="agent-pdf-chart"><h4>${escapeHtml(chart.title)}</h4>` +
        `<img src="${chart.dataUrl}" alt="${escapeHtml(chart.title)}" /></div>`
    )
    .join('')

  // 离屏渲染容器：固定到视口外，宽度固定以保证排版/换行稳定。
  const container = document.createElement('div')
  container.setAttribute('aria-hidden', 'true')
  container.style.cssText = [
    'position: fixed',
    'left: -10000px',
    'top: 0',
    `width: ${PDF_PAGE.renderWidthPx}px`,
    'background: #ffffff',
    'pointer-events: none',
    'z-index: -1',
  ].join('; ')
  container.innerHTML =
    `<style>${PDF_STYLES}</style>` +
    `<div class="agent-pdf-root" id="agent-pdf-root">` +
    `<h1 class="agent-pdf-title">${escapeHtml(options.title)} - Agent 回复</h1>` +
    `<div class="agent-pdf-meta">${escapeHtml(metaParts.join('　·　'))}</div>` +
    `<div class="agent-pdf-content">${options.contentHtml}</div>` +
    chartsHtml +
    `</div>`
  document.body.appendChild(container)

  try {
    const root = container.querySelector('#agent-pdf-root') as HTMLElement | null
    if (!root) throw new Error('PDF 渲染容器创建失败')

    // 等待字体与图片就绪，避免中文回退字体或未解码图片导致度量偏差。
    if (document.fonts?.ready) {
      await document.fonts.ready.catch(() => undefined)
    }
    await Promise.all(
      Array.from(root.querySelectorAll('img')).map((image) =>
        image.complete
          ? Promise.resolve()
          : new Promise<void>((resolve) => {
              image.onload = () => resolve()
              image.onerror = () => resolve()
            })
      )
    )
    await new Promise((resolve) => setTimeout(resolve, 50))

    const scale = PDF_PAGE.scale
    const canvas = await html2canvas(root, {
      scale,
      backgroundColor: '#ffffff',
      useCORS: true,
      logging: false,
      windowWidth: PDF_PAGE.renderWidthPx,
    })
    if (!canvas.width || !canvas.height) throw new Error('导出 PDF 失败，请稍后重试')

    // 采集「安全分页点」：块级元素底部的 Y 坐标（画布像素），
    // 分页时把页底对齐到这些边界，避免把一行文字从中间切断。
    const rootTop = root.getBoundingClientRect().top
    const breakYs: number[] = []
    root
      .querySelectorAll('h1, h2, h3, h4, p, li, tr, pre, blockquote, table, ul, ol, .agent-pdf-chart')
      .forEach((element) => {
        const bottom = (element.getBoundingClientRect().bottom - rootTop) * scale
        if (bottom > 0 && bottom <= canvas.height) breakYs.push(bottom)
      })
    breakYs.sort((a, b) => a - b)

    const pxPerMm = canvas.width / PDF_PAGE.contentWidthMm
    const pageHeightPx = PDF_PAGE.contentHeightMm * pxPerMm
    const pdf = new jsPDF({ unit: 'mm', format: 'a4', compress: true })

    let startY = 0
    let firstPage = true
    while (startY < canvas.height - 1) {
      let endY = Math.min(startY + pageHeightPx, canvas.height)
      // 非末页尽量对齐到安全分页点；至少填满半页，避免超高元素退化出大量空白页。
      if (endY < canvas.height) {
        let snapped = -1
        for (const y of breakYs) {
          if (y > endY) break
          if (y > startY + pageHeightPx * 0.5) snapped = y
        }
        if (snapped > 0) endY = snapped
      }

      const sliceHeightPx = Math.max(1, Math.round(endY - startY))
      const pageCanvas = document.createElement('canvas')
      pageCanvas.width = canvas.width
      pageCanvas.height = sliceHeightPx
      const ctx = pageCanvas.getContext('2d')
      if (!ctx) throw new Error('画布上下文创建失败')
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, pageCanvas.width, pageCanvas.height)
      ctx.drawImage(
        canvas,
        0, startY, canvas.width, sliceHeightPx,
        0, 0, canvas.width, sliceHeightPx
      )

      if (!firstPage) pdf.addPage()
      pdf.addImage(
        pageCanvas.toDataURL('image/png'),
        'PNG',
        PDF_PAGE.marginMm,
        PDF_PAGE.marginMm,
        PDF_PAGE.contentWidthMm,
        sliceHeightPx / pxPerMm,
        undefined,
        'FAST'
      )

      firstPage = false
      startY = endY
    }

    pdf.save(`${sanitizeFilename(options.title)}-${formatFileStamp(exportedAt)}.pdf`)
  } finally {
    container.remove()
  }
}
