<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Breadcrumb Navigation -->
    <nav class="flex mb-6" aria-label="Breadcrumb">
      <ol class="flex items-center space-x-2">
        <li>
          <router-link
            to="/endpoints"
            class="text-gray-500 hover:text-gray-700 text-sm font-medium flex items-center"
          >
            <Server class="h-4 w-4 mr-1" />
            Endpoints
          </router-link>
        </li>
        <li class="flex items-center">
          <ChevronRight class="h-4 w-4 text-gray-400 mx-2" />
          <span class="text-gray-900 text-sm font-medium">{{
            endpoint?.name || 'Loading...'
          }}</span>
        </li>
      </ol>
    </nav>
    <!-- Error State -->
    <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
      <h3 class="text-lg font-medium text-red-900 mb-2">Endpoint not found</h3>
      <p class="text-red-700 mb-4">
        The endpoint you're looking for doesn't exist or has been deleted.
      </p>
      <Button @click="$router.push('/endpoints')" variant="outline"> Back to Endpoints </Button>
    </div>

    <!-- Endpoint details -->
    <div v-else-if="endpoint" class="space-y-6">
      <!-- Header -->
      <div class="bg-white border border-gray-200 rounded-lg p-6">
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-4">
            <div class="p-3 rounded-lg bg-green-100">
              <Server class="h-8 w-8" />
            </div>
            <div>
              <h1 class="text-3xl font-bold text-gray-900 mb-2">{{ endpoint.name }}</h1>
              <p class="text-gray-600 mb-4">{{ endpoint.summary }}</p>
              <div class="flex flex-wrap items-center gap-2">
                <Badge
                  :variant="endpoint.status === 'published' ? 'default' : 'outline'"
                  :class="
                    endpoint.status === 'published'
                      ? 'bg-green-50 text-green-700 border-green-200'
                      : 'bg-gray-50 text-gray-600 border-gray-200'
                  "
                >
                  <div
                    :class="
                      endpoint.status === 'published'
                        ? 'w-2 h-2 bg-green-500 rounded-full mr-2'
                        : 'w-2 h-2 bg-gray-400 rounded-full mr-2'
                    "
                  ></div>
                  {{ endpoint.status === 'published' ? 'Published' : 'Draft' }}
                </Badge>
                <Badge
                  :variant="endpoint.mcpCompatible ? 'default' : 'outline'"
                  :class="
                    endpoint.mcpCompatible
                      ? 'bg-blue-50 text-blue-700 border-blue-200'
                      : 'bg-gray-50 text-gray-600 border-gray-200'
                  "
                >
                  <div
                    :class="
                      endpoint.mcpCompatible
                        ? 'w-2 h-2 bg-blue-500 rounded-full mr-2'
                        : 'w-2 h-2 bg-gray-400 rounded-full mr-2'
                    "
                  ></div>
                  {{ endpoint.mcpCompatible ? 'MCP Compatible' : 'Not MCP Compatible' }}
                </Badge>
                <!-- Languages as badges -->
                <Badge
                  v-for="language in endpoint.languages"
                  :key="`lang-${language}`"
                  variant="outline"
                  class="bg-amber-50 text-amber-700 border-amber-200"
                >
                  <div class="w-2 h-2 bg-amber-500 rounded-full mr-2"></div>
                  {{ language.charAt(0).toUpperCase() + language.slice(1) }}
                </Badge>
                <!-- Domains as badges -->
                <Badge
                  v-for="domain in endpoint.domains"
                  :key="`domain-${domain}`"
                  variant="outline"
                  class="bg-purple-50 text-purple-700 border-purple-200"
                >
                  <div class="w-2 h-2 bg-purple-500 rounded-full mr-2"></div>
                  {{ domain.charAt(0).toUpperCase() + domain.slice(1) }}
                </Badge>
                <!-- Additional tags as badges -->
                <Badge
                  v-for="tag in endpoint.tags.filter(
                    (t) => !t.startsWith('domain:') && !t.startsWith('language:'),
                  )"
                  :key="tag"
                  variant="outline"
                  class="bg-gray-50 text-gray-700 border-gray-200"
                >
                  <div class="w-2 h-2 bg-gray-500 rounded-full mr-2"></div>
                  {{ tag }}
                </Badge>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <template v-if="endpoint.status === 'draft'">
              <Button
                variant="outline"
                class="border-purple-600 text-purple-600 hover:bg-purple-50 hover:text-purple-700"
              >
                <Send class="h-4 w-4 mr-2" />
                Publish
              </Button>
              <Button variant="outline">
                <Edit class="h-4 w-4 mr-2" />
                Edit
              </Button>
              <Button variant="outline" class="text-red-600 hover:text-red-700">
                <Trash2 class="h-4 w-4 mr-2" />
                Delete
              </Button>
            </template>
            <template v-else>
              <Button variant="outline">
                <EyeOff class="h-4 w-4 mr-2" />
                Unpublish
              </Button>
            </template>
          </div>
        </div>
      </div>

      <!-- Endpoint Revenue -->
      <div class="bg-white border border-gray-200 rounded-lg p-6">
        <h2 class="text-2xl font-semibold text-gray-900 mb-6">Endpoint Revenue</h2>
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div class="text-center p-4 bg-green-50 rounded-lg">
            <p class="text-3xl font-bold text-green-600 mb-1">{{ getEndpointRevenue().total }}</p>
            <p class="text-sm text-green-700">Total Revenue</p>
          </div>
          <div class="space-y-3">
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-600">This Month:</span>
              <span class="text-sm text-green-600 font-semibold">{{
                getEndpointRevenue().thisMonth
              }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-600">Last Month:</span>
              <span class="text-sm text-gray-900 font-semibold">{{
                getEndpointRevenue().lastMonth
              }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-600">Growth:</span>
              <span class="text-sm text-green-600 font-semibold">{{
                getEndpointRevenue().growth
              }}</span>
            </div>
          </div>
          <div class="space-y-3">
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-600">Avg per Request:</span>
              <span class="text-sm text-gray-900 font-semibold">{{
                getEndpointRevenue().avgPerRequest
              }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-600">Revenue Rate:</span>
              <span class="text-sm text-gray-900 font-semibold">{{
                getEndpointRevenue().revenueRate
              }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-600">Paid Users:</span>
              <span class="text-sm text-gray-900 font-semibold">{{
                getEndpointRevenue().paidUsers
              }}</span>
            </div>
          </div>
          <div class="space-y-3">
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-600">Free Requests:</span>
              <span class="text-sm text-gray-900 font-semibold">{{
                getEndpointRevenue().freeRequests
              }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-600">Paid Requests:</span>
              <span class="text-sm text-gray-900 font-semibold">{{
                getEndpointRevenue().paidRequests
              }}</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-sm text-gray-600">Conversion Rate:</span>
              <span class="text-sm text-green-600 font-semibold">{{
                getEndpointRevenue().conversionRate
              }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Content Grid -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Main Content - Description -->
        <div class="lg:col-span-2 space-y-6">
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h2 class="text-2xl font-semibold text-gray-900 mb-4">Description</h2>
            <div class="prose prose-sm max-w-none text-gray-600">
              <div v-if="endpoint.description" class="markdown-content">
                <MdPreview
                  :model-value="endpoint.description"
                  preview-theme="default"
                  :show-code-row-number="false"
                />
              </div>
              <div v-else>
                {{ endpoint.summary }}
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
        </div>

        <!-- Sidebar -->
        <div class="lg:col-span-1 space-y-6">
          <!-- Endpoint Details -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Endpoint Details</h2>
            <div class="space-y-3">
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Endpoint Type:</span>
                <span class="text-sm text-gray-900">{{ getEndpointType() }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Response Type:</span>
                <span class="text-sm text-gray-900">{{ getResponseType() }}</span>
              </div>
              <div v-if="endpoint.dataSourceType" class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Data Source:</span>
                <router-link
                  :to="{
                    name: 'dataset-detail',
                    params: { slug: getDatasetSlug(endpoint.dataSourceType) },
                  }"
                  class="text-sm text-purple-600 hover:text-purple-700 hover:underline"
                >
                  {{ getDataSourceName(endpoint.dataSourceType) }}
                </router-link>
              </div>
              <div v-if="endpoint.modelType" class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Model:</span>
                <router-link
                  :to="{ name: 'model-detail', params: { slug: getModelSlug(endpoint.modelType) } }"
                  class="text-sm text-purple-600 hover:text-purple-700 hover:underline"
                >
                  {{ getModelName(endpoint.modelType) }}
                </router-link>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Status:</span>
                <span class="text-sm text-gray-900 capitalize">{{ endpoint.status }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">MCP Compatible:</span>
                <span class="text-sm text-gray-900">{{
                  endpoint.mcpCompatible ? 'Yes' : 'No'
                }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Pricing:</span>
                <span class="text-sm text-gray-900">{{ endpoint.price }}</span>
              </div>
            </div>
          </div>

          <!-- Applied Policies -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Applied Policies</h2>

            <div class="space-y-4">
              <!-- Rate Limiter -->
              <div class="border border-gray-200 rounded-lg">
                <button
                  @click="togglePolicySection('rateLimiter')"
                  class="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 rounded-lg transition-colors"
                >
                  <div class="flex items-center gap-3">
                    <div class="p-2 rounded-lg bg-green-100">
                      <Gauge class="h-4 w-4 text-green-600" />
                    </div>
                    <h4 class="font-semibold text-gray-900">Rate Limiter</h4>
                    <span class="text-xs text-gray-500">(2 rules)</span>
                  </div>
                  <ChevronDown
                    :class="[
                      'h-4 w-4 text-gray-500 transition-transform duration-200',
                      expandedSections.rateLimiter ? 'rotate-180' : '',
                    ]"
                  />
                </button>

                <div v-if="expandedSections.rateLimiter" class="px-4 pt-2 pb-4 space-y-3">
                  <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 ml-6">
                    <h5 class="font-medium text-gray-900 mb-3">Rate Limiter rule #1</h5>
                    <div class="space-y-2 text-sm text-gray-700">
                      <p class="flex items-start">
                        <span class="font-medium text-gray-500 w-20 flex-shrink-0">Limit:</span>
                        <span>100 requests per 1 minute(s)</span>
                      </p>
                      <p class="flex items-start">
                        <span class="font-medium text-gray-500 w-20 flex-shrink-0">Scope:</span>
                        <span>per user</span>
                      </p>
                      <p class="flex items-start">
                        <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                          >Applies to:</span
                        >
                        <span>All users</span>
                      </p>
                    </div>
                  </div>

                  <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 ml-6">
                    <h5 class="font-medium text-gray-900 mb-3">Rate Limiter rule #2</h5>
                    <div class="space-y-2 text-sm text-gray-700">
                      <p class="flex items-start">
                        <span class="font-medium text-gray-500 w-20 flex-shrink-0">Limit:</span>
                        <span>500 requests per 1 minute(s)</span>
                      </p>
                      <p class="flex items-start">
                        <span class="font-medium text-gray-500 w-20 flex-shrink-0">Scope:</span>
                        <span>per user</span>
                      </p>
                      <p class="flex items-start">
                        <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                          >Applies to:</span
                        >
                        <span>Only: *@openmined.org</span>
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Pricing -->
              <div class="border border-gray-200 rounded-lg">
                <button
                  @click="togglePolicySection('pricing')"
                  class="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 rounded-lg transition-colors"
                >
                  <div class="flex items-center gap-3">
                    <div class="p-2 rounded-lg bg-yellow-100">
                      <DollarSign class="h-4 w-4 text-yellow-600" />
                    </div>
                    <h4 class="font-semibold text-gray-900">Pricing</h4>
                    <span class="text-xs text-gray-500">(2 rules)</span>
                  </div>
                  <ChevronDown
                    :class="[
                      'h-4 w-4 text-gray-500 transition-transform duration-200',
                      expandedSections.pricing ? 'rotate-180' : '',
                    ]"
                  />
                </button>

                <div v-if="expandedSections.pricing" class="px-4 pt-2 pb-4 space-y-3">
                  <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 ml-6">
                    <h5 class="font-medium text-gray-900 mb-3">Pricing rule #1</h5>
                    <div class="space-y-2 text-sm text-gray-700">
                      <p class="flex items-start">
                        <span class="font-medium text-gray-500 w-20 flex-shrink-0">Price:</span>
                        <span>$0.005 per 1 request(s)</span>
                      </p>
                      <p class="flex items-start">
                        <span class="font-medium text-gray-500 w-20 flex-shrink-0">Apply to:</span>
                        <span>All users</span>
                      </p>
                    </div>
                  </div>

                  <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 ml-6">
                    <h5 class="font-medium text-gray-900 mb-3">Free for teachers and students</h5>
                    <div class="space-y-2 text-sm text-gray-700">
                      <p class="flex items-start">
                        <span class="font-medium text-gray-500 w-20 flex-shrink-0">Price:</span>
                        <span>$0 per 1 request(s)</span>
                      </p>
                      <p class="flex items-start">
                        <span class="font-medium text-gray-500 w-20 flex-shrink-0">Apply to:</span>
                        <span>Only: *.edu</span>
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Manual approval -->
              <div class="border border-gray-200 rounded-lg">
                <button
                  @click="togglePolicySection('manualApproval')"
                  class="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 rounded-lg transition-colors"
                >
                  <div class="flex items-center gap-3">
                    <div class="p-2 rounded-lg bg-purple-100">
                      <UserCheck class="h-4 w-4 text-purple-600" />
                    </div>
                    <h4 class="font-semibold text-gray-900">Manual approval</h4>
                    <span class="text-xs text-gray-500">(1 rule)</span>
                  </div>
                  <ChevronDown
                    :class="[
                      'h-4 w-4 text-gray-500 transition-transform duration-200',
                      expandedSections.manualApproval ? 'rotate-180' : '',
                    ]"
                  />
                </button>

                <div v-if="expandedSections.manualApproval" class="px-4 pt-2 pb-4 space-y-3">
                  <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 ml-6">
                    <h5 class="font-medium text-gray-900 mb-3">Manual approval rule #1</h5>
                    <div class="space-y-2 text-sm text-gray-700">
                      <p class="flex items-start">
                        <span class="font-medium text-gray-500 w-20 flex-shrink-0">Alert:</span>
                        <span>In-App Notification</span>
                      </p>
                      <p class="flex items-start">
                        <span class="font-medium text-gray-500 w-20 flex-shrink-0">Apply to:</span>
                        <span>Only: *.edu</span>
                      </p>
                      <p class="flex items-start">
                        <span class="font-medium text-gray-500 w-20 flex-shrink-0">Timeout:</span>
                        <span>24 hour(s)</span>
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Request Statistics -->
          <div class="bg-white border border-gray-200 rounded-lg p-6">
            <h2 class="text-lg font-semibold text-gray-900 mb-4">Request Statistics</h2>
            <div class="space-y-3">
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Total Requests:</span>
                <span class="text-sm text-gray-900 font-semibold">{{
                  getRequestStats().totalRequests
                }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Success Rate:</span>
                <span class="text-sm text-green-600 font-semibold">{{
                  getRequestStats().successRate
                }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">This Month:</span>
                <span class="text-sm text-gray-900 font-semibold">{{
                  getRequestStats().thisMonth
                }}</span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-sm text-gray-600">Active Users:</span>
                <span class="text-sm text-gray-900 font-semibold">{{
                  getRequestStats().activeUsers
                }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import {
  Server,
  ChevronRight,
  Edit,
  Trash2,
  Send,
  EyeOff,
  Gauge,
  DollarSign,
  UserCheck,
  ChevronDown,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useEndpointsStore } from '@/stores/endpoints'
import type { EndpointItem } from '@/stores/endpoints'
import { getDataSourceName, getModelName } from '@/lib/mappers'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'

const route = useRoute()
const error = ref(false)
const endpoint = ref<EndpointItem | null>(null)
const endpointsStore = useEndpointsStore()

// Accordion state for policies
const expandedSections = ref({
  rateLimiter: false,
  pricing: false,
  manualApproval: false,
})

const selectedPeriod = ref('Daily')

const togglePolicySection = (section: keyof typeof expandedSections.value) => {
  expandedSections.value[section] = !expandedSections.value[section]
}

const getDatasetSlug = (dataSourceType: string) => {
  const datasetSlugs: Record<string, string> = {
    filesystem: 'Research Database',
    weaviate: 'Legal Documents Store',
    qdrant: 'Customer Analytics Store',
    chroma: 'Research Database',
  }
  return datasetSlugs[dataSourceType] || 'unknown'
}

const getModelSlug = (modelType: string) => {
  const modelSlugs: Record<string, string> = {
    vllm: 'NLP Processing Engine',
    ollama: 'Code Assistant Model',
    huggingface: 'Text Embedding Service',
  }
  return modelSlugs[modelType] || 'unknown'
}

const getEndpointType = () => {
  // All endpoints are data endpoints for now
  return 'Data Endpoint'
}

const getResponseType = () => {
  // All endpoints have both types for now
  return 'Both AI Summary & Raw Data'
}

const getRequestStats = () => {
  // Mock data - in real app this would come from analytics API
  return {
    totalRequests: '47.2k',
    successRate: '98.7%',
    thisMonth: '12.1k',
    activeUsers: '234',
  }
}

const getEndpointRevenue = () => {
  // Mock data - in real app this would come from billing/revenue API
  return {
    total: '$1,247.85',
    thisMonth: '$285.40',
    lastMonth: '$198.65',
    growth: '+43.7%',
    avgPerRequest: '$0.026',
    revenueRate: '64.2%',
    paidUsers: '156',
    freeRequests: '16.8k',
    paidRequests: '30.4k',
    conversionRate: '18.3%',
  }
}

onMounted(() => {
  const endpointSlug = route.params.slug as string
  const foundEndpoint = endpointsStore.endpoints.find((e) => e.name === endpointSlug)

  if (foundEndpoint) {
    endpoint.value = foundEndpoint
  } else {
    error.value = true
  }
})
</script>

<style scoped>
.markdown-content :deep(*) {
  word-wrap: break-word;
  overflow-wrap: break-word;
  hyphens: auto;
  line-height: 1.6;
}

.markdown-content :deep(p) {
  margin-bottom: 1rem;
  word-break: normal;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  word-break: normal;
  hyphens: none;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 1.5rem;
}

.markdown-content :deep(li) {
  margin-bottom: 0.5rem;
  word-break: normal;
}
</style>
