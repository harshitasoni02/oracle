import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import OraclePage from './pages/OraclePage'
import BacktestingPage from './pages/BacktestingPage'

// Detached mode: standalone deployment with no Shizuha ID login.
const DETACHED = ['1', 'true'].includes(import.meta.env.VITE_DETACHED)

function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (DETACHED) {
    return children
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="text-muted text-sm">Loading...</div>
      </div>
    )
  }

  if (!isAuthenticated) {
    window.location.href = '/id/login?continue=/oracle/'
    return null
  }

  return children
}

export default function App() {
  return (
    <ProtectedRoute>
      <Routes>
        <Route path="/" element={<OraclePage />} />
        <Route path="/backtesting" element={<BacktestingPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ProtectedRoute>
  )
}