<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Header -->
    <div class="bg-white border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-6 py-4">
        <div class="flex items-center justify-between">
          <Button
            variant="ghost"
            @click="handleBack"
            class="flex items-center text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft class="w-5 h-5 mr-2" />
            Back to Endpoints
          </Button>

          <TooltipProvider>
            <Tooltip :delayDuration="0">
              <TooltipTrigger as-child>
                <span>
                  <Button
                    @click="saveDraft"
                    :disabled="!canSaveDraft"
                    variant="outline"
                    class="flex items-center gap-2"
                  >
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

    <div class="max-w-5xl mx-auto px-6 py-12">
      <!-- Progress Steps -->
      <div class="mb-12">
        <div class="flex items-center justify-between mb-8">
          <!-- Step 1 -->
          <div class="flex items-center">
            <div
              :class="[
                'w-10 h-10 rounded-full flex items-center justify-center font-medium transition-colors',
                currentSubStep >= 1 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500',
              ]"
            >
              {{ currentSubStep > 1 ? '✓' : '1' }}
            </div>
            <span
              :class="[
                'ml-3 text-sm font-medium',
                currentSubStep >= 1 ? 'text-gray-900' : 'text-gray-500',
              ]"
            >
              Basic Info
            </span>
          </div>

          <div
            :class="[
              'flex-1 h-1 mx-2 transition-colors',
              currentSubStep > 1 ? 'bg-blue-600' : 'bg-gray-200',
            ]"
          />

          <!-- Step 2 -->
          <div class="flex items-center">
            <div
              :class="[
                'w-10 h-10 rounded-full flex items-center justify-center font-medium transition-colors',
                currentSubStep >= 2 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500',
              ]"
            >
              {{ currentSubStep > 2 ? '✓' : '2' }}
            </div>
            <span
              :class="[
                'ml-3 text-sm font-medium',
                currentSubStep >= 2 ? 'text-gray-900' : 'text-gray-500',
              ]"
            >
              AI Model
            </span>
          </div>

          <div
            :class="[
              'flex-1 h-1 mx-2 transition-colors',
              currentSubStep > 2 ? 'bg-blue-600' : 'bg-gray-200',
            ]"
          />

          <!-- Step 3 -->
          <div class="flex items-center">
            <div
              :class="[
                'w-10 h-10 rounded-full flex items-center justify-center font-medium transition-colors',
                currentSubStep >= 3 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500',
              ]"
            >
              {{ currentSubStep > 3 ? '✓' : '3' }}
            </div>
            <span
              :class="[
                'ml-3 text-sm font-medium',
                currentSubStep >= 3 ? 'text-gray-900' : 'text-gray-500',
              ]"
            >
              Policies
            </span>
          </div>

          <div
            :class="[
              'flex-1 h-1 mx-2 transition-colors',
              currentSubStep > 3 ? 'bg-blue-600' : 'bg-gray-200',
            ]"
          />

          <!-- Step 4: Review -->
          <div class="flex items-center">
            <div
              :class="[
                'w-10 h-10 rounded-full flex items-center justify-center font-medium transition-colors',
                currentSubStep >= 4 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500',
              ]"
            >
              4
            </div>
            <span
              :class="[
                'ml-3 text-sm font-medium',
                currentSubStep >= 4 ? 'text-gray-900' : 'text-gray-500',
              ]"
            >
              Review
            </span>
          </div>
        </div>

        <div class="text-center">
          <h1 class="text-4xl font-bold text-gray-900 mb-4">
            {{ stepTitles[currentSubStep - 1] }}
          </h1>
          <p class="text-lg text-gray-600">
            {{ stepDescriptions[currentSubStep - 1] }}
          </p>
        </div>
      </div>

      <div>
        <!-- Step 1: Basic Information -->
        <div
          v-if="currentSubStep === 1"
          class="bg-white rounded-lg shadow-sm border border-gray-200 p-8"
        >
          <div class="space-y-6">
            <!-- Endpoint Name -->
            <div class="space-y-2">
              <Label for="endpoint-name" class="text-sm font-medium text-gray-700">
                Endpoint Name <span class="text-red-500">*</span>
              </Label>
              <Input
                id="endpoint-name"
                v-model="formData.endpointName"
                placeholder="e.g., Code Generation Assistant"
                class="w-full"
              />
              <p class="text-sm text-gray-500">Choose a descriptive name for your model endpoint</p>
            </div>

            <!-- Summary -->
            <div class="space-y-2">
              <Label for="summary" class="text-sm font-medium text-gray-700"> Summary </Label>
              <Input
                id="summary"
                v-model="formData.summary"
                placeholder="Brief description of what your model endpoint does"
                class="w-full"
              />
              <p class="text-sm text-gray-500">
                A short summary that will appear in endpoint listings
              </p>
            </div>

            <!-- Description -->
            <div class="space-y-2">
              <Label for="description" class="text-sm font-medium text-gray-700">
                Description
              </Label>
              <MdEditor
                v-model="formData.description"
                :height="200"
                :toolbars-exclude="['github']"
                :preview-theme="'github'"
                :code-theme="'github'"
                language="en-US"
                placeholder="Detailed description of your model endpoint (supports Markdown)"
              />
              <p class="text-sm text-gray-500">
                Provide a detailed description using the WYSIWYG markdown editor above.
              </p>
            </div>

            <!-- Tags -->
            <div class="space-y-2">
              <Label for="tags" class="text-sm font-medium text-gray-700"> Tags </Label>
              <div class="space-y-2">
                <div class="flex gap-2">
                  <Input
                    id="tags"
                    v-model="tagInput"
                    @keydown.enter.prevent="addTag"
                    placeholder="Add tags to help users find your endpoint"
                    class="flex-1"
                  />
                  <Button @click="addTag" variant="outline" size="sm">
                    <Plus class="h-4 w-4" />
                  </Button>
                </div>
                <div v-if="formData.tags.length > 0" class="flex flex-wrap gap-2 mt-2">
                  <Badge
                    v-for="(tag, index) in formData.tags"
                    :key="index"
                    variant="secondary"
                    class="px-3 py-1"
                  >
                    {{ tag }}
                    <button @click="removeTag(index)" class="ml-2 hover:text-gray-700">
                      <X class="h-3 w-3" />
                    </button>
                  </Badge>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 2: AI Model Selection -->
        <div v-if="currentSubStep === 2" class="space-y-8">
          <!-- Model Source Selection Cards -->
          <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <!-- Add New Model Card -->
            <Card
              class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-blue-300 hover:bg-gradient-to-br hover:from-blue-50 hover:to-indigo-50 border-2 bg-white"
              :class="
                selectedModelSourceType === 'create-new'
                  ? 'border-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50'
                  : 'border-gray-200'
              "
              @click="selectModelSourceType('create-new')"
            >
              <CardContent class="p-6">
                <div class="flex flex-col items-center text-center">
                  <div
                    class="w-14 h-14 rounded-full bg-blue-100 flex items-center justify-center mb-4"
                  >
                    <Plus class="w-7 h-7 text-blue-600" />
                  </div>

                  <h3 class="text-lg font-bold text-gray-900 mb-2">Add New Model</h3>

                  <p class="text-sm text-gray-600 mb-3">Set up and configure a new AI model</p>

                  <p class="text-xs text-gray-500">vLLM, Ollama, Hugging Face, and more</p>
                </div>
              </CardContent>
            </Card>

            <!-- Select Existing Model Card -->
            <Card
              class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-green-300 hover:bg-gradient-to-br hover:from-green-50 hover:to-emerald-50 border-2 bg-white"
              :class="
                selectedModelSourceType === 'existing'
                  ? 'border-green-500 bg-gradient-to-br from-green-50 to-emerald-50'
                  : 'border-gray-200'
              "
              @click="selectModelSourceType('existing')"
            >
              <CardContent class="p-6">
                <div class="flex flex-col items-center text-center">
                  <div
                    class="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center mb-4"
                  >
                    <FolderOpen class="w-7 h-7 text-green-600" />
                  </div>

                  <h3 class="text-lg font-bold text-gray-900 mb-2">Use Existing Model</h3>

                  <p class="text-sm text-gray-600 mb-3">Select from your configured AI models</p>

                  <p class="text-xs text-gray-500">
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
            <div
              v-if="selectedModelSourceType === 'create-new'"
              class="bg-white rounded-lg shadow-sm border border-gray-200 p-8"
            >
              <div class="space-y-6">
                <div>
                  <h3 class="text-lg font-medium text-gray-900 mb-2">Add New AI Model</h3>
                  <p class="text-sm text-gray-600">Configure a new AI model for your endpoint</p>
                </div>

                <!-- Search Input -->
                <div class="relative">
                  <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <Input
                    v-model="searchQuery"
                    placeholder="Search AI models..."
                    class="pl-10 pr-4"
                  />
                </div>

                <!-- Model Options Grid -->
                <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  <div
                    v-for="model in filteredModels"
                    :key="model.id"
                    @click="
                      model.isCustom ? openCustomSDKDocs() : (selectedNewModelType = model.id)
                    "
                    :class="[
                      'flex flex-col items-center justify-center p-6 rounded-lg border cursor-pointer transition-all group h-40',
                      model.isCustom
                        ? 'border-purple-200 bg-gradient-to-r from-purple-50 to-blue-50 hover:border-purple-300 hover:bg-gradient-to-r hover:from-purple-100 hover:to-blue-100'
                        : selectedNewModelType === model.id
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:bg-gray-50',
                    ]"
                  >
                    <div v-if="model.isCustom" class="transition-all duration-200 mb-2">
                      <div class="p-2 bg-purple-100 rounded-md group-hover:hidden">
                        <Code class="h-6 w-6 text-purple-600" />
                      </div>
                      <div class="hidden group-hover:block p-2 bg-purple-100 rounded-md">
                        <ExternalLink class="h-6 w-6 text-purple-600" />
                      </div>
                    </div>
                    <IntegrationIcon
                      v-else
                      :name="model.id"
                      class="h-12 w-12 mb-3"
                      :class="selectedNewModelType === model.id ? 'text-blue-600' : 'text-gray-600'"
                    />
                    <div
                      v-if="model.isCustom"
                      class="text-center transition-all duration-200 min-h-[1.25rem]"
                    >
                      <span class="font-medium text-purple-800 group-hover:hidden">
                        {{ model.name }}
                      </span>
                      <span class="hidden group-hover:block font-medium text-purple-800">
                        View documentation
                      </span>
                    </div>
                    <span
                      v-else
                      class="font-medium text-center"
                      :class="selectedNewModelType === model.id ? 'text-blue-900' : 'text-gray-900'"
                    >
                      {{ model.name }}
                    </span>
                    <div
                      v-if="model.isCustom"
                      class="text-center transition-all duration-200 min-h-[1rem]"
                    >
                      <span class="text-xs text-purple-600 group-hover:hidden">Using SDK</span>
                      <span class="hidden group-hover:block text-xs text-purple-600"
                        >Opens in a new tab</span
                      >
                    </div>
                  </div>
                </div>

                <!-- Configuration Form -->
                <div v-if="selectedNewModelType" class="mt-6 p-4 bg-gray-50 rounded-lg">
                  <h4 class="font-medium text-gray-900 mb-2">
                    Configure {{ selectedNewModelName }}
                  </h4>
                  <p class="text-sm text-gray-600 mb-4">
                    Set up your {{ selectedNewModelName }} model integration settings
                  </p>
                  <div
                    class="min-h-[100px] flex items-center justify-center border-2 border-dashed rounded-lg bg-white"
                  >
                    <p class="text-gray-500">
                      Configuration form for {{ selectedNewModelName }} will be implemented here
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <!-- Existing Models List -->
            <div
              v-if="selectedModelSourceType === 'existing'"
              class="bg-white rounded-lg shadow-sm border border-gray-200 p-6"
            >
              <div class="space-y-4">
                <h3 class="text-lg font-medium text-gray-900 mb-4">Available AI Models</h3>

                <RadioGroup v-model="formData.aiModel">
                  <div class="space-y-3">
                    <div
                      v-for="model in mockModels"
                      :key="model.id"
                      class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50"
                      :class="
                        formData.aiModel === model.id
                          ? 'border-green-500 bg-green-50'
                          : 'border-gray-200'
                      "
                      @click="formData.aiModel = model.id"
                    >
                      <RadioGroupItem :value="model.id" :id="model.id" />
                      <Label :for="model.id" class="flex items-center gap-3 cursor-pointer flex-1">
                        <div
                          class="p-2 rounded"
                          :class="{
                            'bg-purple-100': model.type === 'vllm',
                            'bg-orange-100': model.type === 'ollama',
                            'bg-blue-100': model.type === 'huggingface',
                          }"
                        >
                          <IntegrationIcon :name="model.type" class="h-5 w-5" />
                        </div>
                        <div class="flex-1">
                          <div class="flex items-center gap-2">
                            <span class="font-medium">{{ model.name }}</span>
                            <Badge variant="secondary" class="text-xs capitalize">{{
                              model.type
                            }}</Badge>
                            <Badge
                              variant="outline"
                              :class="
                                model.status === 'running'
                                  ? 'bg-green-50 text-green-700 border-green-200 text-xs'
                                  : 'bg-gray-50 text-gray-600 border-gray-200 text-xs'
                              "
                            >
                              {{ model.status }}
                            </Badge>
                          </div>
                          <p class="text-sm text-gray-600 mt-1">{{ model.description }}</p>
                        </div>
                      </Label>
                    </div>
                  </div>
                </RadioGroup>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 3: Apply Policies -->
        <div v-if="currentSubStep === 3" class="space-y-8">
          <!-- Policy Sections -->
          <div class="space-y-6">
            <div
              v-for="policy in policyTypes"
              :key="policy.id"
              class="bg-white border border-gray-200 rounded-lg p-6"
            >
              <!-- Policy Header -->
              <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-4">
                  <div
                    :class="{
                      'p-3 rounded-lg bg-blue-100': policy.color === 'blue',
                      'p-3 rounded-lg bg-green-100': policy.color === 'green',
                      'p-3 rounded-lg bg-yellow-100': policy.color === 'yellow',
                      'p-3 rounded-lg bg-purple-100': policy.color === 'purple',
                      'p-3 rounded-lg bg-red-100': policy.color === 'red',
                    }"
                  >
                    <component
                      :is="policy.icon"
                      :class="{
                        'h-6 w-6 text-blue-600': policy.color === 'blue',
                        'h-6 w-6 text-green-600': policy.color === 'green',
                        'h-6 w-6 text-yellow-600': policy.color === 'yellow',
                        'h-6 w-6 text-purple-600': policy.color === 'purple',
                        'h-6 w-6 text-red-600': policy.color === 'red',
                      }"
                    />
                  </div>
                  <div class="flex-1">
                    <h3 class="text-lg font-medium text-gray-900">{{ policy.label }}</h3>
                    <p class="text-sm text-gray-600 mt-1">{{ policy.description }}</p>
                  </div>
                </div>
                <Button @click="addPolicy(policy.id)" variant="outline" class="ml-4">
                  <Plus class="h-4 w-4 mr-2" />
                  Add {{ policy.name }} rule
                </Button>
              </div>

              <!-- Empty State -->
              <div
                v-if="policyRules[policy.id]?.length === 0"
                class="text-center py-8 border-2 border-dashed border-gray-200 rounded-lg"
              >
                <p class="text-gray-500">No {{ policy.name.toLowerCase() }} rule added yet</p>
              </div>

              <!-- Policy Rules -->
              <div v-if="(policyRules[policy.id]?.length || 0) > 0" class="space-y-4">
                <div
                  v-for="rule in policyRules[policy.id] || []"
                  :key="rule.id"
                  class="border border-gray-200 rounded-lg p-4"
                >
                  <!-- Rule in Edit Mode (Expanded) -->
                  <div v-if="rule.isEditing" class="space-y-4">
                    <!-- Policy-specific forms -->
                    <div v-if="policy.id === 'authorization'" class="space-y-6">
                      <!-- Authorization form content -->
                      <div class="flex items-center justify-between">
                        <div>
                          <h3 class="text-lg font-medium text-gray-900">
                            Authorization rule #{{
                              (policyRules[policy.id]?.findIndex((r) => r.id === rule.id) ?? -1) + 1
                            }}
                          </h3>
                          <p class="text-sm text-gray-600 mt-1">
                            {{
                              authorizationForm.ruleType === 'allow'
                                ? 'Only these users can access'
                                : 'These users cannot access'
                            }}
                          </p>
                        </div>
                        <Button variant="ghost" size="sm" @click="cancelEdit(policy.id, rule.id)">
                          Remove
                        </Button>
                      </div>

                      <div class="space-y-2">
                        <Label>Rule Type</Label>
                        <RadioGroup v-model="authorizationForm.ruleType" class="flex gap-6">
                          <div class="flex items-center space-x-2">
                            <RadioGroupItem value="allow" id="allow" />
                            <Label for="allow">Allow-list</Label>
                          </div>
                          <div class="flex items-center space-x-2">
                            <RadioGroupItem value="deny" id="deny" />
                            <Label for="deny">Deny-list</Label>
                          </div>
                        </RadioGroup>
                      </div>

                      <div class="space-y-2">
                        <Label for="auth-users">
                          {{
                            authorizationForm.ruleType === 'allow'
                              ? 'Who can access?'
                              : 'Who cannot access?'
                          }}
                        </Label>
                        <p class="text-sm text-gray-600">
                          Comma-separated list. Examples: jane@acme.com, *@acme.com
                        </p>
                        <Input
                          id="auth-users"
                          v-model="authorizationForm.users"
                          placeholder="*@acme.com, jane@acme.com"
                          class="w-full"
                        />
                      </div>

                      <div class="space-y-2">
                        <Label for="auth-note">Rule name (optional)</Label>
                        <Textarea
                          id="auth-note"
                          v-model="authorizationForm.note"
                          placeholder="e.g., Core team"
                          rows="2"
                        />
                      </div>
                    </div>

                    <!-- Add other policy forms in similar fashion -->
                    <div v-if="policy.id === 'ratelimiter'" class="space-y-6">
                      <div class="flex items-center justify-between">
                        <div>
                          <h3 class="text-lg font-medium text-gray-900">
                            Rate limiter rule #{{
                              (policyRules[policy.id]?.findIndex((r) => r.id === rule.id) ?? -1) + 1
                            }}
                          </h3>
                          <p class="text-sm text-gray-600 mt-1">
                            Control request rates to prevent abuse and ensure fair resource usage
                          </p>
                        </div>
                        <Button variant="ghost" size="sm" @click="cancelEdit(policy.id, rule.id)">
                          Remove
                        </Button>
                      </div>

                      <div class="w-full space-y-6">
                        <div class="w-full grid grid-cols-1 md:grid-cols-5 gap-6">
                          <div class="col-span-3 space-y-2">
                            <Label for="rate-limit">Rate Limit</Label>
                            <div class="w-full flex items-center gap-3">
                              <Input
                                id="rate-limit"
                                v-model="rateLimiterForm.limit"
                                placeholder="100"
                                type="number"
                                class="flex-1 min-w-0"
                              />
                              <span class="text-sm text-gray-600 whitespace-nowrap"
                                >requests per</span
                              >
                              <Input
                                id="rate-window"
                                v-model="rateLimiterForm.windowValue"
                                placeholder="1"
                                type="number"
                                min="1"
                                class="w-16 min-w-0"
                              />
                              <Select v-model="rateLimiterForm.windowUnit" class="w-28 min-w-0">
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="second">second(s)</SelectItem>
                                  <SelectItem value="minute">minute(s)</SelectItem>
                                  <SelectItem value="hour">hour(s)</SelectItem>
                                  <SelectItem value="day">day(s)</SelectItem>
                                  <SelectItem value="week">week(s)</SelectItem>
                                  <SelectItem value="month">month(s)</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                          </div>
                          <div class="col-span-2 space-y-2">
                            <Label for="rate-scope">Scope</Label>
                            <Select v-model="rateLimiterForm.scope" class="w-full">
                              <SelectTrigger class="w-full">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="per user">Per User</SelectItem>
                                <SelectItem value="for this endpoint">For This Endpoint</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>

                        <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                          <div class="space-y-2">
                            <Label for="rate-user-type">Apply this rule to</Label>
                            <Select v-model="rateLimiterForm.userType">
                              <SelectTrigger>
                                <SelectValue placeholder="Select users" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="all">All users</SelectItem>
                                <SelectItem value="only">Only specific users</SelectItem>
                                <SelectItem value="except">All except specific users</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>

                          <div
                            v-if="rateLimiterForm.userType && rateLimiterForm.userType !== 'all'"
                            class="col-span-2 space-y-2"
                          >
                            <Label for="rate-users">
                              {{
                                rateLimiterForm.userType === 'only'
                                  ? 'Which users'
                                  : 'Exclude which users'
                              }}
                            </Label>
                            <Input
                              id="rate-users"
                              v-model="rateLimiterForm.users"
                              :placeholder="
                                rateLimiterForm.userType === 'only'
                                  ? 'john@company.com, *@contractors.com'
                                  : 'admin@company.com, *@management.com'
                              "
                              class="w-full"
                            />
                            <p class="text-xs text-gray-500">
                              Comma-separated list. Wildcard supported (e.g., *@company.com, *.edu,
                              *@contractors.org)
                            </p>
                          </div>
                        </div>
                      </div>
                      <div class="space-y-2">
                        <Label for="rate-note">Rule name (optional)</Label>
                        <Textarea
                          id="rate-note"
                          v-model="rateLimiterForm.note"
                          placeholder="e.g., Burst traffic protection"
                          rows="2"
                        />
                      </div>
                    </div>

                    <!-- Pricing Form -->
                    <div v-if="policy.id === 'pricing'" class="space-y-6">
                      <!-- Rule Header -->
                      <div class="flex items-center justify-between">
                        <div>
                          <h3 class="text-lg font-medium text-gray-900">
                            Pricing rule #{{
                              (policyRules[policy.id]?.findIndex((r) => r.id === rule.id) ?? -1) + 1
                            }}
                          </h3>
                          <p class="text-sm text-gray-600 mt-1">
                            Set pricing based on requests or tokens consumed
                          </p>
                        </div>
                        <Button variant="ghost" size="sm" @click="cancelEdit(policy.id, rule.id)">
                          Remove
                        </Button>
                      </div>

                      <!-- Pricing Type Selection -->
                      <div class="space-y-2">
                        <Label>Pricing Type</Label>
                        <RadioGroup v-model="pricingForm.pricingType" class="flex gap-6">
                          <div class="flex items-center space-x-2">
                            <RadioGroupItem value="request" id="request-pricing" />
                            <Label for="request-pricing">Request-based</Label>
                          </div>
                          <div class="flex items-center space-x-2">
                            <RadioGroupItem value="token" id="token-pricing" />
                            <Label for="token-pricing">Token-based</Label>
                          </div>
                        </RadioGroup>
                      </div>

                      <div class="w-full space-y-6">
                        <div class="w-full grid grid-cols-1 md:grid-cols-3 gap-6">
                          <div class="col-span-3 space-y-2">
                            <Label for="pricing-rate">Pricing</Label>
                            <div class="w-full max-w-md flex items-center gap-3">
                              <span class="text-sm text-gray-600 whitespace-nowrap">$</span>
                              <Input
                                id="pricing-rate"
                                v-model="pricingForm.price"
                                placeholder="0.01"
                                type="number"
                                step="0.001"
                                min="0"
                                class="flex-1 min-w-0"
                              />
                              <span class="text-sm text-gray-600 whitespace-nowrap">per</span>
                              <Input
                                id="pricing-quantity"
                                v-model="pricingForm.quantity"
                                :placeholder="pricingForm.pricingType === 'token' ? '1000' : '1'"
                                type="number"
                                min="1"
                                class="w-20 min-w-0"
                              />
                              <span class="text-sm text-gray-600 whitespace-nowrap">{{
                                pricingForm.pricingType === 'request' ? 'request(s)' : 'token(s)'
                              }}</span>
                            </div>
                          </div>
                        </div>

                        <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
                          <div class="space-y-2">
                            <Label for="pricing-user-type">Apply this rule to</Label>
                            <Select v-model="pricingForm.userType">
                              <SelectTrigger>
                                <SelectValue placeholder="Select users" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="all">All users</SelectItem>
                                <SelectItem value="only">Only specific users</SelectItem>
                                <SelectItem value="except">All except specific users</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>

                          <div
                            v-if="pricingForm.userType && pricingForm.userType !== 'all'"
                            class="col-span-2 space-y-2"
                          >
                            <Label for="pricing-users">
                              {{
                                pricingForm.userType === 'only'
                                  ? 'Which users'
                                  : 'Exclude which users'
                              }}
                            </Label>
                            <Input
                              id="pricing-users"
                              v-model="pricingForm.users"
                              :placeholder="
                                pricingForm.userType === 'only'
                                  ? 'john@company.com, *@contractors.com'
                                  : 'admin@company.com, *@management.com'
                              "
                              class="w-full"
                            />
                            <p class="text-xs text-gray-500">
                              Comma-separated list. Wildcard supported (e.g., *@company.com, *.edu,
                              *@contractors.org)
                            </p>
                          </div>
                        </div>
                      </div>
                      <div class="space-y-2">
                        <Label for="pricing-note">Rule name (optional)</Label>
                        <Textarea
                          id="pricing-note"
                          v-model="pricingForm.note"
                          placeholder="e.g., Intro pricing"
                          rows="2"
                        />
                      </div>
                    </div>

                    <!-- Manual Approval Form -->
                    <div v-if="policy.id === 'manual-approval'" class="space-y-6">
                      <!-- Rule Header -->
                      <div class="flex items-center justify-between">
                        <div>
                          <h3 class="text-lg font-medium text-gray-900">
                            Manual approval rule #{{
                              (policyRules[policy.id]?.findIndex((r) => r.id === rule.id) ?? -1) + 1
                            }}
                          </h3>
                          <p class="text-sm text-gray-600 mt-1">
                            Require human approval for sensitive operations and decisions
                          </p>
                        </div>
                        <Button variant="ghost" size="sm" @click="cancelEdit(policy.id, rule.id)">
                          Remove
                        </Button>
                      </div>
                      <!-- Alert Destination Selection -->
                      <div class="space-y-2">
                        <Label>Alert Destination</Label>
                        <RadioGroup v-model="manualApprovalForm.destination" class="flex gap-6">
                          <div class="flex items-center space-x-2">
                            <RadioGroupItem value="inbox" id="inbox-dest" />
                            <Label for="inbox-dest">In-app Notification</Label>
                          </div>
                          <div class="flex items-center space-x-2">
                            <RadioGroupItem value="email" id="email-dest" />
                            <Label for="email-dest">Email</Label>
                          </div>
                          <div class="flex items-center space-x-2">
                            <RadioGroupItem value="slack" id="slack-dest" />
                            <Label for="slack-dest">Slack</Label>
                          </div>
                          <div class="flex items-center space-x-2">
                            <RadioGroupItem value="whatsapp" id="whatsapp-dest" />
                            <Label for="whatsapp-dest">WhatsApp</Label>
                          </div>
                        </RadioGroup>
                      </div>

                      <!-- Destination-specific fields -->
                      <div v-if="manualApprovalForm.destination === 'email'" class="space-y-2">
                        <Label for="email-addresses">Email Addresses</Label>
                        <Input
                          id="email-addresses"
                          v-model="manualApprovalForm.emailAddresses"
                          placeholder="admin@company.com, manager@company.com"
                        />
                        <p class="text-xs text-gray-500">Comma-separated list of email addresses</p>
                      </div>
                      <div v-else-if="manualApprovalForm.destination === 'slack'" class="space-y-2">
                        <Label for="slack-webhook">Slack Webhook URL</Label>
                        <Input
                          id="slack-webhook"
                          v-model="manualApprovalForm.slackWebhookUrl"
                          placeholder="https://hooks.slack.com/services/..."
                        />
                        <p class="text-xs text-gray-500">
                          Your Slack webhook URL for notifications
                        </p>
                      </div>
                      <div
                        v-else-if="manualApprovalForm.destination === 'whatsapp'"
                        class="space-y-2"
                      >
                        <Label for="whatsapp-number">WhatsApp Number</Label>
                        <Input
                          id="whatsapp-number"
                          v-model="manualApprovalForm.whatsappNumber"
                          placeholder="+1234567890"
                        />
                        <p class="text-xs text-gray-500">WhatsApp number with country code</p>
                      </div>

                      <!-- Approval Timeout -->
                      <div class="space-y-2">
                        <Label for="approval-timeout">Approval Timeout</Label>
                        <div class="flex items-center gap-3">
                          <Input
                            id="approval-timeout"
                            v-model="manualApprovalForm.timeoutValue"
                            placeholder="24"
                            type="number"
                            min="1"
                            class="w-20 min-w-0"
                          />
                          <Select v-model="manualApprovalForm.timeoutUnit" class="w-28 min-w-0">
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="minute">minute(s)</SelectItem>
                              <SelectItem value="hour">hour(s)</SelectItem>
                              <SelectItem value="day">day(s)</SelectItem>
                              <SelectItem value="week">week(s)</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      <!-- User Selection -->
                      <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
                        <div class="space-y-2">
                          <Label for="approval-user-type">Apply this rule to</Label>
                          <Select v-model="manualApprovalForm.userType">
                            <SelectTrigger>
                              <SelectValue placeholder="Select users" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">All users</SelectItem>
                              <SelectItem value="only">Only specific users</SelectItem>
                              <SelectItem value="except">All except specific users</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>

                        <div
                          v-if="
                            manualApprovalForm.userType && manualApprovalForm.userType !== 'all'
                          "
                          class="col-span-2 space-y-2"
                        >
                          <Label for="approval-users">
                            {{
                              manualApprovalForm.userType === 'only'
                                ? 'Which users'
                                : 'Exclude which users'
                            }}
                          </Label>
                          <Input
                            id="approval-users"
                            v-model="manualApprovalForm.users"
                            :placeholder="
                              manualApprovalForm.userType === 'only'
                                ? 'john@company.com, *@contractors.com'
                                : 'admin@company.com, *@management.com'
                            "
                            class="w-full"
                          />
                          <p class="text-xs text-gray-500">
                            Comma-separated list. Wildcard supported (e.g., *@company.com, *.edu,
                            *@contractors.org)
                          </p>
                        </div>
                      </div>

                      <div class="space-y-2">
                        <Label for="approval-note">Rule name (optional)</Label>
                        <Textarea
                          id="approval-note"
                          v-model="manualApprovalForm.note"
                          placeholder="e.g., Slack approval notifications"
                          rows="2"
                        />
                      </div>
                    </div>

                    <!-- AI Filters Form -->
                    <div v-if="policy.id === 'ai-filters'" class="space-y-6">
                      <!-- Rule Header -->
                      <div class="flex items-center justify-between">
                        <div>
                          <h3 class="text-lg font-medium text-gray-900">
                            AI filters rule #{{
                              (policyRules[policy.id]?.findIndex((r) => r.id === rule.id) ?? -1) + 1
                            }}
                          </h3>
                          <p class="text-sm text-gray-600 mt-1">
                            Filter or redact responses using an AI before sending them back
                          </p>
                        </div>
                        <Button variant="ghost" size="sm" @click="cancelEdit(policy.id, rule.id)">
                          Remove
                        </Button>
                      </div>

                      <!-- AI Model Selection -->
                      <ModelSelector
                        v-model="aiFiltersForm.modelId"
                        title="AI Model"
                        description="Select an AI model to filter or transform responses"
                        id-prefix="filter"
                        @create-model="handleAIFilterCreateModel"
                      />

                      <!-- Prompt Field -->
                      <div class="space-y-2">
                        <Label for="filter-prompt">Prompt</Label>
                        <Textarea
                          id="filter-prompt"
                          v-model="aiFiltersForm.prompt"
                          placeholder="Enter the prompt to apply to the endpoint's response..."
                          rows="8"
                          class="w-full min-h-[8rem]"
                        />
                        <p class="text-xs text-gray-500">
                          This prompt will be applied to filter or transform the response before
                          sending it back to the user
                        </p>
                      </div>

                      <!-- User Selection -->
                      <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
                        <div class="space-y-2">
                          <Label for="filter-user-type">Apply this rule to</Label>
                          <Select v-model="aiFiltersForm.userType">
                            <SelectTrigger>
                              <SelectValue placeholder="Select users" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">All users</SelectItem>
                              <SelectItem value="only">Only specific users</SelectItem>
                              <SelectItem value="except">All except specific users</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>

                        <div
                          v-if="aiFiltersForm.userType && aiFiltersForm.userType !== 'all'"
                          class="col-span-2 space-y-2"
                        >
                          <Label for="filter-users">
                            {{
                              aiFiltersForm.userType === 'only'
                                ? 'Which users'
                                : 'Exclude which users'
                            }}
                          </Label>
                          <Input
                            id="filter-users"
                            v-model="aiFiltersForm.users"
                            :placeholder="
                              aiFiltersForm.userType === 'only'
                                ? 'john@company.com, *@contractors.com'
                                : 'admin@company.com, *@management.com'
                            "
                            class="w-full"
                          />
                          <p class="text-xs text-gray-500">
                            Comma-separated list. Wildcard supported (e.g., *@company.com, *.edu,
                            *@contractors.org)
                          </p>
                        </div>
                      </div>

                      <div class="space-y-2">
                        <Label for="filter-note">Rule name (optional)</Label>
                        <Textarea
                          id="filter-note"
                          v-model="aiFiltersForm.note"
                          placeholder="e.g., PII protection filter, Content moderation, etc."
                          rows="2"
                        />
                      </div>
                    </div>

                    <!-- Form Footer -->
                    <div class="pt-4 border-t border-gray-200">
                      <div class="flex justify-end gap-2">
                        <Button variant="outline" @click="cancelEdit(policy.id, rule.id)">
                          Cancel
                        </Button>
                        <Button @click="savePolicy(policy.id, rule.id)"> Save Policy </Button>
                      </div>
                    </div>
                  </div>

                  <!-- Rule in Collapsed Mode -->
                  <div v-else class="flex items-start justify-between">
                    <div class="flex-1 space-y-2">
                      <h4 class="text-sm font-medium text-gray-900">
                        {{
                          rule.config.note ||
                          `${policy.name} rule #${(policyRules[policy.id]?.findIndex((r) => r.id === rule.id) ?? -1) + 1}`
                        }}
                      </h4>
                      <div class="text-sm text-gray-600">
                        <!-- Authorization Rule Summary -->
                        <p v-if="rule.config.ruleType">
                          {{ rule.config.ruleType === 'allow' ? 'Allow' : 'Deny' }} access to
                          {{ rule.config.users || 'specified users' }}
                        </p>

                        <!-- Rate Limiter Rule Summary -->
                        <div v-if="rule.config.limit">
                          <p>
                            {{ rule.config.limit }} requests per {{ rule.config.windowValue }}
                            {{ rule.config.windowUnit }}(s) {{ rule.config.scope }}
                          </p>
                          <p
                            v-if="rule.config.userType === 'only' && rule.config.users"
                            class="text-xs text-gray-500"
                          >
                            Only for: {{ rule.config.users }}
                          </p>
                          <p
                            v-if="rule.config.userType === 'except' && rule.config.users"
                            class="text-xs text-gray-500"
                          >
                            Except for: {{ rule.config.users }}
                          </p>
                        </div>

                        <!-- Pricing Rule Summary -->
                        <div
                          v-if="
                            rule.config.price !== undefined &&
                            rule.config.price !== null &&
                            rule.config.price !== ''
                          "
                        >
                          <p>
                            ${{ rule.config.price }} per {{ rule.config.quantity }}
                            {{ rule.config.pricingType }}(s)
                          </p>
                          <p
                            v-if="rule.config.userType === 'only' && rule.config.users"
                            class="text-xs text-gray-500"
                          >
                            Only for: {{ rule.config.users }}
                          </p>
                          <p
                            v-if="rule.config.userType === 'except' && rule.config.users"
                            class="text-xs text-gray-500"
                          >
                            Except for: {{ rule.config.users }}
                          </p>
                        </div>

                        <!-- Manual Approval Rule Summary -->
                        <div v-if="rule.config.destination">
                          <p>
                            Send alerts via
                            {{
                              rule.config.destination === 'inbox'
                                ? 'in-app notification'
                                : rule.config.destination
                            }}
                          </p>
                          <p
                            v-if="rule.config.destination === 'email' && rule.config.emailAddresses"
                            class="text-xs text-gray-500"
                          >
                            To: {{ rule.config.emailAddresses }}
                          </p>
                          <p
                            v-if="
                              rule.config.destination === 'slack' && rule.config.slackWebhookUrl
                            "
                            class="text-xs text-gray-500"
                          >
                            <span class="font-medium">Webhook:</span>
                            <span class="font-mono bg-gray-100 px-1 py-0.5 rounded break-all">{{
                              rule.config.slackWebhookUrl
                            }}</span>
                          </p>
                          <p
                            v-if="
                              rule.config.destination === 'whatsapp' && rule.config.whatsappNumber
                            "
                            class="text-xs text-gray-500"
                          >
                            Number: {{ rule.config.whatsappNumber }}
                          </p>
                          <p class="text-sm">
                            Timeout: {{ rule.config.timeoutValue }} {{ rule.config.timeoutUnit }}(s)
                          </p>
                          <p
                            v-if="rule.config.userType === 'only' && rule.config.users"
                            class="text-xs text-gray-500"
                          >
                            Only for: {{ rule.config.users }}
                          </p>
                          <p
                            v-if="rule.config.userType === 'except' && rule.config.users"
                            class="text-xs text-gray-500"
                          >
                            Except for: {{ rule.config.users }}
                          </p>
                        </div>

                        <!-- AI Filters Rule Summary -->
                        <div v-if="rule.config.modelId">
                          <p>
                            Filter using
                            {{
                              mockModels.find((m) => m.id === rule.config.modelId)?.name ||
                              rule.config.modelId
                            }}
                          </p>
                          <div v-if="rule.config.prompt" class="mt-2 text-xs text-gray-500">
                            <p class="font-medium mb-1">Prompt:</p>
                            <div
                              class="font-mono bg-gray-50 px-2 py-1 rounded border max-h-20 overflow-y-auto whitespace-pre-wrap"
                            >
                              {{ rule.config.prompt }}
                            </div>
                          </div>
                          <p
                            v-if="rule.config.userType === 'only' && rule.config.users"
                            class="text-xs text-gray-500 mt-2"
                          >
                            Only for: {{ rule.config.users }}
                          </p>
                          <p
                            v-if="rule.config.userType === 'except' && rule.config.users"
                            class="text-xs text-gray-500 mt-2"
                          >
                            Except for: {{ rule.config.users }}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div class="flex gap-2 ml-4">
                      <Button
                        variant="outline"
                        size="sm"
                        class="text-gray-600"
                        @click="editPolicy(policy.id, rule.id)"
                      >
                        <Edit class="h-4 w-4 mr-2" />
                        Edit
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        class="text-red-600 hover:text-red-700"
                        @click="deletePolicy(policy.id, rule.id)"
                      >
                        <Trash2 class="h-4 w-4 mr-2" />
                        Delete
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Custom Policies Info Box -->
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-6">
              <div class="flex items-start gap-4">
                <div class="p-2 bg-blue-100 rounded-full">
                  <Info class="h-5 w-5 text-blue-600" />
                </div>
                <div class="flex-1">
                  <h4 class="text-base font-medium text-gray-900 mb-2">Did you know?</h4>
                  <p class="text-sm text-gray-700 mb-4">
                    You can create your own custom policies for your specific needs using our SDK.
                    Build policies tailored to your unique requirements and integrate them
                    seamlessly.
                  </p>
                  <Button
                    variant="outline"
                    class="text-blue-700 border-blue-300 hover:bg-blue-100"
                    @click="openCustomPoliciesDocs"
                  >
                    <ExternalLink class="h-4 w-4 mr-2" />
                    View Documentation
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 4: Review -->
        <div v-if="currentSubStep === 4" class="space-y-8">
          <!-- Endpoint Summary -->
          <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
            <div class="space-y-6">
              <div>
                <h2 class="text-xl font-semibold text-gray-900 mb-2">Endpoint Summary</h2>
                <p class="text-sm text-gray-600">
                  Review your model endpoint configuration before deployment
                </p>
              </div>

              <!-- Basic Information -->
              <div class="border-l-4 border-blue-500 pl-4">
                <h3 class="font-medium text-gray-900 mb-2">Basic Information</h3>
                <div class="space-y-1 text-sm">
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
                    <div class="border border-gray-200 rounded-lg p-2">
                      <MdPreview
                        :model-value="formData.description"
                        :preview-theme="'github'"
                        :code-theme="'github'"
                        language="en-US"
                      />
                    </div>
                  </div>
                  <div v-if="formData.tags.length > 0">
                    <span class="font-medium">Tags:</span>
                    <span class="ml-2">
                      <Badge
                        v-for="tag in formData.tags"
                        :key="tag"
                        variant="outline"
                        class="mr-1"
                        >{{ tag }}</Badge
                      >
                    </span>
                  </div>
                </div>
              </div>

              <!-- AI Model -->
              <div class="border-l-4 border-purple-500 pl-4">
                <h3 class="font-medium text-gray-900 mb-2">AI Model</h3>
                <div class="text-sm space-y-1">
                  <div v-if="selectedModelSourceType === 'existing'">
                    <div v-if="formData.aiModel === 'nlp-engine'">
                      <p><span class="font-medium">Source:</span> Existing Model</p>
                      <p><span class="font-medium">Model:</span> NLP Processing Engine</p>
                      <p><span class="font-medium">Provider:</span> vLLM</p>
                      <p>
                        <span class="font-medium">Status:</span>
                        <Badge
                          variant="outline"
                          class="bg-gray-50 text-gray-600 border-gray-200 text-xs"
                          >Stopped</Badge
                        >
                      </p>
                    </div>
                    <div v-else-if="formData.aiModel === 'code-assistant'">
                      <p><span class="font-medium">Source:</span> Existing Model</p>
                      <p><span class="font-medium">Model:</span> Code Assistant Model</p>
                      <p><span class="font-medium">Provider:</span> Ollama</p>
                      <p>
                        <span class="font-medium">Status:</span>
                        <Badge
                          variant="outline"
                          class="bg-green-50 text-green-700 border-green-200 text-xs"
                          >Running</Badge
                        >
                      </p>
                    </div>
                    <p v-else>Not selected</p>
                  </div>
                  <div v-else-if="selectedModelSourceType === 'create-new'">
                    <p><span class="font-medium">Source:</span> New Model</p>
                    <p v-if="selectedNewModelType">
                      <span class="font-medium">Type:</span> {{ selectedNewModelName }}
                    </p>
                    <p v-if="selectedNewModelType" class="text-gray-600">
                      Configuration will be completed during deployment
                    </p>
                    <p v-else>Not configured</p>
                  </div>
                  <p v-else>Not configured</p>
                </div>
              </div>

              <!-- Applied Policies -->
              <div class="border-l-4 border-orange-500 pl-4">
                <h3 class="font-medium text-gray-900 mb-2">Applied Policies</h3>
                <div class="text-sm space-y-2">
                  <div v-if="Object.keys(getAppliedPoliciesGrouped()).length > 0" class="space-y-6">
                    <div
                      v-for="(policyGroup, policyType) in getAppliedPoliciesGrouped()"
                      :key="policyType"
                      class="space-y-3"
                    >
                      <!-- Policy Type Header -->
                      <div class="flex items-center gap-3">
                        <div
                          :class="[
                            'p-2 rounded-lg',
                            policyGroup.color === 'blue' ? 'bg-blue-100' : '',
                            policyGroup.color === 'green' ? 'bg-green-100' : '',
                            policyGroup.color === 'yellow' ? 'bg-yellow-100' : '',
                            policyGroup.color === 'purple' ? 'bg-purple-100' : '',
                            policyGroup.color === 'red' ? 'bg-red-100' : '',
                          ]"
                        >
                          <component
                            :is="policyGroup.icon"
                            :class="[
                              'h-4 w-4',
                              policyGroup.color === 'blue' ? 'text-blue-600' : '',
                              policyGroup.color === 'green' ? 'text-green-600' : '',
                              policyGroup.color === 'yellow' ? 'text-yellow-600' : '',
                              policyGroup.color === 'purple' ? 'text-purple-600' : '',
                              policyGroup.color === 'red' ? 'text-red-600' : '',
                            ]"
                          />
                        </div>
                        <h4 class="font-semibold text-gray-900">{{ policyType }}</h4>
                        <span class="text-xs text-gray-500"
                          >({{ policyGroup.rules.length }} rule{{
                            policyGroup.rules.length !== 1 ? 's' : ''
                          }})</span
                        >
                      </div>

                      <!-- Policy Rules -->
                      <div class="space-y-3 ml-6">
                        <div
                          v-for="rule in policyGroup.rules"
                          :key="rule.id"
                          class="bg-gray-50 border border-gray-200 rounded-lg p-4"
                        >
                          <h5 class="font-medium text-gray-900 mb-3">{{ rule.name }}</h5>
                          <div class="space-y-2 text-sm text-gray-700">
                            <!-- Authorization Policy Display -->
                            <div v-if="rule.config.ruleType">
                              <p class="flex items-start">
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Type:</span
                                >
                                <span>{{
                                  rule.config.ruleType === 'allow' ? 'Allow-list' : 'Deny-list'
                                }}</span>
                              </p>
                              <p class="flex items-start">
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Users:</span
                                >
                                <span>{{ rule.config.users || 'Not specified' }}</span>
                              </p>
                            </div>

                            <!-- Rate Limiter Policy Display -->
                            <div v-if="rule.config.limit">
                              <p class="flex items-start">
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Limit:</span
                                >
                                <span
                                  >{{ rule.config.limit }} requests per
                                  {{ rule.config.windowValue }}
                                  {{ rule.config.windowUnit }}(s)</span
                                >
                              </p>
                              <p class="flex items-start">
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Scope:</span
                                >
                                <span>{{ rule.config.scope || 'Per user' }}</span>
                              </p>
                              <p
                                v-if="rule.config.userType === 'only' && rule.config.users"
                                class="flex items-start"
                              >
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Users:</span
                                >
                                <span>Only {{ rule.config.users }}</span>
                              </p>
                              <p
                                v-if="rule.config.userType === 'except' && rule.config.users"
                                class="flex items-start"
                              >
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Users:</span
                                >
                                <span>All except {{ rule.config.users }}</span>
                              </p>
                            </div>

                            <!-- Pricing Policy Display -->
                            <div
                              v-if="
                                rule.config.price !== undefined &&
                                rule.config.price !== null &&
                                rule.config.price !== ''
                              "
                            >
                              <p class="flex items-start">
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Price:</span
                                >
                                <span
                                  >${{ rule.config.price }} per {{ rule.config.quantity }}
                                  {{ rule.config.pricingType }}(s)</span
                                >
                              </p>
                              <p
                                v-if="rule.config.userType === 'only' && rule.config.users"
                                class="flex items-start"
                              >
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Users:</span
                                >
                                <span>Only {{ rule.config.users }}</span>
                              </p>
                              <p
                                v-if="rule.config.userType === 'except' && rule.config.users"
                                class="flex items-start"
                              >
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Users:</span
                                >
                                <span>All except {{ rule.config.users }}</span>
                              </p>
                            </div>

                            <!-- Manual Approval Policy Display -->
                            <div v-if="rule.config.destination">
                              <p class="flex items-start">
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Alert:</span
                                >
                                <span class="capitalize">{{
                                  rule.config.destination === 'inbox'
                                    ? 'In-app notification'
                                    : rule.config.destination
                                }}</span>
                              </p>
                              <p
                                v-if="
                                  rule.config.destination === 'email' && rule.config.emailAddresses
                                "
                                class="flex items-start"
                              >
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Email:</span
                                >
                                <span>{{ rule.config.emailAddresses }}</span>
                              </p>
                              <p
                                v-if="
                                  rule.config.destination === 'slack' && rule.config.slackWebhookUrl
                                "
                                class="flex items-start"
                              >
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Webhook:</span
                                >
                                <span
                                  class="text-xs font-mono bg-gray-100 px-2 py-1 rounded break-all"
                                  >{{ rule.config.slackWebhookUrl }}</span
                                >
                              </p>
                              <p
                                v-if="
                                  rule.config.destination === 'whatsapp' &&
                                  rule.config.whatsappNumber
                                "
                                class="flex items-start"
                              >
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Number:</span
                                >
                                <span>{{ rule.config.whatsappNumber }}</span>
                              </p>
                              <p class="flex items-start">
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Timeout:</span
                                >
                                <span
                                  >{{ rule.config.timeoutValue }}
                                  {{ rule.config.timeoutUnit }}(s)</span
                                >
                              </p>
                              <p
                                v-if="rule.config.userType === 'only' && rule.config.users"
                                class="flex items-start"
                              >
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Users:</span
                                >
                                <span>Only {{ rule.config.users }}</span>
                              </p>
                              <p
                                v-if="rule.config.userType === 'except' && rule.config.users"
                                class="flex items-start"
                              >
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Users:</span
                                >
                                <span>All except {{ rule.config.users }}</span>
                              </p>
                            </div>

                            <!-- AI Filters Policy Display -->
                            <div v-if="rule.config.modelId">
                              <p class="flex items-start">
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Model:</span
                                >
                                <span>{{
                                  mockModels.find((m) => m.id === rule.config.modelId)?.name ||
                                  rule.config.modelId
                                }}</span>
                              </p>
                              <div v-if="rule.config.prompt" class="mt-2">
                                <p class="font-medium text-gray-500 mb-2">Prompt:</p>
                                <div
                                  class="text-xs bg-white border rounded px-3 py-2 font-mono max-h-32 overflow-y-auto whitespace-pre-wrap"
                                >
                                  {{ rule.config.prompt }}
                                </div>
                              </div>
                              <p
                                v-if="rule.config.userType === 'only' && rule.config.users"
                                class="flex items-start mt-2"
                              >
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Users:</span
                                >
                                <span>Only {{ rule.config.users }}</span>
                              </p>
                              <p
                                v-if="rule.config.userType === 'except' && rule.config.users"
                                class="flex items-start mt-2"
                              >
                                <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                  >Users:</span
                                >
                                <span>All except {{ rule.config.users }}</span>
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <p v-else class="text-gray-500">No policies applied</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Endpoint Visibility Card -->
          <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
            <div class="space-y-6">
              <div>
                <h2 class="text-xl font-semibold text-gray-900 mb-2">Endpoint Visibility</h2>
                <p class="text-sm text-gray-600">Configure who can discover your endpoint</p>
              </div>

              <div class="space-y-4">
                <!-- Public Endpoint -->
                <div
                  class="flex items-center space-x-3 p-4 border-2 rounded-lg cursor-pointer transition-all duration-200 hover:bg-gray-50"
                  :class="
                    endpointVisibility === 'public'
                      ? 'border-green-500 bg-green-50'
                      : 'border-gray-200'
                  "
                  @click="endpointVisibility = 'public'"
                >
                  <input
                    type="radio"
                    id="public-endpoint"
                    name="endpoint-visibility"
                    value="public"
                    v-model="endpointVisibility"
                    class="w-4 h-4 text-green-600 border-gray-300 focus:ring-green-500"
                  />
                  <div class="p-2 rounded-full bg-green-100">
                    <Globe class="w-5 h-5 text-green-600" />
                  </div>
                  <div class="flex-1">
                    <label for="public-endpoint" class="cursor-pointer">
                      <h4 class="font-medium text-gray-900">Public Endpoint</h4>
                      <p class="text-sm text-gray-600">Anyone can discover this endpoint.</p>
                    </label>
                  </div>
                </div>

                <!-- Private Endpoint -->
                <div
                  class="flex items-center space-x-3 p-4 border-2 rounded-lg cursor-pointer transition-all duration-200 hover:bg-gray-50"
                  :class="
                    endpointVisibility === 'private'
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200'
                  "
                  @click="endpointVisibility = 'private'"
                >
                  <input
                    type="radio"
                    id="private-endpoint"
                    name="endpoint-visibility"
                    value="private"
                    v-model="endpointVisibility"
                    class="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                  />
                  <div class="p-2 rounded-full bg-blue-100">
                    <Lock class="w-5 h-5 text-blue-600" />
                  </div>
                  <div class="flex-1">
                    <label for="private-endpoint" class="cursor-pointer">
                      <h4 class="font-medium text-gray-900">Private Endpoint</h4>
                      <p class="text-sm text-gray-600">
                        Only selected users can discover this endpoint.
                      </p>
                    </label>
                  </div>
                </div>
              </div>

              <!-- Allowed Users (shown when private is selected) -->
              <div v-if="endpointVisibility === 'private'" class="space-y-4">
                <div>
                  <h3 class="text-lg font-medium text-gray-900 mb-1">Allowed Users (Optional)</h3>
                  <p class="text-sm text-gray-600 mb-4">
                    Add email addresses of users who can discover this endpoint. You can leave this
                    empty and add users later from the endpoint details page.
                  </p>
                </div>

                <div class="flex gap-2">
                  <Input
                    v-model="allowedUserInput"
                    @keydown.enter.prevent="addAllowedUser"
                    placeholder="user@example.com"
                    :class="[
                      'flex-1',
                      hasInputError ? 'border-red-300 focus:border-red-500 focus:ring-red-500' : '',
                    ]"
                    type="text"
                    autocomplete="new-password"
                    autocapitalize="off"
                    autocorrect="off"
                    spellcheck="false"
                    data-1p-ignore
                    data-lpignore="true"
                    data-bwignore
                    data-protonpass-ignore
                    data-dashlane-ignore
                    data-form-type="other"
                    data-password-manager="false"
                    role="textbox"
                  />
                  <Button @click="addAllowedUser" variant="outline" size="default" class="px-4">
                    <Plus class="h-4 w-4" />
                  </Button>
                </div>

                <!-- Error message -->
                <div
                  v-if="allowedUserError"
                  class="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md p-2"
                >
                  {{ allowedUserError }}
                </div>

                <p class="text-xs text-gray-500">
                  Comma-separated list. Wildcard supported (e.g., *@company.com, *.edu,
                  *@contractors.org)
                </p>

                <!-- Display added users -->
                <div v-if="allowedUsers.length > 0" class="flex flex-wrap gap-2">
                  <Badge
                    v-for="(user, index) in allowedUsers"
                    :key="index"
                    variant="secondary"
                    class="px-3 py-1 flex items-center gap-2"
                  >
                    {{ user }}
                    <button
                      @click="removeAllowedUser(index)"
                      class="hover:text-gray-700 transition-colors"
                    >
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

          <Button
            @click="handleNext"
            :disabled="!isCurrentStepValid"
            class="bg-purple-600 hover:bg-purple-700 text-white px-8 ml-auto"
          >
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

  <!-- Create Model Dialog -->
  <CreateModelDialog v-model:open="showCreateModelDialog" @model-created="handleModelCreated" />
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
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
  Edit,
  Trash2,
  Info,
  Globe,
  Lock,
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
import { Textarea } from '@/components/ui/textarea'
import { MdEditor, MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import CreateModelDialog from '@/components/CreateModelDialog.vue'
import ModelSelector from '@/components/ModelSelector.vue'
import { mockModels } from '@/stores/models'
import { APP_LIMITS, UI_CONSTANTS } from '@/lib/constants'

const router = useRouter()

// Sub-step navigation
const currentSubStep = ref(1)

// Step titles and descriptions
const stepTitles = ['Basic Information', 'Select AI Model', 'Apply Policies', 'Review']

const stepDescriptions = [
  'Provide basic details about your model endpoint',
  'Choose the AI model that will power your endpoint',
  "Select policies to govern your endpoint's behavior and access",
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
  'manual-approval': [] as PolicyRule[],
  'ai-filters': [] as PolicyRule[],
})

// Currently editing rule ID for each policy type
const editingRuleId = ref<Record<string, string | null>>({
  authorization: null as string | null,
  ratelimiter: null as string | null,
  pricing: null as string | null,
  'manual-approval': null as string | null,
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
  windowValue: '1',
  windowUnit: 'minute',
  scope: 'per user',
  type: 'sliding window',
  userType: 'all',
  users: '',
  note: '',
})

const pricingForm = ref({
  pricingType: 'request',
  price: '',
  quantity: '1',
  userType: 'all',
  users: '',
  note: '',
})

const manualApprovalForm = ref({
  destination: 'inbox' as string,
  emailAddresses: '',
  slackWebhookUrl: '',
  whatsappNumber: '',
  timeoutValue: UI_CONSTANTS.DEFAULT_MANUAL_APPROVAL_TIMEOUT as string,
  timeoutUnit: 'hour' as string,
  userType: 'all' as string,
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
    id: 'manual-approval',
    name: 'Manual approval',
    label: 'Need approval first?',
    description: 'Require human approval for sensitive operations and decisions',
    icon: UserCheck,
    color: 'purple',
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
  return formData.value.endpointName.trim() !== ''
})

// Can save draft when we have name
const canSaveDraft = computed(() => formData.value.endpointName.trim() !== '')

const isStep2Valid = computed(() => {
  if (selectedModelSourceType.value === 'existing') {
    return formData.value.aiModel !== ''
  } else if (selectedModelSourceType.value === 'create-new') {
    return selectedNewModelType.value !== null
  }
  return false
})

const isStep3Valid = computed(() => {
  // Step 3 (policies) is always valid - policies are optional
  return true
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
  let config = { id: ruleId }

  switch (policyId) {
    case 'authorization':
      config = { ...config, ...authorizationForm.value }
      break
    case 'ratelimiter':
      config = { ...config, ...rateLimiterForm.value }
      break
    case 'pricing':
      config = { ...config, ...pricingForm.value }
      break
    case 'manual-approval':
      config = { ...config, ...manualApprovalForm.value }
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

const cancelEdit = (policyId: string, ruleId: string) => {
  const rule = policyRules.value[policyId]?.find((r) => r.id === ruleId)
  if (rule) {
    // Check if this is a new rule (config is empty or only has id)
    const configKeys = Object.keys(rule.config).filter((key) => key !== 'id')
    const hasActualConfig = configKeys.some((key) => {
      const value = rule.config[key]
      return value && String(value).trim() !== ''
    })

    if (!hasActualConfig) {
      // New rule with no saved data - remove it completely
      deletePolicy(policyId, ruleId)
    } else {
      // Existing rule - just collapse it
      rule.isEditing = false
      editingRuleId.value[policyId] = null
    }
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
        windowValue: '1',
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
        pricingType: 'request',
        price: '',
        quantity: '1',
        userType: 'all',
        users: '',
        note: '',
      }
      break
    case 'manual-approval':
      manualApprovalForm.value = {
        destination: 'inbox',
        emailAddresses: '',
        slackWebhookUrl: '',
        whatsappNumber: '',
        timeoutValue: '24',
        timeoutUnit: 'hour',
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
        windowValue: (config.windowValue as string) || '1',
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
        pricingType: (config.pricingType as string) || 'request',
        price: config.price !== undefined ? String(config.price) : '',
        quantity: (config.quantity as string) || (config.pricingType === 'token' ? '1000' : '1'),
        userType: (config.userType as string) || 'all',
        users: (config.users as string) || '',
        note: (config.note as string) || '',
      }
      break
    case 'manual-approval':
      manualApprovalForm.value = {
        destination: (config.destination as string) || 'inbox',
        emailAddresses: (config.emailAddresses as string) || '',
        slackWebhookUrl: (config.slackWebhookUrl as string) || '',
        whatsappNumber: (config.whatsappNumber as string) || '',
        timeoutValue: config.timeoutValue ? String(config.timeoutValue) : '24',
        timeoutUnit: (config.timeoutUnit as string) || 'hour',
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

// Open custom policies documentation
const openCustomPoliciesDocs = () => {
  window.open('https://docs.openmined.org/custom-policies', '_blank')
}

// Handle AI Filter Create Model
const handleAIFilterCreateModel = () => {
  showCreateModelDialog.value = true
}

// Watch for pricing type changes to update default quantity
watch(
  () => pricingForm.value.pricingType,
  (newType) => {
    if (newType === 'token' && pricingForm.value.quantity === '1') {
      pricingForm.value.quantity = '1000'
    } else if (newType === 'request' && pricingForm.value.quantity === '1000') {
      pricingForm.value.quantity = '1'
    }
  },
)

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
