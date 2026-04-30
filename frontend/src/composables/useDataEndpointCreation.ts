import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { datasetsApi } from '@/api/endpoints/datasets'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { policiesApi } from '@/api/policies/policies'
import { usePolicyCreation } from './usePolicyCreation'
import type { CreateDatasetRequest, CreateEndpointRequest, PolicyResponse } from '@/api/types'

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

export interface DataEndpointCreationData {
  // Step 1: Data source
  selectedDataSourceType: 'filesystem' | 'existing' | ''
  selectedFiles: string[]
  fileDescriptions: Record<string, string>
  selectedDataSource: string // For existing dataset selection

  // Step 2: Response configuration
  responseType: string
  aiModel: string

  // Step 3: Policies
  policyRules: PolicyRules

  // Step 4: Metadata
  endpointName: string
  summary: string
  description: string
  tags: string[]
}

export function useDataEndpointCreation() {
  const router = useRouter()
  const { transformPolicyRules } = usePolicyCreation()

  // State
  const isCreating = ref(false)
  const creationError = ref<string | null>(null)
  const creationStep = ref('')
  const createdResources = ref<{
    datasetId?: string
    datasetName?: string
    endpointId?: string
    endpointSlug?: string
    policyIds: string[]
  }>({
    policyIds: [],
  })

  // Computed
  const isLoading = computed(() => isCreating.value)

  // Step 1: Create dataset (if filesystem source)
  const createDataset = async (data: DataEndpointCreationData): Promise<string | null> => {
    if (data.selectedDataSourceType !== 'filesystem') {
      return null // No dataset to create
    }

    creationStep.value = 'Creating dataset...'

    const filePathsWithDescriptions = data.selectedFiles.map((filePath) => ({
      path: filePath,
      description: data.fileDescriptions[filePath] || '',
    }))

    const createRequest: CreateDatasetRequest = {
      dtype: 'local_file',
      name: data.endpointName,
      summary: `Dataset for ${data.summary}`,
      tags: data.tags.join(','),
      configuration: {
        filePaths: filePathsWithDescriptions,
      },
    }

    const response = await datasetsApi.create(createRequest)
    createdResources.value.datasetId = response.id
    createdResources.value.datasetName = response.name
    return response.id
  }

  // Step 2: Create endpoint
  const createEndpointResource = async (
    data: DataEndpointCreationData,
    datasetId?: string,
  ): Promise<string> => {
    creationStep.value = 'Creating endpoint...'

    // Determine the model ID to use
    const finalModelId = data.responseType === 'raw' ? undefined : data.aiModel || undefined

    const createRequest: CreateEndpointRequest = {
      name: data.endpointName.trim(),
      slug: data.endpointName.trim(),
      summary: data.summary,
      description: data.description || '',
      tags: data.tags.join(','),
      response_type: data.responseType,
      dataset_id:
        datasetId ||
        (data.selectedDataSourceType === 'existing' ? data.selectedDataSource : undefined),
      model_id: finalModelId,
      published: true,
    }

    const response = await endpointsApi.create(createRequest)
    createdResources.value.endpointId = response.id
    createdResources.value.endpointSlug = response.slug
    return response.id
  }

  // Step 3: Create policies
  const createPolicies = async (
    data: DataEndpointCreationData,
    endpointId: string,
  ): Promise<string[]> => {
    creationStep.value = 'Applying policies...'

    // Transform frontend policy rules to backend format using the composable
    const policyRequests = await transformPolicyRules(data.policyRules, data.endpointName)

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

      // Delete dataset (only if we created it)
      if (createdResources.value.datasetName) {
        try {
          await datasetsApi.delete(createdResources.value.datasetName)
          console.log(`Deleted dataset ${createdResources.value.datasetName}`)
        } catch (error) {
          console.warn(`Failed to delete dataset ${createdResources.value.datasetName}:`, error)
        }
      }
    } catch (error) {
      console.error('Rollback failed:', error)
    }
  }

  // Main creation function
  const createDataEndpointWithData = async (data: DataEndpointCreationData): Promise<boolean> => {
    isCreating.value = true
    creationError.value = null
    createdResources.value = {
      policyIds: [],
      datasetId: undefined,
      datasetName: undefined,
      endpointId: undefined,
      endpointSlug: undefined,
    }

    try {
      // Step 1: Create dataset (if filesystem source)
      const datasetId = await createDataset(data)

      // Step 2: Create endpoint
      const endpointId = await createEndpointResource(data, datasetId || undefined)

      // Step 3: Create policies
      await createPolicies(data, endpointId)

      // Step 4: Publish endpoint to all marketplaces
      await publishEndpoint(data.endpointName)

      // Success!
      creationStep.value = 'Complete!'
      toast.success(`Endpoint "${data.endpointName}" published successfully to SyftHub`)

      // Navigate to the endpoint details page
      router.push({ name: 'endpoints' })

      return true
    } catch (error) {
      console.error('Endpoint creation failed:', error)
      creationError.value = error instanceof Error ? error.message : 'Unknown error occurred'

      // Attempt rollback
      await rollback()

      toast.error(`Failed to create endpoint: ${creationError.value}`)
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
      datasetId: undefined,
      datasetName: undefined,
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
    createDataEndpointWithData,
    reset,
  }
}
