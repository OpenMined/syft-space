<template>
  <section class="border border-border/50 rounded-lg p-5 space-y-6">
    <h2 class="heading-3 text-foreground">
      {{ connection ? 'Connection' : 'Connect a benchmark' }}
    </h2>

    <!-- Reaching the benchmark -->
    <div class="space-y-4">
      <p class="text-xs font-medium text-foreground">The benchmark</p>
      <div class="grid sm:grid-cols-2 gap-4">
        <div class="space-y-1.5">
          <Label for="bm-name">Name</Label>
          <Input id="bm-name" v-model="form.name" placeholder="Local benchmark" class="h-9" />
        </div>
        <div class="space-y-1.5">
          <div class="flex items-center justify-between gap-2">
            <Label for="bm-url">Benchmark URL</Label>
            <LocalityChip
              v-if="form.url.trim() && benchmarkAt"
              :local="benchmarkAt.local"
              :tip="
                localityTip(
                  benchmarkAt.host,
                  benchmarkAt.local,
                  'The control key and provider keys go to',
                )
              "
            />
          </div>
          <Input id="bm-url" v-model="form.url" placeholder="http://benchmark:8200" class="h-9" />
          <p class="text-xs text-muted-foreground">
            Where this Space reaches the benchmark's API — a Docker-internal address when the two
            run in separate containers of the same rig.
          </p>
        </div>
        <div class="space-y-1.5 sm:col-span-2">
          <Label for="bm-token">Control key</Label>
          <Input
            id="bm-token"
            v-model="form.token"
            type="password"
            :placeholder="connection?.has_token ? 'Stored — leave blank to keep it' : ''"
            class="h-9"
          />
          <p class="text-xs text-muted-foreground">The benchmark refuses every request without it.</p>
        </div>
      </div>
    </div>

    <!-- Reaching this Space and its index; the benchmark reads the index directly. -->
    <div class="space-y-4 border-t border-border/50 pt-5">
      <p class="text-xs font-medium text-foreground">Reaching this Space's index</p>
      <div class="grid sm:grid-cols-2 gap-4">
        <div class="space-y-1.5 sm:col-span-2">
          <div class="flex items-center justify-between gap-2">
            <Label for="bm-space-url">This Space's own address</Label>
            <LocalityChip
              v-if="form.space_url.trim() && spaceAt"
              :local="spaceAt.local"
              :tip="localityTip(spaceAt.host, spaceAt.local, 'The benchmark calls this Space at')"
            />
          </div>
          <Input
            id="bm-space-url"
            v-model="form.space_url"
            placeholder="http://space:8081"
            class="h-9"
          />
          <p class="text-xs text-muted-foreground">
            Where the benchmark reaches this Space's API to query an endpoint. Filled in when known;
            change it only if this Space answers elsewhere.
          </p>
        </div>
        <div class="space-y-1.5">
          <Label for="bm-chroma-host">Index host</Label>
          <Input id="bm-chroma-host" v-model="form.chroma_host" placeholder="space" class="h-9" />
          <p class="text-xs text-muted-foreground">
            This Space's <strong class="text-foreground">container name</strong> on the shared
            network — never <code>localhost</code>, which inside a container means the benchmark
            itself.
          </p>
        </div>
        <div class="space-y-1.5">
          <Label for="bm-chroma-port">Index port</Label>
          <Input
            id="bm-chroma-port"
            v-model.number="form.chroma_port"
            type="number"
            placeholder="8100"
            class="h-9"
          />
          <p class="text-xs text-muted-foreground">
            0: not published; the container name below is used.
          </p>
        </div>
        <div class="space-y-1.5 sm:col-span-2">
          <Label for="bm-container">Container name</Label>
          <Input id="bm-container" v-model="form.container" placeholder="syft-space" class="h-9" />
          <p class="text-xs text-muted-foreground">
            The fallback road to the index, reached with <code>docker exec</code>
            when the port above is not published.
          </p>
        </div>
      </div>
    </div>

    <div class="flex items-center gap-2">
      <Button
        size="sm"
        :disabled="saving || checkingUrl || !form.name || !form.url"
        @click="requestSubmit"
      >
        {{ saving ? 'Connecting…' : connection ? 'Save' : 'Connect' }}
      </Button>
      <Button variant="ghost" size="sm" :disabled="saving" @click="emit('cancel')">Cancel</Button>
    </div>

    <!-- A benchmark off this machine receives the control key and provider keys. -->
    <Dialog v-model:open="confirmOpen">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Benchmark outside this machine</DialogTitle>
          <DialogDescription>
            The control key and provider keys will be sent to {{ unconfirmed?.host }}.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" @click="confirmOpen = false">Cancel</Button>
          <Button data-testid="confirm-remote" @click="confirmSubmit">
            {{ connection ? 'Save anyway' : 'Connect anyway' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </section>
</template>

<script setup lang="ts">
/**
 * The benchmark connection form: a new connection, or the one given to edit. Saves after a
 * confirmation when the Space says the benchmark is off this machine.
 */
import { computed, onBeforeUnmount, ref } from 'vue'
import { toast } from 'vue-sonner'

import LocalityChip from '@/components/benchmark/LocalityChip.vue'
import { localityTip } from '@/components/benchmark/modelAccess'
import { useLocality } from '@/components/benchmark/useLocality'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import type { BenchmarkConnection } from '@/api/types'

const props = defineProps<{
  /** The connection edited; null for a new one. */
  connection: BenchmarkConnection | null
  /** This Space's own address, prefilled for a new connection. */
  spaceUrl: string
}>()

const emit = defineEmits<{ saved: []; cancel: [] }>()

const form = ref({
  name: props.connection?.name ?? '',
  url: props.connection?.url ?? '',
  // Never prefilled; blank keeps the stored key.
  token: '',
  space_url: props.connection?.space_url ?? props.spaceUrl,
  chroma_host: props.connection?.chroma_host ?? '',
  chroma_port: props.connection?.chroma_port ?? 0,
  container: props.connection?.container ?? '',
})

const saving = ref(false)

/** False once the form is closed: a check still running then submits nothing. */
let open = true
onBeforeUnmount(() => {
  open = false
})

const { locality: benchmarkAt, check: checkBenchmarkUrl } = useLocality(() => form.value.url)
const { locality: spaceAt } = useLocality(() => form.value.space_url)

/** True while Connect is asking where the URL points. */
const checkingUrl = ref(false)
/** The checked URL awaiting confirmation, with the host the dialog names. */
const unconfirmed = ref<{ url: string; host: string } | null>(null)
const confirmOpen = computed({
  get: () => unconfirmed.value !== null,
  set: (shown: boolean) => {
    if (!shown) unconfirmed.value = null
  },
})

/** Saves, after a confirmation unless the Space says the benchmark is local. */
async function requestSubmit() {
  if (checkingUrl.value || saving.value) return
  checkingUrl.value = true
  try {
    let url = form.value.url
    let at = await checkBenchmarkUrl(url)
    // A verdict holds only for the URL it was about: an edit during the check is checked anew.
    while (form.value.url !== url) {
      url = form.value.url
      at = await checkBenchmarkUrl(url)
    }
    if (!open) return
    if (at?.local) {
      void submit(url)
    } else {
      unconfirmed.value = { url, host: at?.host || url }
    }
  } finally {
    checkingUrl.value = false
  }
}

function confirmSubmit() {
  const url = unconfirmed.value?.url
  unconfirmed.value = null
  if (url !== undefined) void submit(url)
}

/** Saves the form, with `url` as checked by `requestSubmit`. */
async function submit(url: string) {
  saving.value = true
  try {
    const body = {
      name: form.value.name,
      url,
      space_url: form.value.space_url,
      chroma_host: form.value.chroma_host,
      chroma_port: form.value.chroma_port || 0,
      container: form.value.container,
      ...(form.value.token ? { token: form.value.token } : {}),
    }
    if (props.connection) {
      await benchmarksApi.updateConnection(props.connection.id, body)
    } else {
      await benchmarksApi.connect(body)
    }
    emit('saved')
  } catch {
    toast.error('Could not save the connection')
  } finally {
    saving.value = false
  }
}
</script>
