<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, Globe, Rocket } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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
import { ApiError } from '@/api/client'
import type { SpaceRequest } from '@/lib/types'
import { slugify } from '@/lib/types'
import { useStationStore } from '@/stores/station'

const props = defineProps<{
  request: SpaceRequest | null
  open: boolean
}>()

const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const station = useStationStore()

const spaceName = ref('')
const subdomain = ref('')
/** 'station' = attach the shared wallet (default); 'none' = unbilled space. */
const walletChoice = ref<'station' | 'none'>('station')

// Prefill from the request whenever the modal opens (review-and-tweak)
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen && props.request) {
      spaceName.value = props.request.spaceName
      subdomain.value = props.request.subdomain
      walletChoice.value = 'station'
    }
  },
)

// Reserved by a running space OR another request already provisioning
const subdomainTaken = computed(() =>
  station.subdomainInUse(slugify(subdomain.value), props.request?.id),
)

const isRetry = computed(() => props.request?.status === 'failed')
const working = ref(false)

async function approve() {
  if (!props.request) return
  if (!isRetry.value && !slugify(subdomain.value)) {
    toast.error('Subdomain is required')
    return
  }
  working.value = true
  try {
    const config = {
      spaceName: spaceName.value.trim(),
      subdomain: slugify(subdomain.value),
      attachWallet: station.wallet !== null && walletChoice.value === 'station',
    }
    // Retry re-runs the failed request as-is; approve allows edits
    if (isRetry.value) await station.retryProvision(props.request.id, config)
    else await station.approveRequest(props.request.id, config)
    toast.success(isRetry.value ? 'Retrying setup' : 'Approved — setting up the space', {
      description: `${props.request.subdomain}.${station.domain}`,
    })
    emit('update:open', false)
  } catch (error) {
    // 409 = subdomain conflict or station not set up
    toast.error(error instanceof ApiError ? error.message : 'Approving the request failed')
  } finally {
    working.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="(v: boolean) => emit('update:open', v)">
    <DialogContent v-if="request">
      <DialogHeader>
        <DialogTitle>{{ isRetry ? 'Retry setup' : 'Approve request' }}</DialogTitle>
        <DialogDescription> {{ request.requesterEmail }} — verified via SyftHub </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <div
          v-if="isRetry && request.failureError"
          class="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive"
        >
          {{ request.failureError }}
        </div>

        <div class="grid gap-4 sm:grid-cols-2">
          <div class="space-y-1.5">
            <Label for="approve-name">Space name</Label>
            <Input id="approve-name" v-model="spaceName" :disabled="isRetry" />
          </div>
          <div class="space-y-1.5">
            <Label for="approve-subdomain">Subdomain</Label>
            <Input id="approve-subdomain" v-model="subdomain" :disabled="isRetry" />
          </div>
        </div>
        <p class="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Globe class="h-3 w-3" />
          {{ slugify(subdomain) || '—' }}.{{ station.domain }}
          <span v-if="!isRetry && subdomainTaken" class="text-destructive">— already in use</span>
        </p>

        <!-- Wallet picker — only when the station has a wallet; retry keeps
             the original choice -->
        <div v-if="station.wallet && !isRetry" class="space-y-1.5">
          <Label>Payments</Label>
          <Select v-model="walletChoice">
            <SelectTrigger class="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="station">
                Station wallet — {{ station.wallet.provider }} · {{ station.wallet.currency }}
              </SelectItem>
              <SelectItem value="none">No wallet — space runs unbilled</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div class="rounded-md border bg-muted/40 px-3 py-2.5">
          <p class="mb-1.5 text-xs font-medium text-muted-foreground">This space will get</p>
          <ul class="space-y-1">
            <li
              v-for="item in station.spaceIncludes"
              :key="item"
              class="flex items-center gap-1.5 text-xs text-muted-foreground"
            >
              <Check class="h-3 w-3 shrink-0 text-success" />
              {{ item }}
            </li>
          </ul>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">Cancel</Button>
        <Button :disabled="working" @click="approve">
          <Rocket class="mr-1.5 h-4 w-4" />
          {{ isRetry ? 'Retry' : 'Approve & create' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
