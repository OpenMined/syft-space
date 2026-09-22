import type { Component } from 'vue'
import { RotateCw, Wallet } from 'lucide-vue-next'
import type { SpaceConditionResponse, SpaceConditionType } from '@/lib/types'

/**
 * Per-condition presentation and remedy. Rendering keys off this map, never
 * off `type ===` checks in components — a new condition is one entry here.
 *
 * `fix` matters as much as the label: a restart re-reads the same Secret, so
 * only a re-apply can resolve wallet_stale. Offering the wrong button would
 * clear the badge over a space that is still wrong.
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
