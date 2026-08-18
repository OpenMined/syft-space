<template>
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10 lg:py-12">
    <!-- Breadcrumb Navigation -->
    <nav class="flex mb-6" aria-label="Breadcrumb">
      <ol class="flex items-center space-x-2">
        <li>
          <router-link
            to="/endpoints"
            class="text-muted-foreground hover:text-foreground body-sm font-medium flex items-center transition-colors"
          >
            <Server class="h-4 w-4 mr-2" />
            APIs
          </router-link>
        </li>
        <li class="flex items-center">
          <ChevronRight class="h-4 w-4 text-muted-foreground mx-3" />
          <span class="text-foreground body-sm font-medium">{{
            endpoint?.name || 'Loading...'
          }}</span>
          <button
            v-if="endpoint?.slug"
            type="button"
            class="ml-2 inline-flex items-center justify-center h-6 w-6 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            :aria-label="slugCopied ? 'Copied' : 'Copy slug'"
            @click="copySlug"
          >
            <Check v-if="slugCopied" class="h-3.5 w-3.5 text-success" />
            <Copy v-else class="h-3.5 w-3.5" />
          </button>
        </li>
      </ol>
    </nav>

    <!-- Loading State -->
    <div v-if="loading" class="space-y-6 animate-pulse">
      <!-- Header Skeleton -->
      <div class="border-b border-border/50 pb-8 mb-2">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-start gap-4 flex-1">
            <div class="w-14 h-14 bg-muted rounded-lg"></div>
            <div class="space-y-3 flex-1">
              <div class="h-8 bg-muted rounded w-56"></div>
              <div class="h-5 bg-muted rounded w-80"></div>
              <div class="h-5 bg-muted rounded w-96"></div>
              <div class="flex gap-2">
                <div class="h-6 bg-muted rounded w-16"></div>
                <div class="h-6 bg-muted rounded w-20"></div>
                <div class="h-6 bg-muted rounded w-14"></div>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <div class="h-10 bg-muted rounded w-32"></div>
            <div class="h-10 bg-muted rounded w-20"></div>
            <div class="h-10 bg-muted rounded w-10"></div>
          </div>
        </div>
      </div>

      <!-- Tabs Skeleton -->
      <div class="h-10 border-b border-border/50 flex items-center gap-6 px-2">
        <div class="h-4 bg-muted rounded w-20"></div>
        <div class="h-4 bg-muted rounded w-20"></div>
        <div class="h-4 bg-muted rounded w-24"></div>
      </div>

      <!-- Content Skeleton -->
      <div class="space-y-6 pt-4">
        <div class="border border-border/50 rounded-lg p-5">
          <div class="h-6 bg-muted rounded w-32 mb-4"></div>
          <div class="space-y-2">
            <div class="h-4 bg-muted rounded w-full"></div>
            <div class="h-4 bg-muted rounded w-5/6"></div>
            <div class="h-4 bg-muted rounded w-4/6"></div>
          </div>
        </div>
        <div class="border border-border/50 rounded-lg p-5">
          <div class="h-6 bg-muted rounded w-36 mb-4"></div>
          <div class="space-y-3">
            <div
              v-for="i in 2"
              :key="`path-${i}`"
              class="p-3 bg-muted/50 border border-border rounded-lg"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="flex-1 space-y-2">
                  <div class="h-4 bg-muted rounded w-64"></div>
                  <div class="h-3 bg-muted rounded w-40"></div>
                </div>
                <div class="h-5 bg-muted rounded w-20"></div>
              </div>
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
      <h3 class="heading-3 text-destructive mb-2">Resource not found</h3>
      <p class="text-destructive mb-4">
        The resource you're looking for doesn't exist or has been deleted.
      </p>
      <Button @click="$router.push('/endpoints')" variant="outline"> Back to APIs </Button>
    </div>

    <!-- Main Content -->
    <div v-else-if="endpoint" class="space-y-6">
      <!-- Header Section -->
      <header class="border-b border-border/50 pb-6">
        <div class="flex items-start justify-between gap-4">
          <!-- Identity block -->
          <div class="flex items-start gap-4 min-w-0 flex-1">
            <div class="p-3 rounded-lg bg-primary/10 shrink-0">
              <Server class="h-6 w-6 text-primary" />
            </div>
            <div class="min-w-0 flex-1 space-y-2">
              <h1 class="heading-2 text-foreground">{{ endpoint.name }}</h1>
              <p v-if="endpoint.summary" class="body-base text-muted-foreground">
                {{ endpoint.summary }}
              </p>

              <!-- Meta row -->
              <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm pt-1">
                <span class="inline-flex items-center gap-1.5">
                  <span
                    :class="[
                      'inline-block w-2 h-2 rounded-full',
                      endpoint.published ? 'bg-success animate-pulse' : 'bg-muted-foreground/60',
                    ]"
                  ></span>
                  <span
                    :class="
                      endpoint.published ? 'text-success font-medium' : 'text-muted-foreground'
                    "
                  >
                    {{ endpoint.published ? 'Published' : 'Offline' }}
                  </span>
                </span>

                <span class="text-muted-foreground/60">·</span>
                <span class="text-muted-foreground">{{ getEndpointType }}</span>

                <template v-if="endpoint.dataset">
                  <span class="text-muted-foreground/60">·</span>
                  <router-link
                    :to="{ name: 'dataset-detail', params: { slug: endpoint.dataset.name } }"
                    class="text-primary hover:text-primary/80 hover:underline font-medium"
                  >
                    {{ endpoint.dataset.name }}
                  </router-link>
                </template>

                <template v-if="endpoint.model">
                  <span class="text-muted-foreground/60">·</span>
                  <router-link
                    :to="{ name: 'model-detail', params: { slug: endpoint.model.name } }"
                    class="text-primary hover:text-primary/80 hover:underline font-medium"
                  >
                    {{ endpoint.model.name }}
                  </router-link>
                </template>

                <template v-for="entry in pricingBreakdown" :key="entry.unit">
                  <span class="text-muted-foreground/60">·</span>
                  <span class="text-muted-foreground">{{ entry.label }}</span>
                </template>
              </div>

              <!-- Tags row -->
              <div v-if="allTags.length" class="flex flex-wrap gap-1.5 pt-1">
                <Badge
                  v-for="tag in allTags"
                  :key="tag"
                  variant="outline"
                  class="font-normal text-muted-foreground"
                >
                  {{ tag }}
                </Badge>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-2 shrink-0">
            <Button
              v-if="syftHubUrl"
              as="a"
              :href="syftHubUrl"
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink class="h-4 w-4 mr-2" />
              View on SyftHub
            </Button>
            <Button variant="outline" @click="openEditDialog">
              <Pencil class="h-4 w-4 mr-2" />
              Edit
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger as-child>
                <Button variant="ghost" size="icon" aria-label="More actions">
                  <MoreVertical class="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" class="w-44">
                <DropdownMenuItem v-if="!endpoint.published" @select="publishEndpoint">
                  <Send class="h-4 w-4 mr-2" />
                  Publish
                </DropdownMenuItem>
                <DropdownMenuItem
                  class="text-destructive focus:text-destructive focus:bg-destructive/10"
                  @select="openDeleteDialog"
                >
                  <Trash2 class="h-4 w-4 mr-2" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      <!-- Tabs Section -->
      <Tabs v-model="activeTab" class="space-y-0">
        <TabsList
          class="h-auto bg-transparent rounded-none p-0 w-full justify-start gap-2 border-b border-border/50"
        >
          <TabsTrigger
            value="overview"
            class="flex-none inline-flex items-center gap-2 h-10 px-3 rounded-none border-0 border-b-2 border-b-transparent bg-transparent shadow-none text-muted-foreground hover:text-foreground data-[state=active]:bg-transparent dark:data-[state=active]:bg-transparent data-[state=active]:text-primary dark:data-[state=active]:text-primary data-[state=active]:border-b-primary data-[state=active]:shadow-none -mb-px"
          >
            <Layout class="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger
            value="access"
            class="flex-none inline-flex items-center gap-2 h-10 px-3 rounded-none border-0 border-b-2 border-b-transparent bg-transparent shadow-none text-muted-foreground hover:text-foreground data-[state=active]:bg-transparent dark:data-[state=active]:bg-transparent data-[state=active]:text-primary dark:data-[state=active]:text-primary data-[state=active]:border-b-primary data-[state=active]:shadow-none -mb-px"
          >
            <Shield class="h-4 w-4" />
            Policies
            <Badge
              v-if="totalPoliciesCount > 0"
              variant="secondary"
              class="ml-1 h-5 min-w-[1.25rem] px-1.5 text-xs font-medium bg-primary/15 text-primary border-0"
            >
              {{ totalPoliciesCount }}
            </Badge>
          </TabsTrigger>
          <TabsTrigger
            value="transactions"
            class="flex-none inline-flex items-center gap-2 h-10 px-3 rounded-none border-0 border-b-2 border-b-transparent bg-transparent shadow-none text-muted-foreground hover:text-foreground data-[state=active]:bg-transparent dark:data-[state=active]:bg-transparent data-[state=active]:text-primary dark:data-[state=active]:text-primary data-[state=active]:border-b-primary data-[state=active]:shadow-none -mb-px"
          >
            <Receipt class="h-4 w-4" />
            Transactions
            <Badge
              v-if="totalTransactionsForBadge > 0"
              variant="secondary"
              class="ml-1 h-5 min-w-[1.25rem] px-1.5 text-xs font-medium bg-primary/15 text-primary border-0"
            >
              {{ totalTransactionsForBadge }}
            </Badge>
          </TabsTrigger>
        </TabsList>

        <!-- Overview Tab -->
        <TabsContent value="overview" class="space-y-6 pt-6 mt-0">
          <!-- Description -->
          <section class="border border-border/50 rounded-lg p-5">
            <h2 class="heading-3 text-foreground mb-4 flex items-center gap-2">
              <FileText class="h-5 w-5 text-muted-foreground" />
              {{ hasDescription ? 'Description' : 'No description yet' }}
            </h2>

            <div v-if="hasDescription" class="prose prose-sm max-w-none text-muted-foreground">
              <div class="markdown-content">
                <MdPreview
                  :model-value="endpoint.description"
                  :theme="isDark ? 'dark' : 'light'"
                  :show-code-row-number="false"
                />
              </div>
            </div>
            <div v-else class="space-y-4">
              <p class="body-sm text-muted-foreground">
                Help consumers understand what this API does, what data it covers, and how to use
                it.
              </p>
              <Button variant="outline" size="sm" @click="openEditDialog">
                <Pencil class="h-4 w-4 mr-2" />
                Add description
              </Button>
            </div>
          </section>

          <!-- Watched Paths (Data APIs only) -->
          <section
            v-if="endpoint.dataset && getWatchedPaths.length > 0"
            class="border border-border/50 rounded-lg p-5"
          >
            <h2 class="heading-3 text-foreground mb-4 flex items-center gap-2">
              <Database class="h-5 w-5 text-muted-foreground" />
              Watched Paths
            </h2>
            <div class="space-y-3">
              <div class="max-h-96 space-y-3 overflow-y-auto pr-1" @scroll="onWatchedPathsScroll">
                <div
                  v-for="path in getWatchedPaths"
                  :key="path.id"
                  class="p-3 bg-muted/50 border border-border rounded-lg"
                >
                  <div class="flex items-start justify-between gap-4">
                    <div class="flex-1 min-w-0">
                      <div class="flex items-baseline flex-wrap gap-x-2">
                        <code class="body-sm font-medium text-foreground font-mono break-all">
                          {{ path.path }}
                        </code>
                        <span class="body-sm text-muted-foreground"
                          >{{ path.fileCount }} files</span
                        >
                      </div>
                      <p v-if="path.description" class="body-sm text-muted-foreground mt-1">
                        {{ path.description }}
                      </p>
                    </div>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger as-child>
                          <span
                            class="inline-flex items-center gap-1.5 text-xs font-medium shrink-0 cursor-help"
                          >
                            <span
                              :class="[
                                'inline-block w-2 h-2 rounded-full',
                                path.status === 'indexed'
                                  ? 'bg-success'
                                  : path.status === 'processing'
                                    ? 'bg-primary'
                                    : path.status === 'queued'
                                      ? 'bg-warning'
                                      : path.status === 'errored'
                                        ? 'bg-destructive'
                                        : 'bg-muted-foreground/50',
                              ]"
                            ></span>
                            <span
                              :class="
                                path.status === 'indexed'
                                  ? 'text-success'
                                  : path.status === 'processing'
                                    ? 'text-primary'
                                    : path.status === 'queued'
                                      ? 'text-warning'
                                      : path.status === 'errored'
                                        ? 'text-destructive'
                                        : 'text-muted-foreground'
                              "
                            >
                              {{ getStatusShortLabel(path.status) }}
                            </span>
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>{{ getStatusLabel(path.status) }}</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                </div>
              </div>

              <div
                v-if="hasMoreWatchedPaths"
                class="pt-1 text-center text-xs text-muted-foreground"
              >
                {{
                  datasetSelectionLoading
                    ? 'Loading…'
                    : `Showing ${datasetSelectionItems.length} of ${datasetSelectionTotal}`
                }}
              </div>
            </div>
          </section>
        </TabsContent>

        <!-- Access Control Tab -->
        <TabsContent value="access" class="space-y-6 pt-6 mt-0">
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
                  <span class="body-sm font-medium text-foreground">{{ totalPoliciesCount }}</span>
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
        <TabsContent value="transactions" class="space-y-4 pt-6 mt-0">
          <!-- Stats summary -->
          <div
            class="border border-border rounded-lg grid grid-cols-1 md:grid-cols-4 divide-y md:divide-y-0 md:divide-x divide-border bg-card/40"
          >
            <div class="p-4">
              <p class="text-xs text-muted-foreground mb-1.5">Total received</p>
              <p class="text-xl font-semibold text-foreground">{{ statTotalReceived }}</p>
            </div>
            <div class="p-4">
              <p class="text-xs text-muted-foreground mb-1.5">Transactions</p>
              <p class="text-xl font-semibold text-foreground">{{ statTransactionCount }}</p>
            </div>
            <div class="p-4">
              <p class="text-xs text-muted-foreground mb-1.5">Unique users</p>
              <p class="text-xl font-semibold text-foreground">{{ statUniqueUsers }}</p>
            </div>
            <div class="p-4">
              <p class="text-xs text-muted-foreground mb-1.5">Period</p>
              <Select v-model="txnPeriod">
                <SelectTrigger class="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="7">Last 7 days</SelectItem>
                  <SelectItem value="30">Last 30 days</SelectItem>
                  <SelectItem value="90">Last 90 days</SelectItem>
                  <SelectItem value="all">All time</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <!-- Filter bar -->
          <div class="flex flex-wrap items-center gap-3">
            <Input
              v-model="txnEmailFilter"
              placeholder="Filter by email..."
              class="h-9 max-w-sm flex-1 min-w-[200px]"
            />
            <Select v-if="walletUsesLedger" v-model="txnStatusFilter">
              <SelectTrigger class="h-9 w-40">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="debit">Debit</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" @click="fetchTransactions" :disabled="txnLoading">
              <Loader2 v-if="txnLoading" class="h-4 w-4 mr-2 animate-spin" />
              <RotateCw v-else class="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>

          <!-- No-wallet empty state -->
          <Card
            v-if="!txnLoading && !lockedWallet"
            class="bg-card/80 backdrop-blur-sm border border-border shadow-sm"
          >
            <CardContent class="py-10 text-center">
              <p class="text-sm text-muted-foreground">
                No pricing configured — no transactions recorded for this endpoint.
              </p>
            </CardContent>
          </Card>

          <!-- MPP payments -->
          <Card
            v-else-if="lockedWallet?.wallet_type === 'mpp'"
            class="bg-card/80 backdrop-blur-sm border border-border shadow-sm"
          >
            <CardHeader class="pb-3">
              <CardTitle class="text-base flex items-center gap-2">
                <Zap class="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                MPP payments
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Info class="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>Marketplace token transactions for this endpoint</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
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

          <!-- Ledger payments (gateway + managed wallets) -->
          <Card
            v-else-if="walletUsesLedger"
            class="bg-card/80 backdrop-blur-sm border border-border shadow-sm"
          >
            <CardHeader class="pb-3">
              <CardTitle class="text-base flex items-center gap-2">
                <CreditCard class="h-4 w-4 text-violet-600 dark:text-violet-400" />
                {{ lockedWallet?.managed ? 'Credit payments' : 'Gateway payments' }}
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <Info class="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>
                        {{
                          lockedWallet?.managed
                            ? 'Credits charged to users of this endpoint'
                            : 'Real-money transactions processed via payment gateway'
                        }}
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
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
                    <p class="text-xs text-muted-foreground flex items-center gap-1.5 flex-wrap">
                      <span :title="formatLocalDateTime(entry.created_at)">{{
                        formatTimeAgo(entry.created_at)
                      }}</span>
                      <span aria-hidden="true">&middot;</span>
                      <span>{{ entry.type }}</span>
                      <span aria-hidden="true">&middot;</span>
                      <span>{{ formatChargeBreakdown(entry) }}</span>
                      <span aria-hidden="true">&middot;</span>
                      <code
                        class="font-mono text-[10px] bg-muted px-1 py-0.5 rounded"
                        :title="`Transaction ID: ${entry.transaction_id}`"
                      >
                        {{ entry.transaction_id.slice(0, 8) }}
                      </code>
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
        <DialogTitle class="text-destructive">Delete resource</DialogTitle>
        <DialogDescription>
          This will permanently delete this resource and remove it from SyftHub. This action cannot
          be undone.
        </DialogDescription>
      </DialogHeader>
      <div class="space-y-2">
        <Label class="gap-1">
          Type <span class="font-semibold text-foreground">{{ endpoint?.name }}</span> to confirm
        </Label>
        <Input v-model="deleteNameConfirm" :placeholder="endpoint?.name || 'api-name'" />
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
          <span v-else>Delete</span>
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
    :endpoint-has-dataset="!!endpoint?.dataset"
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
  Database,
  Plus,
  ExternalLink,
  Pencil,
  Receipt,
  Zap,
  CreditCard,
  Loader2,
  MoreVertical,
  Copy,
  Check,
  Info,
  RotateCw,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
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

import type { PaymentPolicyType, PolicyTypeId } from '@/config/policyTypes'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { useEndpointsStore } from '@/stores/endpoints'
import { toast } from 'vue-sonner'
import { ingestionApi } from '@/api/endpoints/ingestion'
import { datasetsApi } from '@/api/endpoints/datasets'
import { policiesApi } from '@/api/policies/policies'
import { walletsApi } from '@/api/endpoints/wallets'
import { paymentsApi } from '@/api/endpoints/payments'
import type { LedgerEntryResponse, TransactionResponse, WalletListItem } from '@/api/types'
import {
  formatCurrencyAmount,
  formatLocalDateTime,
  formatPrice,
  formatTimeAgo,
} from '@/lib/formatters'
import EditEndpointDialog from '@/components/EditEndpointDialog.vue'
import { useUserStore } from '@/stores/user'
import { usePolicyCreation } from '@/composables/usePolicyCreation'
import type { PolicyFormData } from '@/composables/usePolicyCreation'
import type { EndpointResponse } from '@/api/types'
import type {
  IngestionStatusResponse,
  IngestionJobListResponse,
  SelectedItemResponse,
} from '@/api/types'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'

const route = useRoute()
const router = useRouter()
const endpointsStore = useEndpointsStore()
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
const slugCopied = ref(false)

// The attached dataset's selection is no longer inlined in the endpoint
// payload — fetch and page it here, keyed by the dataset name.
const SELECTION_PAGE_SIZE = 10
const datasetSelectionItems = ref<SelectedItemResponse[]>([])
const datasetSelectionTotal = ref(0)
const datasetSelectionLoading = ref(false)

const { createPolicy, isCreating: policyCreating } = usePolicyCreation()

const syftHubUrl = computed(() =>
  endpoint.value?.slug ? userStore.getEndpointUrlInMarketplace(endpoint.value.slug) : null,
)

const endpointForEdit = computed(() => {
  if (!endpoint.value) return null
  return {
    slug: endpoint.value.slug,
    name: endpoint.value.name,
    summary: endpoint.value.summary,
    description: endpoint.value.description,
    model_id: endpoint.value.model_id ?? endpoint.value.model?.id,
    system_prompt: endpoint.value.system_prompt,
  }
})

const hasDescription = computed(
  () => !!(endpoint.value?.description && endpoint.value.description.trim()),
)

const openEditDialog = () => {
  showEditDialog.value = true
}

const openDeleteDialog = () => {
  deleteNameConfirm.value = ''
  showDeleteDialog.value = true
}

const handleEditSaved = (data: {
  summary: string
  description: string
  system_prompt?: string | null
}) => {
  if (endpoint.value) {
    endpoint.value.summary = data.summary
    endpoint.value.description = data.description
    if (data.system_prompt !== undefined) {
      endpoint.value.system_prompt = data.system_prompt
    }
  }
}

const copySlug = async () => {
  if (!endpoint.value?.slug) return
  try {
    await navigator.clipboard.writeText(endpoint.value.slug)
    slugCopied.value = true
    setTimeout(() => {
      slugCopied.value = false
    }, 1500)
  } catch {
    toast.error('Failed to copy')
  }
}

const allTags = computed(() => {
  if (!endpoint.value?.tags) return []
  return endpoint.value.tags
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
    .map((t) => t.replace(/^(language|domain):/, ''))
})

const watchedPathStats = computed(() => {
  const stats = new Map<string, { fileCount: number; counts: Record<string, number> }>()
  for (const { item_id } of datasetSelectionItems.value) {
    stats.set(item_id, { fileCount: 0, counts: {} })
  }
  for (const job of ingestionJobs.value?.jobs ?? []) {
    for (const [path, entry] of stats) {
      if (job.external_id.startsWith(path)) {
        entry.fileCount += 1
        entry.counts[job.status] = (entry.counts[job.status] || 0) + 1
      }
    }
  }
  return stats
})

const statusFromCounts = (counts: Record<string, number>): string => {
  if ((counts['in_progress'] ?? 0) > 0) return 'processing'
  if ((counts['pending'] ?? 0) > 0) return 'queued'
  if ((counts['failed'] ?? 0) > 0) return 'errored'
  if ((counts['completed'] ?? 0) > 0) return 'indexed'
  return 'unknown'
}

const getWatchedPaths = computed(() => {
  if (!endpoint.value?.dataset) return []

  return datasetSelectionItems.value.map((item) => {
    const entry = watchedPathStats.value.get(item.item_id)
    return {
      id: item.item_id,
      path: item.item_id,
      description: item.description || 'Selected for ingestion',
      fileCount: entry?.fileCount ?? 0,
      status: entry && entry.fileCount > 0 ? statusFromCounts(entry.counts) : 'unknown',
    }
  })
})

const hasMoreWatchedPaths = computed(
  () => datasetSelectionItems.value.length < datasetSelectionTotal.value,
)

// Fetch the attached dataset's selection page-by-page.
const loadDatasetSelection = async (datasetName: string, reset = false) => {
  const offset = reset ? 0 : datasetSelectionItems.value.length
  datasetSelectionLoading.value = true
  try {
    const page = await datasetsApi.getSelection(datasetName, SELECTION_PAGE_SIZE, offset)
    datasetSelectionItems.value = reset
      ? page.items
      : [...datasetSelectionItems.value, ...page.items]
    datasetSelectionTotal.value = page.total
  } catch (err) {
    console.error('Failed to load dataset selection:', err)
  } finally {
    datasetSelectionLoading.value = false
  }
}

// Auto-load the next page when the list is scrolled near the bottom.
const onWatchedPathsScroll = (e: Event) => {
  const el = e.target as HTMLElement
  const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48
  const name = endpoint.value?.dataset?.name
  if (name && nearBottom && hasMoreWatchedPaths.value && !datasetSelectionLoading.value) {
    loadDatasetSelection(name, false)
  }
}

// Fetch all ingestion jobs across all pages
const fetchAllIngestionJobs = async (datasetId: string) => {
  const allJobs = []
  let offset = 0
  const limit = 100

  while (true) {
    const response = await ingestionApi.listJobs(datasetId, undefined, limit, offset)
    allJobs.push(...response.jobs)

    if (response.jobs.length < limit) {
      break
    }

    offset += limit
  }

  return allJobs
}

const STATUS_LABELS: Record<string, { short: string; long: string }> = {
  indexed: { short: 'Indexed', long: 'All files processed successfully' },
  processing: { short: 'Processing', long: 'Files are currently being processed' },
  queued: { short: 'Queued', long: 'Files are queued for processing' },
  errored: { short: 'Errored', long: 'Some files failed to process' },
  unknown: { short: 'Unknown', long: 'Status unknown' },
}

const getStatusEntry = (status: string) => STATUS_LABELS[status] ?? STATUS_LABELS['unknown']!
const getStatusLabel = (status: string) => getStatusEntry(status).long
const getStatusShortLabel = (status: string) => getStatusEntry(status).short

const getAuthorizationPolicies = () => {
  return endpoint.value?.policies?.filter((p) => p.policy_type === 'access') || []
}

const getRateLimitPolicies = () => {
  return endpoint.value?.policies?.filter((p) => p.policy_type === 'rate_limit') || []
}

const walletsById = ref<Record<string, WalletListItem>>({})

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
      (p) => p.policy_type.endsWith('_per_request') || p.policy_type.endsWith('_per_document'),
    ) || []
  )
}

const lockedWallet = computed<WalletListItem | null>(() => {
  const first = getPricingPolicies()[0] as
    | { wallet_id?: string; configuration?: Record<string, unknown> }
    | undefined
  if (!first?.wallet_id) return null
  return walletsById.value[first.wallet_id] ?? null
})

const lockedWalletId = computed(() => lockedWallet.value?.id ?? null)

// Every wallet except MPP settles through the local ledger — gateway wallets
// via BalanceService, managed wallets via the recorded external journal.
// MPP transactions live on-chain and come from the marketplace instead.
const walletUsesLedger = computed(
  () => !!lockedWallet.value && lockedWallet.value.wallet_type !== 'mpp',
)

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

  if (config?.price === undefined) {
    return 'Pricing rule configured'
  }

  const unit = policy.policy_type.endsWith('_per_document') ? 'document' : 'request'
  return `${config.price} ${currency} per ${unit} ${appliedLabel}`.trim()
}

const txnLoading = ref(false)
const txnEmailFilter = ref('')
const txnPeriod = ref<'7' | '30' | '90' | 'all'>('30')
const txnStatusFilter = ref<'all' | 'debit' | 'cancelled'>('all')
const mppTransactions = ref<TransactionResponse[]>([])
const ledgerEntries = ref<LedgerEntryResponse[]>([])

const periodCutoffMs = computed(() => {
  if (txnPeriod.value === 'all') return null
  const days = parseInt(txnPeriod.value, 10)
  return Date.now() - days * 24 * 60 * 60 * 1000
})

const withinPeriod = (createdAt: string) => {
  const cutoff = periodCutoffMs.value
  if (cutoff === null) return true
  const ts = new Date(createdAt).getTime()
  if (Number.isNaN(ts)) return true
  return ts >= cutoff
}

const filteredMppTransactions = computed(() => {
  const emailFilter = txnEmailFilter.value.toLowerCase().trim()
  return mppTransactions.value.filter((t) => {
    if (!withinPeriod(t.created_at)) return false
    if (emailFilter && !t.sender_email.toLowerCase().includes(emailFilter)) return false
    return true
  })
})

const filteredLedgerEntries = computed(() => {
  const emailFilter = txnEmailFilter.value.toLowerCase().trim()
  return ledgerEntries.value.filter((e) => {
    if (!withinPeriod(e.created_at)) return false
    if (emailFilter && !e.user_email.toLowerCase().includes(emailFilter)) return false
    if (txnStatusFilter.value !== 'all' && e.type !== txnStatusFilter.value) return false
    return true
  })
})

const statTransactionCount = computed(() => {
  if (lockedWallet.value?.wallet_type === 'mpp') return filteredMppTransactions.value.length
  if (walletUsesLedger.value) return filteredLedgerEntries.value.length
  return 0
})

const statUniqueUsers = computed(() => {
  if (lockedWallet.value?.wallet_type === 'mpp') {
    return new Set(filteredMppTransactions.value.map((t) => t.sender_email)).size
  }
  if (walletUsesLedger.value) {
    return new Set(filteredLedgerEntries.value.map((e) => e.user_email)).size
  }
  return 0
})

const statTotalReceived = computed(() => {
  if (lockedWallet.value?.wallet_type === 'mpp') {
    const total = filteredMppTransactions.value.reduce((sum, t) => sum + Number(t.amount || 0), 0)
    const currency = lockedWallet.value.currency ?? 'USD'
    return `$${formatPrice(total)} ${currency}`
  }
  if (walletUsesLedger.value && lockedWallet.value) {
    const debits = filteredLedgerEntries.value.filter((e) => e.type === 'debit')
    const total = debits.reduce((sum, e) => sum + Number(e.amount || 0), 0)
    const currency =
      debits[0]?.currency ??
      filteredLedgerEntries.value[0]?.currency ??
      lockedWallet.value.currency ??
      'USD'
    return `$${formatPrice(total)} ${currency}`
  }
  return '$0.00'
})

const totalTransactionsForBadge = computed(
  () => mppTransactions.value.length + ledgerEntries.value.length,
)

const formatChargeBreakdown = (entry: LedgerEntryResponse): string => {
  const unit = entry.charge_quantity === 1 ? entry.charge_unit : `${entry.charge_unit}s`
  return `${entry.charge_quantity} ${unit}`
}

const fetchTransactions = async () => {
  if (!endpoint.value) return
  txnLoading.value = true
  try {
    await ensureWallets()
    const wallet = lockedWallet.value
    if (!wallet) {
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
    } else {
      // Gateway and managed wallets share the same ledger transactions
      // endpoint — every charge is journaled locally regardless of the rail.
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

const totalPoliciesCount = computed(() => endpoint.value?.policies?.length || 0)

const getEndpointType = computed(() => {
  if (!endpoint.value) return 'Unknown'

  const hasDataset = !!endpoint.value.dataset
  const hasModel = !!endpoint.value.model

  if (hasDataset) return 'Data API'
  if (hasModel) return 'AI Model API'
  return 'Unknown'
})

// Group pricing policies by charge unit (request, document, future: token…)
// and render one badge per unit. Currency comes from the linked wallet
// (all payment policies on an endpoint share one wallet by construction).
const pricingBreakdown = computed<Array<{ unit: string; label: string }>>(() => {
  const policies = getPricingPolicies()
  if (policies.length === 0) {
    return [{ unit: 'request', label: '$0.00/request' }]
  }

  const byUnit = new Map<string, number[]>()
  for (const policy of policies) {
    const unit =
      ((policy.configuration as Record<string, unknown>)?.unit_type as string | undefined) ??
      (policy.policy_type.endsWith('_per_document') ? 'document' : 'request')
    const price = (policy.configuration as Record<string, unknown>)?.price
    if (typeof price !== 'number') continue
    if (!byUnit.has(unit)) byUnit.set(unit, [])
    byUnit.get(unit)!.push(price)
  }

  const currency = lockedWallet.value?.currency ?? 'USD'

  return Array.from(byUnit.entries()).map(([unit, prices]) => {
    prices.sort((a, b) => a - b)
    const min = prices[0]!
    const max = prices[prices.length - 1]!
    const range =
      min === max
        ? formatCurrencyAmount(min, currency)
        : `${formatCurrencyAmount(min, currency)} - ${formatCurrencyAmount(max, currency)}`
    return { unit, label: `${range}/${unit}` }
  })
})

const deleteEndpoint = async () => {
  if (!endpoint.value?.slug || isDeleting.value) return

  isDeleting.value = true
  try {
    if (endpoint.value.published) {
      try {
        await endpointsApi.unpublish(endpoint.value.slug)
      } catch (unpublishError) {
        console.error('Failed to unpublish endpoint:', unpublishError)
        toast.error('Failed to remove from SyftHub. Please try again.')
        isDeleting.value = false
        return
      }
    }

    await endpointsApi.delete(endpoint.value.slug)
    endpointsStore.invalidate()

    toast.success('Resource deleted')

    showDeleteDialog.value = false
    router.push('/endpoints')
  } catch (error) {
    console.error('Failed to delete endpoint:', error)
    toast.error('Failed to delete. Please try again.')
  } finally {
    isDeleting.value = false
  }
}

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
    await policiesApi.delete(policyToDelete.value.id)

    if (endpoint.value.policies) {
      endpoint.value.policies = endpoint.value.policies.filter(
        (p) => p.id !== policyToDelete.value!.id,
      )
    }

    showDeletePolicyDialog.value = false
    policyToDelete.value = null

    await publishToMarketplace()
  } catch (error) {
    console.error('Failed to delete policy:', error)
  }
}

const handlePricingCreated = async (payload: {
  walletId: string
  walletType: string
  policyType: PaymentPolicyType
  name: string
  config: Record<string, unknown>
}) => {
  if (!endpoint.value?.id) return

  const ruleIndex = getPricingPolicies().length + 1
  const policyLabel = payload.policyType.startsWith('mpp_')
    ? 'MPP'
    : payload.policyType.startsWith('stripe_')
      ? 'Stripe'
      : payload.policyType.startsWith('cluster_')
        ? 'Credits'
        : 'Xendit'
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

const publishEndpoint = async () => {
  if (!endpoint.value?.slug || endpoint.value.published) return
  try {
    await endpointsApi.publish(endpoint.value.slug, {
      publish_to_all_marketplaces: true,
    })
    endpoint.value.published = true
    toast.success('Endpoint published')
  } catch (err) {
    console.error('Failed to publish endpoint:', err)
    toast.error('Failed to publish. Please try again.')
  }
}

const handleAddPolicy = async (payload: {
  policyType: PolicyTypeId
  formData: Record<string, unknown>
}) => {
  if (!endpoint.value?.id || !endpoint.value?.name) return

  const { policyType, formData } = payload

  const backendPolicyType = policyType === 'pricing' ? 'mpp_per_request' : policyType
  const existingPoliciesOfType =
    endpoint.value.policies?.filter((p) => p.policy_type === backendPolicyType) || []
  const ruleIndex = existingPoliciesOfType.length + 1

  try {
    const newPolicy = await createPolicy(
      policyType,
      formData as unknown as PolicyFormData,
      endpoint.value.id,
      endpoint.value.name,
      ruleIndex,
    )

    if (endpoint.value.policies) {
      endpoint.value.policies.push({
        id: newPolicy.id,
        name: newPolicy.name,
        policy_type: newPolicy.policy_type,
        configuration: newPolicy.configuration,
      })
    }

    showAddPolicyDialog.value = false

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

  ensureWallets()

  try {
    const response = await endpointsApi.get(endpointSlug)
    endpoint.value = response

    if (response.dataset?.id) {
      try {
        const [ingestionResponse, allJobs] = await Promise.all([
          ingestionApi.getStatus(response.dataset.id),
          fetchAllIngestionJobs(response.dataset.id),
          loadDatasetSelection(response.dataset.name, true),
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
