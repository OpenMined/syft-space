<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Loading state -->
    <div v-if="loading" class="animate-pulse">
      <div class="h-8 bg-gray-200 rounded w-1/3 mb-4"></div>
      <div class="h-6 bg-gray-200 rounded w-1/2 mb-8"></div>
      <div class="h-96 bg-gray-200 rounded"></div>
    </div>

    <!-- Service not found -->
    <div v-else-if="!service" class="text-center py-12">
      <Server class="h-12 w-12 text-gray-400 mx-auto mb-4" />
      <h2 class="text-xl font-semibold text-gray-900 mb-2">Service not found</h2>
      <p class="text-gray-600 mb-4">The service you're looking for doesn't exist.</p>
      <Button @click="router.push({ name: 'services' })">
        <ArrowLeft class="h-4 w-4 mr-2" />
        Back to Services
      </Button>
    </div>

    <!-- Service details -->
    <div v-else>
      <!-- Header -->
      <div class="flex items-center gap-4 mb-8">
        <Button 
          variant="outline" 
          @click="router.push({ name: 'services' })"
          class="flex items-center gap-2"
        >
          <ArrowLeft class="h-4 w-4" />
          Back
        </Button>
        <div class="flex-1">
          <div class="flex items-center gap-3 mb-2">
            <Server class="h-6 w-6 text-gray-600" />
            <h1 class="text-2xl font-semibold text-gray-900">{{ service.name }}</h1>
            <Badge 
              :variant="service.status === 'published' ? 'default' : 'secondary'"
              :class="service.status === 'published' ? 'bg-green-100 text-green-700 hover:bg-green-100' : 'bg-gray-100 text-gray-700'"
            >
              {{ service.status === 'published' ? 'Published' : 'Draft' }}
            </Badge>
          </div>
          <p class="text-gray-600">{{ service.description }}</p>
        </div>
        
        <!-- Action buttons -->
        <div class="flex gap-2">
          <template v-if="service.status === 'draft'">
            <Button variant="outline" class="border-purple-600 text-purple-600 hover:bg-purple-50 hover:text-purple-700">
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

      <!-- Content -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- Main content -->
        <div class="lg:col-span-2 space-y-6">
          <!-- Technical Details -->
          <Card>
            <CardHeader>
              <CardTitle>Technical Configuration</CardTitle>
            </CardHeader>
            <CardContent class="space-y-4">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div v-if="service.dataSourceType">
                  <Label class="text-sm font-medium text-gray-700">Data Source</Label>
                  <div class="mt-1 flex items-center gap-2">
                    <IntegrationIcon :name="service.dataSourceType" class="h-5 w-5" />
                    <span class="text-gray-900">{{ getDataSourceName(service.dataSourceType) }}</span>
                    <Badge variant="outline" class="ml-2">{{ getTechnicalDataSourceName(service.dataSourceType) }}</Badge>
                  </div>
                </div>
                <div v-if="service.modelType">
                  <Label class="text-sm font-medium text-gray-700">Model</Label>
                  <div class="mt-1 flex items-center gap-2">
                    <IntegrationIcon :name="service.modelType" class="h-5 w-5" />
                    <span class="text-gray-900">{{ getModelName(service.modelType) }}</span>
                    <Badge variant="outline" class="ml-2">{{ getTechnicalModelName(service.modelType) }}</Badge>
                  </div>
                </div>
                <div>
                  <Label class="text-sm font-medium text-gray-700">Service Type</Label>
                  <div class="mt-1">
                    <Badge variant="outline" class="capitalize">{{ service.type }}</Badge>
                  </div>
                </div>
                <div>
                  <Label class="text-sm font-medium text-gray-700">MCP Compatible</Label>
                  <div class="mt-1">
                    <Badge :variant="service.mcpCompatible ? 'default' : 'secondary'" 
                           :class="service.mcpCompatible ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'">
                      {{ service.mcpCompatible ? 'Yes' : 'No' }}
                    </Badge>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <!-- Languages and Domains -->
          <Card>
            <CardHeader>
              <CardTitle>Supported Languages & Domains</CardTitle>
            </CardHeader>
            <CardContent class="space-y-4">
              <div>
                <Label class="text-sm font-medium text-gray-700">Languages</Label>
                <div class="mt-2 flex flex-wrap gap-2">
                  <Badge v-for="language in service.languages" :key="language" variant="outline" class="capitalize">
                    {{ language }}
                  </Badge>
                </div>
              </div>
              <div>
                <Label class="text-sm font-medium text-gray-700">Domains</Label>
                <div class="mt-2 flex flex-wrap gap-2">
                  <Badge v-for="domain in service.domains" :key="domain" variant="outline" class="capitalize">
                    {{ domain }}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          <!-- Tags -->
          <Card>
            <CardHeader>
              <CardTitle>Tags</CardTitle>
            </CardHeader>
            <CardContent>
              <div class="flex flex-wrap gap-2">
                <Badge v-for="tag in service.tags" :key="tag" variant="secondary">
                  {{ tag }}
                </Badge>
              </div>
            </CardContent>
          </Card>
        </div>

        <!-- Sidebar -->
        <div class="space-y-6">
          <!-- Service Info -->
          <Card>
            <CardHeader>
              <CardTitle>Service Information</CardTitle>
            </CardHeader>
            <CardContent class="space-y-3">
              <div>
                <Label class="text-sm font-medium text-gray-700">Service ID</Label>
                <p class="mt-1 text-sm font-mono text-gray-900">{{ service.id }}</p>
              </div>
              <div>
                <Label class="text-sm font-medium text-gray-700">Status</Label>
                <p class="mt-1">
                  <Badge 
                    :variant="service.status === 'published' ? 'default' : 'secondary'"
                    :class="service.status === 'published' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'"
                  >
                    {{ service.status === 'published' ? 'Published' : 'Draft' }}
                  </Badge>
                </p>
              </div>
            </CardContent>
          </Card>

          <!-- Quick Actions -->
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent class="space-y-2">
              <Button variant="outline" class="w-full justify-start">
                <Settings class="h-4 w-4 mr-2" />
                Configure Service
              </Button>
              <Button variant="outline" class="w-full justify-start">
                <BarChart3 class="h-4 w-4 mr-2" />
                View Analytics
              </Button>
              <Button variant="outline" class="w-full justify-start">
                <Download class="h-4 w-4 mr-2" />
                Export Configuration
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { 
  ArrowLeft, 
  Server, 
  Edit, 
  Trash2, 
  Send, 
  EyeOff, 
  Settings, 
  BarChart3, 
  Download 
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import IntegrationIcon from '@/components/IntegrationIcons.vue'

interface Service {
  id: string
  type: 'data-source' | 'synthesizer'
  name: string
  description: string
  dataSourceType?: string
  modelType?: string
  languages: string[]
  domains: string[]
  mcpCompatible: boolean
  tags: string[]
  status: 'published' | 'draft'
}

const router = useRouter()
const route = useRoute()
const loading = ref(true)
const service = ref<Service | null>(null)

// Mock data - in real app, this would come from an API
const mockServices: Service[] = [
  {
    id: '1',
    type: 'data-source',
    name: 'research@safari-lab.org/animalsofsouthafrica',
    description: 'Species records, park reports, conservation notes.',
    dataSourceType: 'weaviate',
    modelType: 'vllm',
    languages: ['english'],
    domains: ['wildlife'],
    mcpCompatible: true,
    tags: ['domain:wildlife'],
    status: 'published'
  },
  {
    id: '2',
    type: 'data-source',
    name: 'data@lexfirm.eu/lexcivillaw',
    description: 'Civil code, case law digests, firm memos (EU focus).',
    dataSourceType: 'qdrant',
    modelType: 'ollama',
    languages: ['english', 'german', 'french'],
    domains: ['legal'],
    mcpCompatible: false,
    tags: ['domain:legal', 'language:de'],
    status: 'published'
  },
  {
    id: '3',
    type: 'data-source',
    name: 'admin@st-marys-hospital.com/meddevicerecords',
    description: 'Hospital device logs, maintenance + UDI registry links.',
    dataSourceType: 'filesystem',
    languages: ['english'],
    domains: ['healthcare'],
    mcpCompatible: false,
    tags: ['domain:healthcare'],
    status: 'draft'
  }
]

const getDataSourceName = (type: string) => {
  const names: Record<string, string> = {
    filesystem: 'File System',
    weaviate: 'Legal Documents Store',
    qdrant: 'Customer Analytics Store', 
    chroma: 'Research Database'
  }
  return names[type] || type
}

const getModelName = (type: string) => {
  const names: Record<string, string> = {
    vllm: 'NLP Processing Engine',
    ollama: 'Code Assistant Model',
    huggingface: 'Text Embedding Service'
  }
  return names[type] || type
}

const getTechnicalDataSourceName = (type: string) => {
  const names: Record<string, string> = {
    filesystem: 'File System',
    weaviate: 'Weaviate',
    qdrant: 'Qdrant',
    chroma: 'Chroma'
  }
  return names[type] || type
}

const getTechnicalModelName = (type: string) => {
  const names: Record<string, string> = {
    vllm: 'vLLM',
    ollama: 'Ollama',
    huggingface: 'Hugging Face'
  }
  return names[type] || type
}

onMounted(() => {
  const serviceId = route.params.id as string
  // Simulate loading delay
  setTimeout(() => {
    service.value = mockServices.find(s => s.id === serviceId) || null
    loading.value = false
  }, 500)
})
</script>