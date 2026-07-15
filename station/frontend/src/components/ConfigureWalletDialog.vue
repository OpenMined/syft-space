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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { WalletProvider } from '@/lib/types'
import { useStationStore } from '@/stores/station'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const station = useStationStore()

const provider = ref<WalletProvider>('xendit')
const apiKey = ref('')
const currency = ref('USD')

const CURRENCIES = ['USD', 'IDR', 'PHP', 'SGD', 'EUR']

// Prefill from the existing wallet when editing
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      provider.value = station.wallet?.provider ?? 'xendit'
      currency.value = station.wallet?.currency ?? 'USD'
      apiKey.value = ''
    }
  },
)

function save() {
  if (apiKey.value.trim().length < 8) {
    toast.error('A valid secret API key is required')
    return
  }
  station.configureWallet({
    provider: provider.value,
    apiKey: apiKey.value.trim(),
    currency: currency.value,
  })
  toast.success('Shared wallet saved', {
    description: 'New spaces get the shared wallet; running spaces pick it up on restart.',
  })
  emit('update:open', false)
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
          One shared wallet per station, and it's optional. Users buy credits at the station
          and spend them at any space; you pay members from Earnings for what users spend.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <div class="grid gap-4 sm:grid-cols-2">
          <div class="space-y-1.5">
            <Label>Provider</Label>
            <Select v-model="provider">
              <SelectTrigger class="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="xendit">Xendit</SelectItem>
                <SelectItem value="stripe">Stripe</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="space-y-1.5">
            <Label>Currency</Label>
            <Select v-model="currency">
              <SelectTrigger class="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="c in CURRENCIES" :key="c" :value="c">{{ c }}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div class="space-y-1.5">
          <Label for="wallet-key">Secret API key</Label>
          <Input
            id="wallet-key"
            v-model="apiKey"
            type="password"
            :placeholder="provider === 'xendit' ? 'xnd_prod_…' : 'sk_live_…'"
          />
          <p class="text-xs text-muted-foreground">
            Stays at the station — spaces never see it; they only check credits with the
            station before serving a paid query.
          </p>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">Cancel</Button>
        <Button @click="save">
          {{ station.wallet ? 'Replace wallet' : 'Add shared wallet' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
