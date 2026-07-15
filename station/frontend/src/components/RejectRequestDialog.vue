<script setup lang="ts">
import { ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import type { SpaceRequest } from '@/lib/types'
import { useStationStore } from '@/stores/station'

const props = defineProps<{
  request: SpaceRequest | null
  open: boolean
}>()

const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const station = useStationStore()
const reason = ref('')

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) reason.value = ''
  },
)

function reject() {
  if (!props.request) return
  station.rejectRequest(props.request.id, reason.value.trim() || 'No reason given.')
  toast('Request rejected', { description: props.request.spaceName })
  emit('update:open', false)
}
</script>

<template>
  <Dialog :open="open" @update:open="(v: boolean) => emit('update:open', v)">
    <DialogContent v-if="request">
      <DialogHeader>
        <DialogTitle>Reject request</DialogTitle>
        <DialogDescription>
          “{{ request.spaceName }}” from {{ request.requesterEmail }}
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-1.5">
        <Label for="reject-reason">Reason (shown to the requester)</Label>
        <Textarea
          id="reject-reason"
          v-model="reason"
          placeholder="e.g. Please use a descriptive space name tied to a project"
          rows="3"
        />
      </div>

      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">Cancel</Button>
        <Button variant="destructive" @click="reject">Reject</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
