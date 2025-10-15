<template>
  <CreateResourceDialog
    :open="open"
    :resource="dataset"
    :resource-config="datasetConfig"
    @update:open="$emit('update:open', $event)"
    @resource-created="$emit('dataset-created')"
    @resource-updated="$emit('dataset-updated')"
  />
</template>

<script setup lang="ts">
import CreateResourceDialog from '@/components/CreateResourceDialog.vue'

interface DataSource {
  id: string
  name: string
  type: string
  description: string
  tags: string[]
  status: 'running' | 'stopped'
}

defineProps<{
  open: boolean
  dataset?: DataSource | null
}>()

defineEmits<{
  'update:open': [value: boolean]
  'dataset-created': []
  'dataset-updated': []
}>()

const datasetConfig = {
  singularName: 'dataset',
  pluralName: 'datasets',
  displayName: 'Dataset',
  configurationSuffix: 'settings',
  customDocsUrl: 'https://docs.openmined.org/custom-data-sources',
  options: [
    { id: 'filesystem', name: 'File System', type: 'Data' },
    { id: 'weaviate', name: 'Weaviate', type: 'Data' },
    { id: 'qdrant', name: 'Qdrant', type: 'Data' },
    { id: 'chroma', name: 'Chroma', type: 'Data' },
    { id: 'custom', name: 'Custom', type: 'Data', isCustom: true },
  ],
}
</script>
