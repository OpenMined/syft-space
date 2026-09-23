<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Loader2, Wallet, X } from 'lucide-vue-next'
import HelpTip from '@/components/HelpTip.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useWalletAttachRun } from '@/composables/useWalletAttachRun'
import type { Space } from '@/lib/types'
import { useStationStore } from '@/stores/station'

const station = useStationStore()
const { progress, running, run } = useWalletAttachRun()

/** Why a space can't go on the wallet right now, or null if it can. */
type Blocker = 'paused' | 'uncreated'

const BLOCKER_COPY: Record<Blocker, string> = {
  // Converge applies one replica, so attaching would silently un-pause it.
  paused: 'Resume this space first',
  uncreated: "This space hasn't been created yet",
}

function blockerFor(space: Space): Blocker | null {
  if (!space.url) return 'uncreated'
  if (space.health === 'paused') return 'paused'
  return null
}

/** What one row shows on its right-hand side — a live run beats stored state. */
type RowView =
  | { kind: 'queued' }
  | { kind: 'attaching' }
  | { kind: 'failed'; detail: string }
  | { kind: 'attached' }
  | { kind: 'stale'; message: string }
  | { kind: 'blocked'; reason: string; declined: boolean }
  | { kind: 'ready'; declined: boolean }

function viewFor(space: Space): RowView {
  const state = progress.value[space.id]
  if (state) {
    return state.state === 'failed'
      ? { kind: 'failed', detail: state.detail ?? '' }
      : { kind: state.state }
  }
  const blocker = blockerFor(space)
  if (space.walletStatus === 'attached') {
    // On the wallet, but carrying facts the wallet has since changed. Only a
    // re-apply rewrites them — a restart re-reads the same Secret.
    const stale = space.conditions.find((c) => c.type === 'wallet_stale')
    if (!stale) return { kind: 'attached' }
    return blocker
      ? { kind: 'blocked', reason: BLOCKER_COPY[blocker], declined: false }
      : { kind: 'stale', message: stale.message }
  }
  const declined = space.walletStatus === 'declined'
  return blocker
    ? { kind: 'blocked', reason: BLOCKER_COPY[blocker], declined }
    : { kind: 'ready', declined }
}

/**
 * Three groups, because they answer three different questions: what needs
 * doing, what can't be done yet, and what's already fine. A row in a live
 * run stays in `action` so its progress doesn't jump between groups.
 */
type Group = 'action' | 'blocked' | 'current'

function groupOf(view: RowView): Group {
  if (view.kind === 'attached') return 'current'
  if (view.kind === 'blocked') return 'blocked'
  return 'action'
}

const rows = computed(() =>
  [...station.provisionedSpaces]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((space) => ({ space, view: viewFor(space) })),
)

const groups = computed(() => {
  const by: Record<Group, { space: Space; view: RowView }[]> = {
    action: [],
    blocked: [],
    current: [],
  }
  for (const row of rows.value) by[groupOf(row.view)].push(row)
  return by
})

const attachedCount = computed(
  () => station.provisionedSpaces.filter((s) => s.walletStatus === 'attached').length,
)

// Selection is tracked as exclusions, so a space flagged while the admin is
// looking joins the selection instead of being silently left out.
const excluded = ref(new Set<string>())
const confirmOpen = ref(false)

const selectedSpaces = computed(() =>
  groups.value.action
    .filter(({ space, view }) => !excluded.value.has(space.id) && isPickable(view))
    .map(({ space }) => space),
)

/** Rows the admin can still choose — not ones mid-run. */
function isPickable(view: RowView): boolean {
  return view.kind === 'ready' || view.kind === 'stale' || view.kind === 'failed'
}

const pickable = computed(() => groups.value.action.filter((r) => isPickable(r.view)))
const allStale = computed(
  () =>
    selectedSpaces.value.length > 0 &&
    selectedSpaces.value.every((s) => viewFor(s).kind === 'stale'),
)

const allSelected = computed<boolean | 'indeterminate'>(() => {
  if (selectedSpaces.value.length === 0) return false
  return selectedSpaces.value.length === pickable.value.length ? true : 'indeterminate'
})

function toggleAll(value: boolean | 'indeterminate'): void {
  excluded.value = value === true ? new Set() : new Set(pickable.value.map(({ space }) => space.id))
}

function toggleOne(space: Space, value: boolean | 'indeterminate'): void {
  const next = new Set(excluded.value)
  if (value === true) next.delete(space.id)
  else next.add(space.id)
  excluded.value = next
}

// Default to the work, not the inventory: a station with 30 healthy spaces
// opens on "nothing to do" rather than 30 rows.
const filter = ref<'attention' | 'all' | null>(null)
const needsAttention = computed(() => groups.value.action.length + groups.value.blocked.length)
const activeFilter = computed<'attention' | 'all'>(
  () => filter.value ?? (needsAttention.value > 0 ? 'attention' : 'all'),
)

const visibleRows = computed(() =>
  activeFilter.value === 'all'
    ? [...groups.value.action, ...groups.value.blocked, ...groups.value.current]
    : [...groups.value.action, ...groups.value.blocked],
)

watch(running, (isRunning) => {
  if (isRunning) filter.value = 'attention' // keep the run in view
})

const confirmTitle = computed(() => {
  // The wallet row below names it, so the title stays a plain question.
  const count = selectedSpaces.value.length
  const noun = `${count} space${count === 1 ? '' : 's'}`
  return allStale.value ? `Re-apply the wallet to ${noun}?` : `Attach ${noun}?`
})

async function runAttach(): Promise<void> {
  confirmOpen.value = false
  const targets = selectedSpaces.value
  await run(targets)
  // Anything that failed stays selected, so a retry is one click.
  excluded.value = new Set(
    targets.filter((s) => progress.value[s.id]?.state !== 'failed').map((s) => s.id),
  )
}
</script>

<template>
  <section class="space-y-2">
    <div class="flex flex-wrap items-baseline justify-between gap-2">
      <h2 class="flex items-center gap-2 text-sm font-medium">
        Spaces on this wallet
        <Badge variant="secondary"
          >{{ attachedCount }} of {{ station.provisionedSpaces.length }}</Badge
        >
      </h2>
      <p class="text-xs text-muted-foreground">
        A space earns only once it's on the wallet.
        <HelpTip>
          Each attached space carries a copy of the wallet's price list, injected when it was last
          applied. Re-apply a space whenever that copy falls behind.
        </HelpTip>
      </p>
    </div>

    <Skeleton v-if="!station.spacesLoaded" class="h-40 w-full" />

    <div
      v-else-if="station.provisionedSpaces.length === 0"
      class="rounded-lg border bg-card px-4 py-3 text-sm text-muted-foreground"
    >
      No spaces yet.
    </div>

    <template v-else>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex items-center gap-1">
          <Button
            size="sm"
            :variant="activeFilter === 'attention' ? 'secondary' : 'ghost'"
            @click="filter = 'attention'"
          >
            Needs attention
            <Badge variant="outline" class="ml-1.5 px-1.5">{{ needsAttention }}</Badge>
          </Button>
          <Button
            size="sm"
            :variant="activeFilter === 'all' ? 'secondary' : 'ghost'"
            @click="filter = 'all'"
          >
            All {{ station.provisionedSpaces.length }}
          </Button>
        </div>

        <Button
          v-if="pickable.length > 0"
          size="sm"
          :disabled="running || selectedSpaces.length === 0"
          @click="confirmOpen = true"
        >
          <Loader2 v-if="running" class="mr-1.5 h-3.5 w-3.5 animate-spin" />
          <Wallet v-else class="mr-1.5 h-3.5 w-3.5" />
          {{ running ? 'Updating…' : allStale ? 'Re-apply wallet' : 'Attach to wallet' }}
          {{ selectedSpaces.length > 0 ? `(${selectedSpaces.length})` : '' }}
        </Button>
      </div>

      <Table max-height="26rem">
        <TableHeader>
          <TableRow>
            <TableHead class="w-0">
              <Checkbox
                v-if="pickable.length > 0"
                :model-value="allSelected"
                :disabled="running"
                aria-label="Select all"
                @update:model-value="toggleAll"
              />
            </TableHead>
            <TableHead>Space</TableHead>
            <TableHead>Owner</TableHead>
            <TableHead class="text-right">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="visibleRows.length === 0">
            <TableCell colspan="4" class="py-6 text-center text-sm text-muted-foreground">
              Nothing needs attention — every space is on this wallet and up to date.
            </TableCell>
          </TableRow>
          <TableRow
            v-for="{ space, view } in visibleRows"
            :key="space.id"
            :data-state="!excluded.has(space.id) && isPickable(view) ? 'selected' : undefined"
          >
            <TableCell>
              <Checkbox
                v-if="isPickable(view)"
                :model-value="!excluded.has(space.id)"
                :disabled="running"
                :aria-label="`Select ${space.name}`"
                @update:model-value="(v) => toggleOne(space, v)"
              />
            </TableCell>
            <TableCell class="font-medium">{{ space.name }}</TableCell>
            <TableCell class="text-muted-foreground">{{ space.ownerEmail }}</TableCell>
            <TableCell class="text-right text-xs">
              <span v-if="view.kind === 'attached'" class="text-muted-foreground">
                On this wallet
              </span>
              <span v-else-if="view.kind === 'queued'" class="text-muted-foreground">Queued</span>
              <span
                v-else-if="view.kind === 'attaching'"
                class="inline-flex items-center gap-1.5 text-muted-foreground"
              >
                <Loader2 class="h-3 w-3 animate-spin" />
                Attaching…
              </span>
              <span
                v-else-if="view.kind === 'failed'"
                class="inline-flex items-center gap-1.5 text-destructive"
                :title="view.detail"
              >
                <X class="h-3 w-3" />
                Failed
              </span>
              <!-- Tint the surface, keep foreground text: gold-600 on a light
                   card is 2.08:1. Same treatment as HealthBadge. -->
              <Badge
                v-else-if="view.kind === 'stale'"
                variant="outline"
                class="border-warning/40 bg-warning/15 px-1.5 py-0 font-normal text-foreground"
                :title="view.message"
              >
                Out of date
              </Badge>
              <span v-else-if="view.kind === 'blocked'" class="text-muted-foreground">
                {{ view.reason }}
              </span>
              <span v-else class="text-muted-foreground">
                {{ view.declined ? 'Unbilled by choice' : 'Not on this wallet' }}
              </span>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </template>
  </section>

  <Dialog :open="confirmOpen" @update:open="(v: boolean) => (confirmOpen = v)">
    <DialogContent>
      <DialogHeader>
        <DialogTitle>{{ confirmTitle }}</DialogTitle>
        <DialogDescription>
          {{ selectedSpaces.length === 1 ? 'It restarts' : 'Each one restarts, in turn' }} to pick
          up the wallet — about a minute of downtime, cutting off requests in flight and any running
          ingestion. No data is lost.
        </DialogDescription>
      </DialogHeader>

      <div
        v-if="station.wallet"
        class="flex flex-wrap items-center gap-3 rounded-lg border bg-card px-4 py-3 text-sm"
      >
        <span class="flex w-32 shrink-0 items-center gap-1.5 text-muted-foreground">
          Wallet
          <HelpTip>
            Attaching injects the wallet's credentials and its price list into the space, so its
            endpoints can charge against station credits. The gateway key stays at the station — the
            space never sees it.
          </HelpTip>
        </span>
        <span class="flex min-w-0 flex-1 items-center gap-2">
          <span class="font-medium capitalize">{{ station.wallet.provider }}</span>
          <Badge variant="secondary">{{ station.wallet.currency }}</Badge>
        </span>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="confirmOpen = false">Cancel</Button>
        <Button @click="runAttach">Attach and restart</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
