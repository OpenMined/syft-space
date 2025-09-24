<template>
  <component 
    v-if="isLucideIcon" 
    :is="lucideIcon" 
    :class="lucideIconClass"
    v-bind="$attrs"
  />
  <img 
    v-else
    :src="iconSrc" 
    :alt="`${name} icon`"
    v-bind="$attrs"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { FolderOpen } from 'lucide-vue-next'

// Import all icon images
import weaviateIcon from '@/assets/icons/weaviate.png'
import qdrantIcon from '@/assets/icons/qdrant.png'
import chromaIcon from '@/assets/icons/chroma.webp'
import vllmIcon from '@/assets/icons/vllm.png'
import ollamaIcon from '@/assets/icons/ollama.png'
import huggingfaceIcon from '@/assets/icons/huggingface.png'

const props = defineProps<{
  name: string
}>()

const iconMap: Record<string, string> = {
  weaviate: weaviateIcon,
  qdrant: qdrantIcon,
  chroma: chromaIcon,
  vllm: vllmIcon,
  ollama: ollamaIcon,
  huggingface: huggingfaceIcon,
}

const lucideIconMap: Record<string, any> = {
  filesystem: FolderOpen,
}

const isLucideIcon = computed(() => {
  return lucideIconMap[props.name] !== undefined
})

const lucideIcon = computed(() => {
  return lucideIconMap[props.name]
})

const lucideIconClass = computed(() => {
  if (props.name === 'filesystem') {
    return 'text-purple-600'
  }
  return ''
})

const iconSrc = computed(() => {
  return iconMap[props.name] || ''
})
</script>

<style scoped>
img {
  object-fit: contain;
}
</style>