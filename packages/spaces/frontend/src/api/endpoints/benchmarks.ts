/** The Space's benchmark routes: connections, providers, per-endpoint setup, runs and reports. */
import { apiClient } from '../client'
import type {
  AddressLocality,
  BenchmarkConnection,
  BenchmarkConnectionRequest,
  BenchmarkFilterOutcome,
  BenchmarkFilterPage,
  BenchmarkFilterStage,
  BenchmarkGeneratedPage,
  BenchmarkJob,
  BenchmarkModelCatalog,
  BenchmarkPair,
  BenchmarkRunPair,
  BenchmarkRunPairs,
  BenchmarkPairStatus,
  BenchmarkQuestionDetail,
  BenchmarkQuestionPage,
  BenchmarkQuestionQuery,
  BenchmarkReportFragment,
  BenchmarkResult,
  BenchmarkResultPage,
  BenchmarkRunList,
  BenchmarkRunReport,
  BenchmarkRunRequest,
  BenchmarkTarget,
  BenchmarkTargetRequest,
  BenchmarkVerdict,
  BenchmarkWindow,
  BenchmarkWritingPage,
  ProviderKeyState,
  ProviderResponse,
  ProviderUrls,
} from '../types'

function reportPath(slug: string, jobId?: string): string {
  const base = `/benchmarks/endpoints/${slug}/report/runs`
  return jobId ? `${base}/${jobId}` : base
}

/** The file name from a `Content-Disposition` header, if it carries one. */
export function dispositionFileName(header: unknown): string | null {
  if (typeof header !== 'string') return null
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header)
  if (star?.[1]) return decodeURIComponent(star[1])
  const plain = /filename="?([^";]+)"?/i.exec(header)
  return plain?.[1] ?? null
}

export const benchmarksApi = {
  // --- connections ---------------------------------------------------------

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

  checkConnection: async (id: string): Promise<BenchmarkConnection> => {
    const response = await apiClient.post(`/benchmarks/connections/${id}/check`)
    return response.data
  },

  disconnect: async (id: string): Promise<void> => {
    await apiClient.delete(`/benchmarks/connections/${id}`)
  },

  /** Whether an address stays on this machine or its Docker network. */
  locality: async (url: string): Promise<AddressLocality> => {
    const response = await apiClient.get('/benchmarks/locality', { params: { url } })
    return response.data
  },

  // --- the model providers ---------------------------------------------------

  getProvider: async (connectionId: string): Promise<ProviderResponse> => {
    const response = await apiClient.get(`/benchmarks/connections/${connectionId}/provider`)
    return response.data
  },

  saveProvider: async (connectionId: string, urls: ProviderUrls): Promise<ProviderResponse> => {
    const response = await apiClient.put(`/benchmarks/connections/${connectionId}/provider`, urls)
    return response.data
  },

  saveProviderCredential: async (
    connectionId: string,
    name: string,
    value: string,
  ): Promise<ProviderKeyState> => {
    const response = await apiClient.put(
      `/benchmarks/connections/${connectionId}/provider/credentials/${name}`,
      { value },
    )
    return response.data
  },

  deleteProviderCredential: async (
    connectionId: string,
    name: string,
  ): Promise<ProviderKeyState> => {
    const response = await apiClient.delete(
      `/benchmarks/connections/${connectionId}/provider/credentials/${name}`,
    )
    return response.data
  },

  // --- the model catalogue ---------------------------------------------------

  // The whole catalogue; the picker filters it locally.
  listModels: async (connectionId: string): Promise<BenchmarkModelCatalog> => {
    const response = await apiClient.get(`/benchmarks/connections/${connectionId}/models`)
    return response.data
  },

  // Asks the benchmark to fetch its provider's model list again.
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

  // Articles in the time window; `days` overrides the saved window.
  getWindow: async (slug: string, days?: number): Promise<BenchmarkWindow> => {
    const response = await apiClient.get(`/benchmarks/endpoints/${slug}/window`, {
      params: days === undefined ? undefined : { days },
    })
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

  // --- questions, answers, verdicts -------------------------------------------

  updatePairStatus: async (
    slug: string,
    pairId: string,
    status: BenchmarkPairStatus,
    note = '',
  ): Promise<BenchmarkPair> => {
    const response = await apiClient.patch(
      `/benchmarks/endpoints/${slug}/console/pairs/${pairId}`,
      { status, note },
    )
    return response.data
  },

  listResults: async (
    slug: string,
    filters: {
      verdict?: string
      qa_id?: string
      /** One model's answers. */
      model?: string
      /** One job's answers, each marked whether its figures count it (`counted`). */
      job?: string
      limit?: number
      offset?: number
      /** Include prompts and retrieved chunks; heavy, so use with `qa_id`. */
      prompts?: boolean
    },
  ): Promise<BenchmarkResultPage> => {
    const response = await apiClient.get(`/benchmarks/endpoints/${slug}/console/results`, {
      params: filters,
    })
    return response.data
  },

  overrideVerdict: async (
    slug: string,
    resultId: string,
    verdict: BenchmarkVerdict,
    reasoning = '',
  ): Promise<BenchmarkResult> => {
    const response = await apiClient.post(
      `/benchmarks/endpoints/${slug}/console/results/${resultId}/verdict`,
      { verdict, reasoning },
    )
    return response.data
  },

  /** Remove a manual verdict; the judges' verdict applies again. */
  withdrawVerdict: async (slug: string, resultId: string): Promise<void> => {
    await apiClient.delete(`/benchmarks/endpoints/${slug}/console/results/${resultId}/verdict`)
  },

  // --- run reports -----------------------------------------------------------

  listReportRuns: async (
    slug: string,
    params: {
      from?: string
      to?: string
      limit?: number
      offset?: number
    } = {},
  ): Promise<BenchmarkRunList> => {
    const response = await apiClient.get(reportPath(slug), { params })
    return response.data
  },

  getRunReport: async (slug: string, jobId: string): Promise<BenchmarkRunReport> => {
    const response = await apiClient.get(reportPath(slug, jobId))
    return response.data
  },

  /** Questions a job wrote, with how each kind's generation went. */
  getRunGenerated: async (
    slug: string,
    jobId: string,
    params: { generator?: string; status?: string; limit?: number; offset?: number } = {},
  ): Promise<BenchmarkGeneratedPage> => {
    const response = await apiClient.get(`${reportPath(slug, jobId)}/generated`, { params })
    return response.data
  },

  /** Questions of the target by id (at most 200), whichever job wrote them. */
  getRunPairs: async (
    slug: string,
    jobId: string,
    ids: readonly string[],
  ): Promise<BenchmarkRunPairs> => {
    const response = await apiClient.get(`${reportPath(slug, jobId)}/pairs`, {
      params: { ids: ids.join(',') },
    })
    return response.data
  },

  /** One question of a run, with its writing and filter records and the calls behind it. */
  getRunPair: async (slug: string, jobId: string, qaId: string): Promise<BenchmarkRunPair> => {
    const response = await apiClient.get(`${reportPath(slug, jobId)}/pairs/${qaId}`)
    return response.data
  },

  /** A job's writer calls, with the drafts each dropped. */
  getRunWriting: async (
    slug: string,
    jobId: string,
    params: { generator?: string; limit?: number; offset?: number } = {},
  ): Promise<BenchmarkWritingPage> => {
    const response = await apiClient.get(`${reportPath(slug, jobId)}/writing`, { params })
    return response.data
  },

  /** A job's filter decisions, newest first. */
  listRunFilter: async (
    slug: string,
    jobId: string,
    params: {
      generator?: string
      stage?: BenchmarkFilterStage
      outcome?: BenchmarkFilterOutcome
      limit?: number
      offset?: number
    } = {},
  ): Promise<BenchmarkFilterPage> => {
    const response = await apiClient.get(`${reportPath(slug, jobId)}/filter`, { params })
    return response.data
  },

  listRunQuestions: async (
    slug: string,
    jobId: string,
    params: BenchmarkQuestionQuery,
  ): Promise<BenchmarkQuestionPage> => {
    const response = await apiClient.get(`${reportPath(slug, jobId)}/questions`, { params })
    return response.data
  },

  getRunQuestion: async (
    slug: string,
    jobId: string,
    qaId: string,
    model: string,
  ): Promise<BenchmarkQuestionDetail> => {
    const response = await apiClient.get(`${reportPath(slug, jobId)}/questions/${qaId}`, {
      params: { model },
    })
    return response.data
  },

  listQuestionFragments: async (
    slug: string,
    jobId: string,
    qaId: string,
    model: string,
  ): Promise<BenchmarkReportFragment[]> => {
    const response = await apiClient.get(`${reportPath(slug, jobId)}/questions/${qaId}/fragments`, {
      params: { model },
    })
    return response.data
  },

  // Fetched as a blob: the route needs the bearer token, which a plain link cannot carry.
  downloadRunSummary: async (
    slug: string,
    jobId: string,
  ): Promise<{ blob: Blob; fileName: string | null }> => {
    const response = await apiClient.get(`${reportPath(slug, jobId)}/summary.docx`, {
      responseType: 'blob',
    })
    return {
      blob: response.data,
      fileName: dispositionFileName(response.headers?.['content-disposition']),
    }
  },

  /** Everything that took part in a run, one sheet per part. */
  downloadRunExport: async (
    slug: string,
    jobId: string,
  ): Promise<{ blob: Blob; fileName: string | null }> => {
    const response = await apiClient.get(`${reportPath(slug, jobId)}/export.xlsx`, {
      responseType: 'blob',
    })
    return {
      blob: response.data,
      fileName: dispositionFileName(response.headers?.['content-disposition']),
    }
  },

  /** Deletes a finished run and its answers; questions are kept. */
  deleteRun: async (slug: string, jobId: string): Promise<void> => {
    await apiClient.delete(reportPath(slug, jobId))
  },
}
