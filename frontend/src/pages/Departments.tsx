import { Card, Typography, Empty, Button } from 'antd'
import { useNavigate } from 'react-router-dom'
import { ArrowLeftOutlined } from '@ant-design/icons'

const { Title } = Typography

const Departments = () => {
  const navigate = useNavigate()

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')} style={{ marginBottom: 16 }}>
        返回看板
      </Button>
      <Card>
        <Title level={3}>部门详情</Title>
        <Empty
          description="部门详情功能开发中"
          style={{ padding: '40px 0' }}
        />
      </Card>
    </div>
  )
}

export default Departments
