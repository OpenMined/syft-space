import { ref } from 'vue'
import { policiesApi } from '@/api/policies/policies'
import { useUserStore } from '@/stores/user'
import type { CreatePolicyRequest } from '@/api/types'

export interface PolicyRules {
  access: Array<{ id: string; config: Record<string, unknown> }>
  rate_limit: Array<{ id: string; config: Record<string, unknown> }>
  pricing: Array<{ id: string; config: Record<string, unknown> }>
  pii_filter: Array<{ id: string; config: Record<string, unknown> }>
}

export interface AuthorizationFormData {
  ruleType: 'allow' | 'deny'
  users: string
  note: string
}

export interface RateLimitFormData {
  limit: string
  windowUnit: 'second' | 'minute' | 'hour'
  scope: 'per user' | 'global'
  note: string
}

export interface PricingFormData {
  price: string
  userType: 'all' | 'specific'
  users: string
  note: string
}

export interface PiiFilterFormData {
  model_id: string
  prompt: string
  target: 'summary' | 'references' | 'both'
  on_error: 'block' | 'passthrough'
  note: string
}

export type PolicyFormData =
  | AuthorizationFormData
  | RateLimitFormData
  | PricingFormData
  | PiiFilterFormData

export function usePolicyCreation() {
  const isCreating = ref(false)
  const creationError = ref<string | null>(null)

  // Helper functions
  const getPolicyDisplayName = (policyType: string): string => {
    const displayNames = {
      access: 'Authorization',
      rate_limit: 'Rate Limiter',
      pricing: 'Pricing',
      pii_filter: 'PII Filter',
    }
    return displayNames[policyType as keyof typeof displayNames] || policyType
  }

  const generatePolicyName = (
    policyType: string,
    formData: PolicyFormData,
    endpointName: string,
    ruleIndex: number = 1,
  ): string => {
    const baseName = formData.note || `${getPolicyDisplayName(policyType)} Rule #${ruleIndex}`
    return `${baseName} for ${endpointName}`
  }

  const processUserList = (users: string): string[] => {
    return users
      .split(',')
      .map((u) => u.trim())
      .filter((u) => u.length > 0)
  }

  // Helper function to create pricing configuration
  const createPricingConfiguration = (
    price: string | number,
    userType: 'all' | 'specific',
    users: string = '',
  ): Record<string, unknown> => {
    const configuration: Record<string, unknown> = {
      price: typeof price === 'string' ? parseFloat(price) : price,
    }

    // Set applied_to based on userType: ['*'] for all users, user list for specific users
    if (userType === 'specific') {
      const userList = processUserList(users)
      configuration.applied_to = userList
    } else {
      configuration.applied_to = ['*']
    }

    return configuration
  }

  // Policy type specific creation methods
  const createAuthorizationPolicy = async (
    formData: AuthorizationFormData,
    endpointId: string,
    endpointName: string,
    ruleIndex: number = 1,
  ) => {
    const userList = processUserList(formData.users)
    const policyName = generatePolicyName('access', formData, endpointName, ruleIndex)

    let configuration: Record<string, unknown>
    if (formData.ruleType === 'allow') {
      configuration = {
        allowed_users: userList,
        denied_users: [],
      }
    } else {
      configuration = {
        allowed_users: [],
        denied_users: userList,
      }
    }

    const request: CreatePolicyRequest = {
      name: policyName,
      policy_type: 'access',
      configuration: configuration,
      endpoint_id: endpointId,
    }

    return await policiesApi.create(request)
  }

  const createRateLimitPolicy = async (
    formData: RateLimitFormData,
    endpointId: string,
    endpointName: string,
    ruleIndex: number = 1,
  ) => {
    const policyName = generatePolicyName('rate_limit', formData, endpointName, ruleIndex)

    // Convert windowUnit to backend format
    const unitMap: Record<string, string> = {
      second: 's',
      minute: 'm',
      hour: 'h',
    }

    const backendUnit = unitMap[formData.windowUnit] || 'm'
    const formattedLimit = `${formData.limit}/${backendUnit}`

    // Convert scope to backend format
    const backendScope = formData.scope === 'per user' ? 'per_user' : 'global'

    const configuration = {
      limit: formattedLimit,
      scope: backendScope,
    }

    const request: CreatePolicyRequest = {
      name: policyName,
      policy_type: 'rate_limit',
      configuration: configuration,
      endpoint_id: endpointId,
    }

    return await policiesApi.create(request)
  }

  const createPricingPolicy = async (
    formData: PricingFormData,
    endpointId: string,
    endpointName: string,
    ruleIndex: number = 1,
  ) => {
    const userStore = useUserStore()

    if (!userStore.walletId) {
      throw new Error('Please set up a wallet before creating a pricing policy.')
    }

    const policyName = generatePolicyName('pricing', formData, endpointName, ruleIndex)
    const configuration = createPricingConfiguration(
      formData.price,
      formData.userType,
      formData.users,
    )

    const request: CreatePolicyRequest = {
      name: policyName,
      policy_type: 'mpp_accounting',
      configuration: configuration,
      endpoint_id: endpointId,
      wallet_id: userStore.walletId,
    }

    return await policiesApi.create(request)
  }

  // Generic policy creation method that routes to specific handlers
  const createPiiFilterPolicy = async (
    formData: PiiFilterFormData,
    endpointId: string,
    endpointName: string,
    ruleIndex: number = 1,
  ) => {
    const policyName = generatePolicyName('pii_filter', formData, endpointName, ruleIndex)

    const configuration: Record<string, unknown> = {
      model_id: formData.model_id,
      prompt: formData.prompt,
      target: formData.target,
      on_error: formData.on_error,
    }

    const request: CreatePolicyRequest = {
      name: policyName,
      policy_type: 'pii_filter',
      configuration: configuration,
      endpoint_id: endpointId,
    }

    return await policiesApi.create(request)
  }

  const createPolicy = async (
    policyType: 'access' | 'rate_limit' | 'pricing' | 'pii_filter',
    formData: PolicyFormData,
    endpointId: string,
    endpointName: string,
    ruleIndex: number = 1,
  ) => {
    isCreating.value = true
    creationError.value = null

    try {
      let result
      switch (policyType) {
        case 'access':
          result = await createAuthorizationPolicy(
            formData as AuthorizationFormData,
            endpointId,
            endpointName,
            ruleIndex,
          )
          break
        case 'rate_limit':
          result = await createRateLimitPolicy(
            formData as RateLimitFormData,
            endpointId,
            endpointName,
            ruleIndex,
          )
          break
        case 'pricing':
          result = await createPricingPolicy(
            formData as PricingFormData,
            endpointId,
            endpointName,
            ruleIndex,
          )
          break
        case 'pii_filter':
          result = await createPiiFilterPolicy(
            formData as PiiFilterFormData,
            endpointId,
            endpointName,
            ruleIndex,
          )
          break
        default:
          throw new Error(`Unsupported policy type: ${policyType}`)
      }
      return result
    } catch (error) {
      creationError.value = error instanceof Error ? error.message : 'Unknown error occurred'
      throw error
    } finally {
      isCreating.value = false
    }
  }

  // Transform frontend policy rules to backend format for batch creation
  const transformPolicyRules = (
    policyRules:
      | Record<string, Array<{ id: string; config: Record<string, unknown> }>>
      | PolicyRules,
    endpointName: string,
  ): CreatePolicyRequest[] => {
    const policyRequests: CreatePolicyRequest[] = []

    const implementedPolicies = ['access', 'rate_limit', 'pricing', 'pii_filter']

    Object.entries(policyRules).forEach(([policyType, rules]) => {
      if (!implementedPolicies.includes(policyType)) {
        console.log(`Skipping ${policyType} policy - not implemented yet`)
        return
      }

      rules.forEach((rule: { id: string; config: Record<string, unknown> }, index: number) => {
        const policyName = generatePolicyName(
          policyType,
          rule.config as unknown as PolicyFormData,
          endpointName,
          index + 1,
        )

        let configuration: Record<string, unknown>

        if (policyType === 'access') {
          const userList = processUserList((rule.config.users as string) || '')
          const ruleType = rule.config.ruleType as string

          if (ruleType === 'allow') {
            configuration = {
              allowed_users: userList,
              denied_users: [],
            }
          } else {
            configuration = {
              allowed_users: [],
              denied_users: userList,
            }
          }
        } else if (policyType === 'rate_limit') {
          const limit = rule.config.limit as string
          const windowUnit = rule.config.windowUnit as string
          const scope = rule.config.scope as string

          // Convert windowUnit to backend format
          const unitMap: Record<string, string> = {
            second: 's',
            minute: 'm',
            hour: 'h',
          }

          const backendUnit = unitMap[windowUnit] || 'm'
          const formattedLimit = `${limit}/${backendUnit}`

          // Convert scope to backend format
          const backendScope = scope === 'per user' ? 'per_user' : 'global'

          configuration = {
            limit: formattedLimit,
            scope: backendScope,
          }
        } else if (policyType === 'pricing') {
          const price = rule.config.price as string
          const userType = rule.config.userType as 'all' | 'specific'
          const users = rule.config.users as string

          configuration = createPricingConfiguration(price, userType, users)
        } else if (policyType === 'pii_filter') {
          configuration = {
            model_id: rule.config.model_id,
            prompt: rule.config.prompt,
            target: rule.config.target,
            on_error: rule.config.on_error,
          }
        } else {
          // Fallback for other policy types
          configuration = rule.config
        }

        // Map frontend policy type to backend policy type
        const backendPolicyType = policyType === 'pricing' ? 'mpp_accounting' : policyType

        const request: CreatePolicyRequest = {
          name: policyName,
          policy_type: backendPolicyType,
          configuration: configuration,
          endpoint_id: '', // Will be set by caller
        }

        if (backendPolicyType === 'mpp_accounting') {
          const userStore = useUserStore()
          if (userStore.walletId) {
            request.wallet_id = userStore.walletId
          }
        }

        policyRequests.push(request)
      })
    })

    return policyRequests
  }

  // Validation methods
  const validateAuthorizationForm = (formData: AuthorizationFormData): boolean => {
    const userList = processUserList(formData.users)
    return userList.length > 0
  }

  const validateRateLimitForm = (formData: RateLimitFormData): boolean => {
    const limitStr = String(formData.limit).trim()
    return limitStr !== '' && Number(limitStr) > 0
  }

  const validatePricingForm = (formData: PricingFormData): boolean => {
    const price = parseFloat(formData.price)
    return !isNaN(price) && price >= 0
  }

  const validatePiiFilterForm = (formData: PiiFilterFormData): boolean => {
    return formData.model_id.trim().length > 0 && formData.prompt.trim().length >= 10
  }

  const validatePolicyForm = (policyType: string, formData: PolicyFormData): boolean => {
    switch (policyType) {
      case 'access':
        return validateAuthorizationForm(formData as AuthorizationFormData)
      case 'rate_limit':
        return validateRateLimitForm(formData as RateLimitFormData)
      case 'pricing':
        return validatePricingForm(formData as PricingFormData)
      case 'pii_filter':
        return validatePiiFilterForm(formData as PiiFilterFormData)
      default:
        return false
    }
  }

  // Reset error state
  const reset = () => {
    isCreating.value = false
    creationError.value = null
  }

  return {
    // State
    isCreating,
    creationError,

    // Methods
    createPolicy,
    createAuthorizationPolicy,
    createRateLimitPolicy,
    createPricingPolicy,
    createPiiFilterPolicy,
    transformPolicyRules,
    validatePolicyForm,
    validateAuthorizationForm,
    validateRateLimitForm,
    validatePricingForm,
    validatePiiFilterForm,
    processUserList,
    generatePolicyName,
    reset,
  }
}
