<template>
  <div class="wordpress-browser">
    <div class="mb-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <h3 class="text-lg font-medium text-foreground">Select posts & pages</h3>
          <Badge variant="secondary">{{ selected.length }} selected</Badge>
        </div>
        <Button @click="clearSelection" variant="outline" size="sm" :disabled="selected.length === 0">
          Clear Selection
        </Button>
      </div>
    </div>

    <div class="h-[450px]">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full">
        <!-- Left: post-type tree -->
        <div class="border-2 border-border rounded-lg overflow-hidden flex flex-col h-full">
          <div class="bg-muted border-b border-border px-4 py-2 flex-shrink-0">
            <div class="flex items-center gap-2 text-sm text-muted-foreground">
              <Newspaper class="w-4 h-4" />
              <span class="truncate">{{ siteLabel }}</span>
            </div>
          </div>

          <div class="flex-1 min-h-0">
            <ScrollArea class="h-full">
              <div class="p-2 space-y-1">
                <div v-if="isInitialLoading" class="flex items-center justify-center h-[200px]">
                  <div class="text-muted-foreground">Connecting…</div>
                </div>
                <div v-else-if="error" class="p-4 text-sm text-destructive">
                  {{ error }}
                </div>
                <div v-else-if="rootNodes.length === 0" class="p-4 text-sm text-muted-foreground">
                  No post types configured.
                </div>
                <div v-for="group in rootNodes" :key="group.path">
                  <div
                    class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted cursor-pointer"
                    @click="toggleGroup(group)"
                  >
                    <component
                      :is="expandedGroups.has(group.path) ? ChevronDown : ChevronRight"
                      class="w-4 h-4 text-muted-foreground flex-shrink-0"
                    />
                    <Checkbox
                      :model-value="groupSelectionState(group)"
                      @update:model-value="(checked) => onGroupCheckbox(group, checked)"
                      @click.stop
                    />
                    <Folder class="w-4 h-4 text-blue-500 flex-shrink-0" />
                    <span class="text-sm font-medium flex-1">{{ group.name }}</span>
                    <span v-if="group.children" class="text-xs text-muted-foreground">
                      {{ group.children.length || '' }}
                    </span>
                  </div>

                  <div v-if="expandedGroups.has(group.path)" class="ml-7 mt-1 space-y-0.5">
                    <div
                      v-if="group.isLoading"
                      class="flex items-center px-2 py-1.5 text-xs text-muted-foreground"
                    >
                      Loading posts…
                    </div>
                    <div
                      v-else-if="group.children && group.children.length === 0"
                      class="px-2 py-1.5 text-xs text-muted-foreground"
                    >
                      No items found.
                    </div>
                    <div
                      v-for="item in group.children || []"
                      :key="item.path"
                      class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted"
                    >
                      <Checkbox
                        :model-value="selected.includes(item.path)"
                        @update:model-value="(checked) => onItemCheckbox(item.path, checked)"
                      />
                      <FileText class="w-4 h-4 text-muted-foreground flex-shrink-0" />
                      <div class="flex-1 min-w-0">
                        <p class="text-sm truncate">{{ item.name }}</p>
                        <p v-if="item.modifiedTime" class="text-xs text-muted-foreground">
                          modified {{ formatModified(item.modifiedTime) }}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </div>
        </div>

        <!-- Right: selection chips -->
        <div
          class="bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800 rounded-lg p-4 pr-0 flex flex-col h-full min-h-0"
        >
          <div class="flex items-center justify-between mb-4 flex-shrink-0">
            <h4 class="text-sm font-medium text-blue-900 dark:text-blue-100">
              Selected Posts & Pages
            </h4>
            <Badge
              variant="secondary"
              class="bg-blue-100 dark:bg-blue-950/50 text-blue-800 dark:text-blue-200"
            >
              {{ selected.length }} item{{ selected.length !== 1 ? 's' : '' }}
            </Badge>
          </div>

          <div v-if="selected.length > 0" class="flex-1 min-h-0">
            <ScrollArea class="h-full">
              <div class="space-y-1 pr-4">
                <div
                  v-for="id in selected"
                  :key="id"
                  class="flex items-center gap-2 text-xs text-blue-900 dark:text-blue-100 bg-blue-100 dark:bg-blue-900/60 border border-blue-200 dark:border-blue-700 rounded-md px-3 py-2"
                >
                  <FileText class="w-4 h-4 flex-shrink-0" />
                  <span class="flex-1 truncate">
                    <span class="font-mono text-[11px] text-blue-700 dark:text-blue-300 mr-2">{{ id }}</span>
                    <span>{{ titleForId(id) }}</span>
                  </span>
                  <button
                    @click="removeSelected(id)"
                    class="p-0.5 hover:bg-blue-200 dark:hover:bg-blue-800 rounded transition-colors flex-shrink-0"
                  >
                    <X class="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </ScrollArea>
          </div>

          <div v-else class="flex-1 flex flex-col items-center justify-center text-center">
            <div
              class="w-16 h-16 bg-blue-100 dark:bg-blue-950/50 rounded-full flex items-center justify-center mb-4"
            >
              <Newspaper class="w-8 h-8 text-blue-400" />
            </div>
            <h5 class="text-blue-900 dark:text-blue-100 font-medium mb-2">No items selected</h5>
            <p class="text-blue-700 dark:text-blue-300 text-sm">
              Expand a post type on the left and tick the items you want to ingest.
            </p>
          </div>
        </div>
      </div>
    </div>

    <div class="text-sm text-muted-foreground mt-4">
      <p>Click a post type to expand. Use checkboxes to select individual items or whole groups.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  ChevronDown,
  ChevronRight,
  FileText,
  Folder,
  Newspaper,
  X,
} from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useSourceBrowser, type FileNode } from '@/composables/useSourceBrowser'

const props = defineProps<{
  modelValue: string[]
  siteUrl?: string
  username?: string
  applicationPassword?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const selected = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const expandedGroups = ref<Set<string>>(new Set())

const { rootNodes, error, isInitialLoading, loadRootDirectory, loadSubdirectory } =
  useSourceBrowser('wordpress', {
    siteUrl: props.siteUrl ?? '',
    username: props.username ?? '',
    applicationPassword: props.applicationPassword ?? '',
  })

onMounted(async () => {
  await loadRootDirectory()
})

const siteLabel = computed(() => {
  if (!props.siteUrl) return 'Connected WordPress site'
  return props.siteUrl.replace(/^https?:\/\//, '').replace(/\/$/, '')
})

const toggleGroup = async (group: FileNode) => {
  if (expandedGroups.value.has(group.path)) {
    expandedGroups.value.delete(group.path)
    expandedGroups.value = new Set(expandedGroups.value)
    return
  }
  expandedGroups.value.add(group.path)
  expandedGroups.value = new Set(expandedGroups.value)
  await loadSubdirectory(group)
}

const onItemCheckbox = (id: string, checked: boolean | 'indeterminate') => {
  if (checked === true) {
    if (!selected.value.includes(id)) {
      selected.value = [...selected.value, id]
    }
  } else {
    selected.value = selected.value.filter((s) => s !== id)
  }
}

const onGroupCheckbox = (group: FileNode, checked: boolean | 'indeterminate') => {
  const ids = (group.children ?? []).map((c) => c.path)
  if (ids.length === 0) return
  if (checked === true) {
    const merged = new Set(selected.value)
    for (const id of ids) merged.add(id)
    selected.value = Array.from(merged)
  } else {
    const drop = new Set(ids)
    selected.value = selected.value.filter((s) => !drop.has(s))
  }
}

const groupSelectionState = (group: FileNode): boolean | 'indeterminate' => {
  const ids = (group.children ?? []).map((c) => c.path)
  if (ids.length === 0) return false
  const selectedCount = ids.filter((id) => selected.value.includes(id)).length
  if (selectedCount === 0) return false
  if (selectedCount === ids.length) return true
  return 'indeterminate'
}

const clearSelection = () => {
  selected.value = []
}

const removeSelected = (id: string) => {
  selected.value = selected.value.filter((s) => s !== id)
}

const titleForId = (id: string) => {
  for (const group of rootNodes.value) {
    for (const child of group.children ?? []) {
      if (child.path === id) return child.name
    }
  }
  return ''
}

const formatModified = (d: Date) => {
  try {
    return d.toISOString().slice(0, 16).replace('T', ' ')
  } catch {
    return ''
  }
}
</script>
