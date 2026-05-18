<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Breadcrumb Navigation -->
    <nav class="flex mb-6" aria-label="Breadcrumb">
      <ol class="flex items-center space-x-2">
        <li>
          <router-link
            to="/endpoints"
            class="text-muted-foreground hover:text-foreground body-sm font-medium flex items-center transition-colors"
          >
            <Server class="h-4 w-4 mr-2" />
            Endpoints
          </router-link>
        </li>
        <li class="flex items-center">
          <ChevronRight class="h-4 w-4 text-muted-foreground mx-3" />
          <span class="text-foreground body-sm font-medium">{{
            endpoint?.name || 'Loading...'
          }}</span>
        </li>
      </ol>
    </nav>

    <!-- Loading State -->
    <div v-if="loading" class="space-y-6 animate-pulse">
      <!-- Header Skeleton -->
      <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-4">
            <div class="w-14 h-14 bg-muted rounded-lg"></div>
            <div class="space-y-3">
              <div class="h-8 bg-muted rounded w-56"></div>
              <div class="h-5 bg-muted rounded w-80"></div>
              <div class="flex gap-2">
                <div class="h-7 bg-muted rounded-full w-16"></div>
                <div class="h-7 bg-muted rounded-full w-28"></div>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <div class="h-10 bg-muted rounded w-24"></div>
            <div class="h-10 bg-muted rounded w-36"></div>
            <div class="h-10 bg-muted rounded w-24"></div>
          </div>
        </div>
      </div>

      <!-- Tabs Skeleton -->
      <div class="h-10 bg-muted rounded-md w-full"></div>

      <!-- Content Grid Skeleton -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Left Column (2/3) -->
        <div class="lg:col-span-2 space-y-6">
          <!-- Description Card Skeleton -->
          <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
            <div class="h-6 bg-muted rounded w-32 mb-4"></div>
            <div class="space-y-2">
              <div class="h-4 bg-muted rounded w-full"></div>
              <div class="h-4 bg-muted rounded w-5/6"></div>
              <div class="h-4 bg-muted rounded w-4/6"></div>
            </div>
          </div>

          <!-- Watched Paths Card Skeleton -->
          <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
            <div class="h-6 bg-muted rounded w-36 mb-4"></div>
            <div class="space-y-3">
              <div
                v-for="i in 2"
                :key="`path-${i}`"
                class="p-3 bg-muted/50 border border-border rounded-lg"
              >
                <div class="flex items-start gap-3">
                  <div class="w-2 h-2 bg-muted rounded-full mt-1.5"></div>
                  <div class="flex-1 space-y-2">
                    <div class="h-4 bg-muted rounded w-64"></div>
                    <div class="h-3 bg-muted rounded w-20"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Right Column (1/3) -->
        <div class="space-y-4">
          <!-- Details Card Skeleton -->
          <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
            <div class="h-5 bg-muted rounded w-20 mb-4"></div>
            <div class="space-y-3">
              <div
                v-for="i in 3"
                :key="`detail-${i}`"
                class="flex justify-between items-center py-1"
              >
                <div class="h-4 bg-muted rounded w-20"></div>
                <div class="h-4 bg-muted rounded w-28"></div>
              </div>
            </div>
          </div>

          <!-- Tags Card Skeleton -->
          <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
            <div class="h-5 bg-muted rounded w-12 mb-3"></div>
            <div class="flex flex-wrap gap-2">
              <div class="h-6 bg-muted rounded w-16"></div>
              <div class="h-6 bg-muted rounded w-20"></div>
              <div class="h-6 bg-muted rounded w-14"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="bg-destructive/10 border border-destructive/20 rounded-2xl p-8 text-center"
    >
      <h3 class="heading-3 text-destructive mb-2">Endpoint not found</h3>
      <p class="text-destructive mb-4">
        The endpoint you're looking for doesn't exist or has been deleted.
      </p>
      <Button @click="$router.push('/endpoints')" variant="outline"> Back to Endpoints </Button>
    </div>

    <!-- Main Content -->
    <div v-else-if="endpoint" class="space-y-6">
      <!-- Header Section -->
      <div class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6">
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-4">
            <div
              class="p-3 rounded-lg bg-gradient-to-br from-purple-100 dark:from-purple-950 to-blue-100 dark:to-blue-950"
            >
              <Server class="h-8 w-8 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <h1 class="heading-2 mb-2">{{ endpoint.name }}</h1>
              <p class="body-lg text-muted-foreground mb-4">{{ endpoint.summary }}</p>
              <div class="flex flex-wrap items-center gap-2">
                <Badge
                  :variant="endpoint.published ? 'default' : 'outline'"
                  :class="
                    endpoint.published
                      ? 'bg-primary/10 text-primary border border-primary/20'
                      : 'bg-muted text-muted-foreground border border-border'
                  "
                >
                  <div
                    :class="
                      endpoint.published
                        ? 'w-2 h-2 bg-primary rounded-full mr-2 animate-pulse'
                        : 'w-2 h-2 bg-muted-foreground rounded-full mr-2'
                    "
                  ></div>
                  {{ endpoint.published ? 'Live' : 'Draft' }}
                </Badge>
                <Badge variant="outline" class="bg-primary/10 text-primary border-primary/20">
                  {{ getPricingRange }}
                </Badge>
              </div>
            </div>
          </div>
          <!-- Quick Actions -->
          <div class="flex flex-col gap-2">
            <div class="flex items-center gap-2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button v-if="!endpoint.published" variant="default">
                      <Send class="h-4 w-4 mr-2" />
                      Publish
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Make this endpoint publicly available</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <Button variant="outline" @click="openEditDialog">
                <Pencil class="h-4 w-4 mr-2" />
                Edit
              </Button>
              <Button
                variant="outline"
                class="text-destructive hover:text-destructive"
                @click="
                  () => {
                    deleteNameConfirm = ''
                    showDeleteDialog = true
                  }
                "
              >
                <Trash2 class="h-4 w-4 mr-2" />
                Delete
              </Button>
            </div>
            <Button
              v-if="syftHubUrl"
              variant="outline"
              class="w-full"
              as="a"
              :href="syftHubUrl"
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink class="h-4 w-4 mr-2" />
              View on SyftHub
            </Button>
          </div>
        </div>
      </div>

      <!-- Tabs Section -->
      <Tabs v-model="activeTab" class="space-y-4">
        <TabsList
          class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-3"
        >
          <TabsTrigger value="overview" class="flex items-center gap-2">
            <Layout class="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="access" class="flex items-center gap-2">
            <Shield class="h-4 w-4" />
            Access Control
          </TabsTrigger>
          <TabsTrigger value="transactions" class="flex items-center gap-2">
            <Receipt class="h-4 w-4" />
            Transactions
          </TabsTrigger>
        </TabsList>

        <!-- Overview Tab -->
        <TabsContent value="overview" class="space-y-6">
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Description and Data Sources -->
            <div class="lg:col-span-2 space-y-6">
              <!-- Description -->
              <div
                v-if="endpoint.description && endpoint.description.trim()"
                class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6"
              >
                <h2 class="heading-3 text-foreground mb-4 flex items-center gap-2">
                  <FileText class="h-5 w-5 text-muted-foreground" />
                  Description
                </h2>
                <div class="prose prose-sm max-w-none text-muted-foreground">
                  <div class="markdown-content">
                    <MdPreview
                      :model-value="endpoint.description"
                      :theme="isDark ? 'dark' : 'light'"
                      :show-code-row-number="false"
                    />
                  </div>
                </div>
              </div>

              <!-- Data Sources -->
              <div
                v-if="endpoint.dataset && getWatchedPaths.length > 0"
                class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6"
              >
                <h2 class="heading-3 text-foreground mb-4 flex items-center gap-2">
                  <Database class="h-5 w-5 text-muted-foreground" />
                  Watched Paths
                </h2>
                <div class="space-y-3">
                  <div
                    v-for="path in getWatchedPaths"
                    :key="path.id"
                    class="p-3 bg-muted/50 border border-border rounded-lg"
                  >
                    <div class="flex items-start gap-3">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger as-child>
                            <div
                              :class="[
                                'w-2 h-2 rounded-full mt-1.5 cursor-help',
                                path.status === 'indexed'
                                  ? 'bg-success'
                                  : path.status === 'processing'
                                    ? 'bg-primary'
                                    : path.status === 'queued'
                                      ? 'bg-warning'
                                      : path.status === 'errored'
                                        ? 'bg-destructive'
                                        : 'bg-muted',
                              ]"
                            ></div>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p>{{ getStatusLabel(path.status) }}</p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                      <div class="flex-1">
                        <p class="body-sm font-medium text-foreground">{{ path.path }}</p>
                        <p class="body-sm text-muted-foreground mt-1">{{ path.fileCount }} files</p>
                        <p class="body-sm text-muted-foreground mt-1 italic">
                          {{ path.description }}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Quick Stats -->
            <div class="space-y-4">
              <!-- Endpoint Details Card -->
              <div
                class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6"
              >
                <h3 class="body-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                  <Info class="h-4 w-4 text-muted-foreground" />
                  Details
                </h3>
                <div class="space-y-3">
                  <div class="flex justify-between items-center py-1">
                    <span class="body-sm text-muted-foreground">Type</span>
                    <span class="body-sm font-medium text-foreground">{{ getEndpointType }}</span>
                  </div>
                  <!-- Only show Response type for Data endpoints, not AI Model endpoints -->
                  <template v-if="getEndpointType !== 'AI Model Endpoint'">
                    <Separator />
                    <div class="flex justify-between items-center py-1">
                      <span class="body-sm text-muted-foreground">Response</span>
                      <span class="body-sm font-medium text-foreground">{{ getResponseType }}</span>
                    </div>
                    <Separator />
                  </template>
                  <div v-if="endpoint.dataset" class="flex justify-between items-center py-1">
                    <span class="body-sm text-muted-foreground">Data Source</span>
                    <router-link
                      :to="{
                        name: 'dataset-detail',
                        params: { slug: endpoint.dataset.name },
                      }"
                      class="body-sm font-medium text-primary hover:text-primary/80 hover:underline"
                    >
                      {{ endpoint.dataset.name }}
                    </router-link>
                  </div>
                  <template v-if="endpoint.model">
                    <Separator />
                    <div class="flex justify-between items-center py-1">
                      <span class="body-sm text-muted-foreground">Model</span>
                      <router-link
                        :to="{
                          name: 'model-detail',
                          params: { slug: endpoint.model.name },
                        }"
                        class="body-sm font-medium text-primary hover:text-primary/80 hover:underline"
                      >
                        {{ endpoint.model.name }}
                      </router-link>
                    </div>
                  </template>
                </div>
              </div>

              <!-- Tags -->
              <div
                class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6"
              >
                <h3 class="body-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                  <Tags class="h-4 w-4 text-muted-foreground" />
                  Tags
                </h3>
                <div class="flex flex-wrap gap-2">
                  <Badge
                    v-for="language in parsedTags.languages"
                    :key="`lang-${language}`"
                    variant="outline"
                    class="body-sm"
                  >
                    {{ language }}
                  </Badge>
                  <Badge
                    v-for="domain in parsedTags.domains"
                    :key="`domain-${domain}`"
                    variant="outline"
                    class="body-sm"
                  >
                    {{ domain }}
                  </Badge>
                  <Badge
                    v-for="tag in parsedTags.others"
                    :key="tag"
                    variant="outline"
                    class="body-sm"
                  >
                    {{ tag }}
                  </Badge>
                </div>
              </div>
            </div>
          </div>
        </TabsContent>

        <!-- Access Control Tab -->
        <TabsContent value="access" class="space-y-6">
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
            <!-- Authorization Policies -->
            <Card class="bg-card/80 backdrop-blur-sm border border-border shadow-sm flex flex-col">
              <CardHeader>
                <CardTitle class="flex items-center gap-2">
                  <UserCheck class="h-5 w-5 text-muted-foreground" />
                  Authorization
                </CardTitle>
                <CardDescription> Control who can access this endpoint </CardDescription>
              </CardHeader>
              <CardContent class="space-y-3 flex-1">
                <div
                  v-if="getAuthorizationPolicies().length === 0"
                  class="text-sm text-muted-foreground"
                >
                  No authorization policies configured
                </div>
                <div v-else class="space-y-2">
                  <div
                    v-for="policy in getAuthorizationPolicies()"
                    :key="policy.id"
                    class="p-3 bg-muted/50 border border-border rounded-lg"
                  >
                    <div class="flex items-start justify-between">
                      <div class="flex-1">
                        <h4 class="body-sm font-medium text-foreground mb-1">
                          {{ policy.name }}
                        </h4>
                        <p class="body-sm text-muted-foreground">
                          <template
                            v-if="
                              Array.isArray(policy.configuration?.allowed_users) &&
                              policy.configuration.allowed_users.length
                            "
                          >
                            Allow access for {{ policy.configuration.allowed_users.join(', ') }}
                          </template>
                          <template
                            v-else-if="
                              Array.isArray(policy.configuration?.denied_users) &&
                              policy.configuration.denied_users.length
                            "
                          >
                            Deny access for {{ policy.configuration.denied_users.join(', ') }}
                          </template>
                          <template v-else> Authorization rule configured </template>
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        class="text-destructive hover:text-destructive hover:bg-destructive/10 ml-2 h-8 w-8 p-0"
                        @click="handleDeletePolicy(policy.id, policy.name)"
                      >
                        <Trash2 class="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
              <CardFooter>
                <Button
                  variant="outline"
                  class="w-full"
                  @click="
                    () => {
                      selectedPolicyType = 'access'
                      showAddPolicyDialog = true
                    }
                  "
                >
                  <Plus class="h-4 w-4 mr-2" />
                  Add Authorization Rule
                </Button>
              </CardFooter>
            </Card>

            <!-- Rate Limiting Policies -->
            <Card class="bg-card/80 backdrop-blur-sm border border-border shadow-sm flex flex-col">
              <CardHeader>
                <CardTitle class="flex items-center gap-2">
                  <Gauge class="h-5 w-5 text-muted-foreground" />
                  Rate Limiting
                </CardTitle>
                <CardDescription> Manage request frequency limits </CardDescription>
              </CardHeader>
              <CardContent class="space-y-3 flex-1">
                <div
                  v-if="getRateLimitPolicies().length === 0"
                  class="text-sm text-muted-foreground"
                >
                  No rate limiting policies configured
                </div>
                <div v-else class="space-y-2">
                  <div
                    v-for="policy in getRateLimitPolicies()"
                    :key="policy.id"
                    class="p-3 bg-muted/50 border border-border rounded-lg"
                  >
                    <div class="flex items-start justify-between">
                      <div class="flex-1">
                        <h4 class="body-sm font-medium text-foreground mb-1">
                          {{ policy.name }}
                        </h4>
                        <p class="body-sm text-muted-foreground">
                          <template
                            v-if="
                              policy.configuration?.limit &&
                              typeof policy.configuration?.scope === 'string'
                            "
                          >
                            {{ policy.configuration.limit }} requests per
                            {{ policy.configuration.windowUnit || 'minute' }}
                            {{ policy.configuration.scope.replace('_', ' ') }}
                          </template>
                          <template v-else-if="policy.configuration?.limit">
                            Limit: {{ policy.configuration.limit }}
                          </template>
                          <template v-else> Rate limiting configured </template>
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        class="text-destructive hover:text-destructive hover:bg-destructive/10 ml-2 h-8 w-8 p-0"
                        @click="handleDeletePolicy(policy.id, policy.name)"
                      >
                        <Trash2 class="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
              <CardFooter>
                <Button
                  variant="outline"
                  class="w-full"
                  @click="
                    () => {
                      selectedPolicyType = 'rate_limit'
                      showAddPolicyDialog = true
                    }
                  "
                >
                  <Plus class="h-4 w-4 mr-2" />
                  Add Rate Limiting Rule
                </Button>
              </CardFooter>
            </Card>

            <!-- Pricing Policies -->
            <Card class="bg-card/80 backdrop-blur-sm border border-border shadow-sm flex flex-col">
              <CardHeader>
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-3">
                    <div
                      class="h-10 w-10 rounded-lg bg-yellow-100 dark:bg-yellow-900/30 flex items-center justify-center"
                    >
                      <DollarSign class="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
                    </div>
                    <div>
                      <CardTitle>Set your price</CardTitle>
                      <CardDescription>
                        Charge per query or make it free - you decide
                      </CardDescription>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" @click="showAddPricingRuleDialog = true">
                    <Plus class="h-4 w-4 mr-2" />
                    Add Pricing rule
                  </Button>
                </div>
              </CardHeader>
              <CardContent class="space-y-3 flex-1">
                <!-- Default free access banner (only when no pricing rules) -->
                <div
                  v-if="getPricingPolicies().length === 0"
                  class="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/50 rounded-xl px-4 py-3"
                >
                  <p class="text-sm text-emerald-700 dark:text-emerald-300">
                    <strong class="font-medium">Default:</strong> Free access - no charges applied
                  </p>
                </div>

                <div v-if="getPricingPolicies().length === 0" class="text-center py-4">
                  <p class="text-sm text-muted-foreground">No pricing rule added yet</p>
                </div>
                <div v-else class="space-y-2">
                  <div
                    v-for="policy in getPricingPolicies()"
                    :key="policy.id"
                    class="p-3 bg-muted/50 border border-border rounded-lg"
                  >
                    <div class="flex items-start justify-between">
                      <div class="flex-1">
                        <h4 class="body-sm font-medium text-foreground mb-1">
                          {{ policy.name }}
                        </h4>
                        <p class="body-sm text-muted-foreground">
                          {{ getPricingPolicySummary(policy) }}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        class="text-destructive hover:text-destructive hover:bg-destructive/10 ml-2 h-8 w-8 p-0"
                        @click="handleDeletePolicy(policy.id, policy.name)"
                      >
                        <Trash2 class="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <!-- Access Summary -->
            <Card class="bg-card/80 backdrop-blur-sm border border-border shadow-sm flex flex-col">
              <CardHeader>
                <CardTitle class="flex items-center gap-2">
                  <Shield class="h-5 w-5 text-muted-foreground" />
                  Access Summary
                </CardTitle>
                <CardDescription> Overview of all access controls </CardDescription>
              </CardHeader>
              <CardContent class="space-y-3 flex-1">
                <div class="flex justify-between items-center py-1">
                  <span class="body-sm text-muted-foreground">Total Policies</span>
                  <span class="body-sm font-medium text-foreground">{{
                    getTotalPoliciesCount()
                  }}</span>
                </div>
                <Separator />
                <div class="flex justify-between items-center py-1">
                  <span class="body-sm text-muted-foreground">Authorization</span>
                  <span class="body-sm font-medium text-foreground">{{
                    getAuthorizationPolicies().length
                  }}</span>
                </div>
                <Separator />
                <div class="flex justify-between items-center py-1">
                  <span class="body-sm text-muted-foreground">Rate Limiting</span>
                  <span class="body-sm font-medium text-foreground">{{
                    getRateLimitPolicies().length
                  }}</span>
                </div>
                <Separator />
                <div class="flex justify-between items-center py-1">
                  <span class="body-sm text-muted-foreground">Pricing</span>
                  <span class="body-sm font-medium text-foreground">{{
                    getPricingPolicies().length
                  }}</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <!-- Transactions Tab -->
        <TabsContent value="transactions" class="space-y-4">
          <!-- Filter bar -->
          <div class="flex items-center gap-3">
            <div class="flex-1">
              <Input
                v-model="txnEmailFilter"
                placeholder="Filter by email..."
                class="h-9 max-w-sm"
              />
            </div>
            <Button variant="outline" size="sm" @click="fetchTransactions" :disabled="txnLoading">
              <Loader2 v-if="txnLoading" class="h-4 w-4 mr-2 animate-spin" />
              Refresh
            </Button>
          </div>

          <!-- MPP Transactions -->
          <Card
            v-if="!lockedWallet || lockedWallet.wallet_type === 'mpp'"
            class="bg-card/80 backdrop-blur-sm border border-border shadow-sm"
          >
            <CardHeader class="pb-3">
              <CardTitle class="text-base flex items-center gap-2">
                <Zap class="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                MPP Transactions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div v-if="txnLoading" class="space-y-3">
                <Skeleton v-for="i in 3" :key="i" class="h-12 w-full" />
              </div>
              <div
                v-else-if="filteredMppTransactions.length === 0"
                class="text-center py-6 text-sm text-muted-foreground"
              >
                No MPP transactions found
              </div>
              <div v-else class="divide-y divide-border">
                <div
                  v-for="txn in filteredMppTransactions"
                  :key="txn.id"
                  class="flex items-center justify-between py-3"
                >
                  <div class="min-w-0 flex-1">
                    <p class="text-sm font-medium truncate">{{ txn.sender_email }}</p>
                    <p class="text-xs text-muted-foreground">
                      {{ formatTimeAgo(txn.created_at) }}
                      <span v-if="txn.app_ep_path" class="ml-1">
                        &middot; {{ txn.app_ep_path }}
                      </span>
                    </p>
                  </div>
                  <span class="text-sm font-semibold text-emerald-600 dark:text-emerald-400 ml-4">
                    +${{ formatPrice(txn.amount) }}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          <!-- Gateway (Xendit) Ledger Entries -->
          <Card
            v-if="!lockedWallet || lockedWallet.wallet_type === 'xendit'"
            class="bg-card/80 backdrop-blur-sm border border-border shadow-sm"
          >
            <CardHeader class="pb-3">
              <CardTitle class="text-base flex items-center gap-2">
                <Package class="h-4 w-4 text-violet-600 dark:text-violet-400" />
                Transactions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div v-if="txnLoading" class="space-y-3">
                <Skeleton v-for="i in 3" :key="i" class="h-12 w-full" />
              </div>
              <div
                v-else-if="filteredLedgerEntries.length === 0"
                class="text-center py-6 text-sm text-muted-foreground"
              >
                No transactions found
              </div>
              <div v-else class="divide-y divide-border">
                <div
                  v-for="entry in filteredLedgerEntries"
                  :key="entry.id"
                  class="flex items-center justify-between py-3"
                >
                  <div class="min-w-0 flex-1">
                    <p class="text-sm font-medium truncate">{{ entry.user_email }}</p>
                    <p class="text-xs text-muted-foreground">
                      {{ formatTimeAgo(entry.created_at) }}
                      <span class="ml-1">&middot; {{ entry.type }}</span>
                    </p>
                  </div>
                  <span
                    class="text-sm font-semibold ml-4"
                    :class="{
                      'text-emerald-600 dark:text-emerald-400': entry.type === 'debit',
                      'text-muted-foreground line-through': entry.type === 'cancelled',
                    }"
                  >
                    {{ entry.type === 'debit' ? '+' : '-' }}{{ formatPrice(entry.amount) }}
                    {{ entry.currency }}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  </div>

  <!-- Delete Confirmation Dialog -->
  <Dialog v-model:open="showDeleteDialog">
    <DialogContent class="sm:max-w-[425px]">
      <DialogHeader>
        <DialogTitle class="text-destructive">Delete endpoint</DialogTitle>
        <DialogDescription>
          This will permanently delete this endpoint and remove it from SyftHub. This action cannot
          be undone.
        </DialogDescription>
      </DialogHeader>
      <div class="space-y-2">
        <Label class="gap-1">
          Type <span class="font-semibold text-foreground">{{ endpoint?.name }}</span> to confirm
        </Label>
        <Input v-model="deleteNameConfirm" :placeholder="endpoint?.name || 'endpoint-name'" />
        <p
          v-if="deleteNameConfirm"
          class="text-sm"
          :class="deleteNameConfirm === endpoint?.name ? 'text-success' : 'text-muted-foreground'"
        >
          {{ deleteNameConfirm === endpoint?.name ? 'Name matches' : 'Name does not match' }}
        </p>
      </div>
      <DialogFooter>
        <Button variant="outline" @click="showDeleteDialog = false" :disabled="isDeleting">
          Cancel
        </Button>
        <Button
          variant="destructive"
          :disabled="deleteNameConfirm !== endpoint?.name || isDeleting"
          @click="deleteEndpoint"
        >
          <div v-if="isDeleting" class="flex items-center gap-2">
            <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            Deleting...
          </div>
          <span v-else>Delete Endpoint</span>
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>

  <!-- Delete Policy Confirmation Dialog -->
  <Dialog v-model:open="showDeletePolicyDialog">
    <DialogContent class="sm:max-w-[400px]">
      <DialogHeader>
        <DialogTitle>Delete Policy</DialogTitle>
        <DialogDescription>
          Are you sure you want to delete "{{ policyToDelete?.name }}"? This action cannot be
          undone.
        </DialogDescription>
      </DialogHeader>
      <DialogFooter>
        <Button variant="outline" @click="cancelDeletePolicy">Cancel</Button>
        <Button variant="destructive" @click="confirmDeletePolicy"> Delete Policy </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>

  <!-- Add Policy Dialog (for auth + rate limit) -->
  <PolicyFormDialog
    v-model:open="showAddPolicyDialog"
    :policy-type="selectedPolicyType"
    :is-submitting="policyCreating"
    @save="handleAddPolicy"
  />

  <!-- Add Pricing Rule Dialog -->
  <AddPricingRuleDialog
    v-model:open="showAddPricingRuleDialog"
    :locked-wallet-id="lockedWalletId"
    :endpoint-has-dataset="endpoint?.dataset_id != null"
    @pricing-created="handlePricingCreated"
  />

  <!-- Edit Endpoint Dialog -->
  <EditEndpointDialog
    v-model:open="showEditDialog"
    :endpoint="endpointForEdit"
    @saved="handleEditSaved"
  />
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTheme } from '@/composables/useTheme'
import {
  Server,
  ChevronRight,
  Trash2,
  Send,
  Gauge,
  DollarSign,
  UserCheck,
  Layout,
  Shield,
  FileText,
  Info,
  Tags,
  Database,
  Plus,
  ExternalLink,
  Pencil,
  Receipt,
  Zap,
  Package,
  Loader2,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import PolicyFormDialog from '@/components/PolicyFormDialog.vue'
import AddPricingRuleDialog from '@/components/AddPricingRuleDialog.vue'

import type { PolicyTypeId } from '@/config/policyTypes'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { toast } from 'vue-sonner'
import { ingestionApi } from '@/api/endpoints/ingestion'
import { policiesApi } from '@/api/policies/policies'
import { walletsApi } from '@/api/endpoints/wallets'
import { paymentsApi } from '@/api/endpoints/payments'
import type { LedgerEntryResponse, TransactionResponse, WalletListItem } from '@/api/types'
import { formatPrice, formatTimeAgo } from '@/lib/formatters'
import EditEndpointDialog from '@/components/EditEndpointDialog.vue'
import { useUserStore } from '@/stores/user'
import { usePolicyCreation } from '@/composables/usePolicyCreation'
import type { PolicyFormData } from '@/composables/usePolicyCreation'
import type { EndpointResponse } from '@/api/types'
import type { IngestionStatusResponse, IngestionJobListResponse } from '@/api/types'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { isDark } = useTheme()
const error = ref(false)
const loading = ref(true)
const endpoint = ref<EndpointResponse | null>(null)
const activeTab = ref('overview')

watch(activeTab, (tab) => {
  if (tab === 'transactions') {
    fetchTransactions()
  }
})

const deleteNameConfirm = ref('')
const showDeleteDialog = ref(false)
const isDeleting = ref(false)
const showDeletePolicyDialog = ref(false)
const policyToDelete = ref<{ id: string; name: string } | null>(null)
const showAddPolicyDialog = ref(false)
const showAddPricingRuleDialog = ref(false)

const showEditDialog = ref(false)
const selectedPolicyType = ref<PolicyTypeId>('access')
const ingestionStatus = ref<IngestionStatusResponse | null>(null)
const ingestionJobs = ref<IngestionJobListResponse | null>(null)

// Policy creation composable
const { createPolicy, isCreating: policyCreating } = usePolicyCreation()

// Computed URL to view endpoint on SyftHub
const syftHubUrl = computed(() =>
  endpoint.value?.slug ? userStore.getEndpointUrlInMarketplace(endpoint.value.slug) : null,
)

// Computed endpoint data for edit dialog
const endpointForEdit = computed(() => {
  if (!endpoint.value) return null
  return {
    slug: endpoint.value.slug,
    name: endpoint.value.name,
    summary: endpoint.value.summary,
    description: endpoint.value.description,
  }
})

// Edit dialog handlers
const openEditDialog = () => {
  showEditDialog.value = true
}

const handleEditSaved = (data: { summary: string; description: string }) => {
  // Update local endpoint data
  if (endpoint.value) {
    endpoint.value.summary = data.summary
    endpoint.value.description = data.description
  }
}

// Parse tags into languages, domains, and other tags
const parsedTags = computed(() => {
  if (!endpoint.value?.tags) {
    return { languages: [], domains: [], others: [] }
  }

  const tagsArray = endpoint.value.tags
    .split(',')
    .map((t) => t.trim())
    .filter((t) => t)
  const languages: string[] = []
  const domains: string[] = []
  const others: string[] = []

  tagsArray.forEach((tag) => {
    if (tag.startsWith('language:')) {
      languages.push(tag.replace('language:', ''))
    } else if (tag.startsWith('domain:')) {
      domains.push(tag.replace('domain:', ''))
    } else {
      others.push(tag)
    }
  })

  return { languages, domains, others }
})

// Get watched paths from dataset configuration
const getWatchedPaths = computed(() => {
  if (!endpoint.value?.dataset) {
    return []
  }

  const config = endpoint.value.dataset.configuration as Record<string, unknown>
  const filePaths = (config?.filePaths as Array<{ path: string; description?: string }>) || []

  return filePaths.map((pathItem) => {
    const pathStats = getStatsForPath(pathItem.path)
    return {
      id: pathItem.path,
      path: pathItem.path,
      description: pathItem.description || 'Selected folder for ingestion',
      fileCount: pathStats.fileCount,
      status: pathStats.status,
    }
  })
})

// Get statistics for a specific path by filtering jobs
const getStatsForPath = (watchedPath: string) => {
  if (!ingestionJobs.value?.jobs) {
    return { fileCount: 0, status: 'unknown' }
  }

  // Filter jobs that start with the watched path
  const pathJobs = ingestionJobs.value.jobs.filter((job) => job.file_path.startsWith(watchedPath))

  if (pathJobs.length === 0) {
    return { fileCount: 0, status: 'unknown' }
  }

  // Count jobs by status
  const statusCounts = pathJobs.reduce(
    (counts, job) => {
      counts[job.status] = (counts[job.status] || 0) + 1
      return counts
    },
    {} as Record<string, number>,
  )

  // Determine overall status based on priority
  let status = 'unknown'
  if ((statusCounts['in_progress'] ?? 0) > 0) {
    status = 'processing'
  } else if ((statusCounts['pending'] ?? 0) > 0) {
    status = 'queued'
  } else if ((statusCounts['failed'] ?? 0) > 0) {
    status = 'errored'
  } else if ((statusCounts['completed'] ?? 0) > 0) {
    status = 'indexed'
  }

  return {
    fileCount: pathJobs.length,
    status,
  }
}

// Fetch all ingestion jobs across all pages
const fetchAllIngestionJobs = async (datasetId: string) => {
  const allJobs = []
  let offset = 0
  const limit = 100 // Use smaller pages for better performance

  while (true) {
    const response = await ingestionApi.listJobs(datasetId, undefined, limit, offset)
    allJobs.push(...response.jobs)

    // If we got fewer jobs than the limit, we've reached the end
    if (response.jobs.length < limit) {
      break
    }

    offset += limit
  }

  return allJobs
}

// Get human-readable status label for tooltip
const getStatusLabel = (status: string) => {
  switch (status) {
    case 'indexed':
      return 'All files processed successfully'
    case 'processing':
      return 'Files are currently being processed'
    case 'queued':
      return 'Files are queued for processing'
    case 'errored':
      return 'Some files failed to process'
    case 'unknown':
    default:
      return 'Status unknown'
  }
}

// Get policies by type
const getAuthorizationPolicies = () => {
  return endpoint.value?.policies?.filter((p) => p.policy_type === 'access') || []
}

const getRateLimitPolicies = () => {
  return endpoint.value?.policies?.filter((p) => p.policy_type === 'rate_limit') || []
}

const walletsById = ref<Record<string, WalletListItem>>({})

// Cached promise so callers can await the initial fetch even if it's already
// in-flight, without triggering a duplicate network request. Anything that
// reads walletsById (e.g. lockedWallet) should call ensureWallets() first
// rather than racing the initial onMounted fetch.
let walletsPromise: Promise<void> | null = null

const fetchWallets = async () => {
  try {
    const list = await walletsApi.list()
    walletsById.value = Object.fromEntries(list.map((w) => [w.id, w]))
  } catch {
    walletsById.value = {}
  }
}

const ensureWallets = (): Promise<void> => {
  walletsPromise ??= fetchWallets()
  return walletsPromise
}

const getPricingPolicies = () => {
  return (
    endpoint.value?.policies?.filter(
      (p) =>
        p.policy_type === 'mpp_per_request' ||
        p.policy_type === 'xendit_per_request' ||
        p.policy_type === 'mpp_per_document' ||
        p.policy_type === 'xendit_per_document',
    ) || []
  )
}

// All payment policies on an endpoint share one wallet (frontend-enforced).
// The first pricing policy decides which wallet future ones must use.
const lockedWallet = computed<WalletListItem | null>(() => {
  const first = getPricingPolicies()[0] as
    | { wallet_id?: string; configuration?: Record<string, unknown> }
    | undefined
  if (!first?.wallet_id) return null
  return walletsById.value[first.wallet_id] ?? null
})

const lockedWalletId = computed(() => lockedWallet.value?.id ?? null)

const policyWallet = (policy: {
  policy_type: string
  configuration: Record<string, unknown>
  wallet_id?: string | null
}): WalletListItem | null => {
  if (policy.wallet_id) return walletsById.value[policy.wallet_id] ?? null
  return null
}

const getPricingPolicySummary = (policy: {
  policy_type: string
  configuration: Record<string, unknown>
  wallet_id?: string | null
}): string => {
  const config = policy.configuration
  const appliedTo = config?.applied_to as string[] | undefined
  const appliedLabel =
    appliedTo && appliedTo.length === 1 && appliedTo[0] === '*'
      ? 'for all users'
      : appliedTo && appliedTo.length > 0
        ? `for ${appliedTo.join(', ')}`
        : ''

  const wallet = policyWallet(policy)
  const currency = wallet?.currency ?? 'USD'

  // MPP: price per query
  if (policy.policy_type === 'mpp_per_request' && config?.price !== undefined) {
    return `${config.price} ${currency} per query ${appliedLabel}`.trim()
  }

  // Xendit: price per request
  if (policy.policy_type === 'xendit_per_request' && config?.price_per_request !== undefined) {
    return `${config.price_per_request} ${currency} per request ${appliedLabel}`.trim()
  }

  // Per-document (MPP and Xendit share the field name).
  if (
    (policy.policy_type === 'mpp_per_document' ||
      policy.policy_type === 'xendit_per_document') &&
    config?.price_per_document !== undefined
  ) {
    return `${config.price_per_document} ${currency} per document ${appliedLabel}`.trim()
  }

  return 'Pricing rule configured'
}

// ── Transactions state ──
const txnLoading = ref(false)
const txnEmailFilter = ref('')
const mppTransactions = ref<TransactionResponse[]>([])
const ledgerEntries = ref<LedgerEntryResponse[]>([])

const filteredMppTransactions = computed(() => {
  const filter = txnEmailFilter.value.toLowerCase().trim()
  if (!filter) return mppTransactions.value
  return mppTransactions.value.filter((t) => t.sender_email.toLowerCase().includes(filter))
})

const filteredLedgerEntries = computed(() => {
  const filter = txnEmailFilter.value.toLowerCase().trim()
  if (!filter) return ledgerEntries.value
  return ledgerEntries.value.filter((e) => e.user_email.toLowerCase().includes(filter))
})

const fetchTransactions = async () => {
  if (!endpoint.value) return
  txnLoading.value = true
  try {
    // lockedWallet derives from walletsById, which is populated asynchronously
    // in onMounted. Without this await, clicking the Transactions tab before
    // the wallet list lands would see lockedWallet=null and short-circuit to
    // an empty state until the user hit Refresh.
    await ensureWallets()
    const wallet = lockedWallet.value
    if (!wallet) {
      // No payment policy on this endpoint — nothing to fetch.
      mppTransactions.value = []
      ledgerEntries.value = []
      return
    }

    if (wallet.wallet_type === 'mpp') {
      try {
        mppTransactions.value = await walletsApi.getMppTransactions(wallet.id)
      } catch {
        mppTransactions.value = []
      }
      ledgerEntries.value = []
    } else if (wallet.wallet_type === 'xendit') {
      try {
        const page = await paymentsApi.listEndpointTransactions(endpoint.value.id)
        ledgerEntries.value = page.items
      } catch {
        ledgerEntries.value = []
      }
      mppTransactions.value = []
    }
  } finally {
    txnLoading.value = false
  }
}

const getTotalPoliciesCount = () => {
  return endpoint.value?.policies?.length || 0
}

// Get endpoint type based on what resources it has
const getEndpointType = computed(() => {
  if (!endpoint.value) return 'Unknown'

  const hasDataset = !!endpoint.value.dataset
  const hasModel = !!endpoint.value.model

  if (hasDataset) return 'Data Endpoint'
  if (hasModel) return 'AI Model Endpoint'
  return 'Unknown'
})

// Get response type from API data
const getResponseType = computed(() => {
  if (!endpoint.value?.response_type) return 'Unknown'

  switch (endpoint.value.response_type) {
    case 'raw':
      return 'Search & Quote'
    case 'summary':
      return 'AI Assistant'
    case 'both':
      return 'Search + AI'
    default:
      return endpoint.value.response_type
  }
})

// Get pricing range from pricing policies
const getPricingRange = computed(() => {
  const pricingPolicies = getPricingPolicies()

  if (pricingPolicies.length === 0) {
    return '$0.00/request'
  }

  const prices = pricingPolicies
    .map((policy) => policy.configuration?.price)
    .filter((price): price is number => typeof price === 'number')
    .sort((a, b) => a - b)

  if (prices.length === 0) {
    return '$0.00/request'
  }

  const minPrice = prices[0]!
  const maxPrice = prices[prices.length - 1]!

  if (minPrice === maxPrice) {
    return `$${formatPrice(minPrice)}/request`
  }

  return `$${formatPrice(minPrice)} - $${formatPrice(maxPrice)}/request`
})

const deleteEndpoint = async () => {
  if (!endpoint.value?.slug || isDeleting.value) return

  isDeleting.value = true
  try {
    // Unpublish from SyftHub first if published
    if (endpoint.value.published) {
      try {
        await endpointsApi.unpublish(endpoint.value.slug)
      } catch (unpublishError) {
        console.error('Failed to unpublish endpoint:', unpublishError)
        toast.error('Failed to remove endpoint from SyftHub. Please try again.')
        isDeleting.value = false
        return
      }
    }

    // Call the delete API
    await endpointsApi.delete(endpoint.value.slug)

    toast.success('Endpoint deleted successfully')

    // Close dialog and navigate away
    showDeleteDialog.value = false
    router.push('/endpoints')
  } catch (error) {
    console.error('Failed to delete endpoint:', error)
    toast.error('Failed to delete endpoint. Please try again.')
  } finally {
    isDeleting.value = false
  }
}

// Policy deletion functions
const handleDeletePolicy = (policyId: string, policyName: string) => {
  policyToDelete.value = { id: policyId, name: policyName }
  showDeletePolicyDialog.value = true
}

const cancelDeletePolicy = () => {
  showDeletePolicyDialog.value = false
  policyToDelete.value = null
}

const confirmDeletePolicy = async () => {
  if (!policyToDelete.value || !endpoint.value) return

  try {
    // Call the delete policy API
    await policiesApi.delete(policyToDelete.value.id)

    // Remove from local state immediately for better UX
    if (endpoint.value.policies) {
      endpoint.value.policies = endpoint.value.policies.filter(
        (p) => p.id !== policyToDelete.value!.id,
      )
    }

    showDeletePolicyDialog.value = false
    policyToDelete.value = null

    // Publish changes to marketplace
    await publishToMarketplace()
  } catch (error) {
    console.error('Failed to delete policy:', error)
    // TODO: Show error toast/notification
  }
}

// Handle pricing rule created from AddPricingRuleDialog.
// Dialog already resolved the wallet; we just create the policy and refresh.
const handlePricingCreated = async (payload: {
  walletId: string
  walletType: string
  policyType:
    | 'mpp_per_request'
    | 'xendit_per_request'
    | 'mpp_per_document'
    | 'xendit_per_document'
  name: string
  config: Record<string, unknown>
}) => {
  if (!endpoint.value?.id) return

  const ruleIndex = getPricingPolicies().length + 1
  const policyLabel = payload.policyType.startsWith('mpp_') ? 'MPP' : 'Xendit'
  const policyName = payload.name || `${endpoint.value.name} ${policyLabel} Rule #${ruleIndex}`

  try {
    const newPolicy = await policiesApi.create({
      name: policyName,
      policy_type: payload.policyType,
      configuration: payload.config,
      endpoint_id: endpoint.value.id,
      wallet_id: payload.walletId,
    })

    if (endpoint.value.policies) {
      endpoint.value.policies.push({
        id: newPolicy.id,
        name: newPolicy.name,
        policy_type: newPolicy.policy_type,
        configuration: newPolicy.configuration,
        wallet_id: payload.walletId,
      } as (typeof endpoint.value.policies)[number])
    }

    toast.success('Pricing rule added')
    await publishToMarketplace()
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to create pricing policy'
    toast.error(message)
  }
}

// Publish endpoint changes to marketplace
const publishToMarketplace = async () => {
  if (!endpoint.value?.slug) return

  try {
    await endpointsApi.publish(endpoint.value.slug, {
      publish_to_all_marketplaces: true,
    })
  } catch (err) {
    console.error('Failed to publish to marketplace:', err)
  }
}

// Add policy handler
const handleAddPolicy = async (payload: {
  policyType: PolicyTypeId
  formData: Record<string, unknown>
}) => {
  if (!endpoint.value?.id || !endpoint.value?.name) return

  const { policyType, formData } = payload

  // Calculate the correct rule index based on existing policies of this type
  // Map frontend policy type to backend policy type for counting
  const backendPolicyType = policyType === 'pricing' ? 'mpp_per_request' : policyType
  const existingPoliciesOfType =
    endpoint.value.policies?.filter((p) => p.policy_type === backendPolicyType) || []
  const ruleIndex = existingPoliciesOfType.length + 1

  try {
    // Create the policy using the composable
    const newPolicy = await createPolicy(
      policyType,
      formData as unknown as PolicyFormData,
      endpoint.value.id,
      endpoint.value.name,
      ruleIndex,
    )

    // Add the new policy to the local state immediately for better UX
    if (endpoint.value.policies) {
      endpoint.value.policies.push({
        id: newPolicy.id,
        name: newPolicy.name,
        policy_type: newPolicy.policy_type,
        configuration: newPolicy.configuration,
      })
    }

    // Close the dialog
    showAddPolicyDialog.value = false

    // Publish changes to marketplace
    await publishToMarketplace()
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Failed to create policy'
    toast.error(message)
    console.error('Failed to create policy:', error)
  }
}

onMounted(async () => {
  const endpointSlug = route.params.slug as string
  loading.value = true
  error.value = false

  // Wallet lookup table — populated in parallel with endpoint fetch.
  // Used by pricing-policy display and the add-pricing dialog lock logic.
  // The cached promise lets fetchTransactions() await this on tab activation.
  ensureWallets()

  try {
    // Fetch the endpoint details directly from the API
    const response = await endpointsApi.get(endpointSlug)
    endpoint.value = response

    // Fetch ingestion data if endpoint has a dataset
    if (response.dataset?.id) {
      try {
        const [ingestionResponse, allJobs] = await Promise.all([
          ingestionApi.getStatus(response.dataset.id),
          fetchAllIngestionJobs(response.dataset.id),
        ])
        ingestionStatus.value = ingestionResponse
        ingestionJobs.value = {
          jobs: allJobs,
          total: allJobs.length,
          limit: allJobs.length,
          offset: 0,
        }
      } catch (ingestionErr) {
        console.error('Failed to fetch ingestion data:', ingestionErr)
      }
    }
  } catch (err) {
    console.error('Failed to fetch endpoint:', err)
    error.value = true
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.markdown-content :deep(.md-editor) {
  background-color: transparent !important;
}

.markdown-content :deep(*) {
  word-wrap: break-word;
  overflow-wrap: break-word;
  hyphens: auto;
  line-height: 1.6;
}

.markdown-content :deep(p) {
  margin-bottom: 1rem;
  word-break: normal;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  word-break: normal;
  hyphens: none;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 1.5rem;
}

.markdown-content :deep(li) {
  margin-bottom: 0.5rem;
  word-break: normal;
}
</style>
