<template>
  <Dialog v-model:open="isOpen">
    <DialogContent class="sm:max-w-[1200px] max-h-[90vh]">
      <DialogHeader>
        <DialogTitle>{{
          isEditMode ? `Edit ${resourceConfig.displayName}` : `Create ${resourceConfig.displayName}`
        }}</DialogTitle>
      </DialogHeader>

      <!-- Step Indicator -->
      <div class="flex items-center justify-center py-4">
        <div class="flex items-center space-x-4">
          <div class="flex items-center">
            <div
              :class="[
                'w-3 h-3 rounded-full transition-colors',
                currentStepIndex >= 0 ? 'bg-primary' : 'bg-muted',
              ]"
            ></div>
            <span
              class="ml-2 text-sm font-medium"
              :class="currentStepIndex === 0 ? 'text-foreground' : 'text-muted-foreground'"
            >
              Type Selection
            </span>
          </div>
          <div class="w-24 h-0.5 bg-muted">
            <div
              class="h-full bg-primary transition-all"
              :style="{ width: currentStepIndex >= 1 ? '100%' : '0%' }"
            ></div>
          </div>
          <div class="flex items-center">
            <div
              :class="[
                'w-3 h-3 rounded-full transition-colors',
                currentStepIndex >= 1 ? 'bg-primary' : 'bg-muted',
              ]"
            ></div>
            <span
              class="ml-2 text-sm font-medium"
              :class="currentStepIndex === 1 ? 'text-foreground' : 'text-muted-foreground'"
            >
              Configuration
            </span>
          </div>
          <div class="w-24 h-0.5 bg-muted">
            <div
              class="h-full bg-primary transition-all"
              :style="{ width: currentStepIndex >= 2 ? '100%' : '0%' }"
            ></div>
          </div>
          <div class="flex items-center">
            <div
              :class="[
                'w-3 h-3 rounded-full transition-colors',
                currentStepIndex >= 2 ? 'bg-primary' : 'bg-muted',
              ]"
            ></div>
            <span
              class="ml-2 text-sm font-medium"
              :class="currentStepIndex === 2 ? 'text-foreground' : 'text-muted-foreground'"
            >
              Done
            </span>
          </div>
        </div>
      </div>

      <Separator class="mb-6" />

      <div class="flex flex-col overflow-y-auto" style="max-height: calc(90vh - 200px)">
        <!-- Type Selection Step -->
        <div v-if="currentStep === 'type-selection'" class="flex flex-col h-full">
          <!-- Search Input (only for models, not datasets) -->
          <div v-if="resourceConfig.singularName !== 'dataset'" class="relative mb-4">
            <Search
              class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"
            />
            <Input
              v-model="searchQuery"
              :placeholder="`Search ${resourceConfig.pluralName}...`"
              class="pl-10 pr-4"
            />
          </div>

          <!-- Dataset-specific Two-tier Selection -->
          <div v-if="resourceConfig.singularName === 'dataset'" class="space-y-6 flex-1">
            <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
              <!-- Add Files/Folders Card -->
              <div
                @click="dataSourceType = 'filesystem'"
                :class="[
                  'cursor-pointer transition-all duration-200 border-2 rounded-lg p-6 h-40',
                  dataSourceType === 'filesystem'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-border hover:border-border/60 hover:bg-muted/50',
                ]"
              >
                <div class="flex flex-col items-center justify-center text-center h-full">
                  <div
                    :class="[
                      'w-12 h-12 rounded-full flex items-center justify-center mb-3',
                      dataSourceType === 'filesystem' ? 'bg-blue-100' : 'bg-muted/50',
                    ]"
                  >
                    <Folder
                      :class="[
                        'w-6 h-6',
                        dataSourceType === 'filesystem' ? 'text-blue-600' : 'text-muted-foreground',
                      ]"
                    />
                  </div>
                  <h4
                    :class="[
                      'text-lg font-semibold mb-2',
                      dataSourceType === 'filesystem' ? 'text-blue-900' : 'text-foreground',
                    ]"
                  >
                    Add Files & Folders
                  </h4>
                  <p class="text-sm text-muted-foreground">
                    Watch local directories and files for data processing
                  </p>
                </div>
              </div>

              <!-- Connect Database Card -->
              <div
                @click="dataSourceType = 'database'"
                :class="[
                  'cursor-pointer transition-all duration-200 border-2 rounded-lg p-6 h-40',
                  dataSourceType === 'database'
                    ? 'border-purple-500 bg-purple-50'
                    : 'border-border hover:border-border/60 hover:bg-muted/50',
                ]"
              >
                <div class="flex flex-col items-center justify-center text-center h-full">
                  <div
                    :class="[
                      'w-12 h-12 rounded-full flex items-center justify-center mb-3',
                      dataSourceType === 'database' ? 'bg-purple-100' : 'bg-muted/50',
                    ]"
                  >
                    <Database
                      :class="[
                        'w-6 h-6',
                        dataSourceType === 'database' ? 'text-purple-600' : 'text-muted-foreground',
                      ]"
                    />
                  </div>
                  <h4
                    :class="[
                      'text-lg font-semibold mb-2',
                      dataSourceType === 'database' ? 'text-purple-900' : 'text-foreground',
                    ]"
                  >
                    Connect Database
                  </h4>
                  <p class="text-sm text-muted-foreground">
                    Connect to an existing vector database or service
                  </p>
                </div>
              </div>
            </div>

            <!-- Database Type Selection (shown when Connect Database is selected) -->
            <div v-if="dataSourceType === 'database'" class="space-y-4">
              <div class="space-y-2">
                <Label class="text-sm font-medium text-muted-foreground">
                  Choose Database Type <span class="text-red-500">*</span>
                </Label>
                <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <!-- Weaviate -->
                  <div
                    @click="selectedType = 'weaviate'"
                    :class="[
                      'cursor-pointer transition-all duration-200 border rounded-lg p-4 text-center',
                      selectedType === 'weaviate'
                        ? 'border-purple-500 bg-purple-50'
                        : 'border-border hover:border-border/60 hover:bg-muted/50',
                    ]"
                  >
                    <IntegrationIcon
                      name="weaviate"
                      :class="[
                        'h-8 w-8 mx-auto mb-2',
                        selectedType === 'weaviate' ? 'text-purple-600' : 'text-muted-foreground',
                      ]"
                    />
                    <span
                      :class="[
                        'text-sm font-medium',
                        selectedType === 'weaviate' ? 'text-purple-900' : 'text-foreground',
                      ]"
                    >
                      Weaviate
                    </span>
                  </div>

                  <!-- Qdrant -->
                  <div
                    @click="selectedType = 'qdrant'"
                    :class="[
                      'cursor-pointer transition-all duration-200 border rounded-lg p-4 text-center',
                      selectedType === 'qdrant'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-border hover:border-border/60 hover:bg-muted/50',
                    ]"
                  >
                    <IntegrationIcon
                      name="qdrant"
                      :class="[
                        'h-8 w-8 mx-auto mb-2',
                        selectedType === 'qdrant' ? 'text-blue-600' : 'text-muted-foreground',
                      ]"
                    />
                    <span
                      :class="[
                        'text-sm font-medium',
                        selectedType === 'qdrant' ? 'text-blue-900' : 'text-foreground',
                      ]"
                    >
                      Qdrant
                    </span>
                  </div>

                  <!-- Chroma -->
                  <div
                    @click="selectedType = 'chroma'"
                    :class="[
                      'cursor-pointer transition-all duration-200 border rounded-lg p-4 text-center',
                      selectedType === 'chroma'
                        ? 'border-green-500 bg-green-50'
                        : 'border-border hover:border-border/60 hover:bg-muted/50',
                    ]"
                  >
                    <IntegrationIcon
                      name="chroma"
                      :class="[
                        'h-8 w-8 mx-auto mb-2',
                        selectedType === 'chroma' ? 'text-green-600' : 'text-muted-foreground',
                      ]"
                    />
                    <span
                      :class="[
                        'text-sm font-medium',
                        selectedType === 'chroma' ? 'text-green-900' : 'text-foreground',
                      ]"
                    >
                      Chroma
                    </span>
                  </div>

                  <!-- Custom -->
                  <div
                    @click="selectedType = 'custom'"
                    :class="[
                      'cursor-pointer transition-all duration-200 border rounded-lg p-4 text-center',
                      selectedType === 'custom'
                        ? 'border-orange-500 bg-orange-50'
                        : 'border-border hover:border-border/60 hover:bg-muted/50',
                    ]"
                  >
                    <Code
                      :class="[
                        'h-8 w-8 mx-auto mb-2',
                        selectedType === 'custom' ? 'text-orange-600' : 'text-muted-foreground',
                      ]"
                    />
                    <span
                      :class="[
                        'text-sm font-medium',
                        selectedType === 'custom' ? 'text-orange-900' : 'text-foreground',
                      ]"
                    >
                      Custom
                    </span>
                  </div>
                </div>
              </div>

              <!-- Custom SDK Block -->
              <div v-if="selectedType === 'custom'" class="space-y-4">
                <div
                  class="bg-gradient-to-r from-orange-50 to-amber-50 border border-orange-200 rounded-lg p-6"
                >
                  <div class="flex items-start gap-4">
                    <div class="p-2 bg-orange-100 rounded-md">
                      <Code class="h-6 w-6 text-orange-600" />
                    </div>
                    <div class="flex-1">
                      <h5 class="text-lg font-semibold text-orange-900 mb-2">Custom Integration</h5>
                      <p class="text-sm text-orange-800 mb-4">
                        Build your own dataset integration using our SDK. Perfect for custom data
                        sources, proprietary databases, or specialized processing requirements.
                      </p>
                      <Button
                        @click="openCustomSDKDocs"
                        variant="outline"
                        class="border-orange-300 text-orange-700 hover:bg-orange-100"
                      >
                        <ExternalLink class="h-4 w-4 mr-2" />
                        View Documentation
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Standard Resource Options Grid (for models, etc.) -->
          <div
            v-else
            class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 overflow-y-auto flex-1 pr-2 pb-2"
          >
            <div
              v-for="option in filteredOptions"
              :key="option.id"
              @click="option.isCustom ? openCustomSDKDocs() : (selectedType = option.id)"
              :class="[
                'flex flex-col items-center justify-center p-6 rounded-lg border cursor-pointer transition-all group h-40',
                option.isCustom
                  ? 'border-purple-200 bg-gradient-to-r from-purple-50 to-blue-50 hover:border-purple-300 hover:bg-gradient-to-r hover:from-purple-100 hover:to-blue-100'
                  : selectedType === option.id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-border hover:bg-muted/50',
              ]"
            >
              <div v-if="option.isCustom" class="transition-all duration-200 mb-2">
                <div class="p-2 bg-purple-100 rounded-md group-hover:hidden">
                  <Code class="h-6 w-6 text-purple-600" />
                </div>
                <div class="hidden group-hover:block p-2 bg-purple-100 rounded-md">
                  <ExternalLink class="h-6 w-6 text-purple-600" />
                </div>
              </div>
              <IntegrationIcon
                v-else
                :name="option.id"
                class="h-12 w-12 mb-3"
                :class="selectedType === option.id ? 'text-blue-600' : 'text-muted-foreground'"
              />
              <div
                v-if="option.isCustom"
                class="text-center transition-all duration-200 min-h-[1.25rem]"
              >
                <span class="font-medium text-purple-800 group-hover:hidden">
                  {{ option.name }}
                </span>
                <span class="hidden group-hover:block font-medium text-purple-800">
                  View documentation
                </span>
              </div>
              <span
                v-else
                class="font-medium text-center"
                :class="selectedType === option.id ? 'text-blue-900' : 'text-foreground'"
              >
                {{ option.name }}
              </span>
              <div
                v-if="option.isCustom"
                class="text-center transition-all duration-200 min-h-[1rem]"
              >
                <span class="text-xs text-purple-600 group-hover:hidden">Using SDK</span>
                <span class="hidden group-hover:block text-xs text-purple-600"
                  >Opens in a new tab</span
                >
              </div>
            </div>
          </div>
        </div>

        <!-- Configuration Step -->
        <div v-if="currentStep === 'configuration'" class="space-y-4">
          <div>
            <h3 class="text-lg font-semibold">Configure {{ selectedTypeName }}</h3>
            <p class="text-sm text-muted-foreground">
              Set up your {{ selectedTypeName }} {{ resourceConfig.singularName }}
              {{ resourceConfig.configurationSuffix }}
            </p>
          </div>

          <!-- Dataset Name -->
          <div class="space-y-2">
            <Label for="dataset-name" class="text-sm font-medium text-muted-foreground">
              Dataset Name <span class="text-red-500">*</span>
            </Label>
            <Input
              id="dataset-name"
              v-model="datasetName"
              placeholder="e.g., Legal Documents Store"
              class="w-full"
            />
          </div>

          <!-- File System Configuration -->
          <div v-if="dataSourceType === 'filesystem'" class="space-y-4">
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h5 class="text-sm font-medium text-blue-900 mb-4 flex items-center gap-2">
                <Folder class="h-5 w-5 text-blue-600" />
                File System Configuration
              </h5>
              <FileExplorer v-model="selectedFiles" />
            </div>
          </div>

          <!-- Weaviate Configuration -->
          <div v-if="selectedType === 'weaviate'" class="space-y-4">
            <div class="bg-purple-50 border border-purple-200 rounded-lg p-4">
              <h5 class="text-sm font-medium text-purple-900 mb-4 flex items-center gap-2">
                <IntegrationIcon name="weaviate" class="h-5 w-5 text-purple-600" />
                Weaviate Configuration
              </h5>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="space-y-2">
                  <Label for="weaviate-url" class="text-sm font-medium text-muted-foreground">
                    Connection URL <span class="text-red-500">*</span>
                  </Label>
                  <Input
                    id="weaviate-url"
                    v-model="databaseConfig.url"
                    placeholder="http://localhost:8080"
                    class="w-full"
                  />
                </div>
                <div class="space-y-2">
                  <Label for="weaviate-index" class="text-sm font-medium text-muted-foreground">
                    Index Name <span class="text-red-500">*</span>
                  </Label>
                  <Input
                    id="weaviate-index"
                    v-model="databaseConfig.indexName"
                    placeholder="LegalDocuments"
                    class="w-full"
                  />
                </div>
                <div class="space-y-2">
                  <Label
                    for="weaviate-dimensions"
                    class="text-sm font-medium text-muted-foreground"
                  >
                    Vector Dimensions
                  </Label>
                  <Input
                    id="weaviate-dimensions"
                    v-model="databaseConfig.dimensions"
                    placeholder="1536"
                    type="number"
                    class="w-full"
                  />
                </div>
                <div class="space-y-2">
                  <Label for="weaviate-distance" class="text-sm font-medium text-muted-foreground">
                    Distance Metric
                  </Label>
                  <Select v-model="databaseConfig.distanceMetric">
                    <SelectTrigger class="w-full">
                      <SelectValue placeholder="Select metric" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cosine">Cosine</SelectItem>
                      <SelectItem value="euclidean">Euclidean</SelectItem>
                      <SelectItem value="dot">Dot Product</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          </div>

          <!-- Qdrant Configuration -->
          <div v-else-if="selectedType === 'qdrant'" class="space-y-4">
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h5 class="text-sm font-medium text-blue-900 mb-4 flex items-center gap-2">
                <IntegrationIcon name="qdrant" class="h-5 w-5 text-blue-600" />
                Qdrant Configuration
              </h5>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="space-y-2">
                  <Label for="qdrant-url" class="text-sm font-medium text-muted-foreground">
                    Connection URL <span class="text-red-500">*</span>
                  </Label>
                  <Input
                    id="qdrant-url"
                    v-model="databaseConfig.url"
                    placeholder="http://localhost:6333"
                    class="w-full"
                  />
                </div>
                <div class="space-y-2">
                  <Label for="qdrant-collection" class="text-sm font-medium text-muted-foreground">
                    Collection Name <span class="text-red-500">*</span>
                  </Label>
                  <Input
                    id="qdrant-collection"
                    v-model="databaseConfig.collectionName"
                    placeholder="legal_documents"
                    class="w-full"
                  />
                </div>
                <div class="space-y-2">
                  <Label for="qdrant-dimensions" class="text-sm font-medium text-muted-foreground">
                    Vector Dimensions
                  </Label>
                  <Input
                    id="qdrant-dimensions"
                    v-model="databaseConfig.dimensions"
                    placeholder="768"
                    type="number"
                    class="w-full"
                  />
                </div>
                <div class="space-y-2">
                  <Label for="qdrant-distance" class="text-sm font-medium text-muted-foreground">
                    Distance Metric
                  </Label>
                  <Select v-model="databaseConfig.distanceMetric">
                    <SelectTrigger class="w-full">
                      <SelectValue placeholder="Select metric" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cosine">Cosine</SelectItem>
                      <SelectItem value="euclidean">Euclidean</SelectItem>
                      <SelectItem value="dot">Dot Product</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          </div>

          <!-- Chroma Configuration -->
          <div v-else-if="selectedType === 'chroma'" class="space-y-4">
            <div class="bg-green-50 border border-green-200 rounded-lg p-4">
              <h5 class="text-sm font-medium text-green-900 mb-4 flex items-center gap-2">
                <IntegrationIcon name="chroma" class="h-5 w-5 text-green-600" />
                Chroma Configuration
              </h5>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="space-y-2">
                  <Label for="chroma-url" class="text-sm font-medium text-muted-foreground">
                    Connection URL <span class="text-red-500">*</span>
                  </Label>
                  <Input
                    id="chroma-url"
                    v-model="databaseConfig.url"
                    placeholder="http://localhost:8000"
                    class="w-full"
                  />
                </div>
                <div class="space-y-2">
                  <Label for="chroma-collection" class="text-sm font-medium text-muted-foreground">
                    Collection Name <span class="text-red-500">*</span>
                  </Label>
                  <Input
                    id="chroma-collection"
                    v-model="databaseConfig.collectionName"
                    placeholder="legal_documents"
                    class="w-full"
                  />
                </div>
                <div class="space-y-2">
                  <Label for="chroma-embedding" class="text-sm font-medium text-muted-foreground">
                    Embedding Model
                  </Label>
                  <Input
                    id="chroma-embedding"
                    v-model="databaseConfig.embeddingModel"
                    placeholder="all-MiniLM-L6-v2"
                    class="w-full"
                  />
                </div>
                <div class="space-y-2">
                  <Label for="chroma-distance" class="text-sm font-medium text-muted-foreground">
                    Distance Metric
                  </Label>
                  <Select v-model="databaseConfig.distanceMetric">
                    <SelectTrigger class="w-full">
                      <SelectValue placeholder="Select metric" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cosine">Cosine</SelectItem>
                      <SelectItem value="l2">L2 (Euclidean)</SelectItem>
                      <SelectItem value="ip">Inner Product</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          </div>

          <!-- Other types placeholder -->
          <div v-else-if="selectedType && selectedType !== 'custom'" class="space-y-4">
            <div class="bg-muted rounded-lg border border-border p-4 text-center">
              <p class="text-sm text-muted-foreground">
                Configuration form for {{ selectedTypeName }} will be implemented here
              </p>
            </div>
          </div>
        </div>

        <!-- Done Step -->
        <div v-if="currentStep === 'done'" class="space-y-4">
          <div class="text-center py-8">
            <div
              class="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4"
            >
              <Check class="h-8 w-8 text-green-600" />
            </div>
            <h3 class="text-xl font-semibold mb-2">
              {{ resourceConfig.displayName }}
              {{ isEditMode ? 'Updated' : 'Created' }} Successfully!
            </h3>
            <p class="text-muted-foreground">
              Your {{ selectedTypeName }} {{ resourceConfig.singularName }} has been
              {{ isEditMode ? 'updated' : 'created' }} and is ready to use.
            </p>
          </div>
        </div>
      </div>

      <Separator class="mt-4 mb-4" />

      <DialogFooter>
        <!-- Type Selection Step Buttons -->
        <div v-if="currentStep === 'type-selection'" class="flex justify-between w-full">
          <Button variant="ghost" @click="handleCancel"> Cancel </Button>
          <Button @click="goToNextStep" :disabled="!isTypeSelectionValid"> Next </Button>
        </div>

        <!-- Configuration Step Buttons -->
        <div v-if="currentStep === 'configuration'" class="flex justify-between w-full">
          <Button variant="ghost" @click="goToPreviousStep"> Previous </Button>
          <Button @click="handleCreate" :disabled="!isConfigurationValid">
            {{ isEditMode ? 'Update' : 'Create' }}
          </Button>
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
import { ref, computed, watch } from 'vue'
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
import { Search, Check, Code, ExternalLink, Folder, Database } from 'lucide-vue-next'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import FileExplorer from '@/components/FileExplorer.vue'

type Step = 'type-selection' | 'configuration' | 'done'

interface ResourceOption {
  id: string
  name: string
  type: string
  isCustom?: boolean
}

interface ResourceConfig {
  singularName: string
  pluralName: string
  displayName: string
  configurationSuffix: string
  customDocsUrl: string
  options: ResourceOption[]
}

interface Resource {
  id: string
  name: string
  type: string
  description: string
  tags: string[]
  status: 'running' | 'stopped'
}

const props = defineProps<{
  open: boolean
  resource?: Resource | null
  resourceConfig: ResourceConfig
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'resource-created': []
  'resource-updated': []
}>()

const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value),
})

const currentStep = ref<Step>('type-selection')
const searchQuery = ref('')
const selectedType = ref<string | null>(null)
const dataSourceType = ref<string | null>(null)

// Form data
const datasetName = ref('')
const selectedFiles = ref<string[]>([])

// Database configuration
const databaseConfig = ref({
  // Filesystem fields
  watchPath: '',
  filePatterns: '',
  // Database fields
  url: '',
  indexName: '',
  collectionName: '',
  dimensions: '',
  distanceMetric: '',
  embeddingModel: '',
  apiEndpoint: '',
  authToken: '',
})

const isEditMode = computed(() => !!props.resource)

const filteredOptions = computed(() => {
  if (!searchQuery.value) {
    return props.resourceConfig.options
  }
  return props.resourceConfig.options.filter((option) =>
    option.name.toLowerCase().includes(searchQuery.value.toLowerCase()),
  )
})

const currentStepIndex = computed(() => {
  const steps: Step[] = ['type-selection', 'configuration', 'done']
  return steps.indexOf(currentStep.value)
})

const selectedTypeName = computed(() => {
  if (dataSourceType.value === 'filesystem') {
    return 'Files & Folders'
  } else if (selectedType.value) {
    const option = props.resourceConfig.options.find((o) => o.id === selectedType.value)
    return option?.name || selectedType.value
  }
  return props.resourceConfig.displayName
})

const isTypeSelectionValid = computed(() => {
  // For datasets, use the two-tier validation
  if (props.resourceConfig.singularName === 'dataset') {
    if (!dataSourceType.value) return false

    // For filesystem, just need dataSourceType
    if (dataSourceType.value === 'filesystem') {
      return true
    }

    // For database, also need selectedType
    if (dataSourceType.value === 'database') {
      return selectedType.value !== null
    }

    return false
  }

  // For models and other resources, just need selectedType
  return selectedType.value !== null
})

const isConfigurationValid = computed(() => {
  const basicFieldsValid = datasetName.value.trim() !== ''

  // For filesystem datasets, validate required filesystem fields
  if (dataSourceType.value === 'filesystem') {
    return basicFieldsValid && selectedFiles.value.length > 0
  }

  // For vector database types, validate required database-specific fields
  if (selectedType.value === 'weaviate') {
    const dbConfigValid =
      databaseConfig.value.url.trim() !== '' && databaseConfig.value.indexName.trim() !== ''
    return basicFieldsValid && dbConfigValid
  } else if (selectedType.value === 'qdrant') {
    const dbConfigValid =
      databaseConfig.value.url.trim() !== '' && databaseConfig.value.collectionName.trim() !== ''
    return basicFieldsValid && dbConfigValid
  } else if (selectedType.value === 'chroma') {
    const dbConfigValid =
      databaseConfig.value.url.trim() !== '' && databaseConfig.value.collectionName.trim() !== ''
    return basicFieldsValid && dbConfigValid
  } else if (selectedType.value === 'custom') {
    return basicFieldsValid && databaseConfig.value.apiEndpoint.trim() !== ''
  }

  return basicFieldsValid
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
  goToNextStep()
  if (isEditMode.value) {
    emit('resource-updated')
  } else {
    emit('resource-created')
  }
}

const handleClose = () => {
  resetDialog()
  isOpen.value = false
}

const resetDialog = () => {
  currentStep.value = 'type-selection'
  selectedType.value = null
  searchQuery.value = ''
  dataSourceType.value = null
  datasetName.value = ''
  selectedFiles.value = []
  databaseConfig.value = {
    // Filesystem fields
    watchPath: '',
    filePatterns: '',
    // Database fields
    url: '',
    indexName: '',
    collectionName: '',
    dimensions: '',
    distanceMetric: '',
    embeddingModel: '',
    apiEndpoint: '',
    authToken: '',
  }
}

const openCustomSDKDocs = () => {
  window.open(props.resourceConfig.customDocsUrl, '_blank')
}

// Watch for resource prop changes to populate form in edit mode
watch(
  () => props.resource,
  (newResource) => {
    if (newResource && props.open) {
      selectedType.value = newResource.type
      datasetName.value = newResource.name || ''

      currentStep.value = 'configuration'
    }
  },
  { immediate: true },
)

// Watch for dialog open state to reset or populate form
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen && props.resource) {
      // Editing mode - populate form
      selectedType.value = props.resource.type
      datasetName.value = props.resource.name || ''

      currentStep.value = 'configuration'
    } else if (isOpen && !props.resource) {
      // Creation mode - reset form
      resetDialog()
    }
  },
)
</script>
