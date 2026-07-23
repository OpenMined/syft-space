<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowLeft, ArrowRight, Check, Globe, Rocket, Tag, Wallet } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import VersionSelect from '@/components/VersionSelect.vue'
import { ApiError } from '@/api/client'
import type { WalletProvider } from '@/lib/types'
import { useStationStore } from '@/stores/station'

/**
 * First-run setup, shown on the admin dashboard while the domain is not set.
 * Not dismissable — finishing setup (which sets the domain) is what closes it.
 */
defineProps<{ open: boolean }>()

const station = useStationStore()

const STEPS = [
  { title: 'Domain', icon: Globe },
  { title: 'Shared wallet', icon: Wallet },
  { title: 'Version', icon: Tag },
] as const

const step = ref(0)

// Step 1 — public domain
const domainInput = ref('')
const domainValid = computed(() =>
  /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$/.test(
    domainInput.value.trim().toLowerCase(),
  ),
)

// Step 2 — optional shared wallet (Xendit's currencies; USD arrives with Stripe)
const walletProvider = ref<WalletProvider>('xendit')
const walletCurrency = ref('PHP')
const walletKey = ref('')
const walletCallbackToken = ref('')
const savingWallet = ref(false)
const CURRENCIES = ['IDR', 'PHP', 'SGD', 'MYR', 'VND', 'THB']

/** Where the gateway must deliver payment events (shown for the dashboard setup). */
const webhookUrl = computed(() => `${window.location.origin}/api/v1/credits/webhooks/xendit`)

// Step 3 — Syft Space version (image tag from the registry)
const versionInput = ref('')
const finishing = ref(false)

function nextFromDomain() {
  if (!domainValid.value) {
    toast.error('Enter a valid domain, e.g. spaces.my-station.org')
    return
  }
  step.value = 1
}

async function nextFromWallet(withWallet: boolean) {
  if (withWallet) {
    if (walletKey.value.trim().length < 8) {
      toast.error('A valid secret API key is required')
      return
    }
    if (!walletCallbackToken.value.trim()) {
      toast.error('The webhook callback token is required')
      return
    }
    savingWallet.value = true
    try {
      await station.setupWallet({
        provider: walletProvider.value,
        currency: walletCurrency.value,
        credentials: {
          api_key: walletKey.value.trim(),
          callback_token: walletCallbackToken.value.trim(),
        },
      })
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : 'Could not save the wallet')
      return
    } finally {
      savingWallet.value = false
    }
  }
  step.value = 2
}

async function finish() {
  if (!versionInput.value.trim()) {
    toast.error('Pick or enter the version to deploy')
    return
  }
  finishing.value = true
  try {
    // Setting the domain marks setup done, which closes this dialog
    await station.completeOnboarding({
      domain: domainInput.value.trim().toLowerCase(),
      version: versionInput.value.trim(),
    })
  } catch (error) {
    toast.error(error instanceof ApiError ? error.message : 'Saving setup failed')
    return
  } finally {
    finishing.value = false
  }
  toast.success('Station is ready', {
    description: `Spaces will live on *.${station.domain} running ${station.supportedVersion}.`,
  })
}
</script>

<template>
  <Dialog :open="open">
    <DialogContent
      :show-close-button="false"
      @escape-key-down="(e) => e.preventDefault()"
      @interact-outside="(e) => e.preventDefault()"
    >
      <DialogHeader>
        <DialogTitle>Set up your station</DialogTitle>
        <DialogDescription>
          Three quick decisions and you're live — members can request spaces right after.
        </DialogDescription>
      </DialogHeader>

      <!-- Stepper -->
      <div class="flex items-center gap-2">
        <template v-for="(s, i) in STEPS" :key="s.title">
          <div
            class="flex items-center gap-1.5 text-xs"
            :class="i === step ? 'font-medium text-foreground' : 'text-muted-foreground'"
          >
            <span
              class="flex h-5 w-5 items-center justify-center rounded-full border text-[10px]"
              :class="
                i < step
                  ? 'border-success bg-success/15 text-success'
                  : i === step
                    ? 'border-primary text-primary'
                    : ''
              "
            >
              <Check v-if="i < step" class="h-3 w-3" />
              <template v-else>{{ i + 1 }}</template>
            </span>
            {{ s.title }}
          </div>
          <div v-if="i < STEPS.length - 1" class="h-px flex-1 bg-border" />
        </template>
      </div>

      <!-- Step 1: domain -->
      <div v-if="step === 0" class="space-y-4">
        <p class="text-xs text-muted-foreground">
          Every space gets its own subdomain on this domain. Point a wildcard DNS record
          (*.your-domain) at the machines running this station.
        </p>
        <div class="space-y-1.5">
          <Label for="setup-domain">Domain</Label>
          <Input id="setup-domain" v-model="domainInput" placeholder="spaces.my-station.org" />
        </div>
        <p class="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Globe class="h-3 w-3" />
          Spaces will look like: research-lab.{{ domainInput.trim() || '…' }}
        </p>
        <div class="flex justify-end">
          <Button @click="nextFromDomain">
            Next
            <ArrowRight class="ml-1.5 h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <!-- Step 2: optional shared wallet -->
      <div v-else-if="step === 1" class="space-y-4">
        <p class="text-xs text-muted-foreground">
          One gateway account for the whole station: users buy credits here and spend them at any
          space; you pay members for what users spend. Skip it to run without pooled payments — you
          can add it later from Earnings.
        </p>
        <div class="grid gap-4 sm:grid-cols-2">
          <div class="space-y-1.5">
            <Label>Provider</Label>
            <Select v-model="walletProvider">
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
            <Select v-model="walletCurrency">
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
          <Label for="setup-wallet-key">Secret API key</Label>
          <Input id="setup-wallet-key" v-model="walletKey" type="password" placeholder="xnd_…" />
        </div>
        <div class="space-y-1.5">
          <Label for="setup-wallet-callback">Webhook callback token</Label>
          <Input
            id="setup-wallet-callback"
            v-model="walletCallbackToken"
            type="password"
            placeholder="From the Xendit dashboard → Webhooks"
          />
          <p class="text-xs text-muted-foreground">
            Point the Xendit webhook at
            <code class="rounded bg-muted px-1 font-mono text-[11px]">{{ webhookUrl }}</code>
          </p>
        </div>
        <div class="flex items-center justify-between">
          <Button variant="ghost" size="sm" @click="step = 0">
            <ArrowLeft class="mr-1.5 h-3.5 w-3.5" />
            Back
          </Button>
          <div class="flex gap-2">
            <Button variant="outline" @click="nextFromWallet(false)">Skip for now</Button>
            <Button :disabled="savingWallet" @click="nextFromWallet(true)">
              Add wallet
              <ArrowRight class="ml-1.5 h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </div>

      <!-- Step 3: version -->
      <div v-else class="space-y-4">
        <p class="text-xs text-muted-foreground">
          The image version every space runs, straight from the registry. You can bump it later in
          Settings and roll it out with "Update all" — downgrades are not supported.
        </p>
        <div class="space-y-1.5">
          <Label>Version</Label>
          <VersionSelect v-model="versionInput" />
        </div>
        <div class="flex items-center justify-between">
          <Button variant="ghost" size="sm" @click="step = 1">
            <ArrowLeft class="mr-1.5 h-3.5 w-3.5" />
            Back
          </Button>
          <Button :disabled="finishing" @click="finish">
            <Rocket class="mr-1.5 h-4 w-4" />
            Finish setup
          </Button>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
