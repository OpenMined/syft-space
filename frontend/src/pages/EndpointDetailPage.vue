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
              <div v-for="i in 3" :key="`detail-${i}`" class="flex justify-between items-center py-1">
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
            <Button
              v-if="syftHubUrl"
              variant="outline"
              as="a"
              :href="syftHubUrl"
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink class="h-4 w-4 mr-2" />
              View on SyftHub
            </Button>
            <Button
              variant="outline"
              class="text-destructive border-destructive/20 hover:bg-destructive hover:text-destructive-foreground"
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
        </div>
      </div>

      <!-- Tabs Section -->
      <Tabs v-model="activeTab" class="space-y-4">
        <TabsList
          class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-2"
        >
          <TabsTrigger value="overview" class="flex items-center gap-2">
            <Layout class="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="access" class="flex items-center gap-2">
            <Shield class="h-4 w-4" />
            Access Control
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
                      preview-theme="default"
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
                      resetPolicyForm('access')
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
                      resetPolicyForm('rate_limit')
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
                <CardTitle class="flex items-center gap-2">
                  <DollarSign class="h-5 w-5 text-muted-foreground" />
                  Pricing
                </CardTitle>
                <CardDescription> Set pricing for endpoint usage </CardDescription>
              </CardHeader>
              <CardContent class="space-y-3 flex-1">
                <div v-if="getPricingPolicies().length === 0" class="text-sm text-muted-foreground">
                  No pricing policies configured
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
                          <template v-if="policy.configuration?.price !== undefined">
                            ${{ policy.configuration.price }} per query
                            <template
                              v-if="
                                Array.isArray(policy.configuration?.applied_to) &&
                                policy.configuration.applied_to.length > 0 &&
                                !(
                                  policy.configuration.applied_to.length === 1 &&
                                  policy.configuration.applied_to[0] === '*'
                                )
                              "
                            >
                              for {{ policy.configuration.applied_to.join(', ') }}</template
                            >
                            <template
                              v-else-if="
                                Array.isArray(policy.configuration?.applied_to) &&
                                policy.configuration.applied_to.length === 1 &&
                                policy.configuration.applied_to[0] === '*'
                              "
                            >
                              for all users</template
                            >
                          </template>
                          <template v-else> Pricing rule configured </template>
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
                      selectedPolicyType = 'pricing'
                      resetPolicyForm('pricing')
                      showAddPolicyDialog = true
                    }
                  "
                >
                  <Plus class="h-4 w-4 mr-2" />
                  Add Pricing Rule
                </Button>
              </CardFooter>
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
      </Tabs>
    </div>
  </div>

  <!-- Delete Confirmation Dialog -->
  <Dialog v-model:open="showDeleteDialog">
    <DialogContent class="sm:max-w-[600px]">
      <div class="space-y-4">
        <div>
          <h3 class="body-sm font-semibold text-destructive">Danger Zone</h3>
          <p class="body-sm text-muted-foreground mt-1">
            Permanently delete this endpoint and all associated data.
          </p>
        </div>
        <DialogHeader>
          <DialogTitle>Delete endpoint</DialogTitle>
          <DialogDescription>
            This action cannot be undone. Please type
            <span class="font-medium text-foreground"> {{ endpoint?.name }} </span>
            to confirm deletion.
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-2">
          <Label class="body-sm text-muted-foreground">Confirm name</Label>
          <Input v-model="deleteNameConfirm" :placeholder="endpoint?.name || 'endpoint-name'" />
          <p
            class="body-sm"
            :class="deleteNameConfirm === endpoint?.name ? 'text-success' : 'text-muted-foreground'"
          >
            {{
              deleteNameConfirm === endpoint?.name
                ? 'Name matches'
                : 'Enter the endpoint name exactly'
            }}
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" @click="showDeleteDialog = false" :disabled="isDeleting"
            >Cancel</Button
          >
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
      </div>
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

  <!-- Add Policy Dialog -->
  <Dialog v-model:open="showAddPolicyDialog">
    <DialogContent class="sm:max-w-[600px]">
      <DialogHeader>
        <DialogTitle>Add {{ getPolicyTypeLabel(selectedPolicyType) }} Rule</DialogTitle>
        <DialogDescription>
          Create a new
          {{ selectedPolicyType === 'access' ? 'authorization' : selectedPolicyType }} policy for
          this endpoint.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <!-- Authorization Policy Form -->
        <div v-if="selectedPolicyType === 'access'" class="space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Rule Type</Label>
              <Select v-model="authorizationForm.ruleType">
                <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                  <SelectValue placeholder="Select rule type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="allow" class="body-sm">Allow specific users</SelectItem>
                  <SelectItem value="deny" class="body-sm">Deny specific users</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Note</Label>
              <Input
                v-model="authorizationForm.note"
                placeholder="Optional description"
                class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground"
              />
            </div>
          </div>
          <div class="space-y-1">
            <Label class="body-sm text-muted-foreground font-medium">Users</Label>
            <Input
              v-model="authorizationForm.users"
              placeholder="user1@example.com, user2@example.com"
              class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground"
            />
            <p class="text-xs text-muted-foreground">
              Comma-separated list. Wildcard supported (e.g., *@company.com, *.edu,
              *@contractors.org)
            </p>
          </div>
        </div>

        <!-- Rate Limiter Policy Form -->
        <div v-if="selectedPolicyType === 'rate_limit'" class="space-y-4">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Limit</Label>
              <div class="flex">
                <Input
                  v-model="rateLimiterForm.limit"
                  type="number"
                  placeholder="100"
                  class="h-9 w-20 sm:w-24 rounded-l-lg rounded-r-none border-r-0 border-border bg-card body-sm"
                />
                <Select v-model="rateLimiterForm.windowUnit">
                  <SelectTrigger
                    class="h-9 rounded-r-lg rounded-l-none border-border bg-card body-sm min-w-0"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="second">requests per second</SelectItem>
                    <SelectItem value="minute">requests per minute</SelectItem>
                    <SelectItem value="hour">requests per hour</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Scope</Label>
              <Select v-model="rateLimiterForm.scope">
                <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="per user">For Each User</SelectItem>
                  <SelectItem value="global">For This Endpoint</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div class="space-y-1">
            <Label class="body-sm text-muted-foreground font-medium">Note</Label>
            <Input
              v-model="rateLimiterForm.note"
              placeholder="Optional description"
              class="h-9 rounded-lg border-border bg-card body-sm"
            />
          </div>
        </div>

        <!-- Pricing Policy Form -->
        <div v-if="selectedPolicyType === 'pricing'" class="space-y-4">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Price per query ($)</Label>
              <Input
                v-model="pricingForm.price"
                type="number"
                step="any"
                placeholder="0.01"
                class="h-9 rounded-lg border-border bg-card body-sm"
              />
            </div>
            <div class="space-y-1">
              <Label class="body-sm text-muted-foreground font-medium">Note</Label>
              <Input
                v-model="pricingForm.note"
                placeholder="Optional description"
                class="h-9 rounded-lg border-border bg-card body-sm"
              />
            </div>
          </div>
          <div class="flex flex-col sm:flex-row gap-3 sm:gap-4">
            <div class="space-y-1 sm:flex-shrink-0 sm:w-32">
              <Label class="body-sm text-muted-foreground font-medium">Apply To</Label>
              <Select v-model="pricingForm.userType">
                <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Users</SelectItem>
                  <SelectItem value="specific">Specific Users</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div v-if="pricingForm.userType === 'specific'" class="space-y-1 flex-1">
              <Label class="body-sm text-muted-foreground font-medium">Users</Label>
              <Input
                v-model="pricingForm.users"
                placeholder="user1@example.com, user2@example.com"
                class="h-9 rounded-lg border-border bg-card body-sm"
              />
              <p class="text-xs text-muted-foreground">
                Comma-separated list. Wildcard supported (e.g., *@company.com, *.edu,
                *@contractors.org)
              </p>
            </div>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="showAddPolicyDialog = false" :disabled="policyCreating"
          >Cancel</Button
        >
        <Button @click="handleAddPolicy" :disabled="policyCreating || !isCurrentPolicyFormValid">
          <div v-if="policyCreating" class="flex items-center gap-2">
            <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            Creating...
          </div>
          <span v-else>Add Rule</span>
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { ingestionApi } from '@/api/endpoints/ingestion'
import { policiesApi } from '@/api/policies/policies'
import { useUserStore } from '@/stores/user'
import { usePolicyCreation } from '@/composables/usePolicyCreation'
import type { EndpointResponse } from '@/api/types'
import type { IngestionStatusResponse, IngestionJobListResponse } from '@/api/types'
import type {
  AuthorizationFormData,
  RateLimitFormData,
  PricingFormData,
} from '@/composables/usePolicyCreation'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { formatPrice } from '@/lib/formatters'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const error = ref(false)
const loading = ref(true)
const endpoint = ref<EndpointResponse | null>(null)
const activeTab = ref('overview')
const deleteNameConfirm = ref('')
const showDeleteDialog = ref(false)
const isDeleting = ref(false)
const showDeletePolicyDialog = ref(false)
const policyToDelete = ref<{ id: string; name: string } | null>(null)
const showAddPolicyDialog = ref(false)
const selectedPolicyType = ref('')
const ingestionStatus = ref<IngestionStatusResponse | null>(null)
const ingestionJobs = ref<IngestionJobListResponse | null>(null)

// Policy creation composable
const { createPolicy, validatePolicyForm, isCreating: policyCreating } = usePolicyCreation()

// Policy form data
const authorizationForm = ref<AuthorizationFormData>({
  ruleType: 'allow',
  users: '',
  note: '',
})

const rateLimiterForm = ref<RateLimitFormData>({
  limit: '',
  windowUnit: 'minute',
  scope: 'per user',
  note: '',
})

const pricingForm = ref<PricingFormData>({
  price: '',
  userType: 'all',
  users: '',
  note: '',
})

// Form validation using composable
const isCurrentPolicyFormValid = computed(() => {
  const formData = getFormDataForType(selectedPolicyType.value)
  return formData ? validatePolicyForm(selectedPolicyType.value, formData) : false
})

// Helper to get form data for current policy type
const getFormDataForType = (policyType: string) => {
  switch (policyType) {
    case 'access':
      return authorizationForm.value
    case 'rate_limit':
      return rateLimiterForm.value
    case 'pricing':
      return pricingForm.value
    default:
      return null
  }
}

// Computed URL to view endpoint on SyftHub
const syftHubUrl = computed(() =>
  endpoint.value?.slug ? userStore.getEndpointUrlInMarketplace(endpoint.value.slug) : null,
)

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

const getPricingPolicies = () => {
  return endpoint.value?.policies?.filter((p) => p.policy_type === 'accounting') || []
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
    // Call the delete API
    await endpointsApi.delete(endpoint.value.slug)

    // Close dialog and navigate away
    showDeleteDialog.value = false
    router.push('/endpoints')
  } catch (error) {
    console.error('Failed to delete endpoint:', error)
    // You might want to show an error toast here
    // For now, just close the dialog
    showDeleteDialog.value = false
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
  } catch (error) {
    console.error('Failed to delete policy:', error)
    // TODO: Show error toast/notification
  }
}

// Policy type label helper
const getPolicyTypeLabel = (type: string) => {
  switch (type) {
    case 'access':
      return 'Authorization'
    case 'rate_limit':
      return 'Rate Limiting'
    case 'pricing':
      return 'Pricing'
    default:
      return 'Policy'
  }
}

// Reset form data when opening dialog
const resetPolicyForm = (policyType: string) => {
  switch (policyType) {
    case 'access':
      authorizationForm.value = { ruleType: 'allow', users: '', note: '' }
      break
    case 'rate_limit':
      rateLimiterForm.value = {
        limit: '',
        windowUnit: 'minute',
        scope: 'per user',
        note: '',
      }
      break
    case 'pricing':
      pricingForm.value = {
        price: '',
        userType: 'all',
        users: '',
        note: '',
      }
      break
  }
}

// Add policy handler
const handleAddPolicy = async () => {
  if (!endpoint.value?.id || !endpoint.value?.name) return

  const formData = getFormDataForType(selectedPolicyType.value)
  if (!formData) return

  // Calculate the correct rule index based on existing policies of this type
  // Map frontend policy type to backend policy type for counting
  const backendPolicyType =
    selectedPolicyType.value === 'pricing' ? 'accounting' : selectedPolicyType.value
  const existingPoliciesOfType =
    endpoint.value.policies?.filter((p) => p.policy_type === backendPolicyType) || []
  const ruleIndex = existingPoliciesOfType.length + 1

  try {
    // Create the policy using the composable
    const newPolicy = await createPolicy(
      selectedPolicyType.value as 'access' | 'rate_limit' | 'pricing',
      formData,
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

    // Close the dialog and reset forms
    showAddPolicyDialog.value = false
    resetPolicyForm(selectedPolicyType.value)
  } catch (error) {
    console.error('Failed to create policy:', error)
    // Error is handled by the composable
  }
}

onMounted(async () => {
  const endpointSlug = route.params.slug as string
  loading.value = true
  error.value = false

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
