import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { RefreshCw, Brain, Sparkles, ChevronDown, Download, Calendar } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/Card'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { PredictionChart, PredictionTable, PredictionSummary } from '@/components/charts/PredictionChart'
import { api, type PredictionResponse, type PredictionRequest, type ModelResponse } from '@/lib/api'
import { formatCurrency, formatPercent, formatDate, formatRelativeTime, cn } from '@/lib/utils'

const HORIZONS = [
  { value: 1, label: '1 dia' },
  { value: 3, label: '3 dias' },
  { value: 7, label: '7 dias' },
  { value: 14, label: '14 dias' },
  { value: 30, label: '30 dias' },
]

const MODEL_TYPES = [
  { value: 'auto', label: 'Auto (Melhor)' },
  { value: 'xgboost', label: 'XGBoost' },
  { value: 'lightgbm', label: 'LightGBM' },
  { value: 'random_forest', label: 'Random Forest' },
  { value: 'arima', label: 'ARIMA' },
  { value: 'prophet', label: 'Prophet' },
]

export function Predictions() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [rates, setRates] = useState<{ base: string; quote: string; rate: number }[]>([])
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null)
  const [models, setModels] = useState<ModelResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [predictLoading, setPredictLoading] = useState(false)
  const [trainLoading, setTrainLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'predict' | 'models' | 'train'>('predict')

  const baseCurrency = searchParams.get('base') || 'BRL'
  const quoteCurrency = searchParams.get('quote') || 'USD'
  const horizon = Number(searchParams.get('horizon') || '7')
  const modelName = searchParams.get('model') || 'auto'
  const confidence = Number(searchParams.get('confidence') || '0.95')

  const fetchRates = useCallback(async () => {
    try {
      const ratesData = await api.getLatestRates(baseCurrency)
      setRates(ratesData.map(r => ({ base: r.base, quote: r.quote, rate: r.rate })))
    } catch (err) {
      console.error('Failed to fetch rates:', err)
    }
  }, [baseCurrency])

  const fetchPrediction = useCallback(async () => {
    setPredictLoading(true)
    setError(null)
    try {
      const request: PredictionRequest = {
        base: baseCurrency,
        quote: quoteCurrency,
        horizon_days: horizon,
        model_name: modelName !== 'auto' ? modelName : undefined,
        confidence_level: confidence,
      }
      const result = await api.getPrediction(request)
      setPrediction(result)
    } catch (err) {
      setError('Erro ao gerar previsão. Verifique se existe modelo treinado para este par.')
      console.error(err)
    } finally {
      setPredictLoading(false)
    }
  }, [baseCurrency, quoteCurrency, horizon, modelName, confidence])

  const fetchModels = useCallback(async () => {
    try {
      const modelsData = await api.getModels(quoteCurrency)
      setModels(modelsData)
    } catch (err) {
      console.error('Failed to fetch models:', err)
    }
  }, [quoteCurrency])

  const handleTrain = async () => {
    setTrainLoading(true)
    setError(null)
    try {
      const result = await api.trainModels({
        target_currency: quoteCurrency,
        base_currency: baseCurrency,
        model_types: ['xgboost', 'lightgbm', 'random_forest'],
        prediction_horizon: horizon,
        lookback_days: 365,
        test_size: 0.2,
        min_training_samples: 100,
      })
      alert(`Treinamento concluído! Melhor modelo: ${result.best_model}`)
      fetchModels()
    } catch (err) {
      setError('Erro ao treinar modelos.')
      console.error(err)
    } finally {
      setTrainLoading(false)
    }
  }

  useEffect(() => {
    fetchRates()
    fetchModels()
  }, [fetchRates, fetchModels])

  useEffect(() => {
    if (activeTab === 'predict') {
      fetchPrediction()
    }
  }, [fetchPrediction, activeTab])

  const handleBaseChange = (value: string) => {
    setSearchParams({ ...Object.fromEntries(searchParams), base: value, quote: value === 'BRL' ? 'USD' : 'BRL' })
  }

  const handleQuoteChange = (value: string) => {
    setSearchParams({ ...Object.fromEntries(searchParams), quote: value })
  }

  const handleHorizonChange = (value: string) => {
    setSearchParams({ ...Object.fromEntries(searchParams), horizon: value })
  }

  const handleModelChange = (value: string) => {
    setSearchParams({ ...Object.fromEntries(searchParams), model: value })
  }

  const handleConfidenceChange = (value: string) => {
    setSearchParams({ ...Object.fromEntries(searchParams), confidence: value })
  }

  const currentPair = rates.find(r => r.quote === quoteCurrency)

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Previsões de Câmbio</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Modelos de Machine Learning para previsão de taxas
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={baseCurrency}
            onChange={handleBaseChange}
            options={rates.map(r => ({ value: r.base, label: r.base }))}
            className="w-36"
          />
          <span className="text-gray-400">/</span>
          <Select
            value={quoteCurrency}
            onChange={handleQuoteChange}
            options={rates.filter(r => r.quote !== baseCurrency).map(r => ({ value: r.quote, label: r.quote }))}
            className="w-36"
          />
          <Select
            value={String(horizon)}
            onChange={handleHorizonChange}
            options={HORIZONS.map(h => ({ value: String(h.value), label: h.label }))}
            className="w-28"
          />
          <Select
            value={modelName}
            onChange={handleModelChange}
            options={MODEL_TYPES}
            className="w-40"
          />
          <Select
            value={String(confidence)}
            onChange={handleConfidenceChange}
            options={[
              { value: '0.90', label: '90%' },
              { value: '0.95', label: '95%' },
              { value: '0.99', label: '99%' },
            ]}
            className="w-24"
          />
          <Button
            variant={activeTab === 'predict' ? 'primary' : 'secondary'}
            onClick={() => setActiveTab('predict')}
            disabled={predictLoading}
          >
            <Sparkles className="h-4 w-4" />
            Prever
          </Button>
          <Button
            variant={activeTab === 'models' ? 'primary' : 'secondary'}
            onClick={() => setActiveTab('models')}
          >
            <Brain className="h-4 w-4" />
            Modelos
          </Button>
          <Button
            variant={activeTab === 'train' ? 'primary' : 'secondary'}
            onClick={() => setActiveTab('train')}
            disabled={trainLoading}
          >
            Treinar
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-danger-200 bg-danger-50 p-4 dark:border-danger-800 dark:bg-danger-900/30">
          <p className="text-danger-600 dark:text-danger-400">{error}</p>
        </div>
      )}

      {activeTab === 'predict' && (
        <div className="space-y-6">
          {prediction && (
            <>
              <PredictionSummary prediction={prediction} currentRate={currentPair?.rate} />
              <Card>
                <CardHeader>
                  <CardTitle>
                    Previsão {baseCurrency}/{quoteCurrency} - {HORIZONS.find(h => h.value === horizon)?.label}
                    <span className="ml-2 text-sm font-normal text-gray-500 dark:text-gray-400">
                      Modelo: {prediction.model} | IC {Math.round(prediction.confidence_level * 100)}%
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <PredictionChart
                    prediction={prediction}
                    baseCurrency={baseCurrency}
                    currentRate={currentPair?.rate}
                  />
                  <div className="mt-6">
                    <PredictionTable
                      predictions={prediction.predictions}
                      baseCurrency={baseCurrency}
                    />
                  </div>
                </CardContent>
                <CardFooter className="flex justify-end gap-2">
                  <Button variant="secondary" size="sm">
                    <Download className="h-4 w-4" />
                    Exportar CSV
                  </Button>
                  <Button variant="primary" size="sm" onClick={fetchPrediction} loading={predictLoading}>
                    <RefreshCw className="h-4 w-4" />
                    Atualizar
                  </Button>
                </CardFooter>
              </Card>
            </>
          )}

          {!prediction && !predictLoading && (
            <Card>
              <CardContent className="py-12 text-center">
                <Brain className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">Nenhuma previsão disponível</h3>
                <p className="mt-1 text-gray-500 dark:text-gray-400">
                  Clique em "Prever" para gerar uma previsão para {baseCurrency}/{quoteCurrency}
                </p>
                <Button className="mt-4" onClick={fetchPrediction} loading={predictLoading}>
                  <Sparkles className="h-4 w-4" />
                  Gerar Previsão
                </Button>
              </CardContent>
            </Card>
          )}

          {predictLoading && (
            <Card>
              <CardContent className="py-12 text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto mb-4" />
                <p className="text-gray-500 dark:text-gray-400">Gerando previsão...</p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {activeTab === 'models' && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Modelos Disponíveis para {quoteCurrency}</CardTitle>
            </CardHeader>
            <CardContent>
              {models.length > 0 ? (
                <div className="space-y-4">
                  {models.map((model) => (
                    <div
                      key={model.uuid}
                      className="rounded-lg border border-gray-200 p-4 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800/50"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-gray-900 dark:text-white">{model.name}</span>
                            <Badge variant={model.is_production ? 'success' : model.is_active ? 'info' : 'outline'}>
                              {model.is_production ? 'Produção' : model.is_active ? 'Ativo' : 'Inativo'}
                            </Badge>
                            <Badge variant="outline">v{model.version}</Badge>
                          </div>
                          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                            Tipo: {model.model_type} • Treinado: {formatDate(model.trained_at, 'dd/MM/yyyy')}
                          </p>
                        </div>
                        <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                          <div className="flex items-center gap-1">
                            <span>MAE Treino:</span>
                            <span className="font-mono font-medium">{model.train_mae?.toFixed(6) || 'N/A'}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <span>RMSE Treino:</span>
                            <span className="font-mono font-medium">{model.train_rmse?.toFixed(6) || 'N/A'}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <span>MAE Val:</span>
                            <span className="font-mono font-medium">{model.val_mae?.toFixed(6) || 'N/A'}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <span>RMSE Val:</span>
                            <span className="font-mono font-medium">{model.val_rmse?.toFixed(6) || 'N/A'}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-8 text-center">
                  <Brain className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 dark:text-white">Nenhum modelo treinado</h3>
                  <p className="mt-1 text-gray-500 dark:text-gray-400">
                    Treine um modelo na aba "Treinar" para começar
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'train' && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Treinar Novos Modelos</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Moeda Base
                  </label>
                  <Select
                    value={baseCurrency}
                    onChange={handleBaseChange}
                    options={rates.map(r => ({ value: r.base, label: r.base }))}
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Moeda Alvo
                  </label>
                  <Select
                    value={quoteCurrency}
                    onChange={handleQuoteChange}
                    options={rates.filter(r => r.quote !== baseCurrency).map(r => ({ value: r.quote, label: r.quote }))}
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Horizonte de Previsão
                  </label>
                  <Select
                    value={String(horizon)}
                    onChange={handleHorizonChange}
                    options={HORIZONS.map(h => ({ value: String(h.value), label: h.label }))}
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Janela de Treino
                  </label>
                  <Select
                    value="365"
                    options={[
                      { value: '180', label: '6 meses' },
                      { value: '365', label: '1 ano' },
                      { value: '730', label: '2 anos' },
                      { value: '1095', label: '3 anos' },
                    ]}
                    className="w-full"
                  />
                </div>
              </div>

              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/50">
                <h4 className="font-medium text-gray-900 dark:text-white mb-2">Modelos a serem treinados</h4>
                <div className="flex flex-wrap gap-2">
                  {[
                    { id: 'xgboost', name: 'XGBoost', desc: 'Gradient Boosting - Rápido e preciso' },
                    { id: 'lightgbm', name: 'LightGBM', desc: 'Gradient Boosting otimizado' },
                    { id: 'random_forest', name: 'Random Forest', desc: 'Ensemble de árvores - Robusto' },
                    { id: 'arima', name: 'ARIMA', desc: 'Modelo estatístico para séries temporais' },
                    { id: 'prophet', name: 'Prophet', desc: 'Decomposição de tendências e sazonalidade' },
                  ].map(model => (
                    <label key={model.id} className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-800">
                      <input type="checkbox" className="rounded border-gray-300 text-primary-600" defaultChecked />
                      <div>
                        <span className="font-medium">{model.name}</span>
                        <p className="text-xs text-gray-500">{model.desc}</p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              <Button
                variant="primary"
                size="lg"
                onClick={handleTrain}
                loading={trainLoading}
                className="w-full sm:w-auto"
              >
                <Brain className="h-5 w-5" />
                Iniciar Treinamento
              </Button>

              <p className="text-sm text-gray-500 dark:text-gray-400 text-center">
                O treinamento pode levar alguns minutos. Os melhores modelos serão salvos automaticamente.
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
