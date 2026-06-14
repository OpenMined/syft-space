<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
    <template v-if="isCollectiveViewActive">
      <div class="mb-12">
        <div class="flex items-center gap-3 mb-3">
          <Globe class="h-6 w-6 text-primary" />
          <h1 class="text-2xl font-semibold tracking-tight text-foreground">Collective APIs</h1>
        </div>
        <p class="body-lg text-muted-foreground md:max-w-[68%]">
          Collective APIs formed by APIs hosted by members of your collective. For changes, visit
          SyftHub Admin page for your collective.
        </p>
      </div>

      <div class="relative w-full max-w-sm mb-8">
        <Search
          class="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground"
        />
        <Input v-model="searchQuery" placeholder="Search collective APIs..." class="pl-10" />
      </div>

      <div v-if="filteredApis.length === 0" class="text-center py-12 text-muted-foreground">
        No collective APIs match "{{ searchQuery }}"
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="api in filteredApis"
          :key="api.id"
          class="bg-card border border-border rounded-xl p-5"
        >
          <div class="flex items-start gap-4">
            <div
              class="h-11 w-11 rounded-lg bg-primary/10 flex items-center justify-center shrink-0"
            >
              <Globe class="h-5 w-5 text-primary" />
            </div>
            <div class="flex-1 min-w-0">
              <h2 class="text-sm font-semibold text-foreground font-mono mb-1">{{ api.name }}</h2>
              <p class="text-sm text-muted-foreground">{{ api.detail }}</p>
            </div>
            <div class="text-right shrink-0">
              <p class="text-sm font-semibold">{{ formatCurrency(api.revenue) }}</p>
              <p class="text-xs text-muted-foreground">{{ formatNumber(api.requests) }} req</p>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="max-w-xl mx-auto text-center py-20">
      <Globe class="h-10 w-10 text-muted-foreground mx-auto mb-4" />
      <h1 class="text-2xl font-semibold tracking-tight text-foreground mb-3">Collective APIs</h1>
      <p class="text-muted-foreground">
        Collective APIs appear when Syft Space is booted in collective admin mode.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Globe, Search } from 'lucide-vue-next'
import { Input } from '@/components/ui/input'
import { useCollectiveMode } from '@/composables/useCollectiveMode'
import { collectiveApiStats } from '@/stores/mockCollective'

const { isCollectiveViewActive } = useCollectiveMode()
const searchQuery = ref('')

const filteredApis = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return collectiveApiStats
  return collectiveApiStats.filter(
    (api) => api.name.toLowerCase().includes(q) || api.detail.toLowerCase().includes(q),
  )
})

const formatCurrency = (amount: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(amount)

const formatNumber = (value: number) => new Intl.NumberFormat('en-US').format(value)
</script>
