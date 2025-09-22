<template>
  <Card class="p-6 hover:shadow-lg transition-shadow">
    <div class="flex items-start justify-between">
      <div class="flex-1">
        <div class="flex items-center gap-2 mb-2">
          <Database v-if="service.type === 'data-source'" class="h-5 w-5 text-gray-600" />
          <Brain v-else class="h-5 w-5 text-gray-600" />
          <span class="font-medium text-sm text-gray-600">
            {{ service.type === 'data-source' ? 'Data Source' : 'Synthesizer' }}
          </span>
          <Badge 
            :variant="service.status === 'published' ? 'default' : 'secondary'"
            :class="service.status === 'published' ? 'bg-green-100 text-green-700 hover:bg-green-100' : 'bg-gray-100 text-gray-700'"
          >
            {{ service.status === 'published' ? 'Published' : 'Draft' }}
          </Badge>
        </div>
        
        <h3 class="text-lg font-semibold mb-2">{{ service.name }}</h3>
        <p class="text-gray-600 mb-4">{{ service.description }}</p>
        
        <div class="flex items-center gap-4 flex-wrap">
          <div class="flex gap-2">
            <Button
              v-if="service.supportedServices.includes('search')"
              variant="outline"
              size="sm"
            >
              <Search class="h-4 w-4 mr-1" />
              Search
            </Button>
            <Button
              v-if="service.supportedServices.includes('rag')"
              variant="outline"
              size="sm"
            >
              <FileText class="h-4 w-4 mr-1" />
              RAG
            </Button>
          </div>
          
          <Badge
            v-if="service.mcpCompatible"
            variant="secondary"
            class="bg-blue-100"
          >
            <Check class="h-3 w-3 mr-1" />
            MCP
          </Badge>
        </div>
      </div>
      
      <div class="ml-4 text-right">
        <p class="text-sm text-gray-500 mb-4">{{ service.price }}</p>
        <div class="flex flex-col gap-2">
          <template v-if="service.status === 'draft'">
            <div class="flex items-center gap-2">
              <Button variant="outline" size="sm" class="text-gray-600">
                <Edit class="h-4 w-4 mr-2" />
                Edit
              </Button>
              <Button variant="outline" size="sm" class="text-red-600 hover:text-red-700">
                <Trash2 class="h-4 w-4 mr-2" />
                Delete
              </Button>
            </div>
            <Button size="sm" class="bg-purple-600 hover:bg-purple-700 text-white w-full">
              <Send class="h-4 w-4 mr-2" />
              Publish
            </Button>
          </template>
          <template v-else>
            <Button variant="outline" size="sm" class="text-gray-600">
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
import { Database, Brain, Search, FileText, Check, Edit, Trash2, Send, EyeOff } from 'lucide-vue-next'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

interface Service {
  id: string
  type: 'data-source' | 'synthesizer'
  name: string
  description: string
  price: string
  supportedServices: string[]
  languages: string[]
  domains: string[]
  mcpCompatible: boolean
  tags: string[]
  status: 'published' | 'draft'
}

defineProps<{
  service: Service
}>()
</script>