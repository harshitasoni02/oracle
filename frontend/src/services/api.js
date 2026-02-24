import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const client = axios.create({
  baseURL: API_BASE,
  timeout: 30_000,
})

// Request interceptor to add auth token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('shizuha_access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor to handle 401 and token refresh
client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      const refreshToken = localStorage.getItem('shizuha_refresh_token')
      if (refreshToken) {
        try {
          const response = await axios.post('/id/api/auth/refresh/', {
            refresh: refreshToken,
          })
          const { access } = response.data
          localStorage.setItem('shizuha_access_token', access)
          originalRequest.headers.Authorization = `Bearer ${access}`
          return client(originalRequest)
        } catch (refreshError) {
          // Refresh failed - redirect to login
          localStorage.removeItem('shizuha_access_token')
          localStorage.removeItem('shizuha_refresh_token')
          window.location.href = '/id/login?continue=/oracle/'
          return Promise.reject(refreshError)
        }
      } else {
        window.location.href = '/id/login?continue=/oracle/'
      }
    }
    return Promise.reject(error)
  }
)

export const api = {
  getPrice: (metal) => client.get(`/price/${metal}/`).then(r => r.data),
  getHistorical: (metal, timeframe) =>
    client.get(`/historical/${metal}/`, { params: { timeframe } }).then(r => r.data),
  getIndicators: (metal, timeframe) =>
    client.get(`/indicators/${metal}/`, { params: { timeframe } }).then(r => r.data),
  getPredictions: (metal) => client.get(`/predictions/${metal}/`).then(r => r.data),
  triggerRefresh: () => client.post('/refresh/').then(r => r.data),
  getSentiment: (metal) => client.get(`/sentiment/${metal}/`).then(r => r.data),
}
