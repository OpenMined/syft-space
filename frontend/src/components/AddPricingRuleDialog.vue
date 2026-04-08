<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-[680px]">
      <!-- ═══ SCREEN 1: Payment type selection ═══ -->
      <template v-if="!selectedType">
        <DialogHeader>
          <DialogTitle>Add Pricing Rule</DialogTitle>
          <DialogDescription>
            Choose how users pay to access your endpoint.
          </DialogDescription>
        </DialogHeader>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 py-2">
          <!-- Bundle Payments card -->
          <button
            class="group text-left p-5 rounded-xl border border-border bg-card hover:border-primary/40 hover:shadow-md transition-all cursor-pointer flex flex-col"
            @click="selectType('bundle')"
          >
            <div class="flex items-center gap-3 mb-3">
              <div
                class="h-10 w-10 rounded-lg bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center"
              >
                <Package class="h-5 w-5 text-violet-600 dark:text-violet-400" />
              </div>
              <h3 class="font-semibold text-foreground">Bundle Payments</h3>
            </div>
            <p class="text-sm text-muted-foreground mb-4 flex-1">
              Users buy a prepaid package of requests (e.g. 1,000 queries for $10), then use them
              over time.
            </p>
            <div class="mb-4">
              <p class="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                Steps
              </p>
              <ol class="text-sm text-foreground space-y-0.5 list-decimal list-inside">
                <li>Connect Xendit</li>
                <li>Create bundles</li>
                <li>Choose who pays</li>
              </ol>
            </div>
            <div class="flex items-center justify-between">
              <Badge
                variant="outline"
                class="text-xs text-orange-600 border-orange-300 bg-orange-50 dark:bg-orange-900/20 dark:text-orange-400 dark:border-orange-700"
              >
                Popular in SE Asia
              </Badge>
              <ChevronRight
                class="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors"
              />
            </div>
          </button>

          <!-- Micro-payments card -->
          <button
            class="group text-left p-5 rounded-xl border border-border bg-card hover:border-primary/40 hover:shadow-md transition-all cursor-pointer flex flex-col"
            @click="selectType('micro')"
          >
            <div class="flex items-center gap-3 mb-3">
              <div
                class="h-10 w-10 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center"
              >
                <Zap class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <h3 class="font-semibold text-foreground">Micro-payments</h3>
            </div>
            <p class="text-sm text-muted-foreground mb-4 flex-1">
              Users pay a small amount per request automatically. No bundles — they only pay for
              what they use.
            </p>
            <div class="mb-4">
              <p class="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                Steps
              </p>
              <ol class="text-sm text-foreground space-y-0.5 list-decimal list-inside">
                <li>Set up wallet</li>
                <li>Set price per request</li>
                <li>Choose who pays</li>
              </ol>
            </div>
            <div class="flex items-center justify-end">
              <ChevronRight
                class="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors"
              />
            </div>
          </button>
        </div>

        <div class="flex items-center justify-center gap-6 pt-2 text-xs text-muted-foreground">
          <div class="flex items-center gap-1.5">
            <Globe class="h-3.5 w-3.5" />
            Powered by Xendit
          </div>
          <div class="flex items-center gap-1.5">
            <Globe class="h-3.5 w-3.5" />
            Powered by MPP (Tempo)
          </div>
        </div>
      </template>

      <!-- ═══ SCREEN 2: Micro-payments wizard ═══ -->
      <template v-if="selectedType === 'micro'">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <button
              class="p-1 -ml-1 rounded hover:bg-muted transition-colors"
              @click="goBackToSelection"
            >
              <ArrowLeft class="h-4 w-4" />
            </button>
            <Zap class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
            Micro-payments
          </DialogTitle>
        </DialogHeader>

        <!-- Stepper -->
        <div class="flex items-center gap-2 border-b pb-4">
          <button
            v-for="(label, idx) in microStepLabels"
            :key="idx"
            class="flex items-center gap-2 px-4 py-2 rounded-full text-sm transition-colors"
            :class="
              microStep === idx
                ? 'bg-muted font-medium text-foreground'
                : microStep > idx
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : 'text-muted-foreground'
            "
            :disabled="idx > microStep"
            @click="idx < microStep && (microStep = idx)"
          >
            <span
              v-if="microStep > idx"
              class="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/30"
            >
              <Check class="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
            </span>
            <span
              v-else
              class="flex h-5 w-5 items-center justify-center rounded-full text-xs font-medium"
              :class="
                microStep === idx
                  ? 'bg-emerald-600 text-white'
                  : 'bg-muted text-muted-foreground'
              "
            >
              {{ idx + 1 }}
            </span>
            {{ label }}
          </button>
        </div>

        <!-- Micro Step 1: Wallet -->
        <div v-if="microStep === 0" class="py-4">
          <div v-if="microWalletAddress" class="space-y-3">
            <div
              class="flex items-center gap-2 p-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800/50 rounded-lg"
            >
              <Check class="h-4 w-4 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
              <span class="text-sm text-emerald-700 dark:text-emerald-300">
                Wallet: {{ truncateAddress(microWalletAddress) }}
              </span>
            </div>
          </div>
          <div v-else class="py-8">
            <div
              class="border-2 border-dashed border-border rounded-xl p-8 flex flex-col items-center gap-4"
            >
              <div
                class="h-12 w-12 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center"
              >
                <WalletIcon class="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div class="text-center">
                <h4 class="font-medium text-foreground mb-1">Set up your wallet</h4>
                <p class="text-sm text-muted-foreground max-w-sm">
                  Micro-payments go directly to your wallet. Create one in seconds or connect an
                  existing one.
                </p>
              </div>
              <Button
                class="bg-emerald-600 hover:bg-emerald-700 text-white"
                @click="showMicroWalletSetup = true"
              >
                <WalletIcon class="h-4 w-4 mr-2" />
                Set Up Wallet
              </Button>
            </div>
          </div>
        </div>

        <!-- Micro Step 2: Set Price -->
        <div v-if="microStep === 1" class="py-4 space-y-4">
          <div
            v-if="microWalletAddress"
            class="flex items-center justify-between p-3 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800/50 rounded-lg"
          >
            <div class="flex items-center gap-2">
              <Check class="h-4 w-4 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
              <span class="text-sm text-emerald-700 dark:text-emerald-300">
                Wallet: {{ truncateAddress(microWalletAddress) }}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              class="h-7 w-7 p-0"
              @click="copyToClipboard(microWalletAddress!)"
            >
              <Copy class="h-3.5 w-3.5" />
            </Button>
          </div>

          <div
            class="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800/50 rounded-lg"
          >
            <p class="text-sm text-blue-700 dark:text-blue-300">
              Each API call costs a fixed amount (typical range: $0.001 - $1.00), charged
              automatically regardless of how many results are returned.
            </p>
          </div>

          <div class="space-y-2">
            <Label class="text-sm font-medium">Unit type</Label>
            <Select v-model="microForm.unitType">
              <SelectTrigger class="h-10">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="ut in unitTypeOptions" :key="ut" :value="ut">
                  {{ ut }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div class="space-y-2">
            <Label for="micro-price" class="text-sm font-medium">
              Price per {{ microForm.unitType === 'requests' ? 'request' : microForm.unitType }} ($)
            </Label>
            <Input
              id="micro-price"
              v-model="microForm.price"
              type="number"
              step="any"
              min="0"
              placeholder="0.10"
              class="h-10"
            />
            <p v-if="microPriceHint" class="text-sm text-muted-foreground">
              {{ microPriceHint }}
            </p>
          </div>

          <div class="space-y-2">
            <Label for="micro-name" class="text-sm font-medium">Name (optional)</Label>
            <Input
              id="micro-name"
              v-model="microForm.name"
              placeholder="e.g. Standard rate for weather data"
              class="h-10"
            />
          </div>
        </div>

        <!-- Micro Step 3: Apply -->
        <div v-if="microStep === 2" class="py-4 space-y-4">
          <div class="space-y-2">
            <Label class="text-sm font-medium">Apply pricing to</Label>
            <Select v-model="microForm.userType">
              <SelectTrigger class="h-10">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All users</SelectItem>
                <SelectItem value="specific">Specific users only</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div v-if="microForm.userType === 'specific'" class="space-y-2">
            <Label class="text-sm font-medium">User emails</Label>
            <Textarea
              v-model="microForm.users"
              placeholder="alice@example.com&#10;bob@example.com"
              class="min-h-[100px]"
            />
            <p class="text-xs text-muted-foreground">
              One email per line. Only these users will be required to pay.
            </p>
          </div>

          <!-- Summary -->
          <div class="p-4 bg-muted/50 border border-border rounded-lg space-y-2">
            <p class="text-xs font-medium text-muted-foreground uppercase tracking-wide">Summary</p>
            <div class="grid grid-cols-2 gap-y-1 text-sm">
              <span class="text-muted-foreground">Type</span>
              <span class="text-right font-medium">Micro-payment (per {{ microForm.unitType === 'requests' ? 'request' : microForm.unitType }})</span>
              <span class="text-muted-foreground">Provider</span>
              <span class="text-right font-medium">MPP (Tempo)</span>
              <span class="text-muted-foreground">Price</span>
              <span class="text-right font-medium">${{ microForm.price || '0' }} / {{ microForm.unitType === 'requests' ? 'request' : microForm.unitType }}</span>
              <span class="text-muted-foreground">Applies to</span>
              <span class="text-right font-medium">{{
                microForm.userType === 'all' ? 'All users' : 'Specific users'
              }}</span>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <DialogFooter class="flex items-center justify-between sm:justify-between">
          <Button
            variant="outline"
            @click="microStep === 0 ? goBackToSelection() : microStep--"
          >
            <ArrowLeft class="h-4 w-4 mr-2" />
            Back
          </Button>
          <Button
            v-if="microStep < 2"
            :disabled="!canAdvanceMicro"
            @click="microStep++"
            class="bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            {{ microStep === 0 ? 'Next' : 'Choose Who Pays' }}
            <ChevronRight class="h-4 w-4 ml-2" />
          </Button>
          <Button
            v-else
            :disabled="!canSubmitMicro"
            @click="submitMicro"
            class="bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            <Check class="h-4 w-4 mr-2" />
            Add Pricing Rule
          </Button>
        </DialogFooter>
      </template>

      <!-- ═══ SCREEN 3: Bundle Payments wizard ═══ -->
      <template v-if="selectedType === 'bundle'">
        <DialogHeader>
          <DialogTitle class="flex items-center gap-2">
            <button
              class="p-1 -ml-1 rounded hover:bg-muted transition-colors"
              @click="goBackToSelection"
            >
              <ArrowLeft class="h-4 w-4" />
            </button>
            <Package class="h-5 w-5 text-violet-600 dark:text-violet-400" />
            Bundle Payments
          </DialogTitle>
        </DialogHeader>

        <!-- Stepper -->
        <div class="flex items-center gap-2 border-b pb-4">
          <button
            v-for="(label, idx) in bundleStepLabels"
            :key="idx"
            class="flex items-center gap-2 px-4 py-2 rounded-full text-sm transition-colors"
            :class="
              bundleStep === idx
                ? 'bg-muted font-medium text-foreground'
                : bundleStep > idx
                  ? 'text-violet-600 dark:text-violet-400'
                  : 'text-muted-foreground'
            "
            :disabled="idx > bundleStep"
            @click="idx < bundleStep && (bundleStep = idx)"
          >
            <span
              v-if="bundleStep > idx"
              class="flex h-5 w-5 items-center justify-center rounded-full bg-violet-100 dark:bg-violet-900/30"
            >
              <Check class="h-3 w-3 text-violet-600 dark:text-violet-400" />
            </span>
            <span
              v-else
              class="flex h-5 w-5 items-center justify-center rounded-full text-xs font-medium"
              :class="
                bundleStep === idx
                  ? 'bg-violet-600 text-white'
                  : 'bg-muted text-muted-foreground'
              "
            >
              {{ idx + 1 }}
            </span>
            {{ label }}
          </button>
        </div>

        <!-- Bundle Step 1: Connect Provider -->
        <div v-if="bundleStep === 0" class="py-4 space-y-4">
          <div v-if="bundleWalletConnected" class="space-y-3">
            <div
              class="flex items-center gap-2 p-3 bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800/50 rounded-lg"
            >
              <Check class="h-4 w-4 text-violet-600 dark:text-violet-400 flex-shrink-0" />
              <span class="text-sm text-violet-700 dark:text-violet-300">
                Xendit connected
              </span>
            </div>
            <div v-if="bundleWebhookUrl" class="space-y-1">
              <Label class="text-sm font-medium">Webhook URL</Label>
              <p class="text-xs text-muted-foreground">
                Paste this URL into your Xendit dashboard under Webhook settings.
              </p>
              <div class="flex gap-2">
                <Input
                  :model-value="bundleWebhookUrl"
                  readonly
                  class="h-9 font-mono text-xs flex-1"
                />
                <Button
                  variant="outline"
                  size="sm"
                  class="h-9 px-3"
                  @click="copyToClipboard(bundleWebhookUrl!)"
                >
                  <Copy class="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          </div>
          <template v-else>
            <div class="space-y-2">
              <Label class="text-sm font-medium">Gateway</Label>
              <Select v-model="bundleForm.gateway" disabled>
                <SelectTrigger class="h-10">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="xendit">Xendit</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div class="space-y-2">
              <Label for="bundle-api-key" class="text-sm font-medium">Xendit API Key</Label>
              <Input
                id="bundle-api-key"
                v-model="bundleForm.apiKey"
                type="password"
                autocomplete="off"
                placeholder="xnd_production_..."
                class="h-10 font-mono"
              />
            </div>

            <div class="space-y-2">
              <Label for="bundle-callback-token" class="text-sm font-medium"
                >Callback Verification Token</Label
              >
              <Input
                id="bundle-callback-token"
                v-model="bundleForm.callbackToken"
                type="password"
                autocomplete="off"
                placeholder="Enter your Xendit callback token"
                class="h-10 font-mono"
              />
            </div>
          </template>
        </div>

        <!-- Bundle Step 2: Define Bundles -->
        <div v-if="bundleStep === 1" class="py-4 space-y-4">
          <p class="text-sm text-muted-foreground">
            Create a bundle that users can purchase. You can add more bundles later.
          </p>

          <div
            v-for="(tier, tierIdx) in bundleForm.tiers"
            :key="tierIdx"
            class="p-4 border border-border rounded-xl space-y-4"
          >
            <!-- Sell X units for Y currency -->
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-sm font-medium">Sell</span>
              <Input
                v-model="tier.units"
                type="number"
                min="1"
                placeholder="100"
                class="h-9 w-20"
              />
              <Select v-model="tier.unitType">
                <SelectTrigger class="h-9 w-28">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="ut in unitTypeOptions" :key="ut" :value="ut">
                    {{ ut }}
                  </SelectItem>
                </SelectContent>
              </Select>
              <span class="text-sm font-medium">for</span>
              <Input
                v-model="tier.price"
                type="number"
                min="0"
                step="any"
                placeholder="10.00"
                class="h-9 w-24"
              />
              <Select v-model="tier.currency">
                <SelectTrigger class="h-9 w-20">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="IDR">IDR</SelectItem>
                  <SelectItem value="USD">USD</SelectItem>
                  <SelectItem value="PHP">PHP</SelectItem>
                  <SelectItem value="THB">THB</SelectItem>
                  <SelectItem value="MYR">MYR</SelectItem>
                  <SelectItem value="VND">VND</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div class="space-y-2">
                <Label class="text-sm font-medium">Bundle name</Label>
                <Input v-model="tier.name" placeholder="Starter" class="h-9" />
              </div>
              <div class="space-y-2">
                <Label class="text-sm font-medium">Country</Label>
                <Select v-model="tier.country">
                  <SelectTrigger class="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ID">Indonesia</SelectItem>
                    <SelectItem value="PH">Philippines</SelectItem>
                    <SelectItem value="TH">Thailand</SelectItem>
                    <SelectItem value="MY">Malaysia</SelectItem>
                    <SelectItem value="VN">Vietnam</SelectItem>
                    <SelectItem value="US">United States</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <Button
              v-if="bundleForm.tiers.length > 1"
              variant="ghost"
              size="sm"
              class="text-destructive hover:text-destructive"
              @click="bundleForm.tiers.splice(tierIdx, 1)"
            >
              <Trash2 class="h-4 w-4 mr-1" />
              Remove
            </Button>
          </div>

          <button
            class="text-sm text-primary hover:text-primary/80 font-medium"
            @click="addBundleTier"
          >
            + Add another bundle
          </button>
        </div>

        <!-- Bundle Step 3: Apply -->
        <div v-if="bundleStep === 2" class="py-4 space-y-4">
          <div class="space-y-2">
            <Label class="text-sm font-medium">Apply pricing to</Label>
            <Select v-model="bundleForm.userType">
              <SelectTrigger class="h-10">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All users</SelectItem>
                <SelectItem value="specific">Specific users only</SelectItem>
              </SelectContent>
            </Select>
            <p class="text-xs text-muted-foreground">
              "All users" means everyone must purchase a bundle to access your endpoint.
            </p>
          </div>

          <div v-if="bundleForm.userType === 'specific'" class="space-y-2">
            <Label class="text-sm font-medium">User emails</Label>
            <Textarea
              v-model="bundleForm.users"
              placeholder="alice@example.com&#10;bob@example.com"
              class="min-h-[100px]"
            />
            <p class="text-xs text-muted-foreground">
              One email per line. Only these users will be required to pay.
            </p>
          </div>

          <!-- Summary -->
          <div class="p-4 bg-muted/50 border border-border rounded-lg space-y-2">
            <p class="text-xs font-medium text-muted-foreground uppercase tracking-wide">Summary</p>
            <div class="grid grid-cols-2 gap-y-1 text-sm">
              <span class="text-muted-foreground">Type</span>
              <span class="text-right font-medium">Bundle (prepaid)</span>
              <span class="text-muted-foreground">Provider</span>
              <span class="text-right font-medium">Xendit</span>
              <span class="text-muted-foreground">Bundle</span>
              <span class="text-right font-medium">
                {{ bundleForm.tiers[0]?.name || 'Unnamed' }} &mdash;
                {{ bundleForm.tiers[0]?.units || 0 }} reqs for
                {{ bundleForm.tiers[0]?.currency }} {{ bundleForm.tiers[0]?.price || '0' }}
              </span>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <DialogFooter class="flex items-center justify-between sm:justify-between">
          <Button
            variant="outline"
            @click="bundleStep === 0 ? goBackToSelection() : bundleStep--"
          >
            <ArrowLeft class="h-4 w-4 mr-2" />
            Back
          </Button>
          <Button
            v-if="bundleStep < 2"
            :disabled="!canAdvanceBundle || bundleCreating"
            @click="advanceBundle"
            class="bg-violet-600 hover:bg-violet-700 text-white"
          >
            <Loader2 v-if="bundleCreating" class="h-4 w-4 mr-2 animate-spin" />
            {{ bundleStep === 0 ? (bundleWalletConnected ? 'Next' : 'Connect') : 'Choose Who Pays' }}
            <ChevronRight v-if="!bundleCreating" class="h-4 w-4 ml-2" />
          </Button>
          <Button
            v-else
            :disabled="!canSubmitBundle"
            @click="submitBundle"
            class="bg-violet-600 hover:bg-violet-700 text-white"
          >
            <Check class="h-4 w-4 mr-2" />
            Add Pricing Rule
          </Button>
        </DialogFooter>
      </template>
    </DialogContent>
  </Dialog>

  <!-- Wallet setup dialog (reused for micro-payments) -->
  <WalletSetupDialog
    v-model:open="showMicroWalletSetup"
    @wallet-updated="handleMicroWalletUpdated"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  Package,
  Zap,
  ChevronRight,
  Globe,
  ArrowLeft,
  Check,
  Wallet as WalletIcon,
  Trash2,
  Loader2,
  Copy,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
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
import WalletSetupDialog from '@/components/WalletSetupDialog.vue'
import { walletsApi } from '@/api/endpoints/wallets'
import { policyTypesApi } from '@/api/policies/policies'
import { toast } from 'vue-sonner'

export type PricingType = 'bundle' | 'micro'

interface BundleTier {
  name: string
  units: string
  unitType: string
  price: string
  currency: string
  country: string
}

const props = defineProps<{
  open: boolean
  lockedType?: PricingType | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'pricing-created': [
    payload: {
      type: PricingType
      config: Record<string, unknown>
    },
  ]
}>()

// ── Shared state ──
const selectedType = ref<PricingType | null>(null)
const unitTypeOptions = ref<string[]>(['requests'])

const selectType = (type: PricingType) => {
  selectedType.value = type
  if (type === 'micro') {
    fetchMicroWallet()
    fetchPolicyTypeSchema('mpp_accounting')
  } else {
    fetchBundleWallet()
    fetchPolicyTypeSchema('xendit')
  }
}

const extractEnumFromSchema = (schema: Record<string, unknown>): string[] | null => {
  const defs = schema?.['$defs'] as Record<string, Record<string, unknown>> | undefined
  if (!defs) return null

  // Case 1 (xendit): $defs.BundleTier.properties.unit_type.enum
  const bundleTier = defs['BundleTier'] as Record<string, unknown> | undefined
  const tierProps = bundleTier?.['properties'] as Record<string, Record<string, unknown>> | undefined
  const tierUnitType = tierProps?.['unit_type']
  if (tierUnitType?.['enum'] && Array.isArray(tierUnitType['enum'])) {
    return tierUnitType['enum'] as string[]
  }

  // Case 2 (mpp): properties.unit_type.$ref → $defs.UnitType.enum
  const topProps = schema['properties'] as Record<string, Record<string, unknown>> | undefined
  const topUnitType = topProps?.['unit_type']
  if (topUnitType?.['$ref']) {
    const refName = (topUnitType['$ref'] as string).replace('#/$defs/', '')
    const refDef = defs[refName]
    if (refDef?.['enum'] && Array.isArray(refDef['enum'])) {
      return refDef['enum'] as string[]
    }
  }
  // Case 3: inline enum on top-level property
  if (topUnitType?.['enum'] && Array.isArray(topUnitType['enum'])) {
    return topUnitType['enum'] as string[]
  }

  return null
}

const fetchPolicyTypeSchema = async (policyName: string) => {
  try {
    const info = await policyTypesApi.get(policyName)
    const schema = info.config_schema as Record<string, unknown>
    const extracted = extractEnumFromSchema(schema)
    if (extracted && extracted.length > 0) {
      unitTypeOptions.value = extracted
    }
  } catch {
    unitTypeOptions.value = ['requests']
  }
}

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  } catch {
    toast.error('Failed to copy')
  }
}

const goBackToSelection = () => {
  if (props.lockedType) {
    emit('update:open', false)
  } else {
    selectedType.value = null
  }
}

// ── Micro-payments state ──
const microStepLabels = ['Wallet', 'Set price', 'Apply']
const microStep = ref(0)
const microWalletAddress = ref<string | null>(null)
const showMicroWalletSetup = ref(false)

const microForm = ref({
  price: '',
  name: '',
  unitType: 'requests',
  userType: 'all' as 'all' | 'specific',
  users: '',
})

const truncateAddress = (addr: string) => {
  if (addr.length <= 12) return addr
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`
}

const microPriceHint = computed(() => {
  const price = parseFloat(microForm.value.price)
  if (isNaN(price) || price <= 0) return ''
  const cost1k = (price * 1000).toFixed(2)
  return `1,000 ${microForm.value.unitType} = $${cost1k}`
})

const canAdvanceMicro = computed(() => {
  if (microStep.value === 0) return !!microWalletAddress.value
  if (microStep.value === 1) {
    const price = parseFloat(microForm.value.price)
    return !isNaN(price) && price >= 0
  }
  return true
})

const canSubmitMicro = computed(() => {
  if (microForm.value.userType === 'specific') {
    return microForm.value.users.trim().length > 0
  }
  return true
})

const fetchMicroWallet = async () => {
  try {
    const wallets = await walletsApi.list()
    const mppWallet = wallets.find((w) => w.wallet_type === 'mpp' && w.is_active)
    if (mppWallet) {
      microWalletAddress.value = mppWallet.display.wallet_address ?? null
      microStep.value = 1
    }
  } catch {
    microWalletAddress.value = null
  }
}

const handleMicroWalletUpdated = (address: string) => {
  microWalletAddress.value = address
}

const submitMicro = () => {
  const appliedTo =
    microForm.value.userType === 'all'
      ? ['*']
      : microForm.value.users
          .split('\n')
          .map((e) => e.trim())
          .filter((e) => e)

  emit('pricing-created', {
    type: 'micro',
    config: {
      price: parseFloat(microForm.value.price) || 0,
      unit_type: microForm.value.unitType,
      applied_to: appliedTo,
      name: microForm.value.name,
    },
  })
  emit('update:open', false)
}

// ── Bundle payments state ──
const bundleStepLabels = ['Connect provider', 'Define bundles', 'Apply']
const bundleStep = ref(0)
const bundleWalletConnected = ref(false)
const bundleWebhookUrl = ref<string | null>(null)

const fetchBundleWallet = async () => {
  try {
    const wallets = await walletsApi.list()
    const xenditWallet = wallets.find((w) => w.wallet_type === 'xendit' && w.is_active)
    if (xenditWallet) {
      bundleWalletConnected.value = true
      bundleWebhookUrl.value = xenditWallet.display.webhook_url ?? null
      bundleStep.value = 1
    }
  } catch {
    bundleWalletConnected.value = false
  }
}

const createEmptyTier = (): BundleTier => ({
  name: 'Starter',
  units: '100',
  unitType: 'requests',
  price: '10.00',
  currency: 'IDR',
  country: 'ID',
})

const bundleForm = ref({
  gateway: 'xendit',
  apiKey: '',
  callbackToken: '',
  tiers: [createEmptyTier()],
  userType: 'all' as 'all' | 'specific',
  users: '',
})

const addBundleTier = () => {
  bundleForm.value.tiers.push({
    ...createEmptyTier(),
    name: `Tier ${bundleForm.value.tiers.length + 1}`,
  })
}

const bundleCreating = ref(false)

const canAdvanceBundle = computed(() => {
  if (bundleStep.value === 0) {
    if (bundleWalletConnected.value) return true
    return (
      bundleForm.value.apiKey.trim().length > 0 &&
      bundleForm.value.callbackToken.trim().length > 0
    )
  }
  if (bundleStep.value === 1) {
    return bundleForm.value.tiers.every(
      (t) =>
        t.name.trim() &&
        parseInt(t.units) > 0 &&
        parseFloat(t.price) > 0 &&
        t.currency &&
        t.country,
    )
  }
  return true
})

const canSubmitBundle = computed(() => {
  if (bundleForm.value.userType === 'specific') {
    return bundleForm.value.users.trim().length > 0
  }
  return true
})

const advanceBundle = async () => {
  if (bundleStep.value === 0 && !bundleWalletConnected.value) {
    // Create the Xendit wallet via API
    bundleCreating.value = true
    try {
      const wallet = await walletsApi.createXendit(
        bundleForm.value.apiKey,
        bundleForm.value.callbackToken,
      )
      bundleWalletConnected.value = true
      bundleWebhookUrl.value = wallet.display.webhook_url ?? null
      toast.success('Xendit wallet connected')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to connect Xendit')
    } finally {
      bundleCreating.value = false
    }
    return
  }
  bundleStep.value++
}

const submitBundle = () => {
  const appliedTo =
    bundleForm.value.userType === 'all'
      ? ['*']
      : bundleForm.value.users
          .split('\n')
          .map((e) => e.trim())
          .filter((e) => e)

  emit('pricing-created', {
    type: 'bundle',
    config: {
      bundle_tiers: bundleForm.value.tiers.map((t) => ({
        name: t.name,
        units: parseInt(t.units),
        unit_type: t.unitType,
        price: parseFloat(t.price),
      })),
      currency: bundleForm.value.tiers[0]?.currency || 'USD',
      country: bundleForm.value.tiers[0]?.country || 'ID',
      applied_to: appliedTo,
    },
  })
  emit('update:open', false)
}

// ── Reset on close, auto-select on open ──
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen && props.lockedType) {
      selectType(props.lockedType)
    } else if (!isOpen) {
      selectedType.value = null
      unitTypeOptions.value = ['requests']
      microStep.value = 0
      microWalletAddress.value = null
      microForm.value = { price: '', name: '', unitType: 'requests', userType: 'all', users: '' }
      bundleStep.value = 0
      bundleWalletConnected.value = false
      bundleWebhookUrl.value = null
      bundleCreating.value = false
      bundleForm.value = {
        gateway: 'xendit',
        apiKey: '',
        callbackToken: '',
        tiers: [createEmptyTier()],
        userType: 'all',
        users: '',
      }
    }
  },
)
</script>
