import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from '@/App.vue'
import router from '@/router'
import { initSentry, setSentryTag } from '@/lib/sentry'
import { initPosthog, getPosthogSessionId } from '@/lib/posthog'
import '@/style.css'
const app = createApp(App)

const pinia = createPinia()
app.use(pinia)

app.use(router)

initSentry(app, router)
initPosthog()
setSentryTag('posthog_session_id', getPosthogSessionId())

app.mount('#app')
