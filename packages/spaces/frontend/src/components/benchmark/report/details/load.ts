/** Loads what a job did while writing and filtering, for one kind or one question. */
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type { BenchmarkFilterDecision, BenchmarkRunPair, BenchmarkWriterCall } from '@/api/types'
import { earlierDrafts, groupCalls, type CallBlock, type DraftView } from './writing'

const PAGE = 200
/** Pairs read by id per request, which keeps the query string short. */
const IDS_PER_REQUEST = 100

/** Every item of a paged route. Callers narrow the route to one job and kind, or one question, so the set is bounded. */
export async function allPages<T>(
  fetch: (offset: number, limit: number) => Promise<{ items: T[]; total: number }>,
  page = PAGE,
): Promise<T[]> {
  const first = await fetch(0, page)
  const all = first.items.slice()
  while (all.length < first.total) {
    const next = await fetch(all.length, page)
    if (!next.items.length) break
    all.push(...next.items)
  }
  return all
}

function generated(slug: string, jobId: string, generator: string): Promise<BenchmarkRunPair[]> {
  return allPages((offset, limit) =>
    benchmarksApi.getRunGenerated(slug, jobId, { generator, limit, offset }),
  )
}

/** Every filter decision of a kind in one request (`limit: 0`): the benchmark computes the whole list for any page. */
async function decisionsOf(
  slug: string,
  jobId: string,
  generator: string,
): Promise<BenchmarkFilterDecision[]> {
  const all = await benchmarksApi.listRunFilter(slug, jobId, { generator, limit: 0 })
  return all.items
}

/** The job's writer calls of a kind. A job that kept no writing log answers with an empty page. */
function writingOf(slug: string, jobId: string, generator: string): Promise<BenchmarkWriterCall[]> {
  return allPages((offset, limit) =>
    benchmarksApi.getRunWriting(slug, jobId, { generator, limit, offset }),
  )
}

/** The pairs behind decisions on questions earlier jobs wrote, read through `jobId` so a deleted writer job does not hide them. */
async function writtenEarlier(
  slug: string,
  jobId: string,
  decisions: readonly BenchmarkFilterDecision[],
): Promise<Map<string, BenchmarkRunPair>> {
  const ids = decisions.map((d) => d.qa_id)
  const requests: Promise<BenchmarkRunPair[]>[] = []
  for (let at = 0; at < ids.length; at += IDS_PER_REQUEST) {
    const chunk = ids.slice(at, at + IDS_PER_REQUEST)
    requests.push(benchmarksApi.getRunPairs(slug, jobId, chunk).then((page) => page.items))
  }
  const pairs = (await Promise.all(requests)).flat()
  return new Map(pairs.map((pair) => [pair.id, pair]))
}

export interface KindOrigin {
  blocks: CallBlock[]
  earlier: DraftView[]
  /** The writer calls did not load: `blocks` are built from the generated pairs alone. */
  writingFailed: boolean
  /** The earlier questions' pairs did not load: `earlier` is built from the decisions alone. */
  earlierFailed: boolean
}

export async function loadKind(
  slug: string,
  jobId: string,
  generator: string,
): Promise<KindOrigin> {
  const [pairs, writing, decisions] = await Promise.all([
    generated(slug, jobId, generator),
    writingOf(slug, jobId, generator).then(
      (calls) => ({ calls, failed: false }),
      () => ({ calls: [] as BenchmarkWriterCall[], failed: true }),
    ),
    decisionsOf(slug, jobId, generator),
  ])
  const byId = new Map(decisions.map((d) => [d.qa_id, d]))
  const earlier = decisions.filter((d) => d.earlier)
  let earlierPairs = new Map<string, BenchmarkRunPair>()
  let earlierFailed = false
  try {
    earlierPairs = await writtenEarlier(slug, jobId, earlier)
  } catch {
    earlierFailed = true
  }
  return {
    blocks: groupCalls(pairs, writing.calls, jobId, byId),
    earlier: earlierDrafts(earlier, earlierPairs, jobId),
    writingFailed: writing.failed,
    earlierFailed,
  }
}

export interface QuestionOriginData {
  block: CallBlock
  draft: DraftView
}

/** One question with its writer call, as every pair of the call carries it, and the filter path `jobId` took it through. */
export async function loadQuestion(
  slug: string,
  jobId: string,
  qaId: string,
): Promise<QuestionOriginData> {
  const pair = await benchmarksApi.getRunPair(slug, jobId, qaId)
  // `groupCalls` makes one block per pair, with the pair as its one draft.
  const block = groupCalls([pair], [], jobId)[0]!
  return { block, draft: block.drafts[0]! }
}
