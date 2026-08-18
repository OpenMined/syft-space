import { ref, onBeforeUnmount } from 'vue'
import { endpointsApi } from '@/api/endpoints/endpoints'
import type {
  ChatSummaryResponse,
  ChatReferencesResponse,
  ChatDocumentResponse,
  EndpointQueryMessage,
  EndpointQueryResponse,
} from '@/api/types'

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
  references?: ChatReferencesResponse | null
  summary?: ChatSummaryResponse | null
}

export interface DataSourceRef {
  slug: string
  name: string
}

export interface SendMessageOptions {
  content: string
  endpointSlug: string
  endpointName?: string
  dataSources?: DataSourceRef[]
}

const MAX_CONTEXT_DOCS = 6
const PER_SOURCE_LIMIT = 5

interface MergeResult {
  merged: ChatReferencesResponse | null
  failedSources: string[]
}

function mergeReferences(
  results: PromiseSettledResult<EndpointQueryResponse>[],
  sources: DataSourceRef[],
): MergeResult {
  const docs: ChatDocumentResponse[] = []
  const engines = new Set<string>()
  const failed: string[] = []

  results.forEach((result, idx) => {
    const source = sources[idx]
    if (!source) return
    if (result.status === 'rejected') {
      failed.push(source.name)
      return
    }
    const refs = result.value?.references
    if (!refs?.documents?.length) return
    if (refs.search_engine) engines.add(refs.search_engine)
    refs.documents.forEach((doc) => {
      docs.push({
        ...doc,
        source_endpoint_slug: source.slug,
        source_endpoint_name: source.name,
      })
    })
  })

  if (docs.length === 0) {
    return { merged: null, failedSources: failed }
  }

  docs.sort((a, b) => b.similarity_score - a.similarity_score)

  const enginesList = Array.from(engines)
  let searchEngine: string | null = null
  if (enginesList.length === 1) searchEngine = enginesList[0]!
  else if (enginesList.length > 1) searchEngine = 'multiple'

  return {
    merged: {
      documents: docs.slice(0, MAX_CONTEXT_DOCS),
      search_engine: searchEngine,
    },
    failedSources: failed,
  }
}

// Tag a chat target's own (server-side RAG) references with its endpoint name so
// the references panel attributes them, mirroring how data-source docs are tagged.
function tagTargetReferences(
  refs: ChatReferencesResponse | null,
  slug: string,
  name: string | undefined,
): ChatReferencesResponse | null {
  if (!refs?.documents?.length || !name) return refs
  return {
    ...refs,
    documents: refs.documents.map((doc) => ({
      ...doc,
      source_endpoint_slug: doc.source_endpoint_slug ?? slug,
      source_endpoint_name: doc.source_endpoint_name ?? name,
    })),
  }
}

// Merge client-side data-source references with the chat target's own references
// (a hybrid endpoint retrieves server-side), keeping the highest-scoring docs.
function combineReferences(
  clientRefs: ChatReferencesResponse | null,
  targetRefs: ChatReferencesResponse | null,
): ChatReferencesResponse | null {
  if (!targetRefs?.documents?.length) return clientRefs
  if (!clientRefs?.documents?.length) return targetRefs

  const documents = [...clientRefs.documents, ...targetRefs.documents]
    .sort((a, b) => b.similarity_score - a.similarity_score)
    .slice(0, MAX_CONTEXT_DOCS)

  const engines = new Set<string>()
  if (clientRefs.search_engine) engines.add(clientRefs.search_engine)
  if (targetRefs.search_engine) engines.add(targetRefs.search_engine)
  const enginesList = Array.from(engines)
  const searchEngine =
    enginesList.length === 1 ? enginesList[0]! : enginesList.length > 1 ? 'multiple' : null

  return { documents, search_engine: searchEngine }
}

function formatContext(refs: ChatReferencesResponse): string {
  const body = refs.documents
    .map((d) => {
      const tag = d.source_endpoint_name ? ` [${d.source_endpoint_name}]` : ''
      return `Document: ${d.document_id}${tag}\n${d.content}`
    })
    .join('\n\n')
  return `Use the following context to answer:\n${body}`
}

export function useEndpointChat() {
  const turns = ref<ChatTurn[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const warning = ref<string | null>(null)
  let abortController: AbortController | null = null

  function buildHistory(): EndpointQueryMessage[] {
    return turns.value.map((t) => ({ role: t.role, content: t.content }))
  }

  async function sendMessage(options: SendMessageOptions) {
    const { content, endpointSlug, endpointName, dataSources = [] } = options

    abortController?.abort()
    abortController = new AbortController()
    const signal = abortController.signal

    turns.value.push({ role: 'user', content })

    loading.value = true
    error.value = null
    warning.value = null

    const history = buildHistory()

    try {
      let mergedRefs: ChatReferencesResponse | null = null
      let failedSources: string[] = []

      if (dataSources.length > 0) {
        const results = await Promise.allSettled(
          dataSources.map((src) =>
            endpointsApi.query(
              src.slug,
              { messages: history, limit: PER_SOURCE_LIMIT },
              { signal },
            ),
          ),
        )
        if (signal.aborted) return
        const merge = mergeReferences(results, dataSources)
        mergedRefs = merge.merged
        failedSources = merge.failedSources
      }

      const messages: EndpointQueryMessage[] = mergedRefs
        ? [{ role: 'system', content: formatContext(mergedRefs) }, ...history]
        : history

      const response = await endpointsApi.query(
        endpointSlug,
        {
          messages,
          max_tokens: 1000,
          temperature: 0.7,
        },
        { signal },
      )

      const targetRefs = tagTargetReferences(response.references, endpointSlug, endpointName)

      turns.value.push({
        role: 'assistant',
        content: response.summary?.message.content ?? '(no response)',
        references: combineReferences(mergedRefs, targetRefs),
        summary: response.summary,
      })

      if (failedSources.length > 0) {
        warning.value = `Search failed for: ${failedSources.join(', ')}`
      }
    } catch (e: unknown) {
      if (signal.aborted) return
      error.value = e instanceof Error ? e.message : 'Request failed'
    } finally {
      if (!signal.aborted) loading.value = false
    }
  }

  function clearChat() {
    abortController?.abort()
    abortController = null
    turns.value = []
    error.value = null
    warning.value = null
    loading.value = false
  }

  onBeforeUnmount(() => {
    abortController?.abort()
    abortController = null
  })

  return { turns, loading, error, warning, sendMessage, clearChat }
}
