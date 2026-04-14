<template>
  <div
    class="group rounded-lg border border-border/50 bg-card p-5 hover:shadow-sm hover:-translate-y-px transition-all cursor-pointer"
    @click="handleCardClick"
  >
    <div class="flex items-start justify-between">
      <div class="flex items-start gap-4 flex-1 min-w-0">
        <div class="p-3.5 rounded-xl bg-primary/10 shrink-0">
          <Server class="h-6 w-6 text-foreground/60" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-3 mb-2">
            <h3 class="heading-4 text-foreground truncate">{{ endpoint.name }}</h3>
            <div
              :class="
                endpoint.published
                  ? 'w-2 h-2 rounded-full bg-green-500 shrink-0'
                  : 'w-2 h-2 rounded-full bg-muted-foreground/40 shrink-0'
              "
            />
            <Badge
              v-if="!endpoint.modelId && endpoint.datasetId"
              variant="secondary"
              class="text-[10px] px-1.5 py-0 bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400 border-0 shrink-0"
            >
              Data API
            </Badge>
            <Badge
              v-else-if="endpoint.modelId && !endpoint.datasetId"
              variant="secondary"
              class="text-[10px] px-1.5 py-0 bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400 border-0 shrink-0"
            >
              Model API
            </Badge>
          </div>
          <p class="body-sm text-muted-foreground mb-3 line-clamp-2">{{ endpoint.summary }}</p>

          <div v-if="endpoint.tags && endpoint.tags.length > 0" class="flex gap-1.5 flex-wrap">
            <Badge
              v-for="tag in endpoint.tags.slice(0, 3)"
              :key="tag"
              variant="secondary"
              class="text-[11px] px-2 py-0.5"
            >
              {{ tag }}
            </Badge>
            <span
              v-if="endpoint.tags.length > 3"
              class="text-[11px] text-muted-foreground self-center"
            >
              +{{ endpoint.tags.length - 3 }}
            </span>
          </div>
        </div>
      </div>

      <div
        class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
      >
        <Button variant="outline" size="sm" @click.stop="handleEditEndpoint">
          <Pencil class="h-4 w-4 mr-2" />
          Edit
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { Pencil, Server, Trash2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { EndpointItem } from '@/stores/endpoints'

const router = useRouter()

const props = defineProps<{
  endpoint: EndpointItem
}>()

const emit = defineEmits<{
  delete: [endpoint: EndpointItem]
  edit: [endpoint: EndpointItem]
}>()

const handleCardClick = () => {
  router.push({ name: 'endpoint-detail', params: { slug: props.endpoint.slug } })
}

const handleDeleteEndpoint = () => {
  emit('delete', props.endpoint)
}

const handleEditEndpoint = () => {
  emit('edit', props.endpoint)
}
</script>
