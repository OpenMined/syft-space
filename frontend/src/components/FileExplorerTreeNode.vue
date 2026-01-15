<template>
  <div class="tree-node">
    <div
      class="node-content group flex items-center gap-2 px-2 py-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded cursor-pointer select-none"
      :class="{
        'bg-blue-50 dark:bg-blue-950/50': isSelected,
        'font-medium': node.type === 'directory',
      }"
      :style="{ paddingLeft: `${depth * 20}px` }"
      @click="handleClick($event)"
    >
      <!-- Directory toggle icon or spacer -->
      <div class="w-6 h-6 flex items-center justify-center flex-shrink-0">
        <button
          v-if="node.type === 'directory'"
          @click.stop="toggleDir"
          class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"
        >
          <ChevronRight class="w-4 h-4 transition-transform" :class="{ 'rotate-90': isExpanded }" />
        </button>
      </div>

      <!-- Checkbox -->
      <Checkbox
        :model-value="isSelected"
        @click.stop
        @update:model-value="handleCheckboxChange"
        class="flex-shrink-0 border-gray-400 dark:border-gray-500 data-[state=checked]:bg-blue-600 data-[state=checked]:border-blue-600 data-[state=checked]:text-white"
      />

      <!-- File/Folder icon -->
      <component :is="getIcon()" class="w-4 h-4 flex-shrink-0" :class="getIconClass()" />

      <!-- Name -->
      <span class="text-sm truncate flex-1">{{ node.name }}</span>

      <!-- File size -->
      <span v-if="node.type === 'file' && node.size" class="text-xs text-muted-foreground">
        {{ formatFileSize(node.size) }}
      </span>
    </div>

    <!-- Children -->
    <div v-if="node.type === 'directory' && isExpanded" class="ml-2">
      <div
        v-if="node.isLoading"
        class="flex items-center gap-2 px-2 py-1 text-sm text-muted-foreground"
        :style="{ paddingLeft: `${(depth + 1) * 20}px` }"
      >
        <div
          class="w-4 h-4 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent"
        ></div>
        Loading...
      </div>
      <TreeNode
        v-else
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        :depth="depth + 1"
        :selected-files="selectedFiles"
        :expanded-dirs="expandedDirs"
        @toggle-dir="(node: FileNode) => $emit('toggle-dir', node)"
        @toggle-file="(path: string, event: MouseEvent) => $emit('toggle-file', path, event)"
        @toggle-selection="
          (paths: string[], selected: boolean) => $emit('toggle-selection', paths, selected)
        "
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import TreeNode from './FileExplorerTreeNode.vue'
import { ChevronRight } from 'lucide-vue-next'
import { Checkbox } from '@/components/ui/checkbox'
import { useFileIcon } from '@/composables/useFileIcon'

interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  size?: number
  modifiedTime?: Date
  children?: FileNode[]
  isLoading?: boolean
  hasLoaded?: boolean
}

const props = withDefaults(
  defineProps<{
    node: FileNode
    depth?: number
    selectedFiles: string[]
    expandedDirs: Set<string>
  }>(),
  {
    depth: 0,
  },
)

const emit = defineEmits<{
  'toggle-dir': [node: FileNode]
  'toggle-file': [path: string, event: MouseEvent]
  'toggle-selection': [paths: string[], selected: boolean]
}>()

const isExpanded = computed(() => props.expandedDirs.has(props.node.path))

const { getFileIcon, getFileIconColor, formatFileSize } = useFileIcon()

const isSelected = computed(() => {
  return props.selectedFiles.includes(props.node.path)
})

const getIcon = () => getFileIcon(props.node.path, isExpanded.value, [props.node])
const getIconClass = () => getFileIconColor(props.node.path, [props.node])

const toggleDir = () => {
  emit('toggle-dir', props.node)
}

const handleClick = (event: MouseEvent) => {
  if (
    (event.target as HTMLElement).closest('button[data-slot="checkbox"]') ||
    (event.target as HTMLElement).closest('button:not([data-slot="checkbox"])')
  ) {
    return
  }

  if (props.node.type === 'directory') {
    toggleDir()
  }
}

const handleCheckboxChange = (checked: boolean | 'indeterminate') => {
  if (typeof checked === 'boolean') {
    emit('toggle-selection', [props.node.path], checked)
  }
}
</script>
