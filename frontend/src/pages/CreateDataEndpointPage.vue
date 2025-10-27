<template>
  <ErrorBoundary
    :can-retry="true"
    :show-details="true"
    custom-title="Endpoint Creation Error"
    custom-message="There was a problem with the endpoint creation form. Please try again."
    @retry="refreshForm"
  >
    <div class="min-h-screen bg-gray-50">
      <!-- Header -->
      <div class="bg-white border-b border-gray-200">
        <div class="max-w-6xl mx-auto px-6 lg:px-8 py-4">
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

      <!-- Two-column layout -->
      <div class="flex gap-12 max-w-6xl mx-auto px-6 lg:px-8 py-8 lg:py-12">
        <!-- Left sidebar with steps -->
        <div class="w-80 flex-shrink-0">
          <div class="sticky top-8">
            <h2 class="text-lg font-semibold text-gray-900 mb-6">Setup Progress</h2>
            
            <!-- Vertical step list -->
            <div class="space-y-6">
              <!-- Step 1 -->
              <div class="flex items-start gap-4">
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium text-sm transition-all',
                    currentSubStep >= 1 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500',
                  ]"
                >
                  {{ currentSubStep > 1 ? '✓' : '1' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium text-sm',
                      currentSubStep >= 1 ? 'text-gray-900' : 'text-gray-500',
                    ]"
                  >
                    What do you want to share?
                  </h3>
                  <p class="text-xs text-gray-500 mt-1">Upload files or connect database</p>
                  <div
                    v-if="currentSubStep > 1"
                    class="mt-2 text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded"
                  >
                    ✓ Completed
                  </div>
                  <div
                    v-else-if="currentSubStep === 1"
                    class="mt-2 text-xs text-blue-600 font-medium"
                  >
                    Current step
                  </div>
                </div>
              </div>

              <!-- Step 2 -->
              <div class="flex items-start gap-4">
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium text-sm transition-all',
                    currentSubStep >= 2 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500',
                  ]"
                >
                  {{ currentSubStep > 2 ? '✓' : '2' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium text-sm',
                      currentSubStep >= 2 ? 'text-gray-900' : 'text-gray-500',
                    ]"
                  >
                    How should it work?
                  </h3>
                  <p class="text-xs text-gray-500 mt-1">Configure output and AI settings</p>
                  <div
                    v-if="currentSubStep > 2"
                    class="mt-2 text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded"
                  >
                    ✓ Completed
                  </div>
                  <div
                    v-else-if="currentSubStep === 2"
                    class="mt-2 text-xs text-blue-600 font-medium"
                  >
                    Current step
                  </div>
                </div>
              </div>

              <!-- Step 3 -->
              <div class="flex items-start gap-4">
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium text-sm transition-all',
                    currentSubStep >= 3 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500',
                  ]"
                >
                  {{ currentSubStep > 3 ? '✓' : '3' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium text-sm',
                      currentSubStep >= 3 ? 'text-gray-900' : 'text-gray-500',
                    ]"
                  >
                    Who can access it?
                  </h3>
                  <p class="text-xs text-gray-500 mt-1">Control who can use your content</p>
                  <div
                    v-if="currentSubStep > 3"
                    class="mt-2 text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded"
                  >
                    ✓ Completed
                  </div>
                  <div
                    v-else-if="currentSubStep === 3"
                    class="mt-2 text-xs text-blue-600 font-medium"
                  >
                    Current step
                  </div>
                </div>
              </div>

              <!-- Step 4 -->
              <div class="flex items-start gap-4">
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium text-sm transition-all',
                    currentSubStep >= 4 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500',
                  ]"
                >
                  {{ currentSubStep > 4 ? '✓' : '4' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium text-sm',
                      currentSubStep >= 4 ? 'text-gray-900' : 'text-gray-500',
                    ]"
                  >
                    Add details & publish
                  </h3>
                  <p class="text-xs text-gray-500 mt-1">Name and describe your content</p>
                  <div
                    v-if="currentSubStep > 4"
                    class="mt-2 text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded"
                  >
                    ✓ Completed
                  </div>
                  <div
                    v-else-if="currentSubStep === 4"
                    class="mt-2 text-xs text-blue-600 font-medium"
                  >
                    Current step
                  </div>
                </div>
              </div>

              <!-- Step 5 -->
              <div class="flex items-start gap-4">
                <div
                  :class="[
                    'w-8 h-8 rounded-full flex items-center justify-center font-medium text-sm transition-all',
                    currentSubStep >= 5 ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-500',
                  ]"
                >
                  {{ currentSubStep > 5 ? '✓' : '5' }}
                </div>
                <div class="flex-1 min-w-0">
                  <h3
                    :class="[
                      'font-medium text-sm',
                      currentSubStep >= 5 ? 'text-gray-900' : 'text-gray-500',
                    ]"
                  >
                    Review & Publish
                  </h3>
                  <p class="text-xs text-gray-500 mt-1">Final check and go live</p>
                  <div
                    v-if="currentSubStep > 5"
                    class="mt-2 text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded"
                  >
                    ✓ Completed
                  </div>
                  <div
                    v-else-if="currentSubStep === 5"
                    class="mt-2 text-xs text-blue-600 font-medium"
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
            <h1 class="text-2xl font-bold text-gray-900 mb-2">
              {{ stepTitles[currentSubStep - 1] }}
            </h1>
            <p class="text-gray-600">
              {{ stepDescriptions[currentSubStep - 1] }}
            </p>
          </div>

        <div>
          <!-- Step 4: Tell us more about it -->
          <div v-if="currentSubStep === 4" class="space-y-8">
            <!-- Interactive examples -->
            <div class="mb-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 class="font-medium text-blue-900 mb-3 flex items-center gap-2">
                <Lightbulb class="w-4 h-4" />
                Popular examples to get you started
              </h4>
              <p class="text-sm text-blue-800 mb-4">Click any example to auto-fill the form</p>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                <button
                  @click="fillExampleData('news')"
                  class="bg-white p-3 rounded border hover:border-blue-400 hover:shadow-sm transition-all text-left"
                >
                  <p class="font-medium text-gray-900">📰 News Archive</p>
                  <p class="text-gray-600 mt-1">"Herald Tribune Archives 2010-2024" - Historical articles and investigative reports</p>
                </button>
                <button
                  @click="fillExampleData('research')"
                  class="bg-white p-3 rounded border hover:border-blue-400 hover:shadow-sm transition-all text-left"
                >
                  <p class="font-medium text-gray-900">🔬 Research Data</p>
                  <p class="text-gray-600 mt-1">"Cancer Research Publications" - Peer-reviewed papers and clinical studies</p>
                </button>
                <button
                  @click="fillExampleData('library')"
                  class="bg-white p-3 rounded border hover:border-blue-400 hover:shadow-sm transition-all text-left"
                >
                  <p class="font-medium text-gray-900">📚 Document Library</p>
                  <p class="text-gray-600 mt-1">"Technical Manuals Collection" - Product guides and documentation</p>
                </button>
              </div>
            </div>

            <div class="space-y-6">
              <!-- Endpoint Name -->
              <div class="space-y-2">
                <Label for="endpoint-name" class="text-sm font-medium text-gray-700">
                  Name <span class="text-red-500">*</span>
                </Label>
                <Input
                  id="endpoint-name"
                  v-model="formData.endpointName"
                  placeholder="e.g., herald-tribune-archives"
                  class="w-full font-mono text-sm"
                />
                <p class="text-sm text-gray-500">This appears when people discover it. Keep it simple, no spaces</p>
              </div>

              <!-- Summary -->
              <div class="space-y-2">
                <Label for="summary" class="text-sm font-medium text-gray-700">
                  Short Description <span class="text-red-500">*</span>
                </Label>
                <Input
                  id="summary"
                  v-model="formData.summary"
                  placeholder="e.g., Historical news articles from 2010-2024"
                  class="w-full"
                />
                <p class="text-sm text-gray-500">
                  This appears when people browse available content
                </p>
              </div>

              <!-- Add More Details Toggle -->
              <div class="border-t pt-4">
                <button
                  @click="showAdvancedDetails = !showAdvancedDetails"
                  class="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 transition-colors"
                >
                  <ChevronRight 
                    :class="['w-4 h-4 transition-transform', showAdvancedDetails ? 'rotate-90' : '']"
                  />
                  Add more details (optional)
                </button>
              </div>

              <!-- Advanced Details -->
              <div v-if="showAdvancedDetails" class="space-y-4 pl-6 border-l-2 border-gray-100">
                <div class="space-y-2">
                  <Label for="description" class="text-sm font-medium text-gray-700">
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

              <!-- Tags -->
              <div class="space-y-2">
                <Label for="tags" class="text-sm font-medium text-gray-700"> Topics & Categories (Optional) </Label>
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
                      <button @click="removeTag(index)" class="ml-2 hover:text-gray-700">
                        <X class="h-3 w-3" />
                      </button>
                    </Badge>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Step 2: Choose Access Mechanism -->
          <div v-if="currentSubStep === 1" class="space-y-8">
            <!-- Data Source Selection Cards -->
            <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <!-- File System Card -->
              <Card
                class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-blue-300 hover:bg-gradient-to-br hover:from-blue-50 hover:to-indigo-50 border-2 bg-white"
                :class="
                  selectedDataSourceType === 'filesystem'
                    ? 'border-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50'
                    : 'border-gray-200'
                "
                @click="selectDataSourceType('filesystem')"
              >
                <CardContent class="p-6">
                  <div class="flex flex-col items-center text-center">
                    <div
                      class="w-14 h-14 rounded-full bg-blue-100 flex items-center justify-center mb-4"
                    >
                      <FileText class="w-7 h-7 text-blue-600" />
                    </div>

                    <h3 class="text-lg font-bold text-gray-900 mb-2">
                      Add Files
                    </h3>

                    <p class="text-sm text-gray-600 mb-3">
                      Upload PDFs, Word docs, spreadsheets, or text files
                    </p>

                    <div class="flex items-center gap-2 mb-3">
                      <span class="text-xs">📄</span>
                      <span class="text-xs">📊</span>
                      <span class="text-xs">📝</span>
                      <span class="text-xs">📋</span>
                      <span class="text-xs text-gray-400">PDF, DOCX, CSV, TXT</span>
                    </div>

                    <p class="text-xs text-gray-500">
                      Perfect for: News articles, research papers, books, reports
                    </p>
                  </div>
                </CardContent>
              </Card>

              <!-- Vector Database Card -->
              <Card
                class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-purple-300 hover:bg-gradient-to-br hover:from-purple-50 hover:to-pink-50 border-2 bg-white"
                :class="
                  selectedDataSourceType === 'vector'
                    ? 'border-purple-500 bg-gradient-to-br from-purple-50 to-pink-50'
                    : 'border-gray-200'
                "
                @click="selectDataSourceType('vector')"
              >
                <CardContent class="p-6">
                  <div class="flex flex-col items-center text-center">
                    <div
                      class="w-14 h-14 rounded-full bg-purple-100 flex items-center justify-center mb-4"
                    >
                      <Database class="w-7 h-7 text-purple-600" />
                    </div>

                    <h3 class="text-lg font-bold text-gray-900 mb-2">
                      Connect Database
                    </h3>

                    <p class="text-sm text-gray-600 mb-3">
                      Link your existing AI-ready database for smart search
                    </p>

                    <div class="flex items-center gap-2 mb-3">
                      <span class="text-xs">🔵</span>
                      <span class="text-xs">🔴</span>
                      <span class="text-xs">🟡</span>
                      <span class="text-xs text-gray-400">Weaviate, Qdrant, Chroma</span>
                    </div>

                    <div class="flex items-center gap-1">
                      <span class="text-xs bg-orange-100 text-orange-700 px-2 py-1 rounded-full font-medium">Advanced</span>
                      <span class="text-xs text-gray-500">Requires technical setup</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <!-- Existing Data Source Card -->
              <Card
                :class="[
                  'transition-all duration-200 border-2',
                  existingDataSourcesCount > 0 
                    ? 'cursor-pointer hover:shadow-lg hover:border-green-300 hover:bg-gradient-to-br hover:from-green-50 hover:to-emerald-50 bg-white' 
                    : 'cursor-not-allowed opacity-60 bg-gray-50',
                  selectedDataSourceType === 'existing'
                    ? 'border-green-500 bg-gradient-to-br from-green-50 to-emerald-50'
                    : existingDataSourcesCount > 0 ? 'border-gray-200' : 'border-gray-100'
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

                    <h3 class="text-lg font-bold text-gray-900 mb-2">
                      Use Existing Source
                    </h3>

                    <p class="text-sm text-gray-600 mb-3">Choose from data you've already connected</p>

                    <div v-if="existingDataSourcesCount > 0" class="mb-3">
                      <div class="flex items-center gap-1 mb-2">
                        <span class="text-xs">🔵</span>
                        <span class="text-xs text-gray-400">Legal Documents Store</span>
                      </div>
                      <div class="flex items-center gap-1 mb-2">
                        <span class="text-xs">🔴</span>
                        <span class="text-xs text-gray-400">Customer Analytics Store</span>
                      </div>
                      <div v-if="existingDataSourcesCount > 2" class="text-xs text-gray-400">
                        +{{ existingDataSourcesCount - 2 }} more...
                      </div>
                    </div>

                    <p :class="existingDataSourcesCount > 0 ? 'text-xs text-gray-500' : 'text-xs text-gray-400'">
                      {{ existingDataSourcesCount > 0 ? existingDataSourcesCount : 'No' }} data source{{
                        existingDataSourcesCount !== 1 ? 's' : ''
                      }}
                      available
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>

            <!-- Content based on selection -->
            <div v-if="selectedDataSourceType">
              <!-- File System Browser -->
              <div
                v-if="selectedDataSourceType === 'filesystem'"
                class="bg-white rounded-lg shadow-sm border border-gray-200 p-6"
              >
                <FileExplorer v-model="selectedFiles" />
              </div>

              <!-- Vector Database Configuration -->
              <div
                v-if="selectedDataSourceType === 'vector'"
                class="bg-white rounded-lg shadow-sm border border-gray-200 p-6"
              >
                <div class="mb-6">
                  <h3 class="text-lg font-medium text-gray-900 mb-2">Configure Vector Database</h3>
                  <p class="text-sm text-gray-600">
                    Select and configure your vector database connection
                  </p>
                </div>

                <!-- Inline version of CreateDatasetDialog content -->
                <div class="space-y-6">
                  <!-- Vector DB Type Selection -->
                  <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <div
                      v-for="db in vectorDatabases"
                      :key="db.id"
                      @click="db.isCustom ? openCustomSDKDocs() : (selectedVectorDB = db.id)"
                      :class="[
                        'flex flex-col items-center justify-center p-4 rounded-lg border cursor-pointer transition-all group h-32',
                        db.isCustom
                          ? 'border-purple-200 bg-gradient-to-r from-purple-50 to-blue-50 hover:border-purple-300 hover:bg-gradient-to-r hover:from-purple-100 hover:to-blue-100'
                          : selectedVectorDB === db.id
                            ? 'border-purple-500 bg-purple-50'
                            : 'border-gray-200 hover:bg-gray-50',
                      ]"
                    >
                      <div v-if="db.isCustom" class="transition-all duration-200 mb-2">
                        <div class="p-2 bg-purple-100 rounded-md group-hover:hidden">
                          <Code class="h-6 w-6 text-purple-600" />
                        </div>
                        <div class="hidden group-hover:block p-2 bg-purple-100 rounded-md">
                          <ExternalLink class="h-6 w-6 text-purple-600" />
                        </div>
                      </div>
                      <IntegrationIcon
                        v-else
                        :name="db.id"
                        class="h-10 w-10 mb-2"
                        :class="selectedVectorDB === db.id ? 'text-purple-600' : 'text-gray-600'"
                      />
                      <div
                        v-if="db.isCustom"
                        class="text-center transition-all duration-200 min-h-[1.25rem]"
                      >
                        <span class="text-sm font-medium text-purple-800 group-hover:hidden">
                          {{ db.name }}
                        </span>
                        <span class="hidden group-hover:block text-sm font-medium text-purple-800">
                          View documentation
                        </span>
                      </div>
                      <span
                        v-else
                        class="text-sm font-medium text-center"
                        :class="[selectedVectorDB === db.id ? 'text-purple-900' : 'text-gray-900']"
                      >
                        {{ db.name }}
                      </span>
                      <div
                        v-if="db.isCustom"
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
                  <div v-if="selectedVectorDB" class="mt-6 p-4 bg-gray-50 rounded-lg">
                    <p class="text-sm text-gray-600">
                      Configuration form for {{ selectedVectorDB }} will be implemented here
                    </p>
                  </div>
                </div>
              </div>

              <!-- Existing Data Sources List -->
              <div
                v-if="selectedDataSourceType === 'existing'"
                class="bg-white rounded-lg shadow-sm border border-gray-200 p-6"
              >
                <div class="space-y-4">
                  <h3 class="text-lg font-medium text-gray-900 mb-4">Available Data Sources</h3>

                  <RadioGroup v-model="formData.dataSource">
                    <div class="space-y-3">
                      <!-- Legal Documents Store -->
                      <div
                        class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50"
                        :class="
                          formData.dataSource === 'legal-docs'
                            ? 'border-green-500 bg-green-50'
                            : 'border-gray-200'
                        "
                        @click="formData.dataSource = 'legal-docs'"
                      >
                        <RadioGroupItem value="legal-docs" id="legal-docs" />
                        <Label
                          for="legal-docs"
                          class="flex items-center gap-3 cursor-pointer flex-1"
                        >
                          <div class="p-2 bg-purple-100 rounded">
                            <IntegrationIcon name="weaviate" class="h-5 w-5" />
                          </div>
                          <div class="flex-1">
                            <div class="flex items-center gap-2">
                              <span class="font-medium">Legal Documents Store</span>
                              <Badge variant="secondary" class="text-xs">Weaviate</Badge>
                              <Badge
                                variant="outline"
                                class="bg-green-50 text-green-700 border-green-200 text-xs"
                              >
                                running
                              </Badge>
                            </div>
                            <p class="text-sm text-gray-600 mt-1">
                              Vector database for legal document analysis
                            </p>
                          </div>
                        </Label>
                      </div>

                      <!-- Customer Analytics Store -->
                      <div
                        class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50"
                        :class="
                          formData.dataSource === 'customer-analytics'
                            ? 'border-green-500 bg-green-50'
                            : 'border-gray-200'
                        "
                        @click="formData.dataSource = 'customer-analytics'"
                      >
                        <RadioGroupItem value="customer-analytics" id="customer-analytics" />
                        <Label
                          for="customer-analytics"
                          class="flex items-center gap-3 cursor-pointer flex-1"
                        >
                          <div class="p-2 bg-blue-100 rounded">
                            <IntegrationIcon name="qdrant" class="h-5 w-5" />
                          </div>
                          <div class="flex-1">
                            <div class="flex items-center gap-2">
                              <span class="font-medium">Customer Analytics Store</span>
                              <Badge variant="secondary" class="text-xs">Qdrant</Badge>
                              <Badge
                                variant="outline"
                                class="bg-green-50 text-green-700 border-green-200 text-xs"
                              >
                                running
                              </Badge>
                            </div>
                            <p class="text-sm text-gray-600 mt-1">
                              Customer behavior analysis and segmentation
                            </p>
                          </div>
                        </Label>
                      </div>

                      <!-- Research Database -->
                      <div
                        class="flex items-center space-x-3 p-4 border rounded-lg cursor-pointer hover:bg-gray-50"
                        :class="
                          formData.dataSource === 'research-db'
                            ? 'border-green-500 bg-green-50'
                            : 'border-gray-200'
                        "
                        @click="formData.dataSource = 'research-db'"
                      >
                        <RadioGroupItem value="research-db" id="research-db" />
                        <Label
                          for="research-db"
                          class="flex items-center gap-3 cursor-pointer flex-1"
                        >
                          <div class="p-2 bg-green-100 rounded">
                            <IntegrationIcon name="chroma" class="h-5 w-5" />
                          </div>
                          <div class="flex-1">
                            <div class="flex items-center gap-2">
                              <span class="font-medium">Research Database</span>
                              <Badge variant="secondary" class="text-xs">Chroma</Badge>
                              <Badge
                                variant="outline"
                                class="bg-gray-50 text-gray-600 border-gray-200 text-xs"
                              >
                                stopped
                              </Badge>
                            </div>
                            <p class="text-sm text-gray-600 mt-1">
                              Research papers and scientific literature
                            </p>
                          </div>
                        </Label>
                      </div>
                    </div>
                  </RadioGroup>
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
                class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-blue-300 hover:bg-gradient-to-br hover:from-blue-50 hover:to-indigo-50 border-2 bg-white"
                :class="
                  formData.responseType === 'raw'
                    ? 'border-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50'
                    : 'border-gray-200'
                "
                @click="selectResponseType('raw')"
              >
                <CardContent class="p-4">
                  <div class="flex flex-col items-center text-center">
                    <div
                      class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center mb-3"
                    >
                      <FileType class="w-5 h-5 text-blue-600" />
                    </div>

                    <h3 class="text-lg font-bold text-gray-900 mb-2">Search & Quote</h3>
                    <p class="text-xs font-medium mb-2 text-blue-600">Return exact text matches</p>

                    <p class="text-sm text-gray-600 mb-2 text-balance">
                      Users search your content and get back the exact matching text
                    </p>

                    <p class="text-xs text-gray-500 text-balance">
                      Best for: News archives, research papers, legal documents
                    </p>
                  </div>
                </CardContent>
              </Card>

              <!-- AI-Generated Summary Card -->
              <Card
                class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-purple-300 hover:bg-gradient-to-br hover:from-purple-50 hover:to-pink-50 border-2 bg-white"
                :class="
                  formData.responseType === 'summary'
                    ? 'border-purple-500 bg-gradient-to-br from-purple-50 to-pink-50'
                    : 'border-gray-200'
                "
                @click="selectResponseType('summary')"
              >
                <CardContent class="p-4">
                  <div class="flex flex-col items-center text-center">
                    <div
                      class="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center mb-3"
                    >
                      <Sparkles class="w-5 h-5 text-purple-600" />
                    </div>

                    <h3 class="text-lg font-bold text-gray-900 mb-2">AI Assistant</h3>
                    <p class="text-xs font-medium mb-2 text-purple-600">Smart answers from your data</p>

                    <p class="text-sm text-gray-600 mb-2 text-balance">
                      An AI reads your content and provides intelligent answers
                    </p>

                    <p class="text-xs text-gray-500 text-balance">
                      Best for: Customer support, knowledge bases, Q&A systems
                    </p>
                  </div>
                </CardContent>
              </Card>

              <!-- Both Raw and Summary Card -->
              <Card
                class="cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-green-300 hover:bg-gradient-to-br hover:from-green-50 hover:to-emerald-50 border-2 bg-white relative"
                :class="
                  formData.responseType === 'both'
                    ? 'border-green-500 bg-gradient-to-br from-green-50 to-emerald-50'
                    : 'border-gray-200'
                "
                @click="selectResponseType('both')"
              >
                <CardContent class="p-4">
                  <div class="flex flex-col items-center text-center">
                    <div
                      class="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center mb-3"
                    >
                      <GitMerge class="w-5 h-5 text-green-600" />
                    </div>

                    <h3 class="text-lg font-bold text-gray-900 mb-2">Search + AI</h3>
                    <p class="text-xs font-medium mb-2 text-green-600">
                      Complete solution
                    </p>

                    <p class="text-sm text-gray-600 mb-2 text-balance">
                      Users get both exact quotes and AI-powered answers
                    </p>

                    <p class="text-xs text-gray-500 text-balance">
                      Best for: Academic resources, comprehensive documentation
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>

              <!-- Advanced AI Model Selection (collapsible) -->
              <div
                v-if="formData.responseType === 'summary' || formData.responseType === 'both'"
                class="bg-white rounded-lg shadow-sm border border-gray-200"
              >
                <button
                  @click="showAdvancedOptions = !showAdvancedOptions"
                  class="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-gray-50"
                >
                  <div>
                    <h4 class="font-medium text-gray-900">Advanced - Choose Local AI Model</h4>
                    <p class="text-sm text-gray-600 mt-1">Customize AI settings and model selection</p>
                  </div>
                  <ChevronRight 
                    :class="['w-5 h-5 text-gray-400 transition-transform', showAdvancedOptions ? 'rotate-90' : '']"
                  />
                </button>
                
                <div v-if="showAdvancedOptions" class="px-6 pb-6 border-t border-gray-200">
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

          <!-- Step 3: Set Rules & Pricing -->
          <div
            v-if="currentSubStep === 3"
            class="bg-white rounded-lg shadow-sm border border-gray-200 p-8"
          >

            <!-- Policy Configuration -->
            <div class="space-y-4">
              <div
                v-for="policy in policyTypes"
                :key="policy.id"
                class="bg-white border border-gray-200 rounded-lg p-4"
              >
                <!-- Policy Header -->
                <div class="flex items-center justify-between mb-3">
                  <div class="flex items-center gap-3">
                    <div
                      :class="{
                        'p-2 rounded-lg bg-blue-100': policy.color === 'blue',
                        'p-2 rounded-lg bg-green-100': policy.color === 'green',
                        'p-2 rounded-lg bg-yellow-100': policy.color === 'yellow',
                        'p-2 rounded-lg bg-purple-100': policy.color === 'purple',
                        'p-2 rounded-lg bg-red-100': policy.color === 'red',
                      }"
                    >
                      <component
                        :is="policy.icon"
                        :class="{
                          'h-5 w-5 text-blue-600': policy.color === 'blue',
                          'h-5 w-5 text-green-600': policy.color === 'green',
                          'h-5 w-5 text-yellow-600': policy.color === 'yellow',
                          'h-5 w-5 text-purple-600': policy.color === 'purple',
                          'h-5 w-5 text-red-600': policy.color === 'red',
                        }"
                      />
                    </div>
                    <div class="flex-1">
                      <h3 class="font-medium text-gray-900">{{ policy.label }}</h3>
                      <p class="text-sm text-gray-600">{{ policy.description }}</p>
                    </div>
                  </div>
                  <Button @click="addPolicy(policy.id)" variant="outline" size="sm">
                    <Plus class="h-4 w-4 mr-2" />
                    Add {{ policy.name }} rule
                  </Button>
                </div>

                <!-- Default Policy Message -->
                <div v-if="policyRules[policy.id]?.length === 0" class="mb-3">
                  <div class="p-3 bg-green-50 border border-green-200 rounded-lg">
                    <p class="text-sm text-green-800">
                      <strong>Default:</strong> 
                      <span v-if="policy.id === 'authorization'">Open access - everyone can use your endpoint</span>
                      <span v-else-if="policy.id === 'ratelimiter'">No rate limits - unlimited usage</span>
                      <span v-else-if="policy.id === 'pricing'">Free access - no charges applied</span>
                      <span v-else-if="policy.id === 'manual-approval'">Automatic approval - no manual review required</span>
                      <span v-else>Open access - most permissive settings</span>
                    </p>
                  </div>
                </div>

                <!-- Empty State -->
                <div
                  v-if="policyRules[policy.id]?.length === 0"
                  class="text-center py-6 border-2 border-dashed border-gray-200 rounded-lg"
                >
                  <p class="text-gray-500">No {{ policy.name.toLowerCase() }} rule added yet</p>
                </div>

                <!-- Policy Rules -->
                <div v-if="policyRules[policy.id]?.length > 0" class="space-y-3">
                  <div
                    v-for="rule in policyRules[policy.id] || []"
                    :key="rule.id"
                    class="border border-gray-200 rounded-lg p-3"
                  >
                    <!-- Rule in Edit Mode (Expanded) -->
                    <div v-if="rule.isEditing" class="space-y-4">
                      <!-- All the simplified policy forms will be added here -->
                    </div>

                    <!-- Rule in Collapsed Mode -->
                    <div v-else class="flex items-start justify-between">
                      <div class="flex-1">
                        <h4 class="text-sm font-medium text-gray-900">
                          {{ rule.config.note || `${policy.name} Rule` }}
                        </h4>
                        <p class="text-xs text-gray-600 mt-1">Rule summary</p>
                      </div>
                      <div class="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          @click="editPolicy(policy.id, rule.id)"
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
            </div>
          </div>

          <!-- Step 5: Ready to Publish -->
          <div v-if="currentSubStep === 5" class="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
              <div class="space-y-6">
                <div>
                  <h2 class="text-xl font-semibold text-gray-900 mb-2">Ready to Publish?</h2>
                  <p class="text-sm text-gray-600">
                    Double-check everything looks right. You can always change these settings later.
                  </p>
                </div>

                <!-- Basic Information -->
                <div class="border-l-4 border-blue-500 pl-4">
                  <h3 class="font-medium text-gray-900 mb-2">Your Content</h3>
                  <div class="space-y-3 text-sm">
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

                <!-- Data Source -->
                <div class="border-l-4 border-purple-500 pl-4">
                  <h3 class="font-medium text-gray-900 mb-2">Source & Files</h3>
                  <div class="text-sm space-y-2">
                    <div v-if="selectedDataSourceType === 'filesystem'">
                      <p><span class="font-medium">Type:</span> Uploaded Files</p>
                      <p>
                        <span class="font-medium">Files:</span>
                        {{
                          selectedFiles.length > 0
                            ? selectedFiles.length + ' file' + (selectedFiles.length > 1 ? 's' : '') + ' ready'
                            : 'No files selected yet'
                        }}
                      </p>
                      <div v-if="selectedFiles.length > 0" class="mt-2 max-h-32 overflow-y-auto">
                        <ul class="text-xs text-gray-600 space-y-1">
                          <li
                            v-for="file in selectedFiles"
                            :key="file"
                            class="flex items-center gap-1"
                          >
                            <FileText class="w-3 h-3" />
                            {{ file }}
                          </li>
                        </ul>
                      </div>
                    </div>
                    <div v-else-if="selectedDataSourceType === 'vector'">
                      <p><span class="font-medium">Type:</span> Vector Database</p>
                      <p>
                        <span class="font-medium">Database:</span>
                        {{ selectedVectorDB || 'Not selected' }}
                      </p>
                      <p v-if="selectedVectorDB" class="text-gray-600">
                        Configuration will be completed during deployment
                      </p>
                    </div>
                    <div v-else-if="selectedDataSourceType === 'existing'">
                      <p><span class="font-medium">Type:</span> Existing Data Source</p>
                      <div v-if="formData.dataSource === 'legal-docs'">
                        <p><span class="font-medium">Source:</span> Legal Documents Store</p>
                        <p><span class="font-medium">Database:</span> Weaviate</p>
                        <p>
                          <span class="font-medium">Status:</span>
                          <Badge
                            variant="outline"
                            class="bg-green-50 text-green-700 border-green-200 text-xs"
                            >Running</Badge
                          >
                        </p>
                        <p class="text-gray-600">Vector database for legal document analysis</p>
                      </div>
                      <div v-else-if="formData.dataSource === 'customer-analytics'">
                        <p><span class="font-medium">Source:</span> Customer Analytics Store</p>
                        <p><span class="font-medium">Database:</span> Qdrant</p>
                        <p>
                          <span class="font-medium">Status:</span>
                          <Badge
                            variant="outline"
                            class="bg-green-50 text-green-700 border-green-200 text-xs"
                            >Running</Badge
                          >
                        </p>
                        <p class="text-gray-600">Customer behavior analysis and segmentation</p>
                      </div>
                      <div v-else-if="formData.dataSource === 'research-db'">
                        <p><span class="font-medium">Source:</span> Research Database</p>
                        <p><span class="font-medium">Database:</span> Chroma</p>
                        <p>
                          <span class="font-medium">Status:</span>
                          <Badge
                            variant="outline"
                            class="bg-gray-50 text-gray-600 border-gray-200 text-xs"
                            >Stopped</Badge
                          >
                        </p>
                        <p class="text-gray-600">Research papers and scientific literature</p>
                      </div>
                      <p v-if="!formData.dataSource">Not selected</p>
                    </div>
                    <p v-else>Not configured</p>
                  </div>
                </div>

                <!-- Output Configuration -->
                <div class="border-l-4 border-green-500 pl-4">
                  <h3 class="font-medium text-gray-900 mb-2">Output Configuration</h3>
                  <div class="text-sm space-y-1">
                    <p v-if="formData.responseType === 'raw'">
                      <span class="font-medium">Response Type:</span> Raw Document Chunks
                    </p>
                    <p v-else-if="formData.responseType === 'summary'">
                      <span class="font-medium">Response Type:</span> AI-Generated Summary
                    </p>
                    <p v-else-if="formData.responseType === 'both'">
                      <span class="font-medium">Response Type:</span> Both References & Summary
                    </p>
                    <p v-else>Not configured</p>

                    <div
                      v-if="formData.responseType === 'summary' || formData.responseType === 'both'"
                    >
                      <div v-if="formData.aiModel && getSelectedModel()">
                        <p>
                          <span class="font-medium">AI Model:</span> {{ getSelectedModel()?.name }}
                        </p>
                        <p>
                          <span class="font-medium">Provider:</span> {{ getSelectedModel()?.type }}
                        </p>
                        <p>
                          <span class="font-medium">Status:</span>
                          <Badge
                            variant="outline"
                            :class="
                              getSelectedModel()?.status === 'running'
                                ? 'bg-green-50 text-green-700 border-green-200'
                                : 'bg-gray-50 text-gray-600 border-gray-200'
                            "
                            class="text-xs"
                          >
                            {{ getSelectedModel()?.status === 'running' ? 'Running' : 'Stopped' }}
                          </Badge>
                        </p>
                      </div>
                      <p v-else>Not configured</p>
                    </div>
                  </div>
                </div>

                <!-- Applied Policies -->
                <div class="border-l-4 border-orange-500 pl-4">
                  <h3 class="font-medium text-gray-900 mb-2">Applied Policies</h3>
                  <div class="text-sm space-y-2">
                    <div
                      v-if="Object.keys(getAppliedPoliciesGrouped()).length > 0"
                      class="space-y-6"
                    >
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
                                <p class="flex items-start">
                                  <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                    >Applies to:</span
                                  >
                                  <span v-if="rule.config.userType === 'all'">All users</span>
                                  <span v-else-if="rule.config.userType === 'only'"
                                    >Only: {{ rule.config.users || 'No users specified' }}</span
                                  >
                                  <span v-else-if="rule.config.userType === 'except'"
                                    >Everyone except:
                                    {{ rule.config.users || 'No users specified' }}</span
                                  >
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
                                <p class="flex items-start">
                                  <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                    >Apply to:</span
                                  >
                                  <span v-if="rule.config.userType === 'all'">All users</span>
                                  <span v-else-if="rule.config.userType === 'only'"
                                    >Only: {{ rule.config.users || 'No users specified' }}</span
                                  >
                                  <span v-else-if="rule.config.userType === 'except'"
                                    >Everyone except:
                                    {{ rule.config.users || 'No users specified' }}</span
                                  >
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
                                <p class="flex items-start">
                                  <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                    >Apply to:</span
                                  >
                                  <span v-if="rule.config.userType === 'all'">All users</span>
                                  <span v-else-if="rule.config.userType === 'only'"
                                    >Only: {{ rule.config.users || 'No users specified' }}</span
                                  >
                                  <span v-else-if="rule.config.userType === 'except'"
                                    >Everyone except:
                                    {{ rule.config.users || 'No users specified' }}</span
                                  >
                                </p>
                                <p
                                  v-if="
                                    rule.config.destination === 'email' &&
                                    rule.config.emailAddresses
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
                                    rule.config.destination === 'slack' &&
                                    rule.config.slackWebhookUrl
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
                                <p class="flex items-start">
                                  <span class="font-medium text-gray-500 w-20 flex-shrink-0"
                                    >Apply to:</span
                                  >
                                  <span v-if="rule.config.userType === 'all'">All users</span>
                                  <span v-else-if="rule.config.userType === 'only'"
                                    >Only: {{ rule.config.users || 'No users specified' }}</span
                                  >
                                  <span v-else-if="rule.config.userType === 'except'"
                                    >Everyone except:
                                    {{ rule.config.users || 'No users specified' }}</span
                                  >
                                </p>
                                <div v-if="rule.config.prompt" class="mt-2">
                                  <p class="font-medium text-gray-500 mb-2">Prompt:</p>
                                  <div
                                    class="text-xs bg-white border rounded px-3 py-2 font-mono max-h-32 overflow-y-auto whitespace-pre-wrap"
                                  >
                                    {{ rule.config.prompt }}
                                  </div>
                                </div>
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
            <div v-if="currentSubStep === 5" class="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
              <div class="space-y-6">
                <div>
                  <h2 class="text-xl font-semibold text-gray-900 mb-2">Endpoint Visibility</h2>
                  <p class="text-sm text-gray-600">Configure who can discover your endpoint</p>
                  <div class="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg">
                    <p class="text-sm text-green-800">
                      <strong>Default:</strong> Public access - anyone can discover and use your endpoint
                    </p>
                  </div>
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
                      Add email addresses of users who can discover this endpoint. You can leave
                      this empty and add users later from the endpoint details page.
                    </p>
                  </div>

                  <div class="flex gap-2">
                    <Input
                      v-model="allowedUserInput"
                      @keydown.enter.prevent="addAllowedUser"
                      placeholder="user@example.com"
                      :class="[
                        'flex-1',
                        hasInputError
                          ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                          : '',
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
              class="bg-blue-600 hover:bg-blue-700 text-white px-8 ml-auto"
            >
              {{ currentSubStep === 5 ? 'Publish Now' : 'Continue' }}
              <ArrowRight class="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Data Source Dialog -->
    <CreateDatasetDialog
      v-model:open="showCreateDataSourceDialog"
      @data-source-created="handleDataSourceCreated"
    />

    <!-- Create Model Dialog -->
    <CreateModelDialog v-model:open="showCreateModelDialog" @model-created="handleModelCreated" />
  </ErrorBoundary>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  Database,
  Plus,
  X,
  ArrowRight,
  FileText,
  FolderOpen,
  Code,
  FileType,
  Sparkles,
  GitMerge,
  Save,
  ExternalLink,
  Shield,
  Gauge,
  DollarSign,
  UserCheck,
  Filter,
  Globe,
  Lock,
  Lightbulb,
  ChevronRight,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { MdEditor, MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import IntegrationIcon from '@/components/IntegrationIcons.vue'
import CreateDatasetDialog from '@/components/CreateDatasetDialog.vue'
import CreateModelDialog from '@/components/CreateModelDialog.vue'
import FileExplorer from '@/components/FileExplorer.vue'
import ModelSelector from '@/components/ModelSelector.vue'
import ErrorBoundary from '@/components/ErrorBoundary.vue'
import { mockModels } from '@/stores/models'

const router = useRouter()

// Sub-step navigation
const currentSubStep = ref(1)

// Progressive disclosure
const showAdvancedOptions = ref(false)
const showAdvancedDetails = ref(false)

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

// Step titles and descriptions
const stepTitles = [
  'What do you want to share?',
  'How should it work?',
  'Who can access it?',
  'Add details & publish',
]

const stepDescriptions = [
  'Upload files or connect to your existing database',
  'Decide the format of the response users can receive from this content. Search provides most accuracy, while AI assistant answers are more nuanced.',
  'Control who can access your content and whether to charge for it',
  'Give your content a name and description so others know what you\'re sharing',
]

// Form data
const formData = ref({
  endpointName: '',
  summary: '',
  description: '',
  tags: [] as string[],
  dataSource: '',
  responseType: 'both', // Default to Search + AI
  aiModel: 'code-assistant', // Default to the running Ollama model
  policies: {} as Record<string, boolean>,
})

// Data source selection
const selectedDataSourceType = ref<string | null>(null)
const selectedVectorDB = ref<string | null>(null)
const selectedFiles = ref<string[]>([])

// Model source selection (unused variables removed)

// Tag input
const tagInput = ref('')

// Dialog states
const showCreateDataSourceDialog = ref(false)
const showCreateModelDialog = ref(false)

// Endpoint visibility
const endpointVisibility = ref<string>('public')
const allowedUsers = ref<string[]>([])
const allowedUserInput = ref('')
const allowedUserError = ref('')
const hasInputError = ref(false)

// Policy configurations
// Policy type keys as a union type
type PolicyTypeId = 'authorization' | 'ratelimiter' | 'pricing' | 'manual-approval' | 'ai-filters'

interface PolicyConfig {
  id: string
  [key: string]: string | number
}

interface PolicyRule {
  id: string
  config: PolicyConfig
  isEditing: boolean
}

// Policy type interface
interface PolicyType {
  id: PolicyTypeId
  name: string
  label: string
  description: string
  icon: typeof Shield | typeof Gauge | typeof DollarSign | typeof UserCheck | typeof Filter
  color: string
}

// Policy rules record type
type PolicyRulesRecord = Record<PolicyTypeId, PolicyRule[]>

// Grouped policy interface for the review section
interface GroupedPolicy {
  type: string
  icon: typeof Shield | typeof Gauge | typeof DollarSign | typeof UserCheck | typeof Filter
  color: string
  rules: {
    id: string
    name: string
    config: PolicyConfig
  }[]
}

const policyRules = ref<PolicyRulesRecord>({
  authorization: [],
  ratelimiter: [],
  pricing: [],
  'manual-approval': [],
  'ai-filters': [],
})

// Currently editing rule ID for each policy type
const editingRuleId = ref<Record<PolicyTypeId, string | null>>({
  authorization: null,
  ratelimiter: null,
  pricing: null,
  'manual-approval': null,
  'ai-filters': null,
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
  destination: 'inbox',
  emailAddresses: '',
  slackWebhookUrl: '',
  whatsappNumber: '',
  timeoutValue: '24',
  timeoutUnit: 'hour',
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
  {
    id: 'ai-filters',
    name: 'AI filters',
    label: 'Content moderation',
    description: 'Automatically filter out inappropriate or sensitive information',
    icon: Filter,
    color: 'red',
  },
]

// Vector databases options (from CreateDatasetDialog)
const vectorDatabases = [
  { id: 'weaviate', name: 'Weaviate' },
  { id: 'qdrant', name: 'Qdrant' },
  { id: 'chroma', name: 'Chroma' },
  { id: 'custom', name: 'Custom', isCustom: true },
]

// Model options removed - unused

// Count of existing data sources
const existingDataSourcesCount = computed(() => 3) // Based on the 3 sources in SettingsPage

// Watch for data source selection - removed since we no longer use radio button for create new

// Watch for AI model selection - removed since we no longer use radio button for create new

// Step validation
const isStep1Valid = computed(() => {
  return formData.value.endpointName.trim() !== '' && formData.value.summary.trim() !== ''
})

// Can save draft when we have name
const canSaveDraft = computed(() => formData.value.endpointName.trim() !== '')

const isStep2Valid = computed(() => {
  if (selectedDataSourceType.value === 'existing') {
    return formData.value.dataSource !== ''
  } else if (selectedDataSourceType.value === 'vector') {
    return selectedVectorDB.value !== null
  } else if (selectedDataSourceType.value === 'filesystem') {
    return selectedFiles.value.length > 0
  }
  return false
})

const isStep3Valid = computed(() => {
  const hasResponseType = formData.value.responseType !== ''
  const needsModel =
    formData.value.responseType === 'summary' || formData.value.responseType === 'both'

  if (!needsModel) {
    return hasResponseType
  }

  // If model is needed, check if a model is selected (either existing or create-new)
  return hasResponseType && formData.value.aiModel !== ''
})

const isStep4Valid = computed(() => {
  // Step 4 (policies) is always valid - policies are optional
  return true
})

const isStep5Valid = computed(() => {
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
  if (currentSubStep.value === 1) return isStep2Valid.value  // Step 1 is now "Choose your data" (was step 2)
  if (currentSubStep.value === 2) return isStep3Valid.value  // Step 2 is now "Choose response format" (was step 3) 
  if (currentSubStep.value === 3) return isStep4Valid.value  // Step 3 is now "Set Rules & Pricing" (was step 4)
  if (currentSubStep.value === 4) return isStep1Valid.value  // Step 4 is now "Tell us more about it" (was step 1)
  return isStep5Valid.value                                 // Step 5 remains "Review & Publish"
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

// Fill example data
const fillExampleData = (exampleType: 'news' | 'research' | 'library') => {
  switch (exampleType) {
    case 'news':
      formData.value.endpointName = 'herald-tribune-archives'
      formData.value.summary = 'Historical news articles from 2010-2024'
      formData.value.description = `## Dataset Overview
Complete digital archive of Herald Tribune newspaper articles spanning 14 years of journalism, including investigative reporting, breaking news, editorial content, and community coverage.

## Content Description
- **Data types**: Full-text articles, headlines, bylines, publication metadata
- **Size**: ~45,000 articles across 5,110 daily editions
- **Format**: Structured text (JSON), original PDFs available
- **Languages**: English (primary), some Spanish community coverage

## Data Collection
- **Source**: Herald Tribune newspaper digital publishing system
- **Collection method**: Daily automated archival from CMS
- **Time period**: January 2010 - December 2024
- **Update frequency**: Daily (new articles added within 24 hours)

## Potential Use Cases
- Media trend analysis and journalism research
- Historical event documentation and timeline construction
- Natural language processing and sentiment analysis
- Local community impact studies
- Citation and fact-checking for academic research

## Data Quality & Limitations
- **Completeness**: 99.2% coverage (some technical outages in 2018)
- **Accuracy**: Editorial standards maintained, corrections noted
- **Biases**: Regional focus on local/state issues, editorial perspective reflected
- **Ethical considerations**: Public domain articles, privacy-sensitive content redacted

## Citation & Attribution
"Herald Tribune Archives (2010-2024)." Please cite as: Herald Tribune Digital Archive, accessed [date]. Attribution required for commercial use.`
      formData.value.tags = ['news', 'journalism', 'politics', 'business', 'local-news']
      break
      
    case 'research':
      formData.value.endpointName = 'cancer-research-publications'
      formData.value.summary = 'Peer-reviewed cancer research papers and clinical studies'
      formData.value.description = `## Dataset Overview
Curated collection of peer-reviewed cancer research publications from high-impact medical journals, focusing on treatment efficacy, prevention strategies, and clinical trial outcomes.

## Content Description
- **Data types**: Research abstracts, full-text papers, metadata, citation networks
- **Size**: 12,847 papers from 156 journals (2.3GB structured data)
- **Format**: JSON metadata, PDF full-text, CSV summary tables
- **Languages**: English (94%), with abstracts in original languages

## Data Collection
- **Source**: PubMed, PMC, journal APIs (Nature, NEJM, Lancet, JCO)
- **Collection method**: Automated API harvesting with manual curation
- **Time period**: January 2015 - Present (9+ years)
- **Update frequency**: Weekly updates with 2-week embargo

## Potential Use Cases
- Systematic reviews and meta-analyses
- Drug discovery and biomarker identification  
- Clinical decision support systems
- Medical education and training datasets
- Healthcare policy evidence synthesis
- AI/ML model training for medical NLP

## Data Quality & Limitations
- **Completeness**: 85% coverage of major oncology journals (paywall limitations)
- **Accuracy**: Peer-reviewed sources only, automated extraction ~97% accurate
- **Biases**: English-language bias, overrepresentation of Western research
- **Ethical considerations**: IRB-approved studies only, patient privacy protected

## Citation & Attribution
Cite individual papers per journal requirements. Dataset citation: "Cancer Research Publications Dataset v2.1" DOI: 10.5281/zenodo.example. Institutional access required for full text.`
      formData.value.tags = ['research', 'medical', 'oncology', 'clinical-trials', 'peer-reviewed']
      break
      
    case 'library':
      formData.value.endpointName = 'technical-manuals-collection'
      formData.value.summary = 'Product guides and technical documentation'
      formData.value.description = `## Dataset Overview
Comprehensive technical documentation library containing user manuals, API references, installation guides, and system administration procedures across multiple technology domains.

## Content Description
- **Data types**: Technical documents, code examples, configuration files, diagrams
- **Size**: 3,200+ documents totaling 1.8GB (PDF, Markdown, HTML)
- **Format**: Structured docs (Markdown), PDFs, interactive examples
- **Languages**: English (primary), with localized versions in 12 languages

## Data Collection
- **Source**: Official product documentation, open-source projects, vendor portals
- **Collection method**: Automated scraping with manual quality control
- **Time period**: 2020-Present (focus on current/supported versions)
- **Update frequency**: Monthly synchronization with upstream sources

## Potential Use Cases
- Developer onboarding and training programs
- Technical support and troubleshooting automation
- Documentation standardization projects
- API integration and system deployment
- Technical writing style analysis
- Search and knowledge base systems

## Data Quality & Limitations
- **Completeness**: 95% coverage of major platforms (some proprietary docs excluded)
- **Accuracy**: Version-controlled, links verified quarterly
- **Biases**: Emphasis on popular/widely-adopted technologies
- **Ethical considerations**: Respects vendor licensing, no proprietary code included

## Citation & Attribution
Reference original vendor documentation. Collection metadata: "Technical Documentation Corpus v3.2" - Educational and commercial use permitted with attribution.`
      formData.value.tags = ['documentation', 'technical', 'manuals', 'api', 'guides']
      break
  }
}

// Apply access presets

// Select data source type
const selectDataSourceType = (type: string) => {
  selectedDataSourceType.value = type
  // Reset selections when changing type
  if (type !== 'existing') {
    formData.value.dataSource = ''
  }
  if (type !== 'vector') {
    selectedVectorDB.value = null
  }
  if (type !== 'filesystem') {
    selectedFiles.value = []
  }
}

// Select response type
const selectResponseType = (type: 'raw' | 'summary' | 'both') => {
  formData.value.responseType = type
}

// Handle data source created
const handleDataSourceCreated = () => {
  // In a real app, this would update the data source list
  console.log('Data source created')
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
    const typedPolicyId = policyId as PolicyTypeId
    if (rules.length > 0) {
      const policyType = policyTypes.find((p) => p.id === typedPolicyId)
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
        timeoutValue: (config.timeoutValue as string) || '24',
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

// Real-time preview tags for forms

// Navigation handlers
const handleNext = () => {
  if (!isCurrentStepValid.value) return

  if (currentSubStep.value < 5) {
    currentSubStep.value++
  } else {
    // Deploy the endpoint
    console.log('Deploying endpoint with data:', formData.value)
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
  // localStorage.setItem('dataEndpointDraft', JSON.stringify(formData.value))
}

// Open custom SDK documentation
const openCustomSDKDocs = () => {
  window.open('https://docs.openmined.org/custom-data-sources', '_blank')
}

// Open custom policies documentation

// Get selected model details
const getSelectedModel = () => {
  return mockModels.find((model) => model.id === formData.value.aiModel)
}

// Handle AI Filter Create Model

// Handle Step 3 Create Model
const handleStep3CreateModel = () => {
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

      // Auto-clear error after 5 seconds
      setTimeout(() => {
        allowedUserError.value = ''
        hasInputError.value = false
      }, 5000)
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

// Form refresh function for error boundary retry
const refreshForm = () => {
  // In a real app, this would reset form state and reload data
  console.log('Refreshing endpoint creation form...')
  // Could reset form data to initial state
}

</script>
