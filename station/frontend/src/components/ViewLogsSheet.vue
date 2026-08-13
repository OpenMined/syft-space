<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import {
  Check,
  Copy,
  Maximize2,
  Minimize2,
  Pause,
  PauseCircle,
  Play,
  RefreshCw,
  ScrollText,
  WrapText,
} from 'lucide-vue-next'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import HealthBadge from '@/components/HealthBadge.vue'
import { Button } from '@/components/ui/button'
import { spacesApi } from '@/api/endpoints/spaces'
import { ApiError } from '@/api/client'
import type { Space } from '@/lib/types'

const props = defineProps<{
  space: Space | null
  open: boolean
}>()

const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const POLL_MS = 3000

// A snapshot of the pod's last N log lines (GET /spaces/{id}/logs). "Follow"
// re-fetches that snapshot every few seconds — a bounded poll, not a live
// stream — replacing the tail each time. `live` = follow mode is on.
const lines = ref<string[]>([])
const loading = ref(false)
const error = ref('')
const live = ref(false)
const wrap = ref(true)
const expanded = ref(false)
const copied = ref(false)
const updatedAt = ref(0)
const now = ref(0)
const logBox = ref<HTMLElement | null>(null)

let pollTimer: ReturnType<typeof setInterval> | undefined
let clockTimer: ReturnType<typeof setInterval> | undefined

const paused = computed(() => props.space?.health === 'paused')

const updatedAgo = computed(() => {
  if (!updatedAt.value) return ''
  const s = Math.max(0, Math.round((now.value - updatedAt.value) / 1000))
  return s < 2 ? 'just now' : `${s}s ago`
})

/** A log line split into its (dim) timestamp and level-colored remainder. */
function parse(line: string): { time: string; rest: string; level: string } {
  const m = line.match(/^(\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d(?:\.\d+)?Z?)\s*(.*)$/)
  const time = m ? m[1]! : ''
  const rest = m ? m[2]! : line
  const lv = rest.match(/\b(CRITICAL|ERROR|WARNING|WARN|DEBUG|INFO)\b/)
  return { time, rest, level: lv ? lv[1]! : '' }
}

function levelClass(level: string): string {
  // OMDS palette, light steps for the always-dark terminal (error = red,
  // warning = gold, matching the app's status semantics).
  if (level === 'ERROR' || level === 'CRITICAL') return 'text-[color:var(--color-red-400)]'
  if (level === 'WARNING' || level === 'WARN') return 'text-[color:var(--color-gold-400)]'
  if (level === 'DEBUG') return 'opacity-60'
  return ''
}

function atBottom(): boolean {
  const el = logBox.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < 40
}

async function load() {
  if (!props.space) return
  const stick = atBottom()
  loading.value = true
  error.value = ''
  try {
    const res = await spacesApi.logs(props.space.id)
    lines.value = res.lines
    updatedAt.value = Date.now()
    now.value = Date.now()
    if (stick) {
      void nextTick(() => {
        if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
      })
    }
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Could not read the logs'
    lines.value = []
    live.value = false
  } finally {
    loading.value = false
  }
}

function stopPoll() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = undefined
}

watch(live, (on) => {
  stopPoll()
  if (on) {
    void load()
    pollTimer = setInterval(load, POLL_MS)
  }
})

async function copyLogs() {
  try {
    await navigator.clipboard.writeText(lines.value.join('\n'))
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    /* clipboard blocked — no-op */
  }
}

watch(
  () => props.open,
  (isOpen) => {
    stopPoll()
    if (clockTimer) clearInterval(clockTimer)
    live.value = false
    if (isOpen && props.space && !paused.value) {
      void load()
      clockTimer = setInterval(() => (now.value = Date.now()), 1000)
    } else {
      lines.value = []
      error.value = ''
    }
  },
)

onUnmounted(() => {
  stopPoll()
  if (clockTimer) clearInterval(clockTimer)
})
</script>

<template>
  <Sheet :open="open" @update:open="(v: boolean) => emit('update:open', v)">
    <SheetContent
      side="right"
      class="flex w-full flex-col gap-0 p-0 transition-[max-width] duration-200"
      :class="expanded ? 'sm:max-w-5xl' : 'sm:max-w-2xl'"
    >
      <SheetHeader v-if="space" class="px-4 pt-4 pb-3">
        <SheetTitle class="flex items-center gap-2 pr-8">
          <ScrollText class="h-4 w-4 shrink-0" />
          Logs — {{ space.name }}
          <HealthBadge :health="space.health" />
        </SheetTitle>
        <SheetDescription>
          A snapshot of the space's most recent logs, read live from the pod — not stored.
        </SheetDescription>
      </SheetHeader>

      <!-- Control toolbar -->
      <div
        v-if="space && !paused"
        class="flex items-center gap-1 border-y bg-muted/30 px-3 py-1.5"
      >
        <Button
          :variant="live ? 'selected' : 'ghost'"
          size="sm"
          class="h-7 gap-1.5"
          @click="live = !live"
        >
          <span
            v-if="live"
            class="h-1.5 w-1.5 animate-pulse rounded-full bg-success"
          />
          <component :is="live ? Pause : Play" v-else class="h-3.5 w-3.5" />
          {{ live ? 'Following' : 'Follow' }}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          class="h-7 gap-1.5"
          title="Refresh"
          :disabled="live || loading"
          @click="load"
        >
          <RefreshCw class="h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" />
          Refresh
        </Button>
        <div class="mx-1 h-4 w-px bg-border" />
        <Button
          :variant="wrap ? 'selected' : 'ghost'"
          size="sm"
          class="h-7 gap-1.5"
          title="Wrap long lines"
          @click="wrap = !wrap"
        >
          <WrapText class="h-3.5 w-3.5" />
          Wrap
        </Button>
        <Button
          variant="ghost"
          size="sm"
          class="h-7 gap-1.5"
          title="Copy all"
          @click="copyLogs"
        >
          <component :is="copied ? Check : Copy" class="h-3.5 w-3.5" />
          {{ copied ? 'Copied' : 'Copy' }}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          class="ml-auto h-7 w-7"
          :title="expanded ? 'Collapse' : 'Expand'"
          @click="expanded = !expanded"
        >
          <component :is="expanded ? Minimize2 : Maximize2" class="h-3.5 w-3.5" />
        </Button>
      </div>

      <!-- Body -->
      <div v-if="space" class="min-h-0 flex-1 px-4 py-3">
        <div
          v-if="paused"
          class="flex h-full flex-col items-center justify-center gap-2 rounded-md border border-dashed text-center text-sm text-muted-foreground"
        >
          <PauseCircle class="h-6 w-6" />
          <p class="font-medium text-foreground">Space is paused — no logs to show</p>
          <p class="max-w-xs text-xs">
            Logs are available while the space is running. Start the space to read them again.
          </p>
        </div>

        <!-- always-dark: a terminal stays dark in both page themes (otherwise it
             inverts to white in dark mode and the light level colours vanish). -->
        <div
          v-else
          ref="logBox"
          data-section="always-dark"
          class="h-full overflow-auto rounded-md bg-muted p-3 font-mono text-[11px] leading-relaxed text-foreground"
        >
          <p v-if="error" class="text-[color:var(--color-red-400)]">{{ error }}</p>
          <p v-else-if="loading && !lines.length" class="text-foreground/60">Loading logs…</p>
          <p v-else-if="!lines.length" class="text-foreground/60">No logs yet.</p>
          <div
            v-for="(line, i) in lines"
            :key="i"
            :class="[
              wrap ? 'whitespace-pre-wrap break-all' : 'whitespace-pre',
              levelClass(parse(line).level),
            ]"
          >
            <template v-if="parse(line).time">
              <span class="text-foreground/40">{{ parse(line).time }}</span>
              {{ ' ' + parse(line).rest }}
            </template>
            <template v-else>{{ line }}</template>
          </div>
        </div>
      </div>

      <!-- Status footer -->
      <div
        v-if="space && !paused"
        class="flex items-center gap-2 border-t px-4 py-1.5 text-xs text-muted-foreground"
      >
        <span v-if="live" class="flex items-center gap-1.5">
          <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-success" />
          following
        </span>
        <span>{{ lines.length }} line{{ lines.length === 1 ? '' : 's' }}</span>
        <span v-if="updatedAgo" class="ml-auto">updated {{ updatedAgo }}</span>
      </div>
    </SheetContent>
  </Sheet>
</template>
