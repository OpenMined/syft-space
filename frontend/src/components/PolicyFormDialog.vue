<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-[600px]">
      <DialogHeader>
        <DialogTitle
          >{{ isEditing ? 'Edit' : 'Add' }} {{ getPolicyTypeLabel(policyType) }} Rule</DialogTitle
        >
        <DialogDescription>
          {{ isEditing ? 'Update this' : 'Create a new' }}
          {{
            policyType === 'access'
              ? 'access control'
              : policyType === 'rate_limit'
                ? 'usage limit'
                : policyType === 'pricing'
                  ? 'pricing'
                  : policyType === 'human_in_the_loop'
                    ? 'human-in-the-loop approval'
                    : 'PII filter'
          }}
          policy for this endpoint.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <!-- Authorization Policy Form -->
        <div v-if="policyType === 'access'" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Rule Type</Label>
              <Select v-model="authorizationForm.ruleType">
                <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                  <SelectValue placeholder="Select rule type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="allow" class="body-sm">Allow specific users</SelectItem>
                  <SelectItem value="deny" class="body-sm">Deny specific users</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Note</Label>
              <Input
                v-model="authorizationForm.note"
                placeholder="Optional description"
                class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground"
              />
            </div>
          </div>
          <div class="space-y-1">
            <Label class="body-sm text-muted-foreground font-medium">Users</Label>
            <Input
              v-model="authorizationForm.users"
              placeholder="user1@example.com, user2@example.com"
              class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground"
            />
            <p class="text-xs text-muted-foreground">
              Comma-separated list. Wildcard supported (e.g., *@company.com, *.edu,
              *@contractors.org)
            </p>
          </div>
        </div>

        <!-- Rate Limiter Policy Form -->
        <div v-if="policyType === 'rate_limit'" class="space-y-4">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Limit</Label>
              <div class="flex">
                <Input
                  v-model="rateLimiterForm.limit"
                  type="number"
                  placeholder="Enter limit"
                  class="h-9 w-24 sm:w-32 rounded-l-lg rounded-r-none border-r-0 border-border bg-card body-sm"
                />
                <Select v-model="rateLimiterForm.windowUnit">
                  <SelectTrigger
                    class="h-9 rounded-r-lg rounded-l-none border-border bg-card body-sm min-w-0"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="second">requests per second</SelectItem>
                    <SelectItem value="minute">requests per minute</SelectItem>
                    <SelectItem value="hour">requests per hour</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Scope</Label>
              <Select v-model="rateLimiterForm.scope">
                <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="per user">Per User</SelectItem>
                  <SelectItem value="global">Per Full API</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div class="space-y-1">
            <Label class="body-sm text-muted-foreground font-medium">Note</Label>
            <Input
              v-model="rateLimiterForm.note"
              placeholder="Optional description"
              class="h-9 rounded-lg border-border bg-card body-sm"
            />
          </div>
        </div>

        <!-- Pricing Policy Form -->
        <div v-if="policyType === 'pricing'" class="space-y-4">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Price per query ($)</Label>
              <Input
                v-model="pricingForm.price"
                type="number"
                step="any"
                placeholder="Enter price per query"
                class="h-9 rounded-lg border-border bg-card body-sm"
              />
            </div>
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Note</Label>
              <Input
                v-model="pricingForm.note"
                placeholder="Optional description"
                class="h-9 rounded-lg border-border bg-card body-sm"
              />
            </div>
          </div>
          <div class="flex flex-col sm:flex-row gap-3 sm:gap-4">
            <div class="space-y-1 sm:flex-shrink-0 sm:w-32">
              <Label class="body-sm text-muted-foreground font-medium">Apply To</Label>
              <Select v-model="pricingForm.userType">
                <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Users</SelectItem>
                  <SelectItem value="specific">Specific Users</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div v-if="pricingForm.userType === 'specific'" class="space-y-1 flex-1">
              <Label class="body-sm text-muted-foreground font-medium">Users</Label>
              <Input
                v-model="pricingForm.users"
                placeholder="user1@example.com, user2@example.com"
                class="h-9 rounded-lg border-border bg-card body-sm"
              />
              <p class="text-xs text-muted-foreground">
                Comma-separated list. Wildcard supported (e.g., *@company.com, *.edu,
                *@contractors.org)
              </p>
            </div>
          </div>
        </div>

        <!-- PII Filter Policy Form -->
        <div v-if="policyType === 'pii_filter'" class="space-y-4">
          <div class="rounded-lg border border-border bg-muted/40 px-4 py-3">
            <p class="text-sm font-medium text-foreground">No configuration required</p>
            <p class="text-xs text-muted-foreground mt-1">
              The endpoint's AI model will evaluate its own response and replace any detected
              personally identifiable information with [REDACTED] before returning it to the caller.
            </p>
          </div>
          <div class="space-y-1">
            <Label class="body-sm text-muted-foreground font-medium">Note</Label>
            <Input
              v-model="piiFilterForm.note"
              placeholder="Optional description"
              class="h-9 rounded-lg border-border bg-card body-sm"
            />
          </div>
        </div>

        <!-- Human in the Loop Policy Form -->
        <div v-if="policyType === 'human_in_the_loop'" class="space-y-4">
          <div class="flex flex-col sm:flex-row gap-3 sm:gap-4">
            <div class="space-y-1 sm:flex-shrink-0 sm:w-40">
              <Label class="body-sm text-muted-foreground font-medium">Applies to</Label>
              <Select v-model="humanInTheLoopForm.appliesTo">
                <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All users</SelectItem>
                  <SelectItem value="specific">Specific users</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div v-if="humanInTheLoopForm.appliesTo === 'specific'" class="space-y-1 flex-1">
              <Label class="body-sm text-muted-foreground font-medium">Users</Label>
              <Input
                v-model="humanInTheLoopForm.users"
                placeholder="user1@example.com, *@company.com"
                class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground"
              />
              <p class="text-xs text-muted-foreground">
                Comma-separated list. Wildcard supported (e.g., *@company.com).
              </p>
            </div>
          </div>

          <div class="space-y-2">
            <Label class="body-sm text-muted-foreground font-medium">Approval of output</Label>
            <RadioGroup v-model="humanInTheLoopForm.approvalMode" class="gap-2">
              <div
                class="flex items-start gap-3 rounded-lg border px-3 py-2.5 cursor-pointer transition-colors"
                :class="
                  humanInTheLoopForm.approvalMode === 'always'
                    ? 'border-primary bg-primary/5'
                    : 'border-border bg-card'
                "
                @click="humanInTheLoopForm.approvalMode = 'always'"
              >
                <RadioGroupItem value="always" id="hil-mode-always" class="mt-0.5" />
                <Label for="hil-mode-always" class="cursor-pointer space-y-0.5">
                  <span class="block text-sm font-medium text-foreground"
                    >Always require approval</span
                  >
                  <span class="block text-xs text-muted-foreground font-normal">
                    Every reply is held for your manual review before it is sent.
                  </span>
                </Label>
              </div>
              <div
                class="flex items-start gap-3 rounded-lg border px-3 py-2.5 cursor-pointer transition-colors"
                :class="
                  humanInTheLoopForm.approvalMode === 'ai_mediated'
                    ? 'border-primary bg-primary/5'
                    : 'border-border bg-card'
                "
                @click="humanInTheLoopForm.approvalMode = 'ai_mediated'"
              >
                <RadioGroupItem value="ai_mediated" id="hil-mode-ai" class="mt-0.5" />
                <Label for="hil-mode-ai" class="cursor-pointer space-y-0.5">
                  <span class="block text-sm font-medium text-foreground">AI-mediated</span>
                  <span class="block text-xs text-muted-foreground font-normal">
                    A model triages each reply and only escalates the ones that need you.
                  </span>
                </Label>
              </div>
            </RadioGroup>
          </div>

          <div v-if="humanInTheLoopForm.approvalMode === 'ai_mediated'" class="space-y-4">
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Triaging model</Label>
              <Select v-model="humanInTheLoopForm.triagingModel">
                <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                  <SelectValue
                    :placeholder="modelsLoading ? 'Loading models…' : 'Select a model'"
                  />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="model in availableModels" :key="model.id" :value="model.id">
                    {{ model.name }}
                  </SelectItem>
                </SelectContent>
              </Select>
              <p
                v-if="!modelsLoading && availableModels.length === 0"
                class="text-xs text-muted-foreground"
              >
                No models found. Add a model first to use AI-mediated triaging.
              </p>
            </div>
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Triaging prompt</Label>
              <Textarea
                v-model="humanInTheLoopForm.triagingPrompt"
                :rows="4"
                class="rounded-lg border-border bg-card body-sm"
              />
              <p class="text-xs text-muted-foreground">
                Instructions the model uses to decide what to auto-send and what to escalate to you.
              </p>
            </div>
          </div>

          <div class="space-y-1">
            <Label class="body-sm text-muted-foreground font-medium">Note</Label>
            <Input
              v-model="humanInTheLoopForm.note"
              placeholder="Optional description"
              class="h-9 rounded-lg border-border bg-card body-sm"
            />
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="$emit('update:open', false)" :disabled="isSubmitting"
          >Cancel</Button
        >
        <Button @click="handleSave" :disabled="isSubmitting || !isFormValid">
          <div v-if="isSubmitting" class="flex items-center gap-2">
            <Loader2 class="h-4 w-4 animate-spin" />
            {{ isEditing ? 'Updating...' : 'Creating...' }}
          </div>
          <span v-else>{{ isEditing ? 'Update Rule' : 'Add Rule' }}</span>
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { usePolicyCreation, DEFAULT_HIL_TRIAGING_PROMPT } from '@/composables/usePolicyCreation'
import { getPolicyTypeLabel } from '@/config/policyTypes'
import type { PolicyTypeId } from '@/config/policyTypes'
import type {
  AuthorizationFormData,
  RateLimitFormData,
  PricingFormData,
  PiiFilterFormData,
  HumanInTheLoopFormData,
} from '@/composables/usePolicyCreation'
import { modelsApi } from '@/api/endpoints/models'
import type { ModelListItem } from '@/api/types'

const props = defineProps<{
  open: boolean
  policyType: PolicyTypeId
  initialData?: Record<string, unknown> | null
  isSubmitting?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  save: [payload: { policyType: PolicyTypeId; formData: Record<string, unknown> }]
}>()

const { validatePolicyForm } = usePolicyCreation()

const isEditing = computed(() => !!props.initialData)

const authorizationForm = ref<AuthorizationFormData>({
  ruleType: 'allow',
  users: '',
  note: '',
})

const rateLimiterForm = ref<RateLimitFormData>({
  limit: '',
  windowUnit: 'minute',
  scope: 'per user',
  note: '',
})

const pricingForm = ref<PricingFormData>({
  price: '',
  userType: 'all',
  users: '',
  note: '',
})

const piiFilterForm = ref<PiiFilterFormData>({
  note: '',
})

const createHilFormDefaults = (): HumanInTheLoopFormData => ({
  appliesTo: 'all',
  users: '',
  approvalMode: 'always',
  triagingModel: '',
  triagingPrompt: DEFAULT_HIL_TRIAGING_PROMPT,
  note: '',
})

const humanInTheLoopForm = ref<HumanInTheLoopFormData>(createHilFormDefaults())

const availableModels = ref<ModelListItem[]>([])
const modelsLoading = ref(false)

const loadModels = async () => {
  if (availableModels.value.length > 0 || modelsLoading.value) return
  modelsLoading.value = true
  try {
    availableModels.value = await modelsApi.list()
  } catch {
    availableModels.value = []
  } finally {
    modelsLoading.value = false
  }
}

const getCurrentFormData = () => {
  switch (props.policyType) {
    case 'access':
      return authorizationForm.value
    case 'rate_limit':
      return rateLimiterForm.value
    case 'pricing':
      return pricingForm.value
    case 'pii_filter':
      return piiFilterForm.value
    case 'human_in_the_loop':
      return humanInTheLoopForm.value
    default:
      return null
  }
}

const isFormValid = computed(() => {
  const formData = getCurrentFormData()
  return formData ? validatePolicyForm(props.policyType, formData) : false
})

const resetForm = (policyType: PolicyTypeId) => {
  switch (policyType) {
    case 'access':
      authorizationForm.value = { ruleType: 'allow', users: '', note: '' }
      break
    case 'rate_limit':
      rateLimiterForm.value = { limit: '', windowUnit: 'minute', scope: 'per user', note: '' }
      break
    case 'pricing':
      pricingForm.value = { price: '', userType: 'all', users: '', note: '' }
      break
    case 'pii_filter':
      piiFilterForm.value = { note: '' }
      break
    case 'human_in_the_loop':
      humanInTheLoopForm.value = createHilFormDefaults()
      break
  }
}

const loadInitialData = (policyType: PolicyTypeId, data: Record<string, unknown>) => {
  switch (policyType) {
    case 'access':
      authorizationForm.value = {
        ruleType: (data.ruleType as 'allow' | 'deny') || 'allow',
        users: (data.users as string) || '',
        note: (data.note as string) || '',
      }
      break
    case 'rate_limit':
      rateLimiterForm.value = {
        limit: (data.limit as string) || '',
        windowUnit: (data.windowUnit as 'second' | 'minute' | 'hour') || 'minute',
        scope: (data.scope as 'per user' | 'global') || 'per user',
        note: (data.note as string) || '',
      }
      break
    case 'pricing':
      pricingForm.value = {
        price: data.price !== undefined ? String(data.price) : '',
        userType: (data.userType as 'all' | 'specific') || 'all',
        users: (data.users as string) || '',
        note: (data.note as string) || '',
      }
      break
    case 'pii_filter':
      piiFilterForm.value = { note: (data.note as string) || '' }
      break
    case 'human_in_the_loop': {
      const defaults = createHilFormDefaults()
      humanInTheLoopForm.value = {
        appliesTo: (data.appliesTo as 'all' | 'specific') || defaults.appliesTo,
        users: (data.users as string) || '',
        approvalMode: (data.approvalMode as 'always' | 'ai_mediated') || defaults.approvalMode,
        triagingModel: (data.triagingModel as string) || '',
        triagingPrompt: (data.triagingPrompt as string) || defaults.triagingPrompt,
        note: (data.note as string) || '',
      }
      break
    }
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      if (props.initialData) {
        loadInitialData(props.policyType, props.initialData)
      } else {
        resetForm(props.policyType)
      }
      if (props.policyType === 'human_in_the_loop') {
        loadModels()
      }
    }
  },
)

const handleSave = () => {
  const formData = getCurrentFormData()
  if (!formData) return

  emit('save', {
    policyType: props.policyType,
    formData: { ...formData },
  })
}
</script>
