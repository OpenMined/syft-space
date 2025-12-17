import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { datasetsApi } from '@/api/endpoints/datasets'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { policiesApi } from '@/api/policies/policies'
import type { 
  CreateDatasetRequest, 
  CreateEndpointRequest, 
  CreatePolicyRequest,
  PolicyResponse
} from '@/api/types'

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

export interface EndpointCreationData {
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

export function useEndpointCreation() {
  const router = useRouter()
  
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
    policyIds: []
  })

  // Computed
  const isLoading = computed(() => isCreating.value)

  // Helper functions
  const generateCollectionName = (): string => {
    return crypto.randomUUID().replace(/-/g, '')
  }

  const getPolicyDisplayName = (policyType: string): string => {
    const displayNames = {
      'access': 'Authorization',
      'rate_limit': 'Rate Limiter',
      'pricing': 'Pricing'
    }
    return displayNames[policyType as keyof typeof displayNames] || policyType
  }


  const generatePolicyName = (
    policyType: string, 
    ruleIndex: number, 
    ruleConfig: Record<string, unknown>, 
    endpointName: string
  ): string => {
    const baseName = ruleConfig.note || `${getPolicyDisplayName(policyType)} Rule #${ruleIndex + 1}`
    return `${baseName} for ${endpointName}`
  }

  // Step 1: Create dataset (if filesystem source)
  const createDataset = async (data: EndpointCreationData): Promise<string | null> => {
    if (data.selectedDataSourceType !== 'filesystem') {
      return null // No dataset to create
    }

    creationStep.value = 'Creating dataset...'
    
    const filePathsWithDescriptions = data.selectedFiles.map(filePath => ({
      path: filePath,
      description: data.fileDescriptions[filePath] || ''
    }))

    const createRequest: CreateDatasetRequest = {
      dtype: 'local_file',
      name: data.endpointName,
      summary: `Dataset for ${data.summary}`,
      tags: data.tags.join(','),
      configuration: {
        collectionName: generateCollectionName(),
        filePaths: filePathsWithDescriptions
      }
    }

    const response = await datasetsApi.create(createRequest)
    createdResources.value.datasetId = response.id
    createdResources.value.datasetName = response.name
    return response.id
  }

  // Step 2: Create endpoint
  const createEndpoint = async (data: EndpointCreationData, datasetId?: string): Promise<string> => {
    creationStep.value = 'Creating endpoint...'
    
    const createRequest: CreateEndpointRequest = {
      name: data.endpointName,
      slug: data.endpointName,
      summary: data.summary,
      description: data.description || '',
      tags: data.tags.join(','),
      response_type: data.responseType,
      dataset_id: datasetId || (data.selectedDataSourceType === 'existing' ? data.selectedDataSource : undefined),
      model_id: data.aiModel,
      published: true
    }

    const response = await endpointsApi.create(createRequest)
    createdResources.value.endpointId = response.id
    createdResources.value.endpointSlug = response.slug
    return response.id
  }

  // Step 3: Create policies
  const createPolicies = async (data: EndpointCreationData, endpointId: string): Promise<string[]> => {
    creationStep.value = 'Applying policies...'
    
    const policyRequests: CreatePolicyRequest[] = []
    
    // Convert frontend policy rules to backend format
    // Only process implemented policy types (access, rate_limit)
    const implementedPolicies = ['access', 'rate_limit']
    
    Object.entries(data.policyRules).forEach(([policyType, rules]) => {
      // Skip pricing policy for now since it's not implemented
      if (!implementedPolicies.includes(policyType)) {
        console.log(`Skipping ${policyType} policy - not implemented yet`)
        return
      }
      
      rules.forEach((rule: PolicyRule, index: number) => {
        const policyName = generatePolicyName(policyType, index, rule.config, data.endpointName)
        
        // Transform frontend form data to backend configuration format
        let configuration: Record<string, unknown>
        
        if (policyType === 'access') {
          // Transform access policy configuration
          const userList = (rule.config.users as string || '').split(',').map(u => u.trim()).filter(u => u.length > 0)
          const ruleType = rule.config.ruleType as string
          
          if (ruleType === 'allow') {
            configuration = {
              allowed_users: userList,
              denied_users: []
            }
          } else {
            configuration = {
              allowed_users: [],
              denied_users: userList
            }
          }
        } else if (policyType === 'rate_limit') {
          // Transform rate limit policy configuration
          const limit = rule.config.limit as string
          const windowUnit = rule.config.windowUnit as string
          const scope = rule.config.scope as string
          
          // Convert windowUnit to backend format
          const unitMap: Record<string, string> = {
            'second': 's',
            'minute': 'm', 
            'hour': 'h'
          }
          
          const backendUnit = unitMap[windowUnit] || 'm'
          const formattedLimit = `${limit}/${backendUnit}`
          
          // Convert scope to backend format
          const backendScope = scope === 'per user' ? 'per_user' : 'global'
          
          configuration = {
            limit: formattedLimit,
            scope: backendScope
          }
        } else {
          // Fallback for other policy types
          configuration = rule.config
        }
        
        policyRequests.push({
          name: policyName,
          policy_type: policyType,
          configuration: configuration,
          endpoint_id: endpointId
        })
      })
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
        throw new Error(`Failed to create policy "${policyRequest.name}": ${error instanceof Error ? error.message : 'Unknown error'}`)
      }
    }

    return createdPolicies.map(p => p.id)
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
  const createEndpointWithData = async (data: EndpointCreationData): Promise<boolean> => {
    isCreating.value = true
    creationError.value = null
    createdResources.value = { 
      policyIds: [],
      datasetId: undefined,
      datasetName: undefined,
      endpointId: undefined,
      endpointSlug: undefined
    }

    try {
      // Step 1: Create dataset (if filesystem source)
      const datasetId = await createDataset(data)

      // Step 2: Create endpoint
      const endpointId = await createEndpoint(data, datasetId || undefined)

      // Step 3: Create policies
      await createPolicies(data, endpointId)

      // Success!
      creationStep.value = 'Complete!'
      toast.success(`Endpoint "${data.endpointName}" created successfully`)
      
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
      endpointSlug: undefined
    }
  }

  return {
    // State
    isCreating: isLoading,
    creationError,
    creationStep,

    // Methods
    createEndpointWithData,
    reset
  }
}