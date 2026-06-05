<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Breadcrumb Navigation -->
    <nav class="flex mb-12" aria-label="Breadcrumb">
      <ol class="flex items-center space-x-3">
        <li>
          <router-link
            to="/datasets"
            class="text-muted-foreground hover:text-foreground body-sm font-medium flex items-center transition-colors"
          >
            <Database class="h-4 w-4 mr-2" />
            Datasets
          </router-link>
        </li>
        <li class="flex items-center">
          <ChevronRight class="h-4 w-4 text-muted-foreground mx-3" />
          <span class="text-foreground body-sm font-medium">{{
            loading ? 'Loading...' : dataset?.name || 'Dataset not found'
          }}</span>
        </li>
      </ol>
    </nav>

    <!-- Error State -->
    <div
      v-if="error"
      class="bg-destructive/10 border border-destructive/20 rounded-2xl p-8 text-center"
    >
      <h3 class="heading-3 text-destructive mb-2">Dataset not found</h3>
      <p class="text-destructive mb-4">
        The dataset you're looking for doesn't exist or has been deleted.
      </p>
      <Button @click="$router.push('/datasets')" variant="outline"> Back to Datasets </Button>
    </div>

    <!-- Loading State -->
    <div v-else-if="loading" class="space-y-6 animate-pulse">
      <!-- Header Skeleton -->
      <div class="bg-card/60 backdrop-blur-sm border border-border rounded-3xl p-8 mb-8">
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-6">
            <div class="w-16 h-16 bg-muted rounded-2xl"></div>
            <div class="space-y-3">
              <div class="h-8 bg-muted rounded w-48"></div>
              <div class="h-5 bg-muted rounded w-96"></div>
              <div class="flex gap-3">
                <div class="h-8 bg-muted rounded-full w-24"></div>
                <div class="h-8 bg-muted rounded-full w-20"></div>
                <div class="h-8 bg-muted rounded-full w-16"></div>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <div class="h-10 bg-muted rounded w-20"></div>
            <div class="h-10 bg-muted rounded w-24"></div>
          </div>
        </div>
      </div>

      <!-- Tabs Skeleton -->
      <div class="h-10 bg-muted rounded-md w-full"></div>

      <!-- Summary Grid Skeleton -->
      <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
        <div class="grid grid-cols-2 md:grid-cols-6 gap-8">
          <div v-for="i in 6" :key="`summary-${i}`" class="text-center space-y-2">
            <div class="h-4 bg-muted rounded w-16 mx-auto"></div>
            <div class="h-5 bg-muted rounded w-20 mx-auto"></div>
          </div>
        </div>
      </div>

      <!-- Configuration Skeleton -->
      <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
        <div class="h-6 bg-muted rounded w-32 mb-8"></div>
        <div class="space-y-6">
          <div class="flex justify-between items-center py-2 border-b border-border">
            <div class="h-4 bg-muted rounded w-24"></div>
            <div class="h-4 bg-muted rounded w-32"></div>
          </div>
          <div class="flex justify-between items-center py-2">
            <div class="h-4 bg-muted rounded w-32"></div>
            <div class="h-4 bg-muted rounded w-24"></div>
          </div>
        </div>
      </div>

      <!-- Connected Endpoints Skeleton -->
      <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
        <div class="h-6 bg-muted rounded w-48 mb-4"></div>
        <div class="space-y-4">
          <div
            v-for="i in 2"
            :key="`endpoint-${i}`"
            class="flex items-center gap-4 py-6 px-6 bg-muted/50 border border-border rounded-2xl"
          >
            <div class="w-11 h-11 bg-muted rounded-xl"></div>
            <div class="flex-1 space-y-2">
              <div class="h-4 bg-muted rounded w-32"></div>
              <div class="h-3 bg-muted rounded w-48"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Dataset Details -->
    <div v-else-if="dataset" class="space-y-6">
      <!-- Header -->
      <div class="bg-card/60 backdrop-blur-sm border border-border rounded-3xl p-8 mb-8">
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-6">
            <div
              :class="[
                'p-4 rounded-2xl shadow-sm',
                dataset.dtype === 'weaviate'
                  ? 'bg-primary/10 border border-border'
                  : dataset.dtype === 'qdrant'
                    ? 'bg-primary/10 border border-border'
                    : 'bg-primary/10 border border-border',
              ]"
            >
              <IntegrationIcon :name="datasetTypeInfo?.icon || dataset.dtype" class="h-8 w-8" />
            </div>
            <div>
              <h1 class="heading-2 mb-2">{{ dataset.name }}</h1>
              <p class="body-lg text-muted-foreground mb-4">{{ dataset.summary }}</p>
              <div class="flex flex-wrap items-center gap-3">
                <Badge
                  variant="outline"
                  :class="
                    dataset.status === 'running'
                      ? 'bg-primary/10 text-primary border border-primary/20 px-3 py-1.5 rounded-full'
                      : 'bg-muted text-muted-foreground border border-border px-3 py-1.5 rounded-full'
                  "
                >
                  <div
                    :class="
                      dataset.status === 'running'
                        ? 'w-2 h-2 bg-primary rounded-full mr-2'
                        : 'w-2 h-2 bg-muted-foreground rounded-full mr-2'
                    "
                  ></div>
                  {{ dataset.status === 'running' ? 'Running' : 'Stopped' }}
                </Badge>
                <Badge
                  variant="outline"
                  class="bg-muted text-muted-foreground border border-border px-3 py-1.5 rounded-full"
                >
                  {{ dataset.dtype }}
                </Badge>
                <Badge
                  v-for="tag in dataset.tags"
                  :key="`tag-${tag}`"
                  variant="outline"
                  class="bg-muted text-muted-foreground border border-border px-3 py-1.5 rounded-full"
                >
                  {{ tag }}
                </Badge>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <Button variant="outline" @click="editDataset">
              <Edit class="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button
              variant="outline"
              class="text-destructive hover:text-destructive border-destructive/50 hover:border-destructive"
              @click="deleteDataset"
            >
              <Trash2 class="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
        </div>
      </div>

      <!-- Tabs Navigation -->
      <Tabs default-value="overview" class="space-y-4">
        <TabsList
          class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-2"
        >
          <TabsTrigger value="overview" class="flex items-center gap-2">
            <Database class="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="analytics" class="flex items-center gap-2">
            <BarChart3 class="h-4 w-4" />
            Analytics
          </TabsTrigger>
        </TabsList>

        <!-- Overview Tab Content -->
        <TabsContent value="overview" class="space-y-6">
          <!-- Dataset Summary -->
          <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
            <div class="grid grid-cols-2 md:grid-cols-6 gap-8">
              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Type</p>
                <p class="body-sm font-medium text-foreground">
                  {{
                    datasetTypeInfo?.name ||
                    dataset.dtype.charAt(0).toUpperCase() + dataset.dtype.slice(1)
                  }}
                </p>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Status</p>
                <div class="flex items-center justify-center gap-2">
                  <div :class="['w-2.5 h-2.5 rounded-full', getDatasetStatus().color]"></div>
                  <p class="body-sm font-medium text-foreground">{{ getDatasetStatus().text }}</p>
                </div>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Endpoints</p>
                <p class="body-sm font-medium text-foreground">{{ dataset.endpointCount }}</p>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Files</p>
                <p class="body-sm font-medium text-primary">
                  {{ getTotalFiles() }}
                </p>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Ingested</p>
                <p class="body-sm font-medium text-primary">
                  {{ getIngestedFiles() }}
                </p>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Created</p>
                <p class="body-sm font-medium text-foreground">
                  {{ formatDate(dataset.created_at) }}
                </p>
              </div>
            </div>
          </div>

          <!-- File Watching Status (only for self-managed) -->
          <div
            v-if="getDatasetManagement() === 'Self-managed'"
            class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6"
          >
            <div class="flex items-center justify-between mb-8">
              <div class="flex items-center gap-4">
                <h2 class="heading-3">Watched Paths</h2>
                <div class="flex items-center gap-2">
                  <div
                    :class="[
                      'w-2 h-2 rounded-full',
                      ingestionStatus?.is_watching ? 'bg-primary' : 'bg-muted',
                    ]"
                  ></div>
                  <span class="body-sm text-muted-foreground">
                    {{ ingestionStatus?.is_watching ? 'Watching' : 'Not watching' }}
                  </span>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <Button
                  v-if="ingestionStatus?.failed && ingestionStatus.failed > 0"
                  variant="outline"
                  size="sm"
                  @click="retryFailedJobs"
                  :disabled="isRetryingJobs"
                >
                  <RotateCcw class="h-4 w-4 mr-2" :class="{ 'animate-spin': isRetryingJobs }" />
                  Retry Failed ({{ ingestionStatus.failed }})
                </Button>
              </div>
            </div>
            <div v-if="getWatchedPaths().length > 0">
              <!-- Watched Paths Overview -->
              <div class="space-y-4 mb-8">
                <div
                  v-for="path in getWatchedPaths()"
                  :key="path.id"
                  class="flex items-center justify-between py-6 px-6 bg-muted/50 border border-border rounded-2xl hover:bg-muted/80 transition-all"
                >
                  <div class="flex items-center gap-4">
                    <div
                      :class="[
                        'w-3 h-3 rounded-full',
                        path.status === 'watching' ? 'bg-primary' : 'bg-muted',
                      ]"
                    ></div>
                    <div class="flex-1">
                      <p class="body-sm font-medium text-foreground">{{ path.path }}</p>
                      <p class="body-sm text-muted-foreground mt-1">
                        {{ path.description }}
                      </p>
                    </div>
                  </div>
                  <div class="flex items-center gap-4">
                    <Badge
                      :variant="path.status === 'watching' ? 'default' : 'outline'"
                      class="capitalize px-3 py-1.5 rounded-full border-0"
                    >
                      {{ path.status === 'watching' ? 'Watching' : 'Not Watching' }}
                    </Badge>
                  </div>
                </div>
              </div>
            </div>

            <!-- No Watched Paths Message -->
            <div v-else class="text-center py-16">
              <div
                class="mx-auto mb-4 h-12 w-12 rounded-full bg-muted flex items-center justify-center"
              >
                <Database class="h-6 w-6 text-muted-foreground" />
              </div>
              <p class="text-muted-foreground body-sm mb-4">No watched paths configured</p>
              <p class="text-muted-foreground body-sm">
                Configure file paths in dataset settings to enable file watching
              </p>
            </div>

            <div class="mt-8">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-4 flex-wrap">
                  <span
                    v-for="status in ['completed', 'in_progress', 'pending', 'failed', 'cancelled']"
                    :key="status"
                    class="flex items-center gap-2.5 body-sm font-medium text-muted-foreground px-3 py-2 rounded-lg"
                  >
                    <div :class="getStatusDotClass(status)"></div>
                    {{ getStatusLabel(status) }} ({{ getStatusCount(status) }})
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Configuration Settings -->
          <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between mb-8">
              <h2 class="heading-3">Configuration</h2>
            </div>

            <!-- Basic Settings -->
            <div class="space-y-3">
              <div class="flex justify-between items-center py-2 border-b border-border">
                <span class="body-sm text-muted-foreground">Index Name</span>
                <span class="body-sm font-medium text-foreground">{{
                  getConfigValue('indexName') || getConfigValue('collectionName') || dataset.name
                }}</span>
              </div>
              <div
                class="flex justify-between items-center py-2 border-b border-border last:border-b-0"
              >
                <span class="body-sm text-muted-foreground">Connection Status</span>
                <div class="flex items-center gap-3">
                  <div
                    :class="[
                      'w-2.5 h-2.5 rounded-full',
                      healthStatus?.status === 'healthy' ? 'bg-primary' : 'bg-destructive',
                    ]"
                  ></div>
                  <span
                    :class="[
                      'body-sm font-medium',
                      healthStatus?.status === 'healthy' ? 'text-primary' : 'text-destructive',
                    ]"
                  >
                    {{ healthStatus?.status === 'healthy' ? 'Connected' : 'Disconnected' }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Dynamic Configuration Display -->
            <div v-if="showAdvancedConfig && dataset?.configuration" class="mt-6">
              <div class="space-y-6">
                <h3 class="body-sm font-semibold text-foreground mb-4">Advanced Settings</h3>
                <div class="space-y-3">
                  <!-- Dynamically render configuration properties -->
                  <div
                    v-for="(value, key) in getDisplayableConfig()"
                    :key="key"
                    class="flex justify-between items-center py-2 border-b border-border last:border-b-0"
                  >
                    <span class="body-sm text-muted-foreground">{{ formatConfigKey(key) }}</span>
                    <span class="body-sm font-medium text-foreground">{{
                      formatConfigValue(key, value)
                    }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Show Advanced Button (Bottom Right) -->
            <div class="flex justify-end mt-6">
              <Button variant="ghost" size="sm" @click="showAdvancedConfig = !showAdvancedConfig">
                <ChevronDown
                  class="h-4 w-4 mr-2 transition-transform"
                  :class="{ 'rotate-180': showAdvancedConfig }"
                />
                {{ showAdvancedConfig ? 'Hide' : 'Show' }} Advanced
              </Button>
            </div>
          </div>

          <!-- Connected Endpoints -->
          <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
            <h2 class="heading-3 mb-4">Connected Endpoints ({{ connectedEndpoints.length }})</h2>
            <div v-if="connectedEndpoints.length > 0" class="space-y-4">
              <div
                v-for="endpoint in connectedEndpoints"
                :key="endpoint.id"
                class="flex items-center gap-4 py-6 px-6 bg-muted/50 border border-border rounded-2xl hover:bg-muted/80 transition-all cursor-pointer"
                @click="navigateToEndpoint(endpoint.slug)"
              >
                <div class="p-3 bg-primary/10 rounded-xl">
                  <Globe class="h-5 w-5 text-primary" />
                </div>
                <div class="flex-1">
                  <h3 class="body-sm font-medium text-foreground">{{ endpoint.name }}</h3>
                  <p class="body-sm text-muted-foreground mt-1">
                    {{ endpoint.slug || 'API endpoint' }}
                  </p>
                </div>
              </div>
            </div>
            <div v-else class="text-center py-16">
              <Globe class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p class="text-muted-foreground body-sm mb-4">
                No endpoints connected to this dataset
              </p>
              <Button size="sm" @click="$router.push({ name: 'create-data-endpoint' })">
                <Plus class="h-4 w-4 mr-2" />
                Create Endpoint
              </Button>
            </div>
          </div>
        </TabsContent>

        <!-- Analytics Tab Content -->
        <TabsContent value="analytics" class="space-y-6">
          <!-- Watched Files (only for self-managed) -->
          <div
            v-if="getDatasetManagement() === 'Self-managed' && getWatchedPaths().length > 0"
            class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6"
          >
            <div class="flex items-center justify-between mb-6">
              <h2 class="heading-3">Watched Files</h2>
              <Button variant="outline" size="sm" @click="refreshWatchedPaths">
                <RefreshCw class="h-4 w-4 mr-2" :class="{ 'animate-spin': isRefreshingPaths }" />
                Refresh
              </Button>
            </div>

            <!-- Status Filter Tabs -->
            <div class="flex items-center justify-between mb-6 pb-4 border-b border-border">
              <div class="flex items-center gap-4 flex-wrap">
                <span
                  v-for="status in ['completed', 'in_progress', 'pending', 'failed', 'cancelled']"
                  :key="status"
                  :class="getStatusTagClass(status)"
                  @click="onJobStatusChange(status)"
                >
                  <div :class="getStatusDotClass(status)"></div>
                  {{ getStatusLabel(status) }} ({{ getStatusCount(status) }})
                </span>
              </div>
              <div class="body-sm text-muted-foreground">
                {{ getPageInfo().start }}-{{ getPageInfo().end }} of
                {{ getStatusCount(selectedJobStatus) }} files
              </div>
            </div>

            <!-- Loading State -->
            <div v-if="isLoadingFiles" class="flex items-center justify-center py-8">
              <div class="flex items-center gap-2 text-muted-foreground">
                <RefreshCw class="h-4 w-4 animate-spin" />
                <span class="body-sm">Loading files...</span>
              </div>
            </div>

            <!-- Files List -->
            <div v-else-if="getFilteredJobs().length > 0" class="space-y-2">
              <div
                v-for="job in getFilteredJobs()"
                :key="job.id"
                class="flex items-center justify-between py-3 px-4 bg-background border border-border rounded-lg hover:bg-muted/50 transition-all"
              >
                <div class="flex items-center gap-3 flex-1 min-w-0">
                  <File class="h-4 w-4 text-muted-foreground flex-shrink-0" />
                  <div class="flex-1 min-w-0">
                    <p class="body-sm font-medium text-foreground truncate">
                      {{ job.external_id.split('/').pop() || job.external_id }}
                    </p>
                    <div class="flex items-center gap-4 mt-1">
                      <div class="flex items-center gap-1">
                        <Clock class="h-3 w-3 text-muted-foreground" />
                        <p class="body-sm text-muted-foreground">
                          {{ formatTimeAgo(job.created_at) }}
                        </p>
                      </div>
                      <p v-if="job.retry_count > 0" class="body-sm text-muted-foreground">
                        {{ job.retry_count }} retries
                      </p>
                    </div>
                    <p v-if="job.error_message" class="body-sm text-destructive mt-1 truncate">
                      {{ job.error_message }}
                    </p>
                  </div>
                </div>
                <div class="flex items-center gap-3">
                  <Badge :variant="getJobStatusBadgeVariant(job.status)" class="capitalize">
                    {{ job.status.replace('_', ' ') }}
                  </Badge>
                </div>
              </div>

              <!-- Pagination Controls -->
              <div
                v-if="totalPages > 1"
                class="flex items-center justify-between pt-4 border-t border-border"
              >
                <div class="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    :disabled="!canGoPrevious"
                    @click="onPageChange(currentPage - 1)"
                  >
                    <ChevronLeft class="h-4 w-4" />
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    :disabled="!canGoNext"
                    @click="onPageChange(currentPage + 1)"
                  >
                    Next
                    <ChevronRightIcon class="h-4 w-4" />
                  </Button>
                </div>
                <div class="body-sm text-muted-foreground">
                  Page {{ currentPage }} of {{ totalPages }}
                </div>
              </div>
            </div>

            <!-- Empty State -->
            <div v-else class="text-center py-8">
              <File class="h-8 w-8 text-muted-foreground mx-auto mb-2" />
              <p class="text-muted-foreground body-sm">
                No {{ getStatusLabel(selectedJobStatus).toLowerCase() }} files found
              </p>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  </div>

  <!-- Create Dataset Dialog -->
  <CreateDatasetDialogSimple
    v-model:open="showEditDialog"
    :dataset="editingDataset"
    @dataset-updated="handleDatasetUpdated"
    @update:open="!$event && handleDialogClose()"
  />

  <!-- Delete Confirmation Dialog -->
  <DeleteConfirmationDialog
    v-model:open="showDeleteDialog"
    item-type="Dataset"
    :item-name="dataset?.name || ''"
    :dependencies="getEndpointNamesForDataset()"
    dependency-type="endpoint"
    @confirm="confirmDelete"
    @cancel="cancelDelete"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Database,
  ChevronRight,
  Edit,
  Trash2,
  Globe,
  Plus,
  BarChart3,
  RefreshCw,
  ChevronDown,
  RotateCcw,
  File,
  Clock,
  ChevronLeft,
  ChevronRight as ChevronRightIcon,
} from 'lucide-vue-next'
import DeleteConfirmationDialog from '@/components/DeleteConfirmationDialog.vue'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import CreateDatasetDialogSimple from '@/components/CreateDatasetDialogSimple.vue'
import { datasetsApi } from '@/api/endpoints/datasets'
import { ingestionApi } from '@/api/endpoints/ingestion'
import type {
  DatasetResponse,
  IngestionStatusResponse,
  IngestionJobListResponse,
  DatasetTypeInfoResponse,
} from '@/api/types'

// Interface for tag parsing
interface ParsedDataset extends Omit<DatasetResponse, 'tags'> {
  tags: string[]
  status: 'running' | 'stopped'
  endpointCount: number
}

const route = useRoute()
const router = useRouter()

const error = ref(false)
const loading = ref(true)
const dataset = ref<ParsedDataset | null>(null)
const healthStatus = ref<{ status: string; message: string } | null>(null)
const datasetTypeInfo = ref<DatasetTypeInfoResponse | null>(null)
const showEditDialog = ref(false)
const editingDataset = ref<{
  id: string
  name: string
  summary: string
  tags: string[]
  filePaths: Array<{ path: string; description: string }>
} | null>(null)
const showDeleteDialog = ref(false)
const isRefreshingPaths = ref(false)
const ingestionStatus = ref<IngestionStatusResponse | null>(null)
const ingestionJobs = ref<IngestionJobListResponse | null>(null)
const selectedJobStatus = ref<string>('completed')
const isRetryingJobs = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const isLoadingFiles = ref(false)
const showAdvancedConfig = ref(false)

const connectedEndpoints = computed(() => {
  if (!dataset.value) return []
  return dataset.value.connected_endpoints
})

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

const getDatasetStatus = () => {
  if (!healthStatus.value) {
    return { text: 'Unknown', color: 'bg-muted' }
  }

  // Map health status to display format
  switch (healthStatus.value.status) {
    case 'healthy':
      return { text: 'Healthy', color: 'bg-primary' }
    case 'unhealthy':
      return { text: 'Unhealthy', color: 'bg-destructive' }
    case 'degraded':
      return { text: 'Degraded', color: 'bg-yellow-500' }
    default:
      return { text: 'Unknown', color: 'bg-muted' }
  }
}

const getTotalFiles = () => {
  if (getDatasetManagement() === 'Self-managed') {
    return ingestionStatus.value?.total_jobs?.toLocaleString() || '0'
  }
  return 'N/A' // External datasets don't track files
}

const getIngestedFiles = () => {
  if (getDatasetManagement() === 'Self-managed') {
    return ingestionStatus.value?.completed?.toLocaleString() || '0'
  }
  return 'N/A' // External datasets don't track ingestion
}

// Function to get endpoint names connected to a dataset
const getEndpointNamesForDataset = (): string[] => {
  if (!dataset.value) return []
  return dataset.value.connected_endpoints.map((endpoint) => endpoint.name)
}

const editDataset = async () => {
  if (!dataset.value) return

  try {
    editingDataset.value = {
      id: dataset.value.id,
      name: dataset.value.name,
      summary: dataset.value.summary,
      tags: dataset.value.tags || [],
      filePaths: [], // Not used in edit mode
    }
    showEditDialog.value = true
  } catch (err) {
    console.error('Failed to prepare dataset for editing:', err)
  }
}

const deleteDataset = () => {
  showDeleteDialog.value = true
}

const loadDataset = async (name: string) => {
  try {
    loading.value = true
    error.value = false

    const [datasetResponse, healthResponse] = await Promise.all([
      datasetsApi.get(name),
      datasetsApi
        .healthcheck(name)
        .catch(() => ({ dataset_type_status: 'unknown', message: 'Health check unavailable' })),
    ])

    // Parse the dataset and convert tags string to array
    const parsedDataset: ParsedDataset = {
      ...datasetResponse,
      tags: datasetResponse.tags ? datasetResponse.tags.split(',').map((tag) => tag.trim()) : [],
      status: datasetResponse.provisioner_state?.status === 'running' ? 'running' : 'stopped',
      endpointCount: datasetResponse.connected_endpoints.length,
    }

    dataset.value = parsedDataset
    healthStatus.value = {
      status: healthResponse.dataset_type_status,
      message: healthResponse.message,
    }

    // Fetch dataset type information
    try {
      const typeInfoResponse = await datasetsApi.getType(datasetResponse.dtype)
      datasetTypeInfo.value = typeInfoResponse
    } catch (typeErr) {
      console.error('Failed to load dataset type info:', typeErr)
      datasetTypeInfo.value = null
    }

    // Load ingestion data if dataset is self-managed
    if (getDatasetManagement() === 'Self-managed') {
      await loadIngestionData(datasetResponse.id)
    }
  } catch (err) {
    console.error('Failed to load dataset:', err)
    error.value = true
  } finally {
    loading.value = false
  }
}

const loadIngestionData = async (datasetId: string) => {
  try {
    isLoadingFiles.value = true
    const offset = (currentPage.value - 1) * pageSize.value

    const [statusResponse, jobsResponse] = await Promise.all([
      ingestionApi.getStatus(datasetId).catch(() => null),
      ingestionApi
        .listJobs(datasetId, selectedJobStatus.value, pageSize.value, offset)
        .catch(() => null),
    ])

    ingestionStatus.value = statusResponse
    ingestionJobs.value = jobsResponse
  } catch (err) {
    console.error('Failed to load ingestion data:', err)
  } finally {
    isLoadingFiles.value = false
  }
}

const handleDatasetUpdated = () => {
  console.log('Dataset updated successfully')
  showEditDialog.value = false
  // In a real app, you might want to refresh the dataset data here
}

const handleDialogClose = () => {
  showEditDialog.value = false
  editingDataset.value = null
}

const confirmDelete = async () => {
  if (dataset.value) {
    try {
      await datasetsApi.delete(dataset.value.name)
      router.push('/datasets')
    } catch (err) {
      console.error('Failed to delete dataset:', err)
      // Could show toast notification here
    }
  }
}

const cancelDelete = () => {
  showDeleteDialog.value = false
}

const navigateToEndpoint = (endpointSlug: string) => {
  router.push({ name: 'endpoint-detail', params: { slug: endpointSlug } })
}

// Dataset management type - check if dataset has file ingestion paths
const getDatasetManagement = () => {
  if (!dataset.value) return 'External'
  const config = dataset.value.configuration as Record<string, unknown>
  // If dataset has filePaths or ingestionPath in config, it's self-managed
  return config?.filePaths || config?.ingestionPath ? 'Self-managed' : 'External'
}

// Get watched paths from dataset configuration
const getWatchedPaths = () => {
  if (getDatasetManagement() !== 'Self-managed' || !dataset.value) {
    return []
  }

  const config = dataset.value.configuration as Record<string, unknown>
  const filePaths = (config?.filePaths as Array<{ path: string; description?: string }>) || []

  return filePaths.map((pathItem) => ({
    id: pathItem.path,
    path: pathItem.path,
    description: pathItem.description || 'Selected folder for ingestion',
    fileCount: ingestionJobs.value?.total || 0,
    status: ingestionStatus.value?.is_watching ? 'watching' : 'not_watching',
  }))
}

// Get filtered ingestion jobs
const getFilteredJobs = () => {
  if (!ingestionJobs.value) return []
  return ingestionJobs.value.jobs
}

const formatTimeAgo = (dateString: string): string => {
  const now = new Date()
  const date = new Date(dateString)
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins} min ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
  return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
}

const refreshWatchedPaths = async () => {
  if (!dataset.value) return

  isRefreshingPaths.value = true
  try {
    await loadIngestionData(dataset.value.id)
  } catch (err) {
    console.error('Failed to refresh ingestion data:', err)
  } finally {
    isRefreshingPaths.value = false
  }
}

const onJobStatusChange = async (newStatus: string) => {
  selectedJobStatus.value = newStatus
  currentPage.value = 1 // Reset to first page when changing filter
  if (dataset.value) {
    await loadIngestionData(dataset.value.id)
  }
}

const onPageChange = async (page: number) => {
  currentPage.value = page
  if (dataset.value) {
    await loadIngestionData(dataset.value.id)
  }
}

const totalPages = computed(() => {
  const totalCount = getStatusCount(selectedJobStatus.value)
  return Math.ceil(totalCount / pageSize.value)
})

const canGoPrevious = computed(() => currentPage.value > 1)
const canGoNext = computed(() => currentPage.value < totalPages.value)

const getPageInfo = () => {
  const start = (currentPage.value - 1) * pageSize.value + 1
  const end = Math.min(currentPage.value * pageSize.value, getStatusCount(selectedJobStatus.value))
  return { start, end }
}

const getStatusTagClass = (status: string) => {
  const isSelected = selectedJobStatus.value === status
  return [
    'flex items-center gap-2.5 body-sm font-medium cursor-pointer transition-all px-3 py-2 rounded-lg',
    isSelected
      ? 'text-foreground bg-muted/80 border border-border'
      : 'text-muted-foreground hover:text-foreground hover:bg-muted/50',
  ]
}

const getStatusDotClass = (status: string) => {
  const statusMap: Record<string, string> = {
    completed: 'bg-primary',
    in_progress: 'bg-secondary',
    pending: 'bg-accent',
    failed: 'bg-destructive',
    cancelled: 'bg-muted',
  }
  return `w-2.5 h-2.5 rounded-full ${statusMap[status] || 'bg-muted'}`
}

const getStatusLabel = (status: string) => {
  const labelMap: Record<string, string> = {
    completed: 'Indexed',
    in_progress: 'Processing',
    pending: 'Queued',
    failed: 'Errored',
    cancelled: 'Cancelled',
  }
  return labelMap[status] || status
}

const getStatusCount = (status: string) => {
  if (status === 'completed') return ingestionStatus.value?.completed || 0
  if (status === 'in_progress') return ingestionStatus.value?.in_progress || 0
  if (status === 'pending') return ingestionStatus.value?.pending || 0
  if (status === 'failed') return ingestionStatus.value?.failed || 0
  if (status === 'cancelled') return ingestionStatus.value?.cancelled || 0
  return 0
}

const retryFailedJobs = async () => {
  if (!dataset.value) return

  isRetryingJobs.value = true
  try {
    await ingestionApi.retry(dataset.value.id)
    await loadIngestionData(dataset.value.id)
  } catch (err) {
    console.error('Failed to retry jobs:', err)
  } finally {
    isRetryingJobs.value = false
  }
}

const getJobStatusBadgeVariant = (status: string) => {
  switch (status) {
    case 'completed':
      return 'default'
    case 'failed':
      return 'destructive'
    case 'in_progress':
      return 'secondary'
    case 'pending':
      return 'outline'
    case 'cancelled':
      return 'outline'
    default:
      return 'outline'
  }
}

// Configuration display helpers
const getConfigValue = (key: string): unknown => {
  if (!dataset.value?.configuration) return null
  const config = dataset.value.configuration as Record<string, unknown>
  return config[key]
}

const getDisplayableConfig = () => {
  if (!dataset.value?.configuration) return {}
  const config = dataset.value.configuration as Record<string, unknown>

  // Filter out complex nested objects and arrays for display
  const displayable: Record<string, unknown> = {}

  Object.entries(config).forEach(([key, value]) => {
    // Skip file paths as they're shown in the watched paths section
    if (key === 'filePaths' || key === 'ingestionPath') return

    // Include primitives and simple arrays
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      displayable[key] = value
    } else if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'string') {
      displayable[key] = value
    } else if (value && typeof value === 'object' && !Array.isArray(value)) {
      // For simple objects, try to display as JSON
      const objKeys = Object.keys(value)
      if (objKeys.length <= 3) {
        displayable[key] = value
      }
    }
  })

  return displayable
}

const formatConfigKey = (key: string): string => {
  // Convert camelCase to Title Case, handling acronyms properly
  return (
    key
      // Add space before capital letters that follow lowercase or digits
      .replace(/([a-z\d])([A-Z])/g, '$1 $2')
      // Add space before capital letters that start a lowercase word (after acronym)
      .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
      // Capitalize first letter
      .replace(/^./, (str) => str.toUpperCase())
      .trim()
  )
}

const formatConfigValue = (key: string, value: unknown): string => {
  if (value === null || value === undefined) return 'N/A'

  // Special formatting for known keys
  if (key === 'url' || key === 'host') {
    return String(value)
  }

  if (key === 'dimensions' || key === 'chunkSize' || key === 'overlap') {
    return `${value}`
  }

  if (typeof value === 'boolean') {
    return value ? 'Enabled' : 'Disabled'
  }

  if (Array.isArray(value)) {
    return value.join(', ')
  }

  if (typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return '[Object]'
    }
  }

  return String(value)
}

onMounted(async () => {
  const datasetName = route.params.slug as string
  await loadDataset(datasetName)
})
</script>
