<template>
  <div class="tree-node">
    <div
      class="node-content group flex items-center gap-2 px-2 py-1 hover:bg-gray-100 rounded cursor-pointer select-none"
      :class="{
        'bg-blue-50': isSelected,
        'font-medium': node.type === 'directory'
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
          <ChevronRight
            class="w-4 h-4 transition-transform"
            :class="{ 'rotate-90': isExpanded }"
          />
        </button>
      </div>
      
      <!-- Icon/Checkbox container -->
      <div class="relative w-4 h-4 flex-shrink-0">
        <!-- File/Folder icon - hide on hover -->
        <component
          :is="getIcon()"
          class="w-4 h-4 absolute inset-0 transition-opacity duration-150 group-hover:opacity-0"
          :class="getIconClass()"
        />
        
        <!-- Selection checkbox - show on hover -->
        <input
          ref="checkboxRef"
          type="checkbox"
          :checked="isSelected || isPartiallySelected"
          @click.stop
          @change="handleCheckboxChange"
          class="h-4 w-4 absolute inset-0 text-blue-600 rounded border-gray-300 focus:ring-blue-500 opacity-0 group-hover:opacity-100 transition-opacity duration-150"
          :class="{
            '!opacity-100': isSelected || isPartiallySelected
          }"
        />
      </div>
      
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
        @toggle-selection="(paths: string[], selected: boolean) => $emit('toggle-selection', paths, selected)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watchEffect } from 'vue'
// Self-reference for recursive component
import TreeNode from './FileExplorerTreeNode.vue'
import { 
  ChevronRight, 
  Folder, 
  FolderOpen, 
  FileText, 
  FileSpreadsheet, 
  FileImage,
  FileVideo,
  FileArchive,
  FileCode,
  File,
  BookOpen,
  FileJson,
  Cog,
  Database,
  Binary
} from 'lucide-vue-next'

interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  size?: number
  modifiedTime?: Date
  children?: FileNode[]
}

const props = withDefaults(defineProps<{
  node: FileNode
  depth?: number
  selectedFiles: string[]
  expandedDirs: Set<string>
}>(), {
  depth: 0
})

const emit = defineEmits<{
  'toggle-dir': [path: string]
  'toggle-file': [path: string, event: MouseEvent]
  'toggle-selection': [paths: string[], selected: boolean]
}>()

const checkboxRef = ref<HTMLInputElement>()
const isExpanded = computed(() => props.expandedDirs.has(props.node.path))

// For both files and directories, check if this specific item is selected
const isSelected = computed(() => {
  return props.selectedFiles.includes(props.node.path)
})

// No partial selection needed since we're selecting the folder itself, not its contents
const isPartiallySelected = computed(() => false)

// Get all child files recursively
const getAllChildFiles = (node: FileNode): FileNode[] => {
  const files: FileNode[] = []
  
  if (node.type === 'file') {
    files.push(node)
  } else if (node.children) {
    for (const child of node.children) {
      files.push(...getAllChildFiles(child))
    }
  }
  
  return files
}

// Set indeterminate state for checkbox
watchEffect(() => {
  if (checkboxRef.value) {
    checkboxRef.value.indeterminate = isPartiallySelected.value
  }
})

const getIcon = () => {
  if (props.node.type === 'directory') {
    return isExpanded.value ? FolderOpen : Folder
  }
  
  // File icon based on extension
  const extension = props.node.name.split('.').pop()?.toLowerCase()
  const fileName = props.node.name.toLowerCase()
  
  // Special cases for config files
  if (fileName.startsWith('.') && !extension) {
    return Cog
  }
  
  switch (extension) {
    // Documents
    case 'pdf':
      return FileText
    case 'doc':
    case 'docx':
    case 'odt':
    case 'rtf':
      return FileText
    case 'txt':
    case 'md':
      return FileText
    case 'tex':
    case 'bib':
      return FileText
      
    // Spreadsheets
    case 'xls':
    case 'xlsx':
    case 'csv':
      return FileSpreadsheet
      
    // Books
    case 'epub':
      return BookOpen
      
    // Images
    case 'jpg':
    case 'jpeg':
    case 'png':
    case 'gif':
    case 'svg':
    case 'webp':
    case 'ico':
      return FileImage
      
    // Videos
    case 'mp4':
    case 'avi':
    case 'mov':
    case 'webm':
    case 'mkv':
      return FileVideo
      
    // Archives
    case 'zip':
    case 'rar':
    case 'tar':
    case 'gz':
    case '7z':
    case 'deb':
    case 'rpm':
      return FileArchive
      
    // Data files
    case 'json':
      return FileJson
    case 'xml':
    case 'yaml':
    case 'yml':
      return FileCode
      
    // Database files
    case 'sql':
    case 'db':
    case 'sqlite':
      return Database
      
    // Code files
    case 'js':
    case 'ts':
    case 'jsx':
    case 'tsx':
    case 'vue':
    case 'py':
    case 'java':
    case 'cpp':
    case 'c':
    case 'h':
    case 'hpp':
    case 'html':
    case 'css':
    case 'scss':
    case 'sass':
    case 'less':
    case 'php':
    case 'rb':
    case 'go':
    case 'rs':
    case 'sh':
    case 'bash':
      return FileCode
      
    // Binary files
    case 'exe':
    case 'bin':
    case 'so':
    case 'dll':
    case 'iso':
    case 'img':
    case 'h5':
    case 'hdf5':
      return Binary
      
    // Presentations
    case 'ppt':
    case 'pptx':
      return FileText
      
    default:
      return File
  }
}

const getIconClass = () => {
  if (props.node.type === 'directory') {
    return isExpanded.value ? 'text-blue-600' : 'text-blue-500'
  }
  
  const extension = props.node.name.split('.').pop()?.toLowerCase()
  const fileName = props.node.name.toLowerCase()
  
  // Config files
  if (fileName.startsWith('.')) {
    return 'text-gray-500'
  }
  
  switch (extension) {
    // Documents
    case 'pdf':
      return 'text-red-600'
    case 'doc':
    case 'docx':
    case 'odt':
      return 'text-blue-600'
    case 'rtf':
      return 'text-blue-500'
    case 'txt':
      return 'text-gray-600'
    case 'md':
      return 'text-gray-700'
    case 'tex':
    case 'bib':
      return 'text-purple-600'
      
    // Spreadsheets
    case 'xls':
    case 'xlsx':
      return 'text-green-600'
    case 'csv':
      return 'text-green-500'
      
    // Books
    case 'epub':
      return 'text-indigo-600'
      
    // Data files
    case 'json':
      return 'text-yellow-600'
    case 'xml':
      return 'text-orange-600'
    case 'yaml':
    case 'yml':
      return 'text-pink-600'
      
    // Database
    case 'sql':
    case 'db':
    case 'sqlite':
      return 'text-purple-700'
      
    // Code files by language
    case 'js':
    case 'jsx':
      return 'text-yellow-500'
    case 'ts':
    case 'tsx':
      return 'text-blue-700'
    case 'vue':
      return 'text-emerald-600'
    case 'py':
      return 'text-blue-500'
    case 'java':
      return 'text-red-700'
    case 'cpp':
    case 'c':
    case 'h':
    case 'hpp':
      return 'text-blue-800'
    case 'html':
      return 'text-orange-500'
    case 'css':
    case 'scss':
    case 'sass':
    case 'less':
      return 'text-pink-500'
    case 'php':
      return 'text-purple-500'
    case 'rb':
      return 'text-red-500'
    case 'go':
      return 'text-cyan-600'
    case 'rs':
      return 'text-orange-700'
    case 'sh':
    case 'bash':
      return 'text-gray-700'
      
    // Archives
    case 'zip':
    case 'rar':
    case 'tar':
    case 'gz':
    case '7z':
      return 'text-amber-600'
    case 'deb':
    case 'rpm':
      return 'text-red-800'
      
    // Binary/Data files
    case 'iso':
    case 'img':
      return 'text-gray-800'
    case 'h5':
    case 'hdf5':
      return 'text-indigo-700'
      
    // Images
    case 'jpg':
    case 'jpeg':
    case 'png':
    case 'gif':
    case 'svg':
    case 'webp':
      return 'text-teal-600'
      
    // Videos
    case 'mp4':
    case 'avi':
    case 'mov':
    case 'webm':
    case 'mkv':
      return 'text-purple-600'
      
    // Presentations
    case 'ppt':
    case 'pptx':
      return 'text-orange-600'
      
    default:
      return 'text-gray-600'
  }
}

const formatFileSize = (bytes: number) => {
  if (bytes < 1024) return bytes + ' B'
  else if (bytes < 1048576) return Math.round(bytes / 1024) + ' KB'
  else if (bytes < 1073741824) return Math.round(bytes / 1048576) + ' MB'
  else return Math.round(bytes / 1073741824) + ' GB'
}

const toggleDir = () => {
  emit('toggle-dir', props.node.path)
}

const handleClick = (event: MouseEvent) => {
  // Don't do anything if clicking on the checkbox or chevron button
  if ((event.target as HTMLElement).matches('input[type="checkbox"]') || 
      (event.target as HTMLElement).closest('button')) {
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