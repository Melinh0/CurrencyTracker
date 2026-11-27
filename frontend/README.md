# CurrencyTracker Frontend

Interface web responsiva e PWA (Progressive Web App) para o CurrencyTracker, construída com React 18, TypeScript, Vite e Tailwind CSS.

## Características

- **Responsivo**: Funciona perfeitamente em desktop, tablet e mobile
- **PWA**: Instalável como app nativo, funciona offline
- **Tema Escuro/Claro**: Alternância automática ou manual
- **Tempo Real**: Atualização automática de dados
- **Gráficos Interativos**: Recharts com tooltips e zoom
- **TypeScript**: Tipagem forte para maior confiabilidade

## Tecnologias

- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS (styling)
- Recharts (gráficos)
- React Router v6 (roteamento)
- Axios (HTTP client)
- Lucide React (ícones)

## Instalação

```bash
cd frontend
npm install
```

## Desenvolvimento

```bash
npm run dev
```

Acesse em `http://localhost:3000`

O proxy do Vite encaminha `/api` para `http://localhost:8000/api/v1`

## Build para Produção

```bash
npm run build
```

Os arquivos serão gerados em `dist/`

## Preview do Build

```bash
npm run preview
```

## Estrutura do Projeto

```
frontend/
├── public/
│   ├── manifest.json      # PWA manifest
│   ├── sw.js              # Service Worker
│   └── favicon.svg
├── src/
│   ├── components/
│   │   ├── ui/            # Componentes base (Button, Card, Input, etc)
│   │   ├── charts/        # Componentes de gráficos
│   │   └── layout/        # Header, Layout
│   ├── pages/             # Páginas da aplicação
│   ├── lib/
│   │   ├── api.ts         # Cliente API + tipos
│   │   └── utils.ts       # Utilitários
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── postcss.config.js
```

## Páginas

1. **Visão Geral** (`/`) - Taxas atuais, gráficos de histórico, estatísticas
2. **Comparação** (`/comparison`) - Performance relativa entre moedas
3. **Previsões** (`/predictions`) - Previsões de ML, treinamento de modelos
4. **Correlação** (`/correlation`) - Matriz de correlação heatmap
5. **Alertas** (`/alerts`) - Gerenciamento de alertas de câmbio

## Variáveis de Ambiente

Crie `.env` na raiz do frontend:

```env
VITE_API_URL=http://localhost:8000/api/v1
```

## Service Worker

O SW implementa:
- Cache-first para assets estáticos
- Stale-while-revalidate para API
- Suporte offline básico
- Background sync (preparado)

## Responsividade

Breakpoints Tailwind:
- `sm`: 640px+
- `md`: 768px+
- `lg`: 1024px+
- `xl`: 1280px+

Layout adaptativo:
- Sidebar colapsa em mobile
- Tabelas com scroll horizontal
- Gráficos redimensionam automaticamente
- Touch-friendly (botões maiores, espaçamento adequado)

## Acessibilidade

- Semantic HTML
- ARIA labels
- Focus visible
- Contraste WCAG AA
- Navegação por teclado

## Testes

```bash
npm run test
```

## Linting

```bash
npm run lint
```

## Docker

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

## Contribuindo

1. Siga o guia de estilo (ESLint + Prettier)
2. Componentes em PascalCase
3. Hooks customizados com prefixo `use`
4. Tipos TypeScript explícitos
5. Testes para nova funcionalidade

## Licença

MIT