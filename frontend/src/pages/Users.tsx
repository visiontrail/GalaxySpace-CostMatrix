import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, Form, Input, Space, Switch, Table, Tag, Typography, message, Popconfirm } from 'antd'
import { PlusOutlined, UserOutlined, CrownOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { listUsers, createUser, updateUser, deleteUser } from '@/services/api'
import type { UserInfo } from '@/types'
import { useAuth } from '@/contexts/AuthContext'
import type { ColumnsType } from 'antd/es/table'

const { Title, Text } = Typography

const Users = () => {
  const navigate = useNavigate()
  const { user } = useAuth()

  const [data, setData] = useState<UserInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<UserInfo | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [form] = Form.useForm()

  const columns: ColumnsType<UserInfo> = useMemo(
    () => [
      {
        title: '用户名',
        dataIndex: 'username',
        key: 'username',
        render: (value: string) => (
          <Space>
            <UserOutlined style={{ color: '#1677ff' }} />
            <Text strong>{value}</Text>
          </Space>
        )
      },
      {
        title: '角色',
        dataIndex: 'is_admin',
        key: 'role',
        width: 140,
        render: (isAdmin: boolean) =>
          isAdmin ? (
            <Tag color="gold" icon={<CrownOutlined />}>
              管理员
            </Tag>
          ) : (
            <Tag color="blue">普通用户</Tag>
          ),
      },
      {
        title: '创建时间',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 200,
        render: (value?: string) => value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-',
      },
      {
        title: '操作',
        key: 'actions',
        width: 220,
        render: (_, record) => (
          <Space>
            <Button size="small" icon={<EditOutlined />} onClick={() => openEditModal(record)}>
              修改
            </Button>
            <Popconfirm
              title="确认删除该用户？"
              okText="删除"
              okButtonProps={{ danger: true }}
              onConfirm={() => handleDelete(record.username)}
              disabled={record.username === user?.username}
              description={record.username === user?.username ? '不能删除当前登录账户' : undefined}
            >
              <Button size="small" danger icon={<DeleteOutlined />} disabled={record.username === user?.username}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        ),
      },
    ],
    [user?.username]
  )

  const fetchData = async () => {
    setLoading(true)
    try {
      const users = await listUsers()
      setData(users)
    } catch (error: any) {
      message.error(error.message || '获取用户列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!user?.is_admin) {
      message.error('需要管理员权限')
      navigate('/')
      return
    }
    fetchData()
  }, [user, navigate])

  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      setSubmitting(true)
      if (editingUser) {
        await updateUser(editingUser.username, values)
        message.success('用户更新成功')
      } else {
        await createUser(values)
        message.success('用户创建成功')
      }
      setModalOpen(false)
      form.resetFields()
      setEditingUser(null)
      fetchData()
    } catch (error: any) {
      if (error?.errorFields) return
      message.error(error.message || (editingUser ? '更新用户失败' : '创建用户失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const openEditModal = (record: UserInfo) => {
    setEditingUser(record)
    setModalOpen(true)
    form.setFieldsValue({
      username: record.username,
      password: '',
      is_admin: record.is_admin,
    })
  }

  const handleDelete = async (username: string) => {
    try {
      await deleteUser(username)
      message.success('用户已删除')
      fetchData()
    } catch (error: any) {
      message.error(error.message || '删除用户失败')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>用户管理</Title>
          <Text type="secondary">仅管理员可添加新用户，普通用户可访问其余功能。</Text>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditingUser(null)
            form.resetFields()
            form.setFieldsValue({ is_admin: false })
            setModalOpen(true)
          }}
        >
          新增用户
        </Button>
      </div>

      <Card>
        <Table
          rowKey="username"
          loading={loading}
          columns={columns}
          dataSource={data}
          pagination={false}
        />
      </Card>

      {modalOpen && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.35)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <Card
            title="新增用户"
            style={{ width: 420 }}
            actions={[
              <Button key="cancel" onClick={() => { setModalOpen(false); form.resetFields() }}>
                取消
              </Button>,
              <Button key="save" type="primary" loading={submitting} onClick={handleCreate}>
                保存
              </Button>
            ]}
          >
            <Form
              form={form}
              layout="vertical"
              requiredMark={false}
            >
              <Form.Item
                label="用户名"
                name="username"
                rules={[
                  { required: true, message: '请输入用户名' },
                  { min: 3, message: '至少 3 个字符' },
                ]}
              >
                <Input placeholder="请输入用户名" disabled={!!editingUser} />
              </Form.Item>
              <Form.Item
                label={editingUser ? '新密码（留空则不修改）' : '密码'}
                name="password"
                rules={[
                  () => ({
                    validator(_, value) {
                      if (!value && editingUser) return Promise.resolve()
                      if (value && value.length < 6) {
                        return Promise.reject(new Error('至少 6 个字符'))
                      }
                      if (!value && !editingUser) {
                        return Promise.reject(new Error('请输入密码'))
                      }
                      return Promise.resolve()
                    }
                  }),
                ]}
              >
                <Input.Password placeholder={editingUser ? '不修改请留空' : '设置用户密码'} />
              </Form.Item>
              <Form.Item
                label="管理员权限"
                name="is_admin"
                valuePropName="checked"
              >
                <Switch checkedChildren="是" unCheckedChildren="否" />
              </Form.Item>
            </Form>
          </Card>
        </div>
      )}
    </div>
  )
}

export default Users
