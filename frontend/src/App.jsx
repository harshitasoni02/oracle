import React from 'react'
import { useAuth } from './contexts/AuthContext'
import OraclePage from './pages/OraclePage'

function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth()

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
      <OraclePage />
    </ProtectedRoute>
  )
}
