<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Breadcrumb Navigation -->
    <nav class="flex mb-12" aria-label="Breadcrumb">
      <ol class="flex items-center space-x-3">
        <li>
          <router-link
            to="/datasets"
            class="text-gray-500 hover:text-gray-700 text-sm font-medium flex items-center transition-colors"
          >
            <Database class="h-4 w-4 mr-2" />
            Datasets
          </router-link>
        </li>
        <li class="flex items-center">
          <ChevronRight class="h-4 w-4 text-gray-300 mx-3" />
          <span class="text-gray-900 text-sm font-medium">{{ dataset?.name || 'Loading...' }}</span>
        </li>
      </ol>
    </nav>

    <!-- Error State -->
    <div v-if="error" class="bg-red-50/50 border border-red-200/50 rounded-2xl p-8 text-center">
      <h3 class="text-lg font-medium text-red-900 mb-2">Dataset not found</h3>
      <p class="text-red-700 mb-4">
        The dataset you're looking for doesn't exist or has been deleted.
      </p>
      <Button @click="$router.push('/datasets')" variant="outline" class="rounded-xl"> Back to Datasets </Button>
    </div>

    <!-- Dataset Details -->
    <div v-else-if="dataset" class="space-y-6">
      <!-- Header -->
      <div class="bg-white/60 backdrop-blur-sm border border-gray-100 rounded-3xl p-8 mb-8">
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-6">
            <div
              :class="[
                'p-4 rounded-2xl shadow-sm',
                dataset.type === 'weaviate'
                  ? 'bg-purple-50 border border-purple-100'
                  : dataset.type === 'qdrant'
                    ? 'bg-blue-50 border border-blue-100'
                    : 'bg-green-50 border border-green-100',
              ]"
            >
              <IntegrationIcon :name="dataset.type" class="h-8 w-8" />
            </div>
            <div>
              <h1 class="text-2xl font-bold text-gray-900 mb-2">{{ dataset.name }}</h1>
              <p class="text-gray-600 mb-4">{{ dataset.description }}</p>
              <div class="flex flex-wrap items-center gap-3">
                <Badge
                  variant="outline"
                  :class="
                    dataset.status === 'running'
                      ? 'bg-green-50/50 text-green-700 border-green-200/50 px-3 py-1.5 rounded-full'
                      : 'bg-gray-50/50 text-gray-600 border-gray-200/50 px-3 py-1.5 rounded-full'
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
                <Badge variant="outline" class="bg-blue-50/50 text-blue-700 border-blue-200/50 px-3 py-1.5 rounded-full">
                  {{ dataset.type.charAt(0).toUpperCase() + dataset.type.slice(1) }}
                </Badge>
                <Badge
                  v-for="tag in dataset.tags"
                  :key="`tag-${tag}`"
                  variant="outline"
                  class="bg-gray-50/50 text-gray-600 border-gray-200/50 px-3 py-1.5 rounded-full"
                >
                  {{ tag }}
                </Badge>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <Button variant="outline" @click="editDataset" class="rounded-xl border-gray-200 hover:border-gray-300 px-4 py-2.5">
              <Edit class="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button
              variant="outline"
              class="text-red-600 hover:text-red-700 border-red-200 hover:border-red-300 rounded-xl px-4 py-2.5"
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
        <TabsList class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-3">
          <TabsTrigger value="overview" class="flex items-center gap-2">
            <Database class="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="analytics" class="flex items-center gap-2">
            <BarChart3 class="h-4 w-4" />
            Analytics
          </TabsTrigger>
          <TabsTrigger value="logs" class="flex items-center gap-2">
            <ScrollText class="h-4 w-4" />
            Logs
          </TabsTrigger>
        </TabsList>

        <!-- Overview Tab Content -->
        <TabsContent value="overview" class="space-y-6">
          <!-- Dataset Summary -->
          <div class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
            <div class="grid grid-cols-2 md:grid-cols-6 gap-8">
              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Type</p>
                <p class="text-sm font-medium text-gray-900">{{ dataset.type.charAt(0).toUpperCase() + dataset.type.slice(1) }}</p>
              </div>
              
              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Status</p>
                <div class="flex items-center justify-center gap-2">
                  <div 
                    :class="[
                      'w-2.5 h-2.5 rounded-full',
                      dataset.status === 'running' ? 'bg-green-500' : 'bg-gray-400'
                    ]"
                  ></div>
                  <p class="text-sm font-medium text-gray-900 capitalize">{{ dataset.status }}</p>
                </div>
              </div>
              
              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Endpoints</p>
                <p class="text-sm font-medium text-gray-900">{{ dataset.endpointCount }}</p>
              </div>

              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Queries</p>
                <p class="text-sm font-medium text-blue-600">{{ getUsageStats().totalQueries }}</p>
              </div>

              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Data Points</p>
                <p class="text-sm font-medium text-green-600">{{ getUsageStats().dataPoints }}</p>
              </div>

              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Created</p>
                <p class="text-sm font-medium text-gray-900">{{ formatDate(dataset.createdAt) }}</p>
              </div>
            </div>
          </div>

          <!-- File Watching Status (only for self-managed) -->
          <div v-if="getDatasetManagement() === 'Self-managed'" class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between mb-8">
              <h2 class="text-lg font-semibold text-gray-900 flex items-center gap-2">Watched Paths</h2>
              <Button variant="outline" size="sm" @click="refreshWatchedPaths" class="rounded-xl px-4 py-2.5">
                <RefreshCw class="h-4 w-4 mr-2" :class="{ 'animate-spin': isRefreshingPaths }" />
                Refresh
              </Button>
            </div>
            <div class="space-y-4">
              <div 
                v-for="path in getWatchedPaths()" 
                :key="path.id"
                class="flex items-center justify-between py-6 px-6 bg-gray-50/50 border border-gray-100 rounded-2xl hover:bg-gray-50/80 transition-all"
              >
                <div class="flex items-center gap-4">
                  <div 
                    :class="[
                      'w-3 h-3 rounded-full',
                      path.status === 'indexed' ? 'bg-green-500' :
                      path.status === 'processing' ? 'bg-blue-500' :
                      path.status === 'queued' ? 'bg-yellow-500' :
                      path.status === 'errored' ? 'bg-red-500' : 'bg-gray-400'
                    ]"
                  ></div>
                  <div class="flex-1">
                    <p class="text-sm font-medium text-gray-900">{{ path.path }}</p>
                    <p class="text-xs text-gray-500 mt-1">{{ path.fileCount }} files • Last scan: {{ path.lastScan }}</p>
                    <p class="text-xs text-gray-600 mt-2 italic">{{ path.summary }}</p>
                  </div>
                </div>
                <div class="flex items-center gap-4">
                  <Badge 
                    :variant="path.status === 'indexed' ? 'default' : 
                             path.status === 'processing' ? 'secondary' :
                             path.status === 'errored' ? 'destructive' : 'outline'"
                    class="capitalize px-3 py-1.5 rounded-full border-0"
                  >
                    {{ path.status }}
                  </Badge>
                  <span v-if="path.status === 'processing'" class="text-sm font-medium text-gray-600">
                    {{ path.progress }}%
                  </span>
                </div>
              </div>
            </div>
            
            <div class="mt-8 pt-6 border-t border-gray-100">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-6">
                  <span class="flex items-center gap-2.5 text-sm font-medium text-gray-600">
                    <div class="w-2.5 h-2.5 bg-green-500 rounded-full"></div>
                    Indexed ({{ getWatchedPaths().filter(p => p.status === 'indexed').length }})
                  </span>
                  <span class="flex items-center gap-2.5 text-sm font-medium text-gray-600">
                    <div class="w-2.5 h-2.5 bg-blue-500 rounded-full"></div>
                    Processing ({{ getWatchedPaths().filter(p => p.status === 'processing').length }})
                  </span>
                  <span class="flex items-center gap-2.5 text-sm font-medium text-gray-600">
                    <div class="w-2.5 h-2.5 bg-yellow-500 rounded-full"></div>
                    Queued ({{ getWatchedPaths().filter(p => p.status === 'queued').length }})
                  </span>
                  <span class="flex items-center gap-2.5 text-sm font-medium text-gray-600">
                    <div class="w-2.5 h-2.5 bg-red-500 rounded-full"></div>
                    Errored ({{ getWatchedPaths().filter(p => p.status === 'errored').length }})
                  </span>
                </div>
                <Button variant="outline" size="sm" class="rounded-xl px-4 py-2.5">
                  <Plus class="h-4 w-4 mr-2" />
                  Add Path
                </Button>
              </div>
            </div>
          </div>

          <!-- Configuration Settings -->
          <div class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between mb-8">
              <h2 class="text-lg font-semibold text-gray-900 flex items-center gap-2">Configuration</h2>
              <div class="flex items-center gap-3">
                <Button variant="outline" size="sm" class="rounded-xl px-4 py-2.5">
                  <Edit class="h-4 w-4 mr-2" />
                  Edit Settings
                </Button>
              </div>
            </div>
            
            <!-- Basic Settings -->
            <div class="space-y-6">
              <div class="flex justify-between items-center py-2 border-b border-gray-100">
                <span class="text-xs text-gray-600">Index Name</span>
                <span class="text-xs font-medium text-gray-900">{{ getIndexName() }}</span>
              </div>
              <div class="flex justify-between items-center py-2">
                <span class="text-xs text-gray-600">Connection Status</span>
                <div class="flex items-center gap-3">
                  <div class="w-2.5 h-2.5 bg-green-500 rounded-full"></div>
                  <span class="text-xs font-medium text-green-600">Connected</span>
                </div>
              </div>
            </div>

            <!-- Advanced Settings (Collapsible) -->
            <div v-if="showAdvancedConfig" class="mt-6 pt-6 border-t border-gray-200">
              <div class="space-y-6">
                <h3 class="text-sm font-semibold text-gray-900 mb-4">Advanced Settings</h3>
                <div class="space-y-3">
                  <div class="flex justify-between items-center py-2 border-b border-gray-100">
                    <span class="text-xs text-gray-600">URL</span>
                    <span class="text-xs font-medium text-gray-900">{{ getConnectionUrl() }}</span>
                  </div>
                  <div class="flex justify-between items-center py-2 border-b border-gray-100">
                    <span class="text-xs text-gray-600">Vector Dimensions</span>
                    <span class="text-xs font-medium text-gray-900">{{ getWeaviateConfig().dimensions }}</span>
                  </div>
                  <div class="flex justify-between items-center py-2 border-b border-gray-100">
                    <span class="text-xs text-gray-600">Chunk Size</span>
                    <span class="text-xs font-medium text-gray-900">{{ getWeaviateConfig().chunkSize }} tokens</span>
                  </div>
                  <div class="flex justify-between items-center py-2 border-b border-gray-100">
                    <span class="text-xs text-gray-600">Overlap</span>
                    <span class="text-xs font-medium text-gray-900">{{ getWeaviateConfig().overlap }} tokens</span>
                  </div>
                  <div class="flex justify-between items-center py-2 border-b border-gray-100">
                    <span class="text-xs text-gray-600">Embedding Model</span>
                    <span class="text-xs font-medium text-gray-900">{{ getWeaviateConfig().embeddingModel }}</span>
                  </div>
                  <div class="flex justify-between items-center py-2">
                    <span class="text-xs text-gray-600">Distance Metric</span>
                    <span class="text-xs font-medium text-gray-900">{{ getWeaviateConfig().distanceMetric }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Show Advanced Button (Bottom Right) -->
            <div class="flex justify-end mt-6 pt-6 border-t border-gray-100">
              <Button 
                variant="ghost" 
                size="sm" 
                @click="showAdvancedConfig = !showAdvancedConfig"
                class="text-gray-500 hover:text-gray-700 rounded-xl px-4 py-2.5"
              >
                <ChevronDown class="h-4 w-4 mr-2 transition-transform" :class="{ 'rotate-180': showAdvancedConfig }" />
                {{ showAdvancedConfig ? 'Hide' : 'Show' }} Advanced
              </Button>
            </div>
          </div>

          <!-- Connected Endpoints -->
          <div class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">Connected Endpoints ({{ connectedEndpoints.length }})</h2>
            <div v-if="connectedEndpoints.length > 0" class="space-y-4">
              <div
                v-for="endpoint in connectedEndpoints"
                :key="endpoint.id"
                class="flex items-center justify-between py-6 px-6 bg-gray-50/50 border border-gray-100 rounded-2xl hover:bg-gray-50/80 transition-all"
              >
                <div class="flex items-center gap-4">
                  <div class="p-3 bg-blue-50 border border-blue-100 rounded-xl">
                    <Globe class="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 class="text-sm font-medium text-gray-900">{{ endpoint.name }}</h3>
                    <p class="text-xs text-gray-500 mt-1">{{ endpoint.description || 'API endpoint' }}</p>
                  </div>
                </div>
                <Button variant="outline" size="sm" class="rounded-xl px-4 py-2.5">
                  <ExternalLink class="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div v-else class="text-center py-16">
              <Globe class="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <p class="text-gray-500 text-sm mb-4">No endpoints connected to this dataset</p>
              <Button size="sm" class="rounded-xl px-6 py-3">
                <Plus class="h-4 w-4 mr-2" />
                Create Endpoint
              </Button>
            </div>
          </div>
        </TabsContent>

        <!-- Analytics Tab Content -->
        <TabsContent value="analytics" class="space-y-6">

          <!-- Access Trends Chart -->
          <div class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between mb-8">
              <h2 class="text-lg font-semibold text-gray-900 flex items-center gap-2">Access Trends</h2>
              <div class="flex items-center gap-2">
                <Button
                  v-for="period in ['Daily', 'Weekly', 'Monthly']"
                  :key="period"
                  size="sm"
                  :variant="selectedPeriod === period ? 'default' : 'outline'"
                  @click="selectedPeriod = period"
                  class="text-sm rounded-xl px-4 py-2"
                >
                  {{ period }}
                </Button>
              </div>
            </div>
            <div
              class="h-80 flex items-center justify-center border border-dashed border-gray-200 rounded-2xl bg-gray-50/30"
            >
              <div class="text-center">
                <p class="text-gray-500 text-lg mb-1">{{ selectedPeriod }} Access Chart</p>
                <p class="text-gray-400 text-sm">Chart visualization coming soon</p>
              </div>
            </div>
          </div>

          <!-- Access Logs -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <div class="flex items-center justify-between mb-4">
              <h2 class="text-lg font-semibold text-gray-900">Recent Access Logs</h2>
              <Button variant="outline" size="sm">
                <Download class="h-4 w-4 mr-2" />
                Export Logs
              </Button>
            </div>
            <div class="space-y-3">
              <div 
                v-for="log in getAccessLogs()" 
                :key="log.id"
                class="flex items-center justify-between py-3 px-4 border border-gray-200 rounded-lg"
              >
                <div class="flex items-center gap-3">
                  <div 
                    :class="[
                      'w-2 h-2 rounded-full',
                      log.status === 'success' ? 'bg-green-500' : 
                      log.status === 'error' ? 'bg-red-500' : 'bg-yellow-500'
                    ]"
                  ></div>
                  <span class="text-sm font-medium text-gray-900">{{ log.endpoint }}</span>
                  <span class="text-xs text-gray-500">{{ log.method }}</span>
                </div>
                <div class="flex items-center gap-4">
                  <span class="text-xs text-gray-600">{{ log.responseTime }}</span>
                  <span class="text-xs text-gray-500">{{ log.timestamp }}</span>
                  <Badge 
                    :variant="log.status === 'success' ? 'default' : 'destructive'"
                    class="text-xs"
                  >
                    {{ log.status }}
                  </Badge>
                </div>
              </div>
            </div>
          </div>
        </TabsContent>

        <!-- Logs Tab Content -->
        <TabsContent value="logs" class="space-y-6">
          <div class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between mb-8">
              <h2 class="text-lg font-semibold text-gray-900 flex items-center gap-2">Weaviate Logs</h2>
              <div class="flex items-center gap-3">
                <Button variant="outline" size="sm" @click="refreshLogs" class="rounded-xl px-4 py-2.5">
                  <RefreshCw class="h-4 w-4 mr-2" :class="{ 'animate-spin': isRefreshing }" />
                  Refresh
                </Button>
                <Button variant="outline" size="sm" class="rounded-xl px-4 py-2.5">
                  <Download class="h-4 w-4 mr-2" />
                  Download
                </Button>
              </div>
            </div>
            
            <!-- Log Filters -->
            <div class="flex items-center gap-6 mb-8 pb-6 border-b border-gray-100">
              <div class="flex items-center gap-3">
                <span class="text-sm font-medium text-gray-600">Level:</span>
                <div class="flex gap-2">
                  <Button
                    v-for="level in ['ALL', 'INFO', 'WARN', 'ERROR']"
                    :key="level"
                    size="sm"
                    :variant="selectedLogLevel === level ? 'default' : 'outline'"
                    @click="selectedLogLevel = level"
                    class="text-sm rounded-xl px-4 py-2"
                  >
                    {{ level }}
                  </Button>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <span class="text-sm font-medium text-gray-600">Auto-refresh:</span>
                <Button
                  size="sm"
                  :variant="autoRefresh ? 'default' : 'outline'"
                  @click="toggleAutoRefresh"
                  class="text-sm rounded-xl px-4 py-2"
                >
                  {{ autoRefresh ? 'ON' : 'OFF' }}
                </Button>
              </div>
            </div>

            <!-- Logs Display -->
            <div class="bg-gray-900 rounded-2xl p-6 h-96 overflow-y-auto font-mono text-sm border border-gray-200">
              <div 
                v-for="log in filteredLogs" 
                :key="log.id"
                :class="[
                  'mb-2 leading-relaxed',
                  log.level === 'INFO' ? 'text-green-400' :
                  log.level === 'WARN' ? 'text-yellow-400' :
                  log.level === 'ERROR' ? 'text-red-400' : 'text-gray-300'
                ]"
              >
                <span class="text-gray-500">[{{ log.timestamp }}]</span>
                <span :class="[
                  'ml-2 px-2 py-1 rounded text-xs font-bold',
                  log.level === 'INFO' ? 'bg-green-900 text-green-200' :
                  log.level === 'WARN' ? 'bg-yellow-900 text-yellow-200' :
                  log.level === 'ERROR' ? 'bg-red-900 text-red-200' : 'bg-gray-800 text-gray-300'
                ]">{{ log.level }}</span>
                <span class="ml-2">{{ log.message }}</span>
              </div>
              <div v-if="filteredLogs.length === 0" class="text-gray-500 text-center py-8">
                No logs found for the selected filter
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { 
  Database, 
  ChevronRight, 
  Edit, 
  Trash2, 
  Globe, 
  Plus, 
  ExternalLink,
  BarChart3,
  ScrollText,
  Download,
  RefreshCw,
  ChevronDown
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
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
const selectedLogLevel = ref('ALL')
const autoRefresh = ref(false)
const isRefreshing = ref(false)
const refreshInterval = ref<number | null>(null)
const isRefreshingPaths = ref(false)
const showAdvancedConfig = ref(false)

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

// Configuration getters
const getConnectionUrl = () => {
  if (!dataset.value) return 'N/A'
  return dataset.value.type === 'weaviate' 
    ? 'http://localhost:8080/v1'
    : dataset.value.type === 'qdrant' 
    ? 'http://localhost:6333'
    : 'http://localhost:8000'
}

const getIndexName = () => {
  return dataset.value?.name.toLowerCase().replace(/\s+/g, '_') || 'default'
}

const getVectorDimensions = () => {
  return dataset.value?.type === 'weaviate' ? '1536' : '768'
}

const getDistanceMetric = () => {
  return dataset.value?.type === 'weaviate' ? 'cosine' : 'euclidean'
}

// Weaviate configuration settings
const getWeaviateConfig = () => {
  return {
    chunkSize: '512',
    embeddingModel: 'text-embedding-ada-002',
    distanceMetric: getDistanceMetric(),
    dimensions: getVectorDimensions(),
    overlap: '50',
    batchSize: '100',
    maxRetries: '3'
  }
}


// Dataset management type
const getDatasetManagement = () => {
  // For demo purposes, make Legal Documents self-managed, others external
  return dataset.value?.name === 'Legal Documents Store' ? 'Self-managed' : 'External'
}

// Watched paths for self-managed datasets
const getWatchedPaths = () => {
  if (getDatasetManagement() === 'Self-managed') {
    return [
      {
        id: '1',
        path: '/data/legal/contracts',
        fileCount: 1247,
        lastScan: '2 min ago',
        status: 'indexed',
        progress: 100,
        summary: 'Commercial agreements, service contracts, and partnership documents'
      },
      {
        id: '2',
        path: '/data/legal/cases',
        fileCount: 856,
        lastScan: '5 min ago',
        status: 'processing',
        progress: 73,
        summary: 'Court decisions, case law, and legal precedents from various jurisdictions'
      },
      {
        id: '3',
        path: '/data/legal/regulations',
        fileCount: 423,
        lastScan: '1 hour ago',
        status: 'queued',
        progress: 0,
        summary: 'Federal and state regulations, compliance guidelines, and regulatory updates'
      },
      {
        id: '4',
        path: '/data/legal/archived',
        fileCount: 89,
        lastScan: '3 hours ago',
        status: 'errored',
        progress: 0,
        summary: 'Historical legal documents and archived case files'
      }
    ]
  }
  return []
}

const refreshWatchedPaths = async () => {
  isRefreshingPaths.value = true
  // Simulate API call
  await new Promise(resolve => setTimeout(resolve, 1500))
  isRefreshingPaths.value = false
}


const getAccessLogs = () => {
  return [
    {
      id: '1',
      endpoint: 'Legal Document Analysis API',
      method: 'POST',
      status: 'success',
      responseTime: '45ms',
      timestamp: '2 min ago'
    },
    {
      id: '2', 
      endpoint: 'Contract Review Assistant',
      method: 'GET',
      status: 'success',
      responseTime: '23ms',
      timestamp: '5 min ago'
    },
    {
      id: '3',
      endpoint: 'Legal Research Helper', 
      method: 'POST',
      status: 'error',
      responseTime: '1.2s',
      timestamp: '8 min ago'
    },
    {
      id: '4',
      endpoint: 'Legal Document Analysis API',
      method: 'GET', 
      status: 'success',
      responseTime: '67ms',
      timestamp: '12 min ago'
    }
  ]
}

// Mock log data
const mockLogs = ref([
  {
    id: '1',
    timestamp: '2024-10-27 14:32:15',
    level: 'INFO',
    message: 'Successfully connected to Weaviate instance at localhost:8080'
  },
  {
    id: '2', 
    timestamp: '2024-10-27 14:32:16',
    level: 'INFO',
    message: 'Schema validation completed for class LegalDocuments'
  },
  {
    id: '3',
    timestamp: '2024-10-27 14:35:22',
    level: 'WARN',
    message: 'Query performance degraded: 150ms response time exceeded threshold'
  },
  {
    id: '4',
    timestamp: '2024-10-27 14:38:45',
    level: 'ERROR', 
    message: 'Failed to index document: vector dimension mismatch (expected 1536, got 768)'
  },
  {
    id: '5',
    timestamp: '2024-10-27 14:40:12',
    level: 'INFO',
    message: 'Backup process started for class LegalDocuments'
  },
  {
    id: '6',
    timestamp: '2024-10-27 14:42:33',
    level: 'INFO',
    message: 'Successfully processed batch insert: 1,247 documents indexed'
  },
  {
    id: '7',
    timestamp: '2024-10-27 14:45:18', 
    level: 'WARN',
    message: 'Memory usage high: 85% of allocated heap space in use'
  },
  {
    id: '8',
    timestamp: '2024-10-27 14:47:29',
    level: 'INFO',
    message: 'Query executed successfully: similarity search returned 15 results'
  }
])

const filteredLogs = computed(() => {
  if (selectedLogLevel.value === 'ALL') {
    return mockLogs.value
  }
  return mockLogs.value.filter(log => log.level === selectedLogLevel.value)
})

const refreshLogs = async () => {
  isRefreshing.value = true
  // Simulate API call
  await new Promise(resolve => setTimeout(resolve, 1000))
  
  // Add a new mock log entry
  const newLog = {
    id: Date.now().toString(),
    timestamp: new Date().toLocaleString('sv-SE').replace(' ', ' '),
    level: ['INFO', 'WARN', 'ERROR'][Math.floor(Math.random() * 3)] as 'INFO' | 'WARN' | 'ERROR',
    message: 'New log entry generated at ' + new Date().toLocaleTimeString()
  }
  mockLogs.value.unshift(newLog)
  
  isRefreshing.value = false
}

const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value
  
  if (autoRefresh.value) {
    refreshInterval.value = setInterval(() => {
      refreshLogs()
    }, 5000) // Refresh every 5 seconds
  } else {
    if (refreshInterval.value) {
      clearInterval(refreshInterval.value)
      refreshInterval.value = null
    }
  }
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

onUnmounted(() => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value)
  }
})
</script>
