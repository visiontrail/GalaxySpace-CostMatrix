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
  const [selectedMonths, setSelectedMonths] = useState<string[]>([])
  const [pendingMonths, setPendingMonthsState] = useState<string[]>([])

  const normalizeSelection = useCallback((selection: string[], available: string[]) => {
    return available.filter(month => selection.includes(month))
  }, [])

  const isSameSelection = useCallback((a: string[], b: string[]) => {
    return a.length === b.length && a.every(item => b.includes(item))
  }, [])

  const refreshMonths = useCallback(async () => {
    try {
      const res = await getAvailableMonths()
      if (res.success && res.data) {
        const months = res.data
        setAvailableMonths(months)

        const computeNextSelection = (current: string[]) => {
          const normalized = normalizeSelection(current, months)
          if (normalized.length > 0) return normalized
          if (months.length > 0) return [months[months.length - 1]]
          return []
        }

        setPendingMonthsState((prev) => {
          const next = computeNextSelection(prev)
          return isSameSelection(prev, next) ? prev : next
        })

        setSelectedMonths((prev) => {
          const next = computeNextSelection(prev)
          return isSameSelection(prev, next) ? prev : next
        })
      }
    } catch (error) {
      message.error('获取月份列表失败')
    }
  }, [isSameSelection, normalizeSelection])

  useEffect(() => {
    refreshMonths()
  }, [refreshMonths])

  const setPendingMonths = useCallback((months: string[]) => {
    setPendingMonthsState(months)
  }, [])

  const applySelectedMonths = useCallback((months?: string[]) => {
    const targetMonths = normalizeSelection(
      months ?? pendingMonths,
      availableMonths
    )
    setSelectedMonths((prev) => {
      if (isSameSelection(prev, targetMonths)) return prev
      return [...targetMonths]
    })
  }, [availableMonths, isSameSelection, normalizeSelection, pendingMonths])

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
          if (res.success && res.data) {
            const deletedData = res.data
            message.success(
              `删除成功！考勤记录: ${deletedData.deleted_attendance}条，差旅记录: ${deletedData.deleted_travel}条，异常记录: ${deletedData.deleted_anomalies}条`
            )
            // 刷新月份列表
            await refreshMonths()
          }
        } catch (error: any) {
          message.error(`删除失败: ${error.message}`)
        }
      }
    })
  }, [refreshMonths])

  const contextValue: MonthContextValue = useMemo(() => ({
    availableMonths,
    selectedMonths,
    pendingMonths,
    setPendingMonths,
    applySelectedMonths,
    refreshMonths,
    deleteMonth
  }), [availableMonths, selectedMonths, pendingMonths, setPendingMonths, applySelectedMonths, refreshMonths, deleteMonth])

  return <MonthContext.Provider value={contextValue}>{children}</MonthContext.Provider>
}
