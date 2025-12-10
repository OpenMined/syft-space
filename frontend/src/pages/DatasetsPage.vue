<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-10">
      <div class="flex items-center gap-3 mb-3">
        <Database class="h-6 w-6 text-primary" />
        <h1 class="heading-3">Your Datasets</h1>
      </div>
      <p class="body-lg text-muted-foreground md:max-w-[60%]">
        Datasets are local data sources only you can see and use. Power AI workflows and queries
        locally; share access later via endpoints.
      </p>
    </div>

    <!-- Actions Bar -->
    <div class="flex items-center justify-between mb-8">
      <Input v-model="searchQuery" placeholder="Search datasets..." class="w-64" />
      <Button @click="showCreateDataSourceDialog = true">
        <Plus class="h-4 w-4 mr-2" />
        Add Dataset
      </Button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="space-y-5">
      <div v-for="i in 3" :key="`skeleton-${i}`"
        class="bg-card border border-border rounded-xl p-6 animate-pulse">
        <div class="flex items-start justify-between">
          <div class="flex-1 flex gap-4">
            <div class="w-14 h-14 bg-muted rounded-xl"></div>
            <div class="flex-1 space-y-2">
              <div class="h-6 bg-muted rounded w-1/3"></div>
              <div class="h-4 bg-muted rounded w-1/2"></div>
              <div class="h-4 bg-muted rounded w-2/3"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="text-center py-8">
      <div class="text-destructive mb-2">Failed to load datasets</div>
      <Button @click="loadDatasets" variant="outline">Try Again</Button>
    </div>

    <!-- Empty State -->
    <div v-else-if="datasets.length === 0" class="text-center py-8">
      <Database class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
      <h3 class="heading-3 text-foreground mb-2">No datasets yet</h3>
      <p class="body-sm text-muted-foreground mb-4">
        Start by adding or connecting your first dataset
      </p>
      <Button @click="showCreateDataSourceDialog = true">
        <Plus class="h-4 w-4 mr-2" />
        Add Dataset
      </Button>
    </div>

    <!-- Data Sources List -->
    <div v-else class="space-y-5">
      <div v-for="dataSource in filteredDataSources" :key="dataSource.id"
        class="bg-card border border-border rounded-xl p-6 hover:shadow-lg transition-all cursor-pointer"
        @click="navigateToDetail(dataSource.name)">
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-start gap-4">
              <div :class="[
                'p-3.5 rounded-xl',
                dataSource.type === 'weaviate'
                  ? 'bg-primary/10'
                  : dataSource.type === 'qdrant'
                    ? 'bg-primary/10'
                    : 'bg-primary/10',
              ]">
                <Database class="h-6 w-6 text-foreground/60" />
              </div>
              <div class="flex-1">
                <div class="flex items-center gap-3 mb-2">
                  <h3 class="heading-4 text-foreground">{{ dataSource.name }}</h3>
                  <Badge variant="outline" :class="dataSource.status === 'running'
                    ? 'bg-primary/10 text-primary border border-primary/20'
                    : 'bg-muted text-muted-foreground border-border'
                    " class="body-sm px-2.5 py-1 rounded-md">
                    <div :class="dataSource.status === 'running'
                      ? 'w-2 h-2 bg-primary rounded-full mr-1'
                      : 'w-2 h-2 bg-muted-foreground rounded-full mr-1'
                      "></div>
                    {{ dataSource.status }}
                  </Badge>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger as-child>
                        <Badge variant="outline" :class="dataSource.endpointCount > 0
                          ? 'bg-primary/10 text-primary border border-primary/20 cursor-help'
                          : 'bg-muted text-muted-foreground border border-border'
                          " class="body-sm px-2.5 py-1 rounded-md">
                          <Link :class="dataSource.endpointCount > 0
                            ? 'w-3.5 h-3.5 mr-1.5'
                            : 'w-3.5 h-3.5 mr-1.5 opacity-40'
                            " />
                          {{
                            dataSource.endpointCount === 0
                              ? 'No endpoints'
                              : `${dataSource.endpointCount} endpoint${dataSource.endpointCount !== 1 ? 's' : ''}`
                          }}
                        </Badge>
                      </TooltipTrigger>
                      <TooltipContent v-if="dataSource.endpointCount > 0">
                        <div class="space-y-1">
                          <p class="font-medium body-sm">Connected Endpoints:</p>
                          <ul class="space-y-1">
                            <li v-for="endpointName in getEndpointNamesForDataset(dataSource.id)" :key="endpointName"
                              class="body-sm">
                              • {{ endpointName }}
                            </li>
                          </ul>
                        </div>
                      </TooltipContent>
                      <TooltipContent v-else>
                        <p class="body-sm">This dataset is not connected to any endpoint</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <p class="body-sm text-muted-foreground mb-4">
                  {{ dataSource.description }}
                </p>

                <!-- Watched Paths Preview -->
                <div class="mb-4 space-y-2 pl-2">
                  <div v-if="dataSource.isCustom" class="body-sm text-muted-foreground">
                    📂 <span class="italic">Custom dataset - manually configured</span>
                  </div>

                  <div v-else-if="!dataSource.watchedPaths || dataSource.watchedPaths.length === 0"
                    class="body-sm text-muted-foreground">
                    📂 <span class="italic">No paths configured</span>
                  </div>

                  <div v-else class="space-y-1">
                    <div class="body-sm text-muted-foreground flex items-center gap-2">
                      📂 <span class="font-medium">Files & Folders:</span>
                    </div>
                    <div class="ml-6 space-y-1 py-1">
                      <div v-for="path in getPathsPreview(dataSource).paths" :key="path"
                        class="body-sm font-mono text-muted-foreground opacity-75">
                        {{ path }}
                      </div>
                      <div v-if="getPathsPreview(dataSource).hasMore"
                        class="body-sm text-muted-foreground opacity-60 italic">
                        +{{ getPathsPreview(dataSource).totalCount - 3 }} more...
                      </div>
                    </div>
                  </div>
                </div>

                <div class="flex gap-2">
                  <Badge v-for="tag in dataSource.tags" :key="tag" variant="outline" class="body-sm">
                    {{ tag }}
                  </Badge>
                </div>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <Button variant="outline" size="sm" @click.stop="handleEditDataset(dataSource)">
              <Edit class="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button variant="outline" size="sm" class="text-destructive hover:text-destructive"
              @click.stop="handleDeleteDataset(dataSource)">
              <Trash2 class="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
        </div>
      </div>
    </div>

  </div>

  <!-- Create Dataset Dialog -->
  <CreateDatasetDialogSimple v-model:open="showCreateDataSourceDialog" :dataset="editingDataset"
    @dataset-created="handleDatasetCreated" @dataset-updated="handleDatasetUpdated"
    @update:open="!$event && handleDialogClose()" />

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
          <div class="bg-destructive/10 border border-destructive/20 rounded-md p-4">
            <div class="flex items-start gap-3">
              <div class="text-xl">⚠️</div>
              <div class="flex-1">
                <p class="text-destructive font-semibold body-sm mb-2">
                  This dataset has {{ datasetToDelete.endpointCount }} dependent endpoint{{
                    datasetToDelete.endpointCount !== 1 ? 's' : ''
                  }}
                  that will be deleted:
                </p>
                <p class="text-destructive/80 body-sm mb-3">Check each endpoint to confirm deletion</p>
                <div class="space-y-2">
                  <div v-for="endpointName in getEndpointNamesForDataset(datasetToDelete.id)" :key="endpointName"
                    class="flex items-center gap-3 p-2.5 bg-background rounded border border-destructive/20">
                    <input type="checkbox" :id="`endpoint-${endpointName}`"
                      :checked="checkedEndpoints.includes(endpointName)" @change="() => toggleEndpoint(endpointName)"
                      class="w-4 h-4 text-destructive bg-background border-destructive/40 rounded focus:ring-destructive/50 focus:ring-2" />
                    <label :for="`endpoint-${endpointName}`"
                      class="flex-1 cursor-pointer flex items-center justify-between">
                      <span class="body-sm font-medium text-foreground">
                        {{ endpointName }}
                      </span>
                      <span class="body-sm text-destructive"> Will be deleted </span>
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
        <Button variant="destructive" @click="confirmDeleteDataset" :disabled="!allEndpointsChecked || isDeleting">
          {{
            isDeleting
              ? 'Deleting...'
              : datasetToDelete && datasetToDelete.endpointCount && datasetToDelete.endpointCount > 0
                ? `Delete Dataset & ${datasetToDelete.endpointCount} Endpoint${datasetToDelete.endpointCount !== 1 ? 's' : ''}`
                : 'Delete Dataset'
          }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Database, Plus, Edit, Trash2, Link } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import CreateDatasetDialogSimple from '@/components/CreateDatasetDialogSimple.vue'
import { useDatasets } from '@/composables/useDatasets'
import { toast } from 'vue-sonner'

interface DataSource {
  id: string
  name: string
  type: string
  description: string
  tags: string[]
  status: 'running' | 'stopped'
  endpointCount: number
  watchedPaths?: string[]
  isCustom?: boolean
}


const router = useRouter()

// Use datasets composable
const { datasets, loading, error, loadDatasets, deleteDataset, refreshDatasets, transformDataset } = useDatasets()

// Transform API datasets to match component interface
const dataSources = computed(() => {
  return datasets.value.map(transformDataset)
})

const showCreateDataSourceDialog = ref(false)
const searchQuery = ref('')
const editingDataset = ref<DataSource | null>(null)
const showDeleteDialog = ref(false)
const datasetToDelete = ref<DataSource | null>(null)
const checkedEndpoints = ref<string[]>([])
const isDeleting = ref(false)

// Function to get endpoint names connected to a dataset
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const getEndpointNamesForDataset = (datasetId: string): string[] => {
  // TODO: Replace with actual endpoint API call when endpoints are integrated
  return []
}

// Load datasets on mount
onMounted(() => {
  loadDatasets()
})

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


    return true
  })
})

const handleDatasetCreated = () => {
  // Refresh the dataset list after creation
  refreshDatasets()
}

const handleEditDataset = (dataset: DataSource) => {
  editingDataset.value = dataset
  showCreateDataSourceDialog.value = true
}

const handleDatasetUpdated = () => {
  // Refresh the dataset list after update
  refreshDatasets()
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

const confirmDeleteDataset = async () => {
  if (datasetToDelete.value && !isDeleting.value) {
    isDeleting.value = true
    const success = await deleteDataset(datasetToDelete.value.name)
    if (success) {
      toast.success(`Dataset "${datasetToDelete.value.name}" deleted successfully`)
      showDeleteDialog.value = false
      datasetToDelete.value = null
      checkedEndpoints.value = []
    } else {
      toast.error(error.value || 'Failed to delete dataset')
    }
    isDeleting.value = false
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

// Get preview paths for dataset card
const getPathsPreview = (dataSource: DataSource) => {
  if (dataSource.isCustom) {
    return {
      isCustom: true,
      paths: [],
      hasMore: false,
      totalCount: 0,
    }
  }

  if (!dataSource.watchedPaths || dataSource.watchedPaths.length === 0) {
    return {
      isCustom: false,
      paths: [],
      hasMore: false,
      totalCount: 0,
    }
  }

  // Show first 3 paths with "..." if there are more
  const pathsToShow = dataSource.watchedPaths.slice(0, 3)
  const hasMore = dataSource.watchedPaths.length > 3

  return {
    isCustom: false,
    paths: pathsToShow,
    hasMore,
    totalCount: dataSource.watchedPaths.length,
  }
}
</script>
