import { apiClient } from '../client'
import type {
  BenchmarkCheck,
  BenchmarkConnection,
  BenchmarkConnectionRequest,
  BenchmarkJob,
  BenchmarkModelCatalog,
  BenchmarkRunRequest,
  BenchmarkSettingsRequest,
  BenchmarkTarget,
  BenchmarkTargetRequest,
} from '../types'

export const benchmarksApi = {
  // --- connections ---------------------------------------------------------

  // Benchmarks this Space is wired to. An empty list is the shipped state.
  listConnections: async (): Promise<BenchmarkConnection[]> => {
    const response = await apiClient.get('/benchmarks/connections')
    return response.data
  },

  connect: async (data: BenchmarkConnectionRequest): Promise<BenchmarkConnection> => {
    const response = await apiClient.post('/benchmarks/connections', data)
    return response.data
  },

  updateConnection: async (
    id: string,
    data: BenchmarkConnectionRequest,
  ): Promise<BenchmarkConnection> => {
    const response = await apiClient.put(`/benchmarks/connections/${id}`, data)
    return response.data
  },

  // Whole, not patched: the form shows the settings as one document, and with
  // a patch a cleared field would be indistinguishable from one not sent.
  saveSettings: async (
    id: string,
    data: BenchmarkSettingsRequest,
  ): Promise<BenchmarkConnection> => {
    const response = await apiClient.put(`/benchmarks/connections/${id}/settings`, data)
    return response.data
  },

  checkConnection: async (id: string): Promise<BenchmarkConnection> => {
    const response = await apiClient.post(`/benchmarks/connections/${id}/check`)
    return response.data
  },

  disconnect: async (id: string): Promise<void> => {
    await apiClient.delete(`/benchmarks/connections/${id}`)
  },

  // --- the model catalogue ---------------------------------------------------

  // The models this benchmark can be pointed at. Asked for whole and filtered
  // here: the list is a few hundred entries that change only on a refresh, and
  // a request per keystroke would put latency into the one control this whole
  // feature exists to make pleasant.
  listModels: async (connectionId: string): Promise<BenchmarkModelCatalog> => {
    const response = await apiClient.get(`/benchmarks/connections/${connectionId}/models`)
    return response.data
  },

  // An explicit action: on the benchmark's side this is a call outside its
  // perimeter, and a benchmark that forbids it says so with the host to open.
  refreshModels: async (connectionId: string): Promise<BenchmarkModelCatalog> => {
    const response = await apiClient.post(`/benchmarks/connections/${connectionId}/models/refresh`)
    return response.data
  },

  // --- per endpoint --------------------------------------------------------

  getTarget: async (slug: string): Promise<BenchmarkTarget> => {
    const response = await apiClient.get(`/benchmarks/endpoints/${slug}`)
    return response.data
  },

  saveTarget: async (slug: string, data: BenchmarkTargetRequest): Promise<BenchmarkTarget> => {
    const response = await apiClient.put(`/benchmarks/endpoints/${slug}`, data)
    return response.data
  },

  stopMeasuring: async (slug: string): Promise<void> => {
    await apiClient.delete(`/benchmarks/endpoints/${slug}`)
  },

  checkTarget: async (slug: string): Promise<BenchmarkCheck> => {
    const response = await apiClient.post(`/benchmarks/endpoints/${slug}/check`)
    return response.data
  },

  startRun: async (slug: string, data: BenchmarkRunRequest): Promise<BenchmarkJob> => {
    const response = await apiClient.post(`/benchmarks/endpoints/${slug}/runs`, data)
    return response.data
  },

  listJobs: async (slug: string): Promise<BenchmarkJob[]> => {
    const response = await apiClient.get(`/benchmarks/endpoints/${slug}/jobs`)
    return response.data
  },

  cancelRun: async (slug: string, jobId: string): Promise<BenchmarkJob> => {
    const response = await apiClient.post(`/benchmarks/endpoints/${slug}/jobs/${jobId}/cancel`)
    return response.data
  },

  deleteJob: async (slug: string, jobId: string): Promise<void> => {
    await apiClient.delete(`/benchmarks/endpoints/${slug}/jobs/${jobId}`)
  },
}
