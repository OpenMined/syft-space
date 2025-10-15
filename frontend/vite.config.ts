import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  base: '/syftai-server/',
  plugins: [tailwindcss(), vue(), vueJsx(), vueDevTools({ launchEditor: 'cursor' })],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
