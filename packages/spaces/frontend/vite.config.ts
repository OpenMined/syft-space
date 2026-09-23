import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  base: './',
  plugins: [
    tailwindcss(),
    vue(),
    vueJsx(),
    // Dev-only: parts of the devtools plugin apply to builds too, and none of
    // it is any use in the image we ship.
    ...(command === 'serve' ? [vueDevTools({ launchEditor: 'cursor' })] : []),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
}))
