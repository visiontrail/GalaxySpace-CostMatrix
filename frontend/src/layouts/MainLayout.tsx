import { Layout, Menu, Typography } from 'antd'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { DashboardOutlined, UploadOutlined, RocketOutlined } from '@ant-design/icons'

const { Header, Content, Footer } = Layout
const { Title } = Typography

const MainLayout = () => {
  const navigate = useNavigate()
  const location = useLocation()

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

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ 
        display: 'flex', 
        alignItems: 'center', 
        background: '#001529',
        padding: '0 24px'
      }}>
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
        <Outlet />
      </Content>
      <Footer style={{ textAlign: 'center', background: '#f0f2f5' }}>
        CorpPilot © 2026 | GalaxySpace AI Team
      </Footer>
    </Layout>
  )
}

export default MainLayout

