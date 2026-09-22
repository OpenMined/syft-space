<script setup lang="ts">
import { computed } from 'vue'
import HelpTip from '@/components/HelpTip.vue'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatMoney } from '@/lib/types'
import { useStationStore } from '@/stores/station'

const station = useStationStore()

const CHART_DAYS = 14

const chart = computed(() => {
  const days = station.earnedByDay(CHART_DAYS)
  const max = Math.max(...days.map((d) => d.total), 1)
  return days.map((d) => ({
    ...d,
    pct: Math.round((d.total / max) * 100),
    label: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
  }))
})

const recentTopUps = computed(() => station.topUps)
const currency = computed(() => station.wallet?.currency ?? 'USD')

function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
</script>

<template>
  <div class="space-y-8">
    <section class="space-y-2">
      <h2 class="text-sm font-medium">Earned by date · last {{ CHART_DAYS }} days</h2>
      <div class="rounded-lg border bg-card px-4 pt-4 pb-3">
        <div class="flex h-36 items-end gap-1.5">
          <div
            v-for="day in chart"
            :key="day.date"
            class="group relative flex h-full flex-1 flex-col justify-end"
            :title="`${day.label}: ${formatMoney(day.total, currency)}`"
          >
            <div
              class="rounded-t bg-primary/80 transition-colors group-hover:bg-primary"
              :style="{ height: `${day.pct}%`, minHeight: day.total > 0 ? '4px' : '1px' }"
            />
          </div>
        </div>
        <div class="mt-1.5 flex justify-between text-[10px] text-muted-foreground">
          <span>{{ chart[0]?.label }}</span>
          <span>{{ chart[chart.length - 1]?.label }}</span>
        </div>
      </div>
    </section>

    <section class="space-y-2">
      <h2 class="text-sm font-medium">
        Top-ups
        <span class="ml-1 text-xs font-normal text-muted-foreground">
          {{ station.topUps.length }}
        </span>
      </h2>
      <Table max-height="18rem">
        <TableHeader>
          <TableRow>
            <TableHead>Date</TableHead>
            <TableHead>User</TableHead>
            <TableHead>Bundle</TableHead>
            <TableHead class="text-right">Amount</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="t in recentTopUps" :key="t.id">
            <TableCell class="whitespace-nowrap text-muted-foreground">
              {{ formatDay(t.paidAt) }}
            </TableCell>
            <TableCell>{{ t.userEmail }}</TableCell>
            <TableCell class="text-muted-foreground">{{ t.bundleName }}</TableCell>
            <TableCell class="text-right font-medium tabular-nums">
              {{ formatMoney(t.amount, t.currency) }}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </section>

    <section class="space-y-2">
      <h2 class="text-sm font-medium">
        User credit
        <span class="ml-1 text-xs font-normal text-muted-foreground">
          {{ station.userBalances.length }}
        </span>
      </h2>
      <Table max-height="18rem">
        <TableHeader>
          <TableRow>
            <TableHead>User</TableHead>
            <TableHead class="text-right">Bought</TableHead>
            <TableHead class="text-right">Spent</TableHead>
            <TableHead class="text-right">
              Unspent
              <HelpTip>
                Money the station holds for this user. It isn't payable to members until it's spent
                on queries.
              </HelpTip>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="user in station.userBalances" :key="user.email">
            <TableCell class="truncate">{{ user.email }}</TableCell>
            <TableCell class="text-right tabular-nums text-muted-foreground">
              {{ formatMoney(user.toppedUp, currency) }}
            </TableCell>
            <TableCell class="text-right tabular-nums text-muted-foreground">
              {{ formatMoney(user.spent, currency) }}
            </TableCell>
            <TableCell class="text-right font-medium tabular-nums">
              {{ formatMoney(user.balance, currency) }}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </section>
  </div>
</template>
