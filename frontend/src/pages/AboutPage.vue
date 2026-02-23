<template>
  <div class="flex h-screen w-full select-none overflow-hidden">
    <div class="relative flex w-full flex-col items-center justify-center gap-5 p-8">
      <BackgroundGradients class="absolute top-0 left-0 h-full w-full" />
      <div data-tauri-drag-region class="absolute top-0 right-0 bottom-0 left-0 z-0"></div>

      <div data-tauri-drag-region class="relative z-10 flex flex-col items-center">
        <IconGhost :width="72" :height="72" />
        <h1 class="mt-3 text-2xl font-bold text-gray-800">Syft Space</h1>
      </div>

      <div data-tauri-drag-region class="relative z-10 flex flex-col items-center gap-1 text-center text-sm text-gray-500">
        <p>Version {{ version }}</p>
        <p>Built by <span class="font-medium text-gray-700">OpenMined</span></p>
        <a
          href="https://github.com/OpenMined/syft-space"
          class="mt-1 inline-flex items-center gap-1 text-xs text-gray-500 transition-colors hover:text-gray-700"
        >
          <ExternalLink class="h-3 w-3" />
          github.com/OpenMined/syft-space
        </a>
      </div>

      <div class="relative z-10">
        <button
          class="rounded-md border border-gray-400/50 bg-white/40 px-6 py-1.5 text-sm font-medium text-gray-700 backdrop-blur-sm transition-colors hover:bg-white/60"
          @click="closeWindow"
        >
          Close
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ExternalLink } from 'lucide-vue-next'
import BackgroundGradients from '@/components/logo/BackgroundGradients.vue'
import IconGhost from '@/components/logo/IconGhost.vue'

const version = ref('dev')

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const tauri = (window as any).__TAURI__ as
  | {
      core: { invoke: <T>(cmd: string, args?: Record<string, unknown>) => Promise<T> }
      window: { getCurrentWindow: () => { close: () => void } }
    }
  | undefined

onMounted(async () => {
  if (tauri) {
    try {
      version.value = await tauri.core.invoke<string>('plugin:app|version')
    } catch {
      // keep fallback
    }
  }
})

const closeWindow = () => {
  if (tauri) {
    tauri.window.getCurrentWindow().close()
  }
}
</script>
