import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { RefreshCw, ChevronDown, Link2, ArrowUp, ArrowDown, Minus } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { SimpleCorrelationHeatmap } from '@/components/charts/CorrelationHeatmap'
import { ComparisonChart } from '@/components/charts/RateChart'
import { api, type ExchangeRateLatest, type RateStatistics } from '@/lib/api'
import { formatCurrency, formatPercent, formatRelativeTime, cn } from '@/lib/utils'

const TIME_RANGES = [
  { value: '7', label: '7 dias' },
  { value: '30', label: '30 dias' },
  { value: '90', label: '90 dias' },
  { value: '180', label: '180 dias' },
  { value: '365', label: '1 ano' },
]

interface CorrelationData {
  x: string
  y: string
  value: number
}

export function Correlation() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [rates, setRates] = useState<ExchangeRateLatest[]>([])
  const [correlationData, setCorrelationData] = useState<CorrelationData[]>([])
  const [usdCorrelation, setUsdCorrelation] = useState<{ quote: string; value: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [corrLoading, setCorrLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const baseCurrency = searchParams.get('base') || 'BRL'
  const timeRange = searchParams.get('range') || '30'

  const fetchRates = useCallback(async () => {
    try {
      const ratesData = await api.getLatestRates(baseCurrency)
      setRates(ratesData)
    } catch (err) {
      console.error('Failed to fetch rates:', err)
    }
  }, [baseCurrency])

  const fetchCorrelation = useCallback(async () => {
    if (!rates.length) return

    setCorrLoading(true)
    setError(null)

    try {
      const quotes = rates.map(r => r.quote).filter(q => q !== baseCurrency)
      if (quotes.length < 2) return

      const historyPromises = quotes.map(async (quote) => {
        try {
          const history = await api.getRatesHistory({
            base: baseCurrency,
            quote,
            start_date: new Date(Date.now() - Number(timeRange) * 24 * 60 * 60 * 1000).toISOString(),
            end_date: new Date().toISOString(),
            limit: 1000,
          })
          return { quote, history }
        } catch {
          return { quote, history: [] }
        }
      })

      const results = await Promise.all(historyPromises)

      const alignedData: Record<string, number[]> = {}
      const allTimestamps = new Set<string>()

      results.forEach(({ quote, history }) => {
        history.forEach(h => {
          allTimestamps.add(h.timestamp)
          if (!alignedData[quote]) alignedData[quote] = []
        })
      })

      const timestamps = Array.from(allTimestamps).sort()
      const minLength = Math.min(...results.map(r => r.history.length))

      if (minLength < 10) {
        setError('Dados insuficientes para calcular correlação (mínimo 10 pontos)')
        return
      }

      const rateArrays: Record<string, number[]> = {}
      results.forEach(({ quote, history }) => {
        const sorted = [...history].sort((a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        )
        rateArrays[quote] = sorted.slice(-minLength).map(h => h.rate)
      })

      const corrMatrix: CorrelationData[] = []
      quotes.forEach((x, i) => {
        quotes.forEach((y, j) => {
          if (i <= j) {
            const corr = calculateCorrelation(rateArrays[x], rateArrays[y])
            corrMatrix.push({ x, y, value: corr })
            if (i !== j) {
              corrMatrix.push({ x: y, y: x, value: corr })
            }
          }
        })
      })

      setCorrelationData(corrMatrix)

      if (quotes.includes('USD')) {
        const usdCorr = quotes
          .filter(q => q !== 'USD')
          .map(q => ({
            quote: q,
            value: calculateCorrelation(rateArrays['USD'], rateArrays[q]),
          }))
          .sort((a, b) => b.value - a.value)
        setUsdCorrelation(usdCorr)
      }

    } catch (err) {
      setError('Erro ao calcular correlação')
      console.error(err)
    } finally {
      setCorrLoading(false)
    }
  }, [rates, baseCurrency, timeRange])

  useEffect(() => {
    fetchRates()
  }, [fetchRates])

  useEffect(() => {
    if (rates.length) {
      fetchCorrelation()
    }
  }, [fetchCorrelation])

  const handleRefresh = () => {
    fetchCorrelation()
  }

  const handleBaseChange = (value: string) => {
    setSearchParams({ ...Object.fromEntries(searchParams), base: value })
  }

  const handleRangeChange = (value: string) => {
    setSearchParams({ ...Object.fromEntries(searchParams), range: value })
  }

  const currencies = rates.map(r => r.quote).filter(q => q !== baseCurrency)

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Correlação entre Moedas</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Matriz de correlação vs {baseCurrency} ({TIME_RANGES.find(r => r.value === timeRange)?.label})
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={baseCurrency}
            onChange={handleBaseChange}
            options={rates.map(r => ({ value: r.base, label: r.base }))}
            className="w-36"
          />
          <Select
            value={timeRange}
            onChange={handleRangeChange}
            options={TIME_RANGES}
            className="w-32"
          />
          <Button variant="secondary" size="sm" onClick={handleRefresh} loading={corrLoading}>
            <RefreshCw className="h-4 w-4" />
            Recalcular
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-danger-200 bg-danger-50 p-4 dark:border-danger-800 dark:bg-danger-900/30">
          <p className="text-danger-600 dark:text-danger-400">{error}</p>
        </div>
      )}

      
      <Card>
        <CardHeader>
          <CardTitle>Matriz de Correlação</CardTitle>
        </CardHeader>
        <CardContent>
          {currencies.length >= 2 ? (
            corrLoading ? (
              <div className="h-[500px] flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
              </div>
            ) : (
              <SimpleCorrelationHeatmap
                data={correlationData}
                currencies={currencies}
                height={500}
              />
            )
          ) : (
            <div className="h-[300px] flex items-center justify-center text-gray-500 dark:text-gray-400">
              Necessário pelo menos 2 moedas para correlação
            </div>
          )}
        </CardContent>
      </Card>

      
      {usdCorrelation.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Correlação com USD</CardTitle>
          </CardHeader>
          <CardContent>
            <ComparisonChart
              data={usdCorrelation.map(d => ({
                quote: d.quote,
                rate: 0,
                change_pct: d.value * 100,
                current: 0,
              }))}
              baseCurrency="Correlação"
              height={Math.max(300, usdCorrelation.length * 35)}
            />
          </CardContent>
        </Card>
      )}

      
      {correlationData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Pares Mais Correlacionados</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Par</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Correlação</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Força</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                  {correlationData
                    .filter(d => d.x < d.y)
                    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
                    .slice(0, 20)
                    .map((pair, i) => (
                      <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="px-4 py-2 font-medium text-gray-900 dark:text-white">
                          {pair.x}/{pair.y}
                        </td>
                        <td className="px-4 py-2 font-mono text-gray-900 dark:text-white">
                          {pair.value.toFixed(3)}
                        </td>
                        <td className="px-4 py-2">
                          <Badge
                            variant={
                              Math.abs(pair.value) > 0.7 ? 'danger' :
                              Math.abs(pair.value) > 0.5 ? 'warning' :
                              Math.abs(pair.value) > 0.3 ? 'info' :
                              'success'
                            }
                          >
                            {Math.abs(pair.value) > 0.7 ? 'Muito Forte' :
                             Math.abs(pair.value) > 0.5 ? 'Forte' :
                             Math.abs(pair.value) > 0.3 ? 'Moderada' : 'Fraca'}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      
      <Card variant="bordered">
        <CardContent className="py-4">
          <h4 className="font-medium text-gray-900 dark:text-white mb-2">Como interpretar a correlação</h4>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-success-500" />
              <span className="text-gray-600 dark:text-gray-400">0.7 a 1.0: Correlação positiva forte</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-warning-500" />
              <span className="text-gray-600 dark:text-gray-400">0.3 a 0.7: Correlação moderada</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-gray-300 dark:bg-gray-600" />
              <span className="text-gray-600 dark:text-gray-400">-0.3 a 0.3: Correlação fraca/inexistente</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded bg-danger-500" />
              <span className="text-gray-600 dark:text-gray-400">-1.0 a -0.7: Correlação negativa forte</span>
            </div>
          </div>
          <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
            Correlação positiva: moedas movem na mesma direção. Negativa: movem em direções opostas.
            Valores próximos a 1 ou -1 indicam relação forte. Use para diversificação de risco.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

function calculateCorrelation(x: number[], y: number[]): number {
  if (x.length !== y.length || x.length === 0) return 0

  const n = x.length
  const sumX = x.reduce((a, b) => a + b, 0)
  const sumY = y.reduce((a, b) => a + b, 0)
  const sumXY = x.reduce((sum, xi, i) => sum + xi * y[i], 0)
  const sumX2 = x.reduce((sum, xi) => sum + xi * xi, 0)
  const sumY2 = y.reduce((sum, yi) => sum + yi * yi, 0)

  const numerator = n * sumXY - sumX * sumY
  const denominator = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY))

  if (denominator === 0) return 0

  return numerator / denominator
}
