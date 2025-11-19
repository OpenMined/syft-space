<template>
  <div
    class="min-h-screen bg-gradient-to-br from-background via-blue-50/20 dark:via-blue-950/20 to-purple-50/20 dark:to-purple-950/20"
  >
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

      <!-- Error State -->
      <div
        v-if="error"
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
                    :variant="endpoint.status === 'published' ? 'default' : 'outline'"
                    :class="
                      endpoint.status === 'published'
                        ? 'bg-primary/10 text-primary border border-primary/20'
                        : 'bg-muted text-muted-foreground border border-border'
                    "
                  >
                    <div
                      :class="
                        endpoint.status === 'published'
                          ? 'w-2 h-2 bg-primary rounded-full mr-2 animate-pulse'
                          : 'w-2 h-2 bg-muted-foreground rounded-full mr-2'
                      "
                    ></div>
                    {{ endpoint.status === 'published' ? 'Live' : 'Draft' }}
                  </Badge>
                  <Badge
                    v-if="endpoint.mcpCompatible"
                    variant="outline"
                    class="bg-primary/10 text-primary border-primary/20"
                  >
                    <CheckCircle2 class="w-3 h-3 mr-1" />
                    MCP Compatible
                  </Badge>
                  <Badge variant="outline" class="bg-primary/10 text-primary border-primary/20">
                    {{ endpoint.price || '$0.005/request' }}
                  </Badge>
                </div>
              </div>
            </div>
            <!-- Quick Actions -->
            <div class="flex items-center gap-2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button v-if="endpoint.status === 'draft'" variant="default">
                      <Send class="h-4 w-4 mr-2" />
                      Publish
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Make this endpoint publicly available</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button variant="outline" size="icon">
                      <Edit class="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Edit endpoint configuration</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <!-- Delete Endpoint Action -->
              <Button
                variant="outline"
                size="icon"
                class="text-destructive border-destructive/20 hover:bg-destructive/10"
                @click="
                  () => {
                    deleteNameConfirm = ''
                    showDeleteDialog = true
                  }
                "
              >
                <Trash2 class="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>

        <!-- Tabs Section -->
        <Tabs v-model="activeTab" class="space-y-4">
          <TabsList
            class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-4"
          >
            <TabsTrigger value="overview" class="flex items-center gap-2">
              <Layout class="h-4 w-4" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="analytics" class="flex items-center gap-2">
              <TrendingUp class="h-4 w-4" />
              Analytics
            </TabsTrigger>
            <TabsTrigger value="monitoring" class="flex items-center gap-2">
              <Activity class="h-4 w-4" />
              Monitoring
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
                  class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6"
                >
                  <h2 class="heading-3 text-foreground mb-4 flex items-center gap-2">
                    <FileText class="h-5 w-5 text-muted-foreground" />
                    Description
                  </h2>
                  <div class="prose prose-sm max-w-none text-muted-foreground">
                    <div v-if="endpoint.description" class="markdown-content">
                      <MdPreview
                        :model-value="endpoint.description"
                        preview-theme="default"
                        :show-code-row-number="false"
                      />
                    </div>
                    <div v-else>
                      {{ endpoint.summary }}
                    </div>
                  </div>
                </div>

                <!-- Data Sources -->
                <div
                  class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6"
                >
                  <h2 class="heading-3 text-foreground mb-4 flex items-center gap-2">
                    <Database class="h-5 w-5 text-muted-foreground" />
                    Data Sources
                  </h2>
                  <div class="space-y-3">
                    <div
                      v-for="path in getEndpointDataSources()"
                      :key="path.id"
                      class="p-3 bg-muted/50 border border-border rounded-lg"
                    >
                      <div class="flex items-start gap-3">
                        <div
                          :class="[
                            'w-2 h-2 rounded-full mt-1.5',
                            path.status === 'indexed'
                              ? 'bg-success'
                              : path.status === 'processing'
                                ? 'bg-primary'
                                : path.status === 'queued'
                                  ? 'bg-warning'
                                  : path.status === 'errored'
                                    ? 'bg-destructive'
                                    : 'bg-muted-foreground',
                          ]"
                        ></div>
                        <div class="flex-1">
                          <p class="body-sm font-medium text-foreground">{{ path.path }}</p>
                          <p class="body-sm text-muted-foreground mt-1">
                            {{ path.fileCount }} files
                          </p>
                          <p class="body-sm text-muted-foreground mt-1 italic">
                            {{ path.summary }}
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
                      <span class="body-sm font-medium text-foreground">{{
                        getEndpointType()
                      }}</span>
                    </div>
                    <Separator />
                    <div class="flex justify-between items-center py-1">
                      <span class="body-sm text-muted-foreground">Response</span>
                      <span class="body-sm font-medium text-foreground">{{
                        getResponseType()
                      }}</span>
                    </div>
                    <Separator />
                    <div
                      v-if="endpoint.dataSourceType"
                      class="flex justify-between items-center py-1"
                    >
                      <span class="body-sm text-muted-foreground">Data Source</span>
                      <router-link
                        :to="{
                          name: 'dataset-detail',
                          params: { slug: getDatasetSlug(endpoint.dataSourceType) },
                        }"
                        class="body-sm font-medium text-primary hover:text-primary/80 hover:underline"
                      >
                        {{ getDataSourceName(endpoint.dataSourceType) }}
                      </router-link>
                    </div>
                    <Separator v-if="endpoint.dataSourceType" />
                    <div v-if="endpoint.modelType" class="flex justify-between items-center py-1">
                      <span class="body-sm text-muted-foreground">Model</span>
                      <router-link
                        :to="{
                          name: 'model-detail',
                          params: { slug: getModelSlug(endpoint.modelType) },
                        }"
                        class="body-sm font-medium text-primary hover:text-primary/80 hover:underline"
                      >
                        {{ getModelName(endpoint.modelType) }}
                      </router-link>
                    </div>
                  </div>
                </div>

                <!-- Tags -->
                <div
                  class="bg-card/80 backdrop-blur-sm border border-border rounded-xl shadow-sm p-6"
                >
                  <h3 class="body-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                    <Tags class="h-4 w-4 text-muted-foreground" />
                    Categories & Tags
                  </h3>
                  <div class="flex flex-wrap gap-2">
                    <Badge
                      v-for="language in endpoint.languages"
                      :key="`lang-${language}`"
                      variant="outline"
                      class="body-sm"
                    >
                      {{ language }}
                    </Badge>
                    <Badge
                      v-for="domain in endpoint.domains"
                      :key="`domain-${domain}`"
                      variant="outline"
                      class="body-sm"
                    >
                      {{ domain }}
                    </Badge>
                    <Badge
                      v-for="tag in endpoint.tags.filter(
                        (t) => !t.startsWith('domain:') && !t.startsWith('language:'),
                      )"
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

          <!-- Analytics Tab -->
          <TabsContent value="analytics" class="space-y-6">
            <!-- Revenue Stats -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card>
                <CardContent class="p-6">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="body-sm text-muted-foreground mb-1">Total Revenue</p>
                      <p class="heading-1 text-foreground">
                        {{ getEndpointRevenue().total }}
                      </p>
                      <p class="body-sm text-success mt-1">
                        {{ getEndpointRevenue().growth }} from last month
                      </p>
                    </div>
                    <div class="p-3 rounded-lg bg-primary/10">
                      <DollarSign class="h-5 w-5 text-primary" />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent class="p-6">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="body-sm text-muted-foreground mb-1">Total Requests</p>
                      <p class="heading-1 text-foreground">
                        {{ getRequestStats().totalRequests }}
                      </p>
                      <p class="body-sm text-muted-foreground mt-1">
                        {{ getRequestStats().successRate }} success rate
                      </p>
                    </div>
                    <div class="p-3 rounded-lg bg-primary/10">
                      <BarChart3 class="h-5 w-5 text-primary" />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent class="p-6">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="body-sm text-muted-foreground mb-1">Active Users</p>
                      <p class="heading-1 text-foreground">
                        {{ getRequestStats().activeUsers }}
                      </p>
                      <p class="body-sm text-muted-foreground mt-1">
                        {{ getEndpointRevenue().paidUsers }} paid
                      </p>
                    </div>
                    <div class="p-3 rounded-lg bg-primary/10">
                      <Users class="h-5 w-5 text-primary" />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent class="p-6">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="body-sm text-muted-foreground mb-1">Avg per Request</p>
                      <p class="heading-1 text-foreground">
                        {{ getEndpointRevenue().avgPerRequest }}
                      </p>
                      <p class="body-sm text-muted-foreground mt-1">
                        {{ getEndpointRevenue().conversionRate }} conversion
                      </p>
                    </div>
                    <div class="p-3 rounded-lg bg-primary/10">
                      <TrendingUp class="h-5 w-5 text-primary" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <!-- Usage Trends -->
            <Card>
              <CardHeader>
                <div class="flex items-center justify-between">
                  <CardTitle>Usage Trends</CardTitle>
                  <div class="flex items-center gap-2">
                    <Button
                      v-for="period in ['Daily', 'Weekly', 'Monthly']"
                      :key="period"
                      size="sm"
                      :variant="selectedPeriod === period ? 'default' : 'outline'"
                      @click="selectedPeriod = period"
                    >
                      {{ period }}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div
                  class="h-64 flex items-center justify-center border border-dashed border-border rounded-lg bg-muted/50"
                >
                  <div class="text-center">
                    <BarChart3 class="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                    <p class="text-muted-foreground body-lg mb-1">
                      {{ selectedPeriod }} Usage Analytics
                    </p>
                    <p class="text-muted-foreground body-sm">Chart visualization coming soon</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <!-- Additional Metrics -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Request Breakdown</CardTitle>
                </CardHeader>
                <CardContent class="space-y-3">
                  <div class="flex justify-between items-center">
                    <span class="body-sm text-muted-foreground">Free Requests</span>
                    <span class="body-sm font-medium">{{ getEndpointRevenue().freeRequests }}</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="body-sm text-muted-foreground">Paid Requests</span>
                    <span class="body-sm font-medium">{{ getEndpointRevenue().paidRequests }}</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="body-sm text-muted-foreground">This Month</span>
                    <span class="body-sm font-medium">{{ getRequestStats().thisMonth }}</span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Revenue Metrics</CardTitle>
                </CardHeader>
                <CardContent class="space-y-3">
                  <div class="flex justify-between items-center">
                    <span class="body-sm text-muted-foreground">This Month</span>
                    <span class="body-sm font-medium">{{ getEndpointRevenue().thisMonth }}</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="body-sm text-muted-foreground">Last Month</span>
                    <span class="body-sm font-medium">{{ getEndpointRevenue().lastMonth }}</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="body-sm text-muted-foreground">Revenue Rate</span>
                    <span class="body-sm font-medium">{{ getEndpointRevenue().revenueRate }}</span>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <!-- Monitoring Tab -->
          <TabsContent value="monitoring" class="space-y-6">
            <!-- Status Overview -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card>
                <CardContent class="p-4">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="body-sm text-muted-foreground mb-1">Status</p>
                      <p class="heading-3 text-success">Healthy</p>
                    </div>
                    <CheckCircle2 class="h-5 w-5 text-primary" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent class="p-4">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="body-sm text-muted-foreground mb-1">Uptime</p>
                      <p class="heading-3 text-foreground">99.98%</p>
                    </div>
                    <Clock class="h-5 w-5 text-blue-500" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent class="p-4">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="body-sm text-muted-foreground mb-1">Response Time</p>
                      <p class="heading-3 text-foreground">142ms</p>
                    </div>
                    <Zap class="h-5 w-5 text-amber-500" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent class="p-4">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="body-sm text-muted-foreground mb-1">Error Rate</p>
                      <p class="heading-3 text-foreground">0.12%</p>
                    </div>
                    <AlertCircle class="h-5 w-5 text-red-500" />
                  </div>
                </CardContent>
              </Card>
            </div>

            <!-- Recent Activity Logs -->
            <Card>
              <CardHeader>
                <div class="flex items-center justify-between">
                  <CardTitle>Recent Activity</CardTitle>
                  <div class="flex items-center gap-2">
                    <Button variant="outline" size="sm">
                      <RefreshCw class="h-4 w-4 mr-2" />
                      Refresh
                    </Button>
                    <Button variant="outline" size="sm">
                      <Download class="h-4 w-4 mr-2" />
                      Export
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div class="space-y-2">
                  <div
                    v-for="i in 5"
                    :key="i"
                    class="flex items-start gap-3 p-3 rounded-lg hover:bg-muted/50"
                  >
                    <div
                      :class="[
                        'w-2 h-2 rounded-full mt-1.5',
                        i === 2 ? 'bg-destructive' : 'bg-success',
                      ]"
                    ></div>
                    <div class="flex-1">
                      <div class="flex items-center justify-between mb-1">
                        <span class="body-sm font-medium">
                          {{ i === 2 ? 'Request Failed' : 'Request Successful' }}
                        </span>
                        <span class="body-sm text-muted-foreground">{{ i * 2 }} min ago</span>
                      </div>
                      <p class="body-sm text-muted-foreground">
                        {{ i === 2 ? 'Error: Rate limit exceeded' : `User: user${i}@example.com` }}
                      </p>
                      <p class="body-sm text-muted-foreground mt-1">
                        Response time: {{ 100 + i * 20 }}ms
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <!-- Access Control Tab -->
          <TabsContent value="access" class="space-y-6">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <!-- Rate Limiting -->
              <Card>
                <CardHeader>
                  <CardTitle class="flex items-center gap-2">
                    <Gauge class="h-5 w-5 text-primary" />
                    Rate Limiting
                  </CardTitle>
                  <CardDescription>Control request frequency</CardDescription>
                </CardHeader>
                <CardContent class="space-y-4">
                  <div class="border rounded-lg p-4 space-y-3">
                    <div class="flex items-center justify-between">
                      <span class="body-sm font-medium">Default Rule</span>
                      <Badge variant="outline" class="body-sm">Active</Badge>
                    </div>
                    <div class="space-y-2 body-sm">
                      <div class="flex justify-between">
                        <span class="text-muted-foreground">Limit:</span>
                        <span class="font-medium">100 req/min</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="text-muted-foreground">Applies to:</span>
                        <span class="font-medium">All users</span>
                      </div>
                    </div>
                  </div>
                  <div class="border rounded-lg p-4 space-y-3">
                    <div class="flex items-center justify-between">
                      <span class="body-sm font-medium">Premium Rule</span>
                      <Badge variant="outline" class="body-sm">Active</Badge>
                    </div>
                    <div class="space-y-2 body-sm">
                      <div class="flex justify-between">
                        <span class="text-muted-foreground">Limit:</span>
                        <span class="font-medium">500 req/min</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="text-muted-foreground">Applies to:</span>
                        <span class="font-medium">*@openmined.org</span>
                      </div>
                    </div>
                  </div>
                  <Button variant="outline" class="w-full">
                    <Plus class="h-4 w-4 mr-2" />
                    Add Rule
                  </Button>
                </CardContent>
              </Card>

              <!-- Pricing Rules -->
              <Card>
                <CardHeader>
                  <CardTitle class="flex items-center gap-2">
                    <DollarSign class="h-5 w-5 text-yellow-600" />
                    Pricing Rules
                  </CardTitle>
                  <CardDescription>Set pricing tiers</CardDescription>
                </CardHeader>
                <CardContent class="space-y-4">
                  <div class="border rounded-lg p-4 space-y-3">
                    <div class="flex items-center justify-between">
                      <span class="body-sm font-medium">Standard Pricing</span>
                      <Badge variant="outline" class="body-sm">Active</Badge>
                    </div>
                    <div class="space-y-2 body-sm">
                      <div class="flex justify-between">
                        <span class="text-muted-foreground">Price:</span>
                        <span class="font-medium">$0.005/request</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="text-muted-foreground">Applies to:</span>
                        <span class="font-medium">All users</span>
                      </div>
                    </div>
                  </div>
                  <div class="border rounded-lg p-4 space-y-3">
                    <div class="flex items-center justify-between">
                      <span class="body-sm font-medium">Educational</span>
                      <Badge variant="outline" class="body-sm">Active</Badge>
                    </div>
                    <div class="space-y-2 body-sm">
                      <div class="flex justify-between">
                        <span class="text-muted-foreground">Price:</span>
                        <span class="font-medium">Free</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="text-muted-foreground">Applies to:</span>
                        <span class="font-medium">*.edu</span>
                      </div>
                    </div>
                  </div>
                  <Button variant="outline" class="w-full">
                    <Plus class="h-4 w-4 mr-2" />
                    Add Pricing Rule
                  </Button>
                </CardContent>
              </Card>

              <!-- Manual Approval -->
              <Card>
                <CardHeader>
                  <CardTitle class="flex items-center gap-2">
                    <UserCheck class="h-5 w-5 text-purple-600" />
                    Manual Approval
                  </CardTitle>
                  <CardDescription>Require approval for certain users</CardDescription>
                </CardHeader>
                <CardContent class="space-y-4">
                  <div class="border rounded-lg p-4 space-y-3">
                    <div class="flex items-center justify-between">
                      <span class="body-sm font-medium">Educational Institutions</span>
                      <Badge variant="outline" class="body-sm">Active</Badge>
                    </div>
                    <div class="space-y-2 body-sm">
                      <div class="flex justify-between">
                        <span class="text-muted-foreground">Alert:</span>
                        <span class="font-medium">In-App Notification</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="text-muted-foreground">Applies to:</span>
                        <span class="font-medium">*.edu</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="text-muted-foreground">Timeout:</span>
                        <span class="font-medium">24 hours</span>
                      </div>
                    </div>
                  </div>
                  <Button variant="outline" class="w-full">
                    <Plus class="h-4 w-4 mr-2" />
                    Add Approval Rule
                  </Button>
                </CardContent>
              </Card>

              <!-- Access Summary -->
              <Card>
                <CardHeader>
                  <CardTitle class="flex items-center gap-2">
                    <Shield class="h-5 w-5 text-blue-600" />
                    Access Summary
                  </CardTitle>
                  <CardDescription>Overview of access controls</CardDescription>
                </CardHeader>
                <CardContent>
                  <div class="space-y-3">
                    <div class="flex items-center justify-between py-2">
                      <span class="body-sm text-muted-foreground">Total Rules</span>
                      <span class="body-sm font-medium">5 active</span>
                    </div>
                    <Separator />
                    <div class="flex items-center justify-between py-2">
                      <span class="body-sm text-muted-foreground">Rate Limits</span>
                      <span class="body-sm font-medium">2 rules</span>
                    </div>
                    <Separator />
                    <div class="flex items-center justify-between py-2">
                      <span class="body-sm text-muted-foreground">Pricing Tiers</span>
                      <span class="body-sm font-medium">2 tiers</span>
                    </div>
                    <Separator />
                    <div class="flex items-center justify-between py-2">
                      <span class="body-sm text-muted-foreground">Approval Rules</span>
                      <span class="body-sm font-medium">1 rule</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>
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
          <Button variant="outline" @click="showDeleteDialog = false">Cancel</Button>
          <Button
            variant="destructive"
            :disabled="deleteNameConfirm !== endpoint?.name"
            @click="deleteEndpoint"
          >
            Delete Endpoint
          </Button>
        </DialogFooter>
      </div>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Server,
  ChevronRight,
  Edit,
  Trash2,
  Send,
  Gauge,
  DollarSign,
  UserCheck,
  Layout,
  TrendingUp,
  Activity,
  Shield,
  FileText,
  Info,
  Tags,
  CheckCircle2,
  Clock,
  Zap,
  AlertCircle,
  RefreshCw,
  Download,
  Plus,
  Users,
  BarChart3,
  Database,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import { useEndpointsStore } from '@/stores/endpoints'
import type { EndpointItem } from '@/stores/endpoints'
import { getDataSourceName, getModelName } from '@/lib/mappers'
import { MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'

const route = useRoute()
const router = useRouter()
const error = ref(false)
const endpoint = ref<EndpointItem | null>(null)
const endpointsStore = useEndpointsStore()
const activeTab = ref('overview')
const selectedPeriod = ref('Daily')
const deleteNameConfirm = ref('')
const showDeleteDialog = ref(false)

const getDatasetSlug = (dataSourceType: string) => {
  const datasetSlugs: Record<string, string> = {
    filesystem: 'Research Database',
    weaviate: 'Legal Documents Store',
    qdrant: 'Customer Analytics Store',
    chroma: 'Research Database',
  }
  return datasetSlugs[dataSourceType] || 'unknown'
}

const getModelSlug = (modelType: string) => {
  const modelSlugs: Record<string, string> = {
    vllm: 'NLP Processing Engine',
    ollama: 'Code Assistant Model',
    huggingface: 'Text Embedding Service',
  }
  return modelSlugs[modelType] || 'unknown'
}

const getEndpointType = () => {
  return 'Data Endpoint'
}

const getResponseType = () => {
  return 'AI Summary & Raw Data'
}

const getRequestStats = () => {
  return {
    totalRequests: '47.2k',
    successRate: '98.7%',
    thisMonth: '12.1k',
    activeUsers: '234',
  }
}

const getEndpointRevenue = () => {
  return {
    total: '$1,247.85',
    thisMonth: '$285.40',
    lastMonth: '$198.65',
    growth: '+43.7%',
    avgPerRequest: '$0.026',
    revenueRate: '64.2%',
    paidUsers: '156',
    freeRequests: '16.8k',
    paidRequests: '30.4k',
    conversionRate: '18.3%',
  }
}

const getEndpointDataSources = () => {
  // Return the same data sources that the endpoint uses
  return [
    {
      id: '1',
      path: '/data/legal/contracts',
      fileCount: 1247,
      status: 'indexed',
      summary: 'Commercial agreements, service contracts, and partnership documents',
    },
    {
      id: '2',
      path: '/data/legal/cases',
      fileCount: 856,
      status: 'processing',
      summary: 'Court decisions, case law, and legal precedents from various jurisdictions',
    },
    {
      id: '3',
      path: '/data/legal/regulations',
      fileCount: 423,
      status: 'queued',
      summary: 'Federal and state regulations, compliance guidelines, and regulatory updates',
    },
  ]
}

const deleteEndpoint = () => {
  // Handle endpoint deletion
  console.log('Deleting endpoint:', endpoint.value?.name)
  showDeleteDialog.value = false
  router.push('/endpoints')
}

onMounted(() => {
  const endpointSlug = route.params.slug as string
  const foundEndpoint = endpointsStore.endpoints.find((e) => e.name === endpointSlug)

  if (foundEndpoint) {
    endpoint.value = foundEndpoint
  } else {
    error.value = true
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
