import axios, { type AxiosInstance } from 'axios'

function getBaseURL(): string {
  const host = sessionStorage.getItem('host')
  const port = sessionStorage.getItem('port')
  if (!host && !port) return import.meta.env.VITE_API_BASE_URL || '/api/v1'
  return `http://${host || 'localhost'}:${port || '8080'}/api/v1`
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: getBaseURL(),
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use(
  (config) => {
    // Dynamically resolve baseURL in case sessionStorage was updated after client creation
    config.baseURL = getBaseURL()

    // Add auth token if available
    const token = localStorage.getItem('authToken')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)