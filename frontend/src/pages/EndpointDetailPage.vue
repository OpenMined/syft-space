<template>
  <div class="min-h-screen bg-gradient-to-br from-[var(--color-bg)] via-[var(--color-accent-contrast)]/10 to-[var(--color-secondary)]/5">
    <div class="max-w-7xl mx-auto px-8 lg:px-16 py-16">
      <!-- Breadcrumb Navigation -->
      <nav class="flex mb-6" aria-label="Breadcrumb">
        <ol class="flex items-center space-x-2">
          <li>
            <router-link
              to="/endpoints"
              class="text-gray-500 hover:text-gray-700 text-sm font-medium flex items-center"
            >
              <Server class="h-4 w-4 mr-1" />
              Endpoints
            </router-link>
          </li>
          <li class="flex items-center">
            <ChevronRight class="h-4 w-4 text-gray-400 mx-2" />
            <span class="text-gray-900 text-sm font-medium">{{
              endpoint?.name || 'Loading...'
            }}</span>
          </li>
        </ol>
      </nav>

      <!-- Error State -->
      <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <h3 class="text-lg font-medium text-red-900 mb-2">Endpoint not found</h3>
        <p class="text-red-700 mb-4">
          The endpoint you're looking for doesn't exist or has been deleted.
        </p>
        <Button @click="$router.push('/endpoints')" variant="outline"> Back to Endpoints </Button>
      </div>

      <!-- Main Content -->
      <div v-else-if="endpoint" class="space-y-6">
        <!-- Header Section -->
        <div class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
          <div class="flex items-start justify-between">
            <div class="flex items-start gap-4">
              <div class="p-3 rounded-lg bg-gradient-to-br from-purple-100 to-blue-100">
                <Server class="h-8 w-8 text-purple-600" />
              </div>
              <div>
                <h1 class="text-2xl font-bold text-gray-900 mb-2">{{ endpoint.name }}</h1>
                <p class="text-gray-600 mb-4">{{ endpoint.summary }}</p>
                <div class="flex flex-wrap items-center gap-2">
                  <Badge
                    :variant="endpoint.status === 'published' ? 'default' : 'outline'"
                    :class="
                      endpoint.status === 'published'
                        ? 'bg-green-50 text-green-700 border-green-200'
                        : 'bg-gray-50 text-gray-600 border-gray-200'
                    "
                  >
                    <div
                      :class="
                        endpoint.status === 'published'
                          ? 'w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse'
                          : 'w-2 h-2 bg-gray-400 rounded-full mr-2'
                      "
                    ></div>
                    {{ endpoint.status === 'published' ? 'Live' : 'Draft' }}
                  </Badge>
                  <Badge
                    v-if="endpoint.mcpCompatible"
                    variant="outline"
                    class="bg-blue-50 text-blue-700 border-blue-200"
                  >
                    <CheckCircle2 class="w-3 h-3 mr-1" />
                    MCP Compatible
                  </Badge>
                  <Badge variant="outline" class="bg-purple-50 text-purple-700 border-purple-200">
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
                    <Button
                      v-if="endpoint.status === 'draft'"
                      variant="default"
                      class="bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-700 hover:to-blue-700"
                    >
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
              <AlertDialog>
                <AlertDialogTrigger as-child>
                  <Button variant="outline" size="icon" class="text-red-600 border-red-200 hover:bg-red-50">
                    <Trash2 class="h-4 w-4" />
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <div class="space-y-4">
                    <div>
                      <h3 class="text-sm font-semibold text-red-600">Danger Zone</h3>
                      <p class="text-xs text-gray-600 mt-1">Permanently delete this endpoint and all associated data.</p>
                    </div>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete endpoint</AlertDialogTitle>
                      <AlertDialogDescription>
                        This action cannot be undone. Please type
                        <span class="font-medium text-gray-900"> {{ endpoint?.name }} </span>
                        to confirm deletion.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <div class="space-y-2">
                      <Label class="text-xs text-gray-600">Confirm name</Label>
                      <Input v-model="deleteNameConfirm" :placeholder="endpoint?.name || 'endpoint-name'" />
                      <p class="text-xs" :class="deleteNameConfirm === endpoint?.name ? 'text-green-600' : 'text-gray-500'">
                        {{ deleteNameConfirm === endpoint?.name ? 'Name matches' : 'Enter the endpoint name exactly' }}
                      </p>
                    </div>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        :disabled="deleteNameConfirm !== endpoint?.name"
                        class="bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        @click="deleteEndpoint"
                      >
                        Delete Endpoint
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </div>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </div>
        </div>

        <!-- Tabs Section -->
          <Tabs v-model="activeTab" class="space-y-4">
          <TabsList class="grid grid-cols-4 w-full bg-white/80 backdrop-blur-sm border border-gray-200">
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
              <!-- Description -->
              <div class="lg:col-span-2 bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
                <h2 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                  <FileText class="h-5 w-5 text-gray-500" />
                  Description
                </h2>
                <div class="prose prose-sm max-w-none text-gray-600">
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

              <!-- Quick Stats -->
              <div class="space-y-4">
                <!-- Endpoint Details Card -->
                <div class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
                  <h3 class="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
                    <Info class="h-4 w-4 text-gray-500" />
                    Details
                  </h3>
                  <div class="space-y-3">
                    <div class="flex justify-between items-center py-1">
                      <span class="text-xs text-gray-600">Type</span>
                      <span class="text-xs font-medium text-gray-900">{{ getEndpointType() }}</span>
                    </div>
                    <Separator />
                    <div class="flex justify-between items-center py-1">
                      <span class="text-xs text-gray-600">Response</span>
                      <span class="text-xs font-medium text-gray-900">{{ getResponseType() }}</span>
                    </div>
                    <Separator />
                    <div v-if="endpoint.dataSourceType" class="flex justify-between items-center py-1">
                      <span class="text-xs text-gray-600">Data Source</span>
                      <router-link
                        :to="{
                          name: 'dataset-detail',
                          params: { slug: getDatasetSlug(endpoint.dataSourceType) },
                        }"
                        class="text-xs font-medium text-purple-600 hover:text-purple-700 hover:underline"
                      >
                        {{ getDataSourceName(endpoint.dataSourceType) }}
                      </router-link>
                    </div>
                    <Separator v-if="endpoint.dataSourceType" />
                    <div v-if="endpoint.modelType" class="flex justify-between items-center py-1">
                      <span class="text-xs text-gray-600">Model</span>
                      <router-link
                        :to="{ name: 'model-detail', params: { slug: getModelSlug(endpoint.modelType) } }"
                        class="text-xs font-medium text-purple-600 hover:text-purple-700 hover:underline"
                      >
                        {{ getModelName(endpoint.modelType) }}
                      </router-link>
                    </div>
                  </div>
                </div>

                <!-- Tags -->
                <div class="bg-white/80 backdrop-blur-sm border border-gray-200 rounded-xl shadow-sm p-6">
                  <h3 class="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    <Tags class="h-4 w-4 text-gray-500" />
                    Categories & Tags
                  </h3>
                  <div class="flex flex-wrap gap-2">
                    <Badge
                      v-for="language in endpoint.languages"
                      :key="`lang-${language}`"
                      variant="outline"
                      class="text-xs"
                    >
                      {{ language }}
                    </Badge>
                    <Badge
                      v-for="domain in endpoint.domains"
                      :key="`domain-${domain}`"
                      variant="outline"
                      class="text-xs"
                    >
                      {{ domain }}
                    </Badge>
                    <Badge
                      v-for="tag in endpoint.tags.filter(
                        (t) => !t.startsWith('domain:') && !t.startsWith('language:'),
                      )"
                      :key="tag"
                      variant="outline"
                      class="text-xs"
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
                      <p class="text-xs text-gray-600 mb-1">Total Revenue</p>
                      <p class="text-2xl font-bold text-gray-900">{{ getEndpointRevenue().total }}</p>
                      <p class="text-xs text-green-600 mt-1">{{ getEndpointRevenue().growth }} from last month</p>
                    </div>
                    <div class="p-3 rounded-lg bg-green-100">
                      <DollarSign class="h-5 w-5 text-green-600" />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent class="p-6">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="text-xs text-gray-600 mb-1">Total Requests</p>
                      <p class="text-2xl font-bold text-gray-900">{{ getRequestStats().totalRequests }}</p>
                      <p class="text-xs text-gray-500 mt-1">{{ getRequestStats().successRate }} success rate</p>
                    </div>
                    <div class="p-3 rounded-lg bg-blue-100">
                      <BarChart3 class="h-5 w-5 text-blue-600" />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent class="p-6">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="text-xs text-gray-600 mb-1">Active Users</p>
                      <p class="text-2xl font-bold text-gray-900">{{ getRequestStats().activeUsers }}</p>
                      <p class="text-xs text-gray-500 mt-1">{{ getEndpointRevenue().paidUsers }} paid</p>
                    </div>
                    <div class="p-3 rounded-lg bg-purple-100">
                      <Users class="h-5 w-5 text-purple-600" />
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent class="p-6">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="text-xs text-gray-600 mb-1">Avg per Request</p>
                      <p class="text-2xl font-bold text-gray-900">{{ getEndpointRevenue().avgPerRequest }}</p>
                      <p class="text-xs text-gray-500 mt-1">{{ getEndpointRevenue().conversionRate }} conversion</p>
                    </div>
                    <div class="p-3 rounded-lg bg-amber-100">
                      <TrendingUp class="h-5 w-5 text-amber-600" />
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
                <div class="h-64 flex items-center justify-center border border-dashed border-gray-300 rounded-lg bg-gray-50">
                  <div class="text-center">
                    <BarChart3 class="h-12 w-12 text-gray-400 mx-auto mb-3" />
                    <p class="text-gray-500 text-lg mb-1">{{ selectedPeriod }} Usage Analytics</p>
                    <p class="text-gray-400 text-sm">Chart visualization coming soon</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <!-- Additional Metrics -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle class="text-base">Request Breakdown</CardTitle>
                </CardHeader>
                <CardContent class="space-y-3">
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">Free Requests</span>
                    <span class="text-sm font-medium">{{ getEndpointRevenue().freeRequests }}</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">Paid Requests</span>
                    <span class="text-sm font-medium">{{ getEndpointRevenue().paidRequests }}</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">This Month</span>
                    <span class="text-sm font-medium">{{ getRequestStats().thisMonth }}</span>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle class="text-base">Revenue Metrics</CardTitle>
                </CardHeader>
                <CardContent class="space-y-3">
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">This Month</span>
                    <span class="text-sm font-medium">{{ getEndpointRevenue().thisMonth }}</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">Last Month</span>
                    <span class="text-sm font-medium">{{ getEndpointRevenue().lastMonth }}</span>
                  </div>
                  <div class="flex justify-between items-center">
                    <span class="text-sm text-gray-600">Revenue Rate</span>
                    <span class="text-sm font-medium">{{ getEndpointRevenue().revenueRate }}</span>
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
                      <p class="text-xs text-gray-600 mb-1">Status</p>
                      <p class="text-lg font-semibold text-green-600">Healthy</p>
                    </div>
                    <CheckCircle2 class="h-5 w-5 text-green-500" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent class="p-4">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="text-xs text-gray-600 mb-1">Uptime</p>
                      <p class="text-lg font-semibold text-gray-900">99.98%</p>
                    </div>
                    <Clock class="h-5 w-5 text-blue-500" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent class="p-4">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="text-xs text-gray-600 mb-1">Response Time</p>
                      <p class="text-lg font-semibold text-gray-900">142ms</p>
                    </div>
                    <Zap class="h-5 w-5 text-amber-500" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent class="p-4">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="text-xs text-gray-600 mb-1">Error Rate</p>
                      <p class="text-lg font-semibold text-gray-900">0.12%</p>
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
                  <div v-for="i in 5" :key="i" class="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50">
                    <div :class="[
                      'w-2 h-2 rounded-full mt-1.5',
                      i === 2 ? 'bg-red-500' : 'bg-green-500'
                    ]"></div>
                    <div class="flex-1">
                      <div class="flex items-center justify-between mb-1">
                        <span class="text-sm font-medium">
                          {{ i === 2 ? 'Request Failed' : 'Request Successful' }}
                        </span>
                        <span class="text-xs text-gray-500">{{ i * 2 }} min ago</span>
                      </div>
                      <p class="text-xs text-gray-600">
                        {{ i === 2 ? 'Error: Rate limit exceeded' : `User: user${i}@example.com` }}
                      </p>
                      <p class="text-xs text-gray-500 mt-1">
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
                    <Gauge class="h-5 w-5 text-green-600" />
                    Rate Limiting
                  </CardTitle>
                  <CardDescription>Control request frequency</CardDescription>
                </CardHeader>
                <CardContent class="space-y-4">
                  <div class="border rounded-lg p-4 space-y-3">
                    <div class="flex items-center justify-between">
                      <span class="text-sm font-medium">Default Rule</span>
                      <Badge variant="outline" class="text-xs">Active</Badge>
                    </div>
                    <div class="space-y-2 text-sm">
                      <div class="flex justify-between">
                        <span class="text-gray-600">Limit:</span>
                        <span class="font-medium">100 req/min</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="text-gray-600">Applies to:</span>
                        <span class="font-medium">All users</span>
                      </div>
                    </div>
                  </div>
                  <div class="border rounded-lg p-4 space-y-3">
                    <div class="flex items-center justify-between">
                      <span class="text-sm font-medium">Premium Rule</span>
                      <Badge variant="outline" class="text-xs">Active</Badge>
                    </div>
                    <div class="space-y-2 text-sm">
                      <div class="flex justify-between">
                        <span class="text-gray-600">Limit:</span>
                        <span class="font-medium">500 req/min</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="text-gray-600">Applies to:</span>
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
                      <span class="text-sm font-medium">Standard Pricing</span>
                      <Badge variant="outline" class="text-xs">Active</Badge>
                    </div>
                    <div class="space-y-2 text-sm">
                      <div class="flex justify-between">
                        <span class="text-gray-600">Price:</span>
                        <span class="font-medium">$0.005/request</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="text-gray-600">Applies to:</span>
                        <span class="font-medium">All users</span>
                      </div>
                    </div>
                  </div>
                  <div class="border rounded-lg p-4 space-y-3">
                    <div class="flex items-center justify-between">
                      <span class="text-sm font-medium">Educational</span>
                      <Badge variant="outline" class="text-xs">Active</Badge>
                    </div>
                    <div class="space-y-2 text-sm">
                      <div class="flex justify-between">
                        <span class="text-gray-600">Price:</span>
                        <span class="font-medium">Free</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="text-gray-600">Applies to:</span>
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
                      <span class="text-sm font-medium">Educational Institutions</span>
                      <Badge variant="outline" class="text-xs">Active</Badge>
                    </div>
                    <div class="space-y-2 text-sm">
                      <div class="flex justify-between">
                        <span class="text-gray-600">Alert:</span>
                        <span class="font-medium">In-App Notification</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="text-gray-600">Applies to:</span>
                        <span class="font-medium">*.edu</span>
                      </div>
                      <div class="flex justify-between">
                        <span class="text-gray-600">Timeout:</span>
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
                      <span class="text-sm text-gray-600">Total Rules</span>
                      <span class="text-sm font-medium">5 active</span>
                    </div>
                    <Separator />
                    <div class="flex items-center justify-between py-2">
                      <span class="text-sm text-gray-600">Rate Limits</span>
                      <span class="text-sm font-medium">2 rules</span>
                    </div>
                    <Separator />
                    <div class="flex items-center justify-between py-2">
                      <span class="text-sm text-gray-600">Pricing Tiers</span>
                      <span class="text-sm font-medium">2 tiers</span>
                    </div>
                    <Separator />
                    <div class="flex items-center justify-between py-2">
                      <span class="text-sm text-gray-600">Approval Rules</span>
                      <span class="text-sm font-medium">1 rule</span>
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
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
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

const deleteEndpoint = () => {
  // Handle endpoint deletion
  console.log('Deleting endpoint:', endpoint.value?.name)
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