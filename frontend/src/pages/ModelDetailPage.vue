<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Breadcrumb Navigation -->
    <nav class="flex mb-12" aria-label="Breadcrumb">
      <ol class="flex items-center space-x-3">
        <li>
          <router-link
            to="/models"
            class="text-gray-500 hover:text-gray-700 text-sm font-medium flex items-center transition-colors"
          >
            <Brain class="h-4 w-4 mr-2" />
            Models
          </router-link>
        </li>
        <li class="flex items-center">
          <ChevronRight class="h-4 w-4 text-gray-300 mx-3" />
          <span class="text-gray-900 text-sm font-medium">{{ model?.name || 'Loading...' }}</span>
        </li>
      </ol>
    </nav>

    <!-- Error State -->
    <div v-if="error" class="bg-red-50/50 border border-red-200/50 rounded-2xl p-8 text-center">
      <h3 class="text-lg font-medium text-red-900 mb-2">Model not found</h3>
      <p class="text-red-700 mb-4">
        The model you're looking for doesn't exist or has been deleted.
      </p>
      <Button @click="goToModels" variant="outline" class="rounded-xl"> Back to Models </Button>
    </div>

    <!-- Model Details -->
    <div v-else-if="model" class="space-y-6">
      <!-- Header -->
      <div class="bg-white/60 backdrop-blur-sm border border-gray-100 rounded-3xl p-8 mb-8">
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-6">
            <div
              :class="[
                'p-4 rounded-2xl shadow-sm',
                model.type === 'vllm'
                  ? 'bg-purple-50 border border-purple-100'
                  : model.type === 'ollama'
                    ? 'bg-orange-50 border border-orange-100'
                    : 'bg-indigo-50 border border-indigo-100',
              ]"
            >
              <IntegrationIcon :name="model.type" class="h-8 w-8" />
            </div>
            <div>
              <h1 class="text-2xl font-bold text-gray-900 mb-2">{{ model.name }}</h1>
              <p class="text-gray-600 mb-4">{{ model.description }}</p>
              <div class="flex flex-wrap items-center gap-3">
                <Badge
                  variant="outline"
                  :class="
                    model.status === 'running'
                      ? 'bg-green-50/50 text-green-700 border-green-200/50 px-3 py-1.5 rounded-full'
                      : 'bg-gray-50/50 text-gray-600 border-gray-200/50 px-3 py-1.5 rounded-full'
                  "
                >
                  <div
                    :class="
                      model.status === 'running'
                        ? 'w-2 h-2 bg-green-500 rounded-full mr-2'
                        : 'w-2 h-2 bg-gray-400 rounded-full mr-2'
                    "
                  ></div>
                  {{ model.status === 'running' ? 'Running' : 'Stopped' }}
                </Badge>
                <Badge variant="outline" class="bg-blue-50/50 text-blue-700 border-blue-200/50 px-3 py-1.5 rounded-full">
                  {{ model.type.charAt(0).toUpperCase() + model.type.slice(1) }}
                </Badge>
                <Badge
                  v-for="tag in model.tags"
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
            <Button variant="outline" @click="editModel" class="rounded-xl border-gray-200 hover:border-gray-300 px-4 py-2.5">
              <Edit class="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button
              variant="outline"
              class="text-red-600 hover:text-red-700 border-red-200 hover:border-red-300 rounded-xl px-4 py-2.5"
              @click="deleteModel"
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
            <Brain class="h-4 w-4" />
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
          <!-- Model Summary -->
          <div class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
            <div class="grid grid-cols-2 md:grid-cols-6 gap-8">
              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Type</p>
                <p class="text-sm font-medium text-gray-900">{{ model.type.charAt(0).toUpperCase() + model.type.slice(1) }}</p>
              </div>
              
              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Status</p>
                <div class="flex items-center justify-center gap-2">
                  <div 
                    :class="[
                      'w-2.5 h-2.5 rounded-full',
                      model.status === 'running' ? 'bg-green-500' : 'bg-gray-400'
                    ]"
                  ></div>
                  <p class="text-sm font-medium text-gray-900 capitalize">{{ model.status }}</p>
                </div>
              </div>
              
              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Endpoints</p>
                <p class="text-sm font-medium text-gray-900">{{ model.endpointCount }}</p>
              </div>

              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Requests</p>
                <p class="text-sm font-medium text-blue-600">{{ getUsageStats().totalRequests }}</p>
              </div>

              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Earnings</p>
                <p class="text-sm font-medium text-green-600">{{ getEarnings().total }}</p>
              </div>

              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Created</p>
                <p class="text-sm font-medium text-gray-900">{{ formatDate(model.createdAt) }}</p>
              </div>
            </div>
          </div>

          <!-- Model Configuration -->
          <div class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between mb-8">
              <h2 class="text-lg font-semibold text-gray-900 flex items-center gap-2">Model Configuration</h2>
              <div class="flex items-center gap-3">
                <Button variant="outline" size="sm" class="rounded-xl px-4 py-2.5">
                  <Edit class="h-4 w-4 mr-2" />
                  Edit Settings
                </Button>
              </div>
            </div>
            
            <!-- Basic Settings -->
            <div class="space-y-6">
              <div class="flex justify-between items-center py-4 border-b border-gray-100">
                <span class="text-sm text-gray-600">URL</span>
                <span class="text-sm font-medium text-gray-900">{{ getModelPath() }}</span>
              </div>
              <div class="flex justify-between items-center py-4 border-b border-gray-100">
                <span class="text-sm text-gray-600">Max Tokens</span>
                <span class="text-sm font-medium text-gray-900">{{ getModelConfig().maxTokens }}</span>
              </div>
              <div class="flex justify-between items-center py-4 border-b border-gray-100">
                <span class="text-sm text-gray-600">Temperature</span>
                <span class="text-sm font-medium text-gray-900">{{ getModelConfig().temperature }}</span>
              </div>
              <div class="flex justify-between items-center py-4">
                <span class="text-sm text-gray-600">Connection Status</span>
                <div class="flex items-center gap-3">
                  <div class="w-2.5 h-2.5 bg-green-500 rounded-full"></div>
                  <span class="text-sm font-medium text-green-600">Connected</span>
                </div>
              </div>
            </div>

            <!-- Advanced Settings (Collapsible) -->
            <div v-if="showAdvancedConfig" class="mt-6 pt-6 border-t border-gray-200">
              <div class="space-y-6">
                <h3 class="text-sm font-semibold text-gray-900 mb-4">Advanced Settings</h3>
                <div class="space-y-3">
                  <div class="flex justify-between items-center py-2 border-b border-gray-100">
                    <span class="text-xs text-gray-600">GPU Memory</span>
                    <span class="text-xs font-medium text-gray-900">{{ getModelConfig().gpuMemory }}</span>
                  </div>
                  <div class="flex justify-between items-center py-2 border-b border-gray-100">
                    <span class="text-xs text-gray-600">Context Length</span>
                    <span class="text-xs font-medium text-gray-900">{{ getModelConfig().contextLength }}</span>
                  </div>
                  <div class="flex justify-between items-center py-2 border-b border-gray-100">
                    <span class="text-xs text-gray-600">Quantization</span>
                    <span class="text-xs font-medium text-gray-900">{{ getModelConfig().quantization }}</span>
                  </div>
                  <div class="flex justify-between items-center py-2 border-b border-gray-100">
                    <span class="text-xs text-gray-600">Tensor Parallel</span>
                    <span class="text-xs font-medium text-gray-900">{{ getModelConfig().tensorParallel }}</span>
                  </div>
                  <div class="flex justify-between items-center py-2">
                    <span class="text-xs text-gray-600">API Port</span>
                    <span class="text-xs font-medium text-gray-900">{{ getModelConfig().apiPort }}</span>
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
              <p class="text-gray-500 text-sm mb-4">No endpoints connected to this model</p>
              <Button size="sm" class="rounded-xl px-6 py-3">
                <Plus class="h-4 w-4 mr-2" />
                Create Endpoint
              </Button>
            </div>
          </div>
        </TabsContent>

        <!-- Analytics Tab Content -->
        <TabsContent value="analytics" class="space-y-6">
          <!-- Analytics Summary -->
          <div class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
            <div class="grid grid-cols-2 md:grid-cols-6 gap-8">
              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Total Earnings</p>
                <p class="text-sm font-medium text-green-600">{{ getEarnings().total }}</p>
              </div>
              
              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">This Month</p>
                <p class="text-sm font-medium text-green-600">{{ getEarnings().thisMonth }}</p>
              </div>
              
              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Total Requests</p>
                <p class="text-sm font-medium text-blue-600">{{ getUsageStats().totalRequests }}</p>
              </div>

              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Success Rate</p>
                <p class="text-sm font-medium text-green-600">{{ getUsageStats().successRate }}</p>
              </div>

              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Active Users</p>
                <p class="text-sm font-medium text-gray-900">{{ getUsageStats().activeUsers }}</p>
              </div>

              <div class="text-center">
                <p class="text-xs text-gray-600 mb-1">Growth</p>
                <p class="text-sm font-medium text-green-600">{{ getEarnings().growth }}</p>
              </div>
            </div>
          </div>

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

          <!-- Revenue Breakdown -->
          <div class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between mb-8">
              <h2 class="text-lg font-semibold text-gray-900 flex items-center gap-2">Revenue Breakdown</h2>
              <Button variant="outline" size="sm" class="rounded-xl px-4 py-2.5">
                <Download class="h-4 w-4 mr-2" />
                Export Report
              </Button>
            </div>
            
            <div class="space-y-6">
              <div class="flex justify-between items-center py-4 border-b border-gray-100">
                <span class="text-xs text-gray-600">Average per Request</span>
                <span class="text-xs font-medium text-gray-900">$0.053</span>
              </div>
              <div class="flex justify-between items-center py-4 border-b border-gray-100">
                <span class="text-xs text-gray-600">Peak Hour Revenue</span>
                <span class="text-xs font-medium text-gray-900">$127.40/hr</span>
              </div>
              <div class="flex justify-between items-center py-4 border-b border-gray-100">
                <span class="text-xs text-gray-600">Total Tokens Processed</span>
                <span class="text-xs font-medium text-blue-600">2.4M</span>
              </div>
              <div class="flex justify-between items-center py-4">
                <span class="text-xs text-gray-600">Cost per Token</span>
                <span class="text-xs font-medium text-gray-900">$0.00012</span>
              </div>
            </div>
          </div>

          <!-- Request Distribution -->
          <div class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">Request Distribution by Endpoint ({{ connectedEndpoints.length }})</h2>
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
                    <p class="text-xs text-gray-500 mt-1">{{ getEndpointRequests(endpoint.name) }} requests • {{ getEndpointPercentage(endpoint.name) }}% of total</p>
                  </div>
                </div>
                <div class="flex items-center gap-4">
                  <div class="flex-1 bg-gray-200 rounded-full h-2 w-24">
                    <div
                      class="h-2 rounded-full transition-all duration-300"
                      :style="{
                        width: getEndpointPercentage(endpoint.name) + '%',
                        backgroundColor: getEndpointColor(endpoint.name),
                      }"
                    ></div>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="text-center py-16">
              <Globe class="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <p class="text-gray-500 text-sm mb-4">No endpoints connected to this model</p>
              <Button size="sm" class="rounded-xl px-6 py-3">
                <Plus class="h-4 w-4 mr-2" />
                Create Endpoint
              </Button>
            </div>
          </div>
        </TabsContent>

        <!-- Logs Tab Content -->
        <TabsContent value="logs" class="space-y-6">
          <div class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between mb-8">
              <h2 class="text-lg font-semibold text-gray-900 flex items-center gap-2">Model Logs</h2>
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

  <!-- Create Model Dialog -->
  <CreateModelDialog
    v-model:open="showEditDialog"
    :model="model"
    @model-updated="handleModelUpdated"
    @update:open="!$event && handleDialogClose()"
  />

  <!-- Delete Confirmation Dialog -->
  <DeleteConfirmationDialog
    v-model:open="showDeleteDialog"
    item-type="Model"
    :item-name="model?.name || ''"
    :dependencies="modelDependencies"
    dependency-type="endpoint"
    @confirm="confirmDelete"
    @cancel="cancelDelete"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { 
  Brain, 
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
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import CreateModelDialog from '@/components/CreateModelDialog.vue'
import DeleteConfirmationDialog from '@/components/DeleteConfirmationDialog.vue'
import { mockModels, type Model } from '@/stores/models'
import { getEndpointsForModel } from '@/stores/mockEndpoints'
import { getMockAnalytics, getMockEndpointDistribution } from '@/stores/mockData'
import { formatDate } from '@/lib/formatters'
import { useNavigation } from '@/composables/useNavigation'
import { useErrorHandling } from '@/composables/useErrorHandling'

// Mock data now imported from centralized store

const route = useRoute()
const { goToModels } = useNavigation()
const { useAsyncOperation } = useErrorHandling()

const error = ref(false)
const model = ref<Model | null>(null)
const showEditDialog = ref(false)
const showDeleteDialog = ref(false)
// Dependencies for delete dialog
const modelDependencies = computed(() => {
  if (!model.value || model.value.endpointCount === 0) return []

  return getEndpointsForModel(model.value.id).map((endpoint) => ({
    id: endpoint.id,
    name: endpoint.name,
  }))
})
const selectedPeriod = ref('Daily')
const selectedLogLevel = ref('ALL')
const autoRefresh = ref(false)
const isRefreshing = ref(false)
const refreshInterval = ref<number | null>(null)
const showAdvancedConfig = ref(false)

const connectedEndpoints = computed(() => {
  if (!model.value) return []
  return getEndpointsForModel(model.value.id)
})

// Utility functions now imported from @/utils/

const getUsageStats = () => {
  const analytics = getMockAnalytics('model')
  return {
    totalRequests: analytics.totalRequests,
    successRate: analytics.successRate,
    thisMonth: analytics.thisMonth,
    activeUsers: analytics.activeUsers,
  }
}

const getEarnings = () => {
  const analytics = getMockAnalytics('model')
  return {
    total: analytics.totalEarnings,
    thisMonth: analytics.monthlyEarnings,
    lastMonth: '$289.15', // Could be calculated from historical data
    avgPerRequest: '$0.053', // Could be calculated from totals
    growth: analytics.growth,
  }
}

const getEndpointDistribution = () => {
  return getMockEndpointDistribution(model.value?.id)
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

// Utility functions now handled by DeleteConfirmationDialog component

const editModel = () => {
  showEditDialog.value = true
}

const deleteModel = () => {
  showDeleteDialog.value = true
}

const handleModelUpdated = () => {
  console.log('Model updated successfully')
  showEditDialog.value = false
  // In a real app, you might want to refresh the model data here
}

const handleDialogClose = () => {
  showEditDialog.value = false
}

const { execute: executeDelete } = useAsyncOperation(async (modelId: string) => {
  // Simulate API call
  await new Promise((resolve) => setTimeout(resolve, 1000))

  // In a real app, this would call an API to delete the model
  console.log('Deleting model:', modelId)

  // Simulate potential error
  if (Math.random() < 0.1) {
    // 10% chance of error for demo
    throw new Error('Failed to delete model')
  }

  return true
})

const confirmDelete = async () => {
  if (model.value) {
    try {
      await executeDelete(model.value.id)
      goToModels()
    } catch (error) {
      // Error is automatically handled by useAsyncOperation
      console.error('Delete failed:', error)
    }
  }
}

const cancelDelete = () => {
  showDeleteDialog.value = false
}

// Model configuration getters
const getModelPath = () => {
  if (!model.value) return 'N/A'
  return model.value.type === 'vllm' 
    ? `http://localhost:8000/v1/models/${model.value.name.toLowerCase().replace(/\s+/g, '-')}`
    : model.value.type === 'ollama' 
    ? `http://localhost:11434/api/models/${model.value.name.toLowerCase().replace(/\s+/g, '-')}`
    : `http://localhost:8080/v1/models/${model.value.name.toLowerCase().replace(/\s+/g, '-')}`
}

const getModelConfig = () => {
  return {
    maxTokens: '4096',
    temperature: '0.7',
    gpuMemory: '24GB',
    contextLength: '8192',
    quantization: 'FP16',
    tensorParallel: '2',
    apiPort: '8000'
  }
}

// Mock log data
const mockLogs = ref([
  {
    id: '1',
    timestamp: '2024-10-27 14:32:15',
    level: 'INFO',
    message: 'Model successfully loaded and ready for inference'
  },
  {
    id: '2', 
    timestamp: '2024-10-27 14:32:16',
    level: 'INFO',
    message: 'GPU memory allocated: 18.2GB / 24GB'
  },
  {
    id: '3',
    timestamp: '2024-10-27 14:35:22',
    level: 'WARN',
    message: 'High GPU utilization: 95% - consider load balancing'
  },
  {
    id: '4',
    timestamp: '2024-10-27 14:38:45',
    level: 'ERROR', 
    message: 'Request timeout: inference took longer than 30s threshold'
  },
  {
    id: '5',
    timestamp: '2024-10-27 14:40:12',
    level: 'INFO',
    message: 'Checkpoint saved successfully'
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
  const modelSlug = route.params.slug as string
  const foundModel = mockModels.find((m) => m.name === modelSlug)

  if (foundModel) {
    model.value = foundModel
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
