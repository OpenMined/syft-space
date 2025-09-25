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
            Back to Create Service
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
                <p>Add service name and summary to enable</p>
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
                currentSubStep >= 1 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
              ]"
            >
              {{ currentSubStep > 1 ? '✓' : '1' }}
            </div>
            <span 
              :class="[
                'ml-3 text-sm font-medium',
                currentSubStep >= 1 ? 'text-gray-900' : 'text-gray-500'
              ]"
            >
              Basic Info
            </span>
          </div>

          <div 
            :class="[
              'flex-1 h-1 mx-2 transition-colors',
              currentSubStep > 1 ? 'bg-blue-600' : 'bg-gray-200'
            ]"
          />

          <!-- Step 2 -->
          <div class="flex items-center">
            <div 
              :class="[
                'w-10 h-10 rounded-full flex items-center justify-center font-medium transition-colors',
                currentSubStep >= 2 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
              ]"
            >
              {{ currentSubStep > 2 ? '✓' : '2' }}
            </div>
            <span 
              :class="[
                'ml-3 text-sm font-medium',
                currentSubStep >= 2 ? 'text-gray-900' : 'text-gray-500'
              ]"
            >
              AI Model
            </span>
          </div>

          <div 
            :class="[
              'flex-1 h-1 mx-2 transition-colors',
              currentSubStep > 2 ? 'bg-blue-600' : 'bg-gray-200'
            ]"
          />

          <!-- Step 3 -->
          <div class="flex items-center">
            <div 
              :class="[
                'w-10 h-10 rounded-full flex items-center justify-center font-medium transition-colors',
                currentSubStep >= 3 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
              ]"
            >
              {{ currentSubStep > 3 ? '✓' : '3' }}
            </div>
            <span 
              :class="[
                'ml-3 text-sm font-medium',
                currentSubStep >= 3 ? 'text-gray-900' : 'text-gray-500'
              ]"
            >
              Policies
            </span>
          </div>

          <div 
            :class="[
              'flex-1 h-1 mx-2 transition-colors',
              currentSubStep > 3 ? 'bg-blue-600' : 'bg-gray-200'
            ]"
          />

          <!-- Step 4: Review -->
          <div class="flex items-center">
            <div 
              :class="[
                'w-10 h-10 rounded-full flex items-center justify-center font-medium transition-colors',
                currentSubStep >= 4 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500'
              ]"
            >
              4
            </div>
            <span 
              :class="[
                'ml-3 text-sm font-medium',
                currentSubStep >= 4 ? 'text-gray-900' : 'text-gray-500'
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
        <div v-if="currentSubStep === 1" class="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
          <div class="space-y-6">

            <!-- Service Name -->
            <div class="space-y-2">
              <Label for="service-name" class="text-sm font-medium text-gray-700">
                Service Name <span class="text-red-500">*</span>
              </Label>
              <Input
                id="service-name"
                v-model="formData.serviceName"
                placeholder="e.g., Code Generation Assistant"
                class="w-full"
              />
              <p class="text-sm text-gray-500">Choose a descriptive name for your model service</p>
            </div>

            <!-- Summary -->
            <div class="space-y-2">
              <Label for="summary" class="text-sm font-medium text-gray-700">
                Summary <span class="text-red-500">*</span>
              </Label>
              <Input
                id="summary"
                v-model="formData.summary"
                placeholder="Brief description of what your model service does"
                class="w-full"
              />
              <p class="text-sm text-gray-500">A short summary that will appear in service listings</p>
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
                placeholder="Detailed description of your model service (supports Markdown)"
              />
              <p class="text-sm text-gray-500">Provide a detailed description using the WYSIWYG markdown editor above.</p>
            </div>

            <!-- Tags -->
            <div class="space-y-2">
              <Label for="tags" class="text-sm font-medium text-gray-700">
                Tags
              </Label>
              <div class="space-y-2">
                <div class="flex gap-2">
                  <Input
                    id="tags"
                    v-model="tagInput"
                    @keydown.enter.prevent="addTag"
                    placeholder="Add tags to help users find your service"
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
                    <button
                      @click="removeTag(index)"
                      class="ml-2 hover:text-gray-700"
                    >
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
            <!-- Create New Model Card -->
            <Card 
              class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-blue-300 hover:bg-gradient-to-br hover:from-blue-50 hover:to-indigo-50 border-2 bg-white"
              :class="selectedModelSourceType === 'create-new' ? 'border-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50' : 'border-gray-200'"
              @click="selectModelSourceType('create-new')"
            >
              <CardContent class="p-6">
                <div class="flex flex-col items-center text-center">
                  <div class="w-14 h-14 rounded-full bg-blue-100 flex items-center justify-center mb-4">
                    <Plus class="w-7 h-7 text-blue-600" />
                  </div>
                  
                  <h3 class="text-lg font-bold text-gray-900 mb-2">Create New Model</h3>
                  
                  <p class="text-sm text-gray-600 mb-3">
                    Set up and configure a new AI model
                  </p>
                  
                  <p class="text-xs text-gray-500">
                    vLLM, Ollama, Hugging Face, and more
                  </p>
                </div>
              </CardContent>
            </Card>

            <!-- Select Existing Model Card -->
            <Card 
              class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-green-300 hover:bg-gradient-to-br hover:from-green-50 hover:to-emerald-50 border-2 bg-white"
              :class="selectedModelSourceType === 'existing' ? 'border-green-500 bg-gradient-to-br from-green-50 to-emerald-50' : 'border-gray-200'"
              @click="selectModelSourceType('existing')"
            >
              <CardContent class="p-6">
                <div class="flex flex-col items-center text-center">
                  <div class="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center mb-4">
                    <FolderOpen class="w-7 h-7 text-green-600" />
                  </div>
                  
                  <h3 class="text-lg font-bold text-gray-900 mb-2">Use Existing Model</h3>
                  
                  <p class="text-sm text-gray-600 mb-3">
                    Select from your configured AI models
                  </p>
                  
                  <p class="text-xs text-gray-500">
                    {{ existingModelsCount }} model{{ existingModelsCount !== 1 ? 's' : '' }} available
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>

          <!-- Content based on selection -->
          <div v-if="selectedModelSourceType">
            <!-- Create New Model Inline Form -->
            <div v-if="selectedModelSourceType === 'create-new'" class="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
              <div class="space-y-6">
                <div>
                  <h3 class="text-lg font-medium text-gray-900 mb-2">Create New AI Model</h3>
                  <p class="text-sm text-gray-600">Configure a new AI model for your service</p>
                </div>

                <!-- Custom Model Banner -->
                <div v-if="!isCustomBannerDismissed" class="bg-gradient-to-r from-purple-50 to-blue-50 border border-purple-200 rounded-lg p-4">
                  <div class="flex items-start justify-between">
                    <div class="flex items-start space-x-3">
                      <div class="p-2 bg-purple-100 rounded-md">
                        <Code class="h-5 w-5 text-purple-600" />
                      </div>
                      <div class="flex-1">
                        <h4 class="font-medium text-gray-900 mb-1">Custom Model Integration</h4>
                        <p class="text-sm text-gray-600 mb-3">Build your own model integration using our SDK</p>
                        <Button variant="outline" size="sm" class="text-purple-700 border-purple-300 hover:bg-purple-100 hover:text-purple-800">
                          <ExternalLink class="h-3 w-3 mr-2" />
                          View Documentation
                        </Button>
                      </div>
                    </div>
                    <button
                      @click="isCustomBannerDismissed = true"
                      class="ml-auto h-5 w-5 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                    >
                      <X class="h-4 w-4" />
                      <span class="sr-only">Dismiss</span>
                    </button>
                  </div>
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
                    @click="selectedNewModelType = model.id"
                    :class="[
                      'flex flex-col items-center justify-center p-6 rounded-lg border cursor-pointer transition-all hover:bg-gray-50',
                      selectedNewModelType === model.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                    ]"
                  >
                    <IntegrationIcon
                      :name="model.id"
                      class="h-12 w-12 mb-3"
                      :class="selectedNewModelType === model.id ? 'text-blue-600' : 'text-gray-600'"
                    />
                    <span class="font-medium text-center" :class="selectedNewModelType === model.id ? 'text-blue-900' : 'text-gray-900'">
                      {{ model.name }}
                    </span>
                  </div>
                </div>

                <!-- Configuration Form -->
                <div v-if="selectedNewModelType" class="mt-6 p-4 bg-gray-50 rounded-lg">
                  <h4 class="font-medium text-gray-900 mb-2">Configure {{ selectedNewModelName }}</h4>
                  <p class="text-sm text-gray-600 mb-4">Set up your {{ selectedNewModelName }} model integration settings</p>
                  <div class="min-h-[100px] flex items-center justify-center border-2 border-dashed rounded-lg bg-white">
                    <p class="text-gray-500">Configuration form for {{ selectedNewModelName }} will be implemented here</p>
                  </div>
                </div>
              </div>
            </div>

            <!-- Existing Models List -->
            <div v-if="selectedModelSourceType === 'existing'" class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <div class="space-y-4">
                <h3 class="text-lg font-medium text-gray-900 mb-4">Available AI Models</h3>
                
                <RadioGroup v-model="formData.aiModel">
                  <div class="space-y-3">
                    <!-- NLP Processing Engine -->
                    <div class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50"
                         :class="formData.aiModel === 'nlp-engine' ? 'border-green-500 bg-green-50' : 'border-gray-200'"
                         @click="formData.aiModel = 'nlp-engine'">
                      <RadioGroupItem value="nlp-engine" id="nlp-engine" />
                      <Label for="nlp-engine" class="flex items-center gap-3 cursor-pointer flex-1">
                        <div class="p-2 bg-purple-100 rounded">
                          <IntegrationIcon name="vllm" class="h-5 w-5" />
                        </div>
                        <div class="flex-1">
                          <div class="flex items-center gap-2">
                            <span class="font-medium">NLP Processing Engine</span>
                            <Badge variant="secondary" class="text-xs">vLLM</Badge>
                            <Badge variant="outline" class="bg-gray-50 text-gray-600 border-gray-200 text-xs">
                              stopped
                            </Badge>
                          </div>
                          <p class="text-sm text-gray-600 mt-1">Large language model for natural language processing</p>
                        </div>
                      </Label>
                    </div>

                    <!-- Code Assistant Model -->
                    <div class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50"
                         :class="formData.aiModel === 'code-assistant' ? 'border-green-500 bg-green-50' : 'border-gray-200'"
                         @click="formData.aiModel = 'code-assistant'">
                      <RadioGroupItem value="code-assistant" id="code-assistant" />
                      <Label for="code-assistant" class="flex items-center gap-3 cursor-pointer flex-1">
                        <div class="p-2 bg-orange-100 rounded">
                          <IntegrationIcon name="ollama" class="h-5 w-5" />
                        </div>
                        <div class="flex-1">
                          <div class="flex items-center gap-2">
                            <span class="font-medium">Code Assistant Model</span>
                            <Badge variant="secondary" class="text-xs">Ollama</Badge>
                            <Badge variant="outline" class="bg-green-50 text-green-700 border-green-200 text-xs">
                              running
                            </Badge>
                          </div>
                          <p class="text-sm text-gray-600 mt-1">Local code generation and programming assistance</p>
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
          <!-- Search and Filters -->
          <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <div class="flex flex-col space-y-4">
              <!-- First Row: Search Bar -->
              <div class="flex-1">
                <div class="relative">
                  <Input
                    v-model="policySearch"
                    placeholder="Search policies..."
                    class="pl-10"
                  />
                  <svg class="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
              </div>

              <!-- Second Row: Filters and Actions -->
              <div class="flex items-center justify-between gap-4">
                <div class="flex items-center gap-4">
                  <!-- Filter by Type -->
                  <Select v-model="policyTypeFilter">
                    <SelectTrigger class="w-[180px]">
                      <div class="flex items-center">
                        <Filter class="w-4 h-4 mr-2 shrink-0" />
                        <SelectValue placeholder="All Types" />
                      </div>
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Types</SelectItem>
                      <SelectItem value="rate-limiter">Rate Limiter</SelectItem>
                      <SelectItem value="usage-tracking">Usage Tracking</SelectItem>
                      <SelectItem value="observability">Observability</SelectItem>
                      <SelectItem value="security">Security</SelectItem>
                    </SelectContent>
                  </Select>

                  <!-- Sort By -->
                  <Select v-model="policySortBy">
                    <SelectTrigger class="w-[240px]">
                      <div class="flex items-center">
                        <ArrowUpDown class="w-4 h-4 mr-2 shrink-0" />
                        <SelectValue placeholder="Most Frequently Used" />
                      </div>
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="most-used">Most Frequently Used</SelectItem>
                      <SelectItem value="recently-added">Most Recently Added</SelectItem>
                      <SelectItem value="name">Name (A-Z)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <!-- Select All/None Actions -->
                <div class="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    @click="selectAllPolicies"
                    class="text-xs"
                  >
                    <CheckSquare class="h-3 w-3 mr-1" />
                    Select All
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    @click="selectNoPolicies"
                    class="text-xs"
                  >
                    <Square class="h-3 w-3 mr-1" />
                    Select None
                  </Button>
                </div>
              </div>
            </div>
          </div>

          <!-- Available Policies -->
          <div class="space-y-4">
            <div
              v-for="policy in filteredAndSortedPolicies"
              :key="policy.id"
              class="bg-white border border-gray-200 rounded-lg p-6 cursor-pointer hover:bg-gray-50"
              :class="{
                'ring-2 ring-blue-500 ring-opacity-20': formData.policies[policy.id] && policy.color === 'blue',
                'ring-2 ring-green-500 ring-opacity-20': formData.policies[policy.id] && policy.color === 'green',
                'ring-2 ring-purple-500 ring-opacity-20': formData.policies[policy.id] && policy.color === 'purple',
                'ring-2 ring-red-500 ring-opacity-20': formData.policies[policy.id] && policy.color === 'red',
                'ring-2 ring-orange-500 ring-opacity-20': formData.policies[policy.id] && policy.color === 'orange'
              }"
              @click="formData.policies[policy.id] = !formData.policies[policy.id]"
            >
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-4">
                  <input 
                    type="checkbox" 
                    :id="policy.id" 
                    v-model="formData.policies[policy.id]"
                    :class="{
                      'h-4 w-4 border-gray-300 rounded focus:ring-blue-500 text-blue-600': policy.color === 'blue',
                      'h-4 w-4 border-gray-300 rounded focus:ring-green-500 text-green-600': policy.color === 'green',
                      'h-4 w-4 border-gray-300 rounded focus:ring-purple-500 text-purple-600': policy.color === 'purple',
                      'h-4 w-4 border-gray-300 rounded focus:ring-red-500 text-red-600': policy.color === 'red',
                      'h-4 w-4 border-gray-300 rounded focus:ring-orange-500 text-orange-600': policy.color === 'orange'
                    }"
                    @click.stop
                  />
                  <div :class="{
                    'p-3 rounded-lg bg-blue-100': policy.color === 'blue',
                    'p-3 rounded-lg bg-green-100': policy.color === 'green',
                    'p-3 rounded-lg bg-purple-100': policy.color === 'purple',
                    'p-3 rounded-lg bg-red-100': policy.color === 'red',
                    'p-3 rounded-lg bg-orange-100': policy.color === 'orange'
                  }">
                    <component :is="policy.icon" :class="{
                      'h-6 w-6 text-blue-600': policy.color === 'blue',
                      'h-6 w-6 text-green-600': policy.color === 'green',
                      'h-6 w-6 text-purple-600': policy.color === 'purple',
                      'h-6 w-6 text-red-600': policy.color === 'red',
                      'h-6 w-6 text-orange-600': policy.color === 'orange'
                    }" />
                  </div>
                  <div class="flex-1">
                    <div class="flex items-center gap-3 mb-2">
                      <h3 class="text-lg font-medium text-gray-900">{{ policy.name }}</h3>
                      <Badge variant="secondary" class="bg-gray-900 text-white text-xs px-2 py-1">{{ policy.badge }}</Badge>
                      <Badge variant="outline" class="bg-green-50 text-green-700 border-green-200 text-xs px-2 py-1">
                        <div class="w-2 h-2 bg-green-500 rounded-full mr-1"></div>
                        {{ policy.serviceCount }} services
                      </Badge>
                    </div>
                    <p class="text-gray-600 mb-3">
                      {{ policy.description }}
                    </p>
                    <div class="flex gap-2">
                      <Badge
                        v-for="config in policy.configs"
                        :key="config"
                        variant="outline"
                        class="text-xs px-2 py-1"
                      >
                        {{ config }}
                      </Badge>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- No Results -->
            <div v-if="filteredAndSortedPolicies.length === 0" class="text-center py-12">
              <div class="text-gray-400 mb-4">
                <svg class="h-12 w-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h3 class="text-lg font-medium text-gray-900 mb-2">No policies found</h3>
              <p class="text-gray-500">Try adjusting your search or filter criteria</p>
            </div>

            <!-- Add More Policies Button (Bottom) -->
            <div class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-gray-400 transition-colors">
              <Button
                variant="outline"
                class="text-gray-600 hover:text-gray-900"
                @click="showCreatePolicyDialog = true"
              >
                <Plus class="h-4 w-4 mr-2" />
                Add More Policies
              </Button>
              <p class="text-sm text-gray-500 mt-2">Create custom policies for your specific needs</p>
            </div>
          </div>
        </div>

        <!-- Step 4: Review -->
        <div v-if="currentSubStep === 4" class="space-y-8">
          <!-- Service Summary -->
          <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
            <div class="space-y-6">
              <div>
                <h2 class="text-xl font-semibold text-gray-900 mb-2">Service Summary</h2>
                <p class="text-sm text-gray-600">Review your model service configuration before deployment</p>
              </div>

              <!-- Basic Information -->
              <div class="border-l-4 border-blue-500 pl-4">
                <h3 class="font-medium text-gray-900 mb-2">Basic Information</h3>
                <div class="space-y-1 text-sm">
                  <p><span class="font-medium">Name:</span> {{ formData.serviceName || 'Not specified' }}</p>
                  <p><span class="font-medium">Summary:</span> {{ formData.summary || 'Not specified' }}</p>
                  <p v-if="formData.description"><span class="font-medium">Description:</span> {{ formData.description }}</p>
                  <div v-if="formData.tags.length > 0">
                    <span class="font-medium">Tags:</span>
                    <span class="ml-2">
                      <Badge v-for="tag in formData.tags" :key="tag" variant="outline" class="mr-1">{{ tag }}</Badge>
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
                      <p><span class="font-medium">Status:</span> <Badge variant="outline" class="bg-gray-50 text-gray-600 border-gray-200 text-xs">Stopped</Badge></p>
                    </div>
                    <div v-else-if="formData.aiModel === 'code-assistant'">
                      <p><span class="font-medium">Source:</span> Existing Model</p>
                      <p><span class="font-medium">Model:</span> Code Assistant Model</p>
                      <p><span class="font-medium">Provider:</span> Ollama</p>
                      <p><span class="font-medium">Status:</span> <Badge variant="outline" class="bg-green-50 text-green-700 border-green-200 text-xs">Running</Badge></p>
                    </div>
                    <p v-else>Not selected</p>
                  </div>
                  <div v-else-if="selectedModelSourceType === 'create-new'">
                    <p><span class="font-medium">Source:</span> New Model</p>
                    <p v-if="selectedNewModelType"><span class="font-medium">Type:</span> {{ selectedNewModelName }}</p>
                    <p v-if="selectedNewModelType" class="text-gray-600">Configuration will be completed during deployment</p>
                    <p v-else>Not configured</p>
                  </div>
                  <p v-else>Not configured</p>
                </div>
              </div>

              <!-- Applied Policies -->
              <div class="border-l-4 border-orange-500 pl-4">
                <h3 class="font-medium text-gray-900 mb-2">Applied Policies</h3>
                <div class="text-sm space-y-2">
                  <div v-if="getAppliedPoliciesDetails().length > 0">
                    <div v-for="policy in getAppliedPoliciesDetails()" :key="policy.id" class="mb-4 last:mb-0">
                      <p><span class="font-medium">Policy:</span> {{ policy.name }}</p>
                      <p><span class="font-medium">Type:</span> {{ policy.type.replace('-', ' ') }}</p>
                      <div v-for="config in parseConfigKeyValues(policy.configs)" :key="config.key">
                        <p><span class="font-medium">{{ config.key }}:</span> {{ config.value }}</p>
                      </div>
                    </div>
                  </div>
                  <p v-else class="text-gray-500">No policies applied</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Navigation Buttons -->
        <div class="flex justify-between mt-8">
          <Button 
            v-if="currentSubStep > 1"
            @click="handlePrevious"
            variant="outline"
            class="px-8"
          >
            <ArrowLeft class="mr-2 h-4 w-4" />
            Previous
          </Button>
          <div v-else></div>
          
          <Button 
            @click="handleNext"
            :disabled="!isCurrentStepValid"
            class="bg-purple-600 hover:bg-purple-700 text-white px-8 ml-auto"
          >
            {{ currentSubStep === 4 ? 'Deploy Service' : 'Next' }}
            <ArrowRight class="ml-2 h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  </div>

  <!-- Create Policy Dialog -->
  <CreatePolicyDialog
    v-model:open="showCreatePolicyDialog"
    @policy-created="handlePolicyCreated"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Plus, X, ArrowRight, Save, CheckSquare, Square, Filter, ArrowUpDown, FolderOpen, Code, ExternalLink, Search } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { MdEditor } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import CreatePolicyDialog from '@/components/CreatePolicyDialog.vue'
import { AVAILABLE_POLICIES } from '@/data/policies'

const router = useRouter()

// Sub-step navigation
const currentSubStep = ref(1)

// Step titles and descriptions
const stepTitles = [
  'Basic Information',
  'Select AI Model',
  'Apply Policies',
  'Review'
]

const stepDescriptions = [
  'Provide basic details about your model service',
  'Choose the AI model that will power your service',
  'Select policies to govern your service\'s behavior and access',
  'Review and deploy your model service'
]

// Form data
const formData = ref({
  serviceName: '',
  summary: '',
  description: '',
  tags: [] as string[],
  aiModel: '',
  policies: {}
})

// Tag input
const tagInput = ref('')

// Model source selection
const selectedModelSourceType = ref<string | null>(null)
const selectedNewModelType = ref<string | null>(null)
const searchQuery = ref('')
const isCustomBannerDismissed = ref(false)

// Dialog states
const showCreatePolicyDialog = ref(false)

// Policy search and filters
const policySearch = ref('')
const policyTypeFilter = ref('all')
const policySortBy = ref('most-used')

// Model options (from CreateModelDialog)
const modelOptions = [
  { id: 'vllm', name: 'vLLM', type: 'Model' },
  { id: 'ollama', name: 'Ollama', type: 'Model' },
  { id: 'huggingface', name: 'Hugging Face', type: 'Model' },
]

// Count of existing models
const existingModelsCount = computed(() => 2) // Based on the 2 models in existing section

// Filtered models for search
const filteredModels = computed(() => {
  if (!searchQuery.value) return modelOptions
  return modelOptions.filter(model => 
    model.name.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

// Selected new model name
const selectedNewModelName = computed(() => {
  const model = modelOptions.find(m => m.id === selectedNewModelType.value)
  return model?.name || 'Model'
})

// Filtered and sorted policies
const filteredAndSortedPolicies = computed(() => {
  let filtered = AVAILABLE_POLICIES.filter(policy => {
    // Filter by search
    const matchesSearch = policySearch.value === '' || 
      policy.name.toLowerCase().includes(policySearch.value.toLowerCase()) ||
      policy.description.toLowerCase().includes(policySearch.value.toLowerCase()) ||
      policy.badge.toLowerCase().includes(policySearch.value.toLowerCase())
    
    // Filter by type
    const matchesType = policyTypeFilter.value === 'all' || policy.type === policyTypeFilter.value
    
    return matchesSearch && matchesType
  })

  // Sort policies
  if (policySortBy.value === 'most-used') {
    filtered = filtered.sort((a, b) => b.usageCount - a.usageCount)
  } else if (policySortBy.value === 'recently-added') {
    filtered = filtered.sort((a, b) => b.dateAdded.getTime() - a.dateAdded.getTime())
  } else if (policySortBy.value === 'name') {
    filtered = filtered.sort((a, b) => a.name.localeCompare(b.name))
  }

  return filtered
})

// No watch needed for inline model creation

// Step validation
const isStep1Valid = computed(() => {
  return formData.value.serviceName.trim() !== '' && 
         formData.value.summary.trim() !== ''
})

// Can save draft when we have name and summary
const canSaveDraft = computed(() => isStep1Valid.value)

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
  // Review step is always valid if we've reached it
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

// Handle policy created
const handlePolicyCreated = () => {
  // In a real app, this would update the policy list
  console.log('Policy created')
}

// Get applied policies with full details for review
const getAppliedPoliciesDetails = () => {
  const policies = []
  for (const [policyId, isSelected] of Object.entries(formData.value.policies)) {
    if (isSelected) {
      const policy = AVAILABLE_POLICIES.find(p => p.id === policyId)
      if (policy) {
        policies.push(policy)
      }
    }
  }
  return policies
}

// Parse config strings into key-value pairs
const parseConfigKeyValues = (configs: string[]) => {
  return configs.map(config => {
    const colonIndex = config.indexOf(':')
    if (colonIndex > -1) {
      return {
        key: config.substring(0, colonIndex).trim(),
        value: config.substring(colonIndex + 1).trim()
      }
    }
    return {
      key: config,
      value: ''
    }
  })
}

// Select all visible policies
const selectAllPolicies = () => {
  filteredAndSortedPolicies.value.forEach(policy => {
    formData.value.policies[policy.id] = true
  })
}

// Select no policies
const selectNoPolicies = () => {
  formData.value.policies = {}
}

// Navigation handlers
const handleNext = () => {
  if (!isCurrentStepValid.value) return
  
  if (currentSubStep.value < 4) {
    currentSubStep.value++
  } else {
    // Deploy the service
    console.log('Deploying model service with data:', formData.value)
    // router.push('/services')
  }
}

const handlePrevious = () => {
  if (currentSubStep.value > 1) {
    currentSubStep.value--
  }
}

const handleBack = () => {
  router.push('/create')
}

// Save draft function
const saveDraft = () => {
  if (!canSaveDraft.value) return
  
  console.log('Saving draft:', formData.value)
  // In a real app, this would save to local storage or backend
  // localStorage.setItem('modelServiceDraft', JSON.stringify(formData.value))
}
</script>