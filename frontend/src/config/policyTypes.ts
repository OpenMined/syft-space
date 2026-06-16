import { Shield, Gauge, DollarSign, UserCheck } from 'lucide-vue-next'
import type { Component } from 'vue'

export type PolicyTypeId = 'access' | 'rate_limit' | 'pricing' | 'pii_filter' | 'human_in_the_loop'

export type PaymentPolicyType =
  | 'mpp_per_request'
  | 'xendit_per_request'
  | 'stripe_per_request'
  | 'mpp_per_document'
  | 'xendit_per_document'
  | 'stripe_per_document'

export interface PolicyConfig {
  id: string
  [key: string]: unknown
}

export interface PolicyRule {
  id: string
  config: PolicyConfig
  isEditing: boolean
}

export interface PolicyType {
  id: PolicyTypeId
  name: string
  label: string
  description: string
  icon: Component
  color: string
}

export type PolicyRulesRecord = Record<PolicyTypeId, PolicyRule[]>

export const POLICY_TYPES: PolicyType[] = [
  {
    id: 'access',
    name: 'Access Control',
    label: 'Who can access?',
    description: 'Control who can use your content - everyone, specific users, or by invitation',
    icon: Shield,
    color: 'blue',
  },
  {
    id: 'rate_limit',
    name: 'Usage Limits',
    label: 'Prevent overuse',
    description: 'Limit how many queries each user can make per day or hour',
    icon: Gauge,
    color: 'green',
  },
  {
    id: 'pricing',
    name: 'Pricing',
    label: 'Set your price',
    description: 'Charge per query or make it free - you decide',
    icon: DollarSign,
    color: 'yellow',
  },
  {
    id: 'human_in_the_loop',
    name: 'Human in the Loop',
    label: 'Require human approval',
    description: 'Hold replies for your review before they are sent',
    icon: UserCheck,
    color: 'purple',
  },
]

export const getPolicyTypeLabel = (type: string): string => {
  switch (type) {
    case 'access':
      return 'Access Control'
    case 'rate_limit':
      return 'Usage Limits'
    case 'pricing':
      return 'Pricing'
    case 'pii_filter':
      return 'PII Filter'
    case 'human_in_the_loop':
      return 'Human in the Loop'
    default:
      return 'Policy'
  }
}

export const createEmptyPolicyRules = (): PolicyRulesRecord => ({
  access: [],
  rate_limit: [],
  pricing: [],
  pii_filter: [],
  human_in_the_loop: [],
})

export const generateRuleId = (): string => {
  return 'rule_' + Math.random().toString(36).slice(2, 11)
}

export const getRuleSummary = (policyId: PolicyTypeId, config: PolicyConfig): string => {
  switch (policyId) {
    case 'access':
      if (!config.users) return 'No users configured'
      {
        const ruleType = config.ruleType === 'allow' ? 'Allow' : 'Deny'
        const userList = (config.users as string)
          .split(',')
          .map((u) => u.trim())
          .filter((u) => u)
        if (userList.length === 0) {
          return 'No users configured'
        }
        return `${ruleType} access for ${userList.join(', ')}`
      }

    case 'rate_limit':
      if (!config.limit) return 'No limit configured'
      {
        const scope = config.scope === 'global' ? 'for full API' : 'per user'
        return `${config.limit} requests per ${config.windowUnit} ${scope}`
      }

    case 'pricing':
      if (config.price === undefined || config.price === null || config.price === '')
        return 'No price configured'
      {
        const price = parseFloat(config.price as string)

        if (isNaN(price)) return 'Invalid price configured'

        if (price === 0) {
          if (config.userType === 'all') {
            return 'Free for all users'
          } else {
            const userList = config.users
              ? (config.users as string)
                  .split(',')
                  .map((u) => u.trim())
                  .filter((u) => u)
              : []
            if (userList.length === 0) {
              return 'Free for specific users (none configured)'
            }
            return `Free for ${userList.join(', ')}`
          }
        }

        const currency = (config.walletCurrency as string) || 'USD'
        const formattedPrice = price.toFixed(8).replace(/\.?0+$/, '')
        if (config.userType === 'all') {
          return `${formattedPrice} ${currency} per query for all users`
        } else {
          const userList = config.users
            ? (config.users as string)
                .split(',')
                .map((u) => u.trim())
                .filter((u) => u)
            : []
          if (userList.length === 0) {
            return `${formattedPrice} ${currency} per query for specific users (none configured)`
          }
          return `${formattedPrice} ${currency} per query for ${userList.join(', ')}`
        }
      }

    case 'pii_filter':
      return 'AI-powered PII redaction enabled'

    case 'human_in_the_loop': {
      const scope =
        config.appliesTo === 'specific'
          ? (() => {
              const userList = config.users
                ? (config.users as string)
                    .split(',')
                    .map((u) => u.trim())
                    .filter((u) => u)
                : []
              return userList.length > 0 ? userList.join(', ') : 'specific users (none configured)'
            })()
          : 'all users'
      return config.approvalMode === 'ai_mediated'
        ? `AI-mediated approval for ${scope}`
        : `Always require human approval for ${scope}`
    }

    default:
      return 'Rule configured'
  }
}
