<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Database,
  Brain,
  Plus,
  Loader2,
  Globe,
  Search,
  Sparkles,
  X,
  Pencil,
  Trash2,
  AlertTriangle,
  ExternalLink,
  Lightbulb,
  ChevronRight,
  ShieldCheck,
  Info,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { datasetsApi } from '@/api/endpoints/datasets'
import { modelsApi } from '@/api/endpoints/models'
import { endpointsApi } from '@/api/endpoints/endpoints'
import ModelSelector from '@/components/ModelSelector.vue'
import CreateDatasetDialogSimple from '@/components/CreateDatasetDialogSimple.vue'
import CreateModelDialogSimple from '@/components/CreateModelDialogSimple.vue'
import PolicyFormDialog from '@/components/PolicyFormDialog.vue'
import { MdEditor, MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { useGoLive } from '@/composables/useGoLive'
import { useTheme } from '@/composables/useTheme'
import { useUserStore } from '@/stores/user'
import {
  POLICY_TYPES,
  createEmptyPolicyRules,
  generateRuleId,
  getRuleSummary,
} from '@/config/policyTypes'
import type { PolicyTypeId, PolicyRulesRecord } from '@/config/policyTypes'
import type { GoLiveData, ResourceType, ResponseMode } from '@/composables/useGoLive'
import type { DatasetListItem, ModelListItem } from '@/api/types'

const router = useRouter()
const { isDark } = useTheme()
const userStore = useUserStore()
const { isCreating, creationStep, creationError, goLive } = useGoLive()

const currentStep = ref(1)
const totalSteps = 4

const steps = [
  { num: 1, label: 'Choose', desc: 'Pick your resources' },
  { num: 2, label: 'Configure', desc: 'Set access & limits' },
  { num: 3, label: 'Details', desc: 'Name & describe' },
  { num: 4, label: 'Review', desc: 'Confirm & publish' },
]

const selectedDataSourceId = ref('')
const selectedModelId = ref('')
const datasets = ref<DatasetListItem[]>([])
const models = ref<ModelListItem[]>([])
const isLoadingResources = ref(false)

const resourceType = computed<ResourceType | ''>(() => {
  if (selectedDataSourceId.value) return 'data-source'
  if (selectedModelId.value) return 'model'
  return ''
})

const selectedResourceId = computed(() => {
  if (selectedDataSourceId.value) return selectedDataSourceId.value
  return selectedModelId.value
})

const loadResources = async () => {
  isLoadingResources.value = true
  try {
    const [ds, ms] = await Promise.all([datasetsApi.list(), modelsApi.list()])
    datasets.value = ds
    models.value = ms
  } catch (e) {
    console.error('Failed to load resources:', e)
  } finally {
    isLoadingResources.value = false
  }
}

onMounted(() => {
  loadResources()
})

const toggleDataSource = (id: string) => {
  selectedDataSourceId.value = selectedDataSourceId.value === id ? '' : id
}

const toggleModel = (id: string) => {
  selectedModelId.value = selectedModelId.value === id ? '' : id
}

const showCreateDatasetDialog = ref(false)
const showCreateModelDialog = ref(false)

const handleDatasetCreated = async () => {
  showCreateDatasetDialog.value = false
  datasets.value = await datasetsApi.list()
}

const handleModelCreated = async () => {
  showCreateModelDialog.value = false
  models.value = await modelsApi.list()
}

const responseMode = ref<ResponseMode>('raw')
const aiModelId = ref('')
const systemPrompt = ref('')
const showAiConfigDialog = ref(false)
const pendingResponseMode = ref<ResponseMode>('raw')

interface ResponseModeOption {
  id: ResponseMode
  icon: typeof Search
  iconClass: string
  title: string
  description: string
  badge?: string
  showUsingBadge: boolean
}

const RESPONSE_MODES: ResponseModeOption[] = [
  {
    id: 'raw',
    icon: Search,
    iconClass: 'text-blue-500',
    title: 'Search results',
    description:
      'Returns the raw matching documents from your data source. Best for structured data, APIs, or when consumers want to process results themselves.',
    badge: 'Default',
    showUsingBadge: false,
  },
  {
    id: 'summary',
    icon: Sparkles,
    iconClass: 'text-amber-500',
    title: 'AI-generated',
    description:
      'An AI model reads the matching documents and generates a natural-language answer. Great for Q&A, summaries, or conversational access to your data.',
    showUsingBadge: true,
  },
  {
    id: 'both',
    icon: Globe,
    iconClass: 'text-green-500',
    title: 'Both',
    description:
      'Returns the raw search results alongside an AI-generated summary. Consumers get the best of both worlds — verifiable sources plus a readable answer.',
    showUsingBadge: true,
  },
]

const PROMPT_PRESETS: Record<string, { label: string; prompt: string }> = {
  'summarise-cite': {
    label: 'Summarise and cite',
    prompt: `You are a helpful assistant that answers questions using the provided data source. When responding:
- Synthesise a clear, concise answer from the retrieved documents
- Cite the specific source document(s) for every claim
- If the data doesn't contain relevant information, say so clearly
- Keep responses well-structured with inline citations`,
  },
  'summarise-filter': {
    label: 'Summarise and filter',
    prompt: `You are a helpful assistant that answers questions using the provided data source. When responding:
- Summarise only the most relevant information from the retrieved documents
- Omit results that are not directly related to the user's question
- If the data doesn't contain relevant information, say so clearly
- Prioritise precision over completeness`,
  },
  other: {
    label: 'Other',
    prompt: '',
  },
}

const selectedPromptPreset = ref('summarise-cite')

const handlePromptPresetChange = (presetId: unknown) => {
  const id = typeof presetId === 'string' ? presetId : ''
  selectedPromptPreset.value = id
  systemPrompt.value = PROMPT_PRESETS[id]?.prompt ?? ''
}

const hasDataSource = computed(() => !!selectedDataSourceId.value)
const hasModel = computed(() => !!selectedModelId.value)
const showsResponseMode = computed(() => hasDataSource.value)
const needsModel = computed(() => {
  if (hasModel.value) return false
  return responseMode.value === 'summary' || responseMode.value === 'both'
})

const isDataOnlyRaw = computed(
  () => hasDataSource.value && !hasModel.value && responseMode.value === 'raw',
)

const apiTypeLabel = computed(() => {
  if (hasDataSource.value && hasModel.value) return 'Combined API'
  if (hasDataSource.value) return 'Data API'
  return 'Model API'
})

const openAiConfigDialog = (mode: ResponseMode) => {
  pendingResponseMode.value = mode
  if (!systemPrompt.value) {
    selectedPromptPreset.value = 'summarise-cite'
    systemPrompt.value = PROMPT_PRESETS['summarise-cite']?.prompt ?? ''
  }
  showAiConfigDialog.value = true
}

const handleResponseModeChange = (value: string) => {
  const mode = value as ResponseMode
  if ((mode === 'summary' || mode === 'both') && !hasModel.value) {
    openAiConfigDialog(mode)
  } else {
    responseMode.value = mode
  }
}

const confirmAiConfig = () => {
  responseMode.value = pendingResponseMode.value
  showAiConfigDialog.value = false
}

const cancelAiConfig = () => {
  showAiConfigDialog.value = false
}

const handleAiModelUpdate = (modelId: string) => {
  aiModelId.value = modelId
}

const aiModelName = computed(
  () => models.value.find((m) => m.id === aiModelId.value)?.name ?? '',
)

const piiFilterEnabled = ref(false)
watch(hasModel, (modelSelected) => {
  if (!modelSelected) piiFilterEnabled.value = false
})

const policyRules = ref<PolicyRulesRecord>(createEmptyPolicyRules())

const showPolicyDialog = ref(false)
const dialogPolicyType = ref<PolicyTypeId>('access')
const dialogInitialData = ref<Record<string, unknown> | null>(null)
const dialogEditingRuleId = ref<string | null>(null)

const openAddPolicyDialog = (policyType: PolicyTypeId) => {
  dialogPolicyType.value = policyType
  dialogInitialData.value = null
  dialogEditingRuleId.value = null
  showPolicyDialog.value = true
}

const openEditPolicyDialog = (policyType: PolicyTypeId, ruleId: string) => {
  const rule = policyRules.value[policyType].find((r) => r.id === ruleId)
  if (!rule) return
  dialogPolicyType.value = policyType
  dialogInitialData.value = { ...rule.config }
  dialogEditingRuleId.value = ruleId
  showPolicyDialog.value = true
}

const handlePolicyDialogSave = (payload: {
  policyType: PolicyTypeId
  formData: Record<string, unknown>
}) => {
  const { policyType, formData: policyFormData } = payload

  if (dialogEditingRuleId.value) {
    const rule = policyRules.value[policyType].find((r) => r.id === dialogEditingRuleId.value)
    if (rule) {
      rule.config = {
        ...policyFormData,
        id: rule.id,
      } as PolicyRulesRecord[PolicyTypeId][number]['config']
    }
  } else {
    const ruleId = generateRuleId()
    policyRules.value[policyType].push({
      id: ruleId,
      config: {
        ...policyFormData,
        id: ruleId,
      } as PolicyRulesRecord[PolicyTypeId][number]['config'],
      isEditing: false,
    })
  }

  showPolicyDialog.value = false
  dialogEditingRuleId.value = null
  dialogInitialData.value = null
}

const deletePolicy = (policyType: PolicyTypeId, ruleId: string) => {
  const index = policyRules.value[policyType].findIndex((r) => r.id === ruleId)
  if (index > -1) {
    policyRules.value[policyType].splice(index, 1)
  }
}

const totalRuleCount = computed(() =>
  Object.values(policyRules.value).reduce((sum, rules) => sum + rules.length, 0),
)

const name = ref('')
const summary = ref('')
const description = ref('')
const tags = ref<string[]>([])
const tagInput = ref('')

const isValidSlug = (val: string): boolean => /^[a-z0-9]+(-[a-z0-9]+)*$/.test(val)

const isCheckingName = ref(false)
const nameAvailability = ref<'available' | 'taken' | null>(null)
let nameDebounce: ReturnType<typeof setTimeout> | null = null

const endpointNameError = computed(() => {
  if (!name.value.trim()) return null
  if (!isValidSlug(name.value.trim())) {
    return 'Use lowercase letters, numbers, and hyphens only (e.g., my-data-source)'
  }
  if (nameAvailability.value === 'taken') {
    return 'This name is already taken. Choose a different name.'
  }
  return null
})

const checkNameAvailability = (val: string) => {
  if (!val || !isValidSlug(val)) {
    nameAvailability.value = null
    return
  }
  isCheckingName.value = true
  nameAvailability.value = null

  if (nameDebounce) clearTimeout(nameDebounce)
  nameDebounce = setTimeout(async () => {
    try {
      const result = await endpointsApi.validateSlug({
        slug: val,
        check_all_marketplaces: true,
      })
      const localOk = result.local_available
      const mktOk = !result.marketplaces || result.marketplaces.every((m) => m.available !== false)
      nameAvailability.value = localOk && mktOk ? 'available' : 'taken'
    } catch (error) {
      console.error('Failed to check name availability:', error)
      nameAvailability.value = null
    } finally {
      isCheckingName.value = false
    }
  }, 400)
}

watch(name, (val) => {
  nameAvailability.value = null
  checkNameAvailability(val.trim())
})

onBeforeUnmount(() => {
  if (nameDebounce) clearTimeout(nameDebounce)
})

const popularTags = ['legal', 'medical', 'research', 'finance', 'education', 'news', 'technical']

const addTag = () => {
  const t = tagInput.value.trim()
  if (t && !tags.value.includes(t)) {
    tags.value.push(t)
  }
  tagInput.value = ''
}

const addSuggestedTag = (tag: string) => {
  if (!tags.value.includes(tag)) {
    tags.value.push(tag)
  }
}

const removeTag = (tag: string) => {
  tags.value = tags.value.filter((t) => t !== tag)
}

const handleTagKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addTag()
  }
}

const defaultDescriptionTemplate = `## Overview
Brief summary of what this resource contains and its primary purpose...

## Content Description
- **Data types**: Text, images, numerical data, etc.
- **Size**: Number of records, files, or approximate volume
- **Format**: CSV, JSON, PDF, etc.

## Potential Use Cases
- Research applications
- Business intelligence
- Educational purposes

## Data Quality & Limitations
- **Completeness**: Any missing data or gaps
- **Accuracy**: Known issues or validation status

## Citation & Attribution
How to properly cite or credit this when used...`

const fillExampleData = (exampleType: 'news' | 'research' | 'library') => {
  switch (exampleType) {
    case 'news':
      name.value = 'herald-tribune-archives'
      summary.value = 'Historical news articles from 2010-2024'
      tags.value = ['news', 'journalism', 'politics', 'business', 'local-news']
      break
    case 'research':
      name.value = 'cancer-research-publications'
      summary.value = 'Peer-reviewed cancer research papers and clinical studies'
      tags.value = ['research', 'medical', 'oncology', 'clinical-trials', 'peer-reviewed']
      break
    case 'library':
      name.value = 'technical-manuals-collection'
      summary.value = 'Product guides and technical documentation'
      tags.value = ['documentation', 'technical', 'manuals', 'api', 'guides']
      break
  }
  checkNameAvailability(name.value)
}

const showOverwriteDialog = ref(false)
const showDescriptionPreview = ref(false)
const isCheckingBeforePublish = ref(false)

const existingEndpointUrl = computed(() => userStore.getEndpointUrlInMarketplace(name.value))

const canProceedStep1 = computed(() => !!selectedDataSourceId.value || !!selectedModelId.value)

const canProceedStep2 = computed(() => {
  if (
    showsResponseMode.value &&
    (responseMode.value === 'summary' || responseMode.value === 'both')
  ) {
    if (!hasModel.value && !aiModelId.value) return false
  }
  return true
})

const canProceedStep3 = computed(() => {
  const n = name.value.trim()
  return (
    n !== '' &&
    isValidSlug(n) &&
    nameAvailability.value === 'available' &&
    !isCheckingName.value &&
    summary.value.trim() !== ''
  )
})

const canProceed = computed(() => {
  if (currentStep.value === 1) return canProceedStep1.value
  if (currentStep.value === 2) return canProceedStep2.value
  if (currentStep.value === 3) return canProceedStep3.value
  return true
})

const nextStep = () => {
  if (currentStep.value < totalSteps && canProceed.value) {
    currentStep.value++
  }
}

const prevStep = () => {
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

const goToStep = (step: number) => {
  if (step < currentStep.value) {
    currentStep.value = step
  }
}

const selectedDataSourceName = computed(
  () => datasets.value.find((d) => d.id === selectedDataSourceId.value)?.name ?? '',
)
const selectedModelName = computed(
  () => models.value.find((m) => m.id === selectedModelId.value)?.name ?? '',
)

const responseModeLabel = computed(() => {
  const map: Record<string, string> = {
    raw: 'Search results only',
    summary: 'AI-generated response',
    both: 'Search + AI-generated',
  }
  return map[responseMode.value] || responseMode.value
})

const buildGoLiveData = (): GoLiveData => ({
  resourceType: resourceType.value as ResourceType,
  resourceId: selectedResourceId.value,
  responseMode: responseMode.value,
  aiModelId: hasModel.value ? selectedModelId.value : aiModelId.value,
  systemPrompt: systemPrompt.value.trim(),
  policyRules: policyRules.value,
  piiFilterEnabled: piiFilterEnabled.value,
  name: name.value.trim(),
  summary: summary.value.trim(),
  description: description.value.trim(),
  tags: tags.value,
  dataSourceId: selectedDataSourceId.value || undefined,
  modelId: selectedModelId.value || undefined,
})

const handleGoLive = async () => {
  isCheckingBeforePublish.value = true
  try {
    const result = await endpointsApi.validateSlug({
      slug: name.value.trim(),
      check_all_marketplaces: true,
    })
    const mktOk = !result.marketplaces || result.marketplaces.every((m) => m.available !== false)
    if (!mktOk) {
      showOverwriteDialog.value = true
      return
    }
  } catch (error) {
    console.error('Pre-publish slug check failed:', error)
  } finally {
    isCheckingBeforePublish.value = false
  }

  await goLive(buildGoLiveData())
}

const handleOverwriteConfirm = async () => {
  showOverwriteDialog.value = false
  await goLive(buildGoLiveData())
}
</script>

<template>
  <div class="min-h-screen bg-background text-foreground flex">
    <!-- Left step indicator -->
    <aside class="hidden lg:flex w-56 shrink-0 border-r border-border bg-muted/20">
      <div class="flex flex-col w-full p-6">
        <button
          class="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-10"
          @click="router.push({ name: 'endpoints' })"
        >
          <ArrowLeft class="h-4 w-4" />
          Back to APIs
        </button>

        <h2 class="text-lg font-semibold text-foreground mb-8">Publish</h2>

        <nav class="space-y-2">
          <button
            v-for="step in steps"
            :key="step.num"
            class="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm transition-colors text-left"
            :class="{
              'bg-primary/10 text-primary font-medium': currentStep === step.num,
              'text-foreground': currentStep > step.num,
              'text-muted-foreground': currentStep < step.num,
            }"
            @click="goToStep(step.num)"
          >
            <span
              class="flex items-center justify-center h-6 w-6 rounded-full text-xs font-medium shrink-0"
              :class="{
                'bg-primary text-primary-foreground': currentStep === step.num,
                'bg-primary/20 text-primary': currentStep > step.num,
                'bg-muted text-muted-foreground': currentStep < step.num,
              }"
            >
              <Check v-if="currentStep > step.num" class="h-3.5 w-3.5" />
              <template v-else>{{ step.num }}</template>
            </span>
            <div class="min-w-0">
              <p class="leading-none">{{ step.label }}</p>
              <p class="text-[11px] font-normal text-muted-foreground mt-0.5">{{ step.desc }}</p>
            </div>
          </button>
        </nav>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 flex flex-col min-h-screen">
      <!-- Mobile header -->
      <header class="lg:hidden flex items-center gap-3 p-4 border-b border-border">
        <button
          class="text-muted-foreground hover:text-foreground"
          @click="router.push({ name: 'endpoints' })"
        >
          <ArrowLeft class="h-5 w-5" />
        </button>
        <span class="font-semibold">Publish</span>
        <span class="text-sm text-muted-foreground ml-auto">
          Step {{ currentStep }} of {{ totalSteps }}
        </span>
      </header>

      <!-- Step content -->
      <div class="flex-1 overflow-y-auto">
        <div class="max-w-2xl mx-auto px-6 py-10">
          <!-- ============ STEP 1: Pick your resource(s) ============ -->
          <div v-if="currentStep === 1">
            <h1 class="text-2xl font-semibold text-foreground mb-2">Pick your resource(s)</h1>
            <p class="text-muted-foreground mb-8">
              Select a data source, a model, or both to publish.
            </p>

            <div v-if="isLoadingResources" class="flex items-center justify-center py-20">
              <Loader2 class="h-6 w-6 animate-spin text-muted-foreground" />
            </div>

            <template v-else>
              <!-- Data Sources -->
              <div class="mb-8">
                <div class="flex items-center gap-2 mb-3">
                  <Database class="h-4 w-4 text-muted-foreground" />
                  <h3 class="text-sm font-semibold text-foreground">Data Sources</h3>
                  <Badge v-if="selectedDataSourceId" variant="secondary" class="text-[10px]">
                    1 selected
                  </Badge>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    v-for="ds in datasets"
                    :key="ds.id"
                    class="p-4 rounded-lg border text-left transition-all hover:shadow-xs"
                    :class="
                      selectedDataSourceId === ds.id
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/40'
                    "
                    @click="toggleDataSource(ds.id)"
                  >
                    <div class="flex items-start justify-between gap-2">
                      <div class="min-w-0">
                        <p class="font-medium text-foreground truncate">{{ ds.name }}</p>
                        <p class="text-xs text-muted-foreground mt-1 line-clamp-2">
                          {{ ds.summary || 'No description' }}
                        </p>
                      </div>
                      <div
                        v-if="selectedDataSourceId === ds.id"
                        class="shrink-0 h-5 w-5 rounded-full bg-primary flex items-center justify-center"
                      >
                        <Check class="h-3 w-3 text-primary-foreground" />
                      </div>
                    </div>
                    <div v-if="ds.tags" class="flex flex-wrap gap-1 mt-2">
                      <Badge
                        v-for="tag in ds.tags.split(',').slice(0, 3)"
                        :key="tag"
                        variant="secondary"
                        class="text-[10px]"
                      >
                        {{ tag.trim() }}
                      </Badge>
                    </div>
                  </button>

                  <button
                    class="p-4 rounded-lg border border-dashed border-border hover:border-primary/40 text-left transition-all flex items-center gap-3 text-muted-foreground hover:text-foreground"
                    @click="showCreateDatasetDialog = true"
                  >
                    <Plus class="h-5 w-5 shrink-0" />
                    <span class="text-sm font-medium">Add data source</span>
                  </button>
                </div>
              </div>

              <!-- Models -->
              <div>
                <div class="flex items-center gap-2 mb-3">
                  <Brain class="h-4 w-4 text-muted-foreground" />
                  <h3 class="text-sm font-semibold text-foreground">Models</h3>
                  <Badge v-if="selectedModelId" variant="secondary" class="text-[10px]">
                    1 selected
                  </Badge>
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <button
                    v-for="m in models"
                    :key="m.id"
                    class="p-4 rounded-lg border text-left transition-all hover:shadow-xs"
                    :class="
                      selectedModelId === m.id
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/40'
                    "
                    @click="toggleModel(m.id)"
                  >
                    <div class="flex items-start justify-between gap-2">
                      <div class="min-w-0">
                        <p class="font-medium text-foreground truncate">{{ m.name }}</p>
                        <p class="text-xs text-muted-foreground mt-1 line-clamp-2">
                          {{ m.summary || m.dtype }}
                        </p>
                      </div>
                      <div
                        v-if="selectedModelId === m.id"
                        class="shrink-0 h-5 w-5 rounded-full bg-primary flex items-center justify-center"
                      >
                        <Check class="h-3 w-3 text-primary-foreground" />
                      </div>
                    </div>
                  </button>

                  <button
                    class="p-4 rounded-lg border border-dashed border-border hover:border-primary/40 text-left transition-all flex items-center gap-3 text-muted-foreground hover:text-foreground"
                    @click="showCreateModelDialog = true"
                  >
                    <Plus class="h-5 w-5 shrink-0" />
                    <span class="text-sm font-medium">Add model</span>
                  </button>
                </div>
              </div>
            </template>
          </div>

          <!-- ============ STEP 2: Configure ============ -->
          <div v-if="currentStep === 2">
            <h1 class="text-2xl font-semibold text-foreground mb-2">Configure</h1>
            <p class="text-muted-foreground mb-8">Set up how people can access your resource.</p>

            <div class="space-y-8">
              <!-- Response mode (data sources only) -->
              <section v-if="showsResponseMode">
                <div class="flex items-center gap-2 mb-4">
                  <Search class="h-4 w-4 text-muted-foreground" />
                  <h3 class="text-sm font-semibold text-foreground">Response mode</h3>
                </div>
                <p class="text-sm text-muted-foreground mb-4">
                  When someone queries your data source, how should they receive results?
                </p>

                <div class="space-y-3">
                  <button
                    v-for="mode in RESPONSE_MODES"
                    :key="mode.id"
                    class="w-full flex items-start gap-3 p-4 rounded-lg border text-left transition-all"
                    :class="
                      responseMode === mode.id
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/40'
                    "
                    @click="handleResponseModeChange(mode.id)"
                  >
                    <div
                      class="shrink-0 mt-0.5 h-4 w-4 rounded-full border-2 flex items-center justify-center"
                      :class="
                        responseMode === mode.id
                          ? 'border-primary bg-primary'
                          : 'border-muted-foreground/40'
                      "
                    >
                      <div
                        v-if="responseMode === mode.id"
                        class="h-1.5 w-1.5 rounded-full bg-primary-foreground"
                      />
                    </div>
                    <div class="flex-1">
                      <div class="flex items-center gap-2">
                        <component :is="mode.icon" class="h-3.5 w-3.5" :class="mode.iconClass" />
                        <p class="font-medium text-sm text-foreground">{{ mode.title }}</p>
                        <Badge v-if="mode.badge" variant="secondary" class="text-[10px]">
                          {{ mode.badge }}
                        </Badge>
                      </div>
                      <p class="text-xs text-muted-foreground mt-1">{{ mode.description }}</p>
                      <div
                        v-if="mode.showUsingBadge && responseMode === mode.id && (hasModel || aiModelId)"
                        class="mt-2 flex items-center gap-2 text-xs text-primary"
                      >
                        <Check class="h-3 w-3" />
                        <span>
                          Using
                          <strong>{{
                            hasModel ? selectedModelName : aiModelName || 'selected model'
                          }}</strong>
                        </span>
                        <button
                          v-if="!hasModel"
                          class="underline hover:no-underline text-muted-foreground"
                          @click.stop="openAiConfigDialog(mode.id)"
                        >
                          Edit
                        </button>
                      </div>
                    </div>
                  </button>
                </div>

                <!-- Validation hint -->
                <p
                  v-if="needsModel && !aiModelId && !hasModel"
                  class="mt-3 text-xs text-amber-600 flex items-center gap-1.5"
                >
                  <AlertTriangle class="h-3 w-3" />
                  Select an AI model to continue
                </p>

                <!-- Data-only / raw callout -->
                <div
                  v-if="isDataOnlyRaw"
                  class="mt-4 flex items-start gap-3 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/40 px-4 py-3"
                >
                  <Info class="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
                  <div>
                    <p class="text-sm font-medium text-blue-900 dark:text-blue-300">
                      This API is search-only
                    </p>
                    <p class="text-xs text-blue-700 dark:text-blue-400 mt-0.5">
                      It won't appear in the Chat model selector. It can be attached as a data
                      context when testing other model APIs in Chat.
                    </p>
                  </div>
                </div>

                <Separator class="mt-8" />
              </section>

              <!-- PII Filter (model endpoints only) -->
              <section v-if="hasModel">
                <div
                  class="flex items-start justify-between gap-4 p-4 rounded-lg border transition-all"
                  :class="
                    piiFilterEnabled ? 'border-primary/30 bg-primary/5' : 'border-border bg-card'
                  "
                >
                  <div class="flex items-start gap-3 flex-1 min-w-0">
                    <div
                      class="mt-0.5 p-1.5 rounded-md shrink-0"
                      :class="piiFilterEnabled ? 'bg-primary/10' : 'bg-muted'"
                    >
                      <ShieldCheck
                        class="h-4 w-4"
                        :class="piiFilterEnabled ? 'text-primary' : 'text-muted-foreground'"
                      />
                    </div>
                    <div>
                      <div class="flex items-center gap-1.5">
                        <h3 class="text-sm font-semibold text-foreground">PII Filter</h3>
                        <TooltipProvider :delay-duration="0">
                          <Tooltip>
                            <TooltipTrigger as-child>
                              <Info class="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                            </TooltipTrigger>
                            <TooltipContent side="top" class="max-w-[300px]">
                              The AI model reviews its own response and replaces any personally
                              identifiable information (names, emails, phone numbers, addresses,
                              IDs) with [REDACTED] before the response is returned. Only
                              available for model endpoints.
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </div>
                      <p class="text-xs text-muted-foreground mt-0.5">
                        Redact information that is PII (names, addresses, etc).
                      </p>
                      <div
                        v-if="piiFilterEnabled"
                        class="mt-2 flex items-center gap-1.5 text-xs text-primary"
                      >
                        <ShieldCheck class="h-3 w-3" />
                        Responses will be filtered before delivery
                      </div>
                    </div>
                  </div>
                  <Switch v-model="piiFilterEnabled" class="mt-1 shrink-0" />
                </div>

                <Separator class="mt-8" />
              </section>

              <!-- Policy sections -->
              <div v-for="policyType in POLICY_TYPES" :key="policyType.id" class="space-y-4">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <component :is="policyType.icon" class="h-4 w-4 text-muted-foreground" />
                    <div>
                      <h3 class="text-sm font-semibold text-foreground">{{ policyType.name }}</h3>
                      <p class="text-xs text-muted-foreground">{{ policyType.description }}</p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    class="gap-1.5"
                    @click="openAddPolicyDialog(policyType.id)"
                  >
                    <Plus class="h-3.5 w-3.5" />
                    Add rule
                  </Button>
                </div>

                <div
                  v-if="policyRules[policyType.id]?.length === 0"
                  class="rounded-lg border border-dashed border-border bg-muted/30 px-4 py-3"
                >
                  <p class="text-sm text-muted-foreground">
                    <template v-if="policyType.id === 'access'"
                      >No access rules — everyone can query this resource.</template
                    >
                    <template v-else-if="policyType.id === 'rate_limit'"
                      >No usage limits — unlimited usage.</template
                    >
                    <template v-else>No pricing rules — free for all users.</template>
                  </p>
                </div>

                <div v-if="policyRules[policyType.id]?.length > 0" class="space-y-2">
                  <div
                    v-for="rule in policyRules[policyType.id]"
                    :key="rule.id"
                    class="flex items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3"
                  >
                    <p class="text-sm text-foreground min-w-0 truncate">
                      {{ getRuleSummary(policyType.id, rule.config) }}
                    </p>
                    <div class="flex items-center gap-1 shrink-0">
                      <Button
                        variant="ghost"
                        size="icon"
                        class="h-7 w-7"
                        @click="openEditPolicyDialog(policyType.id, rule.id)"
                      >
                        <Pencil class="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        class="h-7 w-7 text-destructive hover:text-destructive"
                        @click="deletePolicy(policyType.id, rule.id)"
                      >
                        <Trash2 class="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </div>

                <Separator v-if="policyType.id !== 'pricing'" class="mt-4" />
              </div>
            </div>
          </div>

          <!-- ============ STEP 3: Details ============ -->
          <div v-if="currentStep === 3">
            <h1 class="text-2xl font-semibold text-foreground mb-2">Describe your resource</h1>
            <p class="text-muted-foreground mb-6">
              Give your resource a name and description so others know what you're sharing.
            </p>

            <!-- Example prefillers -->
            <div class="mb-8 bg-muted/50 border border-border/50 rounded-lg p-4">
              <h4 class="font-medium text-blue-900 dark:text-blue-300 mb-2 flex items-center gap-2">
                <Lightbulb class="w-4 h-4" />
                Popular examples to get you started
              </h4>
              <p class="text-sm text-blue-700 dark:text-blue-400 mb-4">
                Click any example to auto-fill the form
              </p>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                <button
                  class="bg-card p-3 rounded border hover:border-blue-400 hover:shadow-sm transition-all text-left"
                  @click="fillExampleData('news')"
                >
                  <p class="font-medium text-foreground">📰 News Archive</p>
                  <p class="text-muted-foreground mt-1">
                    Historical articles and investigative reports
                  </p>
                </button>
                <button
                  class="bg-card p-3 rounded border hover:border-blue-400 hover:shadow-sm transition-all text-left"
                  @click="fillExampleData('research')"
                >
                  <p class="font-medium text-foreground">🔬 Research Data</p>
                  <p class="text-muted-foreground mt-1">
                    Peer-reviewed papers and clinical studies
                  </p>
                </button>
                <button
                  class="bg-card p-3 rounded border hover:border-blue-400 hover:shadow-sm transition-all text-left"
                  @click="fillExampleData('library')"
                >
                  <p class="font-medium text-foreground">📚 Document Library</p>
                  <p class="text-muted-foreground mt-1">
                    Product guides and technical documentation
                  </p>
                </button>
              </div>
            </div>

            <div class="space-y-6">
              <!-- Name with inline availability indicator -->
              <div class="space-y-2">
                <Label for="go-live-name" class="text-sm font-medium">
                  Name <span class="text-red-500">*</span>
                </Label>
                <div class="relative">
                  <Input
                    id="go-live-name"
                    v-model="name"
                    placeholder="e.g., herald-tribune-archives"
                    class="w-full font-mono text-sm pr-10"
                    :class="{
                      'border-red-500 focus-visible:ring-red-500': endpointNameError,
                      'border-green-500 focus-visible:ring-green-500':
                        nameAvailability === 'available',
                    }"
                  />
                  <div
                    class="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none"
                  >
                    <Loader2
                      v-if="isCheckingName"
                      class="h-4 w-4 text-muted-foreground animate-spin"
                    />
                    <Check
                      v-else-if="nameAvailability === 'available'"
                      class="h-4 w-4 text-green-600"
                    />
                  </div>
                </div>
                <p v-if="endpointNameError" class="text-xs text-red-600">{{ endpointNameError }}</p>
                <p v-else-if="nameAvailability === 'available'" class="text-xs text-green-600">
                  This name is available
                </p>
                <p v-else class="text-xs text-muted-foreground">
                  This appears when people discover it. Use lowercase letters, numbers, and hyphens
                  only.
                </p>
              </div>

              <!-- Summary -->
              <div class="space-y-2">
                <Label for="go-live-summary" class="text-sm font-medium">
                  Short Description <span class="text-red-500">*</span>
                </Label>
                <Input
                  id="go-live-summary"
                  v-model="summary"
                  placeholder="e.g., Historical news articles from 2010-2024"
                />
                <p class="text-xs text-muted-foreground">
                  This appears when people browse available content
                </p>
              </div>

              <!-- Tags -->
              <div class="space-y-2">
                <Label class="text-sm font-medium">Tags (optional)</Label>
                <div class="space-y-2">
                  <div class="flex gap-2">
                    <Input
                      v-model="tagInput"
                      placeholder="Add keywords like: legal, medical, research"
                      class="flex-1"
                      @keydown="handleTagKeydown"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      :disabled="!tagInput.trim()"
                      @click="addTag"
                    >
                      <Plus class="h-4 w-4" />
                    </Button>
                  </div>
                  <!-- Popular suggestions -->
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="text-xs text-muted-foreground">Popular:</span>
                    <Button
                      v-for="suggestion in popularTags"
                      :key="suggestion"
                      variant="ghost"
                      size="sm"
                      class="h-6 px-2 text-xs"
                      :disabled="tags.includes(suggestion)"
                      @click="addSuggestedTag(suggestion)"
                    >
                      {{ suggestion }}
                    </Button>
                  </div>

                  <!-- Selected tags -->
                  <div v-if="tags.length > 0" class="flex flex-wrap gap-2 mt-1">
                    <Badge v-for="tag in tags" :key="tag" variant="secondary" class="px-3 py-1">
                      {{ tag }}
                      <button
                        class="ml-2 hover:text-destructive transition-colors"
                        @click="removeTag(tag)"
                      >
                        <X class="h-3 w-3" />
                      </button>
                    </Badge>
                  </div>
                </div>
              </div>

              <!-- Description (optional) -->
              <div class="space-y-2">
                <Label class="text-sm font-medium">Description (optional)</Label>
                <p class="text-xs text-muted-foreground">
                  Add a longer description with formatting if you'd like.
                </p>
                <MdEditor
                  :model-value="description || defaultDescriptionTemplate"
                  @update:model-value="description = $event"
                  :height="200"
                  :theme="isDark ? 'dark' : 'light'"
                  :toolbars="[
                    'bold',
                    'italic',
                    'title',
                    'strikeThrough',
                    'unorderedList',
                    'orderedList',
                    'link',
                    'code',
                    'codeRow',
                  ]"
                  preview-theme="github"
                  code-theme="github"
                  language="en-US"
                />
              </div>
            </div>
          </div>

          <!-- ============ STEP 4: Review ============ -->
          <div v-if="currentStep === 4">
            <!-- Header -->
            <div v-if="!isCreating" class="text-center mb-8">
              <div
                class="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto mb-4"
              >
                <Check class="w-8 h-8 text-green-600 dark:text-green-400" />
              </div>
              <h1 class="text-2xl font-semibold text-foreground mb-2">Ready to Publish!</h1>
              <p class="text-muted-foreground max-w-md mx-auto">
                Review the summary below and hit Publish when you're ready.
              </p>
            </div>

            <!-- Creation progress -->
            <div v-if="isCreating" class="text-center mb-8">
              <div
                class="w-16 h-16 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center mx-auto mb-4 animate-pulse"
              >
                <Loader2 class="w-8 h-8 text-blue-600 dark:text-blue-400 animate-spin" />
              </div>
              <h2 class="text-xl font-semibold text-foreground mb-2">Publishing...</h2>
              <p class="text-muted-foreground">
                {{ creationStep || 'Setting up your resource...' }}
              </p>
            </div>

            <!-- Summary card -->
            <Card v-if="!isCreating" class="p-8 space-y-6">
              <h3 class="text-lg font-semibold text-foreground">Summary</h3>

              <!-- Name & Resource -->
              <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <p class="text-xs font-medium text-muted-foreground mb-1">Name</p>
                  <p class="text-foreground font-medium font-mono">{{ name }}</p>
                </div>
                <div>
                  <p class="text-xs font-medium text-muted-foreground mb-1">Resource(s)</p>
                  <div class="space-y-1.5">
                    <div v-if="selectedDataSourceName" class="flex items-center gap-2">
                      <Database class="h-4 w-4 text-blue-500" />
                      <span class="text-foreground">{{ selectedDataSourceName }}</span>
                      <Badge variant="secondary" class="text-[10px]">Data Source</Badge>
                    </div>
                    <div v-if="selectedModelName" class="flex items-center gap-2">
                      <Brain class="h-4 w-4 text-purple-500" />
                      <span class="text-foreground">{{ selectedModelName }}</span>
                      <Badge variant="secondary" class="text-[10px]">Model</Badge>
                    </div>
                  </div>
                </div>
              </div>

              <!-- API Type -->
              <div>
                <p class="text-xs font-medium text-muted-foreground mb-1">API Type</p>
                <div class="flex items-center gap-2">
                  <span class="text-foreground font-medium">{{ apiTypeLabel }}</span>
                  <span
                    v-if="isDataOnlyRaw"
                    class="text-xs text-blue-600 dark:text-blue-400"
                  >— search-only, not available in Chat model selector</span>
                </div>
              </div>

              <!-- Summary text -->
              <div>
                <p class="text-xs font-medium text-muted-foreground mb-1">Summary</p>
                <p class="text-foreground leading-relaxed">{{ summary }}</p>
              </div>

              <!-- Description preview (collapsible) -->
              <div v-if="description && description.trim()" class="border-t pt-6">
                <button
                  class="flex items-center gap-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
                  @click="showDescriptionPreview = !showDescriptionPreview"
                >
                  <ChevronRight
                    class="h-3.5 w-3.5 transition-transform"
                    :class="showDescriptionPreview ? 'rotate-90' : ''"
                  />
                  Description
                </button>
                <div v-if="showDescriptionPreview" class="mt-3">
                  <MdPreview
                    :model-value="description"
                    :theme="isDark ? 'dark' : 'light'"
                    :show-code-row-number="false"
                    class="text-sm"
                  />
                </div>
              </div>

              <!-- Tags -->
              <div v-if="tags.length > 0" class="border-t pt-6">
                <p class="text-xs font-medium text-muted-foreground mb-3">Tags</p>
                <div class="flex flex-wrap gap-2">
                  <Badge
                    v-for="tag in tags"
                    :key="tag"
                    variant="outline"
                    class="bg-primary/10 text-primary border-primary px-3 py-1"
                  >
                    {{ tag }}
                  </Badge>
                </div>
              </div>

              <!-- Output configuration -->
              <div v-if="showsResponseMode" class="border-t pt-6">
                <p class="text-xs font-medium text-muted-foreground mb-3">Response Mode</p>
                <div class="bg-muted/50 rounded-lg p-4 space-y-3">
                  <div class="flex items-start gap-3">
                    <Search v-if="responseMode === 'raw'" class="w-4 h-4 text-primary mt-0.5" />
                    <Sparkles
                      v-else-if="responseMode === 'summary'"
                      class="w-4 h-4 text-amber-500 mt-0.5"
                    />
                    <Globe v-else class="w-4 h-4 text-green-600 mt-0.5" />
                    <div>
                      <span class="font-medium text-foreground text-sm">{{
                        responseModeLabel
                      }}</span>
                      <span
                        v-if="hasModel && selectedModelName"
                        class="text-sm text-muted-foreground ml-1"
                      >
                        — {{ selectedModelName }}
                      </span>
                      <span v-else-if="aiModelName" class="text-sm text-muted-foreground ml-1">
                        — {{ aiModelName }}
                      </span>
                    </div>
                  </div>
                  <div v-if="needsModel && systemPrompt.trim()" class="pt-3 border-t border-border">
                    <p class="text-xs font-medium text-muted-foreground mb-1">System Prompt</p>
                    <p
                      class="text-xs text-muted-foreground bg-muted rounded px-3 py-2 font-mono line-clamp-4 whitespace-pre-line"
                    >
                      {{ systemPrompt }}
                    </p>
                  </div>
                </div>
              </div>

              <!-- PII Filter -->
              <div v-if="piiFilterEnabled" class="border-t pt-6">
                <p class="text-xs font-medium text-muted-foreground mb-3">Output Filter</p>
                <div class="bg-muted/50 rounded-lg p-4 flex items-center gap-3">
                  <ShieldCheck class="w-4 h-4 text-primary shrink-0" />
                  <div>
                    <span class="font-medium text-foreground text-sm">PII Filter enabled</span>
                    <p class="text-xs text-muted-foreground mt-0.5">
                      Personal information will be automatically redacted from responses
                    </p>
                  </div>
                </div>
              </div>

              <!-- Policies -->
              <div v-if="totalRuleCount > 0" class="border-t pt-6">
                <p class="text-xs font-medium text-muted-foreground mb-3">Access Policies</p>
                <div class="space-y-4">
                  <template v-for="policyType in POLICY_TYPES" :key="policyType.id">
                    <div
                      v-if="policyRules[policyType.id]?.length > 0"
                      class="bg-muted/50 rounded-lg p-4"
                    >
                      <div class="flex items-center gap-2 mb-3">
                        <component :is="policyType.icon" class="w-4 h-4 text-muted-foreground" />
                        <span class="text-sm font-medium text-foreground">{{
                          policyType.name
                        }}</span>
                        <Badge variant="secondary" class="text-xs">
                          {{ policyRules[policyType.id].length }}
                          {{ policyRules[policyType.id].length === 1 ? 'rule' : 'rules' }}
                        </Badge>
                      </div>
                      <div class="space-y-2">
                        <div
                          v-for="(rule, index) in policyRules[policyType.id]"
                          :key="rule.id"
                          class="bg-card/50 border border-border/50 rounded-lg p-3"
                        >
                          <h4 class="text-sm font-medium text-foreground mb-0.5">
                            {{ rule.config.note || `${policyType.name} Rule #${index + 1}` }}
                          </h4>
                          <p class="text-xs text-muted-foreground">
                            {{ getRuleSummary(policyType.id, rule.config) }}
                          </p>
                        </div>
                      </div>
                    </div>
                  </template>
                </div>
              </div>

              <div v-else class="border-t pt-6">
                <p class="text-xs font-medium text-muted-foreground mb-1">Access Policies</p>
                <p class="text-sm text-muted-foreground">
                  No policies configured — open to everyone with no limits, free to use.
                </p>
              </div>
            </Card>

            <!-- Error -->
            <div
              v-if="creationError"
              class="mt-6 p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg"
            >
              <div class="flex items-start gap-3">
                <X class="w-5 h-5 text-red-500 dark:text-red-400 shrink-0 mt-0.5" />
                <div class="flex-1">
                  <h4 class="font-medium text-red-900 dark:text-red-300 mb-1">Failed to publish</h4>
                  <p class="text-sm text-red-700 dark:text-red-400">{{ creationError }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Bottom bar -->
      <footer class="shrink-0 border-t border-border bg-background px-6 py-4">
        <div class="max-w-2xl mx-auto flex items-center justify-between">
          <Button v-if="currentStep > 1" variant="ghost" @click="prevStep" :disabled="isCreating">
            <ArrowLeft class="h-4 w-4 mr-2" />
            Back
          </Button>
          <div v-else />

          <Button v-if="currentStep < totalSteps" :disabled="!canProceed" @click="nextStep">
            Next
            <ArrowRight class="h-4 w-4 ml-2" />
          </Button>

          <Button
            v-else
            :disabled="isCreating || isCheckingBeforePublish"
            class="bg-primary hover:bg-primary/90 text-primary-foreground"
            @click="handleGoLive"
          >
            <template v-if="isCheckingBeforePublish">
              <Loader2 class="h-4 w-4 mr-2 animate-spin" />
              Checking...
            </template>
            <template v-else-if="isCreating">
              <Loader2 class="h-4 w-4 mr-2 animate-spin" />
              {{ creationStep }}
            </template>
            <template v-else>
              <Globe class="h-4 w-4 mr-2" />
              Publish
            </template>
          </Button>
        </div>
      </footer>
    </main>

    <!-- Policy form dialog -->
    <PolicyFormDialog
      v-model:open="showPolicyDialog"
      :policy-type="dialogPolicyType"
      :initial-data="dialogInitialData"
      @save="handlePolicyDialogSave"
    />

    <!-- AI Response Configuration dialog -->
    <Dialog :open="showAiConfigDialog" @update:open="showAiConfigDialog = $event">
      <DialogContent class="sm:max-w-[640px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <Sparkles class="h-5 w-5 text-amber-500" />
            Configure AI Response
          </DialogTitle>
          <DialogDescription>
            Choose a model and a system prompt to control how the AI answers queries.
          </DialogDescription>
        </DialogHeader>

        <div class="space-y-6 py-4">
          <!-- 1. Model -->
          <section class="space-y-3">
            <div class="flex items-center justify-between">
              <Label class="text-sm font-medium">Model</Label>
              <Badge v-if="aiModelId && aiModelName" variant="secondary" class="text-[10px]">
                {{ aiModelName }}
              </Badge>
            </div>

            <ModelSelector
              :model-value="aiModelId"
              title=""
              description=""
              id-prefix="go-live-ai"
              @update:model-value="handleAiModelUpdate"
            />
          </section>

          <Separator />

          <!-- 2. System prompt -->
          <section class="space-y-3">
            <Label class="text-sm font-medium">System prompt</Label>

            <Select
              :model-value="selectedPromptPreset"
              @update:model-value="handlePromptPresetChange"
            >
              <SelectTrigger class="w-full">
                <SelectValue placeholder="Choose a prompt template" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="(preset, key) in PROMPT_PRESETS" :key="key" :value="key">
                  {{ preset.label }}
                </SelectItem>
              </SelectContent>
            </Select>

            <Textarea
              id="ai-system-prompt"
              v-model="systemPrompt"
              placeholder="Enter a custom system prompt..."
              class="min-h-[140px] font-mono text-sm"
            />
            <p class="text-[11px] text-muted-foreground">
              Sent to the model before every query. Controls tone, format, and how retrieved
              documents are used.
            </p>
          </section>
        </div>

        <DialogFooter class="gap-2">
          <Button variant="outline" @click="cancelAiConfig">Cancel</Button>
          <Button :disabled="!aiModelId" @click="confirmAiConfig">
            {{ aiModelId ? 'Confirm' : 'Select a model' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Overwrite confirmation dialog -->
    <Dialog :open="showOverwriteDialog" @update:open="showOverwriteDialog = $event">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <AlertTriangle class="h-5 w-5 text-yellow-500" />
            Name Already Exists
          </DialogTitle>
          <DialogDescription class="space-y-3">
            <span class="block">
              The name "<span class="font-medium">{{ name }}</span
              >" is already taken on SyftHub. Proceeding will overwrite the existing resource.
            </span>
            <a
              v-if="existingEndpointUrl"
              :href="existingEndpointUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center gap-1 text-primary hover:underline"
            >
              View existing resource
              <ExternalLink class="h-3 w-3" />
            </a>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter class="gap-2">
          <Button variant="outline" @click="showOverwriteDialog = false">Cancel</Button>
          <Button variant="destructive" @click="handleOverwriteConfirm">Overwrite</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- Create Data Source Dialog -->
    <CreateDatasetDialogSimple
      :open="showCreateDatasetDialog"
      @update:open="showCreateDatasetDialog = $event"
      @dataset-created="handleDatasetCreated"
    />

    <!-- Create Model Dialog -->
    <CreateModelDialogSimple
      :open="showCreateModelDialog"
      @update:open="showCreateModelDialog = $event"
      @model-created="handleModelCreated"
    />
  </div>
</template>
