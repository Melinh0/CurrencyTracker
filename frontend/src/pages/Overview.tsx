import { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { RefreshCw, ArrowUpRight, ArrowDownRight, Radio } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Select } from '@/components/ui/Select'
import { RateChart, RateChangeChart } from '@/components/charts/RateChart'
import { api, type ExchangeRateLatest, type RateStatistics } from '@/lib/api'
import { formatCurrency, formatPercent, formatRelativeTime, cn } from '@/lib/utils'

const TIME_RANGES = [
  { value: '7', label: '7 dias' },
  { value: '30', label: '30 dias' },
  { value: '90', label: '90 dias' },
  { value: '180', label: '180 dias' },
  { value: '365', label: '1 ano' },
]

const BASE = 'BRL'

export function Overview() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [rates, setRates] = useState<ExchangeRateLatest[]>([])
  const [history, setHistory] = useState<ExchangeRateLatest[]>([])
  const [statistics, setStatistics] = useState<RateStatistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const quote = searchParams.get('quote') || 'USD'
  const range = searchParams.get('range') || '30'

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [ratesData, historyData, statsData] = await Promise.all([
        api.getLatestRates(BASE),
        api.getRatesHistory({
          base: BASE,
          quote,
          start_date: new Date(Date.now() - Number(range) * 24 * 60 * 60 * 1000).toISOString(),
          end_date: new Date().toISOString(),
          limit: 2000,
        }),
        api.getRateStatistics(BASE, quote, Number(range)),
      ])
      setRates(ratesData)
      setHistory(historyData)
      setStatistics(statsData)
      setLastUpdated(new Date())
    } catch (err) {
      setError('Não foi possível carregar as cotações. Verifique se o servidor está ativo.')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [quote, range])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  useEffect(() => {
    const id = setInterval(() => {
      if (document.visibilityState === 'visible') fetchData()
    }, 60000)
    return () => clearInterval(id)
  }, [fetchData])

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await api.collect(BASE)
      await fetchData()
    } catch (e) {
      console.error(e)
      await fetchData()
    } finally {
      setRefreshing(false)
    }
  }

  const quotes = Array.from(new Set(rates.map(r => r.quote)))
  const current = rates.find(r => r.quote === quote) || (rates.length ? rates[0] : null)
  const activeQuote = current?.quote || quote

  const periodChange = history.length >= 2
    ? ((history[history.length - 1].rate - history[0].rate) / history[0].rate) * 100
    : null

  const rangeLabel = TIME_RANGES.find(r => r.value === range)?.label

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Cotações em tempo real</h1>
          <p className="mt-1 flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
            <span className="inline-flex items-center gap-1 text-success-600 dark:text-success-400">
              <Radio className="h-3.5 w-3.5" />
              ao vivo
            </span>
            <span>·</span>
            <span>valores em relação ao Real (BRL)</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={activeQuote}
            onChange={(v) => setSearchParams({ quote: v, range })}
            options={quotes.map(q => ({ value: q, label: q }))}
            placeholder="Moeda"
            className="w-32"
          />
          <Select
            value={range}
            onChange={(v) => setSearchParams({ quote: activeQuote, range: v })}
            options={TIME_RANGES}
            className="w-32"
          />
          <Button variant="primary" onClick={handleRefresh} loading={refreshing}>
            <RefreshCw className={cn('h-4 w-4', refreshing && 'animate-spin')} />
            Atualizar
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-danger-200 bg-danger-50 p-4 text-sm text-danger-600 dark:border-danger-800 dark:bg-danger-900/30 dark:text-danger-400">
          {error}
        </div>
      )}

      {current && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="lg:col-span-1">
            <CardContent className="pt-6">
              <p className="text-sm font-medium text-gray-500 dark:text-gray-400">1 {activeQuote} em BRL</p>
              <p className="mt-1 text-4xl font-bold tracking-tight text-gray-900 dark:text-white">
                {formatCurrency(current.rate, BASE, activeQuote === 'JPY' ? 6 : 4)}
              </p>
              {periodChange !== null && (
                <p className={cn('mt-2 inline-flex items-center gap-1 text-sm font-semibold', periodChange >= 0 ? 'text-success-600 dark:text-success-400' : 'text-danger-600 dark:text-danger-400')}>
                  {periodChange >= 0 ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
                  {formatPercent(periodChange)} <span className="font-normal text-gray-400">em {rangeLabel}</span>
                </p>
              )}
            </CardContent>
          </Card>
          <MiniStat label="Compra (bid)" value={current.bid ? formatCurrency(current.bid, BASE, 4) : '—'} tone="success" />
          <MiniStat label="Venda (ask)" value={current.ask ? formatCurrency(current.ask, BASE, 4) : '—'} tone="danger" />
          <MiniStat label="Spread" value={current.spread != null ? formatPercent(current.spread) : '—'} tone="neutral" />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>{activeQuote}/BRL · {rangeLabel}</span>
              {lastUpdated && <span className="text-xs font-normal text-gray-400">atualizado {formatRelativeTime(lastUpdated)}</span>}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading && history.length === 0 ? (
              <div className="flex h-[360px] items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-primary-600" />
              </div>
            ) : history.length > 1 ? (
              <>
                <RateChart data={history} baseCurrency={BASE} currentRate={current?.rate} height={340} />
                <div className="mt-4 border-t border-gray-100 pt-4 dark:border-gray-700">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wider text-gray-400">Variação diária</p>
                  <RateChangeChart data={history} height={160} />
                </div>
              </>
            ) : (
              <div className="flex h-[360px] items-center justify-center text-sm text-gray-400">
                Sem histórico para {activeQuote}/BRL
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Resumo do período</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {statistics && statistics.count > 0 ? (
              <>
                <Row label="Média" value={formatCurrency(statistics.avg_rate || 0, BASE, 4)} />
                <Row label="Mínima" value={formatCurrency(statistics.min_rate || 0, BASE, 4)} />
                <Row label="Máxima" value={formatCurrency(statistics.max_rate || 0, BASE, 4)} />
                <Row label="Volatilidade" value={formatCurrency(statistics.stddev_rate || 0, BASE, 5)} />
                <Row label="Amostras" value={String(statistics.count)} />
              </>
            ) : (
              <p className="py-6 text-center text-sm text-gray-400">Carregando estatísticas…</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Todas as moedas vs BRL</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-xs uppercase tracking-wider text-gray-400 dark:border-gray-700">
                  <th className="px-3 py-2 text-left">Moeda</th>
                  <th className="px-3 py-2 text-right">Valor (BRL)</th>
                  <th className="px-3 py-2 text-right">Compra</th>
                  <th className="px-3 py-2 text-right">Venda</th>
                  <th className="px-3 py-2 text-right">Spread</th>
                  <th className="px-3 py-2 text-right">Atualizado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {rates.map((r) => (
                  <tr
                    key={r.quote}
                    onClick={() => setSearchParams({ quote: r.quote, range })}
                    className={cn('cursor-pointer transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50', r.quote === activeQuote && 'bg-primary-50/60 dark:bg-primary-900/20')}
                  >
                    <td className="px-3 py-3 font-semibold text-gray-900 dark:text-white">{r.quote}</td>
                    <td className="px-3 py-3 text-right font-mono font-medium text-gray-900 dark:text-white">{formatCurrency(r.rate, BASE, r.quote === 'JPY' ? 6 : 4)}</td>
                    <td className="px-3 py-3 text-right font-mono text-success-600 dark:text-success-400">{r.bid ? formatCurrency(r.bid, BASE, 4) : '—'}</td>
                    <td className="px-3 py-3 text-right font-mono text-danger-600 dark:text-danger-400">{r.ask ? formatCurrency(r.ask, BASE, 4) : '—'}</td>
                    <td className="px-3 py-3 text-right text-gray-500 dark:text-gray-400">{r.spread != null ? formatPercent(r.spread) : '—'}</td>
                    <td className="px-3 py-3 text-right text-xs text-gray-400">{formatRelativeTime(r.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function MiniStat({ label, value, tone }: { label: string; value: string; tone: 'success' | 'danger' | 'neutral' }) {
  const color = tone === 'success' ? 'text-success-600 dark:text-success-400' : tone === 'danger' ? 'text-danger-600 dark:text-danger-400' : 'text-gray-900 dark:text-white'
  return (
    <Card>
      <CardContent className="pt-6">
        <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{label}</p>
        <p className={cn('mt-1 text-2xl font-bold font-mono', color)}>{value}</p>
      </CardContent>
    </Card>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-gray-100 py-2 last:border-0 dark:border-gray-700">
      <span className="text-sm text-gray-500 dark:text-gray-400">{label}</span>
      <span className="font-mono text-sm font-medium text-gray-900 dark:text-white">{value}</span>
    </div>
  )
}
