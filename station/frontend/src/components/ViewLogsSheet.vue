<script setup lang="ts">
import { nextTick, onUnmounted, ref, watch } from 'vue'
import { PauseCircle, ScrollText } from 'lucide-vue-next'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import HealthBadge from '@/components/HealthBadge.vue'
import type { Space } from '@/lib/types'

const props = defineProps<{
  space: Space | null
  open: boolean
}>()

const emit = defineEmits<{ 'update:open': [value: boolean] }>()

// TODO: everything below fabricates a plausible log tail — the station has
// no log endpoint yet. Replace seedLines/liveLine with a real stream (e.g.
// read_namespaced_pod_log via the backend) when it lands.
const lines = ref<string[]>([])
const logBox = ref<HTMLElement | null>(null)
let timer: ReturnType<typeof setInterval> | undefined

function stamp(offsetSeconds = 0): string {
  return new Date(Date.now() - offsetSeconds * 1000).toISOString().replace('T', ' ').slice(0, 19)
}

function slugOf(space: Space): string {
  return space.url.replace('https://', '').split('.')[0] ?? space.name
}

/** Startup tail every pod shows, oldest first. */
function seedLines(space: Space): string[] {
  const slug = slugOf(space)
  const seeded: [number, string][] = [
    [95, 'INFO   uvicorn      Started server process [1]'],
    [94, `INFO   syft         syft-space v${space.version} starting (mode: cluster)`],
    [93, `INFO   syft.vector  connected to shared ChromaDB (database: ${slug})`],
    [92, 'INFO   syft.docling using remote docling-serve'],
  ]
  seeded.push([90, 'INFO   uvicorn      Application startup complete'])
  seeded.push([45, 'INFO   syft.hub     heartbeat ok (next in 60s)'])
  seeded.push([12, 'INFO   uvicorn      GET /healthcheck 200 2ms'])
  if (space.health === 'unhealthy') {
    seeded.push([8, 'ERROR  syft.vector  connection to chroma-shared:8000 timed out (attempt 3)'])
    seeded.push([4, 'WARN   readiness    probe failed (3/3) — pod marked unready'])
  }
  return seeded.map(([ago, msg]) => `${stamp(ago)}  ${msg}`)
}

const HEALTHY_POOL = [
  'INFO   uvicorn      GET /healthcheck 200 2ms',
  'INFO   syft.query   answered query for kim@labmate.org (top_k=8, 412ms)',
  'INFO   syft.ingest  chunked report-q3.pdf → 182 chunks (docling remote)',
  'DEBUG  chromadb     upserted 182 vectors',
  'INFO   syft.hub     heartbeat ok (next in 60s)',
  'INFO   uvicorn      POST /api/v1/query 200 388ms',
]

const UNHEALTHY_POOL = [
  'ERROR  syft.vector  connection to chroma-shared:8000 timed out (retrying)',
  'WARN   readiness    probe failed — pod marked unready',
  'INFO   uvicorn      GET /healthcheck 503 1ms',
]

function appendLine() {
  if (!props.space) return
  const pool = props.space.health === 'unhealthy' ? UNHEALTHY_POOL : HEALTHY_POOL
  const line = pool[Math.floor(Math.random() * pool.length)]
  lines.value.push(`${stamp()}  ${line}`)
  if (lines.value.length > 200) lines.value.shift()
  void nextTick(() => {
    if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
  })
}

function stopStream() {
  if (timer) clearInterval(timer)
  timer = undefined
}

watch(
  () => props.open,
  (isOpen) => {
    stopStream()
    if (isOpen && props.space && props.space.health !== 'paused') {
      lines.value = seedLines(props.space)
      timer = setInterval(appendLine, 1800)
      void nextTick(() => {
        if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
      })
    } else {
      lines.value = []
    }
  },
)

onUnmounted(stopStream)
</script>

<template>
  <Sheet :open="open" @update:open="(v: boolean) => emit('update:open', v)">
    <SheetContent side="right" class="flex w-full flex-col gap-0 sm:max-w-2xl">
      <SheetHeader v-if="space">
        <SheetTitle class="flex items-center gap-2">
          <ScrollText class="h-4 w-4" />
          Logs — {{ space.name }}
          <HealthBadge :health="space.health" />
        </SheetTitle>
        <SheetDescription>
          Live logs from your space. Shown while it runs — not stored.
        </SheetDescription>
      </SheetHeader>

      <div v-if="space" class="min-h-0 flex-1 px-4 pb-4">
        <div
          v-if="space.health === 'paused'"
          class="flex h-full flex-col items-center justify-center gap-2 rounded-md border border-dashed text-center text-sm text-muted-foreground"
        >
          <PauseCircle class="h-6 w-6" />
          <p class="font-medium text-foreground">Space is paused — no logs to show</p>
          <p class="max-w-xs text-xs">
            Logs are available while the space is running. Start the space to stream them again.
          </p>
        </div>

        <div
          v-else
          ref="logBox"
          class="h-full overflow-y-auto rounded-md bg-foreground/95 p-3 font-mono text-[11px] leading-relaxed text-background"
        >
          <div
            v-for="(line, i) in lines"
            :key="i"
            class="whitespace-pre-wrap"
            :class="{
              'text-red-300': line.includes('ERROR'),
              'text-yellow-200': line.includes('WARN'),
              'opacity-70': line.includes('DEBUG'),
            }"
          >
            {{ line }}
          </div>
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>
