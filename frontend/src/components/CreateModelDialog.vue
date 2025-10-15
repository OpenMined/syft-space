<template>
  <CreateResourceDialog 
    :open="open"
    :resource="model"
    :resource-config="modelConfig"
    @update:open="$emit('update:open', $event)"
    @resource-created="$emit('model-created')"
    @resource-updated="$emit('model-updated')"
  />
</template>

<script setup lang="ts">
import CreateResourceDialog from '@/components/CreateResourceDialog.vue'

interface Model {
  id: string
  name: string
  type: string
  description: string
  tags: string[]
  status: 'running' | 'stopped'
}

defineProps<{
  open: boolean
  model?: Model | null
}>()

defineEmits<{
  'update:open': [value: boolean]
  'model-created': []
  'model-updated': []
}>()

const modelConfig = {
  singularName: 'model',
  pluralName: 'models',
  displayName: 'AI Model',
  configurationSuffix: 'integration settings',
  customDocsUrl: 'https://docs.openmined.org/custom-models',
  options: [
    { id: 'vllm', name: 'vLLM', type: 'Model' },
    { id: 'ollama', name: 'Ollama', type: 'Model' },
    { id: 'huggingface', name: 'Hugging Face', type: 'Model' },
    { id: 'custom', name: 'Custom', type: 'Model', isCustom: true },
  ]
}
</script>