import type { SlugAvailabilityResponse } from '@/api/types'

/** Why the name cannot be published, or null when every check passed.
 *  A marketplace whose check failed (available === null) does not block. */
export function slugUnavailableReason(response: SlugAvailabilityResponse): string | null {
  if (!response.local_available) {
    return 'You already have an endpoint with this name in this space.'
  }
  const refused = response.marketplaces?.find((m) => m.available === false)
  if (!refused) return null
  return refused.reason ?? 'This name is already taken on SyftHub.'
}
