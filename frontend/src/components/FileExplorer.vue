<template>
  <div class="file-explorer">
    <div class="file-explorer-header mb-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <h3 class="text-lg font-medium text-gray-900">Select Files & Directories</h3>
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
        <div class="file-tree border-2 border-gray-200 rounded-lg overflow-hidden flex flex-col h-full">
          <div class="bg-gray-50 border-b border-gray-200 px-4 py-2 flex-shrink-0">
            <div class="flex items-center gap-2 text-sm text-gray-600">
              <HardDrive class="w-4 h-4" />
              <span>Home Directory (~)</span>
            </div>
          </div>
          
          <div class="file-tree-content flex-1 overflow-y-auto p-2">
            <TreeNode
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
        <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 flex flex-col h-full">
          <div class="flex items-center justify-between mb-4 flex-shrink-0">
            <h4 class="text-sm font-medium text-blue-900">Selected Files & Directories</h4>
            <Badge variant="secondary" class="bg-blue-100 text-blue-800">
              {{ selectedFiles.length }} item{{ selectedFiles.length !== 1 ? 's' : '' }}
            </Badge>
          </div>
          
          <div v-if="selectedFiles.length > 0" class="flex-1 overflow-y-auto">
            <div class="space-y-1">
              <div 
                v-for="path in selectedFiles" 
                :key="path"
                class="flex items-center gap-2 text-xs text-blue-800 bg-white rounded px-3 py-2 shadow-sm"
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
            <div class="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mb-4">
              <HardDrive class="w-8 h-8 text-blue-400" />
            </div>
            <h5 class="text-blue-900 font-medium mb-2">No files selected</h5>
            <p class="text-blue-700 text-sm">Browse the file tree on the left and select files or folders to see them here.</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Hint Text Below Both Panels -->
    <div class="text-sm text-gray-500 mt-4">
      <p>Click folders to expand/collapse. Use checkboxes to select files and directories.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { HardDrive } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import TreeNode from './FileExplorerTreeNode.vue'
import { useFileIcon } from '@/composables/useFileIcon'

interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  size?: number
  modifiedTime?: Date
  children?: FileNode[]
}

const props = defineProps<{
  modelValue: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const selectedFiles = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const expandedDirs = ref<Set<string>>(new Set())

const { getFileIcon, getFileIconColor } = useFileIcon()

// Mock file system structure - in a real app, this would come from an API
const rootNodes = ref<FileNode[]>([
  {
    name: 'Documents',
    path: '~/Documents',
    type: 'directory',
    children: [
      {
        name: 'Research',
        path: '~/Documents/Research',
        type: 'directory',
        children: [
          { name: 'quantum_computing_survey.pdf', path: '~/Documents/Research/quantum_computing_survey.pdf', type: 'file', size: 3145728 },
          { name: 'ml_algorithms_comparison.pdf', path: '~/Documents/Research/ml_algorithms_comparison.pdf', type: 'file', size: 2621440 },
          { name: 'thesis_draft.tex', path: '~/Documents/Research/thesis_draft.tex', type: 'file', size: 524288 },
          { name: 'thesis_draft.pdf', path: '~/Documents/Research/thesis_draft.pdf', type: 'file', size: 1572864 },
          { name: 'references.bib', path: '~/Documents/Research/references.bib', type: 'file', size: 131072 },
          { name: 'notes.md', path: '~/Documents/Research/notes.md', type: 'file', size: 65536 }
        ]
      },
      {
        name: 'Work',
        path: '~/Documents/Work',
        type: 'directory',
        children: [
          { name: 'quarterly_report_2024.docx', path: '~/Documents/Work/quarterly_report_2024.docx', type: 'file', size: 524288 },
          { name: 'project_proposal.docx', path: '~/Documents/Work/project_proposal.docx', type: 'file', size: 786432 },
          { name: 'meeting_notes.txt', path: '~/Documents/Work/meeting_notes.txt', type: 'file', size: 32768 },
          { name: 'budget_analysis.xlsx', path: '~/Documents/Work/budget_analysis.xlsx', type: 'file', size: 1048576 },
          { name: 'presentation.pptx', path: '~/Documents/Work/presentation.pptx', type: 'file', size: 5242880 }
        ]
      },
      {
        name: 'Personal',
        path: '~/Documents/Personal',
        type: 'directory',
        children: [
          { name: 'resume.pdf', path: '~/Documents/Personal/resume.pdf', type: 'file', size: 262144 },
          { name: 'cover_letter.odt', path: '~/Documents/Personal/cover_letter.odt', type: 'file', size: 131072 },
          { name: 'travel_itinerary.rtf', path: '~/Documents/Personal/travel_itinerary.rtf', type: 'file', size: 98304 }
        ]
      }
    ]
  },
  {
    name: 'Downloads',
    path: '~/Downloads',
    type: 'directory',
    children: [
      { name: 'ubuntu-22.04.iso', path: '~/Downloads/ubuntu-22.04.iso', type: 'file', size: 3865470976 },
      { name: 'vscode-linux.deb', path: '~/Downloads/vscode-linux.deb', type: 'file', size: 89128960 },
      { name: 'research_paper.pdf', path: '~/Downloads/research_paper.pdf', type: 'file', size: 2097152 },
      { name: 'dataset.zip', path: '~/Downloads/dataset.zip', type: 'file', size: 524288000 }
    ]
  },
  {
    name: 'Projects',
    path: '~/Projects',
    type: 'directory',
    children: [
      {
        name: 'machine-learning',
        path: '~/Projects/machine-learning',
        type: 'directory',
        children: [
          { name: 'train_model.py', path: '~/Projects/machine-learning/train_model.py', type: 'file', size: 16384 },
          { name: 'data_preprocessing.py', path: '~/Projects/machine-learning/data_preprocessing.py', type: 'file', size: 12288 },
          { name: 'requirements.txt', path: '~/Projects/machine-learning/requirements.txt', type: 'file', size: 2048 },
          { name: 'README.md', path: '~/Projects/machine-learning/README.md', type: 'file', size: 8192 },
          { name: 'config.json', path: '~/Projects/machine-learning/config.json', type: 'file', size: 1024 },
          { name: 'model_weights.h5', path: '~/Projects/machine-learning/model_weights.h5', type: 'file', size: 134217728 }
        ]
      },
      {
        name: 'web-app',
        path: '~/Projects/web-app',
        type: 'directory',
        children: [
          { name: 'index.html', path: '~/Projects/web-app/index.html', type: 'file', size: 4096 },
          { name: 'style.css', path: '~/Projects/web-app/style.css', type: 'file', size: 8192 },
          { name: 'app.js', path: '~/Projects/web-app/app.js', type: 'file', size: 32768 },
          { name: 'package.json', path: '~/Projects/web-app/package.json', type: 'file', size: 2048 },
          { name: '.gitignore', path: '~/Projects/web-app/.gitignore', type: 'file', size: 512 }
        ]
      }
    ]
  },
  {
    name: 'Data',
    path: '~/Data',
    type: 'directory',
    children: [
      {
        name: 'datasets',
        path: '~/Data/datasets',
        type: 'directory',
        children: [
          { name: 'sales_2024.csv', path: '~/Data/datasets/sales_2024.csv', type: 'file', size: 10485760 },
          { name: 'customer_data.csv', path: '~/Data/datasets/customer_data.csv', type: 'file', size: 5242880 },
          { name: 'inventory.json', path: '~/Data/datasets/inventory.json', type: 'file', size: 2097152 },
          { name: 'analytics_export.xlsx', path: '~/Data/datasets/analytics_export.xlsx', type: 'file', size: 8388608 }
        ]
      },
      {
        name: 'backups',
        path: '~/Data/backups',
        type: 'directory',
        children: [
          { name: 'backup_2024_01.tar.gz', path: '~/Data/backups/backup_2024_01.tar.gz', type: 'file', size: 1073741824 },
          { name: 'database_dump.sql', path: '~/Data/backups/database_dump.sql', type: 'file', size: 268435456 },
          { name: 'config_backup.zip', path: '~/Data/backups/config_backup.zip', type: 'file', size: 16777216 }
        ]
      }
    ]
  },
  {
    name: 'Books',
    path: '~/Books',
    type: 'directory',
    children: [
      { name: 'deep_learning.pdf', path: '~/Books/deep_learning.pdf', type: 'file', size: 41943040 },
      { name: 'clean_code.epub', path: '~/Books/clean_code.epub', type: 'file', size: 3145728 },
      { name: 'design_patterns.epub', path: '~/Books/design_patterns.epub', type: 'file', size: 2621440 },
      { name: 'algorithms_introduction.pdf', path: '~/Books/algorithms_introduction.pdf', type: 'file', size: 52428800 },
      { name: 'linux_bible.pdf', path: '~/Books/linux_bible.pdf', type: 'file', size: 31457280 }
    ]
  },
  {
    name: '.config',
    path: '~/.config',
    type: 'directory',
    children: [
      { name: 'settings.json', path: '~/.config/settings.json', type: 'file', size: 4096 },
      { name: 'preferences.xml', path: '~/.config/preferences.xml', type: 'file', size: 8192 },
      { name: 'shortcuts.yaml', path: '~/.config/shortcuts.yaml', type: 'file', size: 2048 }
    ]
  },
  { name: '.bashrc', path: '~/.bashrc', type: 'file', size: 3584 },
  { name: '.vimrc', path: '~/.vimrc', type: 'file', size: 2048 },
  { name: '.gitconfig', path: '~/.gitconfig', type: 'file', size: 1024 },
  { name: 'README.md', path: '~/README.md', type: 'file', size: 4096 }
])

const toggleDirectory = (path: string) => {
  const newExpanded = new Set(expandedDirs.value)
  if (newExpanded.has(path)) {
    newExpanded.delete(path)
  } else {
    newExpanded.add(path)
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