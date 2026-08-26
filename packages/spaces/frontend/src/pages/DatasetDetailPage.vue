<template>
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Breadcrumb Navigation -->
    <nav class="flex mb-12" aria-label="Breadcrumb">
      <ol class="flex items-center space-x-3">
        <li>
          <router-link
            to="/datasets"
            class="text-muted-foreground hover:text-foreground body-sm font-medium flex items-center transition-colors"
          >
            <Database class="h-4 w-4 mr-2" />
            Data Sources
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
    <div v-else-if="dataset" class="space-y-8">
      <!-- Header -->
      <div class="flex items-start justify-between gap-6 pb-6 border-b border-border/60">
        <div class="flex items-start gap-4 flex-1 min-w-0">
          <div class="p-3 rounded-xl bg-muted/60 border border-border/60 shrink-0">
            <IntegrationIcon :name="datasetTypeInfo?.icon || dataset.dtype" class="h-7 w-7" />
          </div>
          <div class="min-w-0 flex-1">
            <h1 class="heading-2 mb-1.5">{{ dataset.name }}</h1>
            <p class="body-base text-muted-foreground mb-3">{{ dataset.summary }}</p>

            <!-- Inline metadata row -->
            <div class="flex flex-wrap items-center gap-x-3 gap-y-2 mb-3">
              <Badge
                variant="outline"
                :class="
                  dataset.status === 'running'
                    ? 'bg-primary/10 text-primary border-primary/20 px-2.5 py-0.5 rounded-md'
                    : 'bg-muted text-muted-foreground border-border px-2.5 py-0.5 rounded-md'
                "
              >
                <span
                  :class="[
                    'w-1.5 h-1.5 rounded-full mr-1.5',
                    dataset.status === 'running' ? 'bg-primary' : 'bg-muted-foreground',
                  ]"
                ></span>
                {{ dataset.status === 'running' ? 'Running' : 'Stopped' }}
              </Badge>
              <span class="text-xs text-muted-foreground">·</span>
              <span class="body-sm text-muted-foreground font-mono">{{ dataset.dtype }}</span>
              <template v-if="getDatasetManagement() === 'Self-managed'">
                <span class="text-xs text-muted-foreground">·</span>
                <span class="body-sm font-medium text-foreground"
                  >{{ getIngestedFiles() }} files indexed</span
                >
              </template>
              <span class="text-xs text-muted-foreground">·</span>
              <span class="body-sm font-medium text-foreground"
                >{{ dataset.endpointCount }} API{{ dataset.endpointCount !== 1 ? 's' : '' }}</span
              >
            </div>

            <!-- Tag chips -->
            <div v-if="dataset.tags.length > 0" class="flex flex-wrap gap-1.5">
              <Badge
                v-for="tag in dataset.tags"
                :key="`tag-${tag}`"
                variant="outline"
                class="bg-background text-muted-foreground border-border/60 px-2 py-0.5 rounded-md text-[11px] font-normal"
              >
                {{ tag }}
              </Badge>
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <Button variant="outline" size="sm" @click="editDataset">
            <Edit class="h-3.5 w-3.5 mr-2" />
            Edit
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <Button variant="outline" size="sm" class="px-2">
                <MoreVertical class="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" class="w-40">
              <DropdownMenuItem
                class="text-destructive focus:text-destructive"
                @click="deleteDataset"
              >
                <Trash2 class="h-4 w-4 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <!-- Tabs Navigation -->
      <Tabs default-value="overview" class="space-y-6">
        <TabsList
          class="h-auto items-end justify-start gap-6 rounded-none bg-transparent p-0 border-b border-border w-full"
        >
          <TabsTrigger
            value="overview"
            class="-mb-px flex-none justify-start inline-flex items-center gap-2 rounded-none border-0 border-b-2 border-transparent bg-transparent px-1 pb-3 pt-2 h-auto body-sm font-medium text-muted-foreground hover:text-foreground data-[state=active]:border-b-primary data-[state=active]:bg-transparent data-[state=active]:text-primary data-[state=active]:shadow-none dark:data-[state=active]:border-b-primary dark:data-[state=active]:bg-transparent dark:data-[state=active]:text-primary"
          >
            <Database class="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger
            value="files"
            class="-mb-px flex-none justify-start inline-flex items-center gap-2 rounded-none border-0 border-b-2 border-transparent bg-transparent px-1 pb-3 pt-2 h-auto body-sm font-medium text-muted-foreground hover:text-foreground data-[state=active]:border-b-primary data-[state=active]:bg-transparent data-[state=active]:text-primary data-[state=active]:shadow-none dark:data-[state=active]:border-b-primary dark:data-[state=active]:bg-transparent dark:data-[state=active]:text-primary"
          >
            <FileText class="h-4 w-4" />
            Files
            <Badge
              v-if="getDatasetManagement() === 'Self-managed'"
              variant="secondary"
              class="ml-1 h-[18px] min-w-[20px] justify-center px-1.5 text-[11px] font-semibold bg-primary/15 text-primary border-0 rounded-sm"
            >
              {{ ingestionStatus?.total_jobs ?? 0 }}
            </Badge>
          </TabsTrigger>
        </TabsList>

        <!-- Overview Tab Content -->
        <TabsContent value="overview" class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- Selected items (source-agnostic: file paths, WordPress posts, ...) -->
          <div
            v-if="getDatasetManagement() === 'Self-managed'"
            class="lg:col-span-2 bg-card border border-border rounded-xl p-6"
          >
            <div class="flex items-center justify-between mb-5">
              <h2 class="heading-3 flex items-center gap-2">
                <Database class="h-5 w-5 text-foreground/70" />
                {{ selectionPanelTitle }}
              </h2>
              <div class="flex items-center gap-3">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Button
                        variant="outline"
                        size="icon"
                        class="h-8 w-8"
                        aria-label="Add source"
                        @click="openAddSource"
                      >
                        <Plus class="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Add source</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                <Button
                  v-if="ingestionStatus?.failed && ingestionStatus.failed > 0"
                  variant="outline"
                  size="sm"
                  @click="retryFailedJobs"
                  :disabled="isRetryingJobs"
                >
                  <RotateCcw class="h-3.5 w-3.5 mr-2" :class="{ 'animate-spin': isRetryingJobs }" />
                  Retry Failed ({{ ingestionStatus.failed }})
                </Button>
                <div class="flex items-center gap-1.5">
                  <span
                    :class="[
                      'w-1.5 h-1.5 rounded-full',
                      ingestionStatus?.is_watching ? 'bg-primary' : 'bg-muted-foreground',
                    ]"
                  ></span>
                  <span class="body-sm text-muted-foreground">
                    {{ ingestionStatus?.is_watching ? 'Watching' : 'Not watching' }}
                  </span>
                </div>
              </div>
            </div>

            <div v-if="selectedItemsView.length > 0" class="space-y-3">
              <div class="max-h-96 space-y-2.5 overflow-y-auto pr-1" @scroll="onSelectionScroll">
                <div
                  v-for="item in selectedItemsView"
                  :key="item.id"
                  class="flex items-start justify-between gap-4 px-4 py-3 bg-muted/40 border border-border/60 rounded-lg"
                >
                  <div class="min-w-0 flex-1">
                    <p class="body-sm font-mono text-foreground truncate">{{ item.id }}</p>
                    <p v-if="item.description" class="text-xs text-muted-foreground mt-1 truncate">
                      {{ item.description }}
                    </p>
                  </div>
                  <div class="flex items-center gap-1.5 shrink-0 mt-1">
                    <span
                      :class="[
                        'w-1.5 h-1.5 rounded-full',
                        item.status === 'watching' ? 'bg-primary' : 'bg-muted-foreground',
                      ]"
                    ></span>
                    <span class="text-xs text-muted-foreground">
                      {{ item.status === 'watching' ? 'Watching' : 'Not Watching' }}
                    </span>
                  </div>
                </div>
              </div>

              <div v-if="hasMoreSelection" class="pt-1 text-center text-xs text-muted-foreground">
                {{
                  selectionLoading
                    ? 'Loading…'
                    : `Showing ${selectionItems.length} of ${selectionTotal}`
                }}
              </div>
            </div>

            <div v-else-if="!selectionLoading" class="text-center py-12">
              <div
                class="mx-auto mb-3 h-10 w-10 rounded-full bg-muted flex items-center justify-center"
              >
                <Database class="h-5 w-5 text-muted-foreground" />
              </div>
              <p class="text-muted-foreground body-sm">No items selected yet</p>
            </div>
          </div>

          <!-- Configuration (right column on row 1) -->
          <div class="lg:col-span-1 bg-card border border-border rounded-xl p-6">
            <h2 class="heading-3 mb-5 flex items-center gap-2">
              <Settings class="h-5 w-5 text-foreground/70" />
              Configuration
            </h2>

            <div class="space-y-4">
              <div class="flex justify-between items-center gap-4">
                <span class="body-sm text-muted-foreground">Index name</span>
                <span class="body-sm font-mono text-foreground truncate">{{
                  getConfigValue('indexName') || getConfigValue('collectionName') || dataset.name
                }}</span>
              </div>
              <div class="flex justify-between items-center gap-4">
                <span class="body-sm text-muted-foreground">Connection</span>
                <div class="flex items-center gap-1.5">
                  <span
                    :class="[
                      'w-1.5 h-1.5 rounded-full',
                      healthStatus?.status === 'healthy' ? 'bg-primary' : 'bg-destructive',
                    ]"
                  ></span>
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
              <div
                v-for="(value, key) in getDisplayableConfig()"
                :key="key"
                class="flex justify-between items-center gap-4"
              >
                <span class="body-sm text-muted-foreground shrink-0">{{
                  formatConfigKey(key)
                }}</span>
                <span
                  class="body-sm font-mono text-foreground truncate text-right"
                  :title="String(formatConfigValue(key, value))"
                >
                  {{ formatConfigValue(key, value) }}
                </span>
              </div>
            </div>
          </div>

          <!-- Connected APIs (full width on row 2) -->
          <div class="lg:col-span-3 bg-card border border-border rounded-xl p-6">
            <h2 class="heading-3 mb-5 flex items-center gap-2">
              <Globe class="h-5 w-5 text-foreground/70" />
              Connected APIs
              <Badge
                variant="secondary"
                class="ml-1 h-[18px] min-w-[20px] justify-center px-1.5 text-[11px] font-semibold bg-primary/15 text-primary border-0 rounded-sm"
              >
                {{ connectedEndpoints.length }}
              </Badge>
            </h2>

            <div v-if="connectedEndpoints.length > 0" class="space-y-2.5">
              <div
                v-for="endpoint in connectedEndpoints"
                :key="endpoint.id"
                class="group flex items-center gap-4 px-4 py-3 bg-muted/40 border border-border/60 rounded-lg hover:bg-muted/70 transition-all cursor-pointer"
                @click="navigateToEndpoint(endpoint.slug)"
              >
                <Globe class="h-4 w-4 text-muted-foreground shrink-0" />
                <div class="flex-1 min-w-0">
                  <h3 class="body-sm font-medium text-foreground truncate">{{ endpoint.name }}</h3>
                  <p class="text-xs text-muted-foreground truncate mt-0.5">
                    {{ endpoint.slug || 'API' }}
                  </p>
                </div>
                <ChevronRight
                  class="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors shrink-0"
                />
              </div>
            </div>

            <div v-else class="text-center py-12">
              <Globe class="h-10 w-10 text-muted-foreground mx-auto mb-3" />
              <p class="text-muted-foreground body-sm mb-4">No APIs connected to this dataset</p>
              <Button size="sm" @click="$router.push({ name: 'create-data-endpoint' })">
                <Plus class="h-3.5 w-3.5 mr-2" />
                Create API
              </Button>
            </div>
          </div>
        </TabsContent>

        <!-- Files Tab Content -->
        <TabsContent value="files" class="space-y-6">
          <!-- Ingestion jobs (shown for any source that ingests, regardless of shape) -->
          <div
            v-if="getDatasetManagement() === 'Self-managed'"
            class="bg-card border border-border rounded-xl p-6"
          >
            <div class="flex items-center justify-between mb-6">
              <h2 class="heading-3">Ingested Items</h2>
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
                {{ getStatusCount(selectedJobStatus) }} items
              </div>
            </div>

            <!-- Loading State -->
            <div v-if="isLoadingFiles" class="flex items-center justify-center py-8">
              <div class="flex items-center gap-2 text-muted-foreground">
                <RefreshCw class="h-4 w-4 animate-spin" />
                <span class="body-sm">Loading items...</span>
              </div>
            </div>

            <!-- Items List -->
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
                No {{ getStatusLabel(selectedJobStatus).toLowerCase() }} items found
              </p>
            </div>
          </div>

          <!-- Fallback for external (read-only) datasets that don't ingest locally -->
          <div v-else class="bg-card border border-border rounded-xl p-12 text-center">
            <File class="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p class="text-muted-foreground body-sm">
              This data source is read-only — its content is managed externally.
            </p>
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

  <!-- Add Source Dialog -->
  <AddSourceDialog
    v-model:open="showAddSourceDialog"
    :dataset="addSourceDataset"
    @sources-added="handleSourcesAdded"
  />

  <!-- Delete Confirmation Dialog -->
  <DeleteConfirmationDialog
    v-model:open="showDeleteDialog"
    item-type="Dataset"
    :item-name="dataset?.name || ''"
    :dependencies="getEndpointNamesForDataset()"
    dependency-type="API"
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
  RefreshCw,
  RotateCcw,
  File,
  FileText,
  Clock,
  ChevronLeft,
  ChevronRight as ChevronRightIcon,
  MoreVertical,
  Settings,
} from 'lucide-vue-next'
import DeleteConfirmationDialog from '@/components/DeleteConfirmationDialog.vue'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import CreateDatasetDialogSimple from '@/components/CreateDatasetDialogSimple.vue'
import AddSourceDialog from '@/components/AddSourceDialog.vue'
import { datasetsApi } from '@/api/endpoints/datasets'
import { ingestionApi } from '@/api/endpoints/ingestion'
import type {
  DatasetResponse,
  IngestionStatusResponse,
  IngestionJobListResponse,
  DatasetTypeInfoResponse,
  SelectedItemResponse,
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
} | null>(null)
const showDeleteDialog = ref(false)
const showAddSourceDialog = ref(false)
const addSourceDataset = ref<{
  name: string
  dtype: string
  selectedIds: string[]
} | null>(null)
const isRefreshingPaths = ref(false)
const ingestionStatus = ref<IngestionStatusResponse | null>(null)
const ingestionJobs = ref<IngestionJobListResponse | null>(null)
const selectedJobStatus = ref<string>('completed')
const isRetryingJobs = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const isLoadingFiles = ref(false)

// Selection is fetched on demand and paged in — no longer inlined in the
// dataset payload — so a source watching many picks stays cheap to render.
const SELECTION_PAGE_SIZE = 10
const selectionItems = ref<SelectedItemResponse[]>([])
const selectionTotal = ref(0)
const selectionLoading = ref(false)

const connectedEndpoints = computed(() => {
  if (!dataset.value) return []
  return dataset.value.connected_endpoints
})

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

    const typeInfoPromise = datasetsApi.getType(datasetResponse.dtype).catch((typeErr) => {
      console.error('Failed to load dataset type info:', typeErr)
      return null
    })
    const selfManaged = getDatasetManagement() === 'Self-managed'
    const ingestionPromise = selfManaged ? loadIngestionData(datasetResponse.id) : Promise.resolve()
    const selectionPromise = selfManaged ? loadSelection(true) : Promise.resolve()

    const [typeInfoResponse] = await Promise.all([
      typeInfoPromise,
      ingestionPromise,
      selectionPromise,
    ])
    datasetTypeInfo.value = typeInfoResponse
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

const openAddSource = async () => {
  if (!dataset.value) return
  // The picker pre-checks already-selected items, so it needs the full id
  // set (not a page) — fetched from the dedicated ids endpoint.
  let selectedIds: string[] = []
  try {
    const res = await datasetsApi.getSelectionIds(dataset.value.name)
    selectedIds = res.item_ids
  } catch (err) {
    console.error('Failed to load selection ids:', err)
  }
  addSourceDataset.value = {
    name: dataset.value.name,
    dtype: dataset.value.dtype,
    selectedIds,
  }
  showAddSourceDialog.value = true
}

const handleSourcesAdded = async () => {
  showAddSourceDialog.value = false
  addSourceDataset.value = null
  // Reload so the new watched paths and ingestion jobs appear.
  await loadDataset(route.params.slug as string)
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

// Dataset management type - 'External' for read-only bindings (remote_weaviate)
// whose data lives outside this process; 'Self-managed' for everything else,
// where the dataset's source emits ingestion jobs that we track locally.
const getDatasetManagement = () => {
  if (!dataset.value) return 'External'
  return dataset.value.dtype === 'remote_weaviate' ? 'External' : 'Self-managed'
}

// Title for the selection panel — source-specific where a noun reads more
// naturally ("Watched Paths" for files, "Watched posts" for WordPress),
// falling back to the generic "Selected items".
const selectionPanelTitle = computed(() => {
  switch (dataset.value?.dtype) {
    case 'local_file':
      return 'Watched Paths'
    case 'wordpress':
      return 'Watched posts'
    case 'blogspot':
      return 'Watched blogs & posts'
    default:
      return 'Selected items'
  }
})

// Source-agnostic selected items from the paged selection fetch
// (file paths, '{post_type}:{id}', ...), descriptions included.
const selectedItemsView = computed(() =>
  selectionItems.value.map((item) => ({
    id: item.item_id,
    description: item.description || '',
    status: ingestionStatus.value?.is_watching ? 'watching' : 'not_watching',
  })),
)

const hasMoreSelection = computed(() => selectionItems.value.length < selectionTotal.value)

// Load the selection page-by-page. ``reset`` starts from the first page
// (initial load / after picks change); otherwise the next page is appended.
const loadSelection = async (reset = false) => {
  if (!dataset.value || getDatasetManagement() !== 'Self-managed') return

  const offset = reset ? 0 : selectionItems.value.length
  selectionLoading.value = true
  try {
    const page = await datasetsApi.getSelection(dataset.value.name, SELECTION_PAGE_SIZE, offset)
    selectionItems.value = reset ? page.items : [...selectionItems.value, ...page.items]
    selectionTotal.value = page.total
  } catch (err) {
    console.error('Failed to load selection:', err)
  } finally {
    selectionLoading.value = false
  }
}

// Auto-load the next page when the list is scrolled near the bottom.
const onSelectionScroll = (e: Event) => {
  const el = e.target as HTMLElement
  const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48
  if (nearBottom && hasMoreSelection.value && !selectionLoading.value) {
    loadSelection(false)
  }
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
