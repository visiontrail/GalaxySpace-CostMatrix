import { useEffect, useMemo, useState } from 'react'
import { Layout, Menu, Typography, Button, Space, Empty } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { DashboardOutlined, UploadOutlined, RocketOutlined, MenuFoldOutlined, MenuUnfoldOutlined, DeleteOutlined } from '@ant-design/icons'
import type { MonthContextValue } from '@/types'
import { MonthProvider, useMonthContext } from '@/contexts/MonthContext'

const { Header, Content, Footer, Sider } = Layout
const { Title } = Typography

const MainLayout = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const menuItems = [
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
}

const MainLayoutContent: React.FC<MainLayoutContentProps> = ({
  sidebarCollapsed,
  toggleSidebar,
  menuItems,
  handleMenuClick,
  location,
}) => {
  const { availableMonths, selectedMonth, selectMonth, refreshMonths, deleteMonth } = useMonthContext()

  useEffect(() => {
    refreshMonths()
  }, [refreshMonths])

  const contextValue: MonthContextValue = useMemo(() => ({
    availableMonths,
    selectedMonth,
    selectMonth,
    refreshMonths,
    deleteMonth,
  }), [availableMonths, selectedMonth, selectMonth, refreshMonths, deleteMonth])

  const formatMonth = (month: string) => {
    const [year, monthNum] = month.split('-')
    return `${year}年${monthNum}月`
  }

  const monthItems = availableMonths.map((month) => ({
    key: month,
    label: (
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontWeight: 600, color: '#1f1f1f' }}>
            {formatMonth(month)}
          </span>
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
      </div>
    ),
  }))

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
        }}
      >
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between', padding: '0 8px' }}>
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
          <Button size="small" onClick={refreshMonths}>
            刷新
          </Button>
        </Space>
        <div style={{ marginTop: 12 }}>
          {availableMonths.length === 0 ? (
            <Empty description="暂无数据" style={{ paddingTop: 20 }} />
          ) : (
            <Menu
              className="month-menu"
              mode="inline"
              selectedKeys={selectedMonth ? [selectedMonth] : []}
              onClick={(info) => {
                selectMonth(info.key)
              }}
              items={monthItems}
              style={{ borderInlineEnd: 'none', height: 'calc(100vh - 120px)', overflowY: 'auto' }}
            />
          )}
        </div>
      </Sider>
      <Layout>
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
        </Header>
        <Content style={{ padding: '24px' }}>
          <Outlet context={contextValue} />
        </Content>
        <Footer style={{ textAlign: 'center', background: '#f0f2f5' }}>
          CostMatrix © 2026 | GalaxySpace AI Team
        </Footer>
      </Layout>
    </Layout>
  )
}

export default MainLayout
