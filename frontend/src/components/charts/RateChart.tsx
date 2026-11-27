import {
  LineChart,
  Line,
  Area,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { formatCurrency, formatPercent, formatDate } from '@/lib/utils'

interface RateChartProps {
  data: Array<{
    timestamp: string
    rate: number
    bid?: number
    ask?: number
    pct_change?: number
  }>
  baseCurrency: string
  height?: number
  showBollinger?: boolean
  currentRate?: number
}

export function RateChart({
  data,
  baseCurrency,
  height = 400,
  showBollinger = true,
  currentRate,
}: RateChartProps) {
  if (!data.length) return null

  const chartData = data.map((d, i) => {
    const prevRate = i > 0 ? data[i - 1].rate : d.rate
    const pctChange = prevRate !== 0 ? ((d.rate - prevRate) / prevRate) * 100 : 0

    return {
      ...d,
      date: formatDate(d.timestamp, 'dd/MM'),
      fullDate: formatDate(d.timestamp, 'dd/MM/yyyy HH:mm'),
      pctChange: Number(pctChange.toFixed(2)),
    }
  })

  let bollingerData: Array<{ upper: number; lower: number; middle: number }> = []
  if (showBollinger && chartData.length >= 20) {
    const period = 20
    const multiplier = 2

    chartData.forEach((_, i) => {
      if (i >= period - 1) {
        const slice = chartData.slice(i - period + 1, i + 1)
        const rates = slice.map(d => d.rate)
        const mean = rates.reduce((a, b) => a + b, 0) / rates.length
        const std = Math.sqrt(rates.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / rates.length)
        bollingerData[i] = {
          middle: mean,
          upper: mean + multiplier * std,
          lower: mean - multiplier * std,
        }
      } else {
        bollingerData[i] = { upper: 0, lower: 0, middle: 0 }
      }
    })
  }

  const mergedData = chartData.map((d, i) => ({
    ...d,
    bbUpper: bollingerData[i]?.upper,
    bbLower: bollingerData[i]?.lower,
    bbMiddle: bollingerData[i]?.middle,
  }))

  const maxRate = Math.max(...chartData.map(d => d.rate))
  const minRate = Math.min(...chartData.map(d => d.rate))
  const padding = (maxRate - minRate) * 0.1 || 0.01

  return (
    <div className="w-full h-[400px]">
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={mergedData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(value) => formatCurrency(value, baseCurrency, 4)}
            domain={[minRate - padding, maxRate + padding]}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#fff',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
            }}
            formatter={(value: number, name: string) => {
              if (name === 'rate' || name === 'bid' || name === 'ask' || name === 'bbUpper' || name === 'bbLower' || name === 'bbMiddle') {
                return [formatCurrency(value, baseCurrency, 4), name]
              }
              if (name === 'pctChange') {
                return [formatPercent(value), name]
              }
              return [value, name]
            }}
            labelFormatter={(label) => {
              const item = mergedData.find(d => d.date === label)
              return item?.fullDate || label
            }}
          />
          <Legend wrapperStyle={{ paddingTop: '20px' }} />

          {showBollinger && bollingerData.some(d => d.upper > 0) && (
            <>
              <Area
                type="monotone"
                dataKey="bbUpper"
                stroke="#3b82f6"
                strokeWidth={1}
                fillOpacity={0}
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="bbLower"
                stroke="#3b82f6"
                strokeWidth={1}
                fillOpacity={0.1}
                fill="#3b82f6"
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="bbMiddle"
                stroke="#3b82f6"
                strokeWidth={1}
                strokeDasharray="5 5"
                dot={false}
                isAnimationActive={false}
              />
            </>
          )}

          <Line
            type="monotone"
            dataKey="rate"
            name="Taxa"
            stroke="#0ea5e9"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 6, strokeWidth: 2, stroke: '#0ea5e9', fill: '#fff' }}
            isAnimationActive
          />

          {currentRate && (
            <ReferenceLine
              y={currentRate}
              stroke="#9ca3af"
              strokeWidth={1}
              strokeDasharray="5 5"
              label={{
                value: `Atual: ${formatCurrency(currentRate, baseCurrency, 4)}`,
                position: 'right',
                fill: '#9ca3af',
                fontSize: 11,
              }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

interface RateChangeChartProps {
  data: Array<{
    timestamp: string
    rate: number
    pct_change: number
  }>
  height?: number
}

export function RateChangeChart({ data, height = 200 }: RateChangeChartProps) {
  if (!data.length) return null

  const chartData = data.map((d, i) => {
    const prevRate = i > 0 ? data[i - 1].rate : d.rate
    const pct = (d.pct_change ?? (prevRate !== 0 ? ((d.rate - prevRate) / prevRate) * 100 : 0))
    return {
      ...d,
      date: formatDate(d.timestamp, 'dd/MM'),
      fullDate: formatDate(d.timestamp, 'dd/MM/yyyy'),
      pctChange: Number(pct.toFixed(2)),
      pctColor: pct >= 0 ? '#22c55e' : '#ef4444',
    }
  })

  return (
    <div className="w-full h-[200px]">
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(value) => formatPercent(value)}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#fff',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
            }}
            formatter={(value: number) => [formatPercent(value), 'Variação']}
            labelFormatter={(label) => {
              const item = chartData.find(d => d.date === label)
              return item?.fullDate || label
            }}
          />
          <Bar dataKey="pctChange" name="Variação %" radius={[4, 4, 0, 0]} maxBarSize={30}>
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.pctColor} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

interface ComparisonChartProps {
  data: Array<{
    quote: string
    rate: number
    change_pct: number
    current: number
  }>
  baseCurrency: string
  height?: number
}

export function ComparisonChart({ data, baseCurrency, height = 400 }: ComparisonChartProps) {
  if (!data.length) return null

  const sortedData = [...data].sort((a, b) => b.change_pct - a.change_pct)

  return (
    <div className="w-full" style={{ height: `${Math.max(height, sortedData.length * 35)}px` }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={sortedData}
          layout="vertical"
          margin={{ top: 10, right: 30, left: 10, bottom: 10 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickLine={false}
            tickFormatter={(value) => formatPercent(value)}
          />
          <YAxis
            type="category"
            dataKey="quote"
            tick={{ fontSize: 12, fill: '#374151' }}
            axisLine={false}
            tickLine={false}
            width={60}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#fff',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
            }}
            formatter={(value: number, name: string) => {
              if (name === 'rate' || name === 'current') {
                return [formatCurrency(value, baseCurrency, 4), name]
              }
              if (name === 'change_pct') {
                return [formatPercent(value), name]
              }
              return [value, name]
            }}
          />
          <Bar dataKey="change_pct" name="Variação %" radius={[0, 4, 4, 0]} maxBarSize={40}>
            {sortedData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.change_pct >= 0 ? '#22c55e' : '#ef4444'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
