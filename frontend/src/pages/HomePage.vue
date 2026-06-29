<template>
  <ErrorBoundary
    :can-retry="true"
    :show-details="true"
    custom-title="Dashboard Loading Error"
    custom-message="There was a problem loading the dashboard. Please try again."
    @retry="refreshDashboard"
  >
    <div class="min-h-screen">
      <!-- Skeleton (initial load) -->
      <div v-if="isInitialLoading" class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-14 pb-20">
        <Skeleton class="h-12 w-80 mb-4" />
        <Skeleton class="h-5 w-96 mb-8" />
        <div class="flex gap-3 mb-10">
          <Skeleton class="h-11 w-32 rounded-md" />
          <Skeleton class="h-11 w-28 rounded-md" />
        </div>
        <Skeleton class="h-72 rounded-xl" />
      </div>

      <!-- First-time experience: hero + onboarding -->
      <div v-else-if="isFirstTimeUser" class="relative overflow-hidden">
        <div class="absolute inset-0 -z-10 opacity-30 dark:opacity-20 blur-3xl" aria-hidden="true">
          <div class="absolute top-[-10%] left-[10%] h-72 w-72 rounded-full bg-primary/40" />
          <div
            class="absolute top-[5%] right-[15%] h-56 w-56 rounded-full bg-cyan-400/30 dark:bg-cyan-500/20"
          />
          <div
            class="absolute top-[20%] left-[40%] h-48 w-48 rounded-full bg-teal-300/20 dark:bg-teal-600/15"
          />
        </div>

        <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-10 text-center">
          <h1
            class="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-foreground mb-5 leading-[1.05]"
          >
            Your space to share
            <span
              class="bg-gradient-to-r from-primary via-teal-500 to-cyan-500 dark:from-primary dark:via-teal-400 dark:to-cyan-400 bg-clip-text text-transparent"
            >
              knowledge
            </span>
          </h1>
          <p class="text-lg text-muted-foreground max-w-xl mx-auto leading-relaxed">
            Publish documents and AI models on your terms. Set a fair price. See your contribution
            recognized.
          </p>

          <div class="flex flex-wrap items-center justify-center gap-3 mt-8">
            <Button
              size="lg"
              class="px-6 h-11 text-[15px] font-medium shadow-md hover:shadow-lg transition-all"
              @click="router.push({ name: 'go-live' })"
            >
              <Zap class="w-4 h-4 mr-2" />
              Publish your first API
            </Button>
            <a
              href="http://syft.docs.openmined.org/space/quickstart"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center justify-center gap-1.5 h-11 px-5 rounded-md border border-input bg-background text-[15px] font-medium hover:bg-accent hover:text-accent-foreground transition-colors"
            >
              Read the docs
              <ArrowUpRight class="w-4 h-4" />
            </a>
          </div>
        </div>

        <!-- Onboarding checklist -->
        <div class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 mb-12">
          <div class="rounded-xl border border-border/60 bg-card overflow-hidden">
            <div class="px-5 py-4 border-b border-border/50">
              <div class="flex items-center justify-between">
                <h2 class="text-base font-semibold text-foreground">
                  Get to your first publication
                </h2>
                <span class="text-xs text-muted-foreground tabular-nums">
                  {{ completedSteps }} / {{ onboardingSteps.length }}
                </span>
              </div>
              <p class="text-xs text-muted-foreground mt-1">
                A few quick steps and you're live on the marketplace.
              </p>
            </div>
            <ul class="divide-y divide-border/50">
              <li
                v-for="(step, i) in onboardingSteps"
                :key="step.label"
                class="flex items-center gap-3 px-5 py-3.5"
              >
                <div
                  :class="[
                    'flex items-center justify-center h-6 w-6 rounded-full shrink-0 text-[11px] font-semibold',
                    step.complete
                      ? 'bg-green-500 text-white'
                      : 'border border-border bg-muted/40 text-muted-foreground',
                  ]"
                >
                  <Check v-if="step.complete" class="w-3.5 h-3.5" />
                  <span v-else>{{ i + 1 }}</span>
                </div>
                <div class="flex-1 min-w-0">
                  <p
                    :class="[
                      'text-sm font-medium',
                      step.complete
                        ? 'text-muted-foreground line-through decoration-muted-foreground/40'
                        : 'text-foreground',
                    ]"
                  >
                    {{ step.label }}
                  </p>
                  <p class="text-xs text-muted-foreground mt-0.5">{{ step.hint }}</p>
                </div>
                <Button
                  v-if="!step.complete"
                  variant="outline"
                  size="sm"
                  class="h-8 shrink-0"
                  :disabled="step.disabled"
                  @click="step.action"
                >
                  {{ step.ctaLabel }}
                </Button>
                <span
                  v-else
                  class="text-[11px] font-medium text-green-600 dark:text-green-500 shrink-0"
                >
                  Done
                </span>
              </li>
            </ul>
          </div>
        </div>

        <!-- Get started docs -->
        <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pb-16">
          <h3 class="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">
            Get started
          </h3>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <a
              v-for="doc in docs"
              :key="doc.title"
              :href="doc.href"
              target="_blank"
              rel="noopener noreferrer"
              class="group flex items-start gap-3 p-4 rounded-lg border border-border/50 bg-card hover:border-border hover:shadow-sm transition-all"
            >
              <div :class="['p-2 rounded-md shrink-0', doc.iconBg]">
                <component :is="doc.icon" class="w-4 h-4" :class="doc.iconColor" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-foreground">{{ doc.title }}</div>
                <div class="text-xs text-muted-foreground mt-0.5">{{ doc.desc }}</div>
              </div>
              <ArrowUpRight
                class="w-3.5 h-3.5 text-muted-foreground/50 group-hover:text-muted-foreground transition-colors shrink-0 mt-0.5"
              />
            </a>
          </div>
        </div>
      </div>

      <!-- Returning user: dashboard -->
      <div v-else class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 pt-14 pb-20">
        <!-- Hero -->
        <h1
          class="text-4xl sm:text-5xl font-bold tracking-tight text-foreground mb-4 leading-[1.05]"
        >
          Your space to share
          <span
            class="bg-gradient-to-r from-primary via-teal-500 to-cyan-500 dark:from-primary dark:via-teal-400 dark:to-cyan-400 bg-clip-text text-transparent"
          >
            knowledge
          </span>
        </h1>
        <p class="text-lg text-muted-foreground max-w-xl leading-relaxed">
          Publish documents and AI models on your terms. Set a fair price. See your contribution
          recognized.
        </p>

        <!-- Actions -->
        <div class="flex flex-wrap items-center gap-3 mt-8">
          <Button size="lg" class="h-11 px-5 text-[15px]" @click="router.push({ name: 'go-live' })">
            <Zap class="w-4 h-4 mr-2" />
            New API
          </Button>
          <Button
            variant="outline"
            size="lg"
            class="h-11 px-5 text-[15px]"
            @click="router.push({ name: 'datasets' })"
          >
            <Plus class="w-4 h-4 mr-2" />
            Source
          </Button>
        </div>

        <!-- Your APIs -->
        <div class="mt-10 rounded-xl border border-border/60 bg-card overflow-hidden">
          <div class="flex items-center justify-between px-6 py-4 border-b border-border/50">
            <h2 class="text-base font-semibold text-foreground">Your APIs</h2>
            <button
              class="inline-flex items-center text-sm text-muted-foreground hover:text-foreground transition-colors"
              @click="router.push({ name: 'endpoints' })"
            >
              View all
            </button>
          </div>

          <!-- Empty -->
          <div v-if="totalApis === 0" class="px-6 py-16 text-center">
            <div class="p-3 rounded-lg bg-primary/10 w-fit mx-auto mb-3">
              <Zap class="w-5 h-5 text-primary" />
            </div>
            <p class="text-sm text-foreground font-medium mb-1">No APIs published yet</p>
            <p class="text-xs text-muted-foreground mb-4 max-w-xs mx-auto">
              You have resources ready. Compose them into your first API.
            </p>
            <Button size="sm" @click="router.push({ name: 'go-live' })">
              <Zap class="w-3.5 h-3.5 mr-1.5" />
              Publish API
            </Button>
          </div>

          <!-- API rows -->
          <div v-else class="divide-y divide-border/40">
            <button
              v-for="ep in recentEndpoints"
              :key="ep.id"
              class="group w-full flex items-center gap-3 px-6 py-3.5 text-left hover:bg-muted/40 transition-colors"
              @click="router.push({ name: 'endpoint-detail', params: { slug: ep.slug } })"
            >
              <div :class="['p-2 rounded-md shrink-0', kindBg(ep)]">
                <component :is="kindIcon(ep)" class="h-4 w-4" :class="kindIconColor(ep)" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="text-sm font-medium text-foreground truncate">{{ ep.name }}</span>
                  <span
                    class="inline-flex items-center gap-1 text-[11px] font-medium shrink-0"
                    :class="
                      ep.published ? 'text-green-600 dark:text-green-500' : 'text-muted-foreground'
                    "
                  >
                    <span
                      class="h-1.5 w-1.5 rounded-full"
                      :class="ep.published ? 'bg-green-500' : 'bg-muted-foreground/40'"
                    />
                    {{ ep.published ? 'Live' : 'Draft' }}
                  </span>
                </div>
                <p class="text-xs text-muted-foreground truncate mt-0.5">{{ rowMeta(ep) }}</p>
              </div>
              <ChevronRight
                class="w-4 h-4 text-muted-foreground/40 group-hover:text-muted-foreground transition-colors shrink-0"
              />
            </button>
          </div>
        </div>

        <!-- Get started -->
        <h3 class="text-xs font-semibold uppercase tracking-wider text-muted-foreground mt-12 mb-4">
          Get started
        </h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <button
            v-for="action in quickActions"
            :key="action.label"
            class="group flex items-center gap-3 p-4 rounded-lg border border-border/50 bg-card hover:border-border hover:shadow-sm transition-all text-left"
            @click="action.click"
          >
            <div :class="['p-2 rounded-md shrink-0', action.iconBg]">
              <component :is="action.icon" class="w-4 h-4" :class="action.iconColor" />
            </div>
            <span class="text-sm font-medium text-foreground flex-1 min-w-0">{{
              action.label
            }}</span>
            <ChevronRight
              class="w-3.5 h-3.5 text-muted-foreground/40 group-hover:text-muted-foreground transition-colors shrink-0"
            />
          </button>
        </div>

        <!-- Resources -->
        <div class="mt-8 flex flex-wrap items-center gap-x-5 gap-y-2">
          <a
            v-for="r in resources"
            :key="r.label"
            :href="r.href"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {{ r.label }}
            <ArrowUpRight class="w-3 h-3" />
          </a>
        </div>
      </div>
    </div>
  </ErrorBoundary>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowUpRight,
  BarChart3,
  Brain,
  Check,
  ChevronRight,
  Database,
  FileText,
  Layers,
  Plus,
  Shield,
  Sparkles,
  Zap,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import { useEndpointsStore, type EndpointItem } from '@/stores/endpoints'
import { datasetsApi } from '@/api/endpoints/datasets'
import { modelsApi } from '@/api/endpoints/models'

const router = useRouter()
const endpointsStore = useEndpointsStore()

const datasetCount = ref(0)
const modelCount = ref(0)
const resourcesLoaded = ref(false)

const isInitialLoading = computed(
  () =>
    (endpointsStore.isLoading && endpointsStore.endpoints.length === 0) || !resourcesLoaded.value,
)

const totalApis = computed(() => endpointsStore.endpoints.length)

const isFirstTimeUser = computed(
  () => totalApis.value === 0 && datasetCount.value === 0 && modelCount.value === 0,
)

const recentEndpoints = computed(() => endpointsStore.endpoints.slice(0, 5))

type Kind = 'data' | 'model' | 'hybrid'
const kindOf = (ep: EndpointItem): Kind => {
  const hasDataset = !!ep.datasetId
  const hasModel = !!ep.modelId
  if (hasDataset && hasModel) return 'hybrid'
  if (hasModel) return 'model'
  return 'data'
}

const kindIcon = (ep: EndpointItem) => {
  const k = kindOf(ep)
  if (k === 'hybrid') return Layers
  if (k === 'model') return Sparkles
  return Database
}

const kindBg = (ep: EndpointItem) => {
  const k = kindOf(ep)
  if (k === 'hybrid') return 'bg-amber-100 dark:bg-amber-900/40'
  if (k === 'model') return 'bg-purple-100 dark:bg-purple-900/40'
  return 'bg-blue-100 dark:bg-blue-900/40'
}

const kindIconColor = (ep: EndpointItem) => {
  const k = kindOf(ep)
  if (k === 'hybrid') return 'text-amber-700 dark:text-amber-400'
  if (k === 'model') return 'text-purple-700 dark:text-purple-400'
  return 'text-blue-700 dark:text-blue-400'
}

const formatType = (value: string) =>
  value
    .split(/[_-]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')

const rowMeta = (ep: EndpointItem) => {
  const parts: string[] = []
  const k = kindOf(ep)
  if (k === 'hybrid') parts.push('Hybrid API')
  else if (k === 'model') parts.push('Model API')
  else parts.push('Data API')

  if (ep.datasetId) {
    const paths = ep.watchedPaths?.length ?? 0
    if (paths > 0) parts.push(`${paths} path${paths === 1 ? '' : 's'}`)
    else if (ep.dataSourceType) parts.push(formatType(ep.dataSourceType))
  }
  if (ep.modelId && ep.modelType) parts.push(formatType(ep.modelType))

  return parts.join(' · ')
}

const onboardingSteps = computed(() => {
  const hasSource = datasetCount.value > 0
  const hasModel = modelCount.value > 0
  const hasApi = totalApis.value > 0

  return [
    {
      label: 'Add a data source',
      hint: 'Connect a folder or remote vector store to ingest documents.',
      complete: hasSource,
      ctaLabel: 'Add source',
      disabled: false,
      action: () => router.push({ name: 'datasets' }),
    },
    {
      label: 'Connect an AI model',
      hint: 'Optional. Add a vLLM, OpenAI, or compatible model for summaries.',
      complete: hasModel,
      ctaLabel: 'Add model',
      disabled: false,
      action: () => router.push({ name: 'models' }),
    },
    {
      label: 'Publish your first API',
      hint: 'Compose a source and model into a queryable endpoint.',
      complete: hasApi,
      ctaLabel: 'Publish',
      disabled: !hasSource && !hasModel,
      action: () => router.push({ name: 'go-live' }),
    },
  ]
})

const completedSteps = computed(() => onboardingSteps.value.filter((s) => s.complete).length)

const quickActions = [
  {
    label: 'Publish a new API',
    icon: Zap,
    iconBg: 'bg-green-500/10',
    iconColor: 'text-green-600 dark:text-green-400',
    click: () => router.push({ name: 'go-live' }),
  },
  {
    label: 'Add a data source',
    icon: FileText,
    iconBg: 'bg-blue-500/10',
    iconColor: 'text-blue-600 dark:text-blue-400',
    click: () => router.push({ name: 'datasets' }),
  },
  {
    label: 'Connect a model',
    icon: Brain,
    iconBg: 'bg-indigo-500/10',
    iconColor: 'text-indigo-600 dark:text-indigo-400',
    click: () => router.push({ name: 'models' }),
  },
  {
    label: 'View analytics',
    icon: BarChart3,
    iconBg: 'bg-amber-500/10',
    iconColor: 'text-amber-600 dark:text-amber-400',
    click: () => router.push({ name: 'analytics' }),
  },
]

const resources = [
  { label: 'Quickstart', href: 'http://syft.docs.openmined.org/space/quickstart' },
  { label: 'Documentation', href: 'http://syft.docs.openmined.org/space' },
  { label: 'OpenMined Discord', href: 'https://discord.gg/openmined' },
  { label: 'GitHub', href: 'https://github.com/OpenMined' },
]

const docs = [
  {
    title: 'Quickstart',
    desc: 'Get up and running in 5 minutes.',
    icon: Zap,
    iconBg: 'bg-green-500/10',
    iconColor: 'text-green-600 dark:text-green-400',
    href: 'http://syft.docs.openmined.org/space/quickstart',
  },
  {
    title: 'Publish documents',
    desc: 'Share PDFs and datasets securely.',
    icon: FileText,
    iconBg: 'bg-blue-500/10',
    iconColor: 'text-blue-600 dark:text-blue-400',
    href: 'http://syft.docs.openmined.org/space/components/datasets',
  },
  {
    title: 'Connect AI models',
    desc: 'Link your vLLM or OpenAI models.',
    icon: Brain,
    iconBg: 'bg-indigo-500/10',
    iconColor: 'text-indigo-600 dark:text-indigo-400',
    href: 'http://syft.docs.openmined.org/space/components/models',
  },
  {
    title: 'Configure policies',
    desc: 'Rate limits, pricing, and access.',
    icon: Shield,
    iconBg: 'bg-purple-500/10',
    iconColor: 'text-purple-600 dark:text-purple-400',
    href: 'http://syft.docs.openmined.org/space/components/policies',
  },
]

const loadResourceCounts = async () => {
  resourcesLoaded.value = false
  try {
    const [datasets, models] = await Promise.all([
      datasetsApi.list().catch(() => []),
      modelsApi.list().catch(() => []),
    ])
    datasetCount.value = datasets.length
    modelCount.value = models.length
  } finally {
    resourcesLoaded.value = true
  }
}

const refreshDashboard = () => {
  endpointsStore.fetchEndpoints({ force: true })
  loadResourceCounts()
}

onMounted(() => {
  endpointsStore.fetchEndpoints()
  loadResourceCounts()
})
</script>
