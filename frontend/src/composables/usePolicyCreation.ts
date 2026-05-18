import { ref } from 'vue'
import { policiesApi } from '@/api/policies/policies'
import { walletsApi } from '@/api/endpoints/wallets'
import type { CreatePolicyRequest } from '@/api/types'

export interface PolicyRules {
  access: Array<{ id: string; config: Record<string, unknown> }>
  rate_limit: Array<{ id: string; config: Record<string, unknown> }>
  pricing: Array<{ id: string; config: Record<string, unknown> }>
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

export type PolicyFormData = AuthorizationFormData | RateLimitFormData | PricingFormData

export function usePolicyCreation() {
  const isCreating = ref(false)
  const creationError = ref<string | null>(null)

  // Helper functions
  const getPolicyDisplayName = (policyType: string): string => {
    const displayNames = {
      access: 'Authorization',
      rate_limit: 'Rate Limiter',
      pricing: 'Pricing',
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
    const wallets = await walletsApi.list()
    const mppWallet = wallets.find((w) => w.wallet_type === 'mpp' && w.is_active)

    if (!mppWallet) {
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
      policy_type: 'mpp_per_request',
      configuration: configuration,
      endpoint_id: endpointId,
      wallet_id: mppWallet.id,
    }

    return await policiesApi.create(request)
  }

  // Generic policy creation method that routes to specific handlers
  const createPolicy = async (
    policyType: 'access' | 'rate_limit' | 'pricing',
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
  const transformPolicyRules = async (
    policyRules:
      | Record<string, Array<{ id: string; config: Record<string, unknown> }>>
      | PolicyRules,
    endpointName: string,
  ): Promise<CreatePolicyRequest[]> => {
    const policyRequests: CreatePolicyRequest[] = []

    // Only process implemented policy types (access, rate_limit, pricing)
    const implementedPolicies = ['access', 'rate_limit', 'pricing']

    for (const [policyType, rules] of Object.entries(policyRules)) {
      if (!implementedPolicies.includes(policyType)) {
        console.log(`Skipping ${policyType} policy - not implemented yet`)
        continue
      }

      for (const [index, rule] of (
        rules as Array<{ id: string; config: Record<string, unknown> }>
      ).entries()) {
        const policyName = generatePolicyName(
          policyType,
          rule.config as unknown as PolicyFormData,
          endpointName,
          index + 1,
        )

        let configuration: Record<string, unknown>
        let backendPolicyType = policyType
        let walletId: string | undefined

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

          const unitMap: Record<string, string> = {
            second: 's',
            minute: 'm',
            hour: 'h',
          }

          const backendUnit = unitMap[windowUnit] || 'm'
          const formattedLimit = `${limit}/${backendUnit}`
          const backendScope = scope === 'per user' ? 'per_user' : 'global'

          configuration = {
            limit: formattedLimit,
            scope: backendScope,
          }
        } else if (policyType === 'pricing') {
          // New shape: rule.config carries walletId, walletType, policyType.
          // Wallet is resolved by the dialog; we just build the right config.
          walletId = rule.config.walletId as string | undefined
          const walletType = rule.config.walletType as string | undefined
          const explicitPolicyType = rule.config.policyType as
            | 'mpp_per_request'
            | 'xendit_per_request'
            | undefined
          backendPolicyType =
            explicitPolicyType ?? (walletType === 'mpp' ? 'mpp_per_request' : 'xendit_per_request')

          const userType = rule.config.userType as 'all' | 'specific'
          const users = rule.config.users as string
          const appliedTo =
            userType === 'all'
              ? ['*']
              : users
                  .split(',')
                  .map((u) => u.trim())
                  .filter((u) => u)

          if (backendPolicyType === 'mpp_per_request') {
            // Currency lives on the wallet now; only price + applied_to here.
            configuration = createPricingConfiguration(rule.config.price as string, userType, users)
            configuration.applied_to = appliedTo
          } else {
            configuration = {
              price_per_request: parseFloat(rule.config.price as string) || 0,
              applied_to: appliedTo,
            }
          }
        } else {
          configuration = rule.config
        }

        const request: CreatePolicyRequest = {
          name: policyName,
          policy_type: backendPolicyType,
          configuration,
          endpoint_id: '', // Will be set by caller
        }

        if (walletId) {
          request.wallet_id = walletId
        }

        policyRequests.push(request)
      }
    }

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

  const validatePolicyForm = (policyType: string, formData: PolicyFormData): boolean => {
    switch (policyType) {
      case 'access':
        return validateAuthorizationForm(formData as AuthorizationFormData)
      case 'rate_limit':
        return validateRateLimitForm(formData as RateLimitFormData)
      case 'pricing':
        return validatePricingForm(formData as PricingFormData)
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
    transformPolicyRules,
    validatePolicyForm,
    validateAuthorizationForm,
    validateRateLimitForm,
    validatePricingForm,
    processUserList,
    generatePolicyName,
    reset,
  }
}
