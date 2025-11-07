<!-- eslint-disable vue/no-parsing-error -->
<template>
  <ErrorBoundary
    :can-retry="true"
    :show-details="true"
    custom-title="Endpoint Creation Error"
    custom-message="There was a problem with the endpoint creation form. Please try again."
    @retry="refreshForm"
  >
    <div class="min-h-screen bg-muted/50">
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

      <!-- Two-column layout -->
      <div class="flex gap-12 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
        <!-- Left sidebar with steps -->
        <div class="w-80 flex-shrink-0">
          <div class="sticky top-8">
            <h2 class="heading-3 text-foreground mb-6">Setup Progress</h2>

            <!-- Vertical step list -->
            <div class="space-y-6">
              <!-- Step 1 -->
              <div class="flex items-start gap-4">
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium body-sm transition-all',
                    currentSubStep >= 1
                      ? 'bg-primary text-white'
                      : 'bg-muted text-muted-foreground',
                  ]"
                >
                  {{ currentSubStep > 1 ? '✓' : '1' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium body-sm',
                      currentSubStep >= 1 ? 'text-foreground' : 'text-muted-foreground',
                    ]"
                  >
                    What do you want to share?
                  </h3>
                  <p class="body-sm text-muted-foreground mt-1">Add files or connect database</p>
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
              <div class="flex items-start gap-4">
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium body-sm transition-all',
                    currentSubStep >= 2
                      ? 'bg-primary text-white'
                      : 'bg-muted text-muted-foreground',
                  ]"
                >
                  {{ currentSubStep > 2 ? '✓' : '2' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium body-sm',
                      currentSubStep >= 2 ? 'text-foreground' : 'text-muted-foreground',
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
              <div class="flex items-start gap-4">
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium body-sm transition-all',
                    currentSubStep >= 3
                      ? 'bg-primary text-white'
                      : 'bg-muted text-muted-foreground',
                  ]"
                >
                  {{ currentSubStep > 3 ? '✓' : '3' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium body-sm',
                      currentSubStep >= 3 ? 'text-foreground' : 'text-muted-foreground',
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
              <div class="flex items-start gap-4">
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium body-sm transition-all',
                    currentSubStep >= 4
                      ? 'bg-primary text-white'
                      : 'bg-muted text-muted-foreground',
                  ]"
                >
                  {{ currentSubStep > 4 ? '✓' : '4' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium body-sm',
                      currentSubStep >= 4 ? 'text-foreground' : 'text-muted-foreground',
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
              <div class="flex items-start gap-4">
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium body-sm transition-all',
                    currentSubStep >= 5
                      ? 'bg-primary text-white'
                      : 'bg-muted text-muted-foreground',
                  ]"
                >
                  {{ currentSubStep > 5 ? '✓' : '5' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium body-sm',
                      currentSubStep >= 5 ? 'text-foreground' : 'text-muted-foreground',
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
            <!-- Data source selection cards -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
                <CardContent class="p-6">
                  <div class="flex flex-col items-center text-center">
                    <div
                      class="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center mb-4"
                    >
                      <FileText class="w-7 h-7 text-primary" />
                    </div>

                    <h3 class="heading-3 text-foreground mb-2">Add Files</h3>
                    <p class="body-sm text-muted-foreground mb-4">
                      Add documents, spreadsheets, or text files from your computer
                    </p>

                    <div class="space-y-2 body-sm text-muted-foreground mb-4">
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

                    <div class="flex items-center gap-1">
                      <span
                        class="body-sm bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium"
                        >Easy</span
                      >
                      <span class="body-sm text-muted-foreground">2 minute setup</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <!-- Existing Sources Card -->
              <Card
                :class="[
                  'transition-all duration-200 border-2',
                  existingDataSourcesCount > 0
                    ? 'cursor-pointer hover:shadow-lg hover:border-green-300 hover:bg-gradient-to-br hover:from-green-50 hover:to-emerald-50 bg-card'
                    : 'cursor-not-allowed opacity-60 bg-muted/50',
                  selectedDataSourceType === 'existing'
                    ? 'border-green-500 bg-gradient-to-br from-green-50 to-emerald-50'
                    : existingDataSourcesCount > 0
                      ? 'border-border'
                      : 'border-border/50',
                ]"
                @click="existingDataSourcesCount > 0 ? selectDataSourceType('existing') : null"
              >
                <CardContent class="p-6">
                  <div class="flex flex-col items-center text-center">
                    <div
                      class="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center mb-4"
                    >
                      <FolderOpen class="w-7 h-7 text-green-600" />
                    </div>

                    <h3 class="heading-3 text-foreground mb-2">Existing Sources</h3>
                    <p class="body-sm text-muted-foreground mb-4">
                      Choose from data you've already connected
                    </p>

                    <div v-if="existingDataSourcesCount > 0" class="space-y-2 mb-4">
                      <div class="flex items-center gap-2 body-sm">
                        <div class="w-2 h-2 bg-primary/100 rounded-full"></div>
                        <span class="text-muted-foreground">Legal Documents Store</span>
                      </div>
                      <div class="flex items-center gap-2 body-sm">
                        <div class="w-2 h-2 bg-green-500 rounded-full"></div>
                        <span class="text-muted-foreground">Research Papers Collection</span>
                      </div>
                      <div
                        v-if="existingDataSourcesCount > 2"
                        class="body-sm text-muted-foreground"
                      >
                        +{{ existingDataSourcesCount - 2 }} more sources...
                      </div>
                    </div>

                    <div v-else class="mb-4 body-sm text-muted-foreground">
                      No existing data sources found
                    </div>

                    <div class="flex items-center gap-1">
                      <span
                        :class="
                          existingDataSourcesCount > 0
                            ? 'body-sm bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium'
                            : 'body-sm bg-muted text-muted-foreground px-2 py-1 rounded-full'
                        "
                      >
                        {{ existingDataSourcesCount > 0 ? 'Quick' : 'None available' }}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <!-- Advanced Options (Collapsible) -->
            <div class="border border-border rounded-lg bg-card">
              <button
                @click="showAdvancedDataSource = !showAdvancedDataSource"
                class="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-muted/50 transition-colors"
              >
                >
                <div>
                  <h4 class="font-medium text-foreground flex items-center gap-2">
                    <Settings class="w-5 h-5 text-muted-foreground" />
                    Advanced
                  </h4>
                  <p class="body-sm text-muted-foreground mt-1">
                    Connect to external databases and vector stores
                  </p>
                </div>
                <ChevronRight
                  :class="[
                    'w-5 h-5 text-muted-foreground transition-transform',
                    showAdvancedDataSource ? 'rotate-90' : '',
                  ]"
                />
              </button>

              <div
                v-if="showAdvancedDataSource"
                class="px-6 pb-6 border-t border-border bg-muted/50"
              >
                <div class="pt-4">
                  <!-- Bring Your Own VectorDB Card -->
                  <Card
                    :class="[
                      'transition-all duration-200 border-2 cursor-pointer',
                      selectedDataSourceType === 'vector'
                        ? 'border-yellow-500 bg-gradient-to-br from-yellow-50 to-amber-50'
                        : 'border-border bg-card hover:shadow-lg hover:border-yellow-300 hover:bg-gradient-to-br hover:from-yellow-50 hover:to-amber-50',
                    ]"
                    @click="toggleVectorDBOptions"
                  >
                    <CardContent class="p-6">
                      <div class="flex items-center justify-between">
                        <div class="flex items-start gap-4">
                          <div
                            class="w-12 h-12 rounded-full bg-yellow-100 flex items-center justify-center flex-shrink-0"
                          >
                            <Database class="w-6 h-6 text-yellow-600" />
                          </div>
                          <div class="flex-1">
                            <h4 class="font-medium text-foreground mb-2">Connect Database</h4>
                            <p class="body-sm text-muted-foreground">
                              Connect to an existing vector database or service
                            </p>

                            <div class="flex items-center gap-1 mt-3">
                              <span
                                class="body-sm bg-orange-100 text-orange-700 px-2 py-1 rounded-full font-medium"
                                >Advanced</span
                              >
                              <span class="body-sm text-muted-foreground"
                                >Requires technical setup</span
                              >
                            </div>
                          </div>
                        </div>
                        <ChevronRight
                          :class="[
                            'w-5 h-5 text-muted-foreground transition-transform',
                            showVectorDBOptions ? 'rotate-90' : '',
                          ]"
                        />
                      </div>
                    </CardContent>
                  </Card>

                  <!-- Vector DB Options (shown when Bring Your Own VectorDB is selected) -->
                  <div v-if="showVectorDBOptions" class="mt-4 space-y-4">
                    <div class="space-y-2">
                      <Label class="body-sm font-medium text-foreground">
                        Choose Database Type <span class="text-red-500">*</span>
                      </Label>
                      <div class="grid grid-cols-2 gap-3 md:grid-cols-3">
                        <!-- Weaviate -->
                        <div
                          @click="selectVectorDB('weaviate')"
                          :class="[
                            'cursor-pointer transition-all duration-200 border rounded-lg p-4 text-center',
                            selectedVectorDB === 'weaviate'
                              ? 'border-purple-500 bg-purple-50'
                              : 'border-border hover:border-border/80 hover:bg-muted/50',
                          ]"
                        >
                          <div class="w-8 h-8 mx-auto mb-2 flex items-center justify-center">
                            <Database
                              :class="[
                                'h-8 w-8',
                                selectedVectorDB === 'weaviate'
                                  ? 'text-purple-600'
                                  : 'text-muted-foreground',
                              ]"
                            />
                          </div>
                          <span
                            :class="[
                              'body-sm font-medium',
                              selectedVectorDB === 'weaviate'
                                ? 'text-purple-900'
                                : 'text-foreground',
                            ]"
                          >
                            Weaviate
                          </span>
                        </div>

                        <!-- Qdrant -->
                        <div
                          @click="selectVectorDB('qdrant')"
                          :class="[
                            'cursor-pointer transition-all duration-200 border rounded-lg p-4 text-center',
                            selectedVectorDB === 'qdrant'
                              ? 'border-blue-500 bg-primary/10'
                              : 'border-border hover:border-border/80 hover:bg-muted/50',
                          ]"
                        >
                          <div class="w-8 h-8 mx-auto mb-2 flex items-center justify-center">
                            <Database
                              :class="[
                                'h-8 w-8',
                                selectedVectorDB === 'qdrant'
                                  ? 'text-primary'
                                  : 'text-muted-foreground',
                              ]"
                            />
                          </div>
                          <span
                            :class="[
                              'body-sm font-medium',
                              selectedVectorDB === 'qdrant' ? 'text-blue-900' : 'text-foreground',
                            ]"
                          >
                            Qdrant
                          </span>
                        </div>

                        <!-- Chroma -->
                        <div
                          @click="selectVectorDB('chroma')"
                          :class="[
                            'cursor-pointer transition-all duration-200 border rounded-lg p-4 text-center',
                            selectedVectorDB === 'chroma'
                              ? 'border-green-500 bg-green-50'
                              : 'border-border hover:border-border/80 hover:bg-muted/50',
                          ]"
                        >
                          <div class="w-8 h-8 mx-auto mb-2 flex items-center justify-center">
                            <Database
                              :class="[
                                'h-8 w-8',
                                selectedVectorDB === 'chroma'
                                  ? 'text-green-600'
                                  : 'text-muted-foreground',
                              ]"
                            />
                          </div>
                          <span
                            :class="[
                              'body-sm font-medium',
                              selectedVectorDB === 'chroma' ? 'text-green-900' : 'text-foreground',
                            ]"
                          >
                            Chroma
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
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
                  Selected Files ({{ selectedFiles.length }})
                </h4>
                <div class="space-y-2">
                  <Card v-for="file in selectedFiles" :key="file" class="bg-muted/50 border-border">
                    <CardContent class="p-4">
                      <div class="flex items-start gap-3">
                        <FileText class="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                        <div class="min-w-0 flex-1 space-y-1">
                          <p class="body-sm font-medium text-foreground truncate">{{ file }}</p>
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
                        <FileType class="w-6 h-6 text-primary" />
                      </div>

                      <h3 class="heading-3 text-foreground mb-2">Search & Quote</h3>
                      <p class="body-sm font-medium mb-3 text-primary">Return exact text matches</p>

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

              <!-- Advanced AI Model Selection (collapsible) -->
              <div
                v-if="formData.responseType === 'summary' || formData.responseType === 'both'"
                class="bg-card rounded-lg shadow-sm border border-border"
              >
                <button
                  @click="showAdvancedOptions = !showAdvancedOptions"
                  class="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-muted/50"
                >
                  <div>
                    <h4 class="font-medium text-foreground">Advanced - Choose Local AI Model</h4>
                    <p class="body-sm text-muted-foreground mt-1">
                      Customize AI settings and model selection
                    </p>
                  </div>
                  <ChevronRight
                    :class="[
                      'w-5 h-5 text-muted-foreground transition-transform',
                      showAdvancedOptions ? 'rotate-90' : '',
                    ]"
                  />
                </button>

                <div v-if="showAdvancedOptions" class="px-6 pb-6 border-t border-border">
                  <div class="pt-4">
                    <ModelSelector
                      v-model="formData.aiModel"
                      title="AI Model"
                      description="Ollama is pre-selected for local, private AI processing"
                      id-prefix="step2-advanced"
                      @create-model="handleStep3CreateModel"
                    />
                  </div>
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
                      <span v-if="policy.id === 'authorization'"
                        >Open access - everyone can use your endpoint</span
                      >
                      <span v-else-if="policy.id === 'ratelimiter'"
                        >No rate limits - unlimited usage</span
                      >
                      <span v-else-if="policy.id === 'pricing'"
                        >Free access - no charges applied</span
                      >
                      <span v-else-if="policy.id === 'manual-approval'"
                        >Automatic approval - no manual review required</span
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
                    v-for="rule in policyRules[policy.id] || []"
                    :key="rule.id"
                    class="bg-muted/50/30 border border-border/50/50 rounded-xl p-4"
                  >
                    <!-- Rule in Edit Mode (Expanded) -->
                    <div v-if="rule.isEditing" class="space-y-3">
                      <!-- Authorization Policy Form -->
                      <div v-if="policy.id === 'authorization'">
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
                        </div>
                      </div>

                      <!-- Rate Limiter Policy Form -->
                      <div v-if="policy.id === 'ratelimiter'">
                        <div class="grid grid-cols-3 gap-3 mb-3">
                          <div class="space-y-1">
                            <Label class="body-sm text-muted-foreground font-medium">Limit</Label>
                            <Input
                              v-model="rateLimiterForm.limit"
                              type="number"
                              placeholder="100"
                              class="h-9 rounded-lg border-border bg-card body-sm"
                            />
                          </div>
                          <div class="space-y-1">
                            <Label class="body-sm text-muted-foreground font-medium">Window</Label>
                            <Input
                              v-model="rateLimiterForm.windowValue"
                              type="number"
                              placeholder="1"
                              class="h-9 rounded-lg border-border bg-card body-sm"
                            />
                          </div>
                          <div class="space-y-1">
                            <Label class="body-sm text-muted-foreground font-medium">Unit</Label>
                            <Select v-model="rateLimiterForm.windowUnit">
                              <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="second">Second</SelectItem>
                                <SelectItem value="minute">Minute</SelectItem>
                                <SelectItem value="hour">Hour</SelectItem>
                                <SelectItem value="day">Day</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                          <div class="space-y-1">
                            <Label class="body-sm text-muted-foreground font-medium">Scope</Label>
                            <Select v-model="rateLimiterForm.scope">
                              <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="per user">Per User</SelectItem>
                                <SelectItem value="global">Global</SelectItem>
                              </SelectContent>
                            </Select>
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
                      </div>

                      <!-- Pricing Policy Form -->
                      <div v-if="policy.id === 'pricing'">
                        <div class="grid grid-cols-2 gap-3 mb-3">
                          <div class="space-y-1">
                            <Label class="body-sm text-muted-foreground font-medium">Type</Label>
                            <Select v-model="pricingForm.pricingType">
                              <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                                <SelectValue placeholder="Select type" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="per_call">Per Call</SelectItem>
                                <SelectItem value="per_token">Per Token</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div class="space-y-1">
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
                        </div>
                        <div
                          v-if="
                            pricingForm.pricingType === 'per_call' ||
                            pricingForm.pricingType === 'per_token'
                          "
                          class="mb-3"
                        >
                          <div class="space-y-1">
                            <Label class="body-sm text-muted-foreground font-medium"
                              >Price ($)</Label
                            >
                            <Input
                              v-model="pricingForm.price"
                              type="number"
                              step="0.01"
                              placeholder="0.01"
                              class="h-9 rounded-lg border-border bg-card body-sm"
                            />
                          </div>
                        </div>
                        <div class="grid grid-cols-1 gap-3">
                          <div v-if="pricingForm.userType === 'specific'" class="space-y-1">
                            <Label class="body-sm text-muted-foreground font-medium">Users</Label>
                            <Input
                              v-model="pricingForm.users"
                              placeholder="user1@example.com, user2@example.com"
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
                      </div>

                      <!-- Manual Approval Policy Form -->
                      <div v-if="policy.id === 'manual-approval'">
                        <div class="space-y-3">
                          <div class="space-y-1">
                            <Label class="body-sm text-muted-foreground font-medium"
                              >Apply To</Label
                            >
                            <Select v-model="manualApprovalForm.userType">
                              <SelectTrigger class="h-9 rounded-lg border-border bg-card body-sm">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="all">All Users</SelectItem>
                                <SelectItem value="specific">Specific Users</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div v-if="manualApprovalForm.userType === 'specific'" class="space-y-1">
                            <Label class="body-sm text-muted-foreground font-medium">Users</Label>
                            <Input
                              v-model="manualApprovalForm.users"
                              placeholder="user1@example.com, user2@example.com"
                              class="h-9 rounded-lg border-border bg-card body-sm"
                            />
                          </div>
                          <div class="space-y-1">
                            <Label class="body-sm text-muted-foreground font-medium">Note</Label>
                            <Input
                              v-model="manualApprovalForm.note"
                              placeholder="Optional description"
                              class="h-9 rounded-lg border-border bg-card body-sm"
                            />
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
                          {{ rule.config.note || `${policy.name} Rule` }}
                        </h4>
                        <p class="body-sm text-muted-foreground mt-1">Rule summary</p>
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
                <Input
                  id="endpoint-name"
                  v-model="formData.endpointName"
                  placeholder="e.g., herald-tribune-archives"
                  class="w-full font-mono body-sm"
                />
                <p class="body-sm text-muted-foreground">
                  This appears when people discover it. Keep it simple, no spaces
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
                  Topics & Categories (Optional)
                </Label>
                <div class="space-y-2">
                  <div class="flex gap-2">
                    <Input
                      id="tags"
                      v-model="tagInput"
                      @keydown.enter.prevent="addTag"
                      placeholder="Add keywords like: news, research, medical, finance, books"
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
                      <button @click="removeTag(index)" class="ml-2 hover:text-foreground">
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
                  >Watched Paths Descriptions <span class="text-red-500">*</span></Label
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
                        :class="[
                          'body-sm',
                          !fileDescriptions[file] || fileDescriptions[file].trim() === ''
                            ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                            : '',
                        ]"
                      />
                      <p
                        v-if="!fileDescriptions[file] || fileDescriptions[file].trim() === ''"
                        class="body-sm text-red-600 mt-1"
                      >
                        Description is required
                      </p>
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
                    :toolbars-exclude="['github']"
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
                        v-else-if="selectedDataSourceType === 'vector'"
                        class="flex items-center gap-2"
                      >
                        <Database class="w-4 h-4 text-purple-600" />
                        <span class="text-foreground">Vector Database</span>
                        <span v-if="selectedVectorDB" class="body-sm text-muted-foreground"
                          >({{
                            selectedVectorDB.charAt(0).toUpperCase() + selectedVectorDB.slice(1)
                          }})</span
                        >
                      </div>
                      <div
                        v-else-if="selectedDataSourceType === 'existing'"
                        class="flex items-center gap-2"
                      >
                        <Database class="w-4 h-4 text-green-600" />
                        <span class="text-foreground">Existing Source</span>
                      </div>
                      <span v-else class="text-muted-foreground italic">Not configured</span>
                    </div>
                  </div>
                </div>

                <div>
                  <p class="body-sm font-medium text-muted-foreground mb-2">Description</p>
                  <p class="text-foreground leading-relaxed">
                    {{ formData.summary || 'Not specified' }}
                  </p>
                </div>

                <div v-if="formData.tags.length > 0" class="mt-6">
                  <p class="body-sm font-medium text-muted-foreground mb-3">Tags</p>
                  <div class="flex flex-wrap gap-2">
                    <Badge
                      v-for="tag in formData.tags"
                      :key="tag"
                      variant="outline"
                      class="bg-primary/10 text-blue-700 border-blue-200 px-3 py-1"
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
                        formData.aiModel
                      }}</span>
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
                <div class="space-y-2">
                  <div v-for="policyType in policyTypes" :key="policyType.id">
                    <div
                      v-if="policyRules[policyType.id]?.length > 0"
                      class="bg-muted/50 rounded-lg p-3"
                    >
                      <div class="flex items-center gap-2">
                        <component :is="policyType.icon" class="w-4 h-4 text-muted-foreground" />
                        <span class="body-sm font-medium text-foreground">{{
                          policyType.name
                        }}</span>
                        <Badge variant="secondary" class="body-sm">
                          {{ policyRules[policyType.id].length }}
                          {{ policyRules[policyType.id].length === 1 ? 'rule' : 'rules' }}
                        </Badge>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Navigation Buttons -->
          <div class="flex justify-between mt-8 pt-6 border-t border-border">
            <Button variant="outline" @click="handleBack"> Cancel </Button>
            <Button
              @click="nextStep"
              :disabled="!isCurrentStepValid"
              class="bg-primary hover:bg-blue-700 text-white px-8"
            >
              {{ currentSubStep === 5 ? 'Publish Now' : 'Continue' }}
              <ArrowRight class="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  </ErrorBoundary>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  ArrowRight,
  Save,
  FileText,
  FolderOpen,
  Database,
  Settings,
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import FileExplorer from '@/components/FileExplorer.vue'
import ModelSelector from '@/components/ModelSelector.vue'
import { MdEditor } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'

const router = useRouter()

// Sub-step navigation
const currentSubStep = ref(1)

// Progressive disclosure
const showAdvancedDataSource = ref(false)
const showAdvancedOptions = ref(false)
const showVectorDBOptions = ref(false)
const showAdvancedDetails = ref(false)
const selectedVectorDB = ref('')

// Tag input
const tagInput = ref('')

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
type PolicyTypeId = 'authorization' | 'ratelimiter' | 'pricing' | 'manual-approval'

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
  authorization: [],
  ratelimiter: [],
  pricing: [],
  'manual-approval': [],
})

// Currently editing rule ID for each policy type
const editingRuleId = ref<Record<PolicyTypeId, string | null>>({
  authorization: null,
  ratelimiter: null,
  pricing: null,
  'manual-approval': null,
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
  userType: 'all',
  users: '',
  note: '',
})

// Policy types definition
const policyTypes: PolicyType[] = [
  {
    id: 'authorization',
    name: 'Authorization',
    label: 'Who can access?',
    description: 'Control who can use your content - everyone, specific users, or by invitation',
    icon: Shield,
    color: 'blue',
  },
  {
    id: 'ratelimiter',
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
  {
    id: 'manual-approval',
    name: 'Manual approval',
    label: 'Review each request',
    description: 'Approve or deny each query manually (recommended for sensitive data)',
    icon: UserCheck,
    color: 'purple',
  },
]

// Step titles and descriptions
const stepTitles = [
  'What do you want to share?',
  'How should it work?',
  'Who can access it?',
  'Tell us more about it',
  'Review & Publish',
]

const stepDescriptions = [
  'Add files or connect to your existing database',
  'Decide the format of the response users can receive from this content. Search provides most accuracy, while AI assistant answers are more nuanced.',
  'Control who can access your content and whether to charge for it',
  "Give your content a name and description so others know what you're sharing",
  'Final review and go live',
]

// Form data
const formData = ref({
  endpointName: '',
  summary: '',
  description: '',
  tags: [] as string[],
  selectedDataSource: '',
  responseType: 'both', // Default to Search + AI
  aiModel: 'code-assistant', // Default to the running Ollama model
})

// Data source selection
const selectedDataSourceType = ref('')
const selectedFiles = ref<string[]>([]) // Start with empty selection for FileExplorer
const fileDescriptions = ref({} as Record<string, string>)
const existingDataSourcesCount = ref(2) // Mock count

// Computed properties
const canSaveDraft = computed(() => formData.value.endpointName.trim().length > 0)

const isCurrentStepValid = computed(() => {
  if (currentSubStep.value === 1) {
    return (
      selectedDataSourceType.value !== '' &&
      (selectedDataSourceType.value !== 'filesystem' || selectedFiles.value.length > 0)
    )
  }
  if (currentSubStep.value === 2) {
    return formData.value.responseType !== ''
  }
  if (currentSubStep.value === 3) {
    return true // Access rules are optional
  }
  if (currentSubStep.value === 4) {
    const basicFieldsValid =
      formData.value.endpointName.trim() !== '' && formData.value.summary.trim() !== ''

    // If using filesystem, check that all selected files have descriptions
    if (selectedDataSourceType.value === 'filesystem' && selectedFiles.value.length > 0) {
      const allDescriptionsProvided = selectedFiles.value.every(
        (file) => fileDescriptions.value[file] && fileDescriptions.value[file].trim() !== '',
      )
      return basicFieldsValid && allDescriptionsProvided
    }

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

const saveDraft = () => {
  console.log('Saving draft...', formData.value)
  // Add save logic here
}

const selectDataSourceType = (type: string) => {
  selectedDataSourceType.value = type
}

// Vector DB selection functions
const toggleVectorDBOptions = () => {
  showVectorDBOptions.value = !showVectorDBOptions.value
  if (showVectorDBOptions.value) {
    selectedDataSourceType.value = 'vector'
  }
}

const selectVectorDB = (dbType: string) => {
  selectedVectorDB.value = dbType
  selectedDataSourceType.value = 'vector'
}

const nextStep = () => {
  if (isCurrentStepValid.value && currentSubStep.value < 5) {
    currentSubStep.value++
  } else if (currentSubStep.value === 5) {
    // Publish the endpoint
    router.push({ name: 'endpoints' })
  }
}

// Select response type
const selectResponseType = (type: 'raw' | 'summary' | 'both') => {
  formData.value.responseType = type
}

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

// Fill example data
const fillExampleData = (exampleType: 'news' | 'research' | 'library') => {
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
        userType: 'all',
        users: '',
        note: '',
      }
      break
  }
}

const loadRuleIntoForm = (policyId: PolicyTypeId, config: PolicyConfig) => {
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
        quantity: (config.quantity as string) || '1',
        userType: (config.userType as string) || 'all',
        users: (config.users as string) || '',
        note: (config.note as string) || '',
      }
      break
    case 'manual-approval':
      manualApprovalForm.value = {
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
    case 'authorization':
      formData = authorizationForm.value
      break
    case 'ratelimiter':
      formData = rateLimiterForm.value
      break
    case 'pricing':
      formData = pricingForm.value
      break
    case 'manual-approval':
      formData = manualApprovalForm.value
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
</script>
