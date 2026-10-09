import {
  computed,
  getCurrentScope,
  onScopeDispose,
  reactive,
  ref,
  shallowRef,
  toValue,
  watch,
  type MaybeRefOrGetter,
} from 'vue'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { apiErrorDetail } from '@/lib/errors'
import type {
  BenchmarkQuestionDetail,
  BenchmarkQuestionPage,
  BenchmarkQuestionQuery,
  BenchmarkReportFragment,
  BenchmarkRunList,
  BenchmarkRunProgress,
  BenchmarkRunReport,
  BenchmarkRunStatusFilter,
  BenchmarkRunSummary,
  BenchmarkTarget,
  QualityMarketplaceResult,
} from '@/api/types'

/** Same cadence as useBenchmarkJobs. */
export const POLL_MS = 5000
/** Finished runs per page of the runs list. */
export const RUNS_PAGE = 25

export interface RunsFilters {
  /** `YYYY-MM-DD`, or empty. */
  from: string
  to: string
  status: BenchmarkRunStatusFilter
}

export interface PublishOutcome {
  /** Marketplaces that did not accept the change. */
  refused: QualityMarketplaceResult[]
}

/** Hand a blob to the browser as a download. */
export function saveBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = fileName
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

/** Download a run's Excel export. */
export async function saveRunExport(slug: string, jobId: string): Promise<void> {
  const { blob, fileName } = await benchmarksApi.downloadRunExport(slug, jobId)
  saveBlob(blob, fileName ?? `${slug}-run-${jobId}.xlsx`)
}

/**
 * Data for the Benchmark results pages of one endpoint, all served aggregated:
 * the runs list (paged, filtered, polled while any job is queued or running),
 * one run's report, its questions page by page, and the owner's actions.
 */
export function useRunReport(slug: MaybeRefOrGetter<string>) {
  const inProgress = ref<BenchmarkRunProgress[]>([])
  const runs = ref<BenchmarkRunSummary[]>([])
  const total = ref(0)
  const filters = reactive<RunsFilters>({ from: '', to: '', status: 'all' })
  const page = ref(0)
  const target = shallowRef<BenchmarkTarget | null>(null)
  const loading = ref(false)
  /** The runs list has been fetched at least once for this slug. */
  const loaded = ref(false)
  const error = ref<string | null>(null)
  /** Bumped whenever cached run data is dropped; open views refetch on change. */
  const revision = ref(0)

  const filtered = computed(() => Boolean(filters.from || filters.to || filters.status !== 'all'))

  const reportCache = new Map<string, Promise<BenchmarkRunReport>>()
  const detailCache = new Map<string, Promise<BenchmarkQuestionDetail>>()
  const fragmentCache = new Map<string, Promise<BenchmarkReportFragment[]>>()

  function invalidate(jobId?: string): void {
    if (jobId) {
      reportCache.delete(jobId)
      for (const key of detailCache.keys()) if (key.startsWith(`${jobId}|`)) detailCache.delete(key)
    } else {
      reportCache.clear()
      detailCache.clear()
      fragmentCache.clear()
    }
    revision.value += 1
  }

  let listRequest = 0

  async function fetchList(): Promise<BenchmarkRunList | null> {
    const request = ++listRequest
    const list = await benchmarksApi.listReportRuns(toValue(slug), {
      from: filters.from || undefined,
      to: filters.to || undefined,
      status: filters.status === 'all' ? undefined : filters.status,
      limit: RUNS_PAGE,
      offset: page.value * RUNS_PAGE,
    })
    return request === listRequest ? list : null
  }

  function apply(list: BenchmarkRunList): void {
    const finished = inProgress.value
      .map((p) => p.job_id)
      .filter((id) => !list.in_progress.some((p) => p.job_id === id))
    inProgress.value = list.in_progress
    runs.value = list.items
    total.value = list.total
    loaded.value = true
    finished.forEach((id) => invalidate(id))
    if (page.value > 0 && page.value * RUNS_PAGE >= list.total) {
      page.value = Math.max(Math.ceil(list.total / RUNS_PAGE) - 1, 0)
    }
  }

  async function refresh(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const list = await fetchList()
      if (list) apply(list)
    } catch (e) {
      error.value = apiErrorDetail(e, 'Could not load benchmark runs')
    } finally {
      loading.value = false
    }
  }

  /** Refetch the list without a loading state; failures keep what is shown. */
  async function poll(): Promise<void> {
    try {
      const list = await fetchList()
      if (list) apply(list)
    } catch {
      // Keep the rows already shown.
    }
  }

  let timer: ReturnType<typeof setInterval> | undefined
  function stopPolling(): void {
    if (timer) clearInterval(timer)
    timer = undefined
  }
  watch(
    () => inProgress.value.length > 0,
    (on) => {
      if (on && !timer) timer = setInterval(poll, POLL_MS)
      else if (!on) stopPolling()
    },
    { immediate: true },
  )
  if (getCurrentScope()) onScopeDispose(stopPolling)

  watch(
    () => [filters.from, filters.to, filters.status],
    () => {
      if (page.value !== 0) page.value = 0
      else void refresh()
    },
  )
  watch(page, () => void refresh())

  watch(
    () => toValue(slug),
    (s) => {
      invalidate()
      loaded.value = false
      void refresh()
      benchmarksApi
        .getTarget(s)
        .then((t) => (target.value = t))
        .catch(() => (target.value = null))
    },
    { immediate: true },
  )

  function isRunning(jobId: string): boolean {
    return inProgress.value.some((p) => p.job_id === jobId)
  }

  function cached<T>(cache: Map<string, Promise<T>>, key: string, load: () => Promise<T>) {
    const hit = cache.get(key)
    if (hit) return hit
    const promise = load()
    promise.catch(() => cache.delete(key))
    cache.set(key, promise)
    return promise
  }

  /** One run's figures; cached until an action on it invalidates them. */
  function loadReport(jobId: string): Promise<BenchmarkRunReport> {
    return cached(reportCache, jobId, () => benchmarksApi.getRunReport(toValue(slug), jobId))
  }

  /** One page of a run's questions for one model. */
  function loadQuestions(
    jobId: string,
    query: BenchmarkQuestionQuery,
  ): Promise<BenchmarkQuestionPage> {
    return benchmarksApi.listRunQuestions(toValue(slug), jobId, query)
  }

  function loadQuestion(
    jobId: string,
    qaId: string,
    model: string,
  ): Promise<BenchmarkQuestionDetail> {
    return cached(detailCache, `${jobId}|${qaId}|${model}`, () =>
      benchmarksApi.getRunQuestion(toValue(slug), jobId, qaId, model),
    )
  }

  /** The passages sent with the with-data answer. */
  function loadFragments(
    jobId: string,
    qaId: string,
    model: string,
  ): Promise<BenchmarkReportFragment[]> {
    return cached(fragmentCache, `${jobId}|${qaId}|${model}`, () =>
      benchmarksApi.listQuestionFragments(toValue(slug), jobId, qaId, model),
    )
  }

  /** After an action: drop the run's cached figures and refresh the list quietly. */
  function changed(jobId: string): void {
    invalidate(jobId)
    void poll()
  }

  /** Publish the card of this run, whatever its age. */
  async function publish(jobId: string): Promise<PublishOutcome> {
    const result = await benchmarksApi.publishRun(toValue(slug), jobId)
    changed(jobId)
    return { refused: result?.refused ?? [] }
  }

  async function downloadSummary(jobId: string): Promise<void> {
    const { blob, fileName } = await benchmarksApi.downloadRunSummary(toValue(slug), jobId)
    saveBlob(blob, fileName ?? `${toValue(slug)}-${jobId}.docx`)
  }

  return {
    loading,
    loaded,
    error,
    revision,
    target,
    inProgress,
    runs,
    total,
    filters,
    filtered,
    page,
    refresh,
    isRunning,
    invalidate,
    loadReport,
    loadQuestions,
    loadQuestion,
    loadFragments,
    publish,
    downloadSummary,
  }
}

export type RunReport = ReturnType<typeof useRunReport>
