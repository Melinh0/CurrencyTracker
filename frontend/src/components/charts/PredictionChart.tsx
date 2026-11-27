import {
  LineChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from 'recharts'
import { formatCurrency, formatDate, cn } from '@/lib/utils'
import type { PredictionResponse } from '@/lib/api'

interface PredictionChartProps {
  prediction: PredictionResponse
  baseCurrency: string
  currentRate?: number
  height?: number
}

export function PredictionChart({
  prediction,
  baseCurrency,
  currentRate,
  height = 400,
}: PredictionChartProps) {
  const { predictions, confidence_level } = prediction

  if (!predictions.length) return null

  const chartData = predictions.map((p) => ({
    ...p,
    date: formatDate(p.date, 'dd/MM'),
    fullDate: formatDate(p.date, 'dd/MM/yyyy'),
  }))

  const allValues = [
    ...predictions.map(p => p.predicted_rate),
    ...predictions.map(p => p.upper_bound),
    ...predictions.map(p => p.lower_bound),
  ]
  if (currentRate) allValues.push(currentRate)

  const maxRate = Math.max(...allValues)
  const minRate = Math.min(...allValues)
  const padding = (maxRate - minRate) * 0.15 || 0.01

  return (
    <div className="w-full h-[400px]">
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickLine={false}
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
              if (name === 'predicted_rate' || name === 'upper_bound' || name === 'lower_bound') {
                return [formatCurrency(value, baseCurrency, 4), name.replace('_', ' ')]
              }
              return [value, name]
            }}
            labelFormatter={(label) => {
              const item = chartData.find(d => d.date === label)
              return item?.fullDate || label
            }}
          />
          <Legend wrapperStyle={{ paddingTop: '20px' }} />

          
          <Area
            type="monotone"
            dataKey="upper_bound"
            stroke="#f97316"
            strokeWidth={1}
            fillOpacity={0}
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="lower_bound"
            stroke="#f97316"
            strokeWidth={1}
            fillOpacity={0.15}
            fill="#f97316"
            isAnimationActive={false}
          />

          
          <Line
            type="monotone"
            dataKey="predicted_rate"
            name="Previsão"
            stroke="#f97316"
            strokeWidth={2.5}
            dot={{ r: 5, strokeWidth: 2, stroke: '#f97316', fill: '#fff' }}
            activeDot={{ r: 8, strokeWidth: 2, stroke: '#f97316', fill: '#fff' }}
            isAnimationActive={true}
          />

          
          {currentRate && (
            <ReferenceLine
              y={currentRate}
              stroke="#9ca3af"
              strokeWidth={1.5}
              strokeDasharray="5 5"
              label={{
                value: `Atual: ${formatCurrency(currentRate, baseCurrency, 4)}`,
                position: 'right',
                fill: '#9ca3af',
                fontSize: 11,
                fontWeight: 500,
              }}
            />
          )}

          <ReferenceArea
            x1={chartData[0]?.date}
            x2={chartData[chartData.length - 1]?.date}
            y1={chartData[0]?.lower_bound}
            y2={chartData[0]?.upper_bound}
            fill="transparent"
            label={{
              value: `IC ${Math.round(confidence_level * 100)}%`,
              position: 'top',
              fill: '#f97316',
              fontSize: 11,
              fontWeight: 500,
              offset: 10,
            }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

interface PredictionTableProps {
  predictions: PredictionResponse['predictions']
  baseCurrency: string
}

export function PredictionTable({ predictions, baseCurrency }: PredictionTableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 dark:bg-gray-800">
            <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">
              Data
            </th>
            <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">
              Previsão
            </th>
            <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">
              Lim. Inferior
            </th>
            <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">
              Lim. Superior
            </th>
            <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">
              IC
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
          {predictions.map((p) => (
            <tr key={p.day} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
              <td className="px-4 py-3 text-gray-900 dark:text-white">
                {formatDate(p.date, 'dd/MM/yyyy')}
              </td>
              <td className="px-4 py-3 font-mono font-medium text-gray-900 dark:text-white">
                {formatCurrency(p.predicted_rate, baseCurrency, 4)}
              </td>
              <td className="px-4 py-3 font-mono text-gray-600 dark:text-gray-400">
                {formatCurrency(p.lower_bound, baseCurrency, 4)}
              </td>
              <td className="px-4 py-3 font-mono text-gray-600 dark:text-gray-400">
                {formatCurrency(p.upper_bound, baseCurrency, 4)}
              </td>
              <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                {Math.round(p.confidence_level * 100)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface PredictionSummaryProps {
  prediction: PredictionResponse
  currentRate?: number
}

export function PredictionSummary({ prediction, currentRate }: PredictionSummaryProps) {
  const { model, horizon_days, confidence_level, predictions } = prediction
  const firstPred = predictions[0]
  const lastPred = predictions[predictions.length - 1]

  const totalChange = firstPred && lastPred
    ? ((lastPred.predicted_rate - firstPred.predicted_rate) / firstPred.predicted_rate) * 100
    : 0

  const changeFromCurrent = currentRate && firstPred
    ? ((firstPred.predicted_rate - currentRate) / currentRate) * 100
    : 0

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
        <p className="text-sm text-gray-500 dark:text-gray-400">Modelo</p>
        <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">{model}</p>
      </div>
      <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
        <p className="text-sm text-gray-500 dark:text-gray-400">Horizonte</p>
        <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">{horizon_days} dias</p>
      </div>
      <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
        <p className="text-sm text-gray-500 dark:text-gray-400">Confiança</p>
        <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-white">
          {Math.round(confidence_level * 100)}%
        </p>
      </div>

      {currentRate && firstPred && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800 sm:col-span-2">
          <p className="text-sm text-gray-500 dark:text-gray-400">Taxa Atual</p>
          <p className="mt-1 text-2xl font-bold font-mono text-gray-900 dark:text-white">
            {formatCurrency(currentRate, prediction.base, 4)}
          </p>
        </div>
      )}

      {firstPred && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">Previsão Dia 1</p>
          <p className="mt-1 text-2xl font-bold font-mono text-gray-900 dark:text-white">
            {formatCurrency(firstPred.predicted_rate, prediction.base, 4)}
          </p>
        </div>
      )}

      {firstPred && lastPred && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Variação Total Prevista
          </p>
          <p className={cn(
            'mt-1 text-2xl font-bold font-mono',
            totalChange >= 0 ? 'text-success-600' : 'text-danger-600'
          )}>
            {totalChange >= 0 ? '+' : ''}{totalChange.toFixed(2)}%
          </p>
        </div>
      )}

      {changeFromCurrent !== 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">vs Atual (Dia 1)</p>
          <p className={cn(
            'mt-1 text-2xl font-bold font-mono',
            changeFromCurrent >= 0 ? 'text-success-600' : 'text-danger-600'
          )}>
            {changeFromCurrent >= 0 ? '+' : ''}{changeFromCurrent.toFixed(2)}%
          </p>
        </div>
      )}
    </div>
  )
}
