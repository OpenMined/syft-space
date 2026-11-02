import { ref } from 'vue'
import { toast } from 'vue-sonner'
import { endpointsApi } from '@/api/endpoints/endpoints'

/** An endpoint to send back to the Hub where it is already listed. */
export interface RepublishTarget {
  slug: string
  name: string
  published_to?: string[]
}

/**
 * Republish endpoints to the marketplaces they are already on.
 *
 * One request per endpoint, one toast for the batch. `republish` returns
 * the targets that failed so a caller can keep them pending for a retry.
 */
export function useRepublish() {
  const isRepublishing = ref(false)

  const republish = async (targets: RepublishTarget[]): Promise<RepublishTarget[]> => {
    isRepublishing.value = true
    const failed: RepublishTarget[] = []
    try {
      for (const target of targets) {
        try {
          await endpointsApi.publish(
            target.slug,
            target.published_to?.length
              ? { marketplace_ids: target.published_to }
              : { publish_to_all_marketplaces: true },
          )
        } catch (err) {
          console.error('Failed to republish endpoint:', err)
          failed.push(target)
        }
      }
    } finally {
      isRepublishing.value = false
    }

    if (failed.length === 0) {
      toast.success(
        targets.length === 1
          ? `"${targets[0]?.name}" republished`
          : `${targets.length} APIs republished`,
      )
    } else {
      toast.error(`Failed to republish: ${failed.map((t) => t.name).join(', ')}`)
    }
    return failed
  }

  return { isRepublishing, republish }
}
