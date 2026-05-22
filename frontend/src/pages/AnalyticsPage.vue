<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-6">
      <div class="flex items-center justify-between">
        <div>
          <div class="flex items-center gap-3 mb-2">
            <BarChart3 class="h-6 w-6 text-primary" />
            <h1 class="heading-3">Analytics</h1>
          </div>
          <p class="body-lg text-muted-foreground">
            Comprehensive analytics across your endpoints, users, and revenue
          </p>
        </div>
        <TooltipProvider v-if="activeTab === 'overview'">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                variant="outline"
                :disabled="!store.hasData"
                class="gap-2"
                @click="store.exportData()"
              >
                <Download class="h-4 w-4" />
                Export All Data
              </Button>
            </TooltipTrigger>
            <TooltipContent v-if="!store.hasData">No data to export</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>

    <!-- Page Tabs -->
    <Tabs v-model="activeTab">
      <TabsList
        class="h-auto w-full justify-start rounded-none border-b border-border bg-transparent p-0 mb-6"
      >
        <TabsTrigger
          value="overview"
          class="h-auto flex-none gap-2 rounded-none border-0 border-b-2 border-b-transparent px-4 pb-3 pt-2 text-sm font-medium text-muted-foreground hover:text-foreground data-[state=active]:border-b-primary data-[state=active]:bg-transparent data-[state=active]:!text-primary data-[state=active]:shadow-none dark:data-[state=active]:bg-transparent"
        >
          <BarChart3 class="h-4 w-4" />
          Overview
        </TabsTrigger>
        <TabsTrigger
          value="earnings"
          class="h-auto flex-none gap-2 rounded-none border-0 border-b-2 border-b-transparent px-4 pb-3 pt-2 text-sm font-medium text-muted-foreground hover:text-foreground data-[state=active]:border-b-primary data-[state=active]:bg-transparent data-[state=active]:!text-primary data-[state=active]:shadow-none dark:data-[state=active]:bg-transparent"
        >
          <Receipt class="h-4 w-4" />
          Earnings
        </TabsTrigger>
      </TabsList>

      <!-- ─── Overview Tab ─────────────────────────────────────────────────── -->
      <TabsContent value="overview" class="space-y-4">
        <!-- Filters -->
        <Card>
          <CardContent class="px-6 py-4">
            <div class="flex flex-wrap items-center gap-x-6 gap-y-3">
              <div class="flex items-center gap-2 text-sm font-medium text-foreground">
                <Filter class="h-4 w-4" />
                Filters
              </div>
              <div class="flex flex-wrap items-center gap-4">
                <div class="flex items-center gap-2">
                  <span class="text-sm text-muted-foreground">Time Range:</span>
                  <Select v-model="store.timeRange">
                    <SelectTrigger class="w-[150px] h-9">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem
                        v-for="opt in timeRangeOptions"
                        :key="opt.value"
                        :value="opt.value"
                      >
                        {{ opt.label }}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-sm text-muted-foreground">Endpoint:</span>
                  <Select v-model="selectedEndpointId">
                    <SelectTrigger class="w-[170px] h-9">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem :value="ALL_SENTINEL">All Endpoints</SelectItem>
                      <SelectItem v-for="ep in endpointsList" :key="ep.id" :value="ep.id">
                        {{ ep.name }}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <!-- Stat Cards -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <template v-if="store.summaryLoading">
            <Card v-for="i in 4" :key="`stat-skeleton-${i}`">
              <CardContent class="p-5">
                <div class="animate-pulse">
                  <div class="h-3 bg-muted rounded w-1/2 mb-4" />
                  <div class="h-8 bg-muted rounded w-2/3 mb-2" />
                  <div class="h-3 bg-muted rounded w-3/4" />
                </div>
              </CardContent>
            </Card>
          </template>
          <template v-else-if="store.summaryError">
            <Card class="col-span-full">
              <CardContent class="p-5 text-center">
                <p class="text-destructive mb-2">{{ store.summaryError }}</p>
                <Button variant="outline" size="sm" @click="store.fetchSummary()">Retry</Button>
              </CardContent>
            </Card>
          </template>
          <template v-else>
            <Card
              v-for="stat in statCards"
              :key="stat.label"
              class="transition-shadow hover:shadow-md"
            >
              <CardContent class="p-5">
                <div class="flex items-center justify-between mb-3">
                  <p class="text-sm font-medium text-muted-foreground">{{ stat.label }}</p>
                  <div
                    class="w-8 h-8 rounded-lg flex items-center justify-center"
                    :class="stat.iconBg"
                  >
                    <component :is="stat.iconComponent" class="w-4 h-4" :class="stat.iconFg" />
                  </div>
                </div>
                <template v-if="'breakdown' in stat && stat.breakdown.length > 0">
                  <div
                    class="tabular-nums tracking-tight space-y-0.5"
                    :class="
                      stat.breakdown.length === 1 ? 'text-3xl font-bold' : 'text-xl font-bold'
                    "
                  >
                    <p v-for="row in stat.breakdown" :key="row.currency" class="text-foreground">
                      {{ formatCurrencyAmount(row.amount, row.currency) }}
                    </p>
                  </div>
                  <TooltipProvider v-if="stat.overflowRows.length > 0" :delay-duration="100">
                    <Tooltip>
                      <TooltipTrigger as-child>
                        <p class="text-xs text-muted-foreground mt-0.5 cursor-default">
                          +{{ stat.overflowRows.length }} more
                        </p>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p
                          v-for="row in stat.overflowRows"
                          :key="row.currency"
                          class="tabular-nums"
                        >
                          {{ formatCurrencyAmount(row.amount, row.currency) }}
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </template>
                <p v-else class="text-3xl font-bold text-foreground tracking-tight tabular-nums">
                  {{ stat.formattedValue }}
                </p>
                <p
                  v-if="stat.changeLabel"
                  class="text-xs mt-1.5"
                  :class="
                    stat.changePositive
                      ? 'text-green-600 dark:text-green-400'
                      : 'text-muted-foreground'
                  "
                >
                  {{ stat.changeLabel }}
                </p>
              </CardContent>
            </Card>
          </template>
        </div>

        <!-- Charts Row 1 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <!-- Query Volume Trends -->
          <Card class="transition-shadow hover:shadow-md">
            <CardContent class="p-5">
              <div class="flex items-center gap-2 mb-0.5">
                <TrendingUp class="h-4 w-4 text-muted-foreground" />
                <span class="text-sm font-semibold text-foreground">Query Volume Trends</span>
              </div>
              <p class="text-xs text-muted-foreground mb-5">Query count over time</p>
              <div class="h-52">
                <template v-if="store.timeSeriesLoading">
                  <div class="animate-pulse h-full bg-muted rounded" />
                </template>
                <template v-else-if="store.timeSeriesError">
                  <div class="flex items-center justify-center h-full">
                    <div class="text-center">
                      <p class="text-sm text-destructive mb-2">Failed to load chart</p>
                      <Button variant="outline" size="sm" @click="store.fetchTimeSeries()">
                        Retry
                      </Button>
                    </div>
                  </div>
                </template>
                <template v-else-if="isQueryVolumeEmpty">
                  <div class="flex items-center justify-center h-full">
                    <p class="text-sm text-muted-foreground">No query data for this period</p>
                  </div>
                </template>
                <template v-else>
                  <Line :data="queryVolumeChartData" :options="lineChartOptions" />
                </template>
              </div>
            </CardContent>
          </Card>

          <!-- User Activity -->
          <Card class="transition-shadow hover:shadow-md">
            <CardContent class="p-5">
              <div class="flex items-center gap-2 mb-0.5">
                <UsersRound class="h-4 w-4 text-muted-foreground" />
                <span class="text-sm font-semibold text-foreground">User Activity</span>
              </div>
              <p class="text-xs text-muted-foreground mb-5">Distinct active users</p>
              <div class="h-52">
                <template v-if="store.timeSeriesLoading">
                  <div class="animate-pulse h-full bg-muted rounded" />
                </template>
                <template v-else-if="store.timeSeriesError">
                  <div class="flex items-center justify-center h-full">
                    <div class="text-center">
                      <p class="text-sm text-destructive mb-2">Failed to load chart</p>
                      <Button variant="outline" size="sm" @click="store.fetchTimeSeries()">
                        Retry
                      </Button>
                    </div>
                  </div>
                </template>
                <template v-else-if="isUserActivityEmpty">
                  <div class="flex items-center justify-center h-full">
                    <p class="text-sm text-muted-foreground">No activity data for this period</p>
                  </div>
                </template>
                <template v-else>
                  <Bar :data="userActivityChartData" :options="barChartOptions" />
                </template>
              </div>
            </CardContent>
          </Card>
        </div>

        <!-- Charts Row 2 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <!-- Revenue Overview -->
          <Card class="transition-shadow hover:shadow-md">
            <CardContent class="p-5">
              <div class="flex items-center gap-2 mb-0.5">
                <DollarSign class="h-4 w-4 text-muted-foreground" />
                <span class="text-sm font-semibold text-foreground">Revenue Overview</span>
              </div>
              <p class="text-xs text-muted-foreground mb-5">Revenue over time</p>
              <div class="h-52">
                <template v-if="store.timeSeriesLoading">
                  <div class="animate-pulse h-full bg-muted rounded" />
                </template>
                <template v-else-if="store.timeSeriesError">
                  <div class="flex items-center justify-center h-full">
                    <div class="text-center">
                      <p class="text-sm text-destructive mb-2">Failed to load chart</p>
                      <Button variant="outline" size="sm" @click="store.fetchTimeSeries()">
                        Retry
                      </Button>
                    </div>
                  </div>
                </template>
                <template v-else-if="isRevenueEmpty">
                  <div class="flex items-center justify-center h-full">
                    <p class="text-sm text-muted-foreground">No revenue data for this period</p>
                  </div>
                </template>
                <template v-else>
                  <Line :data="revenueChartData" :options="revenueChartOptions" />
                </template>
              </div>
            </CardContent>
          </Card>

          <!-- Most Active Users -->
          <Card class="transition-shadow hover:shadow-md">
            <CardContent class="p-5">
              <div class="flex items-center gap-2 mb-0.5">
                <Heart class="h-4 w-4 text-muted-foreground" />
                <span class="text-sm font-semibold text-foreground">Most Active Users</span>
              </div>
              <p class="text-xs text-muted-foreground mb-4">Top users by query volume</p>
              <template v-if="store.topUsersLoading">
                <div class="space-y-3">
                  <div
                    v-for="i in 5"
                    :key="`user-skeleton-${i}`"
                    class="animate-pulse flex items-center gap-3 px-3 py-2.5"
                  >
                    <div class="w-6 h-6 rounded-full bg-muted shrink-0" />
                    <div class="flex-1">
                      <div class="h-3 bg-muted rounded w-1/3 mb-2" />
                      <div class="h-1.5 bg-muted rounded w-full" />
                    </div>
                  </div>
                </div>
              </template>
              <template v-else-if="store.topUsersError">
                <div class="text-center py-4">
                  <p class="text-sm text-destructive mb-2">{{ store.topUsersError }}</p>
                  <Button variant="outline" size="sm" @click="store.fetchTopUsers()">Retry</Button>
                </div>
              </template>
              <template v-else-if="!activeUsers.length">
                <div class="text-center py-8">
                  <p class="text-sm text-muted-foreground">No user activity for this period</p>
                </div>
              </template>
              <template v-else>
                <div class="space-y-3">
                  <div
                    v-for="(user, idx) in activeUsers"
                    :key="user.user_email"
                    class="flex items-center gap-3 rounded-lg px-3 py-2.5 -mx-1 transition-colors hover:bg-muted/50"
                  >
                    <span
                      class="w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center shrink-0"
                      :class="
                        idx === 0 ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground'
                      "
                    >
                      {{ idx + 1 }}
                    </span>
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center justify-between">
                        <p class="text-sm font-medium text-foreground truncate">
                          {{ user.user_email }}
                        </p>
                        <span class="text-sm font-semibold text-foreground tabular-nums">
                          {{ formatCurrencyBreakdown(user.revenue, '—') }}
                        </span>
                      </div>
                      <div class="flex items-center gap-2 mt-1">
                        <div class="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                          <div
                            class="h-full rounded-full transition-all"
                            :class="idx === 0 ? 'bg-primary' : 'bg-primary/40'"
                            :style="{
                              width: `${(user.query_count / (activeUsers[0]?.query_count ?? 1)) * 100}%`,
                            }"
                          />
                        </div>
                        <span class="text-xs text-muted-foreground tabular-nums shrink-0">
                          {{ user.query_count.toLocaleString() }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </CardContent>
          </Card>
        </div>

        <!-- Most Queried Topics (full width) -->
        <Card class="transition-shadow hover:shadow-md">
          <CardContent class="p-5">
            <div class="flex items-center justify-between mb-4">
              <div>
                <div class="flex items-center gap-2 mb-0.5">
                  <Search class="h-4 w-4 text-muted-foreground" />
                  <span class="text-sm font-semibold text-foreground">Most Queried Topics</span>
                </div>
                <p class="text-xs text-muted-foreground">Top query topics across all endpoints</p>
              </div>
              <Select v-model="selectedNgramSize">
                <SelectTrigger class="w-[160px] h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">Single words</SelectItem>
                  <SelectItem value="2">Two-word phrases</SelectItem>
                  <SelectItem value="3">Three-word phrases</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <template v-if="store.wordCloudLoading">
              <div class="space-y-3">
                <div
                  v-for="i in 5"
                  :key="`topic-skeleton-${i}`"
                  class="animate-pulse flex items-center gap-3 px-3 py-2.5"
                >
                  <div class="w-6 h-6 rounded-full bg-muted shrink-0" />
                  <div class="flex-1">
                    <div class="h-3 bg-muted rounded w-1/3 mb-2" />
                    <div class="h-1.5 bg-muted rounded w-full" />
                  </div>
                </div>
              </div>
            </template>
            <template v-else-if="store.wordCloudError">
              <div class="text-center py-4">
                <p class="text-sm text-destructive mb-2">{{ store.wordCloudError }}</p>
                <Button variant="outline" size="sm" @click="store.fetchWordCloud()">Retry</Button>
              </div>
            </template>
            <template v-else-if="!wordCloudWords.length">
              <div class="text-center py-8">
                <p class="text-sm text-muted-foreground">No query data for this period</p>
              </div>
            </template>
            <template v-else>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-x-6">
                <div
                  v-for="(entry, idx) in wordCloudWords"
                  :key="entry.word"
                  class="flex items-center gap-3 rounded-lg px-3 py-2.5 -mx-1 transition-colors hover:bg-muted/50"
                >
                  <span
                    class="w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center shrink-0"
                    :class="
                      idx < 3 ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground'
                    "
                  >
                    {{ idx + 1 }}
                  </span>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between">
                      <p class="text-sm font-medium text-foreground truncate">{{ entry.word }}</p>
                      <span
                        class="text-sm font-semibold text-foreground tabular-nums shrink-0 ml-2"
                      >
                        {{ entry.count.toLocaleString() }}
                      </span>
                    </div>
                    <div class="mt-1 h-1.5 rounded-full bg-muted overflow-hidden">
                      <div
                        class="h-full rounded-full transition-all"
                        :class="idx < 3 ? 'bg-primary/70' : 'bg-primary/35'"
                        :style="{
                          width: `${(entry.count / (wordCloudWords[0]?.count ?? 1)) * 100}%`,
                        }"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </CardContent>
        </Card>
      </TabsContent>

      <!-- ─── Earnings Tab ──────────────────────────────────────────────────── -->
      <TabsContent value="earnings" class="space-y-6">
        <!-- No-wallets empty state -->
        <div
          v-if="!walletsLoading && wallets.length === 0"
          class="flex flex-col items-center justify-center py-20 text-center"
        >
          <div
            class="w-12 h-12 rounded-xl bg-muted border border-border flex items-center justify-center mb-4"
          >
            <Receipt class="h-5 w-5 text-muted-foreground" />
          </div>
          <p class="text-sm font-semibold text-foreground mb-1">No payment wallets configured</p>
          <p class="text-sm text-muted-foreground">Add a wallet to start tracking earnings.</p>
        </div>

        <template v-else>
          <!-- Wallet selector + Refresh -->
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div class="flex items-center gap-3">
              <span class="text-sm font-medium text-muted-foreground">Wallet</span>
              <Select v-model="selectedWalletId" :disabled="walletsLoading">
                <SelectTrigger class="w-72">
                  <SelectValue placeholder="Select a wallet" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem v-for="w in wallets" :key="w.id" :value="w.id">
                    {{ w.name }} · {{ w.currency }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              variant="outline"
              size="sm"
              class="gap-2"
              :disabled="invoicesLoading"
              @click="fetchInvoices"
            >
              <Loader2 v-if="invoicesLoading" class="h-4 w-4 animate-spin" />
              <RefreshCw v-else class="h-4 w-4" />
              Refresh
            </Button>
          </div>

          <!-- Earnings stat cards -->
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <!-- Total Earned -->
            <Card class="transition-shadow hover:shadow-md">
              <CardContent class="p-5">
                <div class="flex items-center justify-between mb-3">
                  <p class="text-sm font-medium text-muted-foreground">Total Earned</p>
                  <div
                    class="w-8 h-8 rounded-lg flex items-center justify-center bg-emerald-500/10 dark:bg-emerald-400/10"
                  >
                    <DollarSign class="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                  </div>
                </div>
                <div v-if="earnedTotals.length === 0">
                  <p class="text-3xl font-bold text-foreground tracking-tight">—</p>
                </div>
                <div v-else class="space-y-0.5">
                  <p
                    v-for="t in earnedTotals"
                    :key="t.currency"
                    class="text-2xl font-bold text-foreground tracking-tight tabular-nums"
                  >
                    {{ t.amount.toLocaleString() }} {{ t.currency }}
                  </p>
                </div>
                <p class="text-xs text-muted-foreground mt-1.5">
                  {{ paidCount }} paid invoice{{ paidCount === 1 ? '' : 's' }}
                </p>
              </CardContent>
            </Card>

            <!-- Pending -->
            <Card class="transition-shadow hover:shadow-md">
              <CardContent class="p-5">
                <div class="flex items-center justify-between mb-3">
                  <p class="text-sm font-medium text-muted-foreground">Pending</p>
                  <div
                    class="w-8 h-8 rounded-lg flex items-center justify-center bg-amber-500/10 dark:bg-amber-400/10"
                  >
                    <Clock class="w-4 h-4 text-amber-600 dark:text-amber-400" />
                  </div>
                </div>
                <p class="text-3xl font-bold text-foreground tracking-tight tabular-nums">
                  {{ pendingCount }}
                </p>
                <p class="text-xs text-muted-foreground mt-1.5">
                  invoice{{ pendingCount === 1 ? '' : 's' }} awaiting payment
                </p>
              </CardContent>
            </Card>

            <!-- Expired -->
            <Card class="transition-shadow hover:shadow-md">
              <CardContent class="p-5">
                <div class="flex items-center justify-between mb-3">
                  <p class="text-sm font-medium text-muted-foreground">Expired</p>
                  <div
                    class="w-8 h-8 rounded-lg flex items-center justify-center bg-red-500/10 dark:bg-red-400/10"
                  >
                    <AlertCircle class="w-4 h-4 text-red-600 dark:text-red-400" />
                  </div>
                </div>
                <p class="text-3xl font-bold text-foreground tracking-tight tabular-nums">
                  {{ expiredCount }}
                </p>
                <p class="text-xs text-muted-foreground mt-1.5">
                  invoice{{ expiredCount === 1 ? '' : 's' }} expired or cancelled
                </p>
              </CardContent>
            </Card>
          </div>

          <!-- Invoice filters -->
          <div class="flex flex-wrap items-center gap-3">
            <Select v-model="statusFilter">
              <SelectTrigger class="w-40 h-9">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="paid">Paid</SelectItem>
                <SelectItem value="expired">Expired</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>
            <Input
              v-model="emailFilter"
              placeholder="Filter by email..."
              class="h-9 max-w-sm flex-1"
            />
          </div>

          <!-- Invoice list -->
          <Card class="transition-shadow hover:shadow-md">
            <CardContent class="p-0">
              <div v-if="invoicesLoading" class="space-y-3 p-4">
                <Skeleton v-for="i in 5" :key="i" class="h-14 w-full" />
              </div>
              <div
                v-else-if="filteredInvoices.length === 0"
                class="flex items-center justify-center py-14"
              >
                <p class="text-sm text-muted-foreground">No invoices found</p>
              </div>
              <div v-else class="divide-y divide-border">
                <div
                  v-for="inv in filteredInvoices"
                  :key="inv.id"
                  class="flex items-center justify-between px-4 py-3 transition-colors hover:bg-muted/30"
                >
                  <div class="min-w-0 flex-1">
                    <p class="text-sm font-medium truncate">{{ inv.user_email }}</p>
                    <p class="text-xs text-muted-foreground">
                      {{ inv.bundle_name }} · {{ formatTimeAgo(inv.created_at) }}
                      <span v-if="inv.paid_at"> · paid {{ formatTimeAgo(inv.paid_at) }} </span>
                    </p>
                  </div>
                  <div class="flex items-center gap-3 ml-4">
                    <Badge
                      variant="outline"
                      class="text-xs capitalize"
                      :class="{
                        'text-emerald-600 border-emerald-300 dark:border-emerald-700':
                          inv.status === 'paid',
                        'text-amber-600 border-amber-300 dark:border-amber-700':
                          inv.status === 'pending',
                        'text-red-600 border-red-300 dark:border-red-700':
                          inv.status === 'expired' || inv.status === 'cancelled',
                      }"
                    >
                      {{ inv.status }}
                    </Badge>
                    <span class="text-sm font-semibold whitespace-nowrap tabular-nums">
                      {{ inv.amount.toLocaleString() }} {{ inv.currency }}
                    </span>
                    <a
                      v-if="inv.status === 'pending' && inv.checkout_url"
                      :href="inv.checkout_url"
                      target="_blank"
                      rel="noopener"
                      class="text-xs text-primary hover:underline inline-flex items-center gap-1 whitespace-nowrap"
                    >
                      Checkout
                      <ExternalLink class="h-3 w-3" />
                    </a>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </template>
      </TabsContent>
    </Tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, markRaw, onMounted, ref, watch } from 'vue'
import {
  Activity,
  AlertCircle,
  BarChart3,
  CheckCircle,
  Clock,
  DollarSign,
  Download,
  ExternalLink,
  Filter,
  Heart,
  Loader2,
  Receipt,
  RefreshCw,
  Search,
  TrendingUp,
  Users,
  UsersRound,
} from 'lucide-vue-next'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Filler,
  Tooltip as ChartTooltip,
  type TooltipItem,
} from 'chart.js'
import { Line, Bar } from 'vue-chartjs'
import { toast } from 'vue-sonner'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { paymentsApi } from '@/api/endpoints/payments'
import type { InvoiceResponse } from '@/api/endpoints/payments'
import { walletsApi } from '@/api/endpoints/wallets'
import { useAnalyticsStore } from '@/stores/analytics'
import {
  formatCompactNumber,
  formatCurrencyAmount,
  formatCurrencyBreakdown,
  formatTimeAgo,
} from '@/lib/formatters'
import type { TimeRange } from '@/api/types/analytics'
import type { EndpointListItem, WalletListItem } from '@/api/types'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Filler,
  ChartTooltip,
)

// ── Tab state ──────────────────────────────────────────────────────────────
const activeTab = ref('overview')

// ── Analytics store ────────────────────────────────────────────────────────
const store = useAnalyticsStore()

const icons = {
  checkCircle: markRaw(CheckCircle),
  activity: markRaw(Activity),
  dollarSign: markRaw(DollarSign),
  users: markRaw(Users),
}

// ── Analytics filters ──────────────────────────────────────────────────────
const timeRangeOptions: { value: TimeRange; label: string }[] = [
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: '90d', label: 'Last 90 days' },
  { value: '1y', label: 'Last year' },
]

const endpointsList = ref<EndpointListItem[]>([])
const ALL_SENTINEL = '__all__'

const selectedEndpointId = computed({
  get: () => store.endpointId ?? ALL_SENTINEL,
  set: (v: string) => {
    store.endpointId = v === ALL_SENTINEL ? undefined : v
  },
})

watch(
  () => store.filters,
  () => store.fetchAll(),
  { immediate: true },
)

onMounted(async () => {
  try {
    endpointsList.value = await endpointsApi.list()
  } catch {
    // Silently ignore — dropdown will just show "All Endpoints"
  }
  fetchWallets()
})

// ── Analytics stat cards ───────────────────────────────────────────────────
const simpleStatCardMeta = [
  {
    key: 'active_endpoints' as const,
    label: 'Active Endpoints',
    iconComponent: icons.checkCircle,
    iconBg: 'bg-green-500/10 dark:bg-green-400/10',
    iconFg: 'text-green-600 dark:text-green-400',
    format: formatCompactNumber,
    alwaysPositive: true,
    formatChange: (change: number) => `+${change} this period`,
  },
  {
    key: 'total_queries' as const,
    label: 'Total Queries',
    iconComponent: icons.activity,
    iconBg: 'bg-blue-500/10 dark:bg-blue-400/10',
    iconFg: 'text-blue-600 dark:text-blue-400',
    format: formatCompactNumber,
    alwaysPositive: true,
    formatChange: (change: number) =>
      `${change >= 0 ? '+' : ''}${change.toFixed(1)}% from last period`,
  },
  {
    key: 'active_users' as const,
    label: 'Active Users',
    iconComponent: icons.users,
    iconBg: 'bg-muted',
    iconFg: 'text-muted-foreground',
    format: formatCompactNumber,
    alwaysPositive: false,
    formatChange: () => store.timeRange,
  },
] as const

const revenueCardMeta = {
  label: 'Revenue',
  iconComponent: icons.dollarSign,
  iconBg: 'bg-emerald-500/10 dark:bg-emerald-400/10',
  iconFg: 'text-emerald-600 dark:text-emerald-400',
} as const

// Stacking limit before we hide the tail behind a "+N more" indicator
// — keeps the KPI card aligned with siblings even when many currencies exist.
const REVENUE_ROW_LIMIT = 3

const statCards = computed(() => {
  const s = store.summary

  const renderSimple = (meta: (typeof simpleStatCardMeta)[number]) => {
    const card = s?.[meta.key]
    return {
      label: meta.label,
      formattedValue: card ? meta.format(card.value) : '0',
      changeLabel: card ? meta.formatChange(card.change_value) : '--',
      changePositive: meta.alwaysPositive && (card?.change_value ?? 0) > 0,
      iconComponent: meta.iconComponent,
      iconBg: meta.iconBg,
      iconFg: meta.iconFg,
    }
  }

  const revenueCard = s?.total_revenue
  const breakdown = revenueCard?.breakdown ?? []
  const visibleRows = breakdown.slice(0, REVENUE_ROW_LIMIT)
  const overflowRows = breakdown.slice(REVENUE_ROW_LIMIT)
  const revenue = {
    label: revenueCardMeta.label,
    breakdown: visibleRows,
    overflowRows,
    formattedValue: breakdown.length ? '' : '$0.00',
    changeLabel: '',
    changePositive: false,
    iconComponent: revenueCardMeta.iconComponent,
    iconBg: revenueCardMeta.iconBg,
    iconFg: revenueCardMeta.iconFg,
  }

  const [endpointsMeta, queriesMeta, usersMeta] = simpleStatCardMeta
  return [renderSimple(endpointsMeta), renderSimple(queriesMeta), revenue, renderSimple(usersMeta)]
})

// ── Charts ─────────────────────────────────────────────────────────────────
const sharedScaleOptions = {
  grid: { color: 'rgba(0,0,0,0.04)' },
  ticks: { color: '#9ca3af', font: { size: 11 } },
  border: { display: false },
}

const lineChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { enabled: true } },
  scales: {
    x: sharedScaleOptions,
    y: {
      ...sharedScaleOptions,
      ticks: {
        ...sharedScaleOptions.ticks,
        callback: (v: string | number) => `${Number(v).toLocaleString()}`,
      },
    },
  },
}

const barChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { enabled: true } },
  scales: {
    x: sharedScaleOptions,
    y: { ...sharedScaleOptions, beginAtZero: true },
  },
}

const CURRENCY_COLORS: Record<string, string> = {
  USD: '#10b981',
  IDR: '#3b82f6',
  EUR: '#f59e0b',
  GBP: '#a855f7',
}
const PALETTE = ['#10b981', '#3b82f6', '#f59e0b', '#a855f7', '#ef4444', '#06b6d4']
const colorForCurrency = (currency: string, idx: number): string =>
  CURRENCY_COLORS[currency] ?? PALETTE[idx % PALETTE.length] ?? '#10b981'

const revenueChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: (store.timeSeries?.revenue.length ?? 0) > 1,
      position: 'top' as const,
      labels: { color: '#9ca3af', font: { size: 11 }, boxWidth: 12 },
    },
    tooltip: {
      enabled: true,
      callbacks: {
        label: (ctx: TooltipItem<'line'>) => {
          const code = ctx.dataset.label ?? 'USD'
          return formatCurrencyAmount(ctx.parsed.y ?? 0, code)
        },
      },
    },
  },
  scales: {
    x: sharedScaleOptions,
    y: {
      ...sharedScaleOptions,
      ticks: {
        ...sharedScaleOptions.ticks,
        callback: (v: string | number) => formatCompactNumber(Number(v)),
      },
    },
  },
}))

const queryVolumeChartData = computed(() => ({
  labels: store.timeSeries?.query_volume.map((p) => p.label) ?? [],
  datasets: [
    {
      data: store.timeSeries?.query_volume.map((p) => p.value) ?? [],
      borderColor: '#10b981',
      backgroundColor: 'rgba(16, 185, 129, 0.08)',
      borderWidth: 2,
      pointRadius: 4,
      pointBackgroundColor: '#10b981',
      tension: 0.3,
      fill: true,
    },
  ],
}))

const userActivityChartData = computed(() => ({
  labels: store.timeSeries?.user_activity.map((p) => p.label) ?? [],
  datasets: [
    {
      data: store.timeSeries?.user_activity.map((p) => p.value) ?? [],
      backgroundColor: '#2dd4bf',
      borderRadius: 6,
      barPercentage: 0.55,
    },
  ],
}))

// One Chart.js dataset per currency, all sharing the x-axis labels from
// query_volume (the backend gap-fills every CurrencySeries against the same
// bucket sequence so the points line up).
const revenueChartData = computed(() => {
  const series = store.timeSeries?.revenue ?? []
  const labels = store.timeSeries?.query_volume.map((p) => p.label) ?? []
  return {
    labels,
    datasets: series.map((s, idx) => {
      const color = colorForCurrency(s.currency, idx)
      return {
        label: s.currency,
        data: s.points.map((p) => p.value),
        borderColor: color,
        // Fill only when there's a single line — overlapping fills get
        // muddy with multiple currencies.
        backgroundColor: series.length === 1 ? `${color}1f` : 'transparent',
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.4,
        fill: series.length === 1,
      }
    }),
  }
})

const isQueryVolumeEmpty = computed(() => !store.timeSeries?.query_volume.some((p) => p.value > 0))
const isUserActivityEmpty = computed(
  () => !store.timeSeries?.user_activity.some((p) => p.value > 0),
)
const isRevenueEmpty = computed(() => {
  const series = store.timeSeries?.revenue ?? []
  if (series.length === 0) return true
  return !series.some((s) => s.points.some((p) => p.value > 0))
})

const activeUsers = computed(() => store.topUsers?.users ?? [])
const wordCloudWords = computed(() => store.wordCloud?.words ?? [])

const selectedNgramSize = computed({
  get: () => String(store.ngramSize),
  set: (v: string) => {
    store.ngramSize = Number(v)
    store.fetchWordCloud()
  },
})

// ── Earnings state ─────────────────────────────────────────────────────────
const wallets = ref<WalletListItem[]>([])
const walletsLoading = ref(false)
const selectedWalletId = ref<string>('')
const invoicesLoading = ref(false)
const invoices = ref<InvoiceResponse[]>([])
const statusFilter = ref<string>('all')
const emailFilter = ref('')

// Stat cards reflect the email filter but not the status filter — otherwise
// filtering to e.g. "Paid" trivially makes Pending and Expired cards show 0.
const emailScopedInvoices = computed(() => {
  const email = emailFilter.value.toLowerCase().trim()
  if (!email) return invoices.value
  return invoices.value.filter((i) => i.user_email.toLowerCase().includes(email))
})

const filteredInvoices = computed(() => {
  let list = emailScopedInvoices.value
  if (statusFilter.value && statusFilter.value !== 'all') {
    list = list.filter((i) => i.status === statusFilter.value)
  }
  return list
})

function sumByCurrency(statuses: string[]): { currency: string; amount: number }[] {
  const sums: Record<string, number> = {}
  for (const inv of emailScopedInvoices.value) {
    if (!statuses.includes(inv.status)) continue
    sums[inv.currency] = (sums[inv.currency] || 0) + inv.amount
  }
  return Object.entries(sums)
    .map(([currency, amount]) => ({ currency, amount }))
    .sort((a, b) => a.currency.localeCompare(b.currency))
}

const earnedTotals = computed(() => sumByCurrency(['paid']))
const paidCount = computed(
  () => emailScopedInvoices.value.filter((i) => i.status === 'paid').length,
)
const pendingCount = computed(
  () => emailScopedInvoices.value.filter((i) => i.status === 'pending').length,
)
const expiredCount = computed(
  () =>
    emailScopedInvoices.value.filter((i) => i.status === 'expired' || i.status === 'cancelled')
      .length,
)

const fetchWallets = async () => {
  walletsLoading.value = true
  try {
    const all = await walletsApi.list()
    // MPP wallets use on-chain transactions, not invoices — exclude them.
    wallets.value = all.filter((w) => w.wallet_type !== 'mpp')
    const first = wallets.value[0]
    if (first && !selectedWalletId.value) {
      selectedWalletId.value = first.id
    }
  } catch (e) {
    wallets.value = []
    toast.error(e instanceof Error ? e.message : 'Failed to load wallets')
  } finally {
    walletsLoading.value = false
  }
}

const fetchInvoices = async () => {
  if (!selectedWalletId.value) {
    invoices.value = []
    return
  }
  invoicesLoading.value = true
  try {
    invoices.value = await paymentsApi.getInvoicesByWallet(selectedWalletId.value)
  } catch (e) {
    invoices.value = []
    toast.error(e instanceof Error ? e.message : 'Failed to load invoices')
  } finally {
    invoicesLoading.value = false
  }
}

// Selecting the default wallet inside fetchWallets triggers this watcher,
// which fetches invoices — no explicit second call needed.
watch(selectedWalletId, () => {
  fetchInvoices()
})
</script>
