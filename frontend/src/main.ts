import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from '@/App.vue'
import router from '@/router'
import { initializeCollectiveMode } from '@/composables/useCollectiveMode'
import { initSentry, setSentryTag } from '@/lib/sentry'
import { initPosthog, getPosthogSessionId } from '@/lib/posthog'
import '@/style.css'

// The app uses hash history, so a query placed before the hash
// (e.g. `/?collective=collective-m`) never reaches the router guard.
// Pick the collective mode up from the pre-hash query string here so both
// `/?collective=...` and `/#/?collective=...` boot the same way.
const bootParams = new URLSearchParams(window.location.search)
const bootCollective = bootParams.get('collective')
if (bootCollective) {
  initializeCollectiveMode(bootCollective)
}

const app = createApp(App)

const pinia = createPinia()
app.use(pinia)

app.use(router)

initSentry(app, router)
initPosthog()
setSentryTag('posthog_session_id', getPosthogSessionId())

app.mount('#app')
