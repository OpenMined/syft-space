<template>
  <div class="p-6 max-w-5xl mx-auto space-y-6">
    <RouterLink
      :to="{ name: 'settings' }"
      class="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
    >
      <ChevronLeft class="h-3.5 w-3.5" />
      Settings
    </RouterLink>
    <PageHeader>
      <template #title>Model access</template>
      <template #description>
        The benchmark this Space uses, and the providers and keys it calls models with.
      </template>
    </PageHeader>

    <div v-if="loading" class="space-y-4">
      <Skeleton class="h-32 w-full" />
      <Skeleton class="h-64 w-full" />
    </div>

    <!-- Nothing connected (the shipped state). -->
    <div
      v-else-if="!connections.length && !editing"
      class="border border-border/50 rounded-lg p-8 text-center"
    >
      <FlaskConical class="h-8 w-8 text-muted-foreground/50 mx-auto mb-3" />
      <h3 class="text-sm font-medium text-foreground mb-1">No benchmark is connected</h3>
      <p class="text-xs text-muted-foreground max-w-lg mx-auto mb-5">
        Nothing is measuring your endpoints. A benchmark is a separate service that builds questions
        from an endpoint's index, asks them and grades the answers. It normally runs on this
        machine, next to this Space.
      </p>
      <Button size="sm" @click="startConnecting">
        <Plus class="h-4 w-4 mr-1.5" />
        Connect a benchmark
      </Button>
    </div>

    <ConnectionForm
      v-if="editing"
      :connection="editing.connection"
      :space-url="editing.spaceUrl"
      @saved="saved"
      @cancel="editing = null"
    />

    <!-- Connection status as last reported by the benchmark -->
    <section v-if="current && !editing" class="border border-border/50 rounded-lg p-5">
      <div class="flex items-start justify-between gap-4 flex-wrap">
        <div class="space-y-1">
          <h2 class="heading-3 text-foreground flex items-center gap-2">
            <FlaskConical class="h-5 w-5 text-muted-foreground" />
            {{ current.name }}
          </h2>
          <p class="text-xs text-muted-foreground">
            {{ current.url }}
            <span v-if="current.capabilities.profile">
              · profile {{ current.capabilities.profile }}
            </span>
            <span v-if="current.endpoints">
              · measuring {{ plural(current.endpoints, 'endpoint') }}
            </span>
          </p>
        </div>
        <div class="flex items-center gap-2">
          <Button variant="outline" size="sm" :disabled="checking" @click="check">
            {{ checking ? 'Asking…' : 'Check' }}
          </Button>
          <Button
            variant="outline"
            size="sm"
            @click="editing = { connection: current, spaceUrl: current.space_url }"
          >
            Edit
          </Button>
          <Button
            variant="outline"
            size="sm"
            class="text-destructive hover:text-destructive"
            @click="disconnect"
          >
            Disconnect
          </Button>
        </div>
      </div>

      <div
        class="mt-4 flex items-start gap-2 text-xs rounded-md px-3 py-2"
        :class="current.reachable ? TONE.good : TONE.caution"
      >
        <component :is="current.reachable ? CheckCircle2 : TriangleAlert" class="h-4 w-4 mt-px" />
        <span v-if="current.reachable">
          Answering. It offers {{ (current.capabilities.subject_models ?? []).length }} model(s)
          under test and {{ (current.capabilities.judge_models ?? []).length }} grader(s).
        </span>
        <span v-else>
          {{ current.detail || 'Not answering.' }} Settings below can still be edited — they are
          stored here and handed over the next time it answers.
        </span>
      </div>

      <div v-if="current.capabilities.external_models" class="mt-2 text-xs text-muted-foreground">
        This installation is allowed to call models outside its own perimeter. Questions are built
        from your documents and often quote them nearly verbatim.
      </div>
    </section>

    <ModelProviders v-if="current && !editing" :key="current.id" :connection-id="current.id" />
  </div>
</template>

<script setup lang="ts">
/** Model access: the benchmark connection and the model providers it calls. */
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { toast } from 'vue-sonner'
import { CheckCircle2, ChevronLeft, FlaskConical, Plus, TriangleAlert } from 'lucide-vue-next'

import ConnectionForm from '@/components/benchmark/ConnectionForm.vue'
import ModelProviders from '@/components/benchmark/ModelProviders.vue'
import { plural, TONE } from '@/components/benchmark/labels'
import PageHeader from '@/components/ui/PageHeader.vue'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { settingsApi } from '@/api/endpoints/settings'
import type { BenchmarkConnection } from '@/api/types'

const loading = ref(true)
const checking = ref(false)

const connections = ref<BenchmarkConnection[]>([])
const current = computed(() => connections.value[0] ?? null)

/** The form shown: the connection edited (null for a new one) and the Space address it starts with. */
const editing = ref<{ connection: BenchmarkConnection | null; spaceUrl: string } | null>(null)

async function load() {
  loading.value = true
  try {
    connections.value = await benchmarksApi.listConnections()
  } catch {
    toast.error('Could not read the benchmark settings')
  } finally {
    loading.value = false
  }
}

async function startConnecting() {
  editing.value = { connection: null, spaceUrl: await ownUrl() }
}

/** This Space's public URL, prefilled for a new connection. */
async function ownUrl(): Promise<string> {
  try {
    const response = await settingsApi.getPublicUrl()
    return response.public_url ?? ''
  } catch {
    return ''
  }
}

async function saved() {
  editing.value = null
  await load()
  toast.success(current.value?.reachable ? 'Connected' : 'Saved — the benchmark is not answering')
}

async function check() {
  if (!current.value) return
  checking.value = true
  try {
    const updated = await benchmarksApi.checkConnection(current.value.id)
    connections.value = connections.value.map((row) => (row.id === updated.id ? updated : row))
    toast[updated.reachable ? 'success' : 'warning'](
      updated.reachable ? 'The benchmark answered' : updated.detail || 'No answer',
    )
  } catch {
    toast.error('Could not reach the benchmark')
  } finally {
    checking.value = false
  }
}

async function disconnect() {
  if (!current.value) return
  try {
    await benchmarksApi.disconnect(current.value.id)
    await load()
    toast.success('Disconnected')
  } catch {
    toast.error('Could not disconnect')
  }
}

onMounted(load)
</script>
