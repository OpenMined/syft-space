<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[700px]">
      <DialogHeader>
        <DialogTitle>Create Integration</DialogTitle>
      </DialogHeader>

      <!-- Step Indicator -->
      <div class="flex items-center justify-center py-4">
        <div class="flex items-center space-x-4">
          <div class="flex items-center">
            <div :class="[
              'w-3 h-3 rounded-full transition-colors',
              currentStepIndex >= 0 ? 'bg-blue-500' : 'bg-gray-300'
            ]"></div>
            <span class="ml-2 text-sm font-medium" :class="currentStepIndex === 0 ? 'text-gray-900' : 'text-gray-500'">
              Type Selection
            </span>
          </div>
          <div class="w-24 h-0.5 bg-gray-300">
            <div class="h-full bg-blue-500 transition-all" :style="{ width: currentStepIndex >= 1 ? '100%' : '0%' }"></div>
          </div>
          <div class="flex items-center">
            <div :class="[
              'w-3 h-3 rounded-full transition-colors',
              currentStepIndex >= 1 ? 'bg-blue-500' : 'bg-gray-300'
            ]"></div>
            <span class="ml-2 text-sm font-medium" :class="currentStepIndex === 1 ? 'text-gray-900' : 'text-gray-500'">
              Configuration
            </span>
          </div>
          <div class="w-24 h-0.5 bg-gray-300">
            <div class="h-full bg-blue-500 transition-all" :style="{ width: currentStepIndex >= 2 ? '100%' : '0%' }"></div>
          </div>
          <div class="flex items-center">
            <div :class="[
              'w-3 h-3 rounded-full transition-colors',
              currentStepIndex >= 2 ? 'bg-blue-500' : 'bg-gray-300'
            ]"></div>
            <span class="ml-2 text-sm font-medium" :class="currentStepIndex === 2 ? 'text-gray-900' : 'text-gray-500'">
              Done
            </span>
          </div>
        </div>
      </div>

      <Separator class="mb-6" />

      <div class="flex flex-col" style="height: 400px;">
        <!-- Type Selection Step -->
        <div v-if="currentStep === 'type-selection'" class="flex flex-col h-full">
          <!-- Custom Integration Banner -->
          <div v-if="!isCustomBannerDismissed" class="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg p-4 mb-4">
            <div class="flex items-start justify-between">
              <div class="flex items-start space-x-3">
                <div class="p-2 bg-purple-100 rounded-md">
                  <Code class="h-5 w-5 text-purple-600" />
                </div>
                <div class="flex-1">
                  <h4 class="font-medium text-gray-900 mb-1">Create Custom Integration</h4>
                  <p class="text-sm text-gray-600 mb-3">Build your own integration using our SDK</p>
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
            <Input
              v-model="searchQuery"
              placeholder="Search..."
              class="pl-10 pr-4"
            />
          </div>

          <!-- Integration Options List -->
          <div class="space-y-2 overflow-y-auto flex-1 pr-2 pb-2">
            <div
              v-for="integration in filteredIntegrations"
              :key="integration.id"
              @click="selectedIntegrationType = integration.id"
              :class="[
                'flex items-center justify-between p-4 rounded-lg border cursor-pointer transition-all hover:bg-gray-50',
                selectedIntegrationType === integration.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
              ]"
            >
              <div class="flex items-center space-x-3">
                <IntegrationIcon
                  :name="integration.id"
                  class="h-5 w-5"
                  :class="selectedIntegrationType === integration.id ? 'text-blue-600' : 'text-gray-600'"
                />
                <div class="flex flex-col">
                  <span class="font-medium" :class="selectedIntegrationType === integration.id ? 'text-blue-900' : 'text-gray-900'">
                    {{ integration.name }}
                  </span>
                  <span class="text-xs text-gray-500">{{ integration.type }}</span>
                </div>
              </div>
              <ChevronRight class="h-4 w-4 text-gray-400" />
            </div>
          </div>
        </div>

        <!-- Configuration Step -->
        <div v-if="currentStep === 'configuration'" class="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Configure {{ selectedIntegrationName }}</CardTitle>
              <CardDescription>
                Set up your {{ selectedIntegrationName }} integration settings
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div class="min-h-[200px] flex items-center justify-center border-2 border-dashed rounded-lg">
                <p class="text-muted-foreground">Configuration form for {{ selectedIntegrationName }}</p>
              </div>
            </CardContent>
          </Card>
        </div>

        <!-- Done Step -->
        <div v-if="currentStep === 'done'" class="space-y-4">
          <div class="text-center py-8">
            <div class="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
              <Check class="h-8 w-8 text-green-600" />
            </div>
            <h3 class="text-xl font-semibold mb-2">Integration Created Successfully!</h3>
            <p class="text-gray-600">
              Your {{ selectedIntegrationName }} integration has been created and is ready to use.
            </p>
          </div>
        </div>
      </div>

      <Separator class="mt-4 mb-4" />

      <DialogFooter>
        <!-- Type Selection Step Buttons -->
        <div v-if="currentStep === 'type-selection'" class="flex justify-between w-full">
          <Button variant="ghost" @click="handleCancel">
            Cancel
          </Button>
          <Button @click="goToNextStep" :disabled="!selectedIntegrationType">
            Next
          </Button>
        </div>

        <!-- Configuration Step Buttons -->
        <div v-if="currentStep === 'configuration'" class="flex justify-between w-full">
          <Button variant="ghost" @click="goToPreviousStep">
            Previous
          </Button>
          <Button @click="handleCreate">
            Create
          </Button>
        </div>

        <!-- Done Step Buttons -->
        <div v-if="currentStep === 'done'" class="flex justify-end w-full">
          <Button @click="handleClose">
            Close
          </Button>
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Search, ChevronRight, Check, Code, ExternalLink, X } from 'lucide-vue-next'
import IntegrationIcon from '@/components/IntegrationIcons.vue'

type Step = 'type-selection' | 'configuration' | 'done'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'integration-created': []
}>()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value)
})

const currentStep = ref<Step>('type-selection')
const searchQuery = ref('')
const selectedIntegrationType = ref<string | null>(null)
const isCustomBannerDismissed = ref(false)

const integrationOptions = [
  { id: 'weaviate', name: 'Weaviate', type: 'Data' },
  { id: 'qdrant', name: 'Qdrant', type: 'Data' },
  { id: 'chroma', name: 'Chroma', type: 'Data' },
  { id: 'vllm', name: 'vLLM', type: 'Model' },
  { id: 'ollama', name: 'Ollama', type: 'Model' },
  { id: 'huggingface', name: 'Hugging Face', type: 'Model' },
]

const currentStepIndex = computed(() => {
  const steps: Step[] = ['type-selection', 'configuration', 'done']
  return steps.indexOf(currentStep.value)
})

const filteredIntegrations = computed(() => {
  if (!searchQuery.value) return integrationOptions
  return integrationOptions.filter(integration => 
    integration.name.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

const selectedIntegrationName = computed(() => {
  const integration = integrationOptions.find(i => i.id === selectedIntegrationType.value)
  return integration?.name || 'Integration'
})

const goToNextStep = () => {
  if (currentStep.value === 'type-selection') {
    currentStep.value = 'configuration'
  } else if (currentStep.value === 'configuration') {
    currentStep.value = 'done'
  }
}

const goToPreviousStep = () => {
  if (currentStep.value === 'configuration') {
    currentStep.value = 'type-selection'
  }
}

const handleCancel = () => {
  resetDialog()
  isOpen.value = false
}

const handleCreate = () => {
  // In a real implementation, this would submit the integration data
  goToNextStep()
  emit('integration-created')
}

const handleClose = () => {
  resetDialog()
  isOpen.value = false
}

const resetDialog = () => {
  currentStep.value = 'type-selection'
  selectedIntegrationType.value = null
  searchQuery.value = ''
  isCustomBannerDismissed.value = false
}
</script>