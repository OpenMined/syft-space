import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'

// The control API serves this build's `dist/` at /ui — see control/app.py.
// There is only ever one screen (one session names exactly one target), so
// there is no router: the session token arrives as an ordinary `?token=`
// query param, read once in main.ts and stored, and /ui is the only
// server-known path this app needs.
export default defineConfig({
  base: '/ui/',
  plugins: [tailwindcss(), vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // The dev server only ever serves this app; the API it calls is the
    // control API's own process. BENCH_CONTROL_URL lets it point at
    // wherever that happens to be running instead of always localhost:8200.
    proxy: {
      '/console': process.env.BENCH_CONTROL_URL || 'http://localhost:8200',
    },
  },
})
