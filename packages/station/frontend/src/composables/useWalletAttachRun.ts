import { ref } from 'vue'
import { toast } from 'vue-sonner'
import { ApiError } from '@/api/client'
import type { Space } from '@/lib/types'
import { useStationStore } from '@/stores/station'

export interface AttachRunState {
  state: 'queued' | 'attaching' | 'failed'
  detail?: string
}

// Module-level, not per-component: a run started from the wallet-save dialog
// renders in the panel underneath it, and two runs can never overlap.
const progress = ref<Record<string, AttachRunState>>({})
const running = ref(false)

/** Put spaces on the wallet one at a time; a failure never stops the rest. */
export function useWalletAttachRun() {
  const station = useStationStore()

  async function run(spaces: Space[]): Promise<{ attached: number; failed: number }> {
    const newlyAttached = spaces.some((s) => s.walletStatus !== 'attached')
    running.value = true
    progress.value = Object.fromEntries(
      spaces.map((s) => [s.id, { state: 'queued' } as AttachRunState]),
    )
    let failed = 0
    // Sequential: each attach restarts a space, so a parallel run would take
    // the whole station down at once.
    for (const space of spaces) {
      progress.value = { ...progress.value, [space.id]: { state: 'attaching' } }
      try {
        // Already on the wallet = this is a refresh of facts it changed.
        await station.attachWallet(space.id, space.walletStatus === 'attached')
        const done = { ...progress.value }
        delete done[space.id]
        progress.value = done
      } catch (error) {
        failed += 1
        progress.value = {
          ...progress.value,
          [space.id]: {
            state: 'failed',
            detail: error instanceof ApiError ? error.message : 'Attaching failed',
          },
        }
      }
    }
    running.value = false

    const attached = spaces.length - failed
    if (failed === 0) {
      toast.success(`${attached} space${attached === 1 ? '' : 's'} updated`, {
        // Being on the wallet doesn't price anything — say so where the
        // admin can act on it rather than in the confirm they clicked past.
        description: newlyAttached
          ? 'Their owners still need a paid policy on their endpoints, and to publish again, before they earn.'
          : undefined,
      })
    } else if (attached === 0) toast.error('Could not update any space')
    else toast.warning(`${attached} updated, ${failed} failed — the rest stay flagged`)
    return { attached, failed }
  }

  return { progress, running, run }
}
