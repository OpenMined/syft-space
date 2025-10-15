<template>
  <component v-if="isLucideIcon" :is="lucideIcon" :class="lucideIconClass" v-bind="$attrs" />
  <img v-else :src="iconSrc" :alt="`${name} icon`" v-bind="$attrs" />
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

interface IconConfig {
  type: 'image' | 'lucide'
  src?: string
  component?: typeof FolderOpen
  class?: string
}

const iconConfig: Record<string, IconConfig> = {
  weaviate: { type: 'image', src: weaviateIcon },
  qdrant: { type: 'image', src: qdrantIcon },
  chroma: { type: 'image', src: chromaIcon },
  vllm: { type: 'image', src: vllmIcon },
  ollama: { type: 'image', src: ollamaIcon },
  huggingface: { type: 'image', src: huggingfaceIcon },
  filesystem: { type: 'lucide', component: FolderOpen, class: 'text-purple-600' },
}

const currentIcon = computed(() => iconConfig[props.name])

const isLucideIcon = computed(() => currentIcon.value?.type === 'lucide')

const lucideIcon = computed(() => currentIcon.value?.component)

const lucideIconClass = computed(() => currentIcon.value?.class || '')

const iconSrc = computed(() => currentIcon.value?.src || '')
</script>

<style scoped>
img {
  object-fit: contain;
}
</style>
