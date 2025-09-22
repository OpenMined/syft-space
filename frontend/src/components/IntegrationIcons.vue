<template>
  <img 
    :src="iconSrc" 
    :alt="`${name} icon`"
    v-bind="$attrs"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

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

const iconSrc = computed(() => {
  return iconMap[props.name] || ''
})
</script>

<style scoped>
img {
  object-fit: contain;
}
</style>