<template>
  <Card class="p-6 hover:shadow-lg transition-shadow cursor-pointer" @click="handleCardClick">
    <div class="flex items-start justify-between">
      <div class="flex-1">
        <div class="flex items-center gap-3 mb-2">
          <h3 class="heading-4 text-foreground">{{ endpoint.name }}</h3>
          <Badge
            :variant="endpoint.published ? 'default' : 'secondary'"
            :class="
              endpoint.published
                ? 'bg-primary/10 text-primary border border-primary/20'
                : 'bg-muted text-muted-foreground border border-border'
            "
            class="body-sm px-2.5 py-1 rounded-md"
          >
            {{ endpoint.published ? 'Published' : 'Draft' }}
          </Badge>
          <Badge
            v-if="endpoint.archived"
            variant="outline"
            class="body-sm px-2.5 py-1 rounded-md text-muted-foreground border-border"
          >
            <Archive class="h-3 w-3 mr-1" />
            Archived
          </Badge>
        </div>
        <p class="body-sm text-muted-foreground mb-4">{{ endpoint.summary }}</p>

        <!-- Watched Paths Preview (only for local_file data sources) -->
        <div v-if="endpoint.dataSourceType === 'local_file'" class="mb-4 space-y-2 pl-2">
          <div
            v-if="!endpoint.watchedPaths || endpoint.watchedPaths.length === 0"
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

        <div class="flex gap-2 flex-wrap">
          <Badge v-for="tag in endpoint.tags" :key="tag" variant="outline" class="body-sm">
            {{ tag }}
          </Badge>
        </div>
      </div>

      <div class="ml-4 text-right">
        <div class="flex flex-col gap-2">
          <div class="flex items-center gap-2">
            <Button variant="outline" size="sm" @click.stop="handleEditEndpoint">
              <Pencil class="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              @click.stop="handleArchiveToggle"
            >
              <Archive class="h-4 w-4 mr-2" />
              {{ endpoint.archived ? 'Unarchive' : 'Archive' }}
            </Button>
            <Button
              variant="outline"
              size="sm"
              class="text-destructive hover:text-destructive"
              @click.stop="handleDeleteEndpoint"
            >
              <Trash2 class="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
          <Button
            v-if="syftHubUrl"
            variant="outline"
            size="sm"
            class="w-full"
            as="a"
            :href="syftHubUrl"
            target="_blank"
            rel="noopener noreferrer"
            @click.stop
          >
            <ExternalLink class="h-4 w-4 mr-2" />
            View on SyftHub
          </Button>
        </div>
      </div>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Archive, ExternalLink, Pencil, Trash2 } from 'lucide-vue-next'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useUserStore } from '@/stores/user'
import type { EndpointItem } from '@/stores/endpoints'

const router = useRouter()
const userStore = useUserStore()

const props = defineProps<{
  endpoint: EndpointItem
}>()

const emit = defineEmits<{
  delete: [endpoint: EndpointItem]
  edit: [endpoint: EndpointItem]
  archive: [endpoint: EndpointItem]
}>()

const syftHubUrl = computed(() =>
  props.endpoint.name ? userStore.getEndpointUrlInMarketplace(props.endpoint.name) : null,
)

const handleCardClick = () => {
  router.push({ name: 'endpoint-detail', params: { slug: props.endpoint.name } })
}

const handleDeleteEndpoint = () => {
  emit('delete', props.endpoint)
}

const handleEditEndpoint = () => {
  emit('edit', props.endpoint)
}

const handleArchiveToggle = () => {
  emit('archive', props.endpoint)
}

// Get preview paths for endpoint card
const getPathsPreview = (endpoint: EndpointItem) => {
  if (!endpoint.watchedPaths || endpoint.watchedPaths.length === 0) {
    return {
      paths: [],
      hasMore: false,
      totalCount: 0,
    }
  }

  // Show first 3 paths with "..." if there are more
  const pathsToShow = endpoint.watchedPaths.slice(0, 3)
  const hasMore = endpoint.watchedPaths.length > 3

  return {
    paths: pathsToShow,
    hasMore,
    totalCount: endpoint.watchedPaths.length,
  }
}
</script>
