<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  Banknote,
  ExternalLink,
  Inbox,
  MoreVertical,
  PauseCircle,
  ScrollText,
  Trash2,
  TriangleAlert,
  X,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import EmptyState from '@/components/ui/EmptyState.vue'
import StationAnimation from '@/components/StationAnimation.vue'
import HealthBadge from '@/components/HealthBadge.vue'
import RequestStatusBadge from '@/components/RequestStatusBadge.vue'
import RequestHistoryList from '@/components/RequestHistoryList.vue'
import ViewLogsSheet from '@/components/ViewLogsSheet.vue'
import type { Space, SpaceRequest } from '@/lib/types'
import { formatMoney } from '@/lib/types'
import { useStationStore } from '@/stores/station'
import { useSessionStore } from '@/stores/session'

const station = useStationStore()
const session = useSessionStore()

const email = computed(() => session.profile?.email ?? '')
// A member's loaded spaces are already their own; filter defensively anyway.
const mySpaces = computed(() => station.spaces.filter((s) => s.ownerEmail === email.value))
const inflightCreates = computed(() => station.inflightCreatesFor(email.value))
const pastRequests = computed(() => station.pastRequestsFor(email.value))
const hasNothing = computed(
  () => !mySpaces.value.length && !inflightCreates.value.length && !pastRequests.value.length,
)

const currency = computed(() => station.wallet?.currency ?? 'USD')

function earningsFor(spaceId: string) {
  return station.memberEarnings?.spaces.find((row) => row.space_id === spaceId)
}
function pendingDeletion(spaceId: string) {
  return station.pendingDeletionFor(spaceId)
}

// --- Logs ---
const logsTarget = ref<Space | null>(null)
const logsOpen = ref(false)
function openLogs(space: Space) {
  logsTarget.value = space
  logsOpen.value = true
}

// --- Withdraw an in-flight create ---
async function withdraw(request: SpaceRequest) {
  try {
    await station.withdrawRequest(request.id)
    toast('Request withdrawn', { description: request.spaceName })
  } catch {
    toast.error('Withdrawing the request failed')
  }
}

// --- Request / cancel deletion ---
const deleteTarget = ref<Space | null>(null)
const deleteReason = ref('')
const deleteDialogOpen = ref(false)
const submittingDeletion = ref(false)

function openDeleteDialog(space: Space) {
  deleteTarget.value = space
  deleteReason.value = ''
  deleteDialogOpen.value = true
}
async function confirmRequestDeletion() {
  if (!deleteTarget.value) return
  submittingDeletion.value = true
  try {
    await station.requestDeletion(deleteTarget.value.id, deleteReason.value.trim())
    toast('Deletion requested', { description: 'The station admin will review it.' })
    deleteDialogOpen.value = false
  } catch {
    toast.error('Requesting deletion failed')
  } finally {
    submittingDeletion.value = false
  }
}
async function cancelDeletion(request: SpaceRequest) {
  try {
    await station.withdrawRequest(request.id)
    toast('Deletion request cancelled', { description: request.spaceName })
  } catch {
    toast.error('Cancelling the request failed')
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <div class="space-y-3">
    <h2 class="text-sm font-medium text-muted-foreground">My requests</h2>

    <EmptyState
      v-if="hasNothing"
      :icon="Inbox"
      title="No requests yet"
      description="Submit the form to request your first space on this station."
    />

    <!-- Live space -->
    <Card v-for="space in mySpaces" :key="space.id">
      <CardContent class="space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div class="font-medium">{{ space.name }}</div>
            <div class="text-xs text-muted-foreground">
              {{ space.subdomain }}.{{ station.domain }}
            </div>
          </div>
          <div class="flex items-center gap-2">
            <HealthBadge :health="space.health" />
            <DropdownMenu v-if="!pendingDeletion(space.id)">
              <DropdownMenuTrigger as-child>
                <Button variant="ghost" size="icon" class="h-7 w-7">
                  <MoreVertical class="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem class="text-destructive" @click="openDeleteDialog(space)">
                  <Trash2 class="mr-2 h-3.5 w-3.5" />
                  Request deletion
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        <!-- Pending deletion: awaiting admin, space still runs -->
        <div
          v-if="pendingDeletion(space.id)"
          class="flex flex-wrap items-center justify-between gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2"
        >
          <span class="flex items-start gap-2 text-xs text-foreground">
            <Trash2 class="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
            Waiting for the admin to approve deletion. Your space keeps running until then.
          </span>
          <Button
            size="sm"
            variant="ghost"
            class="h-7 text-xs"
            @click="cancelDeletion(pendingDeletion(space.id)!)"
          >
            <X class="mr-1 h-3 w-3" />
            Cancel request
          </Button>
        </div>

        <!-- Paused -->
        <div
          v-else-if="space.health === 'paused'"
          class="flex items-start gap-2 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground"
        >
          <PauseCircle class="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>The admin paused this space. Your data is safe and it can be started again.</span>
        </div>

        <!-- Unhealthy -->
        <div
          v-else-if="space.health === 'unhealthy'"
          class="flex flex-wrap items-center justify-between gap-2 rounded-md bg-warning/10 px-3 py-2 text-xs text-foreground"
        >
          <span class="flex items-start gap-2">
            <TriangleAlert class="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
            Your space is having trouble right now. The admin has been notified.
          </span>
          <Button size="sm" variant="outline" class="h-7 text-xs" @click="openLogs(space)">
            <ScrollText class="mr-1 h-3 w-3" />
            View logs
          </Button>
        </div>

        <!-- Healthy -->
        <div
          v-else
          class="flex flex-wrap items-center justify-between gap-2 rounded-md bg-success/10 px-3 py-2"
        >
          <a
            :href="space.adminUrl ?? space.url"
            target="_blank"
            rel="noopener"
            class="flex items-center gap-1.5 text-sm font-medium underline-offset-2 hover:underline"
          >
            {{ space.url.replace('https://', '') }}
            <ExternalLink class="h-3.5 w-3.5" />
          </a>
          <Button size="sm" variant="ghost" class="h-7 text-xs" @click="openLogs(space)">
            <ScrollText class="mr-1 h-3 w-3" />
            Logs
          </Button>
        </div>

        <p
          v-if="earningsFor(space.id)"
          class="flex items-center gap-1.5 text-xs text-muted-foreground"
        >
          <Banknote class="h-3.5 w-3.5" />
          Earned {{ formatMoney(earningsFor(space.id)!.earned, currency) }} from
          {{ earningsFor(space.id)!.query_count.toLocaleString() }} paid queries ·
          {{ formatMoney(earningsFor(space.id)!.payable, currency) }} owed
        </p>
      </CardContent>
    </Card>

    <!-- In-flight create requests (no space yet) -->
    <Card v-for="request in inflightCreates" :key="request.id">
      <CardContent class="space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div class="font-medium">{{ request.spaceName }}</div>
            <div class="text-xs text-muted-foreground">
              {{ request.subdomain }}.{{ station.domain }} · requested
              {{ formatDate(request.createdAt) }}
            </div>
          </div>
          <RequestStatusBadge :status="request.status" />
        </div>

        <div
          v-if="request.status === 'pending'"
          class="flex flex-wrap items-center justify-between gap-2 rounded-md border border-dashed px-3 py-2"
        >
          <span class="text-xs text-muted-foreground">
            Waiting for the station admin to review your request.
          </span>
          <Button size="sm" variant="ghost" class="h-7 text-xs" @click="withdraw(request)">
            <X class="mr-1 h-3 w-3" />
            Withdraw
          </Button>
        </div>
        <div
          v-else-if="request.status === 'provisioning'"
          class="flex items-center gap-3 rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground"
        >
          <StationAnimation mini class="h-10 w-10 shrink-0" />
          Approved — your space is being set up. This usually takes a minute.
        </div>
        <div
          v-else-if="request.status === 'failed'"
          class="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive"
        >
          Provisioning failed — the station admin has been notified and can retry.
        </div>
      </CardContent>
    </Card>

    <!-- Past requests: terminal history of every type -->
    <template v-if="pastRequests.length">
      <h3 class="pt-2 text-xs font-medium text-muted-foreground">History</h3>
      <RequestHistoryList :requests="pastRequests" />
    </template>
  </div>

  <ViewLogsSheet v-model:open="logsOpen" :space="logsTarget" />

  <Dialog v-model:open="deleteDialogOpen">
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Request space deletion</DialogTitle>
        <DialogDescription>
          This asks the station admin to permanently delete
          <span class="font-medium text-foreground">{{ deleteTarget?.name }}</span
          >. Its data volume is removed on approval — this can't be undone.
        </DialogDescription>
      </DialogHeader>
      <div class="space-y-1.5">
        <Label for="delete-reason">Reason (optional)</Label>
        <Textarea
          id="delete-reason"
          v-model="deleteReason"
          rows="2"
          placeholder="Helps the admin review — e.g. no longer needed"
        />
      </div>
      <DialogFooter>
        <Button variant="ghost" @click="deleteDialogOpen = false">Cancel</Button>
        <Button
          variant="destructive"
          :disabled="submittingDeletion"
          @click="confirmRequestDeletion"
        >
          <Trash2 class="mr-1.5 h-4 w-4" />
          Request deletion
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
