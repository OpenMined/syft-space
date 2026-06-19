<template>
  <div class="source-node">
    <TooltipProvider :delay-duration="400">
      <Tooltip>
        <TooltipTrigger as-child>
          <div
            class="group flex items-center gap-2 px-2 py-1 rounded hover:bg-muted cursor-pointer select-none"
            :class="{ 'bg-blue-50 dark:bg-blue-950/50': isLeafSelected }"
            :style="{ paddingLeft: `${depth * 20 + 8}px` }"
            @click="onRowClick"
          >
            <div class="w-5 h-5 flex items-center justify-center flex-shrink-0">
              <component
                v-if="isContainer"
                :is="isExpanded ? ChevronDown : ChevronRight"
                class="w-4 h-4 text-muted-foreground"
              />
            </div>

            <Checkbox
              :model-value="checkboxState"
              @click.stop
              @update:model-value="onCheckbox"
              class="flex-shrink-0"
            />

            <component :is="iconComponent" class="w-4 h-4 flex-shrink-0" :class="iconClass" />

            <div class="flex-1 min-w-0 flex items-center gap-1.5">
              <span class="text-sm truncate min-w-0" :class="{ 'font-medium': isContainer }">
                {{ node.name }}
              </span>
              <Badge
                v-if="node.status === 'private'"
                variant="outline"
                class="flex-shrink-0 h-4 px-1 text-[10px] font-normal text-amber-600 border-amber-300 dark:text-amber-400 dark:border-amber-700"
              >
                Private
              </Badge>
            </div>

            <span
              v-if="!isContainer && node.size"
              class="text-xs text-muted-foreground flex-shrink-0"
            >
              {{ formatFileSize(node.size) }}
            </span>

            <a
              v-if="node.link"
              :href="node.link"
              target="_blank"
              rel="noopener noreferrer"
              @click.stop
              title="Preview"
              class="flex-shrink-0 p-1 rounded opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-blue-600 dark:hover:text-blue-400 hover:bg-muted-foreground/10 transition-opacity"
            >
              <ExternalLink class="w-3.5 h-3.5" />
            </a>
          </div>
        </TooltipTrigger>
        <TooltipContent v-if="node.modifiedTime" side="bottom" align="start">
          modified {{ formatModified(node.modifiedTime) }}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>

    <div v-if="isContainer && isExpanded" class="mt-0.5 space-y-0.5">
      <div
        v-if="node.isLoading"
        class="flex items-center gap-2 px-2 py-1.5 text-xs text-muted-foreground"
        :style="{ paddingLeft: `${(depth + 1) * 20 + 8}px` }"
      >
        <div
          class="w-3.5 h-3.5 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent"
        ></div>
        Loading…
      </div>
      <div
        v-else-if="node.permissionDenied"
        class="flex items-center gap-2 px-2 py-1.5 text-xs text-amber-600 dark:text-amber-400"
        :style="{ paddingLeft: `${(depth + 1) * 20 + 8}px` }"
      >
        <ShieldAlert class="w-4 h-4 flex-shrink-0" />
        <span class="flex-1">Permission required</span>
        <Button variant="outline" size="sm" @click.stop="$emit('retry-permission', node)">
          Grant Access
        </Button>
      </div>
      <template v-else>
        <div
          v-if="(node.children?.length ?? 0) === 0 && !node.nextCursor"
          class="px-2 py-1.5 text-xs text-muted-foreground"
          :style="{ paddingLeft: `${(depth + 1) * 20 + 8}px` }"
        >
          No items found.
        </div>
        <SourceBrowserNode
          v-for="child in node.children ?? []"
          :key="child.path"
          :node="child"
          :depth="depth + 1"
          :dtype="dtype"
          :container-mode="containerMode"
          :selected="selected"
          :expanded="expanded"
          @toggle-expand="(n: FileNode) => $emit('toggle-expand', n)"
          @toggle-select="(paths: string[], on: boolean) => $emit('toggle-select', paths, on)"
          @load-more="(n: FileNode) => $emit('load-more', n)"
          @retry-permission="(n: FileNode) => $emit('retry-permission', n)"
        />
        <div
          v-if="node.nextCursor"
          :style="{ paddingLeft: `${(depth + 1) * 20 + 8}px` }"
        >
          <Button
            variant="ghost"
            size="sm"
            class="h-7 text-xs text-muted-foreground"
            :disabled="node.isLoadingMore"
            @click.stop="$emit('load-more', node)"
          >
            {{ node.isLoadingMore ? 'Loading…' : 'Load more' }}
          </Button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  ChevronDown,
  ChevronRight,
  ExternalLink,
  FileText,
  Folder,
  ShieldAlert,
} from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useFileIcon } from '@/composables/useFileIcon'
import type { FileNode } from '@/composables/useSourceBrowser'

const props = withDefaults(
  defineProps<{
    node: FileNode
    depth?: number
    dtype: string
    containerMode: 'self' | 'group'
    selected: string[]
    expanded: Set<string>
  }>(),
  { depth: 0 },
)

const emit = defineEmits<{
  'toggle-expand': [node: FileNode]
  'toggle-select': [paths: string[], on: boolean]
  'load-more': [node: FileNode]
  'retry-permission': [node: FileNode]
}>()

const { getFileIcon, getFileIconColor, formatFileSize } = useFileIcon()

const isContainer = computed(() => props.node.type === 'directory')
const isExpanded = computed(() => props.expanded.has(props.node.path))
const isLeafSelected = computed(() => props.selected.includes(props.node.path))

/** Paths of the container's currently-loaded leaf/child items. */
const childPaths = computed(() => (props.node.children ?? []).map((c) => c.path))

/** Tri-state for group-mode containers: all / some / none of loaded children selected. */
const groupState = computed<boolean | 'indeterminate'>(() => {
  const ids = childPaths.value
  if (ids.length === 0) return false
  const count = ids.filter((id) => props.selected.includes(id)).length
  if (count === 0) return false
  if (count === ids.length) return true
  return 'indeterminate'
})

const checkboxState = computed<boolean | 'indeterminate'>(() => {
  if (isContainer.value && props.containerMode === 'group') return groupState.value
  return isLeafSelected.value
})

const iconComponent = computed(() => {
  if (props.dtype === 'local_file') {
    return getFileIcon(props.node.path, isExpanded.value, [props.node])
  }
  return isContainer.value ? Folder : FileText
})

const iconClass = computed(() => {
  if (props.dtype === 'local_file') {
    return getFileIconColor(props.node.path, [props.node])
  }
  return isContainer.value ? 'text-blue-500' : 'text-muted-foreground'
})

const onCheckbox = (checked: boolean | 'indeterminate') => {
  const on = checked === true
  if (isContainer.value && props.containerMode === 'group') {
    if (childPaths.value.length === 0) return
    emit('toggle-select', childPaths.value, on)
  } else {
    emit('toggle-select', [props.node.path], on)
  }
}

const onRowClick = () => {
  if (isContainer.value) {
    emit('toggle-expand', props.node)
  } else {
    emit('toggle-select', [props.node.path], !isLeafSelected.value)
  }
}

const isSameDay = (a: Date, b: Date) =>
  a.getFullYear() === b.getFullYear() &&
  a.getMonth() === b.getMonth() &&
  a.getDate() === b.getDate()

const formatModified = (d: Date) => {
  try {
    const now = new Date()
    const time = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
    if (isSameDay(d, now)) return `Today at ${time}`
    const yesterday = new Date(now)
    yesterday.setDate(now.getDate() - 1)
    if (isSameDay(d, yesterday)) return `Yesterday at ${time}`
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: d.getFullYear() === now.getFullYear() ? undefined : 'numeric',
    })
  } catch {
    return ''
  }
}
</script>
