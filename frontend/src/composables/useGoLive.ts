import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { datasetsApi } from '@/api/endpoints/datasets'
import { modelsApi } from '@/api/endpoints/models'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { policiesApi } from '@/api/policies/policies'
import { getProviderBaseUrl } from '@/config/providers'
import { usePolicyCreation } from './usePolicyCreation'
import { DEFAULT_PII_FILTER_CONFIG } from '@/config/policyTypes'
import type { PolicyRulesRecord } from '@/config/policyTypes'
import type {
  CreateDatasetRequest,
  CreateModelRequest,
  CreateEndpointRequest,
  PolicyResponse,
} from '@/api/types'

export type ResourceType = 'data-source' | 'model'
export type ResponseMode = 'raw' | 'summary' | 'both'

export interface GoLiveData {
  resourceType: ResourceType
  resourceId: string
  resourceIsNew: boolean

  dataSourceId?: string
  modelId?: string

  newDataSource?: {
    files: string[]
    fileDescriptions: Record<string, string>
  }

  newModel?: {
    provider: string
    model: string
    apiKey: string
    baseUrl: string
  }

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
  const { transformPolicyRules } = usePolicyCreation()

  const isCreating = ref(false)
  const creationError = ref<string | null>(null)
  const creationStep = ref('')
  const createdResources = ref<{
    datasetId?: string
    datasetName?: string
    modelId?: string
    modelName?: string
    endpointId?: string
    endpointSlug?: string
    policyIds: string[]
  }>({ policyIds: [] })

  const resetCreatedResources = () => {
    createdResources.value = {
      policyIds: [],
      datasetId: undefined,
      datasetName: undefined,
      modelId: undefined,
      modelName: undefined,
      endpointId: undefined,
      endpointSlug: undefined,
    }
  }

  const createDatasetIfNeeded = async (data: GoLiveData): Promise<string | undefined> => {
    if (data.resourceType !== 'data-source' || !data.resourceIsNew || !data.newDataSource) {
      return undefined
    }

    creationStep.value = 'Creating data source...'

    const filePaths = data.newDataSource.files.map((path) => ({
      path,
      description: data.newDataSource!.fileDescriptions[path] || '',
    }))

    const request: CreateDatasetRequest = {
      dtype: 'local_file',
      name: data.name,
      summary: `Dataset for ${data.summary}`,
      tags: data.tags.join(','),
      configuration: { filePaths },
    }

    const response = await datasetsApi.create(request)
    createdResources.value.datasetId = response.id
    createdResources.value.datasetName = response.name
    return response.id
  }

  const createModelIfNeeded = async (data: GoLiveData): Promise<string | undefined> => {
    if (data.resourceType !== 'model' || !data.resourceIsNew || !data.newModel) {
      return undefined
    }

    creationStep.value = 'Creating model...'

    const request: CreateModelRequest = {
      name: data.name,
      dtype: 'openai',
      configuration: {
        api_key: data.newModel.apiKey,
        model: data.newModel.model,
        base_url: data.newModel.baseUrl || getProviderBaseUrl(data.newModel.provider),
        system_prompt: data.systemPrompt || '',
      },
      summary: data.summary ? `Model for ${data.summary}` : '',
      tags: data.tags.join(', '),
    }

    const response = await modelsApi.create(request)
    createdResources.value.modelId = response.id
    createdResources.value.modelName = response.name
    return response.id
  }

  const createEndpoint = async (
    data: GoLiveData,
    datasetId?: string,
    modelId?: string,
  ): Promise<string> => {
    creationStep.value = 'Setting up your resource...'

    let finalDatasetId = datasetId || data.dataSourceId
    let finalModelId = modelId || data.modelId
    let responseType: string = data.responseMode

    if (data.dataSourceId && data.modelId) {
      finalDatasetId = data.dataSourceId
      finalModelId = data.modelId
      if (responseType === 'raw') responseType = 'summary'
    } else if (data.resourceType === 'data-source') {
      finalDatasetId = finalDatasetId || (data.resourceIsNew ? undefined : data.resourceId)
      finalModelId = data.responseMode === 'raw' ? undefined : data.aiModelId || undefined
    } else {
      finalModelId = finalModelId || (data.resourceIsNew ? undefined : data.resourceId)
      responseType = 'summary'
    }

    const request: CreateEndpointRequest = {
      name: data.name.trim(),
      slug: data.name.trim(),
      summary: data.summary,
      description: data.description || '',
      tags: data.tags.join(','),
      response_type: responseType,
      dataset_id: finalDatasetId,
      model_id: finalModelId,
      system_prompt: data.systemPrompt || undefined,
      published: true,
    }

    const response = await endpointsApi.create(request)
    createdResources.value.endpointId = response.id
    createdResources.value.endpointSlug = response.slug
    return response.id
  }

  const createPolicies = async (data: GoLiveData, endpointId: string): Promise<void> => {
    const policyRequests = transformPolicyRules(data.policyRules, data.name)

    if (data.piiFilterEnabled) {
      policyRequests.push({
        name: `PII Filter for ${data.name}`,
        policy_type: 'pii_filter',
        configuration: {
          categories: [...DEFAULT_PII_FILTER_CONFIG.categories],
          replacement: DEFAULT_PII_FILTER_CONFIG.replacement,
        },
        endpoint_id: '',
      })
    }

    if (policyRequests.length === 0) return

    creationStep.value = 'Applying access rules...'

    for (const request of policyRequests) {
      request.endpoint_id = endpointId
      const response: PolicyResponse = await policiesApi.create(request)
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

    if (createdResources.value.datasetName) {
      try {
        await datasetsApi.delete(createdResources.value.datasetName)
      } catch (e) {
        console.warn(`Rollback: failed to delete dataset`, e)
      }
    }

    if (createdResources.value.modelName) {
      try {
        await modelsApi.delete(createdResources.value.modelName)
      } catch (e) {
        console.warn(`Rollback: failed to delete model`, e)
      }
    }
  }

  const goLive = async (data: GoLiveData): Promise<boolean> => {
    isCreating.value = true
    creationError.value = null
    resetCreatedResources()

    try {
      const datasetId = await createDatasetIfNeeded(data)
      const modelId = await createModelIfNeeded(data)
      const endpointId = await createEndpoint(data, datasetId, modelId)
      await createPolicies(data, endpointId)
      await publishEndpoint(data.name)

      creationStep.value = 'Complete!'
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
