<template>
  <div class="file-explorer">
    <div class="file-explorer-header mb-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <h3 class="text-lg font-medium text-foreground">Select Files & Directories</h3>
          <Badge variant="secondary">{{ selectedFiles.length }} selected</Badge>
        </div>
        <div class="flex items-center gap-2">
          <Button
            @click="clearSelection"
            variant="outline"
            size="sm"
            :disabled="selectedFiles.length === 0"
          >
            Clear Selection
          </Button>
        </div>
      </div>
    </div>

    <!-- Split Layout Container -->
    <div class="h-[450px]">
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 h-full">
        <!-- Left Panel: File Browser -->
        <div
          class="file-tree border-2 border-border rounded-lg overflow-hidden flex flex-col h-full"
        >
          <div class="bg-muted border-b border-border px-4 py-2 flex-shrink-0">
            <div class="flex items-center gap-2 text-sm text-muted-foreground">
              <HardDrive class="w-4 h-4" />
              <span>Home Directory (~)</span>
            </div>
          </div>

          <div class="file-tree-content flex-1 overflow-y-auto p-2">
            <div v-if="isInitialLoading" class="flex items-center justify-center h-full">
              <div class="text-muted-foreground">Loading files...</div>
            </div>
            <div v-else-if="error" class="p-4 text-sm text-destructive">
              Error loading files: {{ error }}
            </div>
            <div v-else-if="rootNodes.length === 0" class="p-4 text-sm text-muted-foreground">
              No files found in home directory
            </div>
            <TreeNode
              v-else
              v-for="node in rootNodes"
              :key="node.path"
              :node="node"
              :selected-files="selectedFiles"
              :expanded-dirs="expandedDirs"
              @toggle-dir="toggleDirectory"
              @toggle-file="toggleFile"
              @toggle-selection="toggleSelection"
            />
          </div>
        </div>

        <!-- Right Panel: Selection Preview -->
        <div class="bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800 rounded-lg p-4 flex flex-col h-full">
          <div class="flex items-center justify-between mb-4 flex-shrink-0">
            <h4 class="text-sm font-medium text-blue-900 dark:text-blue-100">Selected Files & Directories</h4>
            <Badge variant="secondary" class="bg-blue-100 dark:bg-blue-950/50 text-blue-800 dark:text-blue-200">
              {{ selectedFiles.length }} item{{ selectedFiles.length !== 1 ? 's' : '' }}
            </Badge>
          </div>

          <div v-if="selectedFiles.length > 0" class="flex-1 overflow-y-auto">
            <div class="space-y-1">
              <div
                v-for="path in selectedFiles"
                :key="path"
                class="flex items-center gap-2 text-xs text-blue-800 dark:text-blue-200 bg-card rounded px-3 py-2 shadow-sm"
              >
                <component
                  :is="getFileIconForPath(path)"
                  class="w-4 h-4 flex-shrink-0"
                  :class="getFileIconColorForPath(path)"
                />
                <span class="truncate font-mono text-sm">{{ path }}</span>
              </div>
            </div>
          </div>

          <div v-else class="flex-1 flex flex-col items-center justify-center text-center">
            <div class="w-16 h-16 bg-blue-100 dark:bg-blue-950/50 rounded-full flex items-center justify-center mb-4">
              <HardDrive class="w-8 h-8 text-blue-400" />
            </div>
            <h5 class="text-blue-900 dark:text-blue-100 font-medium mb-2">No files selected</h5>
            <p class="text-blue-700 dark:text-blue-300 text-sm">
              Browse the file tree on the left and select files or folders to see them here.
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Hint Text Below Both Panels -->
    <div class="text-sm text-muted-foreground mt-4">
      <p>Click folders to expand/collapse. Use checkboxes to select files and directories.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { HardDrive } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import TreeNode from './FileExplorerTreeNode.vue'
import { useFileIcon } from '@/composables/useFileIcon'
import { useDatasetBrowser, type FileNode } from '@/composables/useDatasetBrowser'

const props = defineProps<{
  modelValue: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const selectedFiles = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const expandedDirs = ref<Set<string>>(new Set())

const { getFileIcon, getFileIconColor } = useFileIcon()
const { rootNodes, error, isInitialLoading, loadRootDirectory, loadSubdirectory } = useDatasetBrowser()

// Load initial data on mount
onMounted(async () => {
  await loadRootDirectory()
})

const toggleDirectory = async (node: FileNode) => {
  const path = node.path
  const newExpanded = new Set(expandedDirs.value)
  if (newExpanded.has(path)) {
    newExpanded.delete(path)
  } else {
    newExpanded.add(path)
    // Load subdirectory content if not already loaded
    await loadSubdirectory(node)
  }
  expandedDirs.value = newExpanded
}

const toggleFile = (path: string, event: MouseEvent) => {
  const newSelection = [...selectedFiles.value]
  const index = newSelection.indexOf(path)

  if (event.ctrlKey || event.metaKey) {
    // Multi-select mode
    if (index > -1) {
      newSelection.splice(index, 1)
    } else {
      newSelection.push(path)
    }
  } else {
    // Single select mode
    if (index > -1 && newSelection.length === 1) {
      // Deselect if clicking the only selected file
      newSelection.splice(index, 1)
    } else {
      // Select only this file
      selectedFiles.value = [path]
      return
    }
  }

  selectedFiles.value = newSelection
}

const toggleSelection = (paths: string[], selected: boolean) => {
  const newSelection = [...selectedFiles.value]

  if (selected) {
    // Add paths that aren't already selected
    for (const path of paths) {
      if (!newSelection.includes(path)) {
        newSelection.push(path)
      }
    }
  } else {
    // Remove paths that are selected
    for (const path of paths) {
      const index = newSelection.indexOf(path)
      if (index > -1) {
        newSelection.splice(index, 1)
      }
    }
  }

  selectedFiles.value = newSelection
}

const clearSelection = () => {
  selectedFiles.value = []
}

// Helper functions using composable
const getFileIconForPath = (path: string) => getFileIcon(path, false, rootNodes.value)
const getFileIconColorForPath = (path: string) => getFileIconColor(path, rootNodes.value)
</script>

<style scoped>
.file-tree-content {
  min-height: 200px;
}
</style>
