import posthog from 'posthog-js'
import type { CaptureResult } from 'posthog-js'

const POSTHOG_API_KEY = 'phc_vKWFOKM4ZUhCrwrgm1JZdLhT9IY3xmL2G9SJbNNkOf7'
const POSTHOG_HOST = 'https://us.i.posthog.com'

export function getPosthogSessionId(): string {
  return posthog.get_session_id()
}

export function setPosthogDiagnosticsEnabled(enabled: boolean) {
  if (enabled) {
    posthog.opt_in_capturing()
  } else {
    posthog.opt_out_capturing()
  }
}

export function initPosthog() {
  posthog.init(POSTHOG_API_KEY, {
    api_host: POSTHOG_HOST,
    defaults: '2026-01-30',
    opt_out_capturing_by_default: true,
    before_send: (event: CaptureResult | null): CaptureResult | null => {
      if (event?.properties?.$current_url) {
        const parsed = new URL(event.properties.$current_url)
        if (parsed.hash) {
          event.properties.$pathname = parsed.pathname + parsed.hash
        }
      }
      return event
    },
  })
}
