import { apiClient } from '../client'
import type {
  PublicUrlResponse,
  UpdatePublicUrlRequest,
  ManagedResponse,
  ProxyStatusResponse,
  DiagnosticsResponse,
  UpdateDiagnosticsRequest,
  BenchmarksModeResponse,
  UpdateBenchmarksModeRequest,
} from '../types'

export const settingsApi = {
  // Get current public URL
  getPublicUrl: async (): Promise<PublicUrlResponse> => {
    const response = await apiClient.get('/settings/public-url')
    return response.data
  },

  // Whether a station manages this space (plus its assigned public URL)
  getManaged: async (): Promise<ManagedResponse> => {
    const response = await apiClient.get('/settings/managed')
    return response.data
  },

  // Update public URL
  updatePublicUrl: async (data: UpdatePublicUrlRequest): Promise<PublicUrlResponse> => {
    const response = await apiClient.patch('/settings/public-url', data)
    return response.data
  },

  // Get proxy status
  getProxyStatus: async (): Promise<ProxyStatusResponse> => {
    const response = await apiClient.get('/settings/proxy')
    return response.data
  },

  // Configure proxy (fetches tunnel credentials from SyftHub automatically)
  configureProxy: async (): Promise<ProxyStatusResponse> => {
    const response = await apiClient.post('/settings/proxy')
    return response.data
  },

  // Disconnect proxy
  disconnectProxy: async (): Promise<ProxyStatusResponse> => {
    const response = await apiClient.delete('/settings/proxy')
    return response.data
  },

  // Get diagnostics preference
  getDiagnostics: async (): Promise<DiagnosticsResponse> => {
    const response = await apiClient.get('/settings/diagnostics')
    return response.data
  },

  // Update diagnostics preference
  updateDiagnostics: async (data: UpdateDiagnosticsRequest): Promise<DiagnosticsResponse> => {
    const response = await apiClient.patch('/settings/diagnostics', data)
    return response.data
  },

  // How this Space accepts benchmark cards: 'off' or 'local'
  getBenchmarksMode: async (): Promise<BenchmarksModeResponse> => {
    const response = await apiClient.get('/settings/benchmarks')
    return response.data
  },

  // Change it. Turning it off closes the door on new cards; it does not
  // retract what was published while it was open — that stays a separate,
  // owner-only act.
  updateBenchmarksMode: async (
    data: UpdateBenchmarksModeRequest,
  ): Promise<BenchmarksModeResponse> => {
    const response = await apiClient.patch('/settings/benchmarks', data)
    return response.data
  },
}
