<template>
  <Card class="p-6 hover:shadow-lg transition-shadow cursor-pointer" @click="handleCardClick">
    <div class="flex items-start justify-between">
      <div class="flex-1">
        <div class="flex items-center gap-3 mb-2">
          <h3 class="text-lg font-semibold">{{ service.name }}</h3>
          <Badge 
            :variant="service.status === 'published' ? 'default' : 'secondary'"
            :class="service.status === 'published' ? 'bg-green-100 text-green-700 hover:bg-green-100' : 'bg-gray-100 text-gray-700'"
          >
            {{ service.status === 'published' ? 'Published' : 'Draft' }}
          </Badge>
        </div>
        <p class="text-gray-600 mb-4">{{ service.description }}</p>
        
        <div class="flex items-center gap-4 flex-wrap">
          <div class="flex gap-2">
            <TooltipProvider v-if="service.dataSourceType">
              <Tooltip>
                <TooltipTrigger as-child>
                  <Badge
                    variant="outline"
                    class="flex items-center gap-1 cursor-help"
                  >
                    <IntegrationIcon :name="service.dataSourceType" class="h-3 w-3" />
                    {{ getDataSourceName(service.dataSourceType) }}
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  {{ getTechnicalDataSourceName(service.dataSourceType) }}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <TooltipProvider v-if="service.modelType">
              <Tooltip>
                <TooltipTrigger as-child>
                  <Badge
                    variant="outline"
                    class="flex items-center gap-1 cursor-help"
                  >
                    <IntegrationIcon :name="service.modelType" class="h-3 w-3" />
                    {{ getModelName(service.modelType) }}
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  {{ getTechnicalModelName(service.modelType) }}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </div>
      
      <div class="ml-4 text-right">
        <div class="flex flex-col gap-2">
          <template v-if="service.status === 'draft'">
            <Button variant="outline" size="sm" class="border-purple-600 text-purple-600 hover:bg-purple-50 hover:text-purple-700 w-full" @click.stop>
              <Send class="h-4 w-4 mr-2" />
              Publish
            </Button>
            <div class="flex items-center gap-2">
              <Button variant="outline" size="sm" class="text-gray-600" @click.stop>
                <Edit class="h-4 w-4 mr-2" />
                Edit
              </Button>
              <Button variant="outline" size="sm" class="text-red-600 hover:text-red-700" @click.stop>
                <Trash2 class="h-4 w-4 mr-2" />
                Delete
              </Button>
            </div>
          </template>
          <template v-else>
            <Button variant="outline" size="sm" class="text-gray-600" @click.stop>
              <EyeOff class="h-4 w-4 mr-2" />
              Unpublish
            </Button>
          </template>
        </div>
      </div>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Edit, Trash2, Send, EyeOff } from 'lucide-vue-next'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import IntegrationIcon from '@/components/IntegrationIcons.vue'

const router = useRouter()

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

const props = defineProps<{
  service: Service
}>()

const handleCardClick = () => {
  router.push({ name: 'service-detail', params: { id: props.service.id } })
}
</script>