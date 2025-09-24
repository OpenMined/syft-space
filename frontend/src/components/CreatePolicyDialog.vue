<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[700px]">
      <DialogHeader>
        <DialogTitle>Create Policy</DialogTitle>
      </DialogHeader>

      <!-- Step Indicator -->
      <div class="flex items-center justify-center py-3">
        <div class="flex items-center space-x-2 md:space-x-4">
          <div class="flex items-center">
            <div
              :class="[
                'w-3 h-3 rounded-full transition-colors',
                currentStepIndex >= 0 ? 'bg-blue-500' : 'bg-gray-300',
              ]"
            ></div>
            <span
              class="ml-2 text-xs md:text-sm font-medium whitespace-nowrap truncate max-w-[100px] md:max-w-none"
              :class="currentStepIndex === 0 ? 'text-gray-900' : 'text-gray-500'"
            >
              Type Selection
            </span>
          </div>
          <div class="w-8 md:w-16 h-0.5 bg-gray-300">
            <div
              class="h-full bg-blue-500 transition-all"
              :style="{ width: currentStepIndex >= 1 ? '100%' : '0%' }"
            ></div>
          </div>
          <div class="flex items-center">
            <div
              :class="[
                'w-3 h-3 rounded-full transition-colors',
                currentStepIndex >= 1 ? 'bg-blue-500' : 'bg-gray-300',
              ]"
            ></div>
            <span
              class="ml-2 text-xs md:text-sm font-medium whitespace-nowrap truncate max-w-[100px] md:max-w-none"
              :class="currentStepIndex === 1 ? 'text-gray-900' : 'text-gray-500'"
            >
              Configuration
            </span>
          </div>
          <div class="w-8 md:w-16 h-0.5 bg-gray-300">
            <div
              class="h-full bg-blue-500 transition-all"
              :style="{ width: currentStepIndex >= 2 ? '100%' : '0%' }"
            ></div>
          </div>
          <div class="flex items-center">
            <div
              :class="[
                'w-3 h-3 rounded-full transition-colors',
                currentStepIndex >= 2 ? 'bg-blue-500' : 'bg-gray-300',
              ]"
            ></div>
            <span
              class="ml-2 text-xs md:text-sm font-medium whitespace-nowrap truncate max-w-[100px] md:max-w-none"
              :class="currentStepIndex === 2 ? 'text-gray-900' : 'text-gray-500'"
            >
              Apply
            </span>
          </div>
          <div class="w-8 md:w-16 h-0.5 bg-gray-300">
            <div
              class="h-full bg-blue-500 transition-all"
              :style="{ width: currentStepIndex >= 3 ? '100%' : '0%' }"
            ></div>
          </div>
          <div class="flex items-center">
            <div
              :class="[
                'w-3 h-3 rounded-full transition-colors',
                currentStepIndex >= 3 ? 'bg-blue-500' : 'bg-gray-300',
              ]"
            ></div>
            <span
              class="ml-2 text-xs md:text-sm font-medium whitespace-nowrap truncate max-w-[100px] md:max-w-none"
              :class="currentStepIndex === 3 ? 'text-gray-900' : 'text-gray-500'"
            >
              Done
            </span>
          </div>
        </div>
      </div>

      <Separator class="mb-6" />

      <div class="flex flex-col" style="height: 420px">
        <!-- Type Selection Step -->
        <div v-if="currentStep === 'type-selection'" class="flex flex-col h-full">
          <!-- Custom Policy Banner -->
          <div v-if="!isCustomBannerDismissed" class="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg p-4 mb-4">
            <div class="flex items-start justify-between">
              <div class="flex items-start space-x-3">
                <div class="p-2 bg-purple-100 rounded-md">
                  <Code class="h-5 w-5 text-purple-600" />
                </div>
                <div class="flex-1">
                  <h4 class="font-medium text-gray-900 mb-1">Create Custom Policy</h4>
                  <p class="text-sm text-gray-600 mb-3">Build your own policy using our SDK</p>
                  <Button variant="outline" size="sm" class="text-purple-700 border-purple-300 hover:bg-purple-100 hover:text-purple-800">
                    <ExternalLink class="h-3 w-3 mr-2" />
                    View Documentation
                  </Button>
                </div>
              </div>
              <button
                @click="isCustomBannerDismissed = true"
                class="ml-auto h-5 w-5 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              >
                <X class="h-4 w-4" />
                <span class="sr-only">Dismiss</span>
              </button>
            </div>
          </div>

          <!-- Search Input -->
          <div class="relative mb-4">
            <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input v-model="searchQuery" placeholder="Search..." class="pl-10 pr-4" />
          </div>

          <!-- Policy Options List -->
          <div class="space-y-2 overflow-y-auto flex-1 pr-2 pb-2">
            <div
              v-for="policy in filteredPolicies"
              :key="policy.id"
              @click="selectedPolicyType = policy.id"
              :class="[
                'flex items-center justify-between p-4 rounded-lg border cursor-pointer transition-all hover:bg-gray-50',
                selectedPolicyType === policy.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200',
              ]"
            >
              <div class="flex items-center space-x-3">
                <component
                  :is="policy.icon"
                  class="h-5 w-5"
                  :class="selectedPolicyType === policy.id ? 'text-blue-600' : 'text-gray-600'"
                />
                <div class="flex flex-col">
                  <span
                    class="font-medium"
                    :class="selectedPolicyType === policy.id ? 'text-blue-900' : 'text-gray-900'"
                  >
                    {{ policy.name }}
                  </span>
                  <span class="text-xs text-gray-500">{{ policy.description }}</span>
                </div>
              </div>
              <ChevronRight class="h-4 w-4 text-gray-400" />
            </div>
          </div>
        </div>

        <!-- Configuration Step -->
        <div v-if="currentStep === 'configuration'" class="space-y-3">
          <div>
            <h3 class="text-lg font-semibold">Configure {{ selectedPolicyName }}</h3>
            <p class="text-sm text-muted-foreground">
              Set up your {{ selectedPolicyName }} policy settings
            </p>
          </div>
          <div
            class="min-h-[200px] flex items-center justify-center border-2 border-dashed rounded-lg"
          >
            <p class="text-muted-foreground">Configuration form for {{ selectedPolicyName }}</p>
          </div>
        </div>

        <!-- Apply Step -->
        <div v-if="currentStep === 'apply'" class="flex flex-col h-full">
          <div class="mb-2">
            <h3 class="text-lg font-semibold">Apply to Services</h3>
            <p class="text-sm text-muted-foreground">
              Optional: Select services to apply this policy to
            </p>
          </div>
          <div class="flex items-center justify-between gap-2 mb-2">
            <div class="relative w-56 md:w-72">
              <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input v-model="servicesSearchQuery" placeholder="Search services..." class="pl-10 pr-4 w-full" />
            </div>
            <div class="flex items-center justify-end gap-1.5">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button size="icon" variant="outline" @click="selectAllServices" :disabled="allServices.length === 0" class="h-8 w-8">
                      <CheckSquare class="h-4 w-4" />
                      <span class="sr-only">Select all</span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    Select all services
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button size="icon" variant="ghost" @click="clearAllSelections" :disabled="selectedServiceIds.length === 0" class="h-8 w-8">
                      <Square class="h-4 w-4" />
                      <span class="sr-only">Select none</span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    Clear all selections
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto pr-2">
            <div
              v-for="service in filteredServices"
              :key="service.id"
              @click="toggleServiceSelection(service.id)"
              :class="[
                'flex items-center justify-between p-4 rounded-lg border transition-all hover:bg-gray-50 mb-2 last:mb-0 cursor-pointer',
                isServiceSelected(service.id) ? 'border-blue-500 bg-blue-50' : 'border-gray-200',
              ]"
            >
              <div class="min-w-0 pr-4">
                <div class="font-medium truncate">{{ service.name }}</div>
                <div class="text-xs text-gray-500 truncate">{{ service.description }}</div>
              </div>
              <input
                type="checkbox"
                class="h-4 w-4 mt-1"
                @click.stop
                :value="service.id"
                v-model="selectedServiceIds"
              />
            </div>
          </div>
          <p class="text-xs text-gray-500 mt-2">
            You can skip applying now and do it later from My Services or Policies pages.
          </p>
        </div>

        <!-- Done Step -->
        <div v-if="currentStep === 'done'" class="space-y-4">
          <div class="text-center py-8">
            <div
              class="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4"
            >
              <Check class="h-8 w-8 text-green-600" />
            </div>
            <h3 class="text-xl font-semibold mb-2">Policy Created Successfully!</h3>
            <p class="text-gray-600">
              Your {{ selectedPolicyName }} policy has been created and is ready to use.
            </p>
          </div>
        </div>
      </div>

      <Separator class="mt-4 mb-4" />

      <DialogFooter>
        <!-- Type Selection Step Buttons -->
        <div v-if="currentStep === 'type-selection'" class="flex justify-between w-full">
          <Button variant="ghost" @click="handleCancel"> Cancel </Button>
          <Button @click="goToNextStep" :disabled="!selectedPolicyType"> Next </Button>
        </div>

        <!-- Configuration Step Buttons -->
        <div v-if="currentStep === 'configuration'" class="flex justify-between w-full">
          <Button variant="ghost" @click="goToPreviousStep"> Previous </Button>
          <Button @click="goToApplyStep"> Next </Button>
        </div>

        <!-- Apply Step Buttons -->
        <div v-if="currentStep === 'apply'" class="flex justify-between w-full">
          <Button variant="ghost" @click="goToConfigurationStep"> Back </Button>
          <div class="flex gap-2">
            <Button variant="outline" @click="handleCreate"> Skip </Button>
            <Button @click="handleCreate" :disabled="selectedServiceIds.length === 0"> Apply </Button>
          </div>
        </div>

        <!-- Done Step Buttons -->
        <div v-if="currentStep === 'done'" class="flex justify-end w-full">
          <Button @click="handleClose"> Close </Button>
        </div>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { Search, ChevronRight, Check, Gauge, Calculator, Activity, Users, Code, ExternalLink, X, CheckSquare, Square } from 'lucide-vue-next'
import { useServicesStore } from '@/stores/services'
import type { ServiceItem } from '@/stores/services'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

type Step = 'type-selection' | 'configuration' | 'apply' | 'done'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'policy-created': []
}>()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const currentStep = ref<Step>('type-selection')
const searchQuery = ref('')
const selectedPolicyType = ref<string | null>(null)
const isCustomBannerDismissed = ref(false)
const servicesStore = useServicesStore()
const selectedServiceIds = ref<string[]>([])
const servicesSearchQuery = ref('')
const allServices = computed(() => servicesStore.publishedServices as unknown as ServiceItem[])

const policyOptions = [
  {
    id: 'ratelimiter',
    name: 'Rate Limiter',
    description: 'Control request rates to prevent abuse and ensure fair resource usage',
    icon: Gauge,
  },
  {
    id: 'accounting',
    name: 'Accounting',
    description: 'Apply pricing and accounting to service requests, including per-request and token usage',
    icon: Calculator,
  },
  {
    id: 'otel',
    name: 'OpenTelemetry',
    description: 'Collect traces, metrics, and logs for system monitoring and debugging',
    icon: Activity,
  },
  {
    id: 'hitl',
    name: 'Human-in-the-Loop',
    description: 'Require human approval for sensitive operations and decisions',
    icon: Users,
  },
]

const currentStepIndex = computed(() => {
  const steps: Step[] = ['type-selection', 'configuration', 'apply', 'done']
  return steps.indexOf(currentStep.value)
})

const filteredPolicies = computed(() => {
  if (!searchQuery.value) return policyOptions
  return policyOptions.filter((policy) =>
    policy.name.toLowerCase().includes(searchQuery.value.toLowerCase()),
  )
})

const filteredServices = computed(() => {
  const list: ServiceItem[] = servicesStore.publishedServices as unknown as ServiceItem[]
  if (!servicesSearchQuery.value) return list
  const q = servicesSearchQuery.value.toLowerCase()
  return list.filter((s: ServiceItem) =>
    (s.name || '').toLowerCase().includes(q) || (s.description || '').toLowerCase().includes(q),
  )
})

const selectedPolicyName = computed(() => {
  const policy = policyOptions.find((i) => i.id === selectedPolicyType.value)
  return policy?.name || 'Policy'
})

const goToNextStep = () => {
  if (currentStep.value === 'type-selection') {
    currentStep.value = 'configuration'
  } else if (currentStep.value === 'configuration') {
    currentStep.value = 'apply'
  } else if (currentStep.value === 'apply') {
    currentStep.value = 'done'
  }
}

const goToPreviousStep = () => {
  if (currentStep.value === 'configuration') {
    currentStep.value = 'type-selection'
  } else if (currentStep.value === 'apply') {
    currentStep.value = 'configuration'
  }
}

const goToApplyStep = () => {
  currentStep.value = 'apply'
}

const goToConfigurationStep = () => {
  currentStep.value = 'configuration'
}

const handleCancel = () => {
  resetDialog()
  isOpen.value = false
}

const handleCreate = () => {
  // In a real implementation, this would submit the policy data
  goToNextStep()
  emit('policy-created')
}

const handleClose = () => {
  resetDialog()
  isOpen.value = false
}

const resetDialog = () => {
  currentStep.value = 'type-selection'
  selectedPolicyType.value = null
  searchQuery.value = ''
  selectedServiceIds.value = []
}

const isServiceSelected = (id: string) => {
  return selectedServiceIds.value.includes(id)
}

const toggleServiceSelection = (id: string) => {
  const idx = selectedServiceIds.value.indexOf(id)
  if (idx === -1) {
    selectedServiceIds.value = [...selectedServiceIds.value, id]
  } else {
    const next = [...selectedServiceIds.value]
    next.splice(idx, 1)
    selectedServiceIds.value = next
  }
}

const selectAllServices = () => {
  const ids = (servicesStore.publishedServices as unknown as ServiceItem[]).map((s) => s.id)
  const set = new Set<string>(ids)
  selectedServiceIds.value = Array.from(set)
}

const clearAllSelections = () => {
  selectedServiceIds.value = []
}
</script>
