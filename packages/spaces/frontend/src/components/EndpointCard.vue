<template>
  <div
    class="group rounded-lg border border-border/50 bg-card px-5 py-4 hover:border-border transition-colors cursor-pointer"
    @click="handleCardClick"
  >
    <div class="flex items-start gap-4">
      <div
        class="shrink-0 h-10 w-10 rounded-lg flex items-center justify-center"
        :class="iconStyles.bg"
      >
        <component :is="iconStyles.icon" class="h-5 w-5" :class="iconStyles.fg" />
      </div>

      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1">
          <h3 class="text-sm font-semibold text-foreground truncate">{{ endpoint.name }}</h3>

          <span
            v-if="endpoint.published"
            class="inline-flex items-center gap-1 text-[11px] text-emerald-500 shrink-0"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Live
          </span>
          <span
            v-else
            class="inline-flex items-center gap-1 text-[11px] text-muted-foreground shrink-0"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-muted-foreground/50" />
            Offline
          </span>

          <Badge
            variant="secondary"
            class="text-[10px] font-medium px-1.5 py-0 border-0 shrink-0"
            :class="typeBadgeStyles"
          >
            {{ typeLabel }}
          </Badge>
        </div>

        <p class="text-xs text-muted-foreground line-clamp-1 mb-2">{{ endpoint.summary }}</p>

        <div class="flex items-center gap-2 flex-wrap text-[11px]">
          <span
            v-if="endpoint.watchedPathsCount && endpoint.watchedPathsCount > 0"
            class="inline-flex items-center gap-1 text-muted-foreground"
          >
            <Database class="h-3 w-3" />
            {{ endpoint.watchedPathsCount }}
            {{ endpoint.watchedPathsCount === 1 ? 'path' : 'paths' }}
          </span>

          <span
            v-if="endpoint.modelType && !endpoint.datasetId"
            class="inline-flex items-center gap-1 text-muted-foreground"
          >
            <Sparkles class="h-3 w-3" />
            {{ formattedModelType }}
          </span>

          <template v-if="visibleTags.length > 0">
            <Badge
              v-for="tag in visibleTags"
              :key="tag"
              variant="secondary"
              class="text-[10px] font-normal px-1.5 py-0 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-0"
            >
              {{ tag }}
            </Badge>
            <span v-if="extraTagsCount > 0" class="text-muted-foreground">
              +{{ extraTagsCount }}
            </span>
          </template>
        </div>
      </div>

      <div class="shrink-0" @click.stop>
        <DropdownMenu>
          <DropdownMenuTrigger as-child>
            <Button
              variant="ghost"
              size="icon"
              class="h-8 w-8 text-muted-foreground hover:text-foreground"
            >
              <MoreHorizontal class="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" class="w-40">
            <DropdownMenuItem @select="handleView">
              <Eye class="h-4 w-4 mr-2" />
              View
            </DropdownMenuItem>
            <DropdownMenuItem @select="handleCopyUrl">
              <Copy class="h-4 w-4 mr-2" />
              Copy URL
            </DropdownMenuItem>
            <DropdownMenuItem @select="handleEditEndpoint">
              <Pencil class="h-4 w-4 mr-2" />
              Edit
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              class="text-destructive focus:text-destructive"
              @select="handleDeleteEndpoint"
            >
              <Trash2 class="h-4 w-4 mr-2" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Copy,
  Database,
  Eye,
  Layers,
  MoreHorizontal,
  Pencil,
  Sparkles,
  Trash2,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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
}>()

const endpointKind = computed<'data' | 'model' | 'hybrid' | 'unknown'>(() => {
  const hasDataset = !!props.endpoint.datasetId
  const hasModel = !!props.endpoint.modelId
  if (hasDataset && hasModel) return 'hybrid'
  if (hasDataset) return 'data'
  if (hasModel) return 'model'
  return 'unknown'
})

const iconStyles = computed(() => {
  switch (endpointKind.value) {
    case 'data':
      return {
        icon: Database,
        bg: 'bg-teal-500/15',
        fg: 'text-teal-500 dark:text-teal-400',
      }
    case 'model':
      return {
        icon: Sparkles,
        bg: 'bg-purple-500/15',
        fg: 'text-purple-500 dark:text-purple-400',
      }
    case 'hybrid':
      return {
        icon: Layers,
        bg: 'bg-amber-500/15',
        fg: 'text-amber-500 dark:text-amber-400',
      }
    default:
      return {
        icon: Database,
        bg: 'bg-muted',
        fg: 'text-muted-foreground',
      }
  }
})

const typeLabel = computed(() => {
  switch (endpointKind.value) {
    case 'data':
      return 'Data API'
    case 'model':
      return 'Model API'
    case 'hybrid':
      return 'Hybrid'
    default:
      return 'API'
  }
})

const typeBadgeStyles = computed(() => {
  switch (endpointKind.value) {
    case 'data':
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400'
    case 'model':
      return 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-400'
    case 'hybrid':
      return 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400'
    default:
      return 'bg-muted text-muted-foreground'
  }
})

const formattedModelType = computed(() => {
  const t = props.endpoint.modelType
  if (!t) return ''
  return t.charAt(0).toUpperCase() + t.slice(1)
})

const cleanTags = computed(() =>
  props.endpoint.tags.filter((t) => !t.startsWith('domain:') && !t.startsWith('language:')),
)

const visibleTags = computed(() => cleanTags.value.slice(0, 3))
const extraTagsCount = computed(() => Math.max(0, cleanTags.value.length - 3))

const handleCardClick = () => {
  router.push({ name: 'endpoint-detail', params: { slug: props.endpoint.slug } })
}

const handleView = () => {
  router.push({ name: 'endpoint-detail', params: { slug: props.endpoint.slug } })
}

const handleCopyUrl = async () => {
  const url =
    userStore.getEndpointUrlInMarketplace(props.endpoint.slug) ??
    `${window.location.origin}${window.location.pathname}#/endpoints/${props.endpoint.slug}`
  try {
    await navigator.clipboard.writeText(url)
    toast.success('URL copied to clipboard')
  } catch {
    toast.error('Failed to copy URL')
  }
}

const handleDeleteEndpoint = () => {
  emit('delete', props.endpoint)
}

const handleEditEndpoint = () => {
  emit('edit', props.endpoint)
}
</script>
