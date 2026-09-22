import type { Component } from 'vue'
import { RotateCw, Wallet } from 'lucide-vue-next'
import type { SpaceConditionResponse, SpaceConditionType } from '@/lib/types'

/**
 * Per-condition presentation and remedy; components render off this map, not
 * off `type ===`. `fix` carries the backend's clearing rule — a restart
 * re-reads the same Secret, so only a re-apply resolves wallet_stale.
 */
export interface SpaceConditionMeta {
  label: string
  icon: Component
  fix: 'restart' | 'reapply-wallet'
}

export const SPACE_CONDITION_META: Record<SpaceConditionType, SpaceConditionMeta> = {
  restart_required: { label: 'restart required', icon: RotateCw, fix: 'restart' },
  wallet_stale: { label: 'wallet out of date', icon: Wallet, fix: 'reapply-wallet' },
}

export function hasCondition(
  conditions: SpaceConditionResponse[],
  type: SpaceConditionType,
): boolean {
  return conditions.some((c) => c.type === type)
}
