import React, { useState, useEffect } from 'react'
import { Select, Button, Space } from 'antd'
import type { SelectProps } from 'antd'

interface MonthSelectorProps {
  availableMonths: string[]
  selectedMonths: string[]
  onChange: (months: string[]) => void
}

export const MonthSelector: React.FC<MonthSelectorProps> = ({
  availableMonths,
  selectedMonths,
  onChange
}) => {
  const [months, setMonths] = useState<string[]>(selectedMonths)

  useEffect(() => {
    setMonths(selectedMonths)
  }, [selectedMonths])

  const currentYear = new Date().getFullYear()

  const getQuarterMonths = (quarter: number): string[] => {
    const quarters: Record<number, number[]> = {
      1: [1, 2, 3],
      2: [4, 5, 6],
      3: [7, 8, 9],
      4: [10, 11, 12]
    }
    return quarters[quarter].map(m => `${currentYear}-${String(m).padStart(2, '0')}`)
  }

  const getYearMonths = (): string[] => {
    const currentMonth = new Date().getMonth() + 1
    const months = []
    for (let i = 1; i <= currentMonth; i++) {
      months.push(`${currentYear}-${String(i).padStart(2, '0')}`)
    }
    return months
  }

  const handleQuarterClick = (quarter: number) => {
    const quarterMonths = getQuarterMonths(quarter)
    const availableQuarterMonths = quarterMonths.filter(m => availableMonths.includes(m))
    onChange(availableQuarterMonths)
  }

  const handleYearClick = () => {
    const yearMonths = getYearMonths()
    const availableYearMonths = yearMonths.filter(m => availableMonths.includes(m))
    onChange(availableYearMonths)
  }

  const handleClear = () => {
    onChange([])
  }

  const options: SelectProps['options'] = availableMonths.map(month => ({
    label: month,
    value: month
  }))

  if (availableMonths.length === 0) {
    return null
  }

  return (
    <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
      <Select
        mode="multiple"
        placeholder="选择月份"
        value={months}
        onChange={(value) => {
          setMonths(value)
          onChange(value)
        }}
        options={options}
        style={{ minWidth: 300, maxWidth: 500 }}
        maxTagCount="responsive"
      />
      <Space>
        <Button
          size="small"
          onClick={() => handleQuarterClick(1)}
          disabled={!getQuarterMonths(1).some(m => availableMonths.includes(m))}
        >
          Q1
        </Button>
        <Button
          size="small"
          onClick={() => handleQuarterClick(2)}
          disabled={!getQuarterMonths(2).some(m => availableMonths.includes(m))}
        >
          Q2
        </Button>
        <Button
          size="small"
          onClick={() => handleQuarterClick(3)}
          disabled={!getQuarterMonths(3).some(m => availableMonths.includes(m))}
        >
          Q3
        </Button>
        <Button
          size="small"
          onClick={() => handleQuarterClick(4)}
          disabled={!getQuarterMonths(4).some(m => availableMonths.includes(m))}
        >
          Q4
        </Button>
        <Button
          size="small"
          onClick={handleYearClick}
          disabled={!getYearMonths().some(m => availableMonths.includes(m))}
        >
          {currentYear}全年
        </Button>
        <Button
          size="small"
          onClick={handleClear}
          disabled={months.length === 0}
        >
          清除
        </Button>
      </Space>
    </div>
  )
}
