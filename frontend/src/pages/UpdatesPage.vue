<template>
  <div class="flex min-h-screen w-full flex-row overflow-hidden select-none">
    <!-- Left panel - Visual -->
    <div class="relative flex w-full flex-col justify-between p-8 md:w-2/5">
      <BackgroundGradients class="absolute top-0 left-0 h-full w-full" />
      <div class="absolute top-0 left-0 h-full w-full opacity-10">
        <svg width="100%" height="100%" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
              <path d="M 10 0 L 0 0 0 10" fill="none" stroke="white" stroke-width="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
      </div>

      <div class="relative z-10">
        <!-- Logo -->
        <div class="flex items-center">
          <IconGhost :width="60" :height="60" />
          <div class="ml-3">
            <h1 class="text-3xl font-bold text-white">Syft Space</h1>
          </div>
        </div>

        <p class="mt-2 text-white/80">
          A space where your documents and AI models are ready to help the world — without leaving
          home. Open the door on your terms, set a fair price, and see your contribution recognized.
        </p>
      </div>

      <div class="relative z-10 mt-auto">
        <div class="flex items-center text-sm text-white/90">
          <div class="flex flex-col">
            <span>Current Version</span>
            <span class="font-mono font-bold">
              {{ state.currentVersion }}
            </span>
          </div>
          <template v-if="state.updateWindowType === UpdateType.available">
            <ArrowRight class="mx-4 text-white/50" />
            <div class="flex flex-col">
              <span>New Version</span>
              <span class="font-mono font-bold">{{ state.version }}</span>
            </div>
          </template>
        </div>
      </div>
      <div data-tauri-drag-region class="absolute top-0 right-0 bottom-0 left-0 z-20"></div>
    </div>

    <!-- Right panel - Content -->
    <div class="bg-primary-foreground flex max-h-screen w-full flex-col md:w-3/5">
      <div class="relative flex items-start justify-between border-b p-6">
        <div data-tauri-drag-region class="absolute top-0 right-0 bottom-0 left-0 z-20"></div>
        <Transition
          enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="opacity-0 translate-y-2"
          enter-to-class="opacity-100 translate-y-0"
          leave-active-class="transition-all duration-200 ease-in"
          leave-from-class="opacity-100 translate-y-0"
          leave-to-class="opacity-0 -translate-y-2"
          mode="out-in"
        >
          <div :key="state.updateWindowType">
            <div v-if="state.updateWindowType === UpdateType.available" class="flex items-center">
              <div
                class="mr-3 flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30"
              >
                <Info class="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h3 class="text-primary text-xl font-bold">Update Available</h3>
                <p class="text-muted-foreground">Syft Space {{ state.version }} is ready to install</p>
              </div>
            </div>

            <div v-if="state.updateWindowType === UpdateType.none" class="flex items-center">
              <div
                class="mr-3 flex h-10 w-10 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30"
              >
                <CheckCircle class="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <h3 class="text-primary text-xl font-bold">You're Up To Date</h3>
                <p class="text-muted-foreground">
                  Syft Space {{ state.currentVersion }} is the latest version
                </p>
              </div>
            </div>

            <div v-if="state.updateWindowType === UpdateType.error" class="flex items-center">
              <div
                class="mr-3 flex h-10 w-10 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30"
              >
                <X class="h-5 w-5 text-red-600 dark:text-red-400" />
              </div>
              <div>
                <h3 class="text-primary text-xl font-bold">Update Check Failed</h3>
                <p class="text-muted-foreground">We couldn't check for updates</p>
              </div>
            </div>

            <div v-if="state.updateWindowType === UpdateType.downloading" class="flex items-center">
              <div
                class="mr-3 flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30"
              >
                <Download class="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h3 class="text-primary text-xl font-bold">Downloading Update</h3>
                <p class="text-muted-foreground">Syft Space {{ state.version }} is being downloaded</p>
              </div>
            </div>

            <div v-if="state.updateWindowType === UpdateType.failed" class="flex items-center">
              <div
                class="mr-3 flex h-10 w-10 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30"
              >
                <X class="h-5 w-5 text-red-600 dark:text-red-400" />
              </div>
              <div>
                <h3 class="text-primary text-xl font-bold">Update Failed</h3>
                <p class="text-muted-foreground">We couldn't install the update</p>
              </div>
            </div>

            <div v-if="state.updateWindowType === UpdateType.checking" class="flex items-center">
              <div
                class="mr-3 flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30"
              >
                <RefreshCcw class="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h3 class="text-primary text-xl font-bold">Checking for Updates</h3>
                <p class="text-muted-foreground">Looking for the latest version of Syft Space</p>
              </div>
            </div>
          </div>
        </Transition>
      </div>

      <div
        :class="[
          'flex-1 overflow-y-auto p-6',
          state.updateWindowType === UpdateType.downloading
            ? 'flex flex-col items-center justify-center'
            : '',
        ]"
      >
        <Transition
          enter-active-class="transition-opacity duration-200 ease-out"
          enter-from-class="opacity-0"
          enter-to-class="opacity-100"
          leave-active-class="transition-opacity duration-200 ease-in"
          leave-from-class="opacity-100"
          leave-to-class="opacity-0"
          mode="out-in"
        >
          <div :key="state.updateWindowType" class="w-full">
            <div
              v-if="state.updateWindowType === UpdateType.available && state.releaseNotes"
              class="prose prose-sm dark:prose-invert max-w-none select-auto"
            >
              <VueMarkdown
                :source="state.releaseNotes"
                :options="{ linkify: true, breaks: true }"
                @click="handleMarkdownClick"
              />
            </div>

            <div
              v-if="state.updateWindowType === UpdateType.error && state.error"
              class="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20"
            >
              <p class="break-words text-red-800 dark:text-red-300">
                {{ state.error }}
              </p>
            </div>

            <div
              v-if="state.updateWindowType === UpdateType.failed && state.error"
              class="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20"
            >
              <p class="break-words text-red-800 dark:text-red-300">
                {{ state.error }}
              </p>
            </div>

            <div
              v-if="state.updateWindowType === UpdateType.downloading"
              class="mx-auto w-full max-w-md text-center"
            >
              <div class="relative w-full pt-1">
                <div class="flex h-2 overflow-hidden rounded-full bg-blue-200 dark:bg-blue-900/30">
                  <div
                    class="bg-blue-500 transition-all duration-500 ease-out"
                    :style="{ width: `${animatedProgress}%` }"
                  ></div>
                </div>
              </div>
              <p class="text-muted-foreground mt-4">
                Downloading Syft Space {{ state.version }}... {{ animatedProgress }}%
              </p>
              <div class="mt-6 flex justify-center">
                <div class="animate-spin">
                  <RefreshCcw class="h-6 w-6 text-blue-500" />
                </div>
              </div>
            </div>

            <div
              v-if="state.updateWindowType === UpdateType.none"
              class="overflow-hidden py-6 text-center"
            >
              <Transition
                enter-active-class="transition-transform duration-300"
                enter-from-class="scale-0"
                enter-to-class="scale-100"
                appear
              >
                <div
                  class="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30"
                >
                  <CheckCircle class="h-10 w-10 text-green-600 dark:text-green-400" />
                </div>
              </Transition>
              <h3 class="text-primary mt-6 text-xl font-medium">You're all set!</h3>
              <p class="text-muted-foreground mt-2">
                Syft Space {{ state.currentVersion }} is the latest version available.
              </p>
            </div>

            <div
              v-if="state.updateWindowType === UpdateType.checking"
              class="overflow-hidden py-6 text-center"
            >
              <div class="animate-spin">
                <div
                  class="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30"
                >
                  <RefreshCcw class="h-10 w-10 text-blue-600 dark:text-blue-400" />
                </div>
              </div>
              <h3 class="text-primary mt-6 text-xl font-medium">Checking for updates...</h3>
              <p class="text-muted-foreground mt-2">
                Please wait while we check for the latest version.
              </p>
            </div>
          </div>
        </Transition>
      </div>

      <div data-tauri-drag-region class="flex justify-end gap-3 border-t p-6">
        <Transition
          enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="opacity-0 translate-y-2"
          enter-to-class="opacity-100 translate-y-0"
          leave-active-class="transition-all duration-200 ease-in"
          leave-from-class="opacity-100 translate-y-0"
          leave-to-class="opacity-0 translate-y-2"
          mode="out-in"
        >
          <div
            :key="state.updateWindowType"
            data-tauri-drag-region
            class="flex w-full justify-end gap-3"
          >
            <template v-if="state.updateWindowType === UpdateType.available">
              <Button variant="outline" @click="onLater"> Remind Me Later </Button>
              <Button @click="onUpdate">Update Now</Button>
            </template>

            <template
              v-if="
                [UpdateType.none, UpdateType.error, UpdateType.failed].includes(
                  state.updateWindowType,
                )
              "
            >
              <Button @click="closeHandler">Close</Button>
            </template>

            <Button
              v-if="state.updateWindowType === UpdateType.downloading"
              disabled
              class="cursor-not-allowed opacity-50"
            >
              Downloading...
            </Button>

            <Button
              v-if="state.updateWindowType === UpdateType.checking"
              disabled
              class="cursor-not-allowed opacity-50"
            >
              Checking...
            </Button>
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, watch } from 'vue'
import { ArrowRight, CheckCircle, Download, Info, RefreshCcw, X } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import VueMarkdown from 'vue-markdown-render'
import BackgroundGradients from '@/components/logo/BackgroundGradients.vue'
import IconGhost from '@/components/logo/IconGhost.vue'
import { useOpenPath } from '@/composables/useOpenPath'

enum UpdateType {
  checking = 'checking',
  none = 'none',
  available = 'available',
  downloading = 'downloading',
  error = 'error',
  failed = 'failed',
}

interface UpdateWindowState {
  updateWindowType: UpdateType
  version: string
  currentVersion: string
  releaseNotes: string
  error: string
  progress: number
}

declare global {
  interface Window {
    __TAURI__?: {
      core: {
        invoke: <T>(cmd: string, args?: Record<string, unknown>) => Promise<T>
      }
      webviewWindow: {
        getCurrentWebviewWindow: () => {
          listen: <T>(
            event: string,
            callback: (event: { payload: T }) => void,
          ) => Promise<() => void>
        }
      }
      window: {
        getCurrentWindow: () => {
          close: () => void
        }
      }
      shell: {
        open: (path: string) => Promise<void>
      }
    }
  }
}

const initialState: UpdateWindowState = {
  updateWindowType: UpdateType.checking,
  version: '',
  currentVersion: '',
  releaseNotes: '',
  error: '',
  progress: 0,
}

const state = reactive<UpdateWindowState>({ ...initialState })
const animatedProgress = ref(0)
const { openPath } = useOpenPath()

let unlisten: (() => void) | undefined

watch(
  () => state.updateWindowType,
  (newType) => {
    if (newType === UpdateType.downloading) {
      animatedProgress.value = state.progress
    } else {
      animatedProgress.value = 0
    }
  },
)

watch(
  () => state.progress,
  (newProgress) => {
    if (state.updateWindowType === UpdateType.downloading) {
      animatedProgress.value = newProgress
    }
  },
)

const handleMarkdownClick = (event: MouseEvent) => {
  const target = event.target as HTMLElement
  if (target.tagName === 'A') {
    event.preventDefault()
    const href = target.getAttribute('href')
    if (href) {
      openPath(href)
    }
  }
}

const onUpdate = () => {
  state.updateWindowType = UpdateType.downloading
  if (window.__TAURI__) {
    window.__TAURI__.core.invoke('update_window_response', {
      installUpdate: true,
    })
  }
}

const onLater = () => {
  if (window.__TAURI__) {
    window.__TAURI__.core.invoke('update_window_response', {
      installUpdate: false,
    })
  }
  closeHandler()
}

const closeHandler = () => {
  if (window.__TAURI__) {
    window.__TAURI__.window.getCurrentWindow().close()
  }
}

onMounted(async () => {
  if (window.__TAURI__) {
    // Get initial state
    const initialStateData =
      await window.__TAURI__.core.invoke<UpdateWindowState>('get_window_state')
    Object.assign(state, initialStateData)

    // Listen for further state updates
    const appWebview = window.__TAURI__.webviewWindow.getCurrentWebviewWindow()
    unlisten = await appWebview.listen<UpdateWindowState>('update-window-state', (event) => {
      Object.assign(state, event.payload)
    })
  }
})

onUnmounted(() => {
  if (unlisten) {
    unlisten()
  }
})
</script>

<style>
@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.animate-spin {
  animation: spin 2s linear infinite;
}
</style>
