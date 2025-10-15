<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-2">
      <Database class="h-6 w-6 text-gray-600" />
      <h1 class="text-2xl font-semibold text-gray-900">Datasets</h1>
    </div>
    <p class="text-gray-600 mb-8">Organize and manage your datasets</p>

    <!-- Header with tabs and search bar -->
    <div class="flex items-center justify-between gap-4 mb-8">
      <!-- Tabs -->
      <Tabs v-model="activeTab" class="w-auto">
        <TabsList
          class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-3 lg:w-[400px]"
        >
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="running">Running</TabsTrigger>
          <TabsTrigger value="stopped">Stopped</TabsTrigger>
        </TabsList>
      </Tabs>

      <!-- Search bar and Create button -->
      <div class="flex items-center gap-4">
        <div class="relative w-80">
          <Search
            class="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400"
          />
          <Input
            v-model="searchQuery"
            placeholder="Find datasets, tags, types..."
            class="pl-10 pr-4 py-2 w-full"
          />
        </div>

        <!-- Add Dataset Button -->
        <Button
          class="bg-purple-600 hover:bg-purple-700 text-white"
          @click="showCreateDataSourceDialog = true"
        >
          <Plus class="h-4 w-4 mr-2" />
          Add Dataset
        </Button>
      </div>
    </div>

    <!-- Data Sources List -->
    <div class="space-y-4">
      <div
        v-for="dataSource in filteredDataSources"
        :key="dataSource.id"
        class="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-shadow cursor-pointer"
        @click="navigateToDetail(dataSource.name)"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div
              :class="[
                'p-3 rounded-lg',
                dataSource.type === 'weaviate'
                  ? 'bg-purple-100'
                  : dataSource.type === 'qdrant'
                    ? 'bg-blue-100'
                    : 'bg-green-100',
              ]"
            >
              <IntegrationIcon :name="dataSource.type" class="h-6 w-6" />
            </div>
            <div class="flex-1">
              <div class="flex items-center gap-3 mb-2">
                <h3 class="text-lg font-medium text-gray-900">{{ dataSource.name }}</h3>
                <Badge variant="secondary" class="bg-gray-900 text-white text-xs px-2 py-1">{{
                  dataSource.type
                }}</Badge>
                <Badge
                  variant="outline"
                  :class="
                    dataSource.status === 'running'
                      ? 'bg-green-50 text-green-700 border-green-200'
                      : 'bg-gray-50 text-gray-600 border-gray-200'
                  "
                  class="text-xs px-2 py-1"
                >
                  <div
                    :class="
                      dataSource.status === 'running'
                        ? 'w-2 h-2 bg-green-500 rounded-full mr-1'
                        : 'w-2 h-2 bg-gray-400 rounded-full mr-1'
                    "
                  ></div>
                  {{ dataSource.status }}
                </Badge>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Badge
                        variant="outline"
                        :class="
                          dataSource.endpointCount > 0
                            ? 'bg-blue-50 text-blue-700 border-blue-200 cursor-help'
                            : 'bg-gray-50 text-gray-600 border-gray-200'
                        "
                        class="text-xs px-2 py-1"
                      >
                        <div
                          :class="
                            dataSource.endpointCount > 0
                              ? 'w-2 h-2 bg-blue-500 rounded-full mr-1'
                              : 'w-2 h-2 bg-gray-400 rounded-full mr-1'
                          "
                        ></div>
                        {{
                          dataSource.endpointCount === 0
                            ? 'No endpoints'
                            : `${dataSource.endpointCount} endpoint${dataSource.endpointCount !== 1 ? 's' : ''}`
                        }}
                      </Badge>
                    </TooltipTrigger>
                    <TooltipContent v-if="dataSource.endpointCount > 0">
                      <div class="space-y-1">
                        <p class="font-medium text-xs">Connected Endpoints:</p>
                        <ul class="space-y-1">
                          <li
                            v-for="endpointName in getEndpointNamesForDataset(dataSource.id)"
                            :key="endpointName"
                            class="text-xs"
                          >
                            • {{ endpointName }}
                          </li>
                        </ul>
                      </div>
                    </TooltipContent>
                    <TooltipContent v-else>
                      <p class="text-xs">This dataset is not connected to any endpoint</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <p class="text-gray-600 mb-3">
                {{ dataSource.description }}
              </p>
              <div class="flex gap-2">
                <Badge
                  v-for="tag in dataSource.tags"
                  :key="tag"
                  variant="outline"
                  class="text-xs px-2 py-1"
                >
                  {{ tag }}
                </Badge>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              class="text-gray-600"
              @click.stop="handleEditDataset(dataSource)"
            >
              <Edit class="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              class="text-red-600 hover:text-red-700"
              @click.stop="handleDeleteDataset(dataSource)"
            >
              <Trash2 class="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
        </div>
      </div>
    </div>

    <!-- DEMO: Empty State Section -->
    <div class="mt-16">
      <!-- Divider with centered text -->
      <div class="relative">
        <div class="absolute inset-0 flex items-center">
          <div class="w-full border-t border-gray-300"></div>
        </div>
        <div class="relative flex justify-center text-sm">
          <span class="px-4 bg-gray-50 text-gray-600 font-medium">
            Demo: Empty State (shown when no datasets exist)
          </span>
        </div>
      </div>

      <!-- Empty state content -->
      <div class="mt-8 bg-white rounded-lg shadow border border-gray-200 p-8 text-center">
        <Database class="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 class="text-lg font-medium text-gray-900 mb-2">No datasets yet</h3>
        <p class="text-gray-600 mb-4">Start by adding or connecting your first dataset</p>
        <Button
          class="bg-purple-600 hover:bg-purple-700 text-white"
          @click="showCreateDataSourceDialog = true"
        >
          <Plus class="h-4 w-4 mr-2" />
          Add Dataset
        </Button>
      </div>
    </div>
  </div>

  <!-- Create Dataset Dialog -->
  <CreateDatasetDialog
    v-model:open="showCreateDataSourceDialog"
    :dataset="editingDataset"
    @dataset-created="handleDatasetCreated"
    @dataset-updated="handleDatasetUpdated"
    @update:open="!$event && handleDialogClose()"
  />

  <!-- Delete Confirmation Dialog -->
  <Dialog v-model:open="showDeleteDialog">
    <DialogContent class="sm:max-w-[600px]">
      <DialogHeader>
        <DialogTitle>Delete Dataset</DialogTitle>
        <DialogDescription>
          Are you sure you want to delete "{{ datasetToDelete?.name }}"? This action cannot be
          undone.
        </DialogDescription>
      </DialogHeader>

      <div v-if="datasetToDelete && datasetToDelete.endpointCount > 0" class="py-4">
        <div class="space-y-4">
          <div class="bg-red-50 border border-red-200 rounded-md p-4">
            <div class="flex items-start gap-3">
              <div class="text-xl">⚠️</div>
              <div class="flex-1">
                <p class="text-red-900 font-semibold text-sm mb-2">
                  This dataset has {{ datasetToDelete.endpointCount }} dependent endpoint{{
                    datasetToDelete.endpointCount !== 1 ? 's' : ''
                  }}
                  that will be deleted:
                </p>
                <p class="text-red-800 text-xs mb-3">Check each endpoint to confirm deletion</p>
                <div class="space-y-2">
                  <div
                    v-for="endpointName in getEndpointNamesForDataset(datasetToDelete.id)"
                    :key="endpointName"
                    class="flex items-center gap-3 p-2.5 bg-white rounded border border-red-200"
                  >
                    <input
                      type="checkbox"
                      :id="`endpoint-${endpointName}`"
                      :checked="checkedEndpoints.includes(endpointName)"
                      @change="() => toggleEndpoint(endpointName)"
                      class="w-4 h-4 text-red-600 bg-white border-red-400 rounded focus:ring-red-500 focus:ring-2"
                    />
                    <label
                      :for="`endpoint-${endpointName}`"
                      class="flex-1 cursor-pointer flex items-center justify-between"
                    >
                      <span class="text-sm font-medium text-gray-900">
                        {{ endpointName }}
                      </span>
                      <span class="text-xs text-red-600"> Will be deleted </span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="cancelDeleteDataset"> Cancel </Button>
        <Button
          variant="destructive"
          @click="confirmDeleteDataset"
          :disabled="!allEndpointsChecked"
        >
          {{
            datasetToDelete && datasetToDelete.endpointCount && datasetToDelete.endpointCount > 0
              ? `Delete Dataset & ${datasetToDelete.endpointCount} Endpoint${datasetToDelete.endpointCount !== 1 ? 's' : ''}`
              : 'Delete Dataset'
          }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { Database, Plus, Edit, Trash2, Search } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import CreateDatasetDialog from '@/components/CreateDatasetDialog.vue'

interface DataSource {
  id: string
  name: string
  type: string
  description: string
  tags: string[]
  status: 'running' | 'stopped'
  endpointCount: number
}

interface Endpoint {
  id: string
  name: string
  datasetIds: string[]
}

// Mock endpoints data
const mockEndpoints: Endpoint[] = [
  {
    id: 'endpoint-1',
    name: 'Legal Document Analysis API',
    datasetIds: ['1'],
  },
  {
    id: 'endpoint-2',
    name: 'Contract Review Assistant',
    datasetIds: ['1'],
  },
  {
    id: 'endpoint-3',
    name: 'Legal Research Helper',
    datasetIds: ['1'],
  },
  {
    id: 'endpoint-4',
    name: 'Customer Insights API',
    datasetIds: ['2'],
  },
]

const router = useRouter()

// Mock data sources
const dataSources = ref<DataSource[]>([
  {
    id: '1',
    name: 'Legal Documents Store',
    type: 'weaviate',
    description: 'Vector database for legal document analysis and retrieval',
    tags: ['legal', 'documents', 'analysis'],
    status: 'running',
    endpointCount: 3,
  },
  {
    id: '2',
    name: 'Customer Analytics Store',
    type: 'qdrant',
    description: 'Vector database for customer behavior analysis and segmentation',
    tags: ['customer', 'analytics', 'segmentation'],
    status: 'running',
    endpointCount: 1,
  },
  {
    id: '3',
    name: 'Research Database',
    type: 'chroma',
    description: 'Knowledge base for research papers and scientific literature',
    tags: ['research', 'papers', 'knowledge'],
    status: 'stopped',
    endpointCount: 0,
  },
])

const showCreateDataSourceDialog = ref(false)
const searchQuery = ref('')
const activeTab = ref('all')
const editingDataset = ref<DataSource | null>(null)
const showDeleteDialog = ref(false)
const datasetToDelete = ref<DataSource | null>(null)
const checkedEndpoints = ref<string[]>([])

// Function to get endpoint names connected to a dataset
const getEndpointNamesForDataset = (datasetId: string): string[] => {
  return mockEndpoints
    .filter((endpoint) => endpoint.datasetIds.includes(datasetId))
    .map((endpoint) => endpoint.name)
}

const filteredDataSources = computed(() => {
  return dataSources.value.filter((dataSource) => {
    // Search query filter
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      if (
        !dataSource.name.toLowerCase().includes(query) &&
        !dataSource.description.toLowerCase().includes(query) &&
        !dataSource.tags.some((tag) => tag.toLowerCase().includes(query))
      ) {
        return false
      }
    }

    // Tab filter
    if (activeTab.value === 'running' && dataSource.status !== 'running') {
      return false
    }
    if (activeTab.value === 'stopped' && dataSource.status !== 'stopped') {
      return false
    }

    return true
  })
})

const handleDatasetCreated = () => {
  console.log('Dataset created successfully')
}

const handleEditDataset = (dataset: DataSource) => {
  editingDataset.value = dataset
  showCreateDataSourceDialog.value = true
}

const handleDatasetUpdated = () => {
  console.log('Dataset updated successfully')
  editingDataset.value = null
}

// Reset editing state when dialog closes
const handleDialogClose = () => {
  editingDataset.value = null
}

const handleDeleteDataset = (dataset: DataSource) => {
  datasetToDelete.value = dataset
  checkedEndpoints.value = []
  showDeleteDialog.value = true
}

const confirmDeleteDataset = () => {
  if (datasetToDelete.value) {
    console.log('Deleting dataset:', datasetToDelete.value.name)
    // In a real app, this would call an API to delete the dataset
    const index = dataSources.value.findIndex((ds) => ds.id === datasetToDelete.value!.id)
    if (index > -1) {
      dataSources.value.splice(index, 1)
    }
    showDeleteDialog.value = false
    datasetToDelete.value = null
  }
}

const cancelDeleteDataset = () => {
  showDeleteDialog.value = false
  datasetToDelete.value = null
  checkedEndpoints.value = []
}

// Check if all endpoints are selected
const allEndpointsChecked = computed(() => {
  if (!datasetToDelete.value) return true
  if (datasetToDelete.value.endpointCount === 0) return true

  const endpointNames = getEndpointNamesForDataset(datasetToDelete.value.id)
  return endpointNames.length > 0 && endpointNames.length === checkedEndpoints.value.length
})

// Navigate to dataset detail page
const navigateToDetail = (datasetSlug: string) => {
  router.push(`/datasets/${datasetSlug}`)
}

// Toggle endpoint checkbox
const toggleEndpoint = (endpointName: string) => {
  const index = checkedEndpoints.value.indexOf(endpointName)
  if (index > -1) {
    checkedEndpoints.value.splice(index, 1)
  } else {
    checkedEndpoints.value.push(endpointName)
  }
}
</script>
