<template>
  <ErrorBoundary>
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Breadcrumb Navigation -->
    <BreadcrumbNav :breadcrumbs="[
      { label: 'Models', route: { name: 'models' }, icon: Brain },
      { label: model?.name || 'Loading...' }
    ]" />

    <!-- Error State -->
    <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
      <h3 class="text-lg font-medium text-red-900 mb-2">Model not found</h3>
      <p class="text-red-700 mb-4">The model you're looking for doesn't exist or has been deleted.</p>
      <Button @click="goToModels" variant="outline">
        Back to Models
      </Button>
    </div>

    <!-- Model Details -->
    <div v-else-if="model" class="space-y-6">
      <!-- Header -->
      <div class="bg-white border border-gray-200 rounded-lg p-6">
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-4">
            <div :class="[
              'p-3 rounded-lg',
              model.type === 'vllm' ? 'bg-purple-100' : 
              model.type === 'ollama' ? 'bg-orange-100' : 
              'bg-indigo-100'
            ]">
              <IntegrationIcon :name="model.type" class="h-8 w-8" />
            </div>
            <div>
              <h1 class="text-3xl font-bold text-gray-900 mb-2">{{ model.name }}</h1>
              <p class="text-gray-600 mb-4">{{ model.description }}</p>
              <div class="flex flex-wrap items-center gap-2">
                <Badge :variant="model.status === 'running' ? 'default' : 'outline'" :class="model.status === 'running'
                  ? 'bg-green-50 text-green-700 border-green-200'
                  : 'bg-gray-50 text-gray-600 border-gray-200'">
                  <div :class="model.status === 'running'
                    ? 'w-2 h-2 bg-green-500 rounded-full mr-2'
                    : 'w-2 h-2 bg-gray-400 rounded-full mr-2'"></div>
                  {{ model.status === 'running' ? 'Running' : 'Stopped' }}
                </Badge>
                <Badge variant="outline" class="bg-blue-50 text-blue-700 border-blue-200">
                  <div class="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                  {{ model.type.charAt(0).toUpperCase() + model.type.slice(1) }}
                </Badge>
                <!-- Tags as badges -->
                <Badge v-for="tag in model.tags" :key="`tag-${tag}`" variant="outline"
                  class="bg-amber-50 text-amber-700 border-amber-200">
                  <div class="w-2 h-2 bg-amber-500 rounded-full mr-2"></div>
                  {{ tag }}
                </Badge>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <Button variant="outline" @click="editModel">
              <Edit class="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button variant="outline" class="text-red-600 hover:text-red-700" @click="deleteModel">
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
          <!-- Model Details -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Model Details</h2>
            <div class="space-y-3">
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Type:</span>
                <span class="text-sm text-gray-900">{{ model.type.charAt(0).toUpperCase() + model.type.slice(1) }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Status:</span>
                <span class="text-sm text-gray-900 capitalize">{{ model.status }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Connected Endpoints:</span>
                <span class="text-sm text-gray-900">{{ model.endpointCount }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Created:</span>
                <span class="text-sm text-gray-900">{{ formatDate(model.createdAt) }}</span>
              </div>
            </div>
          </div>

          <!-- Model Earnings -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Model Earnings</h2>
            <div class="space-y-4">
              <div class="text-center p-4 bg-green-50 rounded-lg">
                <p class="text-2xl font-bold text-green-600 mb-1">{{ getEarnings().total }}</p>
                <p class="text-sm text-green-700">Total Earnings</p>
              </div>
              <div class="space-y-3">
                <div class="flex justify-between items-center">
                  <span class="text-sm text-gray-600">This Month:</span>
                  <span class="text-sm text-green-600 font-semibold">{{ getEarnings().thisMonth }}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-sm text-gray-600">Growth:</span>
                  <span class="text-sm text-green-600 font-semibold">{{ getEarnings().growth }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Usage Statistics -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Usage Statistics</h2>
            <div class="space-y-3">
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Total Requests:</span>
                <span class="text-sm text-gray-900 font-semibold">{{ getUsageStats().totalRequests }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Success Rate:</span>
                <span class="text-sm text-green-600 font-semibold">{{ getUsageStats().successRate }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">This Month:</span>
                <span class="text-sm text-gray-900 font-semibold">{{ getUsageStats().thisMonth }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Active Users:</span>
                <span class="text-sm text-gray-900 font-semibold">{{ getUsageStats().activeUsers }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Model Configuration -->
        <div class="bg-white border border-gray-200 rounded-lg p-6">
          <h2 class="text-2xl font-semibold text-gray-900 mb-4">Model Configuration</h2>
          <div class="min-h-[300px] flex items-center justify-center border-2 border-dashed border-gray-300 rounded-lg bg-gray-50">
            <div class="text-center">
              <p class="text-gray-500 text-lg mb-2">Configuration for {{ model.type.charAt(0).toUpperCase() + model.type.slice(1) }}</p>
              <p class="text-gray-400 text-sm">Model configuration details will be displayed here</p>
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
          <div class="h-64 flex items-center justify-center border border-dashed border-gray-300 rounded-lg bg-gray-50">
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
                    <p class="text-xs text-gray-600">{{ endpoint.description || 'API endpoint' }}</p>
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
                  <span class="text-xs text-gray-900 font-semibold">{{ getEndpointPercentage(endpoint.name) }}% of total</span>
                </div>
                <div class="flex items-center gap-3">
                  <div class="flex-1 bg-gray-200 rounded-full h-2">
                    <div 
                      class="h-2 rounded-full transition-all duration-300" 
                      :style="{ 
                        width: getEndpointPercentage(endpoint.name) + '%', 
                        backgroundColor: getEndpointColor(endpoint.name) 
                      }"
                    ></div>
                  </div>
                  <span class="text-xs text-gray-600">{{ getEndpointRequests(endpoint.name) }} requests</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="text-center py-8">
            <Globe class="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 class="text-lg font-medium text-gray-900 mb-2">No endpoints connected</h3>
            <p class="text-gray-600 mb-4">This model is not currently connected to any endpoints.</p>
            <Button>
              <Plus class="h-4 w-4 mr-2" />
              Create Endpoint
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>
  </ErrorBoundary>

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
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Brain, Edit, Trash2, Globe, Plus, ExternalLink } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import CreateModelDialog from '@/components/CreateModelDialog.vue'
import DeleteConfirmationDialog from '@/components/DeleteConfirmationDialog.vue'
import BreadcrumbNav from '@/components/BreadcrumbNav.vue'
import { mockModels, type Model } from '@/stores/models'
import { mockModelEndpoints, getEndpointsForModel, type ModelEndpoint } from '@/stores/mockEndpoints'
import { getMockAnalytics, getMockEndpointDistribution } from '@/stores/mockData'
import { formatDate } from '@/lib/formatters'
import { useNavigation } from '@/composables/useNavigation'
import { useErrorHandling } from '@/composables/useErrorHandling'
import ErrorBoundary from '@/components/ErrorBoundary.vue'

// Mock data now imported from centralized store

const route = useRoute()
const { goToModels } = useNavigation()
const { useAsyncOperation, setError } = useErrorHandling()

const error = ref(false)
const model = ref<Model | null>(null)
const showEditDialog = ref(false)
const showDeleteDialog = ref(false)
// Dependencies for delete dialog
const modelDependencies = computed(() => {
  if (!model.value || model.value.endpointCount === 0) return []
  
  return getEndpointsForModel(model.value.id)
    .map(endpoint => ({ id: endpoint.id, name: endpoint.name }))
})
const selectedPeriod = ref('Daily')

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
    activeUsers: analytics.activeUsers
  }
}

const getEarnings = () => {
  const analytics = getMockAnalytics('model')
  return {
    total: analytics.totalEarnings,
    thisMonth: analytics.monthlyEarnings,
    lastMonth: '$289.15', // Could be calculated from historical data
    avgPerRequest: '$0.053', // Could be calculated from totals
    growth: analytics.growth
  }
}

const getEndpointDistribution = () => {
  return getMockEndpointDistribution(model.value?.id)
}

const getEndpointPercentage = (endpointName: string) => {
  const distribution = getEndpointDistribution()
  const endpoint = distribution.find(e => e.name === endpointName)
  return endpoint?.percentage || 0
}

const getEndpointColor = (endpointName: string) => {
  const distribution = getEndpointDistribution()
  const endpoint = distribution.find(e => e.name === endpointName)
  return endpoint?.color || '#6B7280'
}

const getEndpointRequests = (endpointName: string) => {
  const distribution = getEndpointDistribution()
  const endpoint = distribution.find(e => e.name === endpointName)
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

const { execute: executeDelete, loading: isDeleting } = useAsyncOperation(
  async (modelId: string) => {
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    // In a real app, this would call an API to delete the model
    console.log('Deleting model:', modelId)
    
    // Simulate potential error
    if (Math.random() < 0.1) { // 10% chance of error for demo
      throw new Error('Failed to delete model')
    }
    
    return true
  }
)

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

onMounted(() => {
  const modelSlug = route.params.slug as string
  const foundModel = mockModels.find(m => m.name === modelSlug)
  
  if (foundModel) {
    model.value = foundModel
  } else {
    error.value = true
  }
})
</script>