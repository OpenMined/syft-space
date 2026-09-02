<script setup lang="ts">
import { ref } from 'vue'
import { toast } from 'vue-sonner'
import SyftHubIdentityCard from '@/components/SyftHubIdentityCard.vue'
import WalletSetupForm from '@/components/WalletSetupForm.vue'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useStationStore } from '@/stores/station'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const station = useStationStore()

// The form remounts on every open (DialogContent unmounts when closed), so
// its state resets without any bookkeeping here.
const form = ref<InstanceType<typeof WalletSetupForm> | null>(null)
const saving = ref(false)

async function save() {
  saving.value = true
  try {
    const result = await form.value?.save()
    if (!result) return // validation/API errors already toasted by the form
    toast.success('Shared wallet saved', {
      description:
        result.spacesAttached > 0
          ? `${result.spacesAttached} existing space(s) attached — they pick it up on restart.`
          : 'New spaces get the shared wallet automatically.',
    })
    emit('update:open', false)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="(v: boolean) => emit('update:open', v)">
    <DialogContent>
      <DialogHeader>
        <DialogTitle>{{
          station.wallet ? 'Replace shared wallet' : 'Add shared wallet'
        }}</DialogTitle>
        <DialogDescription>
          One shared wallet per station, and it's optional. Users buy credits at the station and
          spend them at any space; you pay members from Earnings for what users spend.
        </DialogDescription>
      </DialogHeader>

      <WalletSetupForm ref="form" />

      <div class="border-t pt-4">
        <SyftHubIdentityCard />
      </div>

      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">Cancel</Button>
        <Button :disabled="saving" @click="save">
          {{ station.wallet ? 'Replace wallet' : 'Add shared wallet' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
