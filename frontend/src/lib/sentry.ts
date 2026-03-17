import * as Sentry from '@sentry/vue'
import type { App } from 'vue'
import type { Router } from 'vue-router'

const SENTRY_DSN =
  'https://73a207ffa24b9fa3b6791a431216089f@o4511056487317504.ingest.us.sentry.io/4511056489021440'

let diagnosticsEnabled = false

export function setDiagnosticsEnabled(enabled: boolean) {
  diagnosticsEnabled = enabled
}

export function initSentry(app: App, router: Router) {
  Sentry.init({
    app,
    dsn: SENTRY_DSN,
    integrations: [Sentry.browserTracingIntegration({ router }), Sentry.replayIntegration()],
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 1.0,
    beforeSend(event) {
      return diagnosticsEnabled ? event : null
    },
    beforeSendTransaction(event) {
      return diagnosticsEnabled ? event : null
    },
    environment: import.meta.env.MODE,
    release: `syft-space-frontend@0.0.0`,
  })
}
