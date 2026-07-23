<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  Banknote,
  ExternalLink,
  Inbox,
  PauseCircle,
  ScrollText,
  TriangleAlert,
  X,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import EmptyState from '@/components/ui/EmptyState.vue'
import ApiKeyRevealDialog from '@/components/ApiKeyRevealDialog.vue'
import StationAnimation from '@/components/StationAnimation.vue'
import HealthBadge from '@/components/HealthBadge.vue'
import RequestStatusBadge from '@/components/RequestStatusBadge.vue'
import ViewLogsSheet from '@/components/ViewLogsSheet.vue'
import type { Space, SpaceRequest } from '@/lib/types'
import { formatMoney } from '@/lib/types'
import { useStationStore } from '@/stores/station'
import { useSessionStore } from '@/stores/session'

const station = useStationStore()
const session = useSessionStore()

const myRequests = computed(() =>
  session.profile ? station.requestsFor(session.profile.email) : [],
)

const currency = computed(() => station.wallet?.currency ?? 'USD')

function spaceFor(request: SpaceRequest) {
  return request.spaceId ? station.spaceById(request.spaceId) : undefined
}

function earningsFor(request: SpaceRequest) {
  return station.memberEarnings?.spaces.find((row) => row.subdomain === request.subdomain)
}

const logsTarget = ref<Space | null>(null)
const logsOpen = ref(false)

function openLogs(request: SpaceRequest) {
  const space = spaceFor(request)
  if (!space) return
  logsTarget.value = space
  logsOpen.value = true
}

async function withdraw(request: SpaceRequest) {
  try {
    await station.withdrawRequest(request.id)
    toast('Request withdrawn', { description: request.spaceName })
  } catch {
    toast.error('Withdrawing the request failed')
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
      v-if="myRequests.length === 0"
      :icon="Inbox"
      title="No requests yet"
      description="Submit the form to request your first space on this station."
    />

    <Card v-for="request in myRequests" :key="request.id">
      <CardContent class="space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div class="font-medium">{{ request.spaceName }}</div>
            <div class="text-xs text-muted-foreground">
              {{ request.subdomain }}.{{ station.domain }} · requested
              {{ formatDate(request.createdAt) }}
            </div>
          </div>
          <div class="flex items-center gap-2">
            <HealthBadge
              v-if="request.status === 'active' && spaceFor(request)"
              :health="spaceFor(request)!.health"
            />
            <RequestStatusBadge v-else :status="request.status" />
          </div>
        </div>

        <p v-if="request.purpose" class="text-sm text-muted-foreground">
          {{ request.purpose }}
        </p>

        <!-- State-specific detail -->
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
          v-else-if="request.status === 'rejected' && request.rejectReason"
          class="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground"
        >
          <span class="font-medium text-foreground">Admin note:</span>
          {{ request.rejectReason }}
        </div>

        <div
          v-else-if="request.status === 'deleted'"
          class="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground"
        >
          This space was removed, along with its data.
        </div>

        <div
          v-else-if="request.status === 'failed'"
          class="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive"
        >
          Provisioning failed — the station admin has been notified and can retry.
        </div>

        <template v-else-if="request.status === 'active' && spaceFor(request)">
          <!-- Paused: URL is down but nothing is lost -->
          <div
            v-if="spaceFor(request)!.health === 'paused'"
            class="flex items-start gap-2 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground"
          >
            <PauseCircle class="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              The admin paused this space. Your data is safe, and it can be started again anytime.
            </span>
          </div>

          <div
            v-else-if="spaceFor(request)!.health === 'unhealthy'"
            class="flex flex-wrap items-center justify-between gap-2 rounded-md bg-warning/10 px-3 py-2 text-xs text-foreground"
          >
            <span class="flex items-start gap-2">
              <TriangleAlert class="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
              Your space is having trouble right now. The admin has been notified.
            </span>
            <Button size="sm" variant="outline" class="h-7 text-xs" @click="openLogs(request)">
              <ScrollText class="mr-1 h-3 w-3" />
              View logs
            </Button>
          </div>

          <div
            v-else
            class="flex flex-wrap items-center justify-between gap-2 rounded-md bg-success/10 px-3 py-2"
          >
            <a
              :href="spaceFor(request)!.url"
              target="_blank"
              rel="noopener"
              class="flex items-center gap-1.5 text-sm font-medium underline-offset-2 hover:underline"
            >
              {{ spaceFor(request)!.url.replace('https://', '') }}
              <ExternalLink class="h-3.5 w-3.5" />
            </a>
            <div class="flex items-center gap-2">
              <Button size="sm" variant="ghost" class="h-7 text-xs" @click="openLogs(request)">
                <ScrollText class="mr-1 h-3 w-3" />
                Logs
              </Button>
              <ApiKeyRevealDialog :space="spaceFor(request)!" />
            </div>
          </div>

          <!-- What this space earned (visible whenever it has paid queries) -->
          <p
            v-if="earningsFor(request)"
            class="flex items-center gap-1.5 text-xs text-muted-foreground"
          >
            <Banknote class="h-3.5 w-3.5" />
            Earned {{ formatMoney(earningsFor(request)!.earned, currency) }} from
            {{ earningsFor(request)!.query_count.toLocaleString() }} paid queries ·
            {{ formatMoney(earningsFor(request)!.paid_out, currency) }} paid out to you ·
            {{ formatMoney(earningsFor(request)!.payable, currency) }} owed
          </p>
        </template>
      </CardContent>
    </Card>
  </div>

  <ViewLogsSheet v-model:open="logsOpen" :space="logsTarget" />
</template>
