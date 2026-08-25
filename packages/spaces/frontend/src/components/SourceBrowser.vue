<template>
  <div class="source-browser">
    <div class="mb-4 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <h3 class="text-lg font-medium text-foreground">{{ presentation.headerTitle }}</h3>
        <Badge variant="secondary">{{ selected.length }} selected</Badge>
      </div>
      <Button variant="outline" size="sm" :disabled="selected.length === 0" @click="clearSelection">
        Clear Selection
      </Button>
    </div>

    <div class="h-[450px]">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full">
        <!-- Left: source tree -->
        <div class="border-2 border-border rounded-lg overflow-hidden flex flex-col h-full">
          <div class="bg-muted border-b border-border px-4 py-2 flex-shrink-0">
            <div class="flex items-center gap-2 text-sm text-muted-foreground">
              <component :is="presentation.panelIcon" class="w-4 h-4" />
              <span class="truncate">{{ panelLabel }}</span>
            </div>
          </div>

          <div class="flex-1 min-h-0">
            <ScrollArea class="h-full">
              <div class="p-2 space-y-0.5">
                <div v-if="isInitialLoading" class="flex items-center justify-center h-[200px]">
                  <div class="text-muted-foreground">{{ presentation.loadingText }}</div>
                </div>
                <div
                  v-else-if="rootPermissionDenied"
                  class="flex items-center gap-2 p-4 text-sm text-amber-600 dark:text-amber-400"
                >
                  <ShieldAlert class="w-4 h-4 flex-shrink-0" />
                  <span class="flex-1">Permission required to access this source</span>
                  <Button variant="outline" size="sm" @click="retryRootDirectory">
                    Grant Access
                  </Button>
                </div>
                <div v-else-if="error" class="p-4 text-sm text-destructive">
                  {{ error }}
                </div>
                <div v-else-if="rootNodes.length === 0" class="p-4 text-sm text-muted-foreground">
                  {{ presentation.emptyText }}
                </div>
                <template v-else>
                  <SourceBrowserNode
                    v-for="node in rootNodes"
                    :key="node.path"
                    :node="node"
                    :dtype="dtype"
                    :container-mode="presentation.containerMode"
                    :selected="selected"
                    :locked-selection="lockedSelection"
                    :expanded="expanded"
                    @toggle-expand="toggleExpand"
                    @toggle-select="toggleSelect"
                    @load-more="loadMore"
                    @retry-permission="retryDirectory"
                  />
                  <div v-if="rootNextCursor" class="px-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      class="h-7 text-xs text-muted-foreground"
                      :disabled="rootLoadingMore"
                      @click="loadMoreRoot"
                    >
                      {{ rootLoadingMore ? 'Loading…' : 'Load more' }}
                    </Button>
                  </div>
                </template>
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
              {{ presentation.selectionTitle }}
            </h4>
            <Badge
              variant="secondary"
              class="bg-blue-100 dark:bg-blue-950/50 text-blue-800 dark:text-blue-200"
            >
              {{ selected.length }} new
            </Badge>
          </div>

          <div v-if="lockedSelection.length > 0 || selected.length > 0" class="flex-1 min-h-0">
            <ScrollArea class="h-full">
              <div class="space-y-1 pr-4">
                <!-- Already-selected (locked): shown for context, cannot be removed -->
                <div
                  v-for="id in lockedSelection"
                  :key="`locked-${id}`"
                  class="flex items-center gap-2 text-xs text-muted-foreground bg-muted/60 border border-border rounded-md px-3 py-2"
                >
                  <component
                    :is="chipIcon(id)"
                    class="w-4 h-4 flex-shrink-0 opacity-70"
                    :class="chipIconClass(id)"
                  />
                  <span class="flex-1 truncate">
                    <span :class="{ 'font-mono text-sm': dtype === 'local_file' }">
                      {{ dtype === 'local_file' ? id : titleForId(id) }}
                    </span>
                  </span>
                  <span class="text-[10px] uppercase tracking-wide flex-shrink-0 pr-2">Added</span>
                </div>

                <!-- New selections: removable -->
                <div
                  v-for="id in selected"
                  :key="id"
                  class="flex items-center gap-2 text-xs text-blue-900 dark:text-blue-100 bg-blue-100 dark:bg-blue-900/60 border border-blue-200 dark:border-blue-700 rounded-md px-3 py-2"
                >
                  <component
                    :is="chipIcon(id)"
                    class="w-4 h-4 flex-shrink-0"
                    :class="chipIconClass(id)"
                  />
                  <span class="flex-1 truncate">
                    <span
                      v-if="dtype !== 'local_file'"
                      class="font-mono text-[11px] text-blue-700 dark:text-blue-300 mr-2"
                    >
                      {{ id }}
                    </span>
                    <span :class="{ 'font-mono text-sm': dtype === 'local_file' }">
                      {{ dtype === 'local_file' ? id : titleForId(id) }}
                    </span>
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
              <component :is="presentation.panelIcon" class="w-8 h-8 text-blue-400" />
            </div>
            <h5 class="text-blue-900 dark:text-blue-100 font-medium mb-2">
              {{ presentation.selectionEmptyTitle }}
            </h5>
            <p class="text-blue-700 dark:text-blue-300 text-sm">
              {{ presentation.selectionEmptyHint }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <div class="text-sm text-muted-foreground mt-4">
      <p>{{ presentation.footerHint }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, type Component } from 'vue'
import { FileText, HardDrive, Newspaper, PenLine, ShieldAlert, X } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import SourceBrowserNode from './SourceBrowserNode.vue'
import { useFileIcon } from '@/composables/useFileIcon'
import { useSourceBrowser, type FileNode } from '@/composables/useSourceBrowser'

interface SourcePresentation {
  headerTitle: string
  panelIcon: Component
  panelLabel: string
  loadingText: string
  emptyText: string
  selectionTitle: string
  selectionEmptyTitle: string
  selectionEmptyHint: string
  footerHint: string
  containerMode: 'self' | 'group'
}

const PRESENTATIONS: Record<string, SourcePresentation> = {
  local_file: {
    headerTitle: 'Select Files & Directories',
    panelIcon: HardDrive,
    panelLabel: 'Home Directory (~)',
    loadingText: 'Loading files…',
    emptyText: 'No files found in home directory',
    selectionTitle: 'Selected Files & Directories',
    selectionEmptyTitle: 'No files selected',
    selectionEmptyHint:
      'Browse the file tree on the left and select files or folders to see them here.',
    footerHint: 'Click folders to expand/collapse. Use checkboxes to select files and directories.',
    containerMode: 'self',
  },
  wordpress: {
    headerTitle: 'Select posts & pages',
    panelIcon: Newspaper,
    panelLabel: 'Connected WordPress site',
    loadingText: 'Connecting…',
    emptyText: 'No post types configured.',
    selectionTitle: 'Selected Posts & Pages',
    selectionEmptyTitle: 'No items selected',
    selectionEmptyHint: 'Expand a post type on the left and tick the items you want to ingest.',
    footerHint:
      'Click a post type to expand. Use checkboxes to select individual items or whole groups.',
    containerMode: 'group',
  },
  blogspot: {
    headerTitle: 'Select blogs & posts',
    panelIcon: PenLine,
    panelLabel: 'Blogger blogs',
    loadingText: 'Connecting…',
    emptyText: 'No blogs resolved from those URLs.',
    selectionTitle: 'Selected Blogs & Posts',
    selectionEmptyTitle: 'No items selected',
    selectionEmptyHint:
      'Tick a blog to follow all of its posts, or expand it and pick individual posts.',
    footerHint:
      'Ticking a blog follows the whole blog, including posts published later. Expand it to pick individual posts instead.',
    containerMode: 'self',
  },
}

const FALLBACK: SourcePresentation = {
  headerTitle: 'Select items',
  panelIcon: FileText,
  panelLabel: 'Source',
  loadingText: 'Loading…',
  emptyText: 'No items found.',
  selectionTitle: 'Selected items',
  selectionEmptyTitle: 'No items selected',
  selectionEmptyHint: 'Browse the source on the left and tick the items you want to ingest.',
  footerHint: 'Use checkboxes to select items.',
  containerMode: 'self',
}

const props = withDefaults(
  defineProps<{
    dtype: string
    configuration?: Record<string, unknown>
    modelValue: string[]
    // Already-saved selection: shown selected but immutable (add-only mode).
    // modelValue holds only the NEW selections.
    lockedSelection?: string[]
    // When set, browse this existing dataset's source server-side (stored
    // credentials) instead of passing client-supplied configuration.
    datasetName?: string
  }>(),
  { configuration: () => ({}), lockedSelection: () => [] },
)

const lockedSet = computed(() => new Set(props.lockedSelection))

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const selected = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const presentation = computed(() => PRESENTATIONS[props.dtype] ?? FALLBACK)

const panelLabel = computed(() => {
  if (props.dtype === 'blogspot') {
    const urls = props.configuration?.blogUrls as string | undefined
    if (urls) {
      const hosts = urls
        .split(',')
        .map((u) =>
          u
            .trim()
            .replace(/^https?:\/\//, '')
            .replace(/\/$/, ''),
        )
        .filter(Boolean)
      if (hosts.length === 1) return hosts[0]
      if (hosts.length > 1) return `${hosts[0]} +${hosts.length - 1} more`
    }
  }
  if (props.dtype === 'wordpress') {
    const url = props.configuration?.siteUrl as string | undefined
    if (url) return url.replace(/^https?:\/\//, '').replace(/\/$/, '')
  }
  return presentation.value.panelLabel
})

const expanded = ref<Set<string>>(new Set())

const { getFileIcon, getFileIconColor } = useFileIcon()
const {
  rootNodes,
  rootNextCursor,
  rootLoadingMore,
  error,
  isInitialLoading,
  rootPermissionDenied,
  loadRootDirectory,
  loadSubdirectory,
  loadMore,
  loadMoreRoot,
  retryDirectory,
  retryRootDirectory,
} = useSourceBrowser(props.dtype, props.configuration, props.datasetName)

onMounted(loadRootDirectory)

const toggleExpand = async (node: FileNode) => {
  const next = new Set(expanded.value)
  if (next.has(node.path)) {
    next.delete(node.path)
  } else {
    next.add(node.path)
    await loadSubdirectory(node)
  }
  expanded.value = next
}

const toggleSelect = (paths: string[], on: boolean) => {
  const current = [...selected.value]
  // Locked items belong to the saved selection — never add or remove them here.
  const editable = paths.filter((path) => !lockedSet.value.has(path))
  if (on) {
    for (const path of editable) {
      if (!current.includes(path)) current.push(path)
    }
  } else {
    for (const path of editable) {
      const i = current.indexOf(path)
      if (i > -1) current.splice(i, 1)
    }
  }
  selected.value = current
}

const clearSelection = () => {
  selected.value = []
}

const removeSelected = (id: string) => {
  selected.value = selected.value.filter((s) => s !== id)
}

const titleForId = (id: string): string => {
  const walk = (nodes: FileNode[]): string | null => {
    for (const node of nodes) {
      if (node.path === id) return node.name
      if (node.children) {
        const found = walk(node.children)
        if (found) return found
      }
    }
    return null
  }
  return walk(rootNodes.value) ?? id
}

const chipIcon = (id: string): Component => {
  if (props.dtype === 'local_file') return getFileIcon(id, false, rootNodes.value)
  return FileText
}

const chipIconClass = (id: string): string => {
  if (props.dtype === 'local_file') return getFileIconColor(id, rootNodes.value)
  return ''
}

defineExpose({ rootNodes })
</script>
