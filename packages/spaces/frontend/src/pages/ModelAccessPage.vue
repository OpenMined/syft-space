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
    <section v-if="connecting" class="border border-border/50 rounded-lg p-5 space-y-6">
      <h2 class="heading-3 text-foreground">
        {{ editing ? 'Connection' : 'Connect a benchmark' }}
      </h2>

      <!-- Group 1: reaching the benchmark itself — the three fields every
           connection needs, regardless of how it is deployed. -->
      <div class="space-y-4">
        <p class="text-xs font-medium text-foreground">The benchmark</p>
        <div class="grid sm:grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <Label for="bm-name">Name</Label>
            <Input id="bm-name" v-model="form.name" placeholder="Local benchmark" class="h-9" />
          </div>
          <div class="space-y-1.5">
            <Label for="bm-url">Benchmark URL</Label>
            <Input id="bm-url" v-model="form.url" placeholder="http://benchmark:8200" class="h-9" />
            <p class="text-xs text-muted-foreground">
              Where this Space reaches the benchmark's API — a Docker-internal
              address when the two run in separate containers of the same rig.
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
            <Label for="bm-console-url">Console URL (optional)</Label>
            <Input
              id="bm-console-url"
              v-model="form.console_url"
              placeholder="Same as Benchmark URL"
              class="h-9"
            />
            <p class="text-xs text-muted-foreground">
              Only when a browser cannot reach the address above — e.g.
              <code>http://localhost:8200</code> for a port published to the host
              while the address above is a Docker-internal one.
            </p>
          </div>
        </div>
      </div>

      <!-- Group 2: reaching this Space and its index — needed because the
           benchmark reads the corpus directly rather than through this
           Space's API, which has no route for it. -->
      <div class="space-y-4 border-t border-border/50 pt-5">
        <p class="text-xs font-medium text-foreground">Reaching this Space's index</p>
        <div class="grid sm:grid-cols-2 gap-4">
          <div class="space-y-1.5 sm:col-span-2">
            <Label for="bm-space-url">This Space's own address</Label>
            <Input
              id="bm-space-url"
              v-model="form.space_url"
              placeholder="http://space:8081"
              class="h-9"
            />
            <p class="text-xs text-muted-foreground">
              Where the benchmark reaches this Space's API, to ask an endpoint a
              question and hand back the card. Filled in for you when the address
              is known; change it only if this Space answers elsewhere.
            </p>
          </div>
          <div class="space-y-1.5">
            <Label for="bm-chroma-host">Index host</Label>
            <Input id="bm-chroma-host" v-model="form.chroma_host" placeholder="space" class="h-9" />
            <p class="text-xs text-muted-foreground">
              This Space's <strong class="text-foreground">container name</strong> on
              the shared network — never <code>localhost</code>, which inside a
              container means the benchmark itself.
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
            <p class="text-xs text-muted-foreground">0 — not published; use the container name below instead.</p>
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
              The fallback road to the index, reached with <code>docker exec</code>
              when the port above is not published.
            </p>
          </div>
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

    <!-- The providers: installation-wide rather than per endpoint — one
         benchmark process has one environment — so an edit here changes the
         bill for every Space that shares this benchmark. -->
    <section v-if="providerView && !connecting" class="border border-border/50 rounded-lg p-5 space-y-5">
      <div>
        <h2 class="heading-3 text-foreground flex items-center gap-2">
          <KeyRound class="h-5 w-5 text-muted-foreground" />
          Model providers
          <InfoTip text="Each role can use its own provider and key; the key's owner pays for its calls." />
        </h2>
        <p class="text-xs text-muted-foreground mt-1 max-w-2xl">
          What each role sends, and whether it leaves this machine.
        </p>
      </div>

      <div class="space-y-4">
        <ProviderRow
          v-for="role in MODEL_ACCESS_ROLES"
          :key="role.key"
          :label="role.label"
          :tip="role.tip"
          :sends="role.sends"
          v-model:url="providerForm[role.key].url"
          :placeholder="placeholderFor(role.key)"
          :target="targets[role.key]"
          :local="staysLocal(targets[role.key])"
          :key-set="providerView[role.key].key_set"
          :key-source="keySource(providerView, role.key)"
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
 * Model access: connecting a benchmark, and who it asks and grades with.
 *
 * The order on this page is the order of the decisions: **where is it**, then
 * **can it reach me**, then **who does the counting**. How a measurement is
 * built and run — models, arms, judges — lives on each endpoint's Benchmark
 * setup tab.
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { toast } from 'vue-sonner'
import {
  CheckCircle2,
  ChevronLeft,
  FlaskConical,
  KeyRound,
  Plus,
  TriangleAlert,
} from 'lucide-vue-next'

import InfoTip from '@/components/benchmark/InfoTip.vue'
import {
  MODEL_ACCESS_ROLES,
  effectiveUrl,
  keySource,
  staysLocal,
  type ProviderKey,
} from '@/components/benchmark/modelAccess'
import ProviderRow from '@/components/benchmark/ProviderRow.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { settingsApi } from '@/api/endpoints/settings'
import type { BenchmarkConnection, ProviderResponse } from '@/api/types'

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

const providerView = ref<ProviderResponse | null>(null)
const providerForm = reactive<Record<ProviderKey, { url: string }>>({
  shared: { url: '' },
  generator: { url: '' },
  filter: { url: '' },
  subject: { url: '' },
  judge: { url: '' },
})
const savingProvider = ref(false)
const providerBusy = ref<ProviderKey | null>(null)

const providerUrlsDirty = computed(() => {
  if (!providerView.value) return false
  return MODEL_ACCESS_ROLES.some(
    ({ key }) => providerForm[key].url !== providerView.value![key].url,
  )
})

function typedUrls(): Record<ProviderKey, string> {
  const out = {} as Record<ProviderKey, string>
  for (const { key } of MODEL_ACCESS_ROLES) out[key] = providerForm[key].url
  return out
}

// The address each role calls, from what is typed, so the stays/leaves chip
// follows an edit before it is saved.
const targets = computed(() => {
  const out = {} as Record<ProviderKey, string>
  const view = providerView.value
  if (!view) return out
  const urls = typedUrls()
  for (const { key } of MODEL_ACCESS_ROLES) out[key] = effectiveUrl(urls, view, key)
  return out
})

/** What a blank address box resolves to. */
function placeholderFor(key: ProviderKey): string {
  const view = providerView.value
  if (!view) return ''
  return view[key].url_default || targets.value[key] || ''
}

function adoptProvider(view: ProviderResponse) {
  providerView.value = view
  for (const { key } of MODEL_ACCESS_ROLES) {
    providerForm[key].url = view[key]?.url ?? ''
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
        filter_url: providerForm.filter.url,
      }),
    )
    toast.success('Saved')
  } catch {
    toast.error('Could not save those addresses')
  } finally {
    savingProvider.value = false
  }
}

const PROVIDER_KEY_NAMES = Object.fromEntries(
  MODEL_ACCESS_ROLES.map((role) => [role.key, role.keyName]),
) as Record<ProviderKey, string>

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
