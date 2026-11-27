import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { RefreshCw, ChevronDown, ArrowUp, ArrowDown, Minus } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { ComparisonChart } from '@/components/charts/RateChart'
import { api, type ExchangeRateLatest } from '@/lib/api'
import { formatCurrency, formatPercent, formatRelativeTime, cn } from '@/lib/utils'

const TIME_RANGES = [
  { value: '7', label: '7 dias' },
  { value: '30', label: '30 dias' },
  { value: '90', label: '90 dias' },
  { value: '180', label: '180 dias' },
  { value: '365', label: '1 ano' },
]

export function Comparison() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [rates, setRates] = useState<ExchangeRateLatest[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const baseCurrency = searchParams.get('base') || 'BRL'
  const timeRange = searchParams.get('range') || '30'

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const ratesData = await api.getLatestRates(baseCurrency)
      setRates(ratesData)
      setLastUpdated(new Date())
    } catch (err) {
      setError('Erro ao carregar taxas. Verifique sua conexão.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [baseCurrency])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const [changes, setChanges] = useState<Map<string, number>>(new Map())
  const [historyLoading, setHistoryLoading] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!rates.length) return

    const fetchHistory = async () => {
      const newChanges = new Map<string, number>()
      const loadingSet = new Set<string>()

      rates.forEach(rate => {
        if (rate.quote === baseCurrency) return
        loadingSet.add(rate.quote)
      })
      setHistoryLoading(loadingSet)

      await Promise.all(
        rates
          .filter(r => r.quote !== baseCurrency)
          .map(async (rate) => {
            try {
              const history = await api.getRatesHistory({
                base: baseCurrency,
                quote: rate.quote,
                start_date: new Date(Date.now() - Number(timeRange) * 24 * 60 * 60 * 1000).toISOString(),
                end_date: new Date().toISOString(),
                limit: 1000,
              })

              if (history.length >= 2) {
                const first = history[0].rate
                const last = history[history.length - 1].rate
                const pct = ((last - first) / first) * 100
                newChanges.set(rate.quote, pct)
              } else {
                newChanges.set(rate.quote, 0)
              }
            } catch {
              newChanges.set(rate.quote, 0)
            } finally {
              loadingSet.delete(rate.quote)
              setHistoryLoading(new Set(loadingSet))
            }
          })
      )
      setChanges(newChanges)
    }

    fetchHistory()
  }, [rates, baseCurrency, timeRange])

  const handleRefresh = () => {
    fetchData()
  }

  const handleBaseChange = (value: string) => {
    setSearchParams({ ...Object.fromEntries(searchParams), base: value })
  }

  const handleRangeChange = (value: string) => {
    setSearchParams({ ...Object.fromEntries(searchParams), range: value })
  }

  const comparisonData = rates
    .filter(r => r.quote !== baseCurrency)
    .map(rate => ({
      quote: rate.quote,
      rate: rate.rate,
      change_pct: changes.get(rate.quote) || 0,
      current: rate.rate,
    }))
    .sort((a, b) => b.change_pct - a.change_pct)

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Comparação de Moedas</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Performance relativa vs {baseCurrency} nos últimos {TIME_RANGES.find(r => r.value === timeRange)?.label}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={baseCurrency}
            onChange={handleBaseChange}
            options={rates.map(r => ({ value: r.base, label: r.base }))}
            placeholder="Moeda Base"
            className="w-36"
          />
          <Select
            value={timeRange}
            onChange={handleRangeChange}
            options={TIME_RANGES}
            className="w-32"
          />
          <Button variant="secondary" size="sm" onClick={handleRefresh} loading={loading}>
            <RefreshCw className="h-4 w-4" />
            Atualizar
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
          <CardTitle>Variação Percentual vs {baseCurrency}</CardTitle>
        </CardHeader>
        <CardContent>
          {comparisonData.length > 0 ? (
            <ComparisonChart
              data={comparisonData}
              baseCurrency={baseCurrency}
              height={Math.max(400, comparisonData.length * 35)}
            />
          ) : (
            <div className="h-64 flex items-center justify-center text-gray-500 dark:text-gray-400">
              Nenhuma moeda para comparar
            </div>
          )}
        </CardContent>
      </Card>

      
      <Card>
        <CardHeader>
          <CardTitle>Detalhes das Taxas</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Moeda</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Taxa Atual</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Compra</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Venda</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Spread</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">
                    <span className="flex items-center gap-1">
                      Var. {TIME_RANGES.find(r => r.value === timeRange)?.label}
                      {historyLoading.size > 0 && (
                        <span className="animate-spin h-4 w-4 border-b-2 border-primary-600 rounded-full" />
                      )}
                    </span>
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Fonte</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider dark:text-gray-400">Atualizado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {comparisonData.map((data) => {
                  const rate = rates.find(r => r.quote === data.quote)
                  const change = changes.get(data.quote) || 0
                  const isLoading = historyLoading.has(data.quote)

                  return (
                    <tr key={data.quote} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{data.quote}</td>
                      <td className="px-4 py-3 font-mono text-gray-900 dark:text-white">{formatCurrency(data.rate, baseCurrency, 4)}</td>
                      <td className="px-4 py-3 font-mono text-success-600 dark:text-success-400">{rate?.bid ? formatCurrency(rate.bid, baseCurrency, 4) : '—'}</td>
                      <td className="px-4 py-3 font-mono text-danger-600 dark:text-danger-400">{rate?.ask ? formatCurrency(rate.ask, baseCurrency, 4) : '—'}</td>
                      <td className="px-4 py-3">
                        {rate?.spread ? (
                          <Badge variant={rate.spread > 1 ? 'warning' : 'success'}>{formatPercent(rate.spread)}</Badge>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {isLoading ? (
                          <div className="h-4 w-16 animate-pulse bg-gray-200 rounded dark:bg-gray-700" />
                        ) : (
                          <span className={cn(
                            'font-mono font-medium',
                            change > 0 ? 'text-success-600 dark:text-success-400' :
                            change < 0 ? 'text-danger-600 dark:text-danger-400' :
                            'text-gray-500 dark:text-gray-400'
                          )}>
                            {change > 0 && <ArrowUp className="inline h-3.5 w-3.5" />}
                            {change < 0 && <ArrowDown className="inline h-3.5 w-3.5" />}
                            {change === 0 && !isLoading && <Minus className="inline h-3.5 w-3.5" />}
                            {isLoading ? '...' : formatPercent(change)}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{rate?.source}</td>
                      <td className="px-4 py-3 text-gray-500 dark:text-gray-400">{rate ? formatRelativeTime(rate.timestamp) : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: 'Melhor Performance', value: comparisonData[0]?.quote || '—', change: comparisonData[0]?.change_pct },
          { label: 'Pior Performance', value: comparisonData[comparisonData.length - 1]?.quote || '—', change: comparisonData[comparisonData.length - 1]?.change_pct },
          { label: 'Moedas Positivas', value: String(comparisonData.filter(d => d.change_pct > 0).length) },
          { label: 'Moedas Negativas', value: String(comparisonData.filter(d => d.change_pct < 0).length) },
        ].map((stat, i) => (
          <Card key={i}>
            <CardContent className="py-4">
              <p className="text-sm text-gray-500 dark:text-gray-400">{stat.label}</p>
              <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">{stat.value}</p>
              {stat.change !== undefined && (
                <p className={cn(
                  'mt-1 text-sm font-mono',
                  stat.change > 0 ? 'text-success-600' :
                  stat.change < 0 ? 'text-danger-600' :
                  'text-gray-500'
                )}>
                  {stat.change > 0 ? '+' : ''}{stat.change.toFixed(2)}%
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
