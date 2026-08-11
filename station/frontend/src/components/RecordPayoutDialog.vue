<script setup lang="ts">
import { ref, watch } from 'vue'
import { Banknote } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatMoney } from '@/lib/types'
import { useStationStore } from '@/stores/station'

const props = defineProps<{
  open: boolean
  target: {
    spaceId: string
    slug: string
    spaceName: string
    ownerEmail: string
    payable: number
  } | null
  currency: string
}>()

const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const station = useStationStore()

const amount = ref('')
const note = ref('')

// Prefill with the full payable amount — the common case
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen && props.target) {
      amount.value = String(props.target.payable)
      note.value = ''
    }
  },
)

const recording = ref(false)

async function record() {
  if (!props.target) return
  const value = Number(amount.value)
  if (!Number.isFinite(value) || value <= 0) {
    toast.error('Enter a payout amount greater than zero')
    return
  }
  if (value > props.target.payable) {
    toast.error(
      `Amount exceeds what is payable (${formatMoney(props.target.payable, props.currency)})`,
    )
    return
  }
  recording.value = true
  try {
    await station.recordPayout({
      spaceId: props.target.spaceId,
      amount: value,
      note: note.value,
    })
    toast.success('Payout recorded', {
      description: `${formatMoney(value, props.currency)} → ${props.target.ownerEmail}`,
    })
    emit('update:open', false)
  } catch (error) {
    toast.error(error instanceof ApiError ? error.message : 'Could not record the payout')
  } finally {
    recording.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="(v: boolean) => emit('update:open', v)">
    <DialogContent v-if="target">
      <DialogHeader>
        <DialogTitle>Record payout — {{ target.spaceName }}</DialogTitle>
        <DialogDescription>
          You pay {{ target.ownerEmail }} outside the platform (bank transfer, etc.) and record it
          here. Payable: {{ formatMoney(target.payable, currency) }}.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <div class="space-y-1.5">
          <Label for="payout-amount">Amount ({{ currency }})</Label>
          <Input id="payout-amount" v-model="amount" type="number" min="0" step="0.01" />
        </div>
        <div class="space-y-1.5">
          <Label for="payout-note">Note (optional)</Label>
          <Input id="payout-note" v-model="note" placeholder="e.g. July payout — bank transfer" />
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">Cancel</Button>
        <Button :disabled="recording" @click="record">
          <Banknote class="mr-1.5 h-4 w-4" />
          Record payout
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
