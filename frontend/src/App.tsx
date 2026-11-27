import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { Overview } from '@/pages/Overview'
import { Comparison } from '@/pages/Comparison'
import { Predictions } from '@/pages/Predictions'
import { Correlation } from '@/pages/Correlation'
import { Alerts } from '@/pages/Alerts'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/comparison" element={<Comparison />} />
        <Route path="/predictions" element={<Predictions />} />
        <Route path="/correlation" element={<Correlation />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/settings" element={<div>Configurações - Em breve</div>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}

export default App
