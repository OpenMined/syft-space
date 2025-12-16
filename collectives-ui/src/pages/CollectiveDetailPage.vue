<template>
  <div v-if="collective" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-8">
      <Button variant="ghost" @click="$router.push('/collectives')" class="mb-4">
        <ArrowLeft class="h-4 w-4 mr-2" />
        Back to Collectives
      </Button>
      
      <div class="flex items-start justify-between">
        <div class="flex items-center gap-4">
          <div class="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
            <Users class="h-8 w-8 text-primary" />
          </div>
          <div>
            <h1 class="heading-2 text-foreground">{{ collective.name }}</h1>
            <p class="text-muted-foreground">{{ collective.domain }}</p>
          </div>
        </div>
        <Badge :variant="collective.role === 'admin' ? 'default' : 'secondary'">
          {{ collective.role }}
        </Badge>
      </div>
    </div>

    <!-- Tabs -->
    <Tabs v-model="activeTab" class="w-full">
      <TabsList class="grid w-full" :class="collective.role === 'admin' ? 'grid-cols-5' : 'grid-cols-4'">
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="members">Members</TabsTrigger>
        <TabsTrigger value="analytics">Analytics</TabsTrigger>
        <TabsTrigger value="terms">Collective Terms</TabsTrigger>
        <TabsTrigger value="settings" v-if="collective.role === 'admin'">Settings</TabsTrigger>
      </TabsList>

      <!-- Overview Tab -->
      <TabsContent value="overview" class="mt-6 space-y-6">
        <!-- About -->
        <Card>
          <CardHeader>
            <CardTitle>About</CardTitle>
          </CardHeader>
          <CardContent>
            <p class="text-muted-foreground">{{ collective.description }}</p>
          </CardContent>
        </Card>

        <!-- Capabilities -->
        <Card>
          <CardHeader>
            <CardTitle>Collective Capabilities</CardTitle>
            <CardDescription>Features enabled for this collective</CardDescription>
          </CardHeader>
          <CardContent>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div
                class="flex items-start gap-3 p-4 rounded-lg"
                :class="
                  collective.capabilities.collectiveEndpoint
                    ? 'bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800'
                    : 'bg-muted border border-border'
                "
              >
                <Zap
                  class="h-5 w-5 mt-0.5"
                  :class="
                    collective.capabilities.collectiveEndpoint
                      ? 'text-green-600 dark:text-green-400'
                      : 'text-muted-foreground'
                  "
                />
                <div>
                  <p class="font-medium text-foreground">Collective Endpoint</p>
                  <p class="text-sm text-muted-foreground">
                    {{
                      collective.capabilities.collectiveEndpoint
                        ? 'Enabled - unified query endpoint active'
                        : 'Disabled'
                    }}
                  </p>
                </div>
              </div>

              <div
                class="flex items-start gap-3 p-4 rounded-lg"
                :class="
                  collective.capabilities.multiTenancyHosting
                    ? 'bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800'
                    : 'bg-muted border border-border'
                "
              >
                <Server
                  class="h-5 w-5 mt-0.5"
                  :class="
                    collective.capabilities.multiTenancyHosting
                      ? 'text-green-600 dark:text-green-400'
                      : 'text-muted-foreground'
                  "
                />
                <div>
                  <p class="font-medium text-foreground">Multi-Tenancy Hosting</p>
                  <p class="text-sm text-muted-foreground">
                    {{
                      collective.capabilities.multiTenancyHosting
                        ? 'Enabled - subdomain hosting available'
                        : 'Disabled'
                    }}
                  </p>
                </div>
              </div>

              <div
                class="flex items-start gap-3 p-4 rounded-lg"
                :class="
                  collective.capabilities.memberVetting
                    ? 'bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800'
                    : 'bg-muted border border-border'
                "
              >
                <Shield
                  class="h-5 w-5 mt-0.5"
                  :class="
                    collective.capabilities.memberVetting
                      ? 'text-green-600 dark:text-green-400'
                      : 'text-muted-foreground'
                  "
                />
                <div>
                  <p class="font-medium text-foreground">Member Vetting</p>
                  <p class="text-sm text-muted-foreground">
                    {{
                      collective.capabilities.memberVetting
                        ? 'Enabled - requests require approval'
                        : 'Disabled'
                    }}
                  </p>
                </div>
              </div>

              <div
                class="flex items-start gap-3 p-4 rounded-lg"
                :class="
                  collective.capabilities.collectiveTerms
                    ? 'bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800'
                    : 'bg-muted border border-border'
                "
              >
                <FileText
                  class="h-5 w-5 mt-0.5"
                  :class="
                    collective.capabilities.collectiveTerms
                      ? 'text-green-600 dark:text-green-400'
                      : 'text-muted-foreground'
                  "
                />
                <div>
                  <p class="font-medium text-foreground">Collective Terms</p>
                  <p class="text-sm text-muted-foreground">
                    {{
                      collective.capabilities.collectiveTerms
                        ? 'Enabled - shared policies available'
                        : 'Disabled'
                    }}
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <!-- Membership -->
        <Card>
          <CardHeader>
            <CardTitle>Membership Visibility</CardTitle>
          </CardHeader>
          <CardContent>
            <div class="flex items-center gap-3">
              <div
                class="p-2 rounded-lg"
                :class="
                  collective.membershipVisibility === 'anyone'
                    ? 'bg-green-100 dark:bg-green-950/50'
                    : 'bg-purple-100 dark:bg-purple-950/50'
                "
              >
                <Users
                  class="h-5 w-5"
                  :class="
                    collective.membershipVisibility === 'anyone'
                      ? 'text-green-600 dark:text-green-400'
                      : 'text-purple-600 dark:text-purple-400'
                  "
                />
              </div>
              <div>
                <p class="font-medium text-foreground">
                  {{
                    collective.membershipVisibility === 'anyone'
                      ? 'Anyone can request to join'
                      : 'Invite-only'
                  }}
                </p>
                <p class="text-sm text-muted-foreground">
                  {{
                    collective.membershipVisibility === 'anyone'
                      ? 'Users can discover and request membership'
                      : 'Only invited users can join'
                  }}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </TabsContent>

      <!-- Members Tab -->
      <TabsContent value="members" class="mt-6">
        <div class="flex items-center justify-between mb-6">
          <div>
            <h2 class="text-2xl font-semibold text-foreground">Members</h2>
            <p class="text-muted-foreground">
              {{ members.length }} {{ members.length === 1 ? 'member' : 'members' }}
            </p>
          </div>
          <Button v-if="collective.role === 'admin'" @click="showInviteDialog = true">
            <UserPlus class="h-4 w-4 mr-2" />
            Invite Member
          </Button>
        </div>

        <div class="space-y-4">
          <Card v-for="member in members" :key="member.id">
            <CardContent class="p-6">
              <div class="flex items-start justify-between mb-4">
                <div class="flex items-center gap-3">
                  <div class="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                    <User class="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <div class="flex items-center gap-2 mb-1">
                      <p class="font-semibold text-foreground">{{ member.name }}</p>
                      <Badge :variant="member.role === 'admin' ? 'default' : 'secondary'">
                        {{ member.role }}
                      </Badge>
                    </div>
                    <p class="text-sm text-muted-foreground">{{ member.email }}</p>
                    <div class="flex items-center gap-2 mt-2">
                      <Globe class="h-4 w-4 text-muted-foreground" />
                      <span v-if="member.subdomain" class="text-sm text-foreground font-mono">
                        {{ member.subdomain }}
                      </span>
                      <span v-else class="text-sm text-muted-foreground italic">
                        No subdomain assigned
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Endpoints Section -->
              <div v-if="member.endpoints.length > 0" class="mt-4 pt-4 border-t border-border">
                <h4 class="text-sm font-medium text-foreground mb-3 flex items-center gap-2">
                  <Zap class="h-4 w-4 text-primary" />
                  Endpoints ({{ member.endpoints.length }})
                </h4>
                <div class="space-y-2">
                  <div
                    v-for="endpoint in member.endpoints"
                    :key="endpoint.id"
                    class="flex items-start justify-between p-3 bg-muted/30 rounded-lg"
                  >
                    <div class="flex-1">
                      <div class="flex items-center gap-2 mb-1">
                        <p class="text-sm font-medium text-foreground">{{ endpoint.name }}</p>
                        <Badge variant="outline" class="text-xs">{{ endpoint.type }}</Badge>
                      </div>
                      <div class="flex items-center gap-4 mt-2">
                        <div class="flex items-center gap-1.5">
                          <DollarSign class="h-3.5 w-3.5" 
                            :class="endpoint.usesCollectivePricing ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'" 
                          />
                          <span class="text-xs" 
                            :class="endpoint.usesCollectivePricing ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'">
                            {{ endpoint.usesCollectivePricing ? 'Collective pricing' : 'Own pricing' }}
                          </span>
                        </div>
                        <div class="flex items-center gap-1.5">
                          <Shield class="h-3.5 w-3.5" 
                            :class="endpoint.usesCollectiveAccess ? 'text-blue-600 dark:text-blue-400' : 'text-muted-foreground'" 
                          />
                          <span class="text-xs" 
                            :class="endpoint.usesCollectiveAccess ? 'text-blue-600 dark:text-blue-400' : 'text-muted-foreground'">
                            {{ endpoint.usesCollectiveAccess ? 'Collective access' : 'Own access' }}
                          </span>
                        </div>
                      </div>
                      <div v-if="endpoint.usesCollectivePricing && endpoint.assignedPricingTier" class="mt-2">
                        <Select 
                          v-if="collective.role === 'admin'"
                          :model-value="endpoint.assignedPricingTier"
                          @update:model-value="(value) => assignTier(collective.id, member.id, endpoint.id, value)"
                        >
                          <SelectTrigger class="h-7 w-48 text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem 
                              v-for="tier in getPricingTiers(collective.id)" 
                              :key="tier.id" 
                              :value="tier.id"
                              class="text-xs"
                            >
                              {{ tier.name }} - ${{ tier.price }}/{{ tier.priceUnit === 'per_call' ? 'call' : 'token' }}
                            </SelectItem>
                          </SelectContent>
                        </Select>
                        <Badge v-else variant="secondary" class="text-xs">
                          {{ getTierName(collective.id, endpoint.assignedPricingTier) }}
                        </Badge>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div v-else class="mt-4 pt-4 border-t border-border">
                <p class="text-sm text-muted-foreground italic">No endpoints attached to this collective</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </TabsContent>

      <!-- Analytics Tab -->
      <TabsContent value="analytics" class="mt-6">
        <div v-if="collectiveAnalytics" class="space-y-6">
          <!-- Key Metrics -->
          <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
            <Card>
              <CardContent class="p-6">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-blue-100 dark:bg-blue-950/50 rounded-lg">
                    <Activity class="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <p class="text-2xl font-light text-foreground">
                      {{ formatNumber(collectiveAnalytics.totalQueries) }}
                    </p>
                    <p class="text-xs text-muted-foreground">Total Queries</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent class="p-6">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-green-100 dark:bg-green-950/50 rounded-lg">
                    <DollarSign class="h-5 w-5 text-green-600 dark:text-green-400" />
                  </div>
                  <div>
                    <p class="text-2xl font-light text-foreground">
                      ${{ formatNumber(collectiveAnalytics.totalRevenue) }}
                    </p>
                    <p class="text-xs text-muted-foreground">Total Revenue</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent class="p-6">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-purple-100 dark:bg-purple-950/50 rounded-lg">
                    <Clock class="h-5 w-5 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div>
                    <p class="text-2xl font-light text-foreground">
                      {{ collectiveAnalytics.averageResponseTime }}ms
                    </p>
                    <p class="text-xs text-muted-foreground">Avg Response Time</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent class="p-6">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-orange-100 dark:bg-orange-950/50 rounded-lg">
                    <Zap class="h-5 w-5 text-orange-600 dark:text-orange-400" />
                  </div>
                  <div>
                    <p class="text-2xl font-light text-foreground">
                      {{ collectiveAnalytics.topEndpoints.length }}
                    </p>
                    <p class="text-xs text-muted-foreground">Active Endpoints</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <!-- Query History Chart -->
          <Card>
            <CardHeader>
              <CardTitle class="flex items-center gap-2">
                <TrendingUp class="h-5 w-5 text-primary" />
                Query Volume (Last 7 Days)
              </CardTitle>
              <CardDescription>Number of queries through the collective endpoint</CardDescription>
            </CardHeader>
            <CardContent>
              <div class="h-64 flex items-end justify-between gap-2">
                <div
                  v-for="(point, index) in collectiveAnalytics.queryHistory"
                  :key="index"
                  class="flex-1 flex flex-col items-center gap-2"
                >
                  <div class="w-full bg-primary/20 rounded-t relative group cursor-pointer hover:bg-primary/30 transition-colors"
                    :style="{ height: (point.queries / maxQueries * 100) + '%' }"
                  >
                    <div class="absolute -top-8 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-popover border border-border rounded px-2 py-1 text-xs whitespace-nowrap">
                      {{ formatNumber(point.queries) }} queries
                    </div>
                  </div>
                  <span class="text-xs text-muted-foreground">
                    {{ formatDate(point.date) }}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          <!-- Revenue History Chart -->
          <Card>
            <CardHeader>
              <CardTitle class="flex items-center gap-2">
                <DollarSign class="h-5 w-5 text-green-600 dark:text-green-400" />
                Revenue (Last 7 Days)
              </CardTitle>
              <CardDescription>Revenue generated through the collective endpoint</CardDescription>
            </CardHeader>
            <CardContent>
              <div class="h-64 flex items-end justify-between gap-2">
                <div
                  v-for="(point, index) in collectiveAnalytics.revenueHistory"
                  :key="index"
                  class="flex-1 flex flex-col items-center gap-2"
                >
                  <div class="w-full bg-green-500/20 rounded-t relative group cursor-pointer hover:bg-green-500/30 transition-colors"
                    :style="{ height: (point.revenue / maxRevenue * 100) + '%' }"
                  >
                    <div class="absolute -top-8 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-popover border border-border rounded px-2 py-1 text-xs whitespace-nowrap">
                      ${{ formatNumber(point.revenue) }}
                    </div>
                  </div>
                  <span class="text-xs text-muted-foreground">
                    {{ formatDate(point.date) }}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          <!-- Member Statistics -->
          <Card>
            <CardHeader>
              <CardTitle class="flex items-center gap-2">
                <Users class="h-5 w-5 text-primary" />
                Member Contributions
              </CardTitle>
              <CardDescription>Query and revenue breakdown by member</CardDescription>
            </CardHeader>
            <CardContent>
              <div class="space-y-3">
                <div
                  v-for="member in collectiveAnalytics.memberStats"
                  :key="member.memberId"
                  class="flex items-center justify-between p-4 border border-border rounded-lg"
                >
                  <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                      <User class="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <p class="font-medium text-foreground">{{ member.memberName }}</p>
                      <p class="text-sm text-muted-foreground">{{ member.endpointCount }} endpoint{{ member.endpointCount !== 1 ? 's' : '' }}</p>
                    </div>
                  </div>
                  <div class="flex items-center gap-6">
                    <div class="text-right">
                      <p class="font-semibold text-foreground">{{ formatNumber(member.queries) }}</p>
                      <p class="text-xs text-muted-foreground">queries</p>
                    </div>
                    <div class="text-right">
                      <p class="font-semibold text-foreground">${{ formatNumber(member.revenue) }}</p>
                      <p class="text-xs text-muted-foreground">revenue</p>
                    </div>
                    <div class="text-right">
                      <p class="text-sm text-primary font-medium">
                        {{ ((member.queries / collectiveAnalytics.totalQueries) * 100).toFixed(1) }}%
                      </p>
                      <p class="text-xs text-muted-foreground">of total</p>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
        <div v-else class="text-center py-16">
          <Activity class="h-16 w-16 text-muted-foreground mx-auto mb-4" />
          <p class="text-muted-foreground">No analytics data available</p>
        </div>
      </TabsContent>

      <!-- Terms Tab -->
      <TabsContent value="terms" class="mt-6">
        <div class="space-y-6">
          <!-- Quick Stats -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardContent class="p-6">
                <div class="flex items-center gap-4">
                  <div class="p-3 bg-green-100 dark:bg-green-950/50 rounded-lg">
                    <DollarSign class="h-6 w-6 text-green-600 dark:text-green-400" />
                  </div>
                  <div>
                    <p class="text-3xl font-light text-foreground">
                      {{ (collectivesStore.pricingTiers[collective.id] || []).length }}
                    </p>
                    <p class="text-sm text-muted-foreground">Pricing Tiers</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent class="p-6">
                <div class="flex items-center gap-4">
                  <div class="p-3 bg-blue-100 dark:bg-blue-950/50 rounded-lg">
                    <Shield class="h-6 w-6 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <p class="text-3xl font-light text-foreground">
                      {{ (collectivesStore.accessRules[collective.id] || []).length }}
                    </p>
                    <p class="text-sm text-muted-foreground">Access Rules</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <!-- Pricing Tiers Preview -->
          <Card>
            <CardHeader>
              <div class="flex items-center justify-between">
                <div>
                  <CardTitle class="flex items-center gap-2">
                    <DollarSign class="h-5 w-5 text-green-600 dark:text-green-400" />
                    Pricing Tiers
                  </CardTitle>
                  <CardDescription class="mt-1">
                    Pricing options available for members
                  </CardDescription>
                </div>
                <Button 
                  @click="$router.push(`/collectives/${slug}/terms`)"
                  variant="outline"
                  size="sm"
                >
                  Manage Tiers
                  <ArrowRight class="h-4 w-4 ml-2" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div v-if="(collectivesStore.pricingTiers[collective.id] || []).length > 0" class="space-y-3">
                <div
                  v-for="tier in (collectivesStore.pricingTiers[collective.id] || []).slice(0, 3)"
                  :key="tier.id"
                  class="flex items-center justify-between p-3 border border-border rounded-lg"
                >
                  <div>
                    <div class="flex items-center gap-2 mb-1">
                      <span class="font-medium text-foreground">{{ tier.name }}</span>
                      <Badge v-if="tier.isDefault" variant="default" class="text-xs">Default</Badge>
                    </div>
                    <p class="text-sm text-muted-foreground">{{ tier.description }}</p>
                  </div>
                  <div class="text-right">
                    <p class="text-lg font-semibold text-foreground">${{ tier.price }}</p>
                    <p class="text-xs text-muted-foreground">
                      per {{ tier.priceUnit === 'per_call' ? 'call' : 'token' }}
                    </p>
                  </div>
                </div>
                <Button 
                  v-if="(collectivesStore.pricingTiers[collective.id] || []).length > 3"
                  variant="ghost" 
                  class="w-full"
                  @click="$router.push(`/collectives/${slug}/terms`)"
                >
                  View all {{ (collectivesStore.pricingTiers[collective.id] || []).length }} tiers
                </Button>
              </div>
              <div v-else class="text-center py-8">
                <p class="text-sm text-muted-foreground mb-4">No pricing tiers configured</p>
                <Button 
                  v-if="collective.role === 'admin'"
                  @click="$router.push(`/collectives/${slug}/terms`)"
                  size="sm"
                >
                  <Plus class="h-4 w-4 mr-2" />
                  Create Pricing Tier
                </Button>
              </div>
            </CardContent>
          </Card>

          <!-- Access Rules Preview -->
          <Card>
            <CardHeader>
              <CardTitle class="flex items-center gap-2">
                <Shield class="h-5 w-5 text-blue-600 dark:text-blue-400" />
                Access Rules
              </CardTitle>
              <CardDescription>
                Access policies available for members
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div v-if="(collectivesStore.accessRules[collective.id] || []).length > 0" class="space-y-3">
                <div
                  v-for="rule in collectivesStore.accessRules[collective.id] || []"
                  :key="rule.id"
                  class="flex items-start justify-between p-3 border border-border rounded-lg"
                >
                  <div>
                    <span class="font-medium text-foreground">{{ rule.name }}</span>
                    <p class="text-sm text-muted-foreground mt-1">{{ rule.description }}</p>
                  </div>
                  <Badge variant="outline" class="text-xs">{{ rule.type }}</Badge>
                </div>
              </div>
              <div v-else class="text-center py-8">
                <p class="text-sm text-muted-foreground">No access rules configured</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </TabsContent>

      <!-- Settings Tab -->
      <TabsContent value="settings" v-if="collective.role === 'admin'" class="mt-6">
        <Card>
          <CardHeader>
            <CardTitle>Collective Settings</CardTitle>
            <CardDescription>Manage your collective configuration</CardDescription>
          </CardHeader>
          <CardContent>
            <p class="text-sm text-muted-foreground">Settings management to be implemented...</p>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>

    <!-- Invite Dialog -->
    <Dialog v-model:open="showInviteDialog">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite Member</DialogTitle>
          <DialogDescription>
            Send an invitation to join {{ collective.name }}
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-4 py-4">
          <div class="space-y-2">
            <Label for="email">Email Address</Label>
            <Input id="email" type="email" placeholder="user@example.com" />
          </div>
          <div class="space-y-2">
            <Label for="message">Message (Optional)</Label>
            <Textarea id="message" placeholder="Add a personal message..." rows="3" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="showInviteDialog = false">Cancel</Button>
          <Button @click="sendInvite">Send Invitation</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
  <div v-else class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <p class="text-muted-foreground">Collective not found</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  Users,
  User,
  UserPlus,
  Zap,
  Server,
  Shield,
  FileText,
  Globe,
  DollarSign,
  ArrowRight,
  Plus,
  Activity,
  TrendingUp,
  Clock,
} from 'lucide-vue-next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useCollectivesStore } from '@/stores/collectives'

const route = useRoute()
const router = useRouter()
const collectivesStore = useCollectivesStore()

const slug = route.params.slug as string
const collective = computed(() => collectivesStore.getCollectiveBySlug(slug))
const members = computed(() =>
  collective.value ? collectivesStore.getMembersByCollectiveId(collective.value.id) : []
)
const collectiveAnalytics = computed(() =>
  collective.value ? collectivesStore.getAnalytics(collective.value.id) : null
)

const activeTab = ref('overview')
const showInviteDialog = ref(false)

// Analytics computed values
const maxQueries = computed(() => {
  if (!collectiveAnalytics.value) return 0
  return Math.max(...collectiveAnalytics.value.queryHistory.map((p) => p.queries))
})

const maxRevenue = computed(() => {
  if (!collectiveAnalytics.value) return 0
  return Math.max(...collectiveAnalytics.value.revenueHistory.map((p) => p.revenue))
})

const sendInvite = () => {
  // Implementation for sending invitation
  showInviteDialog.value = false
}

const getPricingTiers = (collectiveId: string) => {
  return collectivesStore.pricingTiers[collectiveId] || []
}

const getTierName = (collectiveId: string, tierId: string) => {
  const tier = getPricingTiers(collectiveId).find((t) => t.id === tierId)
  return tier ? `${tier.name} - $${tier.price}/${tier.priceUnit === 'per_call' ? 'call' : 'token'}` : 'Unknown tier'
}

const assignTier = (collectiveId: string, memberId: string, endpointId: string, tierId: string) => {
  collectivesStore.assignPricingTierToEndpoint(collectiveId, memberId, endpointId, tierId)
}

const formatNumber = (num: number) => {
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'k'
  }
  return num.toFixed(2)
}

const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
</script>

