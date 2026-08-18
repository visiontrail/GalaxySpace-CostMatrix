import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Row,
  Select,
  Skeleton,
  Space,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  ApiOutlined,
  CheckCircleFilled,
  CloudServerOutlined,
  DatabaseOutlined,
  KeyOutlined,
  ReloadOutlined,
  RobotOutlined,
  SaveOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  SwapOutlined,
  ThunderboltOutlined,
  WarningFilled,
} from '@ant-design/icons'
import {
  getAISettings,
  resetAISettings,
  testAISettings,
  updateAISettings,
} from '@/services/api'
import { useAuth } from '@/contexts/AuthContext'
import type {
  AIConnectionTestResult,
  AISettings,
  AISettingsUpdate,
} from '@/types'
import './Settings.css'

const { Paragraph, Text, Title } = Typography
const { TextArea } = Input

const parseServerTime = (value: string) =>
  new Date(/[zZ]$|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`)

const FIELD_LABELS: Record<string, string> = {
  provider: 'Provider',
  api_key: 'API Key',
  base_url: 'Base URL',
  model: '模型',
  backup_provider: '备用 Provider',
  backup_api_key: '备用 API Key',
  backup_base_url: '备用 Base URL',
  backup_model: '备用模型',
  max_turns: '最大轮次',
  request_timeout_seconds: '请求超时',
  max_result_rows: '查询行数',
  system_prompt: '系统提示词',
}

const PROVIDER_BASE_URLS: Record<string, string> = {
  anthropic: 'https://api.anthropic.com',
  deepseek: 'https://api.deepseek.com/anthropic',
  aliyun_beijing: 'https://dashscope.aliyuncs.com/apps/anthropic',
  aliyun_workspace: 'https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/apps/anthropic',
  aliyun_singapore: 'https://dashscope-intl.aliyuncs.com/apps/anthropic',
  aliyun_token_plan: 'https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic',
  aliyun_coding_plan: 'https://coding.dashscope.aliyuncs.com/apps/anthropic',
  zhipu: 'https://open.bigmodel.cn/api/anthropic',
  kimi: 'https://api.moonshot.cn/anthropic',
  minimax: 'https://api.minimaxi.com/anthropic',
  stepfun: 'https://api.stepfun.com',
  stepfun_plan: 'https://api.stepfun.com/step_plan',
  xiaomi: 'https://api.xiaomimimo.com/anthropic',
  tencent: 'https://api.hunyuan.cloud.tencent.com/anthropic',
  yhroot: 'https://oneapi.yhroot.com',
  custom: '',
}

const PROVIDER_OPTIONS = [
  {
    label: '官方与通用服务',
    options: [
      { value: 'anthropic', label: 'Anthropic 官方' },
      { value: 'deepseek', label: 'DeepSeek · Anthropic 兼容' },
      { value: 'yhroot', label: 'yhroot / 银河模型网关' },
      { value: 'custom', label: '自定义 Anthropic 兼容端点' },
    ],
  },
  {
    label: '阿里云百炼 / 通义千问',
    options: [
      { value: 'aliyun_workspace', label: '阿里云百炼 · 工作空间按量（北京）' },
      { value: 'aliyun_beijing', label: '阿里云百炼 · 通用（北京）' },
      { value: 'aliyun_singapore', label: '阿里云百炼 · 新加坡' },
      { value: 'aliyun_token_plan', label: '阿里云百炼 · Token Plan' },
      { value: 'aliyun_coding_plan', label: '阿里云百炼 · Coding Plan' },
    ],
  },
  {
    label: '国内 Anthropic 兼容服务',
    options: [
      { value: 'zhipu', label: '智谱 AI / GLM' },
      { value: 'kimi', label: '月之暗面 / Kimi' },
      { value: 'minimax', label: 'MiniMax' },
      { value: 'stepfun', label: '阶跃星辰 · 按量调用' },
      { value: 'stepfun_plan', label: '阶跃星辰 · Step Plan' },
      { value: 'xiaomi', label: '小米 MiMo · 按量调用' },
      { value: 'tencent', label: '腾讯混元直连平台' },
    ],
  },
]

const SourceTag = ({
  source,
}: {
  source?: 'database' | 'environment' | 'unset'
}) => {
  if (source === 'database') return <Tag color="cyan">数据库覆盖</Tag>
  if (source === 'unset') return <Tag color="warning">未配置</Tag>
  return <Tag>环境默认</Tag>
}

const Settings = () => {
  const { user } = useAuth()
  const [form] = Form.useForm<AISettingsUpdate>()
  const [settings, setSettings] = useState<AISettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testingTarget, setTestingTarget] = useState<'primary' | 'backup'>('primary')
  const [testTarget, setTestTarget] = useState<'primary' | 'backup'>('primary')
  const [testResult, setTestResult] = useState<AIConnectionTestResult | null>(null)

  const applySettings = (value: AISettings) => {
    setSettings(value)
    form.setFieldsValue({
      provider: value.provider,
      api_key: '',
      base_url: value.base_url,
      model: value.model,
      backup_enabled: value.backup_enabled,
      backup_provider: value.backup_provider,
      backup_api_key: '',
      backup_base_url: value.backup_base_url,
      backup_model: value.backup_model,
      router_enabled: value.router_enabled,
      router_first_token_timeout_seconds: value.router_first_token_timeout_seconds,
      router_failure_threshold: value.router_failure_threshold,
      router_cooldown_seconds: value.router_cooldown_seconds,
      max_turns: value.max_turns,
      request_timeout_seconds: value.request_timeout_seconds,
      max_result_rows: value.max_result_rows,
      system_prompt: value.system_prompt,
    })
  }

  const load = async () => {
    setLoading(true)
    try {
      applySettings(await getAISettings())
    } catch (error: any) {
      message.error(error.message || '设置加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (user?.is_admin) load()
  }, [user?.is_admin])

  const save = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      const payload = {
        ...values,
        api_key: values.api_key?.trim() || undefined,
        backup_api_key: values.backup_api_key?.trim() || undefined,
        base_url: values.base_url?.trim(),
        model: values.model?.trim(),
        backup_base_url: values.backup_base_url?.trim(),
        backup_model: values.backup_model?.trim(),
        system_prompt: values.system_prompt?.trim(),
      }
      applySettings(await updateAISettings(payload))
      message.success('Agent 设置已生效，无需重启服务')
    } catch (error: any) {
      if (!error?.errorFields) message.error(error.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const reset = async () => {
    setResetting(true)
    try {
      applySettings(await resetAISettings())
      message.success('已恢复环境变量默认值')
    } catch (error: any) {
      message.error(error.message || '恢复失败')
    } finally {
      setResetting(false)
    }
  }

  const testConnection = async (target: 'primary' | 'backup') => {
    try {
      const prefix = target === 'backup' ? 'backup_' : ''
      const values = await form.validateFields([
        `${prefix}provider`,
        `${prefix}api_key`,
        `${prefix}base_url`,
        `${prefix}model`,
      ])
      const provider = target === 'backup' ? values.backup_provider : values.provider
      const apiKey = target === 'backup' ? values.backup_api_key : values.api_key
      const baseUrl = target === 'backup' ? values.backup_base_url : values.base_url
      const selectedModel = target === 'backup' ? values.backup_model : values.model
      setTesting(true)
      setTestingTarget(target)
      setTestResult(null)
      const result = await testAISettings({
        provider: provider!,
        api_key: apiKey?.trim() || undefined,
        base_url: baseUrl!.trim(),
        model: selectedModel!.trim(),
        target,
      })
      setTestTarget(target)
      setTestResult(result)
      message.success(`模型连接测试成功（${result.latency_ms} ms）`)
    } catch (error: any) {
      if (!error?.errorFields) message.error(error.message || '连接测试失败')
    } finally {
      setTesting(false)
    }
  }

  const label = (field: string) => (
    <span className="settings-field-label">
      {FIELD_LABELS[field]}
      <SourceTag source={settings?.sources[field]} />
    </span>
  )

  if (!user?.is_admin) {
    return (
      <Alert
        type="warning"
        showIcon
        message="仅管理员可以修改 AI Agent 设置"
        description="模型密钥、服务地址和 Agent 行为属于系统级配置。"
      />
    )
  }

  if (loading || !settings) {
    return <Card><Skeleton active paragraph={{ rows: 10 }} /></Card>
  }

  return (
    <div className="settings-page">
      <section className="settings-hero">
        <div>
          <Text className="settings-eyebrow">AGENT CONTROL PLANE</Text>
          <Title>AI Agent 设置</Title>
          <Paragraph>
            管理 Claude Agent SDK 的模型连接、执行边界与数据查询上限。数据库中的覆盖值即时生效。
          </Paragraph>
        </div>
        <div className={`settings-status ${settings.api_key_set ? 'is-ready' : 'is-warning'}`}>
          {settings.api_key_set ? <CheckCircleFilled /> : <WarningFilled />}
          <span>
            <small>RUNTIME STATUS</small>
            <strong>{settings.api_key_set ? '模型连接已配置' : '等待 API Key'}</strong>
          </span>
        </div>
      </section>

      {!settings.api_key_set && (
        <Alert
          className="settings-alert"
          type="warning"
          showIcon
          message="Agent 尚不能发起模型请求"
          description="填写 API Key 并保存后，对话页面即可通过 Claude Agent SDK 查询系统数据。"
        />
      )}

      <Form
        className="settings-form"
        layout="vertical"
        form={form}
        requiredMark={false}
        onValuesChange={() => setTestResult(null)}
      >
        <Card className="settings-section-card" variant="borderless">
          <div className="settings-section-title">
            <span><CloudServerOutlined /></span>
            <div>
              <Title level={4}>模型连接</Title>
              <Text type="secondary">选择服务商后自动匹配 Anthropic 兼容 Base URL，也可手动调整</Text>
            </div>
          </div>
          <Divider />
          <Row gutter={[20, 2]}>
            <Col xs={24} md={8}>
              <Form.Item label={label('provider')} name="provider" rules={[{ required: true }]}>
                <Select
                  showSearch
                  optionFilterProp="label"
                  options={PROVIDER_OPTIONS}
                  onChange={(provider) => {
                    form.setFieldValue('base_url', PROVIDER_BASE_URLS[provider])
                    setTestResult(null)
                  }}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={16}>
              <Form.Item
                label={label('api_key')}
                name="api_key"
                extra={settings.api_key_set ? '密钥已设置；留空会保留现有密钥。' : '密钥加密保存在数据库中，后端永不回传明文。'}
              >
                <Input.Password
                  prefix={<KeyOutlined />}
                  autoComplete="new-password"
                  placeholder={settings.api_key_set ? '••••••••••••••••（已设置）' : '输入模型 API Key'}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={14}>
              <Form.Item
                label={label('base_url')}
                name="base_url"
                rules={[
                  { required: true, message: '请输入 Base URL' },
                  { pattern: /^https?:\/\//, message: '必须以 http:// 或 https:// 开头' },
                ]}
              >
                <Input prefix={<ApiOutlined />} placeholder="https://api.anthropic.com" />
              </Form.Item>
            </Col>
            <Col xs={24} md={10}>
              <Form.Item
                label={label('model')}
                name="model"
                rules={[{ required: true, message: '请输入模型名称' }]}
              >
                <Input prefix={<RobotOutlined />} placeholder="claude-sonnet-4-6" />
              </Form.Item>
            </Col>
          </Row>
          <div className={`settings-connection-test ${testResult && testTarget === 'primary' ? 'is-success' : ''}`}>
            <div>
              <strong>连接可用性检查</strong>
              <span>
                {testResult && testTarget === 'primary'
                  ? `${testResult.message} · ${testResult.latency_ms} ms`
                  : '发送一个最小请求，验证 Base URL、API Key 和模型名称；不会保存表单。'}
              </span>
              {testResult && testTarget === 'primary' && <code>{testResult.endpoint}</code>}
            </div>
            <Button
              icon={<ThunderboltOutlined />}
              loading={testing && testingTarget === 'primary'}
              onClick={() => testConnection('primary')}
            >
              测试连接
            </Button>
          </div>
        </Card>

        <Card className="settings-section-card" variant="borderless">
          <div className="settings-section-title">
            <span><SwapOutlined /></span>
            <div>
              <Title level={4}>主备模型路由</Title>
              <Text type="secondary">
                主模型只在首个模型输出前失败或超时时切换；已开始回答后不会重放工具调用
              </Text>
            </div>
          </div>
          <Divider />
          <Row gutter={[20, 12]} align="middle">
            <Col xs={24} md={8}>
              <Form.Item label="启用备用模型" name="backup_enabled" valuePropName="checked">
                <Switch checkedChildren="已启用" unCheckedChildren="已停用" />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="启用自动故障接管" name="router_enabled" valuePropName="checked">
                <Switch checkedChildren="自动切换" unCheckedChildren="仅主模型" />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <div className="settings-status-inline">
                <Text type="secondary">当前路由</Text>
                <Tag color={settings.router.serving_slot === 'backup' ? 'orange' : 'green'}>
                  {settings.router.serving_slot === 'backup' ? 'BACKUP' : 'PRIMARY'}
                </Tag>
                {settings.router.primary_breaker_open && (
                  <Text type="warning">
                    主模型冷却中 {settings.router.cooldown_remaining_seconds ?? 0}s
                  </Text>
                )}
              </div>
            </Col>
          </Row>

          <Form.Item noStyle shouldUpdate={(previous, current) => (
            previous.backup_enabled !== current.backup_enabled
            || previous.backup_provider !== current.backup_provider
          )}>
            {({ getFieldValue }) => {
              const backupEnabled = Boolean(getFieldValue('backup_enabled'))
              return (
                <>
                  <Row gutter={[20, 2]}>
                    <Col xs={24} md={8}>
                      <Form.Item
                        label={label('backup_provider')}
                        name="backup_provider"
                        rules={[{ required: backupEnabled, message: '请选择备用 Provider' }]}
                      >
                        <Select
                          showSearch
                          optionFilterProp="label"
                          options={PROVIDER_OPTIONS}
                          disabled={!backupEnabled}
                          onChange={(provider) => {
                            form.setFieldValue('backup_base_url', PROVIDER_BASE_URLS[provider])
                            setTestResult(null)
                          }}
                        />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={16}>
                      <Form.Item
                        label={label('backup_api_key')}
                        name="backup_api_key"
                        extra={settings.backup_api_key_set
                          ? '备用密钥已设置；留空会保留现有密钥。'
                          : '备用密钥独立加密保存，后端永不回传明文。'}
                      >
                        <Input.Password
                          prefix={<KeyOutlined />}
                          autoComplete="new-password"
                          disabled={!backupEnabled}
                          placeholder={settings.backup_api_key_set
                            ? '••••••••••••••••（已设置）'
                            : '输入备用模型 API Key'}
                        />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={14}>
                      <Form.Item
                        label={label('backup_base_url')}
                        name="backup_base_url"
                        rules={[
                          { required: backupEnabled, message: '请输入备用 Base URL' },
                          { pattern: /^https?:\/\//, message: '必须以 http:// 或 https:// 开头' },
                        ]}
                      >
                        <Input prefix={<ApiOutlined />} disabled={!backupEnabled} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={10}>
                      <Form.Item
                        label={label('backup_model')}
                        name="backup_model"
                        rules={[{ required: backupEnabled, message: '请输入备用模型名称' }]}
                      >
                        <Input prefix={<RobotOutlined />} disabled={!backupEnabled} placeholder="kimi-k3" />
                      </Form.Item>
                    </Col>
                  </Row>
                  <div className={`settings-connection-test ${testResult && testTarget === 'backup' ? 'is-success' : ''}`}>
                    <div>
                      <strong>备用连接可用性检查</strong>
                      <span>
                        {testResult && testTarget === 'backup'
                          ? `${testResult.message} · ${testResult.latency_ms} ms`
                          : '独立验证备用 Base URL、API Key 和模型，不影响当前路由。'}
                      </span>
                      {testResult && testTarget === 'backup' && <code>{testResult.endpoint}</code>}
                    </div>
                    <Button
                      icon={<ThunderboltOutlined />}
                      disabled={!backupEnabled}
                      loading={testing && testingTarget === 'backup'}
                      onClick={() => testConnection('backup')}
                    >
                      测试备用连接
                    </Button>
                  </div>
                </>
              )
            }}
          </Form.Item>

          <Divider />
          <Row gutter={[20, 2]}>
            <Col xs={24} md={8}>
              <Form.Item
                label="首个模型输出超时"
                name="router_first_token_timeout_seconds"
                extra="0 表示只在明确错误时切换。"
              >
                <InputNumber min={0} max={600} suffix="秒" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="连续失败阈值" name="router_failure_threshold">
                <InputNumber min={1} max={20} suffix="次" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="主模型冷却时间" name="router_cooldown_seconds">
                <InputNumber min={10} max={86400} suffix="秒" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          {settings.router.primary_breaker_open && settings.router.last_error && (
            <Alert
              showIcon
              type="warning"
              message="主模型已自动熔断，当前由备用模型接管"
              description={settings.router.last_error}
            />
          )}
        </Card>

        <Card className="settings-section-card" variant="borderless">
          <div className="settings-section-title">
            <span><SettingOutlined /></span>
            <div>
              <Title level={4}>执行边界</Title>
              <Text type="secondary">控制 Agent 工具循环、请求时限和单次数据库结果规模</Text>
            </div>
          </div>
          <Divider />
          <Row gutter={[20, 2]}>
            <Col xs={24} md={8}>
              <Form.Item label={label('max_turns')} name="max_turns">
                <InputNumber min={1} max={50} suffix="轮" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label={label('request_timeout_seconds')} name="request_timeout_seconds">
                <InputNumber min={30} max={900} suffix="秒" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label={label('max_result_rows')} name="max_result_rows">
                <InputNumber min={10} max={5000} suffix="行" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <div className="settings-guardrail-strip">
            <SafetyCertificateOutlined />
            <div>
              <strong>数据库硬性只读保护</strong>
              <span>无论提示词如何修改，工具层始终拒绝写入、DDL、多语句及认证机密字段。</span>
            </div>
            <Tag icon={<DatabaseOutlined />} color="cyan">READ ONLY</Tag>
          </div>
        </Card>

        <Card className="settings-section-card" variant="borderless">
          <div className="settings-section-title">
            <span><RobotOutlined /></span>
            <div>
              <Title level={4}>Agent 行为</Title>
              <Text type="secondary">固定为 CostMatrix 单 Agent；无需操作人员选择 Agent</Text>
            </div>
          </div>
          <Divider />
          <Form.Item
            label={label('system_prompt')}
            name="system_prompt"
            rules={[{ required: true, message: '系统提示词不能为空' }]}
            extra="建议保留数据核实、认证机密保护和 ECharts 工具调用规则。"
          >
            <TextArea rows={12} showCount maxLength={20000} />
          </Form.Item>
        </Card>

        <Card className="settings-actions" variant="borderless">
          <Space wrap>
            <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={save}>
              保存并立即生效
            </Button>
            <Popconfirm
              title="恢复环境变量默认值？"
              description="数据库中的模型设置和密钥覆盖都会删除。"
              okText="恢复"
              cancelText="取消"
              onConfirm={reset}
            >
              <Button icon={<ReloadOutlined />} loading={resetting}>恢复默认</Button>
            </Popconfirm>
          </Space>
          <Text type="secondary">
            {settings.updated_at
              ? `最近更新：${parseServerTime(settings.updated_at).toLocaleString('zh-CN')}`
              : '当前全部使用环境默认值'}
          </Text>
        </Card>
      </Form>
    </div>
  )
}

export default Settings
