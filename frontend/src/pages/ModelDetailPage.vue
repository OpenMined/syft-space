<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Breadcrumb Navigation -->
    <nav class="flex mb-12" aria-label="Breadcrumb">
      <ol class="flex items-center space-x-3">
        <li>
          <router-link
            to="/models"
            class="text-muted-foreground hover:text-foreground body-sm font-medium flex items-center transition-colors"
          >
            <Brain class="h-4 w-4 mr-2" />
            Models
          </router-link>
        </li>
        <li class="flex items-center">
          <ChevronRight class="h-4 w-4 text-muted-foreground mx-3" />
          <span class="text-foreground body-sm font-medium">{{ model?.name || 'Loading...' }}</span>
        </li>
      </ol>
    </nav>

    <!-- Error State -->
    <div
      v-if="error"
      class="bg-destructive/10 border border-destructive/20 rounded-2xl p-8 text-center"
    >
      <h3 class="heading-3 text-destructive mb-2">Model not found</h3>
      <p class="text-destructive mb-4">
        The model you're looking for doesn't exist or has been deleted.
      </p>
      <Button @click="goToModels" variant="outline"> Back to Models </Button>
    </div>

    <!-- Model Details -->
    <div v-else-if="model" class="space-y-6">
      <!-- Header -->
      <div class="bg-card/60 backdrop-blur-sm border border-border rounded-3xl p-8 mb-8">
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-6">
            <div
              :class="[
                'p-4 rounded-2xl shadow-sm',
                model.type === 'vllm'
                  ? 'bg-purple-50 border border-border'
                  : model.type === 'ollama'
                    ? 'bg-orange-50 border border-border'
                    : 'bg-indigo-50 border border-border',
              ]"
            >
              <IntegrationIcon :name="model.type" class="h-8 w-8" />
            </div>
            <div>
              <h1 class="heading-2 mb-2">{{ model.name }}</h1>
              <p class="body-lg text-muted-foreground mb-4">{{ model.description }}</p>
              <div class="flex flex-wrap items-center gap-3">
                <Badge
                  variant="outline"
                  :class="
                    model.status === 'running'
                      ? 'bg-success/10 text-success-foreground border border-success/20 px-3 py-1.5 rounded-full'
                      : 'bg-muted text-muted-foreground border border-border px-3 py-1.5 rounded-full'
                  "
                >
                  <div
                    :class="
                      model.status === 'running'
                        ? 'w-2 h-2 bg-success rounded-full mr-2'
                        : 'w-2 h-2 bg-muted-foreground rounded-full mr-2'
                    "
                  ></div>
                  {{ model.status === 'running' ? 'Running' : 'Stopped' }}
                </Badge>
                <Badge
                  variant="outline"
                  class="bg-primary/10 text-primary-foreground border border-primary/20 px-3 py-1.5 rounded-full"
                >
                  {{ model.type.charAt(0).toUpperCase() + model.type.slice(1) }}
                </Badge>
                <Badge
                  v-for="tag in model.tags"
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
            <Button variant="outline" @click="editModel">
              <Edit class="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button
              variant="outline"
              class="text-destructive hover:text-destructive border-destructive/50 hover:border-destructive"
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
        <TabsList
          class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-3"
        >
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
          <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
            <div class="grid grid-cols-2 md:grid-cols-6 gap-8">
              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Type</p>
                <p class="body-sm font-medium text-foreground">
                  {{ model.type.charAt(0).toUpperCase() + model.type.slice(1) }}
                </p>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Status</p>
                <div class="flex items-center justify-center gap-2">
                  <div
                    :class="[
                      'w-2.5 h-2.5 rounded-full',
                      model.status === 'running' ? 'bg-green-500 dark:bg-green-400' : 'bg-muted',
                    ]"
                  ></div>
                  <p class="body-sm font-medium text-foreground capitalize">{{ model.status }}</p>
                </div>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Endpoints</p>
                <p class="body-sm font-medium text-foreground">{{ model.endpointCount }}</p>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Requests</p>
                <p class="body-sm font-medium text-primary">
                  {{ getUsageStats().totalRequests }}
                </p>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Earnings</p>
                <p class="body-sm font-medium text-success">
                  {{ getEarnings().total }}
                </p>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Created</p>
                <p class="body-sm font-medium text-foreground">{{ formatDate(model.createdAt) }}</p>
              </div>
            </div>
          </div>

          <!-- Model Configuration -->
          <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between mb-8">
              <h2 class="heading-3">Model Configuration</h2>
              <div class="flex items-center gap-3">
                <Button variant="outline" size="sm">
                  <Edit class="h-4 w-4 mr-2" />
                  Edit Settings
                </Button>
              </div>
            </div>

            <!-- Basic Settings -->
            <div class="space-y-6">
              <div class="flex justify-between items-center py-4 border-b border-border">
                <span class="body-sm text-muted-foreground">URL</span>
                <span class="body-sm font-medium text-foreground">{{ getModelPath() }}</span>
              </div>
              <div class="flex justify-between items-center py-4 border-b border-border">
                <span class="body-sm text-muted-foreground">Max Tokens</span>
                <span class="body-sm font-medium text-foreground">{{
                  getModelConfig().maxTokens
                }}</span>
              </div>
              <div class="flex justify-between items-center py-4 border-b border-border">
                <span class="body-sm text-muted-foreground">Temperature</span>
                <span class="body-sm font-medium text-foreground">{{
                  getModelConfig().temperature
                }}</span>
              </div>
              <div class="flex justify-between items-center py-4">
                <span class="body-sm text-muted-foreground">Connection Status</span>
                <div class="flex items-center gap-3">
                  <div class="w-2.5 h-2.5 bg-success rounded-full"></div>
                  <span class="body-sm font-medium text-success">Connected</span>
                </div>
              </div>
            </div>

            <!-- Advanced Settings (Collapsible) -->
            <div v-if="showAdvancedConfig" class="mt-6 pt-6 border-t border-border">
              <div class="space-y-6">
                <h3 class="body-sm font-semibold text-foreground mb-4">Advanced Settings</h3>
                <div class="space-y-3">
                  <div class="flex justify-between items-center py-2 border-b border-border">
                    <span class="body-sm text-muted-foreground">GPU Memory</span>
                    <span class="body-sm font-medium text-foreground">{{
                      getModelConfig().gpuMemory
                    }}</span>
                  </div>
                  <div class="flex justify-between items-center py-2 border-b border-border">
                    <span class="body-sm text-muted-foreground">Context Length</span>
                    <span class="body-sm font-medium text-foreground">{{
                      getModelConfig().contextLength
                    }}</span>
                  </div>
                  <div class="flex justify-between items-center py-2 border-b border-border">
                    <span class="body-sm text-muted-foreground">Quantization</span>
                    <span class="body-sm font-medium text-foreground">{{
                      getModelConfig().quantization
                    }}</span>
                  </div>
                  <div class="flex justify-between items-center py-2 border-b border-border">
                    <span class="body-sm text-muted-foreground">Tensor Parallel</span>
                    <span class="body-sm font-medium text-foreground">{{
                      getModelConfig().tensorParallel
                    }}</span>
                  </div>
                  <div class="flex justify-between items-center py-2">
                    <span class="body-sm text-muted-foreground">API Port</span>
                    <span class="body-sm font-medium text-foreground">{{
                      getModelConfig().apiPort
                    }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Show Advanced Button (Bottom Right) -->
            <div class="flex justify-end mt-6 pt-6 border-t border-border">
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
                class="flex items-center justify-between py-6 px-6 bg-muted/50 border border-border rounded-2xl hover:bg-muted/80 transition-all"
              >
                <div class="flex items-center gap-4">
                  <div class="p-3 bg-primary/10 border border-primary/20 rounded-xl">
                    <Globe class="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <h3 class="body-sm font-medium text-foreground">{{ endpoint.name }}</h3>
                    <p class="body-sm text-muted-foreground mt-1">
                      {{ endpoint.description || 'API endpoint' }}
                    </p>
                  </div>
                </div>
                <Button variant="outline" size="sm">
                  <ExternalLink class="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div v-else class="text-center py-16">
              <Globe class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p class="text-muted-foreground body-sm mb-4">No endpoints connected to this model</p>
              <Button size="sm">
                <Plus class="h-4 w-4 mr-2" />
                Create Endpoint
              </Button>
            </div>
          </div>
        </TabsContent>

        <!-- Analytics Tab Content -->
        <TabsContent value="analytics" class="space-y-6">
          <!-- Analytics Summary -->
          <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
            <div class="grid grid-cols-2 md:grid-cols-6 gap-8">
              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Total Earnings</p>
                <p class="body-sm font-medium text-success">{{ getEarnings().total }}</p>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">This Month</p>
                <p class="body-sm font-medium text-success">{{ getEarnings().thisMonth }}</p>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Total Requests</p>
                <p class="body-sm font-medium text-primary">{{ getUsageStats().totalRequests }}</p>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Success Rate</p>
                <p class="body-sm font-medium text-success">{{ getUsageStats().successRate }}</p>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Active Users</p>
                <p class="body-sm font-medium text-foreground">{{ getUsageStats().activeUsers }}</p>
              </div>

              <div class="text-center">
                <p class="body-sm text-muted-foreground mb-1">Growth</p>
                <p class="body-sm font-medium text-success">{{ getEarnings().growth }}</p>
              </div>
            </div>
          </div>

          <!-- Access Trends Chart -->
          <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between mb-8">
              <h2 class="heading-3 text-foreground flex items-center gap-2">Access Trends</h2>
              <div class="flex items-center gap-2">
                <Button
                  v-for="period in ['Daily', 'Weekly', 'Monthly']"
                  :key="period"
                  size="sm"
                  :variant="selectedPeriod === period ? 'default' : 'outline'"
                  @click="selectedPeriod = period"
                  class="body-sm rounded-xl px-4 py-2"
                >
                  {{ period }}
                </Button>
              </div>
            </div>
            <div
              class="h-80 flex items-center justify-center border border-dashed border-border rounded-2xl bg-muted/30"
            >
              <div class="text-center">
                <p class="text-muted-foreground body-lg mb-1">{{ selectedPeriod }} Access Chart</p>
                <p class="text-muted-foreground body-sm">Chart visualization coming soon</p>
              </div>
            </div>
          </div>

          <!-- Revenue Breakdown -->
          <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between mb-8">
              <h2 class="heading-3 text-foreground flex items-center gap-2">Revenue Breakdown</h2>
              <Button variant="outline" size="sm" class="rounded-xl px-4 py-2.5">
                <Download class="h-4 w-4 mr-2" />
                Export Report
              </Button>
            </div>

            <div class="space-y-6">
              <div class="flex justify-between items-center py-4 border-b border-border">
                <span class="body-sm text-muted-foreground">Average per Request</span>
                <span class="body-sm font-medium text-foreground">$0.053</span>
              </div>
              <div class="flex justify-between items-center py-4 border-b border-border">
                <span class="body-sm text-muted-foreground">Peak Hour Revenue</span>
                <span class="body-sm font-medium text-foreground">$127.40/hr</span>
              </div>
              <div class="flex justify-between items-center py-4 border-b border-border">
                <span class="body-sm text-muted-foreground">Total Tokens Processed</span>
                <span class="body-sm font-medium text-primary">2.4M</span>
              </div>
              <div class="flex justify-between items-center py-4">
                <span class="body-sm text-muted-foreground">Cost per Token</span>
                <span class="body-sm font-medium text-foreground">$0.00012</span>
              </div>
            </div>
          </div>

          <!-- Request Distribution -->
          <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
            <h2 class="heading-3 text-foreground mb-4 flex items-center gap-2">
              Request Distribution by Endpoint ({{ connectedEndpoints.length }})
            </h2>
            <div v-if="connectedEndpoints.length > 0" class="space-y-4">
              <div
                v-for="endpoint in connectedEndpoints"
                :key="endpoint.id"
                class="flex items-center justify-between py-6 px-6 bg-muted/50 border border-border rounded-2xl hover:bg-muted/80 transition-all"
              >
                <div class="flex items-center gap-4">
                  <div class="p-3 bg-primary/10 border border-primary/20 rounded-xl">
                    <Globe class="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <h3 class="body-sm font-medium text-foreground">{{ endpoint.name }}</h3>
                    <p class="body-sm text-muted-foreground mt-1">
                      {{ getEndpointRequests(endpoint.name) }} requests •
                      {{ getEndpointPercentage(endpoint.name) }}% of total
                    </p>
                  </div>
                </div>
                <div class="flex items-center gap-4">
                  <div class="flex-1 bg-muted rounded-full h-2 w-24">
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
              <Globe class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p class="text-muted-foreground body-sm mb-4">No endpoints connected to this model</p>
              <Button size="sm">
                <Plus class="h-4 w-4 mr-2" />
                Create Endpoint
              </Button>
            </div>
          </div>
        </TabsContent>

        <!-- Logs Tab Content -->
        <TabsContent value="logs" class="space-y-6">
          <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
            <div class="flex items-center justify-between mb-8">
              <h2 class="heading-3 text-foreground flex items-center gap-2">Model Logs</h2>
              <div class="flex items-center gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  @click="refreshLogs"
                  class="rounded-xl px-4 py-2.5"
                >
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
            <div class="flex items-center gap-6 mb-8 pb-6 border-b border-border">
              <div class="flex items-center gap-3">
                <span class="body-sm font-medium text-muted-foreground">Level:</span>
                <div class="flex gap-2">
                  <Button
                    v-for="level in ['ALL', 'INFO', 'WARN', 'ERROR']"
                    :key="level"
                    size="sm"
                    :variant="selectedLogLevel === level ? 'default' : 'outline'"
                    @click="selectedLogLevel = level"
                    class="body-sm rounded-xl px-4 py-2"
                  >
                    {{ level }}
                  </Button>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <span class="body-sm font-medium text-muted-foreground">Auto-refresh:</span>
                <Button
                  size="sm"
                  :variant="autoRefresh ? 'default' : 'outline'"
                  @click="toggleAutoRefresh"
                  class="body-sm rounded-xl px-4 py-2"
                >
                  {{ autoRefresh ? 'ON' : 'OFF' }}
                </Button>
              </div>
            </div>

            <!-- Logs Display -->
            <div
              class="bg-card/95 rounded-2xl p-6 h-96 overflow-y-auto font-mono body-sm border border-border"
            >
              <div
                v-for="log in filteredLogs"
                :key="log.id"
                :class="[
                  'mb-2 leading-relaxed',
                  log.level === 'INFO'
                    ? 'text-green-400'
                    : log.level === 'WARN'
                      ? 'text-yellow-400'
                      : log.level === 'ERROR'
                        ? 'text-red-400'
                        : 'text-muted-foreground',
                ]"
              >
                <span class="text-muted-foreground">[{{ log.timestamp }}]</span>
                <span
                  :class="[
                    'ml-2 px-2 py-1 rounded text-xs font-bold',
                    log.level === 'INFO'
                      ? 'bg-green-900 text-green-200'
                      : log.level === 'WARN'
                        ? 'bg-yellow-900 text-yellow-200'
                        : log.level === 'ERROR'
                          ? 'bg-red-900 text-red-200'
                          : 'bg-muted text-muted-foreground',
                  ]"
                  >{{ log.level }}</span
                >
                <span class="ml-2">{{ log.message }}</span>
              </div>
              <div v-if="filteredLogs.length === 0" class="text-muted-foreground text-center py-8">
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
  ChevronDown,
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
  return endpoint?.color || 'hsl(var(--muted-foreground))'
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
    apiPort: '8000',
  }
}

// Mock log data
const mockLogs = ref([
  {
    id: '1',
    timestamp: '2024-10-27 14:32:15',
    level: 'INFO',
    message: 'Model successfully loaded and ready for inference',
  },
  {
    id: '2',
    timestamp: '2024-10-27 14:32:16',
    level: 'INFO',
    message: 'GPU memory allocated: 18.2GB / 24GB',
  },
  {
    id: '3',
    timestamp: '2024-10-27 14:35:22',
    level: 'WARN',
    message: 'High GPU utilization: 95% - consider load balancing',
  },
  {
    id: '4',
    timestamp: '2024-10-27 14:38:45',
    level: 'ERROR',
    message: 'Request timeout: inference took longer than 30s threshold',
  },
  {
    id: '5',
    timestamp: '2024-10-27 14:40:12',
    level: 'INFO',
    message: 'Checkpoint saved successfully',
  },
])

const filteredLogs = computed(() => {
  if (selectedLogLevel.value === 'ALL') {
    return mockLogs.value
  }
  return mockLogs.value.filter((log) => log.level === selectedLogLevel.value)
})

const refreshLogs = async () => {
  isRefreshing.value = true
  // Simulate API call
  await new Promise((resolve) => setTimeout(resolve, 1000))

  // Add a new mock log entry
  const newLog = {
    id: Date.now().toString(),
    timestamp: new Date().toLocaleString('sv-SE').replace(' ', ' '),
    level: ['INFO', 'WARN', 'ERROR'][Math.floor(Math.random() * 3)] as 'INFO' | 'WARN' | 'ERROR',
    message: 'New log entry generated at ' + new Date().toLocaleTimeString(),
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
