<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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

// Same generic reject endpoint, two framings: declining a create request, or
// declining a deletion request (which leaves the space running).
const isDeletion = computed(() => props.request?.type === 'delete_space')

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) reason.value = ''
  },
)

async function reject() {
  if (!props.request) return
  try {
    await station.rejectRequest(props.request.id, reason.value.trim() || 'No reason given.')
    toast(isDeletion.value ? 'Deletion declined — space kept' : 'Request rejected', {
      description: props.request.spaceName,
    })
    emit('update:open', false)
  } catch {
    toast.error('Could not complete the action')
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="(v: boolean) => emit('update:open', v)">
    <DialogContent v-if="request">
      <DialogHeader>
        <DialogTitle>{{ isDeletion ? 'Decline deletion request' : 'Reject request' }}</DialogTitle>
        <DialogDescription>
          <template v-if="isDeletion">
            “{{ request.spaceName }}” stays running. Let {{ request.requesterEmail }} know why.
          </template>
          <template v-else>“{{ request.spaceName }}” from {{ request.requesterEmail }}</template>
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-1.5">
        <Label for="reject-reason">Reason (shown to the requester)</Label>
        <Textarea
          id="reject-reason"
          v-model="reason"
          :placeholder="
            isDeletion
              ? 'e.g. please export your datasets first'
              : 'e.g. Please use a descriptive space name tied to a project'
          "
          rows="3"
        />
      </div>

      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">Cancel</Button>
        <Button variant="destructive" @click="reject">
          {{ isDeletion ? 'Decline' : 'Reject' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
