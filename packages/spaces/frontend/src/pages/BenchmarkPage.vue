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
          <p class="text-xs text-muted-foreground">
            Where this Space reaches the benchmark's API. On a rig where the
            two run in separate containers, this is a Docker-internal address.
          </p>
        </div>
        <div class="space-y-1.5">
          <Label for="bm-console-url">Console URL</Label>
          <Input
            id="bm-console-url"
            v-model="form.console_url"
            placeholder="Same as Benchmark URL"
            class="h-9"
          />
          <p class="text-xs text-muted-foreground">
            Where a browser reaches the console — fill this in only when it
            differs from the Benchmark URL above, e.g. <code>http://localhost:8200</code>
            for a published port that the address above cannot reach from
            outside the containers.
          </p>
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

    <!-- The provider: who does the asking and the grading, and who is billed
         for it. Installation-wide rather than per endpoint — one benchmark
         process has one environment — so an edit here changes the bill for
         every Space that shares this benchmark, not only this one. -->
    <section v-if="providerView && !connecting" class="border border-border/50 rounded-lg p-5 space-y-5">
      <div>
        <h2 class="heading-3 text-foreground flex items-center gap-2">
          <KeyRound class="h-5 w-5 text-muted-foreground" />
          Models provider
        </h2>
        <p class="text-xs text-muted-foreground mt-1 max-w-2xl">
          The benchmark does the asking and the grading, so the bill lands
          with whoever owns this key. Three roles, because each can point
          at a different provider: the question writer usually has to stay
          inside the perimeter, models under test almost never do.
        </p>
      </div>

      <div
        v-if="current?.capabilities.external_models"
        class="text-xs rounded-md px-3 py-2 bg-amber-500/10 text-amber-700 dark:text-amber-400"
      >
        This installation may call models outside its own perimeter. The
        question writer reads your documents, and questions often quote them
        nearly verbatim.
      </div>

      <div class="space-y-4">
        <ProviderRow
          v-for="role in providerRoles"
          :key="role.key"
          :label="role.label"
          :help="role.help"
          v-model:url="providerForm[role.key].url"
          :url-default="providerView[role.key].url_default"
          :key-set="providerView[role.key].key_set"
          :busy="providerBusy === role.key"
          @save-key="(value) => saveProviderKey(role.key, value)"
          @clear-key="clearProviderKey(role.key)"
        />
      </div>

      <div class="flex items-center gap-2">
        <Button size="sm" :disabled="savingProvider" @click="saveProviderUrls">
          {{ savingProvider ? 'Saving…' : 'Save addresses' }}
        </Button>
        <span v-if="providerUrlsDirty" class="text-xs text-muted-foreground">Unsaved changes</span>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
/**
 * Connecting a benchmark, and who it asks and grades with.
 *
 * The order on this page is the order of the decisions: **where is it**, then
 * **can it reach me**, then **who does the counting**. How a measurement is
 * actually built and run — generators, arms, judges — lives on each
 * endpoint's own Benchmark tab now, next to that endpoint's own results.
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { toast } from 'vue-sonner'
import { CheckCircle2, FlaskConical, KeyRound, Plus, TriangleAlert } from 'lucide-vue-next'

import ProviderRow from '@/components/benchmark/ProviderRow.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { settingsApi } from '@/api/endpoints/settings'
import type { BenchmarkConnection, ProviderResponse, ProviderRole } from '@/api/types'

const loading = ref(true)
const saving = ref(false)
const checking = ref(false)
const connecting = ref(false)
const editing = ref(false)

const connections = ref<BenchmarkConnection[]>([])
const current = computed(() => connections.value[0] ?? null)

const form = ref({
  name: '',
  url: '',
  console_url: '',
  token: '',
  space_url: '',
  chroma_host: '',
  chroma_port: 0,
  container: '',
})

// Compared rather than flagged: a flag has to be cleared in every path that
async function load() {
  loading.value = true
  try {
    connections.value = await benchmarksApi.listConnections()
    await loadProvider()
  } catch {
    toast.error('Could not read the benchmark settings')
  } finally {
    loading.value = false
  }
}

// --- the model providers ------------------------------------------------

type ProviderKey = 'shared' | 'generator' | 'subject' | 'judge'

const providerRoles: { key: ProviderKey; label: string; help: string }[] = [
  {
    key: 'shared',
    label: 'Shared default',
    help: 'Used by any role below left blank.',
  },
  {
    key: 'generator',
    label: 'Question writer',
    help: 'Reads your documents to build questions — usually stays inside the perimeter.',
  },
  {
    key: 'subject',
    label: 'Models under test',
    help: 'What the benchmark asks. Almost always external.',
  },
  {
    key: 'judge',
    label: 'Graders',
    help: 'Must not share a provider with a model under test, or the grading is not independent.',
  },
]

const providerView = ref<ProviderResponse | null>(null)
const providerForm = reactive<Record<ProviderKey, { url: string }>>({
  shared: { url: '' },
  generator: { url: '' },
  subject: { url: '' },
  judge: { url: '' },
})
const savingProvider = ref(false)
const providerBusy = ref<ProviderKey | null>(null)

const providerUrlsDirty = computed(() => {
  if (!providerView.value) return false
  return providerRoles.some(
    ({ key }) => providerForm[key].url !== providerView.value![key].url,
  )
})

function adoptProvider(view: ProviderResponse) {
  providerView.value = view
  for (const { key } of providerRoles) {
    providerForm[key].url = view[key].url
  }
}

async function loadProvider() {
  if (!current.value) {
    providerView.value = null
    return
  }
  try {
    adoptProvider(await benchmarksApi.getProvider(current.value.id))
  } catch {
    providerView.value = null
  }
}

async function saveProviderUrls() {
  if (!current.value) return
  savingProvider.value = true
  try {
    adoptProvider(
      await benchmarksApi.saveProvider(current.value.id, {
        ollama_url: providerForm.shared.url,
        generator_url: providerForm.generator.url,
        subject_url: providerForm.subject.url,
        judge_url: providerForm.judge.url,
      }),
    )
    toast.success('Saved')
  } catch {
    toast.error('Could not save those addresses')
  } finally {
    savingProvider.value = false
  }
}

const PROVIDER_KEY_NAMES: Record<ProviderKey, string> = {
  shared: 'llm_api_key',
  generator: 'generator_key',
  subject: 'subject_key',
  judge: 'judge_key',
}

async function saveProviderKey(role: ProviderKey, value: string) {
  if (!current.value) return
  providerBusy.value = role
  try {
    adoptProvider(
      await benchmarksApi.saveProviderCredential(
        current.value.id,
        PROVIDER_KEY_NAMES[role],
        value,
      ),
    )
    toast.success('Key stored')
  } catch {
    toast.error('Could not store that key')
  } finally {
    providerBusy.value = null
  }
}

async function clearProviderKey(role: ProviderKey) {
  if (!current.value) return
  providerBusy.value = role
  try {
    adoptProvider(
      await benchmarksApi.deleteProviderCredential(current.value.id, PROVIDER_KEY_NAMES[role]),
    )
    toast.success('Key cleared')
  } catch {
    toast.error('Could not clear that key')
  } finally {
    providerBusy.value = null
  }
}

async function startConnecting() {
  editing.value = false
  form.value = {
    name: '',
    url: '',
    console_url: '',
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
    console_url: current.value.console_url,
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
      console_url: form.value.console_url,
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
