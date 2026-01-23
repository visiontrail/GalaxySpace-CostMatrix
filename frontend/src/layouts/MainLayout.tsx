import { useEffect, useMemo, useState } from 'react'
import { Layout, Menu, Typography, Button, Space, Empty, Tag, Modal, Form, Input, message, Checkbox } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { DashboardOutlined, UploadOutlined, RocketOutlined, MenuFoldOutlined, MenuUnfoldOutlined, DeleteOutlined, TeamOutlined, UserOutlined, LogoutOutlined } from '@ant-design/icons'
import type { MonthContextValue } from '@/types'
import { MonthProvider, useMonthContext } from '@/contexts/MonthContext'
import { useAuth } from '@/contexts/AuthContext'
import { changePassword } from '@/services/api'

const { Header, Content, Footer, Sider } = Layout
const { Title, Text } = Typography

const MainLayout = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const { user, logout } = useAuth()

  const menuItems = useMemo(() => {
    const items = [
      {
        key: '/',
        icon: <DashboardOutlined />,
        label: '数据看板',
      },
      {
        key: '/upload',
        icon: <UploadOutlined />,
        label: '文件上传',
      },
    ]

    if (user?.is_admin) {
      items.push({
        key: '/users',
        icon: <TeamOutlined />,
        label: '用户管理',
      })
    }

    return items
  }, [user?.is_admin])

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
  }

  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => !prev)
  }

  return (
    <MonthProvider>
      <MainLayoutContent
        sidebarCollapsed={sidebarCollapsed}
        toggleSidebar={toggleSidebar}
        menuItems={menuItems}
        handleMenuClick={handleMenuClick}
        navigate={navigate}
        location={location}
        user={user}
        onLogout={() => {
          logout()
          navigate('/login')
        }}
      />
    </MonthProvider>
  )
}

interface MainLayoutContentProps {
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  menuItems: any[]
  handleMenuClick: (info: { key: string }) => void
  navigate: any
  location: any
  user: any
  onLogout: () => void
}

const MainLayoutContent: React.FC<MainLayoutContentProps> = ({
  sidebarCollapsed,
  toggleSidebar,
  menuItems,
  handleMenuClick,
  location,
  user,
  onLogout,
}) => {
  const {
    availableMonths,
    selectedMonths,
    pendingMonths,
    setPendingMonths,
    applySelectedMonths,
    refreshMonths,
    deleteMonth
  } = useMonthContext()
  const [multiSelectMode, setMultiSelectMode] = useState(false)
  const [pwdModalOpen, setPwdModalOpen] = useState(false)
  const [changingPwd, setChangingPwd] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    refreshMonths()
  }, [refreshMonths])

  const contextValue: MonthContextValue = useMemo(() => ({
    availableMonths,
    selectedMonths,
    pendingMonths,
    setPendingMonths,
    applySelectedMonths,
    refreshMonths,
    deleteMonth,
  }), [availableMonths, selectedMonths, pendingMonths, setPendingMonths, applySelectedMonths, refreshMonths, deleteMonth])

  const formatMonth = (month: string) => {
    const [year, monthNum] = month.split('-')
    return `${year}年${monthNum}月`
  }

  const sortByAvailable = (months: string[]) => availableMonths.filter(m => months.includes(m))

  const handleToggleMonth = (month: string) => {
    if (!multiSelectMode) {
      const next = sortByAvailable([month])
      setPendingMonths(next)
      applySelectedMonths(next)
      return
    }

    const exists = pendingMonths.includes(month)
    const next = exists
      ? pendingMonths.filter(m => m !== month)
      : [...pendingMonths, month]
    setPendingMonths(sortByAvailable(next))
  }

  const hasPendingChanges = useMemo(() => {
    if (pendingMonths.length !== selectedMonths.length) return true
    return pendingMonths.some(month => !selectedMonths.includes(month))
  }, [pendingMonths, selectedMonths])

  const handleToggleMultiSelect = () => {
    setMultiSelectMode((prev) => {
      const next = !prev
      if (!next) {
        const fallback =
          pendingMonths[pendingMonths.length - 1] ??
          selectedMonths[selectedMonths.length - 1] ??
          availableMonths[availableMonths.length - 1]
        if (fallback) {
          setPendingMonths(sortByAvailable([fallback]))
        }
      }
      return next
    })
  }

  const handleConfirmSelection = () => {
    if (!multiSelectMode) return
    applySelectedMonths()
    if (hasPendingChanges) {
      message.success('已应用所选月份')
    } else {
      message.info('月份选择未变化')
    }
  }

  const handlePasswordChange = async () => {
    try {
      const values = await form.validateFields()
      setChangingPwd(true)
      await changePassword(values)
      message.success('密码修改成功')
      setPwdModalOpen(false)
      form.resetFields()
    } catch (error: any) {
      if (error?.errorFields) return
      message.error(error?.message || '修改密码失败')
    } finally {
      setChangingPwd(false)
    }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        theme="light"
        collapsible
        collapsed={sidebarCollapsed}
        onCollapse={() => {
          toggleSidebar()
        }}
        collapsedWidth={0}
        trigger={null}
        width={320}
        style={{
          borderRight: sidebarCollapsed ? 'none' : '1px solid #f0f0f0',
          padding: sidebarCollapsed ? 0 : '16px 12px',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          zIndex: 100,
          overflow: 'hidden',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <Space align="center" style={{ width: '100%', justifyContent: 'space-between', padding: '0 8px', flexShrink: 0 }}>
            <Space align="center" size={6}>
              <Button
                type="text"
                size="small"
                icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                onClick={toggleSidebar}
                style={{ color: '#1f1f1f' }}
                aria-label={sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'}
              />
              <Title level={4} style={{ margin: 0 }}>统计月份</Title>
            </Space>
            <Space size={8}>
              <Button size="small" onClick={refreshMonths}>
                刷新
              </Button>
              <Button
                size="small"
                type={multiSelectMode ? 'primary' : 'default'}
                ghost={multiSelectMode}
                onClick={handleToggleMultiSelect}
              >
                {multiSelectMode ? '退出多选' : '多选'}
              </Button>
              <Button
                type="primary"
                size="small"
                onClick={handleConfirmSelection}
                disabled={!multiSelectMode || !hasPendingChanges}
              >
                确认
              </Button>
            </Space>
          </Space>
          <div style={{ marginTop: 8, padding: '0 8px' }}>
            <Text type="secondary" style={{ fontSize: 12 }}>已应用月份</Text>
            <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {selectedMonths.length > 0 ? (
                selectedMonths.map(month => (
                  <Tag key={month} color="blue" style={{ marginRight: 0 }}>
                    {formatMonth(month)}
                  </Tag>
                ))
              ) : (
                <Text type="secondary" style={{ fontSize: 12 }}>未选择</Text>
              )}
            </div>
          </div>
          <div style={{ marginTop: 12, flex: 1, overflow: 'hidden', minHeight: 0 }}>
            {availableMonths.length === 0 ? (
              <Empty description="暂无数据" style={{ paddingTop: 20 }} />
            ) : (
              <div style={{ height: '100%', overflowY: 'auto', paddingRight: 4 }}>
                {availableMonths.map(month => (
                  <div
                    key={month}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 10px',
                      borderRadius: 8,
                      border: pendingMonths.includes(month) ? '1px solid #1677ff' : '1px solid #f0f0f0',
                      background: pendingMonths.includes(month) ? '#f0f7ff' : '#fff',
                      marginBottom: 8,
                      cursor: multiSelectMode ? 'default' : 'pointer',
                    }}
                    onClick={() => {
                      if (!multiSelectMode) {
                        handleToggleMonth(month)
                      }
                    }}
                  >
                    {multiSelectMode ? (
                      <Checkbox
                        checked={pendingMonths.includes(month)}
                        onChange={() => handleToggleMonth(month)}
                        style={{ fontWeight: 600, color: '#1f1f1f' }}
                      >
                        {formatMonth(month)}
                      </Checkbox>
                    ) : (
                      <span style={{ fontWeight: 600, color: '#1f1f1f' }}>
                        {formatMonth(month)}
                      </span>
                    )}
                    <Button
                      type="text"
                      size="small"
                      icon={<DeleteOutlined />}
                      danger
                      onClick={(e) => {
                        e.stopPropagation()
                        deleteMonth(month)
                      }}
                      style={{ padding: '2px 4px', minWidth: 'auto' }}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </Sider>
      <Layout style={{ marginLeft: sidebarCollapsed ? 0 : 320, transition: 'margin-left 0.2s' }}>
        <Header style={{
          display: 'flex',
          alignItems: 'center',
          background: '#001529',
          padding: '0 24px'
        }}>
          <Button
            type="text"
            icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={toggleSidebar}
            style={{ color: 'white', marginRight: 12 }}
            aria-label={sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'}
          />
          <div style={{ display: 'flex', alignItems: 'center', marginRight: 40 }}>
            <RocketOutlined style={{ fontSize: 28, color: '#1890ff', marginRight: 12 }} />
            <Title level={3} style={{ color: 'white', margin: 0 }}>
              CostMatrix
            </Title>
          </div>
          <Menu
            theme="dark"
            mode="horizontal"
            selectedKeys={[location.pathname]}
            items={menuItems}
            onClick={handleMenuClick}
            style={{ flex: 1, minWidth: 0 }}
          />
          <Space align="center" size={12} style={{ color: 'white', marginLeft: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <UserOutlined />
              <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.2 }}>
                <span style={{ color: 'white', fontWeight: 600 }}>{user?.username || '未登录'}</span>
                <span style={{ color: '#cbd5e1', fontSize: 12 }}>
                  {user?.is_admin ? <Tag color="gold" style={{ margin: 0 }}>管理员</Tag> : <Tag color="blue" style={{ margin: 0 }}>普通用户</Tag>}
                </span>
              </div>
            </div>
            {user?.is_admin && (
              <Button type="link" onClick={() => setPwdModalOpen(true)} style={{ color: 'white' }}>
                修改密码
              </Button>
            )}
            <Button type="link" icon={<LogoutOutlined />} onClick={onLogout} style={{ color: 'white' }}>
              退出
            </Button>
          </Space>
        </Header>
        <Content style={{ padding: '24px', overflow: 'auto' }}>
          <Outlet context={contextValue} />
        </Content>
        <Footer style={{ textAlign: 'center', background: '#f0f2f5' }}>
          CostMatrix © 2026 | GalaxySpace AI Team
        </Footer>
      </Layout>
      <Modal
        title="修改管理员密码"
        open={pwdModalOpen}
        onCancel={() => { setPwdModalOpen(false); form.resetFields() }}
        onOk={handlePasswordChange}
        confirmLoading={changingPwd}
        destroyOnClose
      >
        <Form
          layout="vertical"
          form={form}
          requiredMark={false}
        >
          <Form.Item
            label="当前密码"
            name="current_password"
            rules={[{ required: true, message: '请输入当前密码' }]}
          >
            <Input.Password placeholder="请输入当前密码" autoComplete="current-password" />
          </Form.Item>
          <Form.Item
            label="新密码"
            name="new_password"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '至少 6 个字符' },
            ]}
          >
            <Input.Password placeholder="请输入新密码" autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            label="确认新密码"
            name="confirm_password"
            dependencies={['new_password']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) {
                    return Promise.resolve()
                  }
                  return Promise.reject(new Error('两次输入的新密码不一致'))
                }
              }),
            ]}
          >
            <Input.Password placeholder="再次输入新密码" autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  )
}

export default MainLayout
