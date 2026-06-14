<template>
  <div class="min-h-screen">
    <div class="relative overflow-hidden border-b border-border/50">
      <div class="absolute inset-0 -z-10 opacity-25 dark:opacity-15 blur-3xl" aria-hidden="true">
        <div class="absolute top-[-5%] left-[5%] h-80 w-80 rounded-full bg-primary/30" />
        <div class="absolute top-[10%] right-[10%] h-64 w-64 rounded-full bg-amber-400/20" />
      </div>

      <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-12">
        <Badge variant="secondary" class="mb-4">Collective host</Badge>
        <h1 class="text-4xl sm:text-5xl font-semibold tracking-tight text-foreground mb-4 leading-[1.1]">
          One system,
          <span
            class="bg-gradient-to-r from-primary via-amber-500 to-orange-400 bg-clip-text text-transparent"
          >
            many member spaces
          </span>
        </h1>
        <p class="text-lg text-muted-foreground max-w-xl leading-relaxed">
          You run the infrastructure. Members run virtual Syft Spaces on your system and query your
          collective APIs — one gateway, many contributors.
        </p>

        <div class="flex flex-wrap gap-3 mt-8">
          <Button size="lg" class="h-12" @click="router.push({ name: 'members' })">
            <UsersRound class="h-4 w-4 mr-2" />
            Members
          </Button>
          <Button variant="outline" size="lg" class="h-12" @click="router.push({ name: 'analytics' })">
            <BarChart3 class="h-4 w-4 mr-2" />
            Stats
          </Button>
        </div>
      </div>
    </div>

    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-10">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <button
          class="rounded-xl border border-border/50 bg-card p-4 text-left hover:border-border transition-colors"
          @click="router.push({ name: 'analytics' })"
        >
          <p class="text-xs text-muted-foreground mb-1">Total revenue</p>
          <p class="text-2xl font-semibold">{{ formatCurrency(collectiveStatsSummary.totalRevenue) }}</p>
        </button>
        <button
          class="rounded-xl border border-border/50 bg-card p-4 text-left hover:border-border transition-colors"
          @click="router.push({ name: 'analytics' })"
        >
          <p class="text-xs text-muted-foreground mb-1">This month</p>
          <p class="text-2xl font-semibold">
            {{ formatCurrency(collectiveStatsSummary.monthlyRevenue) }}
          </p>
        </button>
        <button
          class="rounded-xl border border-border/50 bg-card p-4 text-left hover:border-border transition-colors"
          @click="router.push({ name: 'members' })"
        >
          <p class="text-xs text-muted-foreground mb-1">Active members</p>
          <p class="text-2xl font-semibold">
            {{ collectiveStatsSummary.activeMembers }}/{{ collectiveStatsSummary.totalMembers }}
          </p>
        </button>
        <button
          class="rounded-xl border border-border/50 bg-card p-4 text-left hover:border-border transition-colors"
          @click="router.push({ name: 'analytics' })"
        >
          <p class="text-xs text-muted-foreground mb-1">Earning members</p>
          <p class="text-2xl font-semibold">
            {{ collectiveStatsSummary.earningMembers }}/{{ collectiveStatsSummary.totalMembers }}
          </p>
        </button>
      </div>

      <div class="rounded-xl border border-border/50 bg-card">
        <div class="flex items-center justify-between px-5 py-4 border-b border-border/50">
          <h2 class="text-sm font-semibold text-foreground">Collective APIs</h2>
          <button
            class="text-xs text-muted-foreground hover:text-foreground transition-colors"
            @click="router.push({ name: 'collective-apis' })"
          >
            View all
          </button>
        </div>
        <div class="divide-y divide-border/40">
          <div
            v-for="endpoint in collectiveApis"
            :key="endpoint.id"
            class="flex items-center gap-4 px-5 py-3.5"
          >
            <div class="h-9 w-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
              <Globe class="h-4 w-4 text-primary" />
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium truncate font-mono">{{ endpoint.name }}</p>
              <p class="text-xs text-muted-foreground truncate">{{ endpoint.detail }}</p>
            </div>
            <div class="text-right shrink-0">
              <p class="text-sm font-medium">{{ formatCurrency(endpoint.revenue) }}</p>
              <p class="text-[11px] text-muted-foreground">{{ formatNumber(endpoint.requests) }} req</p>
            </div>
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-border/50 bg-card">
        <div class="flex items-center justify-between px-5 py-4 border-b border-border/50">
          <h2 class="text-sm font-semibold text-foreground">Recent member activity</h2>
          <button
            class="text-xs text-muted-foreground hover:text-foreground transition-colors"
            @click="router.push({ name: 'members' })"
          >
            View all
          </button>
        </div>
        <div class="divide-y divide-border/40">
          <div
            v-for="member in recentMembers"
            :key="member.id"
            class="flex items-center gap-3 px-5 py-3.5"
          >
            <span
              class="h-2 w-2 rounded-full shrink-0"
              :class="member.status === 'Active' ? 'bg-green-500' : 'bg-muted-foreground'"
            />
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium truncate">{{ member.name }}</p>
              <p class="text-xs text-muted-foreground truncate">{{ member.email }}</p>
            </div>
            <span class="text-xs text-muted-foreground shrink-0">{{ member.lastActive }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { UsersRound, BarChart3, Globe } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  collectiveStatsSummary,
  collectiveMembers,
  collectiveApiStats,
} from '@/stores/mockCollective'

const router = useRouter()

const formatCurrency = (amount: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(amount)

const formatNumber = (value: number) => new Intl.NumberFormat('en-US').format(value)

const collectiveApis = collectiveApiStats

const recentMembers = computed(() => collectiveMembers.slice(0, 4))
</script>
