# CurrencyTracker - Monitor de Moedas e Previsão de Câmbio

Sistema completo para monitoramento em tempo real de taxas de câmbio, armazenamento em série temporal e previsão de valores futuros usando modelos de regressão.

## Funcionalidades

- **Coleta em Tempo Real**: Bots coletam taxas de câmbio de múltiplas fontes (APIs públicas, websockets)
- **Moedas Monitoradas**: USD, EUR, GBP, JPY, RUB, ARS, CLP, COP, MXN, CNY, INR, ZAR, AUD, CAD, CHF vs BRL
- **Armazenamento Temporal**: Banco de dados timeseries (InfluxDB/TimescaleDB) para histórico completo
- **Análise e Visualização**: Dashboard com gráficos de variações, correlações e tendências
- **Machine Learning**: Modelos de regressão (ARIMA, LSTM, Prophet, XGBoost) para previsão
- **Alertas**: Notificações para variações significativas ou oportunidades de arbitragem
- **API REST**: Endpoints para integração com outros sistemas

## Arquitetura

```
currency-tracker/
├── collector/          # Bots de coleta de dados
│   ├── sources/       # Implementações por fonte (APIs, WebSocket, Scraping)
│   ├── scheduler.py   # Agendamento de coletas
│   └── validator.py   # Validação e limpeza de dados
├── storage/           # Camada de persistência
│   ├── models.py      # Modelos de dados (SQLAlchemy/InfluxDB)
│   ├── repository.py  # Operações CRUD
│   └── migrations/    # Migrações de banco
├── ml/                # Machine Learning
│   ├── features/      # Engenharia de features
│   ├── models/        # Modelos de regressão
│   ├── training/      # Pipeline de treino
│   └── prediction/    # Serviço de predição
├── api/               # API REST (FastAPI)
│   ├── routes/        # Endpoints
│   ├── schemas/       # Pydantic schemas
│   └── dependencies.py
├── dashboard/         # Frontend (Streamlit/React)
│   ├── components/    # Componentes reutilizáveis
│   ├── pages/         # Páginas da aplicação
│   └── utils/         # Utilitários de visualização
├── alerts/            # Sistema de alertas
│   ├── rules/         # Regras de alerta
│   ├── notifiers/     # Email, Telegram, Discord, Webhook
│   └── scheduler.py
├── config/            # Configurações
│   ├── settings.py    # Configurações centrais
│   └── currencies.yaml # Lista de moedas monitoradas
├── tests/             # Testes unitários e integração
├── scripts/           # Scripts utilitários
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── pyproject.toml
└── .env.example
```

## Instalação Rápida

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/CurrencyTracker.git
cd CurrencyTracker

# Configure variáveis de ambiente
cp .env.example .env
# Edite .env com suas chaves de API

# Suba com Docker
docker-compose up -d

# Ou instale localmente
pip install -r requirements.txt
python -m collector.scheduler
```

## Configuração de Moedas

Edite `config/currencies.yaml` para adicionar/remover moedas:

```yaml
base_currency: "BRL"
tracked_currencies:
  - code: "USD"
    name: "Dólar Americano"
    symbol: "$"
    priority: "high"
  - code: "EUR"
    name: "Euro"
    symbol: "€"
    priority: "high"
  # ... mais moedas
```

## Fontes de Dados Suportadas

- **AwesomeAPI** (Grátis, Brasil) - Taxas comerciais e turismo
- **ExchangeRate-API** - 160+ moedas, plano gratuito
- **Alpha Vantage** - Dados históricos e tempo real
- **Twelve Data** - WebSocket para tempo real
- **Banco Central do Brasil (BCB)** - Taxas oficiais (PTAX)
- **Yahoo Finance** - Via yfinance library
- **Investing.com** - Scraping para moedas exóticas

## Modelos de ML Disponíveis

| Modelo | Tipo | Horizonte | Melhor Para |
|--------|------|-----------|-------------|
| ARIMA/SARIMA | Estatístico | Curto/Médio | Séries sazonais |
| Prophet | Decomposição | Médio/Longo | Tendências + feriados |
| LSTM/GRU | Deep Learning | Curto/Médio | Padrões não-lineares |
| XGBoost/LightGBM | Gradient Boosting | Curto | Features engenheiradas |
| Transformer | Attention | Médio/Longo | Dependências longas |
| Ensemble | Combinação | Todos | Robustez máxima |

## API Endpoints Principais

```
GET  /api/v1/rates/latest          # Últimas taxas
GET  /api/v1/rates/history         # Histórico com filtros
GET  /api/v1/rates/statistics      # Estatísticas (volatilidade, correlação)
GET  /api/v1/predictions/{currency} # Previsão para moeda
POST /api/v1/predictions/train     # Treinar novo modelo
GET  /api/v1/alerts                # Alertas ativos
POST /api/v1/alerts                # Criar alerta
WS   /ws/rates                     # Stream tempo real
```

## Dashboard

Acesse `http://localhost:8501` (Streamlit) ou `http://localhost:3000` (React) para:
- Gráficos de candlestick/linha interativos
- Heatmap de correlação entre moedas
- Comparativo de performance vs BRL
- Backtesting de modelos
- Configuração de alertas

## Variáveis de Ambiente

```env
# Banco de Dados
DATABASE_URL=postgresql://user:pass@localhost:5432/currency_tracker
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your-token
INFLUXDB_ORG=your-org
INFLUXDB_BUCKET=currency_data

# APIs Externas
AWESOME_API_KEY=
EXCHANGE_RATE_API_KEY=
ALPHA_VANTAGE_API_KEY=
TWELVE_DATA_API_KEY=
YAHOO_FINANCE_ENABLED=true

# ML
MLFLOW_TRACKING_URI=http://localhost:5000
MODEL_REGISTRY_URI=./models

# Alertas
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
EMAIL_SMTP_HOST=
EMAIL_SMTP_PORT=
EMAIL_USER=
EMAIL_PASSWORD=

# App
SECRET_KEY=your-secret-key
DEBUG=false
LOG_LEVEL=INFO
```

## Contribuição

1. Fork o projeto
2. Crie branch feature (`git checkout -b feature/nova-funcionalidade`)
3. Commit mudanças (`git commit -m 'Add nova funcionalidade'`)
4. Push (`git push origin feature/nova-funcionalidade`)
5. Abra Pull Request

## Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

## Roadmap

- [ ] Coleta via WebSocket (tempo real verdadeiro)
- [ ] Suporte a criptomoedas
- [ ] Arbitragem triangular automática
- [ ] Integração com corretoras (Clear, XP, Rico)
- [ ] App mobile (React Native)
- [ ] Modelo de ensemble automatizado (AutoML)
- [ ] Explicabilidade (SHAP values para predições)