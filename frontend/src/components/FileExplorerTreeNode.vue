<template>
  <div class="tree-node">
    <div
      class="node-content group flex items-center gap-2 px-2 py-1 hover:bg-gray-100 rounded cursor-pointer select-none"
      :class="{
        'bg-blue-50': isSelected,
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
          class="p-1 hover:bg-gray-200 rounded transition-colors"
        >
          <ChevronRight class="w-4 h-4 transition-transform" :class="{ 'rotate-90': isExpanded }" />
        </button>
      </div>

      <!-- Icon/Checkbox container -->
      <div class="relative w-4 h-4 flex-shrink-0">
        <!-- File/Folder icon - always hidden, replaced by checkbox -->
        <component
          :is="getIcon()"
          class="w-4 h-4 absolute inset-0 opacity-0"
          :class="getIconClass()"
        />

        <!-- Selection checkbox - always visible -->
        <input
          ref="checkboxRef"
          type="checkbox"
          :checked="isSelected || isPartiallySelected"
          @click.stop
          @change="handleCheckboxChange"
          class="h-4 w-4 absolute inset-0 text-blue-600 rounded border-gray-300 focus:ring-blue-500 opacity-100 cursor-pointer"
        />
      </div>

      <!-- File/Folder icon -->
      <component :is="getIcon()" class="w-4 h-4 flex-shrink-0" :class="getIconClass()" />

      <!-- Name -->
      <span class="text-sm truncate flex-1">{{ node.name }}</span>

      <!-- File size -->
      <span v-if="node.type === 'file' && node.size" class="text-xs text-gray-500">
        {{ formatFileSize(node.size) }}
      </span>
    </div>

    <!-- Children -->
    <div v-if="node.type === 'directory' && isExpanded && node.children" class="ml-2">
      <TreeNode
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        :depth="depth + 1"
        :selected-files="selectedFiles"
        :expanded-dirs="expandedDirs"
        @toggle-dir="$emit('toggle-dir', $event)"
        @toggle-file="(path: string, event: MouseEvent) => $emit('toggle-file', path, event)"
        @toggle-selection="
          (paths: string[], selected: boolean) => $emit('toggle-selection', paths, selected)
        "
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watchEffect } from 'vue'
// Self-reference for recursive component
import TreeNode from './FileExplorerTreeNode.vue'
import { ChevronRight } from 'lucide-vue-next'
import { useFileIcon } from '@/composables/useFileIcon'

interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  size?: number
  modifiedTime?: Date
  children?: FileNode[]
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
  'toggle-dir': [path: string]
  'toggle-file': [path: string, event: MouseEvent]
  'toggle-selection': [paths: string[], selected: boolean]
}>()

const checkboxRef = ref<HTMLInputElement>()
const isExpanded = computed(() => props.expandedDirs.has(props.node.path))

const { getFileIcon, getFileIconColor, formatFileSize } = useFileIcon()

// For both files and directories, check if this specific item is selected
const isSelected = computed(() => {
  return props.selectedFiles.includes(props.node.path)
})

// No partial selection needed since we're selecting the folder itself, not its contents
const isPartiallySelected = computed(() => false)

// Set indeterminate state for checkbox
watchEffect(() => {
  if (checkboxRef.value) {
    checkboxRef.value.indeterminate = isPartiallySelected.value
  }
})

const getIcon = () => getFileIcon(props.node.path, isExpanded.value, [props.node])
const getIconClass = () => getFileIconColor(props.node.path, [props.node])

const toggleDir = () => {
  emit('toggle-dir', props.node.path)
}

const handleClick = (event: MouseEvent) => {
  // Don't do anything if clicking on the checkbox or chevron button
  if (
    (event.target as HTMLElement).matches('input[type="checkbox"]') ||
    (event.target as HTMLElement).closest('button')
  ) {
    return
  }

  if (props.node.type === 'directory') {
    toggleDir()
  }
  // Don't toggle file selection on click anymore - only via checkbox
}

const handleCheckboxChange = (event: Event) => {
  const checked = (event.target as HTMLInputElement).checked

  // For both files and directories, just toggle the item itself
  emit('toggle-selection', [props.node.path], checked)
}
</script>
