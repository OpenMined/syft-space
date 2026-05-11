<template>
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-10">
      <div class="flex items-center gap-3 mb-3">
        <Settings class="h-6 w-6 text-primary" />
        <h1 class="heading-3">Settings</h1>
      </div>
      <p class="text-lg text-muted-foreground">Configure your workspace preferences</p>
    </div>

    <!-- Content -->
    <div class="space-y-6">
      <!-- SyftHub Account Section -->
      <div class="bg-card border border-border rounded-xl p-6">
        <div class="flex items-center gap-3 mb-6">
          <div class="p-2 bg-primary/10 rounded-md">
            <User class="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 class="text-lg font-medium text-foreground">Account Details</h3>
            <a
              v-if="userStore.marketplaceUrl"
              :href="`${userStore.marketplaceUrl.replace(/\/$/, '')}/profile`"
              target="_blank"
              class="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
            >
              View on SyftHub
              <ExternalLink class="h-3 w-3" />
            </a>
            <p v-else class="text-sm text-muted-foreground">
              Your connected SyftHub account details
            </p>
          </div>
        </div>

        <!-- Loading skeleton -->
        <div v-if="loadingAccount" class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div v-for="i in 3" :key="i" class="space-y-2">
            <Skeleton class="h-4 w-16" />
            <Skeleton class="h-5 w-32" />
          </div>
        </div>

        <!-- Loaded content -->
        <div v-else class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <!-- Name -->
          <div class="space-y-1">
            <p class="text-sm text-muted-foreground">Name</p>
            <p class="text-sm font-medium text-foreground">
              {{ userStore.name || '--' }}
            </p>
          </div>

          <!-- Username -->
          <div class="space-y-1">
            <p class="text-sm text-muted-foreground">Username</p>
            <p class="text-sm font-medium text-foreground">
              {{ userStore.username || '--' }}
            </p>
          </div>

          <!-- Email -->
          <div class="space-y-1">
            <p class="text-sm text-muted-foreground">Email</p>
            <p class="text-sm font-medium text-foreground">
              {{ userStore.email || '--' }}
            </p>
          </div>
        </div>
      </div>

      <!-- Network Configuration Section -->
      <div class="bg-card border border-border rounded-xl p-6">
        <div class="flex items-center gap-3 mb-6">
          <div class="p-2 bg-primary/10 rounded-md">
            <Globe class="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 class="text-lg font-medium text-foreground">Network Configuration</h3>
            <p class="text-sm text-muted-foreground">Configure how others can access your space</p>
          </div>
        </div>

        <!-- Loading skeleton -->
        <div v-if="loadingNetwork" class="space-y-4">
          <div v-for="i in 2" :key="i" class="flex items-start space-x-3">
            <Skeleton class="h-4 w-4 rounded-full mt-1" />
            <div class="space-y-2 flex-1">
              <Skeleton class="h-5 w-48" />
              <Skeleton class="h-4 w-64" />
            </div>
          </div>
        </div>

        <!-- Radio options -->
        <div v-else class="space-y-4">
          <!-- Subdomain option -->
          <div class="space-y-3">
            <div class="flex items-start space-x-3">
              <input
                type="radio"
                id="subdomain"
                value="subdomain"
                v-model="networkMode"
                class="mt-1 h-4 w-4 text-primary border-gray-300 focus:ring-primary"
              />
              <div class="flex-1">
                <Label for="subdomain" class="font-medium cursor-pointer">
                  Use a URL provided by SyftHub
                  <Badge variant="secondary" class="ml-2">Recommended</Badge>
                </Label>
              </div>
            </div>

            <!-- Subdomain conditional content -->
            <div v-if="networkMode === 'subdomain' && proxyStatus.connected" class="ml-7">
              <div class="p-4 bg-muted/50 rounded-lg border space-y-3">
                <div class="flex items-center gap-2">
                  <div class="h-2 w-2 rounded-full bg-green-500" />
                  <span class="text-sm font-medium">Connected</span>
                </div>

                <div v-if="proxyStatus.publicUrl" class="text-sm">
                  <span class="text-muted-foreground">Public URL:</span>
                  <a
                    :href="proxyStatus.publicUrl"
                    target="_blank"
                    class="ml-2 bg-muted px-2 py-0.5 rounded text-xs font-mono hover:bg-muted/80 inline-flex items-center gap-1"
                  >
                    {{ proxyStatus.publicUrl }}
                    <ExternalLink class="h-3 w-3" />
                  </a>
                </div>
              </div>
            </div>
          </div>

          <!-- Custom domain option -->
          <div class="space-y-3">
            <div class="flex items-start space-x-3">
              <input
                type="radio"
                id="custom"
                value="custom"
                v-model="networkMode"
                class="mt-1 h-4 w-4 text-primary border-gray-300 focus:ring-primary"
              />
              <div class="space-y-1 flex-1">
                <Label for="custom" class="font-medium cursor-pointer">
                  I have my own URL
                  <Badge variant="outline" class="ml-2">Advanced</Badge>
                </Label>
                <p class="text-sm text-muted-foreground">
                  Use this if you've already set up port forwarding or have a public URL
                </p>
              </div>
            </div>

            <!-- Custom domain conditional field -->
            <div v-if="networkMode === 'custom'" class="ml-7 space-y-2">
              <Label for="custom-domain">Your Public URL</Label>
              <Input
                id="custom-domain"
                v-model="customUrl"
                type="url"
                placeholder="https://my-space.example.com"
              />
              <p class="text-sm text-muted-foreground">
                Enter the complete web address where your Syft Space can be reached
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Payments Section -->
      <div class="bg-card border border-border rounded-xl p-6">
        <div class="flex items-center justify-between mb-6">
          <div class="flex items-center gap-3">
            <div class="p-2 bg-primary/10 rounded-md">
              <Wallet class="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 class="text-lg font-medium text-foreground">Payments</h3>
              <p class="text-sm text-muted-foreground">Manage your payment wallets</p>
            </div>
          </div>
          <Button variant="outline" size="sm" @click="addWalletDialogOpen = true">
            <Plus class="h-4 w-4 mr-2" />
            Add Wallet
          </Button>
        </div>

        <!-- Loading skeleton -->
        <div v-if="loadingWallets" class="space-y-3">
          <Skeleton class="h-16 w-full rounded-lg" />
          <Skeleton class="h-16 w-full rounded-lg" />
        </div>

        <!-- No wallets -->
        <div v-else-if="allWallets.length === 0" class="text-center py-6">
          <p class="text-sm text-muted-foreground">
            No wallets configured. Set up a wallet to start receiving payments.
          </p>
        </div>

        <!-- Wallet list -->
        <div v-else class="space-y-3">
          <div
            v-for="wallet in allWallets"
            :key="wallet.id"
            class="flex items-center justify-between p-4 border border-border rounded-lg"
          >
            <div class="flex items-center gap-3 min-w-0">
              <div
                class="h-9 w-9 rounded-lg flex items-center justify-center flex-shrink-0"
                :class="
                  wallet.wallet_type === 'mpp'
                    ? 'bg-emerald-100 dark:bg-emerald-900/30'
                    : 'bg-violet-100 dark:bg-violet-900/30'
                "
              >
                <Zap
                  v-if="wallet.wallet_type === 'mpp'"
                  class="h-4 w-4 text-emerald-600 dark:text-emerald-400"
                />
                <Package v-else class="h-4 w-4 text-violet-600 dark:text-violet-400" />
              </div>
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <p class="text-sm font-medium text-foreground">{{ wallet.name }}</p>
                  <Badge variant="outline" class="text-xs">{{ wallet.currency }}</Badge>
                  <Badge
                    variant="outline"
                    class="text-xs"
                    :class="
                      wallet.is_active
                        ? 'text-emerald-600 border-emerald-300'
                        : 'text-muted-foreground'
                    "
                  >
                    {{ wallet.is_active ? 'Active' : 'Inactive' }}
                  </Badge>
                </div>
                <p class="text-xs text-muted-foreground font-mono truncate">
                  <template v-if="wallet.wallet_type === 'mpp'">
                    {{ wallet.display.wallet_address || 'No address' }}
                  </template>
                  <template v-else-if="wallet.wallet_type === 'xendit'">
                    Webhook: {{ wallet.display.webhook_url || 'N/A' }}
                  </template>
                </p>
              </div>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
              <Button
                v-if="wallet.wallet_type === 'mpp'"
                variant="outline"
                size="sm"
                @click="walletDialogOpen = true"
              >
                Manage
              </Button>
              <Button
                v-else-if="wallet.wallet_type === 'xendit'"
                variant="outline"
                size="sm"
                @click="openXenditManage(wallet)"
              >
                Manage
              </Button>
              <Button
                variant="ghost"
                size="sm"
                class="text-destructive hover:text-destructive"
                @click="handleDeleteWallet(wallet.id, wallet.name)"
              >
                <Trash2 class="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>

      <!-- MPP Wallet Setup Dialog (opened from Manage button) -->
      <WalletSetupDialog v-model:open="walletDialogOpen" @wallet-updated="onWalletUpdated" />

      <!-- Add Wallet Dialog (type selection → config) -->
      <Dialog v-model:open="addWalletDialogOpen">
        <DialogContent class="sm:max-w-md">
          <!-- Step 1: Choose wallet type -->
          <template v-if="!addWalletType">
            <DialogHeader>
              <DialogTitle>Add Wallet</DialogTitle>
              <DialogDescription> Choose a wallet type to set up. </DialogDescription>
            </DialogHeader>
            <div class="grid grid-cols-2 gap-3 py-2">
              <button
                class="group text-left p-4 rounded-xl border border-border bg-card hover:border-primary/40 hover:shadow-md transition-all"
                @click="addWalletType = 'mpp'"
              >
                <div class="flex items-center gap-2 mb-2">
                  <div
                    class="h-8 w-8 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center"
                  >
                    <Zap class="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <h4 class="font-medium text-foreground text-sm">MPP (Tempo)</h4>
                </div>
                <p class="text-xs text-muted-foreground">Blockchain wallet for micro-payments</p>
              </button>
              <button
                class="group text-left p-4 rounded-xl border border-border bg-card hover:border-primary/40 hover:shadow-md transition-all"
                @click="addWalletType = 'xendit'"
              >
                <div class="flex items-center gap-2 mb-2">
                  <div
                    class="h-8 w-8 rounded-lg bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center"
                  >
                    <Package class="h-4 w-4 text-violet-600 dark:text-violet-400" />
                  </div>
                  <h4 class="font-medium text-foreground text-sm">Xendit</h4>
                </div>
                <p class="text-xs text-muted-foreground">Payment gateway for bundle purchases</p>
              </button>
            </div>
          </template>

          <!-- Step 2: MPP setup -->
          <template v-else-if="addWalletType === 'mpp'">
            <DialogHeader>
              <DialogTitle class="flex items-center gap-2">
                <button
                  class="p-1 -ml-1 rounded hover:bg-muted transition-colors"
                  @click="addWalletType = null"
                >
                  <ArrowLeft class="h-4 w-4" />
                </button>
                <Zap class="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                MPP Wallet
              </DialogTitle>
              <DialogDescription>
                Create a new wallet or import an existing one.
              </DialogDescription>
            </DialogHeader>
            <div class="space-y-3 py-2">
              <Button class="w-full" @click="handleCreateMpp" :disabled="addWalletSaving">
                <Loader2 v-if="addWalletSaving" class="h-4 w-4 mr-2 animate-spin" />
                Create New Wallet
              </Button>
              <button
                class="text-sm text-primary hover:text-primary/80 text-left"
                @click="showMppImport = !showMppImport"
              >
                I already have a wallet
              </button>
              <div v-if="showMppImport" class="space-y-3 pt-3 border-t">
                <div class="space-y-2">
                  <Label for="mpp-import-key">Private Key</Label>
                  <Input
                    id="mpp-import-key"
                    v-model="mppImportKey"
                    type="password"
                    autocomplete="off"
                    placeholder="Enter your private key"
                    class="font-mono"
                  />
                </div>
                <Button
                  size="sm"
                  @click="handleImportMpp"
                  :disabled="addWalletSaving || !mppImportKey"
                >
                  <Loader2 v-if="addWalletSaving" class="h-4 w-4 mr-2 animate-spin" />
                  Import Wallet
                </Button>
              </div>
            </div>
          </template>

          <!-- Step 2: Xendit setup -->
          <template v-else-if="addWalletType === 'xendit'">
            <DialogHeader>
              <DialogTitle class="flex items-center gap-2">
                <button
                  class="p-1 -ml-1 rounded hover:bg-muted transition-colors"
                  @click="addWalletType = null"
                >
                  <ArrowLeft class="h-4 w-4" />
                </button>
                <Package class="h-5 w-5 text-violet-600 dark:text-violet-400" />
                Xendit Wallet
              </DialogTitle>
              <DialogDescription> Enter your Xendit API credentials. </DialogDescription>
            </DialogHeader>
            <div class="space-y-4 py-2">
              <!-- Show webhook URL after creation -->
              <div v-if="addWalletWebhookUrl" class="space-y-1">
                <Label class="text-sm font-medium">Webhook URL</Label>
                <p class="text-xs text-muted-foreground">Paste this into your Xendit dashboard.</p>
                <div class="flex gap-2">
                  <Input
                    :model-value="addWalletWebhookUrl"
                    readonly
                    class="h-9 font-mono text-xs flex-1"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    class="h-9 px-3"
                    @click="copyToClipboard(addWalletWebhookUrl!)"
                  >
                    <Copy class="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
              <template v-else>
                <div class="grid grid-cols-2 gap-3">
                  <div class="space-y-2">
                    <Label>Currency</Label>
                    <Select v-model="addXenditForm.currency">
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
                    <Select v-model="addXenditForm.country" disabled>
                      <SelectTrigger class="h-10">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem v-for="r in XENDIT_REGIONS" :key="r.country" :value="r.country">
                          {{ r.countryLabel }}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div class="space-y-2">
                  <Label for="add-xendit-api-key">API Key</Label>
                  <Input
                    id="add-xendit-api-key"
                    v-model="addXenditForm.apiKey"
                    type="password"
                    autocomplete="off"
                    placeholder="xnd_production_..."
                    class="font-mono"
                  />
                </div>
                <div class="space-y-2">
                  <Label for="add-xendit-callback">Callback Verification Token</Label>
                  <Input
                    id="add-xendit-callback"
                    v-model="addXenditForm.callbackToken"
                    type="password"
                    autocomplete="off"
                    placeholder="Enter your callback token"
                    class="font-mono"
                  />
                </div>
                <Button
                  class="w-full"
                  @click="handleCreateXendit"
                  :disabled="
                    addWalletSaving || !addXenditForm.apiKey || !addXenditForm.callbackToken
                  "
                >
                  <Loader2 v-if="addWalletSaving" class="h-4 w-4 mr-2 animate-spin" />
                  Connect Xendit
                </Button>
              </template>
            </div>
          </template>
        </DialogContent>
      </Dialog>

      <!-- Xendit Manage Dialog -->
      <Dialog v-model:open="xenditDialogOpen">
        <DialogContent class="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Manage Xendit Wallet</DialogTitle>
            <DialogDescription>
              Update your Xendit API credentials. Leave a field empty to keep the current value.
            </DialogDescription>
          </DialogHeader>
          <div class="space-y-4">
            <div v-if="xenditWebhookUrl" class="space-y-1">
              <Label class="text-sm font-medium">Webhook URL</Label>
              <div class="flex gap-2">
                <Input
                  :model-value="xenditWebhookUrl"
                  readonly
                  class="h-9 font-mono text-xs flex-1"
                />
                <Button
                  variant="outline"
                  size="sm"
                  class="h-9 px-3"
                  @click="copyToClipboard(xenditWebhookUrl!)"
                >
                  <Copy class="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
            <div class="space-y-2">
              <Label for="xendit-api-key" class="text-sm font-medium">API Key</Label>
              <Input
                id="xendit-api-key"
                v-model="xenditForm.apiKey"
                type="password"
                autocomplete="off"
                placeholder="Leave empty to keep current"
                class="font-mono"
              />
            </div>
            <div class="space-y-2">
              <Label for="xendit-callback-token" class="text-sm font-medium"
                >Callback Verification Token</Label
              >
              <Input
                id="xendit-callback-token"
                v-model="xenditForm.callbackToken"
                type="password"
                autocomplete="off"
                placeholder="Leave empty to keep current"
                class="font-mono"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" @click="xenditDialogOpen = false">Cancel</Button>
            <Button
              @click="handleUpdateXendit"
              :disabled="savingXendit || (!xenditForm.apiKey && !xenditForm.callbackToken)"
            >
              <Loader2 v-if="savingXendit" class="h-4 w-4 mr-2 animate-spin" />
              Update
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <!-- Diagnostics Section -->
      <div class="bg-card border border-border rounded-xl p-6">
        <div class="flex items-start space-x-3">
          <Checkbox id="diagnostics" v-model="diagnosticsEnabled" class="mt-0.5" />
          <Label for="diagnostics" class="text-sm text-foreground cursor-pointer leading-snug">
            Help improve Syft Space by sharing anonymous usage data
          </Label>
        </div>
      </div>

      <!-- Save Button -->
      <div class="mt-8 flex justify-end">
        <Button :disabled="saving" @click="saveChanges">
          <Loader2 v-if="saving" class="h-4 w-4 mr-2 animate-spin" />
          Save Changes
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import {
  Settings,
  Globe,
  User,
  ExternalLink,
  Loader2,
  Wallet,
  Zap,
  Package,
  Trash2,
  Copy,
  Plus,
  ArrowLeft,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useUserStore } from '@/stores/user'
import { settingsApi } from '@/api/endpoints/settings'
import { walletsApi } from '@/api/endpoints/wallets'
import { setDiagnosticsEnabled } from '@/lib/sentry'
import { setPosthogDiagnosticsEnabled } from '@/lib/posthog'
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
import type { WalletListItem } from '@/api/types'
import { XENDIT_REGIONS, countryForCurrency } from '@/lib/xenditRegions'

const userStore = useUserStore()

const loadingAccount = ref(true)
const loadingNetwork = ref(true)
const saving = ref(false)
const networkMode = ref<'subdomain' | 'custom'>('subdomain')
const customUrl = ref(window.location.origin)
const diagnosticsEnabled = ref(false)

// Wallet state
const loadingWallets = ref(true)
const allWallets = ref<WalletListItem[]>([])
const walletDialogOpen = ref(false)

const proxyStatus = reactive({
  connected: false,
  publicUrl: null as string | null,
  hasToken: false,
})

const fetchAccountInfo = async () => {
  loadingAccount.value = true
  try {
    await userStore.fetchMarketplaceInfo()
  } finally {
    loadingAccount.value = false
  }
}

const fetchDiagnostics = async () => {
  try {
    const res = await settingsApi.getDiagnostics()
    diagnosticsEnabled.value = res.enabled
  } catch {
    // Default to false if fetch fails
  }
}

const fetchNetworkConfig = async () => {
  loadingNetwork.value = true
  try {
    const [publicUrlRes, proxyRes] = await Promise.all([
      settingsApi.getPublicUrl(),
      settingsApi.getProxyStatus(),
    ])

    proxyStatus.connected = proxyRes.connected
    proxyStatus.publicUrl = proxyRes.public_url
    proxyStatus.hasToken = proxyRes.has_token

    if (proxyRes.has_token) {
      networkMode.value = 'subdomain'
    } else if (publicUrlRes.public_url) {
      networkMode.value = 'custom'
      customUrl.value = publicUrlRes.public_url
    }
  } catch {
    // If API fails, keep default subdomain mode
  } finally {
    loadingNetwork.value = false
  }
}

// Wallet methods
const fetchWallets = async () => {
  loadingWallets.value = true
  try {
    allWallets.value = await walletsApi.list()
  } catch {
    allWallets.value = []
  } finally {
    loadingWallets.value = false
  }
}

const onWalletUpdated = () => {
  fetchWallets()
}

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  } catch {
    toast.error('Failed to copy')
  }
}

// Xendit manage state
const xenditDialogOpen = ref(false)
const xenditManageId = ref<string | null>(null)
const xenditWebhookUrl = ref<string | null>(null)
const savingXendit = ref(false)
const xenditForm = ref({ apiKey: '', callbackToken: '' })

const openXenditManage = (wallet: { id: string; display: Record<string, string> }) => {
  xenditManageId.value = wallet.id
  xenditWebhookUrl.value = wallet.display.webhook_url ?? null
  xenditForm.value = { apiKey: '', callbackToken: '' }
  xenditDialogOpen.value = true
}

const handleUpdateXendit = async () => {
  if (!xenditManageId.value) return
  savingXendit.value = true
  try {
    const updates: Record<string, string> = {}
    if (xenditForm.value.apiKey) updates.api_key = xenditForm.value.apiKey
    if (xenditForm.value.callbackToken) updates.callback_token = xenditForm.value.callbackToken
    await walletsApi.updateXendit(xenditManageId.value, updates)
    toast.success('Xendit wallet updated')
    xenditDialogOpen.value = false
    await fetchWallets()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to update wallet')
  } finally {
    savingXendit.value = false
  }
}

const handleDeleteWallet = async (walletId: string, walletName: string) => {
  if (!confirm(`Delete wallet "${walletName}"? This cannot be undone.`)) return
  try {
    await walletsApi.delete(walletId)
    allWallets.value = allWallets.value.filter((w) => w.id !== walletId)
    toast.success('Wallet deleted')
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to delete wallet')
  }
}

// Add wallet dialog state
const addWalletDialogOpen = ref(false)
const addWalletType = ref<'mpp' | 'xendit' | null>(null)
const addWalletSaving = ref(false)
const showMppImport = ref(false)
const mppImportKey = ref('')
const addXenditForm = ref({
  apiKey: '',
  callbackToken: '',
  currency: 'IDR',
  country: 'ID',
})
const addWalletWebhookUrl = ref<string | null>(null)

// Currency drives country (per Xendit's per-country channel catalogs).
// Cross-border combinations are blocked at the backend; mirror that here.
watch(
  () => addXenditForm.value.currency,
  (currency) => {
    addXenditForm.value.country = countryForCurrency(currency)
  },
)

watch(
  () => addWalletDialogOpen.value,
  (isOpen) => {
    if (!isOpen) {
      addWalletType.value = null
      addWalletSaving.value = false
      showMppImport.value = false
      mppImportKey.value = ''
      addXenditForm.value = {
        apiKey: '',
        callbackToken: '',
        currency: 'IDR',
        country: 'ID',
      }
      addWalletWebhookUrl.value = null
    }
  },
)

const handleCreateMpp = async () => {
  addWalletSaving.value = true
  try {
    await walletsApi.createMpp()
    toast.success('MPP wallet created')
    addWalletDialogOpen.value = false
    await fetchWallets()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to create wallet')
  } finally {
    addWalletSaving.value = false
  }
}

const handleImportMpp = async () => {
  addWalletSaving.value = true
  try {
    await walletsApi.importMpp(mppImportKey.value)
    toast.success('MPP wallet imported')
    addWalletDialogOpen.value = false
    await fetchWallets()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to import wallet')
  } finally {
    addWalletSaving.value = false
  }
}

const handleCreateXendit = async () => {
  if (
    allWallets.value.some(
      (w) => w.wallet_type === 'xendit' && w.currency === addXenditForm.value.currency,
    )
  ) {
    toast.error(
      `A Xendit wallet for ${addXenditForm.value.currency} already exists. Only one wallet per currency is allowed.`,
    )
    return
  }

  addWalletSaving.value = true
  try {
    const wallet = await walletsApi.createXendit({
      apiKey: addXenditForm.value.apiKey,
      callbackToken: addXenditForm.value.callbackToken,
      currency: addXenditForm.value.currency,
      country: addXenditForm.value.country,
    })
    addWalletWebhookUrl.value = wallet.display.webhook_url ?? null
    toast.success('Xendit wallet connected')
    await fetchWallets()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to connect Xendit')
  } finally {
    addWalletSaving.value = false
  }
}

const saveChanges = async () => {
  if (networkMode.value === 'custom' && !customUrl.value) {
    toast.error('Please enter your public URL')
    return
  }

  saving.value = true
  try {
    if (networkMode.value === 'subdomain') {
      if (!proxyStatus.connected) {
        const result = await settingsApi.configureProxy()
        proxyStatus.connected = result.connected
        proxyStatus.publicUrl = result.public_url
        proxyStatus.hasToken = result.has_token
      }
    } else {
      if (proxyStatus.hasToken) {
        await settingsApi.disconnectProxy()
        proxyStatus.connected = false
        proxyStatus.publicUrl = null
        proxyStatus.hasToken = false
      }

      await settingsApi.updatePublicUrl({ public_url: customUrl.value })
    }

    await settingsApi.updateDiagnostics({ enabled: diagnosticsEnabled.value })
    setDiagnosticsEnabled(diagnosticsEnabled.value)
    setPosthogDiagnosticsEnabled(diagnosticsEnabled.value)

    toast.success('Settings saved')
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to save settings')
  }

  saving.value = false
}

onMounted(() => {
  fetchAccountInfo()
  fetchNetworkConfig()
  fetchDiagnostics()
  fetchWallets()
})
</script>
