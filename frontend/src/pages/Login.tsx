import { useMemo, useState } from 'react'
import { useLocation, useNavigate, Navigate, Location } from 'react-router-dom'
import { Button, Card, Form, Input, Typography, message, Space } from 'antd'
import { LockOutlined, UserOutlined, RocketOutlined } from '@ant-design/icons'
import { useAuth } from '@/contexts/AuthContext'
import './Login.css'

const { Title, Text } = Typography

const Login = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, login } = useAuth()
  const [loading, setLoading] = useState(false)

  const redirectPath = useMemo(() => {
    const state = location.state as { from?: Location }
    return state?.from?.pathname || '/'
  }, [location.state])

  if (user) {
    return <Navigate to={redirectPath} replace />
  }

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true)
    try {
      await login(values.username.trim(), values.password)
      message.success('登录成功')
      navigate(redirectPath, { replace: true })
    } catch (error: any) {
      message.error(error.message || '登录失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <Card
        className="login-card"
        bordered={false}
      >
        <Space direction="vertical" size={12} style={{ width: '100%', textAlign: 'center' }}>
          <div className="login-header">
            <RocketOutlined style={{ fontSize: 32, color: '#1677ff' }} />
            <Title level={3} style={{ margin: 0, color: '#0f172a' }}>CostMatrix 控制台</Title>
          </div>
          <Text type="secondary">请使用账户登录以继续</Text>
        </Space>

        <Form layout="vertical" style={{ marginTop: 24 }} onFinish={onFinish} requiredMark={false}>
          <Form.Item
            label="用户名"
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="例如 admin" size="large" autoFocus />
          </Form.Item>

          <Form.Item
            label="密码"
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" size="large" />
          </Form.Item>

          <Form.Item style={{ marginTop: 8 }}>
            <Button type="primary" htmlType="submit" block size="large" loading={loading}>
              登录
            </Button>
          </Form.Item>
        </Form>

      </Card>
    </div>
  )
}

export default Login
