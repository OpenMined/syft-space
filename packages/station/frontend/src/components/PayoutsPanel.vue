<script setup lang="ts">
import { computed, ref } from 'vue'
import { HandCoins } from 'lucide-vue-next'
import RecordPayoutDialog from '@/components/RecordPayoutDialog.vue'
import HelpTip from '@/components/HelpTip.vue'
import StatStrip from '@/components/StatStrip.vue'
import TablePager from '@/components/TablePager.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatDay, formatMoney } from '@/lib/types'
import { useStationStore } from '@/stores/station'

const station = useStationStore()

const payoutOpen = ref(false)
const payoutTarget = ref<{
  spaceId: string
  slug: string
  spaceName: string
  ownerEmail: string
  payable: number
} | null>(null)

function openPayout(row: {
  spaceId: string
  slug: string
  spaceName: string
  ownerEmail: string
  payable: number
}) {
  payoutTarget.value = row
  payoutOpen.value = true
}

const stats = computed(() => [
  { label: 'Credits sold', value: formatMoney(station.totalCollected, station.currency) },
  {
    label: 'Earned by spaces',
    value: formatMoney(station.totalEarned, station.currency),
    hint: `${station.earnedBySpace.length} space${station.earnedBySpace.length === 1 ? '' : 's'}`,
  },
  {
    label: 'Owed to members',
    value: formatMoney(station.totalPayable, station.currency),
    accent: true,
  },
  { label: 'Unspent user credit', value: formatMoney(station.totalUserCredit, station.currency) },
])
</script>

<template>
  <div class="space-y-8">
    <StatStrip :stats="stats" />

    <section class="space-y-2">
      <h2 class="text-sm font-medium">
        Member payouts
        <span class="ml-1 text-xs font-normal text-muted-foreground">
          {{ station.spaceEarningsPage.total }}
        </span>
      </h2>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Space</TableHead>
            <TableHead class="text-right">Queries</TableHead>
            <TableHead class="text-right">Earned</TableHead>
            <TableHead class="text-right">Paid out</TableHead>
            <TableHead class="text-right">
              Payable
              <HelpTip>
                What users spent at this space, minus what you've already paid its owner.
              </HelpTip>
            </TableHead>
            <TableHead class="w-0" />
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="row in station.earnedBySpace" :key="row.slug">
            <TableCell>
              <span class="font-medium">{{ row.spaceName }}</span>
              <Badge v-if="row.deleted" variant="outline" class="ml-2 text-[11px]">deleted</Badge>
              <div class="text-xs text-muted-foreground">
                {{ row.ownerEmail }} · last active {{ formatDay(row.lastActiveAt) }}
              </div>
            </TableCell>
            <TableCell class="text-right tabular-nums text-muted-foreground">
              {{ row.queries.toLocaleString() }}
            </TableCell>
            <TableCell class="text-right tabular-nums text-muted-foreground">
              {{ formatMoney(row.earned, station.currency) }}
            </TableCell>
            <TableCell class="text-right tabular-nums text-muted-foreground">
              {{ row.paidOut > 0 ? formatMoney(row.paidOut, station.currency) : '—' }}
            </TableCell>
            <TableCell
              class="text-right font-medium tabular-nums"
              :class="row.payable > 0 ? '' : 'text-muted-foreground'"
            >
              {{ formatMoney(row.payable, station.currency) }}
            </TableCell>
            <TableCell class="text-right">
              <Button
                size="sm"
                variant="outline"
                :disabled="row.payable <= 0"
                @click="openPayout(row)"
              >
                <HandCoins class="mr-1.5 h-3.5 w-3.5" />
                Pay
              </Button>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <TablePager
        :page="station.spaceEarningsPage"
        @go="(offset) => station.loadSpaceEarnings(offset)"
      />
    </section>

    <section v-if="station.payouts.length > 0" class="space-y-2">
      <h2 class="text-sm font-medium">
        Payout history
        <span class="ml-1 text-xs font-normal text-muted-foreground">
          {{ station.payoutPage.total }}
        </span>
      </h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Date</TableHead>
            <TableHead>Space</TableHead>
            <TableHead>Note</TableHead>
            <TableHead class="text-right">Amount</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="payout in station.payouts" :key="payout.id">
            <TableCell class="whitespace-nowrap text-muted-foreground">
              {{ formatDay(payout.paidAt) }}
            </TableCell>
            <TableCell>
              {{ station.spaceById(payout.spaceId)?.name ?? 'Deleted space' }}
            </TableCell>
            <TableCell class="text-muted-foreground">{{ payout.note || '—' }}</TableCell>
            <TableCell class="text-right font-medium tabular-nums">
              {{ formatMoney(payout.amount, station.currency) }}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <TablePager :page="station.payoutPage" @go="(offset) => station.loadPayouts(offset)" />
    </section>
  </div>

  <RecordPayoutDialog
    v-model:open="payoutOpen"
    :target="payoutTarget"
    :currency="station.currency"
  />
</template>
