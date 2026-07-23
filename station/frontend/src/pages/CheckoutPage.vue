<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Coins, ExternalLink, ShoppingCart } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { ApiError } from '@/api/client'
import { creditsApi } from '@/api/endpoints/credits'
import type { MyCreditsResponse } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatMoney } from '@/lib/types'
import { useSessionStore } from '@/stores/session'
import { useStationStore } from '@/stores/station'

/**
 * The station checkout: buy credits once, spend them at any space. This is
 * the page the admin's shareable link points at; any signed-in user can buy.
 */
const station = useStationStore()
const session = useSessionStore()
const router = useRouter()

const me = ref<MyCreditsResponse | null>(null)
const loading = ref(true)
const buying = ref<string | null>(null)

onMounted(async () => {
  try {
    await Promise.all([station.loadWallet(), creditsApi.me().then((data) => (me.value = data))])
  } catch {
    toast.error('Could not load the checkout')
  } finally {
    loading.value = false
  }
})

const currency = computed(() => station.wallet?.currency ?? me.value?.currency ?? '')

async function buy(bundleName: string) {
  buying.value = bundleName
  try {
    const checkout = await creditsApi.checkout(bundleName)
    // Off to the provider-hosted payment page; credits land on the webhook.
    window.location.href = checkout.checkout_url
  } catch (error) {
    toast.error(error instanceof ApiError ? error.message : 'Could not start the checkout')
    buying.value = null
  }
}

function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function home() {
  router.push({ name: session.isAdmin ? 'admin' : 'member' })
}
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden bg-background">
    <AppHeader />
    <main class="min-w-0 flex-1 overflow-y-auto">
      <div class="mx-auto w-full max-w-2xl px-6 py-8">
        <Button variant="ghost" size="sm" class="mb-4 -ml-2" @click="home">
          <ArrowLeft class="mr-1.5 h-3.5 w-3.5" />
          Back to dashboard
        </Button>

        <h1 class="text-xl font-semibold tracking-tight">Buy credits</h1>
        <p class="mt-1 text-sm text-muted-foreground">
          Credits are prepaid and work at every space on this station — spend them on paid queries
          wherever you go.
        </p>

        <!-- Balance -->
        <Card class="mt-6">
          <CardContent class="flex items-center justify-between">
            <p class="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Coins class="h-3.5 w-3.5" />
              Your balance
            </p>
            <p class="text-2xl font-semibold tracking-tight tabular-nums">
              {{ me ? formatMoney(me.balance, currency || 'USD') : '—' }}
            </p>
          </CardContent>
        </Card>

        <!-- Bundles -->
        <template v-if="station.wallet">
          <div class="mt-6 grid gap-3 sm:grid-cols-2">
            <Card v-for="bundle in station.wallet.bundles" :key="bundle.name">
              <CardContent class="flex flex-col gap-3">
                <div class="flex items-center justify-between">
                  <span class="text-sm font-medium">{{ bundle.name }}</span>
                  <Badge variant="secondary">{{ currency }}</Badge>
                </div>
                <p class="text-2xl font-semibold tracking-tight">
                  {{ formatMoney(bundle.amount, currency) }}
                </p>
                <Button :disabled="buying !== null" @click="buy(bundle.name)">
                  <ShoppingCart class="mr-1.5 h-4 w-4" />
                  {{ buying === bundle.name ? 'Redirecting…' : 'Buy' }}
                  <ExternalLink class="ml-1.5 h-3 w-3 opacity-60" />
                </Button>
              </CardContent>
            </Card>
          </div>
          <p class="mt-2 text-xs text-muted-foreground">
            Payment happens on the provider's secure page; your balance updates as soon as the
            payment is confirmed.
          </p>
        </template>

        <Card v-else-if="!loading" class="mt-6">
          <CardContent>
            <p class="text-sm text-muted-foreground">
              This station doesn't sell credits yet — ask the station admin to set up the shared
              wallet.
            </p>
          </CardContent>
        </Card>

        <!-- History -->
        <template v-if="me && (me.top_ups.length > 0 || me.spend.length > 0)">
          <Card v-if="me.top_ups.length > 0" class="mt-6">
            <CardHeader>
              <CardTitle class="text-sm">Your purchases</CardTitle>
            </CardHeader>
            <CardContent class="divide-y p-0">
              <div
                v-for="t in me.top_ups"
                :key="t.invoice_id"
                class="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm"
              >
                <div class="min-w-0">
                  <span class="font-medium tabular-nums">
                    {{ formatMoney(t.amount, t.currency) }}
                  </span>
                  <span class="text-muted-foreground"> · {{ t.bundle_name }}</span>
                  <Badge
                    v-if="t.status !== 'paid'"
                    variant="outline"
                    class="ml-2 px-1.5 py-0 text-[11px] font-normal capitalize"
                  >
                    {{ t.status }}
                  </Badge>
                </div>
                <span class="text-xs text-muted-foreground">{{ formatDay(t.created_at) }}</span>
              </div>
            </CardContent>
          </Card>

          <Card v-if="me.spend.length > 0" class="mt-6">
            <CardHeader>
              <CardTitle class="text-sm">Your spend</CardTitle>
              <p class="text-xs text-muted-foreground">
                Paid queries across the station's spaces; refunds appear as cancelled.
              </p>
            </CardHeader>
            <CardContent class="divide-y p-0">
              <div
                v-for="entry in me.spend"
                :key="`${entry.transaction_id}-${entry.type}`"
                class="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm"
              >
                <div class="min-w-0">
                  <span
                    class="font-medium tabular-nums"
                    :class="entry.type === 'cancelled' ? 'text-success' : ''"
                  >
                    {{ entry.type === 'cancelled' ? '+' : '−'
                    }}{{ formatMoney(entry.amount, currency || 'USD') }}
                  </span>
                  <span class="text-muted-foreground">
                    · {{ entry.endpoint || 'query' }}
                    <template v-if="entry.type === 'cancelled'"> (refunded)</template>
                  </span>
                </div>
                <span class="text-xs text-muted-foreground">{{ formatDay(entry.created_at) }}</span>
              </div>
            </CardContent>
          </Card>
        </template>
      </div>
    </main>
  </div>
</template>
