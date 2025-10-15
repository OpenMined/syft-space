<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Breadcrumb Navigation -->
    <nav class="flex mb-6" aria-label="Breadcrumb">
      <ol class="flex items-center space-x-2">
        <li>
          <router-link
            to="/datasets"
            class="text-gray-500 hover:text-gray-700 text-sm font-medium flex items-center"
          >
            <Database class="h-4 w-4 mr-1" />
            Datasets
          </router-link>
        </li>
        <li class="flex items-center">
          <ChevronRight class="h-4 w-4 text-gray-400 mx-2" />
          <span class="text-gray-900 text-sm font-medium">{{ dataset?.name || 'Loading...' }}</span>
        </li>
      </ol>
    </nav>

    <!-- Error State -->
    <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
      <h3 class="text-lg font-medium text-red-900 mb-2">Dataset not found</h3>
      <p class="text-red-700 mb-4">
        The dataset you're looking for doesn't exist or has been deleted.
      </p>
      <Button @click="$router.push('/datasets')" variant="outline"> Back to Datasets </Button>
    </div>

    <!-- Dataset Details -->
    <div v-else-if="dataset" class="space-y-6">
      <!-- Header -->
      <div class="bg-white border border-gray-200 rounded-lg p-6">
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-4">
            <div
              :class="[
                'p-3 rounded-lg',
                dataset.type === 'weaviate'
                  ? 'bg-purple-100'
                  : dataset.type === 'qdrant'
                    ? 'bg-blue-100'
                    : 'bg-green-100',
              ]"
            >
              <IntegrationIcon :name="dataset.type" class="h-8 w-8" />
            </div>
            <div>
              <h1 class="text-3xl font-bold text-gray-900 mb-2">{{ dataset.name }}</h1>
              <p class="text-gray-600 mb-4">{{ dataset.description }}</p>
              <div class="flex flex-wrap items-center gap-2">
                <Badge
                  :variant="dataset.status === 'running' ? 'default' : 'outline'"
                  :class="
                    dataset.status === 'running'
                      ? 'bg-green-50 text-green-700 border-green-200'
                      : 'bg-gray-50 text-gray-600 border-gray-200'
                  "
                >
                  <div
                    :class="
                      dataset.status === 'running'
                        ? 'w-2 h-2 bg-green-500 rounded-full mr-2'
                        : 'w-2 h-2 bg-gray-400 rounded-full mr-2'
                    "
                  ></div>
                  {{ dataset.status === 'running' ? 'Running' : 'Stopped' }}
                </Badge>
                <Badge variant="outline" class="bg-blue-50 text-blue-700 border-blue-200">
                  <div class="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                  {{ dataset.type.charAt(0).toUpperCase() + dataset.type.slice(1) }}
                </Badge>
                <!-- Tags as badges -->
                <Badge
                  v-for="tag in dataset.tags"
                  :key="`tag-${tag}`"
                  variant="outline"
                  class="bg-amber-50 text-amber-700 border-amber-200"
                >
                  <div class="w-2 h-2 bg-amber-500 rounded-full mr-2"></div>
                  {{ tag }}
                </Badge>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <Button variant="outline" @click="editDataset">
              <Edit class="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button
              variant="outline"
              class="text-red-600 hover:text-red-700"
              @click="deleteDataset"
            >
              <Trash2 class="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
        </div>
      </div>

      <!-- Content Grid -->
      <div class="space-y-6">
        <!-- Top Row - Equal Width Cards -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- Dataset Details -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Dataset Details</h2>
            <div class="space-y-3">
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Type:</span>
                <span class="text-sm text-gray-900">{{
                  dataset.type.charAt(0).toUpperCase() + dataset.type.slice(1)
                }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Status:</span>
                <span class="text-sm text-gray-900 capitalize">{{ dataset.status }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Connected Endpoints:</span>
                <span class="text-sm text-gray-900">{{ dataset.endpointCount }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Created:</span>
                <span class="text-sm text-gray-900">{{ formatDate(dataset.createdAt) }}</span>
              </div>
            </div>
          </div>

          <!-- Dataset Revenue -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Dataset Revenue</h2>
            <div class="space-y-4">
              <div class="text-center p-4 bg-green-50 rounded-lg">
                <p class="text-2xl font-bold text-green-600 mb-1">{{ getRevenue().total }}</p>
                <p class="text-sm text-green-700">Total Revenue</p>
              </div>
              <div class="space-y-3">
                <div class="flex justify-between items-center">
                  <span class="text-sm text-gray-600">This Month:</span>
                  <span class="text-sm text-green-600 font-semibold">{{
                    getRevenue().thisMonth
                  }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-sm text-gray-600">Growth:</span>
                  <span class="text-sm text-green-600 font-semibold">{{
                    getRevenue().growth
                  }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Usage Statistics -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Usage Statistics</h2>
            <div class="space-y-3">
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Total Queries:</span>
                <span class="text-sm text-gray-900 font-semibold">{{
                  getUsageStats().totalQueries
                }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Data Points:</span>
                <span class="text-sm text-gray-900 font-semibold">{{
                  getUsageStats().dataPoints
                }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Storage Used:</span>
                <span class="text-sm text-gray-900 font-semibold">{{
                  getUsageStats().storageUsed
                }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">This Month:</span>
                <span class="text-sm text-gray-900 font-semibold">{{
                  getUsageStats().thisMonth
                }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Dataset Configuration -->
        <div class="bg-white border border-gray-200 rounded-lg p-6">
          <h2 class="text-2xl font-semibold text-gray-900 mb-4">Dataset Configuration</h2>
          <div
            class="min-h-[300px] flex items-center justify-center border-2 border-dashed border-gray-300 rounded-lg bg-gray-50"
          >
            <div class="text-center">
              <p class="text-gray-500 text-lg mb-2">
                Configuration for {{ dataset.type.charAt(0).toUpperCase() + dataset.type.slice(1) }}
              </p>
              <p class="text-gray-400 text-sm">
                Dataset configuration details will be displayed here
              </p>
            </div>
          </div>
        </div>

        <!-- Access Trends -->
        <div class="bg-white border border-gray-200 rounded-lg p-6">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-2xl font-semibold text-gray-900">Access Trends</h2>
            <div class="flex items-center gap-2">
              <Button
                v-for="period in ['Daily', 'Weekly', 'Monthly']"
                :key="period"
                size="sm"
                :variant="selectedPeriod === period ? 'default' : 'outline'"
                @click="selectedPeriod = period"
                class="text-xs"
              >
                {{ period }}
              </Button>
            </div>
          </div>
          <div
            class="h-64 flex items-center justify-center border border-dashed border-gray-300 rounded-lg bg-gray-50"
          >
            <div class="text-center">
              <p class="text-gray-500 text-lg mb-1">{{ selectedPeriod }} Access Chart</p>
              <p class="text-gray-400 text-sm">Graph visualization will be displayed here</p>
            </div>
          </div>
        </div>

        <!-- Connected Endpoints - Full Width -->
        <div class="bg-white border border-gray-200 rounded-lg p-6">
          <h2 class="text-xl font-semibold text-gray-900 mb-4">Connected Endpoints</h2>
          <div v-if="connectedEndpoints.length > 0" class="space-y-4">
            <div
              v-for="endpoint in connectedEndpoints"
              :key="endpoint.id"
              class="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
            >
              <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-blue-100 rounded-md">
                    <Globe class="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 class="text-sm font-medium text-gray-900">{{ endpoint.name }}</h3>
                    <p class="text-xs text-gray-600">
                      {{ endpoint.description || 'API endpoint' }}
                    </p>
                  </div>
                </div>
                <Button variant="outline" size="sm">
                  <ExternalLink class="h-3 w-3" />
                </Button>
              </div>

              <!-- Request Distribution for this endpoint -->
              <div class="mt-3 pt-3 border-t border-gray-100">
                <div class="flex items-center justify-between mb-2">
                  <span class="text-xs text-gray-600 font-medium">Request Distribution</span>
                  <span class="text-xs text-gray-900 font-semibold"
                    >{{ getEndpointPercentage(endpoint.name) }}% of total</span
                  >
                </div>
                <div class="flex items-center gap-3">
                  <div class="flex-1 bg-gray-200 rounded-full h-2">
                    <div
                      class="h-2 rounded-full transition-all duration-300"
                      :style="{
                        width: getEndpointPercentage(endpoint.name) + '%',
                        backgroundColor: getEndpointColor(endpoint.name),
                      }"
                    ></div>
                  </div>
                  <span class="text-xs text-gray-600"
                    >{{ getEndpointRequests(endpoint.name) }} requests</span
                  >
                </div>
              </div>
            </div>
          </div>
          <div v-else class="text-center py-8">
            <Globe class="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 class="text-lg font-medium text-gray-900 mb-2">No endpoints connected</h3>
            <p class="text-gray-600 mb-4">
              This dataset is not currently connected to any endpoints.
            </p>
            <Button>
              <Plus class="h-4 w-4 mr-2" />
              Create Endpoint
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Create Dataset Dialog -->
  <CreateDatasetDialog
    v-model:open="showEditDialog"
    :dataset="dataset"
    @dataset-updated="handleDatasetUpdated"
    @update:open="!$event && handleDialogClose()"
  />

  <!-- Delete Confirmation Dialog -->
  <Dialog v-model:open="showDeleteDialog">
    <DialogContent class="sm:max-w-[600px]">
      <DialogHeader>
        <DialogTitle>Delete Dataset</DialogTitle>
        <DialogDescription>
          Are you sure you want to delete "{{ dataset?.name }}"? This action cannot be undone.
        </DialogDescription>
      </DialogHeader>

      <div v-if="dataset && dataset.endpointCount > 0" class="py-4">
        <div class="space-y-4">
          <div class="bg-red-50 border border-red-200 rounded-md p-4">
            <div class="flex items-start gap-3">
              <div class="text-xl">⚠️</div>
              <div class="flex-1">
                <p class="text-red-900 font-semibold text-sm mb-2">
                  This dataset has {{ dataset.endpointCount }} dependent endpoint{{
                    dataset.endpointCount !== 1 ? 's' : ''
                  }}
                  that will be deleted:
                </p>
                <p class="text-red-800 text-xs mb-3">Check each endpoint to confirm deletion</p>
                <div class="space-y-2">
                  <div
                    v-for="endpointName in getEndpointNamesForDataset(dataset.id)"
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
        <Button variant="outline" @click="cancelDelete"> Cancel </Button>
        <Button variant="destructive" @click="confirmDelete" :disabled="!allEndpointsChecked">
          {{
            dataset && dataset.endpointCount && dataset.endpointCount > 0
              ? `Delete Dataset & ${dataset.endpointCount} Endpoint${dataset.endpointCount !== 1 ? 's' : ''}`
              : 'Delete Dataset'
          }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Database, ChevronRight, Edit, Trash2, Globe, Plus, ExternalLink } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
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
  createdAt: Date
}

interface Endpoint {
  id: string
  name: string
  description?: string
  datasetIds: string[]
}

// Mock data - in a real app, this would come from an API
const mockDatasets: DataSource[] = [
  {
    id: '1',
    name: 'Legal Documents Store',
    type: 'weaviate',
    description: 'Vector database for legal document analysis and retrieval',
    tags: ['legal', 'documents', 'analysis'],
    status: 'running',
    endpointCount: 3,
    createdAt: new Date('2024-01-15'),
  },
  {
    id: '2',
    name: 'Customer Analytics Store',
    type: 'qdrant',
    description: 'Vector database for customer behavior analysis and segmentation',
    tags: ['customer', 'analytics', 'segmentation'],
    status: 'running',
    endpointCount: 1,
    createdAt: new Date('2024-02-10'),
  },
  {
    id: '3',
    name: 'Research Database',
    type: 'chroma',
    description: 'Knowledge base for research papers and scientific literature',
    tags: ['research', 'papers', 'knowledge'],
    status: 'stopped',
    endpointCount: 0,
    createdAt: new Date('2024-03-05'),
  },
]

const mockEndpoints: Endpoint[] = [
  {
    id: 'endpoint-1',
    name: 'Legal Document Analysis API',
    description: 'Analyze and extract insights from legal documents',
    datasetIds: ['1'],
  },
  {
    id: 'endpoint-2',
    name: 'Contract Review Assistant',
    description: 'AI-powered contract review and analysis',
    datasetIds: ['1'],
  },
  {
    id: 'endpoint-3',
    name: 'Legal Research Helper',
    description: 'Search and retrieve relevant legal precedents',
    datasetIds: ['1'],
  },
  {
    id: 'endpoint-4',
    name: 'Customer Insights API',
    description: 'Generate customer behavior insights',
    datasetIds: ['2'],
  },
]

const route = useRoute()
const router = useRouter()

const error = ref(false)
const dataset = ref<DataSource | null>(null)
const showEditDialog = ref(false)
const showDeleteDialog = ref(false)
const checkedEndpoints = ref<string[]>([])
const selectedPeriod = ref('Daily')

const connectedEndpoints = computed(() => {
  if (!dataset.value) return []
  return mockEndpoints.filter((endpoint) => endpoint.datasetIds.includes(dataset.value!.id))
})

const formatDate = (date: Date) => {
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

const getUsageStats = () => {
  // Mock data - in real app this would come from analytics API
  return {
    totalQueries: '8.4k',
    dataPoints: '2.1M',
    storageUsed: '1.2GB',
    thisMonth: '847',
  }
}

const getRevenue = () => {
  // Mock data - in real app this would come from billing/revenue API
  return {
    total: '$842.60',
    thisMonth: '$156.30',
    lastMonth: '$142.85',
    growth: '+9.4%',
  }
}

const getEndpointDistribution = () => {
  // Mock data - in real app this would come from analytics API
  return [
    { name: 'Legal Document Analysis API', percentage: 45, color: '#3B82F6', requests: '3.8k' },
    { name: 'Contract Review Assistant', percentage: 35, color: '#10B981', requests: '2.9k' },
    { name: 'Legal Research Helper', percentage: 20, color: '#F59E0B', requests: '1.7k' },
  ]
}

const getEndpointPercentage = (endpointName: string) => {
  const distribution = getEndpointDistribution()
  const endpoint = distribution.find((e) => e.name === endpointName)
  return endpoint?.percentage || 0
}

const getEndpointColor = (endpointName: string) => {
  const distribution = getEndpointDistribution()
  const endpoint = distribution.find((e) => e.name === endpointName)
  return endpoint?.color || '#6B7280'
}

const getEndpointRequests = (endpointName: string) => {
  const distribution = getEndpointDistribution()
  const endpoint = distribution.find((e) => e.name === endpointName)
  return endpoint?.requests || '0'
}

// Function to get endpoint names connected to a dataset
const getEndpointNamesForDataset = (datasetId: string): string[] => {
  return mockEndpoints
    .filter((endpoint) => endpoint.datasetIds.includes(datasetId))
    .map((endpoint) => endpoint.name)
}

// Check if all endpoints are selected
const allEndpointsChecked = computed(() => {
  if (!dataset.value) return true
  if (dataset.value.endpointCount === 0) return true

  const endpointNames = getEndpointNamesForDataset(dataset.value.id)
  return endpointNames.length > 0 && endpointNames.length === checkedEndpoints.value.length
})

// Toggle endpoint checkbox
const toggleEndpoint = (endpointName: string) => {
  const index = checkedEndpoints.value.indexOf(endpointName)
  if (index > -1) {
    checkedEndpoints.value.splice(index, 1)
  } else {
    checkedEndpoints.value.push(endpointName)
  }
}

const editDataset = () => {
  showEditDialog.value = true
}

const deleteDataset = () => {
  checkedEndpoints.value = []
  showDeleteDialog.value = true
}

const handleDatasetUpdated = () => {
  console.log('Dataset updated successfully')
  showEditDialog.value = false
  // In a real app, you might want to refresh the dataset data here
}

const handleDialogClose = () => {
  showEditDialog.value = false
}

const confirmDelete = () => {
  if (dataset.value) {
    console.log('Deleting dataset:', dataset.value.name)
    // In a real app, this would call an API to delete the dataset
    // Then navigate back to the list
    router.push('/datasets')
  }
}

const cancelDelete = () => {
  showDeleteDialog.value = false
  checkedEndpoints.value = []
}

onMounted(() => {
  const datasetSlug = route.params.slug as string
  const foundDataset = mockDatasets.find((d) => d.name === datasetSlug)

  if (foundDataset) {
    dataset.value = foundDataset
  } else {
    error.value = true
  }
})
</script>
