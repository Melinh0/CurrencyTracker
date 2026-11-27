import {
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from 'recharts'
import { cn } from '@/lib/utils'

interface CorrelationData {
  x: string
  y: string
  value: number
}

interface CorrelationHeatmapProps {
  data: CorrelationData[]
  currencies: string[]
  height?: number
  onCellClick?: (x: string, y: string, value: number) => void
}

export function CorrelationHeatmap({
  data,
  currencies,
  height = 500,
  onCellClick,
}: CorrelationHeatmapProps) {
  if (!data.length || !currencies.length) return null

  const matrix = currencies.map(y =>
    currencies.map(x => {
      const found = data.find(d => d.x === x && d.y === y)
      return found ? found.value : (x === y ? 1 : 0)
    })
  )

  const heatmapData = currencies.flatMap((y, yIndex) =>
    currencies.map((x, xIndex) => ({
      x,
      y,
      value: matrix[yIndex][xIndex],
    }))
  )

  const getColor = (value: number) => {

    if (value >= 0) {
      const intensity = Math.min(value, 1)
      const blue = Math.round(30 + intensity * 180)
      return `rgb(255, ${255 - blue}, ${255 - blue})`
    } else {
      const intensity = Math.min(Math.abs(value), 1)
      const red = Math.round(30 + intensity * 200)
      return `rgb(${255}, ${255 - red}, ${255 - red})`
    }
  }

  const getTextColor = (value: number) => {
    const absValue = Math.abs(value)
    if (absValue > 0.5) return '#fff'
    return '#1f2937'
  }

  return (
    <div className="w-full" style={{ height: `${height}px` }}>
      <ComposedChart
        data={heatmapData}
        margin={{ top: 20, right: 20, left: 60, bottom: 20 }}
      >
        <CartesianGrid stroke="transparent" />
        <XAxis
          type="category"
          dataKey="x"
          tick={{ fontSize: 12, fill: '#374151' }}
          axisLine={false}
          tickLine={false}
          tickMargin={8}
        />
        <YAxis
          type="category"
          dataKey="y"
          tick={{ fontSize: 12, fill: '#374151' }}
          axisLine={false}
          tickLine={false}
          width={60}
          tickMargin={8}
          mirror={true}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
          }}
          formatter={(value: number) => [value.toFixed(3), 'Correlação']}
          labelFormatter={(label) => {
            const [x, y] = label.split('-')
            return `${y} vs ${x}`
          }}
        />
        {currencies.map((y, yIndex) => (
          <CustomHeatmapCells
            key={y}
            y={y}
            yIndex={yIndex}
            xValues={currencies}
            matrix={matrix}
            getColor={getColor}
            getTextColor={getTextColor}
            onCellClick={onCellClick}
          />
        ))}
      </ComposedChart>
    </div>
  )
}

interface CustomHeatmapCellsProps {
  y: string
  yIndex: number
  xValues: string[]
  matrix: number[][]
  getColor: (value: number) => string
  getTextColor: (value: number) => string
  onCellClick?: (x: string, y: string, value: number) => void
}

function CustomHeatmapCells({
  y,
  yIndex,
  xValues,
  matrix,
  getColor,
  getTextColor,
  onCellClick,
}: CustomHeatmapCellsProps) {
  const cells = xValues.map((x, xIndex) => {
    const value = matrix[yIndex][xIndex]
    const color = getColor(value)
    const textColor = getTextColor(value)
    const isDiagonal = x === y

    return (
      <Cell
        key={`${x}-${y}`}
        x={xIndex}
        y={yIndex}
        width={40}
        height={40}
        fill={color}
        onClick={() => onCellClick?.(x, y, value)}
        style={{
          cursor: onCellClick ? 'pointer' : 'default',
          transition: 'opacity 0.2s',
        }}
        onMouseEnter={(e) => {
          if (onCellClick) {
            e.currentTarget.style.opacity = '0.8'
          }
        }}
        onMouseLeave={(e) => {
          if (onCellClick) {
            e.currentTarget.style.opacity = '1'
          }
        }}
      >
        <text
          x={20}
          y={25}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={isDiagonal ? 11 : 10}
          fontWeight={isDiagonal ? 600 : 400}
          fill={textColor}
          pointerEvents="none"
        >
          {value.toFixed(2)}
        </text>
      </Cell>
    )
  })

  return <>{cells}</>
}

export function SimpleCorrelationHeatmap({
  data,
  currencies,
  height = 500,
  onCellClick,
}: CorrelationHeatmapProps) {
  if (!data.length || !currencies.length) return null

  const matrix = currencies.map(y =>
    currencies.map(x => {
      const found = data.find(d => d.x === x && d.y === y)
      return found ? found.value : (x === y ? 1 : 0)
    })
  )

  const getColor = (value: number) => {
    if (value >= 0) {
      const intensity = Math.min(value, 1)
      return `rgba(34, 197, 94, ${0.1 + intensity * 0.4})`
    } else {
      const intensity = Math.min(Math.abs(value), 1)
      return `rgba(239, 68, 68, ${0.1 + intensity * 0.4})`
    }
  }

  const getTextColor = (value: number) => {
    const absValue = Math.abs(value)
    if (absValue > 0.5) return '#fff'
    return '#1f2937'
  }

  const cellSize = Math.min(50, Math.floor((height - 80) / currencies.length))

  return (
    <div className="overflow-x-auto">
      <div className="inline-flex" style={{ minWidth: 'max-content' }}>
        
        <div className="flex flex-col">
          <div className={cn('flex items-center justify-center font-medium text-xs text-gray-500', `w-[${cellSize}px] h-[${cellSize}px]`)} />
          {currencies.map((x) => (
            <div
              key={`header-${x}`}
              className={cn(
                'flex items-center justify-center font-medium text-xs text-gray-500 border border-gray-200 dark:border-gray-700',
                `w-[${cellSize}px] h-[${cellSize}px]`
              )}
            >
              {x}
            </div>
          ))}
        </div>

        
        {currencies.map((y, yIndex) => (
          <div key={`row-${y}`} className="flex flex-col">
            <div
              className={cn(
                'flex items-center justify-center font-medium text-xs text-gray-500 border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50',
                `w-[${cellSize}px] h-[${cellSize}px]`
              )}
            >
              {y}
            </div>
            {currencies.map((x, xIndex) => {
              const value = matrix[yIndex][xIndex]
              const color = getColor(value)
              const textColor = getTextColor(value)
              const isDiagonal = x === y

              return (
                <div
                  key={`cell-${x}-${y}`}
                  className={cn(
                    'flex items-center justify-center border border-gray-200 dark:border-gray-700 transition-opacity',
                    `w-[${cellSize}px] h-[${cellSize}px]`,
                    onCellClick && 'cursor-pointer hover:opacity-80'
                  )}
                  style={{ backgroundColor: color }}
                  onClick={() => onCellClick?.(x, y, value)}
                >
                  <span
                    className={cn(
                      'font-mono text-[10px] font-medium',
                      isDiagonal && 'font-semibold'
                    )}
                    style={{ color: textColor }}
                  >
                    {value.toFixed(2)}
                  </span>
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
