<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight, Check, Globe, Lock, Rocket, Tag, Wallet } from 'lucide-vue-next'
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
import VersionSelect from '@/components/VersionSelect.vue'
import SyftHubIdentityCard from '@/components/SyftHubIdentityCard.vue'
import WalletSetupForm from '@/components/WalletSetupForm.vue'
import WalletSummaryCard from '@/components/WalletSummaryCard.vue'
import { ApiError } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import { useStationStore } from '@/stores/station'

/**
 * First-run setup, shown on the admin dashboard while the domain is not set.
 * Not dismissable — finishing setup (which sets the domain) is what closes it.
 */
const props = defineProps<{ open: boolean }>()

const station = useStationStore()
const session = useSessionStore()
const router = useRouter()

// The dialog is not dismissable (setup is what closes it), so it must offer
// its own way out of the SESSION — otherwise a wrong-account sign-in is
// trapped behind the overlay with the header's sign-out unreachable.
function signOut() {
  session.signOut()
  router.push({ name: 'signin' })
}

// Warm the image catalog the moment the wizard opens — the admin spends the
// domain and wallet steps ahead of the version picker, so by step 3 the
// list renders instantly. The picker handles (and falls back on) a failure.
watch(
  () => props.open,
  (open) => {
    if (open) station.loadImageTags().catch(() => {})
  },
  { immediate: true },
)

const STEPS = [
  { title: 'Domain', icon: Globe },
  { title: 'Shared wallet', icon: Wallet },
  { title: 'Version', icon: Tag },
] as const

const step = ref(0)

// Step 1 — where spaces live.
// The station already knows its own public host (from its ingress); we SHOW it
// and hang spaces off it, so the admin only picks an optional subdomain prefix
// rather than retyping the domain. Host-run dev has no known host → free-text.
const DOMAIN_RE = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$/
const LABELS_RE = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$/

const stationHost = computed(() => station.stationHost)
// Escape hatch: type a different domain even when a host is known (dev/edge).
const manualDomain = ref(false)
const useHost = computed(() => !!stationHost.value && !manualDomain.value)

const prefixInput = ref('') // optional label(s) between the space and the host
const domainInput = ref('') // free-text fallback

// The spaces' parent domain we actually submit.
const effectiveDomain = computed(() => {
  if (useHost.value) {
    const prefix = prefixInput.value.trim().toLowerCase().replace(/\.$/, '')
    return prefix ? `${prefix}.${stationHost.value}` : stationHost.value
  }
  return domainInput.value.trim().toLowerCase()
})

const domainValid = computed(() => {
  if (
    useHost.value &&
    prefixInput.value.trim() &&
    !LABELS_RE.test(prefixInput.value.trim().toLowerCase())
  ) {
    return false
  }
  return DOMAIN_RE.test(effectiveDomain.value)
})

// Step 2 — optional shared wallet. The fields, validation, and save live in
// WalletSetupForm (shared with the Earnings dialog); this wizard only owns
// the skip/advance buttons. When a wallet is already saved (setup re-run),
// the step offers it as-is and only unfolds the form to replace it.
const walletForm = ref<InstanceType<typeof WalletSetupForm> | null>(null)
const savingWallet = ref(false)
const replacingWallet = ref(false)

// Step 3 — Syft Space version (image tag from the registry)
const versionInput = ref('')
const finishing = ref(false)

function nextFromDomain() {
  if (!domainValid.value) {
    toast.error(
      useHost.value
        ? 'Enter a valid subdomain prefix, or leave it blank'
        : 'Enter a valid domain, e.g. spaces.my-station.org',
    )
    return
  }
  step.value = 1
}

async function nextFromWallet(withWallet: boolean) {
  if (withWallet) {
    savingWallet.value = true
    try {
      // Validation and API errors are toasted by the form itself.
      const result = await walletForm.value?.save()
      if (!result) return
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
      domain: effectiveDomain.value,
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

      <!-- Step 1: where spaces live -->
      <div v-if="step === 0" class="space-y-4">
        <!-- Host known: show it, ask only for an optional subdomain prefix -->
        <template v-if="useHost">
          <p class="text-xs text-muted-foreground">
            Your station is reachable here, and every space is a subdomain of it. Point a wildcard
            DNS record at this cluster so spaces resolve.
          </p>
          <div class="space-y-1.5">
            <Label>Station</Label>
            <div
              class="flex items-center gap-2 rounded-md border bg-muted/40 px-3 py-2 text-sm font-medium"
            >
              <Globe class="h-3.5 w-3.5 text-muted-foreground" />
              {{ stationHost }}
            </div>
          </div>
          <div class="space-y-1.5">
            <Label for="setup-prefix">Subdomain for spaces (optional)</Label>
            <div class="flex items-center gap-1.5 text-sm">
              <span class="text-muted-foreground">research-lab.</span>
              <Input
                id="setup-prefix"
                v-model="prefixInput"
                placeholder="spaces"
                class="max-w-[8rem]"
              />
              <span class="text-muted-foreground">.{{ stationHost }}</span>
            </div>
            <p class="text-xs text-muted-foreground">
              Blank → spaces sit directly under the station ({{ '*' }}.{{ stationHost }}). A prefix
              sandboxes them under its own <code>*</code> wildcard.
            </p>
          </div>
          <p class="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Globe class="h-3 w-3" />
            Spaces will look like: research-lab.{{ effectiveDomain }}
          </p>
          <p class="flex items-start gap-1.5 text-xs text-muted-foreground">
            <Lock class="mt-0.5 h-3 w-3 shrink-0" />
            <span>
              For HTTPS, one certificate with two names — <code>{{ stationHost }}</code> and
              <code>*.{{ effectiveDomain }}</code> — serves the station and every space: a
              certificate wildcard covers exactly one label, never the bare host.
            </span>
          </p>
          <div class="flex items-center justify-between">
            <button
              type="button"
              class="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
              @click="manualDomain = true"
            >
              Use a different domain
            </button>
            <Button @click="nextFromDomain">
              Next
              <ArrowRight class="ml-1.5 h-3.5 w-3.5" />
            </Button>
          </div>
        </template>

        <!-- Host unknown (or overridden): type the domain -->
        <template v-else>
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
          <p class="flex items-start gap-1.5 text-xs text-muted-foreground">
            <Lock class="mt-0.5 h-3 w-3 shrink-0" />
            <span>
              For HTTPS, the spaces' certificate needs a
              <code>*.{{ domainInput.trim() || 'your-domain' }}</code> wildcard name — a certificate
              wildcard covers exactly one label.
            </span>
          </p>
          <div class="flex items-center justify-between">
            <button
              v-if="stationHost"
              type="button"
              class="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
              @click="manualDomain = false"
            >
              Use the station host
            </button>
            <span v-else />
            <Button @click="nextFromDomain">
              Next
              <ArrowRight class="ml-1.5 h-3.5 w-3.5" />
            </Button>
          </div>
        </template>
      </div>

      <!-- Step 2: optional shared wallet. v-show (not v-if) so the form's
           state — including a minted hub token — survives Back/Next. -->
      <div v-show="step === 1" class="space-y-4">
        <!-- A wallet already exists: offer it as-is, unfold the form to replace. -->
        <template v-if="station.wallet && !replacingWallet">
          <p class="text-xs text-muted-foreground">
            This station already has a shared wallet — users buy credits through it and spend them
            at any space. Keep using it, or replace the provider account behind it.
          </p>
          <WalletSummaryCard />
          <div class="flex items-center justify-between">
            <Button variant="ghost" size="sm" @click="step = 0">
              <ArrowLeft class="mr-1.5 h-3.5 w-3.5" />
              Back
            </Button>
            <div class="flex gap-2">
              <Button variant="outline" @click="replacingWallet = true">Replace…</Button>
              <Button @click="step = 2">
                Use this wallet
                <ArrowRight class="ml-1.5 h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </template>

        <template v-else>
          <p v-if="!station.wallet" class="text-xs text-muted-foreground">
            One gateway account for the whole station: users buy credits here and spend them at any
            space; you pay members for what users spend. Skip it to run without pooled payments —
            you can add it later from Earnings.
          </p>
          <SyftHubIdentityCard />

          <WalletSetupForm ref="walletForm" />
          <div class="flex items-center justify-between">
            <Button
              v-if="replacingWallet"
              variant="ghost"
              size="sm"
              @click="replacingWallet = false"
            >
              <ArrowLeft class="mr-1.5 h-3.5 w-3.5" />
              Keep existing
            </Button>
            <Button v-else variant="ghost" size="sm" @click="step = 0">
              <ArrowLeft class="mr-1.5 h-3.5 w-3.5" />
              Back
            </Button>
            <div class="flex gap-2">
              <Button v-if="!station.wallet" variant="outline" @click="nextFromWallet(false)">
                Skip for now
              </Button>
              <Button :disabled="savingWallet" @click="nextFromWallet(true)">
                {{ station.wallet ? 'Replace wallet' : 'Add wallet' }}
                <ArrowRight class="ml-1.5 h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </template>
      </div>

      <!-- Step 3: version -->
      <div v-if="step === 2" class="space-y-4">
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

      <!-- Identity escape hatch: setup is mandatory, the session is not. -->
      <p class="border-t pt-3 text-center text-xs text-muted-foreground">
        Signed in as <span class="font-medium">{{ session.profile?.email }}</span>
        · Not you?
        <button
          type="button"
          class="underline underline-offset-2 hover:text-foreground"
          @click="signOut"
        >
          Sign out
        </button>
      </p>
    </DialogContent>
  </Dialog>
</template>
