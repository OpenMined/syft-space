<template>
  <div class="p-6 max-w-5xl mx-auto space-y-6">
    <PageHeader
      title="Benchmark"
      description="A benchmark measures how honest your endpoints are and hands the result to this Space. Connect one here, then say on each endpoint whether it should be measured."
    />

    <div v-if="loading" class="space-y-4">
      <Skeleton class="h-32 w-full" />
      <Skeleton class="h-64 w-full" />
    </div>

    <!-- Nothing connected. A Space ships this way, and the page has to say so
         rather than showing an empty form. -->
    <div
      v-else-if="!connections.length && !connecting"
      class="border border-border/50 rounded-lg p-8 text-center"
    >
      <FlaskConical class="h-8 w-8 text-muted-foreground/50 mx-auto mb-3" />
      <h3 class="text-sm font-medium text-foreground mb-1">No benchmark is connected</h3>
      <p class="text-xs text-muted-foreground max-w-lg mx-auto mb-5">
        Nothing is measuring your endpoints. A benchmark is a separate service:
        it builds questions from an endpoint's own index, asks them back, grades
        the answers, and hands this Space a card. It can be yours, running beside
        this Space, or one you share with others.
      </p>
      <Button size="sm" @click="startConnecting">
        <Plus class="h-4 w-4 mr-1.5" />
        Connect a benchmark
      </Button>
    </div>

    <!-- The connection form: where it is, and how it reaches this Space. -->
    <section v-if="connecting" class="border border-border/50 rounded-lg p-5 space-y-5">
      <div>
        <h2 class="heading-3 text-foreground">
          {{ editing ? 'Connection' : 'Connect a benchmark' }}
        </h2>
        <p class="text-xs text-muted-foreground mt-1 max-w-2xl">
          Two addresses, because the benchmark needs two roads. It reaches this
          Space's API over HTTP, and the index directly — ChromaDB's own port,
          or the container when that port is not published. Corpus text never
          travels through this Space's API, and there is no route for it.
        </p>
      </div>

      <div class="grid sm:grid-cols-2 gap-4">
        <div class="space-y-1.5">
          <Label for="bm-name">Name</Label>
          <Input id="bm-name" v-model="form.name" placeholder="Local benchmark" class="h-9" />
        </div>
        <div class="space-y-1.5">
          <Label for="bm-url">Benchmark URL</Label>
          <Input id="bm-url" v-model="form.url" placeholder="http://benchmark:8200" class="h-9" />
        </div>
        <div class="space-y-1.5 sm:col-span-2">
          <Label for="bm-token">Control key</Label>
          <Input
            id="bm-token"
            v-model="form.token"
            type="password"
            :placeholder="editing && current?.has_token ? 'Stored — leave blank to keep it' : ''"
            class="h-9"
          />
          <p class="text-xs text-muted-foreground">
            The benchmark refuses everything without it. A run costs hours and
            money, so an open port would mean anyone who can reach the network
            can spend your budget.
          </p>
        </div>

        <div class="space-y-1.5 sm:col-span-2">
          <Label for="bm-space-url">This Space, as the benchmark sees it</Label>
          <Input
            id="bm-space-url"
            v-model="form.space_url"
            placeholder="http://space:8081"
            class="h-9"
          />
        </div>
        <div class="space-y-1.5">
          <Label for="bm-chroma-host">Index host</Label>
          <Input id="bm-chroma-host" v-model="form.chroma_host" placeholder="space" class="h-9" />
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
          <p class="text-xs text-muted-foreground">0 — not published; use the container instead.</p>
        </div>
        <div class="space-y-1.5 sm:col-span-2">
          <Label for="bm-container">Container name</Label>
          <Input
            id="bm-container"
            v-model="form.container"
            placeholder="syft-space"
            class="h-9"
          />
          <p class="text-xs text-muted-foreground">
            The fallback road to the index, used when its port is not published.
          </p>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <Button size="sm" :disabled="saving || !form.name || !form.url" @click="submit">
          {{ saving ? 'Connecting…' : editing ? 'Save' : 'Connect' }}
        </Button>
        <Button variant="ghost" size="sm" @click="connecting = false">Cancel</Button>
      </div>
    </section>

    <!-- What the benchmark said about itself when last asked. -->
    <section v-if="current && !connecting" class="border border-border/50 rounded-lg p-5">
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
              · measuring {{ current.endpoints }}
              {{ current.endpoints === 1 ? 'endpoint' : 'endpoints' }}
            </span>
          </p>
        </div>
        <div class="flex items-center gap-2">
          <Button variant="outline" size="sm" :disabled="checking" @click="check">
            {{ checking ? 'Asking…' : 'Check' }}
          </Button>
          <Button variant="outline" size="sm" @click="startEditing">Edit</Button>
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
        :class="
          current.reachable
            ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
            : 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
        "
      >
        <component :is="current.reachable ? CheckCircle2 : TriangleAlert" class="h-4 w-4 mt-px" />
        <span v-if="current.reachable">
          Answering. It offers {{ (current.capabilities.subject_models ?? []).length }} model(s)
          under test and {{ (current.capabilities.judge_models ?? []).length }} grader(s).
        </span>
        <span v-else>
          {{ current.detail || 'Not answering.' }} Settings below can still be
          edited — they are stored here and handed over the next time it answers.
        </span>
      </div>

      <div
        v-if="current.capabilities.external_models"
        class="mt-2 text-xs text-muted-foreground"
      >
        This installation is allowed to call models outside its own perimeter.
        Questions are built from your documents and often quote them nearly
        verbatim.
      </div>
    </section>

    <!-- Who does the counting, and who is billed for it. Shown, never edited:
         the key lives in that service's environment and does not leave it —
         this Space never calls the provider, so a copy here would be a second
         secret in a service that has no use for it. -->
    <section v-if="provider && !connecting" class="border border-border/50 rounded-lg p-5">
      <div class="flex items-start justify-between gap-4 flex-wrap">
        <div class="space-y-1">
          <h2 class="heading-3 text-foreground flex items-center gap-2">
            <KeyRound class="h-5 w-5 text-muted-foreground" />
            Models provider
          </h2>
          <p class="text-xs text-muted-foreground max-w-2xl">
            The benchmark does the asking and the grading, so the bill lands
            with whoever owns this key. It is set in that service's own
            environment and is never sent here — this page can only tell you
            whether there is one.
          </p>
        </div>
        <span
          class="text-xs px-2 py-1 rounded-md"
          :class="
            provider.key_set
              ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
              : 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
          "
        >
          {{ provider.key_set ? 'Key is set' : 'No key' }}
        </span>
      </div>

      <dl class="grid sm:grid-cols-2 gap-x-6 gap-y-2 mt-4 text-xs">
        <div class="flex justify-between gap-4 border-b border-border/30 py-1">
          <dt class="text-muted-foreground">Endpoint</dt>
          <dd class="text-foreground text-right break-all">{{ provider.url }}</dd>
        </div>
        <div class="flex justify-between gap-4 border-b border-border/30 py-1">
          <dt class="text-muted-foreground">Identifies itself as</dt>
          <dd class="text-foreground text-right">{{ provider.app_name || '—' }}</dd>
        </div>
      </dl>

      <!-- Roles are listed one by one because each has its own address and key.
           A single "the provider is X" can be plainly wrong: the question
           writer usually has to stay inside the perimeter while the models
           under test almost never do. -->
      <div v-if="ownRoles.length" class="mt-4 space-y-1">
        <p class="text-xs font-medium text-foreground">Roles with their own provider</p>
        <p v-for="role in ownRoles" :key="role.role" class="text-xs text-muted-foreground">
          {{ roleWords(role.role) }} — {{ role.url }}
          <span v-if="!role.key_set"> · no key</span>
        </p>
      </div>

      <div
        v-if="current?.capabilities.external_models"
        class="mt-4 text-xs rounded-md px-3 py-2 bg-amber-500/10 text-amber-700 dark:text-amber-400"
      >
        This installation may call models outside its own perimeter<span
          v-if="provider.external_hosts.length"
        >
          — allowed: {{ provider.external_hosts.join(', ') }}</span
        >. The question writer reads your documents, and questions often quote
        them nearly verbatim.
      </div>

      <p class="mt-3 text-xs text-muted-foreground">
        To change any of this, edit the benchmark service's environment and
        restart it.
      </p>
    </section>

    <!-- The Space-wide settings. Everything here applies to every endpoint
         this benchmark measures unless that endpoint says otherwise. -->
    <section v-if="current && !connecting" class="border border-border/50 rounded-lg p-5 space-y-5">
      <div>
        <h2 class="heading-3 text-foreground">How it measures</h2>
        <p class="text-xs text-muted-foreground mt-1 max-w-2xl">
          One setting for the whole Space. Anything left at its default is
          decided by the benchmark, and a benchmark that changes its default
          changes it here too — which is the point: these are the settings you
          overrode, not a copy of everything.
        </p>
      </div>

      <div v-if="!hasFields" class="text-xs text-muted-foreground">
        The benchmark has not described its settings yet. Check the connection
        above; until it answers, there is nothing to draw a form from.
      </div>

      <template v-else>
        <div class="border-b border-border/50 pb-1">
          <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            The instrument
          </p>
          <p class="text-xs text-muted-foreground mt-1 max-w-2xl mb-2">
            Judges, arms and thresholds. Deliberately not settable per endpoint:
            a card declares the instrument it was measured with, and two
            endpoints graded differently would be quietly incomparable while the
            card still promised otherwise.
          </p>
        </div>
        <LayerForm
          v-model="instrument"
          :fields="current.fields.instrument ?? []"
          :inherited="current.defaults.instrument ?? {}"
          :connection-id="current.id"
        />

        <div class="border-b border-border/50 pb-1 pt-2">
          <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Questioning a node
          </p>
          <p class="text-xs text-muted-foreground mt-1 max-w-2xl mb-2">
            The starting point for every endpoint. Any of these can be set
            differently on a single endpoint, on its own Benchmark tab.
          </p>
        </div>
        <LayerForm
          v-model="probe"
          :fields="current.fields.probe ?? []"
          :inherited="current.defaults.probe ?? {}"
          :connection-id="current.id"
        />

        <div class="flex items-center gap-3 pt-2">
          <Button size="sm" :disabled="savingSettings" @click="saveSettings">
            {{ savingSettings ? 'Saving…' : 'Save settings' }}
          </Button>
          <span v-if="dirty" class="text-xs text-muted-foreground">Unsaved changes</span>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
/**
 * Connecting a benchmark and saying how it should measure.
 *
 * The order on this page is the order of the decisions: **where is it**, then
 * **can it reach me**, then **how should it measure**. Whether a given endpoint
 * is measured at all is not decided here — that is a property of the endpoint
 * and lives on its own page, next to everything else about it.
 */
import { computed, onMounted, ref } from 'vue'
import { toast } from 'vue-sonner'
import { CheckCircle2, FlaskConical, KeyRound, Plus, TriangleAlert } from 'lucide-vue-next'

import LayerForm from '@/components/benchmark/LayerForm.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { settingsApi } from '@/api/endpoints/settings'
import type { BenchmarkConnection, BenchmarkLayer } from '@/api/types'

const loading = ref(true)
const saving = ref(false)
const savingSettings = ref(false)
const checking = ref(false)
const connecting = ref(false)
const editing = ref(false)

const connections = ref<BenchmarkConnection[]>([])
const current = computed(() => connections.value[0] ?? null)

const instrument = ref<BenchmarkLayer>({})
const probe = ref<BenchmarkLayer>({})

const form = ref({
  name: '',
  url: '',
  token: '',
  space_url: '',
  chroma_host: '',
  chroma_port: 0,
  container: '',
})

// Compared rather than flagged: a flag has to be cleared in every path that
// saves, reloads or discards, and the one path somebody forgets is the one
// that leaves "Unsaved changes" showing over saved settings.
const stable = (layer: BenchmarkLayer): string =>
  JSON.stringify(Object.fromEntries(Object.entries(layer).sort(([a], [b]) => a.localeCompare(b))))

const dirty = computed(
  () =>
    stable(instrument.value) !== stable(current.value?.instrument ?? {}) ||
    stable(probe.value) !== stable(current.value?.probe ?? {}),
)

const provider = computed(() => current.value?.capabilities?.provider ?? null)

// Only the roles that were pointed somewhere of their own: listing all three
// when they all inherit the same address would be three ways of saying one
// thing.
const ownRoles = computed(() => (provider.value?.roles ?? []).filter((role) => role.own))

function roleWords(role: string): string {
  switch (role) {
    case 'generator':
      return 'Question writer'
    case 'subject':
      return 'Models under test'
    case 'judge':
      return 'Graders'
    default:
      return role
  }
}

const hasFields = computed(
  () =>
    (current.value?.fields?.instrument?.length ?? 0) > 0 ||
    (current.value?.fields?.probe?.length ?? 0) > 0,
)

async function load() {
  loading.value = true
  try {
    connections.value = await benchmarksApi.listConnections()
    adopt()
  } catch {
    toast.error('Could not read the benchmark settings')
  } finally {
    loading.value = false
  }
}

function adopt() {
  instrument.value = { ...current.value?.instrument }
  probe.value = { ...current.value?.probe }
}

async function startConnecting() {
  editing.value = false
  form.value = {
    name: '',
    url: '',
    token: '',
    // A sensible first guess at how the benchmark sees us, so the commonest
    // case needs no typing at all.
    space_url: await ownUrl(),
    chroma_host: '',
    chroma_port: 0,
    container: '',
  }
  connecting.value = true
}

function startEditing() {
  if (!current.value) return
  editing.value = true
  form.value = {
    name: current.value.name,
    url: current.value.url,
    // Never prefilled: the key is not sent to this form, and a blank box here
    // means "keep the stored one" rather than "clear it".
    token: '',
    space_url: current.value.space_url,
    chroma_host: current.value.chroma_host,
    chroma_port: current.value.chroma_port,
    container: current.value.container,
  }
  connecting.value = true
}

async function ownUrl(): Promise<string> {
  try {
    const response = await settingsApi.getPublicUrl()
    return response.public_url ?? ''
  } catch {
    return ''
  }
}

async function submit() {
  saving.value = true
  try {
    const body = {
      name: form.value.name,
      url: form.value.url,
      space_url: form.value.space_url,
      chroma_host: form.value.chroma_host,
      chroma_port: form.value.chroma_port || 0,
      container: form.value.container,
      ...(form.value.token ? { token: form.value.token } : {}),
    }
    if (editing.value && current.value) {
      await benchmarksApi.updateConnection(current.value.id, body)
    } else {
      await benchmarksApi.connect(body)
    }
    connecting.value = false
    await load()
    toast.success(current.value?.reachable ? 'Connected' : 'Saved — the benchmark is not answering')
  } catch {
    toast.error('Could not save the connection')
  } finally {
    saving.value = false
  }
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

async function saveSettings() {
  if (!current.value) return
  savingSettings.value = true
  try {
    const updated = await benchmarksApi.saveSettings(current.value.id, {
      instrument: instrument.value,
      probe: probe.value,
    })
    connections.value = connections.value.map((row) => (row.id === updated.id ? updated : row))
    adopt()
    toast.success('Settings saved and handed to the benchmark')
  } catch {
    toast.error('Could not save the settings')
  } finally {
    savingSettings.value = false
  }
}

async function disconnect() {
  if (!current.value) return
  try {
    await benchmarksApi.disconnect(current.value.id)
    await load()
    toast.success('Disconnected. Nothing already published was taken down.')
  } catch {
    toast.error('Could not disconnect')
  }
}

onMounted(load)
</script>
