<script setup lang="ts">
import { computed, ref } from 'vue'
import { toast } from 'vue-sonner'
import { ExternalLink, Loader2, Wallet } from 'lucide-vue-next'
import SyftHubIdentityCard from '@/components/SyftHubIdentityCard.vue'
import WalletSetupForm from '@/components/WalletSetupForm.vue'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useWalletAttachRun } from '@/composables/useWalletAttachRun'
import { DOCS } from '@/lib/docs'
import { useStationStore } from '@/stores/station'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const station = useStationStore()
const { running, run } = useWalletAttachRun()

// The form remounts on every open (DialogContent unmounts when closed), so
// its state resets without any bookkeeping here.
const form = ref<InstanceType<typeof WalletSetupForm> | null>(null)
const saving = ref(false)
const confirmOpen = ref(false)

/**
 * Only a provider change reaches the spaces: gateway credentials stay at the
 * station, but the bundle catalog is keyed by provider and each attached
 * space holds the copy injected at its last converge. A key rotation
 * therefore saves silently — prompting for it would train admins to click
 * through a station-wide restart.
 */
const providerChanged = computed(
  () => station.wallet !== null && form.value?.provider !== station.wallet.provider,
)
const attachedSpaces = computed(() => station.spaces.filter((s) => s.walletStatus === 'attached'))
const reappliable = computed(() =>
  attachedSpaces.value.filter((s) => s.url && s.health !== 'paused'),
)
const unreachable = computed(() => attachedSpaces.value.length - reappliable.value.length)

async function save(): Promise<void> {
  if (providerChanged.value && attachedSpaces.value.length > 0) {
    confirmOpen.value = true
    return
  }
  await persist()
}

/** Saves the wallet; returns false when the form refused it. */
async function persist(): Promise<boolean> {
  saving.value = true
  try {
    const saved = await form.value?.save()
    if (!saved) return false // validation/API errors already toasted by the form
    toast.success('Shared wallet saved', {
      description: 'New spaces get it automatically. Existing ones you attach yourself.',
    })
    emit('update:open', false)
    return true
  } finally {
    saving.value = false
  }
}

/**
 * Save, then re-apply. In this order because a re-applied space is rendered
 * from the stored wallet — it has to be the new one. Spaces the run cannot
 * reach keep the wallet_stale condition the save raised on them, which is
 * the record of what is still to do.
 */
async function saveAndUpdate(): Promise<void> {
  confirmOpen.value = false
  const targets = reappliable.value
  if (!(await persist())) return
  await station.loadSpaces() // pick up the conditions the save just raised
  await run(targets)
}

async function saveOnly(): Promise<void> {
  confirmOpen.value = false
  if (await persist()) await station.loadSpaces()
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
          spend them at any space. You pay members from Earnings for what users spend.
          <a
            :href="DOCS.creditsAndPayouts"
            target="_blank"
            rel="noopener"
            class="inline-flex items-center gap-1 whitespace-nowrap underline underline-offset-2 hover:text-foreground"
          >
            How credits work
            <ExternalLink class="h-3.5 w-3.5" />
          </a>
        </DialogDescription>
      </DialogHeader>

      <WalletSetupForm ref="form" />

      <div class="border-t pt-4">
        <SyftHubIdentityCard />
      </div>

      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">Cancel</Button>
        <Button :disabled="saving || running" @click="save">
          <Loader2 v-if="running" class="mr-1.5 h-3.5 w-3.5 animate-spin" />
          {{ station.wallet ? 'Replace wallet' : 'Add shared wallet' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>

  <!-- Only reachable on a provider change with spaces already on the wallet. -->
  <Dialog :open="confirmOpen" @update:open="(v: boolean) => (confirmOpen = v)">
    <DialogContent>
      <DialogHeader>
        <DialogTitle>
          {{ attachedSpaces.length }} space{{ attachedSpaces.length === 1 ? '' : 's' }} publish this
          wallet's price list
        </DialogTitle>
        <DialogDescription>
          Changing the provider changes that list. Each space carries its own copy and has to be
          redeployed to pick up the new one.
        </DialogDescription>
      </DialogHeader>

      <ul class="space-y-2 text-sm text-muted-foreground">
        <li v-if="reappliable.length > 0">
          <span class="font-medium text-foreground">
            {{ reappliable.length }} can be updated now
          </span>
          — one at a time, each down for up to a minute. Requests in flight and any running
          ingestion are cut off.
        </li>
        <li v-if="unreachable > 0">
          <span class="font-medium text-foreground">{{ unreachable }} cannot</span> — paused, or not
          created yet. They stay flagged until you re-apply the wallet to them.
        </li>
      </ul>

      <DialogFooter>
        <Button variant="outline" @click="confirmOpen = false">Cancel</Button>
        <Button variant="outline" @click="saveOnly">Save, update later</Button>
        <Button :disabled="reappliable.length === 0" @click="saveAndUpdate">
          <Wallet class="mr-1.5 h-3.5 w-3.5" />
          Save and update {{ reappliable.length }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
