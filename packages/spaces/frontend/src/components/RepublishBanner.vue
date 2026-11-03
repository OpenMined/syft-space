<template>
  <!-- A changed configuration is not re-sent to the Hub on its own; the
       owner republishes when ready. -->
  <Alert v-if="endpoints.length > 0">
    <RefreshCw class="h-4 w-4" />
    <AlertTitle>Configuration changed</AlertTitle>
    <AlertDescription class="flex flex-wrap items-center justify-between gap-3">
      <span>{{ message }} Republish so SyftHub shows the new details.</span>
      <div class="flex items-center gap-2">
        <Button variant="ghost" size="sm" :disabled="isRepublishing" @click="emit('dismiss')">
          Later
        </Button>
        <Button size="sm" :disabled="isRepublishing" @click="handleRepublish">
          <Loader2 v-if="isRepublishing" class="h-3.5 w-3.5 mr-2 animate-spin" />
          {{ isRepublishing ? 'Republishing...' : 'Republish' }}
        </Button>
      </div>
    </AlertDescription>
  </Alert>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Loader2, RefreshCw } from 'lucide-vue-next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { useRepublish, type RepublishTarget } from '@/composables/useRepublish'

const props = defineProps<{
  /** Published endpoints still waiting to be republished. */
  endpoints: RepublishTarget[]
  /** Names of the data sources whose configuration changed. */
  datasetNames: string[]
}>()

const emit = defineEmits<{
  /** The endpoints still pending after a republish: empty on full success. */
  'update:endpoints': [endpoints: RepublishTarget[]]
  dismiss: []
}>()

const { isRepublishing, republish } = useRepublish()

const message = computed(() => {
  const apis =
    props.endpoints.length === 1
      ? 'One published API uses'
      : `${props.endpoints.length} published APIs use`
  const sources =
    props.datasetNames.length === 1
      ? `"${props.datasetNames[0]}".`
      : `${props.datasetNames.length} changed data sources.`
  return `${apis} ${sources}`
})

const handleRepublish = async () => {
  emit('update:endpoints', await republish(props.endpoints))
}
</script>
