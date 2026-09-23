<script setup lang="ts">
import { computed } from 'vue'
import HelpTip from '@/components/HelpTip.vue'
import TablePager from '@/components/TablePager.vue'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatMoney } from '@/lib/types'
import { formatDay } from '@/lib/types'
import { useStationStore } from '@/stores/station'

const station = useStationStore()

/** Fixed windows for now; a date range can replace this list later without
 *  touching the server, which already takes any day count. */
const RANGES = [
  { days: 7, label: 'Last 7 days' },
  { days: 14, label: 'Last 14 days' },
  { days: 30, label: 'Last 30 days' },
  { days: 90, label: 'Last 90 days' },
]

const chart = computed(() => {
  const days = station.earnedByDay(station.chartDays)
  const max = Math.max(...days.map((d) => d.total), 1)
  return days.map((d) => ({
    ...d,
    pct: Math.round((d.total / max) * 100),
    label: formatDay(d.date),
  }))
})
</script>

<template>
  <div class="space-y-8">
    <section class="space-y-2">
      <h2 class="text-sm font-medium">Earned by date</h2>
      <Select
        :model-value="String(station.chartDays)"
        @update:model-value="(v) => station.setChartDays(Number(v))"
      >
        <SelectTrigger size="sm" class="w-[9.5rem]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem v-for="range in RANGES" :key="range.days" :value="String(range.days)">
            {{ range.label }}
          </SelectItem>
        </SelectContent>
      </Select>
      <div class="rounded-lg border bg-card px-4 pt-4 pb-3">
        <div class="flex h-36 items-end" :class="station.chartDays > 30 ? 'gap-px' : 'gap-1.5'">
          <div
            v-for="day in chart"
            :key="day.date"
            class="group relative flex h-full flex-1 flex-col justify-end"
            :title="`${day.label}: ${formatMoney(day.total, station.currency)}`"
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
          {{ station.topUpPage.total }}
        </span>
      </h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Date</TableHead>
            <TableHead>User</TableHead>
            <TableHead>Bundle</TableHead>
            <TableHead class="text-right">Amount</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="t in station.topUps" :key="t.id">
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
      <TablePager :page="station.topUpPage" @go="(offset) => station.loadTopUps(offset)" />
    </section>

    <section class="space-y-2">
      <h2 class="text-sm font-medium">
        User credit
        <span class="ml-1 text-xs font-normal text-muted-foreground">
          {{ station.balancePage.total }}
        </span>
      </h2>
      <Table>
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
              {{ formatMoney(user.toppedUp, station.currency) }}
            </TableCell>
            <TableCell class="text-right tabular-nums text-muted-foreground">
              {{ formatMoney(user.spent, station.currency) }}
            </TableCell>
            <TableCell class="text-right font-medium tabular-nums">
              {{ formatMoney(user.balance, station.currency) }}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <TablePager :page="station.balancePage" @go="(offset) => station.loadBalances(offset)" />
    </section>
  </div>
</template>
