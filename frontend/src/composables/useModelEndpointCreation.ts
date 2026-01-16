import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { modelsApi } from '@/api/endpoints/models'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { policiesApi } from '@/api/policies/policies'
import { usePolicyCreation } from './usePolicyCreation'
import type { CreateModelRequest, CreateEndpointRequest, PolicyResponse } from '@/api/types'

export interface PolicyRule {
  id: string
  config: Record<string, unknown>
  isEditing: boolean
}

export interface PolicyRules {
  access: PolicyRule[]
  rate_limit: PolicyRule[]
  pricing: PolicyRule[]
}

export interface ModelEndpointCreationData {
  // Step 1: Model configuration
  selectedModelSourceType: 'create-new' | 'existing' | ''
  newModelForm: {
    provider: string
    model: string
    apiKey: string
  }
  selectedModelId: string // For existing model selection

  // Step 2: Policies
  policyRules: PolicyRules

  // Step 3: Metadata
  endpointName: string
  summary: string
  description: string
  tags: string[]
}

export function useModelEndpointCreation() {
  const router = useRouter()
  const { transformPolicyRules } = usePolicyCreation()

  // State
  const isCreating = ref(false)
  const creationError = ref<string | null>(null)
  const creationStep = ref('')
  const createdResources = ref<{
    modelId?: string
    modelName?: string
    endpointId?: string
    endpointSlug?: string
    policyIds: string[]
  }>({
    policyIds: [],
  })

  // Computed
  const isLoading = computed(() => isCreating.value)

  // Helper function to generate base URL for different providers
  const getBaseUrl = (provider: string): string => {
    switch (provider) {
      case 'openai':
        return 'https://api.openai.com/v1'
      case 'groq':
        return 'https://api.groq.com/openai/v1'
      case 'openrouter':
        return 'https://openrouter.ai/api/v1'
      case 'together':
        return 'https://api.together.xyz/v1'
      case 'perplexity':
        return 'https://api.perplexity.ai'
      default:
        return 'https://api.openai.com/v1'
    }
  }

  // Derive model name from endpoint details
  const getDerivedModelName = (data: ModelEndpointCreationData): string => {
    // Use endpoint name as the model name for consistency
    return data.endpointName || 'new-model'
  }

  // Step 1: Create model (if new model source)
  const createModel = async (data: ModelEndpointCreationData): Promise<string | null> => {
    if (data.selectedModelSourceType !== 'create-new') {
      return null // No model to create
    }

    creationStep.value = 'Creating model...'

    const createRequest: CreateModelRequest = {
      name: getDerivedModelName(data),
      dtype: 'openai',
      configuration: {
        api_key: data.newModelForm.apiKey,
        model: data.newModelForm.model,
        base_url: getBaseUrl(data.newModelForm.provider),
        system_prompt: '', // Default empty system prompt
      },
      summary: data.summary ? `Model for ${data.summary}` : '',
      tags: data.tags.join(', '),
    }

    const response = await modelsApi.create(createRequest)
    createdResources.value.modelId = response.id
    createdResources.value.modelName = response.name
    return response.id
  }

  // Step 2: Create endpoint
  const createEndpoint = async (
    data: ModelEndpointCreationData,
    modelId?: string,
  ): Promise<string> => {
    creationStep.value = 'Creating endpoint...'

    const createRequest: CreateEndpointRequest = {
      name: data.endpointName,
      slug: data.endpointName,
      summary: data.summary,
      description: data.description || '',
      tags: data.tags.join(','),
      response_type: 'summary', // Hardcoded to 'summary' for model endpoints
      model_id:
        modelId || (data.selectedModelSourceType === 'existing' ? data.selectedModelId : undefined),
      published: true,
    }

    const response = await endpointsApi.create(createRequest)
    createdResources.value.endpointId = response.id
    createdResources.value.endpointSlug = response.slug
    return response.id
  }

  // Step 3: Create policies
  const createPolicies = async (
    data: ModelEndpointCreationData,
    endpointId: string,
  ): Promise<string[]> => {
    creationStep.value = 'Applying policies...'

    // Transform frontend policy rules to backend format using the composable
    const policyRequests = transformPolicyRules(data.policyRules, data.endpointName)

    // Set the endpoint_id for each request
    policyRequests.forEach((request) => {
      request.endpoint_id = endpointId
    })

    // Create all policies - fail fast on any failure
    const createdPolicies: PolicyResponse[] = []

    for (const policyRequest of policyRequests) {
      try {
        const response = await policiesApi.create(policyRequest)
        createdPolicies.push(response)
        createdResources.value.policyIds.push(response.id)
      } catch (error) {
        console.error(`Failed to create policy: ${policyRequest.name}`, error)
        // Fail fast - throw error to trigger rollback
        throw new Error(
          `Failed to create policy "${policyRequest.name}": ${error instanceof Error ? error.message : 'Unknown error'}`,
        )
      }
    }

    return createdPolicies.map((p) => p.id)
  }

  // Step 4: Publish endpoint to all marketplaces
  const publishEndpoint = async (slug: string): Promise<void> => {
    creationStep.value = 'Publishing to SyftHub...'

    try {
      const response = await endpointsApi.publish(slug, {
        publish_to_all_marketplaces: true,
      })

      // Check if any marketplace failed
      const failedResults = response.results.filter((r) => !r.success)
      if (failedResults.length > 0) {
        const errorMessages = failedResults
          .map((r) => `${r.marketplace_name}: ${r.error}`)
          .join('; ')
        console.warn(`Some marketplaces failed to publish: ${errorMessages}`)
      }
    } catch (error) {
      // Log the error but don't fail the whole creation process
      // The endpoint is created locally, just not published to marketplaces
      console.error('Failed to publish endpoint to marketplaces:', error)
      throw new Error(
        `Failed to publish to SyftHub: ${error instanceof Error ? error.message : 'Unknown error'}`,
      )
    }
  }

  // Rollback function to clean up created resources
  const rollback = async () => {
    creationStep.value = 'Cleaning up...'

    try {
      // Delete policies first (in reverse order)
      for (const policyId of [...createdResources.value.policyIds].reverse()) {
        try {
          await policiesApi.delete(policyId)
          console.log(`Deleted policy ${policyId}`)
        } catch (error) {
          console.warn(`Failed to delete policy ${policyId}:`, error)
        }
      }

      // Delete endpoint
      if (createdResources.value.endpointSlug) {
        try {
          await endpointsApi.delete(createdResources.value.endpointSlug)
          console.log(`Deleted endpoint ${createdResources.value.endpointSlug}`)
        } catch (error) {
          console.warn(`Failed to delete endpoint ${createdResources.value.endpointSlug}:`, error)
        }
      }

      // Delete model (only if we created it)
      if (createdResources.value.modelName) {
        try {
          await modelsApi.delete(createdResources.value.modelName)
          console.log(`Deleted model ${createdResources.value.modelName}`)
        } catch (error) {
          console.warn(`Failed to delete model ${createdResources.value.modelName}:`, error)
        }
      }
    } catch (error) {
      console.error('Rollback failed:', error)
    }
  }

  // Main creation function
  const createModelEndpointWithData = async (data: ModelEndpointCreationData): Promise<boolean> => {
    isCreating.value = true
    creationError.value = null
    createdResources.value = {
      policyIds: [],
      modelId: undefined,
      modelName: undefined,
      endpointId: undefined,
      endpointSlug: undefined,
    }

    try {
      // Step 1: Create model (if new model source)
      const modelId = await createModel(data)

      // Step 2: Create endpoint
      const endpointId = await createEndpoint(data, modelId || undefined)

      // Step 3: Create policies
      await createPolicies(data, endpointId)

      // Step 4: Publish endpoint to all marketplaces
      await publishEndpoint(data.endpointName)

      // Success!
      creationStep.value = 'Complete!'
      toast.success(`Model endpoint "${data.endpointName}" published successfully to SyftHub`)

      // Navigate to the endpoint details page
      router.push({ name: 'endpoints' })

      return true
    } catch (error) {
      console.error('Model endpoint creation failed:', error)
      creationError.value = error instanceof Error ? error.message : 'Unknown error occurred'

      // Attempt rollback
      await rollback()

      toast.error(`Failed to create model endpoint: ${creationError.value}`)
      return false
    } finally {
      isCreating.value = false
      creationStep.value = ''
    }
  }

  // Reset function
  const reset = () => {
    isCreating.value = false
    creationError.value = null
    creationStep.value = ''
    createdResources.value = {
      policyIds: [],
      modelId: undefined,
      modelName: undefined,
      endpointId: undefined,
      endpointSlug: undefined,
    }
  }

  return {
    // State
    isCreating: isLoading,
    creationError,
    creationStep,

    // Methods
    createModelEndpointWithData,
    reset,
  }
}
