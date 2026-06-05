import { ref } from 'vue'
import { policiesApi } from '@/api/policies/policies'
import { walletsApi } from '@/api/endpoints/wallets'
import type { CreatePolicyRequest } from '@/api/types'

export interface PolicyRules {
  access: Array<{ id: string; config: Record<string, unknown> }>
  rate_limit: Array<{ id: string; config: Record<string, unknown> }>
  pricing: Array<{ id: string; config: Record<string, unknown> }>
  pii_filter?: Array<{ id: string; config: Record<string, unknown> }>
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
  note: string
}

export type PolicyFormData =
  | AuthorizationFormData
  | RateLimitFormData
  | PricingFormData
  | PiiFilterFormData

const POLICY_DISPLAY_NAMES: Record<string, string> = {
  access: 'Authorization',
  rate_limit: 'Rate Limiter',
  pricing: 'Pricing',
  pii_filter: 'PII Filter',
}

const RATE_LIMIT_UNIT_MAP: Record<string, string> = {
  second: 's',
  minute: 'm',
  hour: 'h',
}

const processUserList = (users: string): string[] =>
  users
    .split(',')
    .map((u) => u.trim())
    .filter((u) => u.length > 0)

const generatePolicyName = (
  policyType: string,
  formData: PolicyFormData,
  endpointName: string,
  ruleIndex: number = 1,
): string => {
  const displayName = POLICY_DISPLAY_NAMES[policyType] ?? policyType
  const baseName = formData.note || `${displayName} Rule #${ruleIndex}`
  return `${baseName} for ${endpointName}`
}

const createPricingConfiguration = (
  price: string | number,
  userType: 'all' | 'specific',
  users: string = '',
): Record<string, unknown> => ({
  price: typeof price === 'string' ? parseFloat(price) : price,
  applied_to: userType === 'specific' ? processUserList(users) : ['*'],
})

const createAuthorizationPolicy = async (
  formData: AuthorizationFormData,
  endpointId: string,
  endpointName: string,
  ruleIndex: number = 1,
) => {
  const userList = processUserList(formData.users)
  const configuration =
    formData.ruleType === 'allow'
      ? { allowed_users: userList, denied_users: [] }
      : { allowed_users: [], denied_users: userList }

  return policiesApi.create({
    name: generatePolicyName('access', formData, endpointName, ruleIndex),
    policy_type: 'access',
    configuration,
    endpoint_id: endpointId,
  })
}

const createRateLimitPolicy = async (
  formData: RateLimitFormData,
  endpointId: string,
  endpointName: string,
  ruleIndex: number = 1,
) => {
  const backendUnit = RATE_LIMIT_UNIT_MAP[formData.windowUnit] || 'm'
  return policiesApi.create({
    name: generatePolicyName('rate_limit', formData, endpointName, ruleIndex),
    policy_type: 'rate_limit',
    configuration: {
      limit: `${formData.limit}/${backendUnit}`,
      scope: formData.scope === 'per user' ? 'per_user' : 'global',
    },
    endpoint_id: endpointId,
  })
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

  return policiesApi.create({
    name: generatePolicyName('pricing', formData, endpointName, ruleIndex),
    policy_type: 'mpp_per_request',
    configuration: createPricingConfiguration(formData.price, formData.userType, formData.users),
    endpoint_id: endpointId,
    wallet_id: mppWallet.id,
  })
}

const createPiiFilterPolicy = async (
  formData: PiiFilterFormData,
  endpointId: string,
  endpointName: string,
  ruleIndex: number = 1,
) =>
  policiesApi.create({
    name: generatePolicyName('pii_filter', formData, endpointName, ruleIndex),
    policy_type: 'pii_filter',
    configuration: {},
    endpoint_id: endpointId,
  })

const validateAuthorizationForm = (formData: AuthorizationFormData): boolean =>
  processUserList(formData.users).length > 0

const validateRateLimitForm = (formData: RateLimitFormData): boolean => {
  const limitStr = String(formData.limit).trim()
  return limitStr !== '' && Number(limitStr) > 0
}

const validatePricingForm = (formData: PricingFormData): boolean => {
  const price = parseFloat(formData.price)
  return !isNaN(price) && price >= 0
}

export function usePolicyCreation() {
  const isCreating = ref(false)
  const creationError = ref<string | null>(null)

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
      switch (policyType) {
        case 'access':
          return await createAuthorizationPolicy(
            formData as AuthorizationFormData,
            endpointId,
            endpointName,
            ruleIndex,
          )
        case 'rate_limit':
          return await createRateLimitPolicy(
            formData as RateLimitFormData,
            endpointId,
            endpointName,
            ruleIndex,
          )
        case 'pricing':
          return await createPricingPolicy(
            formData as PricingFormData,
            endpointId,
            endpointName,
            ruleIndex,
          )
        case 'pii_filter':
          return await createPiiFilterPolicy(
            formData as PiiFilterFormData,
            endpointId,
            endpointName,
            ruleIndex,
          )
        default:
          throw new Error(`Unsupported policy type: ${policyType}`)
      }
    } catch (error) {
      creationError.value = error instanceof Error ? error.message : 'Unknown error occurred'
      throw error
    } finally {
      isCreating.value = false
    }
  }

  const transformPolicyRules = async (
    policyRules:
      | Record<string, Array<{ id: string; config: Record<string, unknown> }>>
      | PolicyRules,
    endpointName: string,
  ): Promise<CreatePolicyRequest[]> => {
    const policyRequests: CreatePolicyRequest[] = []
    const implementedPolicies = ['access', 'rate_limit', 'pricing', 'pii_filter']

    for (const [policyType, rules] of Object.entries(policyRules)) {
      if (!implementedPolicies.includes(policyType)) continue

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
          configuration =
            rule.config.ruleType === 'allow'
              ? { allowed_users: userList, denied_users: [] }
              : { allowed_users: [], denied_users: userList }
        } else if (policyType === 'rate_limit') {
          const backendUnit = RATE_LIMIT_UNIT_MAP[rule.config.windowUnit as string] || 'm'
          configuration = {
            limit: `${rule.config.limit}/${backendUnit}`,
            scope: rule.config.scope === 'per user' ? 'per_user' : 'global',
          }
        } else if (policyType === 'pricing') {
          walletId = rule.config.walletId as string | undefined
          const walletType = rule.config.walletType as string | undefined
          const explicitPolicyType = rule.config.policyType as
            | 'mpp_per_request'
            | 'xendit_per_request'
            | 'stripe_per_request'
            | 'mpp_per_document'
            | 'xendit_per_document'
            | 'stripe_per_document'
            | undefined
          // Default when no explicit type: derive from wallet type, defaulting
          // to per-request charging (the most common case).
          const defaultPolicyType =
            walletType === 'mpp'
              ? 'mpp_per_request'
              : walletType === 'stripe'
                ? 'stripe_per_request'
                : 'xendit_per_request'
          backendPolicyType = explicitPolicyType ?? defaultPolicyType

          const userType = rule.config.userType as 'all' | 'specific'
          const users = rule.config.users as string
          const appliedTo = userType === 'all' ? ['*'] : processUserList(users)

          configuration = {
            price: parseFloat(rule.config.price as string) || 0,
            applied_to: appliedTo,
          }
        } else if (policyType === 'pii_filter') {
          configuration = {}
        } else {
          configuration = rule.config
        }

        const request: CreatePolicyRequest = {
          name: policyName,
          policy_type: backendPolicyType,
          configuration,
          endpoint_id: '',
        }

        if (walletId) {
          request.wallet_id = walletId
        }

        policyRequests.push(request)
      }
    }

    return policyRequests
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
        return true
      default:
        return false
    }
  }

  return {
    isCreating,
    creationError,
    createPolicy,
    transformPolicyRules,
    validatePolicyForm,
  }
}
