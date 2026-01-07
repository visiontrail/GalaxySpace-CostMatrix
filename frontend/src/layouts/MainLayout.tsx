import { useEffect, useMemo, useState, useCallback } from 'react'
import { Layout, Menu, Typography, Tag, Button, Space, Spin, message, Empty } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { DashboardOutlined, UploadOutlined, RocketOutlined, MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons'
import type { UploadRecord } from '@/types'
import { listUploads } from '@/services/api'

const { Header, Content, Footer, Sider } = Layout
const { Title } = Typography

export interface UploadContextValue {
  uploads: UploadRecord[]
  selectedUpload: UploadRecord | null
  selectUpload: (upload: UploadRecord | null) => void
  refreshUploads: () => Promise<void>
}

const MainLayout = () => {
  const navigate = useNavigate()
  const location = useLocation()
  const [uploads, setUploads] = useState<UploadRecord[]>([])
  const [selectedUpload, setSelectedUpload] = useState<UploadRecord | null>(null)
  const [loadingUploads, setLoadingUploads] = useState(false)
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

  const refreshUploads = useCallback(async () => {
    setLoadingUploads(true)
    try {
      const res = await listUploads()
      if (res.success && res.data) {
        const sorted = [...res.data].sort(
          (a, b) => (b.upload_time || '').localeCompare(a.upload_time || '')
        )
        setUploads(sorted)
        setSelectedUpload((current) => {
          const matched = sorted.find((item) => item.file_path === current?.file_path)
          const nextSelection = matched || sorted.find((item) => item.parsed) || sorted[0] || null
          return nextSelection || null
        })
      } else {
        message.error(res.message || '获取上传记录失败')
      }
    } catch (error: any) {
      message.error(error.message || '获取上传记录失败')
    } finally {
      setLoadingUploads(false)
    }
  }, [])

  useEffect(() => {
    refreshUploads()
  }, [refreshUploads])

  const contextValue: UploadContextValue = useMemo(() => ({
    uploads,
    selectedUpload,
    selectUpload: setSelectedUpload,
    refreshUploads,
  }), [uploads, selectedUpload, refreshUploads])

  const uploadItems = uploads.map((item) => ({
    key: item.file_path,
    label: (
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <span style={{ fontWeight: 600, color: '#1f1f1f' }}>{item.file_name}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Tag color={item.parsed ? 'green' : 'orange'} style={{ marginInlineEnd: 0 }}>
            {item.parsed ? '已解析' : '未解析'}
          </Tag>
          <span style={{ color: '#8c8c8c', fontSize: 12 }}>
            {item.upload_time || '-'}
          </span>
        </div>
      </div>
    ),
    disabled: item.exists === false,
  }))

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        theme="light"
        collapsible
        collapsed={sidebarCollapsed}
        onCollapse={(collapsed) => setSidebarCollapsed(collapsed)}
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
            <Title level={4} style={{ margin: 0 }}>数据文件</Title>
          </Space>
          <Button size="small" onClick={refreshUploads} loading={loadingUploads}>
            刷新
          </Button>
        </Space>
        <div style={{ marginTop: 12 }}>
          {loadingUploads ? (
            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <Spin />
            </div>
          ) : uploads.length ? (
            <Menu
              className="upload-menu"
              mode="inline"
              selectedKeys={selectedUpload ? [selectedUpload.file_path] : []}
              onClick={(info) => {
                const target = uploads.find((item) => item.file_path === info.key)
                setSelectedUpload(target || null)
              }}
              items={uploadItems}
              style={{ borderInlineEnd: 'none', height: 'calc(100vh - 120px)', overflowY: 'auto' }}
            />
          ) : (
            <Empty description="暂无文件" style={{ paddingTop: 20 }} />
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
              CorpPilot
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
          CorpPilot © 2026 | GalaxySpace AI Team
        </Footer>
      </Layout>
    </Layout>
  )
}

export default MainLayout
