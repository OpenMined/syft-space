<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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
const callbackToken = ref('')
const currency = ref('PHP')
const saving = ref(false)

/** Xendit's supported currencies (each locked to its home country). USD arrives with Stripe. */
const CURRENCIES = ['IDR', 'PHP', 'SGD', 'MYR', 'VND', 'THB']

/** Where Xendit must deliver payment events — paste into the Xendit dashboard. */
const webhookUrl = computed(() => `${window.location.origin}/api/v1/credits/webhooks/xendit`)

// Prefill from the existing wallet when replacing. The currency is fixed
// after creation — user balances are denominated in it.
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      provider.value = station.wallet?.provider ?? 'xendit'
      currency.value = station.wallet?.currency ?? 'PHP'
      apiKey.value = ''
      callbackToken.value = ''
    }
  },
)

async function save() {
  if (apiKey.value.trim().length < 8) {
    toast.error('A valid secret API key is required')
    return
  }
  if (!callbackToken.value.trim()) {
    toast.error('The webhook callback token is required')
    return
  }
  saving.value = true
  try {
    const result = await station.setupWallet({
      provider: provider.value,
      currency: currency.value,
      credentials: {
        api_key: apiKey.value.trim(),
        callback_token: callbackToken.value.trim(),
      },
    })
    toast.success('Shared wallet saved', {
      description:
        result.spacesAttached > 0
          ? `${result.spacesAttached} existing space(s) attached — they pick it up on restart.`
          : 'New spaces get the shared wallet automatically.',
    })
    emit('update:open', false)
  } catch (error) {
    toast.error(error instanceof ApiError ? error.message : 'Could not save the wallet')
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
                <SelectItem value="stripe" disabled>Stripe — coming soon</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="space-y-1.5">
            <Label>Currency</Label>
            <Select v-model="currency" :disabled="station.wallet !== null">
              <SelectTrigger class="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="c in CURRENCIES" :key="c" :value="c">{{ c }}</SelectItem>
              </SelectContent>
            </Select>
            <p v-if="station.wallet" class="text-xs text-muted-foreground">
              Fixed — user balances are held in this currency.
            </p>
          </div>
        </div>

        <div class="space-y-1.5">
          <Label for="wallet-key">Secret API key</Label>
          <Input id="wallet-key" v-model="apiKey" type="password" placeholder="xnd_…" />
          <p class="text-xs text-muted-foreground">
            Stays at the station — spaces never see it; they only check credits with the station
            before serving a paid query.
          </p>
        </div>

        <div class="space-y-1.5">
          <Label for="wallet-callback">Webhook callback token</Label>
          <Input
            id="wallet-callback"
            v-model="callbackToken"
            type="password"
            placeholder="From the Xendit dashboard → Webhooks"
          />
          <p class="text-xs text-muted-foreground">
            Set the webhook URL in your Xendit dashboard to
            <code class="rounded bg-muted px-1 font-mono text-[11px]">{{ webhookUrl }}</code>
            — the token verifies its deliveries.
          </p>
        </div>
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
