<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-8">
      <div class="flex items-center gap-3 mb-3">
        <Receipt class="h-6 w-6 text-primary" />
        <h1 class="heading-3">Earnings</h1>
      </div>
      <p class="body-lg text-muted-foreground">Invoices captured across your wallets</p>
    </div>

    <div class="space-y-6">
      <!-- Stat cards: Total Earned / Pending / Lost, per currency -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="Total Earned"
          :totals="earnedTotals"
          :count="paidCount"
          tone="emerald"
        />
        <StatCard
          title="Pending"
          :totals="pendingTotals"
          :count="pendingCount"
          tone="amber"
        />
        <StatCard title="Lost" :totals="lostTotals" :count="lostCount" tone="red" />
      </div>

      <!-- Filters -->
      <div class="flex flex-wrap items-center gap-3">
        <Select v-model="statusFilter">
          <SelectTrigger class="w-40">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="paid">Paid</SelectItem>
            <SelectItem value="expired">Expired</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
          </SelectContent>
        </Select>
        <Input
          v-model="emailFilter"
          placeholder="Filter by email..."
          class="h-9 max-w-sm flex-1"
        />
        <Button variant="outline" size="sm" @click="fetchInvoices" :disabled="loading">
          <Loader2 v-if="loading" class="h-4 w-4 mr-2 animate-spin" />
          Refresh
        </Button>
      </div>

      <!-- Invoices list -->
      <Card class="bg-card/80 backdrop-blur-sm border border-border shadow-sm">
        <CardContent class="p-0">
          <div v-if="loading" class="space-y-3 p-4">
            <Skeleton v-for="i in 5" :key="i" class="h-14 w-full" />
          </div>
          <div
            v-else-if="filteredInvoices.length === 0"
            class="text-center py-12 text-sm text-muted-foreground"
          >
            No invoices found
          </div>
          <div v-else class="divide-y divide-border">
            <div
              v-for="inv in filteredInvoices"
              :key="inv.id"
              class="flex items-center justify-between px-4 py-3"
            >
              <div class="min-w-0 flex-1">
                <p class="text-sm font-medium truncate">{{ inv.user_email }}</p>
                <p class="text-xs text-muted-foreground">
                  {{ inv.bundle_name }} &middot; {{ formatTimeAgo(inv.created_at) }}
                  <span v-if="inv.paid_at"> &middot; paid {{ formatTimeAgo(inv.paid_at) }}</span>
                </p>
              </div>
              <div class="flex items-center gap-3 ml-4">
                <Badge
                  variant="outline"
                  class="text-xs capitalize"
                  :class="{
                    'text-emerald-600 border-emerald-300': inv.status === 'paid',
                    'text-amber-600 border-amber-300': inv.status === 'pending',
                    'text-red-600 border-red-300':
                      inv.status === 'expired' || inv.status === 'failed',
                  }"
                >
                  {{ inv.status }}
                </Badge>
                <span class="text-sm font-semibold whitespace-nowrap">
                  {{ inv.amount.toLocaleString() }} {{ inv.currency }}
                </span>
                <a
                  v-if="inv.status === 'pending' && inv.checkout_url"
                  :href="inv.checkout_url"
                  target="_blank"
                  rel="noopener"
                  class="text-xs text-primary hover:underline inline-flex items-center gap-1"
                >
                  Checkout
                  <ExternalLink class="h-3 w-3" />
                </a>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import { Receipt, Loader2, ExternalLink } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { paymentsApi } from '@/api/endpoints/payments'
import type { InvoiceResponse } from '@/api/endpoints/payments'
import { formatTimeAgo } from '@/lib/formatters'

const loading = ref(false)
const invoices = ref<InvoiceResponse[]>([])
const statusFilter = ref<string>('all')
const emailFilter = ref('')

const filteredInvoices = computed(() => {
  let list = invoices.value
  if (statusFilter.value && statusFilter.value !== 'all') {
    list = list.filter((i) => i.status === statusFilter.value)
  }
  const email = emailFilter.value.toLowerCase().trim()
  if (email) {
    list = list.filter((i) => i.user_email.toLowerCase().includes(email))
  }
  return list
})

// Sum invoice amounts per currency, filtered by status set.
function sumByCurrency(statuses: string[]): { currency: string; amount: number }[] {
  const sums: Record<string, number> = {}
  for (const inv of invoices.value) {
    if (!statuses.includes(inv.status)) continue
    sums[inv.currency] = (sums[inv.currency] || 0) + inv.amount
  }
  return Object.entries(sums)
    .map(([currency, amount]) => ({ currency, amount }))
    .sort((a, b) => a.currency.localeCompare(b.currency))
}

const earnedTotals = computed(() => sumByCurrency(['paid']))
const pendingTotals = computed(() => sumByCurrency(['pending']))
const lostTotals = computed(() => sumByCurrency(['expired', 'failed']))

const paidCount = computed(() => invoices.value.filter((i) => i.status === 'paid').length)
const pendingCount = computed(
  () => invoices.value.filter((i) => i.status === 'pending').length,
)
const lostCount = computed(
  () => invoices.value.filter((i) => i.status === 'expired' || i.status === 'failed').length,
)

const fetchInvoices = async () => {
  loading.value = true
  try {
    invoices.value = await paymentsApi.listInvoices()
  } catch {
    invoices.value = []
  } finally {
    loading.value = false
  }
}

onMounted(fetchInvoices)

const TONE_CLASSES: Record<string, string> = {
  emerald: 'text-emerald-600 dark:text-emerald-400',
  amber: 'text-amber-600 dark:text-amber-400',
  red: 'text-red-600 dark:text-red-400',
}

const StatCard = (props: {
  title: string
  totals: { currency: string; amount: number }[]
  count: number
  tone: 'emerald' | 'amber' | 'red'
}) => {
  return h('div', { class: 'bg-card rounded-lg p-4 border border-border' }, [
    h(
      'p',
      { class: 'text-xs font-medium text-muted-foreground uppercase tracking-wide' },
      props.title,
    ),
    props.totals.length === 0
      ? h('p', { class: ['text-xl font-semibold mt-1', TONE_CLASSES[props.tone]] }, '—')
      : h(
          'div',
          { class: 'mt-1 space-y-0.5' },
          props.totals.map((t) =>
            h(
              'p',
              {
                class: ['text-xl font-semibold leading-tight', TONE_CLASSES[props.tone]],
              },
              `${t.amount.toLocaleString()} ${t.currency}`,
            ),
          ),
        ),
    h(
      'p',
      { class: 'text-xs text-muted-foreground mt-2' },
      `${props.count} invoice${props.count === 1 ? '' : 's'}`,
    ),
  ])
}
</script>
