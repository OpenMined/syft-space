<template>
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 lg:py-14">
    <!-- Header -->
    <div class="mb-8">
      <div class="flex items-center gap-3 mb-2">
        <h1 class="text-3xl font-bold tracking-tight text-foreground">APIs</h1>
        <Badge
          v-if="publishedCount > 0"
          variant="secondary"
          class="text-xs font-medium bg-muted text-muted-foreground border-0"
        >
          {{ publishedCount }} published
        </Badge>
      </div>
      <p class="text-sm text-muted-foreground">
        Resources you've shared with the world. Each one has its own access rules and pricing.
      </p>
    </div>

    <!-- Actions Bar -->
    <div class="flex items-center gap-3 mb-4">
      <div class="relative flex-1 max-w-sm">
        <Search
          class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none"
        />
        <Input v-model="searchQuery" placeholder="Search APIs..." class="pl-9" />
      </div>

      <Select v-model="sortBy">
        <SelectTrigger class="w-[140px]">
          <ArrowUpDown class="h-4 w-4 text-muted-foreground mr-1" />
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="recent">Recent</SelectItem>
          <SelectItem value="name">Name</SelectItem>
          <SelectItem value="status">Status</SelectItem>
        </SelectContent>
      </Select>

      <Button @click="router.push({ name: 'go-live' })">
        <Plus class="h-4 w-4 mr-2" />
        Publish
      </Button>
    </div>

    <!-- Filter Tabs -->
    <div
      v-if="!endpointsStore.isLoading && !endpointsStore.error && allEndpoints.length > 0"
      class="flex items-center justify-between mb-5"
    >
      <div class="flex items-center gap-1">
        <button
          v-for="filter in filterOptions"
          :key="filter.value"
          class="px-2.5 py-1 text-sm rounded-md transition-colors"
          :class="
            activeFilter === filter.value
              ? 'text-foreground font-medium'
              : 'text-muted-foreground hover:text-foreground'
          "
          @click="activeFilter = filter.value"
        >
          {{ filter.label }}
          <span v-if="filter.value !== 'all'" class="ml-1 text-muted-foreground">
            {{ filter.count }}
          </span>
        </button>
      </div>
      <p class="text-xs text-muted-foreground">
        Showing {{ filteredEndpoints.length }} of {{ allEndpoints.length }}
      </p>
    </div>

    <!-- Loading state -->
    <div v-if="endpointsStore.isLoading" class="space-y-3">
      <div
        v-for="i in 3"
        :key="`skeleton-${i}`"
        class="rounded-lg border border-border/50 bg-card px-5 py-4 animate-pulse"
      >
        <div class="flex items-start gap-4">
          <div class="h-10 w-10 bg-muted rounded-lg shrink-0"></div>
          <div class="flex-1 space-y-2">
            <div class="h-4 bg-muted rounded w-1/3"></div>
            <div class="h-3 bg-muted rounded w-1/2"></div>
            <div class="h-3 bg-muted rounded w-2/3"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Error state -->
    <div v-else-if="endpointsStore.error" class="text-center py-8">
      <div class="text-destructive mb-2">Failed to load APIs</div>
      <Button @click="endpointsStore.fetchEndpoints()" variant="outline">Try Again</Button>
    </div>

    <!-- Endpoint cards -->
    <div v-else-if="filteredEndpoints.length > 0" class="space-y-3">
      <EndpointCard
        v-for="endpoint in filteredEndpoints"
        :key="endpoint.id"
        :endpoint="endpoint"
        @delete="handleDeleteEndpoint"
        @edit="handleEditEndpoint"
      />
    </div>

    <!-- No results state -->
    <div
      v-else-if="!endpointsStore.isLoading && (searchQuery || activeFilter !== 'all')"
      class="text-center py-12"
    >
      <p class="text-muted-foreground">No APIs match your filters</p>
    </div>

    <!-- Empty state -->
    <div
      v-if="
        !endpointsStore.isLoading &&
        !endpointsStore.error &&
        allEndpoints.length === 0 &&
        !searchQuery
      "
      class="text-center py-8"
    >
      <Server class="h-10 w-10 text-muted-foreground mx-auto mb-4" />
      <h3 class="heading-3 text-foreground mb-2">No APIs yet</h3>
      <p class="body-sm text-muted-foreground mb-4">
        Share your first data source or model with the world.
      </p>
      <Button @click="router.push({ name: 'go-live' })">
        <Plus class="h-4 w-4 mr-2" />
        Publish
      </Button>
    </div>
  </div>

  <!-- Edit Endpoint Dialog -->
  <EditEndpointDialog
    v-model:open="showEditDialog"
    :endpoint="endpointToEdit"
    @saved="handleEditSaved"
  />

  <!-- Delete Confirmation Dialog -->
  <Dialog v-model:open="showDeleteDialog">
    <DialogContent class="sm:max-w-[425px]">
      <DialogHeader>
        <DialogTitle class="text-destructive">Delete API</DialogTitle>
        <DialogDescription>
          This will permanently delete this API and remove it from SyftHub. This action cannot be
          undone.
        </DialogDescription>
      </DialogHeader>
      <div class="space-y-2">
        <Label class="gap-1">
          Type <span class="font-semibold text-foreground">{{ endpointToDelete?.name }}</span> to
          confirm
        </Label>
        <Input v-model="deleteNameConfirm" :placeholder="endpointToDelete?.name || 'api-name'" />
        <p
          v-if="deleteNameConfirm"
          class="text-sm"
          :class="
            deleteNameConfirm === endpointToDelete?.name ? 'text-success' : 'text-muted-foreground'
          "
        >
          {{
            deleteNameConfirm === endpointToDelete?.name ? 'Name matches' : 'Name does not match'
          }}
        </p>
      </div>
      <DialogFooter>
        <Button variant="outline" @click="cancelDeleteEndpoint" :disabled="isDeleting">
          Cancel
        </Button>
        <Button
          variant="destructive"
          :disabled="deleteNameConfirm !== endpointToDelete?.name || isDeleting"
          @click="confirmDeleteEndpoint"
        >
          <div v-if="isDeleting" class="flex items-center gap-2">
            <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            Deleting...
          </div>
          <span v-else>Delete API</span>
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ArrowUpDown, Plus, Search, Server } from 'lucide-vue-next'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import EndpointCard from '@/components/EndpointCard.vue'
import EditEndpointDialog from '@/components/EditEndpointDialog.vue'
import { useEndpointsStore } from '@/stores/endpoints'
import type { EndpointItem } from '@/stores/endpoints'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { toast } from 'vue-sonner'
import { useRouter } from 'vue-router'
import { mockApis } from '@/stores/mockApis'

const router = useRouter()
const endpointsStore = useEndpointsStore()

// Mock-first demo APIs (agent / data / model backed) rendered as regular list
// members alongside the real backend endpoints.
const MOCK_API_CREATED_AT = '2026-06-10T12:00:00.000Z'
const mockApisAsEndpoints = computed<EndpointItem[]>(() =>
  mockApis.map((api) => ({
    id: api.id,
    name: api.name,
    slug: api.id,
    summary: api.prompt ?? '',
    description: '',
    datasetId: api.rootType === 'data' ? api.rootResourceId : undefined,
    modelId: api.rootType === 'model' ? api.rootResourceId : undefined,
    systemPrompt: api.prompt,
    tags: [],
    published: api.channels.some((c) => c.enabled),
    createdAt: MOCK_API_CREATED_AT,
  })),
)

const allEndpoints = computed<EndpointItem[]>(() => [
  ...endpointsStore.endpoints,
  ...mockApisAsEndpoints.value,
])

onMounted(() => {
  endpointsStore.fetchEndpoints()
})

type FilterValue = 'all' | 'data' | 'model' | 'hybrid'
type SortValue = 'recent' | 'name' | 'status'

const searchQuery = ref('')
const sortBy = ref<SortValue>('recent')
const activeFilter = ref<FilterValue>('all')

const showDeleteDialog = ref(false)
const endpointToDelete = ref<EndpointItem | null>(null)
const deleteNameConfirm = ref('')
const isDeleting = ref(false)

const showEditDialog = ref(false)
const endpointToEdit = ref<{ slug: string; name: string; summary: string } | null>(null)

const classifyEndpoint = (e: EndpointItem): Exclude<FilterValue, 'all'> | 'unknown' => {
  const hasDataset = !!e.datasetId
  const hasModel = !!e.modelId
  if (hasDataset && hasModel) return 'hybrid'
  if (hasDataset) return 'data'
  if (hasModel) return 'model'
  return 'unknown'
}

const publishedCount = computed(() => allEndpoints.value.filter((e) => e.published).length)

const filterCounts = computed(() => {
  const counts = { data: 0, model: 0, hybrid: 0 }
  for (const e of allEndpoints.value) {
    const kind = classifyEndpoint(e)
    if (kind === 'data') counts.data++
    else if (kind === 'model') counts.model++
    else if (kind === 'hybrid') counts.hybrid++
  }
  return counts
})

const filterOptions = computed<{ value: FilterValue; label: string; count: number }[]>(() => [
  { value: 'all', label: 'All', count: allEndpoints.value.length },
  { value: 'data', label: 'Data', count: filterCounts.value.data },
  { value: 'model', label: 'Model', count: filterCounts.value.model },
  { value: 'hybrid', label: 'Hybrid', count: filterCounts.value.hybrid },
])

const filteredEndpoints = computed(() => {
  const query = searchQuery.value.toLowerCase().trim()

  const filtered = allEndpoints.value.filter((endpoint) => {
    if (activeFilter.value !== 'all' && classifyEndpoint(endpoint) !== activeFilter.value) {
      return false
    }
    if (query) {
      const haystack = `${endpoint.name} ${endpoint.summary}`.toLowerCase()
      if (!haystack.includes(query)) return false
    }
    return true
  })

  const sorted = [...filtered]
  if (sortBy.value === 'name') {
    sorted.sort((a, b) => a.name.localeCompare(b.name))
  } else if (sortBy.value === 'status') {
    sorted.sort((a, b) => Number(b.published) - Number(a.published))
  } else {
    sorted.sort((a, b) => (a.createdAt < b.createdAt ? 1 : a.createdAt > b.createdAt ? -1 : 0))
  }
  return sorted
})

const handleDeleteEndpoint = (endpoint: EndpointItem) => {
  endpointToDelete.value = endpoint
  deleteNameConfirm.value = ''
  showDeleteDialog.value = true
}

const handleEditEndpoint = (endpoint: EndpointItem) => {
  endpointToEdit.value = {
    slug: endpoint.slug,
    name: endpoint.name,
    summary: endpoint.summary,
  }
  showEditDialog.value = true
}

const handleEditSaved = (data: { summary: string }) => {
  if (endpointToEdit.value) {
    const index = endpointsStore.endpoints.findIndex((e) => e.slug === endpointToEdit.value!.slug)
    if (index > -1 && endpointsStore.endpoints[index]) {
      endpointsStore.endpoints[index].summary = data.summary
    }
  }
  endpointToEdit.value = null
}

const cancelDeleteEndpoint = () => {
  showDeleteDialog.value = false
  endpointToDelete.value = null
  deleteNameConfirm.value = ''
}

const confirmDeleteEndpoint = async () => {
  if (endpointToDelete.value && !isDeleting.value) {
    isDeleting.value = true

    try {
      if (!endpointToDelete.value.slug) {
        throw new Error('Endpoint slug is undefined')
      }

      if (endpointToDelete.value.published) {
        try {
          await endpointsApi.unpublish(endpointToDelete.value.slug)
        } catch (unpublishError) {
          console.error('Failed to unpublish endpoint:', unpublishError)
          toast.error('Failed to remove API from SyftHub. Please try again.')
          isDeleting.value = false
          return
        }
      }

      await endpointsApi.delete(endpointToDelete.value.slug)

      const index = endpointsStore.endpoints.findIndex((e) => e.id === endpointToDelete.value!.id)
      if (index > -1) {
        endpointsStore.endpoints.splice(index, 1)
      }

      toast.success('API deleted successfully')

      showDeleteDialog.value = false
      endpointToDelete.value = null
      deleteNameConfirm.value = ''
    } catch (error) {
      console.error('Failed to delete endpoint:', error)
      toast.error('Failed to delete API. Please try again.')
    } finally {
      isDeleting.value = false
    }
  }
}
</script>
