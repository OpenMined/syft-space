import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from '@/App.vue'
import router from '@/router'
import '@/style.css'

// The flash-free page theme is set pre-paint by the inline script in index.html
// (data-theme on <html>); useTheme takes over reactively after mount.

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
