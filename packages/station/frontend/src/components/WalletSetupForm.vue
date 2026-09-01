<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { toast } from 'vue-sonner'
import { ApiError } from '@/api/client'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import WalletSummaryCard from '@/components/WalletSummaryCard.vue'
import type { WalletProvider } from '@/lib/types'
import { useStationStore } from '@/stores/station'

/**
 * The shared-wallet form: fields, validation, and the save call. Both hosts
 * render it — the onboarding wizard's wallet step and the Earnings
 * add/replace dialog — and own their footer buttons, invoking the exposed
 * save() when theirs is clicked. save() resolves with the rollout counts on
 * success, null on any failure (already toasted here).
 */

const station = useStationStore()

const provider = ref<WalletProvider>('xendit')
const currency = ref('PHP')
const apiKey = ref('')
const webhookSecret = ref('')
const saving = ref(false)

// Replace mode mirrors the SAVED wallet. A watcher (not mount-time init):
// the form can mount before loadWallet resolves — onboarding renders it with
// the dialog — and a snapshot would lock the wrong currency into the save.
watch(
  () => station.wallet,
  (wallet) => {
    if (wallet) {
      provider.value = wallet.provider
      currency.value = wallet.currency
    }
  },
  { immediate: true },
)

/**
 * Per-provider currency menus — mirrors the backend's provider-split bundle
 * catalog (a gateway's supported currencies ARE its catalog keys). Xendit's
 * set is locked to its home countries; Stripe's is the catalog launch set.
 */
const PROVIDER_CURRENCIES: Record<WalletProvider, string[]> = {
  xendit: ['IDR', 'PHP', 'SGD', 'MYR', 'VND', 'THB'],
  stripe: ['USD', 'EUR', 'GBP', 'SGD', 'AUD', 'CAD', 'JPY', 'BRL'],
}
const DEFAULT_CURRENCY: Record<WalletProvider, string> = { xendit: 'PHP', stripe: 'USD' }

const currencies = computed(() => PROVIDER_CURRENCIES[provider.value])

// Replace mode locks the currency (balances are denominated in it), so a
// provider that doesn't support it can't be selected — the save would 422.
const lockedCurrency = computed(() => station.wallet?.currency ?? null)
function providerUnavailable(p: WalletProvider): boolean {
  return lockedCurrency.value !== null && !PROVIDER_CURRENCIES[p].includes(lockedCurrency.value)
}

watch(provider, () => {
  if (!lockedCurrency.value && !currencies.value.includes(currency.value)) {
    currency.value = DEFAULT_CURRENCY[provider.value]
  }
})

/** Where the provider must deliver payment events — paste into its dashboard. */
const webhookUrl = computed(
  () => `${window.location.origin}/api/v1/credits/webhooks/${provider.value}`,
)

async function save(): Promise<{ spacesAttached: number; spacesFailed: number } | null> {
  if (apiKey.value.trim().length < 8) {
    toast.error('A valid secret API key is required')
    return null
  }
  if (!webhookSecret.value.trim()) {
    toast.error(
      provider.value === 'stripe'
        ? 'The webhook signing secret is required'
        : 'The webhook callback token is required',
    )
    return null
  }
  // Credential keys are provider-specific; each gateway validates its own.
  const credentials: Record<string, string> =
    provider.value === 'stripe'
      ? { secret_key: apiKey.value.trim(), webhook_secret: webhookSecret.value.trim() }
      : { api_key: apiKey.value.trim(), callback_token: webhookSecret.value.trim() }
  saving.value = true
  try {
    return await station.setupWallet({
      provider: provider.value,
      currency: currency.value,
      credentials,
    })
  } catch (error) {
    toast.error(error instanceof ApiError ? error.message : 'Could not save the wallet')
    return null
  } finally {
    saving.value = false
  }
}

defineExpose({ save, saving })
</script>

<template>
  <div class="space-y-4">
    <!-- Replace mode: show what's being replaced and what survives it. -->
    <template v-if="station.wallet">
      <WalletSummaryCard />
      <p class="text-xs text-muted-foreground">
        Replacing swaps the provider account behind this wallet — user balances and connected spaces
        stay as they are.
      </p>
    </template>

    <div class="grid gap-4 sm:grid-cols-2">
      <div class="space-y-1.5">
        <Label>Provider</Label>
        <Select v-model="provider">
          <SelectTrigger class="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="xendit" :disabled="providerUnavailable('xendit')">
              Xendit
              <template v-if="providerUnavailable('xendit')">
                — not available in {{ lockedCurrency }}</template
              >
            </SelectItem>
            <SelectItem value="stripe" :disabled="providerUnavailable('stripe')">
              Stripe
              <template v-if="providerUnavailable('stripe')">
                — not available in {{ lockedCurrency }}</template
              >
            </SelectItem>
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
            <SelectItem v-for="c in currencies" :key="c" :value="c">{{ c }}</SelectItem>
          </SelectContent>
        </Select>
        <p v-if="station.wallet" class="text-xs text-muted-foreground">
          Fixed — user balances are held in this currency.
        </p>
      </div>
    </div>

    <div class="space-y-1.5">
      <Label for="wallet-key">Secret API key</Label>
      <Input
        id="wallet-key"
        v-model="apiKey"
        type="password"
        :placeholder="provider === 'stripe' ? 'sk_…' : 'xnd_…'"
      />
      <p class="text-xs text-muted-foreground">
        Stays at the station — spaces never see it; they only check credits with the station before
        serving a paid query.
      </p>
    </div>

    <div class="space-y-1.5">
      <Label for="wallet-webhook-secret">
        {{ provider === 'stripe' ? 'Webhook signing secret' : 'Webhook callback token' }}
      </Label>
      <Input
        id="wallet-webhook-secret"
        v-model="webhookSecret"
        type="password"
        :placeholder="provider === 'stripe' ? 'whsec_…' : 'From the Xendit dashboard → Webhooks'"
      />
      <p v-if="provider === 'stripe'" class="text-xs text-muted-foreground">
        In the Stripe Dashboard (Developers → Webhooks), add an endpoint for
        <code class="rounded bg-muted px-1 font-mono text-[11px]">{{ webhookUrl }}</code>
        listening to the <code class="font-mono text-[11px]">checkout.session.*</code> events, and
        copy its signing secret here.
      </p>
      <p v-else class="text-xs text-muted-foreground">
        In the Xendit dashboard (Settings → Developers → Webhooks), set the webhook URL to
        <code class="rounded bg-muted px-1 font-mono text-[11px]">{{ webhookUrl }}</code>
        and copy its verification token here.
      </p>
    </div>
  </div>
</template>
