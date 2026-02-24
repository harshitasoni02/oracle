import { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Check for existing token
    const token = localStorage.getItem('shizuha_access_token')
    if (token) {
      // Decode token to get user info
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        setUser({
          id: payload.user_id,
          email: payload.email,
          username: payload.username,
          firstName: payload.first_name,
          lastName: payload.last_name,
        })
      } catch (e) {
        console.error('Error decoding token:', e)
        localStorage.removeItem('shizuha_access_token')
        localStorage.removeItem('shizuha_refresh_token')
      }
    }
    setIsLoading(false)
  }, [])

  const login = (accessToken, refreshToken) => {
    localStorage.setItem('shizuha_access_token', accessToken)
    if (refreshToken) {
      localStorage.setItem('shizuha_refresh_token', refreshToken)
    }

    try {
      const payload = JSON.parse(atob(accessToken.split('.')[1]))
      setUser({
        id: payload.user_id,
        email: payload.email,
        username: payload.username,
        firstName: payload.first_name,
        lastName: payload.last_name,
      })
    } catch (e) {
      console.error('Error decoding token:', e)
    }
  }

  const logout = () => {
    localStorage.removeItem('shizuha_access_token')
    localStorage.removeItem('shizuha_refresh_token')
    setUser(null)
    window.location.href = '/id/logout'
  }

  const value = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
