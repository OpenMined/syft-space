import type { Component } from 'vue'
import { Rocket, Trash2 } from 'lucide-vue-next'
import type { RequestType } from '@/lib/types'

/**
 * Per-type presentation. Rendering keys off this map, never off `type ===`
 * checks scattered through components — a new request type is one entry here
 * (open for extension, closed for modification).
 */
export interface RequestTypeMeta {
  /** The request itself, e.g. an admin queue heading. */
  label: string
  /** Past-tense outcome once approved, for history rows. */
  approvedLabel: string
  icon: Component
}

export const REQUEST_TYPE_META: Record<RequestType, RequestTypeMeta> = {
  create_space: { label: 'Space request', approvedLabel: 'Space created', icon: Rocket },
  delete_space: { label: 'Deletion request', approvedLabel: 'Space removed', icon: Trash2 },
}
