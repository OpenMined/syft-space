<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDocumentVisibility } from '@vueuse/core'
import { BarChart3, HandCoins, Wallet } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import AnalyticsPanel from '@/components/AnalyticsPanel.vue'
import PaymentSettings from '@/components/PaymentSettings.vue'
import PayoutsPanel from '@/components/PayoutsPanel.vue'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import MoneyEmptyState from '@/components/MoneyEmptyState.vue'
import { Skeleton } from '@/components/ui/skeleton'
import { useStationStore } from '@/stores/station'

const station = useStationStore()
const route = useRoute()
const router = useRouter()

/**
 * One destination for the money system, three views of it. The tab rides in
 * the URL (`/admin/earnings/payouts`) so it survives a refresh and the back
 * button moves between tabs, like the sections above it.
 */
const TABS = [
  { id: 'wallet', label: 'Wallet', icon: Wallet },
  { id: 'payouts', label: 'Payouts', icon: HandCoins },
  { id: 'analytics', label: 'Analytics', icon: BarChart3 },
] as const

type EarningsTab = (typeof TABS)[number]['id']
const DEFAULT_TAB: EarningsTab = 'wallet'

const activeTab = computed<EarningsTab>(() => {
  const tab = route.params.tab as EarningsTab | undefined
  return tab && TABS.some((t) => t.id === tab) ? tab : DEFAULT_TAB
})

function goTab(tab: string | number): void {
  router.push({ name: 'admin', params: { section: 'earnings', tab: String(tab) } })
}

/**
 * Refetch around the data that's already on screen rather than clearing it:
 * the panels keep rendering the last response while this resolves, so
 * switching tabs never flashes an empty state.
 */
function revalidate(): void {
  Promise.all([station.loadWallet(), station.loadEarnings()]).catch(() =>
    toast.error('Could not load earnings'),
  )
}

onMounted(revalidate)

// Money moves from other sessions — a member's space charges a query, a
// buyer tops up — so switching tabs refetches, mirroring the section-change
// watch in AdminPage. (The Wallet tab also reloads itself on mount.)
watch(activeTab, revalidate)

// A dashboard left open on a second monitor goes stale silently; coming back
// to it is the moment the numbers matter most.
const visibility = useDocumentVisibility()
watch(visibility, (state) => {
  if (state === 'visible') revalidate()
})

/** Money views are empty until someone has actually bought credits. */
const noMoneyYet = computed(() => station.topUps.length === 0)
</script>

<template>
  <Tabs :model-value="activeTab" class="gap-6" @update:model-value="goTab">
    <!-- Anchored: the tabs stay put while the panel below them changes, so a
         switch never moves the control you just clicked. z-20 keeps it over
         the tables' own sticky headers. -->
    <div class="sticky top-0 z-20 -mt-2 bg-background py-2">
      <TabsList>
        <TabsTrigger v-for="tab in TABS" :key="tab.id" :value="tab.id">
          <component :is="tab.icon" class="h-3.5 w-3.5" />
          {{ tab.label }}
        </TabsTrigger>
      </TabsList>
    </div>

    <TabsContent value="wallet">
      <PaymentSettings />
    </TabsContent>

    <TabsContent value="payouts">
      <Skeleton v-if="!station.earningsLoaded" class="h-64 w-full" />
      <MoneyEmptyState v-else-if="noMoneyYet" @set-up="goTab('wallet')" />
      <PayoutsPanel v-else />
    </TabsContent>

    <TabsContent value="analytics">
      <Skeleton v-if="!station.earningsLoaded" class="h-64 w-full" />
      <MoneyEmptyState v-else-if="noMoneyYet" @set-up="goTab('wallet')" />
      <AnalyticsPanel v-else />
    </TabsContent>
  </Tabs>
</template>
