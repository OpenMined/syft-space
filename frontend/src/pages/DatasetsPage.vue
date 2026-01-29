<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-10">
      <div class="flex items-center gap-3 mb-3">
        <Database class="h-6 w-6 text-primary" />
        <h1 class="heading-3">Your Datasets</h1>
      </div>
      <p class="body-lg text-muted-foreground md:max-w-[60%]">
        Data that lives on your machine and works for you. Use endpoints to make it queryable by
        others, on your terms.
      </p>
    </div>

    <!-- Actions Bar -->
    <div class="flex items-center justify-between mb-8">
      <div class="relative w-64">
        <Search
          class="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-muted-foreground"
        />
        <Input
          v-model="searchQuery"
          placeholder="Search datasets..."
          class="pl-10 pr-4 py-2.5 w-full"
        />
      </div>
      <Button @click="showCreateDataSourceDialog = true">
        <Plus class="h-4 w-4 mr-2" />
        Add Dataset
      </Button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="space-y-5">
      <div
        v-for="i in 3"
        :key="`skeleton-${i}`"
        class="bg-card border border-border rounded-xl p-6 animate-pulse"
      >
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
      <div
        v-for="dataSource in filteredDataSources"
        :key="dataSource.id"
        class="bg-card border border-border rounded-xl p-6 hover:shadow-lg transition-all cursor-pointer"
        @click="navigateToDetail(dataSource.name)"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-start gap-4">
              <div
                :class="[
                  'p-3.5 rounded-xl',
                  dataSource.type === 'weaviate'
                    ? 'bg-primary/10'
                    : dataSource.type === 'qdrant'
                      ? 'bg-primary/10'
                      : 'bg-primary/10',
                ]"
              >
                <Database class="h-6 w-6 text-foreground/60" />
              </div>
              <div class="flex-1">
                <div class="flex items-center gap-3 mb-2">
                  <h3 class="heading-4 text-foreground">{{ dataSource.name }}</h3>
                  <Badge
                    variant="outline"
                    :class="
                      dataSource.status === 'running'
                        ? 'bg-primary/10 text-primary border border-primary/20'
                        : 'bg-muted text-muted-foreground border-border'
                    "
                    class="body-sm px-2.5 py-1 rounded-md"
                  >
                    <div
                      :class="
                        dataSource.status === 'running'
                          ? 'w-2 h-2 bg-primary rounded-full mr-1'
                          : 'w-2 h-2 bg-muted-foreground rounded-full mr-1'
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
                              ? 'bg-primary/10 text-primary border border-primary/20 cursor-help'
                              : 'bg-muted text-muted-foreground border border-border'
                          "
                          class="body-sm px-2.5 py-1 rounded-md"
                        >
                          <Link
                            :class="
                              dataSource.endpointCount > 0
                                ? 'w-3.5 h-3.5 mr-1.5'
                                : 'w-3.5 h-3.5 mr-1.5 opacity-40'
                            "
                          />
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
                            <li
                              v-for="endpointName in getEndpointNamesForDataset(dataSource.id)"
                              :key="endpointName"
                              class="body-sm"
                            >
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
                <div v-if="!dataSource.isCustom" class="mb-4 space-y-2 pl-2">
                  <div
                    v-if="!dataSource.watchedPaths || dataSource.watchedPaths.length === 0"
                    class="body-sm text-muted-foreground"
                  >
                    📂 <span class="italic">No paths configured</span>
                  </div>

                  <div v-else class="space-y-1">
                    <div class="body-sm text-muted-foreground flex items-center gap-2">
                      📂 <span class="font-medium">Files & Folders:</span>
                    </div>
                    <div class="ml-6 space-y-1 py-1">
                      <div
                        v-for="path in getPathsPreview(dataSource).paths"
                        :key="path"
                        class="body-sm font-mono text-muted-foreground opacity-75"
                      >
                        {{ path }}
                      </div>
                      <div
                        v-if="getPathsPreview(dataSource).hasMore"
                        class="body-sm text-muted-foreground opacity-60 italic"
                      >
                        +{{ getPathsPreview(dataSource).totalCount - 3 }} more...
                      </div>
                    </div>
                  </div>
                </div>

                <div class="flex gap-2">
                  <Badge
                    v-for="tag in dataSource.tags"
                    :key="tag"
                    variant="outline"
                    class="body-sm"
                  >
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
            <Button
              variant="outline"
              size="sm"
              class="text-destructive hover:text-destructive"
              @click.stop="handleDeleteDataset(dataSource)"
            >
              <Trash2 class="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Create Dataset Dialog -->
  <CreateDatasetDialogSimple
    v-model:open="showCreateDataSourceDialog"
    :dataset="editingDataset"
    @dataset-created="handleDatasetCreated"
    @dataset-updated="handleDatasetUpdated"
    @update:open="!$event && handleDialogClose()"
  />

  <!-- Delete Confirmation Dialog -->
  <DeleteConfirmationDialog
    v-model:open="showDeleteDialog"
    item-type="Dataset"
    :item-name="datasetToDelete?.name || ''"
    :dependencies="getEndpointNamesForDataset(datasetToDelete?.id || '')"
    dependency-type="endpoint"
    :is-deleting="isDeleting"
    @confirm="confirmDeleteDataset"
    @cancel="cancelDeleteDataset"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Database, Plus, Edit, Trash2, Link, Search } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import CreateDatasetDialogSimple from '@/components/CreateDatasetDialogSimple.vue'
import DeleteConfirmationDialog from '@/components/DeleteConfirmationDialog.vue'
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
  configuration?: Record<string, unknown>
  connected_endpoints: Array<{ id: string; name: string; slug: string }>
}

const router = useRouter()

// Use datasets composable
const {
  datasets,
  loading,
  error,
  loadDatasets,
  getDataset,
  deleteDataset,
  refreshDatasets,
  transformDataset,
} = useDatasets()

// Transform API datasets to match component interface
const dataSources = computed(() => {
  return datasets.value.map(transformDataset)
})

const showCreateDataSourceDialog = ref(false)
const searchQuery = ref('')
const editingDataset = ref<{
  id: string
  name: string
  summary: string
  tags: string[]
  filePaths: Array<{ path: string; description: string }>
} | null>(null)
const showDeleteDialog = ref(false)
const datasetToDelete = ref<DataSource | null>(null)
const isDeleting = ref(false)

// Function to get endpoint names connected to a dataset
const getEndpointNamesForDataset = (datasetId: string): string[] => {
  const dataset = dataSources.value.find((ds) => ds.id === datasetId)
  if (!dataset || !dataset.connected_endpoints) return []

  return dataset.connected_endpoints.map((endpoint) => endpoint.name)
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

const handleEditDataset = async (dataset: DataSource) => {
  try {
    const fullDataset = await getDataset(dataset.name)
    if (fullDataset) {
      editingDataset.value = {
        id: fullDataset.id,
        name: fullDataset.name,
        summary: fullDataset.summary,
        tags: fullDataset.tags
          ? fullDataset.tags
              .split(',')
              .map((tag) => tag.trim())
              .filter(Boolean)
          : [],
        filePaths: [], // Not used in edit mode anymore
      }
      showCreateDataSourceDialog.value = true
    } else {
      toast.error('Failed to load dataset details for editing')
    }
  } catch {
    toast.error('Failed to load dataset details')
  }
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
    } else {
      toast.error(error.value || 'Failed to delete dataset')
    }
    isDeleting.value = false
  }
}

const cancelDeleteDataset = () => {
  showDeleteDialog.value = false
  datasetToDelete.value = null
}

// Navigate to dataset detail page
const navigateToDetail = (datasetSlug: string) => {
  router.push(`/datasets/${datasetSlug}`)
}

// Get preview paths for dataset card
const getPathsPreview = (dataSource: DataSource) => {
  if (!dataSource.watchedPaths || dataSource.watchedPaths.length === 0) {
    return {
      paths: [],
      hasMore: false,
      totalCount: 0,
    }
  }

  // Show first 3 paths with "..." if there are more
  const pathsToShow = dataSource.watchedPaths.slice(0, 3)
  const hasMore = dataSource.watchedPaths.length > 3

  return {
    paths: pathsToShow,
    hasMore,
    totalCount: dataSource.watchedPaths.length,
  }
}
</script>
