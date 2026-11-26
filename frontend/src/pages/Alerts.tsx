import { useState, useEffect, useCallback } from 'react'
import { Plus, Bell, BellOff, Edit, Trash2, Mail, MessageSquare, Send, Globe } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/Card'
import { Select } from '@/components/ui/Select'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { api, type AlertResponse, type AlertCreateRequest } from '@/lib/api'
import { formatCurrency, formatRelativeTime, cn } from '@/lib/utils'

const CONDITION_TYPES = [
  { value: 'above', label: 'Acima de' },
  { value: 'below', label: 'Abaixo de' },
  { value: 'change_pct', label: 'Variação %' },
  { value: 'volatility', label: 'Volatilidade' },
]

const PRIORITIES = [
  { value: 'low', label: 'Baixa' },
  { value: 'medium', label: 'Média' },
  { value: 'high', label: 'Alta' },
  { value: 'critical', label: 'Crítica' },
]

const NOTIFICATION_CHANNELS = [
  { id: 'telegram', icon: Send, label: 'Telegram' },
  { id: 'discord', icon: MessageSquare, label: 'Discord' },
  { id: 'email', icon: Mail, label: 'Email' },
  { id: 'webhook', icon: Globe, label: 'Webhook' },
]

export function Alerts() {
  const [alerts, setAlerts] = useState<AlertResponse[]>([])
  const [rates, setRates] = useState<{ base: string; quote: string; rate: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<number | null>(null)
  const [deleting, setDeleting] = useState<number | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [editingAlert, setEditingAlert] = useState<AlertResponse | null>(null)
  const [formData, setFormData] = useState<Partial<AlertCreateRequest>>({
    name: '',
    base_currency: 'BRL',
    quote_currency: 'USD',
    condition_type: 'above',
    threshold_value: 5.5,
    check_interval_seconds: 60,
    cooldown_seconds: 3600,
    priority: 'medium',
    notify_telegram: false,
    notify_discord: false,
    notify_email: false,
    notify_webhook: false,
    webhook_url: '',
  })

  const fetchAlerts = useCallback(async () => {
    try {
      const data = await api.getAlerts()
      setAlerts(data)
    } catch (err) {
      console.error('Failed to fetch alerts:', err)
    }
  }, [])

  const fetchRates = useCallback(async () => {
    try {
      const ratesData = await api.getLatestRates('BRL')
      setRates(ratesData.map(r => ({ base: r.base, quote: r.quote, rate: r.rate })))
    } catch (err) {
      console.error('Failed to fetch rates:', err)
    }
  }, [])

  useEffect(() => {
    fetchAlerts()
    fetchRates()
  }, [fetchAlerts, fetchRates])

  const openCreateModal = () => {
    setEditingAlert(null)
    setFormData({
      name: '',
      base_currency: 'BRL',
      quote_currency: 'USD',
      condition_type: 'above',
      threshold_value: 5.5,
      check_interval_seconds: 60,
      cooldown_seconds: 3600,
      priority: 'medium',
      notify_telegram: false,
      notify_discord: false,
      notify_email: false,
      notify_webhook: false,
      webhook_url: '',
    })
    setShowModal(true)
  }

  const openEditModal = (alert: AlertResponse) => {
    setEditingAlert(alert)
    setFormData({
      name: alert.name,
      description: alert.description,
      base_currency: alert.base_currency,
      quote_currency: alert.quote_currency,
      condition_type: alert.condition_type,
      threshold_value: Number(alert.threshold_value),
      check_interval_seconds: alert.check_interval_seconds,
      cooldown_seconds: alert.cooldown_seconds,
      priority: alert.priority,
      notify_telegram: alert.notify_telegram,
      notify_discord: alert.notify_discord,
      notify_email: alert.notify_email,
      notify_webhook: alert.notify_webhook,
      webhook_url: alert.webhook_url,
    })
    setShowModal(true)
  }

  const closeModal = () => {
    setShowModal(false)
    setEditingAlert(null)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const id = editingAlert?.id
    setSaving(id || 'new')

    try {
      if (id) {
        await api.updateAlert(id, formData)
      } else {
        await api.createAlert(formData as AlertCreateRequest)
      }
      fetchAlerts()
      closeModal()
    } catch (err) {
      alert('Erro ao salvar alerta')
      console.error(err)
    } finally {
      setSaving(null)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Tem certeza que deseja excluir este alerta?')) return

    setDeleting(id)
    try {
      await api.deleteAlert(id)
      fetchAlerts()
    } catch (err) {
      alert('Erro ao excluir alerta')
      console.error(err)
    } finally {
      setDeleting(null)
    }
  }

  const handleInputChange = (field: string, value: unknown) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  const getCurrentRate = (base: string, quote: string) => {
    return rates.find(r => r.base === base && r.quote === quote)?.rate
  }

  const isAlertTriggered = (alert: AlertResponse) => {
    const currentRate = getCurrentRate(alert.base_currency, alert.quote_currency)
    if (!currentRate) return false

    const threshold = Number(alert.threshold_value)

    switch (alert.condition_type) {
      case 'above':
        return currentRate > threshold
      case 'below':
        return currentRate < threshold
      case 'change_pct':

        return false
      case 'volatility':
        return false
      default:
        return false
    }
  }

  const getConditionLabel = (type: string) => {
    return CONDITION_TYPES.find(c => c.value === type)?.label || type
  }

  const getPriorityBadge = (priority: string) => {
    const variants: Record<string, 'default' | 'success' | 'danger' | 'warning' | 'info'> = {
      low: 'default',
      medium: 'info',
      high: 'warning',
      critical: 'danger',
    }
    return variants[priority] || 'default'
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Alertas</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Configure notificações para movimentos de câmbio
          </p>
        </div>
        <Button onClick={openCreateModal}>
          <Plus className="h-4 w-4" />
          Novo Alerta
        </Button>
      </div>

      
      <Card>
        <CardHeader>
          <CardTitle>Alertas Ativos ({alerts.filter(a => a.is_active).length})</CardTitle>
        </CardHeader>
        <CardContent>
          {alerts.length === 0 ? (
            <div className="py-12 text-center">
              <Bell className="h-12 w-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">Nenhum alerta configurado</h3>
              <p className="mt-1 text-gray-500 dark:text-gray-400">
                Clique em "Novo Alerta" para criar seu primeiro alerta
              </p>
              <Button className="mt-4" onClick={openCreateModal}>
                <Plus className="h-4 w-4" />
                Criar Alerta
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {alerts.map(alert => {
                const triggered = isAlertTriggered(alert)
                const currentRate = getCurrentRate(alert.base_currency, alert.quote_currency)

                return (
                  <div
                    key={alert.id}
                    className={cn(
                      'rounded-lg border p-4 transition-colors',
                      alert.is_active
                        ? 'border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800'
                        : 'border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/50'
                    )}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                      <div className="flex items-center gap-4">
                        <div className={cn(
                          'p-2 rounded-lg',
                          triggered ? 'bg-danger-50 dark:bg-danger-900/30' : 'bg-primary-50 dark:bg-primary-900/30'
                        )}>
                          {triggered ? (
                            <Bell className="h-5 w-5 text-danger-600 dark:text-danger-400" />
                          ) : (
                            <BellOff className="h-5 w-5 text-primary-600 dark:text-primary-400" />
                          )}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="font-semibold text-gray-900 dark:text-white">{alert.name}</h4>
                            <Badge variant={triggered ? 'danger' : getPriorityBadge(alert.priority)}>
                              {triggered ? 'DISPARADO' : alert.priority}
                            </Badge>
                            <Badge variant={alert.is_active ? 'success' : 'default'}>
                              {alert.is_active ? 'Ativo' : 'Inativo'}
                            </Badge>
                          </div>
                          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                            {alert.base_currency}/{alert.quote_currency} •{' '}
                            {getConditionLabel(alert.condition_type)} {formatCurrency(alert.threshold_value, alert.base_currency, 4)}
                            {currentRate && (
                              <> • Atual: {formatCurrency(currentRate, alert.base_currency, 4)}</>
                            )}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                          {alert.notify_telegram && <Send className="h-3.5 w-3.5" />}
                          {alert.notify_discord && <MessageSquare className="h-3.5 w-3.5" />}
                          {alert.notify_email && <Mail className="h-3.5 w-3.5" />}
                          {alert.notify_webhook && <Globe className="h-3.5 w-3.5" />}
                        </div>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {alert.last_triggered
                            ? `Disparado: ${formatRelativeTime(alert.last_triggered)}`
                            : 'Nunca disparado'}
                        </span>
                        <Button variant="ghost" size="sm" onClick={() => openEditModal(alert)} disabled={saving === alert.id}>
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => handleDelete(alert.id)} disabled={deleting === alert.id}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl bg-white shadow-xl dark:bg-gray-800">
            <form onSubmit={handleSubmit}>
              <CardHeader className="border-b border-gray-200 dark:border-gray-700">
                <CardTitle>
                  {editingAlert ? 'Editar Alerta' : 'Criar Novo Alerta'}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6 p-6">
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input
                    label="Nome do Alerta"
                    value={formData.name || ''}
                    onChange={e => handleInputChange('name', e.target.value)}
                    placeholder="Ex: USD acima de 5.50"
                    required
                  />
                  <Select
                    label="Moeda Base"
                    value={formData.base_currency || 'BRL'}
                    onChange={e => handleInputChange('base_currency', e.target.value)}
                    options={rates.map(r => ({ value: r.base, label: r.base }))}
                  />
                  <Select
                    label="Moeda Cotação"
                    value={formData.quote_currency || 'USD'}
                    onChange={e => handleInputChange('quote_currency', e.target.value)}
                    options={rates.filter(r => r.quote !== formData.base_currency).map(r => ({ value: r.quote, label: r.quote }))}
                  />
                  <Select
                    label="Condição"
                    value={formData.condition_type || 'above'}
                    onChange={e => handleInputChange('condition_type', e.target.value)}
                    options={CONDITION_TYPES}
                  />
                  <Input
                    label="Valor Limite"
                    type="number"
                    step="0.0001"
                    value={formData.threshold_value || 0}
                    onChange={e => handleInputChange('threshold_value', Number(e.target.value))}
                    required
                  />
                  <Select
                    label="Prioridade"
                    value={formData.priority || 'medium'}
                    onChange={e => handleInputChange('priority', e.target.value)}
                    options={PRIORITIES}
                  />
                  <Input
                    label="Intervalo de Verificação (seg)"
                    type="number"
                    value={formData.check_interval_seconds || 60}
                    onChange={e => handleInputChange('check_interval_seconds', Number(e.target.value))}
                  />
                  <Input
                    label="Cooldown (seg)"
                    type="number"
                    value={formData.cooldown_seconds || 3600}
                    onChange={e => handleInputChange('cooldown_seconds', Number(e.target.value))}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Canais de Notificação
                  </label>
                  <div className="flex flex-wrap gap-3">
                    {NOTIFICATION_CHANNELS.map(channel => (
                      <label
                        key={channel.id}
                        className={cn(
                          'inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm cursor-pointer transition-colors',
                          formData[`notify_${channel.id}` as keyof typeof formData]
                            ? 'border-primary-500 bg-primary-50 text-primary-700 dark:border-primary-500 dark:bg-primary-900/30 dark:text-primary-300'
                            : 'border-gray-300 hover:bg-gray-50 dark:border-gray-600 dark:hover:bg-gray-800/50'
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={!!formData[`notify_${channel.id}` as keyof typeof formData]}
                          onChange={e => handleInputChange(`notify_${channel.id}`, e.target.checked)}
                          className="rounded border-gray-300 text-primary-600"
                        />
                        <channel.icon className="h-4 w-4" />
                        {channel.label}
                      </label>
                    ))}
                  </div>
                </div>

                {formData.notify_webhook && (
                  <Input
                    label="Webhook URL"
                    value={formData.webhook_url || ''}
                    onChange={e => handleInputChange('webhook_url', e.target.value)}
                    placeholder="https://seu-webhook.com/endpoint"
                  />
                )}

                <Input
                  label="Descrição (opcional)"
                  value={formData.description || ''}
                  onChange={e => handleInputChange('description', e.target.value)}
                  placeholder="Descrição do alerta..."
                  className="mt-4"
                />
              </CardContent>
              <CardFooter className="border-t border-gray-200 dark:border-gray-700 justify-end">
                <Button type="button" variant="secondary" onClick={closeModal}>
                  Cancelar
                </Button>
                <Button type="submit" loading={saving === (editingAlert?.id || 'new')}>
                  {editingAlert ? 'Salvar Alterações' : 'Criar Alerta'}
                </Button>
              </CardFooter>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
