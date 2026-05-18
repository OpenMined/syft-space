<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-[600px]">
      <!-- ═══ View: Pick a wallet provider ═══ -->
      <template v-if="view === 'pick-provider'">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <WalletIcon class="h-5 w-5 text-primary" />
            Set up a wallet
          </DialogTitle>
          <DialogDescription>
            A pricing rule needs a wallet to receive payments. Pick a provider.
          </DialogDescription>
        </DialogHeader>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 py-2">
          <button
            class="text-left p-4 rounded-xl border border-border hover:border-primary/40 hover:shadow-md transition-all flex flex-col gap-2"
            @click="pickProvider('mpp')"
          >
            <div
              class="h-9 w-9 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center"
            >
              <Zap class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <h3 class="font-semibold text-foreground">MPP (Tempo)</h3>
            <p class="text-sm text-muted-foreground">
              Per-request micro-payments via the Machine Payments Protocol.
            </p>
          </button>
          <button
            class="text-left p-4 rounded-xl border border-border hover:border-primary/40 hover:shadow-md transition-all flex flex-col gap-2"
            @click="pickProvider('xendit')"
          >
            <div
              class="h-9 w-9 rounded-lg bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center"
            >
              <Package class="h-5 w-5 text-violet-600 dark:text-violet-400" />
            </div>
            <h3 class="font-semibold text-foreground">Xendit</h3>
            <p class="text-sm text-muted-foreground">
              Prepaid bundles paid via Xendit checkout (SE Asia currencies).
            </p>
          </button>
        </div>

        <DialogFooter v-if="wallets.length > 0">
          <Button variant="outline" @click="view = 'pricing-form'">
            <ArrowLeft class="h-4 w-4 mr-2" />
            Back
          </Button>
        </DialogFooter>
      </template>

      <!-- ═══ View: Provider setup form ═══ -->
      <template v-else-if="view === 'setup-form'">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <button
              class="p-1 -ml-1 rounded hover:bg-muted transition-colors"
              @click="view = 'pick-provider'"
            >
              <ArrowLeft class="h-4 w-4" />
            </button>
            <component
              :is="selectedProviderType === 'mpp' ? Zap : Package"
              class="h-5 w-5"
              :class="
                selectedProviderType === 'mpp'
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : 'text-violet-600 dark:text-violet-400'
              "
            />
            {{ selectedProviderType === 'mpp' ? 'MPP Wallet' : 'Xendit Wallet' }}
          </DialogTitle>
          <DialogDescription v-if="selectedProviderType === 'mpp'">
            Create a fresh MPP wallet for this server.
          </DialogDescription>
          <DialogDescription v-else>
            Enter your Xendit credentials and pick the wallet currency.
          </DialogDescription>
        </DialogHeader>

        <!-- MPP setup -->
        <div v-if="selectedProviderType === 'mpp'" class="space-y-3 py-2">
          <Button class="w-full" :disabled="creatingWallet" @click="createMppWallet">
            <Loader2 v-if="creatingWallet" class="h-4 w-4 mr-2 animate-spin" />
            Create MPP Wallet
          </Button>
          <p class="text-xs text-muted-foreground text-center">
            To import an existing wallet via private key, use Settings → Add Wallet.
          </p>
        </div>

        <!-- Xendit setup -->
        <div v-else class="space-y-3 py-2">
          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-2">
              <Label>Currency</Label>
              <Select v-model="xenditForm.currency">
                <SelectTrigger class="h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="r in XENDIT_REGIONS"
                    :key="r.currency"
                    :value="r.currency"
                  >
                    {{ r.currency }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="space-y-2">
              <Label>Country</Label>
              <Select v-model="xenditForm.country" disabled>
                <SelectTrigger class="h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="r in XENDIT_REGIONS"
                    :key="r.country"
                    :value="r.country"
                  >
                    {{ r.countryLabel }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div class="space-y-2">
            <Label for="xendit-api-key">API Key</Label>
            <Input
              id="xendit-api-key"
              v-model="xenditForm.apiKey"
              type="password"
              autocomplete="off"
              placeholder="xnd_production_..."
              class="font-mono placeholder:text-muted-foreground/50"
            />
          </div>
          <div class="space-y-2">
            <Label for="xendit-callback">Callback Verification Token</Label>
            <Input
              id="xendit-callback"
              v-model="xenditForm.callbackToken"
              type="password"
              autocomplete="off"
              placeholder="Enter your Xendit callback token"
              class="font-mono placeholder:text-muted-foreground/50"
            />
          </div>
          <Button
            class="w-full"
            :disabled="!canCreateXendit || creatingWallet"
            @click="createXenditWallet"
          >
            <Loader2 v-if="creatingWallet" class="h-4 w-4 mr-2 animate-spin" />
            Connect Xendit
          </Button>
        </div>
      </template>

      <!-- ═══ View: Xendit wallet success — show webhook URL ═══ -->
      <template v-else-if="view === 'wallet-success'">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <Check class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
            Wallet connected
          </DialogTitle>
          <DialogDescription>
            Paste this webhook URL into your Xendit dashboard so payment events reach this server.
          </DialogDescription>
        </DialogHeader>

        <div class="space-y-2 py-2">
          <Label>Webhook URL</Label>
          <div class="flex gap-2">
            <Input
              :model-value="newWalletWebhookUrl ?? ''"
              readonly
              class="h-9 font-mono text-xs flex-1"
            />
            <Button
              variant="outline"
              size="sm"
              class="h-9 px-3"
              @click="copyToClipboard(newWalletWebhookUrl ?? '')"
            >
              <Copy class="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        <DialogFooter>
          <Button @click="continueToPricingForm">
            Continue
            <ChevronRight class="h-4 w-4 ml-2" />
          </Button>
        </DialogFooter>
      </template>

      <!-- ═══ View: Pricing form (wallet picker + price + applied_to) ═══ -->
      <template v-else>
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <DollarSign class="h-5 w-5 text-primary" />
            Add Pricing Rule
          </DialogTitle>
          <DialogDescription>
            Charge users per request through a configured wallet.
          </DialogDescription>
        </DialogHeader>

        <div class="space-y-4 py-2">
          <!-- Wallet picker -->
          <div class="space-y-2">
            <Label class="text-sm font-medium">
              Wallet
              <span v-if="lockedWalletId" class="text-xs text-muted-foreground font-normal ml-1">
                (locked — endpoint already uses this wallet)
              </span>
            </Label>
            <Select v-model="selectedWalletId" :disabled="!!lockedWalletId || loadingWallets">
              <SelectTrigger class="h-10">
                <SelectValue placeholder="Select a wallet" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="w in wallets" :key="w.id" :value="w.id">
                  {{ w.name }} · {{ providerLabel(w.wallet_type) }} · {{ w.currency }}
                </SelectItem>
              </SelectContent>
            </Select>
            <button
              v-if="!lockedWalletId"
              class="text-xs text-primary hover:text-primary/80 underline-offset-2 hover:underline"
              @click="view = 'pick-provider'"
            >
              + Set up another wallet
            </button>
            <p v-if="lockedWalletId" class="text-xs text-muted-foreground">
              All payment policies on an endpoint must share the same wallet.
            </p>
          </div>

          <!-- Form (visible once wallet picked) -->
          <template v-if="selectedWallet">
            <div class="space-y-2">
              <Label for="price-per-request" class="text-sm font-medium"> Price per request </Label>
              <div class="flex gap-2 items-stretch">
                <Input
                  id="price-per-request"
                  v-model="form.price"
                  type="number"
                  step="any"
                  min="0"
                  placeholder="0.10"
                  class="h-10 flex-1 placeholder:text-muted-foreground/50"
                />
                <div
                  class="px-3 inline-flex items-center rounded-md border border-input bg-muted text-sm font-medium"
                >
                  {{ selectedWallet.currency }}
                </div>
              </div>
              <p v-if="priceHint" class="text-xs text-muted-foreground">
                {{ priceHint }}
              </p>
            </div>

            <div class="space-y-2">
              <Label for="policy-name" class="text-sm font-medium">
                Policy name <span class="text-muted-foreground font-normal">(optional)</span>
              </Label>
              <Input
                id="policy-name"
                v-model="form.name"
                placeholder="e.g. Standard rate"
                class="h-10 placeholder:text-muted-foreground/50"
              />
            </div>

            <div class="space-y-2">
              <Label class="text-sm font-medium">Apply to</Label>
              <Select v-model="form.userType">
                <SelectTrigger class="h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All users</SelectItem>
                  <SelectItem value="specific">Specific users only</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div v-if="form.userType === 'specific'" class="space-y-2">
              <Label class="text-sm font-medium">User emails</Label>
              <Textarea
                v-model="form.users"
                placeholder="alice@example.com&#10;bob@example.com"
                class="min-h-[100px] placeholder:text-muted-foreground/50"
              />
              <p class="text-xs text-muted-foreground">
                One email per line. Only these users will be charged.
              </p>
            </div>

            <!-- Summary -->
            <div class="p-4 bg-muted/50 border border-border rounded-lg space-y-2">
              <p class="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Summary
              </p>
              <div class="grid grid-cols-2 gap-y-1 text-sm">
                <span class="text-muted-foreground">Wallet</span>
                <span class="text-right font-medium">{{ selectedWallet.name }}</span>
                <span class="text-muted-foreground">Provider</span>
                <span class="text-right font-medium">
                  {{ providerLabel(selectedWallet.wallet_type) }}
                </span>
                <span class="text-muted-foreground">Price</span>
                <span class="text-right font-medium">
                  {{ form.price || '0' }} {{ selectedWallet.currency }} / request
                </span>
                <span class="text-muted-foreground">Applies to</span>
                <span class="text-right font-medium">
                  {{ form.userType === 'all' ? 'All users' : 'Specific users' }}
                </span>
              </div>
            </div>
          </template>

          <DialogFooter>
            <Button variant="outline" @click="$emit('update:open', false)">Cancel</Button>
            <Button :disabled="!canSubmit" @click="submit">
              <Check class="h-4 w-4 mr-2" />
              Add Pricing Rule
            </Button>
          </DialogFooter>
        </div>
      </template>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  DollarSign,
  Wallet as WalletIcon,
  Check,
  ArrowLeft,
  ChevronRight,
  Copy,
  Loader2,
  Zap,
  Package,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { walletsApi } from '@/api/endpoints/wallets'
import { toast } from 'vue-sonner'
import type { WalletListItem } from '@/api/types'
import { XENDIT_REGIONS, countryForCurrency } from '@/lib/xenditRegions'

type View = 'pricing-form' | 'pick-provider' | 'setup-form' | 'wallet-success'

const props = defineProps<{
  open: boolean
  /**
   * Pre-select and lock the wallet picker. Used when an endpoint already
   * has a payment policy — all payment policies on the same endpoint must
   * share one wallet.
   */
  lockedWalletId?: string | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'pricing-created': [
    payload: {
      walletId: string
      walletType: string
      walletCurrency: string
      policyType: 'mpp_per_request' | 'xendit_per_request'
      name: string
      config: Record<string, unknown>
    },
  ]
}>()

const view = ref<View>('pricing-form')

const wallets = ref<WalletListItem[]>([])
const loadingWallets = ref(false)
const selectedWalletId = ref<string | null>(null)

// ── Inline wallet setup state ──
const selectedProviderType = ref<'mpp' | 'xendit' | null>(null)
const creatingWallet = ref(false)
const newWalletWebhookUrl = ref<string | null>(null)
const newWalletId = ref<string | null>(null)
const xenditForm = ref({
  apiKey: '',
  callbackToken: '',
  currency: 'IDR',
  country: 'ID',
})

// Currency drives country (1:1 within Xendit's per-country channel
// catalogs). Cross-border combinations are blocked at the backend, so we
// avoid them here too.
watch(
  () => xenditForm.value.currency,
  (currency) => {
    xenditForm.value.country = countryForCurrency(currency)
  },
)

// ── Pricing form state ──
const form = ref({
  price: '',
  name: '',
  userType: 'all' as 'all' | 'specific',
  users: '',
})

const selectedWallet = computed(
  () => wallets.value.find((w) => w.id === selectedWalletId.value) ?? null,
)

const priceHint = computed(() => {
  const price = parseFloat(form.value.price)
  if (isNaN(price) || price <= 0 || !selectedWallet.value) return ''
  const cost1k = (price * 1000).toLocaleString()
  return `1,000 requests = ${cost1k} ${selectedWallet.value.currency}`
})

const canSubmit = computed(() => {
  if (!selectedWallet.value) return false
  const price = parseFloat(form.value.price)
  if (isNaN(price) || price <= 0) return false
  if (form.value.userType === 'specific') {
    return form.value.users.trim().length > 0
  }
  return true
})

const canCreateXendit = computed(
  () =>
    xenditForm.value.apiKey.trim().length > 0 && xenditForm.value.callbackToken.trim().length > 0,
)

const providerLabel = (walletType: string): string => {
  switch (walletType) {
    case 'mpp':
      return 'MPP (Tempo)'
    case 'xendit':
      return 'Xendit'
    default:
      return walletType
  }
}

const policyTypeForWallet = (walletType: string): 'mpp_per_request' | 'xendit_per_request' => {
  if (walletType === 'mpp') return 'mpp_per_request'
  return 'xendit_per_request'
}

const buildConfig = (walletType: string): Record<string, unknown> => {
  const price = parseFloat(form.value.price) || 0
  const appliedTo =
    form.value.userType === 'all'
      ? ['*']
      : form.value.users
          .split('\n')
          .map((e) => e.trim())
          .filter((e) => e)

  // MPP and Xendit use different price field names.
  if (walletType === 'mpp') {
    return { price, unit_type: 'requests', applied_to: appliedTo }
  }
  return { price_per_request: price, applied_to: appliedTo }
}

const fetchWallets = async () => {
  loadingWallets.value = true
  try {
    const all = await walletsApi.list()
    wallets.value = all.filter((w) => w.is_active)
  } catch {
    wallets.value = []
  } finally {
    loadingWallets.value = false
  }
}

const copyToClipboard = async (text: string) => {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  } catch {
    toast.error('Failed to copy')
  }
}

const pickProvider = (providerType: 'mpp' | 'xendit') => {
  selectedProviderType.value = providerType
  view.value = 'setup-form'
}

const createMppWallet = async () => {
  creatingWallet.value = true
  try {
    const wallet = await walletsApi.createMpp()
    newWalletId.value = wallet.id
    await fetchWallets()
    toast.success('MPP wallet created')
    selectedWalletId.value = wallet.id
    view.value = 'pricing-form'
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to create wallet')
  } finally {
    creatingWallet.value = false
  }
}

const createXenditWallet = async () => {
  // Frontend guard: backend enforces UNIQUE(tenant, type, currency) too.
  if (
    wallets.value.some(
      (w) => w.wallet_type === 'xendit' && w.currency === xenditForm.value.currency,
    )
  ) {
    toast.error(`A Xendit wallet for ${xenditForm.value.currency} already exists.`)
    return
  }

  creatingWallet.value = true
  try {
    const wallet = await walletsApi.createXendit({
      apiKey: xenditForm.value.apiKey,
      callbackToken: xenditForm.value.callbackToken,
      currency: xenditForm.value.currency,
      country: xenditForm.value.country,
    })
    newWalletId.value = wallet.id
    newWalletWebhookUrl.value = wallet.display.webhook_url ?? null
    await fetchWallets()
    toast.success('Xendit wallet connected')
    selectedWalletId.value = wallet.id
    view.value = 'wallet-success'
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to connect Xendit')
  } finally {
    creatingWallet.value = false
  }
}

const continueToPricingForm = () => {
  view.value = 'pricing-form'
}

const submit = () => {
  if (!selectedWallet.value) return
  const w = selectedWallet.value
  emit('pricing-created', {
    walletId: w.id,
    walletType: w.wallet_type,
    walletCurrency: w.currency,
    policyType: policyTypeForWallet(w.wallet_type),
    name: form.value.name.trim(),
    config: buildConfig(w.wallet_type),
  })
  emit('update:open', false)
}

const resetState = () => {
  view.value = 'pricing-form'
  selectedWalletId.value = null
  selectedProviderType.value = null
  newWalletId.value = null
  newWalletWebhookUrl.value = null
  creatingWallet.value = false
  xenditForm.value = {
    apiKey: '',
    callbackToken: '',
    currency: 'IDR',
    country: 'ID',
  }
  form.value = { price: '', name: '', userType: 'all', users: '' }
}

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      await fetchWallets()
      if (props.lockedWalletId) {
        selectedWalletId.value = props.lockedWalletId
        view.value = 'pricing-form'
        const found = wallets.value.find((w) => w.id === props.lockedWalletId)
        if (!found) {
          toast.error('Locked wallet not found among active wallets')
        }
        return
      }
      // Empty state: jump straight to wallet setup.
      view.value = wallets.value.length === 0 ? 'pick-provider' : 'pricing-form'
    } else {
      resetState()
    }
  },
)
</script>
