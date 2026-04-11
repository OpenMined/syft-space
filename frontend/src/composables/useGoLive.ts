import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { policiesApi } from '@/api/policies/policies'
import { useEndpointsStore } from '@/stores/endpoints'
import { usePolicyCreation } from './usePolicyCreation'
import { DEFAULT_PII_FILTER_CONFIG } from '@/config/policyTypes'
import type { PolicyRulesRecord, PolicyTypeId } from '@/config/policyTypes'
import type { CreateEndpointRequest, PolicyResponse } from '@/api/types'

export type ResourceType = 'data-source' | 'model'
export type ResponseMode = 'raw' | 'summary' | 'both'

export interface GoLiveData {
  resourceType: ResourceType
  resourceId: string

  dataSourceId?: string
  modelId?: string

  responseMode: ResponseMode
  aiModelId: string
  systemPrompt: string

  policyRules: PolicyRulesRecord
  piiFilterEnabled: boolean

  name: string
  summary: string
  description: string
  tags: string[]
}

export function useGoLive() {
  const router = useRouter()
  const endpointsStore = useEndpointsStore()
  const { transformPolicyRules } = usePolicyCreation()

  const isCreating = ref(false)
  const creationError = ref<string | null>(null)
  const creationStep = ref('')
  const createdResources = ref<{
    endpointId?: string
    endpointSlug?: string
    policyIds: string[]
  }>({ policyIds: [] })

  const resetCreatedResources = () => {
    createdResources.value = { policyIds: [] }
  }

  const resolveEndpointResources = (
    data: GoLiveData,
  ): { datasetId?: string; modelId?: string; responseType: string } => {
    if (data.dataSourceId && data.modelId) {
      return {
        datasetId: data.dataSourceId,
        modelId: data.modelId,
        responseType: data.responseMode,
      }
    }
    if (data.resourceType === 'data-source') {
      return {
        datasetId: data.dataSourceId || data.resourceId,
        modelId: data.responseMode === 'raw' ? undefined : data.aiModelId || undefined,
        responseType: data.responseMode,
      }
    }
    // Model-only endpoints never return raw documents, so responseType is always 'summary'.
    return {
      datasetId: data.dataSourceId,
      modelId: data.modelId || data.resourceId,
      responseType: 'summary',
    }
  }

  const createEndpoint = async (
    data: GoLiveData,
  ): Promise<{ id: string; slug: string }> => {
    creationStep.value = 'Setting up your resource...'

    const resolved = resolveEndpointResources(data)
    const slug = data.name.trim()

    const request: CreateEndpointRequest = {
      name: slug,
      slug,
      summary: data.summary,
      description: data.description || '',
      tags: data.tags.join(','),
      response_type: resolved.responseType,
      dataset_id: resolved.datasetId,
      model_id: resolved.modelId,
      system_prompt: data.systemPrompt || undefined,
      published: true,
    }

    const response = await endpointsApi.create(request)
    createdResources.value.endpointId = response.id
    createdResources.value.endpointSlug = response.slug
    return { id: response.id, slug: response.slug }
  }

  const createPolicies = async (data: GoLiveData, endpointId: string): Promise<void> => {
    const policyRequests = transformPolicyRules(data.policyRules, data.name).map((request) => ({
      ...request,
      endpoint_id: endpointId,
    }))

    if (data.piiFilterEnabled) {
      const piiFilterType: PolicyTypeId = 'pii_filter'
      policyRequests.push({
        name: `PII Filter for ${data.name}`,
        policy_type: piiFilterType,
        configuration: {
          categories: [...DEFAULT_PII_FILTER_CONFIG.categories],
          replacement: DEFAULT_PII_FILTER_CONFIG.replacement,
        },
        endpoint_id: endpointId,
      })
    }

    if (policyRequests.length === 0) return

    creationStep.value = 'Applying access rules...'

    const responses: PolicyResponse[] = await Promise.all(
      policyRequests.map((request) => policiesApi.create(request)),
    )
    for (const response of responses) {
      createdResources.value.policyIds.push(response.id)
    }
  }

  const publishEndpoint = async (slug: string): Promise<void> => {
    creationStep.value = 'Publishing...'

    const response = await endpointsApi.publish(slug, {
      publish_to_all_marketplaces: true,
    })

    const failed = response.results.filter((r) => !r.success)
    if (failed.length > 0) {
      console.warn('Some marketplaces failed:', failed.map((r) => r.error).join('; '))
    }
  }

  const rollback = async () => {
    creationStep.value = 'Cleaning up...'

    for (const policyId of [...createdResources.value.policyIds].reverse()) {
      try {
        await policiesApi.delete(policyId)
      } catch (e) {
        console.warn(`Rollback: failed to delete policy ${policyId}`, e)
      }
    }

    if (createdResources.value.endpointSlug) {
      try {
        await endpointsApi.delete(createdResources.value.endpointSlug)
      } catch (e) {
        console.warn(`Rollback: failed to delete endpoint`, e)
      }
    }
  }

  const goLive = async (data: GoLiveData): Promise<boolean> => {
    isCreating.value = true
    creationError.value = null
    resetCreatedResources()

    try {
      const endpoint = await createEndpoint(data)
      await createPolicies(data, endpoint.id)
      await publishEndpoint(endpoint.slug)

      creationStep.value = 'Complete!'
      endpointsStore.invalidate()
      toast.success(`"${data.name}" is now published`)
      router.push({ name: 'endpoints' })
      return true
    } catch (error) {
      console.error('Publish failed:', error)
      creationError.value = error instanceof Error ? error.message : 'Unknown error'
      await rollback()
      toast.error(`Failed to publish: ${creationError.value}`)
      return false
    } finally {
      isCreating.value = false
      creationStep.value = ''
    }
  }

  const reset = () => {
    isCreating.value = false
    creationError.value = null
    creationStep.value = ''
    resetCreatedResources()
  }

  return {
    isCreating,
    creationError,
    creationStep,
    goLive,
    reset,
  }
}
