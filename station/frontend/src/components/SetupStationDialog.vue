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
import { useSessionStore } from '@/stores/session'
import { useStationStore } from '@/stores/station'

/**
 * First-run setup, shown on the admin dashboard while the domain is not set.
 * Not dismissable — finishing setup (which sets the domain) is what closes it.
 */
defineProps<{ open: boolean }>()

const station = useStationStore()
const session = useSessionStore()

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

// Step 2 — optional shared wallet
const walletProvider = ref<WalletProvider>('xendit')
const walletCurrency = ref('USD')
const walletKey = ref('')
const CURRENCIES = ['USD', 'IDR', 'PHP', 'SGD', 'EUR']

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

function nextFromWallet(withWallet: boolean) {
  if (withWallet) {
    if (walletKey.value.trim().length < 8) {
      toast.error('A valid secret API key is required')
      return
    }
    station.configureWallet({
      provider: walletProvider.value,
      apiKey: walletKey.value.trim(),
      currency: walletCurrency.value,
    })
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
  // Wallet/earnings demo data is still mocked — seed it now so the
  // dashboard reflects the setup choices (chosen domain; wallet only if
  // one was added)
  if (session.profile) station.seedForDemo(session.profile.email, session.profile.fullName)
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
                <SelectItem value="stripe">Stripe</SelectItem>
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
          <Input
            id="setup-wallet-key"
            v-model="walletKey"
            type="password"
            :placeholder="walletProvider === 'xendit' ? 'xnd_prod_…' : 'sk_live_…'"
          />
        </div>
        <div class="flex items-center justify-between">
          <Button variant="ghost" size="sm" @click="step = 0">
            <ArrowLeft class="mr-1.5 h-3.5 w-3.5" />
            Back
          </Button>
          <div class="flex gap-2">
            <Button variant="outline" @click="nextFromWallet(false)">Skip for now</Button>
            <Button @click="nextFromWallet(true)">
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
