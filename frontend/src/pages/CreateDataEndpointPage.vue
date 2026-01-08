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
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
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
      <div class="flex gap-12 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
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
                      ? 'bg-primary text-white'
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
                    What do you want to share?
                  </h3>
                  <p class="body-sm text-muted-foreground mt-1">
                    {{
                      existingDataSourcesCount > 0
                        ? 'Add files or connect database'
                        : 'Select files to share'
                    }}
                  </p>
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
                      ? 'bg-primary text-white'
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
                    How should it work?
                  </h3>
                  <p class="body-sm text-muted-foreground mt-1">Configure output and AI settings</p>
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
                      ? 'bg-primary text-white'
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
                    Who can access it?
                  </h3>
                  <p class="body-sm text-muted-foreground mt-1">Control who can use your content</p>
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
                      ? 'bg-primary text-white'
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
                    Tell us more about it
                  </h3>
                  <p class="body-sm text-muted-foreground mt-1">Name and describe your endpoint</p>
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

              <!-- Step 5 -->
              <div
                class="flex items-start gap-4"
                :class="{
                  'cursor-pointer': isStepClickable(5),
                  'cursor-not-allowed': !isStepClickable(5),
                }"
                @click="navigateToStep(5)"
              >
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium body-sm transition-all',
                    currentSubStep >= 5
                      ? 'bg-primary text-white'
                      : 'bg-muted text-muted-foreground',
                    isStepClickable(5) ? 'hover:scale-105' : '',
                  ]"
                >
                  {{ currentSubStep > 5 ? '✓' : '5' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium body-sm transition-colors',
                      currentSubStep >= 5 ? 'text-foreground' : 'text-muted-foreground',
                      isStepClickable(5) ? 'hover:text-primary' : '',
                    ]"
                  >
                    Review & Publish
                  </h3>
                  <p class="body-sm text-muted-foreground mt-1">Final check and go live</p>
                  <div
                    v-if="currentSubStep > 5"
                    class="mt-2 body-sm text-primary bg-primary/10 px-2 py-1 rounded"
                  >
                    ✓ Completed
                  </div>
                  <div
                    v-else-if="currentSubStep === 5"
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

          <!-- Step 1: Choose Data Source -->
          <div v-if="currentSubStep === 1" class="space-y-6">
            <!-- Data source selection cards - only show if there are existing datasets -->
            <div
              v-if="existingDataSourcesCount > 0"
              :class="[
                'grid gap-6',
                existingDataSourcesCount > 0 ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1',
              ]"
            >
              <!-- Add Files Card -->
              <Card
                :class="[
                  'transition-all duration-200 border-2 cursor-pointer hover:shadow-lg hover:border-primary/30 hover:bg-gradient-to-br hover:from-primary/5 hover:to-primary/10',
                  selectedDataSourceType === 'filesystem'
                    ? 'border-primary bg-gradient-to-br from-primary/5 to-primary/10'
                    : 'border-border bg-card',
                ]"
                @click="selectDataSourceType('filesystem')"
              >
                <CardContent class="p-6 h-full">
                  <div class="flex flex-col items-center text-center h-full">
                    <div
                      class="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center mb-4"
                    >
                      <FileText class="w-7 h-7 text-primary" />
                    </div>

                    <h3 class="heading-3 text-foreground mb-2">Add Files</h3>
                    <p class="body-sm text-muted-foreground mb-4">
                      Add documents, spreadsheets, or text files from your computer
                    </p>

                    <div class="space-y-2 body-sm text-muted-foreground mb-4 flex-grow">
                      <div class="flex items-center gap-1">
                        <span>📄</span>
                        <span>PDF, Word, PowerPoint documents</span>
                      </div>
                      <div class="flex items-center gap-1">
                        <span>📊</span>
                        <span>CSV, Excel spreadsheets</span>
                      </div>
                      <div class="flex items-center gap-1">
                        <span>📝</span>
                        <span>Text, Markdown, JSON files</span>
                      </div>
                    </div>

                    <div class="flex items-center gap-1 mt-auto">
                      <span
                        class="body-sm bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium"
                        >Easy</span
                      >
                      <span class="body-sm text-muted-foreground">2 minute setup</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <!-- Existing Sources Card - Only show if there are existing datasets -->
              <Card
                v-if="existingDataSourcesCount > 0"
                :class="[
                  'transition-all duration-200 border-2 cursor-pointer hover:shadow-lg hover:border-green-300 hover:bg-gradient-to-br hover:from-green-50 hover:to-emerald-50 bg-card',
                  selectedDataSourceType === 'existing'
                    ? 'border-green-500 bg-gradient-to-br from-green-50 to-emerald-50'
                    : 'border-border',
                ]"
                @click="selectDataSourceType('existing')"
              >
                <CardContent class="p-6 h-full">
                  <div class="flex flex-col items-center text-center h-full">
                    <div
                      class="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center mb-4"
                    >
                      <FolderOpen class="w-7 h-7 text-green-600" />
                    </div>

                    <h3 class="heading-3 text-foreground mb-2">Existing Sources</h3>
                    <p class="body-sm text-muted-foreground mb-4">
                      Choose from data you've already connected<br /><br />
                    </p>

                    <!-- Loading state -->
                    <div
                      v-if="loadingDatasets"
                      class="space-y-2 mb-4 flex-grow flex items-center justify-center"
                    >
                      <span class="body-sm text-muted-foreground">Loading datasets...</span>
                    </div>

                    <!-- Error state -->
                    <div
                      v-else-if="datasetsError"
                      class="space-y-2 mb-4 flex-grow flex items-center justify-center"
                    >
                      <span class="body-sm text-red-600">Failed to load datasets</span>
                    </div>

                    <!-- Dataset list -->
                    <div v-else class="space-y-2 mb-4 flex-grow">
                      <div
                        v-for="dataset in displayedDatasets"
                        :key="dataset.name"
                        class="flex items-center gap-2 body-sm"
                      >
                        <div class="w-2 h-2 bg-primary rounded-full"></div>
                        <span class="text-muted-foreground truncate">{{ dataset.name }}</span>
                      </div>
                      <div
                        v-if="remainingDatasetsCount > 0"
                        class="flex items-center gap-2 body-sm text-muted-foreground"
                      >
                        <div class="w-2 h-2"></div>
                        <span>...and {{ remainingDatasetsCount }} more</span>
                      </div>
                    </div>

                    <div class="flex items-center gap-1 mt-auto">
                      <span
                        class="body-sm bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium"
                      >
                        Quick
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <!-- Dataset Selection (shown when existing is selected) -->
            <div v-if="selectedDataSourceType === 'existing'" class="mt-6">
              <Card class="bg-card border-border">
                <CardContent class="p-6">
                  <div class="space-y-4">
                    <h3 class="heading-3 text-foreground mb-4">Available Data Sources</h3>

                    <!-- Loading state -->
                    <div v-if="loadingDatasets" class="flex items-center justify-center py-8">
                      <span class="body-sm text-muted-foreground">Loading datasets...</span>
                    </div>

                    <!-- Error state -->
                    <div v-else-if="datasetsError" class="flex items-center justify-center py-8">
                      <span class="body-sm text-red-600"
                        >Failed to load datasets: {{ datasetsError }}</span
                      >
                    </div>

                    <!-- Dataset list -->
                    <div v-else-if="existingDatasets.length > 0" class="space-y-3">
                      <div
                        v-for="dataset in existingDatasets"
                        :key="dataset.name"
                        class="flex items-center space-x-3 p-4 border rounded-lg transition-colors"
                        :class="[
                          formData.selectedDataSource === dataset.id
                            ? 'border-primary bg-primary/5'
                            : 'border-border',
                          isDatasetSelectable(dataset)
                            ? 'cursor-pointer hover:bg-muted/50'
                            : 'cursor-not-allowed opacity-60',
                        ]"
                        @click="
                          isDatasetSelectable(dataset)
                            ? (formData.selectedDataSource = dataset.id)
                            : null
                        "
                      >
                        <div class="flex items-center gap-3 flex-1">
                          <div class="p-2 bg-primary/10 rounded">
                            <Database class="h-5 w-5 text-primary" />
                          </div>
                          <div class="flex-1">
                            <div class="flex items-center gap-2">
                              <span class="font-medium text-foreground">{{ dataset.name }}</span>
                              <Badge variant="secondary" class="body-sm">{{ dataset.dtype }}</Badge>
                              <Badge
                                variant="outline"
                                :class="getStatusBadgeClasses(dataset.provisioner_status?.status)"
                                class="body-sm"
                              >
                                {{ getStatusText(dataset.provisioner_status?.status) }}
                              </Badge>
                            </div>
                            <p class="body-sm text-muted-foreground mt-1">
                              {{ dataset.summary || 'No description available' }}
                            </p>
                          </div>
                        </div>
                        <div
                          class="w-4 h-4 rounded-full border-2 flex items-center justify-center"
                          :class="
                            formData.selectedDataSource === dataset.id
                              ? 'border-primary bg-primary'
                              : 'border-muted-foreground'
                          "
                        >
                          <div
                            v-if="formData.selectedDataSource === dataset.id"
                            class="w-2 h-2 rounded-full bg-white"
                          ></div>
                        </div>
                      </div>
                    </div>

                    <!-- Empty state -->
                    <div v-else class="flex items-center justify-center py-8">
                      <span class="body-sm text-muted-foreground">No datasets available</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <!-- File Explorer (shown when filesystem is selected) -->
            <div v-if="selectedDataSourceType === 'filesystem'" class="mt-6">
              <Card class="bg-card border-border">
                <CardContent class="p-6">
                  <FileExplorer
                    v-model="selectedFiles"
                    :show-hidden="false"
                    :allow-multiple="true"
                  />
                </CardContent>
              </Card>

              <!-- File descriptions for selected files -->
              <div v-if="selectedFiles.length > 0" class="mt-4">
                <h4 class="font-medium text-foreground mb-3">
                  Selected Paths ({{ selectedFiles.length }})
                </h4>
                <div class="space-y-2">
                  <Card v-for="file in selectedFiles" :key="file" class="bg-muted/50 border-border">
                    <CardContent class="p-4">
                      <div class="flex items-start gap-3">
                        <FileText class="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                        <div class="min-w-0 flex-1 space-y-1">
                          <div class="flex items-center justify-between gap-2">
                            <p class="body-sm font-medium text-foreground truncate">{{ file }}</p>
                            <Button
                              @click="removeFile(selectedFiles.indexOf(file))"
                              variant="ghost"
                              size="sm"
                              class="h-6 w-6 p-0 hover:text-destructive"
                            >
                              <X class="h-3 w-3" />
                            </Button>
                          </div>
                          <div class="space-y-2">
                            <Label class="body-sm text-muted-foreground"
                              >Description (Optional)</Label
                            >
                            <Input
                              v-model="fileDescriptions[file]"
                              placeholder="Brief description of this file's content..."
                              class="body-sm"
                            />
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </div>
          </div>

          <!-- Step 2: How should it work? -->
          <div v-if="currentSubStep === 2" class="space-y-8">
            <!-- Response Type Selection -->
            <div class="space-y-4">
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                <!-- Raw Document Chunks Card -->
                <Card
                  class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-blue-300 hover:bg-gradient-to-br hover:from-blue-50 hover:to-indigo-50 border-2 bg-card"
                  :class="
                    formData.responseType === 'raw'
                      ? 'border-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50'
                      : 'border-border'
                  "
                  @click="selectResponseType('raw')"
                >
                  <CardContent class="p-6">
                    <div class="flex flex-col items-center text-center">
                      <div
                        class="w-12 h-12 rounded-full bg-blue-100 flex items-center justify-center mb-4"
                      >
                        <FileType class="w-6 h-6 text-blue-600" />
                      </div>

                      <h3 class="heading-3 text-foreground mb-2">Search & Quote</h3>
                      <p class="body-sm font-medium mb-3 text-blue-600">
                        Return exact text matches
                      </p>

                      <p class="body-sm text-muted-foreground mb-4 text-balance leading-relaxed">
                        Users search your content and get back the exact matching text
                      </p>

                      <p class="body-sm text-muted-foreground text-balance">
                        Best for: News archives, research papers, legal documents
                      </p>
                    </div>
                  </CardContent>
                </Card>

                <!-- AI-Generated Summary Card -->
                <Card
                  class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-purple-300 hover:bg-gradient-to-br hover:from-purple-50 hover:to-pink-50 border-2 bg-card"
                  :class="
                    formData.responseType === 'summary'
                      ? 'border-purple-500 bg-gradient-to-br from-purple-50 to-pink-50'
                      : 'border-border'
                  "
                  @click="selectResponseType('summary')"
                >
                  <CardContent class="p-6">
                    <div class="flex flex-col items-center text-center">
                      <div
                        class="w-12 h-12 rounded-full bg-purple-100 flex items-center justify-center mb-4"
                      >
                        <Sparkles class="w-6 h-6 text-purple-600" />
                      </div>

                      <h3 class="heading-3 text-foreground mb-2">AI Assistant</h3>
                      <p class="body-sm font-medium mb-3 text-purple-600">
                        Smart answers from your data
                      </p>

                      <p class="body-sm text-muted-foreground mb-4 text-balance leading-relaxed">
                        An AI reads your content and provides intelligent answers
                      </p>

                      <p class="body-sm text-muted-foreground text-balance">
                        Best for: Customer support, knowledge bases, Q&A systems
                      </p>
                    </div>
                  </CardContent>
                </Card>

                <!-- Both Raw and Summary Card -->
                <Card
                  class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-green-300 hover:bg-gradient-to-br hover:from-green-50 hover:to-emerald-50 border-2 bg-card relative"
                  :class="
                    formData.responseType === 'both'
                      ? 'border-green-500 bg-gradient-to-br from-green-50 to-emerald-50'
                      : 'border-border'
                  "
                  @click="selectResponseType('both')"
                >
                  <!-- Recommended Badge -->
                  <div
                    class="absolute -top-2 -right-2 bg-green-600 text-white text-xs font-semibold px-3 py-1 rounded-full shadow-md"
                  >
                    Recommended
                  </div>
                  <CardContent class="p-6">
                    <div class="flex flex-col items-center text-center">
                      <div
                        class="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mb-4"
                      >
                        <GitMerge class="w-6 h-6 text-green-600" />
                      </div>

                      <h3 class="heading-3 text-foreground mb-2">Search + AI</h3>
                      <p class="body-sm font-medium mb-3 text-green-600">Complete solution</p>

                      <p class="body-sm text-muted-foreground mb-4 text-balance leading-relaxed">
                        Users get both exact quotes and AI-powered answers
                      </p>

                      <p class="body-sm text-muted-foreground text-balance">
                        Best for: Academic resources, comprehensive documentation
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              <!-- AI Model Selection -->
              <div
                v-if="formData.responseType === 'summary' || formData.responseType === 'both'"
                class="bg-card rounded-lg shadow-sm border border-border p-6"
              >
                <!-- Quick Setup (only when no existing models) -->
                <div v-if="availableModels.length === 0">
                  <div class="space-y-2 mb-6">
                    <h3 class="heading-3 text-foreground">Choose AI Model</h3>
                    <p class="body-sm text-muted-foreground">
                      Select how you want to power your AI responses
                    </p>
                  </div>

                  <div class="space-y-3">
                    <!-- OpenAI GPT-4o Option -->
                    <div
                      class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-muted/50"
                      :class="
                        selectedAiProvider === 'openai-gpt-4o'
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-border'
                      "
                      @click="selectAiProvider('openai-gpt-4o')"
                    >
                      <div
                        class="w-4 h-4 rounded-full border-2 flex items-center justify-center"
                        :class="
                          selectedAiProvider === 'openai-gpt-4o'
                            ? 'border-blue-500 bg-blue-500'
                            : 'border-muted-foreground'
                        "
                      >
                        <div
                          v-if="selectedAiProvider === 'openai-gpt-4o'"
                          class="w-2 h-2 rounded-full bg-white"
                        ></div>
                      </div>
                      <div class="flex items-center gap-3 cursor-pointer flex-1">
                        <div class="p-2 rounded bg-primary/10">
                          <span class="text-primary font-bold text-sm">AI</span>
                        </div>
                        <div class="flex-1">
                          <div class="flex items-center gap-2">
                            <span class="font-medium">openai/gpt-4o</span>
                            <Badge variant="secondary" class="text-xs">Popular</Badge>
                          </div>
                          <p class="text-sm text-muted-foreground mt-1">
                            Most capable, industry standard
                          </p>
                        </div>
                      </div>
                    </div>

                    <!-- Claude 3.5 Sonnet via OpenRouter -->
                    <div
                      class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-muted/50"
                      :class="
                        selectedAiProvider === 'openrouter-claude'
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-border'
                      "
                      @click="selectAiProvider('openrouter-claude')"
                    >
                      <div
                        class="w-4 h-4 rounded-full border-2 flex items-center justify-center"
                        :class="
                          selectedAiProvider === 'openrouter-claude'
                            ? 'border-blue-500 bg-blue-500'
                            : 'border-muted-foreground'
                        "
                      >
                        <div
                          v-if="selectedAiProvider === 'openrouter-claude'"
                          class="w-2 h-2 rounded-full bg-white"
                        ></div>
                      </div>
                      <div class="flex items-center gap-3 cursor-pointer flex-1">
                        <div class="p-2 rounded bg-primary/10">
                          <span class="text-primary font-bold text-xs">OR</span>
                        </div>
                        <div class="flex-1">
                          <div class="flex items-center gap-2">
                            <span class="font-medium">openrouter/claude-3.5-sonnet</span>
                            <Badge variant="secondary" class="text-xs">Smart</Badge>
                          </div>
                          <p class="text-sm text-muted-foreground mt-1">
                            Excellent for analysis and reasoning
                          </p>
                        </div>
                      </div>
                    </div>

                    <!-- Groq Llama Option -->
                    <div
                      class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-muted/50"
                      :class="
                        selectedAiProvider === 'groq-llama'
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-border'
                      "
                      @click="selectAiProvider('groq-llama')"
                    >
                      <div
                        class="w-4 h-4 rounded-full border-2 flex items-center justify-center"
                        :class="
                          selectedAiProvider === 'groq-llama'
                            ? 'border-blue-500 bg-blue-500'
                            : 'border-muted-foreground'
                        "
                      >
                        <div
                          v-if="selectedAiProvider === 'groq-llama'"
                          class="w-2 h-2 rounded-full bg-white"
                        ></div>
                      </div>
                      <div class="flex items-center gap-3 cursor-pointer flex-1">
                        <div class="p-2 rounded bg-primary/10">
                          <span class="text-primary font-bold text-sm">⚡</span>
                        </div>
                        <div class="flex-1">
                          <div class="flex items-center gap-2">
                            <span class="font-medium">groq/llama-3.3-70b-instruct</span>
                            <Badge variant="secondary" class="text-xs">Fast</Badge>
                          </div>
                          <p class="text-sm text-muted-foreground mt-1">
                            Ultra-fast inference speed
                          </p>
                        </div>
                      </div>
                    </div>

                    <!-- API Key Input -->
                    <div v-if="selectedAiProvider" class="mt-4 space-y-2">
                      <Label class="body-sm text-muted-foreground font-medium">
                        {{ getProviderName(selectedAiProvider) }} API Key
                      </Label>
                      <Input
                        v-model="apiKeys[selectedAiProvider]"
                        type="password"
                        :placeholder="`Enter your ${getProviderName(selectedAiProvider)} API key`"
                        class="body-sm"
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
                        Your API key is stored securely and only used for your endpoint.
                        <a
                          :href="getProviderApiUrl(selectedAiProvider)"
                          target="_blank"
                          class="text-primary hover:underline"
                        >
                          Get API key →
                        </a>
                      </p>
                    </div>
                  </div>
                </div>

                <!-- Existing Models (when models are available) -->
                <div v-else>
                  <ModelSelector
                    v-model="formData.aiModel"
                    title="Choose AI Model"
                    description="Select from your existing models or create a new one"
                    id-prefix="step2"
                    @create-model="handleStep3CreateModel"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- Step 3: Who can access it? -->
          <div v-if="currentSubStep === 3" class="space-y-6">
            <!-- Policy Configuration -->
            <div class="space-y-6">
              <div
                v-for="policy in policyTypes"
                :key="policy.id"
                class="bg-card/60 backdrop-blur-sm border border-border/50 rounded-2xl p-6"
              >
                <!-- Policy Header -->
                <div class="flex items-center justify-between mb-3">
                  <div class="flex items-center gap-3">
                    <div
                      :class="[
                        'p-2 rounded-lg',
                        policy.color === 'blue' ? 'bg-blue-100' : '',
                        policy.color === 'green' ? 'bg-green-100' : '',
                        policy.color === 'yellow' ? 'bg-yellow-100' : '',
                        policy.color === 'purple' ? 'bg-purple-100' : '',
                        policy.color === 'red' ? 'bg-red-100' : '',
                      ]"
                    >
                      <component
                        :is="policy.icon"
                        :class="[
                          'h-5 w-5',
                          policy.color === 'blue' ? 'text-primary' : '',
                          policy.color === 'green' ? 'text-green-600' : '',
                          policy.color === 'yellow' ? 'text-yellow-600' : '',
                          policy.color === 'purple' ? 'text-purple-600' : '',
                          policy.color === 'red' ? 'text-red-600' : '',
                        ]"
                      />
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
                    <p class="body-sm text-green-700">
                      <strong class="font-medium">Default: </strong>
                      <span v-if="policy.id === 'access'"
                        >Open access - everyone can use your endpoint</span
                      >
                      <span v-else-if="policy.id === 'rate_limit'"
                        >No rate limits - unlimited usage</span
                      >
                      <span v-else-if="policy.id === 'pricing'"
                        >Free access - no charges applied</span
                      >
                      <span v-else>Open access - most permissive settings</span>
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
                    <!-- Rule in Edit Mode (Expanded) -->
                    <div v-if="rule.isEditing" class="space-y-3">
                      <!-- Authorization Policy Form -->
                      <div v-if="policy.id === 'access'">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                          <div class="space-y-1">
                            <Label class="body-sm text-muted-foreground font-medium"
                              >Rule Type</Label
                            >
                            <Select v-model="authorizationForm.ruleType">
                              <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                                <SelectValue placeholder="Select rule type" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="allow" class="body-sm"
                                  >Allow specific users</SelectItem
                                >
                                <SelectItem value="deny" class="body-sm"
                                  >Deny specific users</SelectItem
                                >
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
                        <div class="space-y-1 mt-3">
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
                      <div v-if="policy.id === 'rate_limit'">
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
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
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                          <div class="space-y-1">
                            <Label class="body-sm text-muted-foreground font-medium">Note</Label>
                            <Input
                              v-model="rateLimiterForm.note"
                              placeholder="Optional description"
                              class="h-9 rounded-lg border-border bg-card body-sm"
                            />
                          </div>
                        </div>
                      </div>

                      <!-- Pricing Policy Form -->
                      <div v-if="policy.id === 'pricing'">
                        <div class="space-y-3">
                          <!-- Price and Note side-by-side -->
                          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div class="space-y-1">
                              <Label class="body-sm text-muted-foreground font-medium"
                                >Price per query ($)</Label
                              >
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
                          <!-- Apply To and Users row -->
                          <div class="flex flex-col sm:flex-row gap-3 sm:gap-4">
                            <div class="space-y-1 sm:flex-shrink-0 sm:w-32">
                              <Label class="body-sm text-muted-foreground font-medium"
                                >Apply To</Label
                              >
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
                            <div
                              v-if="pricingForm.userType === 'specific'"
                              class="space-y-1 flex-1"
                            >
                              <Label class="body-sm text-muted-foreground font-medium">Users</Label>
                              <Input
                                v-model="pricingForm.users"
                                placeholder="user1@example.com, user2@example.com"
                                class="h-9 rounded-lg border-border bg-card body-sm"
                              />
                              <p class="text-xs text-muted-foreground">
                                Comma-separated list. Wildcard supported (e.g., *@company.com,
                                *.edu, *@contractors.org)
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>

                      <!-- Form Action Buttons -->
                      <div class="flex gap-2 pt-3 border-t border-border">
                        <Button
                          @click="savePolicy(policy.id, rule.id)"
                          size="sm"
                          class="rounded-lg body-sm font-medium px-3 py-2"
                        >
                          Save
                        </Button>
                        <Button
                          @click="cancelEditPolicy(policy.id, rule.id)"
                          variant="outline"
                          size="sm"
                          class="rounded-lg border-border body-sm font-medium px-3 py-2"
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>

                    <!-- Rule in Collapsed Mode -->
                    <div v-else class="flex items-start justify-between">
                      <div class="flex-1">
                        <h4 class="body-sm font-medium text-foreground">
                          {{ rule.config.note || `${policy.name} Rule #${ruleIndex + 1}` }}
                        </h4>
                        <p class="body-sm text-muted-foreground mt-1">
                          {{ getRuleSummary(policy.id, rule.config) }}
                        </p>
                      </div>
                      <div class="flex gap-2">
                        <Button variant="outline" size="sm" @click="editPolicy(policy.id, rule.id)">
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
            </div>
          </div>

          <!-- Step 4: Tell us more about it -->
          <div
            v-if="currentSubStep === 4"
            class="bg-card rounded-lg shadow-sm border border-border p-8 space-y-8"
          >
            <!-- Interactive examples -->
            <div class="mb-8 bg-primary/10 border border-blue-200 rounded-lg p-4">
              <h4 class="font-medium text-blue-900 mb-3 flex items-center gap-2">
                <Lightbulb class="w-4 h-4" />
                Popular examples to get you started
              </h4>
              <p class="body-sm text-primary/80 mb-4">Click any example to auto-fill the form</p>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-4 body-sm">
                <button
                  @click="fillExampleData('news')"
                  class="bg-card p-3 rounded border hover:border-blue-400 hover:shadow-sm transition-all text-left"
                >
                  <p class="font-medium text-foreground">📰 News Archive</p>
                  <p class="text-muted-foreground mt-1">
                    "Herald Tribune Archives 2010-2024" - Historical articles and investigative
                    reports
                  </p>
                </button>
                <button
                  @click="fillExampleData('research')"
                  class="bg-card p-3 rounded border hover:border-blue-400 hover:shadow-sm transition-all text-left"
                >
                  <p class="font-medium text-foreground">🔬 Research Data</p>
                  <p class="text-muted-foreground mt-1">
                    "Cancer Research Publications" - Peer-reviewed papers and clinical studies
                  </p>
                </button>
                <button
                  @click="fillExampleData('library')"
                  class="bg-card p-3 rounded border hover:border-blue-400 hover:shadow-sm transition-all text-left"
                >
                  <p class="font-medium text-foreground">📚 Document Library</p>
                  <p class="text-muted-foreground mt-1">
                    "Technical Manuals Collection" - Product guides and documentation
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
                    placeholder="e.g., herald-tribune-archives"
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
                  placeholder="e.g., Historical news articles from 2010-2024"
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

              <!-- Watched Paths Descriptions -->
              <div
                v-if="selectedDataSourceType === 'filesystem' && selectedFiles.length > 0"
                class="space-y-3"
              >
                <Label class="body-sm font-medium text-foreground"
                  >Watched Paths Descriptions (Optional)</Label
                >
                <div class="space-y-2">
                  <div
                    v-for="file in selectedFiles"
                    :key="file"
                    class="flex items-start gap-3 p-3 bg-muted/50 border border-border rounded-lg"
                  >
                    <FileText class="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                    <div class="flex-1 min-w-0">
                      <p class="body-sm font-medium text-foreground truncate mb-1">{{ file }}</p>
                      <Input
                        v-model="fileDescriptions[file]"
                        placeholder="Brief description of what this file contains..."
                        class="body-sm"
                      />
                    </div>
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

          <!-- Step 5: Review & Publish -->
          <div v-if="currentSubStep === 5" class="space-y-6">
            <!-- Header -->
            <div
              class="bg-card/60 backdrop-blur-sm border border-border/50 rounded-2xl p-8 text-center"
            >
              <div
                class="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4"
              >
                <svg
                  class="w-8 h-8 text-green-600"
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
                Your data endpoint is configured and ready to go. Review the summary below and
                publish when you're ready.
              </p>
            </div>

            <!-- Creation Progress -->
            <div
              v-if="isCreating"
              class="bg-card/60 backdrop-blur-sm border border-border/50 rounded-2xl p-8 text-center"
            >
              <div
                class="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4 animate-pulse"
              >
                <svg class="w-8 h-8 text-blue-600 animate-spin" fill="none" viewBox="0 0 24 24">
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
                {{ creationStep || 'Setting up your data endpoint...' }}
              </p>
            </div>

            <!-- Summary -->
            <div class="bg-card border border-border rounded-2xl p-8 space-y-6">
              <!-- Basic Information -->
              <div>
                <h3 class="heading-2 text-foreground mb-6">Summary</h3>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                  <div>
                    <p class="body-sm font-medium text-muted-foreground mb-2">Name</p>
                    <p class="text-foreground font-medium">
                      {{ formData.endpointName || 'Not specified' }}
                    </p>
                  </div>

                  <div>
                    <p class="body-sm font-medium text-muted-foreground mb-2">Data Source</p>
                    <div class="flex items-center gap-2">
                      <div
                        v-if="selectedDataSourceType === 'filesystem'"
                        class="flex items-center gap-2"
                      >
                        <FolderOpen class="w-4 h-4 text-primary" />
                        <span class="text-foreground">File System</span>
                        <span class="body-sm text-muted-foreground"
                          >({{ selectedFiles.length }}
                          {{ selectedFiles.length === 1 ? 'file' : 'files' }})</span
                        >
                      </div>
                      <div
                        v-else-if="selectedDataSourceType === 'existing'"
                        class="flex items-center gap-2"
                      >
                        <Database class="w-4 h-4 text-green-600" />
                        <span class="text-foreground">Existing Source</span>
                        <span v-if="selectedDatasetName" class="body-sm text-muted-foreground">
                          ({{ selectedDatasetName }})
                        </span>
                      </div>
                      <span v-else class="text-muted-foreground italic">Not configured</span>
                    </div>
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
                    <MdPreview
                      :model-value="formData.description"
                      :preview-theme="'github'"
                      :code-theme="'github'"
                      language="en-US"
                    />
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

              <!-- Configured Files Detail -->
              <div
                v-if="selectedDataSourceType === 'filesystem' && selectedFiles.length > 0"
                class="border-t pt-6"
              >
                <p class="body-sm font-medium text-muted-foreground mb-3">Selected Files</p>
                <div class="space-y-3">
                  <div
                    v-for="file in selectedFiles"
                    :key="file"
                    class="flex items-start gap-3 p-3 bg-muted/50 rounded-lg"
                  >
                    <FileText class="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                    <div class="min-w-0 flex-1">
                      <p class="body-sm font-medium text-foreground truncate">{{ file }}</p>
                      <p class="body-sm text-muted-foreground mt-1">
                        {{ fileDescriptions[file] || 'No description provided' }}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Output Configuration -->
              <div class="border-t pt-6">
                <p class="body-sm font-medium text-muted-foreground mb-3">Output Configuration</p>
                <div class="bg-muted/50 rounded-lg p-4">
                  <div class="body-sm space-y-2">
                    <div v-if="formData.responseType === 'raw'" class="flex items-start gap-3">
                      <FileType class="w-4 h-4 text-primary mt-0.5" />
                      <div>
                        <span class="font-medium text-foreground">Search & Quote</span>
                        <p class="text-muted-foreground body-sm mt-1">
                          Returns exact text matches from your content
                        </p>
                      </div>
                    </div>
                    <div
                      v-else-if="formData.responseType === 'summary'"
                      class="flex items-start gap-3"
                    >
                      <Sparkles class="w-4 h-4 text-purple-600 mt-0.5" />
                      <div>
                        <span class="font-medium text-foreground">AI Assistant</span>
                        <p class="text-muted-foreground body-sm mt-1">
                          AI provides intelligent answers from your data
                        </p>
                      </div>
                    </div>
                    <div
                      v-else-if="formData.responseType === 'both'"
                      class="flex items-start gap-3"
                    >
                      <GitMerge class="w-4 h-4 text-green-600 mt-0.5" />
                      <div>
                        <span class="font-medium text-foreground">Search + AI</span>
                        <p class="text-muted-foreground body-sm mt-1">
                          Both exact quotes and AI-powered answers
                        </p>
                      </div>
                    </div>
                    <p v-else class="text-muted-foreground italic">Not configured</p>

                    <!-- Show AI Model if selected -->
                    <div
                      v-if="
                        (formData.responseType === 'summary' || formData.responseType === 'both') &&
                        formData.aiModel
                      "
                      class="mt-3 pt-3 border-t border-border"
                    >
                      <span class="body-sm text-muted-foreground">AI Model: </span>
                      <span class="body-sm font-medium text-foreground">{{
                        getModelDisplayName()
                      }}</span>
                      <span v-if="selectedAiProvider" class="text-blue-600"> (New Model)</span>
                      <span v-else-if="formData.aiModel" class="text-green-600">
                        (Existing Model)</span
                      >
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
                  <div v-for="policyType in policyTypes" :key="policyType.id">
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

          <!-- Error Display (only in step 5) -->
          <div
            v-if="creationError && currentSubStep === 5"
            class="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg"
          >
            <div class="flex items-start gap-3">
              <X class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div class="flex-1">
                <h4 class="font-medium text-red-900 mb-1">Failed to create endpoint</h4>
                <p class="text-sm text-red-700">{{ creationError }}</p>
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
              :disabled="
                !isCurrentStepValid || isCreating || (currentSubStep === 3 && isAnyRuleFormOpen)
              "
              class="bg-primary hover:bg-primary/90 text-white px-8"
            >
              <template v-if="currentSubStep === 5 && isCreating">
                {{ creationStep || 'Publishing...' }}
              </template>
              <template v-else>
                {{ currentSubStep === 5 ? 'Publish Now' : 'Continue' }}
              </template>
              <ArrowRight v-if="!isCreating" class="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  </ErrorBoundary>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  ArrowRight,
  FileText,
  FolderOpen,
  Database,
  ChevronRight,
  Plus,
  X,
  FileType,
  Sparkles,
  GitMerge,
  Shield,
  Gauge,
  DollarSign,
  UserCheck,
  Lightbulb,
  Loader2,
  Check,
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
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import FileExplorer from '@/components/FileExplorer.vue'
import ModelSelector from '@/components/ModelSelector.vue'
import { MdEditor, MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { datasetsApi } from '@/api/endpoints/datasets'
import { modelsApi } from '@/api/endpoints/models'
import { endpointsApi } from '@/api/endpoints/endpoints'
import { useDataEndpointCreation } from '@/composables/useDataEndpointCreation'
import type { DatasetListItem, ModelListItem } from '@/api/types'

const router = useRouter()

// Data endpoint creation composable
const { isCreating, creationError, creationStep, createDataEndpointWithData, reset } =
  useDataEndpointCreation()

// Sub-step navigation
const currentSubStep = ref(1)

// Track completed steps - only allow navigation to completed steps
const completedSteps = ref<Set<number>>(new Set())

// Progressive disclosure
const showAdvancedDetails = ref(false)

// AI Provider selection
const selectedAiProvider = ref<'openai-gpt-4o' | 'openrouter-claude' | 'groq-llama' | ''>('')
const apiKeys = ref<Record<string, string>>({
  'openai-gpt-4o': '',
  'openrouter-claude': '',
  'groq-llama': '',
})

// Tag input
const tagInput = ref('')

// Track user input for validation timing
const hasTypedEndpointName = ref(false)

// Name validation state
const isCheckingNameAvailability = ref(false)
const nameAvailabilityResult = ref<'available' | 'taken' | null>(null)
const nameCheckDebounceTimer = ref<number | null>(null)

// Popular tag suggestions
const popularTags = ['legal', 'medical', 'research', 'finance', 'education', 'news', 'technical']

// Description template inspired by Kaggle data cards
const defaultDescriptionTemplate = `## Dataset Overview
Brief summary of what this dataset contains and its primary purpose...

## Content Description
- **Data types**: Text, images, numerical data, etc.
- **Size**: Number of records, files, or approximate volume
- **Format**: CSV, JSON, PDF, etc.
- **Languages**: If applicable

## Data Collection
- **Source**: Where this data originated
- **Collection method**: How it was gathered
- **Time period**: Coverage dates or collection timeframe
- **Update frequency**: How often this is refreshed

## Potential Use Cases
- Research applications
- Business intelligence
- Educational purposes
- Other specific applications

## Data Quality & Limitations
- **Completeness**: Any missing data or gaps
- **Accuracy**: Known issues or validation status  
- **Biases**: Potential limitations or skews
- **Ethical considerations**: Privacy, consent, fairness

## Citation & Attribution
How to properly cite or credit this dataset when used...`

// Policy configurations
type PolicyTypeId = 'access' | 'rate_limit' | 'pricing'

interface PolicyConfig {
  id: string
  [key: string]: string | number
}

interface PolicyRule {
  id: string
  config: PolicyConfig
  isEditing: boolean
}

interface PolicyType {
  id: PolicyTypeId
  name: string
  label: string
  description: string
  icon: typeof Shield | typeof Gauge | typeof DollarSign | typeof UserCheck
  color: string
}

type PolicyRulesRecord = Record<PolicyTypeId, PolicyRule[]>

const policyRules = ref<PolicyRulesRecord>({
  access: [],
  rate_limit: [],
  pricing: [],
})

// Currently editing rule ID for each policy type
const editingRuleId = ref<Record<PolicyTypeId, string | null>>({
  access: null,
  rate_limit: null,
  pricing: null,
})

// Check if any rule form is currently open
const isAnyRuleFormOpen = computed(() => {
  return Object.values(editingRuleId.value).some((id) => id !== null)
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

// Policy types definition
const policyTypes: PolicyType[] = [
  {
    id: 'access',
    name: 'Authorization',
    label: 'Who can access?',
    description: 'Control who can use your content - everyone, specific users, or by invitation',
    icon: Shield,
    color: 'blue',
  },
  {
    id: 'rate_limit',
    name: 'Rate Limiter',
    label: 'Prevent overuse',
    description: 'Limit how many queries each user can make per day or hour',
    icon: Gauge,
    color: 'green',
  },
  {
    id: 'pricing',
    name: 'Pricing',
    label: 'Set your price',
    description: 'Charge per query or make it free - you decide',
    icon: DollarSign,
    color: 'yellow',
  },
]

// Step titles and descriptions
const stepTitles = [
  'What do you want to share?',
  'How should it work?',
  'Who can access it?',
  'Tell us more about it',
  '',
]

const stepDescriptions = computed(() => [
  existingDataSourcesCount.value > 0
    ? 'Add files or connect to your existing database'
    : 'Browse and select the files you want to share. You can select multiple files and add descriptions for each one.',
  'Decide the format of the response users can receive from this content. Search provides most accuracy, while AI assistant answers are more nuanced.',
  'Control who can access your content and whether to charge for it',
  "Give your content a name and description so others know what you're sharing",
  '',
])

// Form data
const formData = ref({
  endpointName: '',
  summary: '',
  description: '',
  tags: [] as string[],
  selectedDataSource: '', // For existing dataset selection
  responseType: '', // No default selection
  aiModel: '', // Will be set when user selects a model
})

// Data source selection
const selectedDataSourceType = ref<'filesystem' | 'existing' | ''>('')
const selectedFiles = ref<string[]>([]) // Start with empty selection for FileExplorer
const fileDescriptions = ref({} as Record<string, string>)
const existingDatasets = ref<DatasetListItem[]>([])
const loadingDatasets = ref(false)
const datasetsError = ref<string | null>(null)

// Models state
const availableModels = ref<ModelListItem[]>([])

// Computed properties for dataset display
const existingDataSourcesCount = computed(() => existingDatasets.value.length)
const displayedDatasets = computed(() => {
  // If we have more than 3 datasets, show only 2 so we can add "...and X more" as the 3rd line
  const maxToShow = existingDatasets.value.length > 3 ? 2 : 3
  return existingDatasets.value.slice(0, maxToShow)
})
const remainingDatasetsCount = computed(() => {
  // If we have more than 3 datasets, remaining count is based on showing only 2
  return existingDatasets.value.length > 3 ? existingDatasets.value.length - 2 : 0
})

const selectedDatasetName = computed(() => {
  if (selectedDataSourceType.value === 'existing' && formData.value.selectedDataSource) {
    const dataset = existingDatasets.value.find((d) => d.id === formData.value.selectedDataSource)
    return dataset?.name || formData.value.selectedDataSource
  }
  return ''
})

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
    await endpointsApi.get(name)
    // If we get here, the endpoint exists, so the name is taken
    nameAvailabilityResult.value = 'taken'
  } catch (error) {
    // If we get a 404, the name is available
    if (
      error &&
      typeof error === 'object' &&
      'response' in error &&
      (error as { response?: { status?: number } }).response?.status === 404
    ) {
      nameAvailabilityResult.value = 'available'
    } else {
      // Other errors, reset the state
      nameAvailabilityResult.value = null
      console.error('Error checking name availability:', error)
    }
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
    if (selectedDataSourceType.value === 'filesystem') {
      return selectedFiles.value.length > 0
    } else if (selectedDataSourceType.value === 'existing') {
      return formData.value.selectedDataSource !== ''
    }
    return selectedDataSourceType.value !== ''
  }
  if (currentSubStep.value === 2) {
    if (formData.value.responseType === '') {
      return false
    }
    // If AI response is needed, require a model selection
    if (formData.value.responseType === 'summary' || formData.value.responseType === 'both') {
      return formData.value.aiModel !== ''
    }
    return true
  }
  if (currentSubStep.value === 3) {
    return true // Access rules are optional
  }
  if (currentSubStep.value === 4) {
    const slug = formData.value.endpointName.trim()
    const basicFieldsValid =
      slug !== '' &&
      isValidSlug(slug) &&
      formData.value.summary.trim() !== '' &&
      nameAvailabilityResult.value === 'available' &&
      !isCheckingNameAvailability.value

    return basicFieldsValid
  }
  if (currentSubStep.value === 5) {
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

// AI Provider methods
const selectAiProvider = (providerModel: 'openai-gpt-4o' | 'openrouter-claude' | 'groq-llama') => {
  selectedAiProvider.value = providerModel

  // Set the AI model configuration based on provider/model combination
  if (providerModel === 'openai-gpt-4o') {
    // Store provider info and model for creating the model later
    formData.value.aiModel = `${providerModel}-${Date.now()}` // Unique model name
  } else if (providerModel === 'openrouter-claude') {
    formData.value.aiModel = `${providerModel}-${Date.now()}`
  } else if (providerModel === 'groq-llama') {
    formData.value.aiModel = `${providerModel}-${Date.now()}`
  }
}

const getProviderName = (providerModel: string) => {
  switch (providerModel) {
    case 'openai-gpt-4o':
      return 'OpenAI'
    case 'openrouter-claude':
      return 'OpenRouter'
    case 'groq-llama':
      return 'Groq'
    default:
      return providerModel
  }
}

const getProviderApiUrl = (providerModel: string) => {
  switch (providerModel) {
    case 'openai-gpt-4o':
      return 'https://platform.openai.com/api-keys'
    case 'openrouter-claude':
      return 'https://openrouter.ai/keys'
    case 'groq-llama':
      return 'https://console.groq.com/keys'
    default:
      return '#'
  }
}

const selectDataSourceType = (type: 'filesystem' | 'existing') => {
  selectedDataSourceType.value = type
}

const nextStep = async () => {
  if (isCurrentStepValid.value && currentSubStep.value < 5) {
    // Mark current step as completed when moving to the next step
    completedSteps.value.add(currentSubStep.value)
    currentSubStep.value++
  } else if (currentSubStep.value === 5) {
    // Publish the endpoint using the composable
    const endpointData = {
      selectedDataSourceType: selectedDataSourceType.value,
      selectedFiles: selectedFiles.value,
      fileDescriptions: fileDescriptions.value,
      selectedDataSource: formData.value.selectedDataSource,
      responseType: formData.value.responseType,
      aiModel: formData.value.aiModel,
      selectedAiProvider: selectedAiProvider.value,
      apiKeys: apiKeys.value,
      policyRules: policyRules.value,
      endpointName: formData.value.endpointName,
      summary: formData.value.summary,
      description: formData.value.description,
      tags: formData.value.tags,
    }

    await createDataEndpointWithData(endpointData)
  }
}

const previousStep = () => {
  if (currentSubStep.value > 1) {
    // Clear creation errors when navigating away from step 5
    if (currentSubStep.value === 5) {
      reset()
    }
    currentSubStep.value--
  }
}

// Select response type
const selectResponseType = (type: 'raw' | 'summary' | 'both') => {
  formData.value.responseType = type

  if (type === 'raw') {
    formData.value.aiModel = ''
    selectedAiProvider.value = ''
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

// Remove file
const removeFile = (index: number) => {
  const file = selectedFiles.value[index]
  selectedFiles.value.splice(index, 1)
  // Also remove the description
  if (file && fileDescriptions.value[file]) {
    delete fileDescriptions.value[file]
  }
}

// Navigate to a specific step (only if it's completed, current, or next available step)
const navigateToStep = (targetStep: number) => {
  // Allow navigation to completed steps, current step, or the next step after the highest completed step
  const highestCompletedStep = Math.max(0, ...Array.from(completedSteps.value))
  const allowedStep = targetStep <= Math.max(highestCompletedStep + 1, currentSubStep.value)

  if (allowedStep) {
    currentSubStep.value = targetStep

    // Clear creation errors when navigating away from step 5
    if (targetStep !== 5) {
      reset()
    }
  }
}

// Check if a step is clickable (completed, current, or next available step)
const isStepClickable = (stepNumber: number) => {
  const highestCompletedStep = Math.max(0, ...Array.from(completedSteps.value))
  return stepNumber <= Math.max(highestCompletedStep + 1, currentSubStep.value)
}

// Generate rule summary based on policy type and configuration
const getRuleSummary = (policyId: PolicyTypeId, config: PolicyConfig): string => {
  switch (policyId) {
    case 'access':
      if (!config.users) return 'No users configured'
      const ruleType = config.ruleType === 'allow' ? 'Allow' : 'Deny'
      const userList = (config.users as string)
        .split(',')
        .map((u) => u.trim())
        .filter((u) => u)
      if (userList.length === 0) {
        return 'No users configured'
      }
      // Show all patterns
      return `${ruleType} access for ${userList.join(', ')}`

    case 'rate_limit':
      if (!config.limit) return 'No limit configured'
      const scope = config.scope === 'global' ? 'for this endpoint' : 'per user'
      return `${config.limit} requests per ${config.windowUnit} ${scope}`

    case 'pricing':
      if (config.price === undefined || config.price === null || config.price === '')
        return 'No price configured'
      const price = parseFloat(config.price as string)

      // Check for invalid number
      if (isNaN(price)) return 'Invalid price configured'

      // Handle free pricing
      if (price === 0) {
        if (config.userType === 'all') {
          return 'Free for all users'
        } else {
          const userList = config.users
            ? (config.users as string)
                .split(',')
                .map((u) => u.trim())
                .filter((u) => u)
            : []
          if (userList.length === 0) {
            return 'Free for specific users (none configured)'
          }
          return `Free for ${userList.join(', ')}`
        }
      }

      // Handle paid pricing
      // Format price dynamically, showing up to 8 decimal places with trailing zeros removed
      const formattedPrice = price.toFixed(8).replace(/\.?0+$/, '')
      if (config.userType === 'all') {
        return `$${formattedPrice} per query for all users`
      } else {
        const userList = config.users
          ? (config.users as string)
              .split(',')
              .map((u) => u.trim())
              .filter((u) => u)
          : []
        if (userList.length === 0) {
          return `$${formattedPrice} per query for specific users (none configured)`
        }
        return `$${formattedPrice} per query for ${userList.join(', ')}`
      }

    default:
      return 'Rule configured'
  }
}

// Fill example data
const fillExampleData = (exampleType: 'news' | 'research' | 'library') => {
  hasTypedEndpointName.value = true // Mark as user input for validation

  switch (exampleType) {
    case 'news':
      formData.value.endpointName = 'herald-tribune-archives'
      formData.value.summary = 'Historical news articles from 2010-2024'
      formData.value.tags = ['news', 'journalism', 'politics', 'business', 'local-news']
      break

    case 'research':
      formData.value.endpointName = 'cancer-research-publications'
      formData.value.summary = 'Peer-reviewed cancer research papers and clinical studies'
      formData.value.tags = ['research', 'medical', 'oncology', 'clinical-trials', 'peer-reviewed']
      break

    case 'library':
      formData.value.endpointName = 'technical-manuals-collection'
      formData.value.summary = 'Product guides and technical documentation'
      formData.value.tags = ['documentation', 'technical', 'manuals', 'api', 'guides']
      break
  }

  // Trigger name availability check for the filled name
  const name = formData.value.endpointName
  if (name && isValidSlug(name)) {
    debouncedCheckNameAvailability(name)
  }
}

// Policy helper functions
const generateRuleId = () => {
  return 'rule_' + Math.random().toString(36).substr(2, 9)
}

const addPolicy = (policyId: PolicyTypeId) => {
  const ruleId = generateRuleId()
  editingRuleId.value[policyId] = ruleId

  // Reset form data
  resetFormData(policyId)

  // Add new rule in editing state
  policyRules.value[policyId].push({
    id: ruleId,
    config: {} as PolicyConfig,
    isEditing: true,
  })
}

const editPolicy = (policyId: PolicyTypeId, ruleId: string) => {
  // Set other rules to not editing
  policyRules.value[policyId].forEach((rule) => {
    rule.isEditing = rule.id === ruleId
  })

  editingRuleId.value[policyId] = ruleId

  // Load rule data into form
  const rule = policyRules.value[policyId].find((r) => r.id === ruleId)
  if (rule) {
    loadRuleIntoForm(policyId, rule.config)
  }
}

const deletePolicy = (policyId: PolicyTypeId, ruleId: string) => {
  // Remove rule from array
  const index = policyRules.value[policyId].findIndex((r) => r.id === ruleId)
  if (index > -1) {
    policyRules.value[policyId].splice(index, 1)
  }

  // Clear editing state if this rule was being edited
  if (editingRuleId.value[policyId] === ruleId) {
    editingRuleId.value[policyId] = null
  }
}

const resetFormData = (policyId: PolicyTypeId) => {
  switch (policyId) {
    case 'access':
      authorizationForm.value = { ruleType: 'allow', users: '', note: '' }
      break
    case 'rate_limit':
      rateLimiterForm.value = {
        limit: '',
        windowUnit: 'minute',
        scope: 'per user',
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
  }
}

const loadRuleIntoForm = (policyId: PolicyTypeId, config: PolicyConfig) => {
  switch (policyId) {
    case 'access':
      authorizationForm.value = {
        ruleType: (config.ruleType as string) || 'allow',
        users: (config.users as string) || '',
        note: (config.note as string) || '',
      }
      break
    case 'rate_limit':
      rateLimiterForm.value = {
        limit: (config.limit as string) || '',
        windowUnit: (config.windowUnit as string) || 'minute',
        scope: (config.scope as string) || 'per user',
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
  }
}

const savePolicy = (policyId: PolicyTypeId, ruleId: string) => {
  const rule = policyRules.value[policyId].find((r) => r.id === ruleId)
  if (!rule) return

  // Get the form data based on policy type
  let formData
  switch (policyId) {
    case 'access':
      formData = authorizationForm.value
      break
    case 'rate_limit':
      formData = { ...rateLimiterForm.value }
      break
    case 'pricing':
      formData = { ...pricingForm.value, pricingType: 'per_call' }
      break
    default:
      return
  }

  // Save form data to rule config
  rule.config = { ...formData, id: ruleId }
  rule.isEditing = false

  // Clear editing state
  editingRuleId.value[policyId] = null
}

const cancelEditPolicy = (policyId: PolicyTypeId, ruleId: string) => {
  const ruleIndex = policyRules.value[policyId].findIndex((r) => r.id === ruleId)
  if (ruleIndex === -1) return

  const rule = policyRules.value[policyId][ruleIndex]
  if (!rule) return

  // If this is a new rule being created, remove it
  if (Object.keys(rule.config).length === 0) {
    policyRules.value[policyId].splice(ruleIndex, 1)
  } else {
    // Otherwise, just exit edit mode
    rule.isEditing = false
  }

  // Clear editing state
  editingRuleId.value[policyId] = null
}

// Handle Step 3 Create Model (placeholder)
const handleStep3CreateModel = () => {
  console.log('Create model dialog would open here')
}

const refreshForm = () => {
  // Form refresh function for error boundary retry
  console.log('Refreshing form...')
}

// Load existing datasets
const loadExistingDatasets = async () => {
  loadingDatasets.value = true
  datasetsError.value = null

  try {
    const datasets = await datasetsApi.list()
    existingDatasets.value = datasets
  } catch (error) {
    console.error('Failed to load existing datasets:', error)
    datasetsError.value = error instanceof Error ? error.message : 'Failed to load datasets'
    existingDatasets.value = []
  } finally {
    loadingDatasets.value = false
  }
}

// Load available models
const loadAvailableModels = async () => {
  try {
    const models = await modelsApi.list()
    availableModels.value = models
  } catch (error) {
    console.error('Failed to load available models:', error)
  }
}

// Get model name by ID
const getModelName = (modelId: string): string | null => {
  const model = availableModels.value.find((m) => m.id === modelId)
  return model?.name || null
}

// Get display name for AI model (handles both quick setup and existing models)
const getModelDisplayName = (): string => {
  // If a quick setup provider is selected, show the provider/model combination
  if (selectedAiProvider.value) {
    switch (selectedAiProvider.value) {
      case 'openai-gpt-4o':
        return 'openai/gpt-4o'
      case 'openrouter-claude':
        return 'openrouter/claude-3.5-sonnet'
      case 'groq-llama':
        return 'groq/llama-3.3-70b-instruct'
      default:
        return selectedAiProvider.value
    }
  }

  // Fall back to existing model name or model ID
  return getModelName(formData.value.aiModel) || formData.value.aiModel || 'Not selected'
}

// Load datasets and models when component mounts
onMounted(async () => {
  await Promise.all([loadExistingDatasets(), loadAvailableModels()])

  // Auto-select filesystem if no existing datasets are available
  if (existingDataSourcesCount.value === 0 && !selectedDataSourceType.value) {
    selectedDataSourceType.value = 'filesystem'
  }
})

// Cleanup debounce timer when component unmounts
onUnmounted(() => {
  if (nameCheckDebounceTimer.value) {
    clearTimeout(nameCheckDebounceTimer.value)
  }
})

// Helper functions for dataset status display
const getStatusText = (status: string | undefined): string => {
  if (!status) return 'unknown'
  return status.toLowerCase()
}

const getStatusBadgeClasses = (status: string | undefined): string => {
  if (!status) return 'bg-muted text-muted-foreground border-muted'

  switch (status.toLowerCase()) {
    case 'running':
    case 'ready':
    case 'active':
      return 'bg-green-50 text-green-700 border-green-200'
    case 'stopped':
    case 'inactive':
      return 'bg-red-50 text-red-700 border-red-200'
    case 'starting':
    case 'loading':
      return 'bg-yellow-50 text-yellow-700 border-yellow-200'
    case 'error':
    case 'failed':
      return 'bg-red-50 text-red-700 border-red-200'
    default:
      return 'bg-muted text-muted-foreground border-muted'
  }
}

const isDatasetSelectable = (dataset: DatasetListItem): boolean => {
  const status = dataset.provisioner_status?.status?.toLowerCase()
  // Allow selection if no status (assume ready) or if status indicates it's ready/running
  return !status || ['running', 'ready', 'active'].includes(status)
}
</script>
