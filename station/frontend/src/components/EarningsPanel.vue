<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Banknote,
  Coins,
  Copy,
  HandCoins,
  Pencil,
  TrendingUp,
  Wallet,
  Webhook,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import ConfigureWalletDialog from '@/components/ConfigureWalletDialog.vue'
import RecordPayoutDialog from '@/components/RecordPayoutDialog.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatMoney } from '@/lib/types'
import { useStationStore } from '@/stores/station'

const station = useStationStore()
const walletOpen = ref(false)

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

onMounted(() => {
  Promise.all([station.loadWallet(), station.loadEarnings()]).catch(() =>
    toast.error('Could not load earnings'),
  )
})

const CHART_DAYS = 14

/** Where the payment provider must deliver its events. */
const webhookUrl = computed(() => `${window.location.origin}/api/v1/credits/webhooks/xendit`)

function copyWebhookUrl() {
  navigator.clipboard.writeText(webhookUrl.value)
  toast('Webhook URL copied', {
    description: 'Paste it in the Xendit dashboard: Settings → Developers → Webhooks.',
  })
}

const chart = computed(() => {
  const days = station.earnedByDay(CHART_DAYS)
  const max = Math.max(...days.map((d) => d.total), 1)
  return days.map((d) => ({
    ...d,
    pct: Math.round((d.total / max) * 100),
    label: new Date(d.date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
  }))
})

const earningSpaceCount = computed(() => station.earnedBySpace.length)

const recentTopUps = computed(() => station.topUps.slice(0, 6))

const currency = computed(() => station.wallet?.currency ?? 'USD')

function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
</script>

<template>
  <div class="space-y-6">
    <!-- Wallet summary (the shared wallet is optional) -->
    <Card v-if="station.wallet">
      <CardContent class="flex flex-wrap items-center justify-between gap-3">
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <Wallet class="h-4 w-4 text-muted-foreground" />
            <span class="font-medium capitalize">{{ station.wallet.provider }}</span>
            <Badge variant="secondary">{{ station.wallet.currency }}</Badge>
            <Badge
              v-if="station.wallet.hubConnected"
              variant="secondary"
              title="The wallet holds a SyftHub API token and can verify buyers' sign-ins"
            >
              SyftHub connected
            </Badge>
            <Badge
              v-else
              variant="destructive"
              title="Buyers can't be verified — replace the wallet and connect SyftHub"
            >
              SyftHub not connected
            </Badge>
          </div>
          <button
            class="mt-1.5 flex items-center gap-1.5 text-xs text-muted-foreground underline-offset-2 hover:underline"
            title="Xendit delivers payment events here — set it under Settings → Developers → Webhooks"
            @click="copyWebhookUrl"
          >
            <Webhook class="h-3 w-3" />
            {{ webhookUrl }}
            <Copy class="h-3 w-3" />
          </button>
          <p class="mt-1 text-xs text-muted-foreground">
            Users buy credits at the first link; Xendit reports payments to the second (set it in
            the Xendit dashboard under Settings → Developers → Webhooks, with the callback token
            from the same page). The gateway key stays at the station.
          </p>
        </div>
        <Button size="sm" variant="outline" @click="walletOpen = true">
          <Pencil class="mr-1.5 h-3.5 w-3.5" />
          Replace
        </Button>
      </CardContent>
    </Card>

    <Card v-else>
      <CardContent class="flex flex-wrap items-center justify-between gap-3">
        <div class="min-w-0">
          <p class="flex items-center gap-2 text-sm font-medium">
            <Wallet class="h-4 w-4 text-muted-foreground" />
            No shared wallet — optional
          </p>
          <p class="mt-1 text-xs text-muted-foreground">
            Add one gateway account (Xendit or Stripe) to sell credits that work at every space —
            you collect the money and pay members for what users spend. Without it, spaces handle
            payments on their own. One shared wallet per station.
          </p>
        </div>
        <Button size="sm" @click="walletOpen = true">
          <Wallet class="mr-1.5 h-3.5 w-3.5" />
          Add shared wallet
        </Button>
      </CardContent>
    </Card>

    <template v-if="station.topUps.length > 0">
      <!-- Stat cards -->
      <div class="grid gap-3 sm:grid-cols-3">
        <Card>
          <CardContent>
            <p class="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Banknote class="h-3.5 w-3.5" />
              Credits sold
            </p>
            <p class="mt-1 text-2xl font-semibold tracking-tight">
              {{ formatMoney(station.totalCollected, currency) }}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <p class="flex items-center gap-1.5 text-xs text-muted-foreground">
              <TrendingUp class="h-3.5 w-3.5" />
              Earned by spaces
            </p>
            <p class="mt-1 text-2xl font-semibold tracking-tight">
              {{ formatMoney(station.totalEarned, currency) }}
              <span class="text-base font-normal text-muted-foreground">
                · {{ earningSpaceCount }} space{{ earningSpaceCount === 1 ? '' : 's' }}</span
              >
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <p class="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Coins class="h-3.5 w-3.5" />
              Unspent user credit
            </p>
            <p class="mt-1 text-2xl font-semibold tracking-tight">
              {{ formatMoney(station.totalUserCredit, currency) }}
            </p>
          </CardContent>
        </Card>
      </div>

      <!-- Earned by date -->
      <Card>
        <CardHeader>
          <CardTitle class="text-sm">Earned by date</CardTitle>
          <p class="text-xs text-muted-foreground">
            Daily query spend across all spaces, last {{ CHART_DAYS }} days.
          </p>
        </CardHeader>
        <CardContent>
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
        </CardContent>
      </Card>

      <!-- Earned by space (payout basis) -->
      <Card>
        <CardHeader>
          <CardTitle class="text-sm">Member payouts</CardTitle>
          <p class="text-xs text-muted-foreground">
            Payouts are based on what users actually spend at each space — per-query price ×
            queries. Record each payout you make so payable amounts stay accurate.
          </p>
        </CardHeader>
        <CardContent class="divide-y p-0">
          <div
            v-for="row in station.earnedBySpace"
            :key="row.slug"
            class="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
          >
            <div class="min-w-0">
              <span class="text-sm font-medium">{{ row.spaceName }}</span>
              <span class="ml-2 text-xs text-muted-foreground">{{ row.ownerEmail }}</span>
              <div class="mt-0.5 text-xs text-muted-foreground">
                {{ row.queries.toLocaleString() }} paid quer{{ row.queries === 1 ? 'y' : 'ies' }} ·
                last active {{ formatDay(row.lastActiveAt) }}
              </div>
            </div>
            <div class="flex shrink-0 items-center gap-4">
              <div class="text-right text-xs text-muted-foreground">
                <div>earned {{ formatMoney(row.earned, currency) }}</div>
                <div>paid out {{ formatMoney(row.paidOut, currency) }}</div>
              </div>
              <span
                class="w-20 text-right text-sm font-semibold tabular-nums"
                :class="row.payable > 0 ? '' : 'text-muted-foreground'"
              >
                {{ formatMoney(row.payable, currency) }}
              </span>
              <Button
                size="sm"
                variant="outline"
                :disabled="row.payable <= 0"
                @click="openPayout(row)"
              >
                <HandCoins class="mr-1.5 h-3.5 w-3.5" />
                Record payout
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Payout history -->
      <Card v-if="station.payouts.length > 0">
        <CardHeader>
          <CardTitle class="text-sm">Payout history</CardTitle>
        </CardHeader>
        <CardContent class="divide-y p-0">
          <div
            v-for="payout in station.payouts"
            :key="payout.id"
            class="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm"
          >
            <div class="min-w-0">
              <span class="font-medium tabular-nums">
                {{ formatMoney(payout.amount, currency) }}
              </span>
              <span class="text-muted-foreground">
                → {{ station.spaceById(payout.spaceId)?.name ?? 'Deleted space' }}</span
              >
              <span v-if="payout.note" class="text-xs text-muted-foreground">
                · {{ payout.note }}</span
              >
            </div>
            <span class="text-xs text-muted-foreground">{{ formatDay(payout.paidAt) }}</span>
          </div>
        </CardContent>
      </Card>

      <!-- User credit balances -->
      <Card>
        <CardHeader>
          <CardTitle class="text-sm">User credit</CardTitle>
          <p class="text-xs text-muted-foreground">
            Unspent credit is money the station holds for users — it isn't payable to members until
            it's spent on queries.
          </p>
        </CardHeader>
        <CardContent class="divide-y p-0">
          <div
            v-for="user in station.userBalances"
            :key="user.email"
            class="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm"
          >
            <span class="min-w-0 truncate">{{ user.email }}</span>
            <div class="flex items-center gap-4">
              <span class="text-xs text-muted-foreground">
                bought {{ formatMoney(user.toppedUp, currency) }} · spent
                {{ formatMoney(user.spent, currency) }}
              </span>
              <span class="w-16 text-right font-medium tabular-nums">
                {{ formatMoney(user.balance, currency) }}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Recent top-ups -->
      <Card>
        <CardHeader>
          <CardTitle class="text-sm">Recent top-ups</CardTitle>
          <p class="text-xs text-muted-foreground">
            Credits bought at the station checkout. The gateway notifies the station directly —
            spaces are never involved in payments.
          </p>
        </CardHeader>
        <CardContent class="divide-y p-0">
          <div
            v-for="t in recentTopUps"
            :key="t.id"
            class="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm"
          >
            <div class="min-w-0">
              <span class="font-medium tabular-nums">{{ formatMoney(t.amount, t.currency) }}</span>
              <span class="text-muted-foreground"> · {{ t.userEmail }}</span>
            </div>
            <span class="text-xs text-muted-foreground">{{ formatDay(t.paidAt) }}</span>
          </div>
        </CardContent>
      </Card>
    </template>
  </div>

  <ConfigureWalletDialog v-model:open="walletOpen" />
  <RecordPayoutDialog v-model:open="payoutOpen" :target="payoutTarget" :currency="currency" />
</template>
