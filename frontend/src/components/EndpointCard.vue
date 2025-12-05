<template>
  <Card class="p-6 hover:shadow-lg transition-shadow cursor-pointer" @click="handleCardClick">
    <div class="flex items-start justify-between">
      <div class="flex-1">
        <div class="flex items-center gap-3 mb-2">
          <h3 class="heading-4 text-foreground">{{ endpoint.name }}</h3>
          <Badge
            :variant="endpoint.status === 'published' ? 'default' : 'secondary'"
            :class="
              endpoint.status === 'published'
                ? 'bg-primary/10 text-primary border border-primary/20'
                : 'bg-muted text-muted-foreground border border-border'
            "
            class="body-sm px-2.5 py-1 rounded-md"
          >
            {{ endpoint.status === 'published' ? 'Published' : 'Draft' }}
          </Badge>
        </div>
        <p class="body-sm text-muted-foreground mb-4">{{ endpoint.summary }}</p>

        <!-- Watched Paths Preview -->
        <div class="mb-4 space-y-2 pl-2">
          <div v-if="endpoint.isCustom" class="text-sm text-muted-foreground">
            📂 <span class="italic">Custom dataset - manually configured</span>
          </div>

          <div
            v-else-if="!endpoint.watchedPaths || endpoint.watchedPaths.length === 0"
            class="text-sm text-muted-foreground"
          >
            📂 <span class="italic">No paths configured</span>
          </div>

          <div v-else class="space-y-1">
            <div class="text-sm text-muted-foreground flex items-center gap-2">
              📂 <span class="font-medium">Files & Folders:</span>
            </div>
            <div class="ml-6 space-y-1 py-1">
              <div
                v-for="path in getPathsPreview(endpoint).paths"
                :key="path"
                class="text-sm font-mono text-muted-foreground opacity-75"
              >
                {{ path }}
              </div>
              <div
                v-if="getPathsPreview(endpoint).hasMore"
                class="text-sm text-muted-foreground opacity-60 italic"
              >
                +{{ getPathsPreview(endpoint).totalCount - 3 }} more...
              </div>
            </div>
          </div>
        </div>

        <div class="flex items-center gap-4 flex-wrap">
          <div class="flex gap-2">
            <TooltipProvider v-if="endpoint.dataSourceType">
              <Tooltip>
                <TooltipTrigger as-child>
                  <Badge variant="outline" class="body-sm flex items-center gap-1 cursor-help">
                    <IntegrationIcon :name="endpoint.dataSourceType" class="h-3 w-3" />
                    {{ getDataSourceName(endpoint.dataSourceType) }}
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  {{ getTechnicalDataSourceName(endpoint.dataSourceType) }}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <TooltipProvider v-if="endpoint.modelType">
              <Tooltip>
                <TooltipTrigger as-child>
                  <Badge variant="outline" class="body-sm flex items-center gap-1 cursor-help">
                    <IntegrationIcon :name="endpoint.modelType" class="h-3 w-3" />
                    {{ getModelName(endpoint.modelType) }}
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  {{ getTechnicalModelName(endpoint.modelType) }}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </div>

      <div class="ml-4 text-right">
        <div class="flex flex-col gap-2">
          <template v-if="endpoint.status === 'draft'">
            <Button variant="outline" size="sm" class="w-full" @click.stop>
              <Send class="h-4 w-4 mr-2" />
              Publish
            </Button>
            <div class="flex items-center gap-2">
              <Button variant="outline" size="sm" @click.stop>
                <Edit class="h-4 w-4 mr-2" />
                Edit
              </Button>
              <Button
                variant="outline"
                size="sm"
                class="text-destructive hover:text-destructive"
                @click.stop
              >
                <Trash2 class="h-4 w-4 mr-2" />
                Delete
              </Button>
            </div>
          </template>
          <template v-else>
            <Button variant="outline" size="sm" @click.stop>
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
import type { EndpointItem } from '@/stores/endpoints'
import {
  getDataSourceName,
  getModelName,
  getTechnicalDataSourceName,
  getTechnicalModelName,
} from '@/lib/mappers'

const router = useRouter()

const props = defineProps<{
  endpoint: EndpointItem
}>()

const handleCardClick = () => {
  router.push({ name: 'endpoint-detail', params: { slug: props.endpoint.name } })
}

// Get preview paths for endpoint card
const getPathsPreview = (endpoint: EndpointItem) => {
  if (endpoint.isCustom) {
    return {
      isCustom: true,
      paths: [],
      hasMore: false,
      totalCount: 0,
    }
  }

  if (!endpoint.watchedPaths || endpoint.watchedPaths.length === 0) {
    return {
      isCustom: false,
      paths: [],
      hasMore: false,
      totalCount: 0,
    }
  }

  // Show first 3 paths with "..." if there are more
  const pathsToShow = endpoint.watchedPaths.slice(0, 3)
  const hasMore = endpoint.watchedPaths.length > 3

  return {
    isCustom: false,
    paths: pathsToShow,
    hasMore,
    totalCount: endpoint.watchedPaths.length,
  }
}
</script>
