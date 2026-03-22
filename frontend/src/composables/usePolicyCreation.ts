import { ref } from 'vue'
import { policiesApi } from '@/api/policies/policies'
import type { CreatePolicyRequest } from '@/api/types'
import { getPolicyTypeLabel } from '@/config/policyTypes'

export interface PolicyRules {
  [key: string]: Array<{ id: string; config: Record<string, unknown> }>
  access: Array<{ id: string; config: Record<string, unknown> }>
  rate_limit: Array<{ id: string; config: Record<string, unknown> }>
  pricing: Array<{ id: string; config: Record<string, unknown> }>
  xendit: Array<{ id: string; config: Record<string, unknown> }>
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

export interface XenditTier {
  name: string
  units: string
  unitType: string
  price: string
}

export interface XenditFormData {
  currency: string
  country: string
  tiers: XenditTier[]
  userType: 'all' | 'specific'
  users: string
}

export type PolicyFormData =
  | AuthorizationFormData
  | RateLimitFormData
  | PricingFormData
  | XenditFormData

export function usePolicyCreation() {
  const isCreating = ref(false)
  const creationError = ref<string | null>(null)

  const generatePolicyName = (
    policyType: string,
    formData: PolicyFormData,
    endpointName: string,
    ruleIndex: number = 1,
  ): string => {
    const baseName =
      ('note' in formData && formData.note) ||
      `${getPolicyTypeLabel(policyType)} Rule #${ruleIndex}`
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
    const policyName = generatePolicyName('pricing', formData, endpointName, ruleIndex)
    const configuration = createPricingConfiguration(
      formData.price,
      formData.userType,
      formData.users,
    )

    const request: CreatePolicyRequest = {
      name: policyName,
      policy_type: 'accounting',
      configuration: configuration,
      endpoint_id: endpointId,
    }

    return await policiesApi.create(request)
  }

  const createXenditConfiguration = (formData: XenditFormData) => ({
    bundle_tiers: formData.tiers.map((t) => ({
      name: t.name,
      units: parseInt(t.units),
      unit_type: t.unitType,
      price: parseFloat(t.price),
    })),
    currency: formData.currency,
    country: formData.country,
    applied_to: formData.userType === 'specific' ? processUserList(formData.users) : ['*'],
  })

  const createXenditPolicy = async (
    formData: XenditFormData,
    endpointId: string,
    endpointName: string,
    ruleIndex: number = 1,
  ) => {
    const policyName = `Bundle Payment Rule #${ruleIndex} for ${endpointName}`
    const configuration = createXenditConfiguration(formData)

    const request: CreatePolicyRequest = {
      name: policyName,
      policy_type: 'xendit',
      configuration: configuration,
      endpoint_id: endpointId,
    }

    return await policiesApi.create(request)
  }

  // Generic policy creation method that routes to specific handlers
  const createPolicy = async (
    policyType: 'access' | 'rate_limit' | 'pricing' | 'xendit',
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
        case 'xendit':
          result = await createXenditPolicy(
            formData as XenditFormData,
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

    Object.entries(policyRules).forEach(([policyType, rules]) => {
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
        } else if (policyType === 'pricing' && rule.config.provider === 'xendit') {
          const xenditData = rule.config as unknown as XenditFormData
          configuration = createXenditConfiguration(xenditData)
        } else if (policyType === 'pricing') {
          const price = rule.config.price as string
          const userType = rule.config.userType as 'all' | 'specific'
          const users = rule.config.users as string

          configuration = createPricingConfiguration(price, userType, users)
        } else if (policyType === 'xendit') {
          const xenditData = rule.config as unknown as XenditFormData
          configuration = createXenditConfiguration(xenditData)
        } else {
          configuration = rule.config
        }

        const isXendit =
          (policyType === 'pricing' && rule.config.provider === 'xendit') ||
          policyType === 'xendit'
        const backendPolicyType = isXendit ? 'xendit' : policyType === 'pricing' ? 'accounting' : policyType

        policyRequests.push({
          name: policyName,
          policy_type: backendPolicyType,
          configuration: configuration,
          endpoint_id: '', // Will be set by caller
        })
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

  const validateXenditForm = (formData: XenditFormData): boolean => {
    if (formData.tiers.length === 0) return false
    return formData.tiers.every((tier) => {
      const nameValid = tier.name.trim().length > 0
      const unitsValid = parseInt(tier.units) > 0
      const priceValid = parseFloat(tier.price) > 0
      return nameValid && unitsValid && priceValid
    })
  }

  const validatePolicyForm = (policyType: string, formData: PolicyFormData): boolean => {
    switch (policyType) {
      case 'access':
        return validateAuthorizationForm(formData as AuthorizationFormData)
      case 'rate_limit':
        return validateRateLimitForm(formData as RateLimitFormData)
      case 'pricing':
        return validatePricingForm(formData as PricingFormData)
      case 'xendit':
        return validateXenditForm(formData as XenditFormData)
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
    createXenditPolicy,
    transformPolicyRules,
    validatePolicyForm,
    validateAuthorizationForm,
    validateRateLimitForm,
    validatePricingForm,
    validateXenditForm,
    processUserList,
    generatePolicyName,
    reset,
  }
}
