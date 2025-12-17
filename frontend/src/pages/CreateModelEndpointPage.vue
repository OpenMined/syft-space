<template>
  <ErrorBoundary :can-retry="true" :show-details="true" custom-title="Endpoint Creation Error"
    custom-message="There was a problem with the endpoint creation form. Please try again." @retry="refreshForm">
    <div class="min-h-screen bg-muted/30">
      <!-- Header -->
      <div class="bg-card border-b border-border">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div class="flex items-center justify-between">
            <Button variant="ghost" @click="handleBack"
              class="flex items-center text-muted-foreground hover:text-foreground">
              <ArrowLeft class="w-5 h-5 mr-2" />
              Back to Endpoints
            </Button>

            <TooltipProvider>
              <Tooltip :delayDuration="0">
                <TooltipTrigger as-child>
                  <span>
                    <Button @click="saveDraft" :disabled="!canSaveDraft" variant="outline"
                      class="flex items-center gap-2">
                      <Save class="w-4 h-4" />
                      Save Draft
                    </Button>
                  </span>
                </TooltipTrigger>
                <TooltipContent v-if="!canSaveDraft">
                  <p>Add endpoint name to enable</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </div>

      <!-- Two-column layout -->
      <div class="flex gap-12 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
        <!-- Left sidebar with steps -->
        <div class="w-80 flex-shrink-0">
          <div class="sticky top-8">
            <h2 class="heading-3 mb-6">Setup Progress</h2>

            <!-- Vertical step list -->
            <div class="space-y-6">
              <!-- Step 1 -->
              <div class="flex items-start gap-4">
                <div :class="[
                  'w-8 h-8 rounded-full flex items-center justify-center font-medium body-sm transition-all',
                  currentSubStep >= 1
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground',
                ]">
                  {{ currentSubStep > 1 ? '✓' : '1' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3 :class="[
                    'font-medium body-sm',
                    currentSubStep >= 1 ? 'text-foreground' : 'text-muted-foreground',
                  ]">
                    What model are you sharing?
                  </h3>
                  <p class="body-sm text-muted-foreground mt-1">Choose your AI model source</p>
                  <div v-if="currentSubStep > 1" class="mt-2 body-sm text-primary bg-primary/10 px-2 py-1 rounded">
                    ✓ Completed
                  </div>
                  <div v-else-if="currentSubStep === 1" class="mt-2 body-sm text-primary font-medium">
                    Current step
                  </div>
                </div>
              </div>

              <!-- Step 2 -->
              <div class="flex items-start gap-4">
                <div :class="[
                  'w-8 h-8 rounded-full flex items-center justify-center font-medium body-sm transition-all',
                  currentSubStep >= 2
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground',
                ]">
                  {{ currentSubStep > 2 ? '✓' : '2' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3 :class="[
                    'font-medium body-sm',
                    currentSubStep >= 2 ? 'text-foreground' : 'text-muted-foreground',
                  ]">
                    Set Rules & Pricing
                  </h3>
                  <p class="body-sm text-muted-foreground mt-1">
                    Configure policies and access controls
                  </p>
                  <div v-if="currentSubStep > 2" class="mt-2 body-sm text-primary bg-primary/10 px-2 py-1 rounded">
                    ✓ Completed
                  </div>
                  <div v-else-if="currentSubStep === 2" class="mt-2 body-sm text-primary font-medium">
                    Current step
                  </div>
                </div>
              </div>

              <!-- Step 3 -->
              <div class="flex items-start gap-4">
                <div :class="[
                  'w-8 h-8 rounded-full flex items-center justify-center font-medium body-sm transition-all',
                  currentSubStep >= 3
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground',
                ]">
                  {{ currentSubStep > 3 ? '✓' : '3' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3 :class="[
                    'font-medium body-sm',
                    currentSubStep >= 3 ? 'text-foreground' : 'text-muted-foreground',
                  ]">
                    Add details & publish
                  </h3>
                  <p class="body-sm text-muted-foreground mt-1">Name and describe your model</p>
                  <div v-if="currentSubStep > 3" class="mt-2 body-sm text-primary bg-primary/10 px-2 py-1 rounded">
                    ✓ Completed
                  </div>
                  <div v-else-if="currentSubStep === 3" class="mt-2 body-sm text-primary font-medium">
                    Current step
                  </div>
                </div>
              </div>

              <!-- Step 4 -->
              <div class="flex items-start gap-4">
                <div :class="[
                  'w-8 h-8 rounded-full flex items-center justify-center font-medium body-sm transition-all',
                  currentSubStep >= 4
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground',
                ]">
                  {{ currentSubStep > 4 ? '✓' : '4' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3 :class="[
                    'font-medium body-sm',
                    currentSubStep >= 4 ? 'text-foreground' : 'text-muted-foreground',
                  ]">
                    Review
                  </h3>
                  <p class="body-sm text-muted-foreground mt-1">Final check and go live</p>
                  <div v-if="currentSubStep > 4" class="mt-2 body-sm text-primary bg-primary/10 px-2 py-1 rounded">
                    ✓ Completed
                  </div>
                  <div v-else-if="currentSubStep === 4" class="mt-2 body-sm text-primary font-medium">
                    Current step
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Main content area -->
        <div class="flex-1 min-w-0">
          <!-- Page title -->
          <div class="mb-8">
            <h1 class="heading-1 text-foreground mb-2">
              {{ stepTitles[currentSubStep - 1] }}
            </h1>
            <p class="text-muted-foreground">
              {{ stepDescriptions[currentSubStep - 1] }}
            </p>
          </div>

          <div>
            <!-- Step 1: What model are you sharing? -->
            <div v-if="currentSubStep === 1" class="space-y-8">
              <!-- Model Source Selection Cards -->
              <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <!-- Add New Model Card -->
                <Card
                  class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-primary hover:bg-gradient-to-br hover:from-primary/10 hover:to-primary/5 border-2 bg-card"
                  :class="selectedModelSourceType === 'create-new'
                    ? 'border-primary bg-gradient-to-br from-primary/10 to-primary/5'
                    : 'border-border'
                    " @click="selectModelSourceType('create-new')">
                  <CardContent class="p-6">
                    <div class="flex flex-col items-center text-center">
                      <div class="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                        <Plus class="w-7 h-7 text-primary" />
                      </div>

                      <h3 class="heading-3 text-foreground mb-2">Add New Model</h3>

                      <p class="body-sm text-muted-foreground mb-3">
                        Set up and configure a new AI model
                      </p>

                      <p class="body-sm text-muted-foreground">
                        vLLM, Ollama, Hugging Face, and more
                      </p>
                    </div>
                  </CardContent>
                </Card>

                <!-- Select Existing Model Card -->
                <Card
                  class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-green-300 hover:bg-gradient-to-br hover:from-green-50 hover:to-emerald-50 border-2 bg-card"
                  :class="selectedModelSourceType === 'existing'
                    ? 'border-green-500 bg-gradient-to-br from-green-50 to-emerald-50'
                    : 'border-border'
                    " @click="selectModelSourceType('existing')">
                  <CardContent class="p-6">
                    <div class="flex flex-col items-center text-center">
                      <div class="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center mb-4">
                        <FolderOpen class="w-7 h-7 text-green-600" />
                      </div>

                      <h3 class="heading-3 text-foreground mb-2">Use Existing Model</h3>

                      <p class="body-sm text-muted-foreground mb-3">
                        Select from your configured AI models
                      </p>

                      <p class="body-sm text-muted-foreground">
                        {{ existingModelsCount }} model{{ existingModelsCount !== 1 ? 's' : '' }}
                        available
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              <!-- Content based on selection -->
              <div v-if="selectedModelSourceType">
                <!-- Add New Model Inline Form -->
                <div v-if="selectedModelSourceType === 'create-new'"
                  class="bg-card rounded-lg shadow-sm border border-border p-8">
                  <div class="space-y-6">
                    <div>
                      <h3 class="heading-3 text-foreground mb-2">Add New AI Model</h3>
                      <p class="body-sm text-muted-foreground">
                        Configure a new AI model for your endpoint
                      </p>
                    </div>

                    <!-- Search Input -->
                    <div class="relative">
                      <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                      <Input v-model="searchQuery" placeholder="Search AI models..." class="pl-10 pr-4" />
                    </div>

                    <!-- Model Options Grid -->
                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                      <div v-for="model in filteredModels" :key="model.id" @click="
                        model.isCustom ? openCustomSDKDocs() : (selectedNewModelType = model.id)
                        " :class="[
                          'flex flex-col items-center justify-center p-6 rounded-lg border cursor-pointer transition-all group h-40',
                          model.isCustom
                            ? 'border-purple-200 bg-gradient-to-r from-purple-50 to-blue-50 hover:border-purple-300 hover:bg-gradient-to-r hover:from-purple-100 hover:to-blue-100'
                            : selectedNewModelType === model.id
                              ? 'border-primary bg-primary/10'
                              : 'border-border hover:bg-muted/50',
                        ]">
                        <div v-if="model.isCustom" class="transition-all duration-200 mb-2">
                          <div class="p-2 bg-purple-100 rounded-md group-hover:hidden">
                            <Code class="h-6 w-6 text-purple-600" />
                          </div>
                          <div class="hidden group-hover:block p-2 bg-purple-100 rounded-md">
                            <ExternalLink class="h-6 w-6 text-purple-600" />
                          </div>
                        </div>
                        <IntegrationIcon v-else :name="model.id" class="h-12 w-12 mb-3" :class="selectedNewModelType === model.id
                          ? 'text-primary'
                          : 'text-muted-foreground'
                          " />
                        <div v-if="model.isCustom" class="text-center transition-all duration-200 min-h-[1.25rem]">
                          <span class="font-medium text-purple-800 group-hover:hidden">
                            {{ model.name }}
                          </span>
                          <span class="hidden group-hover:block font-medium text-purple-800">
                            View documentation
                          </span>
                        </div>
                        <span v-else class="font-medium text-center" :class="selectedNewModelType === model.id ? 'text-primary' : 'text-foreground'
                          ">
                          {{ model.name }}
                        </span>
                        <div v-if="model.isCustom" class="text-center transition-all duration-200 min-h-[1rem]">
                          <span class="text-xs text-purple-600 group-hover:hidden">Using SDK</span>
                          <span class="hidden group-hover:block text-xs text-purple-600">Opens in a new tab</span>
                        </div>
                      </div>
                    </div>

                    <!-- Configuration Form -->
                    <div v-if="selectedNewModelType" class="mt-6 p-4 bg-muted/50 rounded-lg">
                      <h4 class="font-medium text-foreground mb-2">
                        Configure {{ selectedNewModelName }}
                      </h4>
                      <p class="body-sm text-muted-foreground mb-4">
                        Set up your {{ selectedNewModelName }} model integration settings
                      </p>
                      <div
                        class="min-h-[100px] flex items-center justify-center border-2 border-dashed rounded-lg bg-card">
                        <p class="text-muted-foreground">
                          Configuration form for {{ selectedNewModelName }} will be implemented here
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Existing Models List -->
                <div v-if="selectedModelSourceType === 'existing'"
                  class="bg-card rounded-lg shadow-sm border border-border p-6">
                  <div class="space-y-4">
                    <h3 class="heading-3 text-foreground mb-4">Available AI Models</h3>

                    <RadioGroup v-model="formData.aiModel">
                      <div class="space-y-3">
                        <div v-for="model in mockModels" :key="model.id"
                          class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-muted/50"
                          :class="formData.aiModel === model.id
                            ? 'border-green-500 bg-green-50'
                            : 'border-border'
                            " @click="formData.aiModel = model.id">
                          <RadioGroupItem :value="model.id" :id="model.id" />
                          <Label :for="model.id" class="flex items-center gap-3 cursor-pointer flex-1">
                            <div class="p-2 rounded" :class="{
                              'bg-purple-100': model.type === 'vllm',
                              'bg-orange-100': model.type === 'ollama',
                              'bg-primary/10': model.type === 'huggingface',
                            }">
                              <IntegrationIcon :name="model.type" class="h-5 w-5" />
                            </div>
                            <div class="flex-1">
                              <div class="flex items-center gap-2">
                                <span class="font-medium">{{ model.name }}</span>
                                <Badge variant="outline" class="text-xs">{{ model.type }}</Badge>
                              </div>
                              <p class="body-sm text-muted-foreground">{{ model.description }}</p>
                            </div>
                          </Label>
                        </div>
                      </div>
                    </RadioGroup>
                  </div>
                </div>
              </div>
            </div>

            <!-- Step 2: Set Rules & Pricing -->
            <div v-if="currentSubStep === 2" class="space-y-6">
              <!-- Policy Configuration -->
              <div class="space-y-6">
                <div v-for="policy in policyTypes" :key="policy.id"
                  class="bg-card/60 backdrop-blur-sm border border-border rounded-2xl p-6">
                  <!-- Policy Header -->
                  <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-3">
                      <div :class="{
                        'p-2 rounded-lg bg-primary/10': policy.color === 'blue',
                        'p-2 rounded-lg bg-green-100': policy.color === 'green',
                        'p-2 rounded-lg bg-yellow-100': policy.color === 'yellow',
                        'p-2 rounded-lg bg-purple-100': policy.color === 'purple',
                        'p-2 rounded-lg bg-red-100': policy.color === 'red',
                      }">
                        <component :is="policy.icon" :class="{
                          'h-5 w-5 text-primary': policy.color === 'blue',
                          'h-5 w-5 text-green-600': policy.color === 'green',
                          'h-5 w-5 text-yellow-600': policy.color === 'yellow',
                          'h-5 w-5 text-purple-600': policy.color === 'purple',
                          'h-5 w-5 text-red-600': policy.color === 'red',
                        }" />
                      </div>
                      <div class="flex-1">
                        <h3 class="font-medium text-foreground">{{ policy.label }}</h3>
                        <p class="body-sm text-muted-foreground">{{ policy.description }}</p>
                      </div>
                    </div>
                    <Button @click="addPolicy(policy.id)" variant="outline" size="sm">
                      <Plus class="h-4 w-4 mr-2" />
                      Add {{ policy.name }} rule
                    </Button>
                  </div>

                  <!-- Default Policy Message -->
                  <div v-if="policyRules[policy.id]?.length === 0" class="mb-3">
                    <div class="bg-green-50/50 border border-green-200/30 rounded-xl px-4 py-3">
                      <p class="text-sm text-green-700">
                        <strong class="font-medium">Default: </strong>
                        <span v-if="policy.id === 'authorization'">Open access - everyone can use your endpoint</span>
                        <span v-else-if="policy.id === 'ratelimiter'">No rate limits - unlimited usage</span>
                        <span v-else-if="policy.id === 'pricing'">Free access - no charges applied</span>
                        <span v-else>Open access - most permissive settings</span>
                      </p>
                    </div>
                  </div>

                  <!-- Empty State -->
                  <div v-if="policyRules[policy.id]?.length === 0"
                    class="text-center py-8 border-2 border-dashed border-border/50 rounded-xl bg-muted/20">
                    <p class="text-muted-foreground body-sm">
                      No {{ policy.name.toLowerCase() }} rule added yet
                    </p>
                  </div>

                  <!-- Policy Rules -->
                  <div v-if="(policyRules[policy.id] || []).length > 0" class="space-y-3">
                    <div v-for="rule in policyRules[policy.id] || []" :key="rule.id"
                      class="bg-muted/30 border border-border/50 rounded-xl p-4">
                      <!-- Rule in Edit Mode (Expanded) -->
                      <div v-if="rule.isEditing" class="space-y-3">
                        <!-- Authorization Policy Form -->
                        <div v-if="policy.id === 'authorization'">
                          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div class="space-y-1">
                              <Label class="body-sm text-muted-foreground font-medium">Rule Type</Label>
                              <Select v-model="authorizationForm.ruleType">
                                <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                                  <SelectValue placeholder="Select rule type" />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="allow" class="text-sm">Allow specific users</SelectItem>
                                  <SelectItem value="deny" class="text-sm">Deny specific users</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div class="space-y-1">
                              <Label class="body-sm text-muted-foreground font-medium">Note</Label>
                              <Input v-model="authorizationForm.note" placeholder="Optional description"
                                class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground" />
                            </div>
                          </div>
                          <div class="space-y-1 mt-3">
                            <Label class="body-sm text-muted-foreground font-medium">Users</Label>
                            <Input v-model="authorizationForm.users" placeholder="user1@example.com, user2@example.com"
                              class="h-9 rounded-lg border-border bg-card body-sm placeholder:text-muted-foreground" />
                            <p class="text-xs text-muted-foreground">Comma-separated list. Wildcard supported (e.g.,
                              *@company.com, *.edu, *@contractors.org)</p>
                          </div>
                        </div>

                        <!-- Rate Limiter Policy Form -->
                        <div v-if="policy.id === 'ratelimiter'">
                          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
                            <div class="space-y-1">
                              <Label class="body-sm text-muted-foreground font-medium">Limit</Label>
                              <div class="flex">
                                <Input v-model="rateLimiterForm.limit" type="number" placeholder="100"
                                  class="h-9 w-20 sm:w-24 rounded-l-lg rounded-r-none border-r-0 border-border bg-card body-sm" />
                                <Select v-model="rateLimiterForm.windowUnit">
                                  <SelectTrigger
                                    class="h-9 rounded-r-lg rounded-l-none border-border bg-card body-sm min-w-0">
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
                          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <div class="space-y-1">
                              <Label class="body-sm text-muted-foreground font-medium">Note</Label>
                              <Input v-model="rateLimiterForm.note" placeholder="Optional description"
                                class="h-9 rounded-lg border-border bg-card body-sm" />
                            </div>
                          </div>
                        </div>

                        <!-- Pricing Policy Form -->
                        <div v-if="policy.id === 'pricing'">
                          <div class="space-y-3">
                            <!-- Price and Note side-by-side -->
                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              <div class="space-y-1">
                                <Label class="body-sm text-muted-foreground font-medium">Price per query ($)</Label>
                                <Input v-model="pricingForm.price" type="number" step="0.01" placeholder="0.01"
                                  class="h-9 rounded-lg border-border bg-card body-sm" />
                              </div>
                              <div class="space-y-1">
                                <Label class="body-sm text-muted-foreground font-medium">Note</Label>
                                <Input v-model="pricingForm.note" placeholder="Optional description"
                                  class="h-9 rounded-lg border-border bg-card body-sm" />
                              </div>
                            </div>
                            <!-- Apply To and Users row -->
                            <div class="flex flex-col sm:flex-row gap-3">
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
                                <Input v-model="pricingForm.users" placeholder="user1@example.com, user2@example.com"
                                  class="h-9 rounded-lg border-border bg-card body-sm" />
                                <p class="text-xs text-muted-foreground">Comma-separated list. Wildcard supported (e.g.,
                                  *@company.com, *.edu, *@contractors.org)</p>
                              </div>
                            </div>
                          </div>
                        </div>


                        <!-- Form Action Buttons -->
                        <div class="flex gap-2 pt-3 border-t border-border">
                          <Button @click="savePolicy(policy.id, rule.id)" size="sm"
                            class="rounded-lg body-sm font-medium px-3 py-2">
                            Save
                          </Button>
                          <Button @click="cancelEditPolicy(policy.id, rule.id)" variant="outline" size="sm"
                            class="rounded-lg border-border body-sm font-medium px-3 py-2">
                            Cancel
                          </Button>
                        </div>
                      </div>

                      <!-- Rule in Collapsed Mode -->
                      <div v-else class="flex items-start justify-between">
                        <div class="flex-1">
                          <h4 class="body-sm font-medium text-foreground">
                            {{ rule.config.note || `${policy.name} Rule` }}
                          </h4>
                          <p class="body-sm text-muted-foreground mt-1">Rule summary</p>
                        </div>
                        <div class="flex gap-2">
                          <Button variant="outline" size="sm" @click="editPolicy(policy.id, rule.id)">
                            Edit
                          </Button>
                          <Button variant="outline" size="sm" @click="deletePolicy(policy.id, rule.id)">
                            Delete
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Step 3: Add details & publish -->
            <div v-if="currentSubStep === 3" class="bg-card rounded-lg shadow-sm border border-border p-8 space-y-8">
              <!-- Interactive examples -->
              <div class="mb-8 bg-primary/10 border border-primary rounded-lg p-4">
                <h4 class="font-medium text-primary mb-3 flex items-center gap-2">
                  <Lightbulb class="w-4 h-4" />
                  Popular examples to get you started
                </h4>
                <p class="body-sm text-primary mb-4">Click any example to auto-fill the form</p>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 body-sm">
                  <button @click="fillExampleData('code')"
                    class="bg-card p-3 rounded border hover:border-primary hover:shadow-sm transition-all text-left">
                    <p class="font-medium text-foreground">💻 Code Assistant</p>
                    <p class="text-muted-foreground mt-1">
                      "GPT-4 Code Helper" - Helps with programming tasks and debugging
                    </p>
                  </button>
                  <button @click="fillExampleData('chat')"
                    class="bg-card p-3 rounded border hover:border-primary hover:shadow-sm transition-all text-left">
                    <p class="font-medium text-foreground">💬 Chat Assistant</p>
                    <p class="text-muted-foreground mt-1">
                      "Conversational AI" - General purpose chat and question answering
                    </p>
                  </button>
                  <button @click="fillExampleData('analysis')"
                    class="bg-card p-3 rounded border hover:border-primary hover:shadow-sm transition-all text-left">
                    <p class="font-medium text-foreground">📈 Data Analysis</p>
                    <p class="text-muted-foreground mt-1">
                      "Research Assistant" - Specialized for data analysis and insights
                    </p>
                  </button>
                </div>
              </div>

              <div class="space-y-6">
                <!-- Endpoint Name -->
                <div class="space-y-2">
                  <Label for="endpoint-name" class="body-sm font-medium text-foreground">
                    Name <span class="text-red-500">*</span>
                  </Label>
                  <Input id="endpoint-name" v-model="formData.endpointName" placeholder="e.g., gpt-4-code-helper"
                    class="w-full font-mono body-sm" />
                  <p class="body-sm text-muted-foreground">
                    This appears when people discover it. Keep it simple, no spaces
                  </p>
                </div>

                <!-- Summary -->
                <div class="space-y-2">
                  <Label for="summary" class="body-sm font-medium text-foreground">
                    Summary <span class="text-red-500">*</span>
                  </Label>
                  <Input id="summary" v-model="formData.summary" placeholder="Brief description of what your model does"
                    class="w-full" />
                  <p class="body-sm text-muted-foreground">
                    A short summary that will appear in model listings
                  </p>
                </div>

                <!-- Description -->
                <div class="space-y-2">
                  <Label for="description" class="body-sm font-medium text-foreground">
                    Description
                  </Label>
                  <MdEditor v-model="formData.description" :height="200" :toolbars-exclude="['github']"
                    :preview-theme="'github'" :code-theme="'github'" language="en-US"
                    placeholder="Detailed description of your model (supports Markdown)" />
                  <p class="body-sm text-muted-foreground">
                    Provide a detailed description using the WYSIWYG markdown editor above.
                  </p>
                </div>

                <!-- Tags -->
                <div class="space-y-2">
                  <Label for="tags" class="body-sm font-medium text-foreground"> Tags </Label>
                  <div class="space-y-2">
                    <div class="flex gap-2">
                      <Input id="tags" v-model="tagInput" @keydown.enter.prevent="addTag"
                        placeholder="Add tags to help users find your model" class="flex-1" />
                      <Button @click="addTag" variant="outline" size="sm">
                        <Plus class="h-4 w-4" />
                      </Button>
                    </div>
                    <div v-if="formData.tags.length > 0" class="flex flex-wrap gap-2 mt-2">
                      <Badge v-for="(tag, index) in formData.tags" :key="index" variant="secondary" class="px-3 py-1">
                        {{ tag }}
                        <button @click="removeTag(index)" class="ml-2 hover:text-muted-foreground">
                          <X class="h-3 w-3" />
                        </button>
                      </Badge>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Step 4: Review -->
            <div v-if="currentSubStep === 4" class="space-y-8">
              <!-- Endpoint Summary -->
              <div class="bg-card rounded-lg shadow-sm border border-border p-8">
                <div class="space-y-6">
                  <div>
                    <h2 class="heading-2 text-foreground mb-2">Endpoint Summary</h2>
                    <p class="text-sm text-muted-foreground">
                      Review your model endpoint configuration before deployment
                    </p>
                  </div>

                  <!-- Basic Information -->
                  <div class="border-l-4 border-primary pl-4">
                    <h3 class="font-medium text-foreground mb-2">Basic Information</h3>
                    <div class="space-y-1 body-sm">
                      <p>
                        <span class="font-medium">Name:</span>
                        {{ formData.endpointName || 'Not specified' }}
                      </p>
                      <p>
                        <span class="font-medium">Summary:</span>
                        {{ formData.summary || 'Not specified' }}
                      </p>
                      <div v-if="formData.description" class="space-y-2">
                        <p class="font-medium">Description:</p>
                        <div class="border border-border rounded-lg p-2">
                          <MdPreview :model-value="formData.description" :preview-theme="'github'"
                            :code-theme="'github'" language="en-US" />
                        </div>
                      </div>
                      <div v-if="formData.tags.length > 0">
                        <span class="font-medium">Tags:</span>
                        <span class="ml-2">
                          <Badge v-for="tag in formData.tags" :key="tag" variant="outline" class="mr-1">{{ tag }}
                          </Badge>
                        </span>
                      </div>
                    </div>
                  </div>

                  <!-- AI Model -->
                  <div class="border-l-4 border-purple-500 pl-4">
                    <h3 class="font-medium text-foreground mb-2">AI Model</h3>
                    <div class="body-sm space-y-1">
                      <div v-if="selectedModelSourceType === 'existing'">
                        <div v-if="formData.aiModel === 'nlp-engine'">
                          <p><span class="font-medium">Source:</span> Existing Model</p>
                          <p><span class="font-medium">Model:</span> NLP Processing Engine</p>
                          <p><span class="font-medium">Provider:</span> vLLM</p>
                          <p>
                            <span class="font-medium">Status:</span>
                            <Badge variant="outline" class="bg-muted/50 text-muted-foreground border-border body-sm">
                              Stopped</Badge>
                          </p>
                        </div>
                        <div v-else-if="formData.aiModel === 'local-llama'">
                          <p><span class="font-medium">Source:</span> Existing Model</p>
                          <p><span class="font-medium">Model:</span> Code Assistant Model</p>
                          <p><span class="font-medium">Provider:</span> Ollama</p>
                          <p>
                            <span class="font-medium">Status:</span>
                            <Badge variant="outline" class="bg-green-50 text-green-700 border-green-200 body-sm">Running
                            </Badge>
                          </p>
                        </div>
                        <p v-else>Not selected</p>
                      </div>
                      <div v-else-if="selectedModelSourceType === 'create-new'">
                        <p><span class="font-medium">Source:</span> New Model</p>
                        <p v-if="selectedNewModelType">
                          <span class="font-medium">Type:</span> {{ selectedNewModelName }}
                        </p>
                        <p v-if="selectedNewModelType" class="text-muted-foreground">
                          Configuration will be completed during deployment
                        </p>
                        <p v-else>Not configured</p>
                      </div>
                      <p v-else>Not configured</p>
                    </div>
                  </div>

                  <!-- Applied Policies -->
                  <div class="border-l-4 border-orange-500 pl-4">
                    <h3 class="font-medium text-foreground mb-2">Applied Policies</h3>
                    <div class="body-sm space-y-2">
                      <div v-if="Object.keys(getAppliedPoliciesGrouped()).length > 0" class="space-y-6">
                        <div v-for="(policyGroup, policyType) in getAppliedPoliciesGrouped()" :key="policyType"
                          class="space-y-3">
                          <!-- Policy Type Header -->
                          <div class="flex items-center gap-3">
                            <div :class="[
                              'p-2 rounded-lg',
                              policyGroup.color === 'blue' ? 'bg-primary/10' : '',
                              policyGroup.color === 'green' ? 'bg-green-100' : '',
                              policyGroup.color === 'yellow' ? 'bg-yellow-100' : '',
                              policyGroup.color === 'purple' ? 'bg-purple-100' : '',
                              policyGroup.color === 'red' ? 'bg-red-100' : '',
                            ]">
                              <component :is="policyGroup.icon" :class="[
                                'h-4 w-4',
                                policyGroup.color === 'blue' ? 'text-primary' : '',
                                policyGroup.color === 'green' ? 'text-green-600' : '',
                                policyGroup.color === 'yellow' ? 'text-yellow-600' : '',
                                policyGroup.color === 'purple' ? 'text-purple-600' : '',
                                policyGroup.color === 'red' ? 'text-red-600' : '',
                              ]" />
                            </div>
                            <h4 class="font-semibold text-foreground">{{ policyType }}</h4>
                            <span class="body-sm text-muted-foreground">({{ policyGroup.rules.length }} rule{{
                              policyGroup.rules.length !== 1 ? 's' : ''
                              }})</span>
                          </div>

                          <!-- Policy Rules -->
                          <div class="space-y-3 ml-6">
                            <div v-for="rule in policyGroup.rules" :key="rule.id"
                              class="bg-muted/50 border border-border rounded-lg p-4">
                              <h5 class="font-medium text-foreground mb-3">{{ rule.name }}</h5>
                              <div class="space-y-2 body-sm text-muted-foreground">
                                <!-- Authorization Policy Display -->
                                <div v-if="rule.config.ruleType">
                                  <p class="flex items-start">
                                    <span class="font-medium text-muted-foreground w-20 flex-shrink-0">Type:</span>
                                    <span>{{
                                      rule.config.ruleType === 'allow' ? 'Allow-list' : 'Deny-list'
                                    }}</span>
                                  </p>
                                  <p class="flex items-start">
                                    <span class="font-medium text-muted-foreground w-20 flex-shrink-0">Users:</span>
                                    <span>{{ rule.config.users || 'Not specified' }}</span>
                                  </p>
                                </div>

                                <!-- Rate Limiter Policy Display -->
                                <div v-if="rule.config.limit">
                                  <p class="flex items-start">
                                    <span class="font-medium text-muted-foreground w-20 flex-shrink-0">Limit:</span>
                                    <span>{{ rule.config.limit }} requests per
                                      {{ rule.config.windowValue }}
                                      {{ rule.config.windowUnit }}(s)</span>
                                  </p>
                                  <p class="flex items-start">
                                    <span class="font-medium text-muted-foreground w-20 flex-shrink-0">Scope:</span>
                                    <span>{{ rule.config.scope || 'Per user' }}</span>
                                  </p>
                                  <p v-if="rule.config.userType === 'only' && rule.config.users"
                                    class="flex items-start">
                                    <span class="font-medium text-muted-foreground w-20 flex-shrink-0">Users:</span>
                                    <span>Only {{ rule.config.users }}</span>
                                  </p>
                                  <p v-if="rule.config.userType === 'except' && rule.config.users"
                                    class="flex items-start">
                                    <span class="font-medium text-muted-foreground w-20 flex-shrink-0">Users:</span>
                                    <span>All except {{ rule.config.users }}</span>
                                  </p>
                                </div>

                                <!-- Pricing Policy Display -->
                                <div v-if="
                                  rule.config.price !== undefined &&
                                  rule.config.price !== null &&
                                  rule.config.price !== ''
                                ">
                                  <p class="flex items-start">
                                    <span class="font-medium text-muted-foreground w-20 flex-shrink-0">Price:</span>
                                    <span>${{ rule.config.price }} per call</span>
                                  </p>
                                  <p v-if="rule.config.userType === 'only' && rule.config.users"
                                    class="flex items-start">
                                    <span class="font-medium text-muted-foreground w-20 flex-shrink-0">Users:</span>
                                    <span>Only {{ rule.config.users }}</span>
                                  </p>
                                  <p v-if="rule.config.userType === 'except' && rule.config.users"
                                    class="flex items-start">
                                    <span class="font-medium text-muted-foreground w-20 flex-shrink-0">Users:</span>
                                    <span>All except {{ rule.config.users }}</span>
                                  </p>
                                </div>


                                <!-- AI Filters Policy Display -->
                                <div v-if="rule.config.modelId">
                                  <p class="flex items-start">
                                    <span class="font-medium text-muted-foreground w-20 flex-shrink-0">Model:</span>
                                    <span>{{
                                      mockModels.find((m) => m.id === rule.config.modelId)?.name ||
                                      rule.config.modelId
                                    }}</span>
                                  </p>
                                  <div v-if="rule.config.prompt" class="mt-2">
                                    <p class="font-medium text-muted-foreground mb-2">Prompt:</p>
                                    <div
                                      class="body-sm bg-card border rounded px-3 py-2 font-mono max-h-32 overflow-y-auto whitespace-pre-wrap">
                                      {{ rule.config.prompt }}
                                    </div>
                                  </div>
                                  <p v-if="rule.config.userType === 'only' && rule.config.users"
                                    class="flex items-start mt-2">
                                    <span class="font-medium text-muted-foreground w-20 flex-shrink-0">Users:</span>
                                    <span>Only {{ rule.config.users }}</span>
                                  </p>
                                  <p v-if="rule.config.userType === 'except' && rule.config.users"
                                    class="flex items-start mt-2">
                                    <span class="font-medium text-muted-foreground w-20 flex-shrink-0">Users:</span>
                                    <span>All except {{ rule.config.users }}</span>
                                  </p>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                      <p v-else class="text-muted-foreground">No policies applied</p>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Endpoint Visibility Card -->
              <div class="bg-card rounded-lg shadow-sm border border-border p-8">
                <div class="space-y-6">
                  <div>
                    <h2 class="heading-2 text-foreground mb-2">Endpoint Visibility</h2>
                    <p class="text-sm text-muted-foreground">
                      Configure who can discover your endpoint
                    </p>
                  </div>

                  <div class="space-y-4">
                    <!-- Public Endpoint -->
                    <div
                      class="flex items-center space-x-3 p-4 border-2 rounded-lg cursor-pointer transition-all duration-200 hover:bg-muted/50"
                      :class="endpointVisibility === 'public'
                        ? 'border-green-500 bg-green-50'
                        : 'border-border'
                        " @click="endpointVisibility = 'public'">
                      <input type="radio" id="public-endpoint" name="endpoint-visibility" value="public"
                        v-model="endpointVisibility"
                        class="w-4 h-4 text-green-600 border-border focus:ring-green-500" />
                      <div class="p-2 rounded-full bg-green-100">
                        <Globe class="w-5 h-5 text-green-600" />
                      </div>
                      <div class="flex-1">
                        <label for="public-endpoint" class="cursor-pointer">
                          <h4 class="font-medium text-foreground">Public Endpoint</h4>
                          <p class="text-sm text-muted-foreground">
                            Anyone can discover this endpoint.
                          </p>
                        </label>
                      </div>
                    </div>

                    <!-- Private Endpoint -->
                    <div
                      class="flex items-center space-x-3 p-4 border-2 rounded-lg cursor-pointer transition-all duration-200 hover:bg-muted/50"
                      :class="endpointVisibility === 'private'
                        ? 'border-primary bg-primary/10'
                        : 'border-border'
                        " @click="endpointVisibility = 'private'">
                      <input type="radio" id="private-endpoint" name="endpoint-visibility" value="private"
                        v-model="endpointVisibility" class="w-4 h-4 text-primary border-border focus:ring-blue-500" />
                      <div class="p-2 rounded-full bg-primary/10">
                        <Lock class="w-5 h-5 text-primary" />
                      </div>
                      <div class="flex-1">
                        <label for="private-endpoint" class="cursor-pointer">
                          <h4 class="font-medium text-foreground">Private Endpoint</h4>
                          <p class="text-sm text-muted-foreground">
                            Only selected users can discover this endpoint.
                          </p>
                        </label>
                      </div>
                    </div>
                  </div>

                  <!-- Allowed Users (shown when private is selected) -->
                  <div v-if="endpointVisibility === 'private'" class="space-y-4">
                    <div>
                      <h3 class="text-lg font-medium text-foreground mb-1">
                        Allowed Users (Optional)
                      </h3>
                      <p class="text-sm text-muted-foreground mb-4">
                        Add email addresses of users who can discover this endpoint. You can leave
                        this empty and add users later from the endpoint details page.
                      </p>
                    </div>

                    <div class="flex gap-2">
                      <Input v-model="allowedUserInput" @keydown.enter.prevent="addAllowedUser"
                        placeholder="user@example.com" :class="[
                          'flex-1',
                          hasInputError
                            ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                            : '',
                        ]" type="text" autocomplete="new-password" autocapitalize="off" autocorrect="off"
                        spellcheck="false" data-1p-ignore data-lpignore="true" data-bwignore data-protonpass-ignore
                        data-dashlane-ignore data-form-type="other" data-password-manager="false" role="textbox" />
                      <Button @click="addAllowedUser" variant="outline" size="default" class="px-4">
                        <Plus class="h-4 w-4" />
                      </Button>
                    </div>

                    <!-- Error message -->
                    <div v-if="allowedUserError"
                      class="body-sm text-red-600 bg-red-50 border border-red-200 rounded-md p-2">
                      {{ allowedUserError }}
                    </div>

                    <p class="body-sm text-muted-foreground">
                      Comma-separated list. Wildcard supported (e.g., *@company.com, *.edu,
                      *@contractors.org)
                    </p>

                    <!-- Display added users -->
                    <div v-if="allowedUsers.length > 0" class="flex flex-wrap gap-2">
                      <Badge v-for="(user, index) in allowedUsers" :key="index" variant="secondary"
                        class="px-3 py-1 flex items-center gap-2">
                        {{ user }}
                        <button @click="removeAllowedUser(index)" class="hover:text-muted-foreground transition-colors">
                          <X class="h-3 w-3" />
                        </button>
                      </Badge>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Navigation Buttons -->
            <div class="flex justify-between mt-8">
              <Button @click="handlePrevious" variant="outline" class="px-8">
                <ArrowLeft class="mr-2 h-4 w-4" />
                Previous
              </Button>

              <Button @click="handleNext" :disabled="!isCurrentStepValid"
                class="bg-primary hover:bg-primary/90 text-primary-foreground px-8 ml-auto">
                {{
                  currentSubStep === APP_LIMITS.TOTAL_MODEL_ENDPOINT_CREATION_STEPS
                    ? 'Publish Endpoint'
                    : 'Next'
                }}
                <ArrowRight class="ml-2 h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Model Dialog -->
    <CreateModelDialog v-model:open="showCreateModelDialog" @model-created="handleModelCreated" />
  </ErrorBoundary>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  Plus,
  X,
  ArrowRight,
  Save,
  FolderOpen,
  Code,
  ExternalLink,
  Search,
  Shield,
  Gauge,
  DollarSign,
  UserCheck,
  Filter as FilterIcon,
  Globe,
  Lock,
  Lightbulb,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { MdEditor, MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import CreateModelDialog from '@/components/CreateModelDialog.vue'
import { mockModels } from '@/stores/models'
import { APP_LIMITS, UI_CONSTANTS } from '@/lib/constants'
import ErrorBoundary from '@/components/ErrorBoundary.vue'

const router = useRouter()

// Sub-step navigation
const currentSubStep = ref(1)

// Step titles and descriptions
const stepTitles = [
  'What model are you sharing?',
  'Set rules & pricing',
  'Add details & publish',
  'Review',
]

const stepDescriptions = [
  'Choose to add a new model or use an existing one',
  'Control access, set rate limits, pricing, and approval policies',
  'Provide basic details about your model endpoint',
  'Review and deploy your model endpoint',
]

// Form data
const formData = ref({
  endpointName: '',
  summary: '',
  description: '',
  tags: [] as string[],
  aiModel: '',
  policies: {} as Record<string, boolean>,
})

// Tag input
const tagInput = ref('')

// Model source selection
const selectedModelSourceType = ref<string | null>(null)
const selectedNewModelType = ref<string | null>(null)
const searchQuery = ref('')

// Dialog states
const showCreateModelDialog = ref(false)

// Endpoint visibility
const endpointVisibility = ref<string>('')
const allowedUsers = ref<string[]>([])
const allowedUserInput = ref('')
const allowedUserError = ref('')
const hasInputError = ref(false)

// Policy configurations
interface PolicyConfig {
  id: string
  [key: string]: string | number
}

interface PolicyRule {
  id: string
  config: PolicyConfig
  isEditing: boolean
}

// Grouped policy interface for the review section
interface GroupedPolicy {
  type: string
  icon: typeof Shield | typeof Gauge | typeof DollarSign | typeof UserCheck | typeof FilterIcon
  color: string
  rules: {
    id: string
    name: string
    config: PolicyConfig
  }[]
}

const policyRules = ref<Record<string, PolicyRule[]>>({
  authorization: [] as PolicyRule[],
  ratelimiter: [] as PolicyRule[],
  pricing: [] as PolicyRule[],
  'ai-filters': [] as PolicyRule[],
})

// Currently editing rule ID for each policy type
const editingRuleId = ref<Record<string, string | null>>({
  authorization: null as string | null,
  ratelimiter: null as string | null,
  pricing: null as string | null,
  'ai-filters': null as string | null,
})

// Policy form data
const authorizationForm = ref({
  ruleType: 'allow',
  users: '',
  note: '',
})

const rateLimiterForm = ref({
  limit: '',
  windowUnit: 'minute',
  scope: 'per user',
  type: 'sliding window',
  userType: 'all',
  users: '',
  note: '',
})

const pricingForm = ref({
  price: '',
  userType: 'all',
  users: '',
  note: '',
})

const aiFiltersForm = ref({
  modelId: '',
  prompt: '',
  userType: 'all',
  users: '',
  note: '',
})

// Policy type interface
interface PolicyType {
  id: string
  name: string
  label: string
  description: string
  icon: typeof Shield | typeof Gauge | typeof DollarSign | typeof UserCheck | typeof FilterIcon
  color: string
}

// Policy types definition
const policyTypes: PolicyType[] = [
  {
    id: 'authorization',
    name: 'Authorization',
    label: 'Who can use this?',
    description: 'Allow or deny specific users from accessing this endpoint',
    icon: Shield,
    color: 'blue',
  },
  {
    id: 'ratelimiter',
    name: 'Rate Limiter',
    label: 'Handle traffic',
    description: 'Control request rates to prevent abuse and ensure fair resource usage',
    icon: Gauge,
    color: 'green',
  },
  {
    id: 'pricing',
    name: 'Pricing',
    label: 'Charge for usage',
    description: 'Set fixed per-request pricing and/or token-based pricing',
    icon: DollarSign,
    color: 'yellow',
  },
  {
    id: 'ai-filters',
    name: 'AI filters',
    label: 'AI safety filters',
    description: 'Filter or redact responses using an AI before sending them back.',
    icon: FilterIcon,
    color: 'red',
  },
]

// Model options (from CreateModelDialog)
const modelOptions = [
  { id: 'vllm', name: 'vLLM', type: 'Model' },
  { id: 'ollama', name: 'Ollama', type: 'Model' },
  { id: 'huggingface', name: 'Hugging Face', type: 'Model' },
  { id: 'custom', name: 'Custom', type: 'Model', isCustom: true },
]

// Count of existing models
const existingModelsCount = computed(() => mockModels.length)

// Filtered models for search
const filteredModels = computed(() => {
  if (!searchQuery.value) return modelOptions
  return modelOptions.filter((model) =>
    model.name.toLowerCase().includes(searchQuery.value.toLowerCase()),
  )
})

// Selected new model name
const selectedNewModelName = computed(() => {
  const model = modelOptions.find((m) => m.id === selectedNewModelType.value)
  return model?.name || 'Model'
})

// Step validation
const isStep1Valid = computed(() => {
  // Step 1: Model selection
  if (selectedModelSourceType.value === 'existing') {
    return formData.value.aiModel !== ''
  } else if (selectedModelSourceType.value === 'create-new') {
    return selectedNewModelType.value !== null
  }
  return false
})

// Can save draft when we have name (from step 3)
const canSaveDraft = computed(() => formData.value.endpointName.trim() !== '')

const isStep2Valid = computed(() => {
  // Step 2: Policies are always optional
  return true
})

const isStep3Valid = computed(() => {
  // Step 3: Basic details - require endpoint name
  return formData.value.endpointName.trim() !== ''
})

const isStep4Valid = computed(() => {
  // Review step requires endpoint visibility to be selected
  if (endpointVisibility.value === '') return false

  // If private is selected, require at least one user
  if (endpointVisibility.value === 'private') {
    return allowedUsers.value.length > 0
  }

  // For public, just need visibility selected
  return true
})

const isCurrentStepValid = computed(() => {
  if (currentSubStep.value === 1) return isStep1Valid.value
  if (currentSubStep.value === 2) return isStep2Valid.value
  if (currentSubStep.value === 3) return isStep3Valid.value
  return isStep4Valid.value
})

// Add tag
const addTag = () => {
  const tag = tagInput.value.trim()
  if (tag && !formData.value.tags.includes(tag)) {
    formData.value.tags.push(tag)
    tagInput.value = ''
  }
}

// Remove tag
const removeTag = (index: number) => {
  formData.value.tags.splice(index, 1)
}

// Select model source type
const selectModelSourceType = (type: string) => {
  selectedModelSourceType.value = type
  // Reset selections when changing type
  if (type !== 'existing') {
    formData.value.aiModel = ''
  }
  if (type !== 'create-new') {
    selectedNewModelType.value = null
  }
}

// Handle model created
const handleModelCreated = () => {
  // In a real app, this would update the model list and select the new model
  console.log('Model created')
  // If we're in the AI filters context, we could auto-select the new model
  // For now, just reset to empty so user can select from the updated list
  if (aiFiltersForm.value.modelId === 'create-new') {
    aiFiltersForm.value.modelId = ''
  }
}

// Get applied policies grouped by type for review
const getAppliedPoliciesGrouped = (): Record<string, GroupedPolicy> => {
  const groupedPolicies: Record<string, GroupedPolicy> = {}
  for (const [policyId, rules] of Object.entries(policyRules.value)) {
    if (rules.length > 0) {
      const policyType = policyTypes.find((p) => p.id === policyId)
      if (policyType) {
        const savedRules = rules.filter((rule) => !rule.isEditing)
        if (savedRules.length > 0) {
          groupedPolicies[policyType.name] = {
            type: policyType.name,
            icon: policyType.icon,
            color: policyType.color,
            rules: savedRules.map((rule, index) => ({
              id: rule.id,
              name: String(rule.config.note || `${policyType.name} rule #${index + 1}`),
              config: rule.config,
            })),
          }
        }
      }
    }
  }
  return groupedPolicies
}

// Parse config strings into key-value pairs

// Policy helper functions
const generateRuleId = () => {
  return 'rule_' + Math.random().toString(36).substr(2, 9)
}

const addPolicy = (policyId: string) => {
  const ruleId = generateRuleId()
  editingRuleId.value[policyId] = ruleId

  // Reset form data
  resetFormData(policyId)

  // Initialize array if not exists
  if (!policyRules.value[policyId]) {
    policyRules.value[policyId] = []
  }

  // Add new rule in editing state
  policyRules.value[policyId].push({
    id: ruleId,
    config: {} as PolicyConfig,
    isEditing: true,
  })
}

const savePolicy = (policyId: string, ruleId: string) => {
  let config: PolicyConfig = { id: ruleId }

  switch (policyId) {
    case 'authorization':
      config = { ...config, ...authorizationForm.value }
      break
    case 'ratelimiter':
      config = { ...config, ...rateLimiterForm.value, windowValue: '1' }
      break
    case 'pricing':
      config = { ...config, ...pricingForm.value, pricingType: 'per_call' }
      break
    case 'ai-filters':
      config = { ...config, ...aiFiltersForm.value }
      break
  }

  // Find and update the rule
  const rule = policyRules.value[policyId]?.find((r) => r.id === ruleId)
  if (rule) {
    rule.config = config as PolicyConfig
    rule.isEditing = false
  }

  editingRuleId.value[policyId] = null
}

const cancelEditPolicy = (policyId: string, ruleId: string) => {
  // Find and cancel editing for the rule
  const rule = policyRules.value[policyId]?.find((r) => r.id === ruleId)
  if (rule) {
    rule.isEditing = false
  }
  editingRuleId.value[policyId] = null
}

const editPolicy = (policyId: string, ruleId: string) => {
  // Set other rules to not editing
  policyRules.value[policyId]?.forEach((rule) => {
    rule.isEditing = rule.id === ruleId
  })

  editingRuleId.value[policyId] = ruleId

  // Load rule data into form
  const rule = policyRules.value[policyId]?.find((r) => r.id === ruleId)
  if (rule) {
    loadRuleIntoForm(policyId, rule.config)
  }
}

const deletePolicy = (policyId: string, ruleId: string) => {
  // Remove rule from array
  const index = policyRules.value[policyId]?.findIndex((r) => r.id === ruleId) ?? -1
  if (index > -1 && policyRules.value[policyId]) {
    policyRules.value[policyId].splice(index, 1)
  }

  // Clear editing state if this rule was being edited
  if (editingRuleId.value[policyId] === ruleId) {
    editingRuleId.value[policyId] = null
  }
}

const resetFormData = (policyId: string) => {
  switch (policyId) {
    case 'authorization':
      authorizationForm.value = { ruleType: 'allow', users: '', note: '' }
      break
    case 'ratelimiter':
      rateLimiterForm.value = {
        limit: '',
        windowUnit: 'minute',
        scope: 'per user',
        type: 'sliding window',
        userType: 'all',
        users: '',
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
    case 'ai-filters':
      aiFiltersForm.value = { modelId: '', prompt: '', userType: 'all', users: '', note: '' }
      break
  }
}

const loadRuleIntoForm = (policyId: string, config: PolicyConfig) => {
  switch (policyId) {
    case 'authorization':
      authorizationForm.value = {
        ruleType: (config.ruleType as string) || 'allow',
        users: (config.users as string) || '',
        note: (config.note as string) || '',
      }
      break
    case 'ratelimiter':
      rateLimiterForm.value = {
        limit: (config.limit as string) || '',
        windowUnit: (config.windowUnit as string) || 'minute',
        scope: (config.scope as string) || 'per user',
        type: (config.type as string) || 'sliding window',
        userType: (config.userType as string) || 'all',
        users: (config.users as string) || '',
        note: (config.note as string) || '',
      }
      break
    case 'pricing':
      pricingForm.value = {
        price: config.price !== undefined ? String(config.price) : '',
        userType: (config.userType as string) || 'all',
        users: (config.users as string) || '',
        note: (config.note as string) || '',
      }
      break
    case 'ai-filters':
      aiFiltersForm.value = {
        modelId: (config.modelId as string) || '',
        prompt: (config.prompt as string) || '',
        userType: (config.userType as string) || 'all',
        users: (config.users as string) || '',
        note: (config.note as string) || '',
      }
      break
  }
}

// Navigation handlers
const handleNext = () => {
  if (!isCurrentStepValid.value) return

  if (currentSubStep.value < APP_LIMITS.TOTAL_MODEL_ENDPOINT_CREATION_STEPS) {
    currentSubStep.value++
  } else {
    // Deploy the endpoint
    console.log('Deploying model endpoint with data:', formData.value)
    router.push({ name: 'endpoints' })
  }
}

const handlePrevious = () => {
  if (currentSubStep.value > 1) {
    currentSubStep.value--
  } else {
    router.push({ name: 'create' })
  }
}

const handleBack = () => {
  router.push({ name: 'endpoints' })
}

// Save draft function
const saveDraft = () => {
  if (!canSaveDraft.value) return

  console.log('Saving draft:', formData.value)
  // In a real app, this would save to local storage or backend
  // localStorage.setItem('modelEndpointDraft', JSON.stringify(formData.value))
}

// Open custom SDK documentation
const openCustomSDKDocs = () => {
  window.open('https://docs.openmined.org/custom-models', '_blank')
}


// Allowed users management
const addAllowedUser = () => {
  const input = allowedUserInput.value.trim()
  if (input) {
    // Clear previous errors
    allowedUserError.value = ''
    hasInputError.value = false

    // Handle comma-separated input
    const emails = input
      .split(',')
      .map((email) => email.trim())
      .filter((email) => email)
    const validEmails = []
    const invalidEmails = []
    const duplicateEmails = []

    for (const email of emails) {
      if (allowedUsers.value.includes(email)) {
        duplicateEmails.push(email)
      } else if (isValidEmailOrWildcard(email)) {
        validEmails.push(email)
      } else {
        invalidEmails.push(email)
      }
    }

    // Add valid emails
    allowedUsers.value.push(...validEmails)

    // Show error for invalid or duplicate emails
    if (invalidEmails.length > 0 || duplicateEmails.length > 0) {
      const errorMessages = []
      if (invalidEmails.length > 0) {
        errorMessages.push(`Invalid format: ${invalidEmails.join(', ')}`)
      }
      if (duplicateEmails.length > 0) {
        errorMessages.push(`Already added: ${duplicateEmails.join(', ')}`)
      }
      allowedUserError.value = errorMessages.join('. ')
      hasInputError.value = true

      // Clear error after configured delay
      setTimeout(() => {
        allowedUserError.value = ''
        hasInputError.value = false
      }, UI_CONSTANTS.ERROR_AUTO_CLEAR_DELAY)
    }

    // Clear input if all emails were processed (valid or invalid)
    if (validEmails.length > 0 || invalidEmails.length > 0) {
      allowedUserInput.value = ''
    }
  }
}

const removeAllowedUser = (index: number) => {
  allowedUsers.value.splice(index, 1)
}

// Fill example data function
const fillExampleData = (type: string) => {
  switch (type) {
    case 'code':
      formData.value.endpointName = 'gpt-4-code-helper'
      formData.value.summary = 'GPT-4 powered coding assistant for development tasks'
      formData.value.description =
        'A powerful coding assistant that helps with programming tasks, debugging, code reviews, and technical problem-solving. Specialized in multiple programming languages and frameworks.'
      formData.value.tags = ['coding', 'development', 'gpt-4', 'assistant']
      break
    case 'chat':
      formData.value.endpointName = 'conversational-ai'
      formData.value.summary = 'General purpose conversational AI assistant'
      formData.value.description =
        'A versatile AI assistant for general conversations, question answering, creative writing, and everyday tasks. Designed to be helpful, harmless, and honest.'
      formData.value.tags = ['conversation', 'chat', 'general', 'assistant']
      break
    case 'analysis':
      formData.value.endpointName = 'research-assistant'
      formData.value.summary = 'AI model specialized in data analysis and research'
      formData.value.description =
        'Advanced AI assistant focused on data analysis, research tasks, report generation, and analytical thinking. Perfect for academic and business research needs.'
      formData.value.tags = ['research', 'analysis', 'data', 'academic']
      break
  }
}

// Refresh form function
const refreshForm = () => {
  // Reset form data to initial state
  formData.value = {
    endpointName: '',
    summary: '',
    description: '',
    tags: [],
    aiModel: '',
    policies: {},
  }
  currentSubStep.value = 1
  tagInput.value = ''
}

const isValidEmailOrWildcard = (email: string) => {
  // Allow wildcard patterns like *@company.com, *.edu, *@contractors.org
  const wildcardEmailRegex = /^(\*|[^\s@]+)@([^\s@]+\.)*[^\s@]+$/
  const wildcardDomainRegex = /^\*\.[^\s@]+$/ // For patterns like *.edu, *.com
  const regularEmailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

  return (
    wildcardEmailRegex.test(email) ||
    wildcardDomainRegex.test(email) ||
    regularEmailRegex.test(email)
  )
}
</script>
