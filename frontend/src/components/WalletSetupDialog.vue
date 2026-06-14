<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2">
          <Wallet class="h-5 w-5 text-primary" />
          {{ walletAddress ? 'Wallet Settings' : 'Set Up Wallet' }}
        </DialogTitle>
        <DialogDescription>
          {{
            walletAddress
              ? 'Manage your payment wallet for receiving MPP payments'
              : 'Create or import a wallet to start receiving payments for your endpoints'
          }}
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <!-- Wallet exists -->
        <div v-if="walletAddress" class="space-y-4">
          <div class="space-y-1">
            <p class="text-sm text-muted-foreground">Wallet Address</p>
            <p class="text-sm font-mono font-medium text-foreground break-all">
              {{ walletAddress }}
            </p>
          </div>
          <div
            v-if="isCollectiveAdmin"
            class="flex items-start space-x-3 rounded-lg border border-border bg-muted/40 p-4"
          >
            <Checkbox id="dialog-share-wallet" v-model="collectiveWalletShareable" class="mt-0.5" />
            <div>
              <Label for="dialog-share-wallet" class="text-sm font-medium cursor-pointer">
                Share this wallet with the collective
              </Label>
            </div>
          </div>
          <div v-if="showChangeWallet" class="space-y-3 pt-3 border-t">
            <div class="space-y-2">
              <Label for="dialog-new-wallet">New Wallet Address</Label>
              <Input
                id="dialog-new-wallet"
                v-model="newWalletAddress"
                placeholder="0x..."
                class="font-mono"
              />
              <p v-if="walletAddressError" class="text-sm text-red-600">
                {{ walletAddressError }}
              </p>
            </div>
            <div class="flex gap-2">
              <Button size="sm" @click="handleUpdateWallet" :disabled="saving">
                <Loader2 v-if="saving" class="h-4 w-4 mr-2 animate-spin" />
                Update Address
              </Button>
              <Button variant="ghost" size="sm" @click="showChangeWallet = false">Cancel</Button>
            </div>
          </div>
          <Button v-else variant="outline" size="sm" @click="showChangeWallet = true">
            Change Wallet
          </Button>
        </div>

        <!-- No wallet -->
        <div v-else class="space-y-4">
          <div class="flex flex-col gap-3">
            <Button @click="handleCreateWallet" :disabled="saving">
              <Loader2 v-if="saving" class="h-4 w-4 mr-2 animate-spin" />
              Create Wallet
            </Button>
            <div
              v-if="isCollectiveAdmin"
              class="flex items-start space-x-3 rounded-lg border border-border bg-muted/40 p-4"
            >
              <Checkbox
                id="dialog-share-new-wallet"
                v-model="collectiveWalletShareable"
                class="mt-0.5"
              />
              <div>
                <Label for="dialog-share-new-wallet" class="text-sm font-medium cursor-pointer">
                  Make new wallet shareable
                </Label>
                <p class="text-sm text-muted-foreground mt-1">
                  This means members of your collective(s) can decide to collect their revenues with
                  your wallet.
                </p>
              </div>
            </div>
            <button
              @click="showImportWallet = !showImportWallet"
              class="text-sm text-primary hover:text-primary/80 text-left"
            >
              I already have a wallet
            </button>
          </div>
          <div v-if="showImportWallet" class="space-y-3 pt-3 border-t">
            <div class="space-y-2">
              <Label for="dialog-import-key">Private Key</Label>
              <Input
                id="dialog-import-key"
                v-model="importPrivateKey"
                type="password"
                autocomplete="off"
                placeholder="Enter your private key"
                class="font-mono"
              />
            </div>
            <div class="flex gap-2">
              <Button size="sm" @click="handleImportWallet" :disabled="saving || !importPrivateKey">
                <Loader2 v-if="saving" class="h-4 w-4 mr-2 animate-spin" />
                Import Wallet
              </Button>
              <Button variant="ghost" size="sm" @click="showImportWallet = false">Cancel</Button>
            </div>
          </div>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Wallet, Loader2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { walletsApi } from '@/api/endpoints/wallets'
import { useUserStore } from '@/stores/user'
import { useCollectiveMode } from '@/composables/useCollectiveMode'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'wallet-updated': [address: string]
}>()

const userStore = useUserStore()
const { isCollectiveAdmin } = useCollectiveMode()

const walletAddress = ref<string | null>(null)
const currentWalletId = ref<string | null>(null)
const saving = ref(false)
const showChangeWallet = ref(false)
const newWalletAddress = ref('')
const walletAddressError = ref<string | null>(null)
const showImportWallet = ref(false)
const importPrivateKey = ref('')
const collectiveWalletShareable = ref(true)

const isValidEthAddress = (address: string): boolean => {
  return /^0x[0-9a-fA-F]{40}$/.test(address)
}

const fetchWallet = async () => {
  try {
    const wallets = await walletsApi.list()
    const mppWallet = wallets.find((w) => w.wallet_type === 'mpp')
    if (mppWallet) {
      walletAddress.value = mppWallet.display.wallet_address ?? null
      currentWalletId.value = mppWallet.id
    } else {
      walletAddress.value = null
      currentWalletId.value = null
    }
  } catch {
    walletAddress.value = null
    currentWalletId.value = null
  }
}

const handleCreateWallet = async () => {
  saving.value = true
  try {
    const res = await walletsApi.createMpp()
    walletAddress.value = res.display.wallet_address ?? null
    currentWalletId.value = res.id
    toast.success('Wallet created successfully')
    emit('wallet-updated', res.display.wallet_address ?? '')
    await userStore.fetchWalletInfo()
    userStore.fetchBalance()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to create wallet')
  } finally {
    saving.value = false
  }
}

const handleImportWallet = async () => {
  saving.value = true
  try {
    const res = await walletsApi.importMpp(importPrivateKey.value)
    walletAddress.value = res.display.wallet_address ?? null
    currentWalletId.value = res.id
    importPrivateKey.value = ''
    showImportWallet.value = false
    toast.success('Wallet imported successfully')
    emit('wallet-updated', res.display.wallet_address ?? '')
    await userStore.fetchWalletInfo()
    userStore.fetchBalance()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to import wallet')
  } finally {
    saving.value = false
  }
}

const handleUpdateWallet = async () => {
  walletAddressError.value = null
  if (!isValidEthAddress(newWalletAddress.value)) {
    walletAddressError.value =
      'Please enter a valid Ethereum address (0x followed by 40 hex characters)'
    return
  }
  if (!currentWalletId.value) {
    toast.error('No wallet to update')
    return
  }
  saving.value = true
  try {
    const res = await walletsApi.updateMppAddress(currentWalletId.value, newWalletAddress.value)
    walletAddress.value = res.display.wallet_address ?? null
    newWalletAddress.value = ''
    showChangeWallet.value = false
    toast.success('Wallet address updated')
    emit('wallet-updated', res.display.wallet_address ?? '')
    userStore.fetchBalance()
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to update wallet address')
  } finally {
    saving.value = false
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      fetchWallet()
    } else {
      showChangeWallet.value = false
      showImportWallet.value = false
      newWalletAddress.value = ''
      walletAddressError.value = null
      importPrivateKey.value = ''
    }
  },
)
</script>
