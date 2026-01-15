import { createContext, useContext, useState, useEffect, useMemo, useCallback, ReactNode } from 'react'
import { message } from 'antd'
import type { MonthContextValue } from '@/types'
import { getAvailableMonths } from '@/services/api'

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

  const contextValue: MonthContextValue = useMemo(() => ({
    availableMonths,
    selectedMonth,
    selectMonth,
    refreshMonths
  }), [availableMonths, selectedMonth, selectMonth, refreshMonths])

  return <MonthContext.Provider value={contextValue}>{children}</MonthContext.Provider>
}
