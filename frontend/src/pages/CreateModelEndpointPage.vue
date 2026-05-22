<!-- eslint-disable vue/no-parsing-error -->
<template>
  <ErrorBoundary
    :can-retry="true"
    :show-details="true"
    custom-title="Endpoint Creation Error"
    custom-message="There was a problem with the endpoint creation form. Please try again."
    @retry="refreshForm"
  >
    <div class="min-h-screen">
      <!-- Header -->
      <div class="bg-card border-b border-border">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div class="flex items-center justify-between">
            <Button
              variant="ghost"
              @click="handleBack"
              class="flex items-center text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft class="w-5 h-5 mr-2" />
              Back to Endpoints
            </Button>
          </div>
        </div>
      </div>

      <!-- Two-column layout -->
      <div class="flex gap-12 max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
        <!-- Left sidebar with steps -->
        <div class="w-80 flex-shrink-0">
          <div class="sticky top-8">
            <h2 class="heading-3 text-foreground mb-6">Setup Progress</h2>

            <!-- Vertical step list -->
            <div class="space-y-6">
              <!-- Step 1 -->
              <div
                class="flex items-start gap-4"
                :class="{
                  'cursor-pointer': isStepClickable(1),
                  'cursor-not-allowed': !isStepClickable(1),
                }"
                @click="navigateToStep(1)"
              >
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium body-sm transition-all',
                    currentSubStep >= 1
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground',
                    isStepClickable(1) ? 'hover:scale-105' : '',
                  ]"
                >
                  {{ currentSubStep > 1 ? '✓' : '1' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium body-sm transition-colors',
                      currentSubStep >= 1 ? 'text-foreground' : 'text-muted-foreground',
                      isStepClickable(1) ? 'hover:text-primary' : '',
                    ]"
                  >
                    What model are you sharing?
                  </h3>
                  <p class="body-sm text-muted-foreground mt-1">Choose your AI model source</p>
                  <div
                    v-if="currentSubStep > 1"
                    class="mt-2 body-sm text-primary bg-primary/10 px-2 py-1 rounded"
                  >
                    ✓ Completed
                  </div>
                  <div
                    v-else-if="currentSubStep === 1"
                    class="mt-2 body-sm text-primary font-medium"
                  >
                    Current step
                  </div>
                </div>
              </div>

              <!-- Step 2 -->
              <div
                class="flex items-start gap-4"
                :class="{
                  'cursor-pointer': isStepClickable(2),
                  'cursor-not-allowed': !isStepClickable(2),
                }"
                @click="navigateToStep(2)"
              >
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium body-sm transition-all',
                    currentSubStep >= 2
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground',
                    isStepClickable(2) ? 'hover:scale-105' : '',
                  ]"
                >
                  {{ currentSubStep > 2 ? '✓' : '2' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium body-sm transition-colors',
                      currentSubStep >= 2 ? 'text-foreground' : 'text-muted-foreground',
                      isStepClickable(2) ? 'hover:text-primary' : '',
                    ]"
                  >
                    Who can access it?
                  </h3>
                  <p class="body-sm text-muted-foreground mt-1">Control who can use your content</p>
                  <div
                    v-if="currentSubStep > 2"
                    class="mt-2 body-sm text-primary bg-primary/10 px-2 py-1 rounded"
                  >
                    ✓ Completed
                  </div>
                  <div
                    v-else-if="currentSubStep === 2"
                    class="mt-2 body-sm text-primary font-medium"
                  >
                    Current step
                  </div>
                </div>
              </div>

              <!-- Step 3 -->
              <div
                class="flex items-start gap-4"
                :class="{
                  'cursor-pointer': isStepClickable(3),
                  'cursor-not-allowed': !isStepClickable(3),
                }"
                @click="navigateToStep(3)"
              >
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium body-sm transition-all',
                    currentSubStep >= 3
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground',
                    isStepClickable(3) ? 'hover:scale-105' : '',
                  ]"
                >
                  {{ currentSubStep > 3 ? '✓' : '3' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium body-sm transition-colors',
                      currentSubStep >= 3 ? 'text-foreground' : 'text-muted-foreground',
                      isStepClickable(3) ? 'hover:text-primary' : '',
                    ]"
                  >
                    Tell us more about it
                  </h3>
                  <p class="body-sm text-muted-foreground mt-1">Name and describe your endpoint</p>
                  <div
                    v-if="currentSubStep > 3"
                    class="mt-2 body-sm text-primary bg-primary/10 px-2 py-1 rounded"
                  >
                    ✓ Completed
                  </div>
                  <div
                    v-else-if="currentSubStep === 3"
                    class="mt-2 body-sm text-primary font-medium"
                  >
                    Current step
                  </div>
                </div>
              </div>

              <!-- Step 4 -->
              <div
                class="flex items-start gap-4"
                :class="{
                  'cursor-pointer': isStepClickable(4),
                  'cursor-not-allowed': !isStepClickable(4),
                }"
                @click="navigateToStep(4)"
              >
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium body-sm transition-all',
                    currentSubStep >= 4
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground',
                    isStepClickable(4) ? 'hover:scale-105' : '',
                  ]"
                >
                  {{ currentSubStep > 4 ? '✓' : '4' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium body-sm transition-colors',
                      currentSubStep >= 4 ? 'text-foreground' : 'text-muted-foreground',
                      isStepClickable(4) ? 'hover:text-primary' : '',
                    ]"
                  >
                    Review & Publish
                  </h3>
                  <p class="body-sm text-muted-foreground mt-1">Final check and publish</p>
                  <div
                    v-if="currentSubStep > 4"
                    class="mt-2 body-sm text-primary bg-primary/10 px-2 py-1 rounded"
                  >
                    ✓ Completed
                  </div>
                  <div
                    v-else-if="currentSubStep === 4"
                    class="mt-2 body-sm text-primary font-medium"
                  >
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

          <!-- Step 1: What model are you sharing? -->
          <div v-if="currentSubStep === 1" class="space-y-8">
            <!-- Model Source Selection Cards - only show if there are existing models -->
            <div v-if="existingModelsCount > 0" class="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <!-- Add New Model Card -->
              <Card
                class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-primary hover:bg-gradient-to-br hover:from-primary/10 hover:to-primary/5 border-2 bg-card"
                :class="
                  selectedModelSourceType === 'create-new'
                    ? 'border-primary bg-gradient-to-br from-primary/10 to-primary/5'
                    : 'border-border'
                "
                @click="selectModelSourceType('create-new')"
              >
                <CardContent class="p-6">
                  <div class="flex flex-col items-center text-center">
                    <div
                      class="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center mb-4"
                    >
                      <Plus class="w-7 h-7 text-primary" />
                    </div>

                    <h3 class="heading-3 text-foreground mb-2">Add New Model</h3>

                    <p class="body-sm text-muted-foreground mb-3">Set up a new AI model</p>

                    <p class="body-sm text-muted-foreground">OpenAI, Groq, OpenRouter, and more</p>
                  </div>
                </CardContent>
              </Card>

              <!-- Select Existing Model Card -->
              <Card
                class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-green-300 dark:hover:border-green-400 hover:bg-gradient-to-br hover:from-green-50 hover:to-emerald-50 dark:hover:from-green-950/30 dark:hover:to-emerald-950/30 border-2 bg-card"
                :class="
                  selectedModelSourceType === 'existing'
                    ? 'border-green-500 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950/30 dark:to-emerald-950/30'
                    : 'border-border'
                "
                @click="selectModelSourceType('existing')"
              >
                <CardContent class="p-6 h-full">
                  <div class="flex flex-col items-center text-center h-full">
                    <div
                      class="w-14 h-14 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center mb-4"
                    >
                      <FolderOpen class="w-7 h-7 text-green-600 dark:text-green-400" />
                    </div>

                    <h3 class="heading-3 text-foreground mb-2">Use Existing Model</h3>

                    <p class="body-sm text-muted-foreground mb-4">
                      Select an AI model you already configured
                    </p>

                    <!-- Loading state -->
                    <div
                      v-if="loadingModels"
                      class="space-y-2 mb-4 flex-grow flex items-center justify-center"
                    >
                      <span class="body-sm text-muted-foreground">Loading models...</span>
                    </div>

                    <!-- Error state -->
                    <div
                      v-else-if="modelsError"
                      class="space-y-2 mb-4 flex-grow flex items-center justify-center"
                    >
                      <span class="body-sm text-red-600">Failed to load models</span>
                    </div>

                    <!-- Model list -->
                    <div v-else class="space-y-2 mb-4 flex-grow">
                      <div
                        v-for="model in displayedModels"
                        :key="model.id"
                        class="flex items-center gap-2 body-sm"
                      >
                        <div class="w-2 h-2 bg-primary rounded-full"></div>
                        <span class="text-muted-foreground truncate">{{ model.name }}</span>
                      </div>
                      <div
                        v-if="remainingModelsCount > 0"
                        class="flex items-center gap-2 body-sm text-muted-foreground"
                      >
                        <div class="w-2 h-2"></div>
                        <span>...and {{ remainingModelsCount }} more</span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <!-- Content based on selection -->
            <div v-if="selectedModelSourceType || existingModelsCount === 0">
              <!-- Add New Model Inline Form -->
              <div
                v-if="selectedModelSourceType === 'create-new' || existingModelsCount === 0"
                class="bg-card rounded-lg shadow-sm border border-border p-8"
              >
                <div class="space-y-6">
                  <div>
                    <h3 class="heading-3 text-foreground mb-2">Add New AI Model</h3>
                    <p class="body-sm text-muted-foreground">
                      Configure a new AI model for your endpoint
                    </p>
                  </div>

                  <!-- Provider -->
                  <div class="space-y-2">
                    <Label for="provider" class="body-sm font-medium">
                      Provider <span class="text-red-500">*</span>
                    </Label>
                    <Select v-model="newModelForm.provider">
                      <SelectTrigger id="provider" class="w-full">
                        <SelectValue placeholder="Select a provider" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem v-for="p in PROVIDERS" :key="p.id" :value="p.id">
                          {{ p.label }}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <p class="body-sm text-muted-foreground">Choose your AI model provider</p>
                  </div>

                  <!-- Base URL (shown when custom provider is selected) -->
                  <div v-if="newModelForm.provider === 'custom'" class="space-y-2">
                    <Label for="base-url" class="body-sm font-medium">
                      Base URL <span class="text-red-500">*</span>
                    </Label>
                    <Input
                      id="base-url"
                      v-model="newModelForm.baseUrl"
                      placeholder="https://your-api.example.com/v1"
                      class="w-full"
                    />
                    <p class="body-sm text-muted-foreground">
                      The OpenAI-compatible API base URL for your provider
                    </p>
                  </div>

                  <!-- API Key (shown after provider is selected) -->
                  <div v-if="newModelForm.provider" class="space-y-2">
                    <Label for="api-key" class="body-sm font-medium">
                      {{ getProviderLabel(newModelForm.provider) }} API Key
                      <span class="text-red-500">*</span>
                    </Label>
                    <Input
                      id="api-key"
                      v-model="newModelForm.apiKey"
                      type="password"
                      :placeholder="`Enter your ${getProviderLabel(newModelForm.provider)} API key`"
                      class="w-full"
                      autocomplete="new-password"
                      autocorrect="off"
                      autocapitalize="off"
                      spellcheck="false"
                      data-1p-ignore
                      data-lpignore="true"
                      data-form-type="other"
                      data-bwignore
                      data-bitwarden-watching="false"
                      role="textbox"
                      aria-label="API Key Input"
                      name="api-key-input"
                    />
                    <p class="body-sm text-muted-foreground">
                      Models will be fetched automatically after entering your key
                    </p>
                  </div>

                  <!-- Model (shown after API key is entered) -->
                  <div v-if="newModelForm.provider && newModelForm.apiKey.trim()" class="space-y-2">
                    <Label for="model" class="body-sm font-medium">
                      Model <span class="text-red-500">*</span>
                    </Label>
                    <ProviderModelCombobox
                      v-model="newModelForm.model"
                      :models="newProviderModels"
                      :is-loading="isLoadingNewModels"
                      :error="newModelsError"
                      :disabled="isLoadingNewModels"
                      placeholder="Select a model"
                    />
                    <p v-if="isLoadingNewModels" class="body-sm text-muted-foreground">
                      Fetching available models...
                    </p>
                    <p v-else-if="hasNewModelsFetched" class="body-sm text-muted-foreground">
                      {{ newProviderModels.length }} models available
                    </p>
                  </div>
                </div>
              </div>

              <!-- Existing Models List -->
              <div
                v-if="selectedModelSourceType === 'existing'"
                class="bg-card rounded-lg shadow-sm border border-border p-6"
              >
                <div class="space-y-4">
                  <h3 class="heading-3 text-foreground mb-4">Available AI Models</h3>

                  <!-- Loading state -->
                  <div v-if="loadingModels" class="flex items-center justify-center py-8">
                    <div class="flex items-center gap-2">
                      <Loader2 class="h-4 w-4 animate-spin" />
                      <span class="body-sm text-muted-foreground">Loading models...</span>
                    </div>
                  </div>

                  <!-- Error state -->
                  <div v-else-if="modelsError" class="flex items-center justify-center py-8">
                    <span class="body-sm text-red-600"
                      >Failed to load models: {{ modelsError }}</span
                    >
                  </div>

                  <!-- Models list -->
                  <div v-else-if="availableModels.length > 0" class="space-y-3">
                    <div
                      v-for="model in availableModels"
                      :key="model.id"
                      class="flex items-center space-x-3 p-4 border rounded-lg transition-colors"
                      :class="[
                        formData.aiModel === model.id
                          ? 'border-primary bg-primary/5'
                          : 'border-border',
                        'cursor-pointer hover:bg-muted/50',
                      ]"
                      @click="formData.aiModel = model.id"
                    >
                      <div class="flex items-center gap-3 flex-1">
                        <div class="p-2 bg-primary/10 rounded">
                          <Brain class="h-5 w-5 text-primary" />
                        </div>
                        <div class="flex-1">
                          <div class="flex items-center gap-2">
                            <span class="font-medium text-foreground">{{ model.name }}</span>
                            <Badge variant="secondary" class="body-sm"
                              >{{ model.configuration?.model || model.dtype }}
                            </Badge>
                          </div>
                          <p class="body-sm text-muted-foreground mt-1">
                            {{ model.summary || 'No description available' }}
                          </p>
                        </div>
                      </div>
                      <div
                        class="w-4 h-4 rounded-full border-2 flex items-center justify-center"
                        :class="
                          formData.aiModel === model.id
                            ? 'border-primary bg-primary'
                            : 'border-muted-foreground'
                        "
                      >
                        <div
                          v-if="formData.aiModel === model.id"
                          class="w-2 h-2 rounded-full bg-primary-foreground"
                        ></div>
                      </div>
                    </div>
                  </div>

                  <!-- Empty state -->
                  <div v-else class="flex items-center justify-center py-8">
                    <span class="body-sm text-muted-foreground">No models available</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Step 2: Who can access it? -->
          <div v-if="currentSubStep === 2" class="space-y-6">
            <!-- Policy Configuration -->
            <div class="space-y-6">
              <!-- Auth + Rate Limit policies (loop only non-pricing) -->
              <div
                v-for="policy in POLICY_TYPES.filter((p) => p.id !== 'pricing')"
                :key="policy.id"
                class="bg-card/60 backdrop-blur-sm border border-border/50 rounded-2xl p-6"
              >
                <!-- Policy Header -->
                <div class="flex items-center justify-between mb-3">
                  <div class="flex items-center gap-3">
                    <div
                      :class="[
                        'p-2 rounded-lg',
                        policy.color === 'blue' ? 'bg-blue-100 dark:bg-blue-900' : '',
                        policy.color === 'green' ? 'bg-green-100 dark:bg-green-900' : '',
                      ]"
                    >
                      <component
                        :is="policy.icon"
                        :class="[
                          'h-5 w-5',
                          policy.color === 'blue' ? 'text-blue-600 dark:text-blue-400' : '',
                          policy.color === 'green' ? 'text-green-600 dark:text-green-400' : '',
                        ]"
                      />
                    </div>
                    <div class="flex-1">
                      <h3 class="font-medium text-foreground">{{ policy.label }}</h3>
                      <p class="body-sm text-muted-foreground">{{ policy.description }}</p>
                    </div>
                  </div>
                  <Button @click="openAddPolicyDialog(policy.id)" variant="outline" size="sm">
                    <Plus class="h-4 w-4 mr-2" />
                    Add {{ policy.name }} rule
                  </Button>
                </div>

                <!-- Default Policy Message -->
                <div v-if="policyRules[policy.id]?.length === 0" class="mb-3">
                  <div
                    class="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800/50 rounded-xl px-4 py-3"
                  >
                    <p class="body-sm text-green-700 dark:text-green-300">
                      <strong class="font-medium">Default: </strong>
                      <span v-if="policy.id === 'access'"
                        >Open access - everyone can use your endpoint</span
                      >
                      <span v-else-if="policy.id === 'rate_limit'"
                        >No rate limits - unlimited usage</span
                      >
                    </p>
                  </div>
                </div>

                <!-- Empty State -->
                <div
                  v-if="policyRules[policy.id]?.length === 0"
                  class="text-center py-8 border-2 border-dashed border-border/50 rounded-xl bg-muted/50/20"
                >
                  <p class="text-muted-foreground body-sm">
                    No {{ policy.name.toLowerCase() }} rule added yet
                  </p>
                </div>

                <!-- Policy Rules -->
                <div v-if="policyRules[policy.id]?.length > 0" class="space-y-3">
                  <div
                    v-for="(rule, ruleIndex) in policyRules[policy.id] || []"
                    :key="rule.id"
                    class="bg-muted/50/30 border border-border/50/50 rounded-xl p-4"
                  >
                    <div class="flex items-start justify-between">
                      <div class="flex-1">
                        <h4 class="body-sm font-medium text-foreground">
                          {{ rule.config.note || `${policy.name} Rule #${ruleIndex + 1}` }}
                        </h4>
                        <p class="body-sm text-muted-foreground mt-1">
                          {{ getRuleSummary(policy.id, rule.config) }}
                        </p>
                      </div>
                      <div class="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          @click="openEditPolicyDialog(policy.id, rule.id)"
                        >
                          Edit
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          @click="deletePolicy(policy.id, rule.id)"
                        >
                          Delete
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Pricing section (uses AddPricingRuleDialog) -->
              <div class="bg-card/60 backdrop-blur-sm border border-border/50 rounded-2xl p-6">
                <div class="flex items-center justify-between mb-3">
                  <div class="flex items-center gap-3">
                    <div class="p-2 rounded-lg bg-yellow-100 dark:bg-yellow-900">
                      <DollarSign class="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
                    </div>
                    <div class="flex-1">
                      <h3 class="font-medium text-foreground">Set your price</h3>
                      <p class="body-sm text-muted-foreground">
                        Charge per query or make it free - you decide
                      </p>
                    </div>
                  </div>
                  <Button @click="showAddPricingRuleDialog = true" variant="outline" size="sm">
                    <Plus class="h-4 w-4 mr-2" />
                    Add Pricing rule
                  </Button>
                </div>

                <div v-if="policyRules.pricing?.length === 0" class="mb-3">
                  <div
                    class="bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800/50 rounded-xl px-4 py-3"
                  >
                    <p class="body-sm text-green-700 dark:text-green-300">
                      <strong class="font-medium">Default: </strong>
                      Free access - no charges applied
                    </p>
                  </div>
                </div>

                <div
                  v-if="policyRules.pricing?.length === 0"
                  class="text-center py-8 border-2 border-dashed border-border/50 rounded-xl bg-muted/50/20"
                >
                  <p class="text-muted-foreground body-sm">No pricing rule added yet</p>
                </div>

                <div v-if="policyRules.pricing?.length > 0" class="space-y-3">
                  <div
                    v-for="(rule, ruleIndex) in policyRules.pricing"
                    :key="rule.id"
                    class="bg-muted/50/30 border border-border/50/50 rounded-xl p-4"
                  >
                    <div class="flex items-start justify-between">
                      <div class="flex-1">
                        <h4 class="body-sm font-medium text-foreground">
                          {{ rule.config.note || `Pricing Rule #${ruleIndex + 1}` }}
                        </h4>
                        <p class="body-sm text-muted-foreground mt-1">
                          {{ getRuleSummary('pricing', rule.config) }}
                        </p>
                      </div>
                      <Button variant="outline" size="sm" @click="deletePolicy('pricing', rule.id)">
                        Delete
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Step 3: Tell us more about it -->
          <div
            v-if="currentSubStep === 3"
            class="bg-card rounded-lg shadow-sm border border-border p-8 space-y-8"
          >
            <!-- Interactive examples -->
            <div
              class="mb-8 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800/50 rounded-lg p-4"
            >
              <h4 class="font-medium text-blue-900 dark:text-blue-300 mb-3 flex items-center gap-2">
                <Lightbulb class="w-4 h-4" />
                Popular examples to get you started
              </h4>
              <p class="body-sm text-blue-700 dark:text-blue-400 mb-4">
                Click any example to auto-fill the form
              </p>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-4 body-sm">
                <button
                  @click="fillExampleData('code')"
                  class="bg-card p-3 rounded border hover:border-primary hover:shadow-sm transition-all text-left"
                >
                  <p class="font-medium text-foreground">💻 Code Assistant</p>
                  <p class="text-muted-foreground mt-1">
                    "GPT-4 Code Helper" - Helps with programming tasks and debugging
                  </p>
                </button>
                <button
                  @click="fillExampleData('chat')"
                  class="bg-card p-3 rounded border hover:border-primary hover:shadow-sm transition-all text-left"
                >
                  <p class="font-medium text-foreground">💬 Chat Assistant</p>
                  <p class="text-muted-foreground mt-1">
                    "Conversational AI" - General purpose chat and question answering
                  </p>
                </button>
                <button
                  @click="fillExampleData('analysis')"
                  class="bg-card p-3 rounded border hover:border-primary hover:shadow-sm transition-all text-left"
                >
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
                <div class="relative">
                  <Input
                    id="endpoint-name"
                    v-model="formData.endpointName"
                    placeholder="e.g., gpt-4-code-helper"
                    class="w-full font-mono body-sm pr-10"
                    :class="[
                      endpointNameError ? 'border-red-500 focus:ring-red-500' : '',
                      nameAvailabilityResult === 'available'
                        ? 'border-green-500 focus:ring-green-500'
                        : '',
                    ]"
                    @input="handleEndpointNameInput"
                  />
                  <!-- Loading, success, or error indicator -->
                  <div
                    class="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none"
                  >
                    <Loader2
                      v-if="isCheckingNameAvailability"
                      class="h-4 w-4 text-muted-foreground animate-spin"
                    />
                    <Check
                      v-else-if="nameAvailabilityResult === 'available'"
                      class="h-4 w-4 text-green-600"
                    />
                  </div>
                </div>
                <p v-if="endpointNameError" class="body-sm text-red-600">
                  {{ endpointNameError }}
                </p>
                <p
                  v-else-if="nameAvailabilityResult === 'available'"
                  class="body-sm text-green-600"
                >
                  ✓ This name is available
                </p>
                <p v-else class="body-sm text-muted-foreground">
                  This appears when people discover it. Use lowercase letters, numbers, and hyphens
                  only (e.g., my-data-source)
                </p>
              </div>

              <!-- Summary -->
              <div class="space-y-2">
                <Label for="summary" class="body-sm font-medium text-foreground">
                  Short Description <span class="text-red-500">*</span>
                </Label>
                <Input
                  id="summary"
                  v-model="formData.summary"
                  placeholder="e.g., GPT-4 powered coding assistant for development tasks"
                  class="w-full"
                />
                <p class="body-sm text-muted-foreground">
                  This appears when people browse available content
                </p>
              </div>

              <!-- Tags -->
              <div class="space-y-2">
                <Label for="tags" class="body-sm font-medium text-foreground">
                  Tags (Optional)
                </Label>
                <div class="space-y-2">
                  <div class="flex gap-2">
                    <Input
                      id="tags"
                      v-model="tagInput"
                      @keydown.enter.prevent="addTag"
                      placeholder="Add keywords like: legal, medical, research, finance"
                      class="flex-1"
                    />
                    <Button
                      @click="addTag"
                      variant="outline"
                      size="sm"
                      :disabled="!tagInput.trim()"
                    >
                      <Plus class="h-4 w-4" />
                    </Button>
                  </div>
                  <p class="body-sm text-muted-foreground">
                    Tags help others discover your content
                  </p>

                  <!-- Popular Tags Suggestions -->
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="text-xs text-muted-foreground">Popular:</span>
                    <Button
                      v-for="suggestion in popularTags"
                      :key="suggestion"
                      @click="addSuggestedTag(suggestion)"
                      variant="ghost"
                      size="sm"
                      class="h-6 px-2 text-xs"
                      :disabled="formData.tags.includes(suggestion)"
                    >
                      {{ suggestion }}
                    </Button>
                  </div>

                  <!-- Selected Tags -->
                  <div v-if="formData.tags.length > 0" class="flex flex-wrap gap-2 mt-3">
                    <Badge
                      v-for="(tag, index) in formData.tags"
                      :key="index"
                      variant="secondary"
                      class="px-3 py-1"
                    >
                      {{ tag }}
                      <button
                        @click="removeTag(index)"
                        class="ml-2 hover:text-destructive transition-colors"
                      >
                        <X class="h-3 w-3" />
                      </button>
                    </Badge>
                  </div>
                </div>
              </div>

              <!-- Add More Details Toggle -->
              <div class="border-t pt-4">
                <button
                  @click="showAdvancedDetails = !showAdvancedDetails"
                  class="flex items-center gap-2 body-sm text-primary hover:text-primary/80 transition-colors"
                >
                  <ChevronRight
                    :class="[
                      'w-4 h-4 transition-transform',
                      showAdvancedDetails ? 'rotate-90' : '',
                    ]"
                  />
                  Add more details (optional)
                </button>
              </div>

              <!-- Advanced Details -->
              <div v-if="showAdvancedDetails" class="space-y-4 pl-6 border-l-2 border-border/50">
                <div class="space-y-2">
                  <Label for="description" class="body-sm font-medium text-foreground">
                    Description
                  </Label>
                  <MdEditor
                    :model-value="formData.description || defaultDescriptionTemplate"
                    @update:model-value="formData.description = $event"
                    :height="200"
                    :theme="isDark ? 'dark' : 'light'"
                    :toolbars="[
                      'bold',
                      'italic',
                      'title',
                      'strikeThrough',
                      'unorderedList',
                      'orderedList',
                      'link',
                      'code',
                      'codeRow',
                    ]"
                    :preview-theme="'github'"
                    :code-theme="'github'"
                    language="en-US"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- Step 4: Review & Publish -->
          <div v-if="currentSubStep === 4" class="space-y-6">
            <!-- Header - only show when not creating -->
            <div
              v-if="!isCreating"
              class="bg-card/60 backdrop-blur-sm border border-border/50 rounded-2xl p-8 text-center"
            >
              <div
                class="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto mb-4"
              >
                <svg
                  class="w-8 h-8 text-green-600 dark:text-green-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M5 13l4 4L19 7"
                  ></path>
                </svg>
              </div>
              <h2 class="heading-1 text-foreground mb-2">Ready to Publish!</h2>
              <p class="text-muted-foreground max-w-md mx-auto">
                Your model endpoint is configured and ready to go. Review the summary below and
                publish when you're ready.
              </p>
            </div>

            <!-- Creation Progress -->
            <div
              v-if="isCreating"
              class="bg-card/60 backdrop-blur-sm border border-border/50 rounded-2xl p-8 text-center"
            >
              <div
                class="w-16 h-16 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center mx-auto mb-4 animate-pulse"
              >
                <svg
                  class="w-8 h-8 text-blue-600 dark:text-blue-400 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    class="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    stroke-width="4"
                  ></circle>
                  <path
                    class="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
              </div>
              <h3 class="heading-2 text-foreground mb-2">Creating Endpoint...</h3>
              <p class="text-muted-foreground">
                {{ creationStep || 'Setting up your model endpoint...' }}
              </p>
            </div>

            <!-- Summary - only show when not creating -->
            <div v-if="!isCreating" class="bg-card border border-border rounded-2xl p-8 space-y-6">
              <!-- Basic Information -->
              <div>
                <h3 class="heading-2 text-foreground mb-6">Summary</h3>

                <div class="mb-6">
                  <div>
                    <p class="body-sm font-medium text-muted-foreground mb-2">Name</p>
                    <p class="text-foreground font-medium">
                      {{ formData.endpointName || 'Not specified' }}
                    </p>
                  </div>
                </div>

                <div>
                  <p class="body-sm font-medium text-muted-foreground mb-2">Summary</p>
                  <p class="text-foreground leading-relaxed">
                    {{ formData.summary || 'Not specified' }}
                  </p>
                </div>

                <!-- Detailed Description Preview -->
                <div v-if="formData.description && formData.description.trim()" class="mt-6">
                  <p class="body-sm font-medium text-muted-foreground mb-3">Detailed Description</p>
                  <div class="bg-muted/30 border border-border rounded-lg p-4">
                    <div class="prose prose-sm max-w-none text-muted-foreground">
                      <div class="markdown-content">
                        <MdPreview
                          :model-value="formData.description"
                          :theme="isDark ? 'dark' : 'light'"
                          :show-code-row-number="false"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="formData.tags.length > 0" class="mt-6">
                  <p class="body-sm font-medium text-muted-foreground mb-3">Tags</p>
                  <div class="flex flex-wrap gap-2">
                    <Badge
                      v-for="tag in formData.tags"
                      :key="tag"
                      variant="outline"
                      class="bg-primary/10 text-primary border-primary px-3 py-1"
                      >{{ tag }}</Badge
                    >
                  </div>
                </div>
              </div>

              <!-- Model Configuration -->
              <div class="border-t pt-6">
                <p class="body-sm font-medium text-muted-foreground mb-3">
                  Model Configuration
                  <span v-if="selectedModelSourceType === 'existing'" class="text-green-600"
                    >(Existing Model)</span
                  >
                  <span v-else-if="selectedModelSourceType === 'create-new'" class="text-blue-600"
                    >(New Model)</span
                  >
                </p>
                <div class="bg-muted/50 rounded-lg p-4">
                  <div class="body-sm space-y-3">
                    <!-- Existing Model Display -->
                    <div
                      v-if="selectedModelSourceType === 'existing' && formData.aiModel"
                      class="space-y-3"
                    >
                      <div class="flex items-start gap-3">
                        <Brain class="w-4 h-4 text-green-600 mt-0.5" />
                        <div class="flex-1">
                          <div class="flex items-center gap-2 mb-1">
                            <span class="font-medium text-foreground">{{
                              getSelectedModelDetails()?.name || 'Selected Model'
                            }}</span>
                            <Badge variant="secondary" class="body-sm">
                              {{
                                getSelectedModelDetails()?.configuration?.model ||
                                getSelectedModelDetails()?.dtype ||
                                'AI Model'
                              }}
                            </Badge>
                          </div>
                          <p class="text-muted-foreground body-sm">
                            {{
                              getSelectedModelDetails()?.summary ||
                              'AI model for intelligent responses and conversations'
                            }}
                          </p>
                        </div>
                      </div>
                    </div>

                    <!-- New Model Display -->
                    <div
                      v-else-if="
                        selectedModelSourceType === 'create-new' &&
                        newModelForm.provider &&
                        newModelForm.model
                      "
                      class="space-y-3"
                    >
                      <div class="flex items-start gap-3">
                        <Plus class="w-4 h-4 text-primary mt-0.5" />
                        <div class="flex-1">
                          <div class="flex items-center gap-2 mb-1">
                            <span class="font-medium text-foreground">{{
                              getDerivedModelName()
                            }}</span>
                            <Badge variant="secondary" class="body-sm">
                              {{ getSelectedNewModelLabel() || newModelForm.model }}
                            </Badge>
                          </div>
                          <p class="text-muted-foreground body-sm mb-2">
                            {{ getDerivedModelDescription() }}
                          </p>
                          <div class="grid grid-cols-2 gap-3 body-sm">
                            <div>
                              <span class="text-muted-foreground">Provider:</span>
                              <span class="ml-2 font-medium text-foreground">{{
                                getProviderLabel(newModelForm.provider)
                              }}</span>
                            </div>
                            <div>
                              <span class="text-muted-foreground">Model:</span>
                              <span class="ml-2 font-medium text-foreground">{{
                                getSelectedNewModelLabel() || newModelForm.model
                              }}</span>
                            </div>
                            <div class="col-span-2">
                              <span class="text-muted-foreground">API Key:</span>
                              <span class="ml-2 font-medium text-foreground">{{
                                newModelForm.apiKey
                                  ? '•'.repeat(8) + newModelForm.apiKey.slice(-4)
                                  : 'Not provided'
                              }}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- No Model Selected -->
                    <div v-else class="flex items-start gap-3">
                      <Sparkles class="w-4 h-4 text-muted-foreground mt-0.5" />
                      <div>
                        <span class="font-medium text-muted-foreground">No model selected</span>
                        <p class="text-muted-foreground body-sm mt-1">
                          Please complete Step 1 to configure your AI model
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Access Policies Summary -->
              <div
                v-if="Object.values(policyRules).some((rules) => rules.length > 0)"
                class="border-t pt-6"
              >
                <p class="body-sm font-medium text-muted-foreground mb-3">Access Policies</p>
                <div class="space-y-4">
                  <div v-for="policyType in POLICY_TYPES" :key="policyType.id">
                    <div
                      v-if="policyRules[policyType.id]?.length > 0"
                      class="bg-muted/50 rounded-lg p-4"
                    >
                      <div class="flex items-center gap-2 mb-3">
                        <component :is="policyType.icon" class="w-4 h-4 text-muted-foreground" />
                        <span class="body-sm font-medium text-foreground">{{
                          policyType.name
                        }}</span>
                        <Badge variant="secondary" class="body-sm">
                          {{ policyRules[policyType.id].length }}
                          {{ policyRules[policyType.id].length === 1 ? 'rule' : 'rules' }}
                        </Badge>
                      </div>
                      <!-- Rule Details -->
                      <div class="space-y-2">
                        <div
                          v-for="(rule, index) in policyRules[policyType.id]"
                          :key="rule.id"
                          class="bg-card/50 border border-border/50 rounded-lg p-3"
                        >
                          <div class="flex items-start justify-between">
                            <div class="flex-1">
                              <h4 class="body-sm font-medium text-foreground mb-1">
                                {{ rule.config.note || `${policyType.name} Rule #${index + 1}` }}
                              </h4>
                              <p class="body-sm text-muted-foreground">
                                {{ getRuleSummary(policyType.id, rule.config) }}
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Error Display (only in step 4) -->
          <div
            v-if="creationError && currentSubStep === 4"
            class="mt-6 p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg"
          >
            <div class="flex items-start gap-3">
              <X class="w-5 h-5 text-red-500 dark:text-red-400 flex-shrink-0 mt-0.5" />
              <div class="flex-1">
                <h4 class="font-medium text-red-900 dark:text-red-300 mb-1">
                  Failed to create endpoint
                </h4>
                <p class="text-sm text-red-700 dark:text-red-400">{{ creationError }}</p>
              </div>
            </div>
          </div>

          <!-- Navigation Buttons -->
          <div class="flex justify-between mt-8 pt-6 border-t border-border">
            <Button
              variant="outline"
              @click="currentSubStep === 1 ? handleBack() : previousStep()"
              :disabled="isCreating"
            >
              {{ currentSubStep === 1 ? 'Cancel' : 'Back' }}
            </Button>
            <Button
              @click="nextStep"
              :disabled="!isCurrentStepValid || isCreating || isCheckingBeforePublish"
              class="bg-primary hover:bg-primary/90 text-primary-foreground px-8"
            >
              <template v-if="currentSubStep === 4 && isCheckingBeforePublish">
                <Loader2 class="mr-2 h-4 w-4 animate-spin" />
                Checking...
              </template>
              <template v-else-if="currentSubStep === 4 && isCreating">
                {{ creationStep || 'Publishing...' }}
              </template>
              <template v-else>
                {{ currentSubStep === 4 ? 'Publish to SyftHub' : 'Continue' }}
              </template>
              <ArrowRight v-if="!isCreating && !isCheckingBeforePublish" class="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  </ErrorBoundary>

  <!-- Overwrite Confirmation Dialog -->
  <Dialog :open="showOverwriteDialog" @update:open="showOverwriteDialog = $event">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2">
          <AlertTriangle class="h-5 w-5 text-yellow-500" />
          Endpoint Name Already Exists
        </DialogTitle>
        <DialogDescription class="space-y-3">
          <span class="block">
            The endpoint name "<span class="font-medium">{{ formData.endpointName }}</span
            >" is already taken on SyftHub. Proceeding will overwrite the existing endpoint with the
            same name.
          </span>
          <a
            v-if="existingEndpointUrl"
            :href="existingEndpointUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1 text-primary hover:underline"
          >
            View existing endpoint
            <ExternalLink class="h-3 w-3" />
          </a>
        </DialogDescription>
      </DialogHeader>
      <DialogFooter class="gap-2">
        <Button variant="outline" @click="handleOverwriteCancel"> Cancel </Button>
        <Button variant="destructive" @click="handleOverwriteConfirm"> Overwrite </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>

  <!-- Policy Form Dialog (for auth + rate limit) -->
  <PolicyFormDialog
    v-model:open="showPolicyDialog"
    :policy-type="dialogPolicyType"
    :initial-data="dialogInitialData"
    @save="handlePolicyDialogSave"
  />

  <!-- Add Pricing Rule Dialog (for pricing — bundle or micro) -->
  <AddPricingRuleDialog
    v-model:open="showAddPricingRuleDialog"
    :locked-wallet-id="lockedWalletId"
    :endpoint-has-dataset="false"
    @pricing-created="handlePricingRuleCreated"
  />
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  ArrowRight,
  FolderOpen,
  Brain,
  ChevronRight,
  Plus,
  X,
  Sparkles,
  Lightbulb,
  Loader2,
  Check,
  AlertTriangle,
  ExternalLink,
  DollarSign,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import ProviderModelCombobox from '@/components/ProviderModelCombobox.vue'
import PolicyFormDialog from '@/components/PolicyFormDialog.vue'
import AddPricingRuleDialog from '@/components/AddPricingRuleDialog.vue'
import { PROVIDERS, getProviderLabel, getProviderBaseUrl } from '@/config/providers'
import {
  POLICY_TYPES,
  getRuleSummary,
  generateRuleId,
  createEmptyPolicyRules,
} from '@/config/policyTypes'
import type { PolicyTypeId, PolicyRulesRecord, PolicyConfig } from '@/config/policyTypes'
import { useProviderModels } from '@/composables/useProviderModels'
import { useTheme } from '@/composables/useTheme'
import { MdEditor, MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { modelsApi } from '@/api/endpoints/models'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { useModelEndpointCreation } from '@/composables/useModelEndpointCreation'
import { useUserStore } from '@/stores/user'
import type { ModelListItem } from '@/api/types'

const router = useRouter()
const userStore = useUserStore()
const { isDark } = useTheme()

// Computed URL to view existing endpoint on SyftHub
const existingEndpointUrl = computed(() =>
  userStore.getEndpointUrlInMarketplace(formData.value.endpointName),
)

// Model endpoint creation composable
const { isCreating, creationError, creationStep, createModelEndpointWithData, reset } =
  useModelEndpointCreation()

// Sub-step navigation
const currentSubStep = ref(1)

// Track completed steps - only allow navigation to completed steps
const completedSteps = ref<Set<number>>(new Set())

const showAdvancedDetails = ref(false)

// Tag input
const tagInput = ref('')

// Model source selection
const selectedModelSourceType = ref<string | null>(null)
const selectedNewModelType = ref<string | null>(null)

// New model form data
const newModelForm = ref({
  provider: '',
  model: '',
  apiKey: '',
  baseUrl: '',
})

// Provider models for new model creation
const newModelBaseUrlRef = computed(() =>
  newModelForm.value.provider === 'custom'
    ? newModelForm.value.baseUrl
    : getProviderBaseUrl(newModelForm.value.provider),
)
const newModelApiKeyRef = computed(() => newModelForm.value.apiKey)
const {
  models: newProviderModels,
  isLoading: isLoadingNewModels,
  error: newModelsError,
  hasFetched: hasNewModelsFetched,
} = useProviderModels(newModelBaseUrlRef, newModelApiKeyRef)

// Track user input for validation timing
const hasTypedEndpointName = ref(false)

// Name validation state
const isCheckingNameAvailability = ref(false)
const nameAvailabilityResult = ref<'available' | 'taken' | null>(null)
const nameCheckDebounceTimer = ref<number | null>(null)

// Overwrite confirmation dialog state
const showOverwriteDialog = ref(false)
const isCheckingBeforePublish = ref(false)

// Popular tag suggestions
const popularTags = ['legal', 'medical', 'research', 'finance', 'education', 'news', 'technical']

// Description template for model documentation
const defaultDescriptionTemplate = `## Model Overview
Brief summary of what this model does and its primary capabilities...

## Model Details
- **Type**: Text generation, code assistance, analysis, etc.
- **Base model**: Foundation model or architecture used
- **Specialization**: Domain-specific training or fine-tuning
- **Languages**: Supported programming/natural languages

## Capabilities
- **Primary functions**: Main tasks the model excels at
- **Input format**: Text, code, structured data, etc.
- **Output format**: Generated text, code, analysis results
- **Performance**: Response time and accuracy expectations

## Use Cases
- Development and coding assistance
- Content generation and writing
- Data analysis and insights
- Educational and research applications

## Model Limitations
- **Scope**: Tasks the model may not handle well
- **Accuracy**: Known limitations or edge cases
- **Biases**: Potential response biases or skews
- **Ethical considerations**: Usage guidelines and restrictions

## Attribution & Usage
How to properly credit this model when used in projects or research...`

// Computed properties for model display
const existingModelsCount = computed(() => availableModels.value.length)

const displayedModels = computed(() => {
  // If we have more than 3 models, show only 2 so we can add "...and X more" as the 3rd line
  const maxToShow = availableModels.value.length > 3 ? 2 : 3
  return availableModels.value.slice(0, maxToShow)
})

const remainingModelsCount = computed(() => {
  // If we have more than 3 models, remaining count is based on showing only 2
  return availableModels.value.length > 3 ? availableModels.value.length - 2 : 0
})

// Policy state
const policyRules = ref<PolicyRulesRecord>(createEmptyPolicyRules())

// Policy dialog state
const showPolicyDialog = ref(false)
const showAddPricingRuleDialog = ref(false)
const dialogPolicyType = ref<PolicyTypeId>('access')
const dialogInitialData = ref<Record<string, unknown> | null>(null)
const dialogEditingRuleId = ref<string | null>(null)

// Step titles and descriptions
const stepTitles = [
  'What model are you sharing?',
  'Who can access it?',
  'Tell us more about it',
  '',
]

const stepDescriptions = computed(() => [
  existingModelsCount.value > 0
    ? 'Choose to add a new model or use an existing one'
    : 'Set up a new AI model from one of our supported providers',
  'Control who can access your model and whether to charge for it',
  "Give your model a name and description so others know what you're sharing",
  '',
])

// Form data
const formData = ref({
  endpointName: '',
  summary: '',
  description: '',
  tags: [] as string[],
  aiModel: '',
})

// Models state
const availableModels = ref<ModelListItem[]>([])
const loadingModels = ref(false)
const modelsError = ref<string | null>(null)

// Helper function to validate slug format
const isValidSlug = (slug: string): boolean => {
  return /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)
}

// Check name availability with the API
const checkNameAvailability = async (name: string) => {
  if (!name || !isValidSlug(name)) {
    nameAvailabilityResult.value = null
    return
  }

  isCheckingNameAvailability.value = true
  nameAvailabilityResult.value = null

  try {
    const response = await endpointsApi.validateSlug({
      slug: name,
      check_all_marketplaces: true,
    })

    // Must be available locally; marketplaces with unknown status (null) don't block
    const localAvailable = response.local_available
    const marketplacesAvailable =
      !response.marketplaces || response.marketplaces.every((m) => m.available !== false)

    nameAvailabilityResult.value = localAvailable && marketplacesAvailable ? 'available' : 'taken'
  } catch (error) {
    nameAvailabilityResult.value = null
    console.error('Error checking name availability:', error)
  } finally {
    isCheckingNameAvailability.value = false
  }
}

// Debounced name checking
const debouncedCheckNameAvailability = (name: string) => {
  if (nameCheckDebounceTimer.value) {
    clearTimeout(nameCheckDebounceTimer.value)
  }

  nameCheckDebounceTimer.value = setTimeout(() => {
    checkNameAvailability(name)
  }, 500) // 500ms debounce
}

const endpointNameError = computed(() => {
  if (!hasTypedEndpointName.value) {
    return null
  }

  const name = formData.value.endpointName.trim()
  if (!name) {
    return 'Name is required'
  }
  if (!isValidSlug(name)) {
    return 'Name must contain only lowercase letters and numbers, with hyphens as word separators (e.g., my-data-source)'
  }
  if (nameAvailabilityResult.value === 'taken') {
    return 'This name is already taken. Please choose a different name.'
  }
  return null
})

const isCurrentStepValid = computed(() => {
  if (currentSubStep.value === 1) {
    // Step 1: Model selection
    if (selectedModelSourceType.value === 'existing') {
      return formData.value.aiModel !== ''
    } else if (selectedModelSourceType.value === 'create-new') {
      const baseValid =
        newModelForm.value.provider !== 'custom' || newModelForm.value.baseUrl.trim() !== ''
      return (
        newModelForm.value.provider !== '' &&
        newModelForm.value.model !== '' &&
        newModelForm.value.apiKey.trim() !== '' &&
        baseValid
      )
    }
    return false
  }
  if (currentSubStep.value === 2) {
    return true // Access rules are optional
  }
  if (currentSubStep.value === 3) {
    const slug = formData.value.endpointName.trim()
    const basicFieldsValid =
      slug !== '' &&
      isValidSlug(slug) &&
      formData.value.summary.trim() !== '' &&
      nameAvailabilityResult.value === 'available' &&
      !isCheckingNameAvailability.value

    return basicFieldsValid
  }
  if (currentSubStep.value === 4) {
    return true // Review step
  }
  return true
})

// Methods
const handleBack = () => {
  router.push({ name: 'endpoints' })
}

// Handle endpoint name input changes
const handleEndpointNameInput = () => {
  hasTypedEndpointName.value = true
  const name = formData.value.endpointName.trim()

  // Reset availability state when name changes
  nameAvailabilityResult.value = null

  // Only check availability if the name is valid format
  if (name && isValidSlug(name)) {
    debouncedCheckNameAvailability(name)
  }
}

const nextStep = async () => {
  if (isCurrentStepValid.value && currentSubStep.value < 4) {
    // Mark current step as completed when moving to the next step
    completedSteps.value.add(currentSubStep.value)
    currentSubStep.value++
  } else if (currentSubStep.value === 4) {
    // Check availability one more time before publishing
    isCheckingBeforePublish.value = true
    try {
      const response = await endpointsApi.validateSlug({
        slug: formData.value.endpointName,
        check_all_marketplaces: true,
      })

      const marketplacesAvailable =
        !response.marketplaces || response.marketplaces.every((m) => m.available !== false)

      if (!marketplacesAvailable) {
        // Show warning dialog if name is taken on any marketplace
        isCheckingBeforePublish.value = false
        showOverwriteDialog.value = true
        return
      }
    } catch (error) {
      console.error('Error checking availability before publish:', error)
      // Continue with publish even if check fails
    } finally {
      isCheckingBeforePublish.value = false
    }

    await publishEndpoint()
  }
}

const publishEndpoint = async () => {
  const modelEndpointData = {
    selectedModelSourceType: selectedModelSourceType.value as 'create-new' | 'existing' | '',
    newModelForm: newModelForm.value,
    selectedModelId: formData.value.aiModel,
    policyRules: policyRules.value,
    endpointName: formData.value.endpointName,
    summary: formData.value.summary,
    description: formData.value.description,
    tags: formData.value.tags,
  }

  await createModelEndpointWithData(modelEndpointData)
}

const handleOverwriteConfirm = async () => {
  showOverwriteDialog.value = false
  await publishEndpoint()
}

const handleOverwriteCancel = () => {
  showOverwriteDialog.value = false
}

const previousStep = () => {
  if (currentSubStep.value > 1) {
    // Clear creation errors when navigating away from step 4
    if (currentSubStep.value === 4) {
      reset()
    }
    currentSubStep.value--
  }
}

// Add tag
const addTag = () => {
  const tag = tagInput.value.trim().toLowerCase()
  if (tag && !formData.value.tags.includes(tag)) {
    formData.value.tags.push(tag)
    tagInput.value = ''
  }
}

// Add suggested tag
const addSuggestedTag = (tag: string) => {
  if (!formData.value.tags.includes(tag)) {
    formData.value.tags.push(tag)
  }
}

// Remove tag
const removeTag = (index: number) => {
  formData.value.tags.splice(index, 1)
}

// Navigate to a specific step (only if it's completed, current, or next available step)
const navigateToStep = (targetStep: number) => {
  // Allow navigation to completed steps, current step, or the next step after the highest completed step
  const highestCompletedStep = Math.max(0, ...Array.from(completedSteps.value))
  const allowedStep = targetStep <= Math.max(highestCompletedStep + 1, currentSubStep.value)

  if (allowedStep) {
    currentSubStep.value = targetStep

    // Clear creation errors when navigating away from step 4
    if (targetStep !== 4) {
      reset()
    }
  }
}

// Check if a step is clickable (completed, current, or next available step)
const isStepClickable = (stepNumber: number) => {
  const highestCompletedStep = Math.max(0, ...Array.from(completedSteps.value))
  return stepNumber <= Math.max(highestCompletedStep + 1, currentSubStep.value)
}

// Fill example data
const fillExampleData = (exampleType: 'code' | 'chat' | 'analysis') => {
  hasTypedEndpointName.value = true // Mark as user input for validation

  switch (exampleType) {
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

  // Trigger name availability check for the filled name
  const name = formData.value.endpointName
  if (name && isValidSlug(name)) {
    debouncedCheckNameAvailability(name)
  }
}

// Policy dialog functions
const openAddPolicyDialog = (policyId: PolicyTypeId) => {
  dialogPolicyType.value = policyId
  dialogInitialData.value = null
  dialogEditingRuleId.value = null
  showPolicyDialog.value = true
}

const openEditPolicyDialog = (policyId: PolicyTypeId, ruleId: string) => {
  const rule = policyRules.value[policyId].find((r) => r.id === ruleId)
  if (!rule) return
  dialogPolicyType.value = policyId
  dialogInitialData.value = { ...rule.config }
  dialogEditingRuleId.value = ruleId
  showPolicyDialog.value = true
}

const handlePolicyDialogSave = (payload: {
  policyType: PolicyTypeId
  formData: Record<string, unknown>
}) => {
  const { policyType, formData: policyFormData } = payload

  if (dialogEditingRuleId.value) {
    // Update existing rule
    const rule = policyRules.value[policyType].find((r) => r.id === dialogEditingRuleId.value)
    if (rule) {
      rule.config = {
        ...policyFormData,
        id: rule.id,
      } as PolicyRulesRecord[PolicyTypeId][number]['config']
    }
  } else {
    // Add new rule
    const ruleId = generateRuleId()
    policyRules.value[policyType].push({
      id: ruleId,
      config: {
        ...policyFormData,
        id: ruleId,
      } as PolicyRulesRecord[PolicyTypeId][number]['config'],
      isEditing: false,
    })
  }

  showPolicyDialog.value = false
  dialogEditingRuleId.value = null
}

const deletePolicy = (policyId: PolicyTypeId, ruleId: string) => {
  const index = policyRules.value[policyId].findIndex((r) => r.id === ruleId)
  if (index > -1) {
    policyRules.value[policyId].splice(index, 1)
  }
}

// All pricing rules in a single create-endpoint flow share one wallet
// (mirrors the per-endpoint constraint). Picked from the first rule added.
const lockedWalletId = computed<string | null>(() => {
  const firstRule = policyRules.value.pricing[0]
  if (!firstRule) return null
  return (firstRule.config.walletId as string) || null
})

const handlePricingRuleCreated = (payload: {
  walletId: string
  walletType: string
  walletCurrency: string
  policyType:
    | 'mpp_per_request'
    | 'xendit_per_request'
    | 'mpp_per_document'
    | 'xendit_per_document'
  name: string
  config: Record<string, unknown>
}) => {
  const ruleId = generateRuleId()
  const appliedTo = (payload.config.applied_to as string[]) ?? ['*']
  const userType = appliedTo.length === 1 && appliedTo[0] === '*' ? 'all' : 'specific'
  const users = userType === 'specific' ? appliedTo.join(', ') : ''

  const config: Record<string, unknown> = {
    id: ruleId,
    walletId: payload.walletId,
    walletType: payload.walletType,
    walletCurrency: payload.walletCurrency,
    policyType: payload.policyType,
    userType,
    users,
    note: payload.name,
    price: String(payload.config.price ?? '0'),
  }

  policyRules.value.pricing.push({
    id: ruleId,
    config: config as PolicyConfig,
    isEditing: false,
  })
}

const refreshForm = () => {
  // Form refresh function for error boundary retry
  console.log('Refreshing form...')
}

// Load available models
const loadAvailableModels = async () => {
  loadingModels.value = true
  modelsError.value = null
  try {
    const models = await modelsApi.list()
    availableModels.value = models
  } catch (error) {
    console.error('Failed to load available models:', error)
    modelsError.value = error instanceof Error ? error.message : 'Failed to load models'
  } finally {
    loadingModels.value = false
  }
}

// Get selected existing model details
const getSelectedModelDetails = () => {
  if (!formData.value.aiModel) return null
  return availableModels.value.find((m) => m.id === formData.value.aiModel)
}

// Get selected new model label
const getSelectedNewModelLabel = () => {
  if (!newModelForm.value.model) return null
  const modelOption = newProviderModels.value.find((m) => m.id === newModelForm.value.model)
  return modelOption?.name || modelOption?.id || null
}

// Derive model name from endpoint details (follows same pattern as datasets)
const getDerivedModelName = () => {
  return formData.value.endpointName || 'new-model'
}

// Derive model description from endpoint details (follows same pattern as datasets)
const getDerivedModelDescription = () => {
  if (formData.value.summary) {
    return `Model for ${formData.value.summary}`
  }
  return `Model for ${getProviderLabel(newModelForm.value.provider)} AI integration`
}

onMounted(async () => {
  await loadAvailableModels()

  if (existingModelsCount.value === 0 && !selectedModelSourceType.value) {
    selectedModelSourceType.value = 'create-new'
  }
})

// Cleanup debounce timer when component unmounts
onUnmounted(() => {
  if (nameCheckDebounceTimer.value) {
    clearTimeout(nameCheckDebounceTimer.value)
  }
})

// Select model source type
const selectModelSourceType = (type: string) => {
  selectedModelSourceType.value = type
  // Reset selections when changing type
  if (type !== 'existing') {
    formData.value.aiModel = ''
  }
  if (type !== 'create-new') {
    selectedNewModelType.value = null
    // Reset new model form
    newModelForm.value = {
      provider: '',
      model: '',
      apiKey: '',
      baseUrl: '',
    }
  }
}

// Reset model selection when provider or API key changes
watch(
  () => newModelForm.value.provider,
  () => {
    newModelForm.value.model = ''
    if (newModelForm.value.provider !== 'custom') {
      newModelForm.value.baseUrl = ''
    }
  },
)
watch(
  () => newModelForm.value.apiKey,
  () => {
    newModelForm.value.model = ''
  },
)
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
