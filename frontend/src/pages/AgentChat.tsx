import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Button,
  Empty,
  Input,
  message,
  Popconfirm,
  Skeleton,
  Space,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import {
  ArrowDownOutlined,
  BarChartOutlined,
  CopyOutlined,
  DeleteOutlined,
  DatabaseOutlined,
  FilePdfOutlined,
  LoadingOutlined,
  MessageOutlined,
  PlusOutlined,
  RobotOutlined,
  SendOutlined,
  StopOutlined,
  ToolOutlined,
  UserOutlined,
} from '@ant-design/icons'
import AgentChart from '@/components/AgentChart'
import AgentMarkdown from '@/components/AgentMarkdown'
import {
  deleteAgentConversation,
  getAgentConversationMessages,
  listAgentConversations,
  streamAgentChat,
} from '@/services/api'
import {
  collectChartImages,
  copyText,
  exportAgentMessagePdf,
  formatDuration,
} from '@/utils/agentExport'
import type {
  AgentChartSpec,
  AgentConversation,
  AgentMessage,
  AgentStreamEvent,
  AgentToolTrace,
} from '@/types'
import './AgentChat.css'

const { Text, Title } = Typography
const { TextArea } = Input

const QUICK_PROMPTS = [
  '汇总系统当前全部数据，并指出最值得关注的成本问题',
  '按部门分析差旅成本，生成一张交互式图表',
  '找出差旅超标和考勤异常的主要分布',
  '分析项目成本排名，并说明数据口径',
]

const parseServerTime = (value: string) =>
  new Date(/[zZ]$|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`)

const formatTime = (value: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(parseServerTime(value))

const AgentChat = () => {
  const [conversations, setConversations] = useState<AgentConversation[]>([])
  const [selectedId, setSelectedId] = useState<string | undefined>()
  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [draft, setDraft] = useState('')
  const [loadingList, setLoadingList] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [sending, setSending] = useState(false)
  const [statusText, setStatusText] = useState('')
  const [liveTools, setLiveTools] = useState<AgentToolTrace[]>([])
  const [showJumpToBottom, setShowJumpToBottom] = useState(false)
  const [exportingId, setExportingId] = useState<number | null>(null)
  // 正在流式输出的那条回复：它还没拿到模型与耗时，先不显示操作栏。
  const [streamingId, setStreamingId] = useState<number | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  // 用户主动向上翻阅时暂停自动贴底，避免流式输出把视图拽回底部。
  const stickToBottomRef = useRef(true)
  const columnObserverRef = useRef<ResizeObserver | null>(null)

  const loadConversations = useCallback(async () => {
    try {
      const rows = await listAgentConversations()
      setConversations(rows)
    } catch (error: any) {
      message.error(error.message || '对话列表加载失败')
    } finally {
      setLoadingList(false)
    }
  }, [])

  useEffect(() => {
    loadConversations()
  }, [loadConversations])

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'auto') => {
    const element = scrollRef.current
    if (element) element.scrollTo({ top: element.scrollHeight, behavior })
  }, [])

  const handleScroll = useCallback(() => {
    const element = scrollRef.current
    if (!element) return
    const distanceToBottom = element.scrollHeight - element.scrollTop - element.clientHeight
    const atBottom = distanceToBottom <= 80
    stickToBottomRef.current = atBottom
    setShowJumpToBottom(!atBottom && distanceToBottom > 160)
  }, [])

  const pinToBottom = useCallback(() => {
    stickToBottomRef.current = true
    setShowJumpToBottom(false)
    scrollToBottom('smooth')
  }, [scrollToBottom])

  useEffect(() => {
    if (stickToBottomRef.current) scrollToBottom()
  }, [messages, statusText, liveTools, scrollToBottom])

  // 图表挂载后高度才确定，用 ResizeObserver 在内容高度变化时重新贴底。
  const attachColumn = useCallback(
    (node: HTMLDivElement | null) => {
      columnObserverRef.current?.disconnect()
      columnObserverRef.current = null
      if (!node || typeof ResizeObserver === 'undefined') return
      const observer = new ResizeObserver(() => {
        if (stickToBottomRef.current) scrollToBottom()
      })
      observer.observe(node)
      columnObserverRef.current = observer
    },
    [scrollToBottom]
  )

  useEffect(() => () => columnObserverRef.current?.disconnect(), [])

  const selectConversation = async (conversationId: string) => {
    if (sending || conversationId === selectedId) return
    setSelectedId(conversationId)
    setLoadingMessages(true)
    setLiveTools([])
    stickToBottomRef.current = true
    setShowJumpToBottom(false)
    try {
      const result = await getAgentConversationMessages(conversationId)
      setMessages(result.messages)
    } catch (error: any) {
      message.error(error.message || '对话内容加载失败')
    } finally {
      setLoadingMessages(false)
    }
  }

  const newConversation = () => {
    if (sending) return
    setSelectedId(undefined)
    setMessages([])
    setLiveTools([])
    setStatusText('')
    setDraft('')
    stickToBottomRef.current = true
    setShowJumpToBottom(false)
  }

  const removeConversation = async (conversationId: string) => {
    try {
      await deleteAgentConversation(conversationId)
      if (selectedId === conversationId) newConversation()
      await loadConversations()
      message.success('对话已删除')
    } catch (error: any) {
      message.error(error.message || '删除失败')
    }
  }

  const updateAssistant = (
    temporaryId: number,
    updater: (current: AgentMessage) => AgentMessage
  ) => {
    setMessages((current) =>
      current.map((item) => (item.id === temporaryId ? updater(item) : item))
    )
  }

  const sendMessage = async (prompt?: string) => {
    const content = (prompt ?? draft).trim()
    if (!content || sending) return

    const now = new Date().toISOString()
    const userId = -Date.now()
    const assistantId = userId - 1
    const userMessage: AgentMessage = {
      id: userId,
      role: 'user',
      content,
      charts: [],
      tool_trace: [],
      created_at: now,
    }
    const assistantMessage: AgentMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      charts: [],
      tool_trace: [],
      created_at: now,
    }
    // 新提问总是把视图带回底部，无论此前翻阅到哪里。
    stickToBottomRef.current = true
    setShowJumpToBottom(false)
    setMessages((current) => [...current, userMessage, assistantMessage])
    setDraft('')
    setSending(true)
    setStreamingId(assistantId)
    setLiveTools([])
    setStatusText('正在连接 CostMatrix Agent')

    const controller = new AbortController()
    abortRef.current = controller

    const handleEvent = (event: AgentStreamEvent) => {
      switch (event.event) {
        case 'conversation':
          setSelectedId(event.conversation_id)
          setStatusText('Agent 正在分析系统数据')
          break
        case 'status':
          setStatusText(event.message)
          break
        case 'tool_use':
          setStatusText(`正在调用 ${event.tool}`)
          setLiveTools((current) => [
            ...current,
            { tool: event.tool, arguments: event.arguments },
          ])
          break
        case 'answer_delta':
          updateAssistant(assistantId, (item) => ({
            ...item,
            content: item.content + event.delta,
          }))
          break
        case 'chart':
          updateAssistant(assistantId, (item) => ({
            ...item,
            charts: [...item.charts, event.chart],
          }))
          break
        case 'final':
          updateAssistant(assistantId, (item) => ({
            ...item,
            content: event.answer,
            charts: event.charts,
            tool_trace: event.tool_trace,
            model: event.model,
            provider: event.provider,
            route_slot: event.route_slot,
            duration_ms: event.duration_ms ?? null,
          }))
          setStatusText('')
          break
        case 'error':
          // 已流式输出的内容对用户仍有价值，只在末尾追加失败说明。
          updateAssistant(assistantId, (item) => ({
            ...item,
            content: item.content
              ? `${item.content}\n\n> ⚠️ 执行失败：${event.message}`
              : `执行失败：${event.message}`,
          }))
          setStatusText('')
          break
      }
    }

    try {
      await streamAgentChat(
        { message: content, ...(selectedId ? { conversation_id: selectedId } : {}) },
        handleEvent,
        controller.signal
      )
      await loadConversations()
    } catch (error: any) {
      const stopped = error?.name === 'AbortError'
      updateAssistant(assistantId, (item) => ({
        ...item,
        content: item.content || (stopped ? '已停止生成。' : `连接失败：${error.message}`),
      }))
      if (!stopped) message.error(error.message || 'Agent 请求失败')
    } finally {
      abortRef.current = null
      setSending(false)
      setStreamingId(null)
      setStatusText('')
    }
  }

  const stopGeneration = () => {
    abortRef.current?.abort()
  }

  const title = useMemo(
    () => conversations.find((item) => item.id === selectedId)?.title || '新对话',
    [conversations, selectedId]
  )

  // 只复制回答正文：图表是结构化数据，不属于 Markdown 的一部分。
  const copyMessageMarkdown = async (item: AgentMessage) => {
    const content = item.content.trim()
    if (!content) return
    if (await copyText(content)) {
      message.success('Markdown 已复制')
    } else {
      message.error('复制 Markdown 失败')
    }
  }

  const exportMessagePdf = async (
    item: AgentMessage,
    event: React.MouseEvent<HTMLButtonElement>
  ) => {
    // 正文直接取页面上已渲染的 DOM，导出结果与用户看到的一致。
    const article = event.currentTarget.closest('.agent-message') as HTMLElement | null
    const contentHtml = article?.querySelector('.agent-message-content')?.innerHTML
    if (!contentHtml) {
      message.error('未找到可导出的内容')
      return
    }
    setExportingId(item.id)
    try {
      await exportAgentMessagePdf({
        title,
        contentHtml,
        charts: collectChartImages(article),
        model: item.model,
        durationMs: item.duration_ms,
      })
      message.success('PDF 已开始下载')
    } catch (error: any) {
      message.error(error?.message || '导出 PDF 失败，请稍后重试')
    } finally {
      setExportingId(null)
    }
  }

  return (
    <div className="agent-workbench">
      <aside className="agent-history-rail">
        <div className="agent-rail-brand">
          <div className="agent-orbit-mark"><RobotOutlined /></div>
          <div>
            <Text className="agent-rail-eyebrow">COST INTELLIGENCE</Text>
            <Title level={5}>对话记录</Title>
          </div>
        </div>
        <Button
          className="agent-new-chat"
          type="primary"
          icon={<PlusOutlined />}
          block
          onClick={newConversation}
          disabled={sending}
        >
          新建对话
        </Button>
        <div className="agent-conversation-list">
          {loadingList ? (
            <Skeleton active paragraph={{ rows: 5 }} title={false} />
          ) : conversations.length ? (
            conversations.map((item) => (
              <button
                type="button"
                key={item.id}
                className={`agent-conversation-item ${selectedId === item.id ? 'is-active' : ''}`}
                onClick={() => selectConversation(item.id)}
              >
                <MessageOutlined />
                <span>
                  <strong>{item.title}</strong>
                  <small>{formatTime(item.updated_at)}</small>
                </span>
                <Popconfirm
                  title="删除这条对话？"
                  okText="删除"
                  cancelText="取消"
                  onConfirm={(event) => {
                    event?.stopPropagation()
                    removeConversation(item.id)
                  }}
                  onCancel={(event) => event?.stopPropagation()}
                >
                  <Tooltip title="删除">
                    <DeleteOutlined
                      className="agent-conversation-delete"
                      onClick={(event) => event.stopPropagation()}
                    />
                  </Tooltip>
                </Popconfirm>
              </button>
            ))
          ) : (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无历史对话" />
          )}
        </div>
        <div className="agent-rail-scope">
          <DatabaseOutlined />
          <span><strong>全域数据只读</strong><small>六项数据库工具已接入</small></span>
        </div>
      </aside>

      <main className="agent-chat-stage">
        <header className="agent-chat-header">
          <div>
            <Text className="agent-stage-eyebrow">GALAXYSPACE · COSTMATRIX</Text>
            <Title level={4}>{title}</Title>
          </div>
          <Space wrap>
            <Tag icon={<DatabaseOutlined />} color="cyan">系统全量数据</Tag>
            <Tag icon={<BarChartOutlined />} color="blue">ECharts</Tag>
            <Tag color="green">单 Agent 在线</Tag>
          </Space>
        </header>

        <div className="agent-message-scroll" ref={scrollRef} onScroll={handleScroll}>
          {loadingMessages ? (
            <div className="agent-loading"><Skeleton active paragraph={{ rows: 6 }} /></div>
          ) : messages.length === 0 ? (
            <section className="agent-welcome">
              <div className="agent-welcome-icon"><RobotOutlined /></div>
              <Text className="agent-stage-eyebrow">ONE AGENT · ALL COST DATA</Text>
              <Title>今天想从成本数据里找到什么？</Title>
              <Text type="secondary">
                CostMatrix Agent 会自行发现数据库结构、查询完整业务数据，并在需要时生成可交互 ECharts 图表。
              </Text>
              <div className="agent-quick-grid">
                {QUICK_PROMPTS.map((item, index) => (
                  <button key={item} type="button" onClick={() => sendMessage(item)}>
                    <span>0{index + 1}</span>
                    {item}
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <div className="agent-message-column" ref={attachColumn}>
              {messages.map((item) => (
                <article key={item.id} className={`agent-message agent-message--${item.role}`}>
                  <div className="agent-message-avatar">
                    {item.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                  </div>
                  <div className="agent-message-body">
                    <div className="agent-message-meta">
                      <strong>{item.role === 'user' ? '你' : 'CostMatrix Agent'}</strong>
                      <span>{formatTime(item.created_at)}</span>
                    </div>
                    {item.content ? (
                      <div className="agent-message-content">
                        <AgentMarkdown content={item.content} />
                      </div>
                    ) : sending && item.id < 0 ? (
                      <div className="agent-thinking-dots"><i /><i /><i /></div>
                    ) : null}
                    {item.tool_trace.length > 0 && (
                      <details className="agent-tool-summary">
                        <summary><ToolOutlined /> 已完成 {item.tool_trace.length} 次数据工具调用</summary>
                        {item.tool_trace.map((trace, index) => (
                          <div key={`${trace.tool}-${index}`}>
                            <DatabaseOutlined />
                            <span>{trace.tool}</span>
                            {typeof trace.duration_ms === 'number' && <small>{trace.duration_ms} ms</small>}
                            {trace.error && <Tag color="error">{trace.error}</Tag>}
                          </div>
                        ))}
                      </details>
                    )}
                    {item.charts.map((chart: AgentChartSpec, index) => (
                      <AgentChart key={`${chart.title}-${index}`} spec={chart} />
                    ))}
                    {item.role === 'assistant' &&
                      item.content.trim() &&
                      item.id !== streamingId && (
                        <div className="agent-message-actions">
                          <div className="agent-action-group">
                            <Tooltip title="复制本次回复 Markdown">
                              <button
                                type="button"
                                className="agent-action-btn"
                                aria-label="复制本次回复 Markdown"
                                onClick={() => copyMessageMarkdown(item)}
                              >
                                <CopyOutlined />
                              </button>
                            </Tooltip>
                            <Tooltip title="导出本次回复 PDF">
                              <button
                                type="button"
                                className="agent-action-btn"
                                aria-label="导出本次回复 PDF"
                                disabled={exportingId === item.id}
                                onClick={(event) => exportMessagePdf(item, event)}
                              >
                                {exportingId === item.id ? <LoadingOutlined /> : <FilePdfOutlined />}
                              </button>
                            </Tooltip>
                          </div>
                          {item.model && (
                            <div className="agent-run-meta">
                              {item.route_slot && (
                                <Tag color={item.route_slot === 'backup' ? 'orange' : 'green'}>
                                  {item.route_slot === 'backup' ? '备用接管' : '主模型'}
                                </Tag>
                              )}
                              {item.provider && <span>Provider：{item.provider}</span>}
                              <span className="agent-run-model">模型：{item.model}</span>
                              {formatDuration(item.duration_ms) && (
                                <>
                                  <span className="agent-run-separator" aria-hidden="true" />
                                  <span>耗时：{formatDuration(item.duration_ms)}</span>
                                </>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                  </div>
                </article>
              ))}
              {sending && (statusText || liveTools.length > 0) && (
                <div className="agent-live-trace">
                  <RobotOutlined spin />
                  <div>
                    <strong>{statusText || '正在处理'}</strong>
                    {liveTools.length > 0 && (
                      <span>{liveTools.map((item) => item.tool).join(' → ')}</span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <footer className="agent-composer-wrap">
          {showJumpToBottom && (
            <button type="button" className="agent-jump-bottom" onClick={pinToBottom}>
              <ArrowDownOutlined /> 回到最新消息
            </button>
          )}
          <div className="agent-composer">
            <TextArea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  sendMessage()
                }
              }}
              placeholder="询问部门、项目、差旅、考勤或异常数据…"
              autoSize={{ minRows: 1, maxRows: 5 }}
              disabled={sending}
            />
            {sending ? (
              <Button
                danger
                shape="circle"
                icon={<StopOutlined />}
                onClick={stopGeneration}
                aria-label="停止生成"
              />
            ) : (
              <Button
                type="primary"
                shape="circle"
                icon={<SendOutlined />}
                onClick={() => sendMessage()}
                disabled={!draft.trim()}
                aria-label="发送"
              />
            )}
          </div>
          <Text type="secondary">Enter 发送 · Shift + Enter 换行 · 数据查询始终只读</Text>
        </footer>
      </main>
    </div>
  )
}

export default AgentChat
