import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { HomePage } from '@/pages/HomePage'
import { ConversationPage } from '@/pages/ConversationPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { TicketsPage } from '@/pages/TicketsPage'
import { SettingsPage } from '@/pages/SettingsPage'

export function AppRouter() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/conversation" element={<ConversationPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/tickets" element={<TicketsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}