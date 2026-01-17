import { createContext, useContext, useState, useEffect, useMemo, useCallback, ReactNode } from 'react'
import { message, Modal } from 'antd'
import type { MonthContextValue } from '@/types'
import { getAvailableMonths, deleteMonth as deleteMonthApi } from '@/services/api'

const MonthContext = createContext<MonthContextValue | undefined>(undefined)

export const useMonthContext = () => {
  const context = useContext(MonthContext)
  if (!context) {
    throw new Error('useMonthContext must be used within MonthProvider')
  }
  return context
}

interface MonthProviderProps {
  children: ReactNode
}

export const MonthProvider: React.FC<MonthProviderProps> = ({ children }) => {
  const [availableMonths, setAvailableMonths] = useState<string[]>([])
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null)

  const refreshMonths = useCallback(async () => {
    try {
      const res = await getAvailableMonths()
      if (res.success && res.data) {
        setAvailableMonths(res.data)
        if (res.data.length > 0) {
          setSelectedMonth(res.data[res.data.length - 1] || null)
        }
      }
    } catch (error) {
      message.error('获取月份列表失败')
    }
  }, [])

  useEffect(() => {
    refreshMonths()
  }, [refreshMonths])

  const selectMonth = useCallback((month: string | null) => {
    setSelectedMonth(month)
  }, [])

  const deleteMonth = useCallback(async (month: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除 ${month} 月份的所有数据吗？此操作将删除该月份的考勤记录、差旅费用记录、异常记录，以及仅包含该月份数据的原始Excel文件。此操作不可撤销！`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          const res = await deleteMonthApi(month)
          if (res.success) {
            const deletedData = res.data
            message.success(
              `删除成功！考勤记录: ${deletedData.deleted_attendance}条，差旅记录: ${deletedData.deleted_travel}条，异常记录: ${deletedData.deleted_anomalies}条`
            )
            // 刷新月份列表
            await refreshMonths()
            // 如果删除的是当前选中的月份，清空选中状态
            if (selectedMonth === month) {
              setSelectedMonth(null)
            }
          }
        } catch (error: any) {
          message.error(`删除失败: ${error.message}`)
        }
      }
    })
  }, [refreshMonths, selectedMonth])

  const contextValue: MonthContextValue = useMemo(() => ({
    availableMonths,
    selectedMonth,
    selectMonth,
    refreshMonths,
    deleteMonth
  }), [availableMonths, selectedMonth, selectMonth, refreshMonths, deleteMonth])

  return <MonthContext.Provider value={contextValue}>{children}</MonthContext.Provider>
}
