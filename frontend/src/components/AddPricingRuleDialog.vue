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
                  <SelectItem v-for="r in XENDIT_REGIONS" :key="r.currency" :value="r.currency">
                    {{ r.currency }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="space-y-2">
              <Label>Country</Label>
              <Select :model-value="xenditCountry" disabled>
                <SelectTrigger class="h-10">
                  <SelectValue :placeholder="xenditCountry" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem :value="xenditCountry">{{ xenditCountryLabel }}</SelectItem>
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
          <Button @click="view = 'pricing-form'">
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
            {{ isEditing ? 'Edit Pricing Rule' : 'Add Pricing Rule' }}
          </DialogTitle>
          <DialogDescription> Charge users per request through a configured wallet. </DialogDescription>
        </DialogHeader>

        <div class="space-y-4 py-2">
          <!-- Wallet picker -->
          <div class="space-y-2">
            <Label class="text-sm font-medium">
              Wallet
              <span v-if="isCollectiveMember" class="text-xs text-muted-foreground font-normal ml-1">
                (collective wallet — required for members)
              </span>
            </Label>
            <Select v-model="selectedWalletId" :disabled="isCollectiveMember">
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
              v-if="!isCollectiveMember"
              class="text-xs text-primary hover:text-primary/80 underline-offset-2 hover:underline"
              @click="view = 'pick-provider'"
            >
              + Set up another wallet
            </button>
            <p
              v-if="selectedWallet?.id === 'collective'"
              class="text-xs text-muted-foreground font-mono break-all"
            >
              {{ collectiveWalletAddress }}
            </p>
          </div>

          <!-- Form (visible once wallet picked) -->
          <template v-if="selectedWallet">
            <div class="space-y-2">
              <Label for="price-per-request" class="text-sm font-medium">Price per request</Label>
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
            <Button variant="outline" :disabled="isSubmitting" @click="$emit('update:open', false)">
              Cancel
            </Button>
            <Button :disabled="!canSubmit || isSubmitting" @click="submit">
              <Loader2 v-if="isSubmitting" class="h-4 w-4 mr-2 animate-spin" />
              <Check v-else class="h-4 w-4 mr-2" />
              {{ isEditing ? 'Update Rule' : 'Add Pricing Rule' }}
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
import { toast } from 'vue-sonner'
import { useCollectiveMode } from '@/composables/useCollectiveMode'
import { collectiveStatsSummary, collectiveWalletAddress } from '@/stores/mockCollective'

// Frontend-only wallet model (no backend) — enough to drive the modal.
interface MockWallet {
  id: string
  name: string
  wallet_type: 'mpp' | 'xendit'
  currency: string
}

const XENDIT_REGIONS = [
  { currency: 'IDR', country: 'ID', label: 'Indonesia' },
  { currency: 'PHP', country: 'PH', label: 'Philippines' },
  { currency: 'VND', country: 'VN', label: 'Vietnam' },
  { currency: 'THB', country: 'TH', label: 'Thailand' },
  { currency: 'MYR', country: 'MY', label: 'Malaysia' },
  { currency: 'SGD', country: 'SG', label: 'Singapore' },
]

type View = 'pricing-form' | 'pick-provider' | 'setup-form' | 'wallet-success'

const props = defineProps<{
  open: boolean
  initialData?: Record<string, unknown> | null
  isSubmitting?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  save: [payload: { policyType: 'pricing'; formData: Record<string, unknown> }]
}>()

const { isCollectiveMember } = useCollectiveMode()
const collectiveName = collectiveStatsSummary.name

const isEditing = computed(() => !!props.initialData)

const view = ref<View>('pricing-form')
const wallets = ref<MockWallet[]>([])
const selectedWalletId = ref<string | null>(null)

// ── Inline wallet setup state ──
const selectedProviderType = ref<'mpp' | 'xendit' | null>(null)
const creatingWallet = ref(false)
const newWalletWebhookUrl = ref<string | null>(null)
const xenditForm = ref({ apiKey: '', callbackToken: '', currency: 'IDR' })

const xenditCountry = computed(
  () => XENDIT_REGIONS.find((r) => r.currency === xenditForm.value.currency)?.country ?? 'ID',
)
const xenditCountryLabel = computed(
  () => XENDIT_REGIONS.find((r) => r.currency === xenditForm.value.currency)?.label ?? 'Indonesia',
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
  if (isNaN(price) || price < 0) return false
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

// Wallet creation is frontend-only — appends a mock wallet, no backend call.
const createMppWallet = () => {
  creatingWallet.value = true
  const wallet: MockWallet = {
    id: `mpp-${Date.now()}`,
    name: 'MPP Wallet',
    wallet_type: 'mpp',
    currency: 'USD',
  }
  wallets.value.push(wallet)
  selectedWalletId.value = wallet.id
  creatingWallet.value = false
  toast.success('MPP wallet created')
  view.value = 'pricing-form'
}

const createXenditWallet = () => {
  creatingWallet.value = true
  const wallet: MockWallet = {
    id: `xendit-${Date.now()}`,
    name: `Xendit ${xenditForm.value.currency}`,
    wallet_type: 'xendit',
    currency: xenditForm.value.currency,
  }
  wallets.value.push(wallet)
  selectedWalletId.value = wallet.id
  newWalletWebhookUrl.value = `${window.location.origin}/api/v1/wallets/xendit/webhook`
  creatingWallet.value = false
  toast.success('Xendit wallet connected')
  view.value = 'wallet-success'
}

const submit = () => {
  if (!selectedWallet.value) return
  const users =
    form.value.userType === 'specific'
      ? form.value.users
          .split('\n')
          .map((u) => u.trim())
          .filter(Boolean)
          .join(',')
      : ''
  emit('save', {
    policyType: 'pricing',
    formData: {
      price: form.value.price,
      userType: form.value.userType,
      users,
      note: form.value.name.trim(),
    },
  })
}

const seedWallets = (): MockWallet[] =>
  isCollectiveMember.value
    ? [{ id: 'collective', name: `${collectiveName} (collective)`, wallet_type: 'mpp', currency: 'USD' }]
    : []

const resetState = () => {
  wallets.value = seedWallets()
  selectedWalletId.value = wallets.value[0]?.id ?? null
  selectedProviderType.value = null
  newWalletWebhookUrl.value = null
  creatingWallet.value = false
  xenditForm.value = { apiKey: '', callbackToken: '', currency: 'IDR' }
  form.value = { price: '', name: '', userType: 'all', users: '' }
}

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) {
      resetState()
      return
    }

    resetState()

    if (props.initialData) {
      const data = props.initialData
      // Editing an existing rule — ensure a wallet is present to attach to.
      if (wallets.value.length === 0) {
        wallets.value = [{ id: 'mpp-existing', name: 'MPP Wallet', wallet_type: 'mpp', currency: 'USD' }]
      }
      selectedWalletId.value = wallets.value[0]?.id ?? null
      form.value = {
        price: data.price !== undefined ? String(data.price) : '',
        name: (data.note as string) || '',
        userType: (data.userType as 'all' | 'specific') || 'all',
        users: ((data.users as string) || '')
          .split(',')
          .map((u) => u.trim())
          .filter(Boolean)
          .join('\n'),
      }
      view.value = 'pricing-form'
      return
    }

    // New rule: jump to wallet setup if none configured.
    view.value = wallets.value.length === 0 ? 'pick-provider' : 'pricing-form'
  },
  { immediate: true },
)
</script>
